import re
from dataclasses import dataclass
from typing import Callable
from pathlib import Path

import pandas as pd

from hr_pipeline.utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class ValidationCheck:
    check: str
    description: str
    validator: Callable[[pd.DataFrame], pd.Series]

class DataQualityValidator:
    """
    Data quality validator for the golden employee dataset.

    Each validation check returns a boolean Series where True means the row
    passed and False means the row failed.
    """
    def __init__(self, max_failed_checks: int = 2) -> None:
        self.max_failed_checks = max_failed_checks
        self.checks = self._build_checks()
        
    def _build_checks(self) -> list[ValidationCheck]:
        return [
            ValidationCheck(
                check="employee_id_not_null",
                description="employee_id must not be null",
                validator=lambda df: df["employee_id"].notnull().notna()
            ),
            ValidationCheck(
                check="employee_id_unique",
                description="employee_id should be unique across the dataset",
                validator=lambda df: ~df["employee_id"].duplicated(keep=False)
            ),
            ValidationCheck(
                check="employee_id_format",
                description="employee_id must match GT-000001 or AC-000001 format",
                validator=lambda df: df["employee_id"]
                .fillna("")
                .astype(str)
                .str.match(r"^(GT|AC)-\d{6}$")
            ),
            ValidationCheck(
                check="full_name_not_null",
                description="full_name must not be null",
                validator=lambda df: df["full_name"].notnull().notna()
            ),
            ValidationCheck(
                check="email_not_null",
                description="email must not be null",
                validator=lambda df: df["email"].notnull().notna()
            ),
            ValidationCheck(
                check="email_format",
                description="email must be in a valid format",
                validator=lambda df: df["email"]
                .fillna("")
                .astype(str)
                .str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
            ),
            ValidationCheck(
                check="company_origin_allowed",
                description="company_origin must be GlobalTech or AcquiredCo",
                validator=lambda df: df["company_origin"].isin(
                    ["GlobalTech", "AcquiredCo"]
                ),
            ),
            ValidationCheck(
                check="employment_type_allowed",
                description="employment_type must be Full-Time, Part-Time, or Contractor",
                validator=lambda df: df["employment_type"].isna() 
                | df["employment_type"].isin(
                    ["Full-Time", "Part-Time", "Contractor"]
                )
            ),
            ValidationCheck(
                check="department_standardized_not_null",
                description="department_standardized must not be null",
                validator=lambda df: df["department_standardized"].notnull().notna()
            ),
            ValidationCheck(
                check="hire_date_not_null",
                description="hire_date must not be null",
                validator=lambda df: df["hire_date"].notnull().notna()
            ),
            ValidationCheck(
                check="hire_date_plausible_range",
                description="hire_date must be between 1990-01-01 and today",
                validator=self._validate_hire_date_range
            ),
            ValidationCheck(
                check="salary_usd_annual_range",
                description="salary_usd_annual must be between 20,000 and 2,000,000 when present",
                validator=self._validate_salary_range
            ),
            ValidationCheck(
                check="manager_id_referential_integrity",
                description="manager_id must refer to an employee_id in the golden dataset when present",
                validator=self._validate_manager_referential_integrity,
            ),
            ValidationCheck(
                check="benefits_enrolled_boolean",
                description="benefits_enrolled must be boolean",
                validator=lambda df: df["benefits_enrolled"].isin([True, False]),
            ),
        ]
    
    def  run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Run all validation checks and return a validation report DataFrame.
        """
        results = []
        
        for check in self.checks:
            passed_mask = check.validator(df).fillna(False)
            
            total = len(df)
            passed = int(passed_mask.sum())
            failed = int(total - passed)
            pass_rate = round(passed / total * 100, 2) if total else 0.0
            status = "PASS" if failed == 0 else "FAIL"
            
            results.append(
                {
                "check": check.check,
                "description": check.description,
                "total": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": pass_rate,
                "status": status,
                }
            )
            
        report = pd.DataFrame(results)
        
        failed_checks = int((report["status"] == "FAIL").sum())
        
        logger.info(
            "Validation completed | checks=%s | failed_checks=%s",
            len(report),
            failed_checks
        )
        
        if failed_checks > self.max_failed_checks:
            logger.error(
                "Validation gate failed | failed_checks=%s exceeds max_failed_checks=%s",
                failed_checks,
                self.max_failed_checks
            )
            
        return report
    
    def assert_quality_gate(self, report: pd.DataFrame)-> None:
        """
        Raise an error if the number of failed checks exceeds the configured gate.
        """
        failed_checks = int((report["status"] == "FAIL").sum())
        
        if failed_checks > self.max_failed_checks:
            failed_check_names = report.loc[
                report["status"] == "FAIL",
                "check"
            ].tolist()
            
            raise ValueError(
                "Data quality gate failed: "
                f"{failed_checks} checks failed; "
                f"maximum allowed is {self.max_failed_checks}. "
                f"Failed checks: {failed_check_names}"
            )
            
    def get_failed_records(
        self,
        df: pd.DataFrame,
        check_name: str
    ) -> pd.DataFrame:
        """
        Return the records that failed a specific validation check.
        """
        matching_checks = [
            check for check in self.checks if check.check == check_name
        ]
        
        if not matching_checks:
            raise ValueError(f"Unknown validation check: {check_name}")
        
        check = matching_checks[0]
        passed_mask = check.validator(df).fillna(False)
        
        failed_records = df.loc[~passed_mask].copy()
        failed_records["failed_check"] = check_name
        failed_records["failed_check_description"] = check.description
        
        return failed_records
    
    @staticmethod
    def _validate_hire_date_range(df: pd.DataFrame) -> pd.Series:
        hire_dates = pd.to_datetime(df['hire_date'], errors="coerce")
        
        min_date = pd.to_datetime("1990-01-01")
        max_date = pd.to_datetime("today").normalize()
        
        return hire_dates.between(min_date, max_date)
    
    @staticmethod
    def _validate_salary_range(df: pd.DataFrame) -> pd.Series:
        salary = df["salary_usd_annual"]
        
        return salary.isna() | salary.between(20_000, 2_000_000)
    
    @staticmethod
    def _validate_manager_referential_integrity(df: pd.DataFrame) -> pd.Series:
        employee_ids = set(df["employee_id"].dropna())
        
        return df["manager_id"].isna() | df['manager_id'].isin(employee_ids)
    
    def export_report(
        self,
        report: pd.DataFrame,
        output_dir: Path,
        report_name: str = "data_quality_validation_report"
    ) -> None:
        """
        Export validation report as CSV and HTML.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = output_dir / f"{report_name}.csv"
        html_path = output_dir / f"{report_name}.html"
        
        report.to_csv(csv_path, index=False)
        report.to_html(html_path, index=False)
        
        logger.info("Exported validation report to %s", csv_path)
        logger.info("Exported validation report to %s", html_path)
        
    def export_failed_records(
        self,
        failed_records: pd.DataFrame,
        output_dir: Path,
        file_name: str = "failed_records"
    ) -> None:
        """
        Export failed records for a specific check as CSV.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / file_name
        
        failed_records.to_csv(output_path, index=False)
        
        logger.info("Exported failed validation records to %s", output_path)