#!/usr/bin/env bash
# Captures a Java heap dump (HPROF) from a running debuggable app and pulls it locally.
# Usage: capture_heap_dump.sh <package> [output-file]
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <package> [output-file]" >&2
  exit 2
fi

pkg="$1"
out="${2:-${pkg}-$(date +%Y%m%d-%H%M%S).hprof}"
remote="/data/local/tmp/$(basename "$out")"

command -v adb >/dev/null 2>&1 || { echo "adb not found on PATH" >&2; exit 3; }

pid="$(adb shell pidof "$pkg" | tr -d '\r' || true)"
if [[ -z "$pid" ]]; then
  echo "Process $pkg is not running. Open the app and repeat the journey first." >&2
  exit 4
fi

echo "Dumping heap of $pkg (pid $pid)..."
adb shell am dumpheap "$pkg" "$remote"
# am dumpheap returns before the file is complete on some versions; wait for size to settle.
prev=-1
for _ in $(seq 1 60); do
  size="$(adb shell stat -c %s "$remote" 2>/dev/null | tr -d '\r' || echo 0)"
  if [[ "$size" == "$prev" && "$size" != "0" ]]; then break; fi
  prev="$size"
  sleep 1
done

adb pull "$remote" "$out" >/dev/null
adb shell rm -f "$remote"
echo "Saved $out"
echo "Open in Android Studio, or run: shark-cli --hprof \"$out\" analyze"
