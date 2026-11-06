"""The two views keep their legacy contracts and take every value from tables this project builds."""

import csv
import re
import unittest
from pathlib import Path

PROJECT = Path(__file__).parents[1] / "project"
SQL = PROJECT / "sql_scripts"


def output_names(path):
    """The final SELECT's output names: each top-level `AS name` of the last SELECT list."""
    sql = path.read_text()
    select = sql[sql.rindex("\nSELECT") :]
    body = select[: re.search(r"\nFROM\b", select).start()]
    return re.findall(r"\bAS (\w+),?\s*$", body, re.MULTILINE)


def rows(name):
    with (PROJECT / "config" / name).open() as stream:
        return list(csv.DictReader(stream))


class Views(unittest.TestCase):
    def test_the_metrics_view_keeps_the_legacy_columns_in_order(self):
        self.assertEqual(
            output_names(SQL / "data_metrics_view.sql"),
            [
                "dag_run_id",
                "source_name",
                "run_start_date",
                "batch_count",
                "insert_count",
                "update_count",
                "duplicate_count",
                "valid_count",
                "data_quality_score",
                "run_duration_sec",
            ],
        )

    def test_the_fact_view_keeps_the_legacy_columns_then_adds_provenance_and_freshness(self):
        names = output_names(SQL / "customer_support_fact_view.sql")
        self.assertEqual(
            names[:15],
            [
                "source_name",
                "source_record_id",
                "source_system_identifier",
                "pseudo_code",
                "interaction_date",
                "support_area_name",
                "interaction_status",
                "interaction_type",
                "customer_type_name",
                "handle_time",
                "work_time",
                "first_contact_resolution",
                "query_status",
                "solution_type",
                "customer_rating",
            ],
        )
        self.assertEqual(
            names[15:],
            [
                "source_pipeline_run_id",
                "source_task_run_id",
                "upload_id",
                "steward",
                "upload_file_name",
                "dm_pipeline_run_id",
                "dm_task_run_id",
                "ods_changed_at",
                "committed_window_end",
                "freshness_seconds",
            ],
        )

    def test_the_fact_view_reads_active_versions_only_and_excludes_rejected_keys(self):
        sql = (SQL / "customer_support_fact_view.sql").read_text()
        self.assertIn("f.active_flag = 'Y'", sql)
        self.assertIn("f.delete_flag = 'N'", sql)
        self.assertIn("r.status = 'REJECT'", sql)
        self.assertNotIn("is_active", sql)
        self.assertNotIn("NOW()", sql.upper().replace("CURRENT_TIMESTAMP", ""))

    def test_the_metrics_view_reads_the_mirrored_audit_tables_not_a_dag_table(self):
        sql = (SQL / "data_metrics_view.sql").read_text()
        self.assertNotRegex(sql, r"(?i)dag_runs|\baud\.")
        for table in ("aud_pipelines_run_log", "aud_task_run_log", "aud_business_rules_results"):
            self.assertIn(f"aud_mirror.{table}", sql)
        self.assertIn("r.status = 'SUCCESS'", sql)

    def test_each_view_is_one_read_only_select_created_by_a_create_view_task(self):
        for name in ("customer_support_fact_view", "data_metrics_view"):
            sql = (SQL / f"{name}.sql").read_text()
            self.assertNotRegex(sql, r"(?i)\b(create|insert|update|delete|drop|merge)\b")
            self.assertEqual(sql.count(";"), 0)
            params = {
                r["PARAMETER_NAME"]: r["PARAMETER_VALUE"]
                for r in rows("task_parameters.csv")
                if r["PIPELINE_CODE"] == "SI_VIEWS" and r["TASK_CODE"] == name
            }
            self.assertEqual(params["SQL_ACTION"], "CREATE_VIEW")
            self.assertEqual(params["SCRIPT_FILE"], f"sql_scripts/{name}.sql")
            task = next(r for r in rows("tasks.csv") if r["TASK_CODE"] == name)
            self.assertEqual((task["TARGET_SCHEMA_NAME"], task["TARGET_TABLE_NAME"]), ("vw", name))
            table = next(r for r in rows("tables.csv") if r["TABLE_NAME"] == name)
            self.assertEqual((table["SCHEMA_NAME"], table["OBJECT_KIND"]), ("vw", "VIEW"))

    def test_cloning_mirrors_the_audit_tables_into_the_warehouse_schema(self):
        connector = (PROJECT / "craft-connector.yml").read_text()
        self.assertRegex(connector, r"(?m)^Cloning:\n  Every_minutes: \d+\n  dev:\n    Enabled: true\n    Scope: AUD\n")
        self.assertIn("Schema: aud_mirror", connector)


if __name__ == "__main__":
    unittest.main()
