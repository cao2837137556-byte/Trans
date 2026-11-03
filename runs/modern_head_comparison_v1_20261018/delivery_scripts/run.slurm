#!/usr/bin/env bash
#SBATCH --job-name=modern-head-v1
#SBATCH --partition=amd
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=3-00:00:00
#SBATCH --no-requeue
#SBATCH --signal=B:TERM@180
#SBATCH --output=logs/slurm-%j.out
#SBATCH --error=logs/slurm-%j.err
set -eo pipefail
export MODERN_HEAD_ROOT="$SLURM_SUBMIT_DIR"
cd "$MODERN_HEAD_ROOT"
mkdir -p logs
FALLBACK_PYTHON=/public/home/jiangxinwei.zr/work/kitsune/env/kitsune_py39/bin/python
finish() {
  experiment_rc=$?
  trap - EXIT
  set +e
  status_rc=0
  printf '%s\n' "$experiment_rc" > experiment_exit_code.txt || status_rc=74
  sacct -j "$SLURM_JOB_ID" --format=JobID,State,ExitCode,Elapsed,ReqMem,AllocCPUS,MaxRSS,MaxRSSNode,MaxRSSTask,AveRSS -P > logs/sacct_at_exit.txt 2>&1 || true
  "$FALLBACK_PYTHON" repo/ood/modern_head_delivery_io_v1.py export --root "$MODERN_HEAD_ROOT"
  export_rc=$?
  # These receipts are produced after archive creation and pulled separately.
  printf '%s\n' "$export_rc" > export_exit_code.txt || status_rc=74
  final_rc=$experiment_rc
  if (( final_rc == 0 )); then final_rc=$export_rc; fi
  if (( final_rc == 0 )); then final_rc=$status_rc; fi
  if ! printf '%s\n' "$final_rc" > exit_code.txt; then
    status_rc=74
    if (( final_rc == 0 )); then final_rc=74; fi
  fi
  if (( export_rc != 0 )); then
    echo 'EXPORT_FAILED; preserve remote files; repair export only; do not resubmit experiment' >&2
  fi
  if (( status_rc != 0 )); then echo 'STATUS_WRITE_FAILED; inspect job stderr and exit code' >&2; fi
  printf 'EXPERIMENT_EXIT=%s EXPORT_EXIT=%s JOB_EXIT=%s\n' "$experiment_rc" "$export_rc" "$final_rc"
  exit "$final_rc"
}
trap finish EXIT
trap 'exit 143' TERM INT
source scripts/env.sh
FALLBACK_PYTHON="$MODERN_HEAD_PYTHON"
[[ "${MODERN_HEAD_AUTHORIZED:-}" =~ ^[0-9a-f]{64}$ ]] || { echo NO_EXECUTION_AUTHORITY; exit 2; }
[[ "${MODERN_HEAD_RESOURCE_SHA:-}" =~ ^[0-9a-f]{64}$ ]] || { echo RESOURCE_IDENTITY_REQUIRED; exit 2; }
printf '%s  %s\n' "$MODERN_HEAD_AUTHORIZED" experiment_contract.json | sha256sum -c - > logs/compute_contract_sha.log
printf '%s  %s\n' "$MODERN_HEAD_RESOURCE_SHA" resource_plan.json | sha256sum -c - > logs/compute_resource_sha.log
sha256sum -c SHA256SUMS > logs/compute_package_sha.log
"$MODERN_HEAD_PYTHON" repo/ood/modern_head_runner_v1.py resources --root "$MODERN_HEAD_ROOT"
export TMPDIR="$MODERN_HEAD_ROOT/synthetic_tmp"
mkdir -p "$TMPDIR"
"$MODERN_HEAD_PYTHON" repo/ood/modern_head_synthetic_checks_v1.py --root "$MODERN_HEAD_ROOT" --output "$MODERN_HEAD_ROOT/logs/synthetic" > logs/target_synthetic.log 2>&1
"$MODERN_HEAD_PYTHON" repo/ood/modern_head_runner_v1.py run --root "$MODERN_HEAD_ROOT" --authorize-chain &
child=$!
trap 'kill -TERM "$child" 2>/dev/null || true; wait "$child" || true; exit 143' TERM INT
wait "$child"
