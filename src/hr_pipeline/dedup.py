import pandas as pd
from rapidfuzz import fuzz

from hr_pipeline.utils.logging import get_logger


logger = get_logger(__name__)

HRIS_SOURCE_SYSTEMS = ["globaltech_hris", "acquiredco_hris"]
ENRICHMENT_SOURCE_SYSTEMS = ["payroll", "benefits"]

def combine_cleaned_sources(
    cleaned_dataframes: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    Combine all cleaned source DataFrames into one long DataFrame.

    The input DataFrames are expected to share the same canonical schema.
    """
    combined = pd.concat(
        cleaned_dataframes.values(),
        ignore_index=True,
        sort=False
    )
    
    logger.info("Combined cleaned sources into %s total records", len(combined))
    return combined

def build_source_systems(values: pd.Series) -> str:
    """
    Build a stable pipe-delimited source system provenance string.
    """
    source_systems = sorted(
        str(value) for value in values.dropna().unique()
    )
    
    return "|".join(source_systems)

def deduplicate_hris_identity_records(
    hris_records: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Reduce HRIS identity records to one row per employee_id.

    Duplicate HRIS identity rows are preserved in a review DataFrame, while
    the golden dataset keeps one preferred identity record per employee_id.

    Selection rule:
    - Prefer rows with more populated identity fields.
    - Then keep the first stable record by employee_id/source_system.
    """
    duplicate_mask = hris_records.duplicated(
        subset=["employee_id"],
        keep=False,
    )

    duplicate_review = hris_records[duplicate_mask].copy()
    duplicate_review["duplicate_check"] = "hris_employee_id"

    if duplicate_review.empty:
        logger.info("No duplicate HRIS employee_id records found")
        return hris_records, duplicate_review

    identity_quality_columns = [
        "full_name",
        "email",
        "department",
        "job_title",
        "manager_id",
        "employment_type",
        "country",
        "hire_date",
    ]

    available_quality_columns = [
        column
        for column in identity_quality_columns
        if column in hris_records.columns
    ]

    hris_records = hris_records.copy()
    hris_records["_identity_completeness_score"] = hris_records[
        available_quality_columns
    ].notna().sum(axis=1)

    hris_records = hris_records.sort_values(
        by=[
            "employee_id",
            "_identity_completeness_score",
            "source_system",
        ],
        ascending=[True, False, True],
    )

    deduplicated = hris_records.drop_duplicates(
        subset=["employee_id"],
        keep="first",
    ).drop(columns=["_identity_completeness_score"])

    logger.warning(
        "Duplicate HRIS employee_id records found: duplicate_rows=%s duplicate_employee_ids=%s",
        len(duplicate_review),
        duplicate_review["employee_id"].nunique(),
    )

    return deduplicated, duplicate_review

def build_exact_id_golden_dataset(combined: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build an initial golden employee dataset using exact employee_id matching.

    HRIS records are treated as identity records. Payroll and benefits are
    treated as enrichment records. Enrichment records without a matching HRIS
    employee_id are returned as ghost records.
    """
    hris_records = combined[
        combined["source_system"].isin(HRIS_SOURCE_SYSTEMS)
    ].copy()
    
    enrichment_columns_to_replace = [
        "salary_original",
        "currency",
        "pay_frequency",
        "compensation_effective_date",
        "salary_usd_annual",
        "benefits_enrolled",
        "benefits_enrollment_date",
    ]

    hris_records = hris_records.drop(
        columns=[
            column
            for column in enrichment_columns_to_replace
            if column in hris_records.columns
        ]
    )
    
    hris_records, _ = deduplicate_hris_identity_records(
        hris_records
    )
    
    enrichment_records = combined[
        combined["source_system"].isin(ENRICHMENT_SOURCE_SYSTEMS)
    ].copy()
    
    logger.info("HRIS identity records: %s", len(hris_records))
    logger.info("Enrichment records: %s", len(enrichment_records))
    
    hris_employee_ids = set(hris_records["employee_id"].dropna())
    
    ghost_records = enrichment_records[
        ~enrichment_records["employee_id"].isin(hris_employee_ids)
    ].copy()
    
    matched_records = enrichment_records[
        enrichment_records["employee_id"].isin(hris_employee_ids)
    ].copy()
    
    logger.info("Matched enrichment records: %s", len(matched_records))
    logger.info("Ghost enrichment records: %s", len(ghost_records))
    
    payroll_summary = summarize_payroll_records(matched_records)
    benefits_summary = summarize_benefits_records(matched_records)
    source_system_summary = summarize_source_systems(combined)
    
    for name, summary in {
        "payroll_summary": payroll_summary,
        "benefits_summary": benefits_summary,
        "source_system_summary": source_system_summary,
    }.items():
        duplicate_count = summary["employee_id"].duplicated().sum()

        if duplicate_count > 0:
            raise ValueError(
                f"{name} contains duplicate employee_id values: {duplicate_count}"
            )
    
    golden = hris_records.merge(
        payroll_summary,
        on="employee_id",
        how="left",
    ).merge(
        benefits_summary,
        on="employee_id",
        how="left",
    ).merge(
        source_system_summary,
        on="employee_id",
        how="left",
    )
    
    golden["source_systems"] =golden["source_systems"].fillna(golden["source_system"])
    golden["benefits_enrolled"] = golden["benefits_enrolled"].fillna(False)
    golden[golden["employee_id"].str.endswith("000000", na=False)]
    golden["dedup_method"] = 'exact_employee_id'
    
    logger.info("Build exact-ID golden dataset with %s records", len(golden))
    
    duplicate_golden_ids = golden["employee_id"].duplicated().sum()

    if duplicate_golden_ids > 0:
        raise ValueError(
            f"Golden dataset contains duplicate employee_id values: {duplicate_golden_ids}"
        )
    
    return golden, ghost_records


def summarize_payroll_records(enrichment_records: pd.DataFrame) -> pd.DataFrame:
    """
    Reduce payroll enrichment to one row per employee_id.

    If duplicate payroll records exist, keep the latest compensation effective
    date where available.
    """
    payroll = enrichment_records[
        enrichment_records["source_system"] == "payroll"
    ].copy()
    
    
    if payroll.empty:
        return pd.DataFrame(
            columns=[
                "employee_id",
                "salary_original",
                "currency",
                "pay_frequency",
                "compensation_effective_date",
                "salary_usd_annual",
            ]
        )
        
    payroll = payroll.sort_values(
        by=["employee_id", "compensation_effective_date"],
        ascending=[True, False],
        na_position="last"
    )
    
    payroll_latest = payroll.drop_duplicates(
        subset=["employee_id"],
        keep="first"
    )
    
    return payroll_latest[
        [
            "employee_id",
            "salary_original",
            "currency",
            "pay_frequency",
            "compensation_effective_date",
            "salary_usd_annual",
        ]
    ]
    
def summarize_benefits_records(enrichment_records: pd.DataFrame) -> pd.DataFrame:
    """
    Reduce benefits enrichment to one row per employee_id.

    Any benefits record means the employee is considered benefits enrolled.
    The earliest enrollment date is retained.
    """
    benefits = enrichment_records[
        enrichment_records["source_system"] == "benefits"
    ].copy()

    if benefits.empty:
        return pd.DataFrame(
            columns=[
                "employee_id",
                "benefits_enrolled",
                "benefits_enrollment_date",
            ]
        )

    benefits["benefits_enrolled"] = True

    benefits_summary = (
        benefits.groupby("employee_id", as_index=False)
        .agg(
            benefits_enrolled=("benefits_enrolled", "any"),
            benefits_enrollment_date=("benefits_enrollment_date", "min"),
        )
    )

    return benefits_summary


def summarize_source_systems(combined: pd.DataFrame) -> pd.DataFrame:
    """
    Build source-system provenance for each employee_id.
    """
    source_records = combined[
        ["employee_id", "source_system"]
    ].dropna().drop_duplicates()

    return (
        source_records.groupby("employee_id", as_index=False)
        .agg(source_systems=("source_system", build_source_systems))
    )

def find_duplicate_employee_ids(golden: pd.DataFrame) -> pd.DataFrame:
    """
    Find exact duplicate employee IDs in the golden dataset.

    Ideally this should return zero rows because exact-ID integration should
    produce one golden record per employee_id.
    """
    duplicate_mask = golden.duplicated(subset=["employee_id"], keep=False)

    duplicates = golden[duplicate_mask].copy()
    duplicates["duplicate_check"] = "employee_id"

    logger.info("Duplicate employee_id records found: %s", len(duplicates))

    return duplicates


def find_duplicate_emails(golden: pd.DataFrame) -> pd.DataFrame:
    """
    Find duplicate email addresses used by multiple golden employee records.

    Only cross-company duplicate emails are returned for review.
    """
    email_records = golden[golden["email"].notna()].copy()

    duplicate_groups = []

    for email, group in email_records.groupby("email"):
        if len(group) < 2:
            continue

        companies = set(group["company_origin"].dropna())

        if len(companies) < 2:
            continue

        duplicate_group = group.copy()
        duplicate_group["duplicate_check"] = "cross_company_email"
        duplicate_groups.append(duplicate_group)

    if not duplicate_groups:
        duplicates = pd.DataFrame(columns=list(golden.columns) + ["duplicate_check"])
    else:
        duplicates = pd.concat(duplicate_groups, ignore_index=True)

    logger.info("Cross-company duplicate email records found: %s", len(duplicates))

    return duplicates

def _build_same_name_match(left, right, hire_date_gap_days: int) -> dict:
    """Build a match record for same-name cross-company employees."""
    return {
        "match_type": "same_full_name_hire_date_window",
        "left_employee_id": left["employee_id"],
        "right_employee_id": right["employee_id"],
        "left_company_origin": left["company_origin"],
        "right_company_origin": right["company_origin"],
        "left_full_name": left["full_name"],
        "right_full_name": right["full_name"],
        "left_email": left["email"],
        "right_email": right["email"],
        "left_hire_date": left["hire_date"],
        "right_hire_date": right["hire_date"],
        "hire_date_gap_days": hire_date_gap_days,
        "review_required": True,
    }


def _matches_for_same_name_group(
    group: pd.DataFrame,
    max_hire_date_gap_days: int,
) -> list[dict]:
    """Return probable matches for a single full_name group."""
    companies = set(group["company_origin"].dropna())
    if len(companies) < 2:
        return []

    results: list[dict] = []
    records = group.sort_values(["company_origin", "employee_id"])
    for left_index in range(len(records)):
        left = records.iloc[left_index]
        for right_index in range(left_index + 1, len(records)):
            right = records.iloc[right_index]
            if left["company_origin"] == right["company_origin"]:
                continue

            hire_date_gap_days = abs((left["hire_date"] - right["hire_date"]).days)
            if hire_date_gap_days <= max_hire_date_gap_days:
                results.append(_build_same_name_match(left, right, hire_date_gap_days))

    return results


def find_same_name_cross_company_matches(
    golden: pd.DataFrame,
    max_hire_date_gap_days: int = 30,
) -> pd.DataFrame:
    """
    Find same-name cross-company employee candidates with hire dates close together.

    These are review candidates only. They are not automatically merged.
    """
    identity_records = golden[
        golden["full_name"].notna() & golden["hire_date"].notna()
    ].copy()

    probable_matches = []

    for _, group in identity_records.groupby("full_name"):
        probable_matches.extend(
            _matches_for_same_name_group(group, max_hire_date_gap_days)
        )

    matches = pd.DataFrame(probable_matches)

    logger.info(
        "Same-name cross-company probable matches found within %s days: %s",
        max_hire_date_gap_days,
        len(matches),
    )

    return matches

def find_fuzzy_name_hire_date_matches(
    golden: pd.DataFrame,
    similarity_threshold: int = 88,
    max_hire_date_gap_days: int = 30,
) -> pd.DataFrame:
    """
    Find probable cross-company employee matches using fuzzy name similarity
    and a hire-date window.

    These matches are review candidates only. They are not automatically merged.
    """
    identity_records = golden[
        golden["full_name"].notna() & golden["hire_date"].notna()
    ].copy()
    
    left_records = identity_records[
        identity_records["company_origin"] == "AcquiredCo"
    ].copy()
    
    right_records = identity_records[
        identity_records["company_origin"] == "GlobalTech"
    ].copy()
    
    probable_matches = []
    
    for _, left in left_records.iterrows():
        candidate_right_records = right_records[
            (
                right_records["hire_date"] >= left["hire_date"] - pd.Timedelta(days=max_hire_date_gap_days)
            )
            &
            (
                right_records["hire_date"] <= left["hire_date"] + pd.Timedelta(days=max_hire_date_gap_days)
            )
        ]
        
        for _, right in candidate_right_records.iterrows():
            name_similarity_score = fuzz.token_sort_ratio(
                str(left["full_name"]),
                str(right["full_name"])
            )
            
            if name_similarity_score < similarity_threshold:
                continue
            
            hire_date_gap_days = abs(
              (left["hire_date"] - right["hire_date"]).days
            )
            
            probable_matches.append(
                {
                    "match_type": "fuzzy_name_hire_date_window",
                    "left_employee_id": left["employee_id"],
                    "right_employee_id": right["employee_id"],
                    "left_company_origin": left["company_origin"],
                    "right_company_origin": right["company_origin"],
                    "left_full_name": left["full_name"],
                    "right_full_name": right["full_name"],
                    "name_similarity_score": name_similarity_score,
                    "left_email": left["email"],
                    "right_email": right["email"],
                    "left_hire_date": left["hire_date"],
                    "right_hire_date": right["hire_date"],
                    "hire_date_gap_days": hire_date_gap_days,
                    "review_required": True,
                }
            )
            
    matches = pd.DataFrame(probable_matches)
    
    logger.info(
        "Fuzzy name probable matches found | threshold=%s | hire_date_window_days=%s | matches=%s",
        similarity_threshold,
        max_hire_date_gap_days,
        len(matches),
    )
    
    return matches
