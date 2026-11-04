#!/bin/sh
set -eu
umask 077
mkdir -p .state
chmod 700 .state
if [ -e .state/host-token ] && [ ! -s .state/host-token ]; then
  echo '.state/host-token is empty; expected a saved host token; remove it and enroll again' >&2
  exit 1
fi
if [ ! -e .state/host-token ]; then
  token=$(kubectl exec craft-admin -- etl-craft token create --name demo-host --role admin)
  printf %s "$token" > .state/host-token
fi
for pool in ingestion warehouse; do
  if [ "$pool" = ingestion ]; then count=3; else count=9; fi
  for number in $(seq 1 "$count"); do
    suffix=$(printf '%02d' "$number")
    agent="agent-$pool-$suffix"
    file=".state/$agent-token"
    if [ -e "$file" ] && [ ! -s "$file" ]; then
      echo "$file is empty; expected a saved agent token; remove it and enroll again" >&2
      exit 1
    fi
    if [ ! -e "$file" ]; then
      token=$(kubectl exec craft-admin -- etl-craft token create --name "demo-$pool-$suffix" --role agent --pool "$pool")
      printf %s "$token" > "$file"
    fi
    kubectl create secret generic "etl-craft-$agent" --from-file="ETL_CRAFT_TOKEN=$file" --dry-run=client -o yaml | kubectl apply -f -
  done
done
sh infra/bootstrap/configure.sh
