"""Only REJECT flags gate ODS admission; incomplete records retain their provenance."""

import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1] / "project"


class RulePolicy(unittest.TestCase):
    def test_every_ods_write_excludes_only_reject_flags(self):
        paths = list((ROOT / "sql_scripts").glob("*_preods_to_ods_*.sql"))
        self.assertEqual(len(paths), 12)
        for path in paths:
            with self.subTest(task=path.stem):
                sql = path.read_text()
                self.assertIn("$$rule_flags(", sql)
                self.assertIn("_rules, REJECT)", sql)
                self.assertNotIn("INCOMPLETE", sql)
                self.assertNotIn("REPORT", sql)
