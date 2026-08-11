#!/usr/bin/env bash
set -euo pipefail

JOB=${1:?usage: issue27ckda_d0_status.sh JOB_ID}
BASE=${CKDA_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
PARTITION=amd
RUN_NAME="issue27ckda_d0_representation_compatibility_audit_v1_2026-08-11_${PARTITION}_${JOB}"
RUN="$BASE/runs/$RUN_NAME"
CONTROL="$BASE/runs/${RUN_NAME}_control"
PULLBACK="$BASE/runs/${RUN_NAME}_pullback.tar.gz"

state=$(sacct -j "$JOB" -X -n -P --format=State | head -n 1 | cut -d'|' -f1 | sed 's/+.*//' | tr -d '[:space:]')
echo "===== CKDA D0 JOB ====="
squeue -j "$JOB" -o '%.18i %.9P %.16j %.2t %.10M %.6D %R' || true
sacct -j "$JOB" -X -n -P --format=JobID,State,Elapsed,TotalCPU,MaxRSS,ReqMem,AllocCPUS
echo "===== PHASE ====="
cat "$CONTROL/current_phase.txt" 2>/dev/null || echo "phase marker not created yet"
echo "===== COMPLETED UNITS ====="
find "$BASE/runs" -maxdepth 3 -path "*/source_checkpoints/*.json" -newer "$CONTROL/slurm_identity.txt" -print 2>/dev/null | wc -l || true
echo "===== LOG TAIL ====="
tail -40 "$BASE/runs/issue27ckda_d0_amd_${JOB}.out" 2>/dev/null || true
tail -40 "$BASE/runs/issue27ckda_d0_amd_${JOB}.err" 2>/dev/null || true

case "$state" in
  PENDING|RUNNING|CONFIGURING|COMPLETING)
    echo "CKDA_D0_STILL_ACTIVE state=$state job=$JOB"
    exit 0
    ;;
  COMPLETED)
    test -s "$CONTROL/terminal_success.txt"
    test -s "$RUN/ckda_d0_validation_report.json"
    test -s "$PULLBACK"
    test -s "$PULLBACK.sha256"
    (cd "$BASE/runs" && sha256sum -c "$(basename "$PULLBACK.sha256")")
    echo "CKDA_D0_TERMINAL_PASS job=$JOB pullback=$PULLBACK"
    ;;
  *)
    echo "CKDA_D0_TERMINAL_FAILURE job=$JOB state=${state:-UNKNOWN}" >&2
    cat "$CONTROL/job_failure.txt" 2>/dev/null >&2 || true
    exit 1
    ;;
esac
