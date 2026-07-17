import unittest

import pandas as pd

from hr_pipeline.clean import clean_standardized_dataframe
from hr_pipeline.config import STANDARD_EMPLOYEE_COLUMNS


def canonical_row(**overrides: object) -> pd.DataFrame:
    row = {column: pd.NA for column in STANDARD_EMPLOYEE_COLUMNS}
    row.update(overrides)
    return pd.DataFrame([row])


class CleanStandardizedDataframeTests(unittest.TestCase):
    def test_source_full_name_is_preserved_when_name_parts_are_missing(self) -> None:
        source = canonical_row(
            employee_id="ACQ_00001",
            company_origin="AcquiredCo",
            full_name="  madonna  ",
            source_system="acquiredco_hris",
        )

        cleaned = clean_standardized_dataframe(source)

        self.assertEqual(cleaned.loc[0, "full_name"], "Madonna")


if __name__ == "__main__":
    unittest.main()
