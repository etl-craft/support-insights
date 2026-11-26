"""Demo SQL survives a full refresh: it filters runs with $$pipeline_run_id_filter."""

import csv
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SQL = ROOT / "project" / "sql_scripts"
PARAMETERS = ROOT / "project" / "config" / "task_parameters.csv"
PLAIN_TOKEN = re.compile(r"\$\$pipeline_run_id(?!_)")
HARD_CODED = re.compile(r"pipeline_run_id\s*=\s*\$\$pipeline_run_id\b", re.IGNORECASE)


def active_parameters():
    with PARAMETERS.open(newline="") as handle:
        return {
            (row["PIPELINE_CODE"], row["TASK_CODE"], row["PARAMETER_NAME"]): row["PARAMETER_VALUE"]
            for row in csv.DictReader(handle)
            if row["ACTIVE_FLAG"] == "Y"
        }


class FullRefreshSql(unittest.TestCase):
    def test_no_sql_compares_pipeline_run_id_to_the_current_run(self):
        offending = [
            f"{path.name}:{number}"
            for path in sorted(SQL.glob("*.sql"))
            for number, line in enumerate(path.read_text().splitlines(), 1)
            if HARD_CODED.search(line)
        ]
        self.assertEqual(offending, [], "use $$pipeline_run_id_filter, which is 1=1 on a full refresh")

    def test_every_filtered_script_enables_the_filter_and_nothing_else(self):
        parameters = active_parameters()
        scripts = {
            value.rsplit("/", 1)[-1]: key[:2]
            for key, value in parameters.items()
            if key[2] == "SCRIPT_FILE"
        }
        filtered = [path for path in sorted(SQL.glob("*.sql")) if "$$pipeline_run_id_filter" in path.read_text()]
        self.assertTrue(filtered)
        for path in filtered:
            task = scripts[path.name]
            self.assertEqual(parameters.get((*task, "PIPELINE_RUN_ID_FILTER")), "true", path.name)
            if not PLAIN_TOKEN.search(path.read_text()):
                substitution = parameters.get((*task, "PIPELINE_RUN_ID_SUBSTITUTION"), "false")
                self.assertEqual(substitution, "false", path.name)


if __name__ == "__main__":
    unittest.main()
