
from hr_pipeline.config import REFERENCE_FILES
from hr_pipeline.clean import clean_standardized_dataframe, load_department_mapping
from hr_pipeline.ingest import ingest_all_sources, align_all_sources

def main():
    raw_dataframes = ingest_all_sources()
    aligned_dataframes = align_all_sources(raw_dataframes)
    
    department_mapping = load_department_mapping(REFERENCE_FILES["department_mapping"])
    
    cleaned_dataframes = {
        source_name: clean_standardized_dataframe(df, department_mapping)
        for source_name, df in aligned_dataframes.items()
    }
    
    for source_names, df in cleaned_dataframes.items():
        print(f"\n=={source_names}==")
        print(f"Rows: {len(df)}")
        print(f"Columns: {list(df.columns)}")
        print(
            df[
                [
                    "employee_id",
                    "source_system",
                    "department",
                    "department_standardized",
                    "salary_original",
                    "currency",
                    "pay_frequency",
                    "salary_usd_annual",
                ]
            ].head()
        )
              
if __name__ == "__main__":
    main()