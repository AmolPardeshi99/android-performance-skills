-- App startups in the trace, and the longest main-thread slices inside each one.
INCLUDE PERFETTO MODULE android.startup.startups;

SELECT
  st.startup_id,
  st.package,
  st.startup_type,
  ROUND(st.dur / 1e6, 1) AS startup_ms,
  s.name AS slice,
  ROUND(s.dur / 1e6, 1) AS slice_ms
FROM android_startups st
JOIN process p ON p.name = st.package
JOIN thread t ON t.upid = p.upid AND t.tid = p.pid
JOIN thread_track tt ON tt.utid = t.utid
JOIN slice s ON s.track_id = tt.id
WHERE s.ts >= st.ts
  AND s.ts < st.ts_end
  AND s.depth <= 1
  AND s.dur > 5000000
ORDER BY st.startup_id, s.dur DESC
LIMIT 60;
