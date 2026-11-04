"""Stream accepted steward files into the task's typed, upload-attributed landing batch."""

from etl_craft.scripting import ScriptResult, UploadReader


def run(task):
    def rows():
        for upload in task.uploads:
            stream = UploadReader(upload, "CSV").rows(schema={"LOCKED": bool})
            header = next(stream)
            for values in stream:
                yield {
                    name.lower(): value
                    for name, value in zip(header, values, strict=True)
                } | {"upload_id": upload.upload_id}

    return ScriptResult(task.replace_landing(rows()))
