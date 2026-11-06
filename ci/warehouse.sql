-- Local DuckDB counterpart of infra/bootstrap/warehouse.sql and gamma-events.sql for the validate job.
-- The schemas and the one source table that `validate` probes; the file name `warehouse.duckdb` is the catalog.
CREATE SCHEMA IF NOT EXISTS lnd;
CREATE SCHEMA IF NOT EXISTS prs;
CREATE SCHEMA IF NOT EXISTS cdc;
CREATE SCHEMA IF NOT EXISTS pre_ods;
CREATE SCHEMA IF NOT EXISTS ods;
CREATE SCHEMA IF NOT EXISTS dm;
CREATE SCHEMA IF NOT EXISTS dwh;
CREATE SCHEMA IF NOT EXISTS ds;
CREATE SCHEMA IF NOT EXISTS info;
CREATE SCHEMA IF NOT EXISTS vw;
CREATE SCHEMA IF NOT EXISTS aud_mirror;
CREATE TABLE IF NOT EXISTS lnd.gamma_object_events (
    event_key VARCHAR, object_key VARCHAR, etag VARCHAR, size BIGINT, event_time TIMESTAMPTZ
);
