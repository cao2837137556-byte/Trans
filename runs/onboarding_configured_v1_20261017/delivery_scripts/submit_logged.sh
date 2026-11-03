#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
bash scripts/submit_once.sh "$@" 2>&1 | tee -a logs/operator_submit.log
rc=${PIPESTATUS[0]}
printf 'SUBMIT_EXIT_CODE=%s\n' "$rc" | tee -a logs/operator_submit.log
exit "$rc"
