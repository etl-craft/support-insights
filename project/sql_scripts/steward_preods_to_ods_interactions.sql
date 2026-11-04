SELECT
    s.source_id AS source_id,
    s.source_system_identifier AS source_system_identifier,
    s.agent_id AS agent_id,
    s.interaction_date AS interaction_date,
    s.support_area_id AS support_area_id,
    s.interaction_status AS interaction_status,
    s.interaction_type AS interaction_type,
    s.customer_type_id AS customer_type_id,
    s.handle_time AS handle_time,
    s.work_time AS work_time,
    s.first_contact_resolution AS first_contact_resolution,
    s.query_status AS query_status,
    s.solution_type AS solution_type,
    s.customer_rating AS customer_rating,
    s.source_record_id AS source_record_id,
    s.source_pipeline_run_id AS source_pipeline_run_id,
    s.source_task_run_id AS source_task_run_id,
    s.upload_id AS upload_id,
    CAST(s.locked AS BOOLEAN) AS locked
FROM pre_ods.customer_support_stage AS s
WHERE
    s.load_source = 'STEWARD'
    AND NOT CAST(s.row_id AS VARCHAR) IN ($$rule_flags(steward_rules, REJECT))
