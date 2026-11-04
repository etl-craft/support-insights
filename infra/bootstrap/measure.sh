#!/bin/sh
set -eu
label=${1:?supply idle or batch}
mkdir -p .state/measurements
kubectl top pods -A > ".state/measurements/$label-pods.txt"
free -h > ".state/measurements/$label-host.txt"
cat /proc/swaps >> ".state/measurements/$label-host.txt"
df -h /home >> ".state/measurements/$label-host.txt"
docker exec k3d-support-insights-server-0 du -sh /var/lib/rancher/k3s/storage /var/lib/rancher/k3s/agent/containerd > ".state/measurements/$label-disk.txt"
kubectl exec deploy/generator -- cat /sys/fs/cgroup/memory.swap.max > ".state/measurements/$label-swap-max.txt"
swap_max=$(cat ".state/measurements/$label-swap-max.txt")
case "$swap_max" in
  ''|*[!0-9]*|0)
    echo "generator memory.swap.max=$swap_max; expected positive LimitedSwap credit; check kubelet.conf and recreate the pod" >&2
    exit 1
    ;;
esac
