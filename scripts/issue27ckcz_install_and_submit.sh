#!/bin/bash
# CKCZ bundle installer and explicitly authorized AMD submission.
# Bundle/preflight checks always run; an actual sbatch requires the caller to
# set CKCZ_SUBMIT_AUTHORIZATION=YES after the user's separate authorization.
set -euo pipefail

HERE=$(cd "$(dirname "$0")/../.." && pwd)
BASE=${CKCZ_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
JOB_ID_FILE="$HERE/ckcz_seed27_amd_job_id.txt"
PAYLOAD="$HERE/payload"
CODE_ROOT="$PAYLOAD/repo/ood"
SCRIPT_ROOT="$PAYLOAD/scripts"

RUN154917="$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917"
CKBW157624="$BASE/runs/issue27ckbw_tail_margin_dual_control_v1_2026-08-03_seed27_amd_157624"
PREDICTIONS="$CKBW157624/ckbw_record_predictions.csv.gz"
PREDICTIONS_SHA256=d1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85
GOTHAM_MANIFEST="$RUN154917/ckbu_gotham_unified_causal_manifest.csv"
GOTHAM_MANIFEST_SHA256=aaef2a0c0e4cc28d3815dbff4152db2fbe8c7d953dc35cf05cd817c4135d4c22
AUXILIARY_MANIFEST="$RUN154917/ckbu_auxiliary_unified_causal_manifest.csv"
AUXILIARY_MANIFEST_SHA256=f2a674235cb929ed4b7ebb8723c53a4f314f4e4563e727e3f4a2e0a4ab201e43
GOTHAM_CACHE="$RUN154917/gotham_causal_cache"
AUXILIARY_CACHE="$RUN154917/auxiliary_causal_cache"

DIAGNOSTIC="$CODE_ROOT/issue27ckcz_endpoint_pair_conflict_diagnostic_v1.py"
CONTRACT_TESTS="$CODE_ROOT/issue27ckcz_endpoint_pair_conflict_contract_tests_v1.py"
VALIDATOR="$SCRIPT_ROOT/issue27ckcz_validate_and_pack_seed27.sh"
SLURM="$SCRIPT_ROOT/issue27ckcz_endpoint_pair_conflict_diagnostic_formal.slurm"
PREREG="$PAYLOAD/runs/mainline_docs/ckcz_endpoint_pair_conflict_diagnostic_preregistered_20260809.md"
PREREG_SHA256=dad558902f2dfe2dc0dd4bf76cbf2e9e727be9f5d22ed2e91a5267586e8d3fde
GOTHAM_ALLOWLIST="$PAYLOAD/runs/mainline_docs/ckcz_gotham_source_allowlist_20260809.csv"
GOTHAM_ALLOWLIST_SHA256=65b4804109914d50c3efb6b9ae40d2b7d7befc903be571a92ebee90624ab6de7
AUXILIARY_ALLOWLIST="$PAYLOAD/runs/mainline_docs/ckcz_auxiliary_source_allowlist_20260809.csv"
AUXILIARY_ALLOWLIST_SHA256=be4ad12a9b0807b15b120d91ec2f9519a1743120ef0e9f04e0d8bab573252c49

for path in \
  "$BASE/scripts/00_env_issue27ckc.sh" "$DIAGNOSTIC" "$CONTRACT_TESTS" \
  "$VALIDATOR" "$SLURM" "$PREREG" "$GOTHAM_ALLOWLIST" "$AUXILIARY_ALLOWLIST" \
  "$GOTHAM_MANIFEST" "$AUXILIARY_MANIFEST" "$PREDICTIONS"; do
  test -s "$path" || { echo "missing CKCZ runtime asset: $path" >&2; exit 2; }
done
for directory in "$GOTHAM_CACHE" "$AUXILIARY_CACHE"; do
  test -d "$directory" || { echo "missing CKCZ runtime cache: $directory" >&2; exit 2; }
done

echo "=== CKCZ bundle integrity ==="
cd "$HERE"
sha256sum -c SHA256SUMS

echo "=== CKCZ immutable input identities ==="
for pair in \
  "$PREREG:$PREREG_SHA256" \
  "$GOTHAM_ALLOWLIST:$GOTHAM_ALLOWLIST_SHA256" \
  "$AUXILIARY_ALLOWLIST:$AUXILIARY_ALLOWLIST_SHA256" \
  "$GOTHAM_MANIFEST:$GOTHAM_MANIFEST_SHA256" \
  "$AUXILIARY_MANIFEST:$AUXILIARY_MANIFEST_SHA256" \
  "$PREDICTIONS:$PREDICTIONS_SHA256"; do
  asset=${pair%%:*}
  expected=${pair#*:}
  test "$(sha256sum "$asset" | awk '{print $1}')" = "$expected" || {
    echo "immutable CKCZ asset drift: $asset" >&2; exit 2;
  }
done

echo "=== CKCZ auxiliary/Gotham online launch gate ==="
gotham_npz=$(find "$GOTHAM_CACHE" -maxdepth 1 -type f -name '*.npz' -printf '.' | wc -c)
auxiliary_npz=$(find "$AUXILIARY_CACHE" -maxdepth 1 -type f -name '*.npz' -printf '.' | wc -c)
test "$gotham_npz" -eq 29 || { echo "Gotham cache file-count drift: $gotham_npz" >&2; exit 2; }
test "$auxiliary_npz" -eq 31 || { echo "auxiliary cache file-count drift: $auxiliary_npz" >&2; exit 2; }
printf 'CKCZ_CACHE_ONLINE_GATE_PASS gotham_npz=%s auxiliary_npz=%s auxiliary_size=%s\n' \
  "$gotham_npz" "$auxiliary_npz" "$(du -sh "$AUXILIARY_CACHE" | awk '{print $1}')"

echo "=== CKCZ allowed environment and contract suite ==="
cd "$BASE"
source scripts/00_env_issue27ckc.sh
export PYTHONPATH="$CODE_ROOT${PYTHONPATH:+:$PYTHONPATH}"
python -m py_compile "$DIAGNOSTIC" "$CONTRACT_TESTS"
python "$CONTRACT_TESTS"
bash -n "$VALIDATOR" "$SLURM"

DIAGNOSTIC_SHA256=$(sha256sum "$DIAGNOSTIC" | awk '{print $1}')
VALIDATOR_SHA256=$(sha256sum "$VALIDATOR" | awk '{print $1}')
EXPORTS="ALL,CKCZ_COMMIT_SHA=$COMMIT_SHA,CKCZ_BUNDLE_ROOT=$HERE,CKCZ_DIAGNOSTIC_SHA256=$DIAGNOSTIC_SHA256,CKCZ_VALIDATOR_SHA256=$VALIDATOR_SHA256"

for token in \
  'BUNDLE_ROOT=${CKCZ_BUNDLE_ROOT:?missing CKCZ_BUNDLE_ROOT}' \
  'DIAGNOSTIC_SHA256=${CKCZ_DIAGNOSTIC_SHA256:?missing CKCZ_DIAGNOSTIC_SHA256}' \
  'VALIDATOR_SHA256=${CKCZ_VALIDATOR_SHA256:?missing CKCZ_VALIDATOR_SHA256}' \
  '--gotham-allowlist "$GOTHAM_ALLOWLIST"' \
  '--auxiliary-allowlist "$AUXILIARY_ALLOWLIST"' \
  '--bootstrap-reps 200' \
  '--preregistered-protocol "$PREREG"' \
  'write_phase diagnostic_real_inputs' \
  'write_phase validate_result' \
  'bash "$VALIDATOR" "$RUN_ROOT"' \
  'CKCZ_DIAGNOSTIC_COMPLETE'; do
  grep -Fq -- "$token" "$SLURM" || { echo "CKCZ Slurm wiring missing: $token" >&2; exit 2; }
done

echo "=== CKCZ Slurm scheduler dry validation ==="
sbatch --test-only -p amd --export="$EXPORTS" "$SLURM"

if test "${CKCZ_SUBMIT_AUTHORIZATION:-}" != YES; then
  echo "CKCZ_PRE_SUBMIT_PASS"
  echo "CKCZ_HPC_SUBMISSION_NOT_AUTHORIZED"
  echo "No job was submitted. Set CKCZ_SUBMIT_AUTHORIZATION=YES only after the user's explicit authorization."
  exit 3
fi

read_id() {
  local path=$1
  local value=""
  test ! -s "$path" || value=$(tr -d '\r\n' < "$path")
  if test -n "$value" && [[ ! "$value" =~ ^[0-9]+$ ]]; then
    echo "invalid stored CKCZ job id in $path: $value" >&2; exit 2
  fi
  printf '%s' "$value"
}

store_id() {
  local path=$1
  local value=$2
  local temporary="${path}.tmp.$$"
  printf '%s\n' "$value" > "$temporary"
  mv "$temporary" "$path"
}

job=$(read_id "$JOB_ID_FILE")
if test -z "$job"; then
  echo "=== CKCZ submit AMD seed-27 diagnostic ==="
  job=$(sbatch --parsable -p amd \
    --output="$BASE/runs/issue27ckcz_diag_amd_%j.out" \
    --error="$BASE/runs/issue27ckcz_diag_amd_%j.err" \
    --export="$EXPORTS" "$SLURM")
  [[ "$job" =~ ^[0-9]+$ ]] || { echo "invalid CKCZ job id: $job" >&2; exit 2; }
  store_id "$JOB_ID_FILE" "$job"
else
  echo "CKCZ AMD job already recorded; not resubmitting: $job"
fi
printf 'CKCZ_AMD_JOB_ID=%s\nCKCZ_SUBMISSION_RECORDED\n' "$job"

phase_rank() {
  case "$1" in
    startup) printf 1 ;;
    contract_checks) printf 2 ;;
    diagnostic_real_inputs) printf 3 ;;
    validate_result) printf 4 ;;
    resource_accounting) printf 5 ;;
    complete) printf 6 ;;
    *) printf 0 ;;
  esac
}

job_state() {
  local value=""
  value=$(squeue -h -j "$1" -o '%T' 2>/dev/null | head -n 1 || true)
  if test -z "$value"; then
    value=$(sacct -j "$1" -X -n -P --format=State 2>/dev/null |
      head -n 1 | cut -d'|' -f1 | sed 's/+.*//' | tr -d '[:space:]' || true)
  fi
  printf '%s' "${value:-UNKNOWN}"
}

echo "=== CKCZ post-submit result-producing gate ==="
echo "Passes only after the real diagnostic and post-result validator both finish."
deadline=$(( $(date +%s) + ${CKCZ_RUNTIME_GATE_SECONDS:-3600} ))
gate=pending
root="$BASE/runs/issue27ckcz_endpoint_pair_conflict_diagnostic_v1_2026-08-10_seed27_amd_${job}"
control="$BASE/runs/issue27ckcz_endpoint_pair_conflict_diagnostic_v1_2026-08-10_seed27_amd_${job}_control"
while test "$(date +%s)" -lt "$deadline"; do
  phase=unknown
  test ! -s "$control/current_phase.txt" || \
    phase=$(awk -F= '$1 == "phase" {print $2; exit}' "$control/current_phase.txt")
  state=$(job_state "$job")
  if test "$(phase_rank "$phase")" -ge 5; then
    gate=passed
    echo "CKCZ_RUNTIME_GATE_PASS job=$job phase=$phase state=$state"
    break
  fi
  case "$state" in
    FAILED|TIMEOUT|OUT_OF_MEMORY|NODE_FAIL|BOOT_FAIL|PREEMPTED)
      gate=failed
      echo "CKCZ_RUNTIME_GATE_FAIL job=$job phase=$phase state=$state" >&2
      break
      ;;
    CANCELLED)
      gate=cancelled
      echo "CKCZ_RUNTIME_GATE_CANCELLED job=$job phase=$phase" >&2
      break
      ;;
  esac
  sleep 10
done

if test "$gate" = failed || test "$gate" = cancelled; then
  test ! -s "$control/job_failure.txt" || cat "$control/job_failure.txt" >&2
  test ! -s "$BASE/runs/issue27ckcz_diag_amd_${job}.err" || tail -80 "$BASE/runs/issue27ckcz_diag_amd_${job}.err" >&2
  echo "CKCZ_SUBMISSION_RUNTIME_FAILED" >&2
  exit 4
fi
if test "$gate" != passed; then
  echo "CKCZ_SUBMITTED_NOT_YET_RESULT_VALIDATED gate=$gate"
  echo "The job may still be queued or running. Monitor with: squeue -j $job"
  exit 0
fi
test ! -e "$root/job_failure.txt" || { cat "$root/job_failure.txt" >&2; exit 4; }
echo "CKCZ_SUBMISSION_RUNTIME_VALIDATED"
