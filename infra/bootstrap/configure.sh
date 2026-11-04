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
sed 's/Source_type: ENVIRONMENT/Source_type: FILE\n  Path: \/secrets\/provider.env/' project/craft-connector.yml > .state/engine.yml
# UI uses transaction pooling for ordinary work; LISTEN stays on the direct service.
sed 's/Jdbc_url: ENGINE_JDBC_URL/Jdbc_url: jdbc:postgresql:\/\/engine-ui:5432\/etl_craft/' .state/engine.yml > .state/ui.yml
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

python3 - <<'PYTHON'
import json
import os
import subprocess
from pathlib import Path
obj=json.loads(subprocess.check_output(["kubectl","get","deployment","generator","-o","json"]))
container=obj["spec"]["template"]["spec"]["containers"][0]
values={item["name"]:item["value"] for item in container["env"] if "value" in item}
path=Path(".state/source-reader.env")
path.write_text("".join(f"{name}={values[name]}\n" for name in
                       ("MONGO_USER","MONGO_PASSWORD","MINIO_USER","MINIO_PASSWORD")))
os.chmod(path,0o600)
PYTHON
python3 - <<'PYTHON'
from pathlib import Path
root=Path(".state")
engine="\n".join(line for line in (root/"engine.env").read_text().splitlines()
                 if not line.startswith("ETL_CRAFT_TOKEN="))
(root/"provider.env").write_text(engine+"\n"+(root/"source-reader.env").read_text())
(root/"provider.env").chmod(0o600)
PYTHON
kubectl create secret generic etl-craft-provider --from-file=provider.env=.state/provider.env --dry-run=client -o yaml | kubectl apply -f -
