"""Stewardship retains provenance and admits uploads through HAS_DATA."""

import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1] / "project"


class StewardContract(unittest.TestCase):
    def test_every_steward_requires_upload_and_propagates_provenance(self):
        with (ROOT / "config/pipelines.csv").open() as stream:
            pipelines = {
                r["PIPELINE_CODE"]
                for r in csv.DictReader(stream)
                if r["STEWARDABLE_FLAG"] == "Y"
            }
        self.assertEqual(len(pipelines), 4)
        with (ROOT / "config/task_parameters.csv").open() as stream:
            params = {
                (r["PIPELINE_CODE"], r["TASK_CODE"], r["PARAMETER_NAME"]): r[
                    "PARAMETER_VALUE"
                ]
                for r in csv.DictReader(stream)
            }
        with (ROOT / "config/task_dependencies.csv").open() as stream:
            edges = list(csv.DictReader(stream))
        for pipeline in pipelines:
            self.assertEqual(params[pipeline, "validate_file", "REQUIRE_UPLOADS"], "Y")
            downstream = [
                r
                for r in edges
                if r["PIPELINE_CODE"] == pipeline
                and r["DEPENDS_ON_TASK_CODE"] == "validate_file"
                and r["TASK_CODE"] == "steward_to_lnd"
            ]
            self.assertTrue(downstream)
            self.assertTrue(all(r["DEPENDENCY_TYPE"] == "HAS_DATA" for r in downstream))
        for name in [
            "steward_lnd_to_prs",
            "steward_prs_to_cdc",
            "steward_cdc_to_preods",
            "steward_preods_to_ods_interactions",
            "steward_to_ds_agents",
            "steward_to_ds_customer_types",
            "steward_to_ds_support_areas",
        ]:
            self.assertIn(
                "upload_id",
                (ROOT / "sql_scripts" / (name + ".sql")).read_text().lower(),
            )
