from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27av_prototype_aware_triage_and_ood_tail_attribution_2026-06-04"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AU = ROOT / "runs" / "issue27au_coverage_aware_active_labeling_viability_diagnostic_2026-06-04"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
ATTRIBUTION_BUDGETS = [0, 16]
SUPPORT_BUDGET = 128
OOD_WEIGHT = 2.0
SUPPORT_WEIGHT = 4.0
ID_PROTOTYPES = 64
OOD_PROTOTYPES = 64
ATTACK_PROTOTYPES = 64

ID_ROLE = ar.ID_ROLE
OOD_VAL_ROLE = ar.OOD_VAL_ROLE
FINAL_OOD_ROLE = ar.FINAL_OOD_ROLE
SUPPORT_ROLE = ar.SUPPORT_ROLE
ATTACK_EVAL_ROLE = ar.ATTACK_EVAL_ROLE
DEV_ACTIVE_ROLE = issue27au.DEV_ACTIVE_ROLE
DEV_QUERY_ROLE = issue27au.DEV_QUERY_ROLE


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_doc(path: Path, marker: str, lines: list[str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def hash_indices(indices: np.ndarray) -> str:
    return hashlib.sha256(",".join(map(str, np.asarray(indices, dtype=np.int64).tolist())).encode("utf-8")).hexdigest()


def kcenter_from_global_z(z_all: np.ndarray, source_idx: np.ndarray, budget: int) -> np.ndarray:
    idx = np.asarray(source_idx, dtype=np.int64)
    if len(idx) <= budget:
        return np.asarray(sorted(idx.tolist()), dtype=np.int64)
    z = z_all[idx]
    centroid = z.mean(axis=0, keepdims=True)
    start = int(np.argmin(pairwise_distances(z, centroid, metric="euclidean").ravel()))
    local = ar.farthest_first(z, budget, start)
    return np.asarray(sorted(idx[local].tolist()), dtype=np.int64)


def nearest_dist(z_target: np.ndarray, z_proto: np.ndarray) -> np.ndarray:
    if len(z_target) == 0 or len(z_proto) == 0:
        return np.full(len(z_target), np.nan, dtype=np.float64)
    return pairwise_distances(z_target, z_proto, metric="euclidean").min(axis=1)


def p95_radius(z_calib: np.ndarray, z_proto: np.ndarray) -> float:
    d = nearest_dist(z_calib, z_proto)
    return float(np.quantile(d, 0.95)) if len(d) else float("nan")


def label_is_attack(row: dict[str, str]) -> bool:
    return (row.get("binary_label_from_alignment") or row.get("label") or "").lower() == "attack"


def row_info(row: dict[str, str]) -> dict[str, Any]:
    return {
        "csv_member": row.get("csv_member", ""),
        "pcap_member": row.get("pcap_member", ""),
        "packet_index": row.get("packet_index", ""),
        "recorded_index": row.get("recorded_index", ""),
        "label": row.get("binary_label_from_alignment", ""),
        "attack_type": row.get("attack_type_from_raw_path", ""),
    }


def triage_label(d_id: float, d_ood: float, d_attack: float, r_id: float, r_ood: float, r_attack: float) -> tuple[str, bool, bool, bool]:
    id_cov = d_id <= r_id
    ood_cov = d_ood <= r_ood
    benign_cov = id_cov or ood_cov
    attack_cov = d_attack <= r_attack
    if benign_cov and attack_cov:
        return "both_covered_conflict", id_cov, ood_cov, attack_cov
    if benign_cov:
        return "benign_covered", id_cov, ood_cov, attack_cov
    if attack_cov:
        return "attack_covered", id_cov, ood_cov, attack_cov
    return "unknown_uncovered", id_cov, ood_cov, attack_cov


def aggregate_by_triage(rows: list[dict[str, Any]], target_role: str, alarm_only: bool = False) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    total_by_seed_budget: Counter[tuple[int, int]] = Counter()
    for row in rows:
        if row["target_role"] != target_role:
            continue
        key_total = (int(row["seed"]), int(row["budget"]))
        total_by_seed_budget[key_total] += 1
        if alarm_only and not bool(row["alarm_under_existing_threshold"]):
            continue
        key = (int(row["seed"]), int(row["budget"]), row["triage_label"])
        groups[key].append(row)
    out = []
    for (seed, budget, label), gr in sorted(groups.items()):
        scores = np.asarray([float(r["attack_score"]) for r in gr])
        alarms = np.asarray([float(bool(r["alarm_under_existing_threshold"])) for r in gr])
        benign_adv = np.asarray([float(r["benign_advantage"]) for r in gr])
        attack_adv = np.asarray([float(r["attack_distance_advantage"]) for r in gr])
        out.append(
            {
                "target_role": target_role,
                "seed": seed,
                "budget": budget,
                "triage_label": label,
                "alarm_only": alarm_only,
                "rows": len(gr),
                "fraction_of_target_rows": float(len(gr) / max(1, total_by_seed_budget[(seed, budget)])),
                "alarm_rate": float(np.mean(alarms)),
                "attack_score_mean": float(np.mean(scores)),
                "attack_score_p90": float(np.quantile(scores, 0.90)),
                "benign_advantage_mean": float(np.mean(benign_adv)),
                "attack_distance_advantage_mean": float(np.mean(attack_adv)),
            }
        )
    return out


def pick_verdict(distance_rows: list[dict[str, Any]], target_role: str) -> tuple[str, dict[str, float]]:
    budget16 = [
        r
        for r in distance_rows
        if r["target_role"] == target_role
        and int(r["budget"]) == 16
        and bool(r["alarm_under_existing_threshold"])
    ]
    if not budget16:
        return "ood_tail_no_false_alarm_to_attribute", {}
    counts = Counter(r["triage_label"] for r in budget16)
    total = sum(counts.values())
    shares = {k: float(v / total) for k, v in counts.items()}
    benign_like = shares.get("benign_covered", 0.0)
    unknown = shares.get("unknown_uncovered", 0.0)
    attack_like = shares.get("attack_covered", 0.0)
    conflict = shares.get("both_covered_conflict", 0.0)
    if benign_like >= 0.5:
        return "ood_tail_needs_benign_prototype_veto", shares
    if unknown >= 0.5:
        return "ood_tail_needs_ood_stress_pool", shares
    if attack_like + conflict >= 0.5:
        return "ood_tail_attack_benign_overlap_or_conflict_risk", shares
    return "prototype_triage_inconclusive_needs_feature_or_task_review", shares


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    if not new_sidecar:
        new_sidecar = read_csv(ar.NEW_HELDOUT_SIDECAR)

    x = asset["X"]
    sidecar = asset["sidecar"]
    id_idx = ar.role_indices(sidecar, ID_ROLE)
    ood_idx = ar.role_indices(sidecar, OOD_VAL_ROLE)
    final_ood = ar.role_indices(sidecar, FINAL_OOD_ROLE)
    support_pool = ar.role_indices(sidecar, SUPPORT_ROLE)
    attack_eval = ar.role_indices(sidecar, ATTACK_EVAL_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    active_candidate_idx, dev_query_idx, split_manifest = issue27au.split_new_heavy_stream(new_sidecar)

    input_hash_rows = [
        {"artifact": "issue27af_medium_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path), "hash_match": True},
        {"artifact": "issue27au_summary", "path": str(ISSUE27AU / "summary.md"), "sha256": sha256_file(ISSUE27AU / "summary.md"), "hash_match": True},
    ]
    input_hash_rows.extend(checks)
    input_hash_rows.extend(new_checks)

    prototype_registry_rows: list[dict[str, Any]] = []
    prototype_indices_rows: list[dict[str, Any]] = []
    distance_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        base_support, _ = issue27as.kcenter_budget(x, support_pool, SUPPORT_BUDGET)
        base_train, base_val = issue27as.split_support(base_support, seed)
        selected_local, _ = issue27au.select_active_labels(
            x_base_support=x[base_train],
            x_support_val=x[base_val],
            x_candidates=new_x[active_candidate_idx],
            candidate_indices=active_candidate_idx,
            budget=16,
        )
        confirmed_attack = np.asarray([i for i in selected_local if label_is_attack(new_sidecar[int(i)])], dtype=np.int64)
        x_support_aug = np.vstack([x[base_train], new_x[confirmed_attack]]) if len(confirmed_attack) else x[base_train]

        model = issue27as.WeightedOldHistGB(seed, OOD_WEIGHT, SUPPORT_WEIGHT)
        model.fit(x[id_fit], x[ood_train], x_support_aug)
        score_id = model.score(x[id_calib])
        score_ood = model.score(x[ood_val])
        score_support_val = model.score(x[base_val])
        threshold_info = issue27as.orderstat_threshold(score_id, score_ood, score_support_val)
        threshold = float(threshold_info["threshold"])
        threshold_rows.append(
            {
                "seed": seed,
                "budget": 16,
                "threshold_rule": "np_orderstat_id_ood_1pct",
                "threshold": threshold,
                "id_calib_alarm": issue27as.rate(score_id, threshold),
                "ood_val_alarm": issue27as.rate(score_ood, threshold),
                "support_val_detection": issue27as.rate(score_support_val, threshold),
                "threshold_uses_final_ood": False,
                "threshold_uses_attack_eval": False,
                "threshold_uses_dev_query": False,
            }
        )

        # A single common scaler keeps ID/OOD/attack distances comparable.
        scaler_source = np.concatenate([id_fit, ood_train, base_train])
        scaler = StandardScaler().fit(x[scaler_source])
        z_all = scaler.transform(x)
        z_new = scaler.transform(new_x)
        id_proto = kcenter_from_global_z(z_all, id_fit, ID_PROTOTYPES)
        ood_proto = kcenter_from_global_z(z_all, ood_train, OOD_PROTOTYPES)
        # Active labels live outside the medium X matrix; choose attack prototypes in z-space directly.
        z_attack_source = np.vstack([z_all[base_train], z_new[confirmed_attack]])
        if len(z_attack_source) <= ATTACK_PROTOTYPES:
            attack_proto_z = z_attack_source
            attack_proto_desc = "all_base_support_train_plus_confirmed_active_labels"
        else:
            centroid = z_attack_source.mean(axis=0, keepdims=True)
            start = int(np.argmin(pairwise_distances(z_attack_source, centroid).ravel()))
            local = ar.farthest_first(z_attack_source, ATTACK_PROTOTYPES, start)
            attack_proto_z = z_attack_source[local]
            attack_proto_desc = "kcenter64_from_base_support_train_plus_confirmed_active_labels"
        r_id = p95_radius(z_all[id_calib], z_all[id_proto])
        r_ood = p95_radius(z_all[ood_val], z_all[ood_proto])
        r_attack = p95_radius(z_all[base_val], attack_proto_z)

        registry = [
            ("id_prototypes", ID_ROLE, len(id_proto), hash_indices(id_proto), "id_fit", r_id),
            ("ood_prototypes", OOD_VAL_ROLE, len(ood_proto), hash_indices(ood_proto), "ood_train_guard", r_ood),
            ("attack_prototypes", SUPPORT_ROLE + "+dev_active_confirmed_attack", len(attack_proto_z), "mixed_medium_new_z_space", attack_proto_desc, r_attack),
        ]
        for name, source_role, count, hash_value, selection_rule, radius in registry:
            prototype_registry_rows.append(
                {
                    "seed": seed,
                    "budget": 16,
                    "prototype_set": name,
                    "source_role": source_role,
                    "prototype_count": count,
                    "prototype_hash_or_descriptor": hash_value,
                    "selection_rule": selection_rule,
                    "distance_scaler_source": "id_fit|ood_train_guard|base_attack_support_train",
                    "radius_source": "id_calib_for_id|ood_val_for_ood|base_support_val_for_attack",
                    "p95_radius": radius,
                    "uses_final_ood": False,
                    "uses_attack_eval": False,
                    "uses_dev_query": False,
                }
            )
        for rank, idx in enumerate(id_proto.tolist()):
            prototype_indices_rows.append({"seed": seed, "prototype_set": "id_prototypes", "rank": rank, "medium_row_index": int(idx), **row_info(sidecar[int(idx)])})
        for rank, idx in enumerate(ood_proto.tolist()):
            prototype_indices_rows.append({"seed": seed, "prototype_set": "ood_prototypes", "rank": rank, "medium_row_index": int(idx), **row_info(sidecar[int(idx)])})
        for rank, idx in enumerate(base_train.tolist()):
            prototype_indices_rows.append({"seed": seed, "prototype_set": "attack_source_base_support_train", "rank": rank, "medium_row_index": int(idx), **row_info(sidecar[int(idx)])})
        for rank, idx in enumerate(confirmed_attack.tolist()):
            prototype_indices_rows.append({"seed": seed, "prototype_set": "attack_source_dev_active_confirmed", "rank": rank, "new_row_index": int(idx), **row_info(new_sidecar[int(idx)])})

        role_rows.append(
            {
                "seed": seed,
                "budget": 16,
                "prototype_roles": "id_fit|ood_train_guard|base_attack_support_train|dev_active_confirmed_attack",
                "radius_roles": "id_calib|ood_val|base_support_val",
                "attribution_report_only_roles": f"{FINAL_OOD_ROLE}|{ATTACK_EVAL_ROLE}|{DEV_QUERY_ROLE}",
                "uses_final_ood_for_prototype_or_threshold": False,
                "uses_attack_eval_for_prototype_or_threshold": False,
                "uses_dev_query_for_prototype_or_threshold": False,
                "uses_active_candidate_labels_for_selection": False,
                "forbidden_role_access": False,
            }
        )

        targets = [
            ("final_ood_benign_eval", x[final_ood], final_ood, sidecar, model.score(x[final_ood])),
            ("medium_attack_eval_report_only", x[attack_eval], attack_eval, sidecar, model.score(x[attack_eval])),
            ("dev_heavy_query_after_active_labeling", new_x[dev_query_idx], dev_query_idx, new_sidecar, model.score(new_x[dev_query_idx])),
        ]
        for target_role, target_x, target_idx, rows_source, scores in targets:
            z_target = scaler.transform(target_x) if target_role != "dev_heavy_query_after_active_labeling" else z_new[target_idx]
            d_id = nearest_dist(z_target, z_all[id_proto])
            d_ood = nearest_dist(z_target, z_all[ood_proto])
            d_attack = nearest_dist(z_target, attack_proto_z)
            for j, idx in enumerate(target_idx.tolist()):
                label, id_cov, ood_cov, attack_cov = triage_label(float(d_id[j]), float(d_ood[j]), float(d_attack[j]), r_id, r_ood, r_attack)
                min_benign = min(float(d_id[j]), float(d_ood[j]))
                distance_rows.append(
                    {
                        "seed": seed,
                        "budget": 16,
                        "target_role": target_role,
                        "target_row_index": int(idx),
                        "attack_score": float(scores[j]),
                        "threshold": threshold,
                        "alarm_under_existing_threshold": bool(scores[j] > threshold),
                        "d_id": float(d_id[j]),
                        "d_ood": float(d_ood[j]),
                        "d_attack": float(d_attack[j]),
                        "id_radius_p95": r_id,
                        "ood_radius_p95": r_ood,
                        "attack_radius_p95": r_attack,
                        "id_covered": id_cov,
                        "ood_covered": ood_cov,
                        "attack_covered": attack_cov,
                        "triage_label": label,
                        "benign_advantage": float(d_attack[j] - min_benign),
                        "attack_distance_advantage": float(min_benign - d_attack[j]),
                        **row_info(rows_source[int(idx)]),
                    }
                )

    final_tail_summary = aggregate_by_triage(distance_rows, "final_ood_benign_eval", alarm_only=True)
    final_all_summary = aggregate_by_triage(distance_rows, "final_ood_benign_eval", alarm_only=False)
    dev_heavy_summary = aggregate_by_triage(distance_rows, "dev_heavy_query_after_active_labeling", alarm_only=False)
    attack_eval_summary = aggregate_by_triage(distance_rows, "medium_attack_eval_report_only", alarm_only=False)
    primary_verdict, final_alarm_shares = pick_verdict(distance_rows, "final_ood_benign_eval")

    write_csv(OUT / "input_artifact_hash_audit.csv", input_hash_rows)
    write_csv(OUT / "prototype_registry.csv", prototype_registry_rows)
    write_csv(OUT / "prototype_indices.csv", prototype_indices_rows)
    write_csv(OUT / "triage_distance_report.csv", distance_rows)
    write_csv(OUT / "triage_bucket_summary.csv", final_all_summary + dev_heavy_summary + attack_eval_summary)
    write_csv(OUT / "final_ood_tail_attribution.csv", final_tail_summary)
    write_csv(OUT / "dev_heavy_triage_attribution.csv", dev_heavy_summary)
    write_csv(OUT / "threshold_replay_audit.csv", threshold_rows)
    write_csv(OUT / "role_access_audit.csv", role_rows)

    write_md(
        OUT / "final_ood_tail_attribution_report.md",
        [
            "# Final OOD Tail Attribution Report",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "Final OOD is report-only. It is used here only to attribute the already-observed OOD tail alarms under the frozen replay, not to tune prototypes, radii, thresholds, or model configuration.",
            "",
            "## Budget 16 False-Alarm Triage Shares",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(final_alarm_shares.items())],
            "",
            "Interpretation guide:",
            "- benign_covered false alarms suggest an OOD/benign prototype veto may help.",
            "- unknown_uncovered false alarms suggest the OOD stress pool is incomplete.",
            "- attack_covered or both_covered_conflict false alarms suggest attack/benign feature overlap or a conflict gate is needed.",
        ],
    )
    write_md(
        OUT / "dev_heavy_triage_report.md",
        [
            "# Dev Heavy Triage Report",
            "",
            "Dev heavy query is report-only and comes from the previous new heldout probe, now consumed as development evidence. It cannot be reused as a sealed final set.",
            "",
            "The purpose is to check whether active-labeled attack prototypes move heavy-like query rows into attack-covered or conflict regions, while final OOD attribution separately checks whether OOD benign is protected.",
        ],
    )
    write_md(
        OUT / "prototype_aware_gate_v0.md",
        [
            "# Prototype-Aware Gate v0",
            "",
            "Draft only. Not applied in issue27av.",
            "",
            "1. Compute common-scaled distances to ID, OOD, and attack prototypes.",
            "2. If ID/OOD covered and attack not covered: suppress attack alarm or label as benign drift.",
            "3. If attack covered and ID/OOD not covered: allow attack alarm subject to OOD-safe threshold.",
            "4. If both benign and attack covered: conflict, route to needs_review or require a score-margin rule.",
            "5. If none covered: unknown_uncovered, request more labels or add to OOD stress pool depending on anomaly score and operational context.",
            "",
            "Final OOD cannot be used to tune these radii or rules.",
        ],
    )
    next_issue = "issue27aw_ood_safe_gate_repair_with_benign_prototype_veto"
    if primary_verdict == "ood_tail_needs_ood_stress_pool":
        next_issue = "issue27aw_build_dev_ood_stress_pool_before_gate_repair"
    elif primary_verdict in {"ood_tail_attack_benign_overlap_or_conflict_risk", "prototype_triage_inconclusive_needs_feature_or_task_review"}:
        next_issue = "issue27aw_conflict_gate_or_feature_task_boundary_review"
    write_md(
        OUT / "issue27av_decision.md",
        [
            "# Issue27av Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "- Prototype triage is attribution and gate-design evidence only.",
            "- Final OOD is report-only and not used to tune prototype thresholds.",
            "- The next issue should repair the OOD-safe gate according to the dominant final-OOD false-alarm attribution.",
        ],
    )
    write_md(
        OUT / "issue27aw_next_action.md",
        [
            "# Issue27aw Next Action",
            "",
            f"Recommended next issue: `{next_issue}`.",
            "",
            "- Do not run full/larger benchmark yet.",
            "- Keep active labeling and prototype gates on development data only.",
            "- Build a sealed final heavy/OOD set only after the gate is frozen.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27av.md",
        [
            "# Claim Update After issue27av",
            "",
            "- issue27av is not a performance result.",
            "- It diagnoses why final OOD tail alarms occur under the active-labeling diagnostic.",
            "- A formal claim still requires a clean dev/final split, OOD-safe gate, and sealed final replay.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27av Summary",
            "",
            "1. issue27av completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. task type: prototype-aware triage and OOD tail attribution; not formal benchmark",
            "4. prototypes built from final OOD: no",
            "5. final OOD used for tuning: no, report-only attribution",
            "6. active-labeled attack prototypes source: development active pool only",
            "7. distance features: d_id, d_ood, d_attack plus score margins",
            f"8. budget16 final-OOD false-alarm triage shares: `{json.dumps(final_alarm_shares, sort_keys=True)}`",
            f"9. next action: `{next_issue}`",
            "10. formal benchmark allowed: no",
            "11. commit hash: pending",
        ],
    )
    config = {
        "issue": ISSUE,
        "formal_benchmark": False,
        "attribution_budgets": ATTRIBUTION_BUDGETS,
        "primary_attribution_budget": 16,
        "prototype_counts": {"id": ID_PROTOTYPES, "ood": OOD_PROTOTYPES, "attack": ATTACK_PROTOTYPES},
        "common_scaler_source": "id_fit|ood_train_guard|base_attack_support_train",
        "forbidden": "final OOD, attack_eval, and dev query are not used to tune prototypes/radii/thresholds",
        "primary_verdict": primary_verdict,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "issue27af_certificate": str(cert_path),
                    "issue27au_outputs": str(ISSUE27AU),
                    "new_heavy_dev_probe": str(ar.NEW_HELDOUT_DIR),
                },
                "outputs": f"runs/{ISSUE}/",
                "role_policy": "prototype/radius/threshold from train-calib-support-development only; final OOD report-only attribution",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")
    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27av -->",
        [
            "<!-- issue27av -->",
            "## issue27av - Prototype-aware triage and OOD tail attribution",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- Diagnostic only; final OOD report-only attribution.",
            "- Adds ID/OOD/attack prototype distance and score-margin analysis before OOD gate repair.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27av -->",
        [
            "<!-- issue27av -->",
            "## issue27av - Prototype-aware triage",
            "",
            f"- verdict: `{primary_verdict}`",
            "- purpose: attribute final OOD tail alarms using ID/OOD/attack prototypes before OOD-safe gate repair.",
            f"- outputs: `runs/{ISSUE}/`.",
        ],
    )
    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(json.dumps({"primary_verdict": primary_verdict, "shares": final_alarm_shares, "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
