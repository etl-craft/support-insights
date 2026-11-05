SELECT
    agent_id,
    first_name,
    middle_name,
    last_name,
    pseudo_code,
    source_id,
    is_active,
    upload_id,
    CAST(locked AS BOOLEAN) AS locked
FROM lnd.steward_ds_agents
WHERE
    pipeline_run_id = $$pipeline_run_id
