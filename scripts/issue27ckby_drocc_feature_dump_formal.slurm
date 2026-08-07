#!/bin/bash
# CKBY: DROCC feature snapshot dump.  Assembly-only job: re-executes the frozen
# CKBW assembly half unchanged and exports the raw 51-D feature snapshot.
# No PCAP decode, no training, no scoring, no requeue.
#SBATCH -J ckby_dump
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=0-04:00:00
#SBATCH --no-requeue

set -euo pipefail

BASE=${CKBY_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
BUNDLE_ROOT=${CKBY_BUNDLE_ROOT:?missing CKBY_BUNDLE_ROOT}
PARTITION=${SLURM_JOB_PARTITION:?missing SLURM_JOB_PARTITION}
JOB_ID=${SLURM_JOB_ID:?missing SLURM_JOB_ID}
COMMIT_SHA=${CKBY_COMMIT_SHA:?missing CKBY_COMMIT_SHA}
DUMP_SHA256=${CKBY_DUMP_SHA256:?missing CKBY_DUMP_SHA256}

CODE_ROOT="$BUNDLE_ROOT/payload/repo/ood"
RUN154917="$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917"
CKBW157624="$BASE/runs/issue27ckbw_tail_margin_dual_control_v1_2026-08-03_seed27_amd_157624"
T0_ROOT="$BASE/runs/issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
REPORT_T0_EXTENSION="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
C1_ROOT="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
C1_PLAN="$C1_ROOT/canonical_source_load_plan.csv"
C1_TARGETS="$C1_ROOT/canonical_source_target_index.csv"
C1_CACHE="$C1_ROOT/hpc_canonical_c1_cache"
C1_REPORT_EXTENSION="$BASE/runs/issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc"
RAW51_MASK="$BUNDLE_ROOT/payload/runs/raw51_observable_v1/raw51_observable_v1_mask.csv"
RAW51_MASK_SHA256=b16017d2755feaedbe6d3ad76fd7d1e2444cf66a14a70f6bca35f270734ad2df

GOTHAM_MANIFEST="$RUN154917/ckbu_gotham_unified_causal_manifest.csv"
GOTHAM_CACHE="$RUN154917/gotham_causal_cache"
AUX_MANIFEST="$RUN154917/ckbu_auxiliary_unified_causal_manifest.csv"
AUX_PLAN="$RUN154917/ckbu_auxiliary_source_plan.csv"
AUX_CACHE="$RUN154917/auxiliary_causal_cache"
TON_CACHE="$RUN154917/ckbu_ton_raw_pcap_pilot_causal_samples.npz"
RECORD_PREDICTIONS="$CKBW157624/ckbw_record_predictions.csv.gz"
RECORD_PREDICTIONS_SHA256=f53f1e3d465dc02208cc982a799ba268a9d14ff44ab2622256a79bf7d8b13536

case "$PARTITION" in
  amd) ;;
  *) echo "invalid partition for CKBY dump: $PARTITION" >&2; exit 2 ;;
esac

RUN_NAME="issue27ckby_drocc_feature_dump_v1_2026-08-07_seed27_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"
DUMP="$CODE_ROOT/issue27ckby_drocc_feature_dump_v1.py"

for path in \
  "$BASE/scripts/00_env_issue27ckc.sh" \
  "$DUMP" \
  "$GOTHAM_MANIFEST" "$AUX_MANIFEST" "$AUX_PLAN" "$TON_CACHE" \
  "$RECORD_PREDICTIONS" "$RAW51_MASK" \
  "$T0_ROOT/tgn_source_event_plan_frozen.csv" \
  "$T0_ROOT/t0_cache_audit.csv" \
  "$REPORT_T0_EXTENSION/report_only_extension_manifest_frozen.csv" \
  "$C1_PLAN" "$C1_TARGETS" \
  "$C1_REPORT_EXTENSION/c1_report_extension_ready.json" \
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

test "$(sha256sum "$DUMP" | awk '{print $1}')" = "$DUMP_SHA256" || {
  echo "CKBY dump module hash drift" >&2
  exit 2
}
for pair in \
  "$RAW51_MASK:$RAW51_MASK_SHA256" \
  "$RECORD_PREDICTIONS:$RECORD_PREDICTIONS_SHA256"; do
  asset=${pair%%:*}
  expected=${pair#*:}
  test "$(sha256sum "$asset" | awk '{print $1}')" = "$expected" || {
    echo "immutable asset drift: $asset" >&2
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
    sleep 60
    live_phase=unknown
    log_lines=0
    test ! -s "$RUN_ROOT/current_phase.txt" || \
      live_phase=$(awk -F= '$1 == "phase" {print $2; exit}' \
        "$RUN_ROOT/current_phase.txt")
    test ! -s "$RUN_ROOT/dump_stdout.log" || \
      log_lines=$(wc -l < "$RUN_ROOT/dump_stdout.log")
    printf 'CKBY_PROGRESS utc=%s phase=%s job=%s partition=%s dump_log_lines=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$live_phase" "$JOB_ID" "$PARTITION" \
      "$log_lines"
  done
}
write_phase startup
heartbeat &
heartbeat_pid=$!

cd "$BASE"
source scripts/00_env_issue27ckc.sh

export PYTHONPATH="$CODE_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export NUMEXPR_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
printf 'job_id=%s\npartition=%s\ncommit_sha=%s\ncode_root=%s\nstarted_utc=%s\n' \
  "$JOB_ID" "$PARTITION" "$COMMIT_SHA" "$CODE_ROOT" "$started_utc" \
  > "$RUN_ROOT/slurm_identity.txt"

write_phase contract_checks
python -m py_compile "$DUMP"

write_phase snapshot_dump
python -u "$DUMP" --seed 27 \
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
  --record-predictions "$RECORD_PREDICTIONS" \
  > "$RUN_ROOT/dump_stdout.log" 2>&1

write_phase pack
ended_epoch=$(date +%s)
ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'started_utc=%s\nended_utc=%s\nwall_seconds=%s\njob_id=%s\npartition=%s\n' \
  "$started_utc" "$ended_utc" "$((ended_epoch-started_epoch))" \
  "$JOB_ID" "$PARTITION" > "$RUN_ROOT/run_timing.txt"

PULLBACK="$BASE/runs/issue27ckby_drocc_feature_dump_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"
tar -C "$BASE/runs" -czf "$PULLBACK" "$RUN_NAME"
( cd "$BASE/runs" && sha256sum "$(basename "$PULLBACK")" > "$PULLBACK.sha256" )

write_phase complete
echo "CKBY_DUMP_RESULT_COMPLETE partition=$PARTITION job_id=$JOB_ID pullback=$PULLBACK"
