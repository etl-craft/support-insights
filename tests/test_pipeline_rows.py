"""Small live oracles: independently captured generator inputs versus completed targets."""

import csv
import json
import os
import unittest
from pathlib import Path

from pipeline_oracle import eligible, expected

ROOT = Path(__file__).parents[1]


@unittest.skipUnless(
    os.environ.get("SI_ORACLE_INPUTS"),
    "set SI_ORACLE_INPUTS to the captured generator input JSON after pipeline runs",
)
class PipelineRows(unittest.TestCase):
    """The capture contains inputs, never expected SQL output or package-produced rows."""

    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads(Path(os.environ["SI_ORACLE_INPUTS"]).read_text())
        if not cls.inputs.get("setup_tables"):
            raise AssertionError(
                "oracle input must name the setup targets; capture the SI_SETUP inventory"
            )

    def rows(self, table, columns):
        from trino.dbapi import connect

        with connect(
            host=os.environ.get("SI_TRINO_HOST", "localhost"),
            port=int(os.environ.get("SI_TRINO_PORT", "8080")),
            user="etl_craft",
            catalog="warehouse",
            schema="ods",
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT "
                + ",".join(columns)
                + " FROM "
                + table
                + (
                    " WHERE ACTIVE_FLAG='Y'"
                    if table.startswith(("dm.", "dwh."))
                    else ""
                )
            )
            return [dict(zip(columns, row, strict=True)) for row in cursor]

    def client(self, name):
        candidates = [expected(name, row) for row in self.inputs[name]]
        wanted = [row for row in candidates if eligible(row)]
        stage = self.rows(
            "pre_ods.customer_support_stage", [*candidates[0], "load_source"]
        )
        keys = {(r["source_id"], r["source_system_identifier"]) for r in candidates}
        stage = [
            row
            for row in stage
            if row.pop("load_source") == name.upper()
            and (row["source_id"], row["source_system_identifier"]) in keys
        ]
        for row in stage:
            row["interaction_date"] = (
                None
                if row["interaction_date"] is None
                else row["interaction_date"].isoformat(sep=" ")
            )
        self.assertEqual(sorted(stage, key=str), sorted(candidates, key=str))
        actual = self.rows("ods.interactions", list(candidates[0]))
        for row in actual:
            row["interaction_date"] = (
                None
                if row["interaction_date"] is None
                else row["interaction_date"].isoformat(sep=" ")
            )
        actual = [
            r for r in actual if (r["source_id"], r["source_system_identifier"]) in keys
        ]
        self.assertEqual(
            sorted(actual, key=lambda r: str(r)), sorted(wanted, key=lambda r: str(r))
        )

        self.dimensions(wanted)

    def dimensions(self, wanted):
        for table, key in (
            ("agents", "agent_id"),
            ("customer_types", "customer_type_id"),
            ("support_areas", "support_area_id"),
        ):
            keys = {row[key] for row in wanted if row[key] is not None}
            with (
                ROOT / "project/seeds/warehouse/ds" / table / "data.csv"
            ).open() as stream:
                expected_rows = [
                    row
                    for row in csv.DictReader(stream, delimiter="|")
                    if int(row[key]) in keys
                ]
            if not expected_rows:
                continue
            actual = [
                row
                for row in self.rows("ods." + table, list(expected_rows[0]))
                if row[key] in keys
            ]
            self.assertEqual(
                sorted(self.normalized(actual), key=str), sorted(expected_rows, key=str)
            )

    @staticmethod
    def normalized(rows):
        return [
            {
                key: ""
                if value is None
                else str(value).lower()
                if isinstance(value, bool)
                else str(value)
                for key, value in row.items()
            }
            for row in rows
        ]

    def test_alpha(self):
        self.client("alpha")

    def test_beta(self):
        self.client("beta")

    def test_gamma(self):
        self.client("gamma")

    def test_reference(self):
        for schema, table in [
            ("ds", table)
            for table in ["agents", "customer_types", "support_areas", "sources"]
        ] + [("info", "data_dictionary")]:
            with (
                ROOT / "project/seeds/warehouse" / schema / table / "data.csv"
            ).open() as stream:
                wanted = [
                    {key: value for key, value in row.items() if key != "upload_id"}
                    for row in csv.DictReader(stream, delimiter="|")
                ]
            actual = self.rows("dwh." + schema + "_" + table, list(wanted[0]))
            normalized = [
                {
                    k: ""
                    if v is None
                    else str(v).lower()
                    if isinstance(v, bool)
                    else str(v)
                    for k, v in row.items()
                }
                for row in actual
            ]
            self.assertEqual(sorted(normalized, key=str), sorted(wanted, key=str))

    def test_setup(self):
        for table in self.inputs["setup_tables"]:
            # APPEND landing tables intentionally have no reserved audit columns.
            self.rows(table, ["count(*) AS row_count"])
