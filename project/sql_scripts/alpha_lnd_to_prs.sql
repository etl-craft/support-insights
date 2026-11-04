SELECT
    source_system_identifier,
    source_timestamp,
    interaction_id,
    support_category,
    agent_pseudo_name,
    contact_date,
    interaction_status,
    interaction_type,
    type_of_customer,
    interaction_duration,
    total_time,
    status_of_customer_incident,
    resolved_in_first_contact,
    solution_type,
    rating,
    serial_number
FROM lnd.client_alpha_cs_data
WHERE
    pipeline_run_id = $$pipeline_run_id
