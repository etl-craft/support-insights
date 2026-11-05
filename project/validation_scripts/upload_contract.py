"""Shared type and key checks for the four declared correction formats."""

from datetime import datetime

from etl_craft.scripting import PermanentError


def validate_rows(task, columns, keys):
    expected = tuple(columns)
    rows = task.reader.rows(
        schema={name: bool for name, kind in columns.items() if kind is bool}
        | {"LOCKED": bool}
    )
    header = next(rows, None)
    if header not in (expected, (*expected, "LOCKED")):
        raise PermanentError(
            f"{task.upload.file_name}: header={header!r}; expected {expected!r} with optional LOCKED; upload a corrected pipe-delimited file"
        )
    seen = set()
    for number, row in enumerate(rows, 2):
        if len(row) != len(header):
            raise PermanentError(
                f"{task.upload.file_name}: row {number} has {len(row)} cells; expected {len(header)}; upload every declared column"
            )
        values = {}
        for column, value in zip(header, row, strict=True):
            kind = columns.get(column, bool)
            label = {
                int: "BIGINT",
                bool: "BOOLEAN",
                str: "VARCHAR",
                datetime: "TIMESTAMP",
            }[kind]
            typed, valid = typed_value(value, kind)
            if not valid:
                raise PermanentError(
                    f"{task.upload.file_name}: row {number}, column {column}, value={value!r}; expected {label}; correct the typed value and upload again"
                )
            value = typed
            values[column] = value
        key = tuple(values[name] for name in keys)
        if (
            any(value is None or str(value).strip() == "" for value in key)
            or key in seen
        ):
            raise PermanentError(
                f"{task.upload.file_name}: row {number}, key={key!r}; expected a nonempty unique {keys}; correct the key and upload again"
            )
        seen.add(key)


def typed_value(value, kind):
    try:
        if kind is int:
            number = None if isinstance(value, (bool, float)) else int(value)
            return number, number is not None and -(2**63) <= number < 2**63
        if kind is datetime:
            return value, datetime.fromisoformat(str(value)).tzinfo is None
        if kind is bool:
            return value, value is None or isinstance(value, bool)
        return value, value is None or isinstance(value, str)
    except (ValueError, TypeError):
        return value, False
