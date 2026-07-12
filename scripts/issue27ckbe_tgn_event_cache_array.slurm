#!/bin/bash
# CKBE full raw-source TGN event cache. Edit resource directives only if needed.
# The frozen source plan is written once before this array is submitted.
#SBATCH -J ckbe_tgncache
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --array=0-25%3
#SBATCH --time=12:00:00
#SBATCH -o runs/issue27ckbe_cache_%A_%a.out
#SBATCH -e runs/issue27ckbe_cache_%A_%a.err

set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
RUN=issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3
OUT="$BASE/runs/$RUN"
PLAN="$OUT/tgn_source_event_plan_frozen.csv"
CACHE="$OUT/tgn_event_cache"
TARGETS="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1/canonical_source_target_index.csv"

cd "$BASE"
test -s scripts/00_env_issue27ckc.sh || {
  echo "missing provisioned scripts/00_env_issue27ckc.sh" >&2
  exit 2
}
source scripts/00_env_issue27ckc.sh

python - <<'PY'
import torch
import torch_geometric
print("TGN ENV", torch.__version__, torch_geometric.__version__)
PY
test -s "$PLAN" || { echo "missing frozen event plan: $PLAN" >&2; exit 2; }
test -s "$TARGETS" || { echo "missing target index: $TARGETS" >&2; exit 2; }

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}

python -m py_compile repo/ood/issue27ckbe_tgn_fullsupport_event_cache_v1.py
python -u repo/ood/issue27ckbe_tgn_fullsupport_event_cache_v1.py \
  --mode materialize --targets "$TARGETS" --out "$OUT" --source-plan "$PLAN" \
  --cache-dir "$CACHE" --source-index "$SLURM_ARRAY_TASK_ID"
