"""Run with python -m unittest discover -s tests."""

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generators"))
from db_operations import reserve_batch


class GeneratorLimits(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        path = str(Path(self.directory.name) / "state.db")
        self.environment = patch.dict(os.environ, SQLITE_DB_FILE=path)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        with sqlite3.connect(path) as conn:
            conn.execute(
                "CREATE TABLE daily_budget(day TEXT, client TEXT, rows INTEGER, PRIMARY KEY(day,client))"
            )

    def test_daily_cap_includes_updates_and_is_per_client(self):
        for _ in range(8):
            self.assertEqual(reserve_batch("alpha", 1000), 1000)
        with self.assertRaisesRegex(RuntimeError, "daily rows 10000.*10000"):
            reserve_batch("alpha", 1)
        self.assertEqual(reserve_batch("beta", 1000), 1000)

    def test_bad_batch_does_not_spend_budget(self):
        for count in [0, -1, 1001]:
            with self.assertRaisesRegex(RuntimeError, "expected 1..1000"):
                reserve_batch("alpha", count)
        with sqlite3.connect(os.environ["SQLITE_DB_FILE"]) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT count(*) AS count FROM daily_budget").fetchone()
            self.assertEqual(row["count"], 0)
