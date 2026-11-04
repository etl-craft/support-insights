SELECT
    d.agent_id
FROM dwh.ds_agents AS d
WHERE
    d.ACTIVE_FLAG = 'Y'
    AND NOT EXISTS(
        SELECT
            1
        FROM ds.agents AS s
        WHERE
            s.agent_id = d.agent_id
    )
