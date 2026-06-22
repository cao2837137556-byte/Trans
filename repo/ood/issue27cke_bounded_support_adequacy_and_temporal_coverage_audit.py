from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

import issue27cf_initial_support_bank_instantiation as cf
import issue27cj_attack_region_instantiation as cj
import issue27ck_kitsune115_evidence_space_repair as ck
import issue27ckd_initial_region_capacity_audit_before_controller as ckd


ROOT = Path(__file__).resolve().parents[2]
ISSUE = (
    "issue27cke_bounded_support_adequacy_and_temporal_coverage_audit_"
    "before_registry_freeze_2026-06-22"
)
OUT = ROOT / "runs" / ISSUE
S3_NAME = "S3_bounded_heavytail_family_balanced"
BASE_VARIANT = "B0_frozen512_two_medoid"
EXT64_VARIANT = "E64_nested_source_time_balanced"
EXT128_VARIANT = "E128_nested_source_time_balanced"
TIME_BINS = 4
BATCH = 20000


def two_medoid_rule(n: int) -> int:
    return 2 if n >= 16 else 1


def source_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row["device_or_source_group"]),
        str(row["pcap_path"]),
        str(row["source_file"]),
    )


def allocate_e64(
    unused_counts: dict[str, int],
    base_train_counts: dict[str, int],
) -> dict[str, int]:
    labels = sorted(unused_counts)
    alloc = {label: min(4, unused_counts[label]) for label in labels}
    remaining = 64 - sum(alloc.values())
    while remaining > 0:
        eligible = [
            label
            for label in labels
            if alloc[label] < 8 and alloc[label] < unused_counts[label]
        ]
        if not eligible:
            raise RuntimeError("Unable to allocate the preregistered E64 budget")
        chosen = max(
            eligible,
            key=lambda label: (
                math.sqrt(unused_counts[label])
                / (base_train_counts[label] + alloc[label] + 1),
                label,
            ),
        )
        alloc[chosen] += 1
        remaining -= 1
    return alloc


def kcenter_order(
    space: ck.EvidenceSpace,
    transformed: np.ndarray,
    indices: list[int],
    limit: int,
) -> list[int]:
    if not indices or limit <= 0:
        return []
    local = transformed[np.asarray(indices, dtype=np.int64)]
    centroid = np.mean(local, axis=0)
    first = int(np.argmin(space.distance(local, centroid[None, :])[:, 0]))
    chosen_local = [first]
    nearest = space.distance(local, local[first : first + 1])[:, 0]
    nearest[first] = -1.0
    while len(chosen_local) < min(limit, len(indices)):
        nxt = int(np.argmax(nearest))
        chosen_local.append(nxt)
        distance = space.distance(local, local[nxt : nxt + 1])[:, 0]
        nearest = np.minimum(nearest, distance)
        nearest[chosen_local] = -1.0
    return [indices[i] for i in chosen_local]


def build_time_bins(
    candidates: list[dict[str, Any]],
    indices: list[int],
) -> dict[int, int]:
    by_source: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for idx in indices:
        by_source[source_key(candidates[idx])].append(idx)
    bins: dict[int, int] = {}
    for source in sorted(by_source):
        ordered = sorted(
            by_source[source],
            key=lambda idx: (
                float(candidates[idx]["csv_timestamp"]),
                candidates[idx]["global_candidate_id"],
            ),
        )
        n = len(ordered)
        for rank, idx in enumerate(ordered):
            bins[idx] = min(TIME_BINS - 1, int(rank * TIME_BINS / n))
    return bins


def stratified_selection_order(
    space: ck.EvidenceSpace,
    transformed: np.ndarray,
    candidates: list[dict[str, Any]],
    label_indices: list[int],
    limit: int,
) -> tuple[list[int], dict[int, int]]:
    time_bins = build_time_bins(candidates, label_indices)
    strata: dict[tuple[str, str, str, int], list[int]] = defaultdict(list)
    for idx in label_indices:
        strata[(*source_key(candidates[idx]), time_bins[idx])].append(idx)
    local_orders = {
        stratum: kcenter_order(
            space, transformed, indices, min(limit, len(indices))
        )
        for stratum, indices in strata.items()
    }
    positions = {stratum: 0 for stratum in strata}
    selected_per_stratum = Counter()
    selected: list[int] = []
    while len(selected) < min(limit, len(label_indices)):
        available = [
            stratum
            for stratum in sorted(strata)
            if positions[stratum] < len(local_orders[stratum])
        ]
        if not available:
            break
        chosen_stratum = min(
            available,
            key=lambda stratum: (
                selected_per_stratum[stratum],
                -len(strata[stratum]),
                stratum,
            ),
        )
        selected.append(
            local_orders[chosen_stratum][positions[chosen_stratum]]
        )
        positions[chosen_stratum] += 1
        selected_per_stratum[chosen_stratum] += 1
    return selected, time_bins


def extension_row(
    candidate: dict[str, Any],
    rank: int,
    label_rank: int,
    time_bin: int,
) -> dict[str, Any]:
    row = dict(candidate)
    row.update(
        {
            "sample_id": f"issue27cke_ext_{rank:04d}",
            "asset_version": "issue27cke_dev_extension_candidate_v1",
            "selection_round": "bounded_source_time_extension_audit",
            "selection_reason": "source_time_stratified_s3_kcenter",
            "selection_rank_within_label": label_rank,
            "bank_partition": "support_train",
            "memory_status": "dev_extension_candidate_not_frozen",
            "extension_time_bin": time_bin,
        }
    )
    return row


def build_variant(
    name: str,
    base_rows: list[dict[str, str]],
    base_x: np.ndarray,
    extension_indices: list[int],
    candidates: list[dict[str, Any]],
    candidate_x: np.ndarray,
    time_bins: dict[int, int],
) -> tuple[list[dict[str, Any]], np.ndarray]:
    extension_rows = []
    label_rank = Counter()
    for rank, idx in enumerate(extension_indices):
        label = candidates[idx]["exact_attack_label"]
        extension_rows.append(
            extension_row(
                candidates[idx],
                rank,
                label_rank[label],
                time_bins[idx],
            )
        )
        label_rank[label] += 1
    rows = [dict(row) for row in base_rows] + extension_rows
    x = (
        np.vstack([base_x, candidate_x[extension_indices]])
        if extension_indices
        else np.asarray(base_x)
    )
    for row in rows:
        row["audit_variant"] = name
    return rows, x


def candidate_coverage_rows(
    candidates: list[dict[str, Any]],
    unused_by_label: dict[str, list[int]],
    time_bins_by_label: dict[str, dict[int, int]],
    selected64: set[int],
    selected128: set[int],
) -> list[dict[str, Any]]:
    rows = []
    for label in sorted(unused_by_label):
        grouped: dict[tuple[str, str, str, int], list[int]] = defaultdict(list)
        for idx in unused_by_label[label]:
            grouped[
                (
                    *source_key(candidates[idx]),
                    time_bins_by_label[label][idx],
                )
            ].append(idx)
        for stratum, indices in sorted(grouped.items()):
            timestamps = [float(candidates[idx]["csv_timestamp"]) for idx in indices]
            rows.append(
                {
                    "exact_attack_label": label,
                    "device_or_source_group": stratum[0],
                    "pcap_path": stratum[1],
                    "source_file": stratum[2],
                    "time_bin": stratum[3],
                    "unused_candidate_rows": len(indices),
                    "timestamp_min": min(timestamps),
                    "timestamp_max": max(timestamps),
                    "selected_e64_rows": sum(idx in selected64 for idx in indices),
                    "selected_e128_rows": sum(idx in selected128 for idx in indices),
                }
            )
    return rows


def evaluate_static(
    variant: str,
    rows: list[dict[str, Any]],
    x: np.ndarray,
    space: ck.EvidenceSpace,
    cert_x: np.ndarray,
    roles: dict[str, np.ndarray],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    state = ckd.build_geometry(variant, two_medoid_rule, space, rows, x)
    support_audit, support_summary = ckd.audit_support_val(state, rows)
    ood_rows, ood_summary = ckd.audit_benign(
        state, cert_x, roles["ood_benign_val"], "ood_benign_val"
    )
    registry = ckd.freeze_registry(state, rows, support_summary, ood_rows)
    qualification = ckd.qualification_row(
        variant, registry, support_summary, ood_summary
    )
    return (
        state,
        qualification,
        registry,
        support_audit,
        support_summary,
        ood_rows,
        ood_summary,
    )


def query_metric_map(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(row["role"], row["true_attack_label"]): row for row in rows}


def exact_mcnemar_pvalue(old_only: int, new_only: int) -> float:
    discordant = old_only + new_only
    if discordant == 0:
        return 1.0
    tail = sum(
        math.comb(discordant, k) * (0.5**discordant)
        for k in range(min(old_only, new_only) + 1)
    )
    return min(1.0, 2.0 * tail)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base_rows, base_x = cj.load_support()
    derived = cf.find_derived_root()
    candidates, candidate_x, _, _, _ = cf.load_support_candidates(derived)
    candidate_by_id = {
        row["global_candidate_id"]: idx for idx, row in enumerate(candidates)
    }

    alignment_rows = []
    for support_idx, row in enumerate(base_rows):
        candidate_idx = candidate_by_id[row["global_candidate_id"]]
        max_abs = float(
            np.max(
                np.abs(
                    np.asarray(base_x[support_idx], dtype=np.float64)
                    - np.asarray(candidate_x[candidate_idx], dtype=np.float64)
                )
            )
        )
        alignment_rows.append(
            {
                "sample_id": row["sample_id"],
                "global_candidate_id": row["global_candidate_id"],
                "max_abs_feature_delta": max_abs,
                "pass": max_abs <= 1e-6,
            }
        )
    if not all(row["pass"] for row in alignment_rows):
        raise RuntimeError("Frozen support/candidate feature alignment failed")

    roles = cj.load_role_indices()
    cert_x = np.load(cj.CERT_X, mmap_mode="r")
    with cj.FEATURE_SCHEMA.open(encoding="utf-8") as f:
        schema = json.load(f)
    x_id = np.asarray(cert_x[roles["id_benign_train"]], dtype=np.float64)
    spaces, _ = ck.make_spaces(x_id, schema)
    space = next(candidate for candidate in spaces if candidate.name == S3_NAME)
    transformed_candidates = space.transform(candidate_x)

    selected_ids = {row["global_candidate_id"] for row in base_rows}
    unused_by_label: dict[str, list[int]] = defaultdict(list)
    for idx, row in enumerate(candidates):
        if row["global_candidate_id"] not in selected_ids:
            unused_by_label[row["exact_attack_label"]].append(idx)
    base_train_counts = Counter(
        row["exact_attack_label"]
        for row in base_rows
        if row["bank_partition"] == "support_train"
    )
    unused_counts = {label: len(indices) for label, indices in unused_by_label.items()}
    alloc64 = allocate_e64(unused_counts, dict(base_train_counts))
    alloc128 = {label: 2 * count for label, count in alloc64.items()}
    if sum(alloc64.values()) != 64 or sum(alloc128.values()) != 128:
        raise RuntimeError("Extension allocation budget mismatch")

    orders: dict[str, list[int]] = {}
    time_bins_by_label: dict[str, dict[int, int]] = {}
    for label in sorted(unused_by_label):
        order, time_bins = stratified_selection_order(
            space,
            transformed_candidates,
            candidates,
            unused_by_label[label],
            alloc128[label],
        )
        if len(order) != alloc128[label]:
            raise RuntimeError(f"Insufficient extension order for {label}")
        orders[label] = order
        time_bins_by_label[label] = time_bins

    extension64 = [
        idx
        for label in sorted(orders)
        for idx in orders[label][: alloc64[label]]
    ]
    extension128 = [
        idx
        for label in sorted(orders)
        for idx in orders[label][: alloc128[label]]
    ]
    if not set(extension64).issubset(extension128):
        raise RuntimeError("E64 is not nested inside E128")
    all_time_bins = {
        idx: time_bin
        for mapping in time_bins_by_label.values()
        for idx, time_bin in mapping.items()
    }

    variant_data = {
        BASE_VARIANT: build_variant(
            BASE_VARIANT,
            base_rows,
            base_x,
            [],
            candidates,
            candidate_x,
            all_time_bins,
        ),
        EXT64_VARIANT: build_variant(
            EXT64_VARIANT,
            base_rows,
            base_x,
            extension64,
            candidates,
            candidate_x,
            all_time_bins,
        ),
        EXT128_VARIANT: build_variant(
            EXT128_VARIANT,
            base_rows,
            base_x,
            extension128,
            candidates,
            candidate_x,
            all_time_bins,
        ),
    }

    states = {}
    qualifications = []
    all_registry = []
    all_support_audit = []
    all_support_summary = []
    all_ood_rows = []
    all_ood_summary = []
    all_prototypes = []
    all_shells = []
    for variant, (rows, x) in variant_data.items():
        (
            state,
            qualification,
            registry,
            support_audit,
            support_summary,
            ood_rows,
            ood_summary,
        ) = evaluate_static(variant, rows, x, space, cert_x, roles)
        states[variant] = state
        qualification["extension_rows"] = len(rows) - len(base_rows)
        qualifications.append(qualification)
        all_registry.extend(registry)
        all_support_audit.extend(support_audit)
        all_support_summary.extend(support_summary)
        all_ood_rows.extend(ood_rows)
        all_ood_summary.append(ood_summary)
        all_prototypes.extend(state["prototype_rows"])
        all_shells.extend(state["shell_rows"])

    by_variant = {row["variant"]: row for row in qualifications}
    baseline = by_variant[BASE_VARIANT]
    registry_map = defaultdict(dict)
    for row in all_registry:
        registry_map[row["variant"]][row["exact_attack_label"]] = row
    admissible = []
    for row in qualifications:
        row["mirai_udp_nonregression"] = (
            registry_map[row["variant"]]["Mirai UDP Flooding"]["region_status"]
            == "active_strong"
        )
        row["active_count_nonregression"] = (
            row["active_strong_regions"] >= baseline["active_strong_regions"]
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
    selected = max(
        admissible,
        key=lambda row: (
            row["active_strong_regions"],
            row["active_strong_semantic_groups"],
            row["mean_support_val_label_consistency"],
            -row["ood_val_nearest_core_plus_near_rate"],
            -row["extension_rows"],
        ),
    )
    selection = {
        "selected_variant": selected["variant"],
        "selected_on_roles": ["support_val", "ood_benign_val"],
        "historical_query_used_for_selection": False,
        "sealed_final_access": False,
        "selection_frozen_before_reused_diagnostics": True,
    }
    ck.write_json(OUT / "frozen_static_variant_selection.json", selection)

    diagnostic_variants = [BASE_VARIANT]
    if selected["variant"] != BASE_VARIANT:
        diagnostic_variants.append(selected["variant"])
    query_rows_all = []
    query_confusion_all = []
    stress_rows_all = []
    stress_summary_all = []
    for variant in diagnostic_variants:
        query_rows, confusion_rows = ckd.audit_query(states[variant])
        for row in query_rows:
            row["evidence_status"] = (
                "reused_development_diagnostic_not_fresh_validation"
            )
        for row in confusion_rows:
            row["evidence_status"] = (
                "reused_development_diagnostic_not_fresh_validation"
            )
        stress_rows, stress_summary = ckd.audit_benign(
            states[variant],
            cert_x,
            roles["ood_benign_stress"],
            "ood_benign_stress",
        )
        for row in stress_rows:
            row["evidence_status"] = (
                "reused_development_diagnostic_not_fresh_validation"
            )
        stress_summary["evidence_status"] = (
            "reused_development_diagnostic_not_fresh_validation"
        )
        query_rows_all.extend(query_rows)
        query_confusion_all.extend(confusion_rows)
        stress_rows_all.extend(stress_rows)
        stress_summary_all.append(stress_summary)

    selected_query = [
        row for row in query_rows_all if row["variant"] == selected["variant"]
    ]
    selected_active = {
        row["exact_attack_label"]
        for row in all_registry
        if row["variant"] == selected["variant"]
        and row["region_status"] == "active_strong"
    }
    diagnostic_pass_by_label = {}
    for label in sorted(selected_active):
        label_rows = [
            row for row in selected_query if row["true_attack_label"] == label
        ]
        diagnostic_pass_by_label[label] = (
            len(label_rows) >= 2
            and all(
                float(row["nearest_label_match_rate"]) >= 0.80
                and float(row["true_region_core_plus_near_rate"]) >= 0.80
                for row in label_rows
            )
        )
    historical_pass_labels = sorted(
        label for label, passed in diagnostic_pass_by_label.items() if passed
    )

    support_audit_by_variant = defaultdict(dict)
    for row in all_support_audit:
        support_audit_by_variant[row["variant"]][row["sample_id"]] = row
    paired_rows = []
    old_only = 0
    new_only = 0
    both_correct = 0
    both_wrong = 0
    for sample_id, old in sorted(support_audit_by_variant[BASE_VARIANT].items()):
        new = support_audit_by_variant[selected["variant"]][sample_id]
        old_correct = old["true_attack_label"] == old["nearest_attack_label"]
        new_correct = new["true_attack_label"] == new["nearest_attack_label"]
        if old_correct and new_correct:
            both_correct += 1
        elif old_correct and not new_correct:
            old_only += 1
        elif not old_correct and new_correct:
            new_only += 1
        else:
            both_wrong += 1
        if old_correct != new_correct:
            paired_rows.append(
                {
                    "sample_id": sample_id,
                    "true_attack_label": old["true_attack_label"],
                    "baseline_nearest_label": old["nearest_attack_label"],
                    "selected_nearest_label": new["nearest_attack_label"],
                    "baseline_correct": old_correct,
                    "selected_correct": new_correct,
                }
            )
    paired_summary = {
        "baseline_variant": BASE_VARIANT,
        "selected_variant": selected["variant"],
        "rows": len(support_audit_by_variant[BASE_VARIANT]),
        "both_correct": both_correct,
        "baseline_only_correct": old_only,
        "selected_only_correct": new_only,
        "both_wrong": both_wrong,
        "baseline_row_accuracy": (both_correct + old_only)
        / len(support_audit_by_variant[BASE_VARIANT]),
        "selected_row_accuracy": (both_correct + new_only)
        / len(support_audit_by_variant[BASE_VARIANT]),
        "net_correct_rows": new_only - old_only,
        "exact_mcnemar_two_sided_p": exact_mcnemar_pvalue(old_only, new_only),
    }
    static_gain_material = (
        selected["active_strong_regions"] > baseline["active_strong_regions"]
        or paired_summary["exact_mcnemar_two_sided_p"] < 0.05
    )

    stress_map = {
        (row["variant"], row["exact_attack_label"]): row
        for row in stress_rows_all
    }
    stress_comparison = []
    stress_caveat_labels = []
    for label in sorted(selected_active):
        old = stress_map[(BASE_VARIANT, label)]
        new = stress_map[(selected["variant"], label)]
        delta = float(new["direct_core_plus_near_rate"]) - float(
            old["direct_core_plus_near_rate"]
        )
        stress_comparison.append(
            {
                "exact_attack_label": label,
                "baseline_core_plus_near_rate": old[
                    "direct_core_plus_near_rate"
                ],
                "selected_core_plus_near_rate": new[
                    "direct_core_plus_near_rate"
                ],
                "delta": delta,
                "descriptive_caveat_over_0_01": delta > 0.01,
                "evidence_status": (
                    "reused_development_diagnostic_not_preregistered_"
                    "selection_gate"
                ),
            }
        )
        if delta > 0.01:
            stress_caveat_labels.append(label)

    if selected["variant"] == BASE_VARIANT:
        verdict = "bounded_support_extension_no_static_gain_stop_recipe"
        next_action = (
            "repair_temporal_representation_or_materialize_new_support_sources"
        )
    elif historical_pass_labels and stress_caveat_labels:
        verdict = (
            "attack_coverage_gain_with_ood_stress_tradeoff_requires_fresh_"
            "attack_and_benign_holdout"
        )
        next_action = (
            "reserve_or_materialize_fresh_temporal_attack_and_benign_ood_"
            "holdout_before_any_registry_freeze"
        )
    elif historical_pass_labels:
        verdict = (
            "bounded_extension_promising_but_requires_fresh_temporal_holdout"
        )
        next_action = (
            "reserve_or_materialize_fresh_temporal_holdout_before_registry_freeze"
        )
    else:
        verdict = (
            "static_extension_gain_without_historical_temporal_closure"
        )
        next_action = (
            "stop_more_same_pool_expansion_and_repair_temporal_"
            "representation_or_new_source_coverage"
        )

    extension_manifest = []
    for label in sorted(orders):
        for rank, idx in enumerate(orders[label]):
            candidate = candidates[idx]
            extension_manifest.append(
                {
                    "global_candidate_id": candidate["global_candidate_id"],
                    "exact_attack_label": label,
                    "selection_rank_within_label": rank,
                    "included_e64": rank < alloc64[label],
                    "included_e128": rank < alloc128[label],
                    "device_or_source_group": candidate[
                        "device_or_source_group"
                    ],
                    "pcap_path": candidate["pcap_path"],
                    "source_file": candidate["source_file"],
                    "timestamp": candidate["csv_timestamp"],
                    "time_bin": all_time_bins[idx],
                    "selection_allowed": candidate["selection_allowed"],
                    "report_only": candidate["report_only"],
                    "sealed_final": candidate["sealed_final"],
                }
            )

    allocation_rows = [
        {
            "exact_attack_label": label,
            "unused_candidate_rows": unused_counts[label],
            "base_support_train_rows": base_train_counts[label],
            "e64_rows": alloc64[label],
            "e128_rows": alloc128[label],
            "eligible_sources": len(
                {source_key(candidates[idx]) for idx in unused_by_label[label]}
            ),
            "source_gate_possible": len(
                {source_key(candidates[idx]) for idx in unused_by_label[label]}
            )
            >= 2,
        }
        for label in sorted(unused_by_label)
    ]
    coverage_rows = candidate_coverage_rows(
        candidates,
        unused_by_label,
        time_bins_by_label,
        set(extension64),
        set(extension128),
    )

    ck.write_csv(OUT / "support_candidate_alignment.csv", alignment_rows)
    ck.write_csv(OUT / "extension_allocation.csv", allocation_rows)
    ck.write_csv(OUT / "extension_candidate_manifest.csv", extension_manifest)
    ck.write_csv(OUT / "source_time_coverage_audit.csv", coverage_rows)
    ck.write_csv(OUT / "static_variant_qualification.csv", qualifications)
    ck.write_csv(OUT / "region_registry_by_variant.csv", all_registry)
    ck.write_csv(OUT / "support_val_audit.csv", all_support_audit)
    ck.write_csv(OUT / "support_val_summary.csv", all_support_summary)
    ck.write_csv(OUT / "ood_val_overlap.csv", all_ood_rows)
    ck.write_csv(OUT / "ood_val_summary.csv", all_ood_summary)
    ck.write_csv(OUT / "prototype_manifest.csv", all_prototypes)
    ck.write_csv(OUT / "shell_registry.csv", all_shells)
    ck.write_csv(OUT / "reused_query_diagnostic.csv", query_rows_all)
    ck.write_csv(
        OUT / "reused_query_confusion_diagnostic.csv", query_confusion_all
    )
    ck.write_csv(OUT / "reused_ood_stress_diagnostic.csv", stress_rows_all)
    ck.write_csv(
        OUT / "reused_ood_stress_summary.csv", stress_summary_all
    )
    ck.write_csv(OUT / "support_val_paired_changes.csv", paired_rows)
    ck.write_csv(
        OUT / "support_val_paired_summary.csv", [paired_summary]
    )
    ck.write_csv(
        OUT / "active_region_ood_stress_comparison.csv",
        stress_comparison,
    )
    ck.write_csv(
        OUT / "role_access_audit.csv",
        [
            {
                "stage": "extension_selection",
                "roles": "legal_unused_support_candidates",
                "query_status": "not_accessed",
                "sealed_access": False,
            },
            {
                "stage": "transform_fit",
                "roles": "id_benign_train",
                "query_status": "not_accessed",
                "sealed_access": False,
            },
            {
                "stage": "prototype_fit",
                "roles": "frozen_support_train|dev_extension_train",
                "query_status": "not_accessed",
                "sealed_access": False,
            },
            {
                "stage": "qualification_and_selection",
                "roles": "frozen_support_val|ood_benign_val",
                "query_status": "not_accessed",
                "sealed_access": False,
            },
            {
                "stage": "post_freeze_reused_diagnostic",
                "roles": (
                    "ood_benign_stress|same_file_time_forward_dev_query_exact|"
                    "dev_future_attack_query_exact"
                ),
                "query_status": (
                    "previously_inspected_not_fresh_validation"
                ),
                "sealed_access": False,
            },
        ],
    )

    result = {
        "issue": ISSUE,
        "primary_verdict": verdict,
        "selected_static_variant": selected,
        "baseline_static_variant": baseline,
        "selection": selection,
        "historical_diagnostic_pass_labels": historical_pass_labels,
        "historical_diagnostic_is_fresh_validation": False,
        "static_gain_material": static_gain_material,
        "support_val_paired_summary": paired_summary,
        "ood_stress_descriptive_caveat_labels": stress_caveat_labels,
        "original_support_bank_mutated": False,
        "extension_is_deployed_bank": False,
        "model_training": False,
        "controller_tuning": False,
        "sealed_final_access": False,
        "next_action": next_action,
    }
    ck.write_json(OUT / "results.json", result)
    ck.write_json(
        OUT / "config.json",
        {
            "evidence_space": S3_NAME,
            "prototype_rule": "two_train_only_medoids_min_cluster_8",
            "variants": [BASE_VARIANT, EXT64_VARIANT, EXT128_VARIANT],
            "time_bins_per_source": TIME_BINS,
            "extension_nested": True,
            "activation_gates": "unchanged_from_issue27ck",
            "query_role_status": (
                "reused_development_diagnostic_not_fresh_validation"
            ),
        },
    )
    ck.write_md(
        OUT / "summary.md",
        [
            "# issue27cke Bounded Support Adequacy Audit",
            "",
            f"primary_verdict: `{verdict}`",
            "",
            f"- selected static variant: `{selected['variant']}`",
            f"- selected extension rows: `{selected['extension_rows']}`",
            f"- baseline active-strong regions: `{baseline['active_strong_regions']}`",
            f"- selected active-strong regions: `{selected['active_strong_regions']}`",
            f"- baseline mean support-val consistency: `{baseline['mean_support_val_label_consistency']:.6f}`",
            f"- selected mean support-val consistency: `{selected['mean_support_val_label_consistency']:.6f}`",
            f"- baseline OOD-val nearest core+near: `{baseline['ood_val_nearest_core_plus_near_rate']:.6f}`",
            f"- selected OOD-val nearest core+near: `{selected['ood_val_nearest_core_plus_near_rate']:.6f}`",
            f"- support-val net corrected rows: `{paired_summary['net_correct_rows']}` of `{paired_summary['rows']}`.",
            f"- paired exact McNemar p-value: `{paired_summary['exact_mcnemar_two_sided_p']:.6f}`.",
            f"- material static gain: `{static_gain_material}`.",
            (
                "- active labels passing reused historical query diagnostic: "
                + (
                    ", ".join(
                        f"`{label}`" for label in historical_pass_labels
                    )
                    if historical_pass_labels
                    else "none"
                )
                + "."
            ),
            (
                "- active labels with descriptive OOD-stress regression over "
                "0.01: "
                + (
                    ", ".join(
                        f"`{label}`" for label in stress_caveat_labels
                    )
                    if stress_caveat_labels
                    else "none"
                )
                + "."
            ),
            "- historical query status: `development diagnostic; not fresh validation`.",
            "- original 512 support rows mutated: `false`.",
            "- controller integration: `false`.",
            "- sealed-final access: `false`.",
            "",
            "Close-out:",
            "",
            "```text",
            "solved: Audited nested +64/+128 source-time-balanced extensions under frozen S3, two-medoid geometry, activation gates, and role boundaries.",
            "changed_mainline: no",
            f"active_blocker: {verdict}.",
            "frozen: original 512 bank, support-val partition, S3, activation gates, and query contamination status.",
            "superseded: treating previously inspected query roles as fresh deployment certification evidence.",
            f"next_action: {next_action}.",
            "```",
        ],
    )
    ck.write_md(
        OUT / "validation_report.md",
        [
            "# issue27cke Validation Report",
            "",
            "Status: `PASS_PENDING_DETERMINISTIC_RERUN`",
            "",
            "- Frozen support/candidate feature alignment passed.",
            "- E64 is a strict subset of E128.",
            "- All extension rows are legal non-final support candidates.",
            "- Static selection used support-val and OOD-val only.",
            "- Existing query and OOD-stress roles were accessed after selection and are explicitly non-fresh diagnostics.",
            "- No sealed-final access, model training, controller tuning, or original-bank mutation occurred.",
        ],
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
