"""issue27ckas: chronology and mechanism-coverage gate for Level-2 repair.

This is deliberately a data/representation gate, not another detector.  It
answers two prerequisites for a new event-level open-world IDS route:

1. Can raw Gotham rows be replayed in a label-free, deterministic chronology
   for each capture/source group?
2. Does the legal fit contract contain enough cross-environment support for a
   proposed attack-mechanism representation to be trained honestly?

No report/query/future/sealed label is read.  Report rows may be inspected only
for raw timestamp/schema coverage; they never affect the chronology policy,
mechanism mapping, model fitting, thresholding, or any GO decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckai_external_flow_feature_probe_v1 as ckai  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckas_chronology_and_mechanism_coverage_gate_v1_2026-07-10"
OUT_BASE = cko.ROOT / "runs" / ISSUE
WINDOW_ROWS = 128
CANARY_FAMILIES = {
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
    "domotic-monitor",
    "combined-cycle",
    "iotsim-ip-camera-street",
}
RAW_USECOLS = {
    "frame.time",
    "frame.protocols",
    "frame.len",
    "eth.src",
    "eth.dst",
    "ip.src",
    "ip.dst",
    "ip.proto",
    "tcp.srcport",
    "tcp.dstport",
    "udp.srcport",
    "udp.dstport",
}


def slug(text: Any) -> str:
    return "".join(ch if ch.isalnum() or ch in "_.-" else "_" for ch in str(text)).strip("_")[:100] or "empty"


def source_family(value: Any) -> str:
    stem = Path(str(value)).stem
    while stem and stem[-1].isdigit():
        stem = stem[:-1]
    return stem.rstrip("-") or "NA"


def add_environment_columns(frame_by_role: dict[str, pd.DataFrame]) -> None:
    for frame in frame_by_role.values():
        source = frame.get("source_group", pd.Series(["NA"] * len(frame), index=frame.index)).astype(str)
        device = frame.get("device", pd.Series(["NA"] * len(frame), index=frame.index)).astype(str)
        source_families = source.map(source_family)
        device_families = device.map(source_family)
        frame["source_family"] = source_families
        frame["device_family"] = np.where(device_families.isin(["", "NA"]), source_families, device_families)


def stable_cap(indices: np.ndarray, cap: int) -> np.ndarray:
    indices = np.asarray(indices, dtype=np.int64)
    if cap <= 0 or len(indices) <= cap:
        return indices
    return np.unique(np.linspace(0, len(indices) - 1, num=cap, dtype=np.int64)).astype(np.int64)


def phase_indices(frame: pd.DataFrame, phase: str) -> np.ndarray:
    if phase == "all":
        return np.arange(len(frame), dtype=np.int64)
    return np.flatnonzero(frame["phase"].astype(str).to_numpy() == phase).astype(np.int64)


def raw_time_seconds(values: pd.Series) -> np.ndarray:
    parsed = pd.to_datetime(values, utc=True, errors="coerce")
    if int(parsed.notna().sum()) == 0:
        numeric = pd.to_numeric(values, errors="coerce").to_numpy(dtype=np.float64)
        return numeric
    seconds = parsed.astype("int64", copy=False).to_numpy(dtype=np.float64) / 1e9
    seconds[parsed.isna().to_numpy()] = np.nan
    return seconds


def coalesce(a: Any, b: Any, fallback: str) -> str:
    for value in (a, b):
        text = "" if pd.isna(value) else str(value)
        if text and text.lower() != "nan":
            return text
    return fallback


def port_arrays(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    tcp_src = cko.safe_num(frame.get("tcp.srcport", pd.Series(0, index=frame.index)), 0.0)
    tcp_dst = cko.safe_num(frame.get("tcp.dstport", pd.Series(0, index=frame.index)), 0.0)
    udp_src = cko.safe_num(frame.get("udp.srcport", pd.Series(0, index=frame.index)), 0.0)
    udp_dst = cko.safe_num(frame.get("udp.dstport", pd.Series(0, index=frame.index)), 0.0)
    return np.where(tcp_src > 0, tcp_src, udp_src).astype(np.int64), np.where(tcp_dst > 0, tcp_dst, udp_dst).astype(np.int64)


def canonical_order(ts: np.ndarray) -> tuple[np.ndarray, int, int]:
    positions = np.arange(len(ts), dtype=np.int64)
    finite = np.isfinite(ts)
    valid_ts = ts[finite]
    violations = int(np.sum(np.diff(valid_ts) < -1e-9)) if len(valid_ts) >= 2 else 0
    missing = int(np.sum(~finite))
    keys = np.where(finite, ts, np.inf)
    order = np.lexsort((positions, keys)).astype(np.int64)
    return order, violations, missing


def collect_target_rows(
    frame_by_role: dict[str, pd.DataFrame],
    *,
    max_recorded_index: int,
    rows_per_source: int,
    source_cap: int,
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    specs = [
        ("support_train", "fit", "legal_fit"),
        ("id_calib", "fit", "legal_fit"),
        ("ood_val", "fit", "legal_fit"),
        ("ood_stress", "fit", "legal_fit"),
        ("id_calib", "select", "legal_select"),
        ("ood_val", "select", "legal_select"),
        ("ood_stress", "select", "legal_select"),
        ("support_val", "select", "legal_select"),
        ("same_file_query", "select", "report_only"),
        ("future_query", "select", "report_only"),
        ("sealed_final_ood", "all", "report_only"),
        ("sealed_final_attack", "all", "report_only"),
    ]
    rows: list[pd.DataFrame] = []
    usage: list[dict[str, Any]] = []
    for role, phase, use_class in specs:
        frame = frame_by_role[role]
        idx = phase_indices(frame, phase)
        part = frame.iloc[idx].copy()
        if max_recorded_index > 0 and "recorded_index" in part:
            recorded = pd.to_numeric(part["recorded_index"], errors="coerce").fillna(-1)
            part = part.loc[recorded <= max_recorded_index].copy()
        usage.append(
            {
                "role": role,
                "phase": phase,
                "use_class": use_class,
                "input_rows": int(len(idx)),
                "rows_after_recorded_index_cap": int(len(part)),
                "label_used": bool(role == "support_train" and use_class == "legal_fit"),
                "allowed_to_affect_gate": bool(use_class == "legal_fit"),
            }
        )
        if part.empty or "source_group" not in part or "recorded_index" not in part:
            continue
        rows.append(part[["source_group", "source_family", "device_family", "recorded_index"]].assign(role=role, phase=phase, use_class=use_class))
    if not rows:
        return {}, usage
    all_rows = pd.concat(rows, ignore_index=True)
    all_rows["recorded_index"] = pd.to_numeric(all_rows["recorded_index"], errors="coerce").fillna(-1).astype(int)
    all_rows = all_rows[all_rows["recorded_index"] >= 0].copy()
    # A generic priority sort can accidentally inspect several captures from the
    # same held family while omitting another.  This gate is specifically for
    # Level-2 canaries, so reserve one deterministic raw source per canary
    # family before filling the rest of the bounded audit budget.
    source_meta = (
        all_rows.groupby("source_group", sort=True)[["source_family", "device_family"]]
        .agg(lambda col: sorted(set(col.astype(str)))[0] if len(col) else "NA")
        .reset_index()
    )
    selected_sources: list[str] = []
    for family in sorted(CANARY_FAMILIES):
        candidates = source_meta.loc[
            source_meta["source_family"].astype(str).eq(family)
            | source_meta["device_family"].astype(str).eq(family),
            "source_group",
        ].astype(str).sort_values().tolist()
        if candidates:
            selected_sources.append(candidates[0])
    selected_sources = list(dict.fromkeys(selected_sources))
    remaining = [value for value in source_meta["source_group"].astype(str).sort_values().tolist() if value not in selected_sources]
    if source_cap > 0:
        # Canaries are mandatory evidence; a too-small cap may expand only up
        # to the number of available canary source groups.
        selected_sources = selected_sources + remaining[:max(0, source_cap - len(selected_sources))]
    else:
        selected_sources = selected_sources + remaining
    outputs: dict[str, pd.DataFrame] = {}
    for source, group in all_rows[all_rows["source_group"].astype(str).isin(selected_sources)].groupby("source_group", sort=True):
        group = group.sort_values(["recorded_index", "role", "phase"], kind="stable").drop_duplicates(["recorded_index"], keep="first")
        picks = stable_cap(np.arange(len(group), dtype=np.int64), rows_per_source)
        outputs[str(source)] = group.iloc[picks].reset_index(drop=True)
    return outputs, usage


def audit_raw_source(
    zip_path: Path,
    source_group: str,
    targets: pd.DataFrame,
    episode_seconds: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    max_recorded = int(pd.to_numeric(targets["recorded_index"], errors="coerce").max())
    with zipfile.ZipFile(zip_path) as zf:
        if source_group not in zf.namelist():
            return {
                "source_group": source_group,
                "raw_member_found": False,
                "requested_target_rows": int(len(targets)),
                "max_recorded_index": max_recorded,
                "chronology_status": "MISSING_RAW_MEMBER",
            }, []
        with zf.open(source_group) as handle:
            frame = pd.read_csv(handle, usecols=lambda name: name in RAW_USECOLS, nrows=max_recorded + 1, low_memory=False)
    if len(frame) <= max_recorded:
        return {
            "source_group": source_group,
            "raw_member_found": True,
            "requested_target_rows": int(len(targets)),
            "max_recorded_index": max_recorded,
            "processed_prefix_rows": int(len(frame)),
            "chronology_status": "RECORDED_INDEX_OUT_OF_RANGE",
        }, []

    ts = raw_time_seconds(frame.get("frame.time", pd.Series(np.nan, index=frame.index)))
    order, violations, missing_ts = canonical_order(ts)
    rank = np.empty(len(order), dtype=np.int64)
    rank[order] = np.arange(len(order), dtype=np.int64)
    src_values = frame.get("ip.src", pd.Series("", index=frame.index)).to_numpy()
    dst_values = frame.get("ip.dst", pd.Series("", index=frame.index)).to_numpy()
    eth_src_values = frame.get("eth.src", pd.Series("", index=frame.index)).to_numpy()
    eth_dst_values = frame.get("eth.dst", pd.Series("", index=frame.index)).to_numpy()
    proto_values = cko.safe_num(frame.get("ip.proto", pd.Series(0, index=frame.index)), 0.0).astype(np.int64)
    sport_values, dport_values = port_arrays(frame)
    protocol_text = frame.get("frame.protocols", pd.Series("", index=frame.index)).astype(str).to_numpy()
    rows: list[dict[str, Any]] = []
    target_index_set = set(pd.to_numeric(targets["recorded_index"], errors="coerce").astype(int).tolist())
    for recorded_index in sorted(target_index_set):
        canonical_index = int(rank[recorded_index])
        start = max(0, canonical_index - WINDOW_ROWS)
        prior = order[start:canonical_index]
        src = coalesce(src_values[recorded_index], eth_src_values[recorded_index], f"row{recorded_index}:src")
        dst = coalesce(dst_values[recorded_index], eth_dst_values[recorded_index], f"row{recorded_index}:dst")
        prior_src = np.asarray([coalesce(src_values[i], eth_src_values[i], f"row{i}:src") for i in prior], dtype=object)
        same_src = prior[prior_src == src]
        prior_dst = [coalesce(dst_values[i], eth_dst_values[i], f"row{i}:dst") for i in same_src]
        prior_ports = dport_values[same_src] if len(same_src) else np.asarray([], dtype=np.int64)
        current_ts = float(ts[recorded_index]) if np.isfinite(ts[recorded_index]) else float("nan")
        if math.isfinite(current_ts) and episode_seconds > 0:
            bucket = int(math.floor(current_ts / episode_seconds))
            episode_basis = f"time:{bucket}"
        else:
            bucket = canonical_index // WINDOW_ROWS
            episode_basis = f"rank:{bucket}"
        episode_id = hashlib.sha256(f"{source_group}|{src}|{episode_basis}".encode("utf-8")).hexdigest()[:20]
        rows.append(
            {
                "source_group": source_group,
                "recorded_index": int(recorded_index),
                "canonical_index": canonical_index,
                "frame_time_seconds": current_ts,
                "entity": src,
                "peer": dst,
                "ip_proto": int(proto_values[recorded_index]),
                "src_port": int(sport_values[recorded_index]),
                "dst_port": int(dport_values[recorded_index]),
                "protocols": str(protocol_text[recorded_index]),
                "episode_id": episode_id,
                "episode_basis": episode_basis,
                "prior_window_rows": int(len(prior)),
                "prior_entity_rows": int(len(same_src)),
                "prior_entity_unique_dst": int(len(set(prior_dst))),
                "prior_entity_unique_dst_port": int(len(set(prior_ports.tolist()))),
                "warmup_ready": bool(len(same_src) >= 16),
            }
        )
    status = "RECORDED_ORDER_MONOTONIC" if violations == 0 and missing_ts == 0 else "CANONICAL_TIMESTAMP_SORT_REQUIRED"
    return {
        "source_group": source_group,
        "raw_member_found": True,
        "requested_target_rows": int(len(targets)),
        "max_recorded_index": max_recorded,
        "processed_prefix_rows": int(len(frame)),
        "timestamp_parse_failures": int(missing_ts),
        "recorded_order_timestamp_violations": int(violations),
        "chronology_status": status,
        "canonical_sort_policy": "timestamp_ascending_then_recorded_index_stable; missing_timestamp_last",
    }, rows


def mechanism_coverage(frame_by_role: dict[str, pd.DataFrame], min_attack_rows: int, min_benign_rows: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    attack = frame_by_role["support_train"].copy()
    attack = attack[attack["phase"].astype(str) == "fit"].copy()
    attack["mechanism"] = attack.get("attack_label", pd.Series("", index=attack.index)).map(ckai.coarse_attack_family)
    attack["kind"] = "attack_support"
    benign_parts: list[pd.DataFrame] = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        part = frame_by_role[role]
        benign_parts.append(part[part["phase"].astype(str) == "fit"].copy().assign(kind="benign_fit"))
    benign = pd.concat(benign_parts, ignore_index=True)
    environments = sorted(set(attack["source_family"].astype(str)).union(benign["source_family"].astype(str)))
    mechanisms = sorted(value for value in attack["mechanism"].astype(str).unique().tolist() if value not in {"", "benign_or_empty"})
    rows: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for mechanism in mechanisms:
        balanced_envs = 0
        attack_envs = 0
        for environment in environments:
            attack_rows = int(len(attack[(attack["mechanism"] == mechanism) & (attack["source_family"].astype(str) == environment)]))
            benign_rows = int(len(benign[benign["source_family"].astype(str) == environment]))
            attack_present = attack_rows >= int(min_attack_rows)
            benign_present = benign_rows >= int(min_benign_rows)
            if attack_present:
                attack_envs += 1
            if attack_present and benign_present:
                balanced_envs += 1
            rows.append(
                {
                    "mechanism": mechanism,
                    "environment_field": "source_family",
                    "environment": environment,
                    "attack_support_rows": attack_rows,
                    "benign_fit_rows": benign_rows,
                    "attack_support_sufficient": attack_present,
                    "benign_context_sufficient": benign_present,
                    "eligible_cross_environment_cell": bool(attack_present and benign_present),
                }
            )
        summary.append(
            {
                "mechanism": mechanism,
                "attack_environment_count": attack_envs,
                "balanced_environment_count": balanced_envs,
                "attack_support_total": int((attack["mechanism"] == mechanism).sum()),
                "prototype_supcon_status": "eligible_cross_environment_attack_support" if attack_envs >= 2 else "insufficient_cross_environment_attack_support",
                "worst_group_status": "eligible_balanced_environment_constraint" if balanced_envs >= 2 else "not_eligible_balanced_environment_constraint",
            }
        )
    return rows, summary


def build_readout(
    chronology_rows: list[dict[str, Any]],
    mechanism_rows: list[dict[str, Any]],
    episode_rows: list[dict[str, Any]],
    gate: str,
    seconds: float,
) -> list[str]:
    sources = len(chronology_rows)
    canonical_required = sum(row.get("chronology_status") == "CANONICAL_TIMESTAMP_SORT_REQUIRED" for row in chronology_rows)
    missing_raw = sum(not bool(row.get("raw_member_found", False)) for row in chronology_rows)
    prototype_eligible = sum(row.get("prototype_supcon_status") == "eligible_cross_environment_attack_support" for row in mechanism_rows)
    worst_group_eligible = sum(row.get("worst_group_status") == "eligible_balanced_environment_constraint" for row in mechanism_rows)
    warm = sum(bool(row.get("warmup_ready", False)) for row in episode_rows)
    return [
        f"# {ISSUE}",
        "",
        "## Verdict",
        "",
        f"`{gate}`",
        "",
        "## Chronology audit",
        "",
        f"- Audited source groups: `{sources}`.",
        f"- Canonical timestamp replay required: `{canonical_required}`.",
        f"- Missing raw members: `{missing_raw}`.",
        f"- Episode manifest rows: `{len(episode_rows)}`; warmup-ready rows: `{warm}`.",
        "",
        "## Mechanism coverage",
        "",
        f"- Mechanisms eligible for cross-environment attack prototype/SupCon: `{prototype_eligible}` / `{len(mechanism_rows)}`.",
        f"- Mechanisms eligible for a balanced-environment GroupDRO/REx constraint: `{worst_group_eligible}` / `{len(mechanism_rows)}`.",
        "",
        "## Boundary",
        "",
        "- No detector, threshold, model selection, or hyperparameter search is run.",
        "- Mechanism coverage reads labels only from `support_train` fit.",
        "- Report/query/future/sealed raw rows are timestamp/schema audit-only; their labels are never read.",
        "- A prototype/SupCon event-model smoke requires timestamp integrity and cross-environment attack support; GroupDRO/REx additionally requires balanced legal environments.",
        f"- Runtime seconds: `{seconds:.1f}`.",
    ]


def run(args: argparse.Namespace) -> None:
    started = time.time()
    smoke = not bool(args.full)
    out = OUT_BASE if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{args.run_tag}"
    out.mkdir(parents=True, exist_ok=True)
    _x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(smoke)
    add_environment_columns(frame_by_role)
    targets_by_source, role_usage = collect_target_rows(
        frame_by_role,
        max_recorded_index=int(args.max_recorded_index),
        rows_per_source=int(args.rows_per_source),
        source_cap=int(args.source_cap),
    )
    chronology_rows: list[dict[str, Any]] = []
    episode_rows: list[dict[str, Any]] = []
    for source_group, targets in targets_by_source.items():
        summary, episodes = audit_raw_source(cko.GOTHAM_ZIP, source_group, targets, int(args.episode_seconds))
        chronology_rows.append(summary)
        role_map = targets.set_index("recorded_index")
        for episode in episodes:
            target = role_map.loc[int(episode["recorded_index"])]
            episode["role"] = str(target["role"])
            episode["phase"] = str(target["phase"])
            episode["use_class"] = str(target["use_class"])
            episode["source_family"] = str(target["source_family"])
            episode["device_family"] = str(target["device_family"])
            episode_rows.append(episode)
    coverage_rows, mechanism_rows = mechanism_coverage(
        frame_by_role,
        min_attack_rows=int(args.min_attack_rows),
        min_benign_rows=int(args.min_benign_rows),
    )
    chronology_ok = bool(chronology_rows) and all(row.get("chronology_status") != "MISSING_RAW_MEMBER" and int(row.get("timestamp_parse_failures", 0)) == 0 for row in chronology_rows)
    prototype_eligible_mechanisms = sum(row.get("prototype_supcon_status") == "eligible_cross_environment_attack_support" for row in mechanism_rows)
    if not chronology_ok:
        gate = "BLOCKED_RAW_ALIGNMENT_OR_TIMESTAMP_PARSE"
    elif prototype_eligible_mechanisms < int(args.min_eligible_mechanisms):
        gate = "BLOCKED_INSUFFICIENT_CROSS_ENVIRONMENT_ATTACK_SUPPORT"
    elif not episode_rows:
        gate = "BLOCKED_NO_EPISODE_MANIFEST_ROWS"
    else:
        gate = "GO_EVENT_FRONTEND_SMOKE_WITH_CANONICAL_TIMESTAMP_REPLAY"
    seconds = time.time() - started
    cko.write_csv(out / "role_usage_audit.csv", role_usage)
    cko.write_csv(out / "chronology_source_audit.csv", chronology_rows)
    cko.write_csv(out / "mechanism_environment_coverage.csv", coverage_rows)
    cko.write_csv(out / "mechanism_coverage_summary.csv", mechanism_rows)
    cko.write_csv(out / "episode_manifest_preview.csv", episode_rows)
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "run_tag": args.run_tag,
            "full": bool(args.full),
            "max_recorded_index": int(args.max_recorded_index),
            "rows_per_source": int(args.rows_per_source),
            "source_cap": int(args.source_cap),
            "episode_seconds": int(args.episode_seconds),
            "min_attack_rows": int(args.min_attack_rows),
            "min_benign_rows": int(args.min_benign_rows),
            "min_eligible_mechanisms": int(args.min_eligible_mechanisms),
            "gate": gate,
            "data_use_boundary": {
                "mechanism_label_source": "support_train fit only",
                "report_raw_timestamp_schema_use": "audit only; no labels read",
                "query_future_sealed_used_for_fit_threshold_feature_selection": False,
            },
            "input_audit": input_audit,
            "seconds": seconds,
        },
    )
    cko.write_md(out / "codex_readout.md", build_readout(chronology_rows, mechanism_rows, episode_rows, gate, seconds))
    print(json.dumps({"status": "ok", "out": str(out), "gate": gate, "seconds": seconds}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Use full role frames; default uses upstream smoke frames.")
    parser.add_argument("--max-recorded-index", type=int, default=300000, help="0 means no recorded-index cap.")
    parser.add_argument("--rows-per-source", type=int, default=48)
    parser.add_argument("--source-cap", type=int, default=12)
    parser.add_argument("--episode-seconds", type=int, default=60)
    parser.add_argument("--min-attack-rows", type=int, default=4)
    parser.add_argument("--min-benign-rows", type=int, default=16)
    parser.add_argument("--min-eligible-mechanisms", type=int, default=2)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
