SELECT
    source_id,
    source_system_identifier,
    agent_id,
    interaction_date,
    support_area_id,
    interaction_status,
    interaction_type,
    customer_type_id,
    handle_time,
    work_time,
    first_contact_resolution,
    query_status,
    solution_type,
    customer_rating,
    upload_id,
    CAST(locked AS BOOLEAN) AS locked
FROM lnd.steward_cs_data
WHERE
    pipeline_run_id = $$pipeline_run_id
