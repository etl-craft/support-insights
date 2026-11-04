"""Authenticated MinIO signal delivery; retries use durable event receipts."""

import asyncio
import hmac
import json
import os
import sqlite3
from datetime import datetime
from urllib.parse import unquote_plus

import trino
from aiohttp import web


def deliver(records):
    with sqlite3.connect(os.environ["SQLITE_DB_FILE"], timeout=30) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS event_receipts(object_key TEXT, etag TEXT, PRIMARY KEY(object_key,etag))"
        )
        db.execute("BEGIN IMMEDIATE")
        connection = trino.dbapi.connect(
            host="trino",
            port=8080,
            user="gamma_signal",
            catalog="warehouse",
            schema="lnd",
        )
        try:
            for record in records:
                if not record["eventName"].startswith("s3:ObjectCreated:"):
                    continue
                obj = record["s3"]["object"]
                key = unquote_plus(obj["key"])
                bucket = record["s3"]["bucket"]["name"]
                if bucket != "gamma" or not key.endswith(".csv.gz"):
                    raise web.HTTPBadRequest(
                        text=f"Gamma event bucket={bucket!r}, object_key={key!r}; "
                        "expected gamma bucket and .csv.gz suffix; fix notification filter"
                    )
                etag = obj["eTag"]
                if not isinstance(etag, str) or not etag:
                    raise web.HTTPBadRequest(
                        text=f"Gamma object {key!r}: eTag={etag!r}; "
                        "expected a nonempty ETag string; fix notification payload"
                    )
                size = obj["size"]
                when = datetime.fromisoformat(
                    record["eventTime"].replace("Z", "+00:00")
                )
                if (
                    not isinstance(size, int)
                    or isinstance(size, bool)
                    or size < 0
                    or when.tzinfo is None
                ):
                    raise web.HTTPBadRequest(
                        text=f"Gamma object {key!r}: size={size!r}, "
                        f"eventTime={record['eventTime']!r}; expected nonnegative integer "
                        "size and zoned eventTime; fix notification payload"
                    )
                if db.execute(
                    "SELECT 1 FROM event_receipts WHERE object_key=? AND etag=?",
                    (key, etag),
                ).fetchone():
                    continue
                cursor = connection.cursor()
                # Read-free INSERT account: receipt is committed only after Trino acknowledges.
                cursor.execute(
                    "INSERT INTO gamma_object_events (event_key, object_key, etag, size, event_time) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [
                        json.dumps([key, etag], separators=(",", ":")),
                        key,
                        etag,
                        size,
                        when,
                    ],
                )
                cursor.fetchall()
                db.execute("INSERT INTO event_receipts VALUES (?, ?)", (key, etag))
            db.commit()
        finally:
            connection.close()


async def receive(request):
    if not hmac.compare_digest(
        request.headers.get("Authorization", ""),
        "Bearer " + os.environ["GAMMA_WEBHOOK_TOKEN"],
    ):
        raise web.HTTPUnauthorized(
            text="Expected configured MinIO webhook bearer token"
        )
    try:
        payload = await request.json()
        records = payload["Records"]
        await asyncio.to_thread(deliver, records)
    except (KeyError, TypeError, ValueError) as exc:
        raise web.HTTPBadRequest(
            text=f"Invalid MinIO event: {exc}; expected Records with key, eTag, size and eventTime; fix notification payload"
        ) from exc
    return web.json_response({"accepted": len(records)})
