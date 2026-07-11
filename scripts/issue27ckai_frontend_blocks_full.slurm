#!/bin/bash
#SBATCH -J ckai_fe_full
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --time=36:00:00
#SBATCH -o runs/issue27ckai_frontend_full_%j.out
#SBATCH -e runs/issue27ckai_frontend_full_%j.err

set -euo pipefail

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
PROJECT=/public/home/jiangxinwei.zr/work/paper04

cd "$BASE"

test -f "$PROJECT/datasets/gotham2025/raw/GothamDataset2025.zip" || { echo "missing GothamDataset2025.zip"; exit 2; }

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

python -m py_compile repo/ood/issue27ckai_external_flow_feature_probe_v1.py

python -u repo/ood/issue27ckai_external_flow_feature_probe_v1.py \
  --mode frontend \
  --full \
  --max-recorded-index 0 \
  --train-cap 20000 \
  --eval-cap 1000000000 \
  --context-row-output-cap 200000 \
  --run-tag hpc_frontend_blocks_full
