#!/bin/bash
# CKBN: result-producing stream separability diagnosis; dual-partition safe.
#SBATCH -J ckbn_diag
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=08:00:00

set -euo pipefail

BASE=${CKBN_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
PARTITION=${SLURM_JOB_PARTITION:?missing SLURM_JOB_PARTITION}
JOB_ID=${SLURM_JOB_ID:?missing SLURM_JOB_ID}
COMMIT_SHA=${CKBN_COMMIT_SHA:?missing CKBN_COMMIT_SHA}
SCRIPT_SHA256=${CKBN_SCRIPT_SHA256:?missing CKBN_SCRIPT_SHA256}
CKAO_SHA256=${CKAO_SHA256:?missing CKAO_SHA256}
CKAI_SHA256=${CKAI_SHA256:?missing CKAI_SHA256}
CKAT_SHA256=${CKAT_SHA256:?missing CKAT_SHA256}
CKBL_SHA256=${CKBL_SHA256:?missing CKBL_SHA256}
CKO_SHA256=${CKO_SHA256:?missing CKO_SHA256}
RUN_ROOT="$BASE/runs/issue27ckbn_stream_separability_diagnostic_v1_2026-07-15_fullsource_seed27_${PARTITION}_${JOB_ID}"

test -d "$BASE" || { echo "missing project directory: $BASE" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing validated environment script" >&2; exit 2; }
test -s "$BASE/repo/ood/issue27ckbn_stream_separability_diagnostic_v1.py" || { echo "missing CKBN code" >&2; exit 2; }
test "$(sha256sum "$BASE/repo/ood/issue27ckbn_stream_separability_diagnostic_v1.py" | awk '{print $1}')" = "$SCRIPT_SHA256" || {
  echo "installed CKBN hash mismatch" >&2
  exit 2
}
test "$(sha256sum "$BASE/repo/ood/issue27ckao_c1_strict_leave_device_family_canary_v1.py" | awk '{print $1}')" = "$CKAO_SHA256" || { echo "CKAO dependency changed after submit" >&2; exit 2; }
test "$(sha256sum "$BASE/repo/ood/issue27ckai_external_flow_feature_probe_v1.py" | awk '{print $1}')" = "$CKAI_SHA256" || { echo "CKAI dependency changed after submit" >&2; exit 2; }
test "$(sha256sum "$BASE/repo/ood/issue27ckat_canonical_time_c1_canary_v1.py" | awk '{print $1}')" = "$CKAT_SHA256" || { echo "CKAT dependency changed after submit" >&2; exit 2; }
test "$(sha256sum "$BASE/repo/ood/issue27ckbl_frontend_observability_audit_v1.py" | awk '{print $1}')" = "$CKBL_SHA256" || { echo "CKBL dependency changed after submit" >&2; exit 2; }
test "$(sha256sum "$BASE/repo/ood/issue27cko_mechanism_frontend_v1.py" | awk '{print $1}')" = "$CKO_SHA256" || { echo "CKO dependency changed after submit" >&2; exit 2; }
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
    progress=$(find "$RUN_ROOT" -maxdepth 1 -name '*_source_progress.jsonl' -type f -exec cat {} + 2>/dev/null | wc -l || true)
    printf 'CKBN_HEARTBEAT utc=%s job=%s partition=%s completed_source_scopes=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$JOB_ID" "$PARTITION" "$progress"
  done
}
heartbeat &
heartbeat_pid=$!

cd "$BASE"
source scripts/00_env_issue27ckc.sh
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export CKBN_COMMIT_SHA="$COMMIT_SHA"

printf 'job_id=%s\npartition=%s\ncommit_sha=%s\nckbn_sha256=%s\nckao_sha256=%s\nckai_sha256=%s\nckat_sha256=%s\nckbl_sha256=%s\ncko_sha256=%s\nstarted_utc=%s\n' \
  "$JOB_ID" "$PARTITION" "$COMMIT_SHA" "$SCRIPT_SHA256" "$CKAO_SHA256" "$CKAI_SHA256" "$CKAT_SHA256" "$CKBL_SHA256" "$CKO_SHA256" "$started_utc" > "$RUN_ROOT/slurm_identity.txt"
scontrol show job -o "$JOB_ID" > "$RUN_ROOT/slurm_job_at_start.txt" 2>/dev/null || true

python -m py_compile repo/ood/issue27ckbn_stream_separability_diagnostic_v1.py
python -u repo/ood/issue27ckbn_stream_separability_diagnostic_v1.py \
  --mode run \
  --source-read-mode full \
  --seed 27 \
  --canary-cap 3000 \
  --attack-family-cap 2000 \
  --max-iter 80 \
  --out "$RUN_ROOT"

ended_epoch=$(date +%s)
ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'started_utc=%s\nended_utc=%s\nwall_seconds=%s\njob_id=%s\npartition=%s\n' \
  "$started_utc" "$ended_utc" "$((ended_epoch - started_epoch))" "$JOB_ID" "$PARTITION" > "$RUN_ROOT/run_timing.txt"
if command -v sstat >/dev/null 2>&1; then
  sstat -j "${JOB_ID}.batch" --format=JobID,AveCPU,AveRSS,MaxRSS,MaxVMSize -P \
    > "$RUN_ROOT/slurm_in_job_accounting.csv" 2>/dev/null || true
fi
cp "$BASE/runs/issue27ckbn_diag_${PARTITION}_${JOB_ID}.out" "$RUN_ROOT/slurm_stdout_snapshot.txt" 2>/dev/null || true
cp "$BASE/runs/issue27ckbn_diag_${PARTITION}_${JOB_ID}.err" "$RUN_ROOT/slurm_stderr_snapshot.txt" 2>/dev/null || true

CKBN_PARTITION="$PARTITION" CKBN_JOB_ID="$JOB_ID" CKBN_ALLOW_RUNNING=1 \
  bash scripts/issue27ckbn_validate_and_pack_seed27.sh

echo "CKBN_RESULT_COMPLETE partition=$PARTITION job_id=$JOB_ID"
