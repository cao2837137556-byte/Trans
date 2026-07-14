#!/bin/bash
set -euo pipefail

HERE=$(cd "$(dirname "$0")/../.." && pwd)
if test -s "$HERE/ckbk_seed27_amd_job_id.txt"; then
  AMD_JOB=$(tr -d '\r\n' < "$HERE/ckbk_seed27_amd_job_id.txt")
else
  AMD_JOB=${CKBK_AMD_JOB_ID:-}
fi
if test -s "$HERE/ckbk_seed27_intel_job_id.txt"; then
  INTEL_JOB=$(tr -d '\r\n' < "$HERE/ckbk_seed27_intel_job_id.txt")
else
  INTEL_JOB=${CKBK_INTEL_JOB_ID:-}
fi
[[ "$AMD_JOB" =~ ^[0-9]+$ ]] || { echo "missing AMD job id" >&2; exit 2; }
[[ "$INTEL_JOB" =~ ^[0-9]+$ ]] || { echo "missing Intel job id" >&2; exit 2; }

echo "=== live queue ==="
squeue -j "$AMD_JOB,$INTEL_JOB" -o "%.18i %.10P %.24j %.10T %.10M %.10l %.6D %R" || true
echo "=== accounting ==="
sacct -j "$AMD_JOB,$INTEL_JOB" -X --format=JobID,JobName%24,Partition,State,ExitCode,Elapsed,TotalCPU,MaxRSS,Start,End
echo "=== estimated starts ==="
squeue --start -j "$AMD_JOB,$INTEL_JOB" || true
echo "=== priorities ==="
sprio -j "$AMD_JOB,$INTEL_JOB" || true
