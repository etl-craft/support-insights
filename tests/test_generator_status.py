import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra/entrypoint"))
import data_generator_orchestrator


class GeneratorStatus(unittest.IsolatedAsyncioTestCase):
    async def test_completed_run_timestamp_is_json_without_task_objects(self):
        request = Mock(
            app={
                "script_status": {
                    "alpha": {
                        "last_run": datetime(2026, 1, 1, tzinfo=timezone.utc),
                        "task": object(),
                        "status": "Completed",
                    }
                }
            }
        )
        response = await data_generator_orchestrator.status_handler(request)
        status = json.loads(response.text)["alpha"]
        self.assertEqual(status["last_run"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(status["status"], "Completed")
        self.assertNotIn("task", status)
