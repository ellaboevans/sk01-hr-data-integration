import re
import unicodedata

import pandas as pd

from hr_pipeline.utils.logging import get_logger
from hr_pipeline.config import EXCHANGE_RATES_TO_USD
from datetime import date
from pathlib import Path

logger = get_logger(__name__)

def normalize_name(value: object)-> object:
    """
    Normalize employee names using Unicode normalization and title casing.

    Parameters
    ----------
    value : object
        Raw name value.

    Returns
    -------
    object
        Normalized name string, or pd.NA if missing.
    """
    if pd.isna(value):
        return pd.NA
    
    normalized = unicodedata.normalize('NFKC', str(value)).strip()
    
    if not normalized:
        return pd.NA
    
    return normalized.title()

def normalize_employee_id(value: object, company_origin: object) -> object:
    """
    Convert source employee IDs into namespaced canonical IDs.

    GlobalTech IDs become GT-000001.
    AcquiredCo IDs become AC-000001.

    Handles values such as:
    - 123
    - 123.0
    - "123"
    - "ACQ_00123"
    """
    if pd.isna(value) or pd.isna(company_origin):
        return pd.NA

    company = str(company_origin).strip()

    if company == "GlobalTech":
        prefix = "GT"
    elif company == "AcquiredCo":
        prefix = "AC"
    else:
        logger.warning(
            "Unknown company origin for employee ID namespacing: %s",
            company_origin,
        )
        return pd.NA

    raw_id = str(value).strip()

    try:
        # Handles numeric IDs loaded as int, float, or numeric-looking strings.
        if isinstance(value, (int, float)) or raw_id.replace(".", "", 1).isdigit():
            numeric_id = int(float(raw_id))
        else:
            # Handles IDs like ACQ_00001 by extracting the first meaningful number.
            match = re.search(r"\d+", raw_id)
            if match is None:
                logger.warning(
                    "Could not parse employee ID: value=%s company_origin=%s",
                    value,
                    company_origin,
                )
                return pd.NA

            numeric_id = int(match.group())

    except ValueError:
        logger.warning(
            "Could not parse employee ID: value=%s company_origin=%s",
            value,
            company_origin,
        )
        return pd.NA

    return f"{prefix}-{numeric_id:06d}"


def normalize_manager_id(value: object, company_origin: object) -> object:
    """
    Normalize manager IDs to match the employee ID format.

    Missing manager IDs remain null.
    """
    if pd.isna(value):
        return pd.NA
    
    return normalize_employee_id(value, company_origin)

def normalize_employment_type(value: object) -> object:
    """
    Normalize employment type values into the allowed taxonomy.

    Allowed values:
    - Full-Time
    - Part-Time
    - Contractor
    """
    if pd.isna(value):
        return pd.NA
    
    normalized = str(value).strip().lower()
    
    mapping = {
        "full-time": "Full-Time",
        "full time": "Full-Time",
        "ft": "Full-Time",
        "part-time": "Part-Time",
        "part time": "Part-Time",
        "pt": "Part-Time",
        "contractor": "Contractor",
        "contract": "Contractor",
        "ct": "Contractor",
    }
    
    result = mapping.get(normalized)
    
    if result is None:
        logger.warning("Unknown employment type '%s'", value)
        return pd.NA
    
    return result

def standardize_date(value: object) -> object:
    """
    Convert source date values into pandas Timestamp values.

    Invalid dates, missing dates, dates before 1970-01-01, and dates after
    today are returned as pd.NaT.
    """
    if pd.isna(value):
        return pd.NaT
    
    parsed = pd.to_datetime(value, errors='coerce', utc=True)
    
    if pd.isna(parsed):
        logger.warning("Could not parse date: %s", value)
        return pd.NaT
    
    parsed = parsed.tz_convert(None)  # Convert to naive datetime in local timezone
    
    min_date = pd.Timestamp("1970-01-01")
    max_date = pd.Timestamp(date.today())
    
    if parsed < min_date or parsed > max_date:
        logger.warning("Date out of range: %s", value)
        return pd.NaT
    
    return parsed

def parse_salary(value:object) -> object:
    """
    Convert salary values such as '$85,000', '85000', or 85000 into float.

    Returns pd.NA for missing or unparsable values.
    """
    if pd.isna(value):
        return pd.NA
    
    cleaned = (
        str(value)
        .strip()
        .replace("$", "")
        .replace(",", "")
        .replace("€", "")
        .replace("£", "")
    )
    
    if not cleaned:
        return pd.NA
    
    try:
        return float(cleaned)
    except ValueError:
        logger.warning("Could not parse salary: %s", value)
        return pd.NA
    
def normalize_salary_to_usd_annual(
    salary_value: object,
    currency: object,
    pay_frequency: object
) -> object:
    """
    Normalize salary to annual USD.

    Steps:
    1. Parse raw salary into a numeric value.
    2. Convert currency to USD using fixed exchange rates.
    3. Annualize based on pay frequency.
    """
    amount = parse_salary(salary_value)
    
    if pd.isna(amount) or pd.isna(currency) or pd.isna(pay_frequency):
        return pd.NA
    
    currency_code = str(currency).strip().upper()
    frequency =  str(pay_frequency).strip().lower()
    
    exchange_rate = EXCHANGE_RATES_TO_USD.get(currency_code)
    
    if exchange_rate is None:
        logger.warning("Unknown currency for salary normalization: %s", currency)
        return pd.NA
    
    frequency_multipliers = {
        "annual": 1,
        "monthly": 12,
        "bi-weekly": 26,
        "biweekly": 26,
        "bi weekly": 26,
    }.get(frequency)
    
    if frequency_multipliers is None:
        logger.warning("Unknown pay frequency for salary normalization: %s", pay_frequency)
        return pd.NA
    
    salary_usd_annual = round(float(amount) * exchange_rate * frequency_multipliers, 2)
    return salary_usd_annual

def clean_standardized_dataframe(df: pd.DataFrame, department_mapping: pd.DataFrame | None = None) -> pd.Dataframe:
    """
    Apply core cleaning rules to a standardized employee DataFrame.

    This function assumes the input DataFrame already conforms to the canonical
    schema produced by ingest.align_all_sources().
    """
    
    cleaned = df.copy()
    
    cleaned["first_name"] = cleaned["first_name"].apply(normalize_name)
    cleaned["last_name"] = cleaned["last_name"].apply(normalize_name)
    cleaned["full_name"] = (
        cleaned['first_name'].fillna("").astype(str).str.strip()
        + " "
        + cleaned['last_name'].fillna("").astype(str).str.strip()
    )
    
    cleaned['full_name'] = cleaned["full_name"].replace("", pd.NA)
    
    cleaned["email"] = cleaned["email"].astype("string").str.strip().str.lower()
    
    cleaned["employee_id"] = cleaned.apply(
        lambda row: normalize_employee_id(row["employee_id"], row["company_origin"]),
        axis=1
    )
    
    cleaned["manager_id"] = cleaned.apply(
        lambda row: normalize_manager_id(row["manager_id"], row["company_origin"]),
        axis=1
    )
    
    cleaned["employment_type"] = cleaned["employment_type"].apply(normalize_employment_type)
    
    cleaned["hire_date"] = cleaned["hire_date"].apply(standardize_date)
    
    cleaned["compensation_effective_date"] = cleaned["compensation_effective_date"].apply(standardize_date)
    
    cleaned["benefits_enrollment_date"] = cleaned["benefits_enrollment_date"].apply(standardize_date)
    
    cleaned["salary_usd_annual"] = cleaned.apply(
        lambda row: normalize_salary_to_usd_annual(
            row["salary_original"], row["currency"], row["pay_frequency"]
        ),
        axis=1
    )
    
    if department_mapping is not None:
        cleaned = map_departments(cleaned, department_mapping)
    
    logger.info("Applied core cleaning rules to %s records", len(cleaned))
    
    return cleaned

def load_department_mapping(file_path: Path) -> pd.DataFrame:
    """
    Load department taxonomy mapping reference data.

    Expected columns:
    - source_system
    - source_department
    - standard_department
    """
    try:
        mapping_df = pd.read_csv(file_path)

        required_columns = {
            "source_system",
            "source_department",
            "standard_department",
        }

        missing_columns = required_columns - set(mapping_df.columns)

        if missing_columns:
            raise ValueError(
                f"Department mapping file is missing columns: {missing_columns}"
            )

        logger.info("Loaded %s department mapping rows", len(mapping_df))
        return mapping_df

    except FileNotFoundError:
        logger.exception("Department mapping file not found: %s", file_path)
        return pd.DataFrame(
            columns=["source_system", "source_department", "standard_department"]
        )
        
def map_departments(
    df: pd.DataFrame,
    department_mapping: pd.DataFrame,
) -> pd.DataFrame:
    """
    Map source department values to the standard department taxonomy.

    Unmapped departments are left as pd.NA and logged once per unique
    source_system + department pair for manual review.
    """
    cleaned = df.copy()

    if department_mapping.empty:
        logger.warning(
            "Department mapping is empty; department_standardized will remain null"
        )
        cleaned["department_standardized"] = pd.NA
        return cleaned

    mapping_lookup = {
        (
            str(row["source_system"]).strip().lower(),
            str(row["source_department"]).strip().lower(),
        ): row["standard_department"]
        for _, row in department_mapping.iterrows()
    }

    unmapped_departments: set[tuple[str, str]] = set()

    def map_single_department(row: pd.Series) -> object:
        if pd.isna(row["department"]):
            return pd.NA

        source_system = str(row["source_system"]).strip()
        department = str(row["department"]).strip()

        lookup_key = (
            source_system.lower(),
            department.lower(),
        )

        mapped_value = mapping_lookup.get(lookup_key)

        if mapped_value is None:
            unmapped_departments.add((source_system, department))
            return pd.NA

        return mapped_value

    cleaned["department_standardized"] = cleaned.apply(map_single_department, axis=1)

    for source_system, department in sorted(unmapped_departments):
        logger.warning(
            "Unmapped department: source_system=%s department=%s",
            source_system,
            department,
        )

    logger.info(
        "Department mapping completed | rows=%s | unmapped_unique_departments=%s",
        len(cleaned),
        len(unmapped_departments),
    )

    return cleaned