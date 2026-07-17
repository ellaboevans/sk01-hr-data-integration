import unittest

import pandas as pd

from hr_pipeline.config import STANDARD_EMPLOYEE_COLUMNS
from hr_pipeline.dedup import (
    build_exact_id_golden_dataset,
    deduplicate_hris_identity_records,
)


class DeduplicateHrisIdentityRecordsTests(unittest.TestCase):
    def test_identical_duplicates_mark_exactly_one_record_as_kept(self) -> None:
        row = {column: pd.NA for column in STANDARD_EMPLOYEE_COLUMNS}
        row.update(
            {
                "employee_id": "GT-000001",
                "source_employee_id": "1",
                "company_origin": "GlobalTech",
                "full_name": "Ada Lovelace",
                "email": "ada@example.com",
                "hire_date": pd.Timestamp("2020-01-01"),
                "source_system": "globaltech_hris",
            }
        )
        hris_records = pd.DataFrame([row, row.copy()])

        deduplicated, duplicate_review = deduplicate_hris_identity_records(
            hris_records
        )

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(int(duplicate_review["kept_in_golden"].sum()), 1)

    def test_exact_id_build_enriches_hris_and_isolates_ghost_payroll(self) -> None:
        def row(**values: object) -> dict[str, object]:
            record = {column: pd.NA for column in STANDARD_EMPLOYEE_COLUMNS}
            record.update(values)
            return record

        combined = pd.DataFrame(
            [
                row(
                    employee_id="GT-000001",
                    company_origin="GlobalTech",
                    full_name="Ada Lovelace",
                    source_system="globaltech_hris",
                ),
                row(
                    employee_id="GT-000001",
                    company_origin="GlobalTech",
                    salary_usd_annual=100_000.0,
                    source_system="payroll",
                ),
                row(
                    employee_id="GT-999999",
                    company_origin="GlobalTech",
                    salary_usd_annual=90_000.0,
                    source_system="payroll",
                ),
            ]
        )

        golden, ghost_records, _ = build_exact_id_golden_dataset(combined)

        self.assertEqual(golden["employee_id"].tolist(), ["GT-000001"])
        self.assertEqual(golden.loc[0, "salary_usd_annual"], 100_000.0)
        self.assertEqual(ghost_records["employee_id"].tolist(), ["GT-999999"])


if __name__ == "__main__":
    unittest.main()
