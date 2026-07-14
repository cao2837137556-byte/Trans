#!/bin/bash
set -euo pipefail

BASE=${CKBM_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
PARTITION=${CKBM_PARTITION:?set CKBM_PARTITION to amd or intel}
JOB_ID=${CKBM_JOB_ID:?set CKBM_JOB_ID}
case "$PARTITION" in amd|intel) ;; *) echo "invalid partition: $PARTITION" >&2; exit 2 ;; esac
[[ "$JOB_ID" =~ ^[0-9]+$ ]] || { echo "invalid job id: $JOB_ID" >&2; exit 2; }

RUN_ROOT="$BASE/runs/issue27ckbm_tabm_causal_source_calibration_v1_2026-07-14_seed27_${PARTITION}_${JOB_ID}"
ARCHIVE="$BASE/runs/issue27ckbm_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"
SHA_FILE="$ARCHIVE.sha256"
test -d "$RUN_ROOT" || { echo "missing run root: $RUN_ROOT" >&2; exit 2; }

RUN_ROOT="$RUN_ROOT" PARTITION="$PARTITION" JOB_ID="$JOB_ID" python - <<'PY'
import csv
import json
import os
from collections import Counter
from pathlib import Path

root = Path(os.environ["RUN_ROOT"])
errors = []

def require(condition, message):
    if not condition:
        errors.append(message)

def load_json(name):
    path = root / name
    if not path.is_file():
        errors.append(f"missing output: {name}")
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def rows(name):
    path = root / name
    if not path.is_file():
        errors.append(f"missing output: {name}")
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))

decision = load_json("ckbm_single_seed_go_no_go.json")
spec = load_json("run_spec.json")
environment = load_json("ckbm_environment.json")
require(decision.get("seed") == 27, "decision seed is not 27")
require(decision.get("candidate") == "M3-TabM-CSR", "wrong primary decision candidate")
require(decision.get("decision") in {"GO_SIGNAL", "NO_GO"}, "missing scientific GO/NO_GO result")
require(isinstance(decision.get("checks"), dict) and decision["checks"], "decision checks missing")
require(spec.get("mode") == "formal", "run mode is not formal")
require(spec.get("seed") == 27, "run seed is not 27")
require(spec.get("primary_candidate") == "M3-TabM-CSR", "run primary candidate drift")
require(spec.get("report_used_for_fit_or_select") is False, "report used for fit/select")
require(spec.get("review_rate") == 0.0, "review is not zero")
require(environment.get("seed") == 27, "environment seed is not 27")
require(environment.get("review_rate") == 0.0, "environment review is not zero")
require(environment.get("slurm_partition") == os.environ["PARTITION"], "partition identity mismatch")
require(environment.get("slurm_job_id") == os.environ["JOB_ID"], "job identity mismatch")
require(environment.get("base_manifest_sha256") == "b102b04347dd320f9f89a219285285866dbfa09e09bd73d0839cbe1a91bb0f67", "base manifest hash drift")
vendor = environment.get("vendor", {})
require(vendor.get("version") == "0.0.3", "TabM version drift")
require(vendor.get("upstream_commit") == "a507095893d784c5702059d737ddfbd1299c41dd", "TabM upstream commit drift")
require(vendor.get("tabm_py_sha256_lf") == "fc654af6a16bac53d893a8265c79d7af4ebddcb95ad0d600cc6b6bc6b7317ade", "TabM source hash drift")
require(vendor.get("source_modified") is False, "TabM source marked modified")

scope = rows("ckbm_event_scope_audit.csv")
global_scope = {row["record_set"]: row for row in scope if row.get("held_value") == "GLOBAL_ATTACK_PRESERVATION"}
expected = {"fit_attack": 385, "fit_benign": 12000, "select_attack": 69, "select_benign": 9000, "report": 301931}
for key, count in expected.items():
    require(key in global_scope, f"missing global scope {key}")
    if key in global_scope:
        require(int(global_scope[key]["events"]) == count, f"global {key} count != {count}")
        require(int(global_scope[key]["memory_only_events"]) == 0, f"unexpected memory-only events for {key}")

usage = rows("ckbm_support_training_usage.csv")
global_usage = [row for row in usage if row.get("held_value") == "GLOBAL_ATTACK_PRESERVATION"]
counts = Counter(row.get("candidate") for row in global_usage)
for candidate in ["M1-ExtraTrees-Global", "M2-TabM-Global", "M3-TabM-CSR", "A1-ExtraTrees-CSR"]:
    require(counts[candidate] == 385, f"global support usage for {candidate} != 385")
require(all(row.get("used_at_least_once_each_epoch") == "True" for row in global_usage), "support row not used as contracted")

family_usage = rows("ckbm_support_family_training_usage.csv")
global_family_usage = [
    row for row in family_usage if row.get("held_value") == "GLOBAL_ATTACK_PRESERVATION"
]
for candidate in ["M1-ExtraTrees-Global", "M2-TabM-Global", "M3-TabM-CSR", "A1-ExtraTrees-CSR"]:
    values = {
        int(row["sampled_occurrences_per_epoch"])
        for row in global_family_usage
        if row.get("candidate") == candidate
    }
    require(len(values) == 1 and next(iter(values), 0) > 0, f"attack-family sampling is not balanced for {candidate}")

causal = rows("ckbm_causal_source_state_audit.csv")
require(len(causal) == 18, "expected 3 causal phase audits for each of 6 protocols")
for row in causal:
    require(int(row["records"]) == int(row["score_before_update_records"]), "score-before-update count mismatch")
    require(row.get("label_read_for_state") == "False", "label read for causal state")
    require(row.get("phase_state_crossing") == "False", "causal state crossed phase")
    require(int(row["fresh_resets"]) == int(row["sources"]), "source reset count mismatch")

selection = rows("ckbm_candidate_selection.csv")
selected_primary = [row for row in selection if row.get("candidate") == "M3-TabM-CSR" and row.get("selected") == "True"]
require(len(selected_primary) == 6, "primary threshold was not selected once per protocol")
require(all(int(row.get("report_rows_used", "-1")) == 0 for row in selection), "report rows used during gate selection")

losses = rows("ckbm_loss_curves.csv")
require(losses, "loss curves empty")
require(all(row.get("finite_losses") == "True" for row in losses), "nonfinite loss marker")
require(all(row.get("all_unique_rows_covered") == "True" for row in losses), "training epoch omitted legal rows")
require(all(row.get("sampling_contract") == "coverage_first_attack_family_balanced" for row in losses), "family-balanced sampling contract drift")
require(all(row.get("support_val_used_for_early_stopping") == "False" for row in losses), "support_val used for early stopping")

negative = rows("ckbm_negative_sampling_audit.csv")
require(len(negative) == 1 and int(negative[0].get("sampled_negatives", "-1")) == 0, "negative-sampling audit mismatch")

attack = rows("attack_preservation_summary.csv")
strict = rows("strict_level2_summary.csv")
require(any(row.get("candidate") == "M3-TabM-CSR" and row.get("metric") == "overall_attack_hard_recall" for row in attack), "primary overall attack metric missing")
for held in ["iotsim-stream-consumer", "iotsim-hydraulic-system", "iotsim-ip-camera-street"]:
    require(any(row.get("candidate") == "M3-TabM-CSR" and row.get("held_value") == held for row in strict), f"primary strict metric missing for {held}")
for row in attack + strict:
    require(float(row.get("review_rate", "1")) == 0.0, "nonzero review rate")

required_files = [
    "ckbm_required_report_source_coverage.csv",
    "ckbm_source_family_contract.csv",
    "ckbm_support_val_lineage.csv",
    "ckbm_live_report_extension_fit_select_exclusion.csv",
    "ckbm_role_usage_audit.csv",
    "ckbm_held_exclusion_audit.csv",
    "ckbm_support_family_training_usage.csv",
    "ckbm_preprocessing_audit.csv",
    "ckbm_model_audit.csv",
    "ckbm_per_attack_family_metrics.csv",
    "resource_usage.txt",
    "slurm_identity.txt",
]
for name in required_files:
    require((root / name).is_file(), f"missing output: {name}")

result = {
    "status": "PASS" if not errors else "FAIL",
    "partition": os.environ["PARTITION"],
    "job_id": os.environ["JOB_ID"],
    "scientific_decision": decision.get("decision"),
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
echo "CKBM_PULLBACK_ARCHIVE=$ARCHIVE"
cat "$SHA_FILE"
