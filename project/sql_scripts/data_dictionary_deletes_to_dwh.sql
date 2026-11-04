SELECT
    d.source_id,
    d.field_name
FROM dwh.info_data_dictionary AS d
WHERE
    d.ACTIVE_FLAG = 'Y'
    AND NOT EXISTS(
        SELECT
            1
        FROM info.data_dictionary AS s
        WHERE
            s.source_id = d.source_id AND s.field_name = d.field_name
    )
