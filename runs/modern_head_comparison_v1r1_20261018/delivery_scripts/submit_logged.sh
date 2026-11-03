#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
mode=full
if [[ "$#" == 2 && "$2" == --heads-only ]]; then mode=heads; fi
if [[ "$#" == 2 && "$2" == --modules-only ]]; then mode=modules; fi
mkdir -p "logs/$mode"
bash scripts/submit_once.sh "$@" 2>&1 | tee -a "logs/$mode/operator_submit.log"
rc=${PIPESTATUS[0]}
printf 'SUBMIT_EXIT_CODE=%s\n' "$rc" | tee -a "logs/$mode/operator_submit.log"
exit "$rc"
