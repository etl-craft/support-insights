import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generators"))
import gamma_webhook
from aiohttp import web


class GammaDelivery(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database = str(Path(directory.name) / "state.db")
        environment = patch.dict(os.environ, SQLITE_DB_FILE=self.database)
        environment.start()
        self.addCleanup(environment.stop)
        self.connection = Mock()
        self.connect = patch.object(
            gamma_webhook.trino.dbapi, "connect", return_value=self.connection
        )
        self.connect.start()
        self.addCleanup(self.connect.stop)
        self.record = {
            "eventName": "s3:ObjectCreated:Put",
            "eventTime": "2026-01-01T00:00:00Z",
            "s3": {
                "bucket": {"name": "gamma"},
                "object": {"key": "batch%27s%2Bfile.csv.gz", "eTag": "one", "size": 42},
            },
        }

    def test_receipt_replay_and_new_etag(self):
        gamma_webhook.deliver([self.record, self.record])
        execute = self.connection.cursor.return_value.execute
        self.assertEqual(execute.call_count, 1)
        sql, values = execute.call_args.args
        self.assertEqual(json.loads(values[0]), ["batch's+file.csv.gz", "one"])
        self.assertEqual(values[1], "batch's+file.csv.gz")
        self.assertNotIn("batch's", sql)
        self.record["s3"]["object"]["eTag"] = "two"
        gamma_webhook.deliver([self.record])
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(json.loads(execute.call_args.args[1][0]), ["batch's+file.csv.gz", "two"])

    def test_crash_after_insert_may_repeat_the_same_version_key(self):
        gamma_webhook.deliver([self.record])
        with sqlite3.connect(self.database) as connection:
            connection.execute("DELETE FROM event_receipts")
        gamma_webhook.deliver([self.record])
        calls = self.connection.cursor.return_value.execute.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].args[1], calls[1].args[1])

    def test_wrong_bucket_is_refused(self):
        self.record["s3"]["bucket"]["name"] = "lake"
        with self.assertRaises(web.HTTPBadRequest) as caught:
            gamma_webhook.deliver([self.record])
        for part in ("lake", "object_key", "expected gamma bucket", "fix notification filter"):
            self.assertIn(part, caught.exception.text)
        self.connection.cursor.return_value.execute.assert_not_called()

    def test_bad_object_metadata_is_refused_before_inserting(self):
        import copy

        for field, value in [
            ("eTag", None),
            ("eTag", ""),
            ("size", -1),
            ("size", "42"),
            ("size", True),
        ]:
            record = copy.deepcopy(self.record)
            record["s3"]["object"][field] = value
            with (
                self.subTest(field=field, value=value),
                self.assertRaises(web.HTTPBadRequest) as caught,
            ):
                gamma_webhook.deliver([record])
            for part in (
                "batch's+file.csv.gz",
                repr(value),
                "expected",
                "fix notification payload",
            ):
                self.assertIn(part, caught.exception.text)
        self.connection.cursor.return_value.execute.assert_not_called()


class WebhookAuthentication(unittest.IsolatedAsyncioTestCase):
    async def test_bad_bearer_cannot_deliver(self):
        request = Mock(headers={"Authorization": "Bearer wrong"})
        with (
            patch.dict(os.environ, GAMMA_WEBHOOK_TOKEN="expected"),
            patch.object(gamma_webhook, "deliver") as deliver,
        ):
            with self.assertRaises(web.HTTPUnauthorized):
                await gamma_webhook.receive(request)
            deliver.assert_not_called()
