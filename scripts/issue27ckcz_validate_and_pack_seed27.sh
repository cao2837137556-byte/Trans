#!/bin/bash
# CKCZ post-result validator.  This validates the scientific output contract
# before the Slurm wrapper is allowed to package a pullback archive.
set -euo pipefail

RUN_ROOT=${1:?usage: issue27ckcz_validate_and_pack_seed27.sh RUN_ROOT}

test -d "$RUN_ROOT" || { echo "missing CKCZ run root: $RUN_ROOT" >&2; exit 2; }
test ! -e "$RUN_ROOT/job_failure.txt" || {
  echo "CKCZ engineering failure marker exists" >&2
  cat "$RUN_ROOT/job_failure.txt" >&2
  exit 2
}

for name in \
  ckcz_input_audit.json ckcz_source_allowlist_audit.csv \
  ckcz_target_metadata.csv.gz ckcz_pair_cardinality_by_source.csv \
  ckcz_pair_cardinality_distribution.csv ckcz_metadata_temporal_audit.csv \
  ckcz_prediction_join_audit.csv ckcz_pair_state_rows.csv.gz \
  ckcz_conflict_descriptive_audit.csv ckcz_conflict_delta_time_ecdf.csv \
  ckcz_bootstrap_intervals.csv ckcz_verdict.json run_spec.json SHA256SUMS; do
  test -s "$RUN_ROOT/$name" || { echo "missing CKCZ output: $name" >&2; exit 2; }
done

(
  cd "$RUN_ROOT"
  sha256sum -c SHA256SUMS
)

python - "$RUN_ROOT" <<'PY'
import gzip
import json
import math
import os
import sys
from pathlib import Path

import pandas as pd

root = Path(sys.argv[1])
protocol_sha = "dad558902f2dfe2dc0dd4bf76cbf2e9e727be9f5d22ed2e91a5267586e8d3fde"
prediction_sha = "d1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85"
scalars = (
    "pair_conflict_count_so_far",
    "pair_consecutive_conflicts_so_far",
    "pair_conflict_fraction_so_far",
    "pair_conflict_span_seconds_so_far",
)
protocol_rows = {
    "GLOBAL_ATTACK_PRESERVATION": 251050,
    "iotsim-hydraulic-system": 10069,
    "iotsim-ip-camera-street": 10069,
    "iotsim-predictive-maintenance": 16069,
    "iotsim-stream-consumer": 10069,
}
allowed_verdicts = {
    "CKCZ_ORACLE_INFORMATION_EXISTS_LEGAL_NOT_TESTED",
    "CKCZ_ORACLE_NO_INFORMATION",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def load_json(name):
    with (root / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


verdict = load_json("ckcz_verdict.json")
spec = load_json("run_spec.json")
audit = load_json("ckcz_input_audit.json")
require(verdict.get("status") in allowed_verdicts, "invalid scientific verdict status")
require(verdict.get("scientific_verdict_valid") is True, "scientific verdict not valid")
require(verdict.get("bootstrap_complete") is True, "bootstrap is incomplete")
require(verdict.get("bootstrap_reps") == 200, "bootstrap rep drift")
require(set(verdict.get("scalar_oracle_compatible", {})) == set(scalars), "scalar verdict set drift")
compatible = any(bool(value) for value in verdict["scalar_oracle_compatible"].values())
require(
    compatible == (verdict["status"] == "CKCZ_ORACLE_INFORMATION_EXISTS_LEGAL_NOT_TESTED"),
    "verdict status/frontier feasibility mismatch",
)

require(spec.get("issue") == "issue27ckcz_endpoint_pair_conflict_diagnostic_v1_2026-08-09", "issue drift")
require(spec.get("seed") == 27, "seed drift")
require(spec.get("frozen_preregistered_protocol_sha256") == protocol_sha, "protocol SHA drift")
require(spec.get("hpc_submission_authorized") is False, "implementation rewrote authorization history")
require(spec.get("bootstrap_reps") == 200 and spec.get("bootstrap_complete") is True, "run_spec bootstrap drift")
require(spec.get("scientific_verdict_valid") is True, "run_spec scientific verdict invalid")
require(audit.get("status") == "CKCZ_INPUT_CONTRACT_PASS", "input contract did not pass")
require(audit.get("prediction_sha256") == prediction_sha, "prediction SHA drift")
require(audit.get("final_markers_loaded") is False, "FINAL marker was loaded")
require(len(audit.get("gotham", [])) == 24, "Gotham selected-source count drift")
require(len(audit.get("auxiliary", [])) == 31, "auxiliary selected-source count drift")

allow = pd.read_csv(root / "ckcz_source_allowlist_audit.csv")
require(len(allow) == 55, "source allowlist audit row drift")
metadata = pd.read_csv(
    root / "ckcz_target_metadata.csv.gz",
    usecols=["cache_kind", "source_group", "target_index"],
)
require(len(metadata) == 336123, "metadata row drift")
require(metadata.groupby("cache_kind").size().to_dict() == {"auxiliary": 18600, "gotham": 317523}, "metadata cache row drift")

cardinality = pd.read_csv(root / "ckcz_pair_cardinality_by_source.csv")
require(len(cardinality) == 55, "pair-cardinality source coverage drift")

join = pd.read_csv(root / "ckcz_prediction_join_audit.csv")
require(join.set_index("held_value")["rows"].astype(int).to_dict() == protocol_rows, "prediction protocol row drift")
require(int(join["unexpected_unmatched"].sum()) == 0, "unexpected metadata join miss")
require(
    join["metadata_unmatched"].astype(int).equals(join["ton_expected_unmatched"].astype(int)),
    "metadata misses are not exactly the frozen ToN rows",
)
require(int(join["metadata_unmatched"].sum()) > 0, "expected ToN metadata-miss rows disappeared")

state = pd.read_csv(
    root / "ckcz_pair_state_rows.csv.gz",
    usecols=["held_value", "uid", "review", "attack_family"],
)
require(len(state) == 297326, "pair-state row drift")
require(state.groupby("held_value").size().to_dict() == protocol_rows, "pair-state protocol row drift")
require(not state.duplicated(["held_value", "uid"]).any(), "pair-state UID collision")
review = state["review"].astype(str).str.lower()
require(not review.isin({"true", "1", "yes"}).any(), "review rows are forbidden")

bootstrap = pd.read_csv(root / "ckcz_bootstrap_intervals.csv")
expected_bootstrap = 0
all_families = set()
for scalar in scalars:
    frontier_path = root / f"ckcz_oracle_frontier_{scalar}.csv"
    family_path = root / f"ckcz_attack_family_metrics_{scalar}.csv"
    pool_path = root / f"ckcz_ood_pool_metrics_{scalar}.csv"
    for path in (frontier_path, family_path, pool_path):
        require(path.is_file() and path.stat().st_size > 0, f"missing scalar output: {path.name}")
    frontier = pd.read_csv(frontier_path)
    families = pd.read_csv(family_path)
    pools = pd.read_csv(pool_path)
    require(len(frontier) >= 1, f"empty frontier: {scalar}")
    require(frontier["frontier_index"].astype(int).tolist() == list(range(len(frontier))), f"frontier index drift: {scalar}")
    require(set(frontier["cut_use"].astype(str)) == {"FORBIDDEN_FOR_SELECTION"}, f"cut-use drift: {scalar}")
    require(float(frontier.iloc[0]["review_rate"]) == 0.0, f"review-rate drift: {scalar}")
    require(math.isinf(float(frontier.iloc[0]["cut"])), f"baseline cut is not infinity: {scalar}")
    require(len(families) == 16 * len(frontier), f"family frontier coverage drift: {scalar}")
    require(families.groupby("frontier_index").size().eq(16).all(), f"family rows/frontier drift: {scalar}")
    require(len(pools) == 4 * len(frontier), f"OOD frontier coverage drift: {scalar}")
    require(pools.groupby("frontier_index").size().eq(4).all(), f"OOD rows/frontier drift: {scalar}")
    all_families.update(families["attack_family"].astype(str).unique())
    scalar_bootstrap = bootstrap.loc[bootstrap["scalar"].eq(scalar)]
    require(len(scalar_bootstrap) == 12 * len(frontier), f"bootstrap frontier coverage drift: {scalar}")
    require(scalar_bootstrap.groupby("frontier_index").size().eq(12).all(), f"bootstrap rows/frontier drift: {scalar}")
    expected_bootstrap += 12 * len(frontier)
require(len(all_families) == 16, "attack-family denominator drift")
require(len(bootstrap) == expected_bootstrap, "bootstrap total row drift")
require(set(bootstrap["cluster_unit"].astype(str)) <= {"source", "pair"}, "record-level bootstrap is forbidden")
require(bootstrap["bootstrap_reps"].astype(int).eq(200).all(), "bootstrap rep column drift")

for path in root.iterdir():
    lowered = path.name.lower()
    require("seed37" not in lowered and "seed47" not in lowered, "FINAL seed marker in output name")

report = {
    "status": "CKCZ_POST_RESULT_VALIDATION_PASS",
    "scientific_verdict": verdict["status"],
    "metadata_rows": int(len(metadata)),
    "pair_state_rows": int(len(state)),
    "selected_sources": int(len(allow)),
    "attack_families": int(len(all_families)),
    "bootstrap_rows": int(len(bootstrap)),
    "core_sha256sum_verified": True,
}
temporary = root / "ckcz_validation_report.json.tmp"
temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(temporary, root / "ckcz_validation_report.json")
print(json.dumps(report, sort_keys=True))
PY

echo "CKCZ_POST_RESULT_VALIDATION_PASS run_root=$RUN_ROOT"
