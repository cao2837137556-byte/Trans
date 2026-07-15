#!/bin/bash
set -euo pipefail

BASE=${CKBP_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
PARTITION=${CKBP_PARTITION:?set CKBP_PARTITION to amd or intel}
JOB_ID=${CKBP_JOB_ID:?set CKBP_JOB_ID}
ALLOW_RUNNING=${CKBP_ALLOW_RUNNING:-0}

case "$PARTITION" in amd|intel) ;; *) echo "invalid partition: $PARTITION" >&2; exit 2;; esac
case "$JOB_ID" in ''|*[!0-9]*) echo "invalid job id: $JOB_ID" >&2; exit 2;; esac

RUN_NAME="issue27ckbp_source_local_normal_calibration_v1_2026-07-15_seed27_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"
ARCHIVE="$BASE/runs/issue27ckbp_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"

for file in run_spec.json ckbp_single_seed_go_no_go.json ckbp_environment.json codex_readout.md \
  ckbo_auxiliary_benign_manifest.csv ckbo_auxiliary_benign_ready.json \
  ckbp_live_report_extension_exclusion.csv ckbp_required_report_source_coverage.csv \
  ckbp_support_val_lineage.csv ckbp_permanent_report_only_audit.csv \
  ckbp_frozen_model_scope_audit.csv ckbp_sealed_holdout_audit.csv \
  ckbp_c1_fit_select_audit.csv ckbp_role_usage_audit.csv ckbp_candidate_selection.csv \
  ckbp_normal_model_audit.csv ckbp_source_oof_audit.csv ckbp_source_reference_audit.csv \
  ckbp_calibration_state_audit.csv ckbp_support_training_usage.csv \
  ckbp_support_family_training_usage.csv ckbp_negative_sampling_audit.csv \
  ckbp_optimization_audit.csv ckbp_all_metrics.csv ckbp_per_attack_family_metrics.csv \
  ckbp_event_scope_audit.csv attack_preservation_summary.csv strict_level2_summary.csv \
  run_timing.txt slurm_identity.txt; do
  test -s "$RUN_ROOT/$file" || { echo "missing result file: $RUN_ROOT/$file" >&2; exit 2; }
done

python - "$RUN_ROOT" "$PARTITION" "$JOB_ID" <<'PY'
import csv
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
partition = sys.argv[2]
job_id = sys.argv[3]
errors = []


def rows(name):
    with (root / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def integer(value, default=-1):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


spec = json.loads((root / "run_spec.json").read_text(encoding="utf-8"))
decision = json.loads((root / "ckbp_single_seed_go_no_go.json").read_text(encoding="utf-8"))
env = json.loads((root / "ckbp_environment.json").read_text(encoding="utf-8"))
ready = json.loads((root / "ckbo_auxiliary_benign_ready.json").read_text(encoding="utf-8"))

if decision.get("decision") not in {"GO_SIGNAL", "NO_GO"}:
    errors.append("unknown scientific decision")
if decision.get("candidate") != "M2-CappedSourceConformal":
    errors.append("registered primary candidate drift")
if set(decision.get("legal_development_held_families", [])) != {
    "iotsim-ip-camera-street",
    "iotsim-predictive-maintenance",
}:
    errors.append("legal development held-family boundary drift")
if spec.get("original_1m_split_modified") is not False:
    errors.append("original 1M split changed")
if spec.get("sealed_unopened") != ["iotsim-cooler-motor"]:
    errors.append("sealed cooler-motor contract changed")
expected_protocols = [
    "GLOBAL_ATTACK_PRESERVATION",
    "iotsim-ip-camera-street",
    "iotsim-predictive-maintenance",
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
]
if spec.get("protocols") != expected_protocols:
    errors.append("formal protocol list drift")
if float(spec.get("review_rate", -1)) != 0.0:
    errors.append("review != 0")

candidates = {row.get("name"): row for row in spec.get("candidates", [])}
if candidates.get("M2-CappedSourceConformal", {}).get("primary") is not True:
    errors.append("bounded source conformal is not primary")
if candidates.get("A1-UnboundedSourceConformal", {}).get("deployable") is not False:
    errors.append("unbounded adaptation control became deployable")

manifest_path = root / "ckbo_auxiliary_benign_manifest.csv"
manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
expected_aux_hash = "d45bb5c0359555b45d19b4b5d2c62ad83ae9dfb177654a3f36c4393fd3120c4f"
if manifest_hash != expected_aux_hash or manifest_hash != ready.get("manifest_sha256"):
    errors.append("frozen CKBO auxiliary manifest changed")
if env.get("auxiliary_manifest_sha256") != expected_aux_hash:
    errors.append("environment auxiliary manifest hash mismatch")
if (
    integer(ready.get("source_count")) != 31
    or integer(ready.get("fit_sources")) != 11
    or integer(ready.get("select_sources")) != 5
    or integer(ready.get("report_sources")) != 15
):
    errors.append("auxiliary source split drift")
if ready.get("raw_label_column_read") is not False or ready.get("original_1m_assets_modified") is not False:
    errors.append("auxiliary data contract failed")

permanent = rows("ckbp_permanent_report_only_audit.csv")
if not permanent or any(
    integer(row.get(field)) != 0
    for row in permanent
    for field in ("fit_select_rows_after_mask", "model_use_count", "preprocessing_use_count", "gate_use_count")
):
    errors.append("permanent report family entered fit/select")

scope = rows("ckbp_frozen_model_scope_audit.csv")
if not scope or any(
    integer(row.get("missing_feature_zero_fill")) != 0
    or integer(row.get("raw_rows_materialized")) != 0
    or integer(row.get("report_extension_rows_retained")) != 0
    for row in scope
):
    errors.append("frozen target cohort contract failed")

sealed = rows("ckbp_sealed_holdout_audit.csv")
if not sealed or any(
    row.get("sealed_family") != "iotsim-cooler-motor"
    or integer(row.get("fit_records_used")) != 0
    or integer(row.get("select_records_used")) != 0
    or integer(row.get("report_records_scored")) != 0
    or integer(row.get("metric_labels_opened")) != 0
    or row.get("sealed_unopened") != "True"
    for row in sealed
):
    errors.append("sealed cooler-motor was used or scored")

c1_audit = rows("ckbp_c1_fit_select_audit.csv")
c1_threshold = [
    row
    for row in c1_audit
    if row.get("threshold_origin") == "minimum_legal_support_val_attack_score_nextafter_negative_infinity"
]
if not c1_threshold or any(
    integer(row.get("benign_select_rows_used_for_c1_threshold")) != 0
    or integer(row.get("report_rows_used_for_c1_threshold")) != 0
    or float(row.get("support_val_c1_recall", 0)) < 1.0
    for row in c1_threshold
):
    errors.append("C1 attack-preserving threshold contract failed")

support = rows("ckbp_support_training_usage.csv")
if (
    len(support) != 385
    or len({row.get("uid") for row in support}) != 385
    or any(row.get("used_at_least_once") != "True" for row in support)
    or any(integer(row.get("fit_count")) < 1 for row in support)
    or any(integer(row.get("normal_calibrator_fit_count")) != 0 for row in support)
):
    errors.append("global support_train coverage or one-sided use failed")

usage = rows("ckbp_role_usage_audit.csv")
if not usage or any(integer(row.get("target_alignment_incomplete"), 1) != 0 for row in usage):
    errors.append("target alignment incomplete")
aux_scope = [row for row in usage if row.get("role") in {"aux_fit", "aux_select"}]
if not aux_scope or any(integer(row.get("held_family_rows_retained", 0), 0) != 0 for row in aux_scope):
    errors.append("held family entered auxiliary fit/select")
aux_report = [row for row in usage if row.get("role") == "aux_report"]
if len(aux_report) != 1 or aux_report[0].get("held_value") != "iotsim-predictive-maintenance" or integer(aux_report[0].get("fit_select_use_count")) != 0:
    errors.append("predictive report scope drift")

models = rows("ckbp_normal_model_audit.csv")
if not models or any(
    row.get("model") != "normal_only_quantile_ledoit_wolf"
    or integer(row.get("fit_attack_rows")) != 0
    or integer(row.get("fit_report_rows")) != 0
    or row.get("source_disjoint_select_reference") != "True"
    or row.get("source_out_of_fold_diagnostic") != "True"
    or integer(row.get("source_oof_folds")) < 3
    or integer(row.get("reference_sources")) < 3
    or integer(row.get("reference_attack_rows")) != 0
    or integer(row.get("reference_report_rows")) != 0
    or integer(row.get("report_gradient_updates")) != 0
    or integer(row.get("report_threshold_updates")) != 0
    for row in models
):
    errors.append("normal-only source-OOF model contract failed")

oof = rows("ckbp_source_oof_audit.csv")
if not oof or any(
    integer(row.get("held_source_used_in_fit")) != 0
    or integer(row.get("report_rows_used")) != 0
    or integer(row.get("attack_rows_used")) != 0
    for row in oof
):
    errors.append("source-out-of-fold calibration leakage")

state = rows("ckbp_calibration_state_audit.csv")
if not state or any(
    integer(row.get("score_before_update_records")) != integer(row.get("records"))
    or row.get("phase_state_crossing") != "False"
    or row.get("label_read_for_state") != "False"
    or row.get("future_events_used") != "False"
    or integer(row.get("report_gradient_updates")) != 0
    for row in state
):
    errors.append("past-only causal calibration state contract failed")
primary_state = [row for row in state if row.get("candidate") == "M2-CappedSourceConformal"]
if not primary_state or sum(integer(row.get("fresh_resets"), 0) for row in primary_state) <= 0:
    errors.append("primary source resets missing")
if sum(integer(row.get("cold_start_records"), 0) for row in primary_state) <= 0:
    errors.append("primary cold-start fail-closed evidence missing")
if any(row.get("bounded_shift_contract") != "True" for row in primary_state):
    errors.append("primary bounded-shift contract missing")
for row in primary_state:
    lower = float(row.get("registered_shift_low", "nan"))
    upper = float(row.get("registered_shift_high", "nan"))
    observed_low = row.get("minimum_applied_shift", "")
    observed_high = row.get("maximum_applied_shift", "")
    if observed_low not in {"", "nan"} and float(observed_low) < lower - 1e-12:
        errors.append("primary applied shift below registered lower bound")
    if observed_high not in {"", "nan"} and float(observed_high) > upper + 1e-12:
        errors.append("primary applied shift above registered upper bound")

selection = [
    row
    for row in rows("ckbp_candidate_selection.csv")
    if row.get("candidate") == "M2-CappedSourceConformal"
    and row.get("held_value") == "GLOBAL_ATTACK_PRESERVATION"
    and row.get("selected") == "True"
]
if (
    len(selection) != 1
    or selection[0].get("gate_constraint_pass") != "True"
    or integer(selection[0].get("report_rows_used")) != 0
):
    errors.append("primary global gate selection invalid")

for name in ("attack_preservation_summary.csv", "strict_level2_summary.csv"):
    table = rows(name)
    if not table or any(float(row.get("review_rate", -1)) != 0.0 for row in table):
        errors.append(f"{name} missing or review nonzero")
strict = [row for row in rows("strict_level2_summary.csv") if row.get("candidate") == "M2-CappedSourceConformal"]
strict_holds = {row.get("held_value") for row in strict}
if not {
    "iotsim-ip-camera-street",
    "iotsim-predictive-maintenance",
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
}.issubset(strict_holds):
    errors.append("required held-family metrics missing")

if str(env.get("slurm_partition")) != partition or str(env.get("slurm_job_id")) != job_id:
    errors.append("Slurm identity mismatch")
if env.get("base_t0_manifest_sha256") != env.get("expected_base_t0_manifest_sha256"):
    errors.append("frozen T0 manifest changed")

if errors:
    raise SystemExit("; ".join(errors))
print(
    json.dumps(
        {
            "status": "CKBP_RESULT_VALID",
            "scientific_decision": decision["decision"],
            "partition": partition,
            "job_id": job_id,
        },
        indent=2,
    )
)
PY

if test "$ALLOW_RUNNING" != "1"; then
  state=$(sacct -j "$JOB_ID" -X -n -P --format=State | head -n 1 | cut -d'|' -f1 | sed 's/+.*//' | tr -d '[:space:]')
  exit_code=$(sacct -j "$JOB_ID" -X -n -P --format=ExitCode | head -n 1 | cut -d'|' -f1 | tr -d '[:space:]')
  test "$state" = "COMPLETED" || { echo "job is not COMPLETED: $state" >&2; exit 2; }
  test "$exit_code" = "0:0" || { echo "job exit code is not 0:0: $exit_code" >&2; exit 2; }
fi

tmp="$ARCHIVE.tmp"
rm -f "$tmp"
tar -czf "$tmp" -C "$BASE/runs" "$RUN_NAME"
mv "$tmp" "$ARCHIVE"
cd "$BASE/runs"
sha256sum "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256"
sha256sum -c "$(basename "$ARCHIVE").sha256"
echo "CKBP_PULLBACK_ARCHIVE=$ARCHIVE"
