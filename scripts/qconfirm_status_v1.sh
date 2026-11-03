#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if test -f submit_claim/job_id.txt; then
  jid=$(cat submit_claim/job_id.txt)
  sacct -j "$jid" --format=JobID,State,ExitCode,Elapsed -X || true
fi
if test -f logs/job_exit.txt; then cat logs/job_exit.txt; fi
latest=$(find runs/confirmation/progress -maxdepth 1 -name '*.json' -type f 2>/dev/null | sort | tail -n 1 || true)
if test -n "$latest"; then cat "$latest"; else echo 'Waiting for allocation / environment / synthetic checks.'; fi
echo 'Feature targets=341270. Optimizer updates remain0. COMPLETE means execution finished; read scientific_gate separately.'
