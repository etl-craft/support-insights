SELECT
    s.support_area_id AS support_area_id,
    d.support_area_name AS support_area_name,
    s.source_id AS source_id,
    d.description AS description,
    d.is_active AS is_active,
    s.source_record_id AS source_record_id,
    s.source_pipeline_run_id AS source_pipeline_run_id,
    s.source_task_run_id AS source_task_run_id,
    CAST(NULL AS BIGINT) AS upload_id
FROM pre_ods.customer_support_stage AS s
JOIN ds.support_areas AS d
    ON d.support_area_id = s.support_area_id
WHERE
    s.load_source = 'BETA'
    AND NOT CAST(s.row_id AS VARCHAR) IN ($$rule_flags(beta_rules, REJECT))
