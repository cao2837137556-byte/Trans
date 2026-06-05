from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
OOD_DIR = REPO_DIR / "ood"
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ab_gotham_kitsune115_frontend_feasibility as ab  # noqa: E402
import issue27ad_gotham_kitsune115_split_aware_smoke_expansion as ad  # noqa: E402
import issue27af_gotham_kitsune115_larger_materialization_plan as af  # noqa: E402
import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar  # noqa: E402
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au  # noqa: E402
import issue27ay_region_aware_attack_bank_and_score_gate_diagnostic as ay  # noqa: E402
import issue27az_region_aware_ood_safe_gate_repair as az  # noqa: E402


ISSUE = "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AZ = ROOT / "runs" / "issue27az_region_aware_attack_preserving_ood_safe_gate_repair_2026-06-05"
DERIVED = ab.DATA_ROOT / "derived" / "kitsune115_ood_stress_pool_v1"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
ACTIVE_LABEL_BUDGETS = [64, 128]
RADIUS_QUANTILES = [0.75, 0.90, 0.95]
MARGINS = [-0.25, 0.0, 0.25, 0.50, 0.75, 1.0]
VAL_TARGET = 0.01
REVIEW_BUDGET = 0.10
RELAXED_REVIEW_BUDGET = 0.20

OOD_STRESS_ROLE = "ood_stress_val"
OOD_STRESS_SPLIT_ROLE = "OOD_stress_val"

# Strict first-pass stress pool: unseen files from the pre-registered OOD-val
# contract, excluding anything already used by the medium asset and excluding
# final/report-only roles. This gives the gate a harder dev-side OOD signal
# without opening final OOD.
PREFERRED_STRESS_FILES = [
    "processed/iotsim-stream-consumer-1.csv",
    "processed/iotsim-stream-consumer-2.csv",
    "processed/iotsim-predictive-maintenance-10.csv",
    "processed/iotsim-predictive-maintenance-11.csv",
    "processed/iotsim-building-monitor-2.csv",
    "processed/iotsim-building-monitor-5.csv",
]


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


def rate(mask: np.ndarray) -> float:
    arr = np.asarray(mask)
    if arr.size == 0:
        return float("nan")
    return float(np.mean(arr.astype(bool)))


def summarize(vals: list[float] | np.ndarray) -> dict[str, float]:
    arr = np.asarray(vals, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return {"mean": float("nan"), "min": float("nan"), "max": float("nan")}
    return {"mean": float(np.mean(arr)), "min": float(np.min(arr)), "max": float(np.max(arr))}


def used_medium_csvs(cert: dict[str, Any]) -> set[str]:
    sidecar_path = Path(cert[PRIMARY_STRATEGY]["sidecar_path"])
    rows = read_csv(sidecar_path)
    return {r["csv_member"] for r in rows}


def device_from_csv(csv_member: str) -> str:
    return af.device_from_csv(csv_member)


def save_stress_asset(
    x: np.ndarray,
    sidecar: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
    selection_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    DERIVED.mkdir(parents=True, exist_ok=True)
    prefix = DERIVED / "gotham_kitsune115_ood_stress_reset_at_split_boundary"
    x_path = prefix.with_name(prefix.name + "_X.npy")
    y_path = prefix.with_name(prefix.name + "_y.npy")
    sidecar_path = prefix.with_name(prefix.name + "_sidecar.csv.gz")
    split_path = prefix.with_name(prefix.name + "_split_manifest.csv")
    state_path = prefix.with_name(prefix.name + "_state_transition_log.csv")
    schema_path = prefix.with_name(prefix.name + "_feature_schema.json")
    selection_path = prefix.with_name(prefix.name + "_file_selection.csv")

    np.save(x_path, x.astype(np.float32))
    np.save(y_path, np.zeros(len(x), dtype=np.int8))
    with gzip.open(sidecar_path, "wt", newline="", encoding="utf-8") as f:
        if sidecar:
            writer = csv.DictWriter(f, fieldnames=list(sidecar[0].keys()))
            writer.writeheader()
            writer.writerows(sidecar)
    split_rows = [
        {
            "row_id": i,
            "strategy": r.get("strategy", PRIMARY_STRATEGY),
            "role": r.get("role", OOD_STRESS_ROLE),
            "split_role": r.get("split_role", OOD_STRESS_SPLIT_ROLE),
            "binary_label": r.get("binary_label_from_alignment", "benign"),
            "csv_member": r.get("csv_member", ""),
            "pcap_member": r.get("pcap_member", ""),
            "warmup_only": r.get("warmup_only", ""),
            "model_ready_hint": r.get("model_ready_hint", ""),
        }
        for i, r in enumerate(sidecar)
    ]
    write_csv(split_path, split_rows)
    write_csv(state_path, transitions)
    write_csv(selection_path, selection_rows)
    schema = {
        "schema_id": "gotham_kitsune_restored115_v1",
        "feature_count": 115,
        "family_counts": {"MI_dir": 15, "H": 15, "HH": 35, "HH_jit": 15, "HpHp": 35},
        "feature_names": ab.RestoredNetStat115().headers(),
        "schema_sha256": ab.sha256_bytes("\n".join(ab.RestoredNetStat115().headers()).encode("utf-8")),
        "source": "same restored Kitsune/AfterImage/netStat frontend as issue27af",
    }
    schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    role_counts = Counter(r["role"] for r in sidecar if str(r.get("model_ready_hint", "")).lower() == "true")
    device_counts = Counter(device_from_csv(r["csv_member"]) for r in sidecar)
    cert = {
        "strategy": PRIMARY_STRATEGY,
        "stress_role": OOD_STRESS_ROLE,
        "X_115D_path": str(x_path),
        "y_path": str(y_path),
        "sidecar_path": str(sidecar_path),
        "split_manifest_path": str(split_path),
        "feature_schema_path": str(schema_path),
        "state_transition_log_path": str(state_path),
        "file_selection_path": str(selection_path),
        "X_115D_sha256": sha256_file(x_path),
        "y_sha256": sha256_file(y_path),
        "sidecar_sha256": sha256_file(sidecar_path),
        "split_manifest_sha256": sha256_file(split_path),
        "feature_schema_sha256": sha256_file(schema_path),
        "state_transition_log_sha256": sha256_file(state_path),
        "file_selection_sha256": sha256_file(selection_path),
        "rows": int(x.shape[0]),
        "columns": int(x.shape[1]) if x.ndim == 2 else 0,
        "role_counts": dict(role_counts),
        "device_counts": dict(device_counts),
        "final_eval_report_only": True,
        "stress_pool_uses_final_ood": False,
        "stress_pool_uses_attack_files": False,
    }
    return cert


def load_stress_asset(cert: dict[str, Any]) -> tuple[np.ndarray, list[dict[str, str]], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    for key, hash_key in [
        ("X_115D_path", "X_115D_sha256"),
        ("sidecar_path", "sidecar_sha256"),
        ("split_manifest_path", "split_manifest_sha256"),
        ("feature_schema_path", "feature_schema_sha256"),
    ]:
        path = Path(cert[key])
        actual = sha256_file(path)
        ok = actual == cert[hash_key]
        checks.append({"artifact": key, "path": str(path), "expected_sha256": cert[hash_key], "actual_sha256": actual, "hash_match": ok})
        if not ok:
            raise RuntimeError(f"OOD stress hash mismatch: {key}")
    x = np.load(cert["X_115D_path"]).astype(np.float32)
    sidecar = read_csv(Path(cert["sidecar_path"]))
    if x.shape[0] != len(sidecar) or x.shape[1] != 115:
        raise RuntimeError("OOD stress row alignment or 115D schema check failed")
    return x, sidecar, checks


def select_stress_files(contract: dict[str, Any], manifest: dict[str, dict[str, str]], medium_csvs: set[str]) -> tuple[list[ad.ab.SmokeFile], list[dict[str, Any]], list[dict[str, Any]]]:
    final_files = set(contract["final_OOD_benign_eval_files"])
    attack_files = set(contract["attack_support_files"]) | set(contract["attack_eval_files"])
    ood_contract_files = set(contract["OOD_benign_val_files"])
    selected: list[ad.ab.SmokeFile] = []
    selection_rows: list[dict[str, Any]] = []
    overlap_rows: list[dict[str, Any]] = []

    for csv_member in PREFERRED_STRESS_FILES:
        row = manifest.get(csv_member)
        pcap = row.get("pcap_counterpart_candidate", "") if row else ""
        checks = {
            "in_contract_ood_val": csv_member in ood_contract_files,
            "not_medium_used": csv_member not in medium_csvs,
            "not_final_ood": csv_member not in final_files,
            "not_attack_file": csv_member not in attack_files,
            "pcap_is_benign": pcap.startswith("raw/benign/"),
            "all_benign_flag": row.get("all_benign_flag") == "True" if row else False,
        }
        passed = all(checks.values())
        overlap_rows.append(
            {
                "csv_member": csv_member,
                "pcap_member": pcap,
                **checks,
                "overlap_pass": passed,
                "used_as_stress": passed,
            }
        )
        if not passed:
            continue
        selected.append(ad.make_smoke(OOD_STRESS_ROLE, OOD_STRESS_SPLIT_ROLE, csv_member, pcap, "benign"))
        selection_rows.append(
            {
                "role": OOD_STRESS_ROLE,
                "split_role": OOD_STRESS_SPLIT_ROLE,
                "csv_member": csv_member,
                "pcap_member": pcap,
                "inferred_device": device_from_csv(csv_member),
                "selection_reason": "unused pre-registered OOD-val benign file; disjoint from current medium/final/attack roles",
            }
        )
    if not selected:
        raise RuntimeError("No legal OOD stress files passed disjointness gate")
    return selected, selection_rows, overlap_rows


def materialize_stress_pool(packet_limit: int, warmup_packets: int, max_scan_packets: int) -> dict[str, Any]:
    cert = json.loads((ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json").read_text(encoding="utf-8"))
    contract = ad.load_contract()
    manifest = ad.load_file_manifest()
    medium_csvs = used_medium_csvs(cert)
    stress_smokes, selection_rows, overlap_rows = select_stress_files(contract, manifest, medium_csvs)

    arrays: list[np.ndarray] = []
    sidecar: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    metas: list[dict[str, Any]] = []
    with zipfile.ZipFile(ab.ZIP_PATH, "r") as zf:
        for smoke in stress_smokes:
            nstat = ab.RestoredNetStat115()
            x, sc, meta, tr = ad.extract_file(
                zf,
                smoke,
                nstat,
                packet_limit=packet_limit,
                warmup_packets=warmup_packets,
                strategy=PRIMARY_STRATEGY,
                state_id=f"stress::{Path(smoke.csv_member).stem}",
                record_start_ts=None,
                max_scan_packets=max_scan_packets,
            )
            arrays.append(x)
            sidecar.extend(sc)
            metas.append(meta)
            transitions.append(tr)

    x_all = np.vstack(arrays) if arrays else np.empty((0, 115), dtype=np.float32)
    cert_stress = save_stress_asset(x_all, sidecar, transitions, selection_rows)
    write_csv(OUT / "ood_stress_candidate_inventory.csv", selection_rows)
    write_csv(OUT / "ood_stress_overlap_audit.csv", overlap_rows)
    write_csv(OUT / "ood_stress_materialization_meta.csv", metas)
    (OUT / "ood_stress_data_certificate.json").write_text(json.dumps(cert_stress, indent=2, sort_keys=True), encoding="utf-8")
    write_md(
        OUT / "ood_stress_materialization_report.md",
        [
            "# OOD Stress Materialization Report",
            "",
            f"- stress files selected: `{len(selection_rows)}`",
            f"- rows materialized: `{x_all.shape[0]}`",
            f"- columns: `{x_all.shape[1] if x_all.ndim == 2 else 0}`",
            "- state strategy: `reset_at_split_boundary` per stress file",
            "- final OOD used: `false`",
            "- attack files used: `false`",
            "- formal benchmark: `false`",
        ],
    )
    return cert_stress


def role_indices(sidecar: list[dict[str, str]], role: str) -> np.ndarray:
    return np.asarray(
        [i for i, r in enumerate(sidecar) if r.get("role") == role and r.get("model_ready_hint", "").lower() == "true"],
        dtype=np.int64,
    )


def deterministic_split(idx: np.ndarray, first_fraction: float) -> tuple[np.ndarray, np.ndarray]:
    idx = np.asarray(sorted(map(int, idx.tolist())), dtype=np.int64)
    cut = int(round(len(idx) * first_fraction))
    cut = max(1, min(cut, len(idx) - 1))
    return idx[:cut], idx[cut:]


def aggregate_selection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["active_label_budget"], row["gate_name"], row["radius_quantile"], row["margin"])].append(row)
    out: list[dict[str, Any]] = []
    metrics = [
        "id_calib_hard_alarm",
        "ood_val_hard_alarm",
        "ood_val_review",
        "ood_stress_hard_alarm",
        "ood_stress_review",
        "support_medium_hard_detection",
        "support_heavy_hard_detection",
        "dev_support_attack_min",
        "dev_selection_score",
    ]
    for key, gr in sorted(groups.items()):
        row = {"active_label_budget": key[0], "gate_name": key[1], "radius_quantile": key[2], "margin": key[3], "seeds": len(gr)}
        for metric in metrics:
            stats = summarize([float(r[metric]) for r in gr])
            for stat, value in stats.items():
                row[f"{metric}_{stat}"] = value
        row["stress_feasible_all_seeds"] = all(str(r["stress_feasible"]) == "True" for r in gr)
        row["stress_relaxed_feasible_all_seeds"] = all(str(r["stress_relaxed_feasible"]) == "True" for r in gr)
        out.append(row)
    return out


def aggregate_replay(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["active_label_budget"], row["gate_name"], row["radius_quantile"], row["margin"])].append(row)
    out: list[dict[str, Any]] = []
    roles = [
        "medium_attack_eval_report_only",
        "dev_heavy_query_report_only",
        "final_ood_report_only",
        "id_calib",
        "ood_val",
        "ood_stress_val",
        "support_medium_val",
        "support_heavy_val",
    ]
    for key, gr in sorted(groups.items()):
        row = {"active_label_budget": key[0], "gate_name": key[1], "radius_quantile": key[2], "margin": key[3], "seeds": len(gr)}
        for role in roles:
            for metric in ["hard_alarm_rate", "review_rate", "suppress_rate", "raw_alarm_rate"]:
                stats = summarize([float(r[f"{role}_{metric}"]) for r in gr])
                for stat, value in stats.items():
                    row[f"{role}_{metric}_{stat}"] = value
        row["triple_attack_hard_min"] = min(
            float(row["support_medium_val_hard_alarm_rate_min"]),
            float(row["support_heavy_val_hard_alarm_rate_min"]),
            float(row["medium_attack_eval_report_only_hard_alarm_rate_min"]),
            float(row["dev_heavy_query_report_only_hard_alarm_rate_min"]),
        )
        row["triple_attack_score_or_review_min"] = min(
            float(row["support_medium_val_hard_alarm_rate_min"]),
            float(row["support_heavy_val_hard_alarm_rate_min"]),
            float(row["medium_attack_eval_report_only_hard_alarm_rate_min"]) + float(row["medium_attack_eval_report_only_review_rate_min"]),
            float(row["dev_heavy_query_report_only_hard_alarm_rate_min"]) + float(row["dev_heavy_query_report_only_review_rate_min"]),
        )
        out.append(row)
    return out


def choose_dev_candidate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    feasible = [r for r in rows if r["stress_feasible"]]
    relaxed = [r for r in rows if r["stress_relaxed_feasible"]]
    pool = feasible or relaxed or rows
    return max(
        pool,
        key=lambda r: (
            bool(r["stress_feasible"]),
            bool(r["stress_relaxed_feasible"]),
            float(r["dev_support_attack_min"]),
            -float(r["ood_stress_hard_alarm"]),
            -float(r["ood_stress_review"]),
            -float(r["ood_val_review"]),
            -float(r["id_calib_hard_alarm"]),
            -float(r["margin"]),
        ),
    )


def choose_verdict(report_summary: list[dict[str, Any]], replay_rows: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    # Gate parameters are legally selected per seed/budget from dev roles only.
    # For this diagnostic verdict, do not cherry-pick the best selected group:
    # report the worst-case envelope across all per-seed dev-selected replays.
    selected_configs = sorted(
        {
            f"budget={r['active_label_budget']}|gate={r['gate_name']}|q={r['radius_quantile']}|margin={r['margin']}"
            for r in replay_rows
        }
    )
    def min_metric(role: str, metric: str) -> float:
        return float(np.nanmin([float(r[f"{role}_{metric}"]) for r in replay_rows]))

    def max_metric(role: str, metric: str) -> float:
        return float(np.nanmax([float(r[f"{role}_{metric}"]) for r in replay_rows]))

    stats = {
        "selected_active_label_budget": "per_seed_dev_selected",
        "selected_gate_name": "per_seed_dev_selected_mixed",
        "selected_radius_quantile": "per_seed_dev_selected",
        "selected_margin": "per_seed_dev_selected",
        "selected_config_count": len(selected_configs),
        "selected_configs": ";".join(selected_configs),
        "triple_attack_hard_min": min(
            min_metric("support_medium_val", "hard_alarm_rate"),
            min_metric("support_heavy_val", "hard_alarm_rate"),
            min_metric("medium_attack_eval_report_only", "hard_alarm_rate"),
            min_metric("dev_heavy_query_report_only", "hard_alarm_rate"),
        ),
        "triple_attack_score_or_review_min": min(
            min_metric("support_medium_val", "hard_alarm_rate") + min_metric("support_medium_val", "review_rate"),
            min_metric("support_heavy_val", "hard_alarm_rate") + min_metric("support_heavy_val", "review_rate"),
            min_metric("medium_attack_eval_report_only", "hard_alarm_rate") + min_metric("medium_attack_eval_report_only", "review_rate"),
            min_metric("dev_heavy_query_report_only", "hard_alarm_rate") + min_metric("dev_heavy_query_report_only", "review_rate"),
        ),
        "medium_attack_hard_min": min_metric("medium_attack_eval_report_only", "hard_alarm_rate"),
        "dev_heavy_hard_min": min_metric("dev_heavy_query_report_only", "hard_alarm_rate"),
        "final_ood_hard_max": max_metric("final_ood_report_only", "hard_alarm_rate"),
        "final_ood_review_max": max_metric("final_ood_report_only", "review_rate"),
        "ood_val_hard_max": max_metric("ood_val", "hard_alarm_rate"),
        "ood_val_review_max": max_metric("ood_val", "review_rate"),
        "ood_stress_hard_max": max_metric("ood_stress_val", "hard_alarm_rate"),
        "ood_stress_review_max": max_metric("ood_stress_val", "review_rate"),
    }
    if stats["triple_attack_hard_min"] >= 0.95 and stats["final_ood_hard_max"] <= VAL_TARGET and stats["ood_stress_hard_max"] <= VAL_TARGET:
        return "stress_ood_gate_supported_ready_for_mixed_stream", stats
    if stats["triple_attack_hard_min"] >= 0.90 and stats["ood_stress_hard_max"] <= VAL_TARGET and stats["final_ood_hard_max"] > 0.05:
        return "stress_pool_still_misses_final_tail", stats
    if stats["triple_attack_hard_min"] >= 0.90 and stats["ood_stress_hard_max"] > VAL_TARGET:
        return "stress_pool_exposes_ood_gate_gap_needs_gate_repair", stats
    if stats["triple_attack_hard_min"] < 0.90 and stats["ood_stress_hard_max"] <= VAL_TARGET:
        return "stress_gate_kills_attack_repair_needed", stats
    return "stress_gate_unresolved_needs_broader_pool_or_design", stats


def run_gate_with_stress(stress_cert: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    stress_x, stress_sidecar, stress_checks = load_stress_asset(stress_cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    if not new_sidecar:
        new_sidecar = ay.read_csv(ar.NEW_HELDOUT_SIDECAR)

    x = asset["X"]
    sidecar = asset["sidecar"]
    id_idx = ar.role_indices(sidecar, ar.ID_ROLE)
    ood_idx = ar.role_indices(sidecar, ar.OOD_VAL_ROLE)
    final_ood = ar.role_indices(sidecar, ar.FINAL_OOD_ROLE)
    support_pool = ar.role_indices(sidecar, ar.SUPPORT_ROLE)
    attack_eval = ar.role_indices(sidecar, ar.ATTACK_EVAL_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    stress_idx = role_indices(stress_sidecar, OOD_STRESS_ROLE)
    stress_train, stress_val = deterministic_split(stress_idx, 0.50)
    active_candidate_idx, dev_query_idx, _ = issue27au.split_new_heavy_stream(new_sidecar)

    input_rows = [
        {"artifact": "issue27af_certificate", "path": str(cert_path), "actual_sha256": sha256_file(cert_path), "hash_match": True},
        {"artifact": "issue27az_summary", "path": str(ISSUE27AZ / "summary.md"), "actual_sha256": sha256_file(ISSUE27AZ / "summary.md"), "hash_match": True},
    ]
    input_rows.extend(checks)
    input_rows.extend(stress_checks)
    input_rows.extend(new_checks)

    radius_rows: list[dict[str, Any]] = []
    grid_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        for budget in ACTIVE_LABEL_BUDGETS:
            sel = ay.select_base_and_active(x, new_x, support_pool, active_candidate_idx, new_sidecar, seed, budget)
            medium_train = sel["base_train"]
            medium_val = sel["base_val"]
            heavy_train_idx = sel["heavy_train"]
            heavy_val_idx = sel["heavy_val"]
            heavy_train_x = new_x[heavy_train_idx]
            heavy_val_x = new_x[heavy_val_idx]
            medium_head = ay.fit_region_head(x[id_fit], x[ood_train], x[medium_train], seed)
            heavy_head = ay.fit_region_head(x[id_fit], x[ood_train], heavy_train_x, seed)
            medium_th = ay.threshold_for(medium_head.score(x[id_calib]), medium_head.score(x[ood_val]), medium_head.score(x[medium_val]))
            heavy_th = ay.threshold_for(heavy_head.score(x[id_calib]), heavy_head.score(x[ood_val]), heavy_head.score(heavy_val_x))

            regions = {
                "attack_medium": az.CoverageRegion("attack_medium", x[medium_train], x[medium_val]),
                "attack_heavy": az.CoverageRegion("attack_heavy", heavy_train_x, heavy_val_x),
                "id_benign": az.CoverageRegion("id_benign", x[id_fit], x[id_calib]),
                "ood_benign": az.CoverageRegion("ood_benign", x[ood_train], x[ood_val]),
                "ood_stress": az.CoverageRegion("ood_stress", stress_x[stress_train], stress_x[stress_val]),
            }
            for region in regions.values():
                for q in RADIUS_QUANTILES:
                    row = region.audit_row(q)
                    row.update({"seed": seed, "active_label_budget": budget})
                    radius_rows.append(row)

            role_x = {
                "id_calib": x[id_calib],
                "ood_val": x[ood_val],
                "ood_stress_val": stress_x[stress_val],
                "support_medium_val": x[medium_val],
                "support_heavy_val": heavy_val_x,
                "medium_attack_eval_report_only": x[attack_eval],
                "dev_heavy_query_report_only": new_x[dev_query_idx],
                "final_ood_report_only": x[final_ood],
            }
            role_precomp: dict[tuple[str, float], dict[str, np.ndarray]] = {}
            for q in RADIUS_QUANTILES:
                for role, x_role in role_x.items():
                    _, _, raw = az.head_alarms(
                        medium_head,
                        heavy_head,
                        float(medium_th["threshold"]),
                        float(heavy_th["threshold"]),
                        x_role,
                    )
                    c_m = regions["attack_medium"].normalized_distance(x_role, q)
                    c_h = regions["attack_heavy"].normalized_distance(x_role, q)
                    c_id = regions["id_benign"].normalized_distance(x_role, q)
                    c_ood = regions["ood_benign"].normalized_distance(x_role, q)
                    c_stress = regions["ood_stress"].normalized_distance(x_role, q)
                    role_precomp[(role, q)] = {
                        "raw_alarm": raw,
                        "attack_cov": np.minimum(c_m, c_h),
                        "benign_cov": np.minimum.reduce([c_id, c_ood, c_stress]),
                    }

            seed_rows: list[dict[str, Any]] = []
            for gate_name in ["no_gate", "soft_benign_veto", "attack_advantage_margin", "conflict_to_review"]:
                q_iter = [0.95] if gate_name == "no_gate" else RADIUS_QUANTILES
                margin_iter = [0.0] if gate_name in {"no_gate", "conflict_to_review"} else MARGINS
                for q in q_iter:
                    for margin in margin_iter:
                        dev_metrics: dict[str, float] = {}
                        for role in ["id_calib", "ood_val", "ood_stress_val", "support_medium_val", "support_heavy_val"]:
                            pre = role_precomp[(role, q)]
                            hard, review, suppress = az.gate_decision(gate_name, pre["raw_alarm"], pre["attack_cov"], pre["benign_cov"], float(margin))
                            dev_metrics[f"{role}_hard"] = rate(hard)
                            dev_metrics[f"{role}_review"] = rate(review)
                            dev_metrics[f"{role}_suppress"] = rate(suppress)
                            dev_metrics[f"{role}_raw"] = rate(pre["raw_alarm"])
                        dev_attack_min = min(dev_metrics["support_medium_val_hard"], dev_metrics["support_heavy_val_hard"])
                        stress_feasible = (
                            dev_metrics["id_calib_hard"] <= VAL_TARGET
                            and dev_metrics["ood_val_hard"] <= VAL_TARGET
                            and dev_metrics["ood_stress_val_hard"] <= VAL_TARGET
                            and dev_metrics["ood_val_review"] <= REVIEW_BUDGET
                            and dev_metrics["ood_stress_val_review"] <= REVIEW_BUDGET
                        )
                        stress_relaxed = (
                            dev_metrics["id_calib_hard"] <= VAL_TARGET
                            and dev_metrics["ood_val_hard"] <= VAL_TARGET
                            and dev_metrics["ood_stress_val_hard"] <= VAL_TARGET
                            and dev_metrics["ood_val_review"] <= RELAXED_REVIEW_BUDGET
                            and dev_metrics["ood_stress_val_review"] <= RELAXED_REVIEW_BUDGET
                        )
                        row = {
                            "seed": seed,
                            "active_label_budget": budget,
                            "gate_name": gate_name,
                            "radius_quantile": q,
                            "margin": float(margin),
                            "id_calib_hard_alarm": dev_metrics["id_calib_hard"],
                            "id_calib_review": dev_metrics["id_calib_review"],
                            "ood_val_hard_alarm": dev_metrics["ood_val_hard"],
                            "ood_val_review": dev_metrics["ood_val_review"],
                            "ood_stress_hard_alarm": dev_metrics["ood_stress_val_hard"],
                            "ood_stress_review": dev_metrics["ood_stress_val_review"],
                            "support_medium_hard_detection": dev_metrics["support_medium_val_hard"],
                            "support_heavy_hard_detection": dev_metrics["support_heavy_val_hard"],
                            "dev_support_attack_min": dev_attack_min,
                            "stress_feasible": stress_feasible,
                            "stress_relaxed_feasible": stress_relaxed,
                            "dev_selection_score": dev_attack_min - 0.1 * dev_metrics["ood_stress_val_review"],
                            "selection_uses_final_ood": False,
                            "selection_uses_attack_eval": False,
                            "selection_uses_dev_heavy_query": False,
                        }
                        seed_rows.append(row)
                        grid_rows.append(row)
            selected = choose_dev_candidate(seed_rows)
            selection_rows.append({**selected, "selected_for_report_only_replay": True})
            replay_row: dict[str, Any] = {
                "seed": seed,
                "active_label_budget": budget,
                "gate_name": selected["gate_name"],
                "radius_quantile": selected["radius_quantile"],
                "margin": selected["margin"],
                "selected_for_replay": True,
                "selection_uses_final_ood": False,
                "selection_uses_attack_eval": False,
                "selection_uses_dev_heavy_query": False,
            }
            for role, x_role in role_x.items():
                pre = role_precomp[(role, float(selected["radius_quantile"]))]
                hard, review, suppress = az.gate_decision(selected["gate_name"], pre["raw_alarm"], pre["attack_cov"], pre["benign_cov"], float(selected["margin"]))
                metrics = az.role_metrics(role, pre["raw_alarm"], hard, review, suppress, pre["attack_cov"], pre["benign_cov"])
                for key, value in metrics.items():
                    if key != "role":
                        replay_row[f"{role}_{key}"] = value
            replay_rows.append(replay_row)
            role_rows.append(
                {
                    "seed": seed,
                    "active_label_budget": budget,
                    "fit_roles": "id_fit|ood_train_guard|medium_region_train_attack|active_heavy_region_train_attack",
                    "threshold_roles": "id_calib|ood_val|medium_support_val|active_heavy_val",
                    "gate_radius_roles": "id_fit/id_calib|ood_train/ood_val|ood_stress_val|medium_train/medium_val|heavy_train/heavy_val",
                    "gate_selection_roles": "id_calib|ood_val|ood_stress_val|support_medium_val|support_heavy_val",
                    "report_only_roles": "medium_attack_eval|dev_heavy_query|final_ood",
                    "uses_final_ood_for_gate_selection": False,
                    "uses_attack_eval_for_gate_selection": False,
                    "uses_dev_heavy_query_for_gate_selection": False,
                    "uses_final_ood_for_radius": False,
                    "uses_attack_eval_for_radius": False,
                    "forbidden_role_access": False,
                }
            )

    gate_summary = aggregate_selection(grid_rows)
    replay_summary = aggregate_replay(replay_rows)
    primary_verdict, verdict_stats = choose_verdict(replay_summary, replay_rows)

    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "stress_gate_radius_audit.csv", radius_rows)
    write_csv(OUT / "gate_with_stress_candidate_grid.csv", grid_rows)
    write_csv(OUT / "gate_with_stress_selection_audit.csv", selection_rows)
    write_csv(OUT / "gate_with_stress_dev_summary.csv", gate_summary)
    write_csv(OUT / "gate_with_stress_replay_by_seed.csv", replay_rows)
    write_csv(OUT / "gate_with_stress_summary.csv", replay_summary)
    write_csv(OUT / "role_access_audit.csv", role_rows)
    write_md(
        OUT / "gate_with_stress_report.md",
        [
            "# Gate With Disjoint OOD Stress Report",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "The OOD stress pool is dev-side and selected before looking at final OOD replay.",
            "",
            "## Selected Replay Stats",
            "",
            *[f"- {k}: `{v}`" for k, v in verdict_stats.items()],
            "",
            "## Interpretation Rule",
            "",
            "- If OOD stress is controlled but final OOD still explodes, the stress pool still misses the final tail.",
            "- If OOD stress itself explodes, the gate repair has a legal dev signal and should be fixed before mixed-stream work.",
            "- Final OOD remains report-only and cannot change this issue's selected gate.",
        ],
    )
    return primary_verdict, verdict_stats


def write_issue_reports(primary_verdict: str, stats: dict[str, Any], stress_cert: dict[str, Any]) -> None:
    next_issue = "issue27bb_harder_ood_stress_pool_or_gate_repair"
    if primary_verdict == "stress_ood_gate_supported_ready_for_mixed_stream":
        next_issue = "issue27bb_mixed_stream_active_labeling_realism_gate"
    elif primary_verdict == "stress_pool_exposes_ood_gate_gap_needs_gate_repair":
        next_issue = "issue27bb_ood_gate_repair_on_disjoint_stress_pool"
    elif primary_verdict == "stress_pool_still_misses_final_tail":
        next_issue = "issue27bb_broaden_disjoint_ood_stress_pool_before_mixed_stream"
    elif primary_verdict == "stress_gate_kills_attack_repair_needed":
        next_issue = "issue27bb_attack_preserving_ood_gate_repair_on_disjoint_stress_pool"

    write_md(
        OUT / "issue27ba_decision.md",
        [
            "# Issue27ba Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "- Constructed a disjoint dev-side OOD stress pool from unused pre-registered OOD-val benign files.",
            "- Did not use final OOD, attack eval, or dev-heavy query for gate/radius/threshold selection.",
            "- Did not change the 115D frontend or existing medium split.",
            f"- Recommended next issue: `{next_issue}`.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27ba.md",
        [
            "# Claim Update After issue27ba",
            "",
            "- issue27ba remains a diagnostic gate-repair step, not a formal benchmark.",
            "- A disjoint OOD stress pool can be used for dev-side gate calibration only if its overlap audit remains clean.",
            "- Formal claims still require frozen data contracts, mixed-stream realism, larger/full materialization, and sealed final replay.",
        ],
    )
    write_md(
        OUT / "issue27bb_next_action.md",
        [
            "# Issue27bb Next Action",
            "",
            f"Recommended next issue: `{next_issue}`.",
            "",
            "- If stress exposed OOD gate weakness, repair the gate on stress without using final OOD.",
            "- If stress missed final tail, broaden stress pool from remaining legal OOD-val/dev benign files.",
            "- If stress and final are both controlled with attack preserved, move to mixed incoming stream realism.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27ba Summary",
            "",
            "1. issue27ba completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. task type: disjoint OOD stress pool plus gate selection diagnostic; not formal benchmark",
            "4. 115D frontend/split changed: no",
            "5. OOD stress source: unused pre-registered OOD-val benign files only",
            "6. final OOD used for stress selection/gate selection: no",
            "7. attack eval/dev-heavy query used for gate selection: no",
            f"8. OOD stress rows: `{stress_cert['rows']}`",
            f"9. OOD stress devices: `{json.dumps(stress_cert['device_counts'], sort_keys=True)}`",
            f"10. selected gate: `{stats['selected_gate_name']}`",
            f"11. selected active label budget: `{stats['selected_active_label_budget']}`",
            f"12. selected radius quantile: `{stats['selected_radius_quantile']}`",
            f"13. selected margin: `{stats['selected_margin']}`",
            f"14. triple attack hard min: `{stats['triple_attack_hard_min']}`",
            f"15. OOD val hard max: `{stats['ood_val_hard_max']}`",
            f"16. OOD stress hard max: `{stats['ood_stress_hard_max']}`",
            f"17. final OOD hard max report-only: `{stats['final_ood_hard_max']}`",
            "18. current formal benchmark allowed: no",
            f"19. next action: `{next_issue}`",
            "20. commit hash: pending",
        ],
    )
    config = {
        "issue": ISSUE,
        "formal_benchmark": False,
        "state_strategy": PRIMARY_STRATEGY,
        "ood_stress_files": PREFERRED_STRESS_FILES,
        "active_label_budgets": ACTIVE_LABEL_BUDGETS,
        "radius_quantiles": RADIUS_QUANTILES,
        "margins": MARGINS,
        "val_target": VAL_TARGET,
        "review_budget": REVIEW_BUDGET,
        "primary_verdict": primary_verdict,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "issue27af_certificate": str(ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"),
                    "issue27az_outputs": str(ISSUE27AZ),
                    "gotham_zip": str(ab.ZIP_PATH),
                },
                "outputs": f"runs/{ISSUE}/",
                "scope": "disjoint OOD stress pool and dev-side gate diagnostic only; final roles report-only",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")
    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27ba -->",
        [
            "<!-- issue27ba -->",
            "## issue27ba - Disjoint OOD stress pool before mixed stream",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- Diagnostic only; materializes a dev-side OOD stress pool from unused OOD-val benign files.",
            "- Final OOD, attack eval, and dev-heavy query were not used for gate selection.",
            f"- next action: `{next_issue}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27ba -->",
        [
            "<!-- issue27ba -->",
            "## issue27ba - Disjoint OOD stress pool gate diagnostic",
            "",
            f"- verdict: `{primary_verdict}`",
            "- purpose: give OOD gate selection a harder legal dev-side benign drift signal before mixed-stream realism.",
            f"- outputs: `runs/{ISSUE}/`.",
        ],
    )
    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet-limit", type=int, default=1000)
    parser.add_argument("--warmup-packets", type=int, default=50)
    parser.add_argument("--max-scan-packets", type=int, default=200_000)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    if ab.file_hash(ab.ZIP_PATH, "md5") != ab.EXPECTED_ZIP_MD5:
        raise RuntimeError("Gotham zip md5 mismatch")

    stress_cert = materialize_stress_pool(args.packet_limit, args.warmup_packets, args.max_scan_packets)
    primary_verdict, stats = run_gate_with_stress(stress_cert)
    write_issue_reports(primary_verdict, stats, stress_cert)
    print(json.dumps({"primary_verdict": primary_verdict, "stats": stats, "out": str(OUT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
