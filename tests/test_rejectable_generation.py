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
                with (
                    Path(__file__).parents[1] / "project/config/columns.csv"
                ).open() as stream:
                    contract = [
                        column
                        for column in csv.DictReader(stream)
                        if column["TABLE_NAME"] == f"client_{client}_cs_data"
                        and column["COLUMN_NAME"] == duration_column
                    ]
                self.assertEqual(len(contract), 1)
                self.assertEqual(contract[0]["DATA_TYPE"], "VARCHAR")
                self.assertEqual(
                    duration,
                    -1
                    if client == "alpha"
                    else "-1:00:00"
                    if client == "beta"
                    else "-1",
                )
                with patch.object(sys, "argv", ["generate", "3"]):
                    self.assertEqual(module._parse_args(), 3)
                self.assertFalse(module.REJECTABLE)
