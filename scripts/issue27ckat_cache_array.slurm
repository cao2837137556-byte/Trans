#!/bin/bash
# CKAT full-support canonical C1 feature cache: one raw source per task.
# The user may edit partition/CPUs/time below before submission.
#SBATCH -J ckat_cache
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --array=0-25%4
#SBATCH --time=12:00:00
#SBATCH -o runs/issue27ckat_cache_%A_%a.out
#SBATCH -e runs/issue27ckat_cache_%A_%a.err

set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
PROJECT=/public/home/jiangxinwei.zr/work/paper04
PLAN_DIR="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
PLAN="$PLAN_DIR/canonical_source_load_plan.csv"
TARGETS="$PLAN_DIR/canonical_source_target_index.csv"
CACHE_DIR="$PLAN_DIR/hpc_canonical_c1_cache"

cd "$BASE"
test -f "$PROJECT/datasets/gotham2025/raw/GothamDataset2025.zip" || { echo "missing GothamDataset2025.zip"; exit 2; }
test -s "$PLAN" || { echo "missing source plan: $PLAN"; exit 2; }
test -s "$TARGETS" || { echo "missing source targets: $TARGETS"; exit 2; }

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

python -m py_compile repo/ood/issue27ckat_canonical_time_c1_canary_v1.py
python -u repo/ood/issue27ckat_canonical_time_c1_canary_v1.py \
  --mode source-cache \
  --source-plan "$PLAN" \
  --source-targets "$TARGETS" \
  --source-index "$SLURM_ARRAY_TASK_ID" \
  --cache-dir "$CACHE_DIR" \
  --episode-seconds 60
