#!/bin/bash
# CKBU: one result-producing unified-front-end + process-rescue run.
# Submit once to AMD and once to Intel.  Every writable path contains partition
# and job id, so both copies may finish without corrupting one another.
#SBATCH -J ckbu_process
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=1-00:00:00

set -euo pipefail

BASE=${CKBU_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
DATA_ROOT=${CKBU_DATA_ROOT:-/public/home/jiangxinwei.zr/work/paper04/datasets}
PARTITION=${SLURM_JOB_PARTITION:?missing SLURM_JOB_PARTITION}
JOB_ID=${SLURM_JOB_ID:?missing SLURM_JOB_ID}
COMMIT_SHA=${CKBU_COMMIT_SHA:?missing CKBU_COMMIT_SHA}
FRONTEND_SHA256=${CKBU_FRONTEND_SHA256:?missing CKBU_FRONTEND_SHA256}
FORMAL_SHA256=${CKBU_FORMAL_SHA256:?missing CKBU_FORMAL_SHA256}

case "$PARTITION" in amd|intel) ;; *) echo "invalid partition: $PARTITION" >&2; exit 2;; esac

RUN_NAME="issue27ckbu_unified_process_rescue_formal_v1_2026-07-23_seed27_${PARTITION}_${JOB_ID}"
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

test -d "$BASE" || { echo "missing project directory: $BASE" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing allowed environment script" >&2; exit 2; }
test -s "$FRONTEND" && test -s "$FORMAL" || { echo "missing CKBU code" >&2; exit 2; }
test "$(sha256sum "$FRONTEND" | awk '{print $1}')" = "$FRONTEND_SHA256" || { echo "frontend hash mismatch" >&2; exit 2; }
test "$(sha256sum "$FORMAL" | awk '{print $1}')" = "$FORMAL_SHA256" || { echo "formal hash mismatch" >&2; exit 2; }
for path in "$GOTHAM_ZIP" "$CKBT_MANIFEST" "$CKBQ_PREDICTIONS" "$CKBO_AUX_MANIFEST" "$REPORT_TARGETS" "$BASE_TARGETS" "$TON_PILOT_MANIFEST"; do
  test -s "$path" || { echo "missing required immutable input: $path" >&2; exit 2; }
done
for name in normal_1.pcap normal_2.pcap normal_scanning1.pcap password_normal1.pcap injection_normal1.pcap MITM_normal1.pcap; do
  test -s "$TON_PILOT/$name" || { echo "missing ToN raw pilot PCAP: $TON_PILOT/$name" >&2; exit 2; }
done
test -d "$TON_EXTRACTED" || { echo "missing ToN extracted metadata root: $TON_EXTRACTED" >&2; exit 2; }
test ! -e "$RUN_ROOT" || { echo "refusing mixed run root: $RUN_ROOT" >&2; exit 2; }
mkdir -p "$RUN_ROOT"

started_epoch=$(date +%s)
started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
heartbeat_pid=""
cleanup() {
  status=$?
  if test -n "$heartbeat_pid"; then
    kill "$heartbeat_pid" >/dev/null 2>&1 || true
    wait "$heartbeat_pid" >/dev/null 2>&1 || true
  fi
  if test "$status" -ne 0; then
    printf 'status=FAILED\nexit_code=%s\nfailed_utc=%s\n' "$status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$RUN_ROOT/job_failure.txt"
  fi
  exit "$status"
}
trap cleanup EXIT

heartbeat() {
  while true; do
    sleep 300
    gotham=0; aux=0; outputs=0
    test -d "$RUN_ROOT/gotham_causal_cache" && gotham=$(find "$RUN_ROOT/gotham_causal_cache" -maxdepth 1 -name '*.npz' | wc -l || true)
    test -d "$RUN_ROOT/auxiliary_causal_cache" && aux=$(find "$RUN_ROOT/auxiliary_causal_cache" -maxdepth 1 -name '*.npz' | wc -l || true)
    outputs=$(find "$RUN_ROOT" -maxdepth 1 -type f | wc -l || true)
    printf 'CKBU_HEARTBEAT utc=%s job=%s partition=%s gotham_cache=%s aux_cache=%s top_files=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$JOB_ID" "$PARTITION" "$gotham" "$aux" "$outputs"
  done
}
heartbeat &
heartbeat_pid=$!

cd "$BASE"
source scripts/00_env_issue27ckc.sh
if type module >/dev/null 2>&1; then
  module load apps/tshark/4.6.6
else
  echo "module command unavailable in batch shell" >&2
  exit 2
fi
TSHARK=$(command -v tshark)
TSHARK_VERSION=$(tshark --version | head -n 1)
case "$TSHARK_VERSION" in "TShark (Wireshark) 4.6.6"*) ;; *) echo "unexpected TShark: $TSHARK_VERSION" >&2; exit 2;; esac

export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export NUMEXPR_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export CKBU_COMMIT_SHA="$COMMIT_SHA"
export CKBU_TSHARK_VERSION="$TSHARK_VERSION"

python - "$TON_PILOT" "$TON_PILOT_MANIFEST" <<'PY'
import csv, hashlib, sys
from pathlib import Path

root=Path(sys.argv[1]); manifest=Path(sys.argv[2])
for row in csv.DictReader(manifest.open(encoding="utf-8")):
    path=root/row["source_file"]
    if path.stat().st_size != int(row["bytes"]):
        raise SystemExit(f"ToN pilot size mismatch at execution: {path}")
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4*1024*1024), b""):
            digest.update(block)
    if digest.hexdigest() != row["sha256"]:
        raise SystemExit(f"ToN pilot SHA-256 mismatch at execution: {path}")
print("CKBU_TON_EXECUTION_HASHES_OK")
PY

printf 'job_id=%s\npartition=%s\ncommit_sha=%s\nfrontend_sha256=%s\nformal_sha256=%s\ntshark=%s\ntshark_version=%s\nstarted_utc=%s\n' \
  "$JOB_ID" "$PARTITION" "$COMMIT_SHA" "$FRONTEND_SHA256" "$FORMAL_SHA256" "$TSHARK" "$TSHARK_VERSION" "$started_utc" \
  > "$RUN_ROOT/slurm_identity.txt"
scontrol show job -o "$JOB_ID" > "$RUN_ROOT/slurm_job_at_start.txt" 2>/dev/null || true

python -m py_compile "$FRONTEND" "$FORMAL"
python "$FRONTEND" --mode unit
python "$FORMAL" --mode contract-unit

python "$FRONTEND" --mode plan-gotham --out "$RUN_ROOT" --gotham-zip "$GOTHAM_ZIP" \
  --targets "$BASE_TARGETS" --targets "$REPORT_TARGETS"
python "$FRONTEND" --mode plan-auxiliary --out "$RUN_ROOT" --aux-manifest "$CKBO_AUX_MANIFEST"
python "$FRONTEND" --mode plan-ton-pilot --out "$RUN_ROOT" --ton-pilot-dir "$TON_PILOT"

GOTHAM_SOURCES=$(python -c "import pandas as pd; print(len(pd.read_csv(r'$RUN_ROOT/ckbu_gotham_source_plan.csv')))" )
for ((index=0; index<GOTHAM_SOURCES; index++)); do
  python -u "$FRONTEND" --mode materialize-gotham-source --out "$RUN_ROOT" \
    --gotham-zip "$GOTHAM_ZIP" --targets "$BASE_TARGETS" --targets "$REPORT_TARGETS" \
    --source-plan "$RUN_ROOT/ckbu_gotham_source_plan.csv" --source-index "$index" \
    --cache-dir "$RUN_ROOT/gotham_causal_cache" --tshark "$TSHARK"
done
python "$FRONTEND" --mode aggregate-gotham --out "$RUN_ROOT" \
  --source-plan "$RUN_ROOT/ckbu_gotham_source_plan.csv" --cache-dir "$RUN_ROOT/gotham_causal_cache"

AUX_SOURCES=$(python -c "import pandas as pd; print(len(pd.read_csv(r'$RUN_ROOT/ckbu_auxiliary_source_plan.csv')))" )
for ((index=0; index<AUX_SOURCES; index++)); do
  python -u "$FRONTEND" --mode materialize-auxiliary-source --out "$RUN_ROOT" \
    --gotham-zip "$GOTHAM_ZIP" --source-plan "$RUN_ROOT/ckbu_auxiliary_source_plan.csv" \
    --source-index "$index" --cache-dir "$RUN_ROOT/auxiliary_causal_cache" --tshark "$TSHARK"
done
python "$FRONTEND" --mode aggregate-auxiliary --out "$RUN_ROOT" \
  --source-plan "$RUN_ROOT/ckbu_auxiliary_source_plan.csv" --cache-dir "$RUN_ROOT/auxiliary_causal_cache"

python -u "$FRONTEND" --mode materialize-ton-pilot --out "$RUN_ROOT" \
  --ton-pilot-dir "$TON_PILOT" --ton-extracted-root "$TON_EXTRACTED" \
  --ckbt-candidate-manifest "$CKBT_MANIFEST" --ton-normal-budget 4000 --seed 27 --tshark "$TSHARK"

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
if command -v sstat >/dev/null 2>&1; then
  sstat -j "${JOB_ID}.batch" --format=JobID,AveCPU,AveRSS,MaxRSS,MaxVMSize -P > "$RUN_ROOT/slurm_in_job_accounting.csv" 2>/dev/null || true
fi

CKBU_PARTITION="$PARTITION" CKBU_JOB_ID="$JOB_ID" CKBU_ALLOW_RUNNING=1 \
  bash scripts/issue27ckbu_validate_and_pack_seed27.sh
echo "CKBU_RESULT_COMPLETE partition=$PARTITION job_id=$JOB_ID"
