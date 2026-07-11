#!/bin/bash
# CKAU: read-only mechanism observability diagnostic on the completed CKAT cache.
# The user may edit partition/CPUs/time below before submission.
#SBATCH -J ckau_obs
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
#SBATCH -o runs/issue27ckau_obs_%j.out
#SBATCH -e runs/issue27ckau_obs_%j.err

set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
PROJECT=/public/home/jiangxinwei.zr/work/paper04
PLAN_DIR="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
PLAN="$PLAN_DIR/canonical_source_load_plan.csv"
CACHE_DIR="$PLAN_DIR/hpc_canonical_c1_cache"

cd "$BASE"
test -f "$PROJECT/datasets/gotham2025/raw/GothamDataset2025.zip" || { echo "missing GothamDataset2025.zip"; exit 2; }
test -s "$PLAN" || { echo "missing CKAT source plan: $PLAN"; exit 2; }
test -d "$CACHE_DIR" || { echo "missing CKAT cache: $CACHE_DIR"; exit 2; }

if [ -s scripts/00_env_issue27ckc.sh ]; then
  source scripts/00_env_issue27ckc.sh
elif [ -s "$HOME/work/venvs/kitnet_issue27_py39/bin/activate" ]; then
  source "$HOME/work/venvs/kitnet_issue27_py39/bin/activate"
else
  echo "missing Python env: scripts/00_env_issue27ckc.sh or ~/work/venvs/kitnet_issue27_py39"
  exit 2
fi

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}

# The cache is immutable. Verify every planned source before reading any role.
while IFS=, read -r _source key _rest; do
  [ "$_source" = "source_group" ] && continue
  test -s "$CACHE_DIR/$key.npz" || { echo "missing cache npz: $key"; exit 3; }
  test -s "$CACHE_DIR/$key.json" || { echo "missing cache audit: $key"; exit 3; }
done < "$PLAN"

python -m py_compile repo/ood/issue27ckau_c1_mechanism_observability_diagnostic_v1.py
python -u repo/ood/issue27ckau_c1_mechanism_observability_diagnostic_v1.py \
  --train-cap 4000 \
  --eval-cap 3000 \
  --radius-q 0.95 \
  --source-plan "$PLAN" \
  --cache-dir "$CACHE_DIR" \
  --run-tag hpc_fullsupport_c1_mech_observability
