#!/usr/bin/env bash
# Runs every .sql file in this folder against a Perfetto trace and prints the results.
# Usage: run_queries.sh <trace-file> [query-file ...]
# Needs trace_processor_shell (or trace_processor) on PATH. Get it from
# https://perfetto.dev/docs/analysis/trace-processor
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <trace-file> [query-file ...]" >&2
  exit 2
fi

trace="$1"; shift
if [[ ! -f "$trace" ]]; then
  echo "Trace not found: $trace" >&2
  exit 2
fi

tp=""
for candidate in trace_processor_shell trace_processor; do
  if command -v "$candidate" >/dev/null 2>&1; then tp="$candidate"; break; fi
done
if [[ -z "$tp" ]]; then
  echo "trace_processor_shell not found on PATH." >&2
  echo "Install it from https://perfetto.dev/docs/analysis/trace-processor and retry." >&2
  exit 3
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -gt 0 ]]; then queries=("$@"); else queries=("$here"/*.sql); fi

for q in "${queries[@]}"; do
  echo "=== $(basename "$q")"
  if ! "$tp" --query-file "$q" "$trace" 2>&1 | grep -v '^\[' ; then
    echo "(query failed or returned nothing)"
  fi
  echo
done
