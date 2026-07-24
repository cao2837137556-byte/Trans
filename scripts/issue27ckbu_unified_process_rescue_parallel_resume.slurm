#!/bin/bash
# CKBU execution-only repair: validated cache reuse plus concurrent source scans.
# Scientific inputs, frontend, formal model, seed, and thresholds are unchanged.
#SBATCH -J ckbu_parallel
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=1-12:00:00

set -euo pipefail

BASE=${CKBU_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
DATA_ROOT=${CKBU_DATA_ROOT:-/public/home/jiangxinwei.zr/work/paper04/datasets}
PARTITION=${SLURM_JOB_PARTITION:?missing SLURM_JOB_PARTITION}
JOB_ID=${SLURM_JOB_ID:?missing SLURM_JOB_ID}
COMMIT_SHA=${CKBU_COMMIT_SHA:?missing CKBU_COMMIT_SHA}
FRONTEND_SHA256=${CKBU_FRONTEND_SHA256:?missing CKBU_FRONTEND_SHA256}
FORMAL_SHA256=${CKBU_FORMAL_SHA256:?missing CKBU_FORMAL_SHA256}
RESUME_SHA256=${CKBU_RESUME_SHA256:?missing CKBU_RESUME_SHA256}
PREDECESSOR_ROOT=${CKBU_REUSE_RUN_ROOT:-$BASE/runs/issue27ckbu_unified_process_rescue_formal_v1_2026-07-23_seed27_amd_153973}
GOTHAM_WORKERS=${CKBU_GOTHAM_WORKERS:-4}
AUX_WORKERS=${CKBU_AUX_WORKERS:-2}

case "$PARTITION" in amd|intel) ;; *) echo "invalid partition: $PARTITION" >&2; exit 2;; esac
[[ "$GOTHAM_WORKERS" =~ ^[1-9][0-9]*$ ]] || { echo "invalid Gotham worker count" >&2; exit 2; }
[[ "$AUX_WORKERS" =~ ^[1-9][0-9]*$ ]] || { echo "invalid auxiliary worker count" >&2; exit 2; }
test "$((GOTHAM_WORKERS + AUX_WORKERS + 1))" -le "${SLURM_CPUS_PER_TASK:-8}" || {
  echo "parallel workers exceed allocated CPUs" >&2
  exit 2
}

RUN_NAME="issue27ckbu_unified_process_rescue_parallel_v2_2026-07-24_seed27_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"
GOTHAM_ZIP="$DATA_ROOT/gotham2025/raw/GothamDataset2025.zip"
TON_ROOT="$DATA_ROOT/external/ton_iot_raw_network"
TON_PILOT="$TON_ROOT/raw_pcap_pilot_v1"
TON_EXTRACTED="$TON_ROOT/extracted"
CKBT_MANIFEST="$BASE/runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/aux_process_support_candidate_manifest.csv"
CKBQ_ROOT=${CKBU_CKBQ_ROOT:-$BASE/runs/issue27ckbq_causal_minirocket_consensus_v1_2026-07-17_seed27_amd_153037}
CKBQ_PREDICTIONS="$CKBQ_ROOT/ckbq_record_predictions.csv.gz"
CKBO_AUX_MANIFEST="$CKBQ_ROOT/ckbo_auxiliary_benign_manifest.csv"
TON_PILOT_MANIFEST="$BASE/runs/mainline_docs/ckbu_ton_raw_pcap_pilot_manifest_20260723.csv"
REPORT_TARGETS="$BASE/runs/issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc/report_extension_recorded_targets.csv"
BASE_TARGETS="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1/canonical_source_target_index.csv"
FRONTEND="$BASE/repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py"
FORMAL="$BASE/repo/ood/issue27ckbu_unified_process_rescue_formal_v1.py"
RESUME="$BASE/repo/ood/issue27ckbu_parallel_cache_resume_v1.py"
VALIDATOR="$BASE/scripts/issue27ckbu_validate_and_pack_parallel_resume_seed27.sh"
PCAP_LIB_DIR="/share/software/CST/installed/MCR/bin/glnxa64"

test -d "$BASE" || { echo "missing project directory: $BASE" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing allowed environment script" >&2; exit 2; }
for path in "$FRONTEND" "$FORMAL" "$RESUME" "$VALIDATOR" "$GOTHAM_ZIP" \
  "$CKBT_MANIFEST" "$CKBQ_PREDICTIONS" "$CKBO_AUX_MANIFEST" "$REPORT_TARGETS" \
  "$BASE_TARGETS" "$TON_PILOT_MANIFEST"; do
  test -s "$path" || { echo "missing immutable input: $path" >&2; exit 2; }
done
test "$(sha256sum "$FRONTEND" | awk '{print $1}')" = "$FRONTEND_SHA256" || exit 2
test "$(sha256sum "$FORMAL" | awk '{print $1}')" = "$FORMAL_SHA256" || exit 2
test "$(sha256sum "$RESUME" | awk '{print $1}')" = "$RESUME_SHA256" || exit 2
for name in normal_1.pcap normal_2.pcap normal_scanning1.pcap password_normal1.pcap injection_normal1.pcap MITM_normal1.pcap; do
  test -s "$TON_PILOT/$name" || { echo "missing ToN pilot PCAP: $name" >&2; exit 2; }
done
test -d "$TON_EXTRACTED" || { echo "missing ToN extracted metadata root" >&2; exit 2; }
test ! -e "$RUN_ROOT" || { echo "refusing mixed run root: $RUN_ROOT" >&2; exit 2; }
mkdir -p "$RUN_ROOT"

started_epoch=$(date +%s)
started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
heartbeat_pid=""
stage_pids=()
cleanup() {
  status=$?
  if test -n "$heartbeat_pid"; then kill "$heartbeat_pid" >/dev/null 2>&1 || true; fi
  for pid in "${stage_pids[@]:-}"; do kill "$pid" >/dev/null 2>&1 || true; done
  wait >/dev/null 2>&1 || true
  if test "$status" -ne 0; then
    printf 'status=FAILED\nexit_code=%s\nfailed_utc=%s\n' \
      "$status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$RUN_ROOT/job_failure.txt"
  fi
  exit "$status"
}
trap cleanup EXIT

heartbeat() {
  while true; do
    sleep 300
    gotham=0; aux=0; top=0
    test -d "$RUN_ROOT/gotham_causal_cache" && gotham=$(find "$RUN_ROOT/gotham_causal_cache" -maxdepth 1 -name '*.npz' | wc -l || true)
    test -d "$RUN_ROOT/auxiliary_causal_cache" && aux=$(find "$RUN_ROOT/auxiliary_causal_cache" -maxdepth 1 -name '*.npz' | wc -l || true)
    top=$(find "$RUN_ROOT" -maxdepth 1 -type f | wc -l || true)
    printf 'CKBU_PARALLEL_HEARTBEAT utc=%s job=%s partition=%s gotham_cache=%s/30 aux_cache=%s/31 top_files=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$JOB_ID" "$PARTITION" "$gotham" "$aux" "$top"
  done
}
heartbeat &
heartbeat_pid=$!

cd "$BASE"
source scripts/00_env_issue27ckc.sh
module load apps/tshark/4.6.6
test -s "$PCAP_LIB_DIR/libpcap.so.1" || { echo "shared compute-node libpcap missing" >&2; exit 2; }
export LD_LIBRARY_PATH="$PCAP_LIB_DIR:${LD_LIBRARY_PATH:-}"
TSHARK=$(command -v tshark)
PCAP_RESOLVED=$(ldd "$TSHARK" | awk '$1 == "libpcap.so.1" {print $3}')
test "$PCAP_RESOLVED" = "$PCAP_LIB_DIR/libpcap.so.1" || { echo "TShark libpcap mismatch" >&2; exit 2; }
TSHARK_VERSION=$("$TSHARK" --version | head -n 1)
case "$TSHARK_VERSION" in "TShark (Wireshark) 4.6.6"*) ;; *) echo "unexpected TShark" >&2; exit 2;; esac
test "$("$TSHARK" -n -r "$TON_PILOT/normal_1.pcap" -c 1 -T fields -e frame.number 2>/dev/null)" = 1 || {
  echo "real-PCAP TShark probe failed" >&2
  exit 2
}

export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export CKBU_COMMIT_SHA="$COMMIT_SHA" CKBU_TSHARK_VERSION="$TSHARK_VERSION"
printf 'job_id=%s\npartition=%s\ncommit_sha=%s\npredecessor_root=%s\ngotham_workers=%s\naux_workers=%s\nstarted_utc=%s\n' \
  "$JOB_ID" "$PARTITION" "$COMMIT_SHA" "$PREDECESSOR_ROOT" "$GOTHAM_WORKERS" "$AUX_WORKERS" "$started_utc" \
  > "$RUN_ROOT/slurm_identity.txt"
scontrol show job -o "$JOB_ID" > "$RUN_ROOT/slurm_job_at_start.txt" 2>/dev/null || true

python -m py_compile "$FRONTEND" "$FORMAL" "$RESUME"
python "$FRONTEND" --mode unit
python "$FORMAL" --mode contract-unit
python "$RESUME" --mode unit

python "$FRONTEND" --mode plan-gotham --out "$RUN_ROOT" --gotham-zip "$GOTHAM_ZIP" \
  --targets "$BASE_TARGETS" --targets "$REPORT_TARGETS"
python "$FRONTEND" --mode plan-auxiliary --out "$RUN_ROOT" --aux-manifest "$CKBO_AUX_MANIFEST"
python "$FRONTEND" --mode plan-ton-pilot --out "$RUN_ROOT" --ton-pilot-dir "$TON_PILOT"

REUSE_GOTHAM=()
REUSE_AUX=()
if test -d "$PREDECESSOR_ROOT/gotham_causal_cache"; then
  REUSE_GOTHAM=(--reuse-cache-dir "$PREDECESSOR_ROOT/gotham_causal_cache")
fi
if test -d "$PREDECESSOR_ROOT/auxiliary_causal_cache"; then
  REUSE_AUX=(--reuse-cache-dir "$PREDECESSOR_ROOT/auxiliary_causal_cache")
fi

python -u "$RESUME" --mode run-gotham --frontend "$FRONTEND" --out "$RUN_ROOT" \
  --worker-out "$RUN_ROOT/gotham_worker" \
  --gotham-zip "$GOTHAM_ZIP" --source-plan "$RUN_ROOT/ckbu_gotham_source_plan.csv" \
  --cache-dir "$RUN_ROOT/gotham_causal_cache" "${REUSE_GOTHAM[@]}" \
  --targets "$BASE_TARGETS" --targets "$REPORT_TARGETS" --tshark "$TSHARK" \
  --max-workers "$GOTHAM_WORKERS" > "$RUN_ROOT/gotham_parallel_stage.log" 2>&1 &
stage_pids+=("$!")

python -u "$RESUME" --mode run-auxiliary --frontend "$FRONTEND" --out "$RUN_ROOT" \
  --worker-out "$RUN_ROOT/auxiliary_worker" \
  --gotham-zip "$GOTHAM_ZIP" --source-plan "$RUN_ROOT/ckbu_auxiliary_source_plan.csv" \
  --cache-dir "$RUN_ROOT/auxiliary_causal_cache" "${REUSE_AUX[@]}" \
  --tshark "$TSHARK" --max-workers "$AUX_WORKERS" \
  > "$RUN_ROOT/auxiliary_parallel_stage.log" 2>&1 &
stage_pids+=("$!")

python -u "$FRONTEND" --mode materialize-ton-pilot --out "$RUN_ROOT" \
  --ton-pilot-dir "$TON_PILOT" --ton-extracted-root "$TON_EXTRACTED" \
  --ckbt-candidate-manifest "$CKBT_MANIFEST" --ton-normal-budget 4000 \
  --seed 27 --tshark "$TSHARK" > "$RUN_ROOT/ton_parallel_stage.log" 2>&1 &
stage_pids+=("$!")

stage_failure=0
for pid in "${stage_pids[@]}"; do
  wait "$pid" || stage_failure=1
done
stage_pids=()
if test "$stage_failure" -ne 0; then
  echo "one or more parallel materialization stages failed" >&2
  for log in "$RUN_ROOT"/*_parallel_stage.log; do echo "=== $log ===" >&2; tail -n 100 "$log" >&2 || true; done
  exit 1
fi

python "$FRONTEND" --mode aggregate-gotham --out "$RUN_ROOT" \
  --source-plan "$RUN_ROOT/ckbu_gotham_source_plan.csv" --cache-dir "$RUN_ROOT/gotham_causal_cache"
python "$FRONTEND" --mode aggregate-auxiliary --out "$RUN_ROOT" \
  --source-plan "$RUN_ROOT/ckbu_auxiliary_source_plan.csv" --cache-dir "$RUN_ROOT/auxiliary_causal_cache"

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export NUMEXPR_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
python -u "$FORMAL" --mode formal --seed 27 --threads "${SLURM_CPUS_PER_TASK:-8}" \
  --epochs 24 --batch-size 512 --tabm-k 16 --tabm-width 192 --tabm-blocks 3 --extra-trees 500 \
  --train-cap 4000 --eval-cap 3000 --bootstrap-reps 500 --aux-rows-per-source 600 \
  --out "$RUN_ROOT" \
  --gotham-manifest "$RUN_ROOT/ckbu_gotham_unified_causal_manifest.csv" \
  --gotham-cache "$RUN_ROOT/gotham_causal_cache" \
  --auxiliary-manifest "$RUN_ROOT/ckbu_auxiliary_unified_causal_manifest.csv" \
  --auxiliary-plan "$RUN_ROOT/ckbu_auxiliary_source_plan.csv" \
  --auxiliary-cache "$RUN_ROOT/auxiliary_causal_cache" \
  --ton-cache "$RUN_ROOT/ckbu_ton_raw_pcap_pilot_causal_samples.npz" \
  --ckbq-predictions "$CKBQ_PREDICTIONS"

ended_epoch=$(date +%s)
ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'started_utc=%s\nended_utc=%s\nwall_seconds=%s\njob_id=%s\npartition=%s\n' \
  "$started_utc" "$ended_utc" "$((ended_epoch-started_epoch))" "$JOB_ID" "$PARTITION" > "$RUN_ROOT/run_timing.txt"
sstat -j "${JOB_ID}.batch" --format=JobID,AveCPU,AveRSS,MaxRSS,MaxVMSize -P \
  > "$RUN_ROOT/slurm_in_job_accounting.csv" 2>/dev/null || true

CKBU_PARTITION="$PARTITION" CKBU_JOB_ID="$JOB_ID" CKBU_ALLOW_RUNNING=1 \
  bash "$VALIDATOR"
echo "CKBU_PARALLEL_RESULT_COMPLETE partition=$PARTITION job_id=$JOB_ID"
