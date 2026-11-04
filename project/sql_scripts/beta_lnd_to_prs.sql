SELECT
    source_system_identifier,
    source_timestamp,
    support_identifier,
    contact_regarding,
    agent_code,
    date_of_interaction,
    status_of_interaction,
    type_of_interaction,
    customer_type,
    contact_duration,
    after_contact_work_time,
    incident_status,
    first_contact_solve,
    type_of_resolution,
    support_rating,
    time_stamp,
    source_partition,
    source_offset
FROM lnd.client_beta_cs_data
WHERE
    pipeline_run_id = $$pipeline_run_id
