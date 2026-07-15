#!/bin/bash
set -u

BUNDLE_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BASE=${CKBP_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}

show_one() {
  partition=$1
  id_file="$BUNDLE_ROOT/ckbp_${partition}_job_id.txt"
  if ! test -s "$id_file"; then
    echo "=== $partition: job id not recorded ==="
    return
  fi
  job_id=$(tr -d '\r\n' < "$id_file")
  case "$job_id" in ''|*[!0-9]*) echo "=== $partition: invalid job id in $id_file ==="; return;; esac
  run_root="$BASE/runs/issue27ckbp_source_local_normal_calibration_v1_2026-07-15_seed27_${partition}_${job_id}"
  echo "=== $partition / $job_id ==="
  squeue -j "$job_id" -o "%.18i %.9P %.22j %.10T %.10M %.10l %.6D %R" 2>/dev/null || true
  sacct -j "$job_id" -X --format=JobID,JobName%20,Partition,State,ExitCode,Elapsed,MaxRSS,ReqMem,AllocCPUS,Start,End 2>/dev/null || true
  if test -s "$run_root/ckbp_single_seed_go_no_go.json"; then
    echo "--- scientific decision ---"
    cat "$run_root/ckbp_single_seed_go_no_go.json"
  elif test -s "$run_root/job_failure.txt"; then
    echo "--- failure marker ---"
    cat "$run_root/job_failure.txt"
  else
    echo "--- latest stdout ---"
    tail -n 30 "$BASE/runs/issue27ckbp_${partition}_${job_id}.out" 2>/dev/null || true
    echo "--- latest stderr ---"
    tail -n 30 "$BASE/runs/issue27ckbp_${partition}_${job_id}.err" 2>/dev/null || true
  fi
}

show_one amd
show_one intel
