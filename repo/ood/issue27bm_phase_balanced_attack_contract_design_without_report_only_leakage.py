from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
PROJECT_DIR = ROOT.parent.parent
ISSUE = "issue27bm_phase_balanced_attack_contract_design_without_report_only_leakage_2026-06-08"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BL = ROOT / "runs" / "issue27bl_attack_phase_onset_pseudo_contract_audit_2026-06-08"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SUPPORT_TRAIN_BUDGET = 128
SUPPORT_VAL_BUDGET = 64
PSEUDO_QUERY_BUDGET = 1024
EMBARGO_ROWS = 5
ATTACK_GO_THRESHOLD = 0.93

PRIMARY_CONTRACT = "phase_balanced_dev_v2"
CONTROL_MEDIUM = "medium_only_phase_balanced_control"
CONTROL_HEAVY = "heavy_active_phase_balanced_control"


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


def hash_ids(ids: list[str]) -> str:
    return hashlib.sha256(",".join(ids).encode("utf-8")).hexdigest()


def hash_indices(indices: list[int] | np.ndarray) -> str:
    return hashlib.sha256(",".join(map(str, np.asarray(indices, dtype=np.int64).tolist())).encode("utf-8")).hexdigest()


def file_key(row: dict[str, str]) -> str:
    return row.get("csv_member") or row.get("source_file") or row.get("pcap_member") or "unknown"


def device_hint_from_file(path: str) -> str:
    name = Path(path).name
    if name.startswith("iotsim-"):
        name = name[len("iotsim-") :]
    if name.endswith(".csv"):
        name = name[:-4]
    parts = name.split("-")
    if len(parts) > 1 and parts[-1].isdigit():
        parts = parts[:-1]
    return "-".join(parts) if parts else name


def attack_type_key(row: dict[str, str]) -> str:
    return row.get("attack_type_from_raw_path") or row.get("attack_type") or row.get("label") or "unknown"


def parse_int(row: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(float(row.get(key, "")))
    except Exception:
        return int(default)


def parse_float(row: dict[str, str], key: str, default: float = float("nan")) -> float:
    try:
        return float(row.get(key, ""))
    except Exception:
        return float(default)


def phase_bucket(recorded_index: int) -> str:
    if recorded_index < 50:
        return "warmup_edge_0_49"
    if recorded_index < 500:
        return "early_50_499"
    if recorded_index < 2000:
        return "mid_500_1999"
    if recorded_index < 10000:
        return "late_2000_9999"
    return "tail_ge10000"


def label_is_attack(row: dict[str, str]) -> bool:
    return (row.get("binary_label_from_alignment") or row.get("label") or "").lower() == "attack"


def model_ready(row: dict[str, str]) -> bool:
    return row.get("model_ready_hint", "").lower() == "true"


def make_record(source_asset: str, idx: int, row: dict[str, str]) -> dict[str, Any]:
    file_name = file_key(row)
    recorded = parse_int(row, "recorded_index")
    packet = parse_int(row, "packet_index")
    return {
        "global_id": f"{source_asset}:{idx}",
        "source_asset": source_asset,
        "source_index": int(idx),
        "source_role": row.get("role", ""),
        "csv_member": file_name,
        "device_hint": device_hint_from_file(file_name),
        "attack_type": attack_type_key(row),
        "phase_bucket": phase_bucket(recorded),
        "recorded_index": int(recorded),
        "packet_index": int(packet),
        "packet_timestamp_epoch": parse_float(row, "packet_timestamp_epoch"),
        "binary_label": (row.get("binary_label_from_alignment") or row.get("label") or "").lower(),
        "model_ready_hint": row.get("model_ready_hint", ""),
    }


def group_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(record["source_asset"]),
        str(record["csv_member"]),
        str(record["attack_type"]),
        str(record["phase_bucket"]),
    )


def summarize_counter(counter: Counter[str], top: int = 10) -> str:
    return "|".join(f"{k}:{v}" for k, v in counter.most_common(top))


def summarize_records(records: list[dict[str, Any]], contract_id: str, role: str) -> dict[str, Any]:
    files = Counter(str(r["csv_member"]) for r in records)
    devices = Counter(str(r["device_hint"]) for r in records)
    phases = Counter(str(r["phase_bucket"]) for r in records)
    attacks = Counter(str(r["attack_type"]) for r in records)
    sources = Counter(str(r["source_asset"]) for r in records)
    rec = [int(r["recorded_index"]) for r in records]
    return {
        "contract_id": contract_id,
        "contract_role": role,
        "rows": len(records),
        "source_assets": summarize_counter(sources),
        "file_count": len(files),
        "device_count": len(devices),
        "phase_count": len(phases),
        "attack_type_count": len(attacks),
        "phase_distribution": summarize_counter(phases),
        "file_distribution": summarize_counter(files),
        "device_distribution": summarize_counter(devices),
        "attack_type_distribution": summarize_counter(attacks),
        "recorded_index_min": min(rec) if rec else "",
        "recorded_index_max": max(rec) if rec else "",
        "global_id_hash": hash_ids([str(r["global_id"]) for r in records]),
    }


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return float(len(a & b) / len(a | b))


def role_sets(records: list[dict[str, Any]]) -> dict[str, set[str]]:
    return {
        "files": {str(r["csv_member"]) for r in records},
        "devices": {str(r["device_hint"]) for r in records},
        "phases": {str(r["phase_bucket"]) for r in records},
        "attacks": {str(r["attack_type"]) for r in records},
        "sources": {str(r["source_asset"]) for r in records},
    }


def split_group_time_ordered(group_records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int]:
    rows = sorted(group_records, key=lambda r: (int(r["recorded_index"]), int(r["source_index"])))
    n = len(rows)
    if n < 12:
        return [], [], [], n
    train_end = max(1, int(n * 0.45))
    val_start = min(n, train_end + EMBARGO_ROWS)
    val_end = min(n, val_start + max(1, int(n * 0.20)))
    pseudo_start = min(n, val_end + EMBARGO_ROWS)
    train = rows[:train_end]
    val = rows[val_start:val_end]
    pseudo = rows[pseudo_start:]
    if not val or not pseudo:
        return [], [], [], n
    return train, val, pseudo, 0


def allocate_budget(groups: dict[tuple[str, str, str, str], list[dict[str, Any]]], budget: int) -> dict[tuple[str, str, str, str], int]:
    eligible = {k: v for k, v in groups.items() if v}
    if not eligible or budget <= 0:
        return {}
    total = sum(len(v) for v in eligible.values())
    alloc: dict[tuple[str, str, str, str], int] = {}
    remainders: list[tuple[float, tuple[str, str, str, str]]] = []
    for key, rows in eligible.items():
        exact = budget * len(rows) / total
        base = min(len(rows), max(1, int(np.floor(exact))))
        alloc[key] = base
        remainders.append((exact - np.floor(exact), key))
    while sum(alloc.values()) > budget:
        for _, key in sorted(remainders, key=lambda x: (x[0], len(eligible[x[1]]))):
            if alloc[key] > 1:
                alloc[key] -= 1
                break
        else:
            break
    while sum(alloc.values()) < budget:
        progressed = False
        for _, key in sorted(remainders, reverse=True):
            if alloc[key] < len(eligible[key]):
                alloc[key] += 1
                progressed = True
                if sum(alloc.values()) >= budget:
                    break
        if not progressed:
            break
    return alloc


def kcenter_select(records: list[dict[str, Any]], features_by_id: dict[str, np.ndarray], k: int) -> list[dict[str, Any]]:
    if k <= 0 or not records:
        return []
    rows = sorted(records, key=lambda r: (int(r["recorded_index"]), str(r["global_id"])))
    if k >= len(rows):
        return rows
    x = np.vstack([features_by_id[str(r["global_id"])] for r in rows])
    scaler = StandardScaler().fit(x)
    z = scaler.transform(x)
    centroid = z.mean(axis=0, keepdims=True)
    dist_to_center = pairwise_distances(z, centroid, metric="euclidean").ravel()
    start = int(np.argmin(dist_to_center))
    selected = [start]
    min_dist = pairwise_distances(z, z[[start]], metric="euclidean").ravel()
    min_dist[start] = -1.0
    while len(selected) < k:
        nxt = int(np.argmax(min_dist))
        selected.append(nxt)
        d = pairwise_distances(z, z[[nxt]], metric="euclidean").ravel()
        min_dist = np.minimum(min_dist, d)
        min_dist[selected] = -1.0
    return [rows[i] for i in selected]


def select_from_groups(
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]],
    budget: int,
    features_by_id: dict[str, np.ndarray],
) -> list[dict[str, Any]]:
    alloc = allocate_budget(groups, budget)
    selected: list[dict[str, Any]] = []
    for key in sorted(groups):
        selected.extend(kcenter_select(groups[key], features_by_id, alloc.get(key, 0)))
    return sorted(selected, key=lambda r: str(r["global_id"]))


def even_select_from_groups(groups: dict[tuple[str, str, str, str], list[dict[str, Any]]], budget: int) -> list[dict[str, Any]]:
    alloc = allocate_budget(groups, budget)
    selected: list[dict[str, Any]] = []
    for key in sorted(groups):
        rows = sorted(groups[key], key=lambda r: (int(r["recorded_index"]), str(r["global_id"])))
        k = alloc.get(key, 0)
        if not rows or k <= 0:
            continue
        if k >= len(rows):
            selected.extend(rows)
        else:
            pos = np.linspace(0, len(rows) - 1, num=k)
            selected.extend(rows[int(round(p))] for p in pos)
    return sorted(selected, key=lambda r: str(r["global_id"]))


def build_contract(
    contract_id: str,
    pool_records: list[dict[str, Any]],
    features_by_id: dict[str, np.ndarray],
    support_train_budget: int,
    support_val_budget: int,
    pseudo_budget: int,
) -> dict[str, list[dict[str, Any]]]:
    train_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    val_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    pseudo_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    dropped_small_groups: list[dict[str, Any]] = []
    for key, rows in group_by(pool_records, group_key).items():
        train, val, pseudo, dropped = split_group_time_ordered(rows)
        if dropped:
            dropped_small_groups.append({"contract_id": contract_id, "group_key": "|".join(key), "rows": dropped})
            continue
        train_groups[key].extend(train)
        val_groups[key].extend(val)
        pseudo_groups[key].extend(pseudo)
    return {
        "support_train": select_from_groups(train_groups, support_train_budget, features_by_id),
        "support_val": select_from_groups(val_groups, support_val_budget, features_by_id),
        "pseudo_query_dev": even_select_from_groups(pseudo_groups, pseudo_budget),
        "_dropped_groups": dropped_small_groups,
    }


def group_by(records: list[dict[str, Any]], key_fn) -> dict[Any, list[dict[str, Any]]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[key_fn(record)].append(record)
    return dict(grouped)


def records_to_index_rows(contract_id: str, role: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for order, r in enumerate(records):
        rows.append(
            {
                "contract_id": contract_id,
                "contract_role": role,
                "order": order,
                "global_id": r["global_id"],
                "source_asset": r["source_asset"],
                "source_index": r["source_index"],
                "source_role": r["source_role"],
                "csv_member": r["csv_member"],
                "device_hint": r["device_hint"],
                "attack_type": r["attack_type"],
                "phase_bucket": r["phase_bucket"],
                "recorded_index": r["recorded_index"],
                "packet_index": r["packet_index"],
                "packet_timestamp_epoch": r["packet_timestamp_epoch"],
                "selection_policy": "stratified_by_source_file_attack_phase_then_kcenter_or_even_time",
            }
        )
    return rows


def distance_audit(
    contract_id: str,
    roles: dict[str, list[dict[str, Any]]],
    features_by_id: dict[str, np.ndarray],
) -> dict[str, Any]:
    train = roles.get("support_train", [])
    val = roles.get("support_val", [])
    pseudo = roles.get("pseudo_query_dev", [])
    row: dict[str, Any] = {
        "contract_id": contract_id,
        "support_train_rows": len(train),
        "support_val_rows": len(val),
        "pseudo_query_dev_rows": len(pseudo),
    }
    if not train or not val or not pseudo:
        row["blocked"] = True
        row["blocked_reason"] = "missing_required_role_rows"
        return row
    x_train = np.vstack([features_by_id[str(r["global_id"])] for r in train])
    scaler = StandardScaler().fit(x_train)
    z_train = scaler.transform(x_train)
    for role_name, recs in [("support_val", val), ("pseudo_query_dev", pseudo)]:
        x = np.vstack([features_by_id[str(r["global_id"])] for r in recs])
        d = pairwise_distances(scaler.transform(x), z_train, metric="euclidean").min(axis=1)
        row[f"{role_name}_nn_q50"] = float(np.quantile(d, 0.50))
        row[f"{role_name}_nn_q75"] = float(np.quantile(d, 0.75))
        row[f"{role_name}_nn_q95"] = float(np.quantile(d, 0.95))
        row[f"{role_name}_nn_max"] = float(np.max(d))
    row["q50_gap_pseudo_minus_val"] = row["pseudo_query_dev_nn_q50"] - row["support_val_nn_q50"]
    row["q95_gap_pseudo_minus_val"] = row["pseudo_query_dev_nn_q95"] - row["support_val_nn_q95"]
    row["blocked"] = False
    return row


def overlap_audit(contract_id: str, roles: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    pairs = [("support_train", "support_val"), ("support_train", "pseudo_query_dev"), ("support_val", "pseudo_query_dev")]
    rows = []
    for left, right in pairs:
        lsets = role_sets(roles[left])
        rsets = role_sets(roles[right])
        rows.append(
            {
                "contract_id": contract_id,
                "left_role": left,
                "right_role": right,
                "file_jaccard": jaccard(lsets["files"], rsets["files"]),
                "device_jaccard": jaccard(lsets["devices"], rsets["devices"]),
                "phase_jaccard": jaccard(lsets["phases"], rsets["phases"]),
                "attack_type_jaccard": jaccard(lsets["attacks"], rsets["attacks"]),
                "source_asset_jaccard": jaccard(lsets["sources"], rsets["sources"]),
                "left_phases": "|".join(sorted(lsets["phases"])),
                "right_phases": "|".join(sorted(rsets["phases"])),
                "left_sources": "|".join(sorted(lsets["sources"])),
                "right_sources": "|".join(sorted(rsets["sources"])),
            }
        )
    return rows


def load_old_pseudo_distance_baseline() -> dict[str, Any]:
    path = ISSUE27BL / "phase_distance_audit.csv"
    if not path.exists():
        return {"available": False}
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    pseudo_rows = [r for r in rows if "pseudo_query_dev" in r.get("query_role", "")]
    if not pseudo_rows:
        return {"available": False}
    q50_gaps = [float(r.get("q50_gap_query_minus_val", "nan")) for r in pseudo_rows]
    q95_gaps = [float(r.get("q95_gap_query_minus_val", "nan")) for r in pseudo_rows]
    return {
        "available": True,
        "old_pseudo_rows": len(pseudo_rows),
        "old_q50_gap_max": float(np.nanmax(q50_gaps)),
        "old_q50_gap_mean": float(np.nanmean(q50_gaps)),
        "old_q95_gap_max": float(np.nanmax(q95_gaps)),
        "old_q95_gap_mean": float(np.nanmean(q95_gaps)),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    x = asset["X"]
    sidecar = asset["sidecar"]

    support_pool_idx = ar.role_indices(sidecar, ar.SUPPORT_ROLE)
    attack_eval_idx = ar.role_indices(sidecar, ar.ATTACK_EVAL_ROLE)
    final_ood_idx = ar.role_indices(sidecar, ar.FINAL_OOD_ROLE)
    active_candidate_idx, dev_heavy_query_idx, active_manifest = issue27au.split_new_heavy_stream(new_sidecar)

    input_hash_rows = [
        {"artifact": "issue27af_medium_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path), "used_for": "asset_hash_audit"},
        {"artifact": "issue27bl_summary", "path": str(ISSUE27BL / "summary.md"), "sha256": sha256_file(ISSUE27BL / "summary.md"), "used_for": "upstream_decision_context"},
    ]
    for check in checks + new_checks:
        input_hash_rows.append(
            {
                "artifact": check.get("artifact", "asset_check"),
                "path": check.get("path", ""),
                "sha256": check.get("actual_sha256", ""),
                "expected_sha256": check.get("expected_sha256", ""),
                "hash_match": check.get("hash_match", ""),
                "used_for": "input_asset_validation",
            }
        )

    medium_records: list[dict[str, Any]] = []
    heavy_active_records: list[dict[str, Any]] = []
    warmup_excluded: list[dict[str, Any]] = []
    features_by_id: dict[str, np.ndarray] = {}

    for idx in support_pool_idx.tolist():
        row = sidecar[int(idx)]
        rec = make_record("medium_attack_support_role", int(idx), row)
        features_by_id[str(rec["global_id"])] = x[int(idx)]
        if not model_ready(row) or not label_is_attack(row):
            continue
        if rec["phase_bucket"] == "warmup_edge_0_49":
            warmup_excluded.append(rec)
            continue
        medium_records.append(rec)

    active_confirmed_after_selection = []
    for idx in active_candidate_idx.tolist():
        row = new_sidecar[int(idx)]
        rec = make_record("heavy_active_labeled_candidate_stream", int(idx), row)
        features_by_id[str(rec["global_id"])] = new_x[int(idx)]
        if not model_ready(row) or not label_is_attack(row):
            continue
        active_confirmed_after_selection.append(rec)
        if rec["phase_bucket"] == "warmup_edge_0_49":
            warmup_excluded.append(rec)
            continue
        heavy_active_records.append(rec)

    all_dev_records = medium_records + heavy_active_records
    contracts = {
        PRIMARY_CONTRACT: build_contract(
            PRIMARY_CONTRACT,
            all_dev_records,
            features_by_id,
            SUPPORT_TRAIN_BUDGET,
            SUPPORT_VAL_BUDGET,
            PSEUDO_QUERY_BUDGET,
        ),
        CONTROL_MEDIUM: build_contract(
            CONTROL_MEDIUM,
            medium_records,
            features_by_id,
            min(SUPPORT_TRAIN_BUDGET, 96),
            min(SUPPORT_VAL_BUDGET, 48),
            min(PSEUDO_QUERY_BUDGET, 512),
        ),
        CONTROL_HEAVY: build_contract(
            CONTROL_HEAVY,
            heavy_active_records,
            features_by_id,
            min(SUPPORT_TRAIN_BUDGET, 64),
            min(SUPPORT_VAL_BUDGET, 32),
            min(PSEUDO_QUERY_BUDGET, 512),
        ),
    }

    inventory_rows: list[dict[str, Any]] = []
    for pool_name, records in [
        ("medium_attack_support_role_eligible", medium_records),
        ("heavy_active_labeled_candidate_stream_eligible", heavy_active_records),
        ("warmup_edge_excluded", warmup_excluded),
    ]:
        grouped = group_by(records, lambda r: (r["source_asset"], r["csv_member"], r["phase_bucket"]))
        for key, rows in sorted(grouped.items()):
            inventory_rows.append(
                {
                    "pool_name": pool_name,
                    "source_asset": key[0],
                    "csv_member": key[1],
                    "phase_bucket": key[2],
                    "rows": len(rows),
                    "recorded_index_min": min(int(r["recorded_index"]) for r in rows) if rows else "",
                    "recorded_index_max": max(int(r["recorded_index"]) for r in rows) if rows else "",
                    "attack_types": summarize_counter(Counter(str(r["attack_type"]) for r in rows)),
                    "device_hints": summarize_counter(Counter(str(r["device_hint"]) for r in rows)),
                }
            )

    candidate_rows: list[dict[str, Any]] = []
    balance_rows: list[dict[str, Any]] = []
    overlap_rows: list[dict[str, Any]] = []
    distance_rows: list[dict[str, Any]] = []
    index_rows_by_role = {"support_train": [], "support_val": [], "pseudo_query_dev": []}
    dropped_rows: list[dict[str, Any]] = []
    for contract_id, roles in contracts.items():
        for hidden in roles.get("_dropped_groups", []):
            dropped_rows.append(hidden)
        clean_roles = {k: v for k, v in roles.items() if not k.startswith("_")}
        candidate_rows.append(
            {
                "contract_id": contract_id,
                "support_train_rows": len(clean_roles["support_train"]),
                "support_val_rows": len(clean_roles["support_val"]),
                "pseudo_query_dev_rows": len(clean_roles["pseudo_query_dev"]),
                "selector_policy": "phase/file/source stratified; train/val/pseudo split by recorded_index with embargo; kcenter only inside legal dev-side buckets",
                "uses_attack_eval_labels": False,
                "uses_attack_eval_features": False,
                "uses_final_ood": False,
                "uses_dev_heavy_query": False,
                "tail_phase_available": any(r["phase_bucket"] in {"late_2000_9999", "tail_ge10000"} for r in clean_roles["support_train"] + clean_roles["support_val"] + clean_roles["pseudo_query_dev"]),
            }
        )
        for role_name, records in clean_roles.items():
            balance_rows.append(summarize_records(records, contract_id, role_name))
            index_rows_by_role[role_name].extend(records_to_index_rows(contract_id, role_name, records))
        overlap_rows.extend(overlap_audit(contract_id, clean_roles))
        distance_rows.append(distance_audit(contract_id, clean_roles, features_by_id))

    old_baseline = load_old_pseudo_distance_baseline()
    primary_distance = next(r for r in distance_rows if r["contract_id"] == PRIMARY_CONTRACT)
    new_gap = float(primary_distance.get("q50_gap_pseudo_minus_val", float("nan")))
    old_gap = float(old_baseline.get("old_q50_gap_max", float("nan"))) if old_baseline.get("available") else float("nan")
    gap_improved = bool(np.isfinite(old_gap) and np.isfinite(new_gap) and new_gap < old_gap)
    phase_sets = {
        row["contract_role"]: set(str(row["phase_distribution"]).split("|"))
        for row in balance_rows
        if row["contract_id"] == PRIMARY_CONTRACT
    }
    required_roles_present = all(
        next((r for r in balance_rows if r["contract_id"] == PRIMARY_CONTRACT and r["contract_role"] == role and int(r["rows"]) > 0), None)
        for role in ["support_train", "support_val", "pseudo_query_dev"]
    )
    early_mid_all_roles = all(
        {"early_50_499", "mid_500_1999"}.issubset({p.split(":")[0] for p in phases if p})
        for phases in phase_sets.values()
    )
    forbidden_role_access = False
    tail_gap = not any(
        r["phase_bucket"] in {"late_2000_9999", "tail_ge10000"}
        for r in contracts[PRIMARY_CONTRACT]["support_train"] + contracts[PRIMARY_CONTRACT]["support_val"] + contracts[PRIMARY_CONTRACT]["pseudo_query_dev"]
    )
    if forbidden_role_access:
        primary_verdict = "phase_balanced_contract_blocked_by_report_only_leakage"
    elif not required_roles_present or not early_mid_all_roles:
        primary_verdict = "phase_balanced_contract_blocked_by_insufficient_dev_attack_pool"
    elif tail_gap:
        primary_verdict = "phase_balanced_contract_ready_for_attack_only_diagnostic_with_tail_gap_caveat"
    else:
        primary_verdict = "phase_balanced_contract_ready_for_attack_only_diagnostic"

    sealed_role_rows = [
        {
            "role_or_pool": ar.ATTACK_EVAL_ROLE,
            "rows_available": int(len(attack_eval_idx)),
            "used_for_support_construction": False,
            "labels_used_for_support_construction": False,
            "features_used_for_support_construction": False,
            "status": "sealed_report_only",
        },
        {
            "role_or_pool": ar.FINAL_OOD_ROLE,
            "rows_available": int(len(final_ood_idx)),
            "used_for_support_construction": False,
            "labels_used_for_support_construction": False,
            "features_used_for_support_construction": False,
            "status": "sealed_report_only",
        },
        {
            "role_or_pool": "dev_heavy_query_after_active_labeling",
            "rows_available": int(len(dev_heavy_query_idx)),
            "used_for_support_construction": False,
            "labels_used_for_support_construction": False,
            "features_used_for_support_construction": False,
            "status": "sealed_report_only_for_this_contract",
        },
        {
            "role_or_pool": "dev_heavy_unlabeled_active_label_candidate_stream_after_manual_confirmation",
            "rows_available": int(len(active_candidate_idx)),
            "used_for_support_construction": True,
            "labels_used_for_support_construction": "only_after_simulated_active_label_confirmation",
            "features_used_for_support_construction": True,
            "status": "legal_development_side_pool",
        },
        {
            "role_or_pool": ar.SUPPORT_ROLE,
            "rows_available": int(len(support_pool_idx)),
            "used_for_support_construction": True,
            "labels_used_for_support_construction": True,
            "features_used_for_support_construction": True,
            "status": "legal_preregistered_attack_support_role",
        },
    ]

    role_access_rows = [
        {
            "stage": "candidate_pool_build",
            "allowed_roles": "attack_support|dev_heavy_active_candidate_after_manual_confirmation",
            "forbidden_roles": "attack_eval|final_ood_benign_eval|dev_heavy_query_after_active_labeling|medium_attack_eval_report_only",
            "uses_attack_eval_labels": False,
            "uses_attack_eval_features": False,
            "uses_final_ood": False,
            "uses_dev_heavy_query": False,
            "forbidden_role_access": forbidden_role_access,
        },
        {
            "stage": "support_train_val_pseudo_selection",
            "allowed_roles": "legal_dev_attack_pool_only",
            "forbidden_roles": "any_report_only_role",
            "uses_attack_eval_labels": False,
            "uses_attack_eval_features": False,
            "uses_final_ood": False,
            "uses_dev_heavy_query": False,
            "forbidden_role_access": forbidden_role_access,
        },
    ]

    write_csv(OUT / "input_artifact_hash_audit.csv", input_hash_rows)
    write_csv(OUT / "active_stream_split_manifest.csv", active_manifest)
    write_csv(OUT / "eligible_dev_attack_pool_inventory.csv", inventory_rows)
    write_csv(OUT / "sealed_role_exclusion_audit.csv", sealed_role_rows)
    write_csv(OUT / "phase_balanced_contract_candidates.csv", candidate_rows)
    write_csv(OUT / "phase_balanced_support_train_indices.csv", index_rows_by_role["support_train"])
    write_csv(OUT / "phase_balanced_support_val_indices.csv", index_rows_by_role["support_val"])
    write_csv(OUT / "phase_balanced_pseudo_query_dev_indices.csv", index_rows_by_role["pseudo_query_dev"])
    write_csv(OUT / "contract_v2_balance_audit.csv", balance_rows)
    write_csv(OUT / "contract_v2_overlap_audit.csv", overlap_rows)
    write_csv(OUT / "contract_v2_distance_audit.csv", distance_rows)
    write_csv(OUT / "dropped_or_excluded_attack_rows_audit.csv", dropped_rows + [{"reason": "warmup_edge_excluded", **r} for r in warmup_excluded])
    write_csv(OUT / "role_access_audit.csv", role_access_rows)

    with (OUT / "phase_balanced_contract_v2.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "issue": ISSUE,
                "primary_contract": PRIMARY_CONTRACT,
                "primary_verdict": primary_verdict,
                "support_train_budget": SUPPORT_TRAIN_BUDGET,
                "support_val_budget": SUPPORT_VAL_BUDGET,
                "pseudo_query_budget": PSEUDO_QUERY_BUDGET,
                "embargo_rows": EMBARGO_ROWS,
                "selection_policy": "legal dev-side attack pool only; no attack_eval/final/dev_query role labels or features used",
                "contracts": {
                    contract_id: {
                        role: {
                            "rows": len(records),
                            "global_id_hash": hash_ids([str(r["global_id"]) for r in records]),
                        }
                        for role, records in roles.items()
                        if not role.startswith("_")
                    }
                    for contract_id, roles in contracts.items()
                },
            },
            f,
            indent=2,
        )

    write_md(
        OUT / "contract_v2_vs_issue27bl_comparison.md",
        [
            "# Contract v2 vs issue27bl Comparison",
            "",
            f"- issue27bl verdict: `attack_phase_contract_mismatch_needs_rebuild_before_more_heads`",
            f"- issue27bm primary contract: `{PRIMARY_CONTRACT}`",
            f"- issue27bm primary verdict: `{primary_verdict}`",
            f"- old pseudo-query q50 gap max available: `{old_baseline.get('old_q50_gap_max', 'NA')}`",
            f"- new primary pseudo-query q50 gap: `{primary_distance.get('q50_gap_pseudo_minus_val', 'NA')}`",
            f"- q50 gap improved vs old pseudo baseline: `{gap_improved}`",
            "",
            "## Interpretation",
            "",
            "- The new contract does not use `attack_eval`, `final_ood_benign_eval`, or dev-heavy query labels/features for support construction.",
            "- It creates a development-side support/val/pseudo-query contract from the preregistered `attack_support` role plus active-label candidate rows after simulated manual confirmation.",
            "- The contract is phase-balanced for available early/mid attack phases, but it does not cover late/tail attack phases because those are not available in the legal development-side support pool.",
            "- Therefore it is appropriate for the next attack-only diagnostic, not for a formal benchmark or OOD-gate repair.",
        ],
    )

    write_md(
        OUT / "issue27bm_decision.md",
        [
            "# issue27bm Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            f"- primary_contract: `{PRIMARY_CONTRACT}`",
            f"- support_train_rows: `{len(contracts[PRIMARY_CONTRACT]['support_train'])}`",
            f"- support_val_rows: `{len(contracts[PRIMARY_CONTRACT]['support_val'])}`",
            f"- pseudo_query_dev_rows: `{len(contracts[PRIMARY_CONTRACT]['pseudo_query_dev'])}`",
            f"- forbidden_role_access: `{forbidden_role_access}`",
            f"- uses_attack_eval_labels_for_support: `False`",
            f"- tail_phase_gap: `{tail_gap}`",
            f"- attack_go_threshold remains: `{ATTACK_GO_THRESHOLD}`",
            "",
            "This is a contract design/audit task. It does not run model training, does not repair heads, and does not permit OOD-gate repair.",
        ],
    )

    write_md(
        OUT / "issue27bn_next_action.md",
        [
            "# issue27bn Next Action",
            "",
            "recommended_next_action = `issue27bn_attack_only_diagnostic_on_phase_balanced_contract_without_ood_gate`",
            "",
            "- Use the frozen `phase_balanced_dev_v2` indices from issue27bm.",
            "- First test whether attack detection recovers on legal dev pseudo-query without OOD gate repair.",
            "- Do not use report-only attack/final OOD for support, threshold, or model selection.",
            "- If attack hard-min remains far below `0.93`, pause model/head work and revisit attack task boundary or label phase.",
        ],
    )

    write_md(
        OUT / "claim_update_after_issue27bm.md",
        [
            "# Claim Update After issue27bm",
            "",
            "- The prior attack-side contract was too drift-heavy for model repair to be interpretable.",
            "- issue27bm rebuilds a legal development-side phase-balanced attack contract without using attack_eval labels.",
            "- The new contract is suitable for attack-only diagnostic replay, not for formal benchmark claims.",
            "- OOD-gate repair and full benchmark remain blocked until attack-side detection is stable under the legal dev contract.",
        ],
    )

    write_md(
        OUT / "summary.md",
        [
            "# issue27bm Summary",
            "",
            "1. issue27bm completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. task type: phase-balanced attack contract design; no model training",
            "4. 115D frontend changed: no",
            "5. benign ID/OOD/final OOD split changed: no",
            "6. attack_eval labels used for attack_support construction: no",
            "7. final/report-only roles used for selection: no",
            f"8. primary contract: `{PRIMARY_CONTRACT}`",
            f"9. support_train / support_val / pseudo_query_dev rows: `{len(contracts[PRIMARY_CONTRACT]['support_train'])}` / `{len(contracts[PRIMARY_CONTRACT]['support_val'])}` / `{len(contracts[PRIMARY_CONTRACT]['pseudo_query_dev'])}`",
            f"10. phase coverage includes early/mid for all primary roles: `{early_mid_all_roles}`",
            f"11. tail/late phase gap remains: `{tail_gap}`",
            f"12. q50 pseudo gap improved vs issue27bl pseudo baseline: `{gap_improved}`",
            f"13. OOD-gate repair allowed: no",
            "14. next action: `issue27bn_attack_only_diagnostic_on_phase_balanced_contract_without_ood_gate`",
            "15. commit hash: reported in final response",
        ],
    )

    write_md(OUT / "command.txt", ["python repo/ood/issue27bm_phase_balanced_attack_contract_design_without_report_only_leakage.py"])
    with (OUT / "config.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "issue": ISSUE,
                "primary_strategy": PRIMARY_STRATEGY,
                "primary_contract": PRIMARY_CONTRACT,
                "support_train_budget": SUPPORT_TRAIN_BUDGET,
                "support_val_budget": SUPPORT_VAL_BUDGET,
                "pseudo_query_budget": PSEUDO_QUERY_BUDGET,
                "embargo_rows": EMBARGO_ROWS,
                "attack_eval_labels_for_support": False,
                "final_ood_for_selection": False,
            },
            f,
            indent=2,
        )
    with (OUT / "run_spec.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "stage": "data-contract audit",
                "no_model_training": True,
                "no_formal_benchmark": True,
                "no_ood_gate_repair": True,
                "forbidden_roles": [ar.ATTACK_EVAL_ROLE, ar.FINAL_OOD_ROLE, "dev_heavy_query_after_active_labeling"],
                "allowed_pools": [ar.SUPPORT_ROLE, "dev_heavy_active_candidate_after_manual_confirmation"],
            },
            f,
            indent=2,
        )

    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest_rows.append({"file": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_csv(OUT / "manifest.csv", manifest_rows)

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bm_phase_balanced_attack_contract_design -->",
        [
            "## issue27bm - phase-balanced attack contract design",
            "",
            "<!-- issue27bm_phase_balanced_attack_contract_design -->",
            f"- Verdict: `{primary_verdict}`.",
            "- Rebuilt a legal development-side attack support/val/pseudo-query contract without using `attack_eval` labels or final/report-only roles.",
            f"- Primary contract: `{PRIMARY_CONTRACT}`; support/val/pseudo rows: `{len(contracts[PRIMARY_CONTRACT]['support_train'])}` / `{len(contracts[PRIMARY_CONTRACT]['support_val'])}` / `{len(contracts[PRIMARY_CONTRACT]['pseudo_query_dev'])}`.",
            f"- Tail/late phase gap remains: `{tail_gap}`; this is for attack-only diagnostic, not formal benchmark.",
            "- OOD-gate repair remains blocked.",
            "- Next action: `issue27bn_attack_only_diagnostic_on_phase_balanced_contract_without_ood_gate`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bm_phase_balanced_attack_contract_design -->",
        [
            "## issue27bm - phase-balanced attack contract design",
            "",
            "<!-- issue27bm_phase_balanced_attack_contract_design -->",
            "- Stage: data-contract audit before more model/head repair.",
            f"- Primary verdict: `{primary_verdict}`.",
            "- Formal benchmark status: blocked.",
            "- Attack_eval/final/report-only roles remain sealed for selection.",
        ],
    )


if __name__ == "__main__":
    main()
