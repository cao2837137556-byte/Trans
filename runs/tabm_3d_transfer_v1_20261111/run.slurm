#!/bin/bash
#SBATCH --job-name=tabm-3d-transfer
#SBATCH --partition=gpu
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16384M
#SBATCH --gres=gpu:nvidia_geforce_rtx_4090:1
#SBATCH --time=02:00:00
#SBATCH --no-requeue
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err
set -euo pipefail
umask 077
TASK_DIR="${SLURM_SUBMIT_DIR:?Submit from the package directory}"
PROJECT_DIR="$(cd "$TASK_DIR/../.." && pwd)"
test ! -e "$TASK_DIR/results"
source "$PROJECT_DIR/frontend_compat_v1/environment.sh"
export PYTHONPATH="$PROJECT_DIR/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201:$PROJECT_DIR/environment/vendor_py311_v1:${PYTHONPATH:-}"
export OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMEXPR_NUM_THREADS=8 PYTHONDONTWRITEBYTECODE=1 CUBLAS_WORKSPACE_CONFIG=:4096:8
exec /share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -X utf8 -B "$TASK_DIR/launch.py"
