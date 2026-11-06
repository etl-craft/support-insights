#!/bin/sh
# Validate project/ the way a pull request does: no secrets, no cluster. It builds the wheel at
# the commit in ci/PACKAGE_COMMIT, migrates an empty Engine DB, bootstraps a local DuckDB
# warehouse, then runs `config plan`, `config apply`, `bundle publish` and `validate` on a
# scratch copy of project/.
#   SI_CI_WORK   keep the scratch folder here (default: a new temporary folder, removed on exit)
#   ETL_CRAFT_WHEEL   use this wheel instead of building the pinned commit
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
work=${SI_CI_WORK:-}
if [ -z "$work" ]; then
  work=$(mktemp -d)
  trap 'rm -rf "$work"' EXIT
fi
mkdir -p "$work"
EXTRAS=duckdb "$root/ci/install.sh" "$work"
PATH="$work/venv/bin:$PATH"

# A scratch copy: the project's own files, with this job's connector in place of the deployment's.
rm -rf "$work/project"
cp -R "$root/project" "$work/project"
rm -f "$work/project/logs"/* 2>/dev/null || true
sed "s#__BUNDLES__#$work/bundles#" "$root/ci/craft-connector.yml" > "$work/project/craft-connector.yml"
python3 - "$work/project" <<'PY'
import re, sys
folder = sys.argv[1]
text = open(f"{folder}/craft-connector.yml").read()
# The bootstrap commands check the email relay, which does not exist here; the project's own
# commands need the Email section because it has EMAIL_ALERT tasks.
open(f"{folder}/bootstrap.yml", "w").write(re.sub(r"  Email:\n(    .*\n)+", "", text))
PY
cd "$work/project"

# Declared secret names get placeholder values: validate checks that they exist, never their value.
for name in $(awk -F, '$3=="SECRETS" {print $4}' config/task_parameters.csv | tr '|' '\n' | sort -u); do
  export "$name=ci-placeholder"
done
export PRIVACY_HMAC=ci-placeholder
XDG_CONFIG_HOME="$work/xdg"; export XDG_CONFIG_HOME
password=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')

etl-craft --config bootstrap.yml init-db > /dev/null
printf '%s\n' "$password" | etl-craft --config bootstrap.yml setup --admin-name ci-admin --password-stdin > /dev/null
printf '%s\n' "$password" | etl-craft --config bootstrap.yml login --name ci-admin --password-stdin
etl-craft --config bootstrap.yml project add --project support_insights --name "Support Insights" \
  --environment-type CUSTOM --reason "ci validation" > /dev/null
for pool in $(awk -F, '$3=="POOL" {print $4}' config/task_parameters.csv | sort -u); do
  etl-craft --config bootstrap.yml pool add --name "$pool" --reason "ci validation" > /dev/null
done
python3 - "$root/ci/warehouse.sql" <<'PY'
import sys

import duckdb

connection = duckdb.connect("warehouse.duckdb")
connection.execute(open(sys.argv[1]).read())
connection.close()
PY

etl-craft --config craft-connector.yml config plan > /dev/null
etl-craft --config craft-connector.yml config apply
# validate reads the seed files from the published bundle, so publish before it.
etl-craft --config craft-connector.yml bundle publish
etl-craft --config craft-connector.yml validate
