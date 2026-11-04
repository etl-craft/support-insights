SELECT
    load_source,
    source_id,
    source_system_identifier
FROM pre_ods.customer_support_stage
WHERE
    load_source = 'BETA'
