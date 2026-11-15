#!/bin/bash
set -euo pipefail
umask 077
project="$1"
target="$2"
package="$(pwd -P)"
source "$project/frontend_compat_v1/environment.sh"
numpy_runtime="$project/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201"
export PYTHONPATH="$numpy_runtime:$project/environment/vendor_py311_v1"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHASHSEED=27 CUDA_VISIBLE_DEVICES=""
exec "$PAPER04_PYTHON" -X utf8 -B "$package/worker.py" "$project" "$target"
