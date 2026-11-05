SELECT
    customer_type_id,
    customer_type_name,
    source_id,
    description,
    is_active,
    upload_id,
    CAST(locked AS BOOLEAN) AS locked
FROM lnd.steward_ds_customer_types
WHERE
    pipeline_run_id = $$pipeline_run_id
