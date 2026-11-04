"""Two bounded readers retain exact per-partition positions through fan-out retries."""

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from confluent_kafka import Consumer, TopicPartition
from etl_craft.scripting import Offset, PermanentError, ScriptResult, TransientError
from source_rows import READER_BYTES, bounded, raw

TOPIC = "client-beta"


def consumer(task):
    return Consumer(
        {
            "bootstrap.servers": "kafka:9092",
            "group.id": f"si-{task.task_run_id}",
            "enable.auto.commit": False,
            "enable.partition.eof": True,
            "fetch.max.bytes": READER_BYTES // 2,
            "max.partition.fetch.bytes": READER_BYTES // 2,
            "queued.max.messages.kbytes": READER_BYTES // 2 // 1024,
        }
    )


def run(task):
    probe = consumer(task)
    try:
        metadata = probe.list_topics(TOPIC, timeout=30).topics[TOPIC]
        if metadata.error is not None:
            raise TransientError(
                f"{TOPIC}: {metadata.error}; restore broker/topic access and retry"
            )
        partitions = sorted(metadata.partitions)
        if not partitions:
            raise PermanentError(
                f"{TOPIC}: no partitions; create the declared four-partition topic before running"
            )
    finally:
        probe.close()
    if len(partitions) > 4:
        raise PermanentError(
            f"{TOPIC}: {len(partitions)} partitions exceeds max_items=4; deliberately revise the metadata and memory budget"
        )
    committed = dict(task.offset.value) if task.offset else {}

    def load(key):
        source = consumer(task)
        try:
            partition = int(key)
            low, high = source.get_watermark_offsets(
                TopicPartition(TOPIC, partition), timeout=30
            )
            start = committed.get(key, low)
            if start < low:
                raise PermanentError(
                    f"{TOPIC} partition {key}: committed position {start} is older than retained position {low}; reset deliberately with etl-craft mark --offset"
                )
            if start > high:
                raise PermanentError(
                    f"{TOPIC} partition {key}: committed position {start} exceeds end {high}; check for topic recreation and deliberately reset the offset"
                )
            position = start
            source.assign([TopicPartition(TOPIC, partition, start)])

            def rows():
                nonlocal position
                seen = 0
                while position < high and seen < 1000:
                    message = source.poll(30)
                    if message is None:
                        raise TransientError(
                            f"{TOPIC} partition {key}: no record at position {position} before high {high}; check broker availability and retry"
                        )
                    if message.error():
                        raise TransientError(
                            f"{TOPIC} partition {key}: {message.error()}; restore broker access and retry"
                        )
                    value = bounded(
                        message.value(),
                        f"{TOPIC} partition {key} offset {message.offset()}",
                    )
                    value = value.decode("utf-8")
                    if "<!DOCTYPE" in value.upper() or "<!ENTITY" in value.upper():
                        raise PermanentError(
                            f"{TOPIC} partition {key}: XML declarations are forbidden; send a plain RECORD"
                        )
                    root = ET.fromstring(value)
                    data = {node.tag: node.text for node in root}
                    row = raw("beta", data)
                    position = message.offset() + 1
                    seen += 1
                    yield row | {
                        "source_system_identifier": row["support_identifier"],
                        "source_timestamp": datetime.fromtimestamp(
                            message.timestamp()[1] / 1000, UTC
                        ),
                        "source_partition": partition,
                        "source_offset": message.offset(),
                    }

            count = task.replace_landing(rows(), item_key=key)
            return ScriptResult(count, Offset.partitions({key: position}))
        finally:
            source.close()

    return task.fan_out((str(p) for p in partitions), load, max_parallel=2, max_items=4)
