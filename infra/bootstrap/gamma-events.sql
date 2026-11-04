-- S8.B EVENT_SQL: one result row per object version, despite repeated notifications.
-- EVENT_KEY_COLUMN=event_key; downstream reads object_key from task.event_rows.
SELECT event_key AS event_key, object_key AS object_key, etag AS etag, max(size) AS size, max(event_time) AS event_time
FROM warehouse.lnd.gamma_object_events
GROUP BY event_key, object_key, etag;
