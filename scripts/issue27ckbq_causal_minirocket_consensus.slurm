#!/bin/bash
# CKBQ: result-producing attack-shielded causal MiniRocket consensus.
# AMD and Intel copies are output-isolated and may both finish safely.
#SBATCH -J ckbq_consensus
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=04:00:00

set -euo pipefail

BASE=${CKBQ_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
PARTITION=${SLURM_JOB_PARTITION:?missing SLURM_JOB_PARTITION}
JOB_ID=${SLURM_JOB_ID:?missing SLURM_JOB_ID}
COMMIT_SHA=${CKBQ_COMMIT_SHA:?missing CKBQ_COMMIT_SHA}
SCRIPT_SHA256=${CKBQ_SCRIPT_SHA256:?missing CKBQ_SCRIPT_SHA256}
VENDOR_SHA256=${CKBQ_VENDOR_SHA256:?missing CKBQ_VENDOR_SHA256}
DEPENDENCY_SHA256=${CKBQ_DEPENDENCY_SHA256:?missing CKBQ_DEPENDENCY_SHA256}
AUX_REUSE_ROOT=${CKBQ_AUX_REUSE_ROOT:-$BASE/runs/issue27ckbo_mature_afterimage_transfer_v1_2026-07-15_seed27_amd_151780}
RUN_NAME="issue27ckbq_causal_minirocket_consensus_v1_2026-07-17_seed27_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"

case "$PARTITION" in amd|intel) ;; *) echo "invalid partition: $PARTITION" >&2; exit 2;; esac
test -d "$BASE" || { echo "missing project directory: $BASE" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing validated environment script" >&2; exit 2; }
test -s "$BASE/repo/ood/issue27ckbq_causal_minirocket_consensus_v1.py" || { echo "missing CKBQ code" >&2; exit 2; }
test -s "$BASE/repo/ood/vendor/sktime_minirocket_v0_24_1/minirocket_torch.py" || { echo "missing MiniRocket port" >&2; exit 2; }
test "$(sha256sum "$BASE/repo/ood/issue27ckbq_causal_minirocket_consensus_v1.py" | awk '{print $1}')" = "$SCRIPT_SHA256" || {
  echo "installed CKBQ hash mismatch" >&2; exit 2;
}
test "$(sha256sum "$BASE/repo/ood/vendor/sktime_minirocket_v0_24_1/minirocket_torch.py" | awk '{print $1}')" = "$VENDOR_SHA256" || {
  echo "installed MiniRocket port hash mismatch" >&2; exit 2;
}
test "$(sha256sum "$BASE/runs/mainline_docs/ckbq_dependency_sha256_20260717.txt" | awk '{print $1}')" = "$DEPENDENCY_SHA256" || {
  echo "CKBQ dependency manifest hash mismatch" >&2; exit 2;
}
test -d "$AUX_REUSE_ROOT/aux_afterimage_cache" || { echo "missing reusable CKBO auxiliary cache: $AUX_REUSE_ROOT" >&2; exit 2; }
test -s "$AUX_REUSE_ROOT/ckbo_auxiliary_benign_manifest.csv" || { echo "missing reusable CKBO auxiliary manifest" >&2; exit 2; }
test -s "$AUX_REUSE_ROOT/ckbo_auxiliary_benign_ready.json" || { echo "missing reusable CKBO auxiliary marker" >&2; exit 2; }
test "$(sha256sum "$AUX_REUSE_ROOT/ckbo_auxiliary_benign_manifest.csv" | awk '{print $1}')" = \
  "d45bb5c0359555b45d19b4b5d2c62ad83ae9dfb177654a3f36c4393fd3120c4f" || {
  echo "reusable CKBO auxiliary manifest drift" >&2; exit 2;
}
test ! -e "$RUN_ROOT" || { echo "refusing to mix existing run root: $RUN_ROOT" >&2; exit 2; }

mkdir -p "$RUN_ROOT"
cp -a "$AUX_REUSE_ROOT/aux_afterimage_cache" "$RUN_ROOT/"
cp "$AUX_REUSE_ROOT/ckbo_auxiliary_benign_manifest.csv" "$RUN_ROOT/"
cp "$AUX_REUSE_ROOT/ckbo_auxiliary_benign_ready.json" "$RUN_ROOT/"
echo "CKBQ_REUSED_CKBO_AUXILIARY_CACHE=$AUX_REUSE_ROOT"

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
    temporal_caches=0
    output_files=0
    test -d "$RUN_ROOT/aux_temporal_cache" && temporal_caches=$(find "$RUN_ROOT/aux_temporal_cache" -maxdepth 1 -name '*.npz' | wc -l || true)
    test -d "$RUN_ROOT" && output_files=$(find "$RUN_ROOT" -maxdepth 1 -type f | wc -l || true)
    printf 'CKBQ_HEARTBEAT utc=%s job=%s partition=%s temporal_caches=%s output_files=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$JOB_ID" "$PARTITION" "$temporal_caches" "$output_files"
  done
}
heartbeat &
heartbeat_pid=$!

cd "$BASE"
source scripts/00_env_issue27ckc.sh
python - <<'PY'
import hashlib
from pathlib import Path

manifest = Path("runs/mainline_docs/ckbq_dependency_sha256_20260717.txt")
for line in manifest.read_text(encoding="utf-8").splitlines():
    expected, relative = line.split(None, 1)
    actual = hashlib.sha256(Path(relative).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if actual != expected:
        raise SystemExit(f"dependency hash mismatch: {relative}: {actual} != {expected}")
print("CKBQ_DEPENDENCIES_OK")
PY

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export NUMEXPR_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export CKBQ_COMMIT_SHA="$COMMIT_SHA"

printf 'job_id=%s\npartition=%s\ncommit_sha=%s\nckbq_sha256=%s\nminirocket_sha256=%s\ndependency_manifest_sha256=%s\naux_reuse_root=%s\nstarted_utc=%s\n' \
  "$JOB_ID" "$PARTITION" "$COMMIT_SHA" "$SCRIPT_SHA256" "$VENDOR_SHA256" "$DEPENDENCY_SHA256" "$AUX_REUSE_ROOT" "$started_utc" \
  > "$RUN_ROOT/slurm_identity.txt"
scontrol show job -o "$JOB_ID" > "$RUN_ROOT/slurm_job_at_start.txt" 2>/dev/null || true

python -m py_compile \
  repo/ood/issue27ckbq_causal_minirocket_consensus_v1.py \
  repo/ood/vendor/sktime_minirocket_v0_24_1/minirocket_torch.py
python -u repo/ood/issue27ckbq_causal_minirocket_consensus_v1.py \
  --mode formal \
  --seed 27 \
  --threads "${SLURM_CPUS_PER_TASK:-8}" \
  --rocket-batch-size 256 \
  --train-cap 4000 \
  --eval-cap 3000 \
  --bootstrap-reps 500 \
  --aux-rows-per-source 600 \
  --out "$RUN_ROOT"

ended_epoch=$(date +%s)
ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'started_utc=%s\nended_utc=%s\nwall_seconds=%s\njob_id=%s\npartition=%s\n' \
  "$started_utc" "$ended_utc" "$((ended_epoch - started_epoch))" "$JOB_ID" "$PARTITION" > "$RUN_ROOT/run_timing.txt"
if command -v sstat >/dev/null 2>&1; then
  sstat -j "${JOB_ID}.batch" --format=JobID,AveCPU,AveRSS,MaxRSS,MaxVMSize -P \
    > "$RUN_ROOT/slurm_in_job_accounting.csv" 2>/dev/null || true
fi
cp "$BASE/runs/issue27ckbq_${PARTITION}_${JOB_ID}.out" "$RUN_ROOT/slurm_stdout_snapshot.txt" 2>/dev/null || true
cp "$BASE/runs/issue27ckbq_${PARTITION}_${JOB_ID}.err" "$RUN_ROOT/slurm_stderr_snapshot.txt" 2>/dev/null || true

CKBQ_PARTITION="$PARTITION" CKBQ_JOB_ID="$JOB_ID" CKBQ_ALLOW_RUNNING=1 \
  bash scripts/issue27ckbq_validate_and_pack_seed27.sh

echo "CKBQ_RESULT_COMPLETE partition=$PARTITION job_id=$JOB_ID"
