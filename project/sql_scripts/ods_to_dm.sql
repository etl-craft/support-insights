WITH changes AS (
    SELECT
        i.source_id,
        i.source_system_identifier,
        i.update_date AS changed_at
    FROM ods.interactions AS i
    WHERE
        i.update_date >= $$watermark AND i.update_date < $$watermark_max
    UNION ALL
    SELECT
        i.source_id,
        i.source_system_identifier,
        x.update_date AS changed_at
    FROM ods.interactions AS i
    JOIN ods.agents AS x
        ON x.agent_id = i.agent_id
    WHERE
        x.update_date >= $$watermark AND x.update_date < $$watermark_max
    UNION ALL
    SELECT
        i.source_id,
        i.source_system_identifier,
        x.update_date AS changed_at
    FROM ods.interactions AS i
    JOIN ods.support_areas AS x
        ON x.support_area_id = i.support_area_id
    WHERE
        x.update_date >= $$watermark AND x.update_date < $$watermark_max
    UNION ALL
    SELECT
        i.source_id,
        i.source_system_identifier,
        x.update_date AS changed_at
    FROM ods.interactions AS i
    JOIN ods.customer_types AS x
        ON x.customer_type_id = i.customer_type_id
    WHERE
        x.update_date >= $$watermark AND x.update_date < $$watermark_max
), dirty AS (
    SELECT
        source_id,
        source_system_identifier,
        MAX(changed_at) AS ods_changed_at
    FROM changes
    GROUP BY
        source_id,
        source_system_identifier
)
SELECT
    i.source_id AS source_id,
    i.source_system_identifier AS source_system_identifier,
    i.agent_id AS agent_id,
    i.interaction_date AS interaction_date,
    i.support_area_id AS support_area_id,
    i.interaction_status AS interaction_status,
    i.interaction_type AS interaction_type,
    i.customer_type_id AS customer_type_id,
    i.handle_time AS handle_time,
    i.work_time AS work_time,
    i.first_contact_resolution AS first_contact_resolution,
    i.query_status AS query_status,
    i.solution_type AS solution_type,
    i.customer_rating AS customer_rating,
    CONCAT_WS(' ', a.first_name, a.middle_name, a.last_name) AS agent_name,
    s.support_area_name AS support_area_name,
    c.customer_type_name AS customer_type_name,
    i.source_record_id AS source_record_id,
    i.source_pipeline_run_id AS source_pipeline_run_id,
    i.source_task_run_id AS source_task_run_id,
    k.ods_changed_at AS ods_changed_at
FROM dirty AS k
JOIN ods.interactions AS i
    ON i.source_id = k.source_id
    AND i.source_system_identifier = k.source_system_identifier
LEFT JOIN ods.agents AS a
    ON a.agent_id = i.agent_id
LEFT JOIN ods.support_areas AS s
    ON s.support_area_id = i.support_area_id
LEFT JOIN ods.customer_types AS c
    ON c.customer_type_id = i.customer_type_id
WHERE
    i.update_date < $$watermark_max
    AND (a.agent_id IS NULL OR a.update_date < $$watermark_max)
    AND (s.support_area_id IS NULL OR s.update_date < $$watermark_max)
    AND (c.customer_type_id IS NULL OR c.update_date < $$watermark_max)
