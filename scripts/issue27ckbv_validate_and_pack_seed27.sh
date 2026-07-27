#!/bin/bash
set -euo pipefail

BASE=${CKBV_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
DATA_ROOT=${CKBV_DATA_ROOT:-/public/home/jiangxinwei.zr/work/paper04/datasets}
PARTITION=${CKBV_PARTITION:?missing CKBV_PARTITION}
JOB_ID=${CKBV_JOB_ID:?missing CKBV_JOB_ID}
ALLOW_RUNNING=${CKBV_ALLOW_RUNNING:-0}
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
if test "$ALLOW_RUNNING" != 1; then
  state=$(sacct -j "$JOB_ID" -X -n -P --format=State |
    head -n 1 |
    cut -d'|' -f1 |
    sed 's/+.*//' |
    tr -d '[:space:]')
  test "$state" = COMPLETED || {
    echo "job is not COMPLETED: $state" >&2
    exit 2
  }
fi

python - "$RUN_ROOT" "$PARTITION" "$JOB_ID" "$CODE_ROOT" "$DATA_ROOT" \
  "$COMMIT_SHA" <<'PY'
import csv
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
sys.path.insert(0, str(code_root))

import issue27ckbv_checkpointed_sparse_process_frontend_v1 as ckbv

required = [
    "ckbu_single_seed_go_no_go.json",
    "attack_preservation_summary.csv",
    "strict_level2_summary.csv",
    "ckbu_candidate_selection.csv",
    "ckbu_support_training_usage.csv",
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
core = sens[
    (sens["held_value"] == "GLOBAL_ATTACK_PRESERVATION")
    & (sens["pool"] == "core_ood_val_select")
    & (sens["row_kind"] == "pool_total")
]
if len(core) != 1:
    raise SystemExit(f"core ood_val pool_total row missing/duplicated: {len(core)}")
row = core.iloc[0]
if (int(row["rows_full"]), int(row["rows_observable"]), int(row["rows_masked"])) != (
    8682, 7329, 1353
):
    raise SystemExit(
        f"core ood_val composition drift: {row['rows_full']}/"
        f"{row['rows_observable']}/{row['rows_masked']} != 8682/7329/1353"
    )
masked_sources = set(
    sens[(sens["row_kind"] == "per_source") & (sens["rows_masked"] > 0)]["source_group"]
)
if masked_sources != {RAW51_MASK_SOURCE}:
    raise SystemExit(f"sensitivity masked source drift: {masked_sources}")
core_masked = sens[
    (sens["source_group"] == RAW51_MASK_SOURCE)
    & (sens["pool"] == "core_ood_val_select")
    & (sens["row_kind"] == "per_source")
]
if len(core_masked) != 1 or int(core_masked.iloc[0]["rows_masked"]) != 1353:
    raise SystemExit("hydraulic-1 per-source masked count != 1353")

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
if not str(environment.get("tshark", "")).startswith(
    "TShark (Wireshark) 4.6.6"
):
    raise SystemExit(f"TShark version drift: {environment.get('tshark')}")

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
if (
    run_spec.get("original_1m_split_modified") is not False
    or run_spec.get("review_rate") != 0.0
    or run_spec.get("per_family_experts") != 0
    or frontend.get("feature_dim") != 51
    or frontend.get("score_before_update") is not True
    or frontend.get("raw_label_column_read") is not False
):
    raise SystemExit("frozen formal run specification drift")

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
