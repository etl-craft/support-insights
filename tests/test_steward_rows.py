"""Uploaded CSVs independently define expected stewarded rows and per-row writers."""

import csv
import json
import os
import unittest
from datetime import datetime
from pathlib import Path

import test_pipeline_rows

ROOT = Path(__file__).parents[1]


def normalized(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    return str(value)


@unittest.skipUnless(
    os.environ.get("SI_STEWARD_INPUTS"),
    "set SI_STEWARD_INPUTS after the exact upload runs",
)
class StewardRows(unittest.TestCase):
    def inputs(self):
        return json.loads(Path(os.environ["SI_STEWARD_INPUTS"]).read_text())

    def wanted(self, files):
        result = []
        for file in files:
            with (ROOT / file["fixture"]).open() as stream:
                for row in csv.DictReader(stream, delimiter="|"):
                    row.pop("LOCKED", None)
                    row |= {
                        "upload_id": str(file["upload_id"]),
                        "created_by": file["account"],
                        "updated_by": file["account"],
                    }
                    row |= file.get("retained_metadata", {}).get(
                        row[next(iter(row))], {}
                    )
                    result.append(row)
        return result

    def compare(self, table, wanted, keys, *, actors=False, stage=False):
        fields = list(wanted[0])
        if not actors:
            fields = [
                field for field in fields if field not in ("created_by", "updated_by")
            ]
        columns = [
            *fields,
            *(["active_flag"] if table.startswith("prs.") else []),
            *(["load_source"] if stage else []),
        ]
        rows = test_pipeline_rows.PipelineRows().rows(table, columns)
        wanted_keys = {tuple(row[key] for key in keys) for row in wanted}
        received = []
        for row in rows:
            if table.startswith("prs.") and row.pop("active_flag") != "Y":
                continue
            if stage and row.pop("load_source") != "STEWARD":
                continue
            row = {key: normalized(value) for key, value in row.items()}
            if tuple(row[key] for key in keys) in wanted_keys:
                received.append(row)
        expected = [
            {key: value for key, value in row.items() if key in fields}
            for row in wanted
        ]
        self.assertEqual(sorted(received, key=str), sorted(expected, key=str), table)

    def test_three_reference_uploads_and_their_history_copies(self):
        for table, item in self.inputs()["reference"].items():
            wanted = self.wanted(item["files"])
            key = {
                "agents": "agent_id",
                "customer_types": "customer_type_id",
                "support_areas": "support_area_id",
            }[table]
            self.compare("ds." + table, wanted, [key], actors=True)
            business = [
                {
                    key: value
                    for key, value in row.items()
                    if key not in ("upload_id", "created_by", "updated_by")
                }
                for row in wanted
            ]
            self.compare("dwh.ds_" + table, business, [key])

    def test_two_uploaders_keep_identity_through_every_business_stage(self):
        item = self.inputs()["business"]
        wanted = self.wanted(item["files"])
        self.assertEqual(len({row["updated_by"] for row in wanted}), 2)
        for table in [
            "lnd.steward_cs_data",
            "prs.steward_cs_data",
            "cdc.steward_cs_data",
            "pre_ods.customer_support_stage",
            "ods.interactions",
        ]:
            self.compare(
                table,
                wanted,
                ["source_id", "source_system_identifier"],
                actors=table.startswith(("prs.", "ods.")),
                stage=table.startswith("pre_ods."),
            )
