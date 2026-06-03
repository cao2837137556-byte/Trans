from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import ks_2samp, wasserstein_distance
from sklearn.metrics import pairwise_distances, roc_auc_score
from sklearn.preprocessing import StandardScaler


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27an_gotham_kitsune115_feature_state_onset_label_alignment_audit_2026-06-03"
OUT = ROOT / "runs" / ISSUE
ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AM = ROOT / "runs" / "issue27am_medium_bounded_protocol_repair_validation_2026-06-03"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ID_ROLE = "id_benign_train"
OOD_VAL_ROLE = "ood_benign_val"
FINAL_OOD_ROLE = "final_ood_benign_eval"
SUPPORT_ROLE = "attack_support"
ATTACK_EVAL_ROLE = "attack_eval"
PRIMARY_STRATEGY = "reset_at_split_boundary"
ONLINE_STRATEGY = "train_state_then_eval_online"
SEEDS = [42, 43, 44]


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


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_indices(indices: np.ndarray) -> str:
    text = ",".join(map(str, np.asarray(indices, dtype=np.int64).tolist()))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def verify_hash(path: Path, expected: str) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    actual = sha256(path)
    return actual == expected, actual


def load_asset(strategy: str, cert: dict[str, Any]) -> dict[str, Any]:
    c = cert[strategy]
    checks = []
    for key, hash_key in [
        ("X_115D_path", "X_115D_sha256"),
        ("y_path", "y_sha256"),
        ("sidecar_path", "sidecar_sha256"),
        ("split_manifest_path", "split_manifest_sha256"),
        ("feature_schema_path", "feature_schema_sha256"),
        ("state_transition_log_path", "state_transition_log_sha256"),
    ]:
        ok, actual = verify_hash(Path(c[key]), c[hash_key])
        checks.append({
            "strategy": strategy,
            "artifact_key": key,
            "path": c[key],
            "expected_sha256": c[hash_key],
            "actual_sha256": actual,
            "hash_match": ok,
        })
        if not ok:
            raise RuntimeError(f"hash mismatch for {strategy}:{key}")
    x = np.load(c["X_115D_path"])
    y = np.load(c["y_path"]).astype(int)
    sidecar = load_csv(Path(c["sidecar_path"]))
    schema = json.loads(Path(c["feature_schema_path"]).read_text(encoding="utf-8"))
    state_log = load_csv(Path(c["state_transition_log_path"]))
    if x.shape[0] != y.shape[0] or x.shape[0] != len(sidecar):
        raise RuntimeError(f"row mismatch for {strategy}")
    if x.shape[1] != 115:
        raise RuntimeError(f"expected 115D, got {x.shape[1]}")
    return {"X": x, "y": y, "sidecar": sidecar, "schema": schema, "state_log": state_log, "certificate": c, "checks": checks}


def role_mask(sidecar: list[dict[str, str]], role: str, model_ready: bool = True) -> np.ndarray:
    if model_ready:
        return np.asarray([r.get("role") == role and r.get("model_ready_hint", "").lower() == "true" for r in sidecar], dtype=bool)
    return np.asarray([r.get("role") == role for r in sidecar], dtype=bool)


def family_of(name: str) -> str:
    if name.startswith("MI_dir"):
        return "MI_dir"
    if name.startswith("HH_jit"):
        return "HH_jit"
    if name.startswith("HpHp"):
        return "HpHp"
    if name.startswith("HH"):
        return "HH"
    if name.startswith("H"):
        return "H"
    return "unknown"


def auc_abs(a: np.ndarray, b: np.ndarray) -> float:
    y = np.concatenate([np.zeros(a.shape[0]), np.ones(b.shape[0])])
    s = np.concatenate([a, b])
    if len(set(np.asarray(s, dtype=float).tolist())) <= 1:
        return 0.5
    auc = float(roc_auc_score(y, s))
    return max(auc, 1.0 - auc)


def effect_size(a: np.ndarray, b: np.ndarray) -> float:
    va = float(np.var(a))
    vb = float(np.var(b))
    denom = math.sqrt((va + vb) / 2.0)
    if denom == 0:
        return 0.0
    return float((np.mean(b) - np.mean(a)) / denom)


def overlap_coefficient(a: np.ndarray, b: np.ndarray) -> float:
    lo = min(float(np.min(a)), float(np.min(b)))
    hi = max(float(np.max(a)), float(np.max(b)))
    if not np.isfinite(lo) or not np.isfinite(hi) or lo == hi:
        return 1.0
    ha, edges = np.histogram(a, bins=80, range=(lo, hi), density=True)
    hb, _ = np.histogram(b, bins=edges, density=True)
    width = edges[1] - edges[0]
    return float(np.minimum(ha, hb).sum() * width)


def pair_indices(asset: dict[str, Any], pair_name: str, support_val_union: np.ndarray) -> tuple[np.ndarray, np.ndarray, str, str]:
    sidecar = asset["sidecar"]
    if pair_name == "id_vs_ood":
        return np.flatnonzero(role_mask(sidecar, ID_ROLE)), np.flatnonzero(role_mask(sidecar, OOD_VAL_ROLE)), ID_ROLE, OOD_VAL_ROLE
    if pair_name == "ood_vs_attack_eval":
        return np.flatnonzero(role_mask(sidecar, OOD_VAL_ROLE)), np.flatnonzero(role_mask(sidecar, ATTACK_EVAL_ROLE)), OOD_VAL_ROLE, ATTACK_EVAL_ROLE
    if pair_name == "attack_support_vs_attack_eval":
        return np.flatnonzero(role_mask(sidecar, SUPPORT_ROLE)), np.flatnonzero(role_mask(sidecar, ATTACK_EVAL_ROLE)), SUPPORT_ROLE, ATTACK_EVAL_ROLE
    if pair_name == "support_val_vs_attack_eval":
        return support_val_union, np.flatnonzero(role_mask(sidecar, ATTACK_EVAL_ROLE)), "attack_support_val_union", ATTACK_EVAL_ROLE
    raise ValueError(pair_name)


def split_support(selected: np.ndarray, train_size: int, val_size: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    shuffled = np.asarray(selected, dtype=np.int64).copy()
    rng.shuffle(shuffled)
    return np.asarray(sorted(shuffled[:train_size].tolist()), dtype=np.int64), np.asarray(sorted(shuffled[train_size:train_size + val_size].tolist()), dtype=np.int64)


def issue27am_support_val_union(strategy: str = PRIMARY_STRATEGY) -> np.ndarray:
    rows = load_csv(ISSUE27AM / "support_selector_indices.csv")
    selected = np.asarray([
        int(r["global_row_index"]) for r in rows
        if r.get("strategy") == strategy and r.get("support_selector") == "stratified_kcenter64" and r.get("support_size") == "64"
    ], dtype=np.int64)
    vals: set[int] = set()
    for seed in SEEDS:
        _, val = split_support(selected, 48, 16, seed)
        vals.update(val.tolist())
    return np.asarray(sorted(vals), dtype=np.int64)


def feature_separability(asset: dict[str, Any], support_val_union: np.ndarray) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    x = asset["X"]
    names = asset["schema"]["feature_names"]
    feature_rows: list[dict[str, Any]] = []
    pair_names = ["id_vs_ood", "ood_vs_attack_eval", "attack_support_vs_attack_eval", "support_val_vs_attack_eval"]
    for pair_name in pair_names:
        ia, ib, role_a, role_b = pair_indices(asset, pair_name, support_val_union)
        for j, name in enumerate(names):
            a = x[ia, j]
            b = x[ib, j]
            feature_rows.append({
                "strategy": asset["certificate"]["strategy"],
                "pair_name": pair_name,
                "role_a": role_a,
                "role_b": role_b,
                "feature_index": j,
                "feature_name": name,
                "family": family_of(name),
                "n_a": len(a),
                "n_b": len(b),
                "auc_abs_report_only": auc_abs(a, b),
                "ks_stat": float(ks_2samp(a, b).statistic),
                "wasserstein": float(wasserstein_distance(a, b)),
                "effect_size": effect_size(a, b),
                "overlap_coeff": overlap_coefficient(a, b),
                "mean_a": float(np.mean(a)),
                "mean_b": float(np.mean(b)),
                "std_a": float(np.std(a)),
                "std_b": float(np.std(b)),
                "report_only_oracle": pair_name != "id_vs_ood",
                "used_for_protocol_selection": False,
            })
    family_rows: list[dict[str, Any]] = []
    for pair_name in pair_names:
        pair_features = [r for r in feature_rows if r["pair_name"] == pair_name]
        for fam in ["MI_dir", "H", "HH", "HH_jit", "HpHp"]:
            fam_rows = [r for r in pair_features if r["family"] == fam]
            aucs = sorted([float(r["auc_abs_report_only"]) for r in fam_rows], reverse=True)
            ks_vals = sorted([float(r["ks_stat"]) for r in fam_rows], reverse=True)
            if not fam_rows:
                continue
            family_rows.append({
                "strategy": asset["certificate"]["strategy"],
                "pair_name": pair_name,
                "family": fam,
                "feature_count": len(fam_rows),
                "max_feature_auc_abs_report_only": aucs[0],
                "mean_top5_auc_abs_report_only": float(np.mean(aucs[: min(5, len(aucs))])),
                "median_auc_abs_report_only": float(np.median(aucs)),
                "max_ks_stat": ks_vals[0],
                "mean_top5_ks_stat": float(np.mean(ks_vals[: min(5, len(ks_vals))])),
                "report_only_oracle": pair_name != "id_vs_ood",
                "used_for_protocol_selection": False,
            })
    return feature_rows, family_rows


def role_file_groups(sidecar: list[dict[str, str]], role: str) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(sidecar):
        if r.get("role") == role:
            groups[r.get("csv_member", "unknown_csv")].append(i)
    return groups


def onset_audit(asset: dict[str, Any]) -> list[dict[str, Any]]:
    x = asset["X"]
    sidecar = asset["sidecar"]
    rows = []
    for role in [SUPPORT_ROLE, ATTACK_EVAL_ROLE]:
        for csv_member, idxs in sorted(role_file_groups(sidecar, role).items()):
            idxs = sorted(idxs)
            ready = [i for i in idxs if sidecar[i].get("model_ready_hint", "").lower() == "true"]
            warmup = [i for i in idxs if sidecar[i].get("warmup_only", "").lower() == "true"]
            attack_labeled = [i for i in idxs if sidecar[i].get("binary_label_from_alignment") == "attack"]
            if not idxs:
                continue
            ts_all = np.asarray([float(sidecar[i].get("packet_timestamp_epoch") or "nan") for i in idxs])
            first_attack = min(attack_labeled) if attack_labeled else None
            first_ready = min(ready) if ready else None
            first_attack_ts = float(sidecar[first_attack]["packet_timestamp_epoch"]) if first_attack is not None else float("nan")
            first_ready_ts = float(sidecar[first_ready]["packet_timestamp_epoch"]) if first_ready is not None else float("nan")
            for bucket_name, lo, hi in [
                ("onset_to_500", 0, 500),
                ("onset_500_to_2000", 500, 2000),
                ("onset_2000_to_10000", 2000, 10000),
                ("model_ready_all", None, None),
            ]:
                if first_attack is None:
                    bucket = []
                elif lo is None:
                    bucket = ready
                else:
                    onset_packet = int(sidecar[first_attack].get("packet_index") or 0)
                    bucket = [
                        i for i in ready
                        if lo <= (int(sidecar[i].get("packet_index") or 0) - onset_packet) < hi
                    ]
                if bucket:
                    feat_energy = float(np.mean(np.abs(StandardScaler().fit_transform(x[bucket])))) if len(bucket) > 1 else 0.0
                else:
                    feat_energy = 0.0
                rows.append({
                    "strategy": asset["certificate"]["strategy"],
                    "role": role,
                    "csv_member": csv_member,
                    "bucket": bucket_name,
                    "total_rows_in_file_role": len(idxs),
                    "model_ready_rows": len(ready),
                    "warmup_rows": len(warmup),
                    "attack_labeled_rows": len(attack_labeled),
                    "attack_density_model_ready": len([i for i in ready if sidecar[i].get("binary_label_from_alignment") == "attack"]) / max(1, len(ready)),
                    "first_attack_global_row": first_attack if first_attack is not None else "",
                    "first_model_ready_global_row": first_ready if first_ready is not None else "",
                    "first_attack_timestamp": first_attack_ts,
                    "first_model_ready_timestamp": first_ready_ts,
                    "ready_after_onset": bool(first_attack is not None and first_ready is not None and first_ready >= first_attack),
                    "bucket_rows": len(bucket),
                    "bucket_feature_energy_diagnostic": feat_energy,
                    "onset_alignment_status": "ready_after_attack_onset" if first_attack is not None and first_ready is not None and first_ready >= first_attack else "needs_review",
                })
    return rows


def state_audit(primary: dict[str, Any], online: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for asset in [primary, online]:
        sidecar = asset["sidecar"]
        state_log = asset["state_log"]
        for role in [ID_ROLE, OOD_VAL_ROLE, FINAL_OOD_ROLE, SUPPORT_ROLE, ATTACK_EVAL_ROLE]:
            mask_all = role_mask(sidecar, role, model_ready=False)
            mask_ready = role_mask(sidecar, role, model_ready=True)
            warmup = np.asarray([r.get("role") == role and r.get("warmup_only", "").lower() == "true" for r in sidecar], dtype=bool)
            state_ids = sorted({r.get("state_id", "") for r in sidecar if r.get("role") == role})
            rows.append({
                "strategy": asset["certificate"]["strategy"],
                "role": role,
                "all_rows": int(mask_all.sum()),
                "model_ready_rows": int(mask_ready.sum()),
                "warmup_rows": int(warmup.sum()),
                "state_id_count": len([s for s in state_ids if s]),
                "state_id_examples": "|".join(state_ids[:5]),
                "warmup_excluded_from_model_ready": bool(not np.any(warmup & mask_ready)),
                "state_transition_log_rows": len(state_log),
                "state_strategy_status": "auditable",
            })
    x0 = primary["X"]
    x1 = online["X"]
    if x0.shape == x1.shape:
        for role in [ID_ROLE, OOD_VAL_ROLE, FINAL_OOD_ROLE, SUPPORT_ROLE, ATTACK_EVAL_ROLE]:
            m = role_mask(primary["sidecar"], role)
            diff = np.abs(x0[m] - x1[m])
            rows.append({
                "strategy": "reset_vs_online_feature_delta",
                "role": role,
                "all_rows": int(m.sum()),
                "model_ready_rows": int(m.sum()),
                "warmup_rows": "",
                "state_id_count": "",
                "state_id_examples": "",
                "warmup_excluded_from_model_ready": "",
                "state_transition_log_rows": "",
                "mean_abs_feature_delta": float(np.mean(diff)) if diff.size else 0.0,
                "max_abs_feature_delta": float(np.max(diff)) if diff.size else 0.0,
                "state_strategy_status": "feature_delta_computed",
            })
    return rows


def support_coverage(asset: dict[str, Any], support_val_union: np.ndarray) -> list[dict[str, Any]]:
    x = asset["X"]
    sidecar = asset["sidecar"]
    attack_eval_idx = np.flatnonzero(role_mask(sidecar, ATTACK_EVAL_ROLE))
    selector_rows = load_csv(ISSUE27AM / "support_selector_indices.csv")
    rows = []
    for selector in ["kcenter32", "stratified_kcenter64", "stratified_kcenter128", "support_val_union_stratified_kcenter64"]:
        if selector == "support_val_union_stratified_kcenter64":
            selected = support_val_union
            support_size = len(selected)
        else:
            selected = np.asarray([
                int(r["global_row_index"]) for r in selector_rows
                if r.get("strategy") == asset["certificate"]["strategy"] and r.get("support_selector") == selector.replace("stratified_kcenter", "stratified_kcenter") and (
                    (selector == "kcenter32" and r.get("support_size") == "32")
                    or (selector == "stratified_kcenter64" and r.get("support_size") == "64")
                    or (selector == "stratified_kcenter128" and r.get("support_size") == "128")
                )
            ], dtype=np.int64)
            support_size = len(selected)
        if selected.size == 0:
            continue
        scaler = StandardScaler().fit(x[selected])
        zs = scaler.transform(x[selected])
        ze = scaler.transform(x[attack_eval_idx])
        d = pairwise_distances(ze, zs, metric="euclidean")
        nearest = d.min(axis=1)
        nearest_support = selected[d.argmin(axis=1)]
        for group_field in ["csv_member", "attack_type_from_raw_path"]:
            groups: dict[str, list[int]] = defaultdict(list)
            for local_i, global_i in enumerate(attack_eval_idx):
                groups[sidecar[int(global_i)].get(group_field) or "unknown"].append(local_i)
            for group, local_rows in sorted(groups.items()):
                vals = nearest[local_rows]
                rows.append({
                    "strategy": asset["certificate"]["strategy"],
                    "selector": selector,
                    "support_size": support_size,
                    "group_field": group_field,
                    "group_value": group,
                    "attack_eval_rows": len(local_rows),
                    "nearest_distance_median": float(np.median(vals)),
                    "nearest_distance_p90": float(np.quantile(vals, 0.9)),
                    "nearest_distance_p95": float(np.quantile(vals, 0.95)),
                    "nearest_distance_max": float(np.max(vals)),
                    "coverage_radius_p95_global": float(np.quantile(nearest, 0.95)),
                    "nearest_support_unique_count": len(set(nearest_support[local_rows].tolist())),
                    "selected_support_hash": hash_indices(selected),
                    "uses_attack_eval_for_selection": False,
                    "report_only_coverage_audit": True,
                })
    return rows


def label_semantic(asset: dict[str, Any], feature_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sidecar = asset["sidecar"]
    rows = []
    attack_roles = [SUPPORT_ROLE, ATTACK_EVAL_ROLE]
    for role in attack_roles:
        model_ready_idx = np.flatnonzero(role_mask(sidecar, role))
        attack_types = Counter(sidecar[int(i)].get("attack_type_from_raw_path") or "unknown" for i in model_ready_idx)
        files = Counter(sidecar[int(i)].get("csv_member") or "unknown" for i in model_ready_idx)
        for attack_type, count in attack_types.items():
            # Current medium asset mainly has mirai-infection. Keep explicit so
            # later larger assets can surface mixed attack semantics.
            pair = "ood_vs_attack_eval" if role == ATTACK_EVAL_ROLE else "attack_support_vs_attack_eval"
            related = [r for r in feature_rows if r["strategy"] == asset["certificate"]["strategy"] and r["pair_name"] == pair]
            max_auc = max([float(r["auc_abs_report_only"]) for r in related], default=0.5)
            median_auc = float(np.median([float(r["auc_abs_report_only"]) for r in related])) if related else 0.5
            rows.append({
                "strategy": asset["certificate"]["strategy"],
                "role": role,
                "attack_type": attack_type,
                "rows": count,
                "file_count": len(files),
                "files": "|".join(sorted(files.keys())),
                "max_related_feature_auc_abs_report_only": max_auc,
                "median_related_feature_auc_abs_report_only": median_auc,
                "semantic_status": "single_attack_type_medium_asset" if len(attack_types) == 1 else "mixed_attack_types_need_stratified_reporting",
                "recommendation": "larger/full asset should split C&C/reporting/download/scan/flood if present; medium only contains mirai-infection path labels",
            })
    return rows


def decision(feature_rows: list[dict[str, Any]], coverage_rows: list[dict[str, Any]], onset_rows: list[dict[str, Any]], state_rows: list[dict[str, Any]]) -> tuple[str, list[str]]:
    ood_attack = [r for r in feature_rows if r["pair_name"] == "ood_vs_attack_eval"]
    support_eval = [r for r in feature_rows if r["pair_name"] in {"attack_support_vs_attack_eval", "support_val_vs_attack_eval"}]
    support_val_eval = [r for r in feature_rows if r["pair_name"] == "support_val_vs_attack_eval"]
    max_ood_attack_auc = max([float(r["auc_abs_report_only"]) for r in ood_attack], default=0.5)
    median_ood_attack_auc = float(np.median([float(r["auc_abs_report_only"]) for r in ood_attack])) if ood_attack else 0.5
    max_support_eval_auc = max([float(r["auc_abs_report_only"]) for r in support_eval], default=0.5)
    max_support_val_eval_auc = max([float(r["auc_abs_report_only"]) for r in support_val_eval], default=0.5)
    coverage_p95 = max([float(r["nearest_distance_p95"]) for r in coverage_rows if r.get("group_field") == "csv_member"], default=0.0)
    coverage_max = max([float(r["nearest_distance_max"]) for r in coverage_rows if r.get("group_field") == "csv_member"], default=0.0)
    onset_needs_review = any(r.get("onset_alignment_status") == "needs_review" for r in onset_rows)
    reset_online_attack_delta = [
        float(r.get("mean_abs_feature_delta", 0.0)) for r in state_rows
        if r.get("strategy") == "reset_vs_online_feature_delta" and r.get("role") in {SUPPORT_ROLE, ATTACK_EVAL_ROLE}
    ]
    reasons = [
        f"max_ood_vs_attack_eval_feature_auc_abs={max_ood_attack_auc:.6f}",
        f"median_ood_vs_attack_eval_feature_auc_abs={median_ood_attack_auc:.6f}",
        f"max_support_eval_related_feature_auc_abs={max_support_eval_auc:.6f}",
        f"max_support_val_vs_attack_eval_feature_auc_abs={max_support_val_eval_auc:.6f}",
        f"max_attack_eval_nearest_support_p95={coverage_p95:.6f}",
        f"max_attack_eval_nearest_support_max={coverage_max:.6f}",
        f"onset_rows_needing_review={onset_needs_review}",
        f"reset_online_attack_mean_abs_delta_max={max(reset_online_attack_delta) if reset_online_attack_delta else 0.0:.6f}",
    ]
    if max_ood_attack_auc < 0.70:
        return "kitsune115_feature_space_insufficient_for_gotham_attack_claim", reasons
    if onset_needs_review:
        return "attack_onset_or_label_alignment_blocker_found", reasons
    if max_support_val_eval_auc > 0.85 or coverage_p95 > 7.5 or coverage_max > 1000.0:
        return "support_eval_distribution_mismatch_blocker_found", reasons + [
            "support_val and/or selected support coverage differs materially from attack_eval; repair should target support/eval contract before adding heads"
        ]
    if max(reset_online_attack_delta, default=0.0) > 1.0:
        return "feature_state_audit_passed_protocol_needs_redesign", reasons + ["state strategy materially changes features; protocol must handle strategy explicitly"]
    return "feature_state_audit_passed_protocol_needs_redesign", reasons


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    primary = load_asset(PRIMARY_STRATEGY, cert)
    online = load_asset(ONLINE_STRATEGY, cert)
    artifact_rows = primary["checks"] + online["checks"] + [{
        "strategy": "issue27am",
        "artifact_key": "bounded_repair_summary",
        "path": str(ISSUE27AM / "bounded_repair_summary.csv"),
        "expected_sha256": "",
        "actual_sha256": sha256(ISSUE27AM / "bounded_repair_summary.csv"),
        "hash_match": True,
    }]
    write_csv(OUT / "input_artifact_hash_audit.csv", artifact_rows)

    support_val_union = issue27am_support_val_union(PRIMARY_STRATEGY)
    feature_rows, family_rows = feature_separability(primary, support_val_union)
    write_csv(OUT / "feature_separability_report.csv", feature_rows)
    write_csv(OUT / "family_separability_report.csv", family_rows)

    onset_rows = onset_audit(primary)
    state_rows = state_audit(primary, online)
    coverage_rows = support_coverage(primary, support_val_union)
    semantic_rows = label_semantic(primary, feature_rows)
    write_csv(OUT / "attack_onset_label_density_audit.csv", onset_rows)
    write_csv(OUT / "state_warmup_carryover_audit.csv", state_rows)
    write_csv(OUT / "support_eval_coverage_audit.csv", coverage_rows)
    write_csv(OUT / "label_semantic_audit.csv", semantic_rows)

    role_access_rows = [
        {"analysis": "feature_separability", "uses_final_ood_eval": True, "uses_attack_eval": True, "purpose": "report_only_failure_attribution", "used_for_protocol_selection": False},
        {"analysis": "onset_label_density", "uses_final_ood_eval": False, "uses_attack_eval": True, "purpose": "label_alignment_audit", "used_for_protocol_selection": False},
        {"analysis": "support_eval_coverage", "uses_final_ood_eval": False, "uses_attack_eval": True, "purpose": "support_eval_mismatch_audit", "used_for_protocol_selection": False},
        {"analysis": "label_semantic", "uses_final_ood_eval": False, "uses_attack_eval": True, "purpose": "failure_attribution", "used_for_protocol_selection": False},
    ]
    write_csv(OUT / "role_access_audit.csv", role_access_rows)

    primary_verdict, reasons = decision(feature_rows, coverage_rows, onset_rows, state_rows)
    top_pairs = {}
    for pair in ["id_vs_ood", "ood_vs_attack_eval", "attack_support_vs_attack_eval", "support_val_vs_attack_eval"]:
        rows = [r for r in feature_rows if r["pair_name"] == pair]
        top_pairs[pair] = max([float(r["auc_abs_report_only"]) for r in rows], default=0.5)
    top_families = {}
    for pair in ["ood_vs_attack_eval", "attack_support_vs_attack_eval", "support_val_vs_attack_eval"]:
        rows = [r for r in family_rows if r["pair_name"] == pair]
        top_families[pair] = max(rows, key=lambda r: float(r["max_feature_auc_abs_report_only"])) if rows else {}

    write_md(OUT / "issue27an_decision.md", [
        "# Issue27an Decision",
        "",
        f"- primary_verdict: `{primary_verdict}`",
        "- Scope: feature/state/onset/label alignment failure attribution only.",
        "- No new model training, no split change, no frontend change, no support-pool reconstruction.",
        "- Report-only oracle/separability analysis was used only for failure attribution.",
        "",
        "## Evidence",
        "",
        *[f"- {r}" for r in reasons],
        "",
        "## Pair Upper Bounds",
        "",
        *[f"- {k}: max per-feature AUC(abs) = {v:.6f}" for k, v in top_pairs.items()],
    ])
    next_action = {
        "kitsune115_feature_space_insufficient_for_gotham_attack_claim": "issue27ao_pause_model_line_and_review_feature_or_task_boundary",
        "attack_onset_or_label_alignment_blocker_found": "issue27ao_repair_attack_onset_label_alignment_before_protocol",
        "support_eval_distribution_mismatch_blocker_found": "issue27ao_repair_support_eval_contract_before_head_repair",
        "label_semantic_mismatch_blocker_found": "issue27ao_refine_attack_target_semantics",
        "feature_state_audit_passed_protocol_needs_redesign": "issue27ao_protocol_redesign_with_fixed_data_after_alignment_audit",
    }.get(primary_verdict, "issue27ao_manual_review")
    write_md(OUT / "issue27ao_next_action.md", [
        "# Issue27ao Next Action",
        "",
        f"- recommended_next_issue: `{next_action}`",
        "- Do not proceed to full/larger benchmark from issue27am.",
        "- If support/eval mismatch dominates, revise support/eval contract before adding heads.",
        "- If feature-space upper bound is weak, pause model repair and revisit feature/task boundary.",
        "- If protocol capture is the issue, redesign protocol using only train-side roles and keep final eval report-only.",
    ])
    write_md(OUT / "summary.md", [
        "# Issue27an Summary",
        "",
        "1. issue27an completed: yes",
        f"2. primary_verdict: `{primary_verdict}`",
        "3. no new model training: yes",
        "4. split changed: no",
        "5. frontend changed: no",
        "6. support pool reconstructed: no",
        f"7. ID vs OOD max feature AUC(abs): {top_pairs['id_vs_ood']:.6f}",
        f"8. OOD vs attack_eval max feature AUC(abs): {top_pairs['ood_vs_attack_eval']:.6f}",
        f"9. attack_support vs attack_eval max feature AUC(abs): {top_pairs['attack_support_vs_attack_eval']:.6f}",
        f"10. support_val vs attack_eval max feature AUC(abs): {top_pairs['support_val_vs_attack_eval']:.6f}",
        f"11. best OOD-vs-attack family: `{top_families['ood_vs_attack_eval'].get('family', 'none')}`",
        f"12. best support-vs-eval family: `{top_families['attack_support_vs_attack_eval'].get('family', 'none')}`",
        f"13. onset/label review needed: {any(r.get('onset_alignment_status') == 'needs_review' for r in onset_rows)}",
        "14. report-only eval used for selection: false",
        f"15. next action: `{next_action}`",
        "16. commit hash: pending",
    ])
    write_md(OUT / "command.txt", ["python repo/ood/issue27an_gotham_kitsune115_feature_state_onset_label_alignment_audit.py"])
    (OUT / "config.json").write_text(json.dumps({
        "issue": ISSUE,
        "primary_strategy": PRIMARY_STRATEGY,
        "online_strategy": ONLINE_STRATEGY,
        "no_new_model_training": True,
        "report_only_oracle_for_failure_attribution_only": True,
        "support_val_union_source": "issue27am stratified_kcenter64 support split seeds 42/43/44",
    }, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(json.dumps({
        "inputs": {
            "issue27af_certificate": str(cert_path),
            "issue27am_summary": str(ISSUE27AM / "summary.md"),
        },
        "required_outputs": [
            "summary.md",
            "feature_separability_report.csv",
            "family_separability_report.csv",
            "attack_onset_label_density_audit.csv",
            "state_warmup_carryover_audit.csv",
            "support_eval_coverage_audit.csv",
            "label_semantic_audit.csv",
            "issue27an_decision.md",
            "issue27ao_next_action.md",
        ],
    }, indent=2, sort_keys=True), encoding="utf-8")

    write_md(OUT / "claim_update_after_issue27an.md", [
        "# Claim Update After Issue27an",
        "",
        "- Issue27an is a failure attribution audit, not a model performance result.",
        "- issue27am repair results remain diagnostic only.",
        "- No formal Gotham Kitsune115 model claim should be made until the identified feature/state/onset/label or protocol blocker is resolved.",
    ])
    manifest_rows = []
    for p in sorted(OUT.glob("*")):
        if p.is_file():
            manifest_rows.append({"path": str(p.relative_to(ROOT)), "sha256": sha256(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)

    append_doc(MAINLINE_DOCS / "mainline_handoff.md", "<!-- issue27an -->", [
        "<!-- issue27an -->",
        "## issue27an_gotham_kitsune115_feature_state_onset_label_alignment_audit_2026-06-03",
        "",
        f"- primary_verdict: `{primary_verdict}`",
        "- Failure attribution audit after issue27am; no new model training or protocol repair.",
        "- Audited feature separability, onset/label density, state/warmup/carryover, support/eval coverage, and label semantics.",
        f"- next action: `{next_action}`",
    ])
    append_doc(MAINLINE_DOCS / "mainline_experiment_map.md", "<!-- issue27an -->", [
        "<!-- issue27an -->",
        "## issue27an",
        "",
        f"- verdict: `{primary_verdict}`",
        "- route: Gotham Kitsune115 medium failure attribution audit.",
        "- claim boundary: diagnostic failure attribution only; no model ranking or formal benchmark.",
    ])


if __name__ == "__main__":
    main()
