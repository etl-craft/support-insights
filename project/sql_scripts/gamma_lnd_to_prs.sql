SELECT
    source_system_identifier,
    source_timestamp,
    ticket_identifier,
    support_category,
    agent_name,
    date_of_call,
    call_status,
    call_type,
    type_of_customer,
    duration,
    work_time,
    ticket_status,
    resolved_in_first_contact,
    resolution_category,
    rating,
    source_object,
    source_etag,
    source_row
FROM lnd.client_gamma_cs_data
WHERE
    pipeline_run_id = $$pipeline_run_id
