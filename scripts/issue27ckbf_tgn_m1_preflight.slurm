#!/bin/bash
# CKBF is an audit-only M1 preflight. It does not train, score, or select a model.
#SBATCH -J ckbf_preflight_r2
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH -o runs/issue27ckbf_preflight_r2_%j.out
#SBATCH -e runs/issue27ckbf_preflight_r2_%j.err

set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
T0="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
OUT="$BASE/runs/issue27ckbf_tgn_m1_preflight_v1_2026-07-12_hpc_preflight_r2"

cd "$BASE"
test -s scripts/00_env_issue27ckc.sh || { echo "missing provisioned scripts/00_env_issue27ckc.sh" >&2; exit 2; }
source scripts/00_env_issue27ckc.sh
test -d "$T0/tgn_event_cache" || { echo "missing CKBE T0 event cache" >&2; exit 2; }

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-16}

python -m py_compile repo/ood/issue27ckbf_tgn_m1_preflight_v1.py
python -u repo/ood/issue27ckbf_tgn_m1_preflight_v1.py \
  --t0-root "$T0" \
  --out "$OUT" \
  --max-events-per-source 200000
