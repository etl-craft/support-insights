"""The original DS inserts independently define the exact seed rows and identities."""

import csv
import re
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class OriginalReferenceRows(unittest.TestCase):
    def test_ds_seeds_equal_the_original_records(self):
        with sqlite3.connect(":memory:") as conn:
            conn.execute("ATTACH DATABASE ':memory:' AS ds")
            ddl = (
                ROOT / "reference/legacy-sql/03_ds_schema_tables_creation.sql"
            ).read_text()
            ddl = ddl.split("-- Indexes for", 1)[0].replace("\\c support_insights", "")
            ddl = re.sub(r"REFERENCES\s+ds\.", "REFERENCES ", ddl, flags=re.IGNORECASE)
            conn.executescript(re.sub(r"\bSERIAL\b", "INTEGER", ddl))
            inserts = (
                ROOT / "reference/legacy-sql/13_ds_schema_tables_inserts.sql"
            ).read_text()
            conn.executescript(inserts.replace("\\c support_insights", ""))
            for table in ("sources", "agents", "support_areas", "customer_types"):
                folder = ROOT / "project/seeds/warehouse/ds" / table
                with (folder / "data.csv").open() as stream:
                    reader = csv.DictReader(stream, delimiter="|")
                    fields = [name for name in reader.fieldnames if name != "upload_id"]
                    received = list(reader)
                    self.assertNotIn("upload_id", reader.fieldnames)
                    if table != "sources":
                        declarations = (folder / "columns.csv").read_text()
                        self.assertIn("upload_id|BIGINT|N", declarations)
                    actual = [{name: row[name] for name in fields} for row in received]
                cursor = conn.execute(
                    f"SELECT {','.join(fields)} FROM ds.{table} ORDER BY {fields[0]}"
                )
                expected = [
                    {
                        name: ("true" if value else "false")
                        if name == "is_active"
                        else ""
                        if value is None
                        else str(value)
                        for name, value in zip(fields, row, strict=True)
                    }
                    for row in cursor
                ]
                self.assertEqual(actual, expected, table)
