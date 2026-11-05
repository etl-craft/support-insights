SELECT
    s.support_area_id AS support_area_id,
    d.support_area_name AS support_area_name,
    s.source_id AS source_id,
    d.description AS description,
    d.is_active AS is_active,
    s.source_record_id AS source_record_id,
    s.source_pipeline_run_id AS source_pipeline_run_id,
    s.source_task_run_id AS source_task_run_id,
    s.upload_id AS upload_id,
    CAST(s.locked AS BOOLEAN) AS locked
FROM pre_ods.customer_support_stage AS s
JOIN ds.support_areas AS d
    ON d.support_area_id = s.support_area_id
WHERE
    s.load_source = 'STEWARD'
    AND NOT CAST(s.row_id AS VARCHAR) IN ($$rule_flags(steward_rules, REJECT))
