#!/bin/bash
#SBATCH -J issue27ckab_main
#SBATCH -p intel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=16
#SBATCH --time=16:00:00
#SBATCH -o runs/issue27ckab_main_%j.out
#SBATCH -e runs/issue27ckab_main_%j.err

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

python -m py_compile repo/ood/issue27ckab_pseudoheld_episode_map_v1.py

# Main CKAB experiment:
# - B0 is the A3 replay control under the CKAB code path.
# - B1 adds legal-fit pseudo-held device-family episode pressure.
# - Query/future/sealed roles remain report-only.
python -u repo/ood/issue27ckab_pseudoheld_episode_map_v1.py \
  --role-cap 768 \
  --source-cap 48 \
  --train-cap 512 \
  --eval-cap 768 \
  --candidates B0_a3_replay_control,B1_pseudoheld_episode_map \
  --held-values iotsim-stream-consumer,iotsim-hydraulic-system \
  --run-tag hpc_b0b1
