from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
REFERENCE_DATA_DIR = DATA_DIR / "reference"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"

LOG_DIR = PROJECT_ROOT / "logs"

RAW_FILES = {
    "globaltech_hris": RAW_DATA_DIR / "globaltech_hris.csv",
    "acquiredco_hris": RAW_DATA_DIR / "acquiredco_api.json",
    "payroll": RAW_DATA_DIR / "payroll_data.xlsx",
    "benefits": RAW_DATA_DIR / "benefits_enrollment.xml"
}

SOURCE_PRIORITY = {
    "globaltech_hris": 1,
    "acquiredco_hris": 1,
    "payroll": 2,
    "benefits": 3
}

COMPANY_PREFIXES ={
    "GlobalTech": "GT",
    "AcquiredCo": "AC"
}

STANDARD_EMPLOYEE_COLUMNS = [
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
    "hire_date",
    "salary_original",
    "currency",
    "pay_frequency",
    "compensation_effective_date",
    "salary_usd_annual",
    "benefits_enrolled",
    "benefits_enrollment_date",
    "source_system",
]