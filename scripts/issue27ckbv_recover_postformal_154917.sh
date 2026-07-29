#!/bin/bash
set -euo pipefail

# Metadata-only recovery for the already-computed AMD seed-27 result.
# This script never submits a job, trains a model, or decodes a PCAP.

BASE=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline
DATA_ROOT=/public/home/jiangxinwei.zr/work/paper04/datasets
SOURCE_JOB_ID=154917
SOURCE_PARTITION=amd
RUN_ROOT="$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_${SOURCE_PARTITION}_${SOURCE_JOB_ID}"
R16_ROOT=/public/home/jiangxinwei.zr/work/paper04/m1_transfer/issue27ckbv_checkpointed_process_seed27_dual_20260728_r16/issue27ckbv_checkpointed_process_seed27_dual_20260728_r16
R16_CODE_ROOT="$R16_ROOT/payload/repo/ood"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PAYLOAD_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
RECOVERY_PY="$PAYLOAD_ROOT/repo/ood/issue27ckbv_postformal_recovery_v1.py"
VALIDATOR="$SCRIPT_DIR/issue27ckbv_validate_and_pack_seed27.sh"

test -d "$RUN_ROOT" || {
  echo "missing completed AMD run root: $RUN_ROOT" >&2
  exit 2
}
test -s "$RUN_ROOT/ckbu_single_seed_go_no_go.json" || {
  echo "missing completed scientific decision: $RUN_ROOT" >&2
  exit 2
}
grep -Fxq 'phase=validate_and_pack' "$RUN_ROOT/job_failure.txt" || {
  echo "refusing recovery: source failure was not validate_and_pack" >&2
  exit 2
}
test -s "$RECOVERY_PY" || {
  echo "missing recovery program: $RECOVERY_PY" >&2
  exit 2
}
test -s "$VALIDATOR" || {
  echo "missing corrected validator: $VALIDATOR" >&2
  exit 2
}
test -s "$R16_CODE_ROOT/issue27ckbv_checkpointed_sparse_process_frontend_v1.py" || {
  echo "missing immutable r16 validator code root: $R16_CODE_ROOT" >&2
  exit 2
}
test -s "$R16_ROOT/payload/runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/manifest.csv" || {
  echo "missing immutable r16 CKBT validation payload" >&2
  exit 2
}

state=$(
  sacct -j "$SOURCE_JOB_ID" -X -n -P --format=State |
    head -n 1 |
    cut -d'|' -f1 |
    sed 's/+.*//' |
    tr -d '[:space:]'
)
test "$state" = FAILED || {
  echo "source job must remain FAILED for post-formal recovery; got: $state" >&2
  exit 2
}

source "$BASE/scripts/00_env_issue27ckc.sh"

python -m py_compile "$RECOVERY_PY"
python "$RECOVERY_PY" \
  --mode recover \
  --run-root "$RUN_ROOT" \
  --source-job-id "$SOURCE_JOB_ID" \
  --source-partition "$SOURCE_PARTITION"

COMMIT_SHA=$(
  awk -F= '$1 == "commit_sha" {print $2; exit}' "$RUN_ROOT/slurm_identity.txt"
)
test -n "$COMMIT_SHA" || {
  echo "missing original run commit SHA" >&2
  exit 2
}

CKBV_BASE="$BASE" \
CKBV_DATA_ROOT="$DATA_ROOT" \
CKBV_PARTITION="$SOURCE_PARTITION" \
CKBV_JOB_ID="$SOURCE_JOB_ID" \
CKBV_ALLOW_POSTFORMAL_FAILED=1 \
CKBV_CODE_ROOT="$R16_CODE_ROOT" \
CKBV_COMMIT_SHA="$COMMIT_SHA" \
bash "$VALIDATOR"

echo '=== recovered scientific decision (unchanged) ==='
cat "$RUN_ROOT/ckbu_single_seed_go_no_go.json"
echo '=== recovery validation ==='
cat "$RUN_ROOT/ckbv_result_validation.json"
echo "CKBV_POSTFORMAL_RECOVERY_COMPLETE job=$SOURCE_JOB_ID partition=$SOURCE_PARTITION"
