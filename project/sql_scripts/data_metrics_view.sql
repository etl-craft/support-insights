WITH pipelines AS (
    SELECT
        pipeline_id,
        pipeline_code
    FROM aud_mirror.aud_cfg_pipelines_history
    WHERE current_flag = 'Y'
), tasks AS (
    SELECT
        k.task_id,
        k.task_code,
        p.pipeline_code
    FROM aud_mirror.aud_cfg_tasks_history AS k
    JOIN pipelines AS p
        ON p.pipeline_id = k.pipeline_id
    WHERE k.current_flag = 'Y'
), runs AS (
    SELECT
        r.pipeline_run_id,
        s.source_id,
        s.source_name,
        r.start_date AS run_start_date,
        date_diff('millisecond', r.start_date, r.end_date) / 1000.0 AS run_duration_sec
    FROM aud_mirror.aud_pipelines_run_log AS r
    JOIN pipelines AS p
        ON p.pipeline_id = r.pipeline_id
    JOIN ds.sources AS s
        ON p.pipeline_code = 'SI_' || s.source_name
    WHERE r.status = 'SUCCESS'
), ingestion AS (
    SELECT
        t.pipeline_run_id,
        SUM(t.source_count) AS batch_count
    FROM aud_mirror.aud_task_run_log AS t
    JOIN tasks AS k
        ON k.task_id = t.task_id
        AND k.task_code LIKE '%\_source\_to\_lnd' ESCAPE '\'
    WHERE t.status = 'SUCCESS'
    GROUP BY
        t.pipeline_run_id
), versions AS (
    SELECT
        t.pipeline_run_id,
        SUM(t.insert_count) AS insert_count,
        SUM(t.update_count) AS update_count,
        SUM(t.duplicate_count) AS duplicate_count
    FROM aud_mirror.aud_task_run_log AS t
    JOIN tasks AS k
        ON k.task_id = t.task_id
        AND k.task_code LIKE '%\_lnd\_to\_prs' ESCAPE '\'
    WHERE t.status = 'SUCCESS'
    GROUP BY
        t.pipeline_run_id
), valid AS (
    SELECT
        source_pipeline_run_id AS pipeline_run_id,
        COUNT(*) AS valid_count
    FROM ods.interactions
    GROUP BY
        source_pipeline_run_id
), rejected AS (
    SELECT
        t.pipeline_run_id,
        COUNT(DISTINCT r.business_rule_key) AS rejected_count
    FROM aud_mirror.aud_business_rules_results AS r
    JOIN aud_mirror.aud_business_rules_run_log AS l
        ON l.business_rule_run_id = r.business_rule_run_id
    JOIN aud_mirror.aud_task_run_log AS t
        ON t.task_run_id = l.task_run_id
    WHERE r.status = 'REJECT'
    GROUP BY
        t.pipeline_run_id
)
SELECT
    runs.pipeline_run_id AS dag_run_id,
    runs.source_name AS source_name,
    runs.run_start_date AS run_start_date,
    COALESCE(ingestion.batch_count, 0) AS batch_count,
    COALESCE(versions.insert_count - versions.update_count, 0) AS insert_count,
    COALESCE(versions.update_count, 0) AS update_count,
    COALESCE(versions.duplicate_count, 0) AS duplicate_count,
    COALESCE(valid.valid_count, 0) AS valid_count,
    COALESCE(
        100.0 * valid.valid_count / NULLIF(valid.valid_count + COALESCE(rejected.rejected_count, 0), 0),
        0.0
    ) AS data_quality_score,
    COALESCE(runs.run_duration_sec, 0.0) AS run_duration_sec
FROM runs
LEFT JOIN ingestion
    ON ingestion.pipeline_run_id = runs.pipeline_run_id
LEFT JOIN versions
    ON versions.pipeline_run_id = runs.pipeline_run_id
LEFT JOIN valid
    ON valid.pipeline_run_id = runs.pipeline_run_id
LEFT JOIN rejected
    ON rejected.pipeline_run_id = runs.pipeline_run_id
