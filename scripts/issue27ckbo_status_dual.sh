#!/bin/bash
set -euo pipefail

BUNDLE_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BASE=${CKBO_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}

for partition in amd intel; do
  id_file="$BUNDLE_ROOT/ckbo_${partition}_job_id.txt"
  if ! test -s "$id_file"; then
    echo "=== $partition: no submitted job id ==="
    continue
  fi
  job_id=$(tr -d '\r\n' < "$id_file")
  echo "=== $partition job $job_id ==="
  squeue -j "$job_id" -o "%.18i %.9P %.24j %.10T %.10M %.10l %.6D %R" || true
  sacct -j "$job_id" --format=JobID,JobName%24,Partition,State,ExitCode,Elapsed,TotalCPU,MaxRSS,ReqMem,AllocCPUS -X || true
  echo "--- progress ---"
  run_root="$BASE/runs/issue27ckbo_mature_afterimage_transfer_v1_2026-07-15_seed27_${partition}_${job_id}"
  find "$run_root/aux_afterimage_cache" -maxdepth 1 -name '*.npz' -type f 2>/dev/null | wc -l || true
  test -s "$run_root/ckbo_single_seed_go_no_go.json" && cat "$run_root/ckbo_single_seed_go_no_go.json" || true
  echo "--- stdout tail ---"
  tail -n 30 "$BASE/runs/issue27ckbo_${partition}_${job_id}.out" 2>/dev/null || true
  echo "--- stderr tail ---"
  tail -n 30 "$BASE/runs/issue27ckbo_${partition}_${job_id}.err" 2>/dev/null || true
done
