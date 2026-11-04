SELECT
    p.source_system_identifier,
    p.source_timestamp,
    p.support_identifier,
    p.contact_regarding,
    p.agent_code,
    p.date_of_interaction,
    p.status_of_interaction,
    p.type_of_interaction,
    p.customer_type,
    p.contact_duration,
    p.after_contact_work_time,
    p.incident_status,
    p.first_contact_solve,
    p.type_of_resolution,
    p.support_rating,
    p.time_stamp,
    p.source_partition,
    p.source_offset
FROM prs.client_beta_cs_data AS p
WHERE
    p.ACTIVE_FLAG = 'Y' AND p.pipeline_run_id = $$pipeline_run_id
