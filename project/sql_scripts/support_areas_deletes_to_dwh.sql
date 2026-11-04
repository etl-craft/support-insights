SELECT
    d.support_area_id
FROM dwh.ds_support_areas AS d
WHERE
    d.ACTIVE_FLAG = 'Y'
    AND NOT EXISTS(
        SELECT
            1
        FROM ds.support_areas AS s
        WHERE
            s.support_area_id = d.support_area_id
    )
