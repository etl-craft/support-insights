"""Source field contracts and bounded raw-record decoding."""

from etl_craft.scripting import PermanentError

READER_BYTES = 16 * 1024 * 1024
FIELDS = {
    "alpha": [
        "interaction_id",
        "support_category",
        "agent_pseudo_name",
        "contact_date",
        "interaction_status",
        "interaction_type",
        "type_of_customer",
        "interaction_duration",
        "total_time",
        "status_of_customer_incident",
        "resolved_in_first_contact",
        "solution_type",
        "rating",
    ],
    "beta": [
        "support_identifier",
        "contact_regarding",
        "agent_code",
        "date_of_interaction",
        "status_of_interaction",
        "type_of_interaction",
        "customer_type",
        "contact_duration",
        "after_contact_work_time",
        "incident_status",
        "first_contact_solve",
        "type_of_resolution",
        "support_rating",
        "time_stamp",
    ],
    "gamma": [
        "ticket_identifier",
        "support_category",
        "agent_name",
        "date_of_call",
        "call_status",
        "call_type",
        "type_of_customer",
        "duration",
        "work_time",
        "ticket_status",
        "resolved_in_first_contact",
        "resolution_category",
        "rating",
    ],
}


def raw(client, data):
    """Retain source values; warehouse SELECTs own their business transformations."""
    return {
        field: None if data.get(field.upper()) is None else str(data[field.upper()])
        for field in FIELDS[client]
    }


def bounded(value, source):
    if len(value) > READER_BYTES:
        raise PermanentError(
            f"{source}: record has {len(value)} bytes, exceeds {READER_BYTES}; reduce the source record"
        )
    return value
