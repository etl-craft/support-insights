#!/bin/sh
# Replace the etl-craft package in the running demo with one built from a local checkout, without
# rebuilding the base images or the cluster: a thin layer re-installs the wheel on the pinned
# project image, the images are re-imported under their pinned tags, and the deployments that run
# them restart. The Engine DB and every token are kept.
#   sh infra/bootstrap/update.sh [PACKAGE_CHECKOUT]      (default: $ETL_CRAFT_SRC, else ../etl-craft)
# This is a development loop. The images keep their pinned tag but no longer match that commit;
# build.sh with a new pin (or the S8.E candidate images) is the way to release.
set -eu
src=${1:-${ETL_CRAFT_SRC:-../etl-craft}}
[ -f "$src/pyproject.toml" ] || { echo "$src: no pyproject.toml; pass the etl-craft checkout" >&2; exit 1; }
commit=$(sed -n 's/^commit=//p' infra/bootstrap/build.sh)
[ -n "$commit" ] || { echo 'infra/bootstrap/build.sh: no commit= line; expected the pinned package commit' >&2; exit 1; }
docker image inspect "support-insights-project:$commit" > /dev/null 2>&1 ||
  { echo "support-insights-project:$commit: not built; run infra/bootstrap/build.sh once first" >&2; exit 1; }
mkdir -p .state
work=$(mktemp -d "$(pwd)/.state/update.XXXXXX")
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/wheels"
uv build --directory "$src" --wheel --out-dir "$work/wheels"
set -- "$work"/wheels/etl_craft-*-py3-none-any.whl
[ "$#" -eq 1 ] || { echo "$work/wheels: expected exactly one built wheel" >&2; exit 1; }
wheel=${1##*/}
revision=$(git -C "$src" rev-parse HEAD 2> /dev/null || echo unknown)
cat > "$work/Dockerfile" <<DOCKER
ARG BASE_IMAGE
FROM ghcr.io/astral-sh/uv:0.12.17@sha256:10787c682e4184e4f290de1171fd4703dc63de99221f10fe1c99002ce7fa9acc AS uv
FROM \${BASE_IMAGE}
USER root
COPY --from=uv /uv /tmp/uv
COPY wheels/ /tmp/wheels/
RUN /tmp/uv pip install --python /opt/etl-craft/bin/python --no-cache --compile-bytecode --link-mode=copy \\
      --reinstall-package etl-craft "etl-craft[trino,aws] @ file:///tmp/wheels/$wheel" \\
    && rm -rf /tmp/uv /tmp/wheels
USER 10001
DOCKER
base="support-insights-project:$commit"
docker tag "$base" "support-insights-project:before-update" # the layer builds on the image being replaced
docker build --build-arg "BASE_IMAGE=support-insights-project:before-update" \
  --label "org.opencontainers.image.revision=$revision" --label "dev.etl-craft.update=true" \
  -t "$base" "$work"
docker build -f infra/ingestion.Dockerfile --build-arg "PROJECT_IMAGE=$base" \
  -t "support-insights-ingestion:$commit" .
docker rmi "support-insights-project:before-update" > /dev/null
k3d image import --mode direct -c support-insights "$base" "support-insights-ingestion:$commit"
kubectl get deployment -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.template.spec.containers[*].image}{"\n"}{end}' |
  awk '/support-insights-(project|ingestion)/ {print "deployment/" $1}' |
  while read -r deployment; do
    kubectl rollout restart "$deployment"
  done
for deployment in $(kubectl get deployment -o name); do
  kubectl rollout status "$deployment" --timeout=300s
done
echo "etl-craft from $src ($revision) is running; craft-admin, if it exists, still runs the old package: delete and re-apply it"
