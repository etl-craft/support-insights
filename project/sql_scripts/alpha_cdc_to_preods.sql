SELECT
    src.source_id AS source_id,
    c.source_system_identifier AS source_system_identifier,
    a.agent_id AS agent_id,
    TRY(DATE_PARSE(c.contact_date, '%d/%m/%Y %T')) AS interaction_date,
    s.support_area_id AS support_area_id,
    c.interaction_status AS interaction_status,
    c.interaction_type AS interaction_type,
    t.customer_type_id AS customer_type_id,
    TRY_CAST(c.interaction_duration AS BIGINT) AS handle_time,
    TRY_CAST(c.total_time AS BIGINT) - TRY_CAST(c.interaction_duration AS BIGINT) AS work_time,
    CASE c.resolved_in_first_contact
        WHEN 'YES' THEN TRUE
        WHEN 'NO' THEN FALSE
    END AS first_contact_resolution,
    c.status_of_customer_incident AS query_status,
    c.solution_type AS solution_type,
    CAST(CEIL(TRY_CAST(c.rating AS DOUBLE) / 2) AS BIGINT) AS customer_rating,
    'ALPHA' AS load_source,
    c.row_id AS source_record_id,
    c.pipeline_run_id AS source_pipeline_run_id,
    c.task_run_id AS source_task_run_id,
    CAST(NULL AS BIGINT) AS upload_id,
    CAST(NULL AS BOOLEAN) AS locked
FROM cdc.client_alpha_cs_data AS c
LEFT JOIN ds.sources AS src
    ON src.source_name = 'CLIENT_ALPHA' AND src.is_active
LEFT JOIN ds.agents AS a
    ON a.pseudo_code = c.agent_pseudo_name
    AND a.source_id = src.source_id
    AND a.is_active
LEFT JOIN ds.support_areas AS s
    ON s.support_area_name = c.support_category
    AND s.source_id = src.source_id
    AND s.is_active
LEFT JOIN ds.customer_types AS t
    ON t.customer_type_name = c.type_of_customer
    AND t.source_id = src.source_id
    AND t.is_active
