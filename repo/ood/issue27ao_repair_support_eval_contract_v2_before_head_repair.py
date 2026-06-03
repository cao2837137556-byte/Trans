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
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27ao_repair_support_eval_contract_v2_before_head_repair_2026-06-03"
OUT = ROOT / "runs" / ISSUE
ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AN = ROOT / "runs" / "issue27an_gotham_kitsune115_feature_state_onset_label_alignment_audit_2026-06-03"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

PRIMARY_STRATEGY = "reset_at_split_boundary"
ID_ROLE = "id_benign_train"
OOD_VAL_ROLE = "ood_benign_val"
FINAL_OOD_ROLE = "final_ood_benign_eval"
SUPPORT_ROLE = "attack_support"
ATTACK_EVAL_ROLE = "attack_eval"
SUPPORT_TRAIN_SIZE = 128
SUPPORT_VAL_SIZE = 64


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
    return hashlib.sha256(",".join(map(str, np.asarray(indices, dtype=np.int64).tolist())).encode("utf-8")).hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def verify_hash(path: Path, expected: str) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    actual = sha256(path)
    return actual == expected, actual


def load_asset() -> dict[str, Any]:
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    c = cert[PRIMARY_STRATEGY]
    for key, hash_key in [
        ("X_115D_path", "X_115D_sha256"),
        ("y_path", "y_sha256"),
        ("sidecar_path", "sidecar_sha256"),
        ("split_manifest_path", "split_manifest_sha256"),
        ("feature_schema_path", "feature_schema_sha256"),
    ]:
        ok, actual = verify_hash(Path(c[key]), c[hash_key])
        if not ok:
            raise RuntimeError(f"hash mismatch for {key}: {actual} != {c[hash_key]}")
    x = np.load(c["X_115D_path"])
    y = np.load(c["y_path"]).astype(int)
    sidecar = load_csv(Path(c["sidecar_path"]))
    if x.shape[0] != y.shape[0] or len(sidecar) != x.shape[0]:
        raise RuntimeError("asset row alignment failed")
    return {"X": x, "y": y, "sidecar": sidecar, "certificate": c, "cert_path": cert_path}


def role_mask(sidecar: list[dict[str, str]], role: str) -> np.ndarray:
    return np.asarray([r.get("role") == role and r.get("model_ready_hint", "").lower() == "true" for r in sidecar], dtype=bool)


def parse_device(csv_member: str) -> str:
    name = Path(csv_member).name
    if name.startswith("iotsim-"):
        stem = name.removesuffix(".csv").removeprefix("iotsim-")
        parts = stem.split("-")
        while parts and parts[-1].isdigit():
            parts.pop()
        return "-".join(parts) if parts else stem
    return "unknown"


def onset_phase(relative_packet: int) -> str:
    if relative_packet < 0:
        return "pre_onset"
    if relative_packet < 500:
        return "early_0_500"
    if relative_packet < 2000:
        return "mid_500_2000"
    if relative_packet < 10000:
        return "late_2000_10000"
    return "tail_gt_10000"


def build_taxonomy(sidecar: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    attack_indices = [
        i for i, r in enumerate(sidecar)
        if r.get("role") in {SUPPORT_ROLE, ATTACK_EVAL_ROLE}
        and r.get("model_ready_hint", "").lower() == "true"
    ]
    first_attack_packet_by_file: dict[str, int] = {}
    first_attack_ts_by_file: dict[str, float] = {}
    for i in attack_indices:
        r = sidecar[i]
        csv_member = r.get("csv_member", "unknown")
        pkt = int(float(r.get("packet_index") or 0))
        ts = float(r.get("packet_timestamp_epoch") or "nan")
        if r.get("binary_label_from_alignment") == "attack":
            if csv_member not in first_attack_packet_by_file or pkt < first_attack_packet_by_file[csv_member]:
                first_attack_packet_by_file[csv_member] = pkt
                first_attack_ts_by_file[csv_member] = ts
    rows = []
    by_index = {}
    for i in attack_indices:
        r = sidecar[i]
        csv_member = r.get("csv_member", "unknown")
        pkt = int(float(r.get("packet_index") or 0))
        onset_pkt = first_attack_packet_by_file.get(csv_member, pkt)
        rel = pkt - onset_pkt
        info = {
            "global_row_index": i,
            "old_role": r.get("role"),
            "csv_member": csv_member,
            "device": parse_device(csv_member),
            "attack_type": r.get("attack_type_from_raw_path") or "unknown",
            "packet_index": pkt,
            "timestamp": float(r.get("packet_timestamp_epoch") or "nan"),
            "onset_packet_idx": onset_pkt,
            "relative_packet_after_onset": rel,
            "onset_phase": onset_phase(rel),
            "state_strategy": r.get("strategy", PRIMARY_STRATEGY),
            "binary_label": r.get("binary_label_from_alignment"),
            "model_ready_hint": r.get("model_ready_hint"),
            "protocol": "not_available_in_sidecar",
        }
        rows.append(info)
        by_index[i] = info
    return rows, by_index


def farthest_first_order(z: np.ndarray, budget: int) -> np.ndarray:
    n = z.shape[0]
    if n == 0:
        return np.asarray([], dtype=np.int64)
    if budget >= n:
        return np.arange(n, dtype=np.int64)
    centroid = z.mean(axis=0, keepdims=True)
    start = int(np.argmin(pairwise_distances(z, centroid, metric="euclidean").ravel()))
    selected = [start]
    min_dist = pairwise_distances(z, z[[start]], metric="euclidean").ravel()
    min_dist[start] = -1.0
    while len(selected) < budget:
        nxt = int(np.argmax(min_dist))
        selected.append(nxt)
        dist = pairwise_distances(z, z[[nxt]], metric="euclidean").ravel()
        min_dist = np.minimum(min_dist, dist)
        min_dist[selected] = -1.0
    return np.asarray(selected, dtype=np.int64)


def proportional_quotas(groups: dict[str, list[int]], total_budget: int) -> dict[str, int]:
    keys = sorted(groups)
    if total_budget <= len(keys):
        ranked = sorted(keys, key=lambda k: (-len(groups[k]), k))
        return {k: (1 if k in set(ranked[:total_budget]) else 0) for k in keys}
    total = sum(len(v) for v in groups.values())
    quotas: dict[str, int] = {}
    remainders: list[tuple[float, str]] = []
    used = 0
    for key in keys:
        raw = total_budget * len(groups[key]) / total
        q = max(1, int(math.floor(raw)))
        q = min(q, len(groups[key]))
        quotas[key] = q
        used += q
        remainders.append((raw - math.floor(raw), key))
    while used < total_budget:
        changed = False
        for _, key in sorted(remainders, reverse=True):
            if quotas[key] < len(groups[key]):
                quotas[key] += 1
                used += 1
                changed = True
                if used == total_budget:
                    break
        if not changed:
            break
    while used > total_budget:
        for _, key in sorted(remainders):
            if quotas[key] > 1:
                quotas[key] -= 1
                used -= 1
                if used == total_budget:
                    break
    return quotas


def select_stratified(x: np.ndarray, groups: dict[str, list[int]], budget: int) -> np.ndarray:
    quotas = proportional_quotas(groups, budget)
    selected: list[int] = []
    for key in sorted(groups):
        idx = np.asarray(sorted(groups[key]), dtype=np.int64)
        q = quotas.get(key, 0)
        if q <= 0:
            continue
        scaler = StandardScaler().fit(x[idx])
        z = scaler.transform(x[idx])
        local_order = farthest_first_order(z, q)
        selected.extend(idx[local_order].tolist())
    return np.asarray(sorted(selected), dtype=np.int64)


def group_key(info: dict[str, Any], candidate: str) -> str:
    if candidate == "file_balanced_v2":
        return info["csv_member"]
    if candidate == "phase_balanced_v2":
        return info["onset_phase"]
    if candidate == "file_phase_balanced_v2":
        return f"{info['csv_member']}|{info['onset_phase']}"
    raise ValueError(candidate)


def build_contract(x: np.ndarray, taxonomy: list[dict[str, Any]], candidate: str) -> dict[str, np.ndarray]:
    pool = [r["global_row_index"] for r in taxonomy if r["binary_label"] == "attack"]
    groups: dict[str, list[int]] = defaultdict(list)
    info_by_idx = {r["global_row_index"]: r for r in taxonomy}
    for idx in pool:
        groups[group_key(info_by_idx[idx], candidate)].append(idx)
    selected_train = select_stratified(x, groups, SUPPORT_TRAIN_SIZE)
    remaining_groups: dict[str, list[int]] = defaultdict(list)
    selected_train_set = set(selected_train.tolist())
    for idx in pool:
        if idx not in selected_train_set:
            remaining_groups[group_key(info_by_idx[idx], candidate)].append(idx)
    selected_val = select_stratified(x, remaining_groups, SUPPORT_VAL_SIZE)
    selected_val_set = set(selected_val.tolist())
    eval_idx = np.asarray(sorted([idx for idx in pool if idx not in selected_train_set and idx not in selected_val_set]), dtype=np.int64)
    return {"support_train": selected_train, "support_val": selected_val, "attack_eval": eval_idx}


def summarize_coverage(indices: np.ndarray, taxonomy_by_index: dict[int, dict[str, Any]]) -> dict[str, Any]:
    files = Counter(taxonomy_by_index[int(i)]["csv_member"] for i in indices)
    phases = Counter(taxonomy_by_index[int(i)]["onset_phase"] for i in indices)
    devices = Counter(taxonomy_by_index[int(i)]["device"] for i in indices)
    types = Counter(taxonomy_by_index[int(i)]["attack_type"] for i in indices)
    return {
        "rows": len(indices),
        "file_count": len(files),
        "phase_count": len(phases),
        "device_count": len(devices),
        "attack_type_count": len(types),
        "files": "|".join(sorted(files.keys())),
        "phases": "|".join(sorted(phases.keys())),
        "devices": "|".join(sorted(devices.keys())),
        "attack_types": "|".join(sorted(types.keys())),
        "file_counts_json": json.dumps(dict(sorted(files.items())), sort_keys=True),
        "phase_counts_json": json.dumps(dict(sorted(phases.items())), sort_keys=True),
    }


def distance_summary(x: np.ndarray, source_idx: np.ndarray, eval_idx: np.ndarray, label: str) -> dict[str, Any]:
    scaler = StandardScaler().fit(x[source_idx])
    zs = scaler.transform(x[source_idx])
    ze = scaler.transform(x[eval_idx])
    nearest = pairwise_distances(ze, zs, metric="euclidean").min(axis=1)
    return {
        f"{label}_nearest_median": float(np.median(nearest)),
        f"{label}_nearest_p90": float(np.quantile(nearest, 0.90)),
        f"{label}_nearest_p95": float(np.quantile(nearest, 0.95)),
        f"{label}_nearest_p99": float(np.quantile(nearest, 0.99)),
        f"{label}_nearest_max": float(np.max(nearest)),
    }


def old_baseline_summary() -> dict[str, float]:
    p = ISSUE27AN / "support_eval_coverage_audit.csv"
    if not p.exists():
        return {}
    rows = load_csv(p)
    support_val_rows = [r for r in rows if r.get("selector") == "support_val_union_stratified_kcenter64"]
    strat64_rows = [r for r in rows if r.get("selector") == "stratified_kcenter64"]
    def maxf(items: list[dict[str, str]], col: str) -> float:
        return max([float(r[col]) for r in items], default=float("nan"))
    return {
        "old_support_val_union_max_group_p95": maxf(support_val_rows, "nearest_distance_p95"),
        "old_support_val_union_max_group_max": maxf(support_val_rows, "nearest_distance_max"),
        "old_stratified_kcenter64_max_group_p95": maxf(strat64_rows, "nearest_distance_p95"),
        "old_stratified_kcenter64_max_group_max": maxf(strat64_rows, "nearest_distance_max"),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    asset = load_asset()
    x = asset["X"]
    sidecar = asset["sidecar"]
    taxonomy, taxonomy_by_index = build_taxonomy(sidecar)
    required = {"csv_member", "attack_type", "onset_phase", "timestamp", "device"}
    fields_ok = all(required.issubset(row.keys()) for row in taxonomy)

    write_csv(OUT / "attack_taxonomy_inventory.csv", taxonomy)

    candidates = ["file_balanced_v2", "phase_balanced_v2", "file_phase_balanced_v2"]
    candidate_rows = []
    train_rows = []
    val_rows = []
    eval_rows = []
    coverage_rows = []
    distance_rows = []
    old = old_baseline_summary()

    for candidate in candidates:
        contract = build_contract(x, taxonomy, candidate)
        all_sets = {
            "support_train": set(contract["support_train"].tolist()),
            "support_val": set(contract["support_val"].tolist()),
            "attack_eval": set(contract["attack_eval"].tolist()),
        }
        overlap = (
            len(all_sets["support_train"] & all_sets["support_val"])
            + len(all_sets["support_train"] & all_sets["attack_eval"])
            + len(all_sets["support_val"] & all_sets["attack_eval"])
        )
        for role, path_rows in [
            ("support_train", train_rows),
            ("support_val", val_rows),
            ("attack_eval", eval_rows),
        ]:
            for rank, idx in enumerate(contract[role].tolist()):
                info = taxonomy_by_index[int(idx)]
                path_rows.append({
                    "contract_id": candidate,
                    "new_role": role,
                    "rank": rank,
                    "global_row_index": idx,
                    "old_role": info["old_role"],
                    "csv_member": info["csv_member"],
                    "device": info["device"],
                    "attack_type": info["attack_type"],
                    "onset_phase": info["onset_phase"],
                    "relative_packet_after_onset": info["relative_packet_after_onset"],
                    "timestamp": info["timestamp"],
                })
        cov_train = summarize_coverage(contract["support_train"], taxonomy_by_index)
        cov_val = summarize_coverage(contract["support_val"], taxonomy_by_index)
        cov_eval = summarize_coverage(contract["attack_eval"], taxonomy_by_index)
        train_dist = distance_summary(x, contract["support_train"], contract["attack_eval"], "support_train_to_eval")
        val_dist = distance_summary(x, contract["support_val"], contract["attack_eval"], "support_val_to_eval")
        eval_files = set(cov_eval["files"].split("|")) if cov_eval["files"] else set()
        train_files = set(cov_train["files"].split("|")) if cov_train["files"] else set()
        val_files = set(cov_val["files"].split("|")) if cov_val["files"] else set()
        eval_phases = set(cov_eval["phases"].split("|")) if cov_eval["phases"] else set()
        train_phases = set(cov_train["phases"].split("|")) if cov_train["phases"] else set()
        val_phases = set(cov_val["phases"].split("|")) if cov_val["phases"] else set()
        file_coverage = len(eval_files & train_files & val_files) / max(1, len(eval_files))
        phase_coverage = len(eval_phases & train_phases & val_phases) / max(1, len(eval_phases))
        row = {
            "contract_id": candidate,
            "source_pool": "current_medium_attack_support_plus_attack_eval_model_ready_rows",
            "contract_scope": "medium_diagnostic_contract_design_not_formal_eval",
            "support_train_size": len(contract["support_train"]),
            "support_val_size": len(contract["support_val"]),
            "attack_eval_size": len(contract["attack_eval"]),
            "row_disjoint_overlap_count": overlap,
            "support_train_hash": hash_indices(contract["support_train"]),
            "support_val_hash": hash_indices(contract["support_val"]),
            "attack_eval_hash": hash_indices(contract["attack_eval"]),
            "file_coverage_train_val_vs_eval": file_coverage,
            "phase_coverage_train_val_vs_eval": phase_coverage,
            "uses_final_ood_benign_eval": False,
            "uses_model_results": False,
            "old_attack_eval_consumed_for_contract_design": True,
            "future_retest_scope": "diagnostic_only",
        }
        row.update({f"support_train_{k}": v for k, v in cov_train.items()})
        row.update({f"support_val_{k}": v for k, v in cov_val.items()})
        row.update({f"attack_eval_{k}": v for k, v in cov_eval.items()})
        candidate_rows.append(row)
        coverage_rows.extend([
            {"contract_id": candidate, "role": "support_train", **cov_train},
            {"contract_id": candidate, "role": "support_val", **cov_val},
            {"contract_id": candidate, "role": "attack_eval", **cov_eval},
        ])
        drow = {"contract_id": candidate}
        drow.update(train_dist)
        drow.update(val_dist)
        drow.update(old)
        drow["support_train_p95_improvement_vs_old_strat64"] = old.get("old_stratified_kcenter64_max_group_p95", float("nan")) - drow["support_train_to_eval_nearest_p95"]
        drow["support_val_p95_improvement_vs_old_support_val"] = old.get("old_support_val_union_max_group_p95", float("nan")) - drow["support_val_to_eval_nearest_p95"]
        drow["support_train_max_improvement_vs_old_strat64"] = old.get("old_stratified_kcenter64_max_group_max", float("nan")) - drow["support_train_to_eval_nearest_max"]
        drow["support_val_max_improvement_vs_old_support_val"] = old.get("old_support_val_union_max_group_max", float("nan")) - drow["support_val_to_eval_nearest_max"]
        distance_rows.append(drow)

    write_csv(OUT / "contract_v2_candidates.csv", candidate_rows)
    write_csv(OUT / "contract_v2_support_train_indices.csv", train_rows)
    write_csv(OUT / "contract_v2_support_val_indices.csv", val_rows)
    write_csv(OUT / "contract_v2_attack_eval_indices.csv", eval_rows)
    write_csv(OUT / "contract_v2_coverage_report.csv", coverage_rows)
    write_csv(OUT / "contract_v2_distance_report.csv", distance_rows)

    best = sorted(distance_rows, key=lambda r: (float(r["support_val_to_eval_nearest_p95"]), float(r["support_train_to_eval_nearest_p95"])))[0]
    best_candidate = best["contract_id"]
    best_meta = next(r for r in candidate_rows if r["contract_id"] == best_candidate)
    if not fields_ok:
        primary_verdict = "contract_v2_blocked_by_missing_taxonomy_fields"
    elif float(best_meta["file_coverage_train_val_vs_eval"]) >= 1.0 and float(best_meta["phase_coverage_train_val_vs_eval"]) >= 1.0 and float(best["support_val_p95_improvement_vs_old_support_val"]) > 0:
        primary_verdict = "contract_v2_ready_for_medium_detection_retest"
    elif float(best["support_val_p95_improvement_vs_old_support_val"]) > 0 or float(best["support_train_p95_improvement_vs_old_strat64"]) > 0:
        primary_verdict = "contract_v2_partial_ready_missing_some_attack_regions"
    else:
        primary_verdict = "contract_v2_failed_support_eval_mismatch_persists"

    write_md(OUT / "contract_v2_vs_old_comparison.md", [
        "# Contract V2 vs Old Comparison",
        "",
        f"- best_contract_by_support_val_p95: `{best_candidate}`",
        f"- old support_val_union max group p95: {old.get('old_support_val_union_max_group_p95', float('nan')):.6f}",
        f"- old support_val_union max group max: {old.get('old_support_val_union_max_group_max', float('nan')):.6f}",
        f"- v2 support_val_to_eval p95: {float(best['support_val_to_eval_nearest_p95']):.6f}",
        f"- v2 support_val_to_eval max: {float(best['support_val_to_eval_nearest_max']):.6f}",
        f"- v2 support_train_to_eval p95: {float(best['support_train_to_eval_nearest_p95']):.6f}",
        f"- v2 support_train_to_eval max: {float(best['support_train_to_eval_nearest_max']):.6f}",
        "",
        "Important caveat: this consumes the previous medium attack_eval rows for diagnostic contract design. Any later detection retest on this v2 contract remains medium diagnostic only and cannot be treated as formal evaluation.",
    ])

    role_access = [
        {"artifact": "contract_v2_candidates", "uses_id_benign_train": False, "uses_ood_benign_val": False, "uses_final_ood_benign_eval": False, "uses_old_attack_eval": True, "uses_model_results": False, "purpose": "diagnostic_attack_contract_design"},
        {"artifact": "support_selection", "uses_id_benign_train": False, "uses_ood_benign_val": False, "uses_final_ood_benign_eval": False, "uses_old_attack_eval": True, "uses_model_results": False, "purpose": "stratified_kcenter_on_attack_contract_pool"},
        {"artifact": "distance_validation", "uses_id_benign_train": False, "uses_ood_benign_val": False, "uses_final_ood_benign_eval": False, "uses_old_attack_eval": True, "uses_model_results": False, "purpose": "contract_only_coverage_audit"},
    ]
    write_csv(OUT / "role_access_audit.csv", role_access)
    write_md(OUT / "issue27ao_decision.md", [
        "# Issue27ao Decision",
        "",
        f"- primary_verdict: `{primary_verdict}`",
        "- Scope: support/eval contract repair validation only; no model training and no full/larger benchmark.",
        "- Benign ID/OOD/final OOD split unchanged.",
        "- Gotham Kitsune115 115D frontend unchanged.",
        "- The previous medium attack_eval is used only as diagnostic contract-design material; it is not formal report-only evaluation after this point.",
        f"- best_contract: `{best_candidate}`",
        f"- support_val_to_eval_p95: {float(best['support_val_to_eval_nearest_p95']):.6f}",
        f"- support_val_to_eval_max: {float(best['support_val_to_eval_nearest_max']):.6f}",
        f"- support_train_to_eval_p95: {float(best['support_train_to_eval_nearest_p95']):.6f}",
        f"- support_train_to_eval_max: {float(best['support_train_to_eval_nearest_max']):.6f}",
    ])
    next_action = "issue27ap_medium_detection_retest_on_contract_v2_diagnostic_only" if primary_verdict in {"contract_v2_ready_for_medium_detection_retest", "contract_v2_partial_ready_missing_some_attack_regions"} else "issue27ap_review_gotham_attack_contract_boundary"
    write_md(OUT / "issue27ap_next_action.md", [
        "# Issue27ap Next Action",
        "",
        f"- recommended_next_issue: `{next_action}`",
        "- If retesting detection, keep it explicitly medium diagnostic and use the frozen v2 indices from this issue.",
        "- Do not compare v2 retest as formal performance because old attack_eval was consumed for contract design.",
        "- Formal benchmark still requires larger/full held-out attack files or a newly frozen evaluation contract.",
    ])
    write_md(OUT / "summary.md", [
        "# Issue27ao Summary",
        "",
        "1. issue27ao completed: yes",
        f"2. primary_verdict: `{primary_verdict}`",
        "3. no model training: yes",
        "4. full/larger benchmark run: no",
        "5. 115D frontend changed: no",
        "6. benign ID/OOD/final OOD split changed: no",
        "7. final_ood_benign_eval used: false",
        "8. old attack_eval consumed for diagnostic contract design: true",
        f"9. best contract: `{best_candidate}`",
        f"10. support_train size: {best_meta['support_train_size']}",
        f"11. support_val size: {best_meta['support_val_size']}",
        f"12. v2 attack_eval size: {best_meta['attack_eval_size']}",
        f"13. file coverage train/val vs eval: {float(best_meta['file_coverage_train_val_vs_eval']):.6f}",
        f"14. phase coverage train/val vs eval: {float(best_meta['phase_coverage_train_val_vs_eval']):.6f}",
        f"15. support_val p95 improvement vs old: {float(best['support_val_p95_improvement_vs_old_support_val']):.6f}",
        f"16. support_train p95 improvement vs old: {float(best['support_train_p95_improvement_vs_old_strat64']):.6f}",
        f"17. next action: `{next_action}`",
        "18. commit hash: pending",
    ])
    write_md(OUT / "claim_update_after_issue27ao.md", [
        "# Claim Update After Issue27ao",
        "",
        "- Issue27ao repairs only the diagnostic attack support/eval contract.",
        "- It does not provide model performance evidence.",
        "- Any follow-up detection retest on v2 remains medium diagnostic because the previous attack_eval distribution was used for contract design.",
    ])
    write_md(OUT / "command.txt", ["python repo/ood/issue27ao_repair_support_eval_contract_v2_before_head_repair.py"])
    (OUT / "config.json").write_text(json.dumps({
        "issue": ISSUE,
        "strategy": PRIMARY_STRATEGY,
        "support_train_size": SUPPORT_TRAIN_SIZE,
        "support_val_size": SUPPORT_VAL_SIZE,
        "candidate_contracts": candidates,
        "no_model_training": True,
        "old_attack_eval_consumed_for_contract_design": True,
    }, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(json.dumps({
        "inputs": {
            "issue27af_certificate": str(asset["cert_path"]),
            "issue27an_coverage": str(ISSUE27AN / "support_eval_coverage_audit.csv"),
        },
        "outputs": [p.name for p in sorted(OUT.glob("*"))],
    }, indent=2, sort_keys=True), encoding="utf-8")
    manifest_rows = []
    for p in sorted(OUT.glob("*")):
        if p.is_file():
            manifest_rows.append({"path": str(p.relative_to(ROOT)), "sha256": sha256(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)

    append_doc(MAINLINE_DOCS / "mainline_handoff.md", "<!-- issue27ao -->", [
        "<!-- issue27ao -->",
        "## issue27ao_repair_support_eval_contract_v2_before_head_repair_2026-06-03",
        "",
        f"- primary_verdict: `{primary_verdict}`",
        "- Support/eval contract v2 validation only; no model training.",
        "- Benign split and Kitsune115 frontend unchanged.",
        "- Previous medium attack_eval is consumed for diagnostic contract design, so follow-up retest remains diagnostic only.",
        f"- next action: `{next_action}`",
    ])
    append_doc(MAINLINE_DOCS / "mainline_experiment_map.md", "<!-- issue27ao -->", [
        "<!-- issue27ao -->",
        "## issue27ao",
        "",
        f"- verdict: `{primary_verdict}`",
        "- route: Gotham Kitsune115 medium support/eval contract v2 validation.",
        "- claim boundary: contract-only diagnostic; no model performance claim.",
    ])


if __name__ == "__main__":
    main()
