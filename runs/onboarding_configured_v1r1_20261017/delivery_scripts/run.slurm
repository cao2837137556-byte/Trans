#!/usr/bin/env bash
#SBATCH --job-name=onboarding-v1
#SBATCH --partition=amd
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=1-00:00:00
#SBATCH --no-requeue
#SBATCH --signal=B:TERM@180
#SBATCH --output=logs/slurm-%j.out
#SBATCH --error=logs/slurm-%j.err
set -eo pipefail
export ONBOARDING_ROOT="$SLURM_SUBMIT_DIR"
cd "$ONBOARDING_ROOT"
mkdir -p logs
FALLBACK_PYTHON=/public/home/jiangxinwei.zr/work/kitsune/env/kitsune_py39/bin/python
finish() {
  experiment_rc=$?
  trap - EXIT
  set +e
  status_rc=0
  printf '%s\n' "$experiment_rc" > experiment_exit_code.txt || status_rc=74
  sacct -j "$SLURM_JOB_ID" --format=JobID,State,ExitCode,Elapsed,ReqMem,AllocCPUS,MaxRSS,MaxRSSNode,MaxRSSTask,AveRSS -P > logs/sacct_at_exit.txt 2>&1 || true
  "$FALLBACK_PYTHON" repo/ood/onboarding_delivery_io_v1.py export --root "$ONBOARDING_ROOT"
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
FALLBACK_PYTHON="$ONBOARDING_PYTHON"
[[ "${ONBOARDING_AUTHORIZED:-}" == "2fae0e1c8e1b5d6c04de8a972bfe0212ecfad27dbaf91066d267ccc746aaa4b5" ]] || { echo NO_EXECUTION_AUTHORITY; exit 2; }
[[ "${ONBOARDING_RESOURCE_SHA:-}" =~ ^[0-9a-f]{64}$ ]] || { echo RESOURCE_IDENTITY_REQUIRED; exit 2; }
printf '%s  %s\n' "$ONBOARDING_RESOURCE_SHA" resource_plan.json | sha256sum -c - > logs/compute_resource_sha.log
sha256sum -c SHA256SUMS > logs/compute_package_sha.log
"$ONBOARDING_PYTHON" repo/ood/onboarding_resources_v1.py --plan resource_plan.json
export TMPDIR="$ONBOARDING_ROOT/synthetic_tmp"
mkdir -p "$TMPDIR"
"$ONBOARDING_PYTHON" repo/ood/onboarding_synthetic_checks_v1.py --root "$ONBOARDING_ROOT" --output "$ONBOARDING_ROOT/logs/synthetic" > logs/target_synthetic.log 2>&1
"$ONBOARDING_PYTHON" repo/ood/onboarding_delivery_v1.py run --root "$ONBOARDING_ROOT" --authorize-chain &
child=$!
trap 'kill -TERM "$child" 2>/dev/null || true; wait "$child" || true; exit 143' TERM INT
wait "$child"
