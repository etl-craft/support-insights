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
mkdir -p .state
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
kubectl apply -f infra/kubernetes/dex.yml
kubectl rollout restart deployment/dex
# etl-craft signs people in through this issuer; the first sign-in of an invited email binds its subject.
for file in .state/engine.yml .state/ui.yml; do
  python3 - "$file" "$domain" <<'PY'
import re, sys
path, domain = sys.argv[1], sys.argv[2]
text = open(path).read()
text = re.sub(r"\nAuth:\n(?:  .*\n)+", "\n", text)
block = f"Auth:\n  Oidc_issuer: {domain}/dex  # value\n  Oidc_client_id: etl-craft  # value\n  Oidc_bind_by_email: true  # value\n"
text = text.replace("\nObject_stores:\n", "\n" + block + "Object_stores:\n", 1)
open(path, "w").write(text)
PY
done
kubectl create configmap etl-craft-config --from-file=engine.yml=.state/engine.yml \
  --from-file=ui.yml=.state/ui.yml --from-file=agent.yml=.state/agent.yml \
  --from-literal=api-url=https://traefik.kube-system.svc --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deployment/etl-craft-controller deployment/etl-craft-ui
kubectl rollout status deployment/dex --timeout=180s
echo "Dex is running. Serve it at $domain with:"
echo "  kubectl port-forward svc/dex 5556:5556 &  ngrok http --url=$domain 5556"
