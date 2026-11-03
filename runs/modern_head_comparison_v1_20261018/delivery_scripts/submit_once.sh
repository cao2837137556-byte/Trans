#!/usr/bin/env bash
set -euo pipefail
[[ "$#" == 1 ]] || { echo 'Requires explicit whole modern-head chain authority'; exit 2; }
[[ "$1" == "--authorize-chain" ]] || exit 2
cd "$(dirname "$0")/.."
mkdir -p logs
export MODERN_HEAD_ROOT="$PWD"
source scripts/env.sh
test ! -e runs/modern_heads
test ! -e submit_claim
sha256sum -c SHA256SUMS > logs/package_sha.log
selection=$("$MODERN_HEAD_PYTHON" repo/ood/modern_head_runner_v1.py resources --root "$MODERN_HEAD_ROOT" --slurm-fields)
read -r planned_memory planned_cpus resource_sha contract_sha extra <<< "$selection"
[[ "$planned_memory" =~ ^[0-9]+$ && "$planned_cpus" =~ ^[0-9]+$ && "$resource_sha" =~ ^[0-9a-f]{64}$ && "$contract_sha" =~ ^[0-9a-f]{64}$ && -z "$extra" ]] || exit 2
export MODERN_HEAD_RESOURCE_SHA="$resource_sha"
allocation=(--mem="${planned_memory}G" --cpus-per-task="$planned_cpus")
"$MODERN_HEAD_PYTHON" repo/ood/modern_head_runner_v1.py preflight --root "$MODERN_HEAD_ROOT" > logs/input_preflight.log 2>&1 || { cat logs/input_preflight.log; exit 1; }
sbatch --test-only "${allocation[@]}" scripts/run.slurm > logs/scheduler_preflight.log 2>&1 || { cat logs/scheduler_preflight.log; exit 1; }
printf '%s  %s\n' "$resource_sha" resource_plan.json | sha256sum -c - > logs/resource_plan_sha.log
printf '%s  %s\n' "$contract_sha" experiment_contract.json | sha256sum -c - > logs/contract_sha.log
sha256sum -c SHA256SUMS > logs/package_sha_after_preflight.log
mkdir submit_claim
export MODERN_HEAD_AUTHORIZED="$contract_sha"
job=$(sbatch --parsable "${allocation[@]}" scripts/run.slurm 2>logs/submit.stderr.log) || { echo 'SUBMIT_FAILED; claim retained; no retry'; exit 1; }
job=$(printf '%s' "$job" | cut -d ';' -f 1)
[[ "$job" =~ ^[0-9]+$ ]] || { echo 'AMBIGUOUS_SUBMISSION; no retry'; exit 1; }
printf '%s\n' "$job" > job.id
echo "SUBMITTED_MODERN_HEAD_CHAIN job=$job"
