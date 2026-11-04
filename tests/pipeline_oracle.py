"""Expected business rows computed only from generator records and seed files."""

import csv
import math
from datetime import datetime
from pathlib import Path

SEEDS = Path(__file__).parents[1] / "project/seeds/warehouse/ds"


def lookup(table, source, key, source_id):
    with (SEEDS / table / "data.csv").open() as stream:
        return {
            r[source]: int(r[key])
            for r in csv.DictReader(stream, delimiter="|")
            if int(r["source_id"]) == source_id
        }


def seconds(value):
    hours, minutes, seconds = (int(x) for x in value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def expected(client, data):
    """Port the source's business meanings independently of all project SQL and scripts."""
    a, b = client == "alpha", client == "beta"
    source_id = {"alpha": 1, "beta": 2, "gamma": 3}[client]
    fields = {
        "alpha": (
            "INTERACTION_ID",
            "AGENT_PSEUDO_NAME",
            "SUPPORT_CATEGORY",
            "TYPE_OF_CUSTOMER",
            "CONTACT_DATE",
            "%d/%m/%Y %H:%M:%S",
        ),
        "beta": (
            "SUPPORT_IDENTIFIER",
            "AGENT_CODE",
            "CONTACT_REGARDING",
            "CUSTOMER_TYPE",
            "DATE_OF_INTERACTION",
            "%Y%m%d%H%M%S",
        ),
        "gamma": (
            "TICKET_IDENTIFIER",
            "AGENT_NAME",
            "SUPPORT_CATEGORY",
            "TYPE_OF_CUSTOMER",
            "DATE_OF_CALL",
            "%m%d%Y%H%M%S",
        ),
    }[client]
    identity, agent, area, customer, day, date_format = fields
    status = data[
        "INTERACTION_STATUS" if a else "STATUS_OF_INTERACTION" if b else "CALL_STATUS"
    ]
    if b:
        status = {
            "INTERACTION COMPLETED": "COMPLETED",
            "CUSTOMER DROPPED": "DROPPED",
        }.get(status, status)
    handle = (
        int(data["INTERACTION_DURATION" if a else "DURATION"])
        if not b
        else seconds(data["CONTACT_DURATION"])
    )
    work = (
        int(data["TOTAL_TIME"]) - handle
        if a
        else seconds(data["AFTER_CONTACT_WORK_TIME"])
        if b
        else int(data["WORK_TIME"])
    )
    rating = (
        math.ceil(int(data["RATING"]) / 2)
        if a
        else int(data["SUPPORT_RATING"])
        if b
        else ["WORST", "BAD", "NEUTRAL", "GOOD", "BEST"].index(data["RATING"]) + 1
    )
    return {
        "source_id": {"alpha": 1, "beta": 2, "gamma": 3}[client],
        "source_system_identifier": str(data[identity]),
        "agent_id": lookup("agents", "pseudo_code", "agent_id", source_id).get(
            data[agent]
        ),
        "interaction_date": datetime.strptime(data[day], date_format).isoformat(
            sep=" "
        ),
        "support_area_id": lookup(
            "support_areas", "support_area_name", "support_area_id", source_id
        ).get(data[area]),
        "customer_type_id": lookup(
            "customer_types", "customer_type_name", "customer_type_id", source_id
        ).get(data[customer]),
        "interaction_status": status,
        "interaction_type": data[
            "INTERACTION_TYPE" if a else "TYPE_OF_INTERACTION" if b else "CALL_TYPE"
        ],
        "handle_time": handle,
        "work_time": work,
        "first_contact_resolution": data[
            "RESOLVED_IN_FIRST_CONTACT" if not b else "FIRST_CONTACT_SOLVE"
        ]
        == ("YES" if a else "TRUE" if b else "1"),
        "query_status": data[
            "STATUS_OF_CUSTOMER_INCIDENT"
            if a
            else "INCIDENT_STATUS"
            if b
            else "TICKET_STATUS"
        ],
        "solution_type": data[
            "SOLUTION_TYPE"
            if a
            else "TYPE_OF_RESOLUTION"
            if b
            else "RESOLUTION_CATEGORY"
        ],
        "customer_rating": rating,
    }


def eligible(row):
    """Incomplete values remain eligible; only the declared rejection policies exclude a row."""
    return (
        bool(row["source_system_identifier"].strip())
        and all(
            row[key] is None or row[key] >= 0 for key in ("handle_time", "work_time")
        )
        and (row["customer_rating"] is None or 1 <= row["customer_rating"] <= 5)
    )
