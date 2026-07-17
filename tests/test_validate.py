import unittest

import pandas as pd

from hr_pipeline.validate import DataQualityValidator


class DataQualityGateTests(unittest.TestCase):
    def test_critical_check_failure_always_fails_gate(self) -> None:
        report = pd.DataFrame(
            [
                {
                    "check": "employee_id_unique",
                    "status": "FAIL",
                }
            ]
        )
        validator = DataQualityValidator(max_failed_checks=2)

        with self.assertRaisesRegex(ValueError, "Critical checks failed"):
            validator.assert_quality_gate(report)


if __name__ == "__main__":
    unittest.main()
