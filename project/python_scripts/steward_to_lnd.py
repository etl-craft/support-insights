"""Stream accepted steward files into the task's typed, upload-attributed landing batch."""

from etl_craft.scripting import ScriptResult, UploadReader


def run(task):
    task.logger.info("reading %d accepted steward upload(s)", len(task.uploads))

    def rows():
        for upload in task.uploads:
            task.logger.info("upload %s", upload.upload_id)
            stream = UploadReader(upload, "CSV").rows(
                schema={
                    "LOCKED": bool,
                    "is_active": bool,
                    "first_contact_resolution": bool,
                }
            )
            header = next(stream)
            for values in stream:
                row = {
                    name.lower(): value
                    for name, value in zip(header, values, strict=True)
                }
                row.setdefault("locked", None)
                yield row | {"upload_id": upload.upload_id}

    count = task.replace_landing(rows())
    task.logger.info("landed %d row(s)", count)
    return ScriptResult(count)
