"""Small independent fixtures exercise the actual DM SELECT's half-open joins."""

import importlib.util
import unittest
from datetime import UTC, datetime
from pathlib import Path

SQL = Path(__file__).parents[1] / "project/sql_scripts/ods_to_dm.sql"
LOW = datetime(2026, 1, 2, tzinfo=UTC)
HIGH = datetime(2026, 1, 3, tzinfo=UTC)
OLD = datetime(2026, 1, 1, tzinfo=UTC)
MID = datetime(2026, 1, 2, 12, tzinfo=UTC)
LATE = datetime(2026, 1, 3, 12, tzinfo=UTC)


@unittest.skipUnless(
    importlib.util.find_spec("duckdb"), "install DuckDB for local SQL fixtures"
)
class DMWindows(unittest.TestCase):
    def setUp(self):
        import duckdb

        self.db = duckdb.connect()
        self.addCleanup(self.db.close)
        self.db.execute("SET TimeZone='UTC'")
        self.db.execute("CREATE SCHEMA ods")
        self.db.execute("""
            CREATE TABLE ods.interactions (
                source_id BIGINT, source_system_identifier VARCHAR, agent_id BIGINT,
                interaction_date TIMESTAMP, support_area_id BIGINT, interaction_status VARCHAR,
                interaction_type VARCHAR, customer_type_id BIGINT, handle_time BIGINT,
                work_time BIGINT, first_contact_resolution BOOLEAN, query_status VARCHAR,
                solution_type VARCHAR, customer_rating BIGINT, source_record_id BIGINT,
                source_pipeline_run_id BIGINT, source_task_run_id BIGINT, update_date TIMESTAMPTZ
            )
        """)
        self.db.execute("""
            CREATE TABLE ods.agents (
                agent_id BIGINT, first_name VARCHAR, middle_name VARCHAR,
                last_name VARCHAR, update_date TIMESTAMPTZ
            )
        """)
        self.db.execute("""
            CREATE TABLE ods.support_areas (
                support_area_id BIGINT, support_area_name VARCHAR, update_date TIMESTAMPTZ
            )
        """)
        self.db.execute("""
            CREATE TABLE ods.customer_types (
                customer_type_id BIGINT, customer_type_name VARCHAR, update_date TIMESTAMPTZ
            )
        """)
        self.inputs = {}

    def add(self, key, *, interaction=MID, agent=OLD, area=OLD, customer=OLD):
        identity = len(self.inputs) + 1
        row = {
            "source_id": 1,
            "source_system_identifier": key,
            "agent_id": identity,
            "interaction_date": datetime(2025, 12, 1),
            "support_area_id": identity,
            "interaction_status": "COMPLETED",
            "interaction_type": "CALL",
            "customer_type_id": identity,
            "handle_time": 90,
            "work_time": 10,
            "first_contact_resolution": True,
            "query_status": "RESOLVED",
            "solution_type": "SELF-HELP",
            "customer_rating": 4,
            "source_record_id": identity,
            "source_pipeline_run_id": 17,
            "source_task_run_id": 101,
        }
        self.inputs[key] = row
        self.db.execute(
            "INSERT INTO ods.interactions VALUES (" + ",".join(["?"] * 18) + ")",
            [*row.values(), interaction],
        )
        self.db.execute(
            "INSERT INTO ods.agents VALUES (?, 'Ada', NULL, 'Example', ?)",
            [identity, agent],
        )
        self.db.execute(
            "INSERT INTO ods.support_areas VALUES (?, 'Orders', ?)", [identity, area]
        )
        self.db.execute(
            "INSERT INTO ods.customer_types VALUES (?, 'New', ?)", [identity, customer]
        )

    def query(self, low=LOW, high=HIGH):
        sql = SQL.read_text().replace(
            "$$watermark_max", f"TIMESTAMPTZ '{high.isoformat()}'"
        )
        sql = sql.replace("$$watermark", f"TIMESTAMPTZ '{low.isoformat()}'")
        cursor = self.db.execute(sql)
        columns = [column[0] for column in cursor.description]
        return sorted(
            [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()],
            key=lambda row: row["source_system_identifier"],
        )

    def desired(self, key, changed_at):
        return self.inputs[key] | {
            "agent_name": "Ada Example",
            "support_area_name": "Orders",
            "customer_type_name": "New",
            "ods_changed_at": changed_at,
        }

    def test_half_open_boundaries_and_empty_window(self):
        self.add("lower", interaction=LOW)
        self.add("upper", interaction=HIGH)
        self.add("old", interaction=OLD)
        self.assertEqual(self.query(), [self.desired("lower", LOW)])
        self.assertEqual(self.query(HIGH, LATE), [self.desired("upper", HIGH)])
        self.assertEqual(self.query(LATE, datetime(2026, 1, 4, tzinfo=UTC)), [])

    def test_each_lookup_change_expands_unchanged_interactions(self):
        self.add("agent", interaction=OLD, agent=MID)
        self.add("area", interaction=OLD, area=MID)
        self.add("customer", interaction=OLD, customer=MID)
        self.assertEqual(
            self.query(),
            [self.desired(key, MID) for key in ("agent", "area", "customer")],
        )

    def test_join_never_publishes_values_at_or_after_high(self):
        self.add("agent", agent=HIGH)
        self.add("area", area=LATE)
        self.add("customer", customer=LATE)
        self.add("interaction", interaction=LATE, agent=MID)
        self.assertEqual(self.query(), [])
        self.assertEqual(
            self.query(HIGH, datetime(2026, 1, 4, tzinfo=UTC)),
            [
                self.desired(key, HIGH if key == "agent" else LATE)
                for key in ("agent", "area", "customer", "interaction")
            ],
        )


class DMMetadata(unittest.TestCase):
    def test_declared_window_contract_and_schedule(self):
        import csv
        import json

        root = SQL.parents[1] / "config"
        with (root / "task_parameters.csv").open() as stream:
            params = {
                row["PARAMETER_NAME"]: row["PARAMETER_VALUE"]
                for row in csv.DictReader(stream)
                if row["PIPELINE_CODE"] == "SI_DM" and row["TASK_CODE"] == "ods_to_dm"
            }
        self.assertEqual(params["SQL_ACTION"], "SCD2_MERGE")
        self.assertEqual(params["WATERMARK_TYPE"], "TIMESTAMP")
        self.assertEqual(params["WATERMARK_COLUMN"], "ods_changed_at")
        self.assertNotIn("ods_changed_at", params["MERGE_COMPARE_COLUMNS"].split("|"))
        self.assertEqual(
            set(json.loads(params["WATERMARK_SOURCE_PIPELINES"])),
            {"SI_CLIENT_ALPHA", "SI_CLIENT_BETA", "SI_CLIENT_GAMMA"},
        )
        with (root / "pipelines.csv").open() as stream:
            dm = next(
                row for row in csv.DictReader(stream) if row["PIPELINE_CODE"] == "SI_DM"
            )
        self.assertEqual(dm["RUN_SCHEDULE"], "0 */6 * * *")
        self.assertEqual(dm["SCHEDULE_TIMEZONE"], "UTC")
        with (root / "pipeline_dependencies.csv").open() as stream:
            self.assertFalse(
                any(row["PIPELINE_CODE"] == "SI_DM" for row in csv.DictReader(stream))
            )
