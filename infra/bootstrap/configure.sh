#!/bin/sh
set -eu
# Run after CNPG has initialized its generated application Secret.
kubectl wait --for=condition=Ready cluster/engine --timeout=300s
mkdir -p .state
chmod 700 .state
umask 077
kubectl get secret engine-app -o jsonpath='{.data.password}' | base64 -d > .state/engine-password
printf 'ENGINE_PASSWORD=%s\n' "$(cat .state/engine-password)" > .state/engine.env
printf 'ENGINE_JDBC_URL=jdbc:postgresql://engine-rw:5432/etl_craft\nLAKE_ACCESS_KEY=minioadmin\nLAKE_SECRET_KEY=local-demo-only\n' >> .state/engine.env
[ -f .state/privacy-hmac ] || openssl rand -hex 32 > .state/privacy-hmac
printf 'PRIVACY_HMAC=%s\n' "$(cat .state/privacy-hmac)" >> .state/engine.env
if [ -s .state/host-token ]; then
  printf 'ETL_CRAFT_TOKEN=%s\n' "$(cat .state/host-token)" >> .state/engine.env
fi
kubectl create secret generic etl-craft-engine --from-env-file=.state/engine.env --dry-run=client -o yaml | kubectl apply -f -
cp project/craft-connector.yml .state/engine.yml
# UI uses transaction pooling for ordinary work; LISTEN stays on the direct service.
sed 's/Jdbc_url: ENGINE_JDBC_URL/Jdbc_url: jdbc:postgresql:\/\/engine-ui:5432\/etl_craft/' project/craft-connector.yml > .state/ui.yml
cat > .state/agent.yml <<'EOF'
Secrets:
  Source_type: ENVIRONMENT
Orchestration:
  Project: support_insights
Deployment:
  Profile: CONTROLLER_AGENTS
Warehouse:
  Name: Trino
  Table_format: ICEBERG
  dev:
    Jdbc_url: jdbc:trino://trino:8080/warehouse/lnd
    Schema: lnd
    User: etl_craft
    Auth_mode: NONE
EOF
kubectl create configmap etl-craft-config --from-file=engine.yml=.state/engine.yml --from-file=ui.yml=.state/ui.yml --from-file=agent.yml=.state/agent.yml --from-literal=api-url=https://traefik.kube-system.svc --dry-run=client -o yaml | kubectl apply -f -
