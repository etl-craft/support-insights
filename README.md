# Support Insights

A local Trino/Iceberg data-movement example for [etl-craft](https://github.com/etl-craft/etl-craft).
The project defines the S8.B pipelines for MongoDB, Kafka and MinIO ingestion, reference
history and normalized ODS. Execution order,
schedules and actions live in `project/config/`; managed SQL remains read-only SELECTs.
Workflows and the runner remain S8.E; full acceptance checks and the mixed-quality matrix
remain S8.F/H.

Only business-rule **REJECT** flags exclude rows from ODS. INCOMPLETE and REPORT rows remain
eligible. Each generator accepts `--rejectable` to produce bounded, parseable negative-duration
batches that reach business-rule evaluation. See [the project guide](project/README.md) for
source mappings, original reference seeds and independent row comparisons.

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

Pinned package commit: `87a4a1785b9268304d3c193457117a2edfb9fa0e`, including
[#322](https://github.com/etl-craft/etl-craft/pull/322),
[#323](https://github.com/etl-craft/etl-craft/pull/323) and
[#324](https://github.com/etl-craft/etl-craft/pull/324).
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
# Keep craft-admin until the project bootstrap below finishes.
```

The controller is headless with a 1 GiB limit. Its S7.F Recreate strategy stops the old
controller before starting the replacement; two active controllers are refused. Three ingestion agents expose one Python slot
and nine warehouse agents expose one warehouse slot, each with a 256 MiB limit. The package's
explicit Python slot override preserves CPU, total-slot and measured process-floor guards;
The ingestion tasks declare `MEMORY_REQUEST_MB` within those agents’ capacity.

Open [the UI](https://craft.localhost:8443), [generators](http://generator.localhost:8080)
and [Mailpit](http://mail.localhost:8080). The local TLS certificate is in `.state/tls.crt`;
trust it explicitly for this demo. Agents trust it through a ConfigMap and use the TLS ingress.
All host ports bind to loopback. Credentials in service manifests are local demo credentials.
Production separates the warehouse from the Engine DB and supplies managed credentials/TLS.

## Bootstrap the project

Keep schedules disabled while installing a fresh project. Apply config without physical
landing column declarations, publish the project, then run SI_SETUP. Its tasks create all
managed targets; warehouse schemas come from `infra/bootstrap/warehouse.sql`.

```sh
cp -R project/config .state/bootstrap-config
rm .state/bootstrap-config/columns.csv
kubectl cp .state/bootstrap-config craft-admin:/tmp/bootstrap-config
kubectl exec craft-admin -- etl-craft config apply --config-dir /tmp/bootstrap-config
kubectl exec craft-admin -- etl-craft bundle publish --project-dir /project
etl-craft --api https://craft.localhost:8443 --project support_insights run \
  --pipeline-code SI_SETUP --init-only --run-key bootstrap-setup
```

Wait for that exact run to end SUCCESS using `status --pipeline-code SI_SETUP --run-id ID`.
Then apply the seeds and full landing contracts and start reference history:

```sh
kubectl exec craft-admin -- etl-craft seed apply
kubectl cp project/config craft-admin:/tmp/full-config
kubectl exec craft-admin -- etl-craft config apply --config-dir /tmp/full-config
etl-craft --api https://craft.localhost:8443 --project support_insights run \
  --pipeline-code SI_REFERENCE --init-only --run-key bootstrap-reference
kubectl exec craft-admin -- etl-craft logout
kubectl delete pod craft-admin
```

Use the enrolled host token and demo TLS CA for host API commands. Source credentials live
in the FILE provider mounted on controller/API pods only. The controller/API host configuration resides on the project PVC, so uploads and processed
uploads share one mount across both UI copies and the controller. The project guide covers
maintenance holds and source policies; the deployment workflow remains S8.E.

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
Trino's snapshot and orphan minimum retention is one day. The stewardship and maintenance
slice will add the nightly table operations. Budget 50 GB of disk for the local installation and watch actual usage below.

Gamma's `.csv.gz` object-created notification reaches the existing generator HTTP process.
Trino is internal-only and trusts cluster usernames. File ACLs restrict the webhook's
`gamma_signal` principal to INSERT access to `lnd.gamma_object_events`; it cannot
read or mutate lake tables otherwise. The signal stores object key, ETag, size, event time and
an `event_key` encoding the object key/ETag pair as JSON. A new ETag is a new delivery.
SQLite receipts suppress ordinary replays. A crash after Trino commits but before SQLite
commits may repeat a physical row; physical uniqueness is deliberately not required.
[The event query](infra/bootstrap/gamma-events.sql) groups each version to one result row.
An injected duplicate was checked locally: two physical rows grouped to one delivery.
Gamma uses `EVENT_KEY_COLUMN=event_key` and reads the object key from `task.event_rows`.

The live `tests/test_gamma_duplicate_signal.py` check inserts duplicate notification rows for
the same object key/ETag, run Gamma, and assert that object loads once and exactly one key is
recorded in `AUD_EVENT_KEYS` for the event task. S8.F/H extend this to a new ETag and the full acceptance matrix.
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
  support-insights-generator:87a4a1785b9268304d3c193457117a2edfb9fa0e -m unittest discover -s tests
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
`free -h`, `/proc/swaps`, host free disk and node storage/image disk use. The S8.B observations below include ETL workload and the Beta task process.


## Measured on this workstation

S8.B validation on 2026-11-04 ran the complete k3d deployment with real ingestion and
warehouse tasks. Beta's 1,000-input generator batch also produced 250 updates. Its ingestion
attempt 183, run 25, succeeded with two fan-out readers, four partition items and a 256 MiB
container limit. The agent pod cgroup recorded:

| Beta ingestion observation | Measured value |
|---|---:|
| Memory peak | 214,204,416 bytes (204.3 MiB) |
| Memory current after ingestion | 91,893,760 bytes (87.6 MiB) |
| Container memory limit | 268,435,456 bytes (256 MiB) |
| Swap current after ingestion | 49,397,760 bytes (47.1 MiB) |
| `memory.swap.max` | 277,827,584 bytes |

These are container cgroup measurements, including the agent and its child, rather than an
estimate from the task reservation. The peak is the pod's lifetime high-water mark, including
its prior fixture attempt. The source-provider file and source passwords are absent from the
agent container; credentials reach its admitted child through the task-secret pipe.

The post-batch snapshot included the transient bootstrap/admin pod and other pipeline work;
it was taken before the final image build. `kubectl top pods -A` recorded 34 pods totalling
3,724 MiB. Host `free -h` reported 11 GiB used and 3.6 GiB available, with 8.8 GiB swap
used (zram; the NVMe swapfile used zero). Node persistent storage was 2.0 GiB and containerd
storage 9.8 GiB. The host filesystem used 179 GiB with 283 GiB available. Pod working sets
exclude swapped pages and are already included in host RAM. The idle snapshot below is
taken after validation and removal of the admin pod.
