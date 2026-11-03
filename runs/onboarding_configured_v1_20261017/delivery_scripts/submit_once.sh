#!/usr/bin/env bash
set -euo pipefail
[[ "$#" == 1 ]] || { echo 'Requires explicit whole onboarding chain authority'; exit 2; }
[[ "$1" == "--authorize-chain" ]] || exit 2
cd "$(dirname "$0")/.."
mkdir -p logs
export ONBOARDING_ROOT="$PWD"
source scripts/env.sh
test ! -e runs/onboarding
test ! -e submit_claim
sha256sum -c SHA256SUMS > logs/package_sha.log
selection=$("$ONBOARDING_PYTHON" repo/ood/onboarding_resources_v1.py --plan resource_plan.json --slurm-fields)
read -r planned_memory planned_cpus resource_sha extra <<< "$selection"
[[ "$planned_memory" =~ ^[0-9]+$ && "$planned_cpus" =~ ^[0-9]+$ && "$resource_sha" =~ ^[0-9a-f]{64}$ && -z "$extra" ]] || exit 2
export ONBOARDING_RESOURCE_SHA="$resource_sha"
allocation=(--mem="${planned_memory}G" --cpus-per-task="$planned_cpus")
"$ONBOARDING_PYTHON" repo/ood/onboarding_delivery_v1.py preflight --root "$ONBOARDING_ROOT" > logs/input_preflight.log 2>&1 || { cat logs/input_preflight.log; exit 1; }
sbatch --test-only "${allocation[@]}" scripts/run.slurm > logs/scheduler_preflight.log 2>&1 || { cat logs/scheduler_preflight.log; exit 1; }
printf '%s  %s\n' "$resource_sha" resource_plan.json | sha256sum -c - > logs/resource_plan_sha.log
sha256sum -c SHA256SUMS > logs/package_sha_after_preflight.log
mkdir submit_claim
export ONBOARDING_AUTHORIZED=2fae0e1c8e1b5d6c04de8a972bfe0212ecfad27dbaf91066d267ccc746aaa4b5
job=$(sbatch --parsable "${allocation[@]}" scripts/run.slurm 2>logs/submit.stderr.log) || { echo 'SUBMIT_FAILED; claim retained; no retry'; exit 1; }
job=$(printf '%s' "$job" | cut -d ';' -f 1)
[[ "$job" =~ ^[0-9]+$ ]] || { echo 'AMBIGUOUS_SUBMISSION; no retry'; exit 1; }
printf '%s\n' "$job" > job.id
echo "SUBMITTED_ONBOARDING_CHAIN job=$job"
