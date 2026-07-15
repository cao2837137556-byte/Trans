#!/bin/bash
set -euo pipefail

BASE=${CKBN_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
PARTITION=${CKBN_PARTITION:?set CKBN_PARTITION to amd or intel}
JOB_ID=${CKBN_JOB_ID:?set CKBN_JOB_ID}
ALLOW_RUNNING=${CKBN_ALLOW_RUNNING:-0}

case "$PARTITION" in amd|intel) ;; *) echo "invalid partition: $PARTITION" >&2; exit 2;; esac
case "$JOB_ID" in ''|*[!0-9]*) echo "invalid job id: $JOB_ID" >&2; exit 2;; esac

RUN_NAME="issue27ckbn_stream_separability_diagnostic_v1_2026-07-15_fullsource_seed27_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"
ARCHIVE="$BASE/runs/issue27ckbn_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"

for file in run_spec.json decision.json summary.md report_family_zero_use_audit.csv \
  legal_oof_threshold_audit.csv score_distribution_summary.csv \
  canary_vs_attack_family_pairwise_metrics.csv future_attack_family_hard_recall.csv \
  frontend_alignment_audit.csv run_timing.txt slurm_identity.txt; do
  test -s "$RUN_ROOT/$file" || { echo "missing result file: $RUN_ROOT/$file" >&2; exit 2; }
done

python - "$RUN_ROOT" <<'PY'
import csv
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
spec = json.loads((root / "run_spec.json").read_text(encoding="utf-8"))
decision = json.loads((root / "decision.json").read_text(encoding="utf-8"))
errors = []
if spec.get("source_read_mode") != "full":
    errors.append("source_read_mode is not full")
if int(spec.get("support_train_rows", -1)) != 385:
    errors.append("support_train_rows != 385")
if spec.get("report_used_for_fit_threshold_normalization_or_feature_selection") is not False:
    errors.append("report entered model selection")
if spec.get("raw_label_column_read_by_frontend") is not False:
    errors.append("raw label column read")
if int(spec.get("review", -1)) != 0:
    errors.append("review != 0")
if decision.get("status") != "CKBN_DIAGNOSTIC_COMPLETE":
    errors.append("diagnostic status incomplete")
if decision.get("candidate_promoted") is not False:
    errors.append("diagnostic promoted a candidate")
allowed = {
    "TRANSFERABLE_RANK_SIGNAL_WITH_GATE_FAILURE",
    "CURRENT_FRONTEND_ENTANGLED_OR_INSUFFICIENT",
    "MIXED_FAMILY_DEPENDENT_SIGNAL",
}
if decision.get("primary_diagnosis") not in allowed:
    errors.append("unknown primary diagnosis")
with (root / "report_family_zero_use_audit.csv").open(newline="", encoding="utf-8") as handle:
    zero = list(csv.DictReader(handle))
if len(zero) != 3 or any(row.get("fit_rows_used") != "0" or row.get("threshold_rows_used") != "0" for row in zero):
    errors.append("report-family zero-use audit failed")
with (root / "legal_oof_threshold_audit.csv").open(newline="", encoding="utf-8") as handle:
    thresholds = list(csv.DictReader(handle))
if len(thresholds) != 4 or any(row.get("status") != "SELECTED_FROM_INNER_SOURCE_OOF" for row in thresholds):
    errors.append("legal source-OOF thresholds incomplete")
with (root / "canary_vs_attack_family_pairwise_metrics.csv").open(newline="", encoding="utf-8") as handle:
    pairwise = list(csv.DictReader(handle))
if len(pairwise) != 128:
    errors.append(f"expected 128 pairwise rows, got {len(pairwise)}")
if errors:
    raise SystemExit("; ".join(errors))
print(json.dumps({
    "status": "CKBN_RESULT_VALID",
    "primary_diagnosis": decision["primary_diagnosis"],
    "secondary_diagnosis": decision["secondary_diagnosis"],
    "metrics": decision["metrics"],
}, indent=2, sort_keys=True))
PY

if test "$ALLOW_RUNNING" != "1"; then
  state=$(sacct -j "$JOB_ID" -X -n -P --format=State | head -n 1 | cut -d'|' -f1 | sed 's/+.*//' | tr -d '[:space:]')
  exit_code=$(sacct -j "$JOB_ID" -X -n -P --format=ExitCode | head -n 1 | cut -d'|' -f1 | tr -d '[:space:]')
  test "$state" = "COMPLETED" || { echo "job is not COMPLETED: $state" >&2; exit 2; }
  test "$exit_code" = "0:0" || { echo "job exit code is not 0:0: $exit_code" >&2; exit 2; }
fi

tmp="$ARCHIVE.tmp"
rm -f "$tmp"
tar --exclude="$RUN_NAME/source_feature_cache" --exclude="$RUN_NAME/source_feature_cache/*" \
  -czf "$tmp" -C "$BASE/runs" "$RUN_NAME"
mv "$tmp" "$ARCHIVE"
cd "$BASE/runs"
sha256sum "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256"
sha256sum -c "$(basename "$ARCHIVE").sha256"
echo "CKBN_PULLBACK_ARCHIVE=$ARCHIVE"

