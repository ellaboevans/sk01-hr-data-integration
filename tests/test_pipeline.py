import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from hr_pipeline.pipeline import (
    build_probable_matches_export,
    write_golden_dataset,
)


class ProbableMatchesExportTests(unittest.TestCase):
    def test_exact_name_match_without_score_exports_as_full_similarity(self) -> None:
        probable_matches = pd.DataFrame(
            [
                {
                    "match_type": "same_full_name_hire_date_window",
                    "left_employee_id": "AC-000001",
                    "right_employee_id": "GT-000001",
                    "left_company_origin": "AcquiredCo",
                    "right_company_origin": "GlobalTech",
                    "left_full_name": "Ada Lovelace",
                    "right_full_name": "Ada Lovelace",
                    "left_email": "ada@acquired.example",
                    "right_email": "ada@global.example",
                    "left_hire_date": pd.Timestamp("2020-01-01"),
                    "right_hire_date": pd.Timestamp("2020-01-02"),
                    "hire_date_gap_days": 1,
                    "review_required": True,
                }
            ]
        )

        exported = build_probable_matches_export(probable_matches)

        self.assertEqual(exported.loc[0, "similarity_score"], 100.0)
        self.assertEqual(exported.loc[0, "recommended_action"], "HR_REVIEW")


class GoldenDatasetPublishingTests(unittest.TestCase):
    def test_new_dataset_is_staged_before_replacing_existing_output(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "golden_employee_dataset"
            old = pd.DataFrame(
                [{"employee_id": "GT-000001", "company_origin": "GlobalTech"}]
            )
            new = pd.DataFrame(
                [{"employee_id": "AC-000001", "company_origin": "AcquiredCo"}]
            )
            old.to_parquet(
                output_path,
                partition_cols=["company_origin"],
                index=False,
            )

            write_golden_dataset(new, output_path)

            published = pd.read_parquet(output_path)
            self.assertEqual(published["employee_id"].tolist(), ["AC-000001"])
            temporary_artifacts = [
                path
                for path in output_path.parent.iterdir()
                if path.name.startswith(".golden_employee_dataset-")
            ]
            self.assertEqual(temporary_artifacts, [])

    def test_unreadable_staged_dataset_does_not_replace_existing_output(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "golden_employee_dataset"
            old = pd.DataFrame(
                [{"employee_id": "GT-000001", "company_origin": "GlobalTech"}]
            )
            new = pd.DataFrame(
                [{"employee_id": "AC-000001", "company_origin": "AcquiredCo"}]
            )
            old.to_parquet(
                output_path,
                partition_cols=["company_origin"],
                index=False,
            )

            with patch(
                "hr_pipeline.pipeline.pd.read_parquet",
                side_effect=RuntimeError("staged dataset is unreadable"),
            ):
                with self.assertRaisesRegex(RuntimeError, "unreadable"):
                    write_golden_dataset(new, output_path)

            published = pd.read_parquet(output_path)
            self.assertEqual(published["employee_id"].tolist(), ["GT-000001"])


if __name__ == "__main__":
    unittest.main()
