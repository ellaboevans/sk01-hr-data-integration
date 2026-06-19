import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pandas as pd

from hr_pipeline.config import RAW_FILES
from hr_pipeline.utils.logging import get_logger

logger = get_logger(__name__)

def _handle_missing_file(file_path: Path, source_name: str) -> pd.DataFrame:
    """
    Return an empty DataFrame and log an error when a source file is missing.
    """
    logger.error(f"Missing file for {source_name}: {file_path}")
    return pd.DataFrame()  # Return empty DataFrame to allow pipeline to continue

def _ensure_standard_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure that the DataFrame has all standard employee columns, adding any
    missing columns with pd.NA values.
    """
    from hr_pipeline.config import STANDARD_EMPLOYEE_COLUMNS
    
    df = df.copy()  # Avoid modifying the original DataFrame
    
    for col in STANDARD_EMPLOYEE_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA  # Add missing column with NA values
    
    return df[STANDARD_EMPLOYEE_COLUMNS]  # Reorder to standard schema

def _extract_nested_value(value:object, key:str) -> object:
    """
    Safely extract a value from a dictionary-like field.

    Parameters
    ----------
    value : object
        The value from the DataFrame cell. Expected to be a dict for nested
        JSON fields, but may be missing, null, or malformed.
    key : str
        Dictionary key to extract.

    Returns
    -------
    object
        Extracted value if available; otherwise pd.NA.
    """
    if isinstance(value, dict):
        return value.get(key, pd.NA)
    
    return pd.NA  

def ingest_globaltech_hris(file_path: Path)-> pd.DataFrame:
    """
    Ingest GlobalTech Workday HRIS CSV export.

    Parameters
    ----------
    file_path : Path
        Path to the UTF-8 encoded Workday CSV export.

    Returns
    -------
    pd.DataFrame
        Raw GlobalTech HRIS records with source metadata attached.
    """
    source_name = "globaltech_hris"
    
    if not file_path.exists():
        return _handle_missing_file(file_path, source_name)
    
    try:
        df = pd.read_csv(file_path, encoding="utf-8")
        df["source_system"] = source_name
        logger.info(f"Loaded {len(df)} from {source_name}")
        return df
    
    except Exception as exc:
        logger.exception(f"Failed to ingest {source_name} from {file_path}: {exc}")
        return pd.DataFrame()
    
def ingest_acquiredco_hris(file_path: Path, page_size: int = 500) -> pd.DataFrame:
    """
    Ingest AcquiredCo BambooHR JSON export with simulated pagination.

    Parameters
    ----------
    file_path : Path
        Path to the JSON file containing AcquiredCo employee records.
    page_size : int, default 500
        Number of records to process per simulated page.

    Returns
    -------
    pd.DataFrame
        Raw AcquiredCo HRIS records with source metadata attached.
    """
    source_name = "acquiredco_hris"
    if not file_path.exists():
        return _handle_missing_file(file_path, source_name)
    
    try:
        with file_path.open("r", encoding="utf-8") as file:
            payload: Any = json.load(file)
            
            if isinstance(payload, dict):
                records = payload.get("employees", [])
            elif isinstance(payload, list):
                records = payload
            else:
                logger.error(f"Unexpected JSON structure in {file_path}")
                return pd.DataFrame()
            pages = []
            for start in range(0, len(records), page_size):
                page = records[start:start + page_size]
                logger.info(
                    "Loaded simulated page for %s: records %s to %s",
                    source_name, 
                    start + 1,
                    min(start + page_size, len(records)),
                )
                pages.extend(page)
            
            df = pd.DataFrame(pages)
            df["source_system"] = source_name
            logger.info(f"Loaded total {len(df)} records from {source_name}")
            return df
        
    except json.JSONDecodeError as exc:
        logger.exception(f"Malformed JSON in {file_path}: {exc}")
        return pd.DataFrame()
    except Exception as exc:
        logger.exception(f"Failed to ingest {source_name} from {file_path}: {exc}")
        return pd.DataFrame()
    
def ingest_payroll(file_path: Path) -> pd.DataFrame:
    """
    Ingest combined ADP payroll Excel export.

    Parameters
    ----------
    file_path : Path
        Path to the payroll .xlsx export.

    Returns
    -------
    pd.DataFrame
        Raw payroll records with source metadata attached.
    """
    source_name = "payroll"
    
    if not file_path.exists():
        return _handle_missing_file(file_path, source_name)

    try:
        df = pd.read_excel(file_path)
        df["source_system"] = source_name
        logger.info(f"Loaded {len(df)} records from {source_name}")
        return df
    
    except Exception as exc:
        logger.exception(f"Failed to ingest {source_name} from {file_path}: {exc}")
        return pd.DataFrame()
    
def ingest_benefits(file_path: Path) -> pd.DataFrame:
    """
    Ingest MedShield benefits XML export.

    Parameters
    ----------
    file_path : Path
        Path to the MedShield XML export.

    Returns
    -------
    pd.DataFrame
        Raw benefits records with source metadata attached.
    """
    source_name = "benefits"
    
    if not file_path.exists():
        return _handle_missing_file(file_path, source_name)
    
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        records = []
        for enrollment_node in root.findall(".//enrollment"):
            record = {
                child.tag: child.text for child in enrollment_node
            }
            records.append(record)
        
        df = pd.DataFrame(records)
        df["source_system"] = source_name
        logger.info(f"Loaded {len(df)} records from {source_name}")
        return df
    
    except ET.ParseError as exc:
        logger.exception(f"Malformed XML in {file_path}: {exc}")
        return pd.DataFrame()
    except Exception as exc:
        logger.exception(f"Failed to ingest {source_name} from {file_path}: {exc}")
        return pd.DataFrame()
    
def ingest_all_sources() -> dict[str, pd.DataFrame]:
    """
    Ingest all configured raw source files.

    Returns
    -------
    dict[str, pd.DataFrame]
        Dictionary keyed by source name containing raw ingested DataFrames.
    """
    data_frames = {}
    
    for source_name, file_path in RAW_FILES.items():
        if source_name == "globaltech_hris":
            data_frames[source_name] = ingest_globaltech_hris(file_path)
        elif source_name == "acquiredco_hris":
            data_frames[source_name] = ingest_acquiredco_hris(file_path)
        elif source_name == "payroll":
            data_frames[source_name] = ingest_payroll(file_path)
        elif source_name == "benefits":
            data_frames[source_name] = ingest_benefits(file_path)
        else:
            logger.warning(f"No ingestion function defined for {source_name}")
            
    for source_name, df in data_frames.items():
        logger.info(f"Ingestion summary | {source_name} | rows={len(df)} | columns={len(df.columns)}")    
        
    return data_frames

def align_acquiredco_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Align AcquiredCo BambooHR records to the standard employee schema.

    AcquiredCo source data contains nested JSON-like structures in the
    name, contact, assignment, and employment columns. This function flattens
    those nested fields into the canonical employee schema.
    """
    aligned = pd.DataFrame()
    
    aligned["employee_id"] = df["employee_identifier"]
    aligned["source_employee_id"] = df["employee_identifier"]
    aligned["company_origin"] = "AcquiredCo"
    
    aligned["first_name"] = df["name"].apply(
        lambda value: _extract_nested_value(value, "first")
    )
    aligned["last_name"] = df["name"].apply(
        lambda value: _extract_nested_value(value, "last")
    )
    aligned["full_name"] = df["name"].apply(
        lambda value: _extract_nested_value(value, "full")
    )
    
    aligned["email"] = df["contact"].apply(
        lambda value: _extract_nested_value(value, "email")
    )
    
    aligned["department"] = df["assignment"].apply(
        lambda value: _extract_nested_value(value, "department")
    )
    aligned["job_title"] = df["assignment"].apply(
        lambda value: _extract_nested_value(value, "role")
    )
    aligned["country"] = df['assignment'].apply(
        lambda value: _extract_nested_value(value, "location")
    )
    aligned["hire_date"] = df["assignment"].apply(
        lambda value: _extract_nested_value(value, "hire_timestamp")
    )
    
    aligned["employment_type"] = df["employment"].apply(
        lambda value: _extract_nested_value(value, "type")
    )
    
    aligned["manager_id"] = df["manager_employee_id"]
    aligned["source_system"] = "acquiredco_hris"
    
    logger.info(f"Aligned AcquiredCo HRIS to standard schema with {len(aligned)} records")
    return _ensure_standard_columns(aligned)

def align_benefits_schema(df: pd.DataFrame)-> pd.DataFrame:
    """
    Align benefits enrollment records to the standard employee schema.

    Benefits is treated as an enrichment source. A record here indicates
    the employee has at least one benefits enrollment record.
    """
    aligned = pd.DataFrame()

    aligned["employee_id"] = df["employee_id"]
    aligned["source_employee_id"] = df["employee_id"]
    aligned["company_origin"] = "GlobalTech"
    aligned["benefits_enrolled"] = True
    aligned["benefits_enrollment_date"] = df["enrollment_date"]
    aligned["source_system"] = "benefits"

    logger.info("Aligned %s benefits records to standard schema", len(aligned))
    return _ensure_standard_columns(aligned)

def align_globaltech_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Align GlobalTech Workday HRIS records to the standard employee schema.

    GlobalTech HRIS is treated as a primary system of record for employee
    identity, organization, employment type, manager, country, and hire date.
    """
    aligned = pd.DataFrame()

    aligned["employee_id"] = df["employee_id"]
    aligned["source_employee_id"] = df["employee_id"]
    aligned["company_origin"] = "GlobalTech"

    aligned["first_name"] = df["first_name"]
    aligned["last_name"] = df["last_name"]
    aligned["full_name"] = (
        df["first_name"].astype(str).str.strip()
        + " "
        + df["last_name"].astype(str).str.strip()
    )

    aligned["email"] = df["email"]
    aligned["department"] = df["department"]
    aligned["job_title"] = df["job_title"]
    aligned["hire_date"] = df["hire_date"]
    aligned["country"] = df["country"]
    aligned["employment_type"] = df["employment_type"]
    aligned["manager_id"] = df["manager_id"]
    aligned["source_system"] = "globaltech_hris"

    logger.info("Aligned %s GlobalTech HRIS records to standard schema", len(aligned))
    return _ensure_standard_columns(aligned)

def align_payroll_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Align ADP payroll records to the standard employee schema.

    Payroll is treated as an enrichment source. It contributes compensation
    information but is not treated as the primary source for employee identity.
    """
    aligned = pd.DataFrame()

    aligned["employee_id"] = df["employee_id"]
    aligned["source_employee_id"] = df["employee_id"]
    aligned["company_origin"] = df["source"]

    aligned["salary_original"] = df["base_salary"]
    aligned["currency"] = df["currency"]
    aligned["pay_frequency"] = df["pay_frequency"]
    aligned["compensation_effective_date"] = df["effective_date"]

    aligned["source_system"] = "payroll"

    logger.info("Aligned %s payroll records to standard schema", len(aligned))
    return _ensure_standard_columns(aligned)

def align_all_sources(raw_dataframes: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """
    Align all raw source DataFrames to the standard employee schema.

    Parameters
    ----------
    raw_dataframes : dict[str, pd.DataFrame]
        Raw ingested DataFrames keyed by source system name.

    Returns
    -------
    dict[str, pd.DataFrame]
        Standardized DataFrames keyed by source system name.
    """
    aligned_dataframes = {}
    
    for source_name, df in raw_dataframes.items():
        if source_name == "globaltech_hris":
            aligned_dataframes[source_name] = align_globaltech_schema(df)
        elif source_name == "acquiredco_hris":
            aligned_dataframes[source_name] = align_acquiredco_schema(df)
        elif source_name == "payroll":
            aligned_dataframes[source_name] = align_payroll_schema(df)
        elif source_name == "benefits":
            aligned_dataframes[source_name] = align_benefits_schema(df)
        else:
            logger.warning(f"No alignment function defined for {source_name}")
            
    for source_name, df in aligned_dataframes.items():
        logger.info(
            "Schema alignment summary | %s | rows=%s | columns=%s",
            source_name,
            len(df),
            len(df.columns),
        )

    return aligned_dataframes
