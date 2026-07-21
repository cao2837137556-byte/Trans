#!/bin/bash
set -euo pipefail

BASE=${CKBQ_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
PARTITION=${CKBQ_PARTITION:?set CKBQ_PARTITION to amd or intel}
JOB_ID=${CKBQ_JOB_ID:?set CKBQ_JOB_ID}
ALLOW_RUNNING=${CKBQ_ALLOW_RUNNING:-0}

case "$PARTITION" in amd|intel) ;; *) echo "invalid partition: $PARTITION" >&2; exit 2;; esac
case "$JOB_ID" in ''|*[!0-9]*) echo "invalid job id: $JOB_ID" >&2; exit 2;; esac

RUN_NAME="issue27ckbq_causal_minirocket_consensus_v1_2026-07-17_seed27_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"
ARCHIVE="$BASE/runs/issue27ckbq_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"

required=(
  run_spec.json ckbq_single_seed_go_no_go.json ckbq_environment.json codex_readout.md
  ckbo_auxiliary_benign_manifest.csv ckbo_auxiliary_benign_ready.json
  ckbq_aux_temporal_manifest.csv ckbq_live_report_extension_exclusion.csv
  ckbq_required_report_source_coverage.csv ckbq_support_val_lineage.csv
  ckbq_permanent_report_only_audit.csv ckbq_frozen_model_scope_audit.csv
  ckbq_sealed_holdout_audit.csv ckbq_c1_fit_select_audit.csv
  ckbq_role_usage_audit.csv ckbq_candidate_selection.csv ckbq_model_audit.csv
  ckbq_source_oof_audit.csv ckbq_source_reference_audit.csv
  ckbq_temporal_window_audit.csv ckbq_causal_target_scope_audit.csv
  ckbq_training_trace.csv ckbq_support_training_usage.csv
  ckbq_support_family_training_usage.csv ckbq_negative_sampling_audit.csv
  ckbq_review_audit.csv ckbq_all_metrics.csv ckbq_per_attack_family_metrics.csv
  ckbq_event_scope_audit.csv attack_preservation_summary.csv strict_level2_summary.csv
  ckbq_record_predictions.csv.gz run_timing.txt slurm_identity.txt
)
for file in "${required[@]}"; do
  test -s "$RUN_ROOT/$file" || { echo "missing result file: $RUN_ROOT/$file" >&2; exit 2; }
done
test -d "$RUN_ROOT/aux_temporal_cache" || { echo "missing auxiliary temporal cache" >&2; exit 2; }
test "$(find "$RUN_ROOT/aux_temporal_cache" -maxdepth 1 -name '*.npz' | wc -l)" -eq 31 || {
  echo "auxiliary temporal cache count != 31" >&2; exit 2;
}

python - "$RUN_ROOT" "$PARTITION" "$JOB_ID" <<'PY'
import csv
import gzip
import hashlib
import json
import math
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
partition = sys.argv[2]
job_id = sys.argv[3]
errors = []
primary = "M3-StaticTemporalConsensus"


def rows(name, gz=False):
    opener = gzip.open if gz else open
    with opener(root / name, "rt", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def integer(value, default=-1):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def number(value, default=math.nan):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def truth(value):
    return str(value).strip().lower() in {"true", "1", "yes"}


spec = json.loads((root / "run_spec.json").read_text(encoding="utf-8"))
decision = json.loads((root / "ckbq_single_seed_go_no_go.json").read_text(encoding="utf-8"))
env = json.loads((root / "ckbq_environment.json").read_text(encoding="utf-8"))
ready = json.loads((root / "ckbo_auxiliary_benign_ready.json").read_text(encoding="utf-8"))

expected_protocols = [
    "GLOBAL_ATTACK_PRESERVATION",
    "iotsim-ip-camera-street",
    "iotsim-predictive-maintenance",
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
]
expected_candidates = {
    "M0-C1",
    "A0-GlobalNormalConformal",
    "M1-ShieldedStatic",
    "M2-ShieldedTemporal",
    primary,
}
if decision.get("decision") not in {"GO_SIGNAL", "NO_GO"}:
    errors.append("unknown scientific decision")
if decision.get("candidate") != primary or spec.get("primary_candidate") != primary:
    errors.append("registered primary drift")
if spec.get("protocols") != expected_protocols:
    errors.append("formal protocol list drift")
if set(spec.get("candidates", [])) != expected_candidates:
    errors.append("candidate set drift")
if spec.get("original_1m_split_modified") is not False:
    errors.append("original 1M split changed")
if spec.get("sealed_unopened") != ["iotsim-cooler-motor"]:
    errors.append("sealed holdout contract changed")
if number(spec.get("review_rate"), -1) != 0.0 or spec.get("score_addition_used") is not False:
    errors.append("review or fusion contract drift")
if decision.get("single_seed_scope", "").find("no finite-sample") < 0:
    errors.append("support-val statistical claim boundary missing")
if decision.get("cold_fail_hard_verified") is not True:
    errors.append("scientific decision lacks cold fail-hard evidence")

expected_aux_hash = "d45bb5c0359555b45d19b4b5d2c62ad83ae9dfb177654a3f36c4393fd3120c4f"
manifest_path = root / "ckbo_auxiliary_benign_manifest.csv"
manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
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
    errors.append("auxiliary feature contract failed")

temporal_manifest = rows("ckbq_aux_temporal_manifest.csv")
if len(temporal_manifest) != 31 or len({row.get("source_group") for row in temporal_manifest}) != 31:
    errors.append("auxiliary temporal source coverage drift")
aux_manifest = rows("ckbo_auxiliary_benign_manifest.csv")
aux_by_source = {row.get("source_group"): row for row in aux_manifest}
if len(aux_manifest) != 31 or len(aux_by_source) != 31:
    errors.append("frozen auxiliary source coverage drift")
for row in temporal_manifest:
    source = row.get("source_group")
    reference = aux_by_source.get(source)
    if reference is None:
        errors.append(f"auxiliary temporal source missing from frozen manifest: {source}")
        continue
    warmup = integer(reference.get("warmup_packets"))
    target_rows = integer(reference.get("model_ready_rows"))
    expected_positions = b"".join(
        int(position).to_bytes(8, byteorder="little", signed=True)
        for position in range(warmup, warmup + target_rows)
    )
    expected_position_digest = hashlib.sha256()
    expected_position_digest.update(b"int64")
    expected_position_digest.update(
        int(target_rows).to_bytes(8, byteorder="little", signed=True)
    )
    expected_position_digest.update(expected_positions)
    cache_path = root / "aux_temporal_cache" / row.get("cache_file", "")
    cache_hash = hashlib.sha256(cache_path.read_bytes()).hexdigest() if cache_path.is_file() else ""
    if (
        row.get("role") != reference.get("role")
        or row.get("raw_source_path") != reference.get("raw_source_path")
        or row.get("raw_label_column_read") != "False"
        or row.get("source_identity_as_feature") != "False"
        or row.get("current_event_inclusive") != "True"
        or row.get("future_event_used") != "False"
        or row.get("event_schema") != "CKBE portable raw_msg9"
        or warmup != 500
        or target_rows != 600
        or integer(row.get("events")) != warmup + target_rows
        or integer(row.get("target_offset")) != warmup
        or integer(row.get("target_rows")) != target_rows
        or len(row.get("raw_msg_sha256", "")) != 64
        or row.get("target_event_positions_sha256") != expected_position_digest.hexdigest()
        or not cache_hash
        or row.get("cache_sha256") != cache_hash
    ):
        errors.append(f"auxiliary temporal causality/schema contract failed: {source}")

permanent = rows("ckbq_permanent_report_only_audit.csv")
if not permanent or any(
    integer(row.get(field)) != 0
    for row in permanent
    for field in ("fit_select_rows_after_mask", "model_use_count", "preprocessing_use_count", "gate_use_count")
):
    errors.append("permanent report family entered fit/select")

scope = rows("ckbq_frozen_model_scope_audit.csv")
if not scope or any(
    integer(row.get("missing_feature_zero_fill")) != 0
    or integer(row.get("raw_rows_materialized")) != 0
    or integer(row.get("report_extension_rows_retained")) != 0
    for row in scope
):
    errors.append("frozen target cohort contract failed")

usage = rows("ckbq_role_usage_audit.csv")
if not usage or any(integer(row.get("target_alignment_incomplete"), 1) != 0 for row in usage):
    errors.append("target alignment incomplete")
aux_scope = [row for row in usage if row.get("role") in {"aux_fit", "aux_select"}]
if not aux_scope or any(integer(row.get("held_family_rows_retained", 0), 0) != 0 for row in aux_scope):
    errors.append("held auxiliary family entered fit/select")

phase = rows("ckbq_causal_target_scope_audit.csv")
if not phase or any(
    not truth(row.get("pass"))
    or integer(row.get("duplicate_position_cross_phase")) != 0
    or integer(row.get("collected_target_positions_missing_from_frozen_cache")) != 0
    or not truth(row.get("target_scope_isolation_enforced"))
    or truth(row.get("fit_prefix_contains_select_or_report_target"))
    or truth(row.get("select_prefix_contains_report_target"))
    for row in phase
):
    errors.append("causal target-scope isolation failed")

windows = rows("ckbq_temporal_window_audit.csv")
if not windows or any(
    not truth(row.get("current_event_inclusive"))
    or integer(row.get("current_event_missing")) != 0
    or truth(row.get("future_events_used"))
    or integer(row.get("forbidden_target_events_used")) != 0
    or not truth(row.get("target_scope_isolation_enforced"))
    or not truth(row.get("source_fresh_boundary"))
    or truth(row.get("raw_label_column_read"))
    or integer(row.get("window_length")) != 32
    for row in windows
):
    errors.append("causal window contract failed")

models = rows("ckbq_model_audit.csv")
rocket = [row for row in models if row.get("model", "").startswith("MiniRocketMultivariate")]
global_rocket = [row for row in rocket if row.get("held_value") == "GLOBAL_ATTACK_PRESERVATION"]
if len(global_rocket) != 1:
    errors.append("global MiniRocket model audit missing")
elif (
    integer(global_rocket[0].get("fit_attack_rows")) != 385
    or integer(global_rocket[0].get("fit_report_rows")) != 0
    or global_rocket[0].get("all_support_train_used") != "True"
    or global_rocket[0].get("family_balanced_attack_weights") != "True"
    or global_rocket[0].get("source_balanced_normal_weights") != "True"
    or integer(global_rocket[0].get("input_channels")) != 9
    or integer(global_rocket[0].get("actual_features")) != 3360
    or integer(global_rocket[0].get("nan_count")) != 0
    or integer(global_rocket[0].get("report_gradient_updates")) != 0
    or integer(global_rocket[0].get("report_threshold_updates")) != 0
    or integer(global_rocket[0].get("select_report_transform_batch_crossing")) != 0
):
    errors.append("global MiniRocket/support contract failed")
if not rocket or any(
    row.get("upstream") != "sktime/sktime v0.24.1 BSD-3-Clause"
    or integer(row.get("fit_report_rows")) != 0
    for row in rocket
):
    errors.append("MiniRocket provenance or report isolation failed")

trace = rows("ckbq_training_trace.csv")
ridge_trace = [row for row in trace if row.get("stage") == "fit_weighted_ridge"]
if not ridge_trace or any(not math.isfinite(number(row.get("loss"))) for row in ridge_trace):
    errors.append("finite training loss missing")

support = rows("ckbq_support_training_usage.csv")
if (
    len(support) != 385
    or len({row.get("uid") for row in support}) != 385
    or any(row.get("used_at_least_once") != "True" for row in support)
    or any(integer(row.get("fit_count")) != 1 for row in support)
    or any(integer(row.get("temporal_supervised_fit_count")) != 1 for row in support)
):
    errors.append("all-385 support coverage failed")
families = rows("ckbq_support_family_training_usage.csv")
if not families or sum(integer(row.get("unique_rows"), 0) for row in families) != 385:
    errors.append("support family usage lineage failed")

negative = rows("ckbq_negative_sampling_audit.csv")
if len(negative) != 1 or negative[0].get("negative_sampling_used") != "False" or integer(negative[0].get("negative_samples")) != 0:
    errors.append("negative-sampling not-applicable audit failed")
review = rows("ckbq_review_audit.csv")
if len(review) != 1 or integer(review[0].get("review_count")) != 0 or number(review[0].get("review_rate"), -1) != 0.0:
    errors.append("review != 0")

selection = [
    row for row in rows("ckbq_candidate_selection.csv")
    if row.get("candidate") == primary and row.get("selected") == "True"
]
if len(selection) != len(expected_protocols) or {row.get("held_value") for row in selection} != set(expected_protocols):
    errors.append("one primary gate per protocol missing")
elif any(row.get("gate_constraint_pass") != "True" or integer(row.get("report_rows_used")) != 0 for row in selection):
    errors.append("primary gate used report or failed attack constraint")

predictions = rows("ckbq_record_predictions.csv.gz", gz=True)
if not predictions:
    errors.append("record predictions missing")
else:
    cold_c1 = [
        row for row in predictions
        if number(row.get("c1_score"), -math.inf) >= number(row.get("c1_candidate_threshold"), math.inf)
        and not truth(row.get("temporal_reliable"))
    ]
    if any(not truth(row.get(f"hard__{primary}")) for row in cold_c1):
        errors.append("cold-start suppression artifact detected")
    if any(truth(row.get("review")) for row in predictions):
        errors.append("record-level review != 0")

sealed = rows("ckbq_sealed_holdout_audit.csv")
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

for name in ("attack_preservation_summary.csv", "strict_level2_summary.csv"):
    table = rows(name)
    if not table or any(number(row.get("review_rate"), -1) != 0.0 for row in table):
        errors.append(f"{name} missing or review nonzero")
strict = [row for row in rows("strict_level2_summary.csv") if row.get("candidate") == primary]
if not {
    "iotsim-ip-camera-street",
    "iotsim-predictive-maintenance",
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
}.issubset({row.get("held_value") for row in strict}):
    errors.append("required strict held-family metrics missing")

if str(env.get("slurm_partition")) != partition or str(env.get("slurm_job_id")) != job_id:
    errors.append("Slurm identity mismatch")
if env.get("base_t0_manifest_sha256") != env.get("expected_base_t0_manifest_sha256"):
    errors.append("frozen T0 manifest changed")
if env.get("seed") != 27 or env.get("torch_deterministic_algorithms") is not True:
    errors.append("seed or deterministic execution contract failed")
actual_temporal_manifest_sha256 = hashlib.sha256(
    (root / "ckbq_aux_temporal_manifest.csv").read_bytes()
).hexdigest()
if env.get("auxiliary_temporal_manifest_sha256") != actual_temporal_manifest_sha256:
    errors.append("auxiliary temporal manifest hash mismatch")

if errors:
    raise SystemExit("; ".join(errors))
print(json.dumps({
    "status": "CKBQ_RESULT_VALID",
    "scientific_decision": decision["decision"],
    "partition": partition,
    "job_id": job_id,
    "cold_c1_candidates": decision.get("cold_c1_candidates"),
}, indent=2))
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
echo "CKBQ_PULLBACK_ARCHIVE=$ARCHIVE"
