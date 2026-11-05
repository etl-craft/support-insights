"""Validate the declared support_areas correction file before loading."""

from upload_contract import validate_rows


def validate(task):
    validate_rows(
        task,
        {
            "support_area_id": int,
            "support_area_name": str,
            "source_id": int,
            "description": str,
            "is_active": bool,
        },
        ("support_area_id",),
    )
