#!/bin/bash
#SBATCH --job-name=gotham115-by
#SBATCH --output=slurm-%A_%a.out
#SBATCH --error=slurm-%A_%a.err
#SBATCH --array=1-28
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=04:00:00

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

# Prerequisite: run build-train-state once before this array:
# python repo/ood/issue27by_runtime_optimized_1m_or_slurm_materialization.py --mode build-train-state

python repo/ood/issue27by_runtime_optimized_1m_or_slurm_materialization.py \
  --mode run-job \
  --job-index "${SLURM_ARRAY_TASK_ID}" \
  --max-wall-seconds "${MAX_WALL_SECONDS:-10800}"
