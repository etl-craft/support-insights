"""Read only this run's recorded Gamma object identities, including their exact ETags."""

import csv
import gzip
import io
import json
from datetime import datetime

import boto3
from etl_craft.scripting import PermanentError, ScriptResult
from source_rows import READER_BYTES, raw


def run(task):
    csv.field_size_limit(READER_BYTES // 128)
    client = boto3.client(
        "s3",
        endpoint_url="http://minio-gamma:9000",
        region_name="us-east-1",
        aws_access_key_id=task.secret("MINIO_USER"),
        aws_secret_access_key=task.secret("MINIO_PASSWORD"),
    )

    def rows():
        for event_key, event in zip(task.event_keys, task.event_rows, strict=True):
            key, etag = json.loads(event_key)
            if (key, etag) != (event["object_key"], event["etag"]):
                raise PermanentError(
                    f"Gamma event {event_key!r}: payload identity mismatch; repair the notification"
                )
            response = client.get_object(Bucket="gamma", Key=key, IfMatch=etag)
            if response["ContentLength"] != event["size"]:
                response["Body"].close()
                raise PermanentError(
                    f"Gamma object {key!r}: size differs from recorded {event['size']}; restore the exact delivery"
                )
            with (
                response["Body"] as body,
                gzip.GzipFile(fileobj=body) as compressed,
                io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text,
            ):
                for number, data in enumerate(csv.DictReader(text, delimiter="|"), 1):
                    row = raw("gamma", data)
                    stamp = event["event_time"]
                    yield row | {
                        "source_system_identifier": row["ticket_identifier"],
                        "source_timestamp": datetime.fromisoformat(stamp)
                        if isinstance(stamp, str)
                        else stamp,
                        "source_object": key,
                        "source_etag": etag,
                        "source_row": number,
                    }

    return ScriptResult(task.replace_landing(rows()))
