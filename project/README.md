# Project skeleton

`craft-connector.yml` targets the shared PostgreSQL Engine DB and Trino/Iceberg warehouse.
Secrets are environment-variable names. The active config, SQL, Python, validation and
migration directories are intentionally empty until S8.B authors the pipelines.

Reference seeds remain under `seeds/warehouse/`. The former package demo's migrations and
scripts are preserved under `../reference/package-demo/`, outside the active project path,
so `etl-craft setup` cannot apply the old pipelines automatically.
