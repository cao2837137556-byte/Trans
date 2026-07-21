#!/bin/bash
set -euo pipefail

BASE=${CKBQ_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
JOB_ID=153037
PARTITION=amd
RUN_NAME="issue27ckbq_causal_minirocket_consensus_v1_2026-07-17_seed27_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"
STDOUT="$BASE/runs/issue27ckbq_${PARTITION}_${JOB_ID}.out"
STDERR="$BASE/runs/issue27ckbq_${PARTITION}_${JOB_ID}.err"
BUNDLE_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PAYLOAD_VALIDATOR="$BUNDLE_ROOT/payload/scripts/issue27ckbq_validate_and_pack_seed27.sh"
REMOTE_VALIDATOR="$BASE/scripts/issue27ckbq_validate_and_pack_seed27.sh"
OLD_VALIDATOR_SHA256=4e42712562a8aae6c3c3ec59cc34c20d3541d10064b231230cfeca8f3fb648d6
NEW_VALIDATOR_SHA256=08b251b3d8cc3461b89eac79786a01df39a277debed2dad5fd87905bad3a3509

test -s "$BASE/scripts/00_env_issue27ckc.sh"
test -d "$RUN_ROOT"
test -s "$RUN_ROOT/ckbq_single_seed_go_no_go.json"
test -s "$RUN_ROOT/ckbq_aux_temporal_manifest.csv"
test -s "$RUN_ROOT/ckbo_auxiliary_benign_manifest.csv"
test -s "$STDOUT"
test -s "$STDERR"
test -s "$PAYLOAD_VALIDATOR"

state=$(sacct -j "$JOB_ID" -X -n -P --format=State | head -n 1 | cut -d'|' -f1 | sed 's/+.*//' | tr -d '[:space:]')
exit_code=$(sacct -j "$JOB_ID" -X -n -P --format=ExitCode | head -n 1 | cut -d'|' -f1 | tr -d '[:space:]')
partition=$(sacct -j "$JOB_ID" -X -n -P --format=Partition | head -n 1 | cut -d'|' -f1 | tr -d '[:space:]')
test "$state" = "FAILED" || { echo "unexpected job state: $state" >&2; exit 2; }
test "$exit_code" = "1:0" || { echo "unexpected job exit code: $exit_code" >&2; exit 2; }
test "$partition" = "$PARTITION" || { echo "unexpected job partition: $partition" >&2; exit 2; }
grep -Fq '"status": "CKBQ_FORMAL_COMPLETE"' "$STDOUT" || {
  echo "formal program did not report completion" >&2
  exit 2
}
grep -Fq 'auxiliary temporal causality/schema contract failed' "$STDERR" || {
  echo "known stale validator error not found" >&2
  exit 2
}
if grep -Fq 'Traceback (most recent call last)' "$STDERR"; then
  echo "unexpected Python traceback exists in formal stderr" >&2
  exit 2
fi

payload_sha=$(sha256sum "$PAYLOAD_VALIDATOR" | awk '{print $1}')
test "$payload_sha" = "$NEW_VALIDATOR_SHA256" || {
  echo "unexpected corrected validator payload SHA-256: $payload_sha" >&2
  exit 2
}
remote_sha=$(sha256sum "$REMOTE_VALIDATOR" | awk '{print $1}')
case "$remote_sha" in
  "$OLD_VALIDATOR_SHA256")
    install -m 0644 "$PAYLOAD_VALIDATOR" "$REMOTE_VALIDATOR"
    ;;
  "$NEW_VALIDATOR_SHA256")
    ;;
  *)
    echo "remote validator differs from known r3 and corrected content: $remote_sha" >&2
    exit 2
    ;;
esac
test "$(sha256sum "$REMOTE_VALIDATOR" | awk '{print $1}')" = "$NEW_VALIDATOR_SHA256"

source "$BASE/scripts/00_env_issue27ckc.sh"
python - "$RUN_ROOT" "$state" "$exit_code" <<'PY'
import csv
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
with (root / "ckbo_auxiliary_benign_manifest.csv").open(newline="", encoding="utf-8") as handle:
    frozen = list(csv.DictReader(handle))
with (root / "ckbq_aux_temporal_manifest.csv").open(newline="", encoding="utf-8") as handle:
    temporal = list(csv.DictReader(handle))

assert len(frozen) == len(temporal) == 31
assert {int(float(row["warmup_packets"])) for row in frozen} == {500}
assert {int(float(row["model_ready_rows"])) for row in frozen} == {600}
assert {int(float(row["events"])) for row in temporal} == {1100}
assert {int(float(row["target_offset"])) for row in temporal} == {500}
assert {int(float(row["target_rows"])) for row in temporal} == {600}

payload = {
    "status": "CKBQ_POST_FORMAL_VALIDATOR_RECOVERY",
    "models_retrained": False,
    "scores_or_gates_changed": False,
    "job_id": 153037,
    "partition": "amd",
    "original_slurm_state": sys.argv[2],
    "original_exit_code": sys.argv[3],
    "formal_program_complete": True,
    "terminal_failure": "stale auxiliary warm-up validator expected 256 instead of frozen CKBO 500",
    "auxiliary_sources": 31,
    "warmup_packets": 500,
    "target_rows_per_source": 600,
    "events_per_source": 1100,
}
(root / "ckbq_validation_recovery.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(json.dumps(payload, indent=2, sort_keys=True))
PY

CKBQ_BASE="$BASE" CKBQ_PARTITION="$PARTITION" CKBQ_JOB_ID="$JOB_ID" CKBQ_ALLOW_RUNNING=1 \
  bash "$REMOTE_VALIDATOR"

ARCHIVE="$BASE/runs/issue27ckbq_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"
test -s "$ARCHIVE"
test -s "$ARCHIVE.sha256"
cd "$BASE/runs"
sha256sum -c "$(basename "$ARCHIVE").sha256"
echo "CKBQ_RECOVERED_PULLBACK=$ARCHIVE"
