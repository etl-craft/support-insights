SELECT
    p.source_system_identifier,
    p.source_timestamp,
    p.interaction_id,
    p.support_category,
    p.agent_pseudo_name,
    p.contact_date,
    p.interaction_status,
    p.interaction_type,
    p.type_of_customer,
    p.interaction_duration,
    p.total_time,
    p.status_of_customer_incident,
    p.resolved_in_first_contact,
    p.solution_type,
    p.rating,
    p.serial_number
FROM prs.client_alpha_cs_data AS p
WHERE
    p.ACTIVE_FLAG = 'Y' AND p.pipeline_run_id = $$pipeline_run_id
