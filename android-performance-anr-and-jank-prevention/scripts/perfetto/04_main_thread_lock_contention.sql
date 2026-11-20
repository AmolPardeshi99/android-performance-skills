-- Lock contention where the blocked thread is a main thread.
-- If a column is missing in your trace_processor version, run
-- SELECT * FROM android_monitor_contention LIMIT 1; and adjust.
INCLUDE PERFETTO MODULE android.monitor_contention;

SELECT
  process_name,
  blocking_thread_name,
  short_blocked_method,
  short_blocking_method,
  ROUND(dur / 1e6, 1) AS dur_ms
FROM android_monitor_contention
WHERE is_blocked_thread_main
ORDER BY dur DESC
LIMIT 30;
