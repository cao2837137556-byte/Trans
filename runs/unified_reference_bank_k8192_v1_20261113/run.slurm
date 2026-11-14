#!/bin/bash
set -euo pipefail
umask 077
phase="$1"
project="$2"
target="$3"
archive="$4"
export K8192_RSS_MIB="$5"
export K8192_WALL_SECONDS="$6"
package="$(pwd -P)"
stage=COMPUTE_STARTUP
trap 'rc=$?; if [ "$rc" -ne 0 ]; then file="$target/SLURM_STOP_$phase.json"; printf "{\"phase\":\"%s\",\"stage\":\"%s\",\"exit_code\":%d,\"job_id\":\"%s\"}\n" "$phase" "$stage" "$rc" "${SLURM_JOB_ID:-unknown}" > "$file.$$"; mv -- "$file.$$" "$file"; fi' EXIT
test -r "$package/PACKAGE_MANIFEST.json"
if [ -r "$project/scripts/00_env_issue27ckc.sh" ]; then
    source "$project/scripts/00_env_issue27ckc.sh"
fi
if ! type module >/dev/null 2>&1; then
    for init in /etc/profile.d/modules.sh /etc/profile.d/lmod.sh /usr/share/Modules/init/bash /usr/share/lmod/lmod/init/bash; do
        if [ -r "$init" ]; then
            source "$init"
            if type module >/dev/null 2>&1; then break; fi
        fi
    done
fi
printf '%s  %s\n' '8da8564e759d51df121eaf9230a3e34c358e3abd10d9ce8dc8fe4b92e0763fcf' "$project/frontend_compat_v1/environment.sh" | sha256sum --check --status
source "$project/frontend_compat_v1/environment.sh"
if ! command -v tshark >/dev/null 2>&1; then
    module load apps/tshark/4.6.6
fi
numpy_runtime="$project/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201"
test -d "$numpy_runtime/numpy"
export PYTHONPATH="$numpy_runtime:$project/environment/vendor_py311_v1:$package/repo/ood"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTHONHASHSEED=27 CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
test "$PAPER04_PYTHON" = /share/software/miniconda3.2025/envs/torch_demo_2025/bin/python
test -x "$PAPER04_PYTHON"
stage=WORKER
"$PAPER04_PYTHON" -X utf8 -B "$package/worker.py" "$phase" "$project" "$target" "$archive"
