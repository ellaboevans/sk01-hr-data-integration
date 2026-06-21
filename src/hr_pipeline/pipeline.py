import shutil

import pandas as pd

from hr_pipeline.config import REFERENCE_FILES, REPORTS_DATA_DIR, PROCESSED_DATA_DIR
from hr_pipeline.clean import clean_standardized_dataframe, load_department_mapping
from hr_pipeline.ingest import ingest_all_sources, align_all_sources
from hr_pipeline.dedup import (
    combine_cleaned_sources,
    build_exact_id_golden_dataset,
    find_duplicate_employee_ids,
    find_duplicate_emails,
    find_same_name_cross_company_matches,
    find_fuzzy_name_hire_date_matches,
)
from hr_pipeline.validate import DataQualityValidator
from hr_pipeline.visualize import generate_all_charts


def prepare_for_parquet_export(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert mixed object columns into stable Parquet-friendly dtypes.
    """
    export_df = df.copy()

    string_columns = [
        "employee_id",
        "source_employee_id",
        "company_origin",
        "first_name",
        "last_name",
        "full_name",
        "email",
        "department",
        "department_standardized",
        "job_title",
        "manager_id",
        "employment_type",
        "country",
        "jurisdiction",
        "currency",
        "pay_frequency",
        "source_system",
        "source_systems",
        "dedup_method",
    ]

    datetime_columns = [
        "hire_date",
        "compensation_effective_date",
        "benefits_enrollment_date",
    ]

    numeric_columns = [
        "salary_original",
        "salary_usd_annual",
    ]

    boolean_columns = [
        "benefits_enrolled",
    ]

    for column in string_columns:
        if column in export_df.columns:
            export_df[column] = export_df[column].astype("string")

    for column in datetime_columns:
        if column in export_df.columns:
            export_df[column] = pd.to_datetime(export_df[column], errors="coerce")

    for column in numeric_columns:
        if column in export_df.columns:
            export_df[column] = pd.to_numeric(export_df[column], errors="coerce")

    for column in boolean_columns:
        if column in export_df.columns:
            export_df[column] = export_df[column].fillna(False).astype(bool)

    return export_df


def build_probable_matches_export(probable_matches: pd.DataFrame) -> pd.DataFrame:
    """
    Convert internal probable match records into the HR-facing required schema.

    Required fields:
    - record_1_id
    - record_2_id
    - similarity_score
    - hire_date_diff_days
    - recommended_action
    """
    export_columns = [
        "record_1_id",
        "record_2_id",
        "similarity_score",
        "hire_date_diff_days",
        "recommended_action",
        "match_type",
        "left_company_origin",
        "right_company_origin",
        "left_full_name",
        "right_full_name",
        "left_email",
        "right_email",
        "left_hire_date",
        "right_hire_date",
    ]

    probable_matches_export = probable_matches.copy()

    if probable_matches_export.empty:
        return pd.DataFrame(columns=export_columns)

    probable_matches_export["similarity_score"] = probable_matches_export[
        "name_similarity_score"
    ].fillna(100.0)

    probable_matches_export["recommended_action"] = "HR_REVIEW"

    probable_matches_export = probable_matches_export.rename(
        columns={
            "left_employee_id": "record_1_id",
            "right_employee_id": "record_2_id",
            "hire_date_gap_days": "hire_date_diff_days",
        }
    )

    return probable_matches_export[export_columns]


def main() -> None:
    raw_dataframes = ingest_all_sources()
    aligned_dataframes = align_all_sources(raw_dataframes)

    department_mapping = load_department_mapping(
        REFERENCE_FILES["department_mapping"]
    )

    cleaned_dataframes = {
        source_name: clean_standardized_dataframe(df, department_mapping)
        for source_name, df in aligned_dataframes.items()
    }

    combined = combine_cleaned_sources(cleaned_dataframes)

    golden, ghost_records, duplicate_hris_records = build_exact_id_golden_dataset(
        combined
    )

    duplicate_ids = find_duplicate_employee_ids(golden)
    duplicate_emails = find_duplicate_emails(golden)
    same_name_matches = find_same_name_cross_company_matches(golden)

    fuzzy_matches = find_fuzzy_name_hire_date_matches(
        golden,
        similarity_threshold=88,
        max_hire_date_gap_days=30,
    )

    print("\n==golden_dataset_exact_id==")
    print(f"Rows: {len(golden)}")
    print(
        golden[
            [
                "employee_id",
                "company_origin",
                "full_name",
                "email",
                "department_standardized",
                "salary_usd_annual",
                "benefits_enrolled",
                "source_systems",
                "dedup_method",
            ]
        ].head()
    )

    print("\n==ghost_records==")
    print(f"Rows: {len(ghost_records)}")
    print(
        ghost_records[
            [
                "employee_id",
                "company_origin",
                "source_system",
                "salary_usd_annual",
                "benefits_enrolled",
            ]
        ].head()
    )

    print("\n==duplicate_employee_ids==")
    print(f"Rows: {len(duplicate_ids)}")
    print(
        duplicate_ids[
            [
                "employee_id",
                "company_origin",
                "full_name",
                "email",
                "source_systems",
                "duplicate_check",
            ]
        ].head()
    )

    print("\n==duplicate_emails==")
    print(f"Rows: {len(duplicate_emails)}")
    print(
        duplicate_emails[
            [
                "employee_id",
                "company_origin",
                "full_name",
                "email",
                "source_systems",
                "duplicate_check",
            ]
        ].head()
    )

    print("\n==same_name_cross_company_matches==")
    print(f"Rows: {len(same_name_matches)}")

    if not same_name_matches.empty:
        print(same_name_matches.head())
    else:
        print("No same-name cross-company matches found.")

    print("\n==fuzzy_name_hire_date_matches==")
    print(f"Rows: {len(fuzzy_matches)}")

    if not fuzzy_matches.empty:
        print(
            fuzzy_matches[
                [
                    "match_type",
                    "left_employee_id",
                    "right_employee_id",
                    "left_full_name",
                    "right_full_name",
                    "name_similarity_score",
                    "left_hire_date",
                    "right_hire_date",
                    "hire_date_gap_days",
                    "review_required",
                ]
            ].head()
        )
    else:
        print("No fuzzy name + hire-date matches found.")

    probable_matches = pd.concat(
        [same_name_matches, fuzzy_matches],
        ignore_index=True,
        sort=False,
    )

    if probable_matches.empty:
        probable_matches = pd.DataFrame(
            columns=[
                "match_type",
                "left_employee_id",
                "right_employee_id",
                "left_company_origin",
                "right_company_origin",
                "left_full_name",
                "right_full_name",
                "left_email",
                "right_email",
                "left_hire_date",
                "right_hire_date",
                "hire_date_gap_days",
                "review_required",
                "name_similarity_score",
            ]
        )
    else:
        match_type_priority = {
            "same_full_name_hire_date_window": 1,
            "fuzzy_name_hire_date_window": 2,
        }

        probable_matches["match_type_priority"] = probable_matches["match_type"].map(
            match_type_priority
        )

        probable_matches = (
            probable_matches.sort_values(
                by=[
                    "left_employee_id",
                    "right_employee_id",
                    "match_type_priority",
                    "hire_date_gap_days",
                ],
                ascending=[True, True, True, True],
            )
            .drop_duplicates(
                subset=[
                    "left_employee_id",
                    "right_employee_id",
                ],
                keep="first",
            )
            .drop(columns=["match_type_priority"])
            .reset_index(drop=True)
        )

    print("\n==probable_matches_review==")
    print(f"Rows: {len(probable_matches)}")

    if not probable_matches.empty:
        print(probable_matches.head())
    else:
        print("No probable matches requiring review found.")

    validator = DataQualityValidator(max_failed_checks=2)
    validation_report = validator.run(golden)

    print("\n==data_quality_validation_report==")
    print(validation_report)

    validator.assert_quality_gate(validation_report)

    salary_failures = validator.get_failed_records(
        golden,
        check_name="salary_usd_annual_range",
    )

    print("\n==salary_usd_annual_range_failures==")
    print(f"Rows: {len(salary_failures)}")

    if not salary_failures.empty:
        print(
            salary_failures[
                [
                    "employee_id",
                    "company_origin",
                    "full_name",
                    "salary_original",
                    "currency",
                    "pay_frequency",
                    "salary_usd_annual",
                    "failed_check",
                ]
            ].head()
        )
    else:
        print("No salary_usd_annual_range failures found.")

    validator.export_report(
        validation_report,
        output_dir=REPORTS_DATA_DIR,
    )

    validator.export_failed_records(
        salary_failures,
        output_dir=REPORTS_DATA_DIR,
        file_name="salary_usd_annual_range_failures.csv",
    )

    golden_output_path = PROCESSED_DATA_DIR / "golden_employee_dataset"
    golden_for_export = prepare_for_parquet_export(golden)

    if golden_output_path.exists():
        shutil.rmtree(golden_output_path)

    golden_for_export.to_parquet(
        golden_output_path,
        partition_cols=["company_origin"],
        index=False,
    )

    ghost_records.to_csv(
        REPORTS_DATA_DIR / "ghost_employee_records.csv",
        index=False,
    )

    probable_matches_export = build_probable_matches_export(probable_matches)

    probable_matches_export.to_csv(
        REPORTS_DATA_DIR / "probable_match_review.csv",
        index=False,
    )

    duplicate_ids.to_csv(
        REPORTS_DATA_DIR / "duplicate_employee_id_records.csv",
        index=False,
    )

    duplicate_emails.to_csv(
        REPORTS_DATA_DIR / "duplicate_email_records.csv",
        index=False,
    )

    duplicate_hris_records.to_csv(
        REPORTS_DATA_DIR / "duplicate_hris_records.csv",
        index=False,
    )

    print("\n==exported_outputs==")
    print(f"Golden dataset: {golden_output_path}")
    print(f"Ghost records: {REPORTS_DATA_DIR / 'ghost_employee_records.csv'}")
    print(f"Probable matches: {REPORTS_DATA_DIR / 'probable_match_review.csv'}")
    print(f"Duplicate HRIS records: {REPORTS_DATA_DIR / 'duplicate_hris_records.csv'}")
    print(f"Duplicate employee IDs: {REPORTS_DATA_DIR / 'duplicate_employee_id_records.csv'}")
    print(f"Duplicate emails: {REPORTS_DATA_DIR / 'duplicate_email_records.csv'}")
    print(f"Validation report CSV: {REPORTS_DATA_DIR / 'data_quality_validation_report.csv'}")
    print(f"Validation report HTML: {REPORTS_DATA_DIR / 'data_quality_validation_report.html'}")
    print(
        "Salary validation failures: "
        f"{REPORTS_DATA_DIR / 'salary_usd_annual_range_failures.csv'}"
    )

    print("\n==duplicate_hris_records==")
    print(f"Rows: {len(duplicate_hris_records)}")

    if not duplicate_hris_records.empty:
        print(
            duplicate_hris_records[
                [
                    "employee_id",
                    "source_employee_id",
                    "company_origin",
                    "source_system",
                    "full_name",
                    "email",
                    "hire_date",
                    "duplicate_check",
                    "kept_in_golden",
                ]
            ].head()
        )

        print("\n==duplicate_hris_kept_in_golden_counts==")
        print(duplicate_hris_records["kept_in_golden"].value_counts(dropna=False))
    else:
        print("No duplicate HRIS records found.")

    generate_all_charts(
        golden=golden,
        validation_report=validation_report,
        output_dir=REPORTS_DATA_DIR / "figures",
    )


if __name__ == "__main__":
    main()