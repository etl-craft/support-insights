"""Each upload contract refuses bad values before landing writes can begin."""

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "project/validation_scripts"))


@unittest.skipUnless(
    importlib.util.find_spec("etl_craft"),
    "run with the package development environment",
)
class StewardValidation(unittest.TestCase):
    def validator(self, name):
        spec = importlib.util.spec_from_file_location(
            "check_" + name, ROOT / "project/validation_scripts" / (name + ".py")
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.validate

    def task(self, header, row):
        return SimpleNamespace(
            upload=SimpleNamespace(file_name="correction.csv"),
            reader=SimpleNamespace(rows=lambda **kw: iter([tuple(header), tuple(row)])),
        )

    def test_bad_reference_id_is_refused_during_file_validation(self):
        from etl_craft.scripting import PermanentError

        header = [
            "agent_id",
            "first_name",
            "middle_name",
            "last_name",
            "pseudo_code",
            "source_id",
            "is_active",
            "LOCKED",
        ]
        with self.assertRaisesRegex(PermanentError, "agent_id.*not-an-id.*BIGINT"):
            self.validator("agents")(
                self.task(
                    header, ["not-an-id", "Ada", "", "Example", "ADA", "1", True, True]
                )
            )

    def test_optional_locked_header_is_accepted(self):
        self.validator("customer_types")(
            self.task(
                [
                    "customer_type_id",
                    "customer_type_name",
                    "source_id",
                    "description",
                    "is_active",
                ],
                ["1", "New", "1", "Known customer", True],
            )
        )

    def test_bad_timestamp_is_refused_before_landing(self):
        from etl_craft.scripting import PermanentError

        header = [
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
        row = [
            "1",
            "9000",
            "1",
            "not-a-date",
            "1",
            "COMPLETED",
            "CALL",
            "1",
            "-1",
            "10",
            True,
            "RESOLVED",
            "SELF-HELP",
            "4",
            True,
        ]
        with self.assertRaisesRegex(
            PermanentError, "interaction_date.*not-a-date.*TIMESTAMP"
        ):
            self.validator("business")(self.task(header, row))

    def test_loader_keeps_upload_id_and_supplies_optional_locked_without_actor_columns(
        self,
    ):
        import tempfile

        spec = importlib.util.spec_from_file_location(
            "load_steward", ROOT / "project/python_scripts/steward_to_lnd.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        received = []
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data.csv"
            path.write_text("agent_id|is_active\n1|false\n")
            upload = SimpleNamespace(
                path=path,
                upload_id=42,
                file_name="data.csv",
                size_bytes=path.stat().st_size,
            )
            task = SimpleNamespace(
                uploads=[upload],
                replace_landing=lambda rows: received.extend(rows) or len(received),
            )
            module.run(task)
        self.assertEqual(
            received,
            [{"agent_id": "1", "is_active": False, "locked": None, "upload_id": 42}],
        )

    def test_negative_duration_is_valid_typed_input_for_business_rules(self):
        import csv
        import tempfile

        from etl_craft.scripting import UploadReader

        with (ROOT / "tests/fixtures/steward/business-a.csv").open() as stream:
            reader = csv.DictReader(stream, delimiter="|")
            row = next(reader)
        row["handle_time"] = "-1"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rejectable.csv"
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(row), delimiter="|")
                writer.writeheader()
                writer.writerow(row)
            upload = SimpleNamespace(
                path=path,
                upload_id=42,
                file_name="rejectable.csv",
                size_bytes=path.stat().st_size,
            )
            self.validator("business")(
                SimpleNamespace(upload=upload, reader=UploadReader(upload, "CSV"))
            )
