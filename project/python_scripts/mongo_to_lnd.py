"""Stream Alpha's monotonic deliveries into the declared landing batch."""

from etl_craft.scripting import Offset, ScriptResult
from pymongo import MongoClient
from source_rows import raw


def run(task):
    start = int(task.offset.value) if task.offset else 0
    last = start
    with MongoClient(
        host="mongodb",
        port=27017,
        username=task.secret("MONGO_USER"),
        password=task.secret("MONGO_PASSWORD"),
        authSource="admin",
        serverSelectionTimeoutMS=30000,
        tz_aware=True,
    ) as client:
        collection = client["support_insights"]["support"]
        cursor = (
            collection.find({"serial_number": {"$gt": start}})
            .sort("serial_number", 1)
            .limit(1000)
            .batch_size(1)
        )

        def rows():
            nonlocal last
            for document in cursor:
                last = document["serial_number"]
                row = raw("alpha", document)
                yield row | {
                    "source_system_identifier": row["interaction_id"],
                    "source_timestamp": document["created_at"],
                    "serial_number": last,
                }

        count = task.replace_landing(rows())
    return ScriptResult(count, Offset.number(last))
