from pprint import pprint

from hr_pipeline.ingest import ingest_all_sources, align_all_sources

def main():
    raw_dataframes = ingest_all_sources()
    aligned_dataframes = align_all_sources(raw_dataframes)
    
    for source_names, df in aligned_dataframes.items():
        print(f"\n=={source_names}==")
        print(f"Rows: {len(df)}")
        print(f"Columns: {list(df.columns)}")
        print(df.head())              
              
if __name__ == "__main__":
    main()