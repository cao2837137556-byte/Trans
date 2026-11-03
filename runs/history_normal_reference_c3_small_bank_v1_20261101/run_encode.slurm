#!/bin/bash
#SBATCH --job-name=p04-c3-encode
#SBATCH --partition=amd
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=/public/home/jiangxinwei.zr/work/paper04/runs/history_normal_reference_c3_small_bank_v1_20261101/SLURM-%j.log
set -euo pipefail
TASK_ROOT=/public/home/jiangxinwei.zr/work/paper04
TASK_C3="$TASK_ROOT/runs/history_normal_reference_c3_small_bank_v1_20261101"
source "$TASK_ROOT/frontend_compat_v1/environment.sh"
export PYTHONPATH="$TASK_ROOT/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201:$TASK_ROOT/environment/vendor_py311_v1:${PYTHONPATH:-}"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUTF8=1
cd "$TASK_C3"
/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -B guarded_run.py encode
