SELECT
    p.source_id,
    p.source_system_identifier,
    p.agent_id,
    p.interaction_date,
    p.support_area_id,
    p.interaction_status,
    p.interaction_type,
    p.customer_type_id,
    p.handle_time,
    p.work_time,
    p.first_contact_resolution,
    p.query_status,
    p.solution_type,
    p.customer_rating,
    l.upload_id,
    l.locked
FROM prs.steward_cs_data AS p
JOIN (
    SELECT
        r.*,
        ROW_NUMBER() OVER (PARTITION BY source_id, source_system_identifier ORDER BY upload_id DESC) AS receipt_order
    FROM lnd.steward_cs_data AS r
    WHERE
        pipeline_run_id = $$pipeline_run_id
) AS l
    ON l.source_id = p.source_id
    AND l.source_system_identifier = p.source_system_identifier
WHERE
    p.ACTIVE_FLAG = 'Y' AND l.receipt_order = 1
