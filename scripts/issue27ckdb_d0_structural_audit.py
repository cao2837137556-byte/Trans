#!/usr/bin/env python3
"""Read-only CKDB D0 audits for domain identifiability and hydraulic shift.

This script consumes only already-open CKDA D1 report metadata, the frozen
fit/select plan, and CKCZ causal caches.  It never opens a PCAP or a FINAL
source.  Its output is diagnostic evidence, not a training or selection
artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd


FIT_ROLES = {
    "aux_fit",
    "aux_normal_fit",
    "aux_process_fit",
    "id_calib",
    "ood_val",
    "support_train",
}

CONTINUOUS_FEATURES = {
    "frame_len": "cur_log_frame_len",
    "source_iat_ms": "hist_log_source_iat_ms",
    "pair_forward_iat_ms": "hist_log_pair_forward_iat_ms",
    "flow_packets": "hist_log_flow_packets",
    "flow_elapsed_ms": "hist_log_flow_elapsed_ms",
}

BINARY_FEATURES = {
    "is_tcp": "cur_is_tcp",
    "is_udp": "cur_is_udp",
    "is_icmp": "cur_is_icmp",
    "flow_bidirectional_seen": "hist_flow_bidirectional_seen",
    "flow_syn_seen": "hist_flow_syn_seen",
    "flow_rst_seen": "hist_flow_rst_seen",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def normalized_domain(value: object) -> str:
    text = str(value).strip()
    return text[7:] if text.startswith("iotsim-") else text


def majority_domain_accuracy(frame: pd.DataFrame) -> float:
    correct = 0
    for _, part in frame.groupby("domain", sort=True):
        counts = part["label_metric_only"].value_counts()
        correct += int(counts.max())
    return float(correct / len(frame)) if len(frame) else float("nan")


def domain_audit(plan_path: Path) -> Dict[str, object]:
    plan = pd.read_csv(plan_path)
    fit = plan.loc[(plan["phase"] == "fit") & plan["role"].isin(FIT_ROLES)].copy()
    if len(fit) != 18_398:
        raise RuntimeError("unexpected CKDA D1 fit denominator")
    fit["domain"] = fit["device_family"].map(normalized_domain)

    benign = fit.loc[fit["label_metric_only"] == 0]
    attack = fit.loc[fit["label_metric_only"] == 1]
    benign_counts = benign.groupby("domain", sort=True).size().astype(int)
    attack_counts = attack.groupby("domain", sort=True).size().astype(int)
    shares = benign_counts.to_numpy(dtype=float) / float(len(benign))
    effective_benign_domains = float(1.0 / np.square(shares).sum())

    non_ton = fit.loc[fit["domain"] != "ton-iot-external"]
    attack_ton_rows = int((attack["domain"] == "ton-iot-external").sum())
    contingency = (
        fit.groupby(["domain", "label_metric_only"], sort=True)
        .size()
        .unstack(fill_value=0)
        .rename(columns={0: "benign_rows", 1: "attack_rows"})
        .reset_index()
    )
    for column in ("benign_rows", "attack_rows"):
        if column not in contingency:
            contingency[column] = 0

    return {
        "fit_rows": int(len(fit)),
        "fit_sources": int(fit["source_group"].nunique()),
        "benign_rows": int(len(benign)),
        "attack_rows": int(len(attack)),
        "benign_domain_rows": {str(k): int(v) for k, v in benign_counts.items()},
        "attack_domain_rows": {str(k): int(v) for k, v in attack_counts.items()},
        "coarse_benign_domain_count": int(len(benign_counts)),
        "effective_benign_domain_count_hhi": effective_benign_domains,
        "attack_rows_from_ton": attack_ton_rows,
        "attack_rows_from_ton_fraction": float(attack_ton_rows / len(attack)),
        "domain_majority_label_accuracy_all": majority_domain_accuracy(fit),
        "domain_majority_label_accuracy_excluding_ton": majority_domain_accuracy(non_ton),
        "domain_label_contingency": contingency.to_dict(orient="records"),
    }


def ks_distance(left: np.ndarray, right: np.ndarray) -> float:
    left = np.sort(left[np.isfinite(left)])
    right = np.sort(right[np.isfinite(right)])
    if not len(left) or not len(right):
        return float("nan")
    values = np.unique(np.concatenate((left, right)))
    left_cdf = np.searchsorted(left, values, side="right") / len(left)
    right_cdf = np.searchsorted(right, values, side="right") / len(right)
    return float(np.max(np.abs(left_cdf - right_cdf)))


def quantiles(values: np.ndarray) -> Dict[str, float]:
    values = values[np.isfinite(values)]
    if not len(values):
        return {"p25": float("nan"), "p50": float("nan"), "p75": float("nan"), "p90": float("nan")}
    result = np.quantile(values, [0.25, 0.50, 0.75, 0.90])
    return {key: float(value) for key, value in zip(("p25", "p50", "p75", "p90"), result)}


def group_summary(frame: pd.DataFrame) -> Dict[str, object]:
    result: Dict[str, object] = {
        "rows": int(len(frame)),
        "sources": int(frame["source_group"].nunique()),
    }
    for name in CONTINUOUS_FEATURES:
        result[name] = quantiles(frame[name].to_numpy(dtype=float))
    for name in BINARY_FEATURES:
        result[name + "_fraction"] = float(frame[name].mean())
    return result


def load_causal_report_rows(
    report_metadata_path: Path,
    report_scores_path: Path,
    manifest_path: Path,
    cache_root: Path,
) -> pd.DataFrame:
    columns = [
        "uid",
        "role",
        "source_group",
        "device_family",
        "attack_family",
        "label_metric_only",
        "recorded_index",
        "cache_kind",
    ]
    metadata = pd.read_csv(report_metadata_path, usecols=columns)
    if metadata["source_group"].astype(str).str.contains("cooler-motor", case=False).any():
        raise RuntimeError("FINAL cooler-motor source unexpectedly present")
    metadata = metadata.loc[metadata["cache_kind"] == "gotham"].copy()

    scores = pd.read_csv(report_scores_path)
    scores = scores.loc[
        (scores["candidate_id"] == "E3") & (scores["probe_id"] == "P2"),
        ["uid", "hard", "missing", "score"],
    ].copy()
    if scores["uid"].duplicated().any():
        raise RuntimeError("duplicate E3/P2 report score UID")
    metadata = metadata.merge(scores, on="uid", how="left", validate="one_to_one")
    if metadata[["hard", "missing", "score"]].isna().any().any():
        raise RuntimeError("report score join miss")

    manifest = pd.read_csv(manifest_path)
    lookup = manifest.set_index("source_group")["source_cache_key"].astype(str).to_dict()
    unknown = sorted(set(metadata["source_group"]) - set(lookup))
    if unknown:
        raise RuntimeError("causal cache manifest miss: " + repr(unknown))

    pieces: List[pd.DataFrame] = []
    expected_feature_names: Optional[Sequence[str]] = None
    for source_group, part in metadata.groupby("source_group", sort=True):
        cache_path = cache_root / (lookup[str(source_group)] + ".npz")
        with np.load(cache_path, allow_pickle=False) as cache:
            feature_names = cache["feature_names"].astype(str).tolist()
            if expected_feature_names is None:
                expected_feature_names = feature_names
            elif list(expected_feature_names) != feature_names:
                raise RuntimeError("causal feature schema drift")
            indices = cache["recorded_index"].astype(np.int64)
            if len(indices) != len(np.unique(indices)):
                raise RuntimeError("duplicate recorded_index in causal cache")
            position = {int(value): index for index, value in enumerate(indices)}
            missing = sorted(set(part["recorded_index"].astype(int)) - set(position))
            if missing:
                raise RuntimeError("causal recorded_index join miss")
            take = np.asarray([position[int(value)] for value in part["recorded_index"]], dtype=np.int64)
            features = cache["causal_features"][take].astype(np.float64)
        enriched = part.reset_index(drop=True).copy()
        for output_name, feature_name in CONTINUOUS_FEATURES.items():
            values = features[:, feature_names.index(feature_name)]
            enriched[output_name] = np.expm1(np.maximum(values, 0.0))
        for output_name, feature_name in BINARY_FEATURES.items():
            enriched[output_name] = features[:, feature_names.index(feature_name)]
        pieces.append(enriched)
    result = pd.concat(pieces, ignore_index=True)
    if len(result) != len(metadata):
        raise RuntimeError("causal report row denominator drift")
    return result


def structural_audit(frame: pd.DataFrame) -> Dict[str, object]:
    hydraulic = frame["device_family"] == "iotsim-hydraulic-system"
    benign_controls = frame["device_family"].isin(
        ["iotsim-stream-consumer", "iotsim-ip-camera-street"]
    )
    attacks = frame["label_metric_only"] == 1
    groups = {
        "hydraulic": frame.loc[hydraulic],
        "viewed_benign_controls": frame.loc[benign_controls],
        "attacks": frame.loc[attacks],
        "stream_consumer": frame.loc[frame["device_family"] == "iotsim-stream-consumer"],
        "ip_camera_street_benign": frame.loc[frame["device_family"] == "iotsim-ip-camera-street"],
        "hydraulic_p2_hard": frame.loc[hydraulic & (frame["hard"] == 1)],
        "hydraulic_p2_normal": frame.loc[hydraulic & (frame["hard"] == 0)],
    }
    if len(groups["hydraulic"]) != 3_000 or len(groups["viewed_benign_controls"]) != 6_000:
        raise RuntimeError("unexpected hydraulic/control denominator")

    distances: List[Dict[str, object]] = []
    hydraulic_frame = groups["hydraulic"]
    benign_frame = groups["viewed_benign_controls"]
    attack_frame = groups["attacks"]
    for feature in CONTINUOUS_FEATURES:
        hyd = hydraulic_frame[feature].to_numpy(dtype=float)
        benign = benign_frame[feature].to_numpy(dtype=float)
        attack = attack_frame[feature].to_numpy(dtype=float)
        benign_distance = ks_distance(hyd, benign)
        attack_distance = ks_distance(hyd, attack)
        distances.append(
            {
                "feature": feature,
                "distance_kind": "KS",
                "to_viewed_benign_controls": benign_distance,
                "to_attacks": attack_distance,
                "attack_closer": bool(attack_distance < benign_distance),
                "attack_closer_margin": float(benign_distance - attack_distance),
            }
        )
    for feature in BINARY_FEATURES:
        hyd = float(hydraulic_frame[feature].mean())
        benign = float(benign_frame[feature].mean())
        attack = float(attack_frame[feature].mean())
        benign_distance = abs(hyd - benign)
        attack_distance = abs(hyd - attack)
        distances.append(
            {
                "feature": feature,
                "distance_kind": "absolute_prevalence_difference",
                "to_viewed_benign_controls": benign_distance,
                "to_attacks": attack_distance,
                "attack_closer": bool(attack_distance < benign_distance),
                "attack_closer_margin": float(benign_distance - attack_distance),
            }
        )
    distances.sort(key=lambda row: float(row["attack_closer_margin"]), reverse=True)
    return {
        "causal_report_rows": int(len(frame)),
        "causal_report_sources": int(frame["source_group"].nunique()),
        "groups": {name: group_summary(part) for name, part in groups.items()},
        "hydraulic_distance_diagnostic": distances,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit-select-plan", type=Path, required=True)
    parser.add_argument("--report-metadata", type=Path, required=True)
    parser.add_argument("--report-scores", type=Path, required=True)
    parser.add_argument("--causal-manifest", type=Path, required=True)
    parser.add_argument("--causal-cache-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs = {
        "fit_select_plan": args.fit_select_plan,
        "report_metadata": args.report_metadata,
        "report_scores": args.report_scores,
        "causal_manifest": args.causal_manifest,
    }
    for name, path in inputs.items():
        if not path.is_file():
            raise FileNotFoundError("%s: %s" % (name, path))
    report_rows = load_causal_report_rows(
        args.report_metadata,
        args.report_scores,
        args.causal_manifest,
        args.causal_cache_root,
    )
    result = {
        "status": "CKDB_D0_READ_ONLY_AUDIT_COMPLETE",
        "claim_boundary": "diagnostic_only_no_training_no_selection_no_final_open",
        "input_sha256": {name: sha256_file(path) for name, path in inputs.items()},
        "domain_identifiability": domain_audit(args.fit_select_plan),
        "hydraulic_structure": structural_audit(report_rows),
    }
    atomic_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
