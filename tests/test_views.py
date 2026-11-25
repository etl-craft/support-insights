"""The two views keep their legacy contracts and take every value from tables this project builds."""

import csv
import importlib.util
import json
import os
import re
import unittest
from datetime import UTC, datetime
from pathlib import Path

from pipeline_oracle import query_rows, stage_validity, trino_connection

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
                "load_reject_count",
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

    def test_metrics_load_tasks_match_client_write_configuration(self):
        actions = {
            (row["PIPELINE_CODE"], row["TASK_CODE"]): row["PARAMETER_VALUE"]
            for row in rows("task_parameters.csv")
            if row["PARAMETER_NAME"] == "SQL_ACTION" and row["ACTIVE_FLAG"] == "Y"
        }
        expected = set()
        for row in rows("tasks.csv"):
            pipeline, task = row["PIPELINE_CODE"], row["TASK_CODE"]
            target = row["TARGET_SCHEMA_NAME"]
            if (
                pipeline.startswith("SI_CLIENT_")
                and row["ACTIVE_FLAG"] == "Y"
                and target in {"prs", "cdc", "pre_ods"}
                and actions.get((pipeline, task)) in {"APPEND_TABLE", "OVERWRITE_TABLE", "SCD2_MERGE"}
            ):
                expected.add((pipeline, task, "TRUE" if target == "pre_ods" else "FALSE"))
        sql = (SQL / "data_metrics_view.sql").read_text()
        actual = set(re.findall(r"\('([^']+)', '([^']+)', (TRUE|FALSE)\)", sql))
        self.assertTrue(expected)
        self.assertEqual(actual, expected)

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

    def test_upload_provenance_has_an_offline_source_column_contract(self):
        contract = {
            r["COLUMN_NAME"]: r for r in rows("columns.csv")
            if r["SCHEMA_NAME"] == "aud_mirror" and r["TABLE_NAME"] == "aud_uploads"
        }
        table = next(
            r for r in rows("tables.csv")
            if r["SCHEMA_NAME"] == "aud_mirror" and r["TABLE_NAME"] == "aud_uploads"
        )
        self.assertEqual(table["ACTIVE_FLAG"], "Y")
        for name in ("upload_id", "account", "file_name"):
            self.assertIn(name, contract)
            self.assertEqual(contract[name]["ACTIVE_FLAG"], "Y")
        self.assertEqual(contract["upload_id"]["DATA_TYPE"].upper(), "BIGINT")

    def test_every_ingestion_documents_its_source_and_column_mappings(self):
        params = {}
        for row in rows("task_parameters.csv"):
            identity = (row["PIPELINE_CODE"], row["TASK_CODE"])
            params.setdefault(identity, {})[row["PARAMETER_NAME"]] = row["PARAMETER_VALUE"]
        for identity, values in params.items():
            if values.get("SCRIPT_KIND") == "INGESTION":
                with self.subTest(task=identity):
                    self.assertTrue(values.get("LINEAGE_SOURCE"))
                    self.assertTrue(values.get("LINEAGE_COLUMNS"))

    def test_cloning_mirrors_the_audit_tables_into_the_warehouse_schema(self):
        connector = re.sub(r" +#.*", "", (PROJECT / "craft-connector.yml").read_text())
        self.assertRegex(connector, r"(?m)^Cloning:\n  Every_minutes: \d+\n  dev:\n    Enabled: true\n    Scope: AUD\n")
        self.assertIn("Schema: aud_mirror", connector)


@unittest.skipUnless(
    importlib.util.find_spec("duckdb"), "install the package DuckDB test extra"
)
class MetricsAudit(unittest.TestCase):
    def test_validity_counts_only_successful_loads_and_only_reject_rules(self):
        import duckdb

        with duckdb.connect() as conn:
            conn.execute("""
                CREATE SCHEMA aud_mirror;
                CREATE SCHEMA ds;
                CREATE TABLE ds.sources AS
                    SELECT 1 AS source_id, 'CLIENT_ALPHA' AS source_name;
                CREATE TABLE aud_mirror.aud_cfg_pipelines_history AS
                    SELECT 1 AS pipeline_id, 'SI_CLIENT_ALPHA' AS pipeline_code, 'Y' AS current_flag;
                CREATE TABLE aud_mirror.aud_cfg_tasks_history AS
                    SELECT id AS task_id, code AS task_code, 1 AS pipeline_id, 'Y' AS current_flag
                    FROM (VALUES (1, 'alpha_source_to_lnd'), (2, 'alpha_lnd_to_prs'),
                        (3, 'alpha_cdc_to_preods'), (4, 'alpha_rules'),
                        (5, 'unrelated_cdc_to_preods')) AS tasks(id, code);
                CREATE TABLE aud_mirror.aud_pipelines_run_log AS
                    SELECT id AS pipeline_run_id, 1 AS pipeline_id, 'SUCCESS' AS status,
                        TIMESTAMP '2026-01-01' AS start_date,
                        TIMESTAMP '2026-01-01 00:00:01' AS end_date
                    FROM (VALUES (10), (11), (12)) AS runs(id);
                CREATE TABLE aud_mirror.aud_task_run_log AS
                    SELECT task_run_id, task_id, pipeline_run_id, 'SUCCESS' AS status,
                        source_count, insert_count, 0 AS update_count, duplicate_count
                    FROM (VALUES (1, 1, 10, 9, 9, 0), (2, 2, 10, 9, 4, 3),
                        (3, 3, 10, 4, 4, 0), (4, 4, 10, 4, 0, 0),
                        (5, 5, 10, 5, 5, 0), (6, 3, 11, 0, 0, 0),
                        (7, 4, 12, 0, 0, 0))
                    AS log(task_run_id, task_id, pipeline_run_id,
                        source_count, insert_count, duplicate_count);
                CREATE TABLE aud_mirror.aud_task_attempts AS
                    SELECT * FROM (VALUES (2, 1, 'SUCCESS', 4, 2),
                        (3, 1, 'SUCCESS', 5, 0), (3, 2, 'FAILED', 90, 70),
                        (3, 3, 'SUCCESS', 4, 0),
                        (5, 1, 'SUCCESS', 5, 5), (6, 1, 'SUCCESS', 0, 0))
                    AS attempts(task_run_id, attempt_number, status, insert_count, reject_count);
                CREATE TABLE aud_mirror.aud_business_rules_run_log AS
                    SELECT * FROM (VALUES (1, 4), (2, 4), (3, 7))
                    AS rules(business_rule_run_id, task_run_id);
                CREATE TABLE aud_mirror.aud_business_rules_results AS
                    SELECT business_rule_run_id, business_rule_key, status,
                        'warehouse' AS target_catalog_name, 'pre_ods' AS target_schema_name,
                        'customer_support_stage' AS target_table_name
                    FROM (VALUES (1, '101', 'REJECT'), (1, '102', 'INCOMPLETE'),
                        (1, '103', 'REPORT'), (2, '101', 'REJECT'),
                        (3, '102', 'REJECT'), (3, '104', 'REJECT'))
                    AS results(business_rule_run_id, business_rule_key, status);
                UPDATE aud_mirror.aud_pipelines_run_log SET status = 'FAILED'
                WHERE pipeline_run_id = 12;
            """)
            sql = (SQL / "data_metrics_view.sql").read_text()
            expected = [
                (10, "CLIENT_ALPHA", 9, 4, 0, 3, 2, 3, 50.0, 1.0),
                (11, "CLIENT_ALPHA", 0, 0, 0, 0, 0, 0, None, 1.0),
            ]
            self.assert_metrics(conn, sql, expected)
            for name, before, after in (
                ("incomplete and report remain valid", "r.status = 'REJECT'", "TRUE"),
                (
                    "failed attempt is excluded",
                    "a.status = 'SUCCESS'",
                    "a.status = 'FAILED'",
                ),
                (
                    "load rejects are checked",
                    " + COALESCE(staged.load_reject_count, 0)",
                    "",
                ),
            ):
                with self.subTest(mutation=name):
                    self.assertIn(before, sql)
                    with self.assertRaises(AssertionError):
                        self.assert_metrics(conn, sql.replace(before, after), expected)

    def assert_metrics(self, conn, sql, expected):
        got = conn.execute(f"""
            SELECT dag_run_id, source_name, batch_count, insert_count, update_count,
                duplicate_count, load_reject_count, valid_count, data_quality_score,
                run_duration_sec
            FROM ({sql}) AS metrics ORDER BY dag_run_id
        """).fetchall()
        self.assertEqual(got, expected)


@unittest.skipUnless(
    os.environ.get("SI_TRINO_PORT"), "set SI_TRINO_PORT for live view checks"
)
class LiveViews(unittest.TestCase):
    def test_stage_has_one_row_per_business_key_and_run(self):
        with trino_connection() as conn:
            duplicates = query_rows(
                conn,
                """
                SELECT pipeline_run_id, source_id, source_system_identifier, COUNT(*) AS copies
                FROM pre_ods.customer_support_stage
                GROUP BY pipeline_run_id, source_id, source_system_identifier
                HAVING COUNT(*) > 1
            """,
            )
        self.assertEqual(
            duplicates, [], "PRE_ODS business keys must be unique within a run"
        )

    def test_client_run_metrics_match_base_audit(self):
        with trino_connection() as conn:
            runs = query_rows(
                conn,
                """
                SELECT r.pipeline_run_id AS dag_run_id, s.source_name,
                       r.start_date AS run_start_date, r.end_date
                FROM aud_mirror.aud_pipelines_run_log r
                JOIN aud_mirror.aud_cfg_pipelines_history p USING (pipeline_id)
                JOIN ds.sources s ON p.pipeline_code = concat('SI_', s.source_name)
                WHERE p.current_flag = 'Y' AND r.status = 'SUCCESS'
                ORDER BY r.pipeline_run_id
            """,
            )
            self.assertTrue(runs, "finish a client run and clone its audit first")
            actual = query_rows(
                conn, "SELECT * FROM vw.data_metrics_view ORDER BY dag_run_id"
            )
            self.assertEqual(
                [row["dag_run_id"] for row in actual],
                [row["dag_run_id"] for row in runs],
            )
            for got, run in zip(actual, runs, strict=True):
                run_id = run["dag_run_id"]
                with self.subTest(run=run_id):
                    tasks = query_rows(
                        conn,
                        """
                        SELECT k.task_code, t.source_count, t.insert_count, t.update_count,
                               t.duplicate_count, t.task_run_id
                        FROM aud_mirror.aud_task_run_log t
                        JOIN aud_mirror.aud_cfg_tasks_history k USING (task_id)
                        WHERE t.pipeline_run_id = ? AND k.current_flag = 'Y' AND t.status = 'SUCCESS'
                    """,
                        [run_id],
                    )
                    client = run["source_name"].removeprefix("CLIENT_").lower()
                    by_code = {task["task_code"]: task for task in tasks}
                    ingestion = by_code.get(f"{client}_source_to_lnd", {})
                    versions = by_code.get(f"{client}_lnd_to_prs", {})
                    stage = by_code.get(f"{client}_cdc_to_preods", {})
                    rejected = query_rows(
                        conn,
                        """
                        SELECT DISTINCT r.business_rule_key
                        FROM aud_mirror.aud_business_rules_results r
                        WHERE (r.target_catalog_name, r.target_schema_name, r.target_table_name) =
                              ('warehouse', 'pre_ods', 'customer_support_stage')
                          AND r.status = 'REJECT'
                          AND r.business_rule_run_id IN (
                            SELECT b.business_rule_run_id
                            FROM aud_mirror.aud_business_rules_run_log b
                            WHERE b.task_run_id IN (
                                SELECT task_run_id FROM aud_mirror.aud_task_run_log
                                WHERE pipeline_run_id = ?
                            )
                          )
                    """,
                        [run_id],
                    )
                    staged = stage.get("insert_count") or 0
                    valid = staged - len(rejected)
                    self.assertAlmostEqual(
                        float(got.pop("run_duration_sec")),
                        (run["end_date"] - run["run_start_date"]).total_seconds(),
                        delta=0.001,
                    )
                    self.assertEqual(
                        got,
                        {
                            "dag_run_id": run_id,
                            "source_name": run["source_name"],
                            "run_start_date": run["run_start_date"],
                            "batch_count": ingestion.get("source_count") or 0,
                            "insert_count": (versions.get("insert_count") or 0)
                            - (versions.get("update_count") or 0),
                            "update_count": versions.get("update_count") or 0,
                            "duplicate_count": versions.get("duplicate_count") or 0,
                            "load_reject_count": 0,
                            "valid_count": valid,
                            "data_quality_score": 100.0 * valid / staged
                            if staged
                            else None,

                        },
                    )

    @unittest.skipUnless(
        os.environ.get("SI_VIEW_RUNS"),
        "set SI_VIEW_RUNS to first-run capture and second run ID",
    )
    def test_validity_survives_preods_replacement(self):
        capture = json.loads(Path(os.environ["SI_VIEW_RUNS"]).read_text())
        first = capture["first"]
        with trino_connection() as conn:
            self.assertTrue(first["rejected"])
            self.assertTrue(first["incomplete_only"])
            self.assertEqual(stage_validity(conn, first["run_id"])["staged"], 0)
            second = stage_validity(conn, capture["second_run_id"])
            self.assertGreater(second["staged"], 0)
            for expected in (first, second):
                with self.subTest(run=expected["run_id"]):
                    (got,) = query_rows(
                        conn,
                        """
                        SELECT * FROM vw.data_metrics_view WHERE dag_run_id = ?
                    """,
                        [expected["run_id"]],
                    )
                    valid = expected["staged"] - expected["rejected"]
                    self.assertEqual(got["valid_count"], valid)
                    self.assertAlmostEqual(
                        got["data_quality_score"], 100.0 * valid / expected["staged"]
                    )
                    if expected is first:
                        self.assertEqual(json.loads(json.dumps(got, default=str)), first["view"])

    def test_fact_measures_match_base_rows(self):
        measures = {
            "interactions": (
                "source_record_id",
                "interaction_status",
                "interaction_type",
            ),
            "first contact resolution": ("first_contact_resolution",),
            "handle and work time": ("handle_time", "work_time"),
            "ratings": ("customer_rating",),
            "query status": ("query_status", "solution_type"),
            "customer breakdown": ("customer_type_name",),
            "support area breakdown": ("support_area_name",),
            "volume over time": ("interaction_date",),
            "source and publisher provenance": (
                "source_pipeline_run_id",
                "source_task_run_id",
                "dm_pipeline_run_id",
                "dm_task_run_id",
                "ods_changed_at",
            ),
        }
        base = """
            FROM dm.customer_support_fact f
            JOIN ds.sources s ON s.source_id = f.source_id
            WHERE f.active_flag = 'Y' AND f.delete_flag = 'N'
              AND NOT EXISTS (
                SELECT 1 FROM pre_ods.customer_support_stage st
                JOIN aud_mirror.aud_business_rules_results r
                  ON r.business_rule_key = CAST(st.row_id AS VARCHAR)
                WHERE (st.source_id, st.source_system_identifier, st.pipeline_run_id) =
                      (f.source_id, f.source_system_identifier, f.source_pipeline_run_id)
                  AND r.target_schema_name = 'pre_ods'
                  AND r.target_table_name = 'customer_support_stage'
                  AND r.status = 'REJECT' AND r.active_flag = 'Y' AND r.end_date IS NULL
              )
        """
        identity = "source_name, source_system_identifier"
        order = f" ORDER BY {identity}"
        with trino_connection() as conn:
            for label, columns in measures.items():
                with self.subTest(measure=label):
                    projected = ", ".join(columns)
                    expected = projected.replace(
                        "dm_pipeline_run_id", "f.pipeline_run_id AS dm_pipeline_run_id"
                    )
                    expected = expected.replace(
                        "dm_task_run_id", "f.task_run_id AS dm_task_run_id"
                    )
                    self.assertEqual(
                        query_rows(
                            conn,
                            f"SELECT s.source_name, f.source_system_identifier, {expected} {base}{order}",
                        ),
                        query_rows(
                            conn,
                            f"SELECT {identity}, {projected} FROM vw.customer_support_fact_view{order}",
                        ),
                    )
            with self.subTest(measure="agent breakdown"):
                agents = query_rows(
                    conn,
                    f"""
                    SELECT s.source_name, f.source_system_identifier,
                        (SELECT a.pseudo_code FROM ds.agents a WHERE a.agent_id = f.agent_id) AS pseudo_code
                    {base}{order}
                """,
                )
                self.assertEqual(
                    agents,
                    query_rows(
                        conn,
                        f"SELECT {identity}, pseudo_code FROM vw.customer_support_fact_view{order}",
                    ),
                )
            with self.subTest(measure="latest interactions"):
                latest = " ORDER BY interaction_date DESC NULLS LAST, source_name, source_system_identifier LIMIT 20"
                self.assertEqual(
                    query_rows(
                        conn,
                        f"SELECT s.source_name, f.source_system_identifier, f.interaction_date {base}{latest}",
                    ),
                    query_rows(
                        conn,
                        f"SELECT {identity}, interaction_date FROM vw.customer_support_fact_view{latest}",
                    ),
                )
            with self.subTest(measure="committed window and freshness"):
                windows = query_rows(
                    conn,
                    """
                    SELECT t.watermark_to
                    FROM aud_mirror.aud_task_run_log t
                    WHERE t.status = 'SUCCESS' AND t.watermark_to IS NOT NULL
                      AND t.task_id IN (
                        SELECT k.task_id FROM aud_mirror.aud_cfg_tasks_history k
                        JOIN aud_mirror.aud_cfg_pipelines_history p ON p.pipeline_id = k.pipeline_id
                        WHERE k.current_flag = 'Y' AND p.current_flag = 'Y'
                          AND k.task_code = 'ods_to_dm' AND p.pipeline_code = 'SI_DM'
                      )
                    ORDER BY t.task_run_id DESC LIMIT 1
                """,
                )
                self.assertTrue(windows, "run SI_DM and refresh the audit mirror first")
                before = datetime.now(UTC).timestamp()
                freshness = query_rows(
                    conn,
                    """
                    SELECT DISTINCT committed_window_end, freshness_seconds
                    FROM vw.customer_support_fact_view
                """,
                )
                after = datetime.now(UTC).timestamp()
                self.assertEqual(len(freshness), 1)
                window = datetime.fromisoformat(windows[0]["watermark_to"])
                self.assertEqual(freshness[0]["committed_window_end"], window)
                self.assertLessEqual(
                    int(before - window.timestamp()) - 1, freshness[0]["freshness_seconds"]
                )
                self.assertGreaterEqual(
                    int(after - window.timestamp()) + 1, freshness[0]["freshness_seconds"]
                )

    def test_fact_excludes_a_rejected_key_and_preserves_steward_upload(self):
        with trino_connection() as conn:
            rejected = query_rows(
                conn,
                """
                SELECT DISTINCT s.source_name, st.source_system_identifier
                FROM pre_ods.customer_support_stage st
                JOIN ds.sources s ON s.source_id = st.source_id
                WHERE st.source_system_identifier IS NOT NULL AND EXISTS (
                    SELECT 1 FROM aud_mirror.aud_business_rules_results r
                    WHERE r.business_rule_key = CAST(st.row_id AS VARCHAR)
                      AND r.target_schema_name = 'pre_ods'
                      AND r.target_table_name = 'customer_support_stage'
                      AND r.status = 'REJECT' AND r.active_flag = 'Y' AND r.end_date IS NULL
                ) AND NOT EXISTS (
                    SELECT 1 FROM ods.interactions o
                    WHERE o.source_id = st.source_id
                      AND o.source_system_identifier = st.source_system_identifier
                )
            """,
            )
            self.assertTrue(rejected, "generate a rejected interaction with a new key")
            actual_keys = query_rows(
                conn,
                "SELECT source_name, source_system_identifier FROM vw.customer_support_fact_view",
            )
            self.assertFalse(any(row in actual_keys for row in rejected))
            corrections = query_rows(
                conn,
                """
                SELECT s.source_name, o.source_system_identifier, o.upload_id,
                    u.account AS steward, u.file_name AS upload_file_name
                FROM ods.interactions o
                JOIN ds.sources s ON s.source_id = o.source_id
                JOIN aud_mirror.aud_uploads u ON u.upload_id = o.upload_id
                WHERE EXISTS (
                    SELECT 1 FROM dm.customer_support_fact f
                    WHERE f.source_id = o.source_id
                      AND f.source_system_identifier = o.source_system_identifier
                      AND f.active_flag = 'Y' AND f.delete_flag = 'N'
                )
                ORDER BY s.source_name, o.source_system_identifier
            """,
            )
            self.assertTrue(
                corrections, "publish a steward correction through ODS and SI_DM"
            )
            self.assertEqual(
                corrections,
                query_rows(
                    conn,
                    """
                    SELECT source_name, source_system_identifier, upload_id, steward, upload_file_name
                    FROM vw.customer_support_fact_view WHERE upload_id IS NOT NULL
                    ORDER BY source_name, source_system_identifier
                """,
                ),
            )


if __name__ == "__main__":
    unittest.main()
