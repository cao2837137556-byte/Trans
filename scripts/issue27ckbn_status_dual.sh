#!/bin/bash
set -euo pipefail

BUNDLE_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BASE=${CKBN_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}

for partition in amd intel; do
  id_file="$BUNDLE_ROOT/ckbn_${partition}_job_id.txt"
  if ! test -s "$id_file"; then
    echo "=== $partition: no submitted job id ==="
    continue
  fi
  job_id=$(tr -d '\r\n' < "$id_file")
  echo "=== $partition job $job_id ==="
  squeue -j "$job_id" -o "%.18i %.9P %.24j %.10T %.10M %.10l %.6D %R" || true
  sacct -j "$job_id" --format=JobID,JobName%24,Partition,State,ExitCode,Elapsed,TotalCPU,MaxRSS,ReqMem,AllocCPUS -X || true
  echo "--- stdout tail ---"
  tail -n 25 "$BASE/runs/issue27ckbn_diag_${partition}_${job_id}.out" 2>/dev/null || true
  echo "--- stderr tail ---"
  tail -n 25 "$BASE/runs/issue27ckbn_diag_${partition}_${job_id}.err" 2>/dev/null || true
done
