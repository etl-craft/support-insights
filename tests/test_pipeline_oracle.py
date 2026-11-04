"""Deterministic generator outputs exercise the independent oracle's source formats."""

import json
import unittest
from pathlib import Path

from pipeline_oracle import expected


class SourceMeanings(unittest.TestCase):
    def test_three_generator_formats_have_the_expected_business_meanings(self):
        records = json.loads(
            (Path(__file__).parent / "fixtures/generator-records.json").read_text()
        )
        for client, rows in records.items():
            result = expected(client, rows[0])
            self.assertEqual(result["source_system_identifier"], "17")
            identity = {"alpha": 1, "beta": 11, "gamma": 21}[client]
            self.assertEqual(result["agent_id"], identity)
            self.assertEqual(result["support_area_id"], identity)
            self.assertEqual(result["customer_type_id"], identity)
            self.assertGreaterEqual(result["handle_time"], 0)
            self.assertGreaterEqual(result["work_time"], 0)
            self.assertIn(result["customer_rating"], range(1, 6))

    def test_incomplete_lookup_remains_an_ods_candidate(self):
        records = json.loads(
            (Path(__file__).parent / "fixtures/generator-records.json").read_text()
        )
        for client, field in (
            ("alpha", "AGENT_PSEUDO_NAME"),
            ("beta", "AGENT_CODE"),
            ("gamma", "AGENT_NAME"),
        ):
            data = dict(records[client][0])
            data[field] = None
            result = expected(client, data)
            self.assertIsNone(result["agent_id"])
            self.assertEqual(result["source_system_identifier"], "17")
            self.assertGreaterEqual(result["handle_time"], 0)
