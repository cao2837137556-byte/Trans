#!/bin/bash
# Prepared only. Requires separate user execution authorization and staged inputs.
#SBATCH --job-name=p04-history-c1
#SBATCH --partition=amd
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --no-requeue
#SBATCH --output=/public/home/jiangxinwei.zr/work/paper04/runs/history_normal_reference_keyrepair_v1_20261031/slurm-%j.log
set -euo pipefail
export PATH=/usr/local/slurm-25.11.0-build/bin:/usr/bin:/bin
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=27
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
export CUDA_VISIBLE_DEVICES=""
paper04_root=/public/home/jiangxinwei.zr/work/paper04
paper04_package="$paper04_root/runs/history_normal_reference_keyrepair_v1_20261031"
paper04_python="${PAPER04_MAIN_PYTHON:-/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python}"
paper04_runtime_config="${HNR_RUNTIME_CONFIG:?Set explicit staged runtime config; no automatic path substitution}"
paper04_output="${HNR_OUTPUT:?Set explicit new package outputs directory}"
[[ ${SLURM_JOB_ID:-} =~ ^[0-9]+$ ]]
[[ $paper04_python = /* && -x "$paper04_python" ]]
[[ $paper04_runtime_config = /* && -f "$paper04_runtime_config" ]]
[[ $paper04_output = "$paper04_package"/outputs/* && ! -e "$paper04_output" ]]
paper04_environment="$paper04_root/frontend_compat_v1/environment.sh"
printf '%s  %s\n' '8da8564e759d51df121eaf9230a3e34c358e3abd10d9ce8dc8fe4b92e0763fcf' "$paper04_environment" | sha256sum --check --status
if ! type module >/dev/null 2>&1; then
  for paper04_init in /etc/profile.d/modules.sh /etc/profile.d/lmod.sh /usr/share/Modules/init/bash /usr/share/lmod/lmod/init/bash; do
    if [[ -r "$paper04_init" ]]; then
      source "$paper04_init"
      if type module >/dev/null 2>&1; then break; fi
    fi
  done
fi
type module >/dev/null 2>&1
source "$paper04_environment"
paper04_numpy_overlay="$paper04_root/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201"
export PYTHONPATH="$paper04_numpy_overlay:$paper04_root/environment/vendor_py311_v1"
# Mainline numerical environment is experiment 9's Python 3.11, not Python 3.9.
"$paper04_python" -B -c 'import platform,numpy,torch; assert (platform.python_version(),numpy.__version__,str(torch.__version__).split("+")[0]) == ("3.11.11","2.0.1","2.5.1"), "FROZEN_RUNTIME_MISMATCH"'
cd "$paper04_package"
exec "$paper04_python" -B run.py execute --runtime-config "$paper04_runtime_config" --output "$paper04_output" --execute-real-data
