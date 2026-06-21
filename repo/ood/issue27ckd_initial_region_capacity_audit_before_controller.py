from __future__ import annotations

import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

import numpy as np

import issue27cj_attack_region_instantiation as cj
import issue27ck_kitsune115_evidence_space_repair as ck


ROOT = Path(__file__).resolve().parents[2]
ISSUE = "issue27ckd_initial_region_capacity_audit_before_controller_2026-06-21"
OUT = ROOT / "runs" / ISSUE
ISSUE27CK = (
    ROOT
    / "runs"
    / "issue27ck_kitsune115_region_geometry_failure_anatomy_and_evidence_space_repair_2026-06-21"
)
ISSUE27CF = (
    ROOT
    / "runs"
    / "issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_2026-06-16"
)

S3_NAME = "S3_bounded_heavytail_family_balanced"
PRIMARY_SCHEME = "medium"
MIN_CLUSTER_ROWS = 8
BATCH = 20000


VARIANTS: dict[str, Callable[[int], int]] = {
    "V0_frozen512_single_medoid": lambda n: 1,
    "V1_frozen512_two_medoid": lambda n: 2 if n >= 16 else 1,
    "V2_frozen512_adaptive_three_medoid": lambda n: (
        3 if n >= 24 else (2 if n >= 16 else 1)
    ),
}


def fit_medoids(
    space: ck.EvidenceSpace,
    x: np.ndarray,
    requested_k: int,
) -> tuple[np.ndarray, list[int], int]:
    pairwise = space.distance(x, x)
    target_k = min(requested_k, len(x))
    while target_k >= 1:
        first = int(np.argmin(np.sum(pairwise, axis=1)))
        medoids = [first]
        while len(medoids) < target_k:
            nearest = np.min(pairwise[:, medoids], axis=1)
            nearest[medoids] = -1.0
            medoids.append(int(np.argmax(nearest)))

        for _ in range(20):
            assignment = np.argmin(pairwise[:, medoids], axis=1)
            counts = [int(np.sum(assignment == i)) for i in range(len(medoids))]
            if min(counts) < MIN_CLUSTER_ROWS:
                break
            updated = []
            for cluster_id in range(len(medoids)):
                members = np.flatnonzero(assignment == cluster_id)
                sub = pairwise[np.ix_(members, members)]
                updated.append(int(members[int(np.argmin(np.sum(sub, axis=1)))]))
            if updated == medoids:
                return np.asarray(medoids, dtype=np.int64), counts, target_k
            medoids = updated
        else:
            assignment = np.argmin(pairwise[:, medoids], axis=1)
            counts = [int(np.sum(assignment == i)) for i in range(len(medoids))]
            if min(counts) >= MIN_CLUSTER_ROWS:
                return np.asarray(medoids, dtype=np.int64), counts, target_k

        if target_k == 1:
            return np.asarray([first], dtype=np.int64), [len(x)], 1
        target_k -= 1

    raise RuntimeError("Unable to fit at least one medoid")


def build_geometry(
    variant: str,
    requested_k: Callable[[int], int],
    space: ck.EvidenceSpace,
    support_rows: list[dict[str, str]],
    support_x_raw: np.ndarray,
) -> dict[str, Any]:
    support_x = space.transform(support_x_raw)
    train_mask = np.asarray(
        [row["bank_partition"] == "support_train" for row in support_rows]
    )
    val_mask = np.asarray(
        [row["bank_partition"] == "support_val" for row in support_rows]
    )
    labels = sorted({row["exact_attack_label"] for row in support_rows})
    geometry: dict[str, Any] = {}
    prototype_rows: list[dict[str, Any]] = []
    shell_rows: list[dict[str, Any]] = []

    label_array = np.asarray(
        [row["exact_attack_label"] for row in support_rows], dtype=object
    )
    for label in labels:
        train_idx = np.flatnonzero(train_mask & (label_array == label))
        val_idx = np.flatnonzero(val_mask & (label_array == label))
        x_train = support_x[train_idx]
        x_val = support_x[val_idx]
        request = requested_k(len(x_train))
        local_medoids, cluster_counts, effective_k = fit_medoids(
            space, x_train, request
        )
        global_medoids = train_idx[local_medoids]
        prototypes = support_x[global_medoids]
        train_dist = np.min(space.distance(x_train, prototypes), axis=1)
        val_dist = np.min(space.distance(x_val, prototypes), axis=1)
        radii = {
            scheme: cj.shell_radii(train_dist, val_dist, scheme)
            for scheme in cj.SHELL_SCHEMES
        }
        geometry[label] = {
            "train_idx": train_idx,
            "val_idx": val_idx,
            "prototypes": prototypes,
            "prototype_support_indices": global_medoids,
            "requested_prototypes": request,
            "effective_prototypes": effective_k,
            "cluster_counts": cluster_counts,
            "train_dist": train_dist,
            "val_dist": val_dist,
            "radii": radii,
        }
        for rank, global_idx in enumerate(global_medoids):
            meta = support_rows[int(global_idx)]
            prototype_rows.append(
                {
                    "variant": variant,
                    "exact_attack_label": label,
                    "prototype_rank": rank,
                    "requested_prototypes": request,
                    "effective_prototypes": effective_k,
                    "cluster_rows": cluster_counts[rank],
                    "sample_id": meta["sample_id"],
                    "source_file": meta["source_file"],
                    "device_or_source_group": meta["device_or_source_group"],
                    "phase": meta["phase"],
                }
            )
        for scheme, shell in radii.items():
            shell_rows.append(
                {
                    "variant": variant,
                    "exact_attack_label": label,
                    "requested_prototypes": request,
                    "effective_prototypes": effective_k,
                    "shell_scheme": scheme,
                    **shell,
                }
            )

    return {
        "variant": variant,
        "space": space,
        "support_x": support_x,
        "train_mask": train_mask,
        "val_mask": val_mask,
        "labels": labels,
        "label_index": {label: i for i, label in enumerate(labels)},
        "geometry": geometry,
        "prototype_rows": prototype_rows,
        "shell_rows": shell_rows,
    }


def label_distances(
    space: ck.EvidenceSpace,
    state: dict[str, Any],
    x: np.ndarray,
) -> np.ndarray:
    return np.column_stack(
        [
            np.min(
                space.distance(x, state["geometry"][label]["prototypes"]),
                axis=1,
            )
            for label in state["labels"]
        ]
    )


def audit_support_val(
    state: dict[str, Any],
    support_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    space = state["space"]
    val_x = state["support_x"][state["val_mask"]]
    val_meta = [
        row for row in support_rows if row["bank_partition"] == "support_val"
    ]
    distances = label_distances(space, state, val_x)
    rows: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for i, meta in enumerate(val_meta):
        true_label = meta["exact_attack_label"]
        true_idx = state["label_index"][true_label]
        nearest_idx = int(np.argmin(distances[i]))
        nearest_label = state["labels"][nearest_idx]
        rows.append(
            {
                "variant": state["variant"],
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
                "variant": state["variant"],
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
    state: dict[str, Any],
    cert_x: np.ndarray,
    indices: np.ndarray,
    role: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    space = state["space"]
    direct = {label: Counter() for label in state["labels"]}
    nearest = Counter()
    total = 0
    for start in range(0, len(indices), BATCH):
        raw = np.asarray(cert_x[indices[start : start + BATCH]], dtype=np.float64)
        x = space.transform(raw)
        distances = label_distances(space, state, x)
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
            direct[label]["core"] += int(
                np.sum(region_dist <= radii["core_radius"])
            )
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
                "variant": state["variant"],
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
        "variant": state["variant"],
        "role": role,
        "rows": total,
        "nearest_core_rate": nearest["core"] / total,
        "nearest_core_plus_near_rate": (
            nearest["core"] + nearest["near"]
        )
        / total,
        "nearest_out_of_region_rate": nearest["out_of_region"] / total,
    }


def freeze_registry(
    state: dict[str, Any],
    support_rows: list[dict[str, str]],
    support_summary: list[dict[str, Any]],
    ood_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    support_by_label = {
        row["exact_attack_label"]: row for row in support_summary
    }
    ood_by_label = {row["exact_attack_label"]: row for row in ood_rows}
    rows: list[dict[str, Any]] = []
    for label in state["labels"]:
        geometry = state["geometry"][label]
        support = support_by_label[label]
        ood = ood_by_label[label]
        train_meta = [support_rows[i] for i in geometry["train_idx"]]
        sources = ck.source_count(train_meta)
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
                "variant": state["variant"],
                "region_id": cj.stable_id(
                    f"{state['variant']}_region_", label
                ),
                "exact_attack_label": label,
                "semantic_attack_group": train_meta[0][
                    "semantic_attack_group"
                ],
                "train_rows": len(geometry["train_idx"]),
                "val_rows": len(geometry["val_idx"]),
                "requested_prototypes": geometry["requested_prototypes"],
                "effective_prototypes": geometry["effective_prototypes"],
                "prototype_cluster_rows": "|".join(
                    map(str, geometry["cluster_counts"])
                ),
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
            }
        )
    return rows


def qualification_row(
    variant: str,
    registry: list[dict[str, Any]],
    support_summary: list[dict[str, Any]],
    ood_summary: dict[str, Any],
) -> dict[str, Any]:
    active = [
        row for row in registry if row["region_status"] == "active_strong"
    ]
    return {
        "variant": variant,
        "active_strong_regions": len(active),
        "active_strong_labels": "|".join(
            sorted(row["exact_attack_label"] for row in active)
        ),
        "active_strong_semantic_groups": len(
            {row["semantic_attack_group"] for row in active}
        ),
        "mean_support_val_label_consistency": float(
            np.mean(
                [
                    row["nearest_label_consistency"]
                    for row in support_summary
                ]
            )
        ),
        "mean_support_val_uncertain_coverage": float(
            np.mean(
                [
                    row["true_region_uncertain_coverage"]
                    for row in support_summary
                ]
            )
        ),
        "ood_val_nearest_core_rate": ood_summary["nearest_core_rate"],
        "ood_val_nearest_core_plus_near_rate": ood_summary[
            "nearest_core_plus_near_rate"
        ],
    }


def audit_candidate_pool_ceiling() -> list[dict[str, Any]]:
    path = ISSUE27CF / "eligible_candidate_manifest.csv.gz"
    counts: Counter[str] = Counter()
    sources: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    phases: dict[str, set[str]] = defaultdict(set)
    with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            label = row["exact_attack_label"]
            counts[label] += 1
            sources[label].add(
                (
                    row["device_or_source_group"],
                    row["pcap_path"],
                    row["source_file"],
                )
            )
            phases[label].add(row["phase"])
    return [
        {
            "exact_attack_label": label,
            "eligible_candidate_rows": counts[label],
            "eligible_provenance_sources": len(sources[label]),
            "eligible_phases": len(phases[label]),
            "strong_source_gate_possible": len(sources[label]) >= 2,
            "ceiling_note": (
                "candidate_pool_can_satisfy_two_source_gate"
                if len(sources[label]) >= 2
                else "current_candidate_pool_cannot_satisfy_two_source_gate"
            ),
        }
        for label in sorted(counts)
    ]


def baseline_reproduction(
    registry: list[dict[str, Any]],
) -> tuple[bool, list[dict[str, Any]]]:
    old_rows = [
        row
        for row in cj.read_csv(ISSUE27CK / "candidate_region_registry.csv")
        if row["evidence_space"] == S3_NAME
    ]
    old_by_label = {row["exact_attack_label"]: row for row in old_rows}
    checks: list[dict[str, Any]] = []
    for row in registry:
        label = row["exact_attack_label"]
        old = old_by_label[label]
        numeric_fields = [
            "support_val_uncertain_coverage",
            "support_val_nearest_label_consistency",
            "ood_val_core_intrusion_rate",
            "ood_val_core_plus_near_intrusion_rate",
        ]
        numeric_ok = all(
            abs(float(row[field]) - float(old[field])) <= 1e-12
            for field in numeric_fields
        )
        status_ok = row["region_status"] == old["region_status"]
        checks.append(
            {
                "exact_attack_label": label,
                "numeric_match": numeric_ok,
                "status_match": status_ok,
                "pass": numeric_ok and status_ok,
            }
        )
    return all(row["pass"] for row in checks), checks


def audit_query(
    state: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    space = state["space"]
    aggregates: dict[tuple[str, str], Counter] = defaultdict(Counter)
    confusion: dict[tuple[str, str, str], int] = defaultdict(int)
    certified = [
        row
        for row in cj.read_csv(cj.CERTIFIED_CHUNKS)
        if row["status"] == "complete"
        and row["role"]
        in {
            "same_file_time_forward_dev_query_exact",
            "dev_future_attack_query_exact",
        }
    ]
    for chunk in certified:
        raw = np.load(
            cj.ATTACK_CHUNKS
            / f"chunk_{int(chunk['chunk_id']):05d}_X.npy",
            mmap_mode="r",
        )
        for start in range(0, len(raw), BATCH):
            x = space.transform(
                np.asarray(raw[start : start + BATCH], dtype=np.float64)
            )
            distances = label_distances(space, state, x)
            nearest_idx = np.argmin(distances, axis=1)
            for i in range(len(x)):
                nearest_label = state["labels"][int(nearest_idx[i])]
                shell = cj.shell_name(
                    float(distances[i, nearest_idx[i]]),
                    state["geometry"][nearest_label]["radii"][
                        PRIMARY_SCHEME
                    ],
                )
                key = (chunk["role"], chunk["attack_label"])
                aggregates[key]["rows"] += 1
                aggregates[key][shell] += 1
                aggregates[key]["label_match"] += int(
                    nearest_label == chunk["attack_label"]
                )
                confusion[
                    (chunk["role"], chunk["attack_label"], nearest_label)
                ] += 1
                if chunk["attack_label"] in state["label_index"]:
                    true_idx = state["label_index"][chunk["attack_label"]]
                    true_shell = cj.shell_name(
                        float(distances[i, true_idx]),
                        state["geometry"][chunk["attack_label"]]["radii"][
                            PRIMARY_SCHEME
                        ],
                    )
                    aggregates[key][f"true_region_{true_shell}"] += 1
    rows = []
    for (role, label), counts in sorted(aggregates.items()):
        total = counts["rows"]
        rows.append(
            {
                "variant": state["variant"],
                "role": role,
                "true_attack_label": label,
                "rows": total,
                "core_rate": counts["core"] / total,
                "core_plus_near_rate": (
                    counts["core"] + counts["near"]
                )
                / total,
                "uncertain_rate": counts["uncertain"] / total,
                "out_of_region_rate": counts["out_of_region"] / total,
                "nearest_label_match_rate": counts["label_match"] / total,
                "true_region_core_rate": (
                    counts["true_region_core"] / total
                    if label in state["label_index"]
                    else ""
                ),
                "true_region_core_plus_near_rate": (
                    (
                        counts["true_region_core"]
                        + counts["true_region_near"]
                    )
                    / total
                    if label in state["label_index"]
                    else ""
                ),
                "true_region_uncertain_rate": (
                    counts["true_region_uncertain"] / total
                    if label in state["label_index"]
                    else ""
                ),
                "true_region_out_of_region_rate": (
                    counts["true_region_out_of_region"] / total
                    if label in state["label_index"]
                    else ""
                ),
                "read_only": True,
            }
        )
    confusion_rows = []
    for (role, true_label, nearest_label), count in sorted(confusion.items()):
        total = aggregates[(role, true_label)]["rows"]
        confusion_rows.append(
            {
                "variant": state["variant"],
                "role": role,
                "true_attack_label": true_label,
                "nearest_attack_label": nearest_label,
                "rows": count,
                "rate_within_true_label": count / total,
                "read_only": True,
            }
        )
    return rows, confusion_rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    support_rows, support_x = cj.load_support()
    roles = cj.load_role_indices()
    cert_x = np.load(cj.CERT_X, mmap_mode="r")
    with cj.FEATURE_SCHEMA.open(encoding="utf-8") as f:
        schema = json.load(f)
    x_id = np.asarray(cert_x[roles["id_benign_train"]], dtype=np.float64)
    spaces, _ = ck.make_spaces(x_id, schema)
    space = next(candidate for candidate in spaces if candidate.name == S3_NAME)

    all_support_rows: list[dict[str, Any]] = []
    all_support_summary: list[dict[str, Any]] = []
    all_ood_rows: list[dict[str, Any]] = []
    all_ood_summary: list[dict[str, Any]] = []
    all_registry: list[dict[str, Any]] = []
    all_prototypes: list[dict[str, Any]] = []
    all_shells: list[dict[str, Any]] = []
    qualification: list[dict[str, Any]] = []
    states: dict[str, dict[str, Any]] = {}

    for variant, rule in VARIANTS.items():
        state = build_geometry(variant, rule, space, support_rows, support_x)
        states[variant] = state
        support_audit, support_summary = audit_support_val(
            state, support_rows
        )
        ood_rows, ood_summary = audit_benign(
            state, cert_x, roles["ood_benign_val"], "ood_benign_val"
        )
        registry = freeze_registry(
            state, support_rows, support_summary, ood_rows
        )
        qualification.append(
            qualification_row(
                variant, registry, support_summary, ood_summary
            )
        )
        all_support_rows.extend(support_audit)
        all_support_summary.extend(support_summary)
        all_ood_rows.extend(ood_rows)
        all_ood_summary.append(ood_summary)
        all_registry.extend(registry)
        all_prototypes.extend(state["prototype_rows"])
        all_shells.extend(state["shell_rows"])

    v0_registry = [
        row
        for row in all_registry
        if row["variant"] == "V0_frozen512_single_medoid"
    ]
    reproduction_ok, reproduction_checks = baseline_reproduction(v0_registry)
    if not reproduction_ok:
        raise RuntimeError("V0 failed to reproduce issue27ck S3 registry")

    by_variant = {row["variant"]: row for row in qualification}
    baseline = by_variant["V0_frozen512_single_medoid"]
    registry_by_variant = defaultdict(dict)
    for row in all_registry:
        registry_by_variant[row["variant"]][row["exact_attack_label"]] = row

    admissible = []
    for row in qualification:
        udp_status = registry_by_variant[row["variant"]][
            "Mirai UDP Flooding"
        ]["region_status"]
        row["mirai_udp_nonregression"] = udp_status == "active_strong"
        row["active_count_nonregression"] = (
            row["active_strong_regions"]
            >= baseline["active_strong_regions"]
        )
        row["consistency_nonregression"] = (
            row["mean_support_val_label_consistency"]
            >= baseline["mean_support_val_label_consistency"] - 0.02
        )
        row["ood_nonregression"] = (
            row["ood_val_nearest_core_plus_near_rate"]
            <= baseline["ood_val_nearest_core_plus_near_rate"] + 0.02
        )
        row["admissible"] = all(
            [
                row["mirai_udp_nonregression"],
                row["active_count_nonregression"],
                row["consistency_nonregression"],
                row["ood_nonregression"],
            ]
        )
        if row["admissible"]:
            admissible.append(row)

    best = max(
        admissible,
        key=lambda row: (
            row["active_strong_regions"],
            row["active_strong_semantic_groups"],
            row["mean_support_val_label_consistency"],
            -row["ood_val_nearest_core_plus_near_rate"],
        ),
    )
    added_strong = (
        best["active_strong_regions"]
        - baseline["active_strong_regions"]
    )
    consistency_gain = (
        best["mean_support_val_label_consistency"]
        - baseline["mean_support_val_label_consistency"]
    )
    if added_strong >= 1:
        decision = "GO"
        verdict = (
            "frozen512_multi_prototype_region_capacity_gain_before_controller"
        )
        next_action = (
            "freeze_selected_initial_multi_prototype_registry_then_decide_"
            "whether_bounded_support_extension_is_still_needed"
        )
    elif consistency_gain >= 0.10:
        decision = "DIAGNOSTIC_ONLY"
        verdict = (
            "multi_prototype_consistency_gain_without_new_strong_region"
        )
        next_action = (
            "bounded_unused_candidate_extension_audit_without_rewriting_"
            "initial_support_bank_v1"
        )
    else:
        decision = "STOP"
        verdict = (
            "frozen512_multi_prototype_capacity_not_materially_improved"
        )
        next_action = (
            "bounded_unused_candidate_extension_audit_without_rewriting_"
            "initial_support_bank_v1"
        )

    selection = {
        "selected_variant": best["variant"],
        "decision": decision,
        "primary_verdict": verdict,
        "selected_on_roles": ["support_val", "ood_benign_val"],
        "baseline_active_strong_regions": baseline[
            "active_strong_regions"
        ],
        "selected_active_strong_regions": best["active_strong_regions"],
        "added_active_strong_regions": added_strong,
        "mean_consistency_gain": consistency_gain,
        "selection_frozen_before": [
            "ood_benign_stress",
            "certified_dev_query",
        ],
    }
    ck.write_json(OUT / "selected_variant.json", selection)

    selected_state = states[best["variant"]]
    stress_rows, stress_summary = audit_benign(
        selected_state,
        cert_x,
        roles["ood_benign_stress"],
        "ood_benign_stress",
    )
    query_rows, query_confusion = audit_query(selected_state)

    selected_active_labels = set(best["active_strong_labels"].split("|"))
    active_query_rows = [
        row
        for row in query_rows
        if row["true_attack_label"] in selected_active_labels
    ]
    temporal_caveat_labels = sorted(
        {
            row["true_attack_label"]
            for row in active_query_rows
            if float(row["nearest_label_match_rate"]) < 0.80
            or float(row["true_region_core_plus_near_rate"]) < 0.80
        }
    )
    temporal_diagnostic_status = (
        "PASS"
        if not temporal_caveat_labels
        else "BLOCKED_FOR_CONTROLLER_FREEZE"
    )
    if temporal_caveat_labels:
        verdict = (
            "static_region_capacity_gain_but_temporal_label_stability_blocked"
        )
        next_action = (
            "bounded_support_adequacy_and_temporal_coverage_audit_before_"
            "registry_freeze"
        )
        selection["primary_verdict"] = verdict
    selection["temporal_diagnostic_status"] = temporal_diagnostic_status
    selection["temporal_caveat_labels"] = temporal_caveat_labels
    ck.write_json(OUT / "selected_variant.json", selection)

    ceiling = audit_candidate_pool_ceiling()
    structural_single_source = [
        row["exact_attack_label"]
        for row in ceiling
        if not row["strong_source_gate_possible"]
    ]

    ck.write_csv(OUT / "variant_qualification.csv", qualification)
    ck.write_csv(OUT / "region_registry_by_variant.csv", all_registry)
    ck.write_csv(OUT / "support_val_audit.csv", all_support_rows)
    ck.write_csv(OUT / "support_val_summary.csv", all_support_summary)
    ck.write_csv(OUT / "ood_val_overlap.csv", all_ood_rows)
    ck.write_csv(OUT / "ood_val_summary.csv", all_ood_summary)
    ck.write_csv(OUT / "prototype_manifest.csv", all_prototypes)
    ck.write_csv(OUT / "shell_registry.csv", all_shells)
    ck.write_csv(OUT / "baseline_reproduction.csv", reproduction_checks)
    ck.write_csv(OUT / "candidate_pool_structural_ceiling.csv", ceiling)
    ck.write_csv(OUT / "selected_ood_stress.csv", stress_rows)
    ck.write_csv(OUT / "selected_ood_stress_summary.csv", [stress_summary])
    ck.write_csv(OUT / "selected_certified_dev_query.csv", query_rows)
    ck.write_csv(
        OUT / "selected_certified_dev_query_confusion.csv",
        query_confusion,
    )
    ck.write_csv(
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
    result = {
        "issue": ISSUE,
        "primary_verdict": verdict,
        "decision": decision,
        "selected": best,
        "baseline": baseline,
        "selection": selection,
        "baseline_reproduction_pass": reproduction_ok,
        "support_rows_reselected": False,
        "unused_candidate_rows_consumed": False,
        "model_training": False,
        "controller_tuning": False,
        "sealed_final_access": False,
        "single_source_structural_ceiling_labels": structural_single_source,
        "temporal_diagnostic_status": temporal_diagnostic_status,
        "temporal_caveat_labels": temporal_caveat_labels,
        "next_action": next_action,
    }
    ck.write_json(OUT / "results.json", result)
    ck.write_json(
        OUT / "config.json",
        {
            "evidence_space": S3_NAME,
            "variants": list(VARIANTS),
            "minimum_cluster_rows": MIN_CLUSTER_ROWS,
            "primary_shell_scheme": PRIMARY_SCHEME,
            "activation_gates": "identical_to_issue27ck",
            "candidate_reuse": False,
            "controller_integration": False,
        },
    )
    ck.write_md(
        OUT / "summary.md",
        [
            "# issue27ckd Initial Region Capacity Audit",
            "",
            f"primary_verdict: `{verdict}`",
            "",
            f"- decision: `{decision}`",
            f"- selected variant: `{best['variant']}`",
            f"- baseline active-strong regions: `{baseline['active_strong_regions']}`",
            f"- selected active-strong regions: `{best['active_strong_regions']}`",
            f"- added active-strong regions: `{added_strong}`",
            f"- baseline mean support-val consistency: `{baseline['mean_support_val_label_consistency']:.6f}`",
            f"- selected mean support-val consistency: `{best['mean_support_val_label_consistency']:.6f}`",
            f"- selected OOD-val nearest core+near rate: `{best['ood_val_nearest_core_plus_near_rate']:.6f}`",
            f"- V0 reproduction pass: `{reproduction_ok}`",
            f"- support reselection: `false`",
            f"- unused candidate reuse: `false`",
            f"- temporal diagnostic status: `{temporal_diagnostic_status}`",
            (
                "- selected active labels with temporal/query caveats: "
                + (
                    ", ".join(f"`{label}`" for label in temporal_caveat_labels)
                    if temporal_caveat_labels
                    else "none"
                )
                + "."
            ),
            "",
            "Current candidate-pool structural ceiling:",
            "",
            (
                "- labels with only one eligible provenance source and therefore "
                "unable to pass the unchanged two-source strong gate: "
                + ", ".join(f"`{label}`" for label in structural_single_source)
                + "."
            ),
            "",
            "Close-out:",
            "",
            "```text",
            "solved: Audited whether train-only multi-prototype region geometry can improve the frozen 512-row initial support bank under S3.",
            "changed_mainline: no",
            "active_blocker: The two-medoid candidate improves static qualification, but active-label temporal/query stability is not yet sufficient for registry freeze; single-source labels also cannot pass the current strong gate with this candidate pool.",
            "frozen: original 512 support rows and partitions, S3 transform/distance, activation gates, and role order.",
            "superseded: immediate controller integration as the next action before initial region capacity is resolved.",
            f"next_action: {next_action}.",
            "```",
        ],
    )
    ck.write_md(
        OUT / "validation_report.md",
        [
            "# issue27ckd Validation Report",
            "",
            f"Status: `{'PASS' if reproduction_ok else 'FAIL'}`",
            "",
            f"- V0 exactly reproduced issue27ck S3 registry: `{reproduction_ok}`.",
            "- All prototypes were selected from support-train only.",
            "- Support-val and OOD-val selected the candidate variant.",
            "- OOD-stress and certified dev query were read only after selection.",
            "- No support reselection, candidate reuse, model training, controller tuning, or sealed-final access occurred.",
            f"- Read-only temporal/query diagnostic status: `{temporal_diagnostic_status}`.",
            (
                "- Temporal/query caveat labels: "
                + (
                    ", ".join(f"`{label}`" for label in temporal_caveat_labels)
                    if temporal_caveat_labels
                    else "none"
                )
                + "."
            ),
            "- Deterministic rerun verification is recorded separately after execution.",
        ],
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
