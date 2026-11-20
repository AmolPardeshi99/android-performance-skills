-- Top-level slices on each process's main thread longer than one 60 Hz frame (16 ms).
SELECT
  p.name AS process,
  s.name AS slice,
  ROUND(s.dur / 1e6, 1) AS dur_ms,
  s.ts
FROM slice s
JOIN thread_track tt ON s.track_id = tt.id
JOIN thread t ON tt.utid = t.utid
JOIN process p ON t.upid = p.upid
WHERE t.tid = p.pid
  AND s.depth = 0
  AND s.dur > 16000000
ORDER BY s.dur DESC
LIMIT 50;
