#!/bin/bash
set -euo pipefail

BASE=${CKBV_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
DATA_ROOT=${CKBV_DATA_ROOT:-/public/home/jiangxinwei.zr/work/paper04/datasets}
PARTITION=${CKBV_PARTITION:?missing CKBV_PARTITION}
JOB_ID=${CKBV_JOB_ID:?missing CKBV_JOB_ID}
ALLOW_RUNNING=${CKBV_ALLOW_RUNNING:-0}
ALLOW_POSTFORMAL_FAILED=${CKBV_ALLOW_POSTFORMAL_FAILED:-0}
CODE_ROOT=${CKBV_CODE_ROOT:?missing CKBV_CODE_ROOT}
COMMIT_SHA=${CKBV_COMMIT_SHA:?missing CKBV_COMMIT_SHA}

case "$PARTITION" in
  amd|intel) ;;
  *) echo "invalid partition: $PARTITION" >&2; exit 2 ;;
esac

RUN_ROOT="$BASE/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_${PARTITION}_${JOB_ID}"
ARCHIVE="$BASE/runs/issue27ckbv_seed27_${PARTITION}_${JOB_ID}_pullback.tar.gz"
test -d "$RUN_ROOT" || {
  echo "missing CKBV run root: $RUN_ROOT" >&2
  exit 2
}
state=$(sacct -j "$JOB_ID" -X -n -P --format=State |
  head -n 1 |
  cut -d'|' -f1 |
  sed 's/+.*//' |
  tr -d '[:space:]')
if test "$ALLOW_RUNNING" != 1; then
  if test "$ALLOW_POSTFORMAL_FAILED" = 1; then
    test "$state" = FAILED || {
      echo "post-formal recovery requires FAILED job, got: $state" >&2
      exit 2
    }
    grep -Fxq 'phase=validate_and_pack' "$RUN_ROOT/job_failure.txt" || {
      echo "post-formal recovery refused: failure was not validate_and_pack" >&2
      exit 2
    }
  else
    test "$state" = COMPLETED || {
      echo "job is not COMPLETED: $state" >&2
      exit 2
    }
  fi
fi

python - "$RUN_ROOT" "$PARTITION" "$JOB_ID" "$CODE_ROOT" "$DATA_ROOT" \
  "$COMMIT_SHA" "$ALLOW_POSTFORMAL_FAILED" "$state" <<'PY'
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(sys.argv[1])
partition = sys.argv[2]
job = sys.argv[3]
code_root = Path(sys.argv[4])
data_root = Path(sys.argv[5])
commit_sha = sys.argv[6]
postformal_recovery = sys.argv[7] == "1"
slurm_state = sys.argv[8]
sys.path.insert(0, str(code_root))

import issue27ckbv_checkpointed_sparse_process_frontend_v1 as ckbv


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


required = [
    "ckbu_single_seed_go_no_go.json",
    "attack_preservation_summary.csv",
    "strict_level2_summary.csv",
    "ckbu_candidate_selection.csv",
    "ckbu_support_training_usage.csv",
    "ckbu_role_usage_audit.csv",
    "ckbu_record_predictions.csv.gz",
    "ckbu_environment.json",
    "run_spec.json",
    "codex_readout.md",
    "ckbu_review_audit.csv",
    "ckbu_gotham_unified_causal_ready.json",
    "ckbu_auxiliary_unified_causal_ready.json",
    "ckbu_ton_raw_pcap_pilot_causal_ready.json",
    "ckbu_auxiliary_parallel_ready.json",
    "ckbu_auxiliary_parallel_reuse_audit.csv",
    "ckbv_gotham_member_plan.csv",
    "ckbv_gotham_member_plan.json",
    "ckbv_gotham_checkpoint_ready.json",
    "ckbv_source_reuse_audit.csv",
    "ckbv_source_aggregation_audit.csv",
    "ckbu_raw51_mask_sensitivity_audit.csv",
    "current_phase.txt",
    "run_timing.txt",
    "slurm_identity.txt",
    "slurm_in_job_accounting.csv",
]
if postformal_recovery:
    required.append("ckbv_postformal_recovery.json")
missing = [
    name
    for name in required
    if not (root / name).is_file() or not (root / name).stat().st_size
]
if missing:
    raise SystemExit(f"missing CKBV result files: {missing}")

decision = json.loads((root / "ckbu_single_seed_go_no_go.json").read_text())
if decision.get("decision") not in {"GO_SIGNAL", "NO_GO"}:
    raise SystemExit(f"invalid scientific decision: {decision.get('decision')}")

gotham = json.loads((root / "ckbu_gotham_unified_causal_ready.json").read_text())
auxiliary = json.loads((root / "ckbu_auxiliary_unified_causal_ready.json").read_text())
ton = json.loads((root / "ckbu_ton_raw_pcap_pilot_causal_ready.json").read_text())
checkpoint = json.loads((root / "ckbv_gotham_checkpoint_ready.json").read_text())
member_contract = json.loads((root / "ckbv_gotham_member_plan.json").read_text())

# raw51_observable_v1 mask (ledger section 11): one fully-masked benign
# source (hydraulic-system-1, 1,353 ood_val targets) is absent from the
# raw-51D materialization. Frozen manifest unchanged; observable = 323,714.
RAW51_MASK_TOTAL = 1353
RAW51_MASK_SHA256 = "b16017d2755feaedbe6d3ad76fd7d1e2444cf66a14a70f6bca35f270734ad2df"
RAW51_MASK_SOURCE = "processed/iotsim-hydraulic-system-1.csv"
if gotham.get("sources") != 29 or gotham.get("targets") != 325067 - RAW51_MASK_TOTAL:
    raise SystemExit(f"Gotham observable coverage drift: {gotham}")
if gotham.get("raw51_masked_targets_total") != RAW51_MASK_TOTAL:
    raise SystemExit(f"raw51 masked total drift: {gotham}")
if gotham.get("raw51_fully_masked_sources") != [RAW51_MASK_SOURCE]:
    raise SystemExit(f"raw51 masked source drift: {gotham}")
if str(gotham.get("raw51_observable_mask_sha256")) != RAW51_MASK_SHA256:
    raise SystemExit(f"raw51 mask sha256 drift: {gotham}")
if auxiliary.get("sources") != 31 or auxiliary.get("targets") != 18600:
    raise SystemExit(f"auxiliary coverage drift: {auxiliary}")
if ton.get("rows") != 12000 or ton.get("reserved_injection_mitm_model_rows") != 0:
    raise SystemExit(f"ToN scope drift: {ton}")
if ton.get("scientific_protocol_changed") is not False:
    raise SystemExit("ToN scientific protocol changed")
if checkpoint.get("sources") != 29:
    raise SystemExit(f"checkpoint source coverage drift: {checkpoint}")
if checkpoint.get("raw51_fully_masked_sources") != [RAW51_MASK_SOURCE]:
    raise SystemExit(f"checkpoint raw51 masked source drift: {checkpoint}")
if checkpoint.get("members") != member_contract.get("members"):
    raise SystemExit("member count drift between plan and checkpoint summary")
if checkpoint.get("scientific_protocol_changed") is not False:
    raise SystemExit("Gotham scientific protocol changed")
if checkpoint.get("execution_only_sparse_emit") is not True:
    raise SystemExit("sparse execution audit missing")

# raw51_observable_v1 evidence closure (Codex r12 requirement 4). The
# sensitivity audit and dual-denominator attack metrics must be present with
# the exact preregistered numbers, or packaging fails even if a CSV is empty
# or degraded.
sens = pd.read_csv(root / "ckbu_raw51_mask_sensitivity_audit.csv")
for column in ("held_value", "pool", "source_group", "row_kind", "rows_full",
               "rows_observable", "rows_masked"):
    if column not in sens.columns:
        raise SystemExit(f"sensitivity audit missing column: {column}")

# Run-grounded expected fit composition (ledger section 18, 2026-07-29).
# AMD 154917 actually fit the raw51 core on support_train + id_calib + ood_val.
# The earlier 0/8682/0 expectation came from the planning document and was
# falsified by the run's own immutable audits.
EXPECTED_GLOBAL_FIT_ROLES = {
    "support_train": 385,
    "id_calib": 809,
    "ood_val": 2604,
    "ood_stress": 0,
}
role_usage_path = root / "ckbu_role_usage_audit.csv"
role_usage = pd.read_csv(role_usage_path)
required_role_columns = {
    "protocol_run",
    "role",
    "frame_phase",
    "m1_phase",
    "eligible_role_rows",
    "frozen_target_rows",
    "outside_frozen_target_cohort",
    "target_alignment_incomplete",
}
missing_role_columns = required_role_columns - set(role_usage.columns)
if missing_role_columns:
    raise SystemExit(
        f"role usage audit missing columns: {sorted(missing_role_columns)}"
    )
global_fit_roles = role_usage[
    (role_usage["protocol_run"] == "GLOBAL_ATTACK_PRESERVATION")
    & (role_usage["frame_phase"] == "fit")
    & (role_usage["m1_phase"] == "fit")
    & (role_usage["role"].isin(EXPECTED_GLOBAL_FIT_ROLES))
].copy()
observed_global_fit_roles = {}
for role, expected in EXPECTED_GLOBAL_FIT_ROLES.items():
    rows = global_fit_roles[global_fit_roles["role"] == role]
    if len(rows) != 1:
        raise SystemExit(
            f"expected one GLOBAL fit role audit row for {role}; got {len(rows)}"
        )
    row = rows.iloc[0]
    actual = tuple(
        int(float(row[column]))
        for column in (
            "eligible_role_rows",
            "frozen_target_rows",
            "outside_frozen_target_cohort",
            "target_alignment_incomplete",
        )
    )
    if actual != (expected, expected, 0, 0):
        raise SystemExit(
            f"GLOBAL fit role provenance drift for {role}: "
            f"{actual} != {(expected, expected, 0, 0)}"
        )
    observed_global_fit_roles[role] = expected
role_usage_sha256 = sha256_file(role_usage_path)

EXPECTED_PROTOCOLS = {
    "GLOBAL_ATTACK_PRESERVATION",
    "iotsim-ip-camera-street",
    "iotsim-predictive-maintenance",
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
}
EXPECTED_POOLS = {
    "core_fit_benign",
    "core_select_benign",
    "core_ood_val_select",
    "aux_fit_benign",
    "aux_select_benign",
    "ton_fit_benign",
    "ton_select_benign",
    "strict_eval",
}
observed_protocols = set(sens["held_value"].astype(str))
if observed_protocols != EXPECTED_PROTOCOLS:
    raise SystemExit(
        f"sensitivity protocol coverage drift: {sorted(observed_protocols)}"
    )

composition = sens[sens["row_kind"].isin({"per_source", "pool_total"})].copy()
for column in ("rows_full", "rows_observable", "rows_masked"):
    composition[column] = pd.to_numeric(composition[column], errors="coerce")
    if (
        composition[column].isna().any()
        or (composition[column] < 0).any()
        or (composition[column] % 1 != 0).any()
    ):
        raise SystemExit(f"invalid sensitivity count column: {column}")
if not (
    composition["rows_full"]
    == composition["rows_observable"] + composition["rows_masked"]
).all():
    raise SystemExit("sensitivity rows_full != rows_observable + rows_masked")

pool_totals = composition[composition["row_kind"] == "pool_total"]
observed_total_keys = set(
    zip(pool_totals["held_value"].astype(str), pool_totals["pool"].astype(str))
)
expected_total_keys = {
    (protocol, pool)
    for protocol in EXPECTED_PROTOCOLS
    for pool in EXPECTED_POOLS
}
if observed_total_keys != expected_total_keys or len(pool_totals) != len(expected_total_keys):
    missing_keys = sorted(expected_total_keys - observed_total_keys)
    extra_keys = sorted(observed_total_keys - expected_total_keys)
    raise SystemExit(
        f"sensitivity pool_total coverage drift: missing={missing_keys} extra={extra_keys}"
    )

for (protocol, pool), total in pool_totals.groupby(["held_value", "pool"], sort=True):
    if len(total) != 1:
        raise SystemExit(f"duplicated pool_total: {protocol}/{pool}")
    total = total.iloc[0]
    per_source = composition[
        (composition["held_value"] == protocol)
        & (composition["pool"] == pool)
        & (composition["row_kind"] == "per_source")
    ]
    expected = (
        int(total["rows_full"]),
        int(total["rows_observable"]),
        int(total["rows_masked"]),
    )
    actual = tuple(
        int(per_source[column].sum())
        for column in ("rows_full", "rows_observable", "rows_masked")
    )
    if actual != expected:
        raise SystemExit(
            f"per-source sensitivity reconciliation failed for {protocol}/{pool}: "
            f"{actual} != {expected}"
        )
    if expected[0] > 0 and per_source.empty:
        raise SystemExit(f"non-empty pool has no per-source rows: {protocol}/{pool}")

gate_columns = (
    "c1_hard_full",
    "c1_hard_observable",
    "c1_hard_rate_full",
    "c1_hard_rate_observable",
    "c1_frozen_prediction_rows",
    "c1_threshold_only_ton_rows",
    "c1_ton_policy",
    "process_gate_threshold_extra",
    "process_gate_threshold_tabm",
    "masked_are_fail_closed",
)
for column in gate_columns:
    if column not in sens.columns:
        raise SystemExit(f"sensitivity gate audit missing column: {column}")
gate_rows = sens[sens["row_kind"] == "select_c1_gate"].copy()
if (
    len(gate_rows) != len(EXPECTED_PROTOCOLS)
    or set(gate_rows["held_value"].astype(str)) != EXPECTED_PROTOCOLS
    or not (gate_rows["source_group"].astype(str) == "__ALL__").all()
):
    raise SystemExit("select_c1_gate must have exactly one __ALL__ row per protocol")
for column in gate_columns:
    if gate_rows[column].isna().any():
        raise SystemExit(f"select_c1_gate contains null values: {column}")
for _, gate in gate_rows.iterrows():
    full = int(gate["rows_full"])
    observable = int(gate["rows_observable"])
    hard_full = int(gate["c1_hard_full"])
    hard_observable = int(gate["c1_hard_observable"])
    frozen_rows = int(gate["c1_frozen_prediction_rows"])
    ton_rows = int(gate["c1_threshold_only_ton_rows"])
    masked = int(gate["rows_masked"])
    if masked != 0 or full != observable:
        raise SystemExit(
            "fit-only raw51 mask leaked into select C1 gate audit: "
            f"full={full} observable={observable} masked={masked}"
        )
    if not (0 <= hard_full <= full and 0 <= hard_observable <= observable):
        raise SystemExit(f"invalid select C1 hard counts: {gate.to_dict()}")
    if frozen_rows + ton_rows != full or ton_rows != 4000:
        raise SystemExit(
            f"select C1 provenance boundary drift: frozen={frozen_rows} "
            f"ton_threshold_only={ton_rows} full={full}"
        )
    if gate["c1_ton_policy"] != "conservative_all_hard_no_frozen_ckbq":
        raise SystemExit(f"select C1 ToN policy drift: {gate['c1_ton_policy']}")
    expected_full_rate = round(hard_full / full, 6) if full else 0.0
    expected_observable_rate = (
        round(hard_observable / observable, 6) if observable else 0.0
    )
    if (
        abs(float(gate["c1_hard_rate_full"]) - expected_full_rate) > 1e-6
        or abs(
            float(gate["c1_hard_rate_observable"]) - expected_observable_rate
        ) > 1e-6
    ):
        raise SystemExit(f"select C1 rate/count mismatch: {gate.to_dict()}")
    for column in ("process_gate_threshold_extra", "process_gate_threshold_tabm"):
        value = float(gate[column])
        if not np.isfinite(value) or not 0.0 <= value <= 1.0:
            raise SystemExit(f"invalid process gate threshold {column}={value}")
    if str(gate["masked_are_fail_closed"]).strip().lower() not in {
        "true", "1"
    }:
        raise SystemExit("masked rows are not fail-closed in select C1 gate audit")

# Run-grounded raw51 fit/mask closure (ledger section 18, 2026-07-29).
# AMD 154917's immutable audits prove the 1,353 masked rows act at target
# materialization only; every emitted pool is fully observable; the raw51
# core fit consumed support_train(385) + id_calib(809) + ood_val(2,604).
GLOBAL_PROTOCOL = "GLOBAL_ATTACK_PRESERVATION"


def _single_row(frame, *, pool, row_kind, source_group=None):
    rows = frame[
        (frame["held_value"] == GLOBAL_PROTOCOL)
        & (frame["pool"] == pool)
        & (frame["row_kind"] == row_kind)
    ]
    if source_group is not None:
        rows = rows[rows["source_group"] == source_group]
    if len(rows) != 1:
        raise SystemExit(
            f"expected exactly one {pool}/{row_kind} row"
            + (f" for {source_group}" if source_group else "")
            + f"; got {len(rows)}"
        )
    return rows.iloc[0]


def _counts(row):
    return (
        int(row["rows_full"]),
        int(row["rows_observable"]),
        int(row["rows_masked"]),
    )


id_calib_fit = _counts(
    _single_row(sens, pool="core_id_calib_fit", row_kind="role_split")
)
if id_calib_fit != (809, 809, 0):
    raise SystemExit(
        f"core id_calib fit split drift: {id_calib_fit} != (809, 809, 0)"
    )
ood_val_fit = _counts(
    _single_row(sens, pool="core_ood_val_fit", row_kind="role_split")
)
if ood_val_fit != (2604, 2604, 0):
    raise SystemExit(
        f"core ood_val fit split drift: {ood_val_fit} != (2604, 2604, 0)"
    )
core_fit = _counts(
    _single_row(sens, pool="core_fit_benign", row_kind="pool_total")
)
if (
    id_calib_fit[0] + ood_val_fit[0] != core_fit[0]
    or id_calib_fit[1] + ood_val_fit[1] != core_fit[1]
    or core_fit != (3413, 3413, 0)
):
    raise SystemExit(
        "role-split rows do not close against core_fit_benign: "
        f"{id_calib_fit} + {ood_val_fit} != {core_fit}"
    )
core_select = _counts(
    _single_row(sens, pool="core_ood_val_select", row_kind="pool_total")
)
if core_select != (0, 0, 0):
    raise SystemExit(
        f"fit-only ood_val rows leaked into select: {core_select} != (0, 0, 0)"
    )

# No emitted pool row may carry masked rows: the mask lives only at target
# materialization (already numerically validated composition frame).
if (composition["rows_masked"] != 0).any():
    raise SystemExit("masked rows appeared inside an emitted pool")

materialization = sens[sens["row_kind"] == "target_materialization"].copy()
materialization["rows_masked"] = pd.to_numeric(
    materialization["rows_masked"], errors="coerce"
)
masked_sources = set(
    materialization[
        (materialization["rows_masked"] > 0)
        & (materialization["source_group"] != "__ALL__")
    ]["source_group"].astype(str)
)
if masked_sources != {RAW51_MASK_SOURCE}:
    raise SystemExit(f"sensitivity masked source drift: {masked_sources}")
all_materialization = _counts(
    _single_row(
        sens,
        pool="raw51_target_materialization",
        row_kind="target_materialization",
        source_group="__ALL__",
    )
)
expected_materialization = (325067, 325067 - RAW51_MASK_TOTAL, RAW51_MASK_TOTAL)
if all_materialization != expected_materialization:
    raise SystemExit(
        f"raw51 target materialization drift: {all_materialization} != "
        f"{expected_materialization}"
    )
masked_materialization = _counts(
    _single_row(
        sens,
        pool="raw51_target_materialization",
        row_kind="target_materialization",
        source_group=RAW51_MASK_SOURCE,
    )
)
if masked_materialization != (RAW51_MASK_TOTAL, 0, RAW51_MASK_TOTAL):
    raise SystemExit(
        f"hydraulic-1 materialization drift: {masked_materialization}"
    )

attack = pd.read_csv(root / "attack_preservation_summary.csv")
overall = attack[attack["metric"] == "overall_attack_hard_recall"]
for candidate in ("M0-C1", "M4-CKBQ-TabMProcessRescue"):
    for suffix in ("", "-raw51obs"):
        name = candidate + suffix
        if not (overall["candidate"] == name).any():
            raise SystemExit(f"attack preservation missing candidate: {name}")
    full_rows = int(overall[overall["candidate"] == candidate]["rows"].iloc[0])
    obs_rows = int(overall[overall["candidate"] == candidate + "-raw51obs"]["rows"].iloc[0])
    if full_rows != obs_rows:
        raise SystemExit(
            f"attack denominator changed under mask for {candidate}: "
            f"{full_rows} != {obs_rows}"
        )

member_rows = ckbv.read_csv_rows(root / "ckbv_gotham_member_plan.csv")
member_sha = ckbv.ckbu.sha256_file(root / "ckbv_gotham_member_plan.csv")
invalid_members = [
    f"{row['member_index']}:{reason}"
    for row in member_rows
    for valid, reason in [
        ckbv.validate_member_pair(row, root / "gotham_member_cache", member_sha)
    ]
    if not valid
]
if invalid_members:
    raise SystemExit(f"invalid member checkpoints: {invalid_members[:8]}")

source_rows = ckbv.read_csv_rows(root / "ckbu_gotham_source_plan.csv")
invalid_sources = [
    f"{row['source_group']}:{reason}"
    for row in source_rows
    for valid, reason in [
        ckbv.validate_source_pair(row, root / "gotham_causal_cache")
    ]
    if not valid
]
if invalid_sources:
    raise SystemExit(f"invalid source checkpoints: {invalid_sources[:8]}")

ton_names = [
    name
    for name, role in ckbv.ckbu.TON_PILOT_FILES.items()
    if role != "reserved_internal_report_no_model_use"
]
ton_root = data_root / "external/ton_iot_raw_network/raw_pcap_pilot_v1"
ton_extracted = data_root / "external/ton_iot_raw_network/extracted"
ckbt_manifest = code_root.parents[1] / (
    "runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/"
    "aux_process_support_candidate_manifest.csv"
)
if not ckbt_manifest.is_file():
    raise SystemExit(f"missing immutable CKBT manifest: {ckbt_manifest}")
connection_targets = ckbv.ckbu.load_ton_connection_targets(
    ckbt_manifest, ton_extracted
)
invalid_ton = []
for name in ton_names:
    role = ckbv.ckbu.TON_PILOT_FILES[name]
    path = ton_root / name
    expected = len(connection_targets[name]) if name in connection_targets else 4000
    valid, reason = ckbv.validate_ton_file_pair(
        root / "ton_file_cache", name, path, role, expected
    )
    if not valid:
        invalid_ton.append(f"{name}:{reason}")
if invalid_ton:
    raise SystemExit(f"invalid ToN file checkpoints: {invalid_ton}")

if int(checkpoint.get("materialized_member_caches", 0)) > 0:
    projection_path = root / "ckbv_throughput_projection.json"
    if not projection_path.is_file():
        raise SystemExit("missing throughput projection")
    projection = json.loads(projection_path.read_text())
    if projection.get("projection_pass") is not True:
        raise SystemExit(f"throughput projection failed: {projection}")

for name, expected in (
    ("ckbv_source_reuse_audit.csv", 30),
    ("ckbv_source_aggregation_audit.csv", 30),
    ("ckbu_auxiliary_parallel_reuse_audit.csv", 31),
):
    frame = pd.read_csv(root / name)
    if len(frame) != expected or frame.source_group.nunique() != expected:
        raise SystemExit(f"audit coverage drift: {name}")

support = pd.read_csv(root / "ckbu_support_training_usage.csv")
tabm = support[support.candidate.eq("H2-TabMProcessHead")]
if (
    len(tabm) != 385
    or tabm.uid.nunique() != 385
    or not tabm.used_at_least_once_each_epoch.astype(bool).all()
):
    raise SystemExit("385-row support usage contract failed")

review = pd.read_csv(root / "ckbu_review_audit.csv")
if int(review.review_count.sum()) or float(review.review_rate.max()) != 0.0:
    raise SystemExit("review is not zero")

environment = json.loads((root / "ckbu_environment.json").read_text())
if (
    str(environment.get("slurm_job_id")) != job
    or environment.get("slurm_partition") != partition
    or environment.get("commit_sha") != commit_sha
):
    raise SystemExit("job identity drift")
if (
    not str(environment.get("raw51_observable_mask", "")).endswith(
        "raw51_observable_v1_mask.csv"
    )
    or environment.get("raw51_observable_mask_sha256") != RAW51_MASK_SHA256
    or environment.get("raw51_frozen_targets") != 325067
    or environment.get("raw51_masked_targets") != RAW51_MASK_TOTAL
    or environment.get("raw51_observable_targets") != 325067 - RAW51_MASK_TOTAL
    or environment.get("raw51_masked_source") != RAW51_MASK_SOURCE
):
    raise SystemExit("environment raw51 provenance drift")
if not str(environment.get("tshark", "")).startswith(
    "TShark (Wireshark) 4.6.6"
):
    raise SystemExit(f"TShark version drift: {environment.get('tshark')}")

recovery = None
if postformal_recovery:
    recovery = json.loads((root / "ckbv_postformal_recovery.json").read_text())
    environment_mask = recovery.get("environment_mask", {})
    if (
        recovery.get("status") != "CKBV_POSTFORMAL_RUN_GROUNDED_RECOVERY"
        or recovery.get("source_job_id") != job
        or recovery.get("source_partition") != partition
        or recovery.get("models_retrained") is not False
        or recovery.get("pcap_redecoded") is not False
        or recovery.get("scores_or_gates_changed") is not False
        or recovery.get("scientific_hashes_unchanged") is not True
        or recovery.get("id_calib_fit_full") != 809
        or recovery.get("id_calib_fit_observable") != 809
        or recovery.get("id_calib_fit_masked") != 0
        or recovery.get("ood_val_fit_full") != 2604
        or recovery.get("ood_val_fit_observable") != 2604
        or recovery.get("ood_val_fit_masked") != 0
        or recovery.get("fit_benign_full") != 3413
        or recovery.get("fit_benign_observable") != 3413
        or recovery.get("fit_benign_masked") != 0
        or recovery.get("select_pool_full") != 0
        or recovery.get("select_pool_observable") != 0
        or recovery.get("select_pool_masked") != 0
        or recovery.get("target_materialization_full") != 325067
        or recovery.get("target_materialization_observable")
        != 325067 - RAW51_MASK_TOTAL
        or recovery.get("target_materialization_masked") != RAW51_MASK_TOTAL
        or recovery.get("raw51_masked_source") != RAW51_MASK_SOURCE
        or environment_mask.get("raw51_frozen_targets") != 325067
        or environment_mask.get("raw51_observable_targets")
        != 325067 - RAW51_MASK_TOTAL
        or environment_mask.get("raw51_masked_targets") != RAW51_MASK_TOTAL
        or environment_mask.get("raw51_masked_source") != RAW51_MASK_SOURCE
        or environment_mask.get("raw51_observable_mask_sha256")
        != RAW51_MASK_SHA256
        or recovery.get("fit_role_rows") != observed_global_fit_roles
        or recovery.get("role_usage_audit_sha256") != role_usage_sha256
    ):
        raise SystemExit(f"invalid post-formal recovery contract: {recovery}")
    backup = (
        root
        / "ckbu_raw51_mask_sensitivity_audit.pre_pool_semantic_recovery.csv"
    )
    if not backup.is_file() or not backup.stat().st_size:
        raise SystemExit("post-formal recovery is missing immutable audit backup")
    if (
        recovery.get("audit_sha256_before") != sha256_file(backup)
        or recovery.get("audit_sha256_after")
        != sha256_file(root / "ckbu_raw51_mask_sensitivity_audit.csv")
    ):
        raise SystemExit("post-formal audit before/after hash mismatch")
    scientific_files = {
        "ckbu_single_seed_go_no_go.json",
        "attack_preservation_summary.csv",
        "strict_level2_summary.csv",
        "ckbu_candidate_selection.csv",
        "ckbu_support_training_usage.csv",
        "ckbu_role_usage_audit.csv",
        "ckbu_record_predictions.csv.gz",
        "ckbu_review_audit.csv",
        "ckbu_environment.json",
        "run_spec.json",
        "codex_readout.md",
    }
    recorded_hashes = recovery.get("scientific_hashes", {})
    if set(recorded_hashes) != scientific_files:
        raise SystemExit("post-formal scientific hash inventory drift")
    actual_hashes = {
        name: sha256_file(root / name) for name in sorted(scientific_files)
    }
    if recorded_hashes != actual_hashes:
        raise SystemExit("scientific outputs changed after post-formal recovery")

identity = {}
for line in (root / "slurm_identity.txt").read_text().splitlines():
    key, separator, value = line.partition("=")
    if separator:
        identity[key] = value
if (
    identity.get("job_id") != job
    or identity.get("partition") != partition
    or identity.get("commit_sha") != commit_sha
):
    raise SystemExit(f"launcher identity drift: {identity}")

timing = {}
for line in (root / "run_timing.txt").read_text().splitlines():
    key, separator, value = line.partition("=")
    if separator:
        timing[key] = value
if (
    timing.get("job_id") != job
    or timing.get("partition") != partition
    or int(timing.get("wall_seconds", "0")) <= 0
):
    raise SystemExit(f"runtime timing audit failed: {timing}")

run_spec = json.loads((root / "run_spec.json").read_text())
frontend = run_spec.get("unified_frontend", {})
raw51_spec = run_spec.get("raw51_observable_v1", {})
if (
    run_spec.get("original_1m_split_modified") is not False
    or run_spec.get("review_rate") != 0.0
    or run_spec.get("per_family_experts") != 0
    or frontend.get("feature_dim") != 51
    or frontend.get("score_before_update") is not True
    or frontend.get("raw_label_column_read") is not False
):
    raise SystemExit("frozen formal run specification drift")
if (
    not str(raw51_spec.get("mask_path", "")).endswith(
        "raw51_observable_v1_mask.csv"
    )
    or raw51_spec.get("mask_sha256") != RAW51_MASK_SHA256
    or raw51_spec.get("frozen_targets") != 325067
    or raw51_spec.get("masked_targets") != RAW51_MASK_TOTAL
    or raw51_spec.get("observable_targets") != 325067 - RAW51_MASK_TOTAL
    or raw51_spec.get("masked_source") != RAW51_MASK_SOURCE
    or raw51_spec.get("masked_rows_are_fail_closed") is not True
    or raw51_spec.get("frozen_manifest_unchanged") is not True
):
    raise SystemExit("run_spec raw51 provenance drift")

validation = {
    "status": "CKBV_RESULT_VALID",
    "scientific_decision": decision["decision"],
    "partition": partition,
    "job_id": job,
    "commit_sha": commit_sha,
    "tshark": environment["tshark"],
    "wall_seconds": int(timing["wall_seconds"]),
    "gotham_sources": gotham["sources"],
    "gotham_targets": gotham["targets"],
    "gotham_frozen_targets": 325067,
    "raw51_masked_targets_total": gotham.get("raw51_masked_targets_total"),
    "raw51_observable_mask_sha256": gotham.get("raw51_observable_mask_sha256"),
    "gotham_members": len(member_rows),
    "auxiliary_sources": auxiliary["sources"],
    "ton_file_checkpoints": len(ton_names),
    "ton_rows": ton["rows"],
    "support_rows_used": len(tabm),
    "review_rate": 0.0,
    "scientific_protocol_changed": False,
    "source_slurm_state": slurm_state,
    "postformal_recovery": postformal_recovery,
    "models_retrained_during_recovery": (
        recovery.get("models_retrained") if recovery is not None else None
    ),
    "scores_or_gates_changed_during_recovery": (
        recovery.get("scores_or_gates_changed") if recovery is not None else None
    ),
}
(root / "ckbv_result_validation.json").write_text(
    json.dumps(validation, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(json.dumps(validation, indent=2, sort_keys=True))
PY

rm -f "$ARCHIVE" "$ARCHIVE.sha256"
tar -C "$RUN_ROOT" -czf "$ARCHIVE" \
  --exclude='gotham_causal_cache' \
  --exclude='gotham_member_cache' \
  --exclude='auxiliary_causal_cache' \
  --exclude='ton_file_cache' \
  --exclude='source_runtime' \
  --exclude='member_logs' \
  --exclude='ton_file_logs' \
  --exclude='auxiliary_worker' \
  .
cd "$BASE/runs"
sha256sum "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256"
sha256sum -c "$(basename "$ARCHIVE").sha256"
echo "CKBV_PULLBACK_ARCHIVE=$ARCHIVE"
