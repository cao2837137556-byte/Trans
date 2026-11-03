#!/usr/bin/env bash
#SBATCH -J qref_confirm
#SBATCH -p amd
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --time=72:00:00
#SBATCH --no-requeue
#SBATCH --output=logs/confirmation_%j.out
#SBATCH --error=logs/confirmation_%j.err
set -Eeuo pipefail
: "${QCONF_ROOT:?missing QCONF_ROOT}"
cd "$QCONF_ROOT"
finish() {
  rc=$?
  trap - EXIT
  printf 'EXIT_CODE=%s\n' "$rc" > logs/job_exit.txt
  paths=(logs submit_claim authorization.json)
  for folder in runs/confirmation runs/target_synthetic; do
    if test -d "$folder"; then paths+=("$folder"); fi
  done
  if tar -czf confirmation_pullback.tar.gz "${paths[@]}" 2> export_error.txt; then
    sha256sum confirmation_pullback.tar.gz > confirmation_pullback.tar.gz.sha256
  else
    printf 'EXPORT_FAILED\n' >> logs/job_exit.txt
    test "$rc" -ne 0 || rc=90
  fi
  exit "$rc"
}
trap finish EXIT
sha256sum -c SHA256SUMS > logs/code_package_check.txt
source scripts/qconfirm_env_v1.sh
"$QCONF_PYTHON" -B -m unittest discover -s repo/ood -p test_legacy_qconfirm_v1.py -v > logs/target_tests.txt 2>&1
"$QCONF_PYTHON" -B repo/ood/legacy_qconfirm_fixture_v1.py --root "$QCONF_ROOT" --out runs/target_synthetic > logs/target_synthetic.txt 2>&1
"$QCONF_PYTHON" -B repo/ood/legacy_qconfirm_runner_v1.py run --root "$QCONF_ROOT" --out "$QCONF_ROOT/runs/confirmation" --authorization "$QCONF_ROOT/authorization.json" --execute
printf 'EXECUTION_FINISHED; READ_CONFIRMED_GATE; NO_TRAINING_OR_NEW_CALIBRATION\n'
