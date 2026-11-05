"""Every lake table is named explicitly and every maintenance task refuses automatic retry."""

import csv
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1] / "project"


class MaintenanceContract(unittest.TestCase):
    def test_explicit_table_list_covers_the_lake(self):
        with (ROOT / "config/tables.csv").open() as stream:
            tables = {
                row["SCHEMA_NAME"] + "." + row["TABLE_NAME"]
                for row in csv.DictReader(stream)
            }
        tables.add("lnd.gamma_object_events")
        statements = {}
        for path in (ROOT / "sql_scripts").glob("maintenance_*.sql"):
            for table, operation in re.findall(
                r"ALTER TABLE ([\w.]+) EXECUTE (\w+)\(", path.read_text()
            ):
                statements.setdefault(table, []).append(operation)
        self.assertEqual(set(statements), tables)
        for table, operations in statements.items():
            self.assertEqual(
                operations,
                ["optimize", "expire_snapshots", "remove_orphan_files"],
                table,
            )

    def test_nightly_maintenance_has_no_retry(self):
        with (ROOT / "config/tasks.csv").open() as stream:
            tasks = {
                row["TASK_CODE"]
                for row in csv.DictReader(stream)
                if row["PIPELINE_CODE"] == "SI_MAINTENANCE"
            }
        self.assertTrue(tasks)
        with (ROOT / "config/task_parameters.csv").open() as stream:
            retry = {
                row["TASK_CODE"]: row["PARAMETER_VALUE"]
                for row in csv.DictReader(stream)
                if row["PIPELINE_CODE"] == "SI_MAINTENANCE"
                and row["PARAMETER_NAME"] == "RETRY_ON"
            }
        self.assertEqual(retry, dict.fromkeys(tasks, "NONE"))
        with (ROOT / "config/pipelines.csv").open() as stream:
            row = next(
                row
                for row in csv.DictReader(stream)
                if row["PIPELINE_CODE"] == "SI_MAINTENANCE"
            )
        self.assertEqual(row["RUN_SCHEDULE"], "0 2 * * *")
        self.assertEqual(row["SCHEDULE_TIMEZONE"], "UTC")
