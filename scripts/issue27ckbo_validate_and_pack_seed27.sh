#!/bin/bash
set -euo pipefail

BASE=${CKBO_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
PARTITION=${CKBO_PARTITION:?set CKBO_PARTITION to amd or intel}
JOB_ID=${CKBO_JOB_ID:?set CKBO_JOB_ID}
ALLOW_RUNNING=${CKBO_ALLOW_RUNNING:-0}

case "$PARTITION" in amd|intel) ;; *) echo "invalid partition: $PARTITION" >&2; exit 2;; esac
case "$JOB_ID" in ''|*[!0-9]*) echo "invalid job id: $JOB_ID" >&2; exit 2;; esac

RUN_NAME="issue27ckbo_mature_afterimage_transfer_v1_2026-07-15_seed27_${PARTITION}_${JOB_ID}"
RUN_ROOT="$BASE/runs/$RUN_NAME"
ARCHIVE="$BASE/runs/issue27ckbo_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"

for file in run_spec.json ckbo_single_seed_go_no_go.json ckbo_environment.json codex_readout.md \
  ckbo_auxiliary_benign_manifest.csv ckbo_auxiliary_benign_ready.json \
  ckbo_permanent_report_only_audit.csv ckbo_candidate_selection.csv \
  ckbo_frozen_model_scope_audit.csv ckbo_sealed_holdout_audit.csv ckbo_c1_fit_select_audit.csv \
  ckbo_support_training_usage.csv ckbo_role_usage_audit.csv ckbo_loss_curves.csv \
  ckbo_negative_sampling_audit.csv ckbo_frontend_state_audit.csv ckbo_event_scope_audit.csv \
  attack_preservation_summary.csv strict_level2_summary.csv run_timing.txt slurm_identity.txt; do
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

spec = json.loads((root / "run_spec.json").read_text(encoding="utf-8"))
decision = json.loads((root / "ckbo_single_seed_go_no_go.json").read_text(encoding="utf-8"))
env = json.loads((root / "ckbo_environment.json").read_text(encoding="utf-8"))
ready = json.loads((root / "ckbo_auxiliary_benign_ready.json").read_text(encoding="utf-8"))
if decision.get("decision") not in {"GO_SIGNAL", "NO_GO"}:
    errors.append("unknown scientific decision")
if set(decision.get("legal_development_held_families", [])) != {"iotsim-ip-camera-street", "iotsim-predictive-maintenance"}:
    errors.append("legal development held-family boundary drift")
if spec.get("original_1m_split_modified") is not False:
    errors.append("original 1M split changed")
if spec.get("sealed_unopened") != ["iotsim-cooler-motor"]:
    errors.append("sealed cooler-motor contract changed")
if float(spec.get("review_rate", -1)) != 0.0:
    errors.append("review != 0")
if int(ready.get("source_count", -1)) != 31 or int(ready.get("fit_sources", -1)) != 11 or int(ready.get("select_sources", -1)) != 5 or int(ready.get("report_sources", -1)) != 15:
    errors.append("auxiliary source split drift")
if int(ready.get("fit_rows", -1)) != 6600 or int(ready.get("select_rows", -1)) != 3000 or int(ready.get("report_rows", -1)) != 9000 or ready.get("report_family") != "iotsim-predictive-maintenance":
    errors.append("auxiliary row/held-family contract drift")
if ready.get("raw_label_column_read") is not False or ready.get("original_1m_assets_modified") is not False:
    errors.append("auxiliary data contract failed")
manifest_path = root / "ckbo_auxiliary_benign_manifest.csv"
manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
if manifest_hash != ready.get("manifest_sha256") or manifest_hash != env.get("auxiliary_manifest_sha256"):
    errors.append("auxiliary manifest hash mismatch")
manifest = rows("ckbo_auxiliary_benign_manifest.csv")
if len(manifest) != 31 or any(row.get("raw_label_column_read") != "False" for row in manifest):
    errors.append("auxiliary manifest rows invalid")
if sum(row.get("role") == "aux_fit" for row in manifest) != 11 or sum(row.get("role") == "aux_select" for row in manifest) != 5 or sum(row.get("role") == "aux_report" for row in manifest) != 15:
    errors.append("auxiliary manifest role counts invalid")
if any((row.get("role") == "aux_report" and (int(row.get("training_rows", -1)) != 0 or int(row.get("selection_rows", -1)) != 0)) for row in manifest):
    errors.append("predictive held family entered auxiliary fit/select")
for row in manifest:
    cache = root / "aux_afterimage_cache" / row.get("cache_npz", "")
    if not cache.is_file() or hashlib.sha256(cache.read_bytes()).hexdigest() != row.get("cache_sha256"):
        errors.append(f"auxiliary cache missing or hash mismatch: {cache.name}")
permanent = rows("ckbo_permanent_report_only_audit.csv")
if not permanent or any(int(row.get(field, -1)) != 0 for row in permanent for field in ("fit_select_rows_after_mask", "model_use_count", "preprocessing_use_count", "gate_use_count")):
    errors.append("report-only family entered fit/select")
scope = rows("ckbo_frozen_model_scope_audit.csv")
if not scope or any(int(row.get("missing_feature_zero_fill", -1)) != 0 or int(row.get("raw_rows_materialized", -1)) != 0 or int(row.get("report_extension_rows_retained", -1)) != 0 for row in scope):
    errors.append("frozen model scope contract failed")
sealed = rows("ckbo_sealed_holdout_audit.csv")
if not sealed or any(row.get("sealed_family") != "iotsim-cooler-motor" or int(row.get("fit_records_used", -1)) != 0 or int(row.get("select_records_used", -1)) != 0 or int(row.get("report_records_scored", -1)) != 0 or int(row.get("metric_labels_opened", -1)) != 0 or row.get("sealed_unopened") != "True" for row in sealed):
    errors.append("sealed cooler-motor was used or scored")
c1_audit = rows("ckbo_c1_fit_select_audit.csv")
c1_threshold = [row for row in c1_audit if row.get("threshold_origin") == "minimum_legal_support_val_attack_score_nextafter_negative_infinity"]
if not c1_threshold or any(int(float(row.get("benign_select_rows_used_for_c1_threshold", -1))) != 0 or int(float(row.get("report_rows_used_for_c1_threshold", -1))) != 0 or float(row.get("support_val_c1_recall", 0)) < 1.0 for row in c1_threshold):
    errors.append("C1 attack-preserving threshold contract failed")
support = [row for row in rows("ckbo_support_training_usage.csv") if row.get("candidate") == "M3-AfterImageContrast-Aux" and row.get("held_value") == "GLOBAL_ATTACK_PRESERVATION"]
if len(support) != 385 or len({row.get("uid") for row in support}) != 385 or any(row.get("used_at_least_once_each_epoch") != "True" for row in support):
    errors.append("global support_train coverage != 385")
usage = rows("ckbo_role_usage_audit.csv")
if not usage or any(int(float(row.get("target_alignment_incomplete", 1))) != 0 for row in usage):
    errors.append("target alignment incomplete")
selection = [row for row in rows("ckbo_candidate_selection.csv") if row.get("candidate") == "M3-AfterImageContrast-Aux" and row.get("held_value") == "GLOBAL_ATTACK_PRESERVATION" and row.get("selected") == "True"]
if len(selection) != 1 or selection[0].get("gate_constraint_pass") != "True" or selection[0].get("report_rows_used") != "0":
    errors.append("primary global gate selection invalid")
for name in ("attack_preservation_summary.csv", "strict_level2_summary.csv"):
    table = rows(name)
    if not table or any(float(row.get("review_rate", -1)) != 0.0 for row in table):
        errors.append(f"{name} missing or review nonzero")
strict = [row for row in rows("strict_level2_summary.csv") if row.get("candidate") == "M3-AfterImageContrast-Aux"]
strict_holds = {row.get("held_value") for row in strict}
if not {"iotsim-ip-camera-street", "iotsim-predictive-maintenance"}.issubset(strict_holds):
    errors.append("required non-canary held-family metrics missing")
if str(env.get("slurm_partition")) != partition or str(env.get("slurm_job_id")) != job_id:
    errors.append("Slurm identity mismatch")
if env.get("base_t0_manifest_sha256") != env.get("expected_base_t0_manifest_sha256"):
    errors.append("frozen T0 manifest changed")
if errors:
    raise SystemExit("; ".join(errors))
print(json.dumps({"status": "CKBO_RESULT_VALID", "scientific_decision": decision["decision"], "partition": partition, "job_id": job_id}, indent=2))
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
echo "CKBO_PULLBACK_ARCHIVE=$ARCHIVE"
