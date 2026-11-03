#!/usr/bin/env bash
set -euo pipefail
[[ "$#" == 1 || "$#" == 2 ]] || { echo 'Requires --authorize-chain [--heads-only|--modules-only]'; exit 2; }
[[ "$1" == '--authorize-chain' ]] || exit 2
mode=full
phase_args=()
if [[ "$#" == 2 ]]; then
  case "$2" in
    --heads-only) mode=heads; phase_args=(--heads-only);;
    --modules-only) mode=modules; phase_args=(--modules-only);;
    *) echo INVALID_PHASE_ARGUMENT; exit 2;;
  esac
fi
cd "$(dirname "$0")/.."
export MODERN_HEAD_ROOT="$PWD" MODERN_HEAD_EXECUTION_MODE="$mode"
logdir="logs/$mode"
mkdir -p "$logdir"
[[ -d extra_deps ]] || { echo 'DEPENDENCY_DIRECTORY_MISSING: run setup_dependencies.py offline before submission'; exit 2; }
[[ -f dependency_install_receipt.json ]] || { echo 'DEPENDENCY_RECEIPT_MISSING: inspect offline installation; do not submit'; exit 2; }
if [[ "$mode" == modules ]]; then
  [[ -f runs/modern_heads/HEADS_COMPLETE.json && ! -e runs/modern_heads/MODULES_STARTED.json && ! -e submit_claim.modules && ! -e submit_claim.full ]] || { echo MODULES_NOT_READY_OR_ALREADY_CLAIMED; exit 2; }
  [[ -f status/heads/exit_code.txt && "$(cat status/heads/exit_code.txt)" == 0 ]] || { echo HEADS_JOB_NOT_SUCCESSFULLY_FINALIZED; exit 2; }
else
  [[ ! -e runs/modern_heads && ! -e submit_claim.heads && ! -e submit_claim.full && ! -e submit_claim.modules ]] || { echo HEADS_ALREADY_STARTED_OR_CLAIMED; exit 2; }
fi
source scripts/env.sh
sha256sum -c SHA256SUMS > "$logdir/package_sha.log"
selection=$("$MODERN_HEAD_PYTHON" repo/ood/modern_head_runner_v1.py resources --root "$MODERN_HEAD_ROOT" --slurm-fields)
read -r planned_memory planned_cpus resource_sha contract_sha extra <<< "$selection"
[[ "$planned_memory" =~ ^[0-9]+$ && "$planned_cpus" =~ ^[0-9]+$ && "$resource_sha" =~ ^[0-9a-f]{64}$ && "$contract_sha" =~ ^[0-9a-f]{64}$ && -z "$extra" ]] || exit 2
export MODERN_HEAD_RESOURCE_SHA="$resource_sha"
allocation=(--mem="${planned_memory}G" --cpus-per-task="$planned_cpus" --output="$logdir/slurm-%j.out" --error="$logdir/slurm-%j.err")
"$MODERN_HEAD_PYTHON" repo/ood/modern_head_runner_v1.py preflight --root "$MODERN_HEAD_ROOT" "${phase_args[@]}" > "$logdir/input_preflight.log" 2>&1 || { cat "$logdir/input_preflight.log"; exit 1; }
sbatch --test-only "${allocation[@]}" scripts/run.slurm > "$logdir/scheduler_preflight.log" 2>&1 || { cat "$logdir/scheduler_preflight.log"; exit 1; }
printf '%s  %s\n' "$resource_sha" resource_plan.json | sha256sum -c - > "$logdir/resource_plan_sha.log"
printf '%s  %s\n' "$contract_sha" experiment_contract.json | sha256sum -c - > "$logdir/contract_sha.log"
sha256sum -c SHA256SUMS > "$logdir/package_sha_after_preflight.log"
# full and heads compete for the same atomic heads claim; it is never removed.
if [[ "$mode" == full ]]; then
  mkdir submit_claim.heads
  mkdir submit_claim.full
else
  mkdir "submit_claim.$mode"
fi
export MODERN_HEAD_AUTHORIZED="$contract_sha"
job=$(sbatch --parsable "${allocation[@]}" scripts/run.slurm 2>"$logdir/submit.stderr.log") || { echo 'SUBMIT_FAILED; claim retained; no retry'; exit 1; }
job=$(printf '%s' "$job" | cut -d ';' -f 1)
[[ "$job" =~ ^[0-9]+$ ]] || { echo 'AMBIGUOUS_SUBMISSION; no retry'; exit 1; }
printf '%s\n' "$job" > "job.$mode.id"
echo "SUBMITTED_MODERN_HEAD_${mode} job=$job"
