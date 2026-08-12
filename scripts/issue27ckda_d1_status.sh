#!/usr/bin/env bash
set -euo pipefail

JOB=${1:?usage: issue27ckda_d1_status.sh JOB_ID}
BASE=${CKDA_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
RUN_NAME="issue27ckda_d1_representation_probe_v1_2026-08-12_amd_${JOB}"
RUN="$BASE/runs/$RUN_NAME"
CONTROL="$BASE/runs/${RUN_NAME}_control"
PULLBACK="$BASE/runs/${RUN_NAME}_pullback.tar.gz"
CHECKPOINT="$BASE/runs/issue27ckda_d1_checkpoint_v1_amd_ecb429926507d2c4"

state=$(sacct -j "$JOB" -X -n -P --format=State | head -n 1 | cut -d'|' -f1 | sed 's/+.*//' | tr -d '[:space:]')
echo "===== CKDA D1 JOB ====="
squeue -j "$JOB" -o '%.18i %.9P %.16j %.2t %.10M %.6D %R' || true
sacct -j "$JOB" -X -n -P --format=JobID,State,Elapsed,TotalCPU,MaxRSS,ReqMem,AllocCPUS,MaxDiskRead,MaxDiskWrite
echo "===== PHASE ====="
cat "$CONTROL/current_phase.txt" 2>/dev/null || echo "phase marker not created yet"
echo "===== VALIDATED CHECKPOINT UNITS ====="
find "$CHECKPOINT" -maxdepth 3 -type f \( -name '*.npz' -o -name '*.json' \) 2>/dev/null | wc -l || true
echo "===== FAILURE MARKER ====="
if test -s "$CONTROL/job_failure.txt"; then cat "$CONTROL/job_failure.txt"; else echo "none"; fi
echo "===== LOG TAIL ====="
tail -50 "$BASE/runs/issue27ckda_d1_amd_${JOB}.out" 2>/dev/null || true
tail -50 "$BASE/runs/issue27ckda_d1_amd_${JOB}.err" 2>/dev/null || true

case "$state" in
  PENDING|RUNNING|CONFIGURING|COMPLETING)
    echo "CKDA_D1_STILL_ACTIVE state=$state job=$JOB"
    ;;
  COMPLETED)
    test -s "$CONTROL/terminal_success.txt"
    test -s "$RUN/ckda_d1_validation_report.json"
    test -s "$PULLBACK" && test -s "$PULLBACK.sha256"
    (cd "$BASE/runs" && sha256sum -c "$(basename "$PULLBACK.sha256")")
    echo "CKDA_D1_TERMINAL_PASS job=$JOB pullback=$PULLBACK"
    ;;
  *)
    echo "CKDA_D1_TERMINAL_FAILURE job=$JOB state=${state:-UNKNOWN}" >&2
    cat "$CONTROL/job_failure.txt" 2>/dev/null >&2 || true
    exit 1
    ;;
esac
