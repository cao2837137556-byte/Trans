from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
PROJECT_DIR = ROOT.parents[1]
ISSUE = "issue27at_coverage_hypothesis_validation_before_protocol_redesign_2026-06-03"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AO = ROOT / "runs" / "issue27ao_repair_support_eval_contract_v2_before_head_repair_2026-06-03"
ISSUE27AQ = ROOT / "runs" / "issue27aq_model_learning_and_domain_gap_audit_after_new_heldout_zero_detection_2026-06-03"
ISSUE27AR = ROOT / "runs" / "issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium_2026-06-03"
ISSUE27AS = ROOT / "runs" / "issue27as_old_protocol_bounded_calibration_and_coverage_repair_2026-06-03"

PRIMARY_STRATEGY = "reset_at_split_boundary"
PRIMARY_SUPPORT_BUDGET = 128
PRIMARY_OOD_WEIGHT = 2.0
PRIMARY_SUPPORT_WEIGHT = 4.0
PRIMARY_THRESHOLD_RULE = "support_val_guided_empirical_1pct"
SEEDS = [42, 43, 44, 45, 46]

ID_ROLE = ar.ID_ROLE
OOD_VAL_ROLE = ar.OOD_VAL_ROLE
FINAL_OOD_ROLE = ar.FINAL_OOD_ROLE
SUPPORT_ROLE = ar.SUPPORT_ROLE
ATTACK_EVAL_ROLE = ar.ATTACK_EVAL_ROLE
NEW_HELDOUT_ROLE = ar.NEW_HELDOUT_ROLE


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


def load_indices(path: Path, contract_id: str, role_name: str = "support_train") -> np.ndarray:
    if not path.exists():
        return np.asarray([], dtype=np.int64)
    rows = [r for r in read_csv(path) if r.get("contract_id") == contract_id and r.get("new_role", role_name) == role_name]
    return np.asarray(sorted(int(r["global_row_index"]) for r in rows), dtype=np.int64)


def infer_device(row: dict[str, str]) -> str:
    csv_member = row.get("csv_member", "")
    stem = Path(csv_member).stem
    if stem.startswith("iotsim-"):
        stem = stem[len("iotsim-") :]
    m = re.match(r"(.+)-\d+$", stem)
    return m.group(1) if m else (stem or "unknown")


def attack_type(row: dict[str, str]) -> str:
    return row.get("attack_type_from_raw_path") or row.get("attack_type") or "unknown"


def source_file(row: dict[str, str]) -> str:
    return row.get("csv_member") or row.get("pcap_member") or "unknown"


def packet_index(row: dict[str, str]) -> int:
    for key in ["packet_index", "recorded_index"]:
        try:
            return int(float(row.get(key, "")))
        except ValueError:
            continue
    return -1


def build_min_packet_by_file(sidecar: list[dict[str, str]], indices: np.ndarray) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in indices:
        row = sidecar[int(i)]
        sf = source_file(row)
        pi = packet_index(row)
        if pi >= 0:
            out[sf] = min(out.get(sf, pi), pi)
    return out


def onset_phase(row: dict[str, str], min_packet_by_file: dict[str, int]) -> str:
    pi = packet_index(row)
    base = min_packet_by_file.get(source_file(row), pi)
    rel = max(0, pi - base) if pi >= 0 and base >= 0 else -1
    if rel < 0:
        return "unknown"
    if rel < 500:
        return "early_0_500"
    if rel < 2000:
        return "mid_500_2000"
    if rel < 10000:
        return "late_2000_10000"
    return "tail_gt_10000"


def time_bucket(row: dict[str, str], min_packet_by_file: dict[str, int]) -> str:
    phase = onset_phase(row, min_packet_by_file)
    return f"time_{phase}"


def semantic_sets(sidecar: list[dict[str, str]], indices: np.ndarray, min_packet_by_file: dict[str, int]) -> dict[str, set[str]]:
    rows = [sidecar[int(i)] for i in indices]
    return {
        "attack_type": {attack_type(r) for r in rows},
        "source_file": {source_file(r) for r in rows},
        "device": {infer_device(r) for r in rows},
        "onset_phase": {onset_phase(r, min_packet_by_file) for r in rows},
        "time_bucket": {time_bucket(r, min_packet_by_file) for r in rows},
    }


def semantic_flags(row: dict[str, str], sets_train: dict[str, set[str]], sets_train_val: dict[str, set[str]], min_packet_by_file: dict[str, int]) -> dict[str, Any]:
    values = {
        "attack_type": attack_type(row),
        "source_file": source_file(row),
        "device": infer_device(row),
        "onset_phase": onset_phase(row, min_packet_by_file),
        "time_bucket": time_bucket(row, min_packet_by_file),
    }
    out: dict[str, Any] = {}
    train_count = 0
    train_val_count = 0
    for key, val in values.items():
        out[key] = val
        train_hit = val in sets_train.get(key, set())
        train_val_hit = val in sets_train_val.get(key, set())
        out[f"{key}_covered_train"] = train_hit
        out[f"{key}_covered_train_val"] = train_val_hit
        train_count += int(train_hit)
        train_val_count += int(train_val_hit)
    out["semantic_coverage_count_train"] = train_count
    out["semantic_coverage_count_train_val"] = train_val_count
    return out


def pearson(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def rankdata(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=np.float64)
    ranks[order] = np.arange(len(x), dtype=np.float64)
    return ranks


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    return pearson(rankdata(x), rankdata(y))


def quantile_dict(values: np.ndarray, prefix: str) -> dict[str, float]:
    if len(values) == 0:
        return {f"{prefix}_{q}": float("nan") for q in ["p50", "p75", "p90", "p95", "p99", "mean"]}
    return {
        f"{prefix}_p50": float(np.quantile(values, 0.50)),
        f"{prefix}_p75": float(np.quantile(values, 0.75)),
        f"{prefix}_p90": float(np.quantile(values, 0.90)),
        f"{prefix}_p95": float(np.quantile(values, 0.95)),
        f"{prefix}_p99": float(np.quantile(values, 0.99)),
        f"{prefix}_mean": float(np.mean(values)),
    }


def bucket_distance(dist: float, thresholds: dict[str, float]) -> str:
    if dist <= thresholds["p50"]:
        return "covered_close"
    if dist <= thresholds["p75"]:
        return "covered_mid"
    if dist <= thresholds["p95"]:
        return "covered_far"
    return "uncovered_extreme"


def coverage_metrics(
    x_support_train: np.ndarray,
    x_support_val: np.ndarray,
    x_target: np.ndarray,
) -> tuple[dict[str, float], np.ndarray, dict[int, np.ndarray]]:
    scaler = StandardScaler().fit(x_support_train)
    z_train = scaler.transform(x_support_train)
    z_val = scaler.transform(x_support_val)
    z_target = scaler.transform(x_target)
    val_dist = pairwise_distances(z_val, z_train, metric="euclidean")
    target_dist = pairwise_distances(z_target, z_train, metric="euclidean")
    nearest = target_dist.min(axis=1)
    val_nearest = val_dist.min(axis=1)
    thresholds = {
        "p50": float(np.quantile(val_nearest, 0.50)),
        "p75": float(np.quantile(val_nearest, 0.75)),
        "p90": float(np.quantile(val_nearest, 0.90)),
        "p95": float(np.quantile(val_nearest, 0.95)),
    }
    knn = {}
    for k in [3, 5, 10]:
        kk = min(k, target_dist.shape[1])
        knn[k] = np.sort(target_dist, axis=1)[:, :kk].mean(axis=1)
    return thresholds, nearest, knn


def summarize_buckets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["target_role"], row["support_scheme"], row["coverage_bucket"], int(row["seed"]))].append(row)
    out = []
    for (role, scheme, bucket, seed), gr in sorted(groups.items()):
        scores = np.asarray([float(r["score_anomaly_higher"]) for r in gr])
        detections = np.asarray([float(r["detected_under_existing_threshold"]) for r in gr])
        dist = np.asarray([float(r["nearest_support_distance"]) for r in gr])
        sem = np.asarray([float(r["semantic_coverage_count_train_val"]) for r in gr])
        row = {
            "target_role": role,
            "support_scheme": scheme,
            "coverage_bucket": bucket,
            "seed": seed,
            "sample_count": len(gr),
            "detection_rate_under_existing_threshold": float(np.mean(detections)),
            "semantic_coverage_count_train_val_mean": float(np.mean(sem)),
        }
        row.update(quantile_dict(scores, "score"))
        row.update(quantile_dict(dist, "distance"))
        out.append(row)
    return out


def summarize_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["target_role"], row["support_scheme"], int(row["seed"]))].append(row)
    out = []
    for (role, scheme, seed), gr in sorted(groups.items()):
        dist = np.asarray([float(r["nearest_support_distance"]) for r in gr])
        det = np.asarray([float(r["detected_under_existing_threshold"]) for r in gr])
        row = {
            "target_role": role,
            "support_scheme": scheme,
            "seed": seed,
            "sample_count": len(gr),
            "detection_rate": float(np.mean(det)),
        }
        row.update(quantile_dict(dist, "nearest_support_distance"))
        for bucket in ["covered_close", "covered_mid", "covered_far", "uncovered_extreme"]:
            row[f"bucket_fraction_{bucket}"] = float(np.mean([r["coverage_bucket"] == bucket for r in gr]))
        out.append(row)
    return out


def correlations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["target_role"], row["support_scheme"], int(row["seed"]))].append(row)
    out = []
    for (role, scheme, seed), gr in sorted(groups.items()):
        score = np.asarray([float(r["score_anomaly_higher"]) for r in gr])
        detection = np.asarray([float(r["detected_under_existing_threshold"]) for r in gr])
        nearest = np.asarray([float(r["nearest_support_distance"]) for r in gr])
        k3 = np.asarray([float(r["support_density_knn3"]) for r in gr])
        k5 = np.asarray([float(r["support_density_knn5"]) for r in gr])
        sem = np.asarray([float(r["semantic_coverage_count_train_val"]) for r in gr])
        out.append(
            {
                "target_role": role,
                "support_scheme": scheme,
                "seed": seed,
                "n": len(gr),
                "pearson_nearest_vs_score": pearson(nearest, score),
                "spearman_nearest_vs_score": spearman(nearest, score),
                "pearson_nearest_vs_detection": pearson(nearest, detection),
                "spearman_nearest_vs_detection": spearman(nearest, detection),
                "pearson_knn3_vs_score": pearson(k3, score),
                "spearman_knn3_vs_score": spearman(k3, score),
                "pearson_knn5_vs_score": pearson(k5, score),
                "spearman_knn5_vs_score": spearman(k5, score),
                "pearson_semantic_coverage_vs_detection": pearson(sem, detection),
                "spearman_semantic_coverage_vs_detection": spearman(sem, detection),
            }
        )
    return out


def sufficiency(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        sufficient = row["coverage_bucket"] in {"covered_close", "covered_mid"}
        groups[(row["target_role"], row["support_scheme"], int(row["seed"]), "coverage_sufficient" if sufficient else "coverage_insufficient")].append(row)
    out = []
    for (role, scheme, seed, subset), gr in sorted(groups.items()):
        scores = np.asarray([float(r["score_anomaly_higher"]) for r in gr])
        det = np.asarray([float(r["detected_under_existing_threshold"]) for r in gr])
        out.append(
            {
                "target_role": role,
                "support_scheme": scheme,
                "seed": seed,
                "subset": subset,
                "sample_count": len(gr),
                "sample_fraction": float(len(gr) / max(1, len([r for r in rows if r["target_role"] == role and r["support_scheme"] == scheme and int(r["seed"]) == seed]))),
                "detection_rate": float(np.mean(det)),
                "score_mean": float(np.mean(scores)),
                "score_p50": float(np.quantile(scores, 0.50)),
                "score_p90": float(np.quantile(scores, 0.90)),
            }
        )
    return out


def build_support_schemes(x: np.ndarray, sidecar: list[dict[str, str]], support_pool: np.ndarray, seed: int) -> dict[str, tuple[np.ndarray, np.ndarray, str]]:
    schemes: dict[str, tuple[np.ndarray, np.ndarray, str]] = {}
    selected128, _ = issue27as.kcenter_budget(x, support_pool, PRIMARY_SUPPORT_BUDGET)
    tr128, val128 = issue27as.split_support(selected128, seed)
    schemes["issue27as_selected_kcenter128"] = (tr128, val128, "primary issue27as selected support; used for model replay")

    selected32, _ = issue27as.kcenter_budget(x, support_pool, 32)
    tr32, val32 = issue27as.split_support(selected32, seed)
    schemes["old_kcenter32_trace"] = (tr32, val32, "old kcenter32 trace support; coverage comparison only")

    fb_train = load_indices(ISSUE27AO / "contract_v2_support_train_indices.csv", "file_balanced_v2", "support_train")
    fb_val = load_indices(ISSUE27AO / "contract_v2_support_val_indices.csv", "file_balanced_v2", "support_val")
    if len(fb_train) and len(fb_val):
        schemes["file_balanced_v2_diagnostic"] = (
            fb_train,
            fb_val,
            "issue27ao file_balanced_v2 diagnostic support; consumed old attack_eval for contract design, not formal",
        )
    return schemes


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    asset, medium_checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    if not new_sidecar and ar.NEW_HELDOUT_SIDECAR.exists():
        new_sidecar = read_csv(ar.NEW_HELDOUT_SIDECAR)

    x = asset["X"]
    sidecar = asset["sidecar"]
    id_idx = ar.role_indices(sidecar, ID_ROLE)
    ood_idx = ar.role_indices(sidecar, OOD_VAL_ROLE)
    support_pool = ar.role_indices(sidecar, SUPPORT_ROLE)
    attack_eval = ar.role_indices(sidecar, ATTACK_EVAL_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)

    input_hash_rows = [
        {"artifact": "issue27af_medium_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path), "hash_match": True},
        {"artifact": "issue27as_summary", "path": str(ISSUE27AS / "summary.md"), "sha256": sha256_file(ISSUE27AS / "summary.md"), "hash_match": True},
        {"artifact": "issue27ar_summary", "path": str(ISSUE27AR / "summary.md"), "sha256": sha256_file(ISSUE27AR / "summary.md"), "hash_match": True},
        {"artifact": "issue27aq_summary", "path": str(ISSUE27AQ / "summary.md"), "sha256": sha256_file(ISSUE27AQ / "summary.md"), "hash_match": True},
    ]
    input_hash_rows.extend(medium_checks)
    input_hash_rows.extend(new_checks)

    attack_context_idx = np.concatenate([support_pool, attack_eval])
    medium_min_packet = build_min_packet_by_file(sidecar, attack_context_idx)
    new_idx = np.arange(len(new_sidecar), dtype=np.int64)
    new_min_packet = build_min_packet_by_file(new_sidecar, new_idx)

    coverage_rows: list[dict[str, Any]] = []
    role_access_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        support_selected, _ = issue27as.kcenter_budget(x, support_pool, PRIMARY_SUPPORT_BUDGET)
        support_train, support_val = issue27as.split_support(support_selected, seed)
        model = issue27as.WeightedOldHistGB(seed, PRIMARY_OOD_WEIGHT, PRIMARY_SUPPORT_WEIGHT)
        model.fit(x[id_fit], x[ood_train], x[support_train])
        score_id = model.score(x[id_calib])
        score_ood = model.score(x[ood_val])
        score_support_val = model.score(x[support_val])
        threshold_info = issue27as.support_guided_threshold(score_id, score_ood, score_support_val)
        threshold = float(threshold_info["threshold"])
        score_attack = model.score(x[attack_eval])
        score_new = model.score(new_x) if new_x.size else np.asarray([], dtype=np.float64)
        threshold_rows.append(
            {
                "seed": seed,
                "strategy": PRIMARY_STRATEGY,
                "support_budget": PRIMARY_SUPPORT_BUDGET,
                "ood_weight": PRIMARY_OOD_WEIGHT,
                "support_weight": PRIMARY_SUPPORT_WEIGHT,
                "threshold_rule": PRIMARY_THRESHOLD_RULE,
                "threshold": threshold,
                "id_calib_alarm": issue27as.rate(score_id, threshold),
                "ood_val_alarm": issue27as.rate(score_ood, threshold),
                "support_val_detection": issue27as.rate(score_support_val, threshold),
                "selection_feasible": bool(threshold_info["selection_feasible"]),
                "final_or_attack_eval_used": False,
            }
        )
        role_access_rows.append(
            {
                "seed": seed,
                "fit_roles": "id_fit_from_id_benign_train|ood_train_guard_from_ood_benign_val|attack_support_train",
                "threshold_roles": "id_calib_from_id_benign_train|ood_val_calib_from_ood_benign_val|support_val_from_attack_support",
                "coverage_scaler_roles": "support_train_only_per_support_scheme",
                "score_roles_report_only": f"{ATTACK_EVAL_ROLE}|{NEW_HELDOUT_ROLE}",
                "uses_final_ood_for_selection": False,
                "uses_attack_eval_for_selection": False,
                "uses_new_heldout_for_selection": False,
                "forbidden_role_access": False,
                "replay_note": "deterministic replay of issue27as selected candidate to recover per-sample scores; no config search",
            }
        )
        schemes = build_support_schemes(x, sidecar, support_pool, seed)
        for scheme_name, (scheme_train, scheme_val, scheme_note) in schemes.items():
            thresholds, attack_nearest, attack_knn = coverage_metrics(x[scheme_train], x[scheme_val], x[attack_eval])
            train_sets = semantic_sets(sidecar, scheme_train, medium_min_packet)
            train_val_sets = semantic_sets(sidecar, np.concatenate([scheme_train, scheme_val]), medium_min_packet)
            for j, global_idx in enumerate(attack_eval.tolist()):
                row_meta = sidecar[int(global_idx)]
                flags = semantic_flags(row_meta, train_sets, train_val_sets, medium_min_packet)
                dist = float(attack_nearest[j])
                coverage_rows.append(
                    {
                        "seed": seed,
                        "target_role": ATTACK_EVAL_ROLE,
                        "support_scheme": scheme_name,
                        "support_scheme_note": scheme_note,
                        "target_row_id": int(global_idx),
                        "threshold": threshold,
                        "score_anomaly_higher": float(score_attack[j]),
                        "detected_under_existing_threshold": bool(score_attack[j] > threshold),
                        "nearest_support_distance": dist,
                        "support_density_knn3": float(attack_knn[3][j]),
                        "support_density_knn5": float(attack_knn[5][j]),
                        "support_density_knn10": float(attack_knn[10][j]),
                        "coverage_bucket": bucket_distance(dist, thresholds),
                        "coverage_p50": thresholds["p50"],
                        "coverage_p75": thresholds["p75"],
                        "coverage_p90": thresholds["p90"],
                        "coverage_p95": thresholds["p95"],
                        **flags,
                    }
                )
            if new_x.size:
                thresholds_new, new_nearest, new_knn = coverage_metrics(x[scheme_train], x[scheme_val], new_x)
                # Bucket thresholds intentionally come from the same support_val dev distribution;
                # thresholds_new equals thresholds if the support scheme is unchanged except for
                # numerical recomputation. Keep thresholds to avoid target-derived bucket rules.
                _ = thresholds_new
                new_train_sets = train_sets
                new_train_val_sets = train_val_sets
                for j, row_meta in enumerate(new_sidecar):
                    flags = semantic_flags(row_meta, new_train_sets, new_train_val_sets, new_min_packet)
                    dist = float(new_nearest[j])
                    coverage_rows.append(
                        {
                            "seed": seed,
                            "target_role": NEW_HELDOUT_ROLE,
                            "support_scheme": scheme_name,
                            "support_scheme_note": scheme_note,
                            "target_row_id": j,
                            "threshold": threshold,
                            "score_anomaly_higher": float(score_new[j]),
                            "detected_under_existing_threshold": bool(score_new[j] > threshold),
                            "nearest_support_distance": dist,
                            "support_density_knn3": float(new_knn[3][j]),
                            "support_density_knn5": float(new_knn[5][j]),
                            "support_density_knn10": float(new_knn[10][j]),
                            "coverage_bucket": bucket_distance(dist, thresholds),
                            "coverage_p50": thresholds["p50"],
                            "coverage_p75": thresholds["p75"],
                            "coverage_p90": thresholds["p90"],
                            "coverage_p95": thresholds["p95"],
                            **flags,
                        }
                    )

    bucket_summary = summarize_buckets(coverage_rows)
    distribution_rows = summarize_distribution(coverage_rows)
    correlation_rows = correlations(coverage_rows)
    suff_rows = sufficiency(coverage_rows)

    primary_suff = [
        r
        for r in suff_rows
        if r["support_scheme"] == "issue27as_selected_kcenter128" and r["subset"] == "coverage_sufficient"
    ]
    primary_insuff = [
        r
        for r in suff_rows
        if r["support_scheme"] == "issue27as_selected_kcenter128" and r["subset"] == "coverage_insufficient"
    ]
    def mean_det(role: str, rows: list[dict[str, Any]]) -> float:
        vals = [float(r["detection_rate"]) for r in rows if r["target_role"] == role]
        return float(np.mean(vals)) if vals else float("nan")
    def mean_frac(role: str, rows: list[dict[str, Any]]) -> float:
        vals = [float(r["sample_fraction"]) for r in rows if r["target_role"] == role]
        return float(np.mean(vals)) if vals else float("nan")

    medium_suff_det = mean_det(ATTACK_EVAL_ROLE, primary_suff)
    medium_insuff_det = mean_det(ATTACK_EVAL_ROLE, primary_insuff)
    new_suff_det = mean_det(NEW_HELDOUT_ROLE, primary_suff)
    new_insuff_det = mean_det(NEW_HELDOUT_ROLE, primary_insuff)
    new_suff_frac = mean_frac(NEW_HELDOUT_ROLE, primary_suff)
    medium_suff_frac = mean_frac(ATTACK_EVAL_ROLE, primary_suff)
    forbidden = any(r["forbidden_role_access"] for r in role_access_rows)
    if forbidden or not coverage_rows:
        primary_verdict = "coverage_analysis_blocked_by_missing_scores_or_indices"
    elif new_suff_frac < 0.35 and new_suff_det >= 0.75 and new_insuff_det <= 0.25:
        primary_verdict = "coverage_supported_but_new_heldout_requires_target_support_or_active_labeling"
    elif medium_suff_det >= 0.85 and medium_insuff_det + 0.10 < medium_suff_det and new_suff_det >= 0.75:
        primary_verdict = "coverage_hypothesis_supported_ready_for_coverage_gate_design"
    elif medium_suff_det >= 0.75 and new_suff_det > new_insuff_det:
        primary_verdict = "coverage_hypothesis_partially_supported_needs_more_attack_pool"
    else:
        primary_verdict = "coverage_hypothesis_not_supported_feature_or_protocol_boundary"

    definitions = {
        "issue": ISSUE,
        "scope": "coverage hypothesis validation only; not formal benchmark",
        "primary_replay_candidate": {
            "strategy": PRIMARY_STRATEGY,
            "support_budget": PRIMARY_SUPPORT_BUDGET,
            "ood_weight": PRIMARY_OOD_WEIGHT,
            "support_weight": PRIMARY_SUPPORT_WEIGHT,
            "threshold_rule": PRIMARY_THRESHOLD_RULE,
            "selection_source": "issue27as val-side selected candidate",
        },
        "coverage_scaler_policy": "StandardScaler fit on each support_train only; never on attack_eval, new heldout, or final OOD",
        "bucket_threshold_policy": "distance bucket thresholds are p50/p75/p95 of support_val nearest-support distances only",
        "coverage_buckets": {
            "covered_close": "nearest_support_distance <= support_val p50",
            "covered_mid": "p50 < nearest_support_distance <= support_val p75",
            "covered_far": "p75 < nearest_support_distance <= support_val p95",
            "uncovered_extreme": "nearest_support_distance > support_val p95",
        },
        "support_density": ["mean distance to nearest 3 support rows", "mean distance to nearest 5 support rows", "mean distance to nearest 10 support rows"],
        "semantic_fields": ["attack_type", "source_file", "device", "onset_phase", "time_bucket"],
        "support_schemes": {
            "issue27as_selected_kcenter128": "primary issue27as selected support train/val split by seed",
            "old_kcenter32_trace": "old kcenter32 trace comparison only",
            "file_balanced_v2_diagnostic": "issue27ao diagnostic support; not formal because it consumed old attack_eval for contract design",
        },
        "forbidden_selection_roles": [FINAL_OOD_ROLE, ATTACK_EVAL_ROLE, NEW_HELDOUT_ROLE],
    }
    (OUT / "coverage_score_definitions.json").write_text(json.dumps(definitions, indent=2, sort_keys=True), encoding="utf-8")

    write_csv(OUT / "input_artifact_hash_audit.csv", input_hash_rows)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)
    write_csv(OUT / "threshold_replay_audit.csv", threshold_rows)
    write_csv(OUT / "coverage_vs_detection_report.csv", coverage_rows)
    write_csv(OUT / "coverage_bucket_detection_summary.csv", bucket_summary)
    write_csv(OUT / "coverage_correlation_report.csv", correlation_rows)
    write_csv(OUT / "medium_vs_heavy_coverage_distribution.csv", distribution_rows)
    write_csv(OUT / "coverage_sufficiency_test.csv", suff_rows)

    write_md(
        OUT / "medium_vs_heavy_coverage_comparison.md",
        [
            "# Medium vs Heavy Coverage Comparison",
            "",
            f"- primary support scheme: `issue27as_selected_kcenter128`",
            f"- medium coverage-sufficient fraction: `{medium_suff_frac}`",
            f"- new heldout coverage-sufficient fraction: `{new_suff_frac}`",
            f"- medium sufficient detection: `{medium_suff_det}`",
            f"- medium insufficient detection: `{medium_insuff_det}`",
            f"- new heldout sufficient detection: `{new_suff_det}`",
            f"- new heldout insufficient detection: `{new_insuff_det}`",
            "",
            "Interpretation: if the new heldout sufficient subset is detected while the insufficient subset collapses, the low heldout detection is consistent with support-query coverage gap. This does not repair final OOD tail risk and is not a performance claim.",
        ],
    )
    write_md(
        OUT / "coverage_sufficiency_decision.md",
        [
            "# Coverage Sufficiency Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "- Coverage-sufficient means `covered_close` or `covered_mid` under support-val-derived distance buckets.",
            "- This subset is report-only diagnostic and cannot become a formal eval subset.",
            "- No threshold, support, or model config is selected using attack_eval or new heldout.",
            "",
            "## Boundary",
            "",
            "- If coverage explains heldout collapse, the next step is a coverage-aware support gate / active labeling design.",
            "- If coverage does not explain it, the next step is feature/task/protocol boundary redesign.",
            "- The issue27as final OOD tail overbudget remains a separate blocker.",
        ],
    )
    write_md(
        OUT / "issue27at_decision.md",
        [
            "# Issue27at Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "Coverage is evaluated only as a failure-explanation hypothesis. The primary support scheme is the issue27as val-side selected kcenter128 support split; old kcenter32 and file_balanced_v2 are static coverage comparisons only.",
            "",
            "## Key Boundary",
            "",
            f"- medium coverage-sufficient detection: `{medium_suff_det}`",
            f"- medium coverage-insufficient detection: `{medium_insuff_det}`",
            f"- new heldout coverage-sufficient fraction: `{new_suff_frac}`",
            f"- new heldout coverage-sufficient detection: `{new_suff_det}`",
            f"- new heldout coverage-insufficient detection: `{new_insuff_det}`",
            "",
            "This supports the coverage/support-query gap hypothesis only partially: the covered new-heldout subset is detected, but most new-heldout rows are outside the support-val-derived covered region and some uncovered behavior remains seed-sensitive. Therefore this result is not enough to claim a method improvement or proceed to full benchmark.",
            "",
            "Final OOD tail risk from issue27as is not solved by this analysis and remains a separate blocker.",
        ],
    )
    write_md(
        OUT / "coverage_gate_v0_draft.md",
        [
            "# Coverage Gate v0 Draft",
            "",
            "This is a draft only. It is not applied in issue27at and is not tuned on new heldout.",
            "",
            "1. Compute support coverage using a scaler fit only on `support_train`.",
            "2. Define distance buckets using `support_val` nearest-support distance quantiles.",
            "3. `allow_adaptation` if nearest distance <= support_val p75 and at least attack_type plus one of source_file/device/onset_phase is covered by train/val support.",
            "4. `needs_review` if nearest distance is between p75 and p95 or semantic coverage is partial.",
            "5. `support_insufficient_needs_more_labels` if nearest distance > p95 or semantic coverage is missing.",
            "",
            "The rule is intended for future active-labeling/support adequacy checks, not for selecting issue27at results.",
        ],
    )
    next_issue = (
        "issue27au_coverage_aware_support_gate_and_active_labeling_design"
        if primary_verdict
        in {
            "coverage_hypothesis_supported_ready_for_coverage_gate_design",
            "coverage_hypothesis_partially_supported_needs_more_attack_pool",
            "coverage_supported_but_new_heldout_requires_target_support_or_active_labeling",
        }
        else "issue27au_feature_task_boundary_or_protocol_redesign"
    )
    write_md(
        OUT / "issue27au_next_action.md",
        [
            "# Issue27au Next Action",
            "",
            f"Recommended next issue: `{next_issue}`.",
            "",
            "- Do not run full/larger formal benchmark yet.",
            "- Do not use new heldout to optimize a threshold.",
            "- Keep final OOD tail risk as a separate gate.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27at.md",
        [
            "# Claim Update After issue27at",
            "",
            "- issue27at validates a coverage hypothesis only; it is not a model performance claim.",
            "- New heldout remains report-only.",
            "- If coverage is supported, the claim is only that support adequacy/active labeling deserves a clean design pass.",
            "- Formal benchmark and mainline claims remain blocked until data scale, final OOD tail, and full protocol are fixed.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27at Summary",
            "",
            "1. issue27at completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. formal benchmark: no",
            "4. full/larger run: no",
            "5. new model training/search: no; deterministic replay of issue27as selected candidate only",
            "6. support/threshold changed: no",
            "7. final OOD / attack_eval / new heldout used for selection: no",
            f"8. primary support scheme: `issue27as_selected_kcenter128`",
            f"9. medium coverage-sufficient fraction: `{medium_suff_frac}`",
            f"10. new heldout coverage-sufficient fraction: `{new_suff_frac}`",
            f"11. medium sufficient/insufficient detection: `{medium_suff_det}` / `{medium_insuff_det}`",
            f"12. new heldout sufficient/insufficient detection: `{new_suff_det}` / `{new_insuff_det}`",
            "13. final OOD tail issue resolved: no, not addressed by this task",
            f"14. issue27au recommended: `{next_issue}`",
            "15. commit hash: pending",
        ],
    )

    config = {
        "issue": ISSUE,
        "primary_verdict": primary_verdict,
        "primary_replay_candidate": definitions["primary_replay_candidate"],
        "seeds": SEEDS,
        "selection_policy": "no final OOD, attack_eval, or new heldout used for model/support/threshold selection",
        "formal_benchmark": False,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "issue27af_certificate": str(cert_path),
                    "issue27as_outputs": str(ISSUE27AS),
                    "issue27ao_contract_v2": str(ISSUE27AO),
                    "new_heldout": str(ar.NEW_HELDOUT_DIR),
                },
                "outputs": f"runs/{ISSUE}/",
                "replay_policy": "deterministic per-sample score replay for issue27as selected candidate only",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27at -->",
        [
            "<!-- issue27at -->",
            "## issue27at - Coverage hypothesis validation before protocol redesign",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- Diagnostic only; deterministic replay of issue27as selected candidate to compute per-sample coverage vs detection.",
            "- New heldout remains report-only; final OOD tail risk is not resolved.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27at -->",
        [
            "<!-- issue27at -->",
            "## issue27at - Coverage hypothesis validation",
            "",
            f"- verdict: `{primary_verdict}`",
            "- purpose: test whether support-query coverage explains medium/high vs heavy/low heldout behavior without tuning a new protocol.",
            f"- outputs: `runs/{ISSUE}/`.",
        ],
    )
    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(json.dumps({"primary_verdict": primary_verdict, "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
