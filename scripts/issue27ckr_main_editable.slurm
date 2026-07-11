#!/bin/bash
#SBATCH -J issue27ckr_main
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --time=12:00:00
#SBATCH -o runs/issue27ckr_main_%j.out
#SBATCH -e runs/issue27ckr_main_%j.err

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

python -m py_compile repo/ood/issue27ckr_attack_preserving_flow_veto_v1.py

# Full main task: deliberately no --smoke here.
python -u repo/ood/issue27ckr_attack_preserving_flow_veto_v1.py
