SELECT
    d.customer_type_id
FROM dwh.ds_customer_types AS d
WHERE
    d.ACTIVE_FLAG = 'Y'
    AND NOT EXISTS(
        SELECT
            1
        FROM ds.customer_types AS s
        WHERE
            s.customer_type_id = d.customer_type_id
    )
