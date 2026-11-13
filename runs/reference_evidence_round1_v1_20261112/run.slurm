#!/bin/bash
set -euo pipefail
umask 077

phase="$1"
out="$2"
project="$3"
export ROUND1_MEMORY_MIB="$4"
# Slurm can spool the script outside the package. The submitter sets its working directory.
package="$(pwd -P)"
stage=COMPUTE_STARTUP
trap 'rc=$?; if [ "$rc" -ne 0 ]; then file="$out/SLURM_STOP_$phase.json"; printf "{\"phase\":\"%s\",\"stage\":\"%s\",\"exit_code\":%d,\"job_id\":\"%s\"}\n" "$phase" "$stage" "$rc" "${SLURM_JOB_ID:-unknown}" > "$file.$$"; mv -- "$file.$$" "$file"; fi' EXIT
printf '{"phase":"%s","job_id":"%s","node":"%s"}\n' "$phase" "${SLURM_JOB_ID:?}" "${SLURMD_NODENAME:?}" > "$out/STARTUP_$phase.json"
test -r "$package/PACKAGE_MANIFEST.json"
# Load the ledger's project environment when present, with the accepted
# October/November frontend wrapper supplying the frozen replay runtime.
if [ -r "$project/scripts/00_env_issue27ckc.sh" ]; then
    source "$project/scripts/00_env_issue27ckc.sh"
fi
source "$project/frontend_compat_v1/environment.sh"
runtime="$project/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201"
test -d "$runtime/numpy"
export PYTHONPATH="$runtime:$project/environment/vendor_py311_v1"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
test "$PAPER04_PYTHON" = /share/software/miniconda3.2025/envs/torch_demo_2025/bin/python
test -x "$PAPER04_PYTHON"
stage=WORKER
"$PAPER04_PYTHON" -X utf8 -B "$package/worker.py" "$phase" --project "$project" --out "$out"
