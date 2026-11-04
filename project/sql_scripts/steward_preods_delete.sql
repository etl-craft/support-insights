SELECT
    load_source,
    source_id,
    source_system_identifier,
    (
        SELECT
            MIN(upload_id)
        FROM lnd.steward_cs_data
        WHERE
            pipeline_run_id = $$pipeline_run_id
    ) AS upload_id
FROM pre_ods.customer_support_stage
WHERE
    load_source = 'STEWARD'
