#!/bin/bash
set -euo pipefail

BASE=${CKBL_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
PARTITION=${CKBL_PARTITION:?set CKBL_PARTITION to amd or intel}
JOB_ID=${CKBL_JOB_ID:?set CKBL_JOB_ID}
case "$PARTITION" in amd|intel) ;; *) echo "invalid partition: $PARTITION" >&2; exit 2 ;; esac
[[ "$JOB_ID" =~ ^[0-9]+$ ]] || { echo "invalid job id: $JOB_ID" >&2; exit 2; }

RUN_ROOT="$BASE/runs/issue27ckbl_frontend_observability_audit_v1_2026-07-14_fullsource_seed27_${PARTITION}_${JOB_ID}"
ARCHIVE="$BASE/runs/issue27ckbl_full_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"
SHA_FILE="$ARCHIVE.sha256"
test -d "$RUN_ROOT" || { echo "missing run root: $RUN_ROOT" >&2; exit 2; }

RUN_ROOT="$RUN_ROOT" PARTITION="$PARTITION" JOB_ID="$JOB_ID" python - <<'PY'
import csv, json, os
from pathlib import Path

root = Path(os.environ["RUN_ROOT"])
decision = json.loads((root / "decision.json").read_text(encoding="utf-8"))
spec = json.loads((root / "run_spec.json").read_text(encoding="utf-8"))
errors = []

def require(condition, message):
    if not condition:
        errors.append(message)

require(decision.get("formal_complete_protocol") is True, "formal_complete_protocol is not true")
require(decision.get("selected_rows") == 8671, "selected_rows != 8671")
require(decision.get("selected_attack_rows") == 385, "selected_attack_rows != 385")
require(decision.get("selected_benign_rows") == 8286, "selected_benign_rows != 8286")
require(decision.get("source_count") == 8, "source_count != 8")
require(decision.get("attack_family_count") == 10, "attack_family_count != 10")
require(all(value == 0 for value in decision.get("forbidden_family_model_use", {}).values()), "forbidden family use is nonzero")
require(spec.get("source_read_mode") == "full", "source_read_mode is not full")
require(spec.get("max_recorded_index") == 0, "max_recorded_index is not zero")
require(spec.get("max_folds") == 0, "max_folds is not zero")
require(spec.get("histgb_max_iter") == 80, "histgb_max_iter is not 80")
require(spec.get("seed") == 27, "seed is not 27")
require(spec.get("raw_label_column_read") is False, "raw_label_column_read is not false")
require(spec.get("review") == 0, "review is not zero")
require(spec.get("sealed_final_holdout_model_use_rows") == 0, "sealed final use is nonzero")
require(spec.get("known_nonselected_target_state_rows_blocked") == 198173, "known nonfit target block count != 198173")
require(len(spec.get("declared_commit_sha", "")) == 40, "declared commit SHA is invalid")

def rows(name):
    path = root / name
    if not path.exists():
        errors.append(f"missing output: {name}")
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))

alignment = rows("frontend_alignment_audit.csv")
require(len(alignment) == 8671, "alignment row count mismatch")
require(all(row.get("alignment_ok") == "True" for row in alignment), "alignment failure present")
require(all(row.get("raw_label_column_read") == "False" for row in alignment), "raw label read present")
require(all(row.get("state_update_allowed") == "True" for row in alignment), "selected target blocked from state")
folds = rows("fold_contract_audit.csv")
require(len(folds) == 25, "fold count != 25")
require(all(row.get("source_overlap") == "0" for row in folds), "outer source overlap present")
require(all(row.get("test_labels_used_for_fit_or_threshold") == "0" for row in folds), "outer label use present")
require(len(rows("fold_metrics.csv")) == 125, "fold metric count != 125")
require(len(rows("aggregate_metrics.csv")) == 10, "aggregate metric count != 10")
require(len(rows("frontend_source_runtime_audit.csv")) == 8, "source runtime count != 8")
memory_scope = rows("memory_target_scope_audit.csv")
require(sum(int(row.get("new_known_target_rows_blocked", -10**9)) for row in memory_scope) == 198173,
        "memory target scope block lineage != 198173")
require(sum(int(row.get("selected_fit_rows_seen", -10**9)) for row in memory_scope) == 8671,
        "memory target scope selected-fit lineage != 8671")
progress_path = root / "source_progress.jsonl"
progress_count = len(progress_path.read_text(encoding="utf-8").splitlines()) if progress_path.exists() else -1
require(progress_count == 8, "source progress count != 8")

result = {
    "status": "PASS" if not errors else "FAIL",
    "partition": os.environ["PARTITION"],
    "job_id": os.environ["JOB_ID"],
    "decision": decision.get("verdict"),
    "errors": errors,
}
(root / "formal_validation.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if errors:
    raise SystemExit("; ".join(errors))
print(json.dumps(result, indent=2, sort_keys=True))
PY

if test -e "$ARCHIVE" || test -e "$SHA_FILE"; then
  test -s "$ARCHIVE" && test -s "$SHA_FILE" || { echo "partial existing pullback archive" >&2; exit 2; }
  (cd "$(dirname "$ARCHIVE")" && sha256sum -c "$(basename "$SHA_FILE")")
  echo "existing validated archive retained: $ARCHIVE"
  exit 0
fi

tar -C "$(dirname "$RUN_ROOT")" -czf "$ARCHIVE" "$(basename "$RUN_ROOT")"
(cd "$(dirname "$ARCHIVE")" && sha256sum "$(basename "$ARCHIVE")" > "$(basename "$SHA_FILE")")
echo "CKBL_PULLBACK_ARCHIVE=$ARCHIVE"
cat "$SHA_FILE"
