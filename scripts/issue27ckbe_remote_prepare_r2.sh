#!/bin/bash
# CKBE r2 remote preparation.  This script does not submit Slurm work.
# It atomically prepares the compatible PyG environment and frozen event plan.
set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
RUN=issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r2
BUNDLE="${1:-$HOME/work/_upload_issue27ckbe_r2}"

test -f "$BUNDLE/repo/ood/issue27ckbe_tgn_fullsupport_event_cache_v1.py" || {
  echo "missing CKBE r2 bundle at $BUNDLE" >&2
  exit 2
}

cp "$BUNDLE/repo/ood/issue27ckbe_tgn_fullsupport_event_cache_v1.py" "$BASE/repo/ood/"
cp "$BUNDLE/scripts/issue27ckbe_prepare_tgn_env.sh" \
   "$BUNDLE/scripts/issue27ckbe_tgn_event_cache_array.slurm" \
   "$BASE/scripts/"

cd "$BASE"
TGN_WHEELHOUSE="$BUNDLE/wheelhouse_pyg_cp39" bash scripts/issue27ckbe_prepare_tgn_env.sh

mkdir -p "runs/$RUN"
rm -f "runs/$RUN/tgn_source_event_plan.csv" "runs/$RUN/tgn_source_event_plan_frozen.csv"
python -u repo/ood/issue27ckbe_tgn_fullsupport_event_cache_v1.py --mode plan --out "runs/$RUN"
cp "runs/$RUN/tgn_source_event_plan.csv" "runs/$RUN/tgn_source_event_plan_frozen.csv"
test "$(( $(wc -l < "runs/$RUN/tgn_source_event_plan_frozen.csv") - 1 ))" -eq 26

echo "CKBE r2 preflight passed"
echo "RUN=$RUN"
echo "Next: edit only #SBATCH resources in scripts/issue27ckbe_tgn_event_cache_array.slurm if needed, then run:"
echo "sbatch --parsable scripts/issue27ckbe_tgn_event_cache_array.slurm"
