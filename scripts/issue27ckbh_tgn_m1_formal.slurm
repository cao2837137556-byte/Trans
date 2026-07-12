#!/bin/bash
# CKBH formal M1: metrics-producing training/evaluation only.
# It deliberately does not install anything, create an environment, use a
# container, run a CKBF-only preflight, or submit any child job.
#
# Stage B of the CKBI->CKBH dependency chain.  Submit with an afterok
# dependency on issue27ckbi_tgn_report_extension.slurm; do not run standalone.
#SBATCH -J ckbh_m1_formal
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH -o runs/issue27ckbh_m1_formal_%j.out
#SBATCH -e runs/issue27ckbh_m1_formal_%j.err

set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
T0="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
C1PLAN="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1/canonical_source_load_plan.csv"
C1CACHE="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1/hpc_canonical_c1_cache"
EXT="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
OUT="$BASE/runs/issue27ckbh_tgn_m1_strict_formal_v1_2026-07-12_hpc_seed27"

cd "$BASE"
test -s scripts/00_env_issue27ckc.sh || { echo "missing provisioned environment script" >&2; exit 2; }
test -s "$T0/tgn_source_event_plan_frozen.csv" || { echo "missing frozen CKBE plan" >&2; exit 2; }
test -s "$T0/t0_cache_audit.csv" || { echo "missing CKBE T0 audit" >&2; exit 2; }
test -d "$T0/tgn_event_cache" || { echo "missing CKBE event cache" >&2; exit 2; }
test -s "$EXT/report_only_extension_manifest_frozen.csv" || { echo "missing CKBI report extension manifest" >&2; exit 2; }
test -s "$EXT/extension_ready.json" || { echo "missing CKBI extension readiness artifact" >&2; exit 2; }
test -s "$C1PLAN" || { echo "missing canonical C1 plan" >&2; exit 2; }
test -d "$C1CACHE" || { echo "missing canonical C1 cache" >&2; exit 2; }

source scripts/00_env_issue27ckc.sh
python - <<'PY'
import torch
import torch_geometric
print("CKBH_ENV", torch.__version__, torch_geometric.__version__)
PY

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export M1_COMMIT_SHA=${M1_COMMIT_SHA:-bundle-unset}

mkdir -p "$OUT"
python -m py_compile repo/ood/issue27ckbh_tgn_m1_strict_formal_v1.py

# /usr/bin/time records an in-job maximum RSS.  After completion, sacct adds
# Slurm's MaxRSS through the normal result-pull command in the bundle README.
{ /usr/bin/time -v python -u repo/ood/issue27ckbh_tgn_m1_strict_formal_v1.py \
  --mode formal \
  --t0-root "$T0" \
  --report-t0-extension "$EXT" \
  --c1-cache "$C1CACHE" \
  --c1-plan "$C1PLAN" \
  --out "$OUT" \
  --train-cap 0 \
  --eval-cap 0 \
  --seeds 27 \
  --ssl-epochs 3 \
  --verifier-epochs 30 \
  --verifier-negative-ratio 4 \
  --bootstrap-reps 1000; } 2> "$OUT/m1_time_v.txt"

cp "$OUT/m1_environment.json" "$OUT/m1_environment.before_sacct.json"
echo "slurm_job_id=${SLURM_JOB_ID}" > "$OUT/slurm_job_id.txt"
echo "formal M1 completed; pull this run directory and append sacct MaxRSS" >&2
