#!/bin/bash
# Prepared only. Submit once after the failed-attempt retry is authorized.
#SBATCH --job-name=p04-lg-replay-r1
#SBATCH --partition=amd
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --no-requeue
#SBATCH --output=/public/home/jiangxinwei.zr/work/paper04/runs/local_geometry_budgeted_v2_replay_repair_r1_20261029/slurm-source-%j.log

set -euo pipefail
export PATH=/usr/local/slurm-25.11.0-build/bin:/usr/bin:/bin
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
export CUDA_VISIBLE_DEVICES=""
paper04_root=/public/home/jiangxinwei.zr/work/paper04
paper04_package="$paper04_root/runs/local_geometry_budgeted_v2_replay_repair_r1_20261029"
paper04_python=/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python
paper04_environment="$paper04_root/frontend_compat_v1/environment.sh"
[[ ${SLURM_JOB_ID:-} =~ ^[0-9]+$ ]]
[[ -r "$paper04_environment" ]]
printf '%s  %s\n' '8da8564e759d51df121eaf9230a3e34c358e3abd10d9ce8dc8fe4b92e0763fcf' "$paper04_environment" | sha256sum --check --status
if ! type module >/dev/null 2>&1; then
  for paper04_module_init in /etc/profile.d/modules.sh /etc/profile.d/lmod.sh /usr/share/Modules/init/bash /usr/share/lmod/lmod/init/bash; do
    if [[ -r "$paper04_module_init" ]]; then
      source "$paper04_module_init"
      if type module >/dev/null 2>&1; then break; fi
    fi
  done
fi
type module >/dev/null 2>&1
source "$paper04_environment"
export PYTHONPATH="$paper04_root/environment/vendor_py311_v1"
cd "$paper04_package"
exec "$paper04_python" -B historical_source.py --output "outputs/source_retry_${SLURM_JOB_ID}"
