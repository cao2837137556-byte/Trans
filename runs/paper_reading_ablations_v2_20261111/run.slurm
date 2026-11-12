#!/bin/bash
#SBATCH --job-name=paper-3d-ablations
#SBATCH --partition=amd
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8192M
#SBATCH --time=01:00:00
#SBATCH --no-requeue
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err
set -euo pipefail
umask 077
TASK_DIR="${SLURM_SUBMIT_DIR:?Submit from the unpacked package directory}"
PROJECT_DIR="$(cd "$TASK_DIR/../.." && pwd)"
test -f "$TASK_DIR/PACKAGE_MANIFEST.json"
test ! -e "$TASK_DIR/results"
source "$PROJECT_DIR/frontend_compat_v1/environment.sh"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PROJECT_DIR/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201:$PROJECT_DIR/environment/vendor_py311_v1:${PYTHONPATH:-}"
exec /usr/bin/time -v -o "$TASK_DIR/RESOURCE_USAGE.txt" /share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -X utf8 -B "$TASK_DIR/run.py"
