"""Create the generator's SQLite state and source lookup values."""

import csv
import os
import sqlite3
from pathlib import Path


def initialize():
    with sqlite3.connect(os.environ["SQLITE_DB_FILE"]) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sources(source_id INTEGER PRIMARY KEY, source_name TEXT, is_active INTEGER);
        CREATE TABLE IF NOT EXISTS daily_budget(day TEXT, client TEXT, rows INTEGER, PRIMARY KEY(day,client));
        CREATE TABLE IF NOT EXISTS checkpoints(script_name TEXT PRIMARY KEY, script_status TEXT,
            processing_count INTEGER, new_records INTEGER, update_records INTEGER, null_records INTEGER,
            max_serial_number INTEGER, max_record_id INTEGER, change_timestamp TEXT);
        """)
        for table, column, source_column in [
            ("agents", "pseudo_code", "pseudo_code"),
            ("support_areas", "support_area_name", "support_area_name"),
            ("customer_types", "customer_type_name", "customer_type_name"),
        ]:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {table}(source_id INTEGER, {column} TEXT, is_active INTEGER)"
            )
            path = Path("/app/project/seeds/warehouse/ds") / table / "data.csv"
            with path.open() as stream:
                rows = list(csv.DictReader(stream, delimiter="|"))
            conn.execute(f"DELETE FROM {table}")
            conn.executemany(
                f"INSERT INTO {table} VALUES (?, ?, ?)",
                [
                    (
                        int(row["source_id"]),
                        row[source_column],
                        int(row["is_active"].lower() == "true"),
                    )
                    for row in rows
                ],
            )
        conn.executemany(
            "INSERT OR IGNORE INTO sources VALUES (?, ?, 1)",
            enumerate(["CLIENT_ALPHA", "CLIENT_BETA", "CLIENT_GAMMA"], 1),
        )


if __name__ == "__main__":
    initialize()
