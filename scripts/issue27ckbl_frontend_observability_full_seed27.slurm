#!/bin/bash
# CKBL: full-source, full-385-support result-producing observability run.
# Submitted once to AMD and once to Intel; writable paths are job-isolated.
#SBATCH -J ckbl_full
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00

set -euo pipefail

BASE=${CKBL_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
PARTITION=${SLURM_JOB_PARTITION:?missing SLURM_JOB_PARTITION}
JOB_ID=${SLURM_JOB_ID:?missing SLURM_JOB_ID}
RUN_ROOT="$BASE/runs/issue27ckbl_frontend_observability_audit_v1_2026-07-14_fullsource_seed27_${PARTITION}_${JOB_ID}"
CKBL_COMMIT_SHA=${CKBL_COMMIT_SHA:?missing CKBL_COMMIT_SHA}
CKBL_SCRIPT_SHA256=${CKBL_SCRIPT_SHA256:?missing CKBL_SCRIPT_SHA256}
CKAT_SCRIPT_SHA256=${CKAT_SCRIPT_SHA256:?missing CKAT_SCRIPT_SHA256}
export CKBL_COMMIT_SHA

test -d "$BASE" || { echo "missing project directory: $BASE" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing validated environment script" >&2; exit 2; }
test -s "$BASE/repo/ood/issue27ckbl_frontend_observability_audit_v1.py" || { echo "missing CKBL code" >&2; exit 2; }
test -s "$BASE/repo/ood/issue27ckat_canonical_time_c1_canary_v1.py" || { echo "missing CKAT frontend" >&2; exit 2; }
test "$(sha256sum "$BASE/repo/ood/issue27ckbl_frontend_observability_audit_v1.py" | awk '{print $1}')" = "$CKBL_SCRIPT_SHA256" || { echo "installed CKBL hash mismatch" >&2; exit 2; }
test "$(sha256sum "$BASE/repo/ood/issue27ckat_canonical_time_c1_canary_v1.py" | awk '{print $1}')" = "$CKAT_SCRIPT_SHA256" || { echo "installed CKAT hash mismatch" >&2; exit 2; }
test ! -e "$RUN_ROOT" || { echo "refusing to mix existing run root: $RUN_ROOT" >&2; exit 2; }

mkdir -p "$RUN_ROOT"
started_epoch=$(date +%s)
started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
heartbeat_pid=""

cleanup() {
  status=$?
  if test -n "$heartbeat_pid"; then
    kill "$heartbeat_pid" >/dev/null 2>&1 || true
    wait "$heartbeat_pid" >/dev/null 2>&1 || true
  fi
  if test "$status" -ne 0; then
    printf 'status=FAILED\nexit_code=%s\nfailed_utc=%s\n' "$status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      > "$RUN_ROOT/job_failure.txt"
  fi
  exit "$status"
}
trap cleanup EXIT

heartbeat() {
  while true; do
    sleep 300
    printf 'CKBL_HEARTBEAT utc=%s job=%s partition=%s progress_lines=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$JOB_ID" "$PARTITION" \
      "$(wc -l < "$RUN_ROOT/source_progress.jsonl" 2>/dev/null || echo 0)"
  done
}
heartbeat &
heartbeat_pid=$!

cd "$BASE"
source scripts/00_env_issue27ckc.sh
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}

printf 'job_id=%s\npartition=%s\ncommit_sha=%s\nckbl_sha256=%s\nckat_sha256=%s\nstarted_utc=%s\n' \
  "$JOB_ID" "$PARTITION" "$CKBL_COMMIT_SHA" "$CKBL_SCRIPT_SHA256" "$CKAT_SCRIPT_SHA256" "$started_utc" \
  > "$RUN_ROOT/slurm_identity.txt"
scontrol show job -o "$JOB_ID" > "$RUN_ROOT/slurm_job_at_start.txt" 2>/dev/null || true

python - <<'PY' > "$RUN_ROOT/environment.json"
import json, platform
import numpy, pandas, sklearn
print(json.dumps({
    "python": platform.python_version(),
    "numpy": numpy.__version__,
    "pandas": pandas.__version__,
    "scikit_learn": sklearn.__version__,
}, indent=2, sort_keys=True))
PY

python -m py_compile \
  repo/ood/issue27ckat_canonical_time_c1_canary_v1.py \
  repo/ood/issue27ckbl_frontend_observability_audit_v1.py
python repo/ood/issue27ckbl_frontend_observability_audit_v1.py --mode contract-unit \
  > "$RUN_ROOT/contract_unit.json"

python -u repo/ood/issue27ckbl_frontend_observability_audit_v1.py \
  --mode run \
  --source-read-mode full \
  --max-recorded-index 0 \
  --max-folds 0 \
  --max-iter 80 \
  --seed 27 \
  --out "$RUN_ROOT"

ended_epoch=$(date +%s)
ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'started_utc=%s\nended_utc=%s\nwall_seconds=%s\njob_id=%s\npartition=%s\n' \
  "$started_utc" "$ended_utc" "$((ended_epoch - started_epoch))" "$JOB_ID" "$PARTITION" \
  > "$RUN_ROOT/run_timing.txt"
if command -v sstat >/dev/null 2>&1; then
  sstat -j "${JOB_ID}.batch" --format=JobID,AveCPU,AveRSS,MaxRSS,MaxVMSize -P \
    > "$RUN_ROOT/slurm_in_job_accounting.csv" 2>/dev/null || true
fi
cp "$BASE/runs/issue27ckbl_full_seed27_${PARTITION}_${JOB_ID}.out" "$RUN_ROOT/slurm_stdout_snapshot.txt" 2>/dev/null || true
cp "$BASE/runs/issue27ckbl_full_seed27_${PARTITION}_${JOB_ID}.err" "$RUN_ROOT/slurm_stderr_snapshot.txt" 2>/dev/null || true

CKBL_PARTITION="$PARTITION" CKBL_JOB_ID="$JOB_ID" CKBL_ALLOW_RUNNING=1 \
  bash scripts/issue27ckbl_validate_and_pack_full_seed27.sh

echo "CKBL_FULL_RESULT_COMPLETE partition=$PARTITION job_id=$JOB_ID"
