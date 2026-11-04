# Support Insights

A local Trino/Iceberg data-movement example for [etl-craft](https://github.com/etl-craft/etl-craft).
S8.A supplies the project layout, source generators and Kubernetes stack. Pipeline conversion
is S8.B; workflows and the runner are S8.E; deterministic mixed-quality scenarios are S8.H.
The former package demo scripts and migrations are preserved in `reference/package-demo/`,
outside the active project, so setup cannot apply them automatically. Source batches do not
run ETL pipelines yet.

## Layout

- `project/`: team-owned connector, config CSV directory, SQL/Python/validation scripts,
  project migrations and folder-addressed reference seeds.
- `generators/`: retained three clients, bounded generation, SQLite state and Gamma webhook.
- `infra/kubernetes/`: S7.F role manifests, deployment-specific patches, sources and warehouse.
- `infra/bootstrap/`: cluster, local images, source policies and Trino schema bootstrap.
- `reference/legacy-sql/`: reference only, never executed by this deployment.

## Workstation and versions

This workstation has 14 GiB RAM, 12 cores, 15 GiB zram and a 16 GiB NVMe swapfile.
Use Docker, k3d 5.9.0, kubectl 1.37.2, Git, uv and OpenSSL. No Helm is required.
The cluster pins k3s v1.35.5-k3s1 and CloudNativePG 1.28.1's release manifest.
The service manifests pin their image versions. Local images have imagePullPolicy Never
for package roles; the generator tag is imported into the node. The engine has three PostgreSQL instances,
one required synchronous standby, and a transaction-mode PgBouncer Pooler for the two UI copies.
The controller and notification listeners connect directly to `engine-rw`.

Pinned package commit: `dd25ca4a4da713d58e0611d771c8b4d2e9a1aacc` ([#319](https://github.com/etl-craft/etl-craft/pull/319), [#320](https://github.com/etl-craft/etl-craft/pull/320), [#321](https://github.com/etl-craft/etl-craft/pull/321)).
The measured memory/disk figures are recorded below.
Images are built locally with that commit's S7.F Dockerfiles and imported with `k3d image import`.
Nothing is pushed to a registry. S8.E will switch to gated candidate images and wheel evidence.

## Start the stack

Run from this repository. Stop the package development services first. Keep test temporary
files on disk at `$HOME/.cache/etl-craft/tests/tmp-codex`, use at most two workers and one suite.

```sh
sh infra/bootstrap/cluster.sh
sh infra/bootstrap/build.sh
kubectl apply --dry-run=server -f infra/kubernetes/services.yml
kubectl apply -f infra/kubernetes/services.yml
sh infra/bootstrap/sources.sh
sh infra/bootstrap/warehouse.sh
sh infra/bootstrap/tls.sh
sh infra/bootstrap/configure.sh
kubectl apply --dry-run=server -f infra/bootstrap/admin.yml
kubectl apply -f infra/bootstrap/admin.yml
kubectl wait --for=condition=Ready pod/craft-admin --timeout=120s
```

`warehouse.sh` uses the Trino CLI to create the schemas. The package never creates warehouse
schemas. Iceberg REST uses a persistent SQLite catalog; `minio-lake` stores lake data, bundles
and logs. `minio-gamma` is a separate source service.

Create the first admin through the package CLI. For setup, pipe your chosen password on
stdin (a single line); login prompts for it interactively:

```sh
kubectl exec -i craft-admin -- etl-craft setup --admin-name admin --password-stdin
kubectl exec -it craft-admin -- etl-craft login
kubectl exec craft-admin -- etl-craft project add --project support_insights --reason 'Demo bootstrap'
kubectl exec craft-admin -- etl-craft pool add --name ingestion --reason 'Demo ingestion capacity'
kubectl exec craft-admin -- etl-craft pool add --name warehouse --reason 'Demo warehouse capacity'
```

Enroll one host service token and twelve distinct, pool-bound agent tokens. The script
reuses the private credentials under ignored `.state/` for this preserved Engine DB;
remove those credentials before enrolling against a newly recreated Engine DB.
Each one-replica S7.F agent Deployment has its own Secret, containing only ETL_CRAFT_TOKEN.
A shared token cannot be scaled across multiple agent processes.

```sh
sh infra/bootstrap/enroll.sh
kubectl apply --dry-run=server -k infra/kubernetes
kubectl apply -k infra/kubernetes
for deployment in $(kubectl get deployment -o name); do
  kubectl rollout status "$deployment" --timeout=300s
done
kubectl exec craft-admin -- etl-craft logout
kubectl delete pod craft-admin
```

The controller is headless with a 1 GiB limit. Its S7.F Recreate strategy stops the old
controller before starting the replacement; two active controllers are refused. Three ingestion agents expose one Python slot
and nine warehouse agents expose one warehouse slot, each with a 256 MiB limit. The package's
explicit Python slot override preserves CPU, total-slot and measured process-floor guards;
S8.B must give the ingestion tasks measured `MEMORY_REQUEST_MB` values fitting those agents.

Open [the UI](https://craft.localhost:8443), [generators](http://generator.localhost:8080)
and [Mailpit](http://mail.localhost:8080). The local TLS certificate is in `.state/tls.crt`;
trust it explicitly for this demo. Agents trust it through a ConfigMap and use the TLS ingress.
All host ports bind to loopback. Credentials in service manifests are local demo credentials.
Production separates the warehouse from the Engine DB and supplies managed credentials/TLS.

## Source bounds and batches

Each client has a fixed 10,000-business-key space, a 1,000-input-row maximum batch and a
10,000-emitted-row UTC daily budget, including a reserved update for each four inputs.
Failures conservatively retain their reservation. The update share is fixed at one per four
inputs; named deterministic cases and truth fixtures remain S8.H. The UI's random input range
is 100–1,000. Run one batch per client at a time.

```sh
kubectl exec deploy/generator -- python generators/client_alpha_data_generator.py 1000
kubectl exec deploy/generator -- python generators/client_beta_data_generator.py 1000
kubectl exec deploy/generator -- python generators/client_gamma_data_generator.py 1000
```

MongoDB has a two-day TTL on generated documents. Kafka is KRaft with four topic partitions,
one-day retention and `retention.bytes=268435456` per partition. Gamma objects expire after
two days. Project attempt logs retain two days through the existing retention configuration.
Trino's snapshot and orphan minimum retention is one day; nightly table maintenance belongs
in S8.B. Budget 50 GB of disk for the local installation and watch actual usage below.

Gamma's `.csv.gz` object-created notification reaches the existing generator HTTP process.
Trino is internal-only and trusts cluster usernames. File ACLs restrict the webhook's
`gamma_signal` principal to INSERT access to `lnd.gamma_object_events`; it cannot
read or mutate lake tables otherwise. The signal stores object key, ETag, size, event time and
an `event_key` encoding the object key/ETag pair as JSON. A new ETag is a new delivery.
SQLite receipts suppress ordinary replays. A crash after Trino commits but before SQLite
commits may repeat a physical row; physical uniqueness is deliberately not required.
[The event query](infra/bootstrap/gamma-events.sql) groups each version to one result row.
An injected duplicate was checked locally: two physical rows grouped to one delivery.
S8.B must use `EVENT_KEY_COLUMN=event_key` and read the object key from `task.event_rows`.

S8.F acceptance check `gamma_duplicate_notification`: insert a second notification row for
the same object key/ETag, run Gamma, and assert that object loads once and exactly one key is
recorded in `AUD_EVENT_KEYS` for the event task. Test a new ETag as a separate delivery too.
Package probes already confirm identical rows deduplicate to one recorded key without GROUP BY;
conflicting payloads fail naming the key, expected single payload and remedy.

## Local checks

The generator image carries its pinned dependencies. Run its tests without installing
packages into the host environment:

```sh
mkdir -p "$HOME/.cache/etl-craft/tests/tmp-codex/generator-logs"
docker run --rm --user "$(id -u):$(id -g)" --entrypoint python \
  -e TMPDIR="$HOME/.cache/etl-craft/tests/tmp-codex" \
  -v "$HOME/.cache/etl-craft/tests/tmp-codex:$HOME/.cache/etl-craft/tests/tmp-codex" \
  -v "$HOME/.cache/etl-craft/tests/tmp-codex/generator-logs:/app/logs" \
  -v "$(pwd)/tests:/app/tests:ro" \
  support-insights-generator:s8a -m unittest discover -s tests
```

Every manifest is validated against the live API using `kubectl apply --dry-run=server`.
The retained generator status API now emits ISO timestamps after a run instead of failing
JSON serialization. No demo CI or runner is added here.

## Measure and stop

Pods need LimitedSwap, not only `failSwapOn: false`. `cluster.sh` mounts
[`kubelet.conf`](infra/kubernetes/kubelet.conf), setting `memorySwap.swapBehavior: LimitedSwap`.
Every workload has memory requests and limits. Idle-heavy sources have low requests; Trino
requests 2.5 GiB against a 3 GiB limit to keep it resident.

```sh
kubectl exec deploy/generator -- cat /sys/fs/cgroup/memory.swap.max
sh infra/bootstrap/measure.sh idle
# Run the three source batches above, then obtain a fresh metrics-server sample.
sh infra/bootstrap/measure.sh batch
k3d cluster stop support-insights
# Resume the preserved cluster:
k3d cluster start support-insights
```

`memory.swap.max` must be greater than zero. Measurements include `kubectl top pods -A`,
`free -h`, `/proc/swaps`, host free disk and node storage/image disk use. They are source-only
S8.A batch measurements; ETL workload and Beta task-process memory acceptance remain S8.F.


## Measured on this workstation

On 2026-11-04, all 33 running pods were ready on the pinned commit above. Each snapshot
waited for a fresh metrics-server sample for every pod. The batch ran 1,000 inputs per
client sequentially, producing 1,250 rows/events per client (including updates). These are
point-in-time working sets from `kubectl top pods -A`, not peak memory or ETL acceptance.

| Component | Idle MiB | After batch MiB |
|---|---:|---:|
| Kubernetes + CNPG operator (6) | 158 | 156 |
| Agents (12) | 986 | 868 |
| PostgreSQL (3) | 339 | 300 |
| PgBouncer (1) | 15 | 15 |
| Controller (1) | 72 | 72 |
| UI (2) | 198 | 203 |
| Generator (1) | 6 | 14 |
| Iceberg REST (1) | 69 | 125 |
| Kafka (1) | 160 | 168 |
| Mailpit (1) | 7 | 7 |
| Gamma MinIO (1) | 64 | 65 |
| Lake MinIO (1) | 62 | 76 |
| MongoDB (1) | 44 | 45 |
| Trino (1) | 191 | 588 |
| **All 33 pods** | **2371 (2.32 GiB)** | **2702 (2.64 GiB)** |

| Host / disk observation | Idle | After batch |
|---|---:|---:|
| Host RAM used (`free -h`) | 8.9 GiB | 9.3 GiB |
| Host RAM available | 6.0 GiB | 5.7 GiB |
| Host swap used (30 GiB total) | 5.6 GiB | 5.2 GiB |
| NVMe swapfile used | 0 | 0 |
| Node persistent storage | 1.3 GiB | 1.3 GiB |
| Node containerd image/storage directory | 8.7 GiB | 8.7 GiB |
| Host filesystem used / available | 176 / 286 GiB | 176 / 286 GiB |
| Generator `memory.swap.max` | 138,911,744 bytes | 138,911,744 bytes |

Host totals include the workstation's other applications and caches; pod working sets are
already part of host RAM. Swap was in zram in both snapshots. Pod working sets exclude
swapped pages, so their 2.32/2.64 GiB totals do not describe the stack's whole memory footprint.
Node disk figures include the locally imported validation images. The 50 GB disk budget
remains the installation budget; retention and actual disk usage still need monitoring.

Local validation passed: server dry-run for the stack, system limits, admin pod and pinned
CNPG install; all rollouts; twelve active one-slot agents in the 3/9 pools; two ready UI
endpoints; TLS ingress and generator/Mailpit routes; headless controller health/root behavior;
required synchronous replication and transaction pooling; and eight generator tests (0.118s,
with the configured disk TMPDIR asserted). Gamma's real notification matched the object
key, ETag and size. Its principal refused SELECT, DELETE and table optimization. An injected
physical duplicate grouped to one version. The Engine DB pipeline list is empty.

Before these final batches, validation had already emitted one 100-input Gamma smoke batch
and one 1,000-input batch per client. The final measurements therefore cover an incremental
source batch on persisted state, not empty source services. Full pipeline correctness,
load-once audit assertions and peak ingestion memory remain S8.B/S8.F.
