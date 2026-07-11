#!/bin/bash
# Group C: same immutable CKAW cache; role-isolated 60-second episode pooling.
# This is independent of Group A/B once the cache array completes successfully.
#SBATCH -J ckay_C
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --time=04:00:00
#SBATCH -o runs/issue27ckay_C_%j.out
#SBATCH -e runs/issue27ckay_C_%j.err
set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
RUN=issue27ckaw_canonical_interaction_episode_frontend_v1_2026-07-10_hpc_fullsupport
CACHE="$BASE/runs/$RUN/canonical_episode_cache"
PLAN="$BASE/runs/$RUN/episode_source_plan_frozen.csv"
cd "$BASE"

if [ -s scripts/00_env_issue27ckc.sh ]; then
  source scripts/00_env_issue27ckc.sh
elif [ -s "$HOME/work/venvs/kitnet_issue27_py39/bin/activate" ]; then
  source "$HOME/work/venvs/kitnet_issue27_py39/bin/activate"
else
  echo "missing known Python environment" >&2
  exit 2
fi

test -d "$CACHE" || { echo "missing completed CKAW cache: $CACHE" >&2; exit 2; }
test -s "$PLAN" || { echo "missing immutable cache plan: $PLAN" >&2; exit 2; }
python -u repo/ood/issue27ckay_episode_pooling_strict_l2_smoke_v1.py \
  --cache-root "$BASE/runs/$RUN" --plan-path "$PLAN" \
  --train-cap 4000 --eval-cap 3000 --run-tag hpc_fullsupport_groupC
