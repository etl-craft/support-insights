"""The orchestrator's log download serves files of its logs directory and nothing else."""

import asyncio
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import make_mocked_request

ROOT = Path(__file__).resolve().parents[1]


def load(logs: str):
    os.environ["ORCH_LOG_DIR"] = logs
    sys.path.insert(0, str(ROOT / "generators"))  # the orchestrator imports its siblings
    spec = importlib.util.spec_from_file_location(
        "orchestrator_under_test", ROOT / "infra" / "entrypoint" / "data_generator_orchestrator.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LogDownload(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.logs = os.path.join(self.folder.name, "logs")
        os.makedirs(self.logs)
        Path(self.logs, "alpha.log").write_text("alpha")
        Path(self.folder.name, "secret.txt").write_text("outside")
        self.module = load(self.logs)

    def tearDown(self):
        self.folder.cleanup()

    def ask(self, name: str):
        request = make_mocked_request("GET", "/logs", match_info={})
        request = request.clone(rel_url=f"/logs?file={name}")
        return asyncio.run(self.module.log_handler(request))

    def test_a_log_of_the_directory_is_served_by_name_or_by_its_full_path(self):
        for name in ("alpha.log", os.path.join(self.logs, "alpha.log")):
            self.assertEqual(self.ask(name).status, 200)

    def test_nothing_outside_the_directory_is_served(self):
        outside = os.path.join(self.folder.name, "secret.txt")
        for name in (outside, "../secret.txt", self.logs + "/../secret.txt", "missing.log", ""):
            with self.assertRaises(web.HTTPNotFound, msg=name):
                self.ask(name)


if __name__ == "__main__":
    unittest.main()
