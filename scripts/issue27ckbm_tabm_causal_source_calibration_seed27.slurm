#!/bin/bash
# CKBM: one seed-27 result-producing strong-backend/calibration experiment.
# The same script may run on AMD and Intel; every writable path is partition/job isolated.
#SBATCH -J ckbm_seed27
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=12:00:00

set -euo pipefail

BASE=${CKBM_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
PARTITION=${SLURM_JOB_PARTITION:?missing SLURM_JOB_PARTITION}
JOB_ID=${SLURM_JOB_ID:?missing SLURM_JOB_ID}
COMMIT_SHA=${CKBM_COMMIT_SHA:?missing CKBM_COMMIT_SHA}
SCRIPT_SHA256=${CKBM_SCRIPT_SHA256:?missing CKBM_SCRIPT_SHA256}
TABM_SHA256=${CKBM_TABM_SHA256:?missing CKBM_TABM_SHA256}
STUB_SHA256=${CKBM_STUB_SHA256:?missing CKBM_STUB_SHA256}

T0="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
TGN_EXT="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
C1_ROOT="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
C1_PLAN="$C1_ROOT/canonical_source_load_plan.csv"
C1_TARGETS="$C1_ROOT/canonical_source_target_index.csv"
C1_CACHE="$C1_ROOT/hpc_canonical_c1_cache"
C1_REPORT_EXT="$BASE/runs/issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc"
OUT="$BASE/runs/issue27ckbm_tabm_causal_source_calibration_v1_2026-07-14_seed27_${PARTITION}_${JOB_ID}"
FAILURE="$BASE/runs/issue27ckbm_seed27_${PARTITION}_${JOB_ID}.failure.txt"

EXPECTED_T0_SHA256=b102b04347dd320f9f89a219285285866dbfa09e09bd73d0839cbe1a91bb0f67
EXPECTED_C1_PLAN_SHA256=414616332159eb90553213d6656c3d072a701ea93a02df464acdfa6cebc128f2
EXPECTED_C1_TARGET_SHA256=74a1699e29b7b1e227f4532ff81f1546a9ba239f2d2d323d390efa5b07437158
EXPECTED_TABM_LF_SHA256=fc654af6a16bac53d893a8265c79d7af4ebddcb95ad0d600cc6b6bc6b7317ade

heartbeat_pid=""
cleanup() {
  status=$?
  if test -n "$heartbeat_pid"; then
    kill "$heartbeat_pid" >/dev/null 2>&1 || true
    wait "$heartbeat_pid" >/dev/null 2>&1 || true
  fi
  if test "$status" -ne 0; then
    printf 'status=FAILED\nexit_code=%s\nfailed_utc=%s\npartition=%s\njob_id=%s\n' \
      "$status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$PARTITION" "$JOB_ID" > "$FAILURE"
  fi
  exit "$status"
}
trap cleanup EXIT

test -d "$BASE" || { echo "missing project directory: $BASE" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing validated environment entry point" >&2; exit 2; }
test -s "$BASE/repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py" || { echo "missing CKBM code" >&2; exit 2; }
test -s "$BASE/repo/ood/vendor/tabm_v0_0_3/tabm.py" || { echo "missing vendored official TabM" >&2; exit 2; }
test -s "$BASE/repo/ood/vendor/tabm_v0_0_3/rtdl_num_embeddings.py" || { echo "missing frozen no-embedding adapter" >&2; exit 2; }
test -s "$T0/tgn_source_event_plan_frozen.csv" || { echo "missing frozen CKBE plan" >&2; exit 2; }
test -d "$T0/tgn_event_cache" || { echo "missing frozen CKBE cache" >&2; exit 2; }
test -s "$TGN_EXT/extension_ready.json" || { echo "missing completed CKBI report extension" >&2; exit 2; }
test -s "$TGN_EXT/report_only_extension_manifest_frozen.csv" || { echo "missing CKBI extension manifest" >&2; exit 2; }
test -s "$C1_PLAN" || { echo "missing frozen C1 plan" >&2; exit 2; }
test -s "$C1_TARGETS" || { echo "missing frozen C1 target manifest" >&2; exit 2; }
test -d "$C1_CACHE" || { echo "missing frozen C1 cache" >&2; exit 2; }
test -s "$C1_REPORT_EXT/c1_report_extension_ready.json" || { echo "missing completed C1 report extension" >&2; exit 2; }
test "$(sha256sum "$BASE/repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py" | awk '{print $1}')" = "$SCRIPT_SHA256" || { echo "installed CKBM hash mismatch" >&2; exit 2; }
test "$(sha256sum "$BASE/repo/ood/vendor/tabm_v0_0_3/tabm.py" | awk '{print $1}')" = "$TABM_SHA256" || { echo "installed TabM hash mismatch" >&2; exit 2; }
test "$(sha256sum "$BASE/repo/ood/vendor/tabm_v0_0_3/rtdl_num_embeddings.py" | awk '{print $1}')" = "$STUB_SHA256" || { echo "installed TabM adapter hash mismatch" >&2; exit 2; }
test "$(sed 's/\r$//' "$BASE/repo/ood/vendor/tabm_v0_0_3/tabm.py" | sha256sum | awk '{print $1}')" = "$EXPECTED_TABM_LF_SHA256" || { echo "vendored TabM differs from upstream v0.0.3" >&2; exit 2; }
test "$(sha256sum "$T0/tgn_source_event_plan_frozen.csv" | awk '{print $1}')" = "$EXPECTED_T0_SHA256" || { echo "frozen CKBE manifest changed" >&2; exit 2; }
test "$(sha256sum "$C1_PLAN" | awk '{print $1}')" = "$EXPECTED_C1_PLAN_SHA256" || { echo "frozen C1 plan changed" >&2; exit 2; }
test "$(sha256sum "$C1_TARGETS" | awk '{print $1}')" = "$EXPECTED_C1_TARGET_SHA256" || { echo "frozen C1 targets changed" >&2; exit 2; }
test ! -e "$OUT" || { echo "refusing existing partition/job output: $OUT" >&2; exit 2; }

cd "$BASE"
source scripts/00_env_issue27ckc.sh
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export CKBM_COMMIT_SHA="$COMMIT_SHA"

python repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py \
  --mode contract-unit --threads "${SLURM_CPUS_PER_TASK:-8}"

heartbeat() {
  while true; do
    sleep 300
    if test -s "$OUT/ckbm_loss_curves.csv"; then
      loss_rows=$(wc -l < "$OUT/ckbm_loss_curves.csv")
    else
      loss_rows=0
    fi
    printf 'CKBM_HEARTBEAT utc=%s partition=%s job=%s loss_rows=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$PARTITION" "$JOB_ID" \
      "$loss_rows"
  done
}
heartbeat &
heartbeat_pid=$!

started_epoch=$(date +%s)
started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python -u repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py \
  --mode formal \
  --seed 27 \
  --t0-root "$T0" \
  --report-t0-extension "$TGN_EXT" \
  --c1-cache "$C1_CACHE" \
  --c1-plan "$C1_PLAN" \
  --c1-targets "$C1_TARGETS" \
  --c1-report-extension "$C1_REPORT_EXT" \
  --out "$OUT" \
  --train-cap 4000 \
  --eval-cap 3000 \
  --epochs 48 \
  --batch-size 512 \
  --threads "${SLURM_CPUS_PER_TASK:-8}" \
  --tabm-k 16 \
  --tabm-width 256 \
  --tabm-blocks 3 \
  --extra-trees 384 \
  --bootstrap-reps 500
ended_epoch=$(date +%s)
ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)

printf 'started_utc=%s\nended_utc=%s\nwall_seconds=%s\npython_exit_code=0\npartition=%s\njob_id=%s\n' \
  "$started_utc" "$ended_utc" "$((ended_epoch - started_epoch))" "$PARTITION" "$JOB_ID" \
  > "$OUT/resource_usage.txt"
printf 'job_id=%s\npartition=%s\ncommit_sha=%s\nckbm_sha256=%s\ntabm_sha256=%s\nstub_sha256=%s\n' \
  "$JOB_ID" "$PARTITION" "$COMMIT_SHA" "$SCRIPT_SHA256" "$TABM_SHA256" "$STUB_SHA256" \
  > "$OUT/slurm_identity.txt"
scontrol show job -o "$JOB_ID" > "$OUT/slurm_job_at_end.txt" 2>/dev/null || true
if command -v sstat >/dev/null 2>&1; then
  sstat -j "${JOB_ID}.batch" --format=JobID,AveCPU,AveRSS,MaxRSS,MaxVMSize -P \
    > "$OUT/slurm_in_job_accounting.csv" 2>/dev/null || true
fi

CKBM_PARTITION="$PARTITION" CKBM_JOB_ID="$JOB_ID" \
  bash scripts/issue27ckbm_validate_and_pack_seed27.sh

rm -f "$FAILURE"
echo "CKBM_RESULT_COMPLETE partition=$PARTITION job_id=$JOB_ID"
