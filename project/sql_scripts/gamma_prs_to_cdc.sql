SELECT
    p.source_system_identifier,
    p.source_timestamp,
    p.ticket_identifier,
    p.support_category,
    p.agent_name,
    p.date_of_call,
    p.call_status,
    p.call_type,
    p.type_of_customer,
    p.duration,
    p.work_time,
    p.ticket_status,
    p.resolved_in_first_contact,
    p.resolution_category,
    p.rating,
    p.source_object,
    p.source_etag,
    p.source_row
FROM prs.client_gamma_cs_data AS p
WHERE
    p.ACTIVE_FLAG = 'Y' AND p.pipeline_run_id = $$pipeline_run_id
