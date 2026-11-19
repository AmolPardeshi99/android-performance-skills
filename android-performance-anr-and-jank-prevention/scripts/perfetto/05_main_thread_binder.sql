-- Synchronous Binder calls made from a main thread, longest first, with the server side.
-- If a column is missing in your trace_processor version, run
-- SELECT * FROM android_binder_txns LIMIT 1; and adjust.
INCLUDE PERFETTO MODULE android.binder;

SELECT
  client_process,
  server_process,
  aidl_name,
  ROUND(client_dur / 1e6, 1) AS client_ms,
  ROUND(server_dur / 1e6, 1) AS server_ms
FROM android_binder_txns
WHERE is_main_thread
ORDER BY client_dur DESC
LIMIT 30;
