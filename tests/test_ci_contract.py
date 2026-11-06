"""The configuration CI keeps its boundaries: no secrets on pull requests, one pinned package."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def text(name):
    return (WORKFLOWS / name).read_text()


def triggers(name):
    return re.search(r"(?m)^on:\n((?:  .*\n)+)", text(name)).group(0)


class ConfigurationCi(unittest.TestCase):
    def test_validate_runs_on_pull_requests_without_any_secret(self):
        validate = text("validate.yml")
        self.assertIn("pull_request:", validate)
        self.assertNotIn("secrets.", validate)
        self.assertNotIn("self-hosted", validate)
        self.assertNotIn("environment:", validate)
        self.assertNotIn("pull_request_target", triggers("validate.yml"))

    def test_deploy_never_runs_on_pull_requests_and_needs_a_reviewed_environment(self):
        deploy = text("deploy.yml")
        self.assertEqual(
            triggers("deploy.yml"),
            'on:\n  push:\n    branches: [main]\n    paths:\n      - "project/**"\n',
        )
        self.assertIn("runs-on: [self-hosted, support-insights]", deploy)
        self.assertIn("environment: production", deploy)

    def test_deploy_holds_one_developer_token_and_no_engine_or_store_credential(self):
        used = set(re.findall(r"secrets\.([A-Z_]+)", text("deploy.yml")))
        self.assertEqual(used, {"ETL_CRAFT_DEVELOPER_TOKEN"})

    def test_deploy_runs_the_five_steps_in_order(self):
        deploy = text("deploy.yml")
        verbs = [
            "bundle publish",
            "config apply --bundle latest",
            "validate",
            "seed apply",
            "run --pipeline-code SI_REFERENCE",
        ]
        positions = [deploy.index(f"$cli {verb}") for verb in verbs]
        self.assertEqual(positions, sorted(positions))

    def test_every_action_is_pinned_to_a_commit(self):
        for name in ("validate.yml", "deploy.yml"):
            for use in re.findall(r"uses: (\S+)", text(name)):
                self.assertRegex(use, r"@[0-9a-f]{40}$", f"{name}: {use}")

    def test_the_package_is_pinned_to_one_commit_for_both_workflows(self):
        pin = (ROOT / "ci" / "PACKAGE_COMMIT").read_text().strip()
        self.assertRegex(pin, r"^[0-9a-f]{40}$")
        for name in ("validate.sh", "install.sh"):
            self.assertNotIn(pin, (ROOT / "ci" / name).read_text())  # one source, never copied

    def test_the_local_warehouse_creates_every_schema_the_deployment_does(self):
        schemas = lambda path: set(re.findall(r"CREATE SCHEMA IF NOT EXISTS (?:warehouse\.)?(\w+)", path.read_text()))
        self.assertEqual(
            schemas(ROOT / "ci" / "warehouse.sql"), schemas(ROOT / "infra" / "bootstrap" / "warehouse.sql")
        )

    def test_the_ci_connector_reaches_no_remote_system(self):
        connector = (ROOT / "ci" / "craft-connector.yml").read_text()
        self.assertIn("jdbc:duckdb:", connector)
        self.assertIn("jdbc:sqlite:", connector)
        self.assertNotRegex(connector, r"(?i)(trino|s3://|minio|postgres|\bSecret:)")


if __name__ == "__main__":
    unittest.main()
