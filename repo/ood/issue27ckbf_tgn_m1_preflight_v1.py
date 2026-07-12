"""CKBF M1 preflight: executable role, cache, and process contract audit.

This is deliberately upstream of TGN training.  It reads the frozen role
manifests and CKBE cache only, and writes machine-readable evidence that M1
can exclude a held family from every fit/select use.  Raw packet labels are
never read from the source CSVs; attack labels here come solely from legal
role manifests for support supervision accounting.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckbf_tgn_m1_preflight_v1_2026-07-12"
ROOT = cko.ROOT
DEFAULT_OUT = ROOT / "runs" / ISSUE
DEFAULT_PLAN = ROOT / "runs" / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1" / "canonical_source_target_index.csv"
DEFAULT_T0 = ROOT / "_hpc_pullback" / "issue27ckbe_t0_150067" / "issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
HELD = ("iotsim-stream-consumer", "iotsim-hydraulic-system", "domotic-monitor", "combined-cycle", "iotsim-ip-camera-street")
FIT_ROLES = (("support_train", "fit"), ("id_calib", "fit"), ("ood_val", "fit"), ("ood_stress", "fit"))
SELECT_ROLES = (("support_val", "select"), ("id_calib", "select"), ("ood_val", "select"), ("ood_stress", "select"))


def cache_key(source: str) -> str:
    import hashlib
    return hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:20]


class T0Cache:
    """Read-only access to CKBE arrays; no labels belong to this cache."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.cache_dir = self.root / "tgn_event_cache"

    def paths(self, source: str) -> tuple[Path, Path]:
        key = cache_key(source)
        return self.cache_dir / f"{key}.npz", self.cache_dir / f"{key}.json"

    def summary(self, source: str) -> dict[str, Any]:
        npz, meta = self.paths(source)
        row: dict[str, Any] = {
            "source_group": source,
            "source_cache_key": cache_key(source),
            "npz_exists": npz.exists(),
            "cache_json_exists": meta.exists(),
        }
        if meta.exists():
            row.update(json.loads(meta.read_text(encoding="utf-8")))
        if npz.exists():
            with np.load(npz, allow_pickle=False) as data:
                row["event_rows"] = int(len(data["time_ms"]))
                row["target_rows_in_npz"] = int(len(data["target_recorded_index"]))
                row["target_positions_complete"] = bool(np.all(data["target_event_position"] >= 0))
                row["event_schema_dim"] = int(data["raw_msg"].shape[1])
        return row

    def target_positions(self, source: str) -> dict[int, int]:
        npz, _meta = self.paths(source)
        if not npz.exists():
            return {}
        with np.load(npz, allow_pickle=False) as data:
            return {
                int(recorded): int(position)
                for recorded, position in zip(data["target_recorded_index"].tolist(), data["target_event_position"].tolist())
            }


def role_rows(frames: dict[str, pd.DataFrame], role: str, phase: str) -> pd.DataFrame:
    frame = frames[role]
    if phase == "all":
        return frame.copy()
    return frame.loc[frame["phase"].astype(str).eq(phase)].copy()


def role_audit(frames: dict[str, pd.DataFrame], cache: T0Cache) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for role, frame in sorted(frames.items()):
        for phase in sorted(set(frame.get("phase", pd.Series(["all"])).astype(str))):
            part = role_rows(frames, role, phase)
            sources = sorted(set(part.get("source_group", pd.Series(dtype=str)).astype(str)))
            seen_sources.update(source for source in sources if source and source != "nan")
            labels = part.get("attack_label", pd.Series("", index=part.index)).astype(str)
            families = part.get("device_family", pd.Series("NA", index=part.index)).astype(str)
            rows.append({
                "role": role,
                "phase": phase,
                "target_rows": int(len(part)),
                "source_count": int(len(sources)),
                "device_family_count": int(families.nunique()),
                "attack_rows": int(labels.ne("").sum()),
                "benign_rows": int(labels.eq("").sum()),
                "attack_family_distribution": json.dumps(Counter(labels[labels.ne("")]).most_common(), ensure_ascii=False),
                "source_groups": json.dumps(sources, ensure_ascii=False),
            })
    cache_rows = [cache.summary(source) for source in sorted(seen_sources)]
    event_count = {str(row["source_group"]): int(row.get("event_rows", 0)) for row in cache_rows}
    for row in rows:
        sources = json.loads(row["source_groups"])
        row["event_rows_across_sources"] = int(sum(event_count.get(source, 0) for source in sources))
    return rows, cache_rows


def support_alignment(frames: dict[str, pd.DataFrame], cache: T0Cache) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role, phase in (("support_train", "fit"), ("support_val", "select")):
        part = role_rows(frames, role, phase)
        for source, group in part.groupby(part["source_group"].astype(str), sort=True):
            positions = cache.target_positions(str(source))
            indices = pd.to_numeric(group["recorded_index"], errors="coerce").fillna(-1).astype(np.int64).to_numpy()
            mapped = np.asarray([positions.get(int(index), -1) for index in indices], dtype=np.int64)
            labels = group.get("attack_label", pd.Series("", index=group.index)).astype(str)
            family = group.get("device_family", pd.Series("NA", index=group.index)).astype(str)
            rows.append({
                "role": role,
                "phase": phase,
                "source_group": str(source),
                "targets": int(len(group)),
                "event_position_aligned": int(np.sum(mapped >= 0)),
                "event_position_complete": bool(np.all(mapped >= 0)),
                "history_events_p50": float(np.quantile(mapped[mapped >= 0], 0.5)) if np.any(mapped >= 0) else np.nan,
                "cold_start_targets": int(np.sum(mapped <= 0)),
                "unmapped_targets": int(np.sum(mapped < 0)),
                "attack_family_distribution": json.dumps(Counter(labels).most_common(), ensure_ascii=False),
                "device_family_distribution": json.dumps(Counter(family).most_common(), ensure_ascii=False),
            })
    return rows


def manifest_alignment(cache: T0Cache, plan_path: Path) -> list[dict[str, Any]]:
    """Recheck every frozen target, not merely supervised support rows."""
    plan = pd.read_csv(plan_path, usecols=["source_group", "recorded_index"])
    plan["recorded_index"] = pd.to_numeric(plan["recorded_index"], errors="coerce").fillna(-1).astype(np.int64)
    plan = plan.loc[plan["recorded_index"] >= 0]
    rows: list[dict[str, Any]] = []
    for source, group in plan.groupby(plan["source_group"].astype(str), sort=True):
        positions = cache.target_positions(str(source))
        targets = group["recorded_index"].astype(np.int64).unique()
        mapped = np.asarray([positions.get(int(value), -1) for value in targets], dtype=np.int64)
        rows.append({
            "source_group": str(source),
            "frozen_targets": int(len(targets)),
            "event_position_aligned": int(np.sum(mapped >= 0)),
            "event_position_complete": bool(np.all(mapped >= 0)),
            "unmapped_targets": int(np.sum(mapped < 0)),
        })
    return rows


def held_exclusion(frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scopes = {
        "tgn_ssl_fit": FIT_ROLES,
        "support_supervision": (("support_train", "fit"),),
        "benign_ood_fit_and_standardize": FIT_ROLES,
        "negative_sampling": FIT_ROLES,
        "hard_pair_construction": FIT_ROLES,
        "gate_threshold_select": SELECT_ROLES,
        "c1_fit_and_calibration": FIT_ROLES + SELECT_ROLES,
    }
    for held in HELD:
        for scope, uses in scopes.items():
            for role, phase in uses:
                all_part = role_rows(frames, role, phase)
                family = all_part["device_family"].astype(str)
                retained = all_part.loc[family.ne(held)]
                rows.append({
                    "held_value": held,
                    "scope": scope,
                    "role": role,
                    "phase": phase,
                    "rows_before_exclusion": int(len(all_part)),
                    "held_rows_removed": int(family.eq(held).sum()),
                    "rows_after_exclusion": int(len(retained)),
                    "held_rows_remaining": int(retained["device_family"].astype(str).eq(held).sum()),
                    "pass": bool(not retained["device_family"].astype(str).eq(held).any()),
                })
    return rows


def process_observability(cache: T0Cache, sources: list[str], max_events: int) -> list[dict[str, Any]]:
    """Label-free process statistics from the frozen 9D message stream.

    Future outcomes are intentionally not constructed here; this audit asks only
    whether the current, past-only state has the event primitives required for
    a later legal prediction task.  A training job must create future targets
    inside fit only and must never append them to the current input.
    """
    rows: list[dict[str, Any]] = []
    for source in sources:
        npz, _meta = cache.paths(source)
        if not npz.exists():
            rows.append({"source_group": source, "status": "MISSING_NPZ"})
            continue
        with np.load(npz, allow_pickle=False) as data:
            count = min(int(len(data["time_ms"])), int(max_events))
            src, dst, stamp, msg = data["src"][:count], data["dst"][:count], data["time_ms"][:count], data["raw_msg"][:count]
        last_directed: dict[tuple[int, int], int] = {}
        last_reverse: dict[tuple[int, int], int] = {}
        seen_dst: defaultdict[int, set[int]] = defaultdict(set)
        seen_port: defaultdict[int, set[float]] = defaultdict(set)
        reverse_seen = edge_reuse = syn_count = completion_evidence = 0
        for index in range(count):
            pair = (int(src[index]), int(dst[index]))
            reverse = (pair[1], pair[0])
            reverse_seen += int(reverse in last_directed)
            edge_reuse += int(pair in last_directed)
            syn = bool(msg[index, 5] > 0.5)
            ack_or_rst = bool(msg[index, 6] > 0.5 or msg[index, 7] > 0.5)
            syn_count += int(syn)
            completion_evidence += int(ack_or_rst and reverse in last_directed)
            seen_dst[pair[0]].add(pair[1])
            seen_port[pair[0]].add(float(msg[index, 4]))
            last_directed[pair] = int(stamp[index])
            last_reverse[reverse] = int(stamp[index])
        rows.append({
            "source_group": source,
            "status": "OK",
            "events_scanned": count,
            "reverse_response_past_rate": float(reverse_seen / max(1, count)),
            "directed_edge_reuse_rate": float(edge_reuse / max(1, count)),
            "syn_rate": float(syn_count / max(1, count)),
            "ack_or_rst_with_past_reverse_rate": float(completion_evidence / max(1, count)),
            "mean_destinations_per_source_node": float(np.mean([len(v) for v in seen_dst.values()])) if seen_dst else 0.0,
            "mean_port_buckets_per_source_node": float(np.mean([len(v) for v in seen_port.values()])) if seen_port else 0.0,
            "message_dim": int(msg.shape[1]),
            "raw_label_column_read": False,
            "future_events_used_as_input": False,
        })
    return rows


def write_contract(out: Path, cache_root: Path, role: list[dict[str, Any]], held: list[dict[str, Any]], support: list[dict[str, Any]], manifest: list[dict[str, Any]], process: list[dict[str, Any]]) -> None:
    all_held = bool(held) and all(bool(row["pass"]) for row in held)
    aligned = bool(support) and all(bool(row["event_position_complete"]) for row in support)
    all_targets_aligned = bool(manifest) and all(bool(row["event_position_complete"]) for row in manifest)
    observable = bool(process) and all(row.get("status") == "OK" and int(row.get("message_dim", 0)) == 9 for row in process)
    text = [
        f"# {ISSUE}", "",
        "## Verdict", "",
        f"- held exclusion: `{'PASS' if all_held else 'FAIL'}`",
        f"- support alignment: `{'PASS' if aligned else 'FAIL'}`",
        f"- frozen target alignment: `{'PASS' if all_targets_aligned else 'FAIL'}`",
        f"- 9D process primitives available: `{'PASS' if observable else 'BLOCKED_OR_FAIL'}`", "",
        "## Frozen boundary", "",
        f"- T0 cache root: `{cache_root}`",
        "- TGN self-supervision is fit-only. Select/report target events cannot create gradients.",
        "- Support supervision is per packet; support_val is select-only.",
        "- Strict held exclusion covers TGN, support, negative sampling, standardization, hard-pair construction, gate selection, and C1.",
        "- Process labels based on later outcomes may be generated only during fit; they are never current-event input and never used during report.",
    ]
    (out / "m1_data_contract.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    process_text = [
        f"# {ISSUE} process contract", "",
        "- The frozen input is source-local `(src_local_id, dst_local_id, timestamp, 9D raw message)`.",
        "- Audited past-only primitives are reverse-edge presence, directed-edge reuse, SYN activity, reverse ACK/RST evidence, destination expansion, and port-bucket expansion.",
        "- Future outcomes may be fit-only self-supervision labels, but cannot be input features, memory updates before prediction, select data, or report data.",
        "- Future/past perturbation causality remains a required TGN canary check under the provisioned PyG runtime.",
    ]
    (out / "m1_process_contract.md").write_text("\n".join(process_text) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _x, frames, input_audit, _labels = cko.load_role_inputs(False)
    ckao.add_family_columns(frames)
    cache = T0Cache(Path(args.t0_root))
    roles, cache_rows = role_audit(frames, cache)
    support = support_alignment(frames, cache)
    manifest = manifest_alignment(cache, Path(args.plan_path))
    held = held_exclusion(frames)
    # CKBE T0 only materialized its frozen 26-source manifest.  Role frames can
    # also contain future/sealed sources which are deliberately outside M1 fit,
    # select, and this cache contract.  Auditing them as missing cache shards
    # would turn a correctly sealed/report-only source into a false T0 failure.
    process_sources = [str(row["source_group"]) for row in manifest]
    process = process_observability(cache, process_sources, int(args.max_events_per_source))
    pd.DataFrame(roles).to_csv(out / "m1_role_usage_audit.csv", index=False)
    pd.DataFrame(held).to_csv(out / "m1_held_exclusion_audit.csv", index=False)
    pd.DataFrame(support).to_csv(out / "m1_support_alignment_audit.csv", index=False)
    pd.DataFrame(manifest).to_csv(out / "m1_target_alignment_audit.csv", index=False)
    pd.DataFrame(cache_rows).to_csv(out / "m1_t0_cache_audit.csv", index=False)
    pd.DataFrame(process).to_csv(out / "m1_process_observability_audit.csv", index=False)
    write_contract(out, Path(args.t0_root), roles, held, support, manifest, process)
    summary = {
        "issue": ISSUE,
        "t0_root": str(Path(args.t0_root)),
        "plan_path": str(Path(args.plan_path)),
        "input_audit": input_audit,
        "held_exclusion_pass": bool(held) and all(bool(row["pass"]) for row in held),
        "support_alignment_pass": bool(support) and all(bool(row["event_position_complete"]) for row in support),
        "target_alignment_pass": bool(manifest) and all(bool(row["event_position_complete"]) for row in manifest),
        "process_audit_complete": bool(process) and all(row.get("status") == "OK" for row in process),
        "process_audit_scope": "CKBE frozen source manifest only; future/sealed sources outside that manifest are not M1 fit/select input",
        "raw_label_column_read": False,
    }
    (out / "run_spec.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not (summary["held_exclusion_pass"] and summary["support_alignment_pass"] and summary["target_alignment_pass"] and summary["process_audit_complete"]):
        raise SystemExit("M1 preflight failed; do not train")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--t0-root", default=str(DEFAULT_T0))
    parser.add_argument("--plan-path", default=str(DEFAULT_PLAN))
    parser.add_argument("--max-events-per-source", type=int, default=200_000)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
