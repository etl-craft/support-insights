#!/bin/sh
set -eu
k3d cluster create support-insights --image rancher/k3s:v1.35.5-k3s1 \
  --servers 1 --agents 0 --port '127.0.0.1:8080:80@loadbalancer' \
  --volume "$(pwd)/infra/kubernetes/kubelet.conf:/var/lib/rancher/k3s/agent/etc/kubelet.conf.d/90-swap.conf@server:*" \
  --wait --timeout 120s
kubectl apply --dry-run=server -f infra/kubernetes/system-resources.yml
kubectl apply -f infra/kubernetes/system-resources.yml
kubectl create namespace cnpg-system
url=https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.28/releases/cnpg-1.28.1.yaml
kubectl apply --server-side --dry-run=server -f "$url"
kubectl apply --server-side -f "$url"
kubectl patch deployment -n cnpg-system cnpg-controller-manager --type=strategic -p '{"spec":{"template":{"spec":{"containers":[{"name":"manager","resources":{"requests":{"cpu":"20m","memory":"64Mi"},"limits":{"cpu":"1","memory":"256Mi"}}}]}}}}'
kubectl rollout status -n cnpg-system deployment/cnpg-controller-manager --timeout=180s
kubectl apply --dry-run=server -f infra/kubernetes/engine.yml
kubectl apply -f infra/kubernetes/engine.yml

kubectl rollout restart -n kube-system deployment
kubectl rollout restart -n kube-system daemonset
kubectl wait -n kube-system --for=condition=Available deployment --all --timeout=180s
