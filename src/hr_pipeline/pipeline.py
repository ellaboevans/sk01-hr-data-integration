import pandas as pd

from hr_pipeline.config import REFERENCE_FILES
from hr_pipeline.clean import clean_standardized_dataframe, load_department_mapping
from hr_pipeline.ingest import ingest_all_sources, align_all_sources
from hr_pipeline.dedup import (
    combine_cleaned_sources,
    build_exact_id_golden_dataset,
    find_duplicate_employee_ids,
    find_duplicate_emails,
    find_same_name_cross_company_matches,
    find_fuzzy_name_hire_date_matches
)

def main():
    raw_dataframes = ingest_all_sources()
    aligned_dataframes = align_all_sources(raw_dataframes)
    
    department_mapping = load_department_mapping(REFERENCE_FILES["department_mapping"])
    
    cleaned_dataframes = {
        source_name: clean_standardized_dataframe(df, department_mapping)
        for source_name, df in aligned_dataframes.items()
    }
    
    combined = combine_cleaned_sources(cleaned_dataframes)
    golden, ghost_records = build_exact_id_golden_dataset(combined)
    duplicate_ids = find_duplicate_employee_ids(golden)
    duplicate_emails = find_duplicate_emails(golden)
    same_name_matches = find_same_name_cross_company_matches(golden)
    
    fuzzy_matches = find_fuzzy_name_hire_date_matches(golden, similarity_threshold=88, max_hire_date_gap_days=30,)
    
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
    
              
if __name__ == "__main__":
    main()