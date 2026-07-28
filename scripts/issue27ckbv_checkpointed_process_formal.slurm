#!/bin/bash
# CKBV: checkpointed/sparse execution repair followed by the unchanged CKBU
# seed-27 formal model.  This is one result-producing chain, not a preflight job.
#SBATCH -J ckbv_process
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=1-12:00:00
#SBATCH --no-requeue

set -euo pipefail

BASE=${CKBV_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
DATA_ROOT=${CKBV_DATA_ROOT:-/public/home/jiangxinwei.zr/work/paper04/datasets}
CODE_ROOT=${CKBV_CODE_ROOT:?missing CKBV_CODE_ROOT}
SCRIPT_ROOT=${CKBV_SCRIPT_ROOT:?missing CKBV_SCRIPT_ROOT}
PARTITION=${SLURM_JOB_PARTITION:?missing SLURM_JOB_PARTITION}
JOB_ID=${SLURM_JOB_ID:?missing SLURM_JOB_ID}
COMMIT_SHA=${CKBV_COMMIT_SHA:?missing CKBV_COMMIT_SHA}
FRONTEND_SHA256=${CKBV_FRONTEND_SHA256:?missing CKBV_FRONTEND_SHA256}
FORMAL_SHA256=${CKBV_FORMAL_SHA256:?missing CKBV_FORMAL_SHA256}
RESUME_SHA256=${CKBV_RESUME_SHA256:?missing CKBV_RESUME_SHA256}
CHECKPOINT_SHA256=${CKBV_CHECKPOINT_SHA256:?missing CKBV_CHECKPOINT_SHA256}
REUSE_ROOTS=${CKBV_REUSE_RUN_ROOTS:-$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154761:$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154620:$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_intel_154621:$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154606:$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_intel_154607:$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154478:$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154440:$BASE/runs/issue27ckbu_unified_process_rescue_parallel_v2_2026-07-24_seed27_amd_154081}
GOTHAM_WORKERS=${CKBV_GOTHAM_WORKERS:-2}
TON_WORKERS=${CKBV_TON_WORKERS:-2}

case "$PARTITION" in
  amd|intel) ;;
  *) echo "invalid partition: $PARTITION" >&2; exit 2 ;;
esac
[[ "$GOTHAM_WORKERS" =~ ^[1-9][0-9]*$ ]] || {
  echo "invalid Gotham worker count: $GOTHAM_WORKERS" >&2
  exit 2
}
[[ "$TON_WORKERS" =~ ^[1-9][0-9]*$ ]] || {
  echo "invalid ToN worker count: $TON_WORKERS" >&2
  exit 2
}
test "$GOTHAM_WORKERS" -le "${SLURM_CPUS_PER_TASK:-8}" || {
  echo "Gotham workers exceed allocated CPUs" >&2
  exit 2
}
test "$TON_WORKERS" -le "${SLURM_CPUS_PER_TASK:-8}" || {
  echo "ToN workers exceed allocated CPUs" >&2
  exit 2
}

RUN_NAME="issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"
GOTHAM_ZIP="$DATA_ROOT/gotham2025/raw/GothamDataset2025.zip"
TON_ROOT="$DATA_ROOT/external/ton_iot_raw_network"
TON_PILOT="$TON_ROOT/raw_pcap_pilot_v1"
TON_EXTRACTED="$TON_ROOT/extracted"
TON_PILOT_MANIFEST=${CKBV_TON_PILOT_MANIFEST:?missing CKBV_TON_PILOT_MANIFEST}
CKBT_MANIFEST=${CKBV_CKBT_MANIFEST:?missing CKBV_CKBT_MANIFEST}
CKBQ_ROOT=${CKBV_CKBQ_ROOT:-$BASE/runs/issue27ckbq_causal_minirocket_consensus_v1_2026-07-17_seed27_amd_153037}
CKBQ_PREDICTIONS="$CKBQ_ROOT/ckbq_record_predictions.csv.gz"
CKBO_AUX_MANIFEST="$CKBQ_ROOT/ckbo_auxiliary_benign_manifest.csv"
REPORT_TARGETS="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc/report_extension_recorded_targets.csv"
BASE_TARGETS="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1/canonical_source_target_index.csv"
RAW51_MASK=${CKBV_RAW51_MASK:-$BASE/runs/raw51_observable_v1/raw51_observable_v1_mask.csv}
RAW51_MASK_SHA256=${CKBV_RAW51_MASK_SHA256:-b16017d2755feaedbe6d3ad76fd7d1e2444cf66a14a70f6bca35f270734ad2df}
test -s "$RAW51_MASK" || { echo "missing raw51 mask: $RAW51_MASK" >&2; exit 2; }
FRONTEND="$CODE_ROOT/issue27ckbu_unified_tshark_causal_frontend_v1.py"
FORMAL="$CODE_ROOT/issue27ckbu_unified_process_rescue_formal_v1.py"
RESUME="$CODE_ROOT/issue27ckbu_parallel_cache_resume_v1.py"
CHECKPOINT="$CODE_ROOT/issue27ckbv_checkpointed_sparse_process_frontend_v1.py"
VALIDATOR="$SCRIPT_ROOT/issue27ckbv_validate_and_pack_seed27.sh"
PCAP_LIB_DIR="/share/software/CST/installed/MCR/bin/glnxa64"

for path in \
  "$BASE/scripts/00_env_issue27ckc.sh" \
  "$FRONTEND" "$FORMAL" "$RESUME" "$CHECKPOINT" "$VALIDATOR" \
  "$GOTHAM_ZIP" "$TON_PILOT_MANIFEST" "$CKBT_MANIFEST" "$CKBQ_PREDICTIONS" \
  "$CKBO_AUX_MANIFEST" "$REPORT_TARGETS" "$BASE_TARGETS"; do
  test -s "$path" || {
    echo "missing immutable input: $path" >&2
    exit 2
  }
done
test "$(sha256sum "$FRONTEND" | awk '{print $1}')" = "$FRONTEND_SHA256" || {
  echo "frozen frontend hash drift" >&2
  exit 2
}
test "$(sha256sum "$FORMAL" | awk '{print $1}')" = "$FORMAL_SHA256" || {
  echo "frozen formal model hash drift" >&2
  exit 2
}
test "$(sha256sum "$RESUME" | awk '{print $1}')" = "$RESUME_SHA256" || {
  echo "frozen resume helper hash drift" >&2
  exit 2
}
test "$(sha256sum "$CHECKPOINT" | awk '{print $1}')" = "$CHECKPOINT_SHA256" || {
  echo "checkpoint frontend hash drift" >&2
  exit 2
}
for name in normal_1.pcap normal_2.pcap normal_scanning1.pcap \
  password_normal1.pcap injection_normal1.pcap MITM_normal1.pcap; do
  test -s "$TON_PILOT/$name" || {
    echo "missing ToN pilot PCAP: $TON_PILOT/$name" >&2
    exit 2
  }
done
while IFS=, read -r dataset name role bytes sha container model_use raw_label; do
  test "$name" != source_file || continue
  path="$TON_PILOT/$name"
  test "$(stat -c %s "$path")" = "$bytes" || {
    echo "ToN pilot size drift: $name" >&2
    exit 2
  }
done < "$TON_PILOT_MANIFEST"
test -d "$TON_EXTRACTED" || {
  echo "missing ToN extracted metadata: $TON_EXTRACTED" >&2
  exit 2
}
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
    gotham_sources=0
    gotham_members=0
    ton_files=0
    auxiliary=0
    member_total=0
    test ! -d "$RUN_ROOT/gotham_causal_cache" || \
      gotham_sources=$(find "$RUN_ROOT/gotham_causal_cache" -maxdepth 1 -name '*.npz' | wc -l)
    test ! -d "$RUN_ROOT/gotham_member_cache" || \
      gotham_members=$(find "$RUN_ROOT/gotham_member_cache" -maxdepth 1 -name '*.npz' | wc -l)
    test ! -d "$RUN_ROOT/ton_file_cache" || \
      ton_files=$(find "$RUN_ROOT/ton_file_cache" -maxdepth 1 -name '*.npz' | wc -l)
    test ! -d "$RUN_ROOT/auxiliary_causal_cache" || \
      auxiliary=$(find "$RUN_ROOT/auxiliary_causal_cache" -maxdepth 1 -name '*.npz' | wc -l)
    test ! -s "$RUN_ROOT/ckbv_gotham_member_plan.csv" || \
      member_total=$(( $(wc -l < "$RUN_ROOT/ckbv_gotham_member_plan.csv") - 1 ))
    test ! -s "$RUN_ROOT/current_phase.txt" || \
      live_phase=$(awk -F= '$1 == "phase" {print $2; exit}' \
        "$RUN_ROOT/current_phase.txt")
    printf 'CKBV_PROGRESS utc=%s phase=%s job=%s partition=%s gotham_sources=%s/30 gotham_members=%s/%s auxiliary=%s/31 ton_files=%s/4\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$live_phase" "$JOB_ID" "$PARTITION" \
      "$gotham_sources" "$gotham_members" "$member_total" "$auxiliary" "$ton_files"
  done
}
write_phase startup
heartbeat &
heartbeat_pid=$!

cd "$BASE"
source scripts/00_env_issue27ckc.sh
module load apps/tshark/4.6.6
test -s "$PCAP_LIB_DIR/libpcap.so.1" || {
  echo "compute-node libpcap missing: $PCAP_LIB_DIR/libpcap.so.1" >&2
  exit 2
}
export LD_LIBRARY_PATH="$PCAP_LIB_DIR:${LD_LIBRARY_PATH:-}"
TSHARK=$(command -v tshark)
PCAP_RESOLVED=$(ldd "$TSHARK" | awk '$1 == "libpcap.so.1" {print $3}')
test "$PCAP_RESOLVED" = "$PCAP_LIB_DIR/libpcap.so.1" || {
  echo "TShark libpcap mismatch: $PCAP_RESOLVED" >&2
  exit 2
}
TSHARK_VERSION=$("$TSHARK" --version | head -n 1)
case "$TSHARK_VERSION" in
  "TShark (Wireshark) 4.6.6"*) ;;
  *) echo "unexpected TShark version: $TSHARK_VERSION" >&2; exit 2 ;;
esac
test "$("$TSHARK" -n -r "$TON_PILOT/normal_1.pcap" -c 1 \
  -T fields -e frame.number 2>/dev/null)" = 1 || {
  echo "real-PCAP TShark probe failed" >&2
  exit 2
}

export PYTHONPATH="$CODE_ROOT:$BASE/repo/ood${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export CKBU_COMMIT_SHA="$COMMIT_SHA"
export CKBU_TSHARK_VERSION="$TSHARK_VERSION"
printf 'job_id=%s\npartition=%s\ncommit_sha=%s\ncode_root=%s\nreuse_roots=%s\ngotham_workers=%s\nton_workers=%s\nstarted_utc=%s\n' \
  "$JOB_ID" "$PARTITION" "$COMMIT_SHA" "$CODE_ROOT" "$REUSE_ROOTS" \
  "$GOTHAM_WORKERS" "$TON_WORKERS" "$started_utc" \
  > "$RUN_ROOT/slurm_identity.txt"
scontrol show job -o "$JOB_ID" \
  > "$RUN_ROOT/slurm_job_at_start.txt" 2>/dev/null || true

write_phase contract_checks
python -m py_compile "$FRONTEND" "$FORMAL" "$RESUME" "$CHECKPOINT"
python "$FRONTEND" --mode unit
python "$FORMAL" --mode contract-unit
python "$RESUME" --mode unit
python "$CHECKPOINT" --mode unit

write_phase immutable_planning
python "$FRONTEND" --mode plan-gotham --out "$RUN_ROOT" \
  --gotham-zip "$GOTHAM_ZIP" \
  --targets "$BASE_TARGETS" --targets "$REPORT_TARGETS"
python "$FRONTEND" --mode plan-auxiliary --out "$RUN_ROOT" \
  --aux-manifest "$CKBO_AUX_MANIFEST"
python "$FRONTEND" --mode plan-ton-pilot --out "$RUN_ROOT" \
  --ton-pilot-dir "$TON_PILOT"
python "$CHECKPOINT" --mode plan-gotham-members \
  --gotham-zip "$GOTHAM_ZIP" \
  --source-plan "$RUN_ROOT/ckbu_gotham_source_plan.csv" \
  --member-plan "$RUN_ROOT/ckbv_gotham_member_plan.csv"

REUSE_AUX=()
REUSE_GOTHAM=()
REUSE_MEMBER=()
REUSE_TON=()
IFS=':' read -r -a reuse_roots <<< "$REUSE_ROOTS"
for root in "${reuse_roots[@]}"; do
  test ! -d "$root/auxiliary_causal_cache" || \
    REUSE_AUX+=(--reuse-cache-dir "$root/auxiliary_causal_cache")
  test ! -d "$root/gotham_causal_cache" || \
    REUSE_GOTHAM+=(--reuse-source-cache "$root/gotham_causal_cache")
  test ! -d "$root/gotham_member_cache" || \
    REUSE_MEMBER+=(--reuse-member-cache "$root/gotham_member_cache")
  test ! -d "$root/ton_file_cache" || \
    REUSE_TON+=(--reuse-ton-file-cache "$root/ton_file_cache")
done

write_phase auxiliary_reuse_or_repair
python -u "$RESUME" --mode run-auxiliary --frontend "$FRONTEND" \
  --out "$RUN_ROOT" --worker-out "$RUN_ROOT/auxiliary_worker" \
  --gotham-zip "$GOTHAM_ZIP" \
  --source-plan "$RUN_ROOT/ckbu_auxiliary_source_plan.csv" \
  --cache-dir "$RUN_ROOT/auxiliary_causal_cache" \
  "${REUSE_AUX[@]}" --tshark "$TSHARK" --max-workers 2 \
  > "$RUN_ROOT/auxiliary_checkpoint_stage.log" 2>&1

write_phase ton_file_checkpoints
python -u "$CHECKPOINT" --mode run-ton-files --out "$RUN_ROOT" \
  --ton-pilot-dir "$TON_PILOT" --ton-extracted-root "$TON_EXTRACTED" \
  --ckbt-candidate-manifest "$CKBT_MANIFEST" \
  --ton-file-cache "$RUN_ROOT/ton_file_cache" "${REUSE_TON[@]}" \
  --ton-normal-budget 4000 --ton-workers "$TON_WORKERS" \
  --ton-file-timeout-seconds 21600 --stale-seconds 900 \
  --progress-every 25000 --seed 27 --tshark "$TSHARK" \
  > "$RUN_ROOT/ton_checkpoint_stage.log" 2>&1

write_phase gotham_member_checkpoints
elapsed=$(( $(date +%s) - started_epoch ))
available=$(( 129600 - elapsed - 14400 ))
test "$available" -gt 0 || {
  echo "insufficient allocation remains before Gotham stage: $available" >&2
  exit 2
}
python -u "$CHECKPOINT" --mode run-gotham-members --out "$RUN_ROOT" \
  --gotham-zip "$GOTHAM_ZIP" \
  --source-plan "$RUN_ROOT/ckbu_gotham_source_plan.csv" \
  --member-plan "$RUN_ROOT/ckbv_gotham_member_plan.csv" \
  --member-cache "$RUN_ROOT/gotham_member_cache" \
  --source-cache "$RUN_ROOT/gotham_causal_cache" \
  "${REUSE_GOTHAM[@]}" "${REUSE_MEMBER[@]}" \
  --targets "$BASE_TARGETS" --targets "$REPORT_TARGETS" \
  --raw51-mask "$RAW51_MASK" --raw51-mask-sha256 "$RAW51_MASK_SHA256" \
  --tshark "$TSHARK" --max-workers "$GOTHAM_WORKERS" \
  --member-timeout-seconds 14400 --stale-seconds 3600 \
  --liveness-seconds 300 --heartbeat-seconds 60 \
  --progress-every 25000 --available-seconds "$available" \
  --projection-safety-factor 2.0 \
  > "$RUN_ROOT/gotham_checkpoint_stage.log" 2>&1

write_phase aggregate_causal_features
python "$FRONTEND" --mode aggregate-gotham --out "$RUN_ROOT" \
  --source-plan "$RUN_ROOT/ckbu_gotham_source_plan.csv" \
  --cache-dir "$RUN_ROOT/gotham_causal_cache" \
  --raw51-mask "$RAW51_MASK" --raw51-mask-sha256 "$RAW51_MASK_SHA256"
python "$FRONTEND" --mode aggregate-auxiliary --out "$RUN_ROOT" \
  --source-plan "$RUN_ROOT/ckbu_auxiliary_source_plan.csv" \
  --cache-dir "$RUN_ROOT/auxiliary_causal_cache"

write_phase formal_seed27_model
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export NUMEXPR_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
python -u "$FORMAL" --mode formal --seed 27 \
  --threads "${SLURM_CPUS_PER_TASK:-8}" \
  --epochs 24 --batch-size 512 --tabm-k 16 --tabm-width 192 \
  --tabm-blocks 3 --extra-trees 500 --train-cap 4000 \
  --eval-cap 3000 --bootstrap-reps 500 --aux-rows-per-source 600 \
  --out "$RUN_ROOT" \
  --gotham-manifest "$RUN_ROOT/ckbu_gotham_unified_causal_manifest.csv" \
  --gotham-cache "$RUN_ROOT/gotham_causal_cache" \
  --auxiliary-manifest "$RUN_ROOT/ckbu_auxiliary_unified_causal_manifest.csv" \
  --auxiliary-plan "$RUN_ROOT/ckbu_auxiliary_source_plan.csv" \
  --auxiliary-cache "$RUN_ROOT/auxiliary_causal_cache" \
  --ton-cache "$RUN_ROOT/ckbu_ton_raw_pcap_pilot_causal_samples.npz" \
  --ckbq-predictions "$CKBQ_PREDICTIONS" \
  --raw51-mask "$RAW51_MASK" --raw51-mask-sha256 "$RAW51_MASK_SHA256"

write_phase validate_and_pack
ended_epoch=$(date +%s)
ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'started_utc=%s\nended_utc=%s\nwall_seconds=%s\njob_id=%s\npartition=%s\n' \
  "$started_utc" "$ended_utc" "$((ended_epoch-started_epoch))" \
  "$JOB_ID" "$PARTITION" > "$RUN_ROOT/run_timing.txt"
sstat -j "${JOB_ID}.batch" \
  --format=JobID,AveCPU,AveRSS,MaxRSS,MaxDiskRead,MaxDiskWrite -P \
  > "$RUN_ROOT/slurm_in_job_accounting.csv" 2>/dev/null || true

CKBV_PARTITION="$PARTITION" CKBV_JOB_ID="$JOB_ID" CKBV_ALLOW_RUNNING=1 \
  bash "$VALIDATOR"
write_phase complete
echo "CKBV_RESULT_COMPLETE partition=$PARTITION job_id=$JOB_ID"
