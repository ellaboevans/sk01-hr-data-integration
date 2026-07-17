import unittest

import pandas as pd

from hr_pipeline.config import STANDARD_EMPLOYEE_COLUMNS
from hr_pipeline.ingest import align_all_sources


class AlignAllSourcesTests(unittest.TestCase):
    def test_empty_source_aligns_to_empty_canonical_dataframe(self) -> None:
        aligned = align_all_sources({"globaltech_hris": pd.DataFrame()})

        self.assertIn("globaltech_hris", aligned)
        self.assertTrue(aligned["globaltech_hris"].empty)
        self.assertEqual(
            list(aligned["globaltech_hris"].columns),
            STANDARD_EMPLOYEE_COLUMNS,
        )

    def test_nonempty_source_with_missing_columns_has_descriptive_error(self) -> None:
        incomplete_source = pd.DataFrame({"first_name": ["Ada"]})

        with self.assertRaisesRegex(
            ValueError,
            "globaltech_hris.*missing required columns.*employee_id",
        ):
            align_all_sources({"globaltech_hris": incomplete_source})


if __name__ == "__main__":
    unittest.main()
