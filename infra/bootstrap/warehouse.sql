CREATE SCHEMA IF NOT EXISTS warehouse.lnd WITH (location = 's3://warehouse/lnd/');
CREATE SCHEMA IF NOT EXISTS warehouse.prs WITH (location = 's3://warehouse/prs/');
CREATE SCHEMA IF NOT EXISTS warehouse.cdc WITH (location = 's3://warehouse/cdc/');
CREATE SCHEMA IF NOT EXISTS warehouse.pre_ods WITH (location = 's3://warehouse/pre_ods/');
CREATE SCHEMA IF NOT EXISTS warehouse.ods WITH (location = 's3://warehouse/ods/');
CREATE SCHEMA IF NOT EXISTS warehouse.dm WITH (location = 's3://warehouse/dm/');
CREATE SCHEMA IF NOT EXISTS warehouse.dwh WITH (location = 's3://warehouse/dwh/');
CREATE SCHEMA IF NOT EXISTS warehouse.ds WITH (location = 's3://warehouse/ds/');
CREATE SCHEMA IF NOT EXISTS warehouse.info WITH (location = 's3://warehouse/info/');
CREATE SCHEMA IF NOT EXISTS warehouse.vw WITH (location = 's3://warehouse/vw/');
CREATE SCHEMA IF NOT EXISTS warehouse.aud_mirror WITH (location = 's3://warehouse/aud_mirror/');
CREATE TABLE IF NOT EXISTS warehouse.lnd.gamma_object_events (
    event_key varchar, object_key varchar, etag varchar, size bigint, event_time timestamp(6) with time zone
);
