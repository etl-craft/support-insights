"""A duplicated object notification stays one admitted key and one landing object."""

import json
import os
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(
    os.environ.get("SI_DUPLICATE_EVENT"), "set SI_DUPLICATE_EVENT after its Gamma run"
)
class GammaDuplicateSignal(unittest.TestCase):
    def test_one_object_and_one_consumed_key(self):
        from trino.dbapi import connect

        signal = json.loads(Path(os.environ["SI_DUPLICATE_EVENT"]).read_text())
        with connect(
            host=os.environ.get("SI_TRINO_HOST", "localhost"),
            port=int(os.environ.get("SI_TRINO_PORT", "8080")),
            user="etl_craft",
            catalog="warehouse",
            schema="lnd",
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT count(*) FROM gamma_object_events WHERE event_key=?",
                [signal["event_key"]],
            )
            self.assertGreaterEqual(cursor.fetchone()[0], 2)
            cursor.execute(
                "SELECT count(*) FROM client_gamma_cs_data WHERE source_system_identifier=?",
                [signal["business_key"]],
            )
            self.assertEqual(cursor.fetchone()[0], 1)
        # The only interpolation is a server-derived key quoted as a SQL string literal.
        key = signal["event_key"].replace("'", "''")
        query = (
            "SELECT count(*) FROM etl_craft.aud_event_keys e "
            "JOIN etl_craft.cfg_tasks t USING(task_id) "
            "JOIN etl_craft.cfg_pipelines p ON p.pipeline_id=t.pipeline_id "
            "JOIN etl_craft.cfg_projects j ON j.project_id=p.project_id "
            "WHERE j.project_code='support_insights' AND t.task_code='gamma_wait_objects' "
            f"AND e.event_key='{key}'"
        )
        result = subprocess.check_output(
            [
                "kubectl",
                "exec",
                "engine-1",
                "--",
                "psql",
                "-U",
                "postgres",
                "-d",
                "etl_craft",
                "-At",
                "-c",
                query,
            ],
            text=True,
        )
        self.assertEqual(result.strip(), "1")
