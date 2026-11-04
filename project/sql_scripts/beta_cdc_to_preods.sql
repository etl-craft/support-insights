SELECT
    src.source_id AS source_id,
    c.source_system_identifier AS source_system_identifier,
    a.agent_id AS agent_id,
    TRY(DATE_PARSE(c.date_of_interaction, '%Y%m%d%H%i%s')) AS interaction_date,
    s.support_area_id AS support_area_id,
    CASE c.status_of_interaction
        WHEN 'INTERACTION COMPLETED' THEN 'COMPLETED'
        WHEN 'CUSTOMER DROPPED' THEN 'DROPPED'
        ELSE c.status_of_interaction
    END AS interaction_status,
    c.type_of_interaction AS interaction_type,
    t.customer_type_id AS customer_type_id,
    (
        TRY_CAST(SPLIT_PART(c.contact_duration, ':', 1) AS BIGINT) * 3600
        + TRY_CAST(SPLIT_PART(c.contact_duration, ':', 2) AS BIGINT) * 60
        + TRY_CAST(SPLIT_PART(c.contact_duration, ':', 3) AS BIGINT)
    ) AS handle_time,
    (
        TRY_CAST(SPLIT_PART(c.after_contact_work_time, ':', 1) AS BIGINT) * 3600
        + TRY_CAST(SPLIT_PART(c.after_contact_work_time, ':', 2) AS BIGINT) * 60
        + TRY_CAST(SPLIT_PART(c.after_contact_work_time, ':', 3) AS BIGINT)
    ) AS work_time,
    CASE c.first_contact_solve
        WHEN 'TRUE' THEN TRUE
        WHEN 'FALSE' THEN FALSE
    END AS first_contact_resolution,
    c.incident_status AS query_status,
    c.type_of_resolution AS solution_type,
    TRY_CAST(c.support_rating AS BIGINT) AS customer_rating,
    'BETA' AS load_source,
    c.row_id AS source_record_id,
    c.pipeline_run_id AS source_pipeline_run_id,
    c.task_run_id AS source_task_run_id,
    CAST(NULL AS BIGINT) AS upload_id,
    CAST(NULL AS BOOLEAN) AS locked
FROM cdc.client_beta_cs_data AS c
LEFT JOIN ds.sources AS src
    ON src.source_name = 'CLIENT_BETA' AND src.is_active
LEFT JOIN ds.agents AS a
    ON a.pseudo_code = c.agent_code
    AND a.source_id = src.source_id
    AND a.is_active
LEFT JOIN ds.support_areas AS s
    ON s.support_area_name = c.contact_regarding
    AND s.source_id = src.source_id
    AND s.is_active
LEFT JOIN ds.customer_types AS t
    ON t.customer_type_name = c.customer_type
    AND t.source_id = src.source_id
    AND t.is_active
