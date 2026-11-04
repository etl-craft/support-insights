SELECT
    support_area_id,
    support_area_name,
    source_id,
    description,
    is_active,
    upload_id,
    CAST(locked AS BOOLEAN) AS locked
FROM lnd.steward_ds_support_areas
WHERE
    pipeline_run_id = $$pipeline_run_id
