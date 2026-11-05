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
                row |= inputs["source_runs"][client]
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
