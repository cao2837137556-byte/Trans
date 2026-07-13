#!/bin/bash
# CKBJ/CKBH-v2: one metrics-producing seed-27 M1 job.
# CKBI Stage A is already complete and is reused read-only.  This job first
# materializes/validates the label-free C1 report extension, then immediately
# trains and evaluates M0/M1-Random/M1-SSL/TGN-only.  It does not install an
# environment, submit a child job, or run a standalone preflight.
#SBATCH -J ckbj_m1_v2
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=48:00:00
#SBATCH -o runs/issue27ckbj_m1_v2_%j.out
#SBATCH -e runs/issue27ckbj_m1_v2_%j.err

set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
T0="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
TGN_EXT="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
C1_ROOT="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
C1_PLAN="$C1_ROOT/canonical_source_load_plan.csv"
C1_TARGETS="$C1_ROOT/canonical_source_target_index.csv"
C1_CACHE="$C1_ROOT/hpc_canonical_c1_cache"
C1_REPORT_EXT="$BASE/runs/issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc"
OUT="$BASE/runs/issue27ckbj_tgn_m1_strict_formal_v2_2026-07-13_hpc_seed27_${SLURM_JOB_ID}"

EXPECTED_T0_SHA256=b102b04347dd320f9f89a219285285866dbfa09e09bd73d0839cbe1a91bb0f67
EXPECTED_C1_PLAN_SHA256=414616332159eb90553213d6656c3d072a701ea93a02df464acdfa6cebc128f2
EXPECTED_C1_TARGET_SHA256=74a1699e29b7b1e227f4532ff81f1546a9ba239f2d2d323d390efa5b07437158

cd "$BASE"
test -s scripts/00_env_issue27ckc.sh || { echo "missing provisioned environment script" >&2; exit 2; }
test -s "$T0/tgn_source_event_plan_frozen.csv" || { echo "missing frozen CKBE plan" >&2; exit 2; }
test -s "$T0/t0_cache_audit.csv" || { echo "missing CKBE T0 audit" >&2; exit 2; }
test -d "$T0/tgn_event_cache" || { echo "missing CKBE event cache" >&2; exit 2; }
test -s "$TGN_EXT/report_only_extension_manifest_frozen.csv" || { echo "missing completed CKBI TGN extension" >&2; exit 2; }
test -s "$TGN_EXT/extension_ready.json" || { echo "missing CKBI extension readiness artifact" >&2; exit 2; }
test -s "$C1_PLAN" || { echo "missing canonical C1 plan" >&2; exit 2; }
test -s "$C1_TARGETS" || { echo "missing canonical C1 target manifest" >&2; exit 2; }
test -d "$C1_CACHE" || { echo "missing canonical C1 cache" >&2; exit 2; }
test "$(sha256sum "$T0/tgn_source_event_plan_frozen.csv" | awk '{print $1}')" = "$EXPECTED_T0_SHA256" || { echo "frozen CKBE manifest hash changed" >&2; exit 2; }
test "$(sha256sum "$C1_PLAN" | awk '{print $1}')" = "$EXPECTED_C1_PLAN_SHA256" || { echo "frozen C1 plan hash changed" >&2; exit 2; }
test "$(sha256sum "$C1_TARGETS" | awk '{print $1}')" = "$EXPECTED_C1_TARGET_SHA256" || { echo "frozen C1 target hash changed" >&2; exit 2; }
test ! -e "$OUT" || { echo "refusing to mix results in existing output: $OUT" >&2; exit 2; }

source scripts/00_env_issue27ckc.sh
python - <<'PY'
import torch
import torch_geometric
print("CKBJ_ENV", torch.__version__, torch_geometric.__version__)
PY

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export M1_COMMIT_SHA=${M1_COMMIT_SHA:-bundle-unset}

python -m py_compile \
  repo/ood/issue27ckbj_c1_report_only_cache_extension_v1.py \
  repo/ood/issue27ckbj_tgn_m1_strict_formal_v2.py

mkdir -p "$OUT"
{ /usr/bin/time -v python -u repo/ood/issue27ckbj_tgn_m1_strict_formal_v2.py \
  --mode formal \
  --t0-root "$T0" \
  --report-t0-extension "$TGN_EXT" \
  --c1-cache "$C1_CACHE" \
  --c1-plan "$C1_PLAN" \
  --c1-targets "$C1_TARGETS" \
  --c1-report-extension "$C1_REPORT_EXT" \
  --out "$OUT" \
  --train-cap 4000 \
  --eval-cap 3000 \
  --seeds 27 \
  --ssl-epochs 3 \
  --verifier-epochs 30 \
  --verifier-negative-ratio 4 \
  --history-batch-size 200 \
  --bootstrap-reps 1000; } 2> "$OUT/m1_time_v.txt"

echo "slurm_job_id=${SLURM_JOB_ID}" > "$OUT/slurm_job_id.txt"
echo "formal M1 v2 completed; do not launch seeds 37/47 automatically" >&2
