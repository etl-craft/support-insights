SELECT
    d.source_id
FROM dwh.ds_sources AS d
WHERE
    d.ACTIVE_FLAG = 'Y'
    AND NOT EXISTS(
        SELECT
            1
        FROM ds.sources AS s
        WHERE
            s.source_id = d.source_id
    )
