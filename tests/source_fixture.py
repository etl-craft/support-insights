"""Deliver small captured generator inputs; pipeline execution stays in etl-craft."""

import csv
import gzip
import io
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from xml.etree import ElementTree

import boto3
from confluent_kafka import Producer
from pymongo import MongoClient


def deliver(inputs):
    for client in ("alpha", "beta", "gamma"):
        if not 1 <= len(inputs[client]) <= 4:
            raise SystemExit(f"{client}: expected one to four captured fixture records")
    with MongoClient(
        host="mongodb",
        username=os.environ["MONGO_USER"],
        password=os.environ["MONGO_PASSWORD"],
        authSource="admin",
    ) as mongo:
        collection = mongo["support_insights"]["support"]
        last = collection.find_one(sort=[("serial_number", -1)])
        serial = last["serial_number"] if last else 0
        for number, record in enumerate(inputs["alpha"], 1):
            collection.insert_one(
                record
                | {
                    "serial_number": serial + number,
                    "record_id": int(record["INTERACTION_ID"]),
                    "created_at": datetime.now(UTC),
                }
            )
    producer = Producer({"bootstrap.servers": "kafka:9092"})
    for record in inputs["beta"]:
        root = ElementTree.Element("RECORD")
        for key, value in record.items():
            ElementTree.SubElement(root, key).text = (
                None if value is None else str(value)
            )
        producer.produce("client-beta", ElementTree.tostring(root), partition=0)
    if producer.flush(30):
        raise SystemExit(
            "Beta fixture delivery did not finish; restore Kafka before retrying"
        )
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=list(inputs["gamma"][0]), delimiter="|")
    writer.writeheader()
    writer.writerows(inputs["gamma"])
    payload = gzip.compress(text.getvalue().encode())
    key = f"s8b-oracle-{uuid.uuid4().hex}.csv.gz"
    client = boto3.client(
        "s3",
        endpoint_url="http://minio-gamma:9000",
        region_name="us-east-1",
        aws_access_key_id=os.environ["MINIO_USER"],
        aws_secret_access_key=os.environ["MINIO_PASSWORD"],
    )
    response = client.put_object(Bucket="gamma", Key=key, Body=payload)
    return inputs | {
        "delivery": {"object_key": key, "etag": response["ETag"].strip('"')}
    }


if __name__ == "__main__":
    print(json.dumps(deliver(json.load(sys.stdin))))
