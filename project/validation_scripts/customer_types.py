"""Validate the declared customer_types correction file before loading."""

from upload_contract import validate_rows


def validate(task):
    validate_rows(
        task,
        {
            "customer_type_id": int,
            "customer_type_name": str,
            "source_id": int,
            "description": str,
            "is_active": bool,
        },
        ("customer_type_id",),
    )
