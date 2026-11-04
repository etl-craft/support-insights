# Support Insights pipelines

The config CSVs define execution order. SQL files contain one read-only SELECT per managed
write. Python
scripts only read sources and publish their declared landing batches.

Alpha/Beta run every 15 minutes and Gamma every five minutes, outside 02:00–03:00 UTC.
SI_DM runs every six hours over committed ODS windows; it has no client success gate.
SI_REFERENCE runs after seed deployment.

Each client keeps raw fields in PRS history, opens current-run CDC rows, replaces only its
PRE_ODS slice, then evaluates row rules. Only REJECT rows are excluded from ODS;
INCOMPLETE and REPORT rows remain eligible. Rules read this run's rows and the SQL consumers read this run's
committed flags. Business stewardship follows in its own slice.

The source supplies customer types, not customer identities; the ODS therefore normalizes
interactions, agents, support areas and customer types. DM expands changed lookup entities to
all affected interaction keys before joining the latest committed ODS rows.

Bootstrap applies config without columns.csv, creates targets through SI_SETUP and seeds
through seed apply, then applies the full physical landing contracts. Subsequent schema
changes follow the same setup-before-contract sequence. The source column contracts include
engine provenance because refresh validates the entire physical source shape.

`tests/fixtures/generator-records.json` captures one valid output of each retained generator
at 2026-11-04 12:00:00 UTC, random seed 15, business key 9000 (assigned to isolate this fixture from random batches), with the first source-specific agent, support area and customer type from the original DS inserts.
The fixture also contains a parseable negative-duration REJECT row (9001) and a missing-agent
INCOMPLETE row (9002). The live check asserts all three reach PRE_ODS, and only the reject
is absent from ODS.
`tests/pipeline_oracle.py` computes the expected business row from these source fields using
Python alone; it imports no package code and reads no project SQL. Live tests in
`tests/test_pipeline_rows.py` compare scoped target rows after the corresponding pipeline run.
`SI_ORACLE_INPUTS` names the captured input manifest and `SI_TRINO_HOST`/`SI_TRINO_PORT` select
the warehouse connection. The full acceptance runner and mixed-quality cases remain S8.F/H.

The DS seeds reproduce `infra/sql/13_ds_schema_tables_inserts.sql` from
`venkatcg00/Supports-Insights-Docker` at `ed13f16c34252109ee87241c383cff361a00336f`:
3 sources and 30 rows in each stewarded lookup. The source INSERT order supplies their
original SERIAL identities. Source-specific names and codes remain unchanged.

Stewarded seed tables declare a nullable `upload_id`, omitted from `data.csv` and initially NULL; it is provenance
metadata for the first upload, not an additional source business value. All original DS
business fields, records and identities are checked against the legacy inserts.

Each generator accepts `--rejectable` after the batch count. This preserves the existing
batch/daily caps and emits negative interaction durations (including generated updates).
Durations stay syntactically valid in each source format, so they parse into negative
PRE_ODS values. The `negative_duration` REJECT rule flags those keys; invalid identity and rating rules are
separate. Only REJECT rows are excluded from ODS; INCOMPLETE and REPORT rows remain eligible.
For example: `python generators/client_beta_data_generator.py 3 --rejectable`.

## Reserved maintenance window

Client schedules skip 02:00–03:00 UTC. Before maintenance, pause the client definitions,
hold every active run (including a waiting Gamma run), and wait for active writers to finish.
Release the exact holds and resume scheduled definitions with `--then wait` afterward.
Gamma retains its original 55-minute deadline while held; an expired idle wait ends SKIPPED
without an alert. The maintenance pipeline and its full walkthrough ship in the later slice.

The Iceberg REST fixture uses one JDBC catalog connection (`CATALOG_CLIENTS=1`) for its
SQLite metadata database, WAL mode and a bounded 30-second busy timeout. This serializes
catalog database access while agent tasks and lake I/O remain concurrent. A larger catalog
backend belongs to a different deployment design.

The controller and both UI copies read their host configuration under the shared project
PVC mount. Its `uploads/` and `processed_uploads/` directories therefore support atomic
rename within one mount. Upload receipts survive pod replacement, and every API copy can serve the
exact receipt to an admitted agent. Source credentials stay in the controller/API FILE
provider; ingestion scripts declare SECRETS and call `task.secret()`. Agents receive only
the declared values for their fenced attempt through the private task-process pipe.
