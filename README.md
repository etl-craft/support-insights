# Support Insights

A local Trino/Iceberg data-movement example for [etl-craft](https://github.com/etl-craft/etl-craft).
The project defines the S8.B pipelines for MongoDB, Kafka and MinIO ingestion, reference
history, normalized ODS, the six-hour SI_DM mart, four steward upload pipelines and nightly
Iceberg maintenance.
Execution order,
schedules and actions live in `project/config/`; managed SQL remains read-only SELECTs.
The configuration workflows are described under [Configuration through CI](#configuration-through-ci);
the candidate-image workflow and the self-hosted runner's container remain S8.E, and full acceptance
checks and the mixed-quality matrix remain S8.F/H.

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

Pinned package commit: `8a7e67b917d14a413c27d99dfd2ebd4b19ec61c1`, including
[#322](https://github.com/etl-craft/etl-craft/pull/322),
[#323](https://github.com/etl-craft/etl-craft/pull/323),
[#324](https://github.com/etl-craft/etl-craft/pull/324) and
[#325](https://github.com/etl-craft/etl-craft/pull/325) and
[#326](https://github.com/etl-craft/etl-craft/pull/326).
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
kubectl exec craft-admin -- etl-craft bundle publish --project-dir /project
etl-craft --api https://craft.localhost:8443 --project support_insights run \
  --pipeline-code SI_REFERENCE --init-only --run-key bootstrap-reference
# Wait for this exact SI_REFERENCE run to end SUCCESS before enabling schedules.
sed -i 's/Allow_schedule: false/Allow_schedule: true/' .state/engine.yml .state/ui.yml
kubectl create configmap etl-craft-config --from-file=engine.yml=.state/engine.yml \
  --from-file=ui.yml=.state/ui.yml --from-file=agent.yml=.state/agent.yml \
  --from-literal=api-url=https://traefik.kube-system.svc --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deployment/etl-craft-controller deployment/etl-craft-ui
kubectl exec craft-admin -- etl-craft logout
kubectl delete pod craft-admin
```

Use the enrolled host token and demo TLS CA for host API commands:

```sh
export ETL_CRAFT_TOKEN="$(cat .state/host-token)"
export SSL_CERT_FILE="$(pwd)/.state/tls.crt"
```

 Source credentials live
in the FILE provider mounted on controller/API pods only. The controller/API host configuration resides on the project PVC, so uploads and processed
uploads share one mount across both UI copies and the controller. The project guide covers
maintenance holds and source policies; the deployment workflow remains S8.E.

## Configuration through CI

Metadata is code in `project/config/`. Pipeline, rule and stewardable-pipeline edits are pull
requests; access grants use the package's admin commands outside config CI; retiring a row sets
`ACTIVE_FLAG = 'N'`. Nobody edits the Engine DB by hand.

- **`validate.yml`** runs on every pull request that touches `project/`, `ci/` or itself, on a
  GitHub-hosted runner, with no secrets. It runs `ci/validate.sh`: build the wheel at the commit in
  `ci/PACKAGE_COMMIT` (printing its SHA-256), migrate an empty SQLite Engine DB, create the first admin
  with `setup` and `login --password-stdin`, add the project and its pools, bootstrap a local DuckDB
  warehouse (`ci/warehouse.sql`: the same schemas as `infra/bootstrap/warehouse.sql` and the one source
  table `validate` probes), then `config plan`, `config apply`, `bundle publish` and `validate` on a scratch
  copy of `project/` whose connector is `ci/craft-connector.yml`. The declared secret names get placeholder
  values (`validate` checks that they exist, never their value). A bad seed value fails the job: seed files
  are validated from the published bundle against the DuckDB warehouse, so publishing precedes `validate`.
  Run it on any machine with `uv` and Git: `ci/validate.sh` (about 30 seconds; `SI_CI_WORK=dir` keeps the
  scratch folder, `ETL_CRAFT_WHEEL=path` skips the build).
- **`deploy.yml`** runs on a push to `main` that touches `project/`, on the self-hosted runner in the demo
  cluster (label `support-insights`), in the GitHub environment `production`. It installs the same pinned
  command line and runs `validate`, `config apply`, `bundle publish`, `seed apply` and `run` of
  `SI_REFERENCE`, all with `--api`. It holds one developer token and no Engine DB or artifact-store
  credential, and no workflow on that runner runs on `pull_request`.
- **`ci/PACKAGE_COMMIT`** is the one package commit both workflows install; it needs `login
  --password-stdin` (package #338). The cluster images keep their own pin until S8.E.

The repository settings these workflows rely on are not in the repository. Create them once:
an environment named `production` with required reviewers; in it the secret `ETL_CRAFT_DEVELOPER_TOKEN`
(a `developer` token from `etl-craft token create --role developer`) and the variable `ETL_CRAFT_API`;
and a self-hosted runner container in the cluster labelled `support-insights`. Protect `main` so a pull
request must pass `Validate`. `deploy.yml` has not run yet.

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

Kafka mounts its PVC directly at `/var/lib/kafka/data` (the image declares a volume there)
and keeps broker logs in its `broker/` subdirectory. It uses Recreate so two broker instances never share it. A replacement-pod check preserves
the topic identity and end offsets.

MongoDB has a two-day TTL on generated documents. Kafka is KRaft with four topic partitions and automatic topic creation disabled,
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

After inserting a duplicate notification for the same object key/ETag and running Gamma,
the live `tests/test_gamma_duplicate_signal.py` check asserts that the object loads once and one key is
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
  -v "$(pwd)/project:/app/project:ro" \
  -v "$(pwd)/reference:/app/reference:ro" \
  support-insights-generator:8a7e67b917d14a413c27d99dfd2ebd4b19ec61c1 -m unittest discover -s tests
```

For the small live row checks, use unused fixture keys (this validation uses 9000–9002, beyond its random batches). Deliver once after random batch checks, then run each client with
an explicit run key and wait for that exact run to end SUCCESS. Replaying unchanged inputs
keeps PRS history unchanged, so the PRE_ODS check belongs to the delivery that first changes
those rows.

```sh
python3 - <<'PYTHON'
import csv, json
from pathlib import Path
inputs = json.loads(Path("tests/fixtures/generator-records.json").read_text())
inputs["setup_tables"] = [
    row["TARGET_SCHEMA_NAME"] + "." + row["TARGET_TABLE_NAME"]
    for row in csv.DictReader(open("project/config/tasks.csv"))
    if row["PIPELINE_CODE"] == "SI_SETUP"
]
Path(".state/prepared-inputs.json").write_text(json.dumps(inputs))
PYTHON
kubectl exec -i deploy/generator -- sh -c 'cat > /tmp/source_fixture.py' < tests/source_fixture.py
kubectl exec -i deploy/generator -- python /tmp/source_fixture.py \
  < .state/prepared-inputs.json > .state/oracle-inputs.json
# Run SI_CLIENT_ALPHA, SI_CLIENT_BETA and SI_CLIENT_GAMMA through the API.
# Wait for their exact run IDs before checking their targets.
kubectl port-forward service/trino 18080:8080 --address 127.0.0.1
```

In another terminal, the generator image can run the five live oracles with host networking:

```sh
docker run --rm --network host --entrypoint python \
  -e SI_TRINO_HOST=127.0.0.1 -e SI_TRINO_PORT=18080 \
  -e SI_ORACLE_INPUTS=/app/oracle-inputs.json \
  -v "$(pwd)/.state/oracle-inputs.json:/app/oracle-inputs.json:ro" \
  -v "$(pwd)/tests:/app/tests:ro" -v "$(pwd)/project:/app/project:ro" \
  support-insights-generator:8a7e67b917d14a413c27d99dfd2ebd4b19ec61c1 \
  -m unittest discover -s tests -p test_pipeline_rows.py
```

For the duplicate-signal check, copy the delivered object's notification into a second
physical row using the INSERT-only `gamma_signal` principal before starting Gamma. Record
its exact `event_key` and `business_key` (9000) in a JSON file named by
`SI_DUPLICATE_EVENT`; run `tests/test_gamma_duplicate_signal.py` on the host with Trino's
client installed and kubectl access. This also checks the consumed key in the Engine DB.
Stop the temporary port-forward after checking. Full acceptance orchestration remains S8.F.

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

Measured on 2026-11-05 IST (2026-11-04 UTC), using package commit
`4a2fda2a6a83790b373856f63410266504302ebf`. Beta generated 1,000 inputs plus 250 updates;
run 43, ingestion attempt 381 loaded all 1,250 rows. All four partition items succeeded with
`max_parallel=2`, within the 256 MiB agent/task container. Its cgroup recorded:

| Beta ingestion observation | Measured value |
|---|---:|
| Memory peak | 200,548,352 bytes (191.3 MiB) |
| Memory current after ingestion | 18,288,640 bytes (17.4 MiB) |
| Container memory limit | 268,435,456 bytes (256 MiB) |
| Swap current after ingestion | 63,168,512 bytes (60.2 MiB) |
| `memory.swap.max` | 277,827,584 bytes |
| OOM / OOM-kill events | 0 / 0 |

The measured pod was `agent-ingestion-02-594bb4447f-gvwkx`, UID
`c3e1d835-ec22-420f-b639-241150c40ec5`, running the pinned ingestion image. The peak covers
its lifetime, including previous attempts and parent SDK imports. These are actual container
measurements including agent and child, not task reservation estimates. Provider files and
source-password environment variables are absent from the agent container; declared credentials reach its admitted
child through the task-secret pipe.

The idle snapshot follows the Beta run and removal of the admin pod. The post-batch snapshot
follows the three small client deliveries (runs 44–46). Both contain 33 pods and include all
three PostgreSQL instances, two UI copies and twelve agents:

| Observation | Idle | After client batches |
|---|---:|---:|
| `kubectl top pods -A`, summed working sets | 4,093 MiB | 4,917 MiB |
| Host `free -h`, RAM used | 10 GiB | 11 GiB |
| Host RAM available | 4.6 GiB | 3.7 GiB |
| Host `free -h`, swap used | 9 GiB | 9.2 GiB |
| NVMe swapfile used (`/proc/swaps`) | 0 | 0 |
| Node persistent storage (`du -sh`) | 2.1G | 2.1G |
| Node containerd storage (`du -sh`) | 11G | 11G |
| Host filesystem used / available (`df -h`) | 182G / 280G | 183G / 280G |

The active swap is zram; `memory.swap.max` was also positive in the generator in both
snapshots. Pod working sets exclude swapped pages and are included in host RAM. Disk values
retain the tools' human-readable units. A disk scan raced with containerd cleanup and was
retried successfully; the table uses the completed snapshots.

Validation: 14 local tests passed (six live checks skipped in that invocation); the separate
five live pipeline oracles passed in 2.850 seconds and the Gamma duplicate check in 0.457
seconds. Every candidate, including negative durations, reached PRE_ODS; only REJECT keys
were excluded from ODS. The missing-agent INCOMPLETE records reached ODS. Setup run 34
succeeded on 19 targets and reference run 35 on ten tasks. Original DS seed equality is
checked independently against the legacy inserts; prior uploaded DS seeds stayed locked,
and both replaceable seeds reported UNCHANGED on reapplication.

Kafka replacement preserved the topic ID and all four end offsets (307, 150, 262, 531).
An earlier parent-directory PVC mount was masked by the image's child volume, causing topic
loss and a correctly refused stale offset. The corrected mount persists its `broker/` logs;
local fixture replay used the audited `mark --offset` operation with a reason. No raw audit
edits or watermark bypass were used. Attempt 89 was separately reconciled through merged
package #325, recording PROCESS=ATTESTED and QUERIES=VERIFIED.

## SI_DM window checks

SI_DM is independent of client freshness: `0 */6 * * *` UTC, with a bounded timestamp
cursor over the three existing client writers. Deploy the new project/config and publish its
bundle through the bootstrap admin, then run the SI_SETUP task
`setup_dm_customer_support_fact` once under an explicit run key. Run SI_DM with `--init-only`
and an explicit run key; inspect that exact run ID. Existing setup/history is preserved.
SI_STEWARD_BUSINESS is included in the writer fence list.

The DM input JSON extends the captured generator manifest with `source_runs`, mapping each
client to `source_pipeline_run_id` and `source_task_run_id` (its exact `*_prs_to_cdc` task-run
ID from that client's status JSON). The test compares those known provenance values too;
it never selects a run by recency.

For controlled checks, keep schedules disabled as during bootstrap and let active source
writers settle. After the matching DM window succeeds, compare generator inputs and seed
names independently:

```sh
SI_DM_INPUTS="$PWD/.state/dm-inputs.json" SI_TRINO_HOST=127.0.0.1 SI_TRINO_PORT=18080 \
  python -m unittest discover -s tests -p test_dm_rows.py
python -m unittest discover -s tests -p test_dm_windows.py
```

Use the package development environment (with DuckDB) for the four deterministic SQL/config
fixtures, and the temporary Trino port-forward described above for live checks. The fixtures
prove inclusive low/exclusive high, empty ranges, lookup-only changes and joined values at or
after high deferred into the following window. Expected rows are plain Python fixtures;
the SELECT under test is the actual project SQL.

Run another SI_DM window with no intervening ODS writes. It must succeed with zero source
rows and advance from the previous admitted high to its own high without opening SCD2
versions. `tests/test_dm_publication.py` checks exact run snapshots plus the live active
row IDs/hashes; SI_DM_WINDOWS names JSON containing `first`, `empty` (the full status JSON
for each exact run ID), and `active_before_empty` (the live source_id,
source_system_identifier, row_id and hash_key inventory captured before the empty run).
No run is selected by recency, and neither test resets watermarks. The full concurrent
writer/retry/repair matrix remains S8.F.

During this slice, an old claimed Beta attempt (423) had no recorded process start and
continued renewing after an interrupted API exchange. Package #326 fixes that defect.
The stack was upgraded to the merged package commit; reconciliation retained PROCESS
ATTESTED / QUERIES VERIFIED for the deleted original instance with operator reason and
all lease/fence/instance checks. DM attempt 429, interrupted during the controlled rollout,
used the same checked path. Attempt 427 retained VERIFIED process/query evidence. Recovery
of exact DM run 95 uses its existing identity, never an offset or audit edit.

The first recovered run correctly stopped at the next old fence (Gamma attempt 92), so its
success alone did not publish the later fixture rows. Reconciliation of that deleted original
instance removed the final unresolved source ending. Row checks use the subsequent matching
window, rather than assuming any successful DM run includes the latest source delivery.

Live validation on the merged package commit `8a7e67b917d14a413c27d99dfd2ebd4b19ec61c1`:

| Exact DM run | Result | Source rows / rows written | Admitted low → high (UTC) |
|---|---|---:|---|
| 96 (attempt 431) | SUCCESS | 5,714 / 5,714 | 2026-11-04 08:32:40.758454 → 2026-11-05 01:01:11.384294 |
| 97 (attempt 432) | SUCCESS, empty | 0 / 0 | 2026-11-05 01:01:11.384294 → 2026-11-05 01:01:58.988918 |

The independent fact check passed (one test, 0.379 seconds), comparing six clean/incomplete
fixture rows, lookup names and exact client/CDC provenance; reject keys remain absent.
The empty-publication check passed (one test, 0.251 seconds), comparing all 5,714 active row
IDs/hashes before and after run 97 as well as both windows' recorded bounds. Four local
DuckDB SQL/config tests passed in 0.402 seconds, including the failing-first joined-high
case. Generator-image tests passed 15, with 11 explicitly skipped live/DuckDB checks;
the two new live checks and three SQL checks above ran separately. Validate checked six
pipelines and 66 tasks with zero failures/warnings. All manifests passed server dry-run.

The prior interrupted attempts remain in audit as expected recovery evidence. Schedules are
re-enabled after the controlled checks. Full held-writer, retry and old-run repair acceptance
remains S8.F; SI_STEWARD_BUSINESS now participates in the writer fence.

Local USER account names and passwords are stored in the gitignored `.env.demo-users`
(mode 0600): the admin plus demo-steward-a and demo-steward-b. Keep each newly created
local demo USER in that file. It is workstation-only and must never enter a bundle or PR.

## Stewardship checks

The four steward pipelines are unscheduled and require an uploaded CSV. Use the project's
admin token to create USER accounts and grant access, then sign in separately for each user:

```sh
etl-craft --api https://craft.localhost:8443 --project support_insights account add \
  --name demo-steward-a --kind USER --role viewer
etl-craft --api https://craft.localhost:8443 --project support_insights access grant \
  --account demo-steward-a --permission CAN_VIEW --reason 'Demo project discovery'
for pipeline in SI_STEWARD_DS_AGENTS SI_STEWARD_DS_CUSTOMER_TYPES \
  SI_STEWARD_DS_SUPPORT_AREAS SI_STEWARD_BUSINESS; do
  etl-craft --api https://craft.localhost:8443 --project support_insights access grant \
    --account demo-steward-a --pipeline "$pipeline" --permission CAN_UPLOAD \
    --reason 'Demo steward uploads'
done
# Repeat for demo-steward-b. Record the chosen passwords in .env.demo-users (0600).
env -u ETL_CRAFT_TOKEN XDG_CONFIG_HOME="$PWD/.state/steward-a-config" \
  etl-craft --api https://craft.localhost:8443 --project support_insights login
```

The USER session must be used without the admin service token in the environment. Service
uploads intentionally create no human locks. The local validation used two viewer-role USER
accounts with project CAN_VIEW and CAN_UPLOAD on only these four pipelines.

Upload `tests/fixtures/steward/agents.csv`, `customer_types.csv` and `support_areas.csv` to
their respective SI_STEWARD_DS pipelines. Each changes an original reference key and ends
with a detached SI_REFERENCE run; wait for its exact child run ID too. The business files
correct the existing Alpha and Beta key 9000, preserving source identities:

```sh
env -u ETL_CRAFT_TOKEN XDG_CONFIG_HOME="$PWD/.state/steward-a-config" \
  etl-craft --api https://craft.localhost:8443 --project support_insights upload \
    --pipeline-code SI_STEWARD_BUSINESS tests/fixtures/steward/business-a.csv --format json
```

For the two-uploader check, pause `validate_file`, admit a controlled bad-header blocker
file, then upload business-a and business-b from their separate USER sessions while that run
is held. Resume the validation task. The blocker is an expected refusal with a failure alert;
both waiting files then enter one following run, retaining distinct upload IDs/accounts.
Check the exact receipt/run IDs through `uploads` and `status` rather than selecting by recency.
A separate upload-free manual run of a steward pipeline must fail permanently with
“no uploaded files in this run”; its FAILURE alert succeeds. These expected failures remain
audited, with no automatic retry of validation.

`SI_STEWARD_INPUTS` names JSON with `reference` entries for agents/customer_types/support_areas,
each containing `files`, plus `business.files`. Each file entry has `fixture` (repo-relative CSV),
`upload_id` and `account`. Run:

```sh
SI_STEWARD_INPUTS="$PWD/.state/steward-inputs.json" SI_TRINO_HOST=127.0.0.1 SI_TRINO_PORT=18080 \
  python -m unittest discover -s tests -p test_steward_rows.py
python -m unittest discover -s tests -p test_steward_validation.py
```

The live checks compare uploaded values and UPLOAD_ID through LND → PRS → CDC → PRE_ODS →
ODS, checking each uploader's CREATED_BY/UPDATED_BY on the SCD targets. Reference checks
compare DS and active DWH copies. The unit tests need the package development environment;
the generator-only image skips them explicitly. Validators accept optional LOCKED and check
types before landing; negative integer durations still reach business rules.

Run the next matching SI_DM window to publish corrections. Its independent input manifest
can add `reference_overrides` (table → CSV paths), `business_overrides` (CSV paths), and
`provenance_overrides` (`source_id:key` → exact writing pipeline/CDC task-run IDs). Expectations
apply these uploaded inputs to generator inputs/seeds, without reading project SQL.

The `*-restore.csv` files return fixture values and set LOCKED=false. Reference restore
batches include an unchanged control record. An entirely unchanged batch retains its prior
receipt/writer; `retained_metadata`, keyed by the reference ID in a file entry, records those
known prior values for the oracle. Duplicate file bytes are refused, including older retained
receipts; resume/rerun the recorded upload context for a retry. The local restore exercise
encountered an old identical one-row file, then used the declared two-row restore fixture.

## Run maintenance safely

Before the 02:00–03:00 UTC maintenance window, pause every writer definition (clients, DM,
all stewards, SI_REFERENCE and SI_SETUP), hold every active exact run, including waiting Gamma
runs and manual selections, and let already executing writes finish. A definition pause or
cron skip alone does not stop active dispatch. Use the Runs page and explicit status identities
to enumerate active contexts; do not take only the most recent rows. Keep the holds if draining
fails. Only then start SI_MAINTENANCE with an explicit run key.

The nine SQL_SCRIPT tasks explicitly cover the 32 lake tables, including Gamma signals.
They use RETRY_ON=NONE: statements commit independently, so inspect a failed statement before
any explicit retry. Trino's ALTER TABLE EXECUTE is opaque to the generic parser; validate
reports parser diagnostics but cannot infer the managed-target overlap warning here. The
independent inventory test checks every registered table plus the signal table. Operator
holds/draining remain required. Native execution and full attempt statement logs are authoritative.

After success, release the exact holds and resume each paused definition. Scheduled clients
and DM use `--then wait`; unscheduled reference/setup/steward definitions do not use `--then`.
Resume any guarded task definitions too. A held Gamma wait keeps its original 55-minute
deadline; if it expired while held, it ends SKIPPED when evaluated, without a failure alert.
The workflow/runner that automates this procedure remains S8.E.

Run `tests/test_maintenance_contract.py` for the explicit table/routine inventory and retry
policy. The live `tests/test_maintenance_rows.py` takes SI_MAINTENANCE_INPUTS containing the
exact maintenance `status`, `before` row snapshots, `gamma_before`/`gamma_after` status snapshots
and `writer_count_before`. It checks nine successful first attempts, unchanged selected
business row identities/hashes and the preserved Gamma wait start/deadline. Full historical
snapshot-retention acceptance stays in S8.H.

Local final-slice validation used the pinned package commit above: setup run 135 created/checked
26 targets; business run 144 admitted two USER uploaders together and the independent oracle
verified attribution through ODS. Three reference corrections refreshed DWH history; restore/
unlock batches and DM runs 145/156 matched independent expectations. Maintenance run 158
completed all nine tasks on their first attempts (96 explicit statements), with no active
writer, unchanged selected row identities/hashes and Gamma run 157's original wait budget
preserved. The temporary holds and definition pauses were released afterward. Validation
checked all 11 pipelines and 108 tasks with zero failures/warnings.
