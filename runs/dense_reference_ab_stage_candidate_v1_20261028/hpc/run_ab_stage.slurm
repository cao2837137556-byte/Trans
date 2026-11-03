#!/bin/bash
# Prepared candidate only. Creating this file does not submit a job.
#SBATCH --job-name=p04-dense-ab
#SBATCH --partition=amd
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --no-requeue
#SBATCH --signal=B:TERM@120
#SBATCH --output=/public/home/jiangxinwei.zr/work/paper04/runs/dense_reference_ab_stage_candidate_v1_20261028_runtime/slurm-%j.log
set -euo pipefail
export PATH=/usr/local/slurm-25.11.0-build/bin:/usr/bin:/bin
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
paper04_root=/public/home/jiangxinwei.zr/work/paper04
paper04_package="$paper04_root/runs/dense_reference_ab_stage_candidate_v1_20261028"
paper04_runtime="${paper04_package}_runtime"
paper04_python=/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python
paper04_environment="$paper04_root/frontend_compat_v1/environment.sh"
paper04_previous="$paper04_root/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science"
[[ ${SLURM_JOB_ID:-} =~ ^[0-9]+$ ]]
paper04_attempt="$paper04_runtime/job_$SLURM_JOB_ID"
# The runtime parent and Slurm log folder must be created before sbatch.
mkdir "$paper04_attempt"
paper04_pid=""
paper04_stage=entry
paper04_exit() {
  paper04_code=$?
  trap - EXIT
  "$paper04_python" -B "$paper04_package/hpc/fallback.py" --output "$paper04_attempt" \
    --exit-code "$paper04_code" --stage "$paper04_stage" || true
  exit "$paper04_code"
}
paper04_term() {
  if [[ -n "$paper04_pid" ]]; then kill -TERM "$paper04_pid" 2>/dev/null || true; wait "$paper04_pid" || true; fi
  exit 143
}
trap paper04_exit EXIT
trap paper04_term TERM INT
[[ -r "$paper04_environment" ]]
printf '%s  %s\n' '8da8564e759d51df121eaf9230a3e34c358e3abd10d9ce8dc8fe4b92e0763fcf' "$paper04_environment" | sha256sum --check --status
if ! type module >/dev/null 2>&1; then
  for paper04_init in /etc/profile.d/modules.sh /etc/profile.d/lmod.sh /usr/share/Modules/init/bash /usr/share/lmod/lmod/init/bash; do
    if [[ -r "$paper04_init" ]]; then source "$paper04_init"; if type module >/dev/null 2>&1; then break; fi; fi
  done
fi
source "$paper04_environment"
export PYTHONPATH="$paper04_previous/runtime/numpy201:$paper04_package/src:$paper04_package/vendor/encoding_v2/repo/ood:$paper04_root/environment/vendor_py311_v1${PYTHONPATH:+:$PYTHONPATH}"
cd "$paper04_package"
paper04_stage=package_sha
# Python splitlines accepts the sealed CRLF/LF manifest without weakening SHA.
timeout --signal=TERM --kill-after=10s 180s "$paper04_python" -B -c \
  'from common import verify_package; import sys; print(verify_package(sys.argv[1]))' \
  "$paper04_package" > "$paper04_attempt/package_sha.log" 2>&1
paper04_stage=synthetic_tests
timeout --signal=TERM --kill-after=10s 240s "$paper04_python" -B -m unittest discover -s tests -v \
  > "$paper04_attempt/tests.log" 2>&1
paper04_stage=authorized_ab_stage
"$paper04_python" -B -u src/launch_stage.py --package "$paper04_package" \
  --assets-root "$paper04_root" --manifest "$paper04_package/config/MATRIX_CANDIDATE_HPC.json" \
  --source-cal-result "$paper04_previous/source_cal/RESULT.json" \
  --approval-file "$paper04_package/.private/APPROVED.json" \
  --output "$paper04_attempt/science" &
paper04_pid=$!
wait "$paper04_pid"
paper04_pid=""
paper04_stage=complete
