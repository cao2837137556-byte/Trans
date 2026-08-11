#!/usr/bin/env bash
# Run from the extracted CKDA D0 bundle on the logged-in HPC terminal.
set -euo pipefail

HERE=$(cd "$(dirname "$0")/../.." && pwd)
BASE=${CKDA_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
DATA_ROOT=${CKDA_DATA_ROOT:-/public/home/jiangxinwei.zr/work/paper04/datasets}
PAYLOAD="$HERE/payload"
SLURM="$PAYLOAD/scripts/issue27ckda_d0_representation_compatibility_audit_formal.slurm"
STATUS="$PAYLOAD/scripts/issue27ckda_d0_status.sh"
COMMIT_SHA=$(tr -d '\r\n' < "$HERE/bundle_commit.txt")
JOB_FILE="$HERE/ckda_d0_amd_job_id.txt"
RUN154917="$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917"
C1_ROOT="$BASE/runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"

test "${CKDA_D0_SUBMIT_AUTHORIZATION:-NO}" = YES || {
  echo "CKDA D0 submission is not authorized; export CKDA_D0_SUBMIT_AUTHORIZATION=YES" >&2
  exit 3
}
test -d "$BASE" || { echo "missing experiment root: $BASE" >&2; exit 2; }
test -s "$BASE/scripts/00_env_issue27ckc.sh" || { echo "missing allowed project environment" >&2; exit 2; }
test -s "$HERE/SHA256SUMS" || { echo "bundle SHA256SUMS missing" >&2; exit 2; }

echo "=== CKDA D0 exact bundle SHA-256 ==="
(cd "$HERE" && sha256sum -c SHA256SUMS)
while IFS= read -r relative; do
  test -n "$relative" || continue
  case "$relative" in
    *.py|*.sh|*.slurm|*.md|*.txt|*.csv|*.json|SHA256SUMS)
      if LC_ALL=C grep -q $'\r' "$HERE/$relative"; then
        echo "bundle text file is not LF-only: $relative" >&2
        exit 2
      fi
      ;;
  esac
done < <(awk '{print $2}' "$HERE/SHA256SUMS")

for path in \
  "$SLURM" "$STATUS" \
  "$PAYLOAD/repo/ood/issue27ckda_d0_representation_compatibility_audit_v1.py" \
  "$PAYLOAD/repo/ood/issue27ckda_d0_resource_pilot_v1.py" \
  "$PAYLOAD/repo/ood/issue27ckda_d0_validate_and_pack_v1.py" \
  "$PAYLOAD/repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py" \
  "$PAYLOAD/vendor/netFound-base/config.json" \
  "$PAYLOAD/vendor/netFound-base/model.safetensors" \
  "$RUN154917/ckbu_gotham_source_plan.csv" \
  "$RUN154917/ckbu_auxiliary_source_plan.csv" \
  "$RUN154917/ckbu_ton_raw_pcap_materialization_audit.csv" \
  "$C1_ROOT/canonical_source_target_index.csv" \
  "$DATA_ROOT/gotham2025/raw/GothamDataset2025.zip"; do
  test -s "$path" || { echo "missing immutable CKDA D0 input: $path" >&2; exit 2; }
done
for directory in \
  "$RUN154917/gotham_causal_cache" \
  "$DATA_ROOT/external/ton_iot_raw_network/raw_pcap_pilot_v1" \
  "$PAYLOAD/vendor_py"; do
  test -d "$directory" || { echo "missing CKDA D0 input directory: $directory" >&2; exit 2; }
done

for pair in \
  "$C1_ROOT/canonical_source_target_index.csv:74a1699e29b7b1e227f4532ff81f1546a9ba239f2d2d323d390efa5b07437158" \
  "$RUN154917/ckbu_gotham_source_plan.csv:79cf8f92df2d4d3eec9ceafd8279413a75c0e323e9af0518db269ad4a45e91d3" \
  "$RUN154917/ckbu_auxiliary_source_plan.csv:28a485932ba0f7e637b79ebd77b7c397c1fabaa5107790616aa559ea1aba719b" \
  "$RUN154917/ckbu_ton_raw_pcap_materialization_audit.csv:1d4b29ef694263a8a60760685f4a7fcd0eebadf77d452b1b591116cba17e90bf" \
  "$PAYLOAD/vendor/netFound-base/config.json:e22262d4b840a0055915f6c48e9c64d04e790f80e907fa9dc06df855eff05401" \
  "$PAYLOAD/vendor/netFound-base/model.safetensors:e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105"; do
  asset=${pair%%:*}
  expected=${pair#*:}
  test "$(sha256sum "$asset" | awk '{print $1}')" = "$expected" || {
    echo "immutable CKDA D0 asset drift: $asset" >&2; exit 2;
  }
done
test "$(stat -c %s "$PAYLOAD/vendor/netFound-base/model.safetensors")" = 698780900
test "$(stat -c %s "$DATA_ROOT/gotham2025/raw/GothamDataset2025.zip")" = 23824968355

source "$BASE/scripts/00_env_issue27ckc.sh"
export PYTHONPATH="$PAYLOAD/vendor_py:$PAYLOAD/repo/ood${PYTHONPATH:+:$PYTHONPATH}"
export TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1
python -m py_compile \
  "$PAYLOAD/repo/ood/issue27ckda_d0_representation_compatibility_audit_v1.py" \
  "$PAYLOAD/repo/ood/issue27ckda_d0_resource_pilot_v1.py" \
  "$PAYLOAD/repo/ood/issue27ckda_d0_validate_and_pack_v1.py"
bash -n "$SLURM"
bash -n "$STATUS"
python "$PAYLOAD/repo/ood/issue27ckda_d0_representation_compatibility_audit_v1.py" contract-test
python "$PAYLOAD/repo/ood/issue27ckda_d0_resource_pilot_v1.py" contract-test
python - <<'PY'
import psutil, safetensors, tokenizers, transformers
print("CKDA_D0_LOGIN_DEPENDENCY_GATE_PASS", transformers.__version__, safetensors.__version__, tokenizers.__version__, psutil.__version__)
PY

if test -s "$JOB_FILE"; then
  old_job=$(tr -dc '0-9' < "$JOB_FILE")
  old_state=$(sacct -j "$old_job" -X -n -P --format=State 2>/dev/null | head -n 1 | cut -d'|' -f1 | sed 's/+.*//' | tr -d '[:space:]')
  case "$old_state" in
    PENDING|RUNNING|COMPLETED)
      echo "refusing duplicate CKDA D0 submission: job=$old_job state=$old_state" >&2
      exit 4
      ;;
  esac
fi

export_spec="ALL,CKDA_BUNDLE_ROOT=$HERE,CKDA_COMMIT_SHA=$COMMIT_SHA,CKDA_BASE=$BASE,CKDA_DATA_ROOT=$DATA_ROOT"
echo "=== CKDA D0 Slurm scheduler dry validation ==="
sbatch --test-only -p amd --export="$export_spec" "$SLURM"

echo "=== CKDA D0 submit complete result-producing chain ==="
job_id=$(sbatch --parsable -p amd \
  --output="$BASE/runs/issue27ckda_d0_amd_%j.out" \
  --error="$BASE/runs/issue27ckda_d0_amd_%j.err" \
  --export="$export_spec" \
  "$SLURM")
printf '%s\n' "$job_id" > "$JOB_FILE"
printf 'job_id=%s\npartition=amd\ncommit_sha=%s\nbundle_root=%s\nsubmitted_utc=%s\n' \
  "$job_id" "$COMMIT_SHA" "$HERE" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  > "$HERE/ckda_d0_submission_record.txt"
echo "CKDA_D0_JOB_ID=$job_id"
echo "CKDA_D0_SUBMISSION_RECORDED"
echo "Monitor with: bash $STATUS $job_id"
