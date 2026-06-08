from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au
import issue27ay_region_aware_attack_bank_and_score_gate_diagnostic as ay
import issue27ba_disjoint_ood_stress_pool_before_mixed_stream as ba
import issue27bb_attack_preserving_ood_gate_with_three_prototype_banks as bb
import issue27bc_attack_core_purity_unknown_band_review_budget as bc
import issue27bd_conflict_aware_attack_shell_and_gate_subspace_diagnostic as bd
import issue27bf_bounded_attack_region_bank as bf
import issue27bg_shared_scorer_region_refinement_before_ood_gate as bg


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bh_attack_scorer_region_failure_anatomy_before_new_head_2026-06-08"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BA = ROOT / "runs" / "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"
ISSUE27BD = ROOT / "runs" / "issue27bd_conflict_aware_attack_shell_and_gate_subspace_diagnostic_2026-06-07"
ISSUE27BF = ROOT / "runs" / "issue27bf_bounded_attack_region_bank_2026-06-08"
ISSUE27BG = ROOT / "runs" / "issue27bg_shared_scorer_region_refinement_before_ood_gate_2026-06-08"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
ACTIVE_LABEL_BUDGET = 64
ATTACK_GO_THRESHOLD = 0.93


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


def rate(mask: np.ndarray) -> float:
    arr = np.asarray(mask)
    if arr.size == 0:
        return float("nan")
    return float(np.mean(arr.astype(bool)))


def quantiles(vals: np.ndarray) -> dict[str, float]:
    arr = np.asarray(vals, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return {k: float("nan") for k in ["mean", "q10", "q50", "q90", "q95", "q99", "min", "max"]}
    return {
        "mean": float(np.mean(arr)),
        "q10": float(np.quantile(arr, 0.10)),
        "q50": float(np.quantile(arr, 0.50)),
        "q90": float(np.quantile(arr, 0.90)),
        "q95": float(np.quantile(arr, 0.95)),
        "q99": float(np.quantile(arr, 0.99)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def safe_auc(x0: np.ndarray, x1: np.ndarray) -> float:
    if len(x0) == 0 or len(x1) == 0:
        return float("nan")
    y = np.concatenate([np.zeros(len(x0), dtype=np.int64), np.ones(len(x1), dtype=np.int64)])
    s = np.concatenate([x0, x1]).astype(np.float64)
    if len(np.unique(s[np.isfinite(s)])) < 2:
        return 0.5
    try:
        return float(roc_auc_score(y, s))
    except Exception:
        return float("nan")


def family_slices(schema: dict[str, Any]) -> dict[str, np.ndarray]:
    counts = schema["family_counts"]
    out: dict[str, np.ndarray] = {}
    start = 0
    for fam in ["MI_dir", "H", "HH", "HH_jit", "HpHp"]:
        n = int(counts[fam])
        out[fam] = np.arange(start, start + n, dtype=np.int64)
        start += n
    out["HH_HpHp"] = np.concatenate([out["HH"], out["HpHp"]])
    out["all115"] = np.arange(115, dtype=np.int64)
    return out


def max_abs_feature_auc(x0: np.ndarray, x1: np.ndarray, cols: np.ndarray) -> dict[str, float]:
    aucs = []
    for c in cols:
        auc = safe_auc(x0[:, int(c)], x1[:, int(c)])
        if np.isfinite(auc):
            aucs.append(abs(auc - 0.5) + 0.5)
    arr = np.asarray(aucs, dtype=np.float64)
    if len(arr) == 0:
        return {"max_abs_auc": float("nan"), "mean_abs_auc": float("nan")}
    return {"max_abs_auc": float(np.max(arr)), "mean_abs_auc": float(np.mean(arr))}


def gate_with_bundle(
    x_role: np.ndarray,
    sub_idx: np.ndarray,
    bank: bf.BoundedAttackRegionBank,
    benign_banks: dict[str, bd.ShellPrototypeBank],
    bundle: dict[str, np.ndarray],
    cfg: dict[str, Any],
    weak_ceiling: float,
) -> tuple[dict[str, Any], dict[str, np.ndarray], dict[str, np.ndarray]]:
    pre = bf.precompute_role(x_role, sub_idx, bank, benign_banks, bundle, int(cfg["top_k"]))
    state, masks = bf.apply_region_bank_gate(
        pre["raw_alarm"],
        pre["score_strength"],
        pre["attack_inner"],
        pre["attack_outer"],
        pre["benign_inner"],
        pre["benign_outer"],
        pre["region_score_floor"],
        pre["region_strong_floor"],
        float(cfg["attack_outer_norm"]),
        float(cfg["benign_core_norm"]),
        float(cfg["conflict_slack"]),
        weak_ceiling,
        float(cfg["review_budget"]),
    )
    return bf.role_metrics("role", state, masks, pre, pre["top1_region"]), masks, pre


def selected_cfg(path: Path) -> dict[str, Any]:
    return json.loads((path / "config.json").read_text(encoding="utf-8"))["selected_config"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    stress_cert_path = ISSUE27BA / "ood_stress_data_certificate.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    stress_cert = json.loads(stress_cert_path.read_text(encoding="utf-8"))
    bf_cfg = selected_cfg(ISSUE27BF)
    bg_cfg = selected_cfg(ISSUE27BG)
    bd_cfg = json.loads((ISSUE27BD / "config.json").read_text(encoding="utf-8"))["selected_config"]
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    stress_x, stress_sidecar, stress_checks = ba.load_stress_asset(stress_cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    if not new_sidecar:
        new_sidecar = ay.read_csv(ar.NEW_HELDOUT_SIDECAR)
    x = asset["X"]
    sidecar = asset["sidecar"]
    schema = asset["schema"]
    slices = family_slices(schema)
    sub_idx = slices["HH_HpHp"]

    id_idx = ar.role_indices(sidecar, ar.ID_ROLE)
    ood_idx = ar.role_indices(sidecar, ar.OOD_VAL_ROLE)
    final_ood = ar.role_indices(sidecar, ar.FINAL_OOD_ROLE)
    support_pool = ar.role_indices(sidecar, ar.SUPPORT_ROLE)
    attack_eval = ar.role_indices(sidecar, ar.ATTACK_EVAL_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    stress_idx = ba.role_indices(stress_sidecar, ba.OOD_STRESS_ROLE)
    stress_train, stress_val = ba.deterministic_split(stress_idx, 0.50)
    active_candidate_idx, dev_query_idx, active_manifest = issue27au.split_new_heavy_stream(new_sidecar)

    input_rows = [
        {"artifact": "issue27af_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path)},
        {"artifact": "issue27ba_stress_certificate", "path": str(stress_cert_path), "sha256": sha256_file(stress_cert_path)},
        {"artifact": "issue27bf_config", "path": str(ISSUE27BF / "config.json"), "sha256": sha256_file(ISSUE27BF / "config.json")},
        {"artifact": "issue27bg_config", "path": str(ISSUE27BG / "config.json"), "sha256": sha256_file(ISSUE27BG / "config.json")},
    ]
    input_rows.extend(checks)
    input_rows.extend(stress_checks)
    input_rows.extend(new_checks)

    score_rows: list[dict[str, Any]] = []
    false_negative_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []
    interference_rows: list[dict[str, Any]] = []
    layer_rows: list[dict[str, Any]] = []
    training_rows: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []

    feature_roles: dict[str, list[np.ndarray]] = defaultdict(list)
    report_roles: dict[str, list[np.ndarray]] = defaultdict(list)

    for seed in SEEDS:
        base_support, base_audit = issue27as.kcenter_budget(x, support_pool, ay.BASE_SUPPORT_BUDGET)
        medium_train, medium_val, medium_pseudo, medium_audit = bc.split_train_val_pseudo(base_support, sidecar, seed, "medium_attack_support")
        selected_active, active_audit = issue27au.select_active_labels(
            x_base_support=x[medium_train],
            x_support_val=x[medium_val],
            x_candidates=new_x[active_candidate_idx],
            candidate_indices=active_candidate_idx,
            budget=ACTIVE_LABEL_BUDGET,
        )
        selected_confirmed = np.asarray([idx for idx in selected_active if ay.label_is_attack(new_sidecar[int(idx)])], dtype=np.int64)
        heavy_train, heavy_val, heavy_pseudo, heavy_audit = bc.split_train_val_pseudo(selected_confirmed, new_sidecar, seed, "active_heavy_attack_support")
        if len(heavy_train) == 0 or len(heavy_val) == 0 or len(heavy_pseudo) == 0:
            continue
        split_rows.extend(
            [
                {"seed": seed, "split_family": "medium_attack_support", **medium_audit, "base_support_hash": bf.hash_indices(base_support), **{f"base_{k}": v for k, v in base_audit.items()}},
                {"seed": seed, "split_family": "active_heavy_attack_support", **heavy_audit, "active_confirmed_hash": bf.hash_indices(selected_confirmed), **{f"active_{k}": v for k, v in active_audit.items()}},
            ]
        )

        medium_head = ay.fit_region_head(x[id_fit], x[ood_train], x[medium_train], seed)
        heavy_head = ay.fit_region_head(x[id_fit], x[ood_train], new_x[heavy_train], seed)
        medium_th = ay.threshold_for(medium_head.score(x[id_calib]), medium_head.score(x[ood_val]), medium_head.score(x[medium_val]))
        heavy_th = ay.threshold_for(heavy_head.score(x[id_calib]), heavy_head.score(x[ood_val]), heavy_head.score(new_x[heavy_val]))
        shared = bg.SharedAttackHistGB(seed, str(bg_cfg["weighting_policy"]))
        shared.fit(
            x_id=x[id_fit],
            x_ood=x[ood_train],
            x_ood_stress=stress_x[stress_train],
            x_medium_attack=x[medium_train],
            x_heavy_attack=new_x[heavy_train],
        )
        shared_th = ay.threshold_for(shared.score(x[id_calib]), shared.score(x[ood_val]), shared.score(np.vstack([x[medium_val], new_x[heavy_val]])))
        training_rows.append({"seed": seed, "scorer": "shared", **shared.fit_shape, **shared.direction_check})

        bf_train_x, bf_train_meta, bf_calib_x, bf_calib_meta, bf_train_global = bf.make_bank_inputs(
            x, sidecar, new_x, new_sidecar, medium_head, heavy_head, medium_th, heavy_th, medium_train, medium_val, medium_pseudo, heavy_train, heavy_val, heavy_pseudo
        )
        bf_bank = bf.BoundedAttackRegionBank(
            train_x=bf_train_x,
            train_meta=bf_train_meta,
            calib_x=bf_calib_x,
            calib_meta=bf_calib_meta,
            subspace_idx=sub_idx,
            region_policy=str(bf_cfg["region_policy"]),
            region_balance=str(bf_cfg["region_balance"]),
            prototype_budget=int(bf_cfg["prototype_budget"]),
            region_max=int(bf_cfg["region_max"]),
            inner_radius_q=float(bf_cfg["inner_radius_q"]),
            outer_radius_q=float(bf_cfg["outer_radius_q"]),
            score_floor_q=float(bf_cfg["score_floor_q"]),
        )
        bg_train_x, bg_train_meta, bg_calib_x, bg_calib_meta, bg_train_global = bg.make_shared_bank_inputs(
            x, sidecar, new_x, new_sidecar, shared, float(shared_th["threshold"]), medium_train, medium_val, medium_pseudo, heavy_train, heavy_val, heavy_pseudo
        )
        bg_bank = bf.BoundedAttackRegionBank(
            train_x=bg_train_x,
            train_meta=bg_train_meta,
            calib_x=bg_calib_x,
            calib_meta=bg_calib_meta,
            subspace_idx=sub_idx,
            region_policy=str(bg_cfg["region_policy"]),
            region_balance="equal_region_total",
            prototype_budget=int(bg_cfg["prototype_budget"]),
            region_max=int(bg_cfg["region_max"]),
            inner_radius_q=float(bg_cfg["inner_radius_q"]),
            outer_radius_q=float(bg_cfg["outer_radius_q"]),
            score_floor_q=0.0,
        )
        benign_banks = bf.build_benign_banks(x, stress_x, sub_idx, id_fit, id_calib, ood_train, ood_val, stress_train, stress_val)
        weak_two = float(np.quantile(np.concatenate([
            bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), x[medium_val])["score_strength"],
            bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), new_x[heavy_val])["score_strength"],
        ]), float(bd_cfg["weak_score_q"])))
        weak_shared = float(np.quantile(np.concatenate([
            bg.shared_score_bundle(shared, float(shared_th["threshold"]), x[medium_val])["score_strength"],
            bg.shared_score_bundle(shared, float(shared_th["threshold"]), new_x[heavy_val])["score_strength"],
        ]), float(bd_cfg["weak_score_q"])))

        roles = {
            "id_calib": x[id_calib],
            "ood_val": x[ood_val],
            "ood_stress_val": stress_x[stress_val],
            "support_medium_val": x[medium_val],
            "support_heavy_val": new_x[heavy_val],
            "pseudo_medium_query": x[medium_pseudo],
            "pseudo_heavy_query": new_x[heavy_pseudo],
            "medium_attack_eval_report_only": x[attack_eval],
            "dev_heavy_query_report_only": new_x[dev_query_idx],
            "final_ood_report_only": x[final_ood],
        }
        for role, xr in roles.items():
            if role in {"id_calib", "ood_val", "ood_stress_val", "support_medium_val", "support_heavy_val", "pseudo_medium_query", "pseudo_heavy_query"}:
                feature_roles[role].append(xr)
            else:
                report_roles[role].append(xr)
            two_bundle = bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), xr)
            shared_bundle = bg.shared_score_bundle(shared, float(shared_th["threshold"]), xr)
            two_metrics, two_masks, two_pre = gate_with_bundle(xr, sub_idx, bf_bank, benign_banks, two_bundle, bf_cfg, weak_two)
            shared_metrics, shared_masks, shared_pre = gate_with_bundle(xr, sub_idx, bg_bank, benign_banks, shared_bundle, bg_cfg, weak_shared)
            for scorer_name, bundle, metrics, masks, pre in [
                ("two_head", two_bundle, two_metrics, two_masks, two_pre),
                ("shared", shared_bundle, shared_metrics, shared_masks, shared_pre),
            ]:
                score_rows.append(
                    {
                        "seed": seed,
                        "role": role,
                        "scorer": scorer_name,
                        **{f"score_strength_{k}": v for k, v in quantiles(bundle["score_strength"]).items()},
                        "raw_alarm_rate": metrics["raw_alarm_rate"],
                        "hard_alarm_rate": metrics["hard_alarm_rate"],
                        "review_rate": metrics["review_any_rate"],
                        "suppress_rate": metrics["suppress_rate"],
                        "attack_outer_p50": metrics["attack_outer_p50"],
                        "attack_outer_p95": metrics["attack_outer_p95"],
                        "benign_outer_p50": metrics["benign_outer_p50"],
                    }
                )
                if "attack" in role or "support" in role or "pseudo" in role:
                    raw_fn = ~bundle["raw_alarm"]
                    gate_fn = bundle["raw_alarm"] & ~masks["hard_alarm"]
                    false_negative_rows.append(
                        {
                            "seed": seed,
                            "role": role,
                            "scorer": scorer_name,
                            "rows": int(len(xr)),
                            "raw_false_negative_rate": rate(raw_fn),
                            "gate_false_negative_rate_among_all_rows": rate(gate_fn),
                            "gate_false_negative_rate_among_raw_alarm": float(np.mean(gate_fn[bundle["raw_alarm"]])) if np.any(bundle["raw_alarm"]) else float("nan"),
                            "hard_alarm_rate": metrics["hard_alarm_rate"],
                            "raw_alarm_rate": metrics["raw_alarm_rate"],
                            "median_score_strength_hard": float(np.median(bundle["score_strength"][masks["hard_alarm"]])) if np.any(masks["hard_alarm"]) else float("nan"),
                            "median_score_strength_missed": float(np.median(bundle["score_strength"][~masks["hard_alarm"]])) if np.any(~masks["hard_alarm"]) else float("nan"),
                            "attack_outer_missed_p50": float(np.quantile(pre["attack_outer"][~masks["hard_alarm"]], 0.50)) if np.any(~masks["hard_alarm"]) else float("nan"),
                            "benign_outer_missed_p50": float(np.quantile(pre["benign_outer"][~masks["hard_alarm"]], 0.50)) if np.any(~masks["hard_alarm"]) else float("nan"),
                        }
                    )
        for scorer_name, score_fn in [
            ("two_head_medium_head", lambda z: medium_head.score(z) - float(medium_th["threshold"])),
            ("two_head_heavy_head", lambda z: heavy_head.score(z) - float(heavy_th["threshold"])),
            ("two_head_max_margin", lambda z: bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), z)["score_strength"]),
            ("shared", lambda z: bg.shared_score_bundle(shared, float(shared_th["threshold"]), z)["score_strength"]),
        ]:
            med_support = score_fn(x[medium_val])
            med_query = score_fn(x[medium_pseudo])
            hv_support = score_fn(new_x[heavy_val])
            hv_query = score_fn(new_x[heavy_pseudo])
            gap_rows.extend(
                [
                    {
                        "seed": seed,
                        "scorer": scorer_name,
                        "family": "medium",
                        "support_q50": float(np.quantile(med_support, 0.50)),
                        "query_q50": float(np.quantile(med_query, 0.50)),
                        "support_minus_query_q50": float(np.quantile(med_support, 0.50) - np.quantile(med_query, 0.50)),
                        "support_alarm_rate": rate(med_support > 0),
                        "query_alarm_rate": rate(med_query > 0),
                    },
                    {
                        "seed": seed,
                        "scorer": scorer_name,
                        "family": "heavy",
                        "support_q50": float(np.quantile(hv_support, 0.50)),
                        "query_q50": float(np.quantile(hv_query, 0.50)),
                        "support_minus_query_q50": float(np.quantile(hv_support, 0.50) - np.quantile(hv_query, 0.50)),
                        "support_alarm_rate": rate(hv_support > 0),
                        "query_alarm_rate": rate(hv_query > 0),
                    },
                ]
            )
            interference_rows.append(
                {
                    "seed": seed,
                    "scorer": scorer_name,
                    "medium_support_mean": float(np.mean(med_support)),
                    "medium_query_mean": float(np.mean(med_query)),
                    "heavy_support_mean": float(np.mean(hv_support)),
                    "heavy_query_mean": float(np.mean(hv_query)),
                    "medium_vs_heavy_support_gap": float(np.mean(med_support) - np.mean(hv_support)),
                    "medium_vs_heavy_query_gap": float(np.mean(med_query) - np.mean(hv_query)),
                }
            )

    feature_rows: list[dict[str, Any]] = []
    role_arrays = {k: np.vstack(v) for k, v in feature_roles.items() if v}
    report_arrays = {k: np.vstack(v) for k, v in report_roles.items() if v}
    pairs = [
        ("id_vs_ood", "id_calib", "ood_val", False),
        ("ood_vs_medium_pseudo", "ood_val", "pseudo_medium_query", False),
        ("ood_vs_heavy_pseudo", "ood_val", "pseudo_heavy_query", False),
        ("medium_support_vs_query", "support_medium_val", "pseudo_medium_query", False),
        ("heavy_support_vs_query", "support_heavy_val", "pseudo_heavy_query", False),
        ("ood_vs_medium_attack_eval_report_only", "ood_val", "medium_attack_eval_report_only", True),
        ("ood_vs_dev_heavy_query_report_only", "ood_val", "dev_heavy_query_report_only", True),
    ]
    all_arrays = {**role_arrays, **report_arrays}
    for pair_name, left, right, report_only in pairs:
        if left not in all_arrays or right not in all_arrays:
            continue
        for fam, cols in slices.items():
            if fam == "all115":
                continue
            stats = max_abs_feature_auc(all_arrays[left], all_arrays[right], cols)
            feature_rows.append(
                {
                    "pair": pair_name,
                    "left_role": left,
                    "right_role": right,
                    "family": fam,
                    **stats,
                    "report_only_pair": report_only,
                    "allowed_for_selection": False if report_only else True,
                    "notes": "separability anatomy only; not used for protocol selection",
                }
            )

    # Aggregate layer failure across dev-side attack roles.
    for scorer in ["two_head", "shared"]:
        dev_rows = [r for r in false_negative_rows if r["scorer"] == scorer and "report_only" not in r["role"]]
        if not dev_rows:
            continue
        raw_fn_max = max(float(r["raw_false_negative_rate"]) for r in dev_rows)
        gate_fn_max = max(float(r["gate_false_negative_rate_among_all_rows"]) for r in dev_rows)
        layer = "raw_score_layer" if raw_fn_max >= gate_fn_max else "gate_region_layer"
        layer_rows.append(
            {
                "scorer": scorer,
                "max_raw_false_negative_rate": raw_fn_max,
                "max_gate_false_negative_rate": gate_fn_max,
                "dominant_failure_layer": layer,
                "attack_go_threshold": ATTACK_GO_THRESHOLD,
            }
        )

    role_access_rows = [
        {
            "object": "anatomy_replay",
            "operation": "fit_previous_scorers_and_score_roles",
            "source_roles": "id_fit|ood_train|ood_stress_train|medium_attack_train|active_heavy_attack_train|id_calib|ood_val|ood_stress_val|support_val|pseudo_query",
            "uses_final_ood_for_selection": False,
            "uses_attack_eval_for_selection": False,
            "uses_dev_heavy_query_for_selection": False,
            "forbidden_selection_access": False,
        },
        {
            "object": "report_only_anatomy",
            "operation": "frozen_score_distribution_and_family_auc_only",
            "source_roles": "final_ood_report_only|medium_attack_eval_report_only|dev_heavy_query_report_only",
            "uses_final_ood_for_selection": False,
            "uses_attack_eval_for_selection": False,
            "uses_dev_heavy_query_for_selection": False,
            "forbidden_selection_access": False,
        },
    ]

    # Decision logic: if shared is worse and two-head failures are mixed, do not
    # proceed to new head before a region-aware scorer design.
    two_layer = next((r for r in layer_rows if r["scorer"] == "two_head"), {})
    shared_layer = next((r for r in layer_rows if r["scorer"] == "shared"), {})
    max_medium_gap = max((float(r["support_minus_query_q50"]) for r in gap_rows if r["family"] == "medium"), default=float("nan"))
    verdict = "attack_failure_anatomy_supports_region_aware_scorer_redesign"
    if float(shared_layer.get("max_raw_false_negative_rate", 0.0)) > float(two_layer.get("max_raw_false_negative_rate", 1.0)):
        verdict = "shared_scorer_raw_layer_regression_confirmed"
    if np.isfinite(max_medium_gap) and max_medium_gap > 0.5:
        verdict = "support_query_gap_primary_blocker_before_new_head"
    next_action = "issue27bi_region_aware_metric_or_calibrated_two_head_design"

    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "support_split_audit.csv", split_rows)
    write_csv(OUT / "score_distribution_by_role.csv", score_rows)
    write_csv(OUT / "false_negative_attack_audit.csv", false_negative_rows)
    write_csv(OUT / "support_query_score_gap.csv", gap_rows)
    write_csv(OUT / "feature_family_separability.csv", feature_rows)
    write_csv(OUT / "medium_heavy_interference_audit.csv", interference_rows)
    write_csv(OUT / "scorer_layer_vs_gate_layer_audit.csv", layer_rows)
    write_csv(OUT / "shared_scorer_training_audit_replay.csv", training_rows)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)
    write_csv(OUT / "active_stream_split_manifest.csv", active_manifest)
    write_md(
        OUT / "issue27bh_decision.md",
        [
            "# issue27bh Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            "- This is a failure-anatomy diagnostic, not a new protocol repair.",
            "- It replays prior two-head and shared-scorer designs under the same split and legal dev roles.",
            "- Final/report-only roles are score-only anatomy and are not used for selection.",
            f"- next action: `{next_action}`.",
        ],
    )
    write_md(
        OUT / "issue27bi_next_action.md",
        [
            "# issue27bi Next Action",
            "",
            f"recommended_next_action = `{next_action}`",
            "",
            "- Do not enter OOD-gate repair until attack hard min reaches at least 0.93.",
            "- Candidate directions: calibrated two-head, region-aware metric evidence, or bounded region-specific calibration.",
            "- Avoid unlimited per-attack heads and avoid report-only selection.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27bh.md",
        [
            "# Claim Update After issue27bh",
            "",
            "- issue27bh does not establish model performance.",
            "- It identifies where attack-side failure occurs before selecting a new scorer/head structure.",
            "- Formal claims remain blocked until attack, OOD, review, and final-report-only gates are all satisfied on frozen larger/full assets.",
        ],
    )
    summary_lines = [
        "# issue27bh Summary",
        "",
        "1. issue27bh completed: yes",
        f"2. primary_verdict: `{verdict}`",
        "3. task type: attack-side failure anatomy; not protocol repair; not formal benchmark",
        "4. 115D frontend changed: no",
        "5. split changed: no",
        "6. new head/scorer introduced: no",
        f"7. dominant two-head failure layer: `{two_layer.get('dominant_failure_layer', 'NA')}`",
        f"8. dominant shared failure layer: `{shared_layer.get('dominant_failure_layer', 'NA')}`",
        f"9. max medium support-query score gap q50: `{max_medium_gap}`",
        "10. final/report-only used for selection: no",
        "11. current formal benchmark allowed: no",
        f"12. next action: `{next_action}`",
        "13. commit hash: reported in final response",
    ]
    write_md(OUT / "summary.md", summary_lines)
    config = {
        "issue": ISSUE,
        "seeds": SEEDS,
        "primary_verdict": verdict,
        "next_action": next_action,
        "report_only_selection_forbidden": True,
        "attack_go_threshold": ATTACK_GO_THRESHOLD,
        "inputs": {
            "issue27bf": str(ISSUE27BF),
            "issue27bg": str(ISSUE27BG),
        },
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "command": f"python repo/ood/{Path(__file__).name}",
                "formal_benchmark": False,
                "introduces_new_head": False,
                "uses_final_ood_for_selection": False,
                "uses_attack_eval_for_selection": False,
                "uses_dev_heavy_query_for_selection": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")
    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bh -->",
        [
            "<!-- issue27bh -->",
            "## issue27bh - Attack scorer/region failure anatomy before new head",
            "",
            f"- primary_verdict: `{verdict}`",
            "- purpose: decompose attack-side failure across raw scorer, support-query gap, region/gate, and feature-family evidence.",
            f"- dominant two-head failure layer: `{two_layer.get('dominant_failure_layer', 'NA')}`; dominant shared failure layer: `{shared_layer.get('dominant_failure_layer', 'NA')}`.",
            "- no 115D frontend/split changes; no OOD-gate repair; no formal benchmark.",
            f"- next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bh -->",
        [
            "<!-- issue27bh -->",
            "## issue27bh - Attack-side failure anatomy",
            "",
            f"- verdict: `{verdict}`",
            f"- outputs: `runs/{ISSUE}/`.",
            "- no new head is selected here; this is anatomy before scorer redesign.",
        ],
    )
    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file():
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(json.dumps({"primary_verdict": verdict, "next_action": next_action, "out": str(OUT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
