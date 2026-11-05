"""Maintenance completes its exact run without changing the captured business rows."""

import json
import os
import unittest
from pathlib import Path

import test_pipeline_rows


@unittest.skipUnless(
    os.environ.get("SI_MAINTENANCE_INPUTS"),
    "set SI_MAINTENANCE_INPUTS after the drained maintenance run",
)
class MaintenanceRows(unittest.TestCase):
    def test_maintenance_keeps_rows_and_has_no_automatic_retry(self):
        evidence = json.loads(Path(os.environ["SI_MAINTENANCE_INPUTS"]).read_text())
        self.assertEqual(evidence["status"]["run"]["status"], "SUCCESS")
        tasks = evidence["status"]["tasks"]
        self.assertEqual(len(tasks), 9)
        for task in tasks:
            self.assertEqual(task["status"], "SUCCESS")
            self.assertEqual(task["attempts"], 1)
        for result in (evidence["gamma_before"], evidence["gamma_after"]):
            self.assertEqual(
                result["run"]["pipeline_run_id"],
                evidence["gamma_before"]["run"]["pipeline_run_id"],
            )
        waits = [
            next(
                task
                for task in result["tasks"]
                if task["task_code"] == "gamma_wait_objects"
            )["explanation"]["gate_waits"]
            for result in (evidence["gamma_before"], evidence["gamma_after"])
        ]
        self.assertTrue(waits[0] and waits[1])
        self.assertEqual(waits[0][0]["first_check_at"], waits[1][0]["first_check_at"])
        self.assertEqual(waits[0][0]["wait_until"], waits[1][0]["wait_until"])
        self.assertEqual(evidence["writer_count_before"], 0)
        for table, item in evidence["before"].items():
            rows = test_pipeline_rows.PipelineRows().rows(table, item["columns"])
            keys = {tuple(row[key] for key in item["keys"]) for row in item["rows"]}
            actual = [
                row for row in rows if tuple(row[key] for key in item["keys"]) in keys
            ]
            self.assertEqual(
                sorted(actual, key=str), sorted(item["rows"], key=str), table
            )
