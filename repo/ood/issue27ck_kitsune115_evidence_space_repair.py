from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

import issue27cj_attack_region_instantiation as cj


ROOT = Path(__file__).resolve().parents[2]
ISSUE = "issue27ck_kitsune115_region_geometry_failure_anatomy_and_evidence_space_repair_2026-06-21"
OUT = ROOT / "runs" / ISSUE

PRIMARY_SCHEME = "medium"
DELTA_CLIP = 5.0
WINSOR_LOW = 0.001
WINSOR_HIGH = 0.999
EPS = 1e-8
BATCH = 20000


@dataclass
class EvidenceSpace:
    name: str
    bounded_heavy_tail: bool
    family_balanced: bool
    feature_names: list[str]
    family_indices: dict[str, np.ndarray]
    heavy_mask: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    center: np.ndarray
    scale: np.ndarray

    def transform(self, x: np.ndarray) -> np.ndarray:
        out = np.asarray(x, dtype=np.float64)
        if self.bounded_heavy_tail:
            out = np.clip(out, self.lower, self.upper)
            out = out.copy()
            out[:, self.heavy_mask] = np.sign(out[:, self.heavy_mask]) * np.log1p(
                np.abs(out[:, self.heavy_mask])
            )
        return (out - self.center) / self.scale

    def distance(self, x: np.ndarray, prototypes: np.ndarray) -> np.ndarray:
        if not self.family_balanced:
            return cj.euclidean_distance(x, prototypes)
        out = np.zeros((len(x), len(prototypes)), dtype=np.float64)
        for idx in self.family_indices.values():
            delta = x[:, None, idx] - prototypes[None, :, idx]
            family_loss = np.mean(np.minimum(delta * delta, DELTA_CLIP**2), axis=2)
            out += family_loss
        return np.sqrt(out / len(self.family_indices))

    def feature_contributions(self, x: np.ndarray, prototype: np.ndarray) -> np.ndarray:
        delta2 = np.square(x - prototype)
        if not self.family_balanced:
            return delta2
        out = np.zeros_like(delta2)
        for idx in self.family_indices.values():
            out[:, idx] = np.minimum(delta2[:, idx], DELTA_CLIP**2) / (
                len(self.family_indices) * len(idx)
            )
        return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def feature_families(schema: dict[str, Any]) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    start = 0
    for family in ["MI_dir", "H", "HH", "HH_jit", "HpHp"]:
        stop = start + int(schema["family_counts"][family])
        out[family] = np.arange(start, stop, dtype=np.int64)
        start = stop
    if start != 115:
        raise RuntimeError(f"Unexpected feature count from family schema: {start}")
    return out


def signed_log_heavy_mask(names: list[str]) -> np.ndarray:
    tokens = ("_mean", "_std", "_radius", "_magnitude", "_covariance")
    return np.asarray([any(token in name for token in tokens) for name in names], dtype=bool)


def robust_parameters(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    center = np.median(x, axis=0)
    q25 = np.quantile(x, 0.25, axis=0)
    q75 = np.quantile(x, 0.75, axis=0)
    scale = q75 - q25
    std = np.std(x, axis=0)
    fallback = scale <= EPS
    scale[fallback] = std[fallback]
    scale[scale <= EPS] = 1.0
    return center, scale


def make_spaces(x_id: np.ndarray, schema: dict[str, Any]) -> tuple[list[EvidenceSpace], list[dict[str, Any]]]:
    names = list(schema["feature_names"])
    families = feature_families(schema)
    heavy = signed_log_heavy_mask(names)
    lower = np.quantile(x_id, WINSOR_LOW, axis=0)
    upper = np.quantile(x_id, WINSOR_HIGH, axis=0)

    raw_center, raw_scale = robust_parameters(x_id)
    bounded = np.clip(x_id, lower, upper)
    bounded[:, heavy] = np.sign(bounded[:, heavy]) * np.log1p(np.abs(bounded[:, heavy]))
    bounded_center, bounded_scale = robust_parameters(bounded)

    spaces = [
        EvidenceSpace(
            "S0_raw_robust_global",
            False,
            False,
            names,
            families,
            heavy,
            lower,
            upper,
            raw_center,
            raw_scale,
        ),
        EvidenceSpace(
            "S1_bounded_heavytail_global",
            True,
            False,
            names,
            families,
            heavy,
            lower,
            upper,
            bounded_center,
            bounded_scale,
        ),
        EvidenceSpace(
            "S2_raw_family_balanced",
            False,
            True,
            names,
            families,
            heavy,
            lower,
            upper,
            raw_center,
            raw_scale,
        ),
        EvidenceSpace(
            "S3_bounded_heavytail_family_balanced",
            True,
            True,
            names,
            families,
            heavy,
            lower,
            upper,
            bounded_center,
            bounded_scale,
        ),
    ]
    audit = []
    for idx, name in enumerate(names):
        raw = x_id[:, idx]
        q01 = float(np.quantile(raw, 0.01))
        q50 = float(np.quantile(raw, 0.50))
        q99 = float(np.quantile(raw, 0.99))
        audit.append(
            {
                "feature_index": idx,
                "feature_name": name,
                "family": next(f for f, ids in families.items() if idx in ids),
                "signed_log_selected": bool(heavy[idx]),
                "id_q001": float(lower[idx]),
                "id_q01": q01,
                "id_q50": q50,
                "id_q99": q99,
                "id_q999": float(upper[idx]),
                "q99_minus_q50": q99 - q50,
                "q50_minus_q01": q50 - q01,
            }
        )
    return spaces, audit


def medoid_index(space: EvidenceSpace, x: np.ndarray) -> int:
    distances = space.distance(x, x)
    return int(np.argmin(np.sum(distances, axis=1)))


def source_count(rows: list[dict[str, str]]) -> int:
    return len({(r["device_or_source_group"], r["pcap_path"], r["source_file"]) for r in rows})


def build_geometry(
    space: EvidenceSpace,
    support_rows: list[dict[str, str]],
    support_x_raw: np.ndarray,
) -> dict[str, Any]:
    support_x = space.transform(support_x_raw)
    train_mask = np.asarray([row["bank_partition"] == "support_train" for row in support_rows])
    val_mask = np.asarray([row["bank_partition"] == "support_val" for row in support_rows])
    labels = sorted({row["exact_attack_label"] for row in support_rows})
    prototypes = []
    geometry: dict[str, Any] = {}
    radii_rows = []
    prototype_rows = []

    for label in labels:
        train_idx = np.flatnonzero(
            train_mask
            & np.asarray([row["exact_attack_label"] == label for row in support_rows], dtype=bool)
        )
        val_idx = np.flatnonzero(
            val_mask
            & np.asarray([row["exact_attack_label"] == label for row in support_rows], dtype=bool)
        )
        x_train = support_x[train_idx]
        x_val = support_x[val_idx]
        local = medoid_index(space, x_train)
        global_idx = int(train_idx[local])
        prototype = support_x[global_idx]
        prototypes.append(prototype)
        train_dist = space.distance(x_train, prototype[None, :])[:, 0]
        val_dist = space.distance(x_val, prototype[None, :])[:, 0]
        radii = {
            scheme: cj.shell_radii(train_dist, val_dist, scheme) for scheme in cj.SHELL_SCHEMES
        }
        geometry[label] = {
            "train_idx": train_idx,
            "val_idx": val_idx,
            "train_dist": train_dist,
            "val_dist": val_dist,
            "radii": radii,
            "prototype": prototype,
            "prototype_support_index": global_idx,
        }
        proto_row = support_rows[global_idx]
        prototype_rows.append(
            {
                "evidence_space": space.name,
                "exact_attack_label": label,
                "sample_id": proto_row["sample_id"],
                "source_file": proto_row["source_file"],
                "device_or_source_group": proto_row["device_or_source_group"],
                "phase": proto_row["phase"],
            }
        )
        for scheme, shell in radii.items():
            radii_rows.append(
                {
                    "evidence_space": space.name,
                    "exact_attack_label": label,
                    "shell_scheme": scheme,
                    **shell,
                }
            )
    return {
        "support_x": support_x,
        "train_mask": train_mask,
        "val_mask": val_mask,
        "labels": labels,
        "label_index": {label: i for i, label in enumerate(labels)},
        "prototypes": np.vstack(prototypes),
        "geometry": geometry,
        "prototype_rows": prototype_rows,
        "radii_rows": radii_rows,
    }


def audit_support_val(
    space: EvidenceSpace,
    state: dict[str, Any],
    support_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    val_x = state["support_x"][state["val_mask"]]
    val_meta = [row for row in support_rows if row["bank_partition"] == "support_val"]
    distances = space.distance(val_x, state["prototypes"])
    rows = []
    summary = []
    for i, meta in enumerate(val_meta):
        true_label = meta["exact_attack_label"]
        true_idx = state["label_index"][true_label]
        nearest_idx = int(np.argmin(distances[i]))
        nearest_label = state["labels"][nearest_idx]
        rows.append(
            {
                "evidence_space": space.name,
                "sample_id": meta["sample_id"],
                "true_attack_label": true_label,
                "nearest_attack_label": nearest_label,
                "nearest_distance": float(distances[i, nearest_idx]),
                "true_region_distance": float(distances[i, true_idx]),
                "true_region_shell": cj.shell_name(
                    float(distances[i, true_idx]),
                    state["geometry"][true_label]["radii"][PRIMARY_SCHEME],
                ),
                "nearest_region_shell": cj.shell_name(
                    float(distances[i, nearest_idx]),
                    state["geometry"][nearest_label]["radii"][PRIMARY_SCHEME],
                ),
            }
        )
    for label in state["labels"]:
        group = [row for row in rows if row["true_attack_label"] == label]
        summary.append(
            {
                "evidence_space": space.name,
                "exact_attack_label": label,
                "rows": len(group),
                "nearest_label_consistency": sum(
                    row["nearest_attack_label"] == label for row in group
                )
                / len(group),
                "true_region_uncertain_coverage": sum(
                    cj.shell_rank(row["true_region_shell"]) <= 2 for row in group
                )
                / len(group),
                "true_region_core_rate": sum(
                    row["true_region_shell"] == "core" for row in group
                )
                / len(group),
            }
        )
    return rows, summary


def audit_benign(
    space: EvidenceSpace,
    state: dict[str, Any],
    cert_x: np.ndarray,
    indices: np.ndarray,
    role: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    direct = {label: Counter() for label in state["labels"]}
    nearest = Counter()
    total = 0
    for start in range(0, len(indices), BATCH):
        raw = np.asarray(cert_x[indices[start : start + BATCH]], dtype=np.float64)
        x = space.transform(raw)
        distances = space.distance(x, state["prototypes"])
        nearest_idx = np.argmin(distances, axis=1)
        for i in range(len(x)):
            label = state["labels"][int(nearest_idx[i])]
            nearest[
                cj.shell_name(
                    float(distances[i, nearest_idx[i]]),
                    state["geometry"][label]["radii"][PRIMARY_SCHEME],
                )
            ] += 1
        for region_idx, label in enumerate(state["labels"]):
            radii = state["geometry"][label]["radii"][PRIMARY_SCHEME]
            region_dist = distances[:, region_idx]
            direct[label]["core"] += int(np.sum(region_dist <= radii["core_radius"]))
            direct[label]["near"] += int(
                np.sum(
                    (region_dist > radii["core_radius"])
                    & (region_dist <= radii["near_radius"])
                )
            )
        total += len(x)
    rows = []
    for label in state["labels"]:
        rows.append(
            {
                "evidence_space": space.name,
                "role": role,
                "exact_attack_label": label,
                "rows": total,
                "direct_core_rate": direct[label]["core"] / total,
                "direct_core_plus_near_rate": (
                    direct[label]["core"] + direct[label]["near"]
                )
                / total,
                "read_only": role == "ood_benign_stress",
            }
        )
    return rows, {
        "evidence_space": space.name,
        "role": role,
        "rows": total,
        "nearest_core_rate": nearest["core"] / total,
        "nearest_core_plus_near_rate": (nearest["core"] + nearest["near"]) / total,
        "nearest_out_of_region_rate": nearest["out_of_region"] / total,
    }


def freeze_registry(
    space: EvidenceSpace,
    state: dict[str, Any],
    support_rows: list[dict[str, str]],
    support_summary: list[dict[str, Any]],
    ood_val_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    support_by_label = {row["exact_attack_label"]: row for row in support_summary}
    ood_by_label = {row["exact_attack_label"]: row for row in ood_val_rows}
    rows = []
    for label in state["labels"]:
        geometry = state["geometry"][label]
        support = support_by_label[label]
        ood = ood_by_label[label]
        train_meta = [support_rows[i] for i in geometry["train_idx"]]
        sources = source_count(train_meta)
        minimum_ok = (
            len(geometry["train_idx"]) >= 12
            and len(geometry["val_idx"]) >= 3
            and support["true_region_uncertain_coverage"] >= 0.80
            and support["nearest_label_consistency"] >= 0.80
        )
        if not minimum_ok:
            status = "ambiguous_region"
        elif (
            sources >= 2
            and ood["direct_core_rate"] <= 0.001
            and ood["direct_core_plus_near_rate"] <= 0.01
        ):
            status = "active_strong"
        else:
            status = "active_conflict_sensitive"
        rows.append(
            {
                "evidence_space": space.name,
                "region_id": cj.stable_id(f"{space.name}_region_", label),
                "exact_attack_label": label,
                "semantic_attack_group": train_meta[0]["semantic_attack_group"],
                "train_rows": len(geometry["train_idx"]),
                "val_rows": len(geometry["val_idx"]),
                "provenance_source_count": sources,
                "support_val_uncertain_coverage": support[
                    "true_region_uncertain_coverage"
                ],
                "support_val_nearest_label_consistency": support[
                    "nearest_label_consistency"
                ],
                "ood_val_core_intrusion_rate": ood["direct_core_rate"],
                "ood_val_core_plus_near_intrusion_rate": ood[
                    "direct_core_plus_near_rate"
                ],
                "region_status": status,
                "status_frozen_before_stress_query": True,
            }
        )
    return rows


def space_decision(registry: list[dict[str, Any]]) -> tuple[str, int, int]:
    active = [row for row in registry if row["region_status"] == "active_strong"]
    groups = len({row["semantic_attack_group"] for row in active})
    if len(active) >= 3 and groups >= 2:
        return "GO", len(active), groups
    if 1 <= len(active) <= 2:
        return "LIMITED_GO", len(active), groups
    return "STOP", len(active), groups


def audit_query(
    space: EvidenceSpace,
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    aggregates: dict[tuple[str, str], Counter] = defaultdict(Counter)
    certified = [
        row
        for row in cj.read_csv(cj.CERTIFIED_CHUNKS)
        if row["status"] == "complete"
        and row["role"]
        in {"same_file_time_forward_dev_query_exact", "dev_future_attack_query_exact"}
    ]
    for chunk in certified:
        raw = np.load(
            cj.ATTACK_CHUNKS / f"chunk_{int(chunk['chunk_id']):05d}_X.npy",
            mmap_mode="r",
        )
        for start in range(0, len(raw), BATCH):
            x = space.transform(np.asarray(raw[start : start + BATCH], dtype=np.float64))
            distances = space.distance(x, state["prototypes"])
            nearest_idx = np.argmin(distances, axis=1)
            for i in range(len(x)):
                nearest_label = state["labels"][int(nearest_idx[i])]
                shell = cj.shell_name(
                    float(distances[i, nearest_idx[i]]),
                    state["geometry"][nearest_label]["radii"][PRIMARY_SCHEME],
                )
                key = (chunk["role"], chunk["attack_label"])
                aggregates[key]["rows"] += 1
                aggregates[key][shell] += 1
                aggregates[key]["label_match"] += int(
                    nearest_label == chunk["attack_label"]
                )
    rows = []
    for (role, label), counts in sorted(aggregates.items()):
        total = counts["rows"]
        rows.append(
            {
                "evidence_space": space.name,
                "role": role,
                "true_attack_label": label,
                "rows": total,
                "core_rate": counts["core"] / total,
                "core_plus_near_rate": (counts["core"] + counts["near"]) / total,
                "uncertain_rate": counts["uncertain"] / total,
                "out_of_region_rate": counts["out_of_region"] / total,
                "nearest_label_match_rate": counts["label_match"] / total,
                "read_only": True,
            }
        )
    return rows


def feature_dominance(
    space: EvidenceSpace,
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for label in state["labels"]:
        geometry = state["geometry"][label]
        x = state["support_x"][geometry["train_idx"]]
        contributions = space.feature_contributions(x, geometry["prototype"])
        totals = np.sum(contributions, axis=1)
        valid = totals > EPS
        fractions = np.zeros_like(contributions)
        fractions[valid] = contributions[valid] / totals[valid, None]
        sorted_fraction = np.sort(fractions, axis=1)[:, ::-1]
        mean_fraction = np.mean(fractions, axis=0)
        family_share = {
            family: float(np.mean(np.sum(fractions[:, idx], axis=1)))
            for family, idx in space.family_indices.items()
        }
        rows.append(
            {
                "evidence_space": space.name,
                "exact_attack_label": label,
                "median_top1_fraction": float(np.median(sorted_fraction[:, 0])),
                "median_top5_fraction": float(
                    np.median(np.sum(sorted_fraction[:, :5], axis=1))
                ),
                "dominant_feature": space.feature_names[int(np.argmax(mean_fraction))],
                **{f"{family}_mean_share": share for family, share in family_share.items()},
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    support_rows, support_x = cj.load_support()
    roles = cj.load_role_indices()
    cert_x = np.load(cj.CERT_X, mmap_mode="r")
    with cj.FEATURE_SCHEMA.open(encoding="utf-8") as f:
        schema = json.load(f)
    x_id = np.asarray(cert_x[roles["id_benign_train"]], dtype=np.float64)
    spaces, tail_audit = make_spaces(x_id, schema)

    all_support_rows = []
    all_support_summary = []
    all_ood_rows = []
    all_ood_summary = []
    all_registry = []
    all_query = []
    all_dominance = []
    all_prototypes = []
    all_radii = []
    qualification = []
    states: dict[str, dict[str, Any]] = {}

    for space in spaces:
        state = build_geometry(space, support_rows, support_x)
        states[space.name] = state
        support_audit, support_summary = audit_support_val(space, state, support_rows)
        ood_rows, ood_summary = audit_benign(
            space, state, cert_x, roles["ood_benign_val"], "ood_benign_val"
        )
        registry = freeze_registry(
            space, state, support_rows, support_summary, ood_rows
        )
        decision, active_count, group_count = space_decision(registry)
        qualification.append(
            {
                "evidence_space": space.name,
                "decision": decision,
                "active_strong_regions": active_count,
                "active_strong_semantic_groups": group_count,
                "mean_support_val_label_consistency": float(
                    np.mean([row["nearest_label_consistency"] for row in support_summary])
                ),
                "mean_support_val_uncertain_coverage": float(
                    np.mean(
                        [row["true_region_uncertain_coverage"] for row in support_summary]
                    )
                ),
                "ood_val_nearest_core_rate": ood_summary["nearest_core_rate"],
                "ood_val_nearest_core_plus_near_rate": ood_summary[
                    "nearest_core_plus_near_rate"
                ],
            }
        )
        all_support_rows.extend(support_audit)
        all_support_summary.extend(support_summary)
        all_ood_rows.extend(ood_rows)
        all_ood_summary.append(ood_summary)
        all_registry.extend(registry)
        all_dominance.extend(feature_dominance(space, state))
        all_prototypes.extend(state["prototype_rows"])
        all_radii.extend(state["radii_rows"])

    rank = {"GO": 2, "LIMITED_GO": 1, "STOP": 0}
    selected = max(
        qualification,
        key=lambda row: (
            rank[row["decision"]],
            row["active_strong_regions"],
            row["mean_support_val_label_consistency"],
            -row["ood_val_nearest_core_plus_near_rate"],
        ),
    )
    frozen_selection = {
        "selected_evidence_space": selected["evidence_space"],
        "selected_on_roles": ["support_val", "ood_benign_val"],
        "decision": selected["decision"],
        "selection_frozen_before": ["ood_benign_stress", "certified_dev_query"],
    }
    write_json(OUT / "frozen_evidence_space_selection.json", frozen_selection)

    # Read-only after the selection record exists.
    for space in spaces:
        stress_rows, stress_summary = audit_benign(
            space, states[space.name], cert_x, roles["ood_benign_stress"], "ood_benign_stress"
        )
        all_ood_rows.extend(stress_rows)
        all_ood_summary.append(stress_summary)
        all_query.extend(audit_query(space, states[space.name]))

    write_csv(OUT / "feature_tail_audit.csv", tail_audit)
    write_csv(OUT / "evidence_space_qualification.csv", qualification)
    write_csv(OUT / "support_val_audit.csv", all_support_rows)
    write_csv(OUT / "support_val_summary.csv", all_support_summary)
    write_csv(OUT / "ood_overlap_audit.csv", all_ood_rows)
    write_csv(OUT / "ood_role_summary.csv", all_ood_summary)
    write_csv(OUT / "candidate_region_registry.csv", all_registry)
    write_csv(OUT / "certified_dev_query_stress.csv", all_query)
    write_csv(OUT / "feature_dominance_by_space.csv", all_dominance)
    write_csv(OUT / "prototype_manifest.csv", all_prototypes)
    write_csv(OUT / "shell_registry.csv", all_radii)
    write_csv(
        OUT / "role_access_audit.csv",
        [
            {
                "stage": "transform_fit",
                "roles": "id_benign_train",
                "sealed_access": False,
            },
            {
                "stage": "prototype_fit",
                "roles": "support_train",
                "sealed_access": False,
            },
            {
                "stage": "shell_and_structure",
                "roles": "support_val",
                "sealed_access": False,
            },
            {
                "stage": "qualification_and_selection",
                "roles": "ood_benign_val",
                "sealed_access": False,
            },
            {
                "stage": "read_only_stress",
                "roles": "ood_benign_stress|certified_dev_query",
                "sealed_access": False,
            },
        ],
    )

    decisions = Counter(row["decision"] for row in qualification)
    if selected["decision"] == "GO":
        verdict = "nonlearned_evidence_space_repair_go_region_activation_allowed_for_qualified_regions"
        next_action = "freeze_selected_region_registry_then_controller_evidence_replay"
    elif selected["decision"] == "LIMITED_GO":
        verdict = "nonlearned_evidence_space_repair_limited_go_only_qualified_regions_may_emit_strong_evidence"
        next_action = "freeze_limited_registry_unqualified_routes_unknown_review"
    else:
        verdict = "nonlearned_evidence_space_repair_failed_stop_raw_geometry_route"
        next_action = "separate_issue_learned_family_aware_attack_evidence_representation"

    result = {
        "issue": ISSUE,
        "primary_verdict": verdict,
        "spaces": [space.name for space in spaces],
        "space_decision_counts": dict(decisions),
        "selected": selected,
        "support_train_rows": sum(
            row["bank_partition"] == "support_train" for row in support_rows
        ),
        "support_val_rows": sum(
            row["bank_partition"] == "support_val" for row in support_rows
        ),
        "support_reselection": False,
        "region_split_execution": False,
        "model_training": False,
        "controller_tuning": False,
        "sealed_final_access": False,
        "selection_frozen_before_stress_query": True,
        "next_action": next_action,
    }
    write_json(OUT / "results.json", result)
    write_json(
        OUT / "config.json",
        {
            "spaces": {
                "S0": "raw robust-scaled global Euclidean control",
                "S1": "ID q0.001/q0.999 winsorization plus signed log1p on mean/std/radius/magnitude/covariance then robust-scaled global Euclidean",
                "S2": "raw robust-scaled family-balanced bounded Euclidean",
                "S3": "S1 transform plus S2 family-balanced bounded distance",
            },
            "family_distance": "mean clipped squared delta within family, equal average across five families, sqrt",
            "delta_clip": DELTA_CLIP,
            "shell_schemes": cj.SHELL_SCHEMES,
            "primary_shell_scheme": PRIMARY_SCHEME,
            "prototype": "one_medoid_per_exact_label_no_split",
        },
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27ck Evidence-space Repair Summary",
            "",
            f"primary_verdict: `{verdict}`",
            "",
            f"- selected evidence space: `{selected['evidence_space']}`",
            f"- selected decision: `{selected['decision']}`",
            f"- active-strong regions: `{selected['active_strong_regions']}`",
            f"- active-strong semantic groups: `{selected['active_strong_semantic_groups']}`",
            f"- mean support-val nearest-label consistency: `{selected['mean_support_val_label_consistency']:.6f}`",
            f"- OOD-val nearest core+near rate: `{selected['ood_val_nearest_core_plus_near_rate']:.6f}`",
            "",
            "Close-out:",
            "",
            "```text",
            "solved: Audited four preregistered non-learned evidence spaces under the frozen support and role contract.",
            f"changed_mainline: {'yes' if selected['decision'] != 'STOP' else 'no'}.",
            f"active_blocker: {'strong region evidence remains limited to a small qualified subset' if selected['decision'] != 'STOP' else 'non-learned Kitsune115 region geometry remains unqualified'}.",
            "frozen: support rows, role order, four evidence spaces, shell rules, activation gates, and pre-stress selection.",
            "superseded: further raw-115D shell tuning or covariance swaps.",
            f"next_action: {next_action}.",
            "```",
        ],
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
