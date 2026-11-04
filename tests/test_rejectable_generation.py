"""The opt-in bad batch remains bounded and produces a definite REJECT predicate."""

import csv
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "generators"))


class RejectableBatch(unittest.TestCase):
    def test_each_client_generates_negative_duration_only_when_requested(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(os.environ, SCRIPT_LOG_FILE=folder + "/generator.log"),
        ):
            for client in ("alpha", "beta", "gamma"):
                module = importlib.import_module(f"client_{client}_data_generator")
                with patch.object(sys, "argv", ["generate", "3", "--rejectable"]):
                    self.assertEqual(module._parse_args(), 3)
                row = module.generate_random_record(17, ["AREA"], ["AGENT"], ["TYPE"])
                duration = (
                    row["INTERACTION_DURATION"]
                    if client == "alpha"
                    else row.find("CONTACT_DURATION").text
                    if client == "beta"
                    else row[module._HEADERS.index("DURATION")]
                )
                duration_column = {
                    "alpha": "interaction_duration",
                    "beta": "contact_duration",
                    "gamma": "duration",
                }[client]
                with (Path(__file__).parents[1] / "project/config/columns.csv").open() as stream:
                    contract = [
                        column
                        for column in csv.DictReader(stream)
                        if column["TABLE_NAME"] == f"client_{client}_cs_data"
                        and column["COLUMN_NAME"] == duration_column
                    ]
                self.assertEqual(len(contract), 1)
                self.assertEqual(contract[0]["DATA_TYPE"], "VARCHAR")
                self.assertEqual(
                    duration, -1 if client == "alpha" else "-1:00:00" if client == "beta" else "-1"
                )
                with patch.object(sys, "argv", ["generate", "3"]):
                    self.assertEqual(module._parse_args(), 3)
                self.assertFalse(module.REJECTABLE)

    @unittest.skipUnless(os.environ.get("SI_TRINO_HOST"), "requires local Trino")
    def test_rejectable_values_parse_before_business_rules(self):
        import sqlglot
        from trino.dbapi import connect

        root = Path(__file__).parents[1]
        connection = connect(
            host=os.environ["SI_TRINO_HOST"],
            port=int(os.environ.get("SI_TRINO_PORT", "8080")),
            user="rejectable-test",
        )
        try:
            with (
                tempfile.TemporaryDirectory() as folder,
                patch.dict(os.environ, SCRIPT_LOG_FILE=folder + "/generator.log"),
            ):
                for client in ("alpha", "beta", "gamma"):
                    module = importlib.import_module(f"client_{client}_data_generator")
                    try:
                        module.REJECTABLE = True
                        row = module.generate_random_record(17, ["AREA"], ["AGENT"], ["TYPE"])
                        data = (
                            row
                            if client == "alpha"
                            else {element.tag: element.text for element in row}
                            if client == "beta"
                            else dict(zip(module._HEADERS, row, strict=True))
                        )
                        tree = sqlglot.parse_one(
                            (root / f"project/sql_scripts/{client}_cdc_to_preods.sql").read_text(),
                            read="trino",
                        )
                        names = {
                            "handle_time",
                            "work_time",
                            "customer_rating",
                            "interaction_date",
                            "first_contact_resolution",
                        }
                        expressions = [item for item in tree.expressions if item.alias in names]
                        columns = sorted(
                            {
                                column.name
                                for item in expressions
                                for column in item.find_all(sqlglot.exp.Column)
                            }
                        )
                        sql = "SELECT " + ", ".join(
                            item.sql(dialect="trino") for item in expressions
                        )
                        sql += " FROM (VALUES (" + ", ".join("?" for _ in columns) + ")) AS c ("
                        sql += ", ".join(columns) + ")"
                        cursor = connection.cursor()
                        cursor.execute(sql, [str(data[name.upper()]) for name in columns])
                        result = dict(
                            zip(
                                [item.alias for item in expressions], cursor.fetchone(), strict=True
                            )
                        )
                        with self.subTest(client=client):
                            self.assertTrue(
                                all(value is not None for value in result.values()), result
                            )
                            self.assertLess(result["handle_time"], 0)
                            self.assertGreaterEqual(result["work_time"], 0)
                            self.assertIn(result["customer_rating"], range(1, 6))
                    finally:
                        module.REJECTABLE = False
        finally:
            connection.close()
