#!/usr/bin/env bash
# Recover only the post-result validation/package tail of CKDA D0 job 158210.
# The failed Slurm job and its original stage are preserved unchanged.
set -euo pipefail

HERE=$(cd "$(dirname "$0")/../.." && pwd)
BASE=${CKDA_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
R2_ROOT=${CKDA_R2_ROOT:-/public/home/jiangxinwei.zr/work/issue27ckda_d0_representation_compatibility_20260811_r2}
JOB=158210
PARTITION=amd
RUN_NAME="issue27ckda_d0_representation_compatibility_audit_v1_2026-08-11_${PARTITION}_${JOB}"
FAILED_STAGE="$BASE/runs/.${RUN_NAME}.stage"
RECOVERY_STAGE="$BASE/runs/.${RUN_NAME}.tail_recovery.stage"
RUN_ROOT="$BASE/runs/$RUN_NAME"
CONTROL_ROOT="$BASE/runs/${RUN_NAME}_control"
PULLBACK="$BASE/runs/${RUN_NAME}_pullback.tar.gz"

VALIDATOR="$HERE/payload/repo/ood/issue27ckda_d0_validate_and_pack_v1.py"
AUDIT="$R2_ROOT/payload/repo/ood/issue27ckda_d0_representation_compatibility_audit_v1.py"
PILOT="$R2_ROOT/payload/repo/ood/issue27ckda_d0_resource_pilot_v1.py"
CONTRACT="$R2_ROOT/payload/runs/mainline_docs/ckda_d0_representation_compatibility_audit_preregistered_20260811.md"

test "${CKDA_D0_TAIL_RECOVERY_AUTHORIZATION:-NO}" = YES || {
  echo "CKDA D0 tail recovery is not authorized" >&2
  exit 3
}

for path in \
  "$HERE/SHA256SUMS" "$VALIDATOR" "$R2_ROOT/SHA256SUMS" \
  "$R2_ROOT/bundle_commit.txt" "$AUDIT" "$PILOT" "$CONTRACT" \
  "$CONTROL_ROOT/current_phase.txt" "$CONTROL_ROOT/job_failure.txt"; do
  test -s "$path" || { echo "missing immutable recovery input: $path" >&2; exit 2; }
done

(cd "$HERE" && sha256sum -c SHA256SUMS)
(cd "$R2_ROOT" && sha256sum -c SHA256SUMS)
test "$(tr -d '\r\n' < "$R2_ROOT/bundle_commit.txt")" = c4276bd3074dccb900c361d09772ae4bc97eb656
test "$(sha256sum "$CONTRACT" | awk '{print $1}')" = ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5

STATE=$(sacct -j "$JOB" -X -n -P --format=State | head -n 1 | cut -d'|' -f1 | sed 's/+.*//' | tr -d '[:space:]')
test "$STATE" = FAILED || { echo "job $JOB is not the frozen failed source: $STATE" >&2; exit 2; }
grep -Fxq 'phase=validate_and_finalize' "$CONTROL_ROOT/job_failure.txt"
grep -Fq "write_text() got an unexpected keyword argument 'newline'" "$CONTROL_ROOT/validation.log"

test -d "$FAILED_STAGE" || { echo "preserved failed stage is missing" >&2; exit 2; }
test -s "$FAILED_STAGE/engineering_failure.json" || { echo "preserved failure marker is missing" >&2; exit 2; }
test ! -e "$RECOVERY_STAGE" || { echo "refusing stale recovery stage" >&2; exit 2; }
test ! -e "$RUN_ROOT" || { echo "refusing existing result root" >&2; exit 2; }
test ! -e "$PULLBACK" || { echo "refusing existing pullback" >&2; exit 2; }
test ! -e "$PULLBACK.sha256" || { echo "refusing existing pullback sidecar" >&2; exit 2; }

python - "$FAILED_STAGE" <<'PY'
import csv
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
required = (
    "ckda_d0_candidate_audit.csv",
    "ckda_d0_data_census.json",
    "ckda_d0_evidence_manifest.csv",
    "ckda_d0_final_exclusion_audit.json",
    "ckda_d0_fit_prefix_manifest.csv",
    "ckda_d0_resource_pilot.csv",
    "ckda_d0_resource_pilot_measurements.json",
    "ckda_d0_verdict.json",
)
for name in required:
    path = root / name
    assert path.is_file() and path.stat().st_size > 0, name

sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
census = json.loads((root / "ckda_d0_data_census.json").read_text(encoding="utf-8"))
assert census["status"] == "CKDA_D0_DATA_CENSUS_COMPLETE"
assert census["i1_data_gate"] == "PASS"
assert census["i1_fit_sessions"] == 4_764_022
assert census["i1_fit_tokens"] == 11_705_453
assert census["source_checkpoint_manifest_sha256"] == "6e303e9fcd1e3140dda0861bb4f943a3970074cbda31d50769874b50821a7c9f"
assert census["final_files_opened"] == 0 and census["raw_label_columns_read"] == 0
assert sha(root / "ckda_d0_fit_prefix_manifest.csv") == "9184cd018efcc6547832bf04ce6d3046c687b8e48cac73234482d9fb3ba89689"

measurements = json.loads((root / "ckda_d0_resource_pilot_measurements.json").read_text(encoding="utf-8"))
assert measurements["status"] == "CKDA_D0_RESOURCE_PILOT_COMPLETE"
assert sorted(measurements["candidates"]) == ["E3", "I1"]
verdict = json.loads((root / "ckda_d0_verdict.json").read_text(encoding="utf-8"))
assert verdict["status"] == "CKDA_D0_PRIMARY_AND_OPTIONAL_BACKUP_FROZEN"
assert verdict["primary"] == "I1" and verdict["backup"] == "E3"
assert verdict["candidate_audit_sha256"] == sha(root / "ckda_d0_candidate_audit.csv")
assert verdict["final_files_opened"] == 0
assert verdict["labels_read"] == 0
assert verdict["performance_embeddings_generated"] == 0
exclusion = json.loads((root / "ckda_d0_final_exclusion_audit.json").read_text(encoding="utf-8"))
assert exclusion["status"] == "PASS" and exclusion["final_files_opened"] == 0
with (root / "ckda_d0_resource_pilot.csv").open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
assert [row["candidate_id"] for row in rows] == ["E3", "I1"]
assert all(row["status"] == "PASS" for row in rows)
print("CKDA_D0_PRESERVED_SCIENTIFIC_RESULTS_GATE_PASS")
PY

source "$BASE/scripts/00_env_issue27ckc.sh"
python -m py_compile "$VALIDATOR" "$AUDIT" "$PILOT"
python "$VALIDATOR" contract-test

mkdir "$RECOVERY_STAGE"
cp -a "$FAILED_STAGE/." "$RECOVERY_STAGE/"
mv "$RECOVERY_STAGE/engineering_failure.json" "$RECOVERY_STAGE/prior_engineering_failure_158210.txt"

VALIDATOR_SHA=$(sha256sum "$VALIDATOR" | awk '{print $1}')
PRIOR_FAILURE_SHA=$(sha256sum "$RECOVERY_STAGE/prior_engineering_failure_158210.txt" | awk '{print $1}')
export RUN_NAME STATE VALIDATOR_SHA PRIOR_FAILURE_SHA FAILED_STAGE
python - "$RECOVERY_STAGE/tail_recovery_lineage.json" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

value = {
    "status": "CKDA_D0_POST_RESULT_TAIL_RECOVERY",
    "original_job_id": 158210,
    "original_job_state": os.environ["STATE"],
    "original_failed_stage": os.environ["FAILED_STAGE"],
    "original_failure_phase": "validate_and_finalize",
    "original_failure_class": "POST_RESULT_VALIDATION_PACKAGING",
    "scientific_recomputation": False,
    "final_or_labels_reopened": False,
    "validator_sha256": os.environ["VALIDATOR_SHA"],
    "prior_engineering_failure_sha256": os.environ["PRIOR_FAILURE_SHA"],
    "recovered_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
Path(sys.argv[1]).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

python "$VALIDATOR" \
  --result "$RECOVERY_STAGE" \
  --contract "$CONTRACT" \
  --audit-module "$AUDIT" \
  --pilot-module "$PILOT" \
  > "$CONTROL_ROOT/tail_recovery_validation.log" 2>&1
cat "$CONTROL_ROOT/tail_recovery_validation.log"
cp "$CONTROL_ROOT/current_phase.txt" "$RECOVERY_STAGE/last_precomplete_phase.txt"

python - "$RECOVERY_STAGE/ckda_d0_validation_report.json" <<'PY'
import json
import sys
from pathlib import Path
report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert report["status"] == "PASS"
assert report["ranked_candidates"] == ["I1", "E3"]
assert report["resource_pilot_candidates"] == ["E3", "I1"]
assert report["final_files_opened"] == 0
assert report["labels_read"] == 0
assert report["performance_embeddings_persisted"] == 0
print("CKDA_D0_RECOVERED_VALIDATION_GATE_PASS")
PY

(
  cd "$RECOVERY_STAGE"
  find . -maxdepth 1 -type f ! -name TAIL_RECOVERY_SHA256SUMS -printf '%P\n' | LC_ALL=C sort |
    while IFS= read -r name; do sha256sum "$name"; done > TAIL_RECOVERY_SHA256SUMS
  sha256sum -c TAIL_RECOVERY_SHA256SUMS
)

mv "$RECOVERY_STAGE" "$RUN_ROOT"
PULLBACK_TMP="${PULLBACK}.tmp.tail_recovery.$$"
tar -czf "$PULLBACK_TMP" -C "$BASE/runs" "$RUN_NAME"
mv "$PULLBACK_TMP" "$PULLBACK"
printf '%s  %s\n' "$(sha256sum "$PULLBACK" | awk '{print $1}')" "$(basename "$PULLBACK")" > "$PULLBACK.sha256"
(
  cd "$BASE/runs"
  sha256sum -c "$(basename "$PULLBACK.sha256")"
)

printf 'status=PASS\nmode=POST_RESULT_TAIL_RECOVERY\noriginal_job_id=%s\noriginal_job_state=%s\nrun_root=%s\npullback=%s\nrecovered_utc=%s\n' \
  "$JOB" "$STATE" "$RUN_ROOT" "$PULLBACK" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  > "$CONTROL_ROOT/tail_recovery_success.txt"

echo "CKDA_D0_TAIL_RECOVERY_PASS original_job=$JOB original_state=$STATE validation=PASS"
echo "Pullback: $PULLBACK"
