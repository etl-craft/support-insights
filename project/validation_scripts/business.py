"""Refuse malformed reference or business corrections before loading."""

from etl_craft.scripting import PermanentError


def validate(task):
    rows = task.reader.rows(schema={"LOCKED": bool})
    header = next(rows, None)
    expected = [
        "source_id",
        "source_system_identifier",
        "agent_id",
        "interaction_date",
        "support_area_id",
        "interaction_status",
        "interaction_type",
        "customer_type_id",
        "handle_time",
        "work_time",
        "first_contact_resolution",
        "query_status",
        "solution_type",
        "customer_rating",
        "LOCKED",
    ]
    if header != tuple(expected):
        raise PermanentError(
            f"{task.upload.file_name}: header={header!r}; expected {expected!r}; upload a corrected pipe-delimited file"
        )
    seen = set()
    key_indexes = (0, 1) if expected[0] == "source_id" else (0,)
    for number, row in enumerate(rows, 2):
        key = tuple(row[i] for i in key_indexes) if len(row) == len(header) else ()
        if (
            len(row) != len(header)
            or any(value is None or value == "" for value in key)
            or key in seen
        ):
            raise PermanentError(
                f"{task.upload.file_name}: row {number} value={row!r}; expected one nonempty unique key and every declared column; upload a corrected file"
            )
        seen.add(key)
