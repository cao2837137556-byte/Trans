#!/bin/bash
# CKAT full-support strict Level-2 aggregation after the cache array completes.
# The user may edit partition/CPUs/time below before submission.
#SBATCH -J ckat_l2
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --time=04:00:00
#SBATCH -o runs/issue27ckat_l2_%j.out
#SBATCH -e runs/issue27ckat_l2_%j.err

set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
PROJECT=/public/home/jiangxinwei.zr/work/paper04
PLAN_DIR="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
PLAN="$PLAN_DIR/canonical_source_load_plan.csv"
CACHE_DIR="$PLAN_DIR/hpc_canonical_c1_cache"

cd "$BASE"
test -f "$PROJECT/datasets/gotham2025/raw/GothamDataset2025.zip" || { echo "missing GothamDataset2025.zip"; exit 2; }
test -s "$PLAN" || { echo "missing source plan: $PLAN"; exit 2; }
test -d "$CACHE_DIR" || { echo "missing cache dir: $CACHE_DIR"; exit 2; }

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

# Every planned source must have both immutable cache artifacts.
while IFS=, read -r _source key _rest; do
  [ "$_source" = "source_group" ] && continue
  test -s "$CACHE_DIR/$key.npz" || { echo "missing cache npz: $key"; exit 3; }
  test -s "$CACHE_DIR/$key.json" || { echo "missing cache audit: $key"; exit 3; }
done < "$PLAN"

python -m py_compile repo/ood/issue27ckat_canonical_time_c1_canary_v1.py
python -u repo/ood/issue27ckat_canonical_time_c1_canary_v1.py \
  --mode smoke \
  --full \
  --max-recorded-index 0 \
  --train-cap 4000 \
  --eval-cap 3000 \
  --max-leave-groups 5 \
  --cache-dir "$CACHE_DIR" \
  --source-plan "$PLAN" \
  --run-tag hpc_fullsupport_cached_l2
