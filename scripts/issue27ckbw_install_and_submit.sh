#!/bin/bash
# Run from the extracted CKBW bundle on the already logged-in HPC terminal.
# The bundle's exact code is executed in place; the job reuses the completed
# 154917 unified caches and frozen scores.  No existing experiment file is
# overwritten, so a differing remote worktree cannot break installation.
set -euo pipefail

HERE=$(cd "$(dirname "$0")/../.." && pwd)
BASE=${CKBW_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
AMD_ID_FILE="$HERE/ckbw_seed27_amd_job_id.txt"
CODE_ROOT="$HERE/payload/repo/ood"
SCRIPT_ROOT="$HERE/payload/scripts"
T0_ROOT="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
REPORT_T0_EXTENSION="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
C1_ROOT="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
C1_PLAN="$C1_ROOT/canonical_source_load_plan.csv"
C1_TARGETS="$C1_ROOT/canonical_source_target_index.csv"
C1_CACHE="$C1_ROOT/hpc_canonical_c1_cache"
C1_REPORT_EXTENSION="$BASE/runs/issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc"
RUN154917="$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917"
RAW51_MASK="$HERE/payload/runs/raw51_observable_v1/raw51_observable_v1_mask.csv"
RAW51_MASK_SHA256=b16017d2755feaedbe6d3ad76fd7d1e2444cf66a14a70f6bca35f270734ad2df

test -d "$BASE" || {
  echo "missing experiment directory: $BASE" >&2
  exit 2
}
test -s "$BASE/scripts/00_env_issue27ckc.sh" || {
  echo "missing allowed environment script" >&2
  exit 2
}
test -s "$HERE/SHA256SUMS" || {
  echo "missing bundle SHA256SUMS" >&2
  exit 2
}
echo "=== CKBW exact bundle payload SHA-256 ==="
(cd "$HERE" && sha256sum -c SHA256SUMS)

while IFS= read -r relative; do
  test -n "$relative" || continue
  case "$relative" in
    *.py|*.sh|*.slurm|*.md|*.txt|*.csv|SHA256SUMS)
      if LC_ALL=C grep -q $'\r' "$HERE/$relative"; then
        echo "bundle text file is not LF-only: $relative" >&2
        exit 2
      fi
      ;;
  esac
done < <(awk '{print $2}' "$HERE/SHA256SUMS")

for path in \
  "$CODE_ROOT/issue27ckbw_tail_margin_dual_control_v1.py" \
  "$SCRIPT_ROOT/issue27ckbw_tail_margin_dual_control_formal.slurm" \
  "$HERE/payload/runs/issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_2026-06-16/support_bank_sidecar.csv" \
  "$HERE/payload/runs/issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17/certified_chunk_manifest.csv" \
  "$HERE/payload/runs/issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17/certified_attack_subset_v1.json" \
  "$HERE/payload/runs/issue27bu_unified_temporal_attack_ood_heads_certification_2026-06-10/unified_two_head_selection_audit.csv" \
  "$RAW51_MASK" \
  "$RUN154917/ckbu_gotham_unified_causal_manifest.csv" \
  "$RUN154917/ckbu_auxiliary_unified_causal_manifest.csv" \
  "$RUN154917/ckbu_auxiliary_source_plan.csv" \
  "$RUN154917/ckbu_ton_raw_pcap_pilot_causal_samples.npz" \
  "$RUN154917/ckbu_record_predictions.csv.gz" \
  "$RUN154917/ckbu_model_audit.csv" \
  "$T0_ROOT/tgn_source_event_plan_frozen.csv" \
  "$T0_ROOT/t0_cache_audit.csv" \
  "$REPORT_T0_EXTENSION/report_only_extension_manifest_frozen.csv" \
  "$REPORT_T0_EXTENSION/report_only_extension_manifest_sha256.txt" \
  "$REPORT_T0_EXTENSION/extension_ready.json" \
  "$REPORT_T0_EXTENSION/report_only_fit_select_exclusion_audit.csv" \
  "$REPORT_T0_EXTENSION/report_extension_recorded_targets.csv" \
  "$C1_PLAN" "$C1_TARGETS" \
  "$C1_REPORT_EXTENSION/c1_report_extension_ready.json" \
  "$C1_REPORT_EXTENSION/c1_report_only_extension_manifest.csv" \
  "$C1_REPORT_EXTENSION/c1_report_only_extension_manifest_sha256.txt" \
  "$C1_REPORT_EXTENSION/canonical_source_load_plan.csv" \
  "$C1_REPORT_EXTENSION/canonical_source_target_index.csv"; do
  test -s "$path" || {
    echo "missing immutable input: $path" >&2
    exit 2
  }
done
for directory in \
  "$RUN154917/gotham_causal_cache" \
  "$RUN154917/auxiliary_causal_cache" \
  "$T0_ROOT/tgn_event_cache" \
  "$REPORT_T0_EXTENSION/tgn_event_cache" \
  "$C1_CACHE" \
  "$C1_REPORT_EXTENSION/c1_report_cache"; do
  test -d "$directory" || {
    echo "missing immutable input directory: $directory" >&2
    exit 2
  }
done

test "$(sha256sum "$RAW51_MASK" | awk '{print $1}')" = "$RAW51_MASK_SHA256" || {
  echo "raw51 mask sha256 mismatch" >&2
  exit 2
}

echo "=== CKBW immutable 154917 asset identities ==="
for pair in \
  "$RUN154917/ckbu_gotham_unified_causal_manifest.csv:aaef2a0c0e4cc28d3815dbff4152db2fbe8c7d953dc35cf05cd817c4135d4c22" \
  "$RUN154917/ckbu_auxiliary_unified_causal_manifest.csv:f2a674235cb929ed4b7ebb8723c53a4f314f4e4563e727e3f4a2e0a4ab201e43" \
  "$RUN154917/ckbu_auxiliary_source_plan.csv:28a485932ba0f7e637b79ebd77b7c397c1fabaa5107790616aa559ea1aba719b" \
  "$RUN154917/ckbu_ton_raw_pcap_pilot_causal_samples.npz:5a20a0bb8de92bb0ace0c33361b9af3c668d115a4646ff80c660bb70c4601ffa" \
  "$RUN154917/ckbu_record_predictions.csv.gz:f53f1e3d465dc02208cc982a799ba268a9d14ff44ab2622256a79bf7d8b13536" \
  "$RUN154917/ckbu_model_audit.csv:a2b9856e65b00934e70fa4ad44350c805ea296e6fb41cde0cb5917e326d8f930"; do
  asset=${pair%%:*}
  expected=${pair#*:}
  test "$(sha256sum "$asset" | awk '{print $1}')" = "$expected" || {
    echo "immutable 154917 asset drift: $asset" >&2
    exit 2
  }
done

echo "=== CKBW allowed environment and pre-submit regression ==="
cd "$BASE"
source scripts/00_env_issue27ckc.sh
export PYTHONPATH="$CODE_ROOT${PYTHONPATH:+:$PYTHONPATH}"
python -m py_compile "$CODE_ROOT/issue27ckbw_tail_margin_dual_control_v1.py"
python "$CODE_ROOT/issue27ckbw_tail_margin_dual_control_v1.py" --contract-unit
python "$CODE_ROOT/issue27ckbw_tail_margin_dual_control_v1.py" --validate-frozen \
  --frozen-predictions "$RUN154917/ckbu_record_predictions.csv.gz" \
  --frozen-model-audit "$RUN154917/ckbu_model_audit.csv"

FORMAL_SHA256=$(sha256sum "$CODE_ROOT/issue27ckbw_tail_margin_dual_control_v1.py" | awk '{print $1}')
SLURM="$SCRIPT_ROOT/issue27ckbw_tail_margin_dual_control_formal.slurm"
EXPORTS="ALL,CKBW_COMMIT_SHA=$COMMIT_SHA,CKBW_CODE_ROOT=$CODE_ROOT,CKBW_SCRIPT_ROOT=$SCRIPT_ROOT,CKBW_FORMAL_SHA256=$FORMAL_SHA256,CKBW_T0_ROOT=$T0_ROOT,CKBW_REPORT_T0_EXTENSION=$REPORT_T0_EXTENSION,CKBW_C1_PLAN=$C1_PLAN,CKBW_C1_TARGETS=$C1_TARGETS,CKBW_C1_CACHE=$C1_CACHE,CKBW_C1_REPORT_EXTENSION=$C1_REPORT_EXTENSION,CKBW_RUN154917=$RUN154917,CKBW_RAW51_MASK=$RAW51_MASK,CKBW_RAW51_MASK_SHA256=$RAW51_MASK_SHA256"

for name in \
  CKBW_T0_ROOT CKBW_REPORT_T0_EXTENSION CKBW_C1_PLAN \
  CKBW_C1_TARGETS CKBW_C1_CACHE CKBW_C1_REPORT_EXTENSION \
  CKBW_RUN154917 CKBW_RAW51_MASK CKBW_RAW51_MASK_SHA256; do
  case ",$EXPORTS," in
    *",$name="*) ;;
    *)
      echo "missing external runtime asset in Slurm EXPORTS: $name" >&2
      exit 2
      ;;
  esac
done
for token in \
  'T0_ROOT=${CKBW_T0_ROOT:?missing CKBW_T0_ROOT}' \
  'REPORT_T0_EXTENSION=${CKBW_REPORT_T0_EXTENSION:?missing CKBW_REPORT_T0_EXTENSION}' \
  'C1_PLAN=${CKBW_C1_PLAN:?missing CKBW_C1_PLAN}' \
  'C1_TARGETS=${CKBW_C1_TARGETS:?missing CKBW_C1_TARGETS}' \
  'C1_CACHE=${CKBW_C1_CACHE:?missing CKBW_C1_CACHE}' \
  'C1_REPORT_EXTENSION=${CKBW_C1_REPORT_EXTENSION:?missing CKBW_C1_REPORT_EXTENSION}' \
  'RUN154917=${CKBW_RUN154917:?missing CKBW_RUN154917}' \
  '--t0-root "$T0_ROOT"' \
  '--report-t0-extension "$REPORT_T0_EXTENSION"' \
  '--c1-plan "$C1_PLAN"' \
  '--c1-targets "$C1_TARGETS"' \
  '--c1-cache "$C1_CACHE"' \
  '--c1-report-extension "$C1_REPORT_EXTENSION"' \
  '--gotham-manifest "$GOTHAM_MANIFEST"' \
  '--auxiliary-cache "$AUX_CACHE"' \
  '--ton-cache "$TON_CACHE"' \
  '--frozen-predictions "$FROZEN_PREDICTIONS"' \
  '--frozen-model-audit "$FROZEN_MODEL_AUDIT"'; do
  grep -Fq -- "$token" "$SLURM" || {
    echo "Slurm external runtime asset wiring missing: $token" >&2
    exit 2
  }
done

echo "=== CKBW Slurm scheduler dry validation ==="
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
  echo "=== CKBW submit AMD seed-27 formal ==="
  amd=$(sbatch --parsable -p amd \
    --output="$BASE/runs/issue27ckbw_amd_%j.out" \
    --error="$BASE/runs/issue27ckbw_amd_%j.err" \
    --export="$EXPORTS" "$SLURM")
  [[ "$amd" =~ ^[0-9]+$ ]] || {
    echo "invalid AMD job id: $amd" >&2
    exit 2
  }
  store_id "$AMD_ID_FILE" "$amd"
else
  echo "AMD job already recorded; not resubmitting: $amd"
fi

printf 'CKBW_AMD_JOB_ID=%s\n' "$amd"
echo "CKBW_SUBMISSION_RECORDED"

phase_rank() {
  case "$1" in
    startup) printf 1 ;;
    contract_checks) printf 2 ;;
    formal_model) printf 3 ;;
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

echo "=== CKBW post-submit runtime gate ==="
echo "Watches the submitted job for up to ${CKBW_RUNTIME_GATE_SECONDS:-900} seconds;"
echo "runtime pass is declared once the formal_model phase is reached."

deadline=$(( $(date +%s) + ${CKBW_RUNTIME_GATE_SECONDS:-900} ))
gate=pending
while test "$(date +%s)" -lt "$deadline"; do
  root="$BASE/runs/issue27ckbw_tail_margin_dual_control_v1_2026-08-03_seed27_amd_${amd}"
  phase=unknown
  test ! -s "$root/current_phase.txt" || \
    phase=$(awk -F= '$1 == "phase" {print $2; exit}' "$root/current_phase.txt")
  state=$(job_state "$amd")
  if test "$(phase_rank "$phase")" -ge 3; then
    gate=passed
    echo "CKBW_RUNTIME_GATE_PASS job=$amd phase=$phase state=$state"
    break
  fi
  case "$state" in
    FAILED|TIMEOUT|OUT_OF_MEMORY|NODE_FAIL|BOOT_FAIL|PREEMPTED)
      gate=failed
      echo "CKBW_RUNTIME_GATE_FAIL job=$amd phase=$phase state=$state" >&2
      break
      ;;
    CANCELLED)
      gate=cancelled
      echo "CKBW_RUNTIME_GATE_CANCELLED job=$amd phase=$phase"
      break
      ;;
  esac
  sleep 10
done

if test "$gate" = failed; then
  test ! -s "$root/job_failure.txt" || cat "$root/job_failure.txt" >&2
  echo "CKBW_SUBMISSION_RUNTIME_FAILED" >&2
  exit 4
fi
if test "$gate" != passed; then
  echo "CKBW_SUBMITTED_NOT_YET_RUNTIME_VALIDATED gate=$gate"
  echo "The job may still be queued. Monitor with: squeue -j $amd"
fi
