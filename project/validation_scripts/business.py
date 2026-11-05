"""Validate the declared business correction file before loading."""

from datetime import datetime

from upload_contract import validate_rows


def validate(task):
    validate_rows(
        task,
        {
            "source_id": int,
            "source_system_identifier": str,
            "agent_id": int,
            "interaction_date": datetime,
            "support_area_id": int,
            "interaction_status": str,
            "interaction_type": str,
            "customer_type_id": int,
            "handle_time": int,
            "work_time": int,
            "first_contact_resolution": bool,
            "query_status": str,
            "solution_type": str,
            "customer_rating": int,
        },
        ("source_id", "source_system_identifier"),
    )
