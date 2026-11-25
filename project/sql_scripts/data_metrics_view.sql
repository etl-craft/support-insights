-- For each successful client run, valid_count is the audited INSERT_COUNT of the
-- successful PRE_ODS append attempt minus that run's distinct REJECT keys.
-- load_reject_count sums REJECT_COUNT from successful ingestion-to-PRE_ODS load
-- attempts. checked_count is the audited PRE_ODS row count plus load_reject_count.
-- Validity percentage (data_quality_score) is 100 * valid_count / checked_count,
-- or NULL when checked_count is zero. Duplicates are reported separately.
-- PRE_ODS is replaced by subsequent runs.
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
), load_tasks (pipeline_code, task_code, writes_preods) AS (
    VALUES
        ('SI_CLIENT_ALPHA', 'alpha_lnd_to_prs', FALSE),
        ('SI_CLIENT_ALPHA', 'alpha_prs_to_cdc', FALSE),
        ('SI_CLIENT_ALPHA', 'alpha_cdc_to_preods', TRUE),
        ('SI_CLIENT_BETA', 'beta_lnd_to_prs', FALSE),
        ('SI_CLIENT_BETA', 'beta_prs_to_cdc', FALSE),
        ('SI_CLIENT_BETA', 'beta_cdc_to_preods', TRUE),
        ('SI_CLIENT_GAMMA', 'gamma_lnd_to_prs', FALSE),
        ('SI_CLIENT_GAMMA', 'gamma_prs_to_cdc', FALSE),
        ('SI_CLIENT_GAMMA', 'gamma_cdc_to_preods', TRUE)
), successful_load_attempts AS (
    SELECT
        t.pipeline_run_id,
        t.task_run_id,
        MAX_BY(CASE WHEN d.writes_preods THEN a.insert_count ELSE 0 END, a.attempt_number)
            AS stage_count,
        MAX_BY(COALESCE(a.reject_count, 0), a.attempt_number) AS load_reject_count
    FROM aud_mirror.aud_task_run_log AS t
    JOIN tasks AS k
        ON k.task_id = t.task_id
    JOIN load_tasks AS d
        ON d.pipeline_code = k.pipeline_code AND d.task_code = k.task_code
    JOIN aud_mirror.aud_task_attempts AS a
        ON a.task_run_id = t.task_run_id
    WHERE t.status = 'SUCCESS' AND a.status = 'SUCCESS'
    GROUP BY t.pipeline_run_id, t.task_run_id
), staged AS (
    SELECT
        pipeline_run_id,
        SUM(stage_count) AS stage_count,
        SUM(load_reject_count) AS load_reject_count
    FROM successful_load_attempts
    GROUP BY pipeline_run_id
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
        AND r.target_catalog_name = 'warehouse'
        AND r.target_schema_name = 'pre_ods'
        AND r.target_table_name = 'customer_support_stage'
    GROUP BY t.pipeline_run_id
)
SELECT
    runs.pipeline_run_id AS dag_run_id,
    runs.source_name AS source_name,
    runs.run_start_date AS run_start_date,
    COALESCE(ingestion.batch_count, 0) AS batch_count,
    COALESCE(versions.insert_count - versions.update_count, 0) AS insert_count,
    COALESCE(versions.update_count, 0) AS update_count,
    COALESCE(versions.duplicate_count, 0) AS duplicate_count,
    COALESCE(staged.load_reject_count, 0) AS load_reject_count,
    COALESCE(staged.stage_count, 0) - COALESCE(rejected.rejected_count, 0) AS valid_count,
    CAST(100 AS DOUBLE)
        * (COALESCE(staged.stage_count, 0) - COALESCE(rejected.rejected_count, 0))
        / NULLIF(COALESCE(staged.stage_count, 0) + COALESCE(staged.load_reject_count, 0), 0) AS data_quality_score,
    COALESCE(runs.run_duration_sec, 0.0) AS run_duration_sec
FROM runs
LEFT JOIN ingestion
    ON ingestion.pipeline_run_id = runs.pipeline_run_id
LEFT JOIN versions
    ON versions.pipeline_run_id = runs.pipeline_run_id
LEFT JOIN staged
    ON staged.pipeline_run_id = runs.pipeline_run_id
LEFT JOIN rejected
    ON rejected.pipeline_run_id = runs.pipeline_run_id
