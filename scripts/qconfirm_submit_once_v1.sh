#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export QCONF_ROOT="$PWD"
test "$QCONF_ROOT" = /public/home/jiangxinwei.zr/work/legacy_qref_device_confirmation_v1_20260923
test -f authorization.json
test ! -e runs/confirmation
test ! -e runs/target_synthetic
source scripts/qconfirm_env_v1.sh
"$QCONF_PYTHON" -B repo/ood/legacy_qconfirm_runner_v1.py check-scope --root "$QCONF_ROOT" --out "$QCONF_ROOT/runs/confirmation" --authorization "$QCONF_ROOT/authorization.json" --execute
mkdir submit_claim
mkdir -p logs
sbatch --parsable --export=ALL,QCONF_ROOT="$QCONF_ROOT" scripts/qconfirm_run_v1.slurm > submit_claim/response.txt
jid=$(cut -d';' -f1 submit_claim/response.txt | tr -d '\r\n')
case "$jid" in ''|*[!0-9]*) echo 'Invalid job ID; do not resubmit'; exit 2;; esac
printf '%s\n' "$jid" > submit_claim/job_id.txt
printf 'SUBMITTED_DEVICE_CONFIRMATION job=%s\n' "$jid"
