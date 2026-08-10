#!/bin/bash
# CKCZ: frozen endpoint-pair conflict-persistence Oracle diagnostic.
# Read-only analysis of CKBV/CKBW artifacts; no training, no PCAP decoding,
# no FINAL inputs, no requeue.
#SBATCH -J ckcz_diag
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=0-08:00:00
#SBATCH --no-requeue

set -euo pipefail

BASE=${CKCZ_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
BUNDLE_ROOT=${CKCZ_BUNDLE_ROOT:?missing CKCZ_BUNDLE_ROOT}
PARTITION=${SLURM_JOB_PARTITION:?missing SLURM_JOB_PARTITION}
JOB_ID=${SLURM_JOB_ID:?missing SLURM_JOB_ID}
COMMIT_SHA=${CKCZ_COMMIT_SHA:?missing CKCZ_COMMIT_SHA}
DIAGNOSTIC_SHA256=${CKCZ_DIAGNOSTIC_SHA256:?missing CKCZ_DIAGNOSTIC_SHA256}
VALIDATOR_SHA256=${CKCZ_VALIDATOR_SHA256:?missing CKCZ_VALIDATOR_SHA256}

case "$PARTITION" in
  amd) ;;
  *) echo "invalid CKCZ partition: $PARTITION" >&2; exit 2 ;;
esac

RUN154917="$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917"
CKBW157624="$BASE/runs/issue27ckbw_tail_margin_dual_control_v1_2026-08-03_seed27_amd_157624"
PREDICTIONS="$CKBW157624/ckbw_record_predictions.csv.gz"
PREDICTIONS_SHA256=d1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85
CKBY157930="$BASE/runs/issue27ckby_drocc_feature_dump_v1_2026-08-07_seed27_amd_157930"
GOTHAM_LINEAGE="$CKBY157930/ckby_drocc_feature_snapshot_seed27.npz"
GOTHAM_LINEAGE_SHA256=b2ef1f7d0244cc7abb8665c25364744f794190f411482e4e202e346cb850279c
GOTHAM_MANIFEST="$RUN154917/ckbu_gotham_unified_causal_manifest.csv"
GOTHAM_MANIFEST_SHA256=aaef2a0c0e4cc28d3815dbff4152db2fbe8c7d953dc35cf05cd817c4135d4c22
AUXILIARY_MANIFEST="$RUN154917/ckbu_auxiliary_unified_causal_manifest.csv"
AUXILIARY_MANIFEST_SHA256=f2a674235cb929ed4b7ebb8723c53a4f314f4e4563e727e3f4a2e0a4ab201e43
GOTHAM_CACHE="$RUN154917/gotham_causal_cache"
AUXILIARY_CACHE="$RUN154917/auxiliary_causal_cache"

PAYLOAD="$BUNDLE_ROOT/payload"
DIAGNOSTIC="$PAYLOAD/repo/ood/issue27ckcz_endpoint_pair_conflict_diagnostic_v1.py"
VALIDATOR="$PAYLOAD/scripts/issue27ckcz_validate_and_pack_seed27.sh"
PREREG="$PAYLOAD/runs/mainline_docs/ckcz_endpoint_pair_conflict_diagnostic_preregistered_20260809.md"
PREREG_SHA256=dad558902f2dfe2dc0dd4bf76cbf2e9e727be9f5d22ed2e91a5267586e8d3fde
ERRATUM="$PAYLOAD/runs/mainline_docs/ckcz_preregistered_erratum_1_gotham_lineage_20260810.md"
ERRATUM_SHA256=9dfa6f1c6b14e6dc0c61810f71275612f617cf4d97611008da20de78f5bb5968
GOTHAM_ALLOWLIST="$PAYLOAD/runs/mainline_docs/ckcz_gotham_source_allowlist_20260809.csv"
GOTHAM_ALLOWLIST_SHA256=65b4804109914d50c3efb6b9ae40d2b7d7befc903be571a92ebee90624ab6de7
AUXILIARY_ALLOWLIST="$PAYLOAD/runs/mainline_docs/ckcz_auxiliary_source_allowlist_20260809.csv"
AUXILIARY_ALLOWLIST_SHA256=be4ad12a9b0807b15b120d91ec2f9519a1743120ef0e9f04e0d8bab573252c49

RUN_NAME="issue27ckcz_endpoint_pair_conflict_diagnostic_v1_2026-08-10_seed27_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"
CONTROL_ROOT="$BASE/runs/${RUN_NAME}_control"
STDOUT_TMP="$BASE/runs/${RUN_NAME}.diagnostic_stdout.tmp"
PROGRESS_FILE="${SLURM_TMPDIR:-/tmp}/ckcz_${JOB_ID}_diagnostic_progress.json"
STALL_SECONDS=1200

for path in \
  "$BASE/scripts/00_env_issue27ckc.sh" "$DIAGNOSTIC" "$VALIDATOR" \
  "$PREREG" "$ERRATUM" "$GOTHAM_ALLOWLIST" "$AUXILIARY_ALLOWLIST" \
  "$GOTHAM_MANIFEST" "$AUXILIARY_MANIFEST" "$PREDICTIONS" "$GOTHAM_LINEAGE"; do
  test -s "$path" || { echo "missing immutable CKCZ input: $path" >&2; exit 2; }
done
for directory in "$GOTHAM_CACHE" "$AUXILIARY_CACHE"; do
  test -d "$directory" || { echo "missing immutable CKCZ cache: $directory" >&2; exit 2; }
done

test ! -e "$RUN_ROOT" || { echo "refusing mixed CKCZ run root: $RUN_ROOT" >&2; exit 2; }
test ! -e "$CONTROL_ROOT" || { echo "refusing mixed CKCZ control root: $CONTROL_ROOT" >&2; exit 2; }
test ! -e "$STDOUT_TMP" || { echo "refusing stale CKCZ stdout: $STDOUT_TMP" >&2; exit 2; }
mkdir -p "$CONTROL_ROOT"

started_epoch=$(date +%s)
started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
phase=startup
heartbeat_pid=""
watchdog_pid=""
diagnostic_pid=""
wrapper_pid=$$

write_phase() {
  phase=$1
  printf 'phase=%s\nupdated_utc=%s\n' "$phase" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    > "$CONTROL_ROOT/current_phase.txt"
}

cleanup() {
  status=$?
  for background_pid in "$heartbeat_pid" "$watchdog_pid" "$diagnostic_pid"; do
    test -z "$background_pid" || kill "$background_pid" >/dev/null 2>&1 || true
  done
  for background_pid in "$heartbeat_pid" "$watchdog_pid"; do
    test -z "$background_pid" || wait "$background_pid" >/dev/null 2>&1 || true
  done
  if test "$status" -ne 0; then
    printf 'status=FAILED\nphase=%s\nexit_code=%s\nfailed_utc=%s\n' \
      "$phase" "$status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      > "$CONTROL_ROOT/job_failure.txt"
    test ! -e "$STDOUT_TMP" || mv "$STDOUT_TMP" "$CONTROL_ROOT/diagnostic_stdout.log" || true
    test ! -s "$PROGRESS_FILE" || \
      cp "$PROGRESS_FILE" "$CONTROL_ROOT/diagnostic_progress_last.json" || true
    if test -d "$RUN_ROOT"; then
      cp "$CONTROL_ROOT/job_failure.txt" "$RUN_ROOT/slurm_failure.txt" || true
    fi
  fi
  exit "$status"
}
trap cleanup EXIT

heartbeat() {
  while true; do
    sleep 60
    live_phase=unknown
    diagnostic_stage=not_started
    progress_sequence=0
    progress_age=-1
    log_bytes=0
    test ! -s "$CONTROL_ROOT/current_phase.txt" || \
      live_phase=$(awk -F= '$1 == "phase" {print $2; exit}' "$CONTROL_ROOT/current_phase.txt")
    test ! -e "$STDOUT_TMP" || log_bytes=$(wc -c < "$STDOUT_TMP")
    if test -s "$PROGRESS_FILE"; then
      diagnostic_stage=$(sed -n 's/^[[:space:]]*"stage": "\([^"]*\)",*$/\1/p' \
        "$PROGRESS_FILE" | head -n 1)
      progress_sequence=$(sed -n 's/^[[:space:]]*"sequence": \([0-9][0-9]*\),*$/\1/p' \
        "$PROGRESS_FILE" | head -n 1)
      progress_mtime=$(stat -c %Y "$PROGRESS_FILE")
      progress_age=$(( $(date +%s) - progress_mtime ))
    fi
    printf 'CKCZ_PROGRESS utc=%s phase=%s diagnostic_stage=%s sequence=%s age_seconds=%s job=%s partition=%s diagnostic_log_bytes=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$live_phase" "${diagnostic_stage:-unknown}" \
      "${progress_sequence:-0}" "$progress_age" "$JOB_ID" "$PARTITION" "$log_bytes"
  done
}

watchdog() {
  watched_pid=$1
  while kill -0 "$watched_pid" >/dev/null 2>&1; do
    sleep 60
    progress_reference=$started_epoch
    diagnostic_stage=not_started
    if test -s "$PROGRESS_FILE"; then
      progress_reference=$(stat -c %Y "$PROGRESS_FILE")
      diagnostic_stage=$(sed -n 's/^[[:space:]]*"stage": "\([^"]*\)",*$/\1/p' \
        "$PROGRESS_FILE" | head -n 1)
    fi
    progress_age=$(( $(date +%s) - progress_reference ))
    if test "$progress_age" -ge "$STALL_SECONDS"; then
      printf 'status=FAILED\nreason=NO_COMPLETED_UNIT_PROGRESS\nstage=%s\nage_seconds=%s\nthreshold_seconds=%s\nfailed_utc=%s\n' \
        "${diagnostic_stage:-unknown}" "$progress_age" "$STALL_SECONDS" \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$CONTROL_ROOT/progress_stall.txt"
      echo "CKCZ_PROGRESS_STALL stage=${diagnostic_stage:-unknown} age_seconds=$progress_age threshold_seconds=$STALL_SECONDS" >&2
      kill -TERM "$watched_pid" >/dev/null 2>&1 || true
      sleep 30
      kill -KILL "$watched_pid" >/dev/null 2>&1 || true
      kill -TERM "$wrapper_pid" >/dev/null 2>&1 || true
      return
    fi
  done
}

write_phase startup
rm -f "$PROGRESS_FILE"
heartbeat &
heartbeat_pid=$!

cd "$BASE"
source scripts/00_env_issue27ckc.sh
export PYTHONPATH="$PAYLOAD/repo/ood${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export NUMEXPR_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}

write_phase contract_checks
python -m py_compile "$DIAGNOSTIC"
bash -n "$VALIDATOR"
test "$(sha256sum "$DIAGNOSTIC" | awk '{print $1}')" = "$DIAGNOSTIC_SHA256" || {
  echo "CKCZ diagnostic module hash drift" >&2; exit 2;
}
test "$(sha256sum "$VALIDATOR" | awk '{print $1}')" = "$VALIDATOR_SHA256" || {
  echo "CKCZ validator hash drift" >&2; exit 2;
}
for pair in \
  "$PREREG:$PREREG_SHA256" \
  "$ERRATUM:$ERRATUM_SHA256" \
  "$GOTHAM_ALLOWLIST:$GOTHAM_ALLOWLIST_SHA256" \
  "$AUXILIARY_ALLOWLIST:$AUXILIARY_ALLOWLIST_SHA256" \
  "$GOTHAM_MANIFEST:$GOTHAM_MANIFEST_SHA256" \
  "$AUXILIARY_MANIFEST:$AUXILIARY_MANIFEST_SHA256" \
  "$PREDICTIONS:$PREDICTIONS_SHA256" \
  "$GOTHAM_LINEAGE:$GOTHAM_LINEAGE_SHA256"; do
  asset=${pair%%:*}
  expected=${pair#*:}
  test "$(sha256sum "$asset" | awk '{print $1}')" = "$expected" || {
    echo "immutable CKCZ asset drift: $asset" >&2; exit 2;
  }
done

gotham_npz=$(find "$GOTHAM_CACHE" -maxdepth 1 -type f -name '*.npz' -printf '.' | wc -c)
auxiliary_npz=$(find "$AUXILIARY_CACHE" -maxdepth 1 -type f -name '*.npz' -printf '.' | wc -c)
test "$gotham_npz" -eq 29 || { echo "Gotham cache file-count drift: $gotham_npz" >&2; exit 2; }
test "$auxiliary_npz" -eq 31 || { echo "auxiliary cache file-count drift: $auxiliary_npz" >&2; exit 2; }
printf 'status=PASS\ngotham_npz=%s\nauxiliary_npz=%s\nchecked_utc=%s\n' \
  "$gotham_npz" "$auxiliary_npz" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  > "$CONTROL_ROOT/cache_online_gate.txt"
printf 'job_id=%s\npartition=%s\ncommit_sha=%s\nbundle_root=%s\nstarted_utc=%s\n' \
  "$JOB_ID" "$PARTITION" "$COMMIT_SHA" "$BUNDLE_ROOT" "$started_utc" \
  > "$CONTROL_ROOT/slurm_identity.txt"

write_phase diagnostic_real_inputs
python -u "$DIAGNOSTIC" \
  --ckbv-root "$RUN154917" \
  --predictions "$PREDICTIONS" \
  --gotham-lineage-snapshot "$GOTHAM_LINEAGE" \
  --gotham-lineage-snapshot-sha256 "$GOTHAM_LINEAGE_SHA256" \
  --gotham-lineage-rows 287448 \
  --gotham-allowlist "$GOTHAM_ALLOWLIST" \
  --auxiliary-allowlist "$AUXILIARY_ALLOWLIST" \
  --gotham-allowlist-sha256 "$GOTHAM_ALLOWLIST_SHA256" \
  --auxiliary-allowlist-sha256 "$AUXILIARY_ALLOWLIST_SHA256" \
  --gotham-manifest-sha256 "$GOTHAM_MANIFEST_SHA256" \
  --auxiliary-manifest-sha256 "$AUXILIARY_MANIFEST_SHA256" \
  --predictions-sha256 "$PREDICTIONS_SHA256" \
  --gotham-sources 24 --gotham-rows 317523 \
  --auxiliary-sources 31 --auxiliary-rows 18600 \
  --seed 27 --bootstrap-reps 200 \
  --preregistered-protocol "$PREREG" \
  --preregistered-protocol-sha256 "$PREREG_SHA256" \
  --preregistered-erratum "$ERRATUM" \
  --preregistered-erratum-sha256 "$ERRATUM_SHA256" \
  --progress-file "$PROGRESS_FILE" \
  --out "$RUN_ROOT" \
  > "$STDOUT_TMP" 2>&1 &
diagnostic_pid=$!
watchdog "$diagnostic_pid" &
watchdog_pid=$!
set +e
wait "$diagnostic_pid"
diagnostic_status=$?
set -e
diagnostic_pid=""
test -z "$watchdog_pid" || kill "$watchdog_pid" >/dev/null 2>&1 || true
test -z "$watchdog_pid" || wait "$watchdog_pid" >/dev/null 2>&1 || true
watchdog_pid=""
test "$diagnostic_status" -eq 0 || exit "$diagnostic_status"

write_phase validate_result
bash "$VALIDATOR" "$RUN_ROOT" > "$CONTROL_ROOT/validation_stdout.log" 2>&1

write_phase resource_accounting
ended_epoch=$(date +%s)
ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'started_utc=%s\nended_utc=%s\nwall_seconds=%s\njob_id=%s\npartition=%s\n' \
  "$started_utc" "$ended_utc" "$((ended_epoch-started_epoch))" "$JOB_ID" "$PARTITION" \
  > "$CONTROL_ROOT/run_timing.txt"
{
  echo 'sstat:'
  sstat -j "${JOB_ID}.batch" -n -P --format=JobID,MaxRSS,AveRSS,AveCPU,MaxDiskRead,MaxDiskWrite 2>&1 || true
  echo 'sacct:'
  sacct -j "$JOB_ID" -X -n -P --format=JobID,State,Elapsed,TotalCPU,MaxRSS,ReqMem,AllocCPUS 2>&1 || true
} > "$CONTROL_ROOT/resource_usage.txt"

write_phase complete
test -z "$heartbeat_pid" || kill "$heartbeat_pid" >/dev/null 2>&1 || true
wait "$heartbeat_pid" >/dev/null 2>&1 || true
heartbeat_pid=""
mv "$STDOUT_TMP" "$CONTROL_ROOT/diagnostic_stdout.log"
mkdir "$RUN_ROOT/runtime_control"
cp "$CONTROL_ROOT"/* "$RUN_ROOT/runtime_control/"
cp "$PROGRESS_FILE" "$RUN_ROOT/runtime_control/diagnostic_progress_final.json"

PULLBACK="$BASE/runs/issue27ckcz_endpoint_pair_conflict_diagnostic_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"
tar -C "$BASE/runs" -czf "$PULLBACK" "$RUN_NAME"
(
  cd "$BASE/runs"
  sha256sum "$(basename "$PULLBACK")" > "$(basename "$PULLBACK").sha256"
)

echo "CKCZ_DIAGNOSTIC_COMPLETE partition=$PARTITION job_id=$JOB_ID pullback=$PULLBACK"
