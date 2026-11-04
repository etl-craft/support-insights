#!/bin/sh
set -eu
mkdir -p .state
umask 077
if [ ! -f .state/tls.crt ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -keyout .state/tls.key -out .state/tls.crt -days 365 -subj /CN=craft.localhost -addext 'subjectAltName=DNS:craft.localhost,DNS:traefik.kube-system.svc' -addext 'basicConstraints=critical,CA:TRUE'
fi
kubectl create secret tls craft-tls --cert=.state/tls.crt --key=.state/tls.key --dry-run=client -o yaml | kubectl apply -f -
kubectl create configmap demo-ca --from-file=ca.crt=.state/tls.crt --dry-run=client -o yaml | kubectl apply -f -
