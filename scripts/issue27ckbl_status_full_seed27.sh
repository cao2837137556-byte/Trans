#!/bin/bash
set -euo pipefail

BASE=${CKBL_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
HERE=$(cd "$(dirname "$0")/../.." && pwd)

job_for() {
  local partition=$1
  local record="$HERE/ckbl_full_seed27_${partition}_job_id.txt"
  test -s "$record" || { echo "missing $partition job id: $record" >&2; exit 2; }
  tr -d '\r\n' < "$record"
}

AMD_JOB=$(job_for amd)
INTEL_JOB=$(job_for intel)
[[ "$AMD_JOB" =~ ^[0-9]+$ ]] || { echo "invalid AMD job id" >&2; exit 2; }
[[ "$INTEL_JOB" =~ ^[0-9]+$ ]] || { echo "invalid Intel job id" >&2; exit 2; }

echo "=== live queue ==="
squeue -j "$AMD_JOB,$INTEL_JOB" -o "%.18i %.10P %.24j %.10T %.10M %.10l %.6D %R" || true
echo "=== accounting ==="
sacct -j "$AMD_JOB,$INTEL_JOB" -X --format=JobID,JobName%24,Partition,State,ExitCode,Elapsed,TotalCPU,MaxRSS,Start,End
echo "=== estimated starts ==="
squeue --start -j "$AMD_JOB,$INTEL_JOB" || true

for item in "amd:$AMD_JOB" "intel:$INTEL_JOB"; do
  partition=${item%%:*}
  job_id=${item##*:}
  run_root="$BASE/runs/issue27ckbl_frontend_observability_audit_v1_2026-07-14_fullsource_seed27_${partition}_${job_id}"
  echo "=== $partition job $job_id progress ==="
  tail -n 20 "$run_root/source_progress.jsonl" 2>/dev/null || true
  if test -s "$run_root/decision.json"; then
    cat "$run_root/decision.json"
  fi
  echo "--- stdout tail ---"
  tail -n 60 "$BASE/runs/issue27ckbl_full_seed27_${partition}_${job_id}.out" 2>/dev/null || true
  echo "--- stderr tail ---"
  tail -n 60 "$BASE/runs/issue27ckbl_full_seed27_${partition}_${job_id}.err" 2>/dev/null || true
done
