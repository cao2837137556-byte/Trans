#!/bin/bash
# Submission is separate. This file never authorizes or resubmits a job.
#SBATCH --job-name=p04-dense-batchfix
#SBATCH --partition=amd
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --no-requeue
#SBATCH --signal=B:TERM@120
#SBATCH --output=/public/home/jiangxinwei.zr/work/paper04/runs/dense_reference_batch_repair_v1_20261027_runtime/slurm-%j.log
set -Eeuo pipefail
export PATH=/usr/local/slurm-25.11.0-build/bin:/usr/bin:/bin
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
paper04_root=/public/home/jiangxinwei.zr/work/paper04
paper04_original="$paper04_root/runs/dense_reference_matrix_v1_20261027"
paper04_overlay="$paper04_root/runs/dense_reference_batch_repair_v1_20261027"
paper04_runtime="$paper04_root/runs/dense_reference_batch_repair_v1_20261027_runtime"
paper04_python=/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python
paper04_environment="$paper04_root/frontend_compat_v1/environment.sh"
[[ ${SLURM_JOB_ID:-} =~ ^[1-9][0-9]*$ ]]
paper04_attempt="$paper04_runtime/job_$SLURM_JOB_ID"
mkdir "$paper04_attempt"
paper04_pid=""
paper04_stage=entry
paper04_error_line=0
paper04_mark() {
  paper04_stage=$1
  "$paper04_python" -B "$paper04_overlay/repair_gate.py" record \
    --output "$paper04_attempt" --stage "$paper04_stage" --status RUNNING
}
paper04_exit() {
  paper04_code=$?
  trap - EXIT ERR
  paper04_status=EXCEPTION_STOP
  if [[ $paper04_code -eq 0 && $paper04_stage == complete ]]; then paper04_status=COMPLETE; fi
  paper04_record_code=0
  "$paper04_python" -B "$paper04_overlay/repair_gate.py" record \
    --output "$paper04_attempt" --stage "$paper04_stage" --status "$paper04_status" \
    --returncode "$paper04_code" --line "$paper04_error_line" || paper04_record_code=$?
  if [[ $paper04_code -eq 0 && $paper04_record_code -ne 0 ]]; then paper04_code=$paper04_record_code; fi
  exit "$paper04_code"
}
paper04_term() {
  if [[ -n "$paper04_pid" ]]; then kill -TERM "$paper04_pid" 2>/dev/null || true; wait "$paper04_pid" || true; fi
  exit 143
}
trap 'paper04_error_line=$LINENO' ERR
trap paper04_exit EXIT
trap paper04_term TERM INT
paper04_mark approval_and_seals
timeout --signal=TERM --kill-after=10s 180s "$paper04_python" -B "$paper04_overlay/repair_gate.py" verify \
  --original "$paper04_original" --overlay "$paper04_overlay" \
  --approval-file "$paper04_overlay/.private/APPROVED.json" \
  --output "$paper04_attempt/PACKAGE_GATE.json" > "$paper04_attempt/package_sha.log" 2>&1
paper04_mark environment_sha
printf '%s  %s\n' '8da8564e759d51df121eaf9230a3e34c358e3abd10d9ce8dc8fe4b92e0763fcf' "$paper04_environment" | sha256sum --check --status
paper04_mark module_initialization
if ! type module >/dev/null 2>&1; then
  for paper04_init in /etc/profile.d/modules.sh /etc/profile.d/lmod.sh /usr/share/Modules/init/bash /usr/share/lmod/lmod/init/bash; do
    if [[ -r "$paper04_init" ]]; then source "$paper04_init"; if type module >/dev/null 2>&1; then break; fi; fi
  done
fi
type module >/dev/null 2>&1
source "$paper04_environment"
export PYTHONPATH="$paper04_root/environment/vendor_py311_v1:$paper04_original/src:$paper04_original/vendor/encoding_v2/repo/ood${PYTHONPATH:+:$PYTHONPATH}"
paper04_mark synthetic_tests
export PAPER04_FROZEN_R2_TEST_ROOT="$paper04_original"
# Inert synthetic fixtures only: no real checkpoint/model forward or training.
timeout --signal=TERM --kill-after=10s 240s "$paper04_python" -B -m unittest discover \
  -s "$paper04_overlay" -p 'test_*.py' -v > "$paper04_attempt/tests.log" 2>&1
paper04_mark repaired_chain
"$paper04_python" -B -u "$paper04_overlay/run_repaired_chain.py" --original "$paper04_original" \
  --overlay "$paper04_overlay" --assets-root "$paper04_root" --checkpoint "$paper04_root/assets/model.safetensors" \
  --approval-file "$paper04_overlay/.private/APPROVED.json" --output "$paper04_attempt/science" --execute &
paper04_pid=$!
wait "$paper04_pid"
paper04_pid=""
paper04_mark complete
