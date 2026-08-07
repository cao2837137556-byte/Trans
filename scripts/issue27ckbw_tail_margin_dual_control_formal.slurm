#!/bin/bash
# CKBW: tail-margin dual-control seed-27 formal model.  One result-producing
# job: it reuses the completed 154917 unified feature caches and frozen scores,
# trains the preregistered tail-margin TabM candidates and evaluates all eight
# frozen arms.  No PCAP decode, no retraining of frozen models, no requeue.
#SBATCH -J ckbw_seed27
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=1-00:00:00
#SBATCH --no-requeue

set -euo pipefail

BASE=${CKBW_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
CODE_ROOT=${CKBW_CODE_ROOT:?missing CKBW_CODE_ROOT}
SCRIPT_ROOT=${CKBW_SCRIPT_ROOT:?missing CKBW_SCRIPT_ROOT}
PARTITION=${SLURM_JOB_PARTITION:?missing SLURM_JOB_PARTITION}
JOB_ID=${SLURM_JOB_ID:?missing SLURM_JOB_ID}
COMMIT_SHA=${CKBW_COMMIT_SHA:?missing CKBW_COMMIT_SHA}
FORMAL_SHA256=${CKBW_FORMAL_SHA256:?missing CKBW_FORMAL_SHA256}
T0_ROOT=${CKBW_T0_ROOT:?missing CKBW_T0_ROOT}
REPORT_T0_EXTENSION=${CKBW_REPORT_T0_EXTENSION:?missing CKBW_REPORT_T0_EXTENSION}
C1_PLAN=${CKBW_C1_PLAN:?missing CKBW_C1_PLAN}
C1_TARGETS=${CKBW_C1_TARGETS:?missing CKBW_C1_TARGETS}
C1_CACHE=${CKBW_C1_CACHE:?missing CKBW_C1_CACHE}
C1_REPORT_EXTENSION=${CKBW_C1_REPORT_EXTENSION:?missing CKBW_C1_REPORT_EXTENSION}
RUN154917=${CKBW_RUN154917:?missing CKBW_RUN154917}
RAW51_MASK=${CKBW_RAW51_MASK:?missing CKBW_RAW51_MASK}
RAW51_MASK_SHA256=${CKBW_RAW51_MASK_SHA256:?missing CKBW_RAW51_MASK_SHA256}

GOTHAM_MANIFEST="$RUN154917/ckbu_gotham_unified_causal_manifest.csv"
GOTHAM_CACHE="$RUN154917/gotham_causal_cache"
AUX_MANIFEST="$RUN154917/ckbu_auxiliary_unified_causal_manifest.csv"
AUX_PLAN="$RUN154917/ckbu_auxiliary_source_plan.csv"
AUX_CACHE="$RUN154917/auxiliary_causal_cache"
TON_CACHE="$RUN154917/ckbu_ton_raw_pcap_pilot_causal_samples.npz"
FROZEN_PREDICTIONS="$RUN154917/ckbu_record_predictions.csv.gz"
FROZEN_MODEL_AUDIT="$RUN154917/ckbu_model_audit.csv"

# Immutable 154917 asset identities (verified against the local pullback copy
# and pinned in the CKBW handoff).  Defaults are facts, not knobs.
GOTHAM_MANIFEST_SHA256=${CKBW_GOTHAM_MANIFEST_SHA256:-aaef2a0c0e4cc28d3815dbff4152db2fbe8c7d953dc35cf05cd817c4135d4c22}
AUX_MANIFEST_SHA256=${CKBW_AUX_MANIFEST_SHA256:-f2a674235cb929ed4b7ebb8723c53a4f314f4e4563e727e3f4a2e0a4ab201e43}
AUX_PLAN_SHA256=${CKBW_AUX_PLAN_SHA256:-28a485932ba0f7e637b79ebd77b7c397c1fabaa5107790616aa559ea1aba719b}
TON_CACHE_SHA256=${CKBW_TON_CACHE_SHA256:-5a20a0bb8de92bb0ace0c33361b9af3c668d115a4646ff80c660bb70c4601ffa}
FROZEN_PREDICTIONS_SHA256=${CKBW_FROZEN_PREDICTIONS_SHA256:-f53f1e3d465dc02208cc982a799ba268a9d14ff44ab2622256a79bf7d8b13536}
FROZEN_MODEL_AUDIT_SHA256=${CKBW_FROZEN_MODEL_AUDIT_SHA256:-a2b9856e65b00934e70fa4ad44350c805ea296e6fb41cde0cb5917e326d8f930}

case "$PARTITION" in
  amd) ;;
  *) echo "invalid partition for CKBW seed-27 formal: $PARTITION" >&2; exit 2 ;;
esac

RUN_NAME="issue27ckbw_tail_margin_dual_control_v1_2026-08-03_seed27_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"
FORMAL="$CODE_ROOT/issue27ckbw_tail_margin_dual_control_v1.py"

for path in \
  "$BASE/scripts/00_env_issue27ckc.sh" \
  "$FORMAL" \
  "$GOTHAM_MANIFEST" "$AUX_MANIFEST" "$AUX_PLAN" "$TON_CACHE" \
  "$FROZEN_PREDICTIONS" "$FROZEN_MODEL_AUDIT" "$RAW51_MASK" \
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
  "$GOTHAM_CACHE" "$AUX_CACHE" \
  "$T0_ROOT/tgn_event_cache" \
  "$REPORT_T0_EXTENSION/tgn_event_cache" \
  "$C1_CACHE" \
  "$C1_REPORT_EXTENSION/c1_report_cache"; do
  test -d "$directory" || {
    echo "missing immutable input directory: $directory" >&2
    exit 2
  }
done

test "$(sha256sum "$FORMAL" | awk '{print $1}')" = "$FORMAL_SHA256" || {
  echo "CKBW formal module hash drift" >&2
  exit 2
}
for pair in \
  "$GOTHAM_MANIFEST:$GOTHAM_MANIFEST_SHA256" \
  "$AUX_MANIFEST:$AUX_MANIFEST_SHA256" \
  "$AUX_PLAN:$AUX_PLAN_SHA256" \
  "$TON_CACHE:$TON_CACHE_SHA256" \
  "$FROZEN_PREDICTIONS:$FROZEN_PREDICTIONS_SHA256" \
  "$FROZEN_MODEL_AUDIT:$FROZEN_MODEL_AUDIT_SHA256" \
  "$RAW51_MASK:$RAW51_MASK_SHA256"; do
  asset=${pair%%:*}
  expected=${pair#*:}
  test "$(sha256sum "$asset" | awk '{print $1}')" = "$expected" || {
    echo "immutable 154917 asset drift: $asset" >&2
    exit 2
  }
done

test ! -e "$RUN_ROOT" || {
  echo "refusing mixed run root: $RUN_ROOT" >&2
  exit 2
}
mkdir -p "$RUN_ROOT"

started_epoch=$(date +%s)
started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
phase=startup
heartbeat_pid=""

write_phase() {
  phase=$1
  printf 'phase=%s\nupdated_utc=%s\n' \
    "$phase" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    > "$RUN_ROOT/current_phase.txt"
}

cleanup() {
  status=$?
  test -z "$heartbeat_pid" || kill "$heartbeat_pid" >/dev/null 2>&1 || true
  wait >/dev/null 2>&1 || true
  if test "$status" -ne 0; then
    printf 'status=FAILED\nphase=%s\nexit_code=%s\nfailed_utc=%s\n' \
      "$phase" "$status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      > "$RUN_ROOT/job_failure.txt"
  fi
  exit "$status"
}
trap cleanup EXIT

heartbeat() {
  while true; do
    sleep 300
    live_phase=unknown
    result_files=0
    log_lines=0
    test ! -s "$RUN_ROOT/current_phase.txt" || \
      live_phase=$(awk -F= '$1 == "phase" {print $2; exit}' \
        "$RUN_ROOT/current_phase.txt")
    result_files=$(find "$RUN_ROOT" -maxdepth 1 -name 'ckbw_*' 2>/dev/null | wc -l)
    test ! -s "$RUN_ROOT/formal_stdout.log" || \
      log_lines=$(wc -l < "$RUN_ROOT/formal_stdout.log")
    printf 'CKBW_PROGRESS utc=%s phase=%s job=%s partition=%s ckbw_files=%s formal_log_lines=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$live_phase" "$JOB_ID" "$PARTITION" \
      "$result_files" "$log_lines"
  done
}
write_phase startup
heartbeat &
heartbeat_pid=$!

cd "$BASE"
source scripts/00_env_issue27ckc.sh

export PYTHONPATH="$CODE_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export CKBW_COMMIT_SHA="$COMMIT_SHA"
printf 'job_id=%s\npartition=%s\ncommit_sha=%s\ncode_root=%s\nrun154917=%s\nstarted_utc=%s\n' \
  "$JOB_ID" "$PARTITION" "$COMMIT_SHA" "$CODE_ROOT" "$RUN154917" "$started_utc" \
  > "$RUN_ROOT/slurm_identity.txt"
scontrol show job -o "$JOB_ID" \
  > "$RUN_ROOT/slurm_job_at_start.txt" 2>/dev/null || true

write_phase contract_checks
python -m py_compile "$FORMAL"
python "$FORMAL" --contract-unit
python "$FORMAL" --validate-frozen \
  --frozen-predictions "$FROZEN_PREDICTIONS" \
  --frozen-model-audit "$FROZEN_MODEL_AUDIT"

write_phase formal_model
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export NUMEXPR_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
python -u "$FORMAL" --formal --seed 27 \
  --threads "${SLURM_CPUS_PER_TASK:-8}" \
  --out "$RUN_ROOT" \
  --t0-root "$T0_ROOT" \
  --report-t0-extension "$REPORT_T0_EXTENSION" \
  --c1-plan "$C1_PLAN" \
  --c1-targets "$C1_TARGETS" \
  --c1-cache "$C1_CACHE" \
  --c1-report-extension "$C1_REPORT_EXTENSION" \
  --gotham-manifest "$GOTHAM_MANIFEST" \
  --gotham-cache "$GOTHAM_CACHE" \
  --auxiliary-manifest "$AUX_MANIFEST" \
  --auxiliary-plan "$AUX_PLAN" \
  --auxiliary-cache "$AUX_CACHE" \
  --ton-cache "$TON_CACHE" \
  --raw51-mask "$RAW51_MASK" \
  --raw51-mask-sha256 "$RAW51_MASK_SHA256" \
  --frozen-predictions "$FROZEN_PREDICTIONS" \
  --frozen-model-audit "$FROZEN_MODEL_AUDIT" \
  > "$RUN_ROOT/formal_stdout.log" 2>&1

write_phase pack
ended_epoch=$(date +%s)
ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'started_utc=%s\nended_utc=%s\nwall_seconds=%s\njob_id=%s\npartition=%s\n' \
  "$started_utc" "$ended_utc" "$((ended_epoch-started_epoch))" \
  "$JOB_ID" "$PARTITION" > "$RUN_ROOT/run_timing.txt"
sstat -j "${JOB_ID}.batch" \
  --format=JobID,AveCPU,AveRSS,MaxRSS,MaxDiskRead,MaxDiskWrite -P \
  > "$RUN_ROOT/slurm_in_job_accounting.csv" 2>/dev/null || true

PULLBACK="$BASE/runs/issue27ckbw_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"
tar -C "$BASE/runs" -czf "$PULLBACK" "$RUN_NAME"
( cd "$BASE/runs" && sha256sum "$(basename "$PULLBACK")" > "$PULLBACK.sha256" )

write_phase complete
echo "CKBW_RESULT_COMPLETE partition=$PARTITION job_id=$JOB_ID pullback=$PULLBACK"
