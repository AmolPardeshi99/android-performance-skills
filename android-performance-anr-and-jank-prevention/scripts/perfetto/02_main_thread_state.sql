-- Where each app main thread spent its time: Running, Runnable (waiting for CPU),
-- S (sleeping: locks, Binder, idle looper), D (uninterruptible: usually I/O).
SELECT
  p.name AS process,
  ts.state,
  ROUND(SUM(ts.dur) / 1e6, 1) AS total_ms
FROM thread_state ts
JOIN thread t ON ts.utid = t.utid
JOIN process p ON t.upid = p.upid
WHERE t.tid = p.pid
  AND p.name IS NOT NULL
  AND p.name NOT LIKE '/%'
GROUP BY p.name, ts.state
HAVING total_ms > 50
ORDER BY p.name, total_ms DESC;
