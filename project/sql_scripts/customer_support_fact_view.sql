WITH rejected AS (
    SELECT DISTINCT
        st.source_id,
        st.source_system_identifier,
        st.pipeline_run_id AS source_pipeline_run_id
    FROM pre_ods.customer_support_stage AS st
    JOIN aud_mirror.aud_business_rules_results AS r
        ON r.business_rule_key = CAST(st.row_id AS VARCHAR)
        AND r.target_schema_name = 'pre_ods'
        AND r.target_table_name = 'customer_support_stage'
        AND r.status = 'REJECT'
        AND r.active_flag = 'Y'
        AND r.end_date IS NULL
), committed AS (
    SELECT
        CAST(MAX_BY(from_iso8601_timestamp(t.watermark_to), t.task_run_id) AS TIMESTAMP(6) WITH TIME ZONE) AS committed_window_end
    FROM aud_mirror.aud_task_run_log AS t
    JOIN aud_mirror.aud_cfg_tasks_history AS k
        ON k.task_id = t.task_id
        AND k.current_flag = 'Y'
        AND k.task_code = 'ods_to_dm'
    JOIN aud_mirror.aud_cfg_pipelines_history AS p
        ON p.pipeline_id = k.pipeline_id
        AND p.current_flag = 'Y'
        AND p.pipeline_code = 'SI_DM'
    WHERE t.status = 'SUCCESS'
)
SELECT
    s.source_name AS source_name,
    f.source_record_id AS source_record_id,
    f.source_system_identifier AS source_system_identifier,
    a.pseudo_code AS pseudo_code,
    f.interaction_date AS interaction_date,
    f.support_area_name AS support_area_name,
    f.interaction_status AS interaction_status,
    f.interaction_type AS interaction_type,
    f.customer_type_name AS customer_type_name,
    f.handle_time AS handle_time,
    f.work_time AS work_time,
    f.first_contact_resolution AS first_contact_resolution,
    f.query_status AS query_status,
    f.solution_type AS solution_type,
    f.customer_rating AS customer_rating,
    f.source_pipeline_run_id AS source_pipeline_run_id,
    f.source_task_run_id AS source_task_run_id,
    o.upload_id AS upload_id,
    u.account AS steward,
    u.file_name AS upload_file_name,
    f.pipeline_run_id AS dm_pipeline_run_id,
    f.task_run_id AS dm_task_run_id,
    f.ods_changed_at AS ods_changed_at,
    c.committed_window_end AS committed_window_end,
    date_diff('second', c.committed_window_end, current_timestamp) AS freshness_seconds
FROM dm.customer_support_fact AS f
CROSS JOIN committed AS c
JOIN ds.sources AS s
    ON s.source_id = f.source_id
LEFT JOIN ds.agents AS a
    ON a.agent_id = f.agent_id
LEFT JOIN ods.interactions AS o
    ON o.source_id = f.source_id
    AND o.source_system_identifier = f.source_system_identifier
LEFT JOIN aud_mirror.aud_uploads AS u
    ON u.upload_id = o.upload_id
LEFT JOIN rejected AS x
    ON x.source_id = f.source_id
    AND x.source_system_identifier = f.source_system_identifier
    AND x.source_pipeline_run_id = f.source_pipeline_run_id
WHERE
    f.active_flag = 'Y'
    AND f.delete_flag = 'N'
    AND x.source_id IS NULL
