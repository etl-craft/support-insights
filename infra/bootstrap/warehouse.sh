#!/bin/sh
set -eu
kubectl wait --for=condition=Available deployment/trino --timeout=300s
kubectl exec -i deploy/trino -- trino --server http://localhost:8080 --user bootstrap < infra/bootstrap/warehouse.sql
