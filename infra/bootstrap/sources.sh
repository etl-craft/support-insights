#!/bin/sh
set -eu
kubectl rollout status deploy/minio-lake --timeout=180s
kubectl rollout status deploy/minio-gamma --timeout=180s
kubectl exec deploy/minio-lake -- sh -ec '
  mc alias set lake http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
  for bucket in warehouse bundles logs; do mc mb --ignore-existing lake/$bucket; done
'
kubectl exec -i deploy/minio-gamma -- sh -ec '
  mc alias set gamma http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
  mc mb --ignore-existing gamma/gamma
  mc ilm import gamma/gamma
  events="$(mc event ls gamma/gamma)"
  case "$events" in
    *arn:minio:sqs::GAMMA:webhook*) ;;
    *)
    mc event add gamma/gamma arn:minio:sqs::GAMMA:webhook --event put --suffix .csv.gz
      ;;
  esac
' <<'JSON'
{"Rules":[{"ID":"gamma-expiry","Status":"Enabled","Filter":{"Prefix":""},"Expiration":{"Days":2}}]}
JSON
kubectl rollout status deploy/mongodb --timeout=180s
kubectl exec deploy/mongodb -- sh -ec 'mongosh --quiet --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --eval "$1"' -- 'db.getSiblingDB("support_insights").support.createIndex({created_at:1},{expireAfterSeconds:172800})'
kubectl rollout status deploy/kafka --timeout=180s
kubectl exec deploy/kafka -- /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic client-beta --partitions 4 --replication-factor 1 --config retention.ms=86400000 --config retention.bytes=268435456 --config segment.bytes=16777216
