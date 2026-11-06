#!/bin/sh
# Install the etl-craft command line at the commit in ci/PACKAGE_COMMIT into WORK/venv and print
# the wheel's name and SHA-256. EXTRAS (default none) adds extras, for example duckdb.
#   ETL_CRAFT_WHEEL   use this wheel instead of building the pinned commit
set -eu
work=$1
extras=${EXTRAS:-}
root=$(cd "$(dirname "$0")/.." && pwd)
commit=$(tr -d '[:space:]' < "$root/ci/PACKAGE_COMMIT")
mkdir -p "$work"
wheel=${ETL_CRAFT_WHEEL:-}
if [ -z "$wheel" ]; then
  [ -d "$work/package/.git" ] || git clone --quiet https://github.com/etl-craft/etl-craft.git "$work/package"
  git -C "$work/package" fetch --quiet origin "$commit"
  git -C "$work/package" checkout --quiet --detach "$commit"
  rm -rf "$work/dist"
  uv build --quiet --directory "$work/package" --wheel --out-dir "$work/dist"
  wheel=$(ls "$work"/dist/etl_craft-*-py3-none-any.whl)
fi
echo "etl-craft wheel $(basename "$wheel") sha256 $(sha256sum "$wheel" | cut -d' ' -f1) (package commit $commit)"
uv venv --quiet --clear "$work/venv"
requirement="etl-craft${extras:+[$extras]} @ file://$wheel"
VIRTUAL_ENV="$work/venv" uv pip install --quiet "$requirement"
