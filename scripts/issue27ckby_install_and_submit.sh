#!/bin/bash
# CKBY: verify bundle + immutable assets, then submit the DROCC feature
# snapshot dump job on the amd partition.  Mirrors the CKBW installer
# structure.  Idempotent: a recorded job id is never resubmitted.
set -euo pipefail

HERE=$(cd "$(dirname "$0")/.." && pwd)
BASE=${CKBY_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
AMD_ID_FILE="$HERE/ckby_dump_seed27_amd_job_id.txt"
CODE_ROOT="$HERE/payload/repo/ood"
SCRIPT_ROOT="$HERE/payload/scripts"

RUN154917="$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917"
CKBW157624="$BASE/runs/issue27ckbw_tail_margin_dual_control_v1_2026-08-03_seed27_amd_157624"
T0_ROOT="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
REPORT_T0_EXTENSION="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
C1_ROOT="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
C1_PLAN="$C1_ROOT/canonical_source_load_plan.csv"
C1_TARGETS="$C1_ROOT/canonical_source_target_index.csv"
C1_CACHE="$C1_ROOT/hpc_canonical_c1_cache"
C1_REPORT_EXTENSION="$BASE/runs/issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc"
RAW51_MASK="$HERE/payload/runs/raw51_observable_v1/raw51_observable_v1_mask.csv"
RAW51_MASK_SHA256=b16017d2755feaedbe6d3ad76fd7d1e2444cf66a14a70f6bca35f270734ad2df
RECORD_PREDICTIONS="$CKBW157624/ckbw_record_predictions.csv.gz"
RECORD_PREDICTIONS_SHA256=f53f1e3d465dc02208cc982a799ba268a9d14ff44ab2622256a79bf7d8b13536

for path in \
  "$BASE/scripts/00_env_issue27ckc.sh" \
  "$CODE_ROOT/issue27ckby_drocc_feature_dump_v1.py" \
  "$T0_ROOT" "$REPORT_T0_EXTENSION" "$C1_PLAN" "$C1_TARGETS" "$C1_CACHE" \
  "$C1_REPORT_EXTENSION" "$RUN154917" "$CKBW157624" \
  "$RAW51_MASK" "$RECORD_PREDICTIONS"; do
  test -e "$path" || {
    echo "missing runtime asset: $path" >&2
    exit 2
  }
done

echo "=== CKBY immutable asset identities ==="
for pair in \
  "$RUN154917/ckbu_gotham_unified_causal_manifest.csv:aaef2a0c0e4cc28d3815dbff4152db2fbe8c7d953dc35cf05cd817c4135d4c22" \
  "$RUN154917/ckbu_auxiliary_unified_causal_manifest.csv:f2a674235cb929ed4b7ebb8723c53a4f314f4e4563e727e3f4a2e0a4ab201e43" \
  "$RUN154917/ckbu_auxiliary_source_plan.csv:28a485932ba0f7e637b79ebd77b7c397c1fabaa5107790616aa559ea1aba719b" \
  "$RUN154917/ckbu_ton_raw_pcap_pilot_causal_samples.npz:5a20a0bb8de92bb0ace0c33361b9af3c668d115a4646ff80c660bb70c4601ffa" \
  "$RECORD_PREDICTIONS:$RECORD_PREDICTIONS_SHA256" \
  "$RAW51_MASK:$RAW51_MASK_SHA256"; do
  asset=${pair%%:*}
  expected=${pair#*:}
  test "$(sha256sum "$asset" | awk '{print $1}')" = "$expected" || {
    echo "immutable asset drift: $asset" >&2
    exit 2
  }
done

echo "=== CKBY bundle integrity ==="
cd "$HERE"
sha256sum -c SHA256SUMS

echo "=== CKBY allowed environment and pre-submit compile ==="
cd "$BASE"
source scripts/00_env_issue27ckc.sh
export PYTHONPATH="$CODE_ROOT${PYTHONPATH:+:$PYTHONPATH}"
python -m py_compile "$CODE_ROOT/issue27ckby_drocc_feature_dump_v1.py"

DUMP_SHA256=$(sha256sum "$CODE_ROOT/issue27ckby_drocc_feature_dump_v1.py" | awk '{print $1}')
SLURM="$SCRIPT_ROOT/issue27ckby_drocc_feature_dump_formal.slurm"
EXPORTS="ALL,CKBY_COMMIT_SHA=$COMMIT_SHA,CKBY_BUNDLE_ROOT=$HERE,CKBY_DUMP_SHA256=$DUMP_SHA256"

for token in \
  'CKBY_BUNDLE_ROOT=${CKBY_BUNDLE_ROOT:?missing CKBY_BUNDLE_ROOT}' \
  'CKBY_DUMP_SHA256=${CKBY_DUMP_SHA256:?missing CKBY_DUMP_SHA256}' \
  '--t0-root "$T0_ROOT"' \
  '--report-t0-extension "$REPORT_T0_EXTENSION"' \
  '--c1-plan "$C1_PLAN"' \
  '--c1-targets "$C1_TARGETS"' \
  '--c1-cache "$C1_CACHE"' \
  '--c1-report-extension "$C1_REPORT_EXTENSION"' \
  '--gotham-manifest "$GOTHAM_MANIFEST"' \
  '--auxiliary-cache "$AUX_CACHE"' \
  '--ton-cache "$TON_CACHE"' \
  '--raw51-mask "$RAW51_MASK"' \
  '--record-predictions "$RECORD_PREDICTIONS"'; do
  grep -Fq -- "$token" "$SLURM" || {
    echo "Slurm wiring missing: $token" >&2
    exit 2
  }
done

echo "=== CKBY Slurm scheduler dry validation ==="
sbatch --test-only -p amd --export="$EXPORTS" "$SLURM"

read_id() {
  local path=$1
  local value=""
  test ! -s "$path" || value=$(tr -d '\r\n' < "$path")
  if test -n "$value" && [[ ! "$value" =~ ^[0-9]+$ ]]; then
    echo "invalid stored job id in $path: $value" >&2
    exit 2
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

amd=$(read_id "$AMD_ID_FILE")
if test -z "$amd"; then
  echo "=== CKBY submit AMD seed-27 feature dump ==="
  amd=$(sbatch --parsable -p amd \
    --output="$BASE/runs/issue27ckby_dump_amd_%j.out" \
    --error="$BASE/runs/issue27ckby_dump_amd_%j.err" \
    --export="$EXPORTS" "$SLURM")
  [[ "$amd" =~ ^[0-9]+$ ]] || {
    echo "invalid AMD job id: $amd" >&2
    exit 2
  }
  store_id "$AMD_ID_FILE" "$amd"
else
  echo "AMD job already recorded; not resubmitting: $amd"
fi

printf 'CKBY_AMD_JOB_ID=%s\n' "$amd"
echo "CKBY_SUBMISSION_RECORDED"

phase_rank() {
  case "$1" in
    startup) printf 1 ;;
    contract_checks) printf 2 ;;
    snapshot_dump) printf 3 ;;
    pack) printf 4 ;;
    complete) printf 5 ;;
    *) printf 0 ;;
  esac
}

job_state() {
  local job=$1
  local state=""
  state=$(squeue -h -j "$job" -o '%T' 2>/dev/null | head -n 1 || true)
  if test -z "$state"; then
    state=$(sacct -j "$job" -X -n -P --format=State 2>/dev/null |
      head -n 1 | cut -d'|' -f1 | sed 's/+.*//' |
      tr -d '[:space:]' || true)
  fi
  printf '%s' "${state:-UNKNOWN}"
}

echo "=== CKBY post-submit runtime gate ==="
echo "Watches up to ${CKBY_RUNTIME_GATE_SECONDS:-900} seconds; pass once snapshot_dump phase is reached."

deadline=$(( $(date +%s) + ${CKBY_RUNTIME_GATE_SECONDS:-900} ))
gate=pending
while test "$(date +%s)" -lt "$deadline"; do
  root="$BASE/runs/issue27ckby_drocc_feature_dump_v1_2026-08-07_seed27_amd_${amd}"
  phase=unknown
  test ! -s "$root/current_phase.txt" || \
    phase=$(awk -F= '$1 == "phase" {print $2; exit}' "$root/current_phase.txt")
  state=$(job_state "$amd")
  if test "$(phase_rank "$phase")" -ge 3; then
    gate=passed
    echo "CKBY_RUNTIME_GATE_PASS job=$amd phase=$phase state=$state"
    break
  fi
  case "$state" in
    FAILED|TIMEOUT|OUT_OF_MEMORY|NODE_FAIL|BOOT_FAIL|PREEMPTED)
      gate=failed
      echo "CKBY_RUNTIME_GATE_FAIL job=$amd phase=$phase state=$state" >&2
      break
      ;;
    CANCELLED)
      gate=cancelled
      echo "CKBY_RUNTIME_GATE_CANCELLED job=$amd phase=$phase"
      break
      ;;
  esac
  sleep 10
done

if test "$gate" = failed; then
  test ! -s "$root/job_failure.txt" || cat "$root/job_failure.txt" >&2
  echo "CKBY_SUBMISSION_RUNTIME_FAILED" >&2
  exit 4
fi
if test "$gate" != passed; then
  echo "CKBY_SUBMITTED_NOT_YET_RUNTIME_VALIDATED gate=$gate"
  echo "The job may still be queued. Monitor with: squeue -j $amd"
  exit 0
fi
echo "CKBY_SUBMISSION_RUNTIME_VALIDATED"
