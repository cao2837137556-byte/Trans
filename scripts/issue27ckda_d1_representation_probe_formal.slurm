#!/usr/bin/env bash
# CKDA D1 complete result-producing I1 -> E3 frozen representation probe.
# No FINAL asset is opened.  A nonzero exit is an engineering failure and has
# no scientific verdict.  Long E3 work resumes from persistent member units.
#SBATCH -J ckda_d1
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=3-00:00:00
#SBATCH --no-requeue

set -euo pipefail

BASE=${CKDA_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
DATA_ROOT=${CKDA_DATA_ROOT:-/public/home/jiangxinwei.zr/work/paper04/datasets}
BUNDLE_ROOT=${CKDA_D1_BUNDLE_ROOT:?missing CKDA_D1_BUNDLE_ROOT}
D0_ROOT=${CKDA_D0_BUNDLE_ROOT:-/public/home/jiangxinwei.zr/work/issue27ckda_d0_representation_compatibility_20260811_r2}
COMMIT_SHA=${CKDA_D1_COMMIT_SHA:?missing CKDA_D1_COMMIT_SHA}
PARTITION=${SLURM_JOB_PARTITION:?missing SLURM_JOB_PARTITION}
JOB_ID=${SLURM_JOB_ID:?missing SLURM_JOB_ID}
test "$PARTITION" = amd || { echo "invalid CKDA D1 partition: $PARTITION" >&2; exit 2; }

PAYLOAD="$BUNDLE_ROOT/payload"
OOD="$PAYLOAD/repo/ood"
CONTRACT="$PAYLOAD/runs/mainline_docs/ckda_d1_frozen_representation_probe_preregistered_20260812.md"
CORE="$OOD/issue27ckda_d1_representation_probe_v1.py"
ROLE_PLAN="$OOD/issue27ckda_d1_role_plan_v1.py"
CENSUS="$OOD/issue27ckda_d1_benign_census_v1.py"
TARGET_METADATA="$OOD/issue27ckda_d1_target_metadata_v1.py"
E3_EMBED="$OOD/issue27ckda_d1_e3_embed_v1.py"
PROBE="$OOD/issue27ckda_d1_probe_runner_v1.py"
METRICS="$OOD/issue27ckda_d1_metrics_v1.py"
VALIDATOR="$OOD/issue27ckda_d1_validate_and_pack_v1.py"
CKBU="$OOD/issue27ckbu_unified_tshark_causal_frontend_v1.py"
CKCZ="$OOD/issue27ckcz_endpoint_pair_conflict_diagnostic_v1.py"
D0_AUDIT="$D0_ROOT/payload/repo/ood/issue27ckda_d0_representation_compatibility_audit_v1.py"
D0_PILOT="$D0_ROOT/payload/repo/ood/issue27ckda_d0_resource_pilot_v1.py"
NETFOUND_SOURCE="$D0_ROOT/payload/vendor/netFound"
NETFOUND_MODEL="$D0_ROOT/payload/vendor/netFound-base"
VENDOR_PY="$D0_ROOT/payload/vendor_py"

RUN154917="$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917"
PREDICTIONS="$BASE/runs/issue27ckbw_tail_margin_dual_control_v1_2026-08-03_seed27_amd_157624/ckbw_record_predictions.csv.gz"
SNAPSHOT="$BASE/runs/issue27ckby_drocc_feature_dump_v1_2026-08-07_seed27_amd_157930/ckby_drocc_feature_snapshot_seed27.npz"
D0_RESULT="$BASE/runs/issue27ckda_d0_representation_compatibility_audit_v1_2026-08-11_amd_158210"
D0_MANIFEST="$D0_RESULT/ckda_d0_fit_prefix_manifest.csv"
D0_CHECKPOINT="$BASE/runs/issue27ckda_d0_census_checkpoint_v1_amd_9184cd018efcc654/source_checkpoints"
GOTHAM_MANIFEST="$RUN154917/ckbu_gotham_unified_causal_manifest.csv"
AUXILIARY_MANIFEST="$RUN154917/ckbu_auxiliary_unified_causal_manifest.csv"
GOTHAM_ALLOWLIST="$PAYLOAD/runs/mainline_docs/ckcz_gotham_source_allowlist_20260809.csv"
AUXILIARY_ALLOWLIST="$PAYLOAD/runs/mainline_docs/ckcz_auxiliary_source_allowlist_20260809.csv"
GOTHAM_ZIP="$DATA_ROOT/gotham2025/raw/GothamDataset2025.zip"
TON_ROOT="$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1"

RUN_NAME="issue27ckda_d1_representation_probe_v1_2026-08-12_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"
STAGE_ROOT="$BASE/runs/.${RUN_NAME}.stage"
CONTROL_ROOT="$BASE/runs/${RUN_NAME}_control"
CHECKPOINT_ROOT="$BASE/runs/issue27ckda_d1_checkpoint_v1_${PARTITION}_ecb429926507d2c4"
PULLBACK="$BASE/runs/${RUN_NAME}_pullback.tar.gz"
PHASE=startup
heartbeat_pid=""
active_pid=""

write_phase() {
  PHASE=$1
  printf 'phase=%s\nupdated_utc=%s\n' "$PHASE" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$CONTROL_ROOT/current_phase.txt"
}

cleanup() {
  status=$?
  test -z "$active_pid" || kill "$active_pid" >/dev/null 2>&1 || true
  test -z "$heartbeat_pid" || kill "$heartbeat_pid" >/dev/null 2>&1 || true
  wait >/dev/null 2>&1 || true
  if test "$status" -ne 0; then
    printf 'status=FAILED\nphase=%s\nexit_code=%s\nfailed_utc=%s\n' \
      "$PHASE" "$status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$CONTROL_ROOT/job_failure.txt"
    printf '{"status":"CKDA_D1_ENGINEERING_FAILURE","phase":"%s","exit_code":%s,"scientific_verdict":null}\n' \
      "$PHASE" "$status" > "$CONTROL_ROOT/engineering_failure.json"
  fi
  exit "$status"
}
trap cleanup EXIT

completed_units() {
  find "$CHECKPOINT_ROOT" -maxdepth 3 -type f \( -name '*.npz' -o -name '*.json' \) 2>/dev/null | wc -l
}

heartbeat() {
  while true; do
    sleep 60
    printf 'CKDA_D1_PROGRESS utc=%s phase=%s job=%s completed_units=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$PHASE" "$JOB_ID" "$(completed_units)"
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
  last_units=$(completed_units)
  last_change=$(date +%s)
  while kill -0 "$active_pid" >/dev/null 2>&1; do
    sleep 60
    size=$(stat -c %s "$log" 2>/dev/null || echo 0)
    units=$(completed_units)
    if test "$size" -ne "$last_size" || test "$units" -ne "$last_units"; then
      last_size=$size
      last_units=$units
      last_change=$(date +%s)
    fi
    age=$(( $(date +%s) - last_change ))
    printf 'CKDA_D1_UNIT_PROGRESS phase=%s log_bytes=%s completed_units=%s silence_seconds=%s\n' \
      "$name" "$size" "$units" "$age"
    if test "$age" -ge "$stall_seconds"; then
      echo "CKDA_D1_NO_VALIDATED_PROGRESS phase=$name silence_seconds=$age" >&2
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
  test "$status" -eq 0 || { tail -120 "$log" >&2 || true; return "$status"; }
  tail -50 "$log" || true
}

for path in \
  "$BASE/scripts/00_env_issue27ckc.sh" "$CONTRACT" "$CORE" "$ROLE_PLAN" "$CENSUS" \
  "$TARGET_METADATA" "$E3_EMBED" "$PROBE" "$METRICS" "$VALIDATOR" "$CKBU" "$CKCZ" \
  "$D0_AUDIT" "$D0_PILOT" "$PREDICTIONS" "$SNAPSHOT" "$D0_MANIFEST" \
  "$GOTHAM_MANIFEST" "$AUXILIARY_MANIFEST" "$GOTHAM_ALLOWLIST" "$AUXILIARY_ALLOWLIST" \
  "$GOTHAM_ZIP" "$NETFOUND_SOURCE/PY39_COMPAT_AUDIT.json" "$NETFOUND_MODEL/config.json" \
  "$NETFOUND_MODEL/model.safetensors"; do
  test -s "$path" || { echo "missing immutable CKDA D1 input: $path" >&2; exit 2; }
done
for directory in "$RUN154917/gotham_causal_cache" "$RUN154917/auxiliary_causal_cache" "$TON_ROOT" "$VENDOR_PY"; do
  test -d "$directory" || { echo "missing immutable CKDA D1 directory: $directory" >&2; exit 2; }
done
test ! -e "$RUN_ROOT" || { echo "refusing mixed D1 result root" >&2; exit 2; }
test ! -e "$STAGE_ROOT" || { echo "refusing stale D1 stage root" >&2; exit 2; }
test ! -e "$CONTROL_ROOT" || { echo "refusing stale D1 control root" >&2; exit 2; }
test ! -e "$PULLBACK" || { echo "refusing stale D1 pullback" >&2; exit 2; }
mkdir -p "$STAGE_ROOT" "$CONTROL_ROOT" "$CHECKPOINT_ROOT/e3_fit_select" "$CHECKPOINT_ROOT/e3_report"
printf 'job_id=%s\npartition=%s\ncommit_sha=%s\nbundle_root=%s\nstarted_utc=%s\n' \
  "$JOB_ID" "$PARTITION" "$COMMIT_SHA" "$BUNDLE_ROOT" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$CONTROL_ROOT/slurm_identity.txt"
write_phase startup
heartbeat & heartbeat_pid=$!

cd "$BASE"
source scripts/00_env_issue27ckc.sh
module load apps/tshark/4.6.6
PCAP_LIB_DIR=/share/software/CST/installed/MCR/bin/glnxa64
test -s "$PCAP_LIB_DIR/libpcap.so.1"
export LD_LIBRARY_PATH="$PCAP_LIB_DIR:${LD_LIBRARY_PATH:-}"
TSHARK=$(command -v tshark)
test "$(ldd "$TSHARK" | awk '$1 == "libpcap.so.1" {print $3}')" = "$PCAP_LIB_DIR/libpcap.so.1"
export PYTHONPATH="$VENDOR_PY:$OOD:$D0_ROOT/payload/repo/ood${PYTHONPATH:+:$PYTHONPATH}"
export TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export OPENBLAS_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}

write_phase compute_contract_gates
(cd "$BUNDLE_ROOT" && sha256sum -c SHA256SUMS)
test "$(sha256sum "$CONTRACT" | awk '{print $1}')" = ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9
test "$(sha256sum "$PREDICTIONS" | awk '{print $1}')" = d1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85
test "$(sha256sum "$SNAPSHOT" | awk '{print $1}')" = b2ef1f7d0244cc7abb8665c25364744f794190f411482e4e202e346cb850279c
test "$(sha256sum "$D0_MANIFEST" | awk '{print $1}')" = 9184cd018efcc6547832bf04ce6d3046c687b8e48cac73234482d9fb3ba89689
test "$(sha256sum "$NETFOUND_MODEL/model.safetensors" | awk '{print $1}')" = e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105
python "$CORE" --python39-gate "$OOD"/*.py "$D0_AUDIT" "$D0_PILOT" "$NETFOUND_SOURCE"/src/modules/netFoundModels.py
python -m unittest -v test_issue27ckda_d1_representation_probe_v1
python "$VALIDATOR" contract-test
python - <<'PY'
import numpy, pandas, sklearn, torch, transformers
assert tuple(map(int, __import__('sys').version_info[:2])) == (3, 9)
print("CKDA_D1_COMPUTE_ENV_PASS", torch.__version__, transformers.__version__)
PY

write_phase fit_select_role_plan
python "$ROLE_PLAN" --scope fit-select --contract "$CONTRACT" --snapshot "$SNAPSHOT" --out "$STAGE_ROOT"
FIT_PLAN="$STAGE_ROOT/ckda_d1_fit_select_plan.csv"
FIT_SHA=$(sha256sum "$FIT_PLAN" | awk '{print $1}')
mv "$STAGE_ROOT/ckda_d1_role_plan_audit.json" "$STAGE_ROOT/ckda_d1_fit_select_role_plan_audit.json"

write_phase benign_only_i1_census
run_guarded benign_only_i1_census 1200 "$CONTROL_ROOT/census.log" \
  python -u "$CENSUS" --contract "$CONTRACT" --fit-prefix-manifest "$D0_MANIFEST" \
    --d0-checkpoint-dir "$D0_CHECKPOINT" --d0-audit "$D0_AUDIT" --ckbu-decoder "$CKBU" \
    --tshark "$TSHARK" --out "$STAGE_ROOT"

python - "$STAGE_ROOT/ckda_d1_benign_census.json" "$STAGE_ROOT/ckda_d1_candidate_progression.json" <<'PY'
import json, sys
source, target = sys.argv[1:]
value = json.load(open(source, encoding="utf-8"))
gate = value["gate"]
if gate["passed"]:
    raise RuntimeError("I1 benign gate passed despite the frozen visible-packet upper-bound contradiction")
report = {
    "contract_sha256": "ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9",
    "e3_open_reason": "I1_PRIMARY_PRECONDITION_FAILED",
    "e3_opened": True,
    "final_files_opened": 0,
    "i1_embeddings_generated": 0,
    "i1_training_started": False,
    "primary": "I1",
    "selected_candidate": "E3",
    "status": "CKDA_D1_FROZEN_PROGRESSION_PASS",
}
with open(target, "w", encoding="utf-8", newline="\n") as handle:
    json.dump(report, handle, indent=2, sort_keys=True); handle.write("\n")
print("CKDA_D1_I1_PRECONDITION_FAIL_CLEAN_E3_AUTHORIZED")
PY

write_phase fit_select_target_metadata
python "$TARGET_METADATA" --scope fit-select --contract "$CONTRACT" --plan "$FIT_PLAN" \
  --ckbv-root "$RUN154917" --gotham-manifest "$GOTHAM_MANIFEST" --auxiliary-manifest "$AUXILIARY_MANIFEST" \
  --gotham-allowlist "$GOTHAM_ALLOWLIST" --auxiliary-allowlist "$AUXILIARY_ALLOWLIST" \
  --ton-pcap-root "$TON_ROOT" --gotham-zip "$GOTHAM_ZIP" --out "$STAGE_ROOT/ckda_d1_fit_select_target_metadata.csv"

write_phase e3_fit_select_embeddings
run_guarded e3_fit_select_embeddings 1200 "$CONTROL_ROOT/e3_fit_select.log" \
  python -u "$E3_EMBED" --contract "$CONTRACT" --target-metadata "$STAGE_ROOT/ckda_d1_fit_select_target_metadata.csv" \
    --plan-sha256 "$FIT_SHA" --netfound-source "$NETFOUND_SOURCE" --netfound-checkpoint "$NETFOUND_MODEL" \
    --ckbu-decoder "$CKBU" --d0-pilot "$D0_PILOT" --tshark "$TSHARK" --device cpu --batch-size 16 \
    --checkpoint-dir "$CHECKPOINT_ROOT/e3_fit_select" --out "$STAGE_ROOT/ckda_d1_fit_select_embeddings.npz"

write_phase fit_probes_and_freeze_thresholds
run_guarded fit_probes_and_freeze_thresholds 1200 "$CONTROL_ROOT/probe_fit.log" \
  python -u "$PROBE" --scope fit-select --contract "$CONTRACT" --candidate E3 --plan "$FIT_PLAN" \
    --embeddings "$STAGE_ROOT/ckda_d1_fit_select_embeddings.npz" --out "$STAGE_ROOT"
MARKER="$STAGE_ROOT/ckda_d1_threshold_freeze_marker.json"

write_phase report_role_plan_after_freeze
python "$ROLE_PLAN" --scope report --contract "$CONTRACT" --snapshot "$SNAPSHOT" --predictions "$PREDICTIONS" \
  --threshold-marker "$MARKER" --out "$STAGE_ROOT"
REPORT_PLAN="$STAGE_ROOT/ckda_d1_report_plan.csv"
REPORT_SHA=$(sha256sum "$REPORT_PLAN" | awk '{print $1}')
mv "$STAGE_ROOT/ckda_d1_role_plan_audit.json" "$STAGE_ROOT/ckda_d1_report_role_plan_audit.json"

write_phase report_target_metadata_after_freeze
python "$TARGET_METADATA" --scope report --contract "$CONTRACT" --plan "$REPORT_PLAN" --threshold-marker "$MARKER" \
  --fit-select-plan-sha256 "$FIT_SHA" --ckbv-root "$RUN154917" --gotham-manifest "$GOTHAM_MANIFEST" \
  --auxiliary-manifest "$AUXILIARY_MANIFEST" --gotham-allowlist "$GOTHAM_ALLOWLIST" \
  --auxiliary-allowlist "$AUXILIARY_ALLOWLIST" --ton-pcap-root "$TON_ROOT" --gotham-zip "$GOTHAM_ZIP" \
  --out "$STAGE_ROOT/ckda_d1_report_target_metadata.csv"

write_phase e3_one_shot_report_embeddings
run_guarded e3_one_shot_report_embeddings 1200 "$CONTROL_ROOT/e3_report.log" \
  python -u "$E3_EMBED" --contract "$CONTRACT" --target-metadata "$STAGE_ROOT/ckda_d1_report_target_metadata.csv" \
    --plan-sha256 "$REPORT_SHA" --netfound-source "$NETFOUND_SOURCE" --netfound-checkpoint "$NETFOUND_MODEL" \
    --ckbu-decoder "$CKBU" --d0-pilot "$D0_PILOT" --tshark "$TSHARK" --device cpu --batch-size 16 \
    --checkpoint-dir "$CHECKPOINT_ROOT/e3_report" --out "$STAGE_ROOT/ckda_d1_report_embeddings.npz"

write_phase frozen_report_scoring
run_guarded frozen_report_scoring 1200 "$CONTROL_ROOT/report_score.log" \
  python -u "$PROBE" --scope report --contract "$CONTRACT" --candidate E3 --plan "$REPORT_PLAN" \
    --embeddings "$STAGE_ROOT/ckda_d1_report_embeddings.npz" --state "$STAGE_ROOT/ckda_d1_probe_state.npz" \
    --marker "$MARKER" --out "$STAGE_ROOT"

write_phase metrics_bootstrap_and_state
run_guarded metrics_bootstrap_and_state 1200 "$CONTROL_ROOT/metrics.log" \
  python -u "$METRICS" --contract "$CONTRACT" --candidate E3 --scores "$STAGE_ROOT/ckda_d1_report_scores.csv.gz" \
    --metadata "$STAGE_ROOT/ckda_d1_report_embeddings.npz.metadata.csv.gz" --out "$STAGE_ROOT"

write_phase validate_result
python "$VALIDATOR" --result "$STAGE_ROOT" --contract "$CONTRACT" > "$CONTROL_ROOT/validation.log" 2>&1
cat "$CONTROL_ROOT/validation.log"
cp "$CONTROL_ROOT/current_phase.txt" "$STAGE_ROOT/last_precomplete_phase.txt"
mv "$STAGE_ROOT" "$RUN_ROOT"

write_phase package_pullback
PULLBACK_TMP="${PULLBACK}.tmp.${JOB_ID}"
tar -czf "$PULLBACK_TMP" -C "$RUN_ROOT" -T "$RUN_ROOT/PULLBACK_ALLOWLIST.txt"
mv "$PULLBACK_TMP" "$PULLBACK"
printf '%s  %s\n' "$(sha256sum "$PULLBACK" | awk '{print $1}')" "$(basename "$PULLBACK")" > "$PULLBACK.sha256"

write_phase complete
printf 'status=PASS\njob_id=%s\npartition=%s\ncommit_sha=%s\nrun_root=%s\npullback=%s\ncompleted_utc=%s\n' \
  "$JOB_ID" "$PARTITION" "$COMMIT_SHA" "$RUN_ROOT" "$PULLBACK" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  > "$CONTROL_ROOT/terminal_success.txt"
echo "CKDA_D1_COMPLETE job=$JOB_ID pullback=$PULLBACK"
