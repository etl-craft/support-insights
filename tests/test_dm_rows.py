"""Generator inputs and original reference seeds independently define active mart rows."""

import csv
import json
import os
import unittest
from pathlib import Path

import test_pipeline_rows
from pipeline_oracle import eligible, expected

ROOT = Path(__file__).parents[1]


@unittest.skipUnless(
    os.environ.get("SI_DM_INPUTS"), "set SI_DM_INPUTS after a completed DM window"
)
class DMRows(unittest.TestCase):
    def test_active_facts_match_inputs_and_reference_names(self):
        inputs = json.loads(Path(os.environ["SI_DM_INPUTS"]).read_text())
        seeds = {}
        for table in ("agents", "support_areas", "customer_types"):
            with (
                ROOT / "project/seeds/warehouse/ds" / table / "data.csv"
            ).open() as stream:
                seeds[table] = list(csv.DictReader(stream, delimiter="|"))
        for table, paths in inputs.get("reference_overrides", {}).items():
            key = {
                "agents": "agent_id",
                "customer_types": "customer_type_id",
                "support_areas": "support_area_id",
            }[table]
            for path in paths:
                with (ROOT / path).open() as stream:
                    for override in csv.DictReader(stream, delimiter="|"):
                        override.pop("LOCKED", None)
                        seeds[table] = [
                            row for row in seeds[table] if row[key] != override[key]
                        ] + [override]
        corrections = {}
        numbers = {
            "source_id",
            "agent_id",
            "support_area_id",
            "customer_type_id",
            "handle_time",
            "work_time",
            "customer_rating",
        }
        for path in inputs.get("business_overrides", []):
            with (ROOT / path).open() as stream:
                for correction in csv.DictReader(stream, delimiter="|"):
                    correction.pop("LOCKED", None)
                    correction = {
                        key: int(value)
                        if key in numbers
                        else value.lower() == "true"
                        if key == "first_contact_resolution"
                        else value
                        for key, value in correction.items()
                    }
                    corrections[
                        str(correction["source_id"])
                        + ":"
                        + correction["source_system_identifier"]
                    ] = correction
        self.assertIn(
            "source_runs",
            inputs,
            "capture each client's exact run and CDC task-run IDs",
        )
        wanted = []
        keys = set()
        for client in ("alpha", "beta", "gamma"):
            for raw in inputs[client]:
                row = expected(client, raw)
                identity = str(row["source_id"]) + ":" + row["source_system_identifier"]
                row |= corrections.get(identity, {})
                keys.add((row["source_id"], row["source_system_identifier"]))
                if not eligible(row):
                    continue
                for table, key, output, source in (
                    ("agents", "agent_id", "agent_name", None),
                    (
                        "support_areas",
                        "support_area_id",
                        "support_area_name",
                        "support_area_name",
                    ),
                    (
                        "customer_types",
                        "customer_type_id",
                        "customer_type_name",
                        "customer_type_name",
                    ),
                ):
                    match = next(
                        (r for r in seeds[table] if int(r[key]) == row[key]), None
                    )
                    row[output] = (
                        " ".join(
                            match[k]
                            for k in ("first_name", "middle_name", "last_name")
                            if match[k]
                        )
                        if match and source is None
                        else match[source]
                        if match
                        else ""
                        if source is None
                        else None
                    )
                row |= inputs.get("provenance_overrides", {}).get(
                    identity, inputs["source_runs"][client]
                )
                wanted.append(row)
        actual = test_pipeline_rows.PipelineRows().rows(
            "dm.customer_support_fact", list(wanted[0])
        )
        actual = [
            r for r in actual if (r["source_id"], r["source_system_identifier"]) in keys
        ]
        for row in actual:
            row["interaction_date"] = (
                row["interaction_date"].isoformat(sep=" ")
                if row["interaction_date"]
                else None
            )
        self.assertEqual(sorted(actual, key=str), sorted(wanted, key=str))
        self.assertEqual(
            len(actual),
            len({(r["source_id"], r["source_system_identifier"]) for r in actual}),
        )
