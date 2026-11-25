"""The configuration CI keeps its boundaries: no secrets on pull requests, one pinned package."""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def text(name):
    return (WORKFLOWS / name).read_text()


def triggers(name):
    return re.search(r"(?m)^on:[^\n]*\n(?:[ \t]+[^\n]*\n)*", text(name)).group(0)


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
        self.assertNotIn("pull_request", triggers("deploy.yml"))
        self.assertIn("branches: [main]", triggers("deploy.yml"))
        self.assertIn('"project/**"', triggers("deploy.yml"))
        self.assertIn("runs-on: [self-hosted, support-insights]", deploy)
        self.assertIn("environment: production", deploy)

    def test_deploy_uses_only_the_developer_secret(self):
        deploy = text("deploy.yml")
        used = set(re.findall(r"secrets\.([A-Z0-9_]+)", deploy, re.IGNORECASE))
        self.assertEqual(used, {"ETL_CRAFT_DEVELOPER_TOKEN"})
        self.assertEqual(len(re.findall(r"\bsecrets\b", deploy, re.IGNORECASE)), 1)

    def test_no_self_hosted_workflow_runs_on_pull_requests(self):
        for workflow in sorted(WORKFLOWS.iterdir()):
            if workflow.suffix in {".yml", ".yaml"} and "self-hosted" in workflow.read_text():
                self.assertNotIn("pull_request", triggers(workflow.name), workflow.name)

    def test_local_validation_plans_deploys_and_validates_in_order(self):
        script = (ROOT / "ci" / "validate.sh").read_text()
        commands = ["alert-channel set", "deploy --plan\n", "deploy\n", "validate\n"]
        positions = [script.index(command) for command in commands]
        self.assertEqual(positions, sorted(positions))

    def test_deploy_runs_its_steps_in_order(self):
        deploy = text("deploy.yml")
        verbs = [
            "deploy --plan --project-dir project",
            "deploy --project-dir project",
            "validate",
            "lineage --refresh",
            "generate-docs --with-warehouse",
            "run --pipeline-code SI_REFERENCE",
        ]
        positions = [deploy.index(f"$cli {verb}") for verb in verbs]
        self.assertEqual(positions, sorted(positions))

    def test_removed_package_interfaces_are_absent(self):
        forbidden = ("EMAIL" + "_ALERT", "config" + " apply", "bundle" + " publish", "seed" + " apply")
        paths = subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT
        ).decode().split("\0")
        matches = []
        for path in sorted(set(paths) - {"", "CHANGELOG.md"}):
            file = ROOT / path
            if file.is_file():
                contents = file.read_bytes().lower()
                matches.extend((path, term) for term in forbidden if term.lower().encode() in contents)
        self.assertEqual(matches, [])

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
