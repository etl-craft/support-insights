#!/bin/sh
set -eu
commit=8a7e67b917d14a413c27d99dfd2ebd4b19ec61c1
mkdir -p .state
image_context=$(mktemp -d "$(pwd)/.state/image.XXXXXX")
mkdir -p "$image_context/wheels"
if [ ! -d .state/etl-craft/.git ]; then
  git clone https://github.com/etl-craft/etl-craft.git .state/etl-craft
fi
git -C .state/etl-craft fetch origin main
git -C .state/etl-craft checkout --detach "$commit"
docker build --target base --label "org.opencontainers.image.revision=$commit" -t "support-insights-etl:$commit" .state/etl-craft
docker build --target ui --label "org.opencontainers.image.revision=$commit" -t "support-insights-etl:$commit-ui" .state/etl-craft
uv build --directory .state/etl-craft --wheel --out-dir "$image_context/wheels"
cp .state/etl-craft/docs/deploying/Dockerfile "$image_context/Dockerfile"
cp -R project "$image_context/project"
set -- "$image_context"/wheels/etl_craft-*-py3-none-any.whl
[ "$#" -eq 1 ] || { echo 'Expected one locally built package wheel; inspect the pinned package build' >&2; exit 1; }
wheel=${1##*/}
docker build --build-arg "BASE_IMAGE=support-insights-etl:$commit-ui" --build-arg "ETL_CRAFT_REQUIREMENT=etl-craft[trino,aws] @ file:///tmp/wheels/$wheel" --label "org.opencontainers.image.revision=$commit" -t "support-insights-project:$commit" "$image_context"
docker build -f infra/ingestion.Dockerfile --build-arg "PROJECT_IMAGE=support-insights-project:$commit" -t "support-insights-ingestion:$commit" .
docker build -f generators/Dockerfile -t "support-insights-generator:$commit" .
k3d image import --mode direct -c support-insights "support-insights-etl:$commit" "support-insights-etl:$commit-ui" "support-insights-project:$commit" "support-insights-ingestion:$commit" "support-insights-generator:$commit"

for image in "support-insights-project:$commit" "support-insights-ingestion:$commit" "support-insights-generator:$commit"; do
  docker exec k3d-support-insights-server-0 crictl inspecti "docker.io/library/$image" > /dev/null
done
