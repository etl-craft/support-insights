#!/bin/sh
# Set up single sign-on for the demo: Dex as the OIDC issuer behind an HTTPS tunnel, etl-craft pointed at it.
#   sh infra/bootstrap/sso.sh https://<your-domain>.ngrok-free.dev
# Optional Google sign-in: put the OAuth client in .state/google-client-id.txt and .state/google-client-secret.txt
# first; its authorized redirect URI is <domain>/dex/callback. A local test user always exists so the
# device flow can be tried without Google; its password is written to .state/sso-test-password.
set -eu
domain=${1:-$(tr -d "[:space:]" < .state/sso-domain.txt 2>/dev/null || true)}
[ -n "$domain" ] || { echo "usage: sso.sh https://<domain> (or write it to .state/sso-domain.txt)" >&2; exit 2; }
domain=${domain%/}
python3 - "$domain" <<'PY_DOMAIN'
from urllib.parse import urlsplit
import sys
url = urlsplit(sys.argv[1])
if url.scheme != "https" or not url.hostname or url.path not in ("", "/") or url.username or url.password or url.query or url.fragment:
    raise SystemExit("SSO domain must be an HTTPS origin without credentials, query or fragment")
PY_DOMAIN
mkdir -p .state
chmod 700 .state
umask 077
printf '%s\n' "$domain" > .state/sso-domain.txt
[ -f .state/sso-test-password ] || { head -c 18 /dev/urandom | base64 | tr -d '/+=' > .state/sso-test-password; }
hash=$(uv run --quiet --with bcrypt python -c \
  'import bcrypt,sys;print(bcrypt.hashpw(open(".state/sso-test-password","rb").read().strip(),bcrypt.gensalt(10)).decode())')
google_id=$(tr -d "[:space:]" < .state/google-client-id.txt 2>/dev/null || true)
google_secret=$(tr -d "[:space:]" < .state/google-client-secret.txt 2>/dev/null || true)
connectors=""
if [ -n "$google_id" ] && [ -n "$google_secret" ]; then
  connectors="connectors:
- type: google
  id: google
  name: Google
  config:
    clientID: \$GOOGLE_CLIENT_ID
    clientSecret: \$GOOGLE_CLIENT_SECRET
    redirectURI: $domain/dex/callback"
fi
cat > .state/dex.yaml <<YAML
issuer: $domain/dex
storage:
  type: sqlite3
  config:
    file: /data/dex.db
web:
  http: 0.0.0.0:5556
oauth2:
  skipApprovalScreen: true
  grantTypes:
  - authorization_code
  - refresh_token
  - urn:ietf:params:oauth:grant-type:device_code
staticClients:
- id: etl-craft
  name: etl-craft
  public: true
  redirectURIs:
  - /device/callback
  - $domain/ui/signin/callback
enablePasswordDB: true
staticPasswords:
- email: sso-test@example.test
  username: sso-test
  userID: 00000000-0000-4000-8000-000000000001
  hash: "$hash"
$connectors
YAML
kubectl create configmap dex-config --from-file=config.yaml=.state/dex.yaml --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic dex-secrets \
  --from-literal=GOOGLE_CLIENT_ID="${google_id:-unset}" --from-literal=GOOGLE_CLIENT_SECRET="${google_secret:-unset}" \
  --dry-run=client -o yaml | kubectl apply -f -
python3 - "$domain" <<'PY_INGRESS'
from pathlib import Path
from urllib.parse import urlsplit
import sys, yaml
url = urlsplit(sys.argv[1])
paths = [{"path": path, "pathType": "Prefix", "backend": {"service": {"name": service, "port": {"number": port}}}}
         for path, service, port in (("/dex", "dex", 5556), ("/", "etl-craft-ui", 8730))]
ingress = {"apiVersion": "networking.k8s.io/v1", "kind": "Ingress", "metadata": {"name": "support-insights-sso"},
           "spec": {"ingressClassName": "traefik", "rules": [{"host": url.hostname, "http": {"paths": paths}}]}}
Path(".state/sso-ingress.yml").write_text(yaml.safe_dump(ingress, sort_keys=False))
users = Path(".env.demo-users")
lines = users.read_text().splitlines() if users.exists() else []
lines = [line for line in lines if not line.startswith(("SSO_TEST_USERNAME=", "SSO_TEST_PASSWORD="))]
lines += ["SSO_TEST_USERNAME=sso-test@example.test", "SSO_TEST_PASSWORD=" + Path(".state/sso-test-password").read_text().strip()]
users.write_text("\n".join(lines) + "\n")
users.chmod(0o600)
PY_INGRESS
kubectl apply -f .state/sso-ingress.yml
kubectl apply -f infra/kubernetes/dex.yml
kubectl rollout restart deployment/dex
# etl-craft signs people in through this issuer; the first sign-in of an invited email binds its subject.
for file in .state/engine.yml .state/ui.yml; do
  python3 - "$file" "$domain" <<'PY'
import re, sys
path, domain = sys.argv[1], sys.argv[2]
text = open(path).read()
text = re.sub(r"\nAuth:\n(?:  .*\n)+", "\n", text)
browser_secret = "  Browser_state_secret: BROWSER_STATE_SECRET  # variable\n" if path.endswith("ui.yml") else ""
block = f"Auth:\n  Oidc_issuer: {domain}/dex  # value\n  Oidc_client_id: etl-craft  # value\n  Oidc_bind_by_email: true  # value\n{browser_secret}"
text = text.replace("\nObject_stores:\n", "\n" + block + "Object_stores:\n", 1)
open(path, "w").write(text)
PY
done
python3 - "$domain" <<'PY_SECRET'
import secrets, sys
from pathlib import Path
import yaml
root = Path(".state")
key_file = root / "browser-state-secret"
if not key_file.exists():
    key_file.write_text(secrets.token_urlsafe(48))
key_file.chmod(0o600)
if len(key_file.read_text().strip().encode()) < 32:
    raise SystemExit(".state/browser-state-secret must contain at least 32 bytes; replace it with a random secret")
for name in ("engine.env", "provider.env"):
    path = root / name
    lines = [line for line in path.read_text().splitlines() if not line.startswith("BROWSER_STATE_SECRET=")]
    path.write_text("\n".join(lines) + "\nBROWSER_STATE_SECRET=" + key_file.read_text().strip() + "\n")
    path.chmod(0o600)
for name in ("engine.yml", "ui.yml"):
    path = root / name
    data = yaml.safe_load(path.read_text())
    site = data.setdefault("Docs_site", {})
    site.pop("Domain", None)
    site["External_url"] = sys.argv[1]
    path.write_text(yaml.safe_dump(data, sort_keys=False))
PY_SECRET
kubectl create secret generic etl-craft-engine --from-env-file=.state/engine.env --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic etl-craft-provider --from-file=provider.env=.state/provider.env --dry-run=client -o yaml | kubectl apply -f -
kubectl create configmap etl-craft-config --from-file=engine.yml=.state/engine.yml \
  --from-file=ui.yml=.state/ui.yml --from-file=agent.yml=.state/agent.yml \
  --from-literal=api-url=https://traefik.kube-system.svc --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deployment/etl-craft-controller deployment/etl-craft-ui
kubectl rollout status deployment/dex --timeout=180s
echo "Dex is running. Serve it at $domain with:"
echo "  ngrok http --url=$domain 80"
