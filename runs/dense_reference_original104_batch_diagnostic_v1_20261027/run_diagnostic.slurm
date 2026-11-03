#!/bin/bash
# Prepared only; no submission occurs by creating or validating this file.
#SBATCH --job-name=p04-source8-diag
#SBATCH --partition=amd
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:10:00
#SBATCH --no-requeue
#SBATCH --signal=B:TERM@60
#SBATCH --output=/public/home/jiangxinwei.zr/work/paper04/runs/dense_reference_original104_batch_diagnostic_v1_20261027_runtime/slurm-%j.log
set -Eeuo pipefail
export PATH=/usr/local/slurm-25.11.0-build/bin:/usr/bin:/bin
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
paper04_root=/public/home/jiangxinwei.zr/work/paper04
paper04_package="$paper04_root/runs/dense_reference_original104_batch_diagnostic_v1_20261027"
paper04_runtime="$paper04_root/runs/dense_reference_original104_batch_diagnostic_v1_20261027_runtime"
paper04_original="$paper04_root/runs/dense_reference_matrix_v1_20261027"
paper04_numpy="$paper04_root/runs/dense_reference_launch_repair_v1_20261027/runtime/job_179536/science/runtime/numpy201"
paper04_python=/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python
paper04_environment="$paper04_root/frontend_compat_v1/environment.sh"
[[ ${SLURM_JOB_ID:-} =~ ^[1-9][0-9]*$ ]]
paper04_attempt="$paper04_runtime/job_$SLURM_JOB_ID"
mkdir "$paper04_attempt"
paper04_pid=""
paper04_stage=preflight
paper04_exit() {
  paper04_code=$?
  trap - EXIT ERR
  "$paper04_python" -B - "$paper04_attempt" "$paper04_code" "$paper04_stage" <<'PY'
import json, os, pathlib, sys
p=pathlib.Path(sys.argv[1]); code=int(sys.argv[2]); stage=sys.argv[3]
try: complete=json.loads((p/'science/status.json').read_text()).get('status')=='COMPLETE'
except (OSError,ValueError,AttributeError): complete=False
value=dict(status='COMPLETE' if code==0 and complete else 'EXCEPTION_STOP',stage=stage,returncode=code,
           reason=None if code==0 and complete else 'DIAGNOSTIC_LAUNCH_OR_WORKER_EXIT:'+str(code),
           retries=0,evidence_preserved=True,diagnostic_only=True)
temp=p/'launch.json.tmp'; temp.write_text(json.dumps(value)+'\n');os.replace(temp,p/'launch.json')
PY
  exit "$paper04_code"
}
paper04_term() {
  if [[ -n "$paper04_pid" ]]; then kill -TERM "$paper04_pid" 2>/dev/null || true; wait "$paper04_pid" || true; fi
  exit 143
}
trap paper04_exit EXIT
trap paper04_term TERM INT
"$paper04_python" -B "$paper04_package/diagnostic.py" --package "$paper04_package" > "$paper04_attempt/DRY_RUN.json"
paper04_stage=environment
printf '%s  %s\n' '8da8564e759d51df121eaf9230a3e34c358e3abd10d9ce8dc8fe4b92e0763fcf' "$paper04_environment" | sha256sum --check --status
if ! type module >/dev/null 2>&1; then
  for paper04_init in /etc/profile.d/modules.sh /etc/profile.d/lmod.sh /usr/share/Modules/init/bash /usr/share/lmod/lmod/init/bash; do
    if [[ -r "$paper04_init" ]]; then source "$paper04_init"; if type module >/dev/null 2>&1; then break; fi; fi
  done
fi
type module >/dev/null 2>&1
source "$paper04_environment"
export PYTHONPATH="$paper04_numpy:$paper04_root/environment/vendor_py311_v1:$paper04_original/vendor/encoding_v2/repo/ood${PYTHONPATH:+:$PYTHONPATH}"
paper04_stage=source8_diagnostic
"$paper04_python" -B -u "$paper04_package/diagnostic.py" --package "$paper04_package" --execute \
  --approval-file "$paper04_package/.private/APPROVED.json" --output "$paper04_attempt/science" &
paper04_pid=$!
wait "$paper04_pid"
paper04_pid=""
paper04_stage=complete
