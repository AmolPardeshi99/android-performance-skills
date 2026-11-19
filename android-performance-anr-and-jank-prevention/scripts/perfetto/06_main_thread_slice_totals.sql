-- Total and max time per slice name on main threads. Good for spotting repeated costs:
-- inflate, Lock contention, bindApplication, activityStart, your own trace sections.
SELECT
  p.name AS process,
  s.name AS slice,
  COUNT(*) AS count,
  ROUND(SUM(s.dur) / 1e6, 1) AS total_ms,
  ROUND(MAX(s.dur) / 1e6, 1) AS max_ms
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
JOIN process p ON t.upid = p.upid
WHERE t.tid = p.pid
GROUP BY p.name, s.name
HAVING total_ms > 20
ORDER BY total_ms DESC
LIMIT 40;
