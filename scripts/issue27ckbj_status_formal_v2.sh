#!/bin/bash
# Run from the extracted CKBJ bundle directory after submission.
set -euo pipefail

HERE=$(pwd)
BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
JOB_FILE="$HERE/ckbj_formal_seed27_job_id.txt"
test -s "$JOB_FILE" || { echo "missing job-id file: $JOB_FILE" >&2; exit 2; }
job_id=$(tr -d '\r\n' < "$JOB_FILE")
[[ "$job_id" =~ ^[0-9]+$ ]] || { echo "invalid job id: $job_id" >&2; exit 2; }

echo "=== queue ==="
squeue -j "$job_id" -o "%.18i %.28j %.9T %.10M %.12l %.6D %R" || true
echo "=== accounting ==="
sacct -j "$job_id" --format=JobID,JobName%24,Partition,State,ExitCode,Elapsed,MaxRSS,Start,End -X || true
echo "=== scheduler detail ==="
scontrol show job -o "$job_id" || true
echo "=== stdout tail ==="
if test -f "$BASE/runs/issue27ckbj_m1_v2_${job_id}.out"; then
  tail -n 80 "$BASE/runs/issue27ckbj_m1_v2_${job_id}.out"
elif test -f "$HERE/runs/issue27ckbj_m1_v2_${job_id}.out"; then
  echo "legacy bundle-relative log path"
  tail -n 80 "$HERE/runs/issue27ckbj_m1_v2_${job_id}.out"
else
  echo "stdout log not found"
fi
echo "=== stderr tail ==="
if test -f "$BASE/runs/issue27ckbj_m1_v2_${job_id}.err"; then
  tail -n 80 "$BASE/runs/issue27ckbj_m1_v2_${job_id}.err"
elif test -f "$HERE/runs/issue27ckbj_m1_v2_${job_id}.err"; then
  echo "legacy bundle-relative log path"
  tail -n 80 "$HERE/runs/issue27ckbj_m1_v2_${job_id}.err"
else
  echo "stderr log not found"
fi
