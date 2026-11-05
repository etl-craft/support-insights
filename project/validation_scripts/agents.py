"""Validate the declared agents correction file before loading."""

from upload_contract import validate_rows


def validate(task):
    validate_rows(
        task,
        {
            "agent_id": int,
            "first_name": str,
            "middle_name": str,
            "last_name": str,
            "pseudo_code": str,
            "source_id": int,
            "is_active": bool,
        },
        ("agent_id",),
    )
