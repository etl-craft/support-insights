SELECT
    src.source_id AS source_id,
    c.source_system_identifier AS source_system_identifier,
    a.agent_id AS agent_id,
    TRY(DATE_PARSE(c.date_of_call, '%m%d%Y%H%i%s')) AS interaction_date,
    s.support_area_id AS support_area_id,
    c.call_status AS interaction_status,
    c.call_type AS interaction_type,
    t.customer_type_id AS customer_type_id,
    TRY_CAST(c.duration AS BIGINT) AS handle_time,
    TRY_CAST(c.work_time AS BIGINT) AS work_time,
    CASE c.resolved_in_first_contact
        WHEN '1' THEN TRUE
        WHEN '0' THEN FALSE
    END AS first_contact_resolution,
    c.ticket_status AS query_status,
    c.resolution_category AS solution_type,
    CASE c.rating
        WHEN 'WORST' THEN 1
        WHEN 'BAD' THEN 2
        WHEN 'NEUTRAL' THEN 3
        WHEN 'GOOD' THEN 4
        WHEN 'BEST' THEN 5
    END AS customer_rating,
    'GAMMA' AS load_source,
    c.row_id AS source_record_id,
    c.pipeline_run_id AS source_pipeline_run_id,
    c.task_run_id AS source_task_run_id,
    CAST(NULL AS BIGINT) AS upload_id,
    CAST(NULL AS BOOLEAN) AS locked
FROM cdc.client_gamma_cs_data AS c
LEFT JOIN ds.sources AS src
    ON src.source_name = 'CLIENT_GAMMA' AND src.is_active
LEFT JOIN ds.agents AS a
    ON a.pseudo_code = c.agent_name
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
