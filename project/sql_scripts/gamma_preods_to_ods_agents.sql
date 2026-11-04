SELECT
    s.agent_id AS agent_id,
    d.first_name AS first_name,
    d.middle_name AS middle_name,
    d.last_name AS last_name,
    d.pseudo_code AS pseudo_code,
    s.source_id AS source_id,
    d.is_active AS is_active,
    s.source_record_id AS source_record_id,
    s.source_pipeline_run_id AS source_pipeline_run_id,
    s.source_task_run_id AS source_task_run_id,
    CAST(NULL AS BIGINT) AS upload_id
FROM pre_ods.customer_support_stage AS s
JOIN ds.agents AS d
    ON d.agent_id = s.agent_id
WHERE
    s.load_source = 'GAMMA'
    AND NOT CAST(s.row_id AS VARCHAR) IN ($$rule_flags(gamma_rules, REJECT))
