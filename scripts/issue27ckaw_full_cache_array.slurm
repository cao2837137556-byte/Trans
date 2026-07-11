#!/bin/bash
# Shared full-support CKAW cache.  The array reads a frozen plan because each
# worker writes its own single-source runtime summary under the normal run dir.
#SBATCH -J ckaw_cache
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --array=0-25%5
#SBATCH --time=12:00:00
#SBATCH -o runs/issue27ckaw_cache_%A_%a.out
#SBATCH -e runs/issue27ckaw_cache_%A_%a.err
set -euo pipefail
BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
RUN=issue27ckaw_canonical_interaction_episode_frontend_v1_2026-07-10_hpc_fullsupport
PLAN="$BASE/runs/$RUN/episode_source_plan_frozen.csv"
CACHE="$BASE/runs/$RUN/canonical_episode_cache"
cd "$BASE"
if [ -s scripts/00_env_issue27ckc.sh ]; then source scripts/00_env_issue27ckc.sh
elif [ -s "$HOME/work/venvs/kitnet_issue27_py39/bin/activate" ]; then source "$HOME/work/venvs/kitnet_issue27_py39/bin/activate"
else echo "missing known Python environment"; exit 2; fi
test -s "$PLAN" || { echo "missing CKAW plan: $PLAN"; exit 2; }
SOURCE=$(sed -n "$((SLURM_ARRAY_TASK_ID+2))p" "$PLAN" | cut -d, -f1)
test -n "$SOURCE"
python -u repo/ood/issue27ckaw_canonical_interaction_episode_frontend_v1.py --mode materialize --max-recorded-index 0 --source-group "$SOURCE" --run-tag hpc_fullsupport --cache-dir "$CACHE"
