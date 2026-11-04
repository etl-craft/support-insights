SELECT
    CAST(NULL AS BIGINT) AS source_id,
    CAST(NULL AS VARCHAR) AS source_system_identifier,
    CAST(NULL AS BIGINT) AS agent_id,
    CAST(NULL AS TIMESTAMP(6)) AS interaction_date,
    CAST(NULL AS BIGINT) AS support_area_id,
    CAST(NULL AS VARCHAR) AS interaction_status,
    CAST(NULL AS VARCHAR) AS interaction_type,
    CAST(NULL AS BIGINT) AS customer_type_id,
    CAST(NULL AS BIGINT) AS handle_time,
    CAST(NULL AS BIGINT) AS work_time,
    CAST(NULL AS BOOLEAN) AS first_contact_resolution,
    CAST(NULL AS VARCHAR) AS query_status,
    CAST(NULL AS VARCHAR) AS solution_type,
    CAST(NULL AS BIGINT) AS customer_rating,
    CAST(NULL AS VARCHAR) AS agent_name,
    CAST(NULL AS VARCHAR) AS support_area_name,
    CAST(NULL AS VARCHAR) AS customer_type_name,
    CAST(NULL AS BIGINT) AS source_record_id,
    CAST(NULL AS BIGINT) AS source_pipeline_run_id,
    CAST(NULL AS BIGINT) AS source_task_run_id,
    CAST(NULL AS TIMESTAMP(6) WITH TIME ZONE) AS ods_changed_at
WHERE
    1 = 0
