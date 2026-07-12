#!/bin/bash
# CKBI stage A: materialize exactly four label-free report-only TGN caches.
# This is part of the formal M1 chain, not an environment/preflight job.
#SBATCH -J ckbi_reportcache
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH -o runs/issue27ckbi_reportcache_%j.out
#SBATCH -e runs/issue27ckbi_reportcache_%j.err

set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
OUT="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"

cd "$BASE"
test -s scripts/00_env_issue27ckc.sh || { echo "missing provisioned environment script" >&2; exit 2; }
test -s repo/ood/issue27ckbe_tgn_fullsupport_event_cache_v1.py || { echo "missing CKBE materializer" >&2; exit 2; }
source scripts/00_env_issue27ckc.sh

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}

python -m py_compile repo/ood/issue27ckbi_tgn_report_only_cache_extension_v1.py
python -u repo/ood/issue27ckbi_tgn_report_only_cache_extension_v1.py \
  --mode materialize-all \
  --out "$OUT"
