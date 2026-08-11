#!/usr/bin/env bash
# CKDA D0: fit-only representation compatibility census and resource pilot.
# This job does not train an encoder, read labels/scores, open FINAL, or emit
# performance embeddings.  It produces the complete frozen D0 verdict chain.
#SBATCH -J ckda_d0
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=0-12:00:00
#SBATCH --no-requeue

set -euo pipefail

BASE=${CKDA_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
DATA_ROOT=${CKDA_DATA_ROOT:-/public/home/jiangxinwei.zr/work/paper04/datasets}
BUNDLE_ROOT=${CKDA_BUNDLE_ROOT:?missing CKDA_BUNDLE_ROOT}
COMMIT_SHA=${CKDA_COMMIT_SHA:?missing CKDA_COMMIT_SHA}
PARTITION=${SLURM_JOB_PARTITION:?missing SLURM_JOB_PARTITION}
JOB_ID=${SLURM_JOB_ID:?missing SLURM_JOB_ID}

case "$PARTITION" in
  amd) ;;
  *) echo "invalid CKDA D0 partition: $PARTITION" >&2; exit 2 ;;
esac

PAYLOAD="$BUNDLE_ROOT/payload"
AUDIT="$PAYLOAD/repo/ood/issue27ckda_d0_representation_compatibility_audit_v1.py"
PILOT="$PAYLOAD/repo/ood/issue27ckda_d0_resource_pilot_v1.py"
VALIDATOR="$PAYLOAD/repo/ood/issue27ckda_d0_validate_and_pack_v1.py"
CKBU="$PAYLOAD/repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py"
CONTRACT="$PAYLOAD/runs/mainline_docs/ckda_d0_representation_compatibility_audit_preregistered_20260811.md"
EVIDENCE="$PAYLOAD/runs/mainline_docs/ckda_d0_official_candidate_evidence_20260811.json"
EVIDENCE_MANIFEST="$PAYLOAD/runs/mainline_docs/ckda_d0_official_evidence_manifest_20260811.csv"
GOTHAM_ALLOW="$PAYLOAD/runs/mainline_docs/ckcz_gotham_source_allowlist_20260809.csv"
AUX_ALLOW="$PAYLOAD/runs/mainline_docs/ckcz_auxiliary_source_allowlist_20260809.csv"
TON_MANIFEST="$PAYLOAD/runs/mainline_docs/ckbu_ton_raw_pcap_pilot_manifest_20260723.csv"
NETFOUND_SOURCE="$PAYLOAD/vendor/netFound"
NETFOUND_MODEL="$PAYLOAD/vendor/netFound-base"

RUN154917="$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917"
C1_ROOT="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
BASE_TARGETS="$C1_ROOT/canonical_source_target_index.csv"
GOTHAM_PLAN="$RUN154917/ckbu_gotham_source_plan.csv"
AUX_PLAN="$RUN154917/ckbu_auxiliary_source_plan.csv"
GOTHAM_CACHE="$RUN154917/gotham_causal_cache"
TON_AUDIT="$RUN154917/ckbu_ton_raw_pcap_materialization_audit.csv"
GOTHAM_ZIP="$DATA_ROOT/gotham2025/raw/GothamDataset2025.zip"
TON_PCAP_ROOT="$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1"

RUN_NAME="issue27ckda_d0_representation_compatibility_audit_v1_2026-08-11_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"
STAGE_ROOT="$BASE/runs/.${RUN_NAME}.stage"
CONTROL_ROOT="$BASE/runs/${RUN_NAME}_control"
PULLBACK="$BASE/runs/${RUN_NAME}_pullback.tar.gz"
PHASE=startup
heartbeat_pid=""
active_pid=""

write_phase() {
  PHASE=$1
  printf 'phase=%s\nupdated_utc=%s\n' "$PHASE" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    > "$CONTROL_ROOT/current_phase.txt"
}

cleanup() {
  status=$?
  test -z "$active_pid" || kill "$active_pid" >/dev/null 2>&1 || true
  test -z "$heartbeat_pid" || kill "$heartbeat_pid" >/dev/null 2>&1 || true
  wait >/dev/null 2>&1 || true
  if test "$status" -ne 0; then
    printf 'status=FAILED\nphase=%s\nexit_code=%s\nfailed_utc=%s\n' \
      "$PHASE" "$status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      > "$CONTROL_ROOT/job_failure.txt"
    test ! -d "$STAGE_ROOT" || cp "$CONTROL_ROOT/job_failure.txt" "$STAGE_ROOT/engineering_failure.json" || true
  fi
  exit "$status"
}
trap cleanup EXIT

heartbeat() {
  while true; do
    sleep 60
    checkpoints=0
    test ! -d "${CHECKPOINT_ROOT:-/nonexistent}/source_checkpoints" || \
      checkpoints=$(find "$CHECKPOINT_ROOT/source_checkpoints" -maxdepth 1 -type f -name '*.json' | wc -l)
    printf 'CKDA_D0_PROGRESS utc=%s phase=%s job=%s partition=%s completed_member_checkpoints=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$PHASE" "$JOB_ID" "$PARTITION" "$checkpoints"
  done
}

run_guarded() {
  name=$1
  stall_seconds=$2
  log=$3
  shift 3
  : > "$log"
  "$@" > "$log" 2>&1 &
  active_pid=$!
  last_size=0
  last_change=$(date +%s)
  while kill -0 "$active_pid" >/dev/null 2>&1; do
    sleep 60
    size=$(stat -c %s "$log" 2>/dev/null || echo 0)
    if test "$size" -ne "$last_size"; then
      last_size=$size
      last_change=$(date +%s)
    fi
    age=$(( $(date +%s) - last_change ))
    printf 'CKDA_D0_UNIT_PROGRESS phase=%s log_bytes=%s silence_seconds=%s\n' "$name" "$size" "$age"
    if test "$age" -ge "$stall_seconds"; then
      echo "CKDA_D0_NO_COMPLETED_UNIT_PROGRESS phase=$name silence_seconds=$age" >&2
      kill -TERM "$active_pid" >/dev/null 2>&1 || true
      sleep 20
      kill -KILL "$active_pid" >/dev/null 2>&1 || true
      wait "$active_pid" || true
      active_pid=""
      return 124
    fi
  done
  set +e
  wait "$active_pid"
  status=$?
  set -e
  active_pid=""
  test "$status" -eq 0 || { tail -100 "$log" >&2 || true; return "$status"; }
  tail -40 "$log" || true
}

for path in \
  "$BASE/scripts/00_env_issue27ckc.sh" "$AUDIT" "$PILOT" "$VALIDATOR" "$CKBU" \
  "$CONTRACT" "$EVIDENCE" "$EVIDENCE_MANIFEST" "$GOTHAM_ALLOW" "$AUX_ALLOW" \
  "$TON_MANIFEST" "$NETFOUND_SOURCE/LICENSE" "$NETFOUND_MODEL/config.json" \
  "$NETFOUND_MODEL/model.safetensors" "$BASE_TARGETS" "$GOTHAM_PLAN" "$AUX_PLAN" \
  "$TON_AUDIT" "$GOTHAM_ZIP"; do
  test -s "$path" || { echo "missing immutable CKDA D0 input: $path" >&2; exit 2; }
done
for directory in "$GOTHAM_CACHE" "$TON_PCAP_ROOT" "$PAYLOAD/vendor_py"; do
  test -d "$directory" || { echo "missing immutable CKDA D0 directory: $directory" >&2; exit 2; }
done
test ! -e "$RUN_ROOT" || { echo "refusing mixed result root: $RUN_ROOT" >&2; exit 2; }
test ! -e "$STAGE_ROOT" || { echo "refusing stale stage root: $STAGE_ROOT" >&2; exit 2; }
test ! -e "$CONTROL_ROOT" || { echo "refusing stale control root: $CONTROL_ROOT" >&2; exit 2; }
test ! -e "$PULLBACK" || { echo "refusing stale pullback: $PULLBACK" >&2; exit 2; }
mkdir -p "$STAGE_ROOT" "$CONTROL_ROOT"
printf 'job_id=%s\npartition=%s\ncommit_sha=%s\nbundle_root=%s\nstarted_utc=%s\n' \
  "$JOB_ID" "$PARTITION" "$COMMIT_SHA" "$BUNDLE_ROOT" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  > "$CONTROL_ROOT/slurm_identity.txt"
write_phase startup
heartbeat &
heartbeat_pid=$!

cd "$BASE"
source scripts/00_env_issue27ckc.sh
module load apps/tshark/4.6.6
PCAP_LIB_DIR=/share/software/CST/installed/MCR/bin/glnxa64
test -s "$PCAP_LIB_DIR/libpcap.so.1" || { echo "missing compute-node libpcap" >&2; exit 2; }
export LD_LIBRARY_PATH="$PCAP_LIB_DIR:${LD_LIBRARY_PATH:-}"
TSHARK=$(command -v tshark)
test "$(ldd "$TSHARK" | awk '$1 == "libpcap.so.1" {print $3}')" = "$PCAP_LIB_DIR/libpcap.so.1" || {
  echo "TShark shared-libpcap resolution failed" >&2; exit 2;
}
export PYTHONPATH="$PAYLOAD/vendor_py:$PAYLOAD/repo/ood${PYTHONPATH:+:$PYTHONPATH}"
export TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}

write_phase contract_and_dependency_gates
(cd "$BUNDLE_ROOT" && sha256sum -c SHA256SUMS)
python -m py_compile "$AUDIT" "$PILOT" "$VALIDATOR" "$CKBU"
python "$AUDIT" contract-test
python "$PILOT" contract-test
python "$VALIDATOR" contract-test
python - <<'PY'
import psutil, safetensors, tokenizers, transformers
print("CKDA_D0_DEPENDENCY_GATE_PASS", transformers.__version__, safetensors.__version__, tokenizers.__version__, psutil.__version__)
PY
test "$(sha256sum "$CONTRACT" | awk '{print $1}')" = ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5
test "$(sha256sum "$NETFOUND_MODEL/model.safetensors" | awk '{print $1}')" = e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105
test "$(stat -c %s "$NETFOUND_MODEL/model.safetensors")" = 698780900

write_phase prepare_fit_prefixes
python "$AUDIT" prepare-cutoffs \
  --contract "$CONTRACT" \
  --base-targets "$BASE_TARGETS" \
  --gotham-allowlist "$GOTHAM_ALLOW" \
  --aux-allowlist "$AUX_ALLOW" \
  --gotham-source-plan "$GOTHAM_PLAN" \
  --gotham-cache-dir "$GOTHAM_CACHE" \
  --aux-source-plan "$AUX_PLAN" \
  --ton-manifest "$TON_MANIFEST" \
  --ton-audit "$TON_AUDIT" \
  --ton-pcap-root "$TON_PCAP_ROOT" \
  --gotham-zip "$GOTHAM_ZIP" \
  --out "$STAGE_ROOT/ckda_d0_fit_prefix_manifest.csv" \
  > "$CONTROL_ROOT/prepare_cutoffs.log" 2>&1
cat "$CONTROL_ROOT/prepare_cutoffs.log"
PREFIX_SHA=$(sha256sum "$STAGE_ROOT/ckda_d0_fit_prefix_manifest.csv" | awk '{print $1}')
CHECKPOINT_ROOT="$BASE/runs/issue27ckda_d0_census_checkpoint_v1_${PARTITION}_${PREFIX_SHA:0:16}"
mkdir -p "$CHECKPOINT_ROOT"

write_phase census_real_fit_prefixes
run_guarded census_real_fit_prefixes 1800 "$CONTROL_ROOT/census.log" \
  python -u "$AUDIT" census \
    --contract "$CONTRACT" \
    --cutoffs "$STAGE_ROOT/ckda_d0_fit_prefix_manifest.csv" \
    --ckbu-decoder "$CKBU" \
    --tshark "$TSHARK" \
    --out "$CHECKPOINT_ROOT"
cp "$CHECKPOINT_ROOT/ckda_d0_data_census.json" "$STAGE_ROOT/ckda_d0_data_census.json"
cp "$CHECKPOINT_ROOT/ckda_d0_pilot_session_manifest.csv" "$STAGE_ROOT/ckda_d0_pilot_session_manifest.csv"

write_phase resource_pilot_real_fit_prefixes
run_guarded resource_pilot_real_fit_prefixes 3600 "$CONTROL_ROOT/resource_pilot.log" \
  python -u "$PILOT" run \
    --contract "$CONTRACT" \
    --cutoffs "$STAGE_ROOT/ckda_d0_fit_prefix_manifest.csv" \
    --census "$STAGE_ROOT/ckda_d0_data_census.json" \
    --netfound-source "$NETFOUND_SOURCE" \
    --netfound-checkpoint "$NETFOUND_MODEL" \
    --tshark "$TSHARK" \
    --out "$STAGE_ROOT/ckda_d0_resource_pilot.csv"

write_phase compile_d0_verdict
cp "$EVIDENCE_MANIFEST" "$STAGE_ROOT/ckda_d0_evidence_manifest.csv"
python "$AUDIT" compile \
  --contract "$CONTRACT" \
  --evidence "$EVIDENCE" \
  --evidence-manifest "$STAGE_ROOT/ckda_d0_evidence_manifest.csv" \
  --census "$STAGE_ROOT/ckda_d0_data_census.json" \
  --resource-pilot "$STAGE_ROOT/ckda_d0_resource_pilot.csv" \
  --out "$STAGE_ROOT" \
  > "$CONTROL_ROOT/compile.log" 2>&1
cat "$CONTROL_ROOT/compile.log"
python "$AUDIT" finalize-boundary \
  --contract "$CONTRACT" \
  --cutoff-audit "$STAGE_ROOT/ckda_d0_fit_prefix_manifest.json" \
  --census "$STAGE_ROOT/ckda_d0_data_census.json" \
  --out "$STAGE_ROOT/ckda_d0_final_exclusion_audit.json"

write_phase validate_and_finalize
python "$VALIDATOR" \
  --result "$STAGE_ROOT" \
  --contract "$CONTRACT" \
  --audit-module "$AUDIT" \
  --pilot-module "$PILOT" \
  > "$CONTROL_ROOT/validation.log" 2>&1
cat "$CONTROL_ROOT/validation.log"
cp "$CONTROL_ROOT/current_phase.txt" "$STAGE_ROOT/last_precomplete_phase.txt"
mv "$STAGE_ROOT" "$RUN_ROOT"

write_phase package_pullback
PULLBACK_TMP="${PULLBACK}.tmp.${JOB_ID}"
tar -czf "$PULLBACK_TMP" -C "$BASE/runs" "$RUN_NAME"
mv "$PULLBACK_TMP" "$PULLBACK"
printf '%s  %s\n' "$(sha256sum "$PULLBACK" | awk '{print $1}')" "$(basename "$PULLBACK")" > "$PULLBACK.sha256"

write_phase complete
printf 'status=PASS\njob_id=%s\npartition=%s\ncommit_sha=%s\nrun_root=%s\npullback=%s\ncompleted_utc=%s\n' \
  "$JOB_ID" "$PARTITION" "$COMMIT_SHA" "$RUN_ROOT" "$PULLBACK" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  > "$CONTROL_ROOT/terminal_success.txt"
echo "CKDA_D0_COMPLETE job=$JOB_ID partition=$PARTITION pullback=$PULLBACK"
