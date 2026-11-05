"""Inspect exact completed DM runs and prove an empty window changes only its cursor."""

import json
import os
import unittest
from datetime import datetime
from pathlib import Path

import test_pipeline_rows


@unittest.skipUnless(
    os.environ.get("SI_DM_WINDOWS"), "set SI_DM_WINDOWS to exact run snapshots"
)
class DMPublication(unittest.TestCase):
    def test_empty_success_advances_without_new_versions(self):
        evidence = json.loads(Path(os.environ["SI_DM_WINDOWS"]).read_text())
        first, empty = evidence["first"], evidence["empty"]
        for result in (first, empty):
            self.assertEqual(result["run"]["status"], "SUCCESS")
        tasks = [
            next(
                task["explanation"]["task"]
                for task in result["tasks"]
                if task["task_code"] == "ods_to_dm"
            )
            for result in (first, empty)
        ]
        self.assertEqual(tasks[1]["source_count"], 0)
        self.assertEqual(tasks[1]["rows_written"], 0)
        self.assertEqual(tasks[0]["watermark_to"], tasks[1]["watermark_from"])
        self.assertGreater(
            datetime.fromisoformat(tasks[1]["watermark_to"]),
            datetime.fromisoformat(tasks[1]["watermark_from"]),
        )
        actual = test_pipeline_rows.PipelineRows().rows(
            "dm.customer_support_fact",
            ["source_id", "source_system_identifier", "row_id", "hash_key"],
        )
        self.assertEqual(
            sorted(actual, key=str), sorted(evidence["active_before_empty"], key=str)
        )
