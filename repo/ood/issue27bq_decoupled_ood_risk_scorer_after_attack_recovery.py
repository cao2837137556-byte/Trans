from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au
import issue27ba_disjoint_ood_stress_pool_before_mixed_stream as ba
import issue27bo_attack_future_shift_validation_without_new_support as bo
import issue27bp_attack_preserving_ood_gate_repair_after_future_shift_validation as bp


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bq_decoupled_ood_risk_scorer_after_attack_recovery_2026-06-09"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BA = ROOT / "runs" / "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"
ISSUE27BM = ROOT / "runs" / "issue27bm_phase_balanced_attack_contract_design_without_report_only_leakage_2026-06-08"
ISSUE27BO = ROOT / "runs" / "issue27bo_attack_future_shift_validation_without_new_support_2026-06-09"
ISSUE27BP = ROOT / "runs" / "issue27bp_attack_preserving_ood_gate_repair_after_future_shift_validation_2026-06-09"

PRIMARY_STRATEGY = "reset_at_split_boundary"
PRIMARY_CONTRACT = "phase_balanced_dev_v2"
SEEDS = [42, 43, 44, 45, 46]

VAL_OOD_TARGET = 0.01
OOD_DIAGNOSTIC_TARGET = 0.05
ATTACK_FLOOR = 0.93
REVIEW_BUDGETS = [0.00, 0.03, 0.05]
RISK_THRESHOLDS = [0.50, 0.60, 0.70, 0.80, 0.90, 0.95]
STRONG_MARGIN_QS = [0.00, 0.10, 0.25]
ATTACK_OUTER_NORMS = [1.0, 1.25]
RISK_MODELS = ["logreg_balanced", "histgb_shallow"]

# Keep risk features small and explainable. These subspaces are not selected
# using final/report-only roles.
ATTACK_EVIDENCE_SUBSPACES = ["HH", "HH_HpHp"]
BENIGN_EVIDENCE_SUBSPACES = ["HH_jit", "MI_H_HHjit", "all115"]
PROTO_BUDGET = 32


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


def metric_stats(rows: list[dict[str, Any]], keys: list[str], metrics: list[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    out: list[dict[str, Any]] = []
    for key, vals in sorted(groups.items(), key=lambda x: str(x[0])):
        row = {k: v for k, v in zip(keys, key)}
        row["seeds"] = len(vals)
        for m in metrics:
            arr = np.asarray([float(v[m]) for v in vals], dtype=np.float64)
            row[f"{m}_mean"] = float(np.mean(arr))
            row[f"{m}_min"] = float(np.min(arr))
            row[f"{m}_max"] = float(np.max(arr))
        out.append(row)
    return out


def deterministic_half(n: int) -> tuple[np.ndarray, np.ndarray]:
    idx = np.arange(n, dtype=np.int64)
    cut = max(1, min(n - 1, n // 2)) if n > 1 else n
    return idx[:cut], idx[cut:]


def fit_risk_model(kind: str, x_train: np.ndarray, y_train: np.ndarray, seed: int):
    if kind == "logreg_balanced":
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed, solver="liblinear"),
        )
    elif kind == "histgb_shallow":
        model = HistGradientBoostingClassifier(
            max_iter=80,
            max_leaf_nodes=8,
            learning_rate=0.05,
            l2_regularization=0.1,
            random_state=seed,
        )
    else:
        raise ValueError(kind)
    model.fit(x_train, y_train)
    return model


def risk_score(model: Any, x_feat: np.ndarray) -> np.ndarray:
    proba = model.predict_proba(x_feat)
    classes = list(model.classes_) if hasattr(model, "classes_") else list(model[-1].classes_)
    return np.asarray(proba[:, classes.index(1)], dtype=np.float64)


def build_evidence_banks(
    x: np.ndarray,
    stress_x: np.ndarray,
    support_train: np.ndarray,
    support_val: np.ndarray,
    pseudo: np.ndarray,
    id_fit: np.ndarray,
    id_calib: np.ndarray,
    ood_train: np.ndarray,
    ood_val: np.ndarray,
    stress_train: np.ndarray,
    stress_val: np.ndarray,
    subspaces: dict[str, np.ndarray],
) -> tuple[dict[str, bp.ProtoBank], list[dict[str, Any]]]:
    banks: dict[str, bp.ProtoBank] = {}
    rows: list[dict[str, Any]] = []
    for name in ATTACK_EVIDENCE_SUBSPACES:
        idx = subspaces[name]
        bank = bp.ProtoBank(
            f"attack_{name}",
            support_train[:, idx],
            PROTO_BUDGET,
            {
                "core": (support_val[:, idx], 0.95),
                "outer": (pseudo[:, idx], 0.95),
            },
        )
        banks[f"attack_{name}"] = bank
        rows.append(
            {
                "bank": f"attack_{name}",
                "subspace": name,
                "fit_rows": bank.fit_rows,
                "budget": bank.budget,
                "core_radius": bank.radii["core"],
                "outer_radius": bank.radii["outer"],
            }
        )
    for name in BENIGN_EVIDENCE_SUBSPACES:
        idx = subspaces[name]
        fit = np.vstack([x[id_fit][:, idx], x[ood_train][:, idx], stress_x[stress_train][:, idx]])
        val = np.vstack([x[id_calib][:, idx], x[ood_val][:, idx], stress_x[stress_val][:, idx]])
        bank = bp.ProtoBank(f"benign_{name}", fit, PROTO_BUDGET, {"core": (val, 0.95)})
        banks[f"benign_{name}"] = bank
        rows.append(
            {
                "bank": f"benign_{name}",
                "subspace": name,
                "fit_rows": bank.fit_rows,
                "budget": bank.budget,
                "core_radius": bank.radii["core"],
                "outer_radius": "",
            }
        )
    return banks, rows


def evidence_features(
    x_role: np.ndarray,
    score: np.ndarray,
    threshold: float,
    banks: dict[str, bp.ProtoBank],
    subspaces: dict[str, np.ndarray],
) -> tuple[np.ndarray, list[str], dict[str, np.ndarray]]:
    margin = np.asarray(score, dtype=np.float64) - float(threshold)
    cols: list[np.ndarray] = [
        margin,
        np.maximum(margin, 0.0),
    ]
    names = ["attack_score_margin", "attack_score_positive_margin"]
    aux: dict[str, np.ndarray] = {"margin": margin, "raw_alarm": margin > 0.0}

    attack_norms = []
    for name in ATTACK_EVIDENCE_SUBSPACES:
        idx = subspaces[name]
        bank = banks[f"attack_{name}"]
        d_core = bank.norm_distance(x_role[:, idx], "core")
        d_outer = bank.norm_distance(x_role[:, idx], "outer")
        cols.extend([d_core, d_outer])
        names.extend([f"d_attack_core_{name}", f"d_attack_outer_{name}"])
        aux[f"d_attack_outer_{name}"] = d_outer
        attack_norms.append(d_outer)
    benign_norms = []
    for name in BENIGN_EVIDENCE_SUBSPACES:
        idx = subspaces[name]
        bank = banks[f"benign_{name}"]
        d = bank.norm_distance(x_role[:, idx], "core")
        cols.append(d)
        names.append(f"d_benign_core_{name}")
        aux[f"d_benign_core_{name}"] = d
        benign_norms.append(d)

    min_attack = np.min(np.vstack(attack_norms), axis=0)
    min_benign = np.min(np.vstack(benign_norms), axis=0)
    cols.extend([min_attack, min_benign, min_benign - min_attack])
    names.extend(["d_attack_outer_min", "d_benign_core_min", "benign_minus_attack_distance"])
    aux["d_attack_outer_min"] = min_attack
    aux["d_benign_core_min"] = min_benign
    aux["benign_minus_attack_distance"] = min_benign - min_attack
    return np.column_stack(cols).astype(np.float32), names, aux


def apply_controller(
    raw_alarm: np.ndarray,
    margin: np.ndarray,
    d_attack: np.ndarray,
    risk: np.ndarray,
    params: dict[str, float],
) -> dict[str, np.ndarray]:
    raw = np.asarray(raw_alarm, dtype=bool)
    strong_attack = raw & (margin >= params["strong_margin_floor"]) & (d_attack <= params["attack_outer_norm"])
    high_risk = raw & (risk >= params["risk_threshold"])
    weak_attack = raw & ((margin <= params["weak_margin_ceiling"]) | (d_attack > params["attack_outer_norm"]))
    conflict = high_risk & strong_attack
    # Keep review bounded by selecting the highest OOD-risk conflicts.
    review = np.zeros_like(raw, dtype=bool)
    k = int(np.floor(params["review_budget"] * len(raw)))
    idx = np.flatnonzero(conflict)
    if k > 0 and idx.size:
        order = np.argsort(-risk[idx])
        review[idx[order[: min(k, idx.size)]]] = True
    suppress = high_risk & weak_attack & (~review) & (~strong_attack)
    hard = raw & (~suppress) & (~review)
    hard = hard | (strong_attack & (~review))
    return {
        "raw_alarm": raw,
        "hard_alarm": hard,
        "review": review,
        "suppress": suppress,
        "strong_attack": strong_attack,
        "high_ood_risk": high_risk,
        "weak_attack": weak_attack,
        "conflict": conflict,
    }


def summarize_controller(role: str, is_report_only: bool, risk: np.ndarray, aux: dict[str, np.ndarray], masks: dict[str, np.ndarray]) -> dict[str, Any]:
    return {
        "role": role,
        "is_report_only": bool(is_report_only),
        "n": int(len(risk)),
        "raw_alarm_rate": rate(masks["raw_alarm"]),
        "hard_alarm_rate": rate(masks["hard_alarm"]),
        "review_rate": rate(masks["review"]),
        "suppress_rate": rate(masks["suppress"]),
        "strong_attack_rate": rate(masks["strong_attack"]),
        "high_ood_risk_rate": rate(masks["high_ood_risk"]),
        "weak_attack_rate": rate(masks["weak_attack"]),
        "risk_mean": float(np.mean(risk)) if len(risk) else float("nan"),
        "risk_p50": float(np.quantile(risk, 0.50)) if len(risk) else float("nan"),
        "risk_p95": float(np.quantile(risk, 0.95)) if len(risk) else float("nan"),
        "risk_p99": float(np.quantile(risk, 0.99)) if len(risk) else float("nan"),
        "margin_p50": float(np.quantile(aux["margin"], 0.50)) if len(risk) else float("nan"),
        "d_attack_outer_min_p50": float(np.quantile(aux["d_attack_outer_min"], 0.50)) if len(risk) else float("nan"),
        "d_benign_core_min_p50": float(np.quantile(aux["d_benign_core_min"], 0.50)) if len(risk) else float("nan"),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    x = asset["X"]
    sidecar = asset["sidecar"]
    schema = asset["schema"]
    subspaces = bp.build_subspaces(schema)

    stress_cert_path = ISSUE27BA / "ood_stress_data_certificate.json"
    stress_cert = json.loads(stress_cert_path.read_text(encoding="utf-8"))
    stress_x, stress_sidecar, stress_checks = ba.load_stress_asset(stress_cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()

    support_train_rows = bo.load_contract_role("phase_balanced_support_train_indices.csv")
    support_val_rows = bo.load_contract_role("phase_balanced_support_val_indices.csv")
    pseudo_rows = bo.load_contract_role("phase_balanced_pseudo_query_dev_indices.csv")
    x_support_train = bo.contract_features(support_train_rows, x, new_x)
    x_support_val = bo.contract_features(support_val_rows, x, new_x)
    x_pseudo = bo.contract_features(pseudo_rows, x, new_x)

    id_idx = ar.role_indices(sidecar, ar.ID_ROLE)
    ood_idx = ar.role_indices(sidecar, ar.OOD_VAL_ROLE)
    attack_eval_idx = ar.role_indices(sidecar, ar.ATTACK_EVAL_ROLE)
    final_ood_idx = ar.role_indices(sidecar, ar.FINAL_OOD_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    stress_idx = ba.role_indices(stress_sidecar, ba.OOD_STRESS_ROLE)
    stress_train, stress_val = ba.deterministic_split(stress_idx, 0.50)
    _, dev_heavy_query_idx, _ = issue27au.split_new_heavy_stream(new_sidecar)

    role_x_extra, _, _ = bp.role_records_and_features(
        x,
        sidecar,
        new_x,
        new_sidecar,
        attack_eval_idx,
        final_ood_idx,
        dev_heavy_query_idx,
        support_val_rows,
        pseudo_rows,
    )
    dev_role_x = {
        "id_calib": x[id_calib],
        "ood_val": x[ood_val],
        "ood_stress_val": stress_x[stress_val],
        "support_val": x_support_val,
        "dev_future_near": role_x_extra["dev_future_near"],
        "dev_future_mid": role_x_extra["dev_future_mid"],
        "dev_future_far": role_x_extra["dev_future_far"],
    }
    replay_role_x = {
        **dev_role_x,
        "sealed_medium_attack_eval_report_only": role_x_extra["sealed_medium_attack_eval_report_only"],
        "sealed_dev_heavy_query_report_only": role_x_extra["sealed_dev_heavy_query_report_only"],
        "sealed_heavy_future_near": role_x_extra["sealed_heavy_future_near"],
        "sealed_heavy_future_mid": role_x_extra["sealed_heavy_future_mid"],
        "sealed_heavy_future_far": role_x_extra["sealed_heavy_future_far"],
        "final_ood_report_only": x[final_ood_idx],
    }
    report_only = {k: k.startswith("sealed_") or k.endswith("report_only") or k == "final_ood_report_only" for k in replay_role_x}

    input_rows = [
        {"artifact": "issue27af_medium_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path), "used_for": "fixed_medium_asset"},
        {"artifact": "issue27ba_ood_stress_certificate", "path": str(stress_cert_path), "sha256": sha256_file(stress_cert_path), "used_for": "dev_ood_stress_asset"},
        {"artifact": "issue27bm_phase_balanced_contract", "path": str(ISSUE27BM / "phase_balanced_contract_v2.json"), "sha256": sha256_file(ISSUE27BM / "phase_balanced_contract_v2.json"), "used_for": "fixed_support_contract"},
        {"artifact": "issue27bo_summary", "path": str(ISSUE27BO / "summary.md"), "sha256": sha256_file(ISSUE27BO / "summary.md"), "used_for": "fixed_attack_future_shift_context"},
        {"artifact": "issue27bp_summary", "path": str(ISSUE27BP / "summary.md"), "sha256": sha256_file(ISSUE27BP / "summary.md"), "used_for": "tradeoff_context"},
    ]
    for check in checks + stress_checks + new_checks:
        input_rows.append({**check, "used_for": "hash_validation"})

    feature_schema_rows: list[dict[str, Any]] = []
    for name in ["attack_score_margin", "attack_score_positive_margin"]:
        feature_schema_rows.append({"feature_name": name, "source": "frozen_full115_attack_scorer", "allowed_for_model_input": True})
    for s in ATTACK_EVIDENCE_SUBSPACES:
        feature_schema_rows.append({"feature_name": f"d_attack_core_{s}", "source": "attack_support_prototype_bank", "allowed_for_model_input": True})
        feature_schema_rows.append({"feature_name": f"d_attack_outer_{s}", "source": "attack_support_pseudo_calibrated_bank", "allowed_for_model_input": True})
    for s in BENIGN_EVIDENCE_SUBSPACES:
        feature_schema_rows.append({"feature_name": f"d_benign_core_{s}", "source": "id_ood_stress_dev_prototype_bank", "allowed_for_model_input": True})
    feature_schema_rows.extend(
        [
            {"feature_name": "d_attack_outer_min", "source": "derived_from_attack_distances", "allowed_for_model_input": True},
            {"feature_name": "d_benign_core_min", "source": "derived_from_benign_distances", "allowed_for_model_input": True},
            {"feature_name": "benign_minus_attack_distance", "source": "derived_distance_margin", "allowed_for_model_input": True},
        ]
    )

    bank_rows: list[dict[str, Any]] = []
    train_audit_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    selected_model_payload: dict[str, Any] | None = None

    for seed in SEEDS:
        attack_model = bo.FrozenAttackHistGB(seed)
        attack_model.fit(x[id_fit], x[ood_train], x_support_train)
        attack_threshold = float(np.quantile(attack_model.score(x[id_calib]), 0.99))
        scores_dev = {role: attack_model.score(rx) for role, rx in dev_role_x.items()}
        scores_replay = {role: attack_model.score(rx) for role, rx in replay_role_x.items()}

        banks, audit = build_evidence_banks(
            x,
            stress_x,
            x_support_train,
            x_support_val,
            x_pseudo,
            id_fit,
            id_calib,
            ood_train,
            ood_val,
            stress_train,
            stress_val,
            subspaces,
        )
        for row in audit:
            bank_rows.append({"seed": seed, **row})

        feat_dev: dict[str, np.ndarray] = {}
        aux_dev: dict[str, dict[str, np.ndarray]] = {}
        feat_names: list[str] = []
        for role, rx in dev_role_x.items():
            feat, names, aux = evidence_features(rx, scores_dev[role], attack_threshold, banks, subspaces)
            feat_dev[role] = feat
            aux_dev[role] = aux
            feat_names = names

        # Train/calibrate OOD-risk only on dev-side raw alarms. Positive =
        # benign/OOD false-alarm risk, negative = attack alarm.
        pos_roles = ["id_calib", "ood_val", "ood_stress_val"]
        neg_roles = ["support_val", "dev_future_near", "dev_future_mid", "dev_future_far"]
        x_train_parts, y_train_parts, x_calib_parts, y_calib_parts = [], [], [], []
        for role, label in [(r, 1) for r in pos_roles] + [(r, 0) for r in neg_roles]:
            alarm_idx = np.flatnonzero(aux_dev[role]["raw_alarm"])
            if alarm_idx.size == 0:
                continue
            first, second = deterministic_half(alarm_idx.size)
            train_idx = alarm_idx[first]
            calib_idx = alarm_idx[second]
            x_train_parts.append(feat_dev[role][train_idx])
            y_train_parts.append(np.full(len(train_idx), label, dtype=np.int8))
            x_calib_parts.append(feat_dev[role][calib_idx])
            y_calib_parts.append(np.full(len(calib_idx), label, dtype=np.int8))
            train_audit_rows.append(
                {
                    "seed": seed,
                    "role": role,
                    "risk_label": label,
                    "raw_alarm_rows": int(alarm_idx.size),
                    "risk_train_rows": int(len(train_idx)),
                    "risk_calib_rows": int(len(calib_idx)),
                    "used_for_risk_fit": True,
                    "used_for_controller_selection": True,
                    "is_report_only": False,
                }
            )
        x_train = np.vstack(x_train_parts)
        y_train = np.concatenate(y_train_parts)
        x_calib = np.vstack(x_calib_parts)
        y_calib = np.concatenate(y_calib_parts)

        for model_kind in RISK_MODELS:
            risk_model = fit_risk_model(model_kind, x_train, y_train, seed)
            risk_calib = risk_score(risk_model, x_calib)
            margin_source = np.concatenate([aux_dev[r]["margin"][aux_dev[r]["raw_alarm"]] for r in neg_roles])
            margin_source = margin_source[np.isfinite(margin_source)]
            for risk_thr in RISK_THRESHOLDS:
                for strong_q in STRONG_MARGIN_QS:
                    strong_floor = float(np.quantile(margin_source, strong_q)) if margin_source.size else 0.0
                    weak_ceiling = float(np.quantile(margin_source, 0.25)) if margin_source.size else 0.0
                    for attack_outer_norm in ATTACK_OUTER_NORMS:
                        for review_budget in REVIEW_BUDGETS:
                            role_metrics: dict[str, dict[str, Any]] = {}
                            for role, feat in feat_dev.items():
                                risk = risk_score(risk_model, feat)
                                params = {
                                    "risk_threshold": risk_thr,
                                    "strong_margin_floor": strong_floor,
                                    "weak_margin_ceiling": weak_ceiling,
                                    "attack_outer_norm": attack_outer_norm,
                                    "review_budget": review_budget,
                                }
                                masks = apply_controller(
                                    aux_dev[role]["raw_alarm"],
                                    aux_dev[role]["margin"],
                                    aux_dev[role]["d_attack_outer_min"],
                                    risk,
                                    params,
                                )
                                role_metrics[role] = summarize_controller(role, False, risk, aux_dev[role], masks)
                            dev_attack_min = min(
                                role_metrics["support_val"]["hard_alarm_rate"],
                                role_metrics["dev_future_near"]["hard_alarm_rate"],
                                role_metrics["dev_future_mid"]["hard_alarm_rate"],
                                role_metrics["dev_future_far"]["hard_alarm_rate"],
                            )
                            dev_ood_max = max(
                                role_metrics["id_calib"]["hard_alarm_rate"],
                                role_metrics["ood_val"]["hard_alarm_rate"],
                                role_metrics["ood_stress_val"]["hard_alarm_rate"],
                            )
                            dev_review_max = max(
                                role_metrics["id_calib"]["review_rate"],
                                role_metrics["ood_val"]["review_rate"],
                                role_metrics["ood_stress_val"]["review_rate"],
                            )
                            feasible_1pct = dev_attack_min >= ATTACK_FLOOR and dev_ood_max <= VAL_OOD_TARGET and dev_review_max <= review_budget + 1e-12
                            feasible_5pct = dev_attack_min >= ATTACK_FLOOR and dev_ood_max <= OOD_DIAGNOSTIC_TARGET and dev_review_max <= review_budget + 1e-12
                            candidate_rows.append(
                                {
                                    "seed": seed,
                                    "risk_model": model_kind,
                                    "risk_threshold": risk_thr,
                                    "strong_margin_q": strong_q,
                                    "strong_margin_floor": strong_floor,
                                    "weak_margin_ceiling": weak_ceiling,
                                    "attack_outer_norm": attack_outer_norm,
                                    "review_budget": review_budget,
                                    "risk_calib_auc_proxy_mean_pos": float(np.mean(risk_calib[y_calib == 1])) if np.any(y_calib == 1) else float("nan"),
                                    "risk_calib_auc_proxy_mean_neg": float(np.mean(risk_calib[y_calib == 0])) if np.any(y_calib == 0) else float("nan"),
                                    "dev_attack_min": dev_attack_min,
                                    "dev_ood_max": dev_ood_max,
                                    "dev_review_max": dev_review_max,
                                    "id_hard": role_metrics["id_calib"]["hard_alarm_rate"],
                                    "ood_val_hard": role_metrics["ood_val"]["hard_alarm_rate"],
                                    "ood_stress_hard": role_metrics["ood_stress_val"]["hard_alarm_rate"],
                                    "support_val_hard": role_metrics["support_val"]["hard_alarm_rate"],
                                    "dev_future_near_hard": role_metrics["dev_future_near"]["hard_alarm_rate"],
                                    "dev_future_mid_hard": role_metrics["dev_future_mid"]["hard_alarm_rate"],
                                    "dev_future_far_hard": role_metrics["dev_future_far"]["hard_alarm_rate"],
                                    "feasible_1pct": feasible_1pct,
                                    "feasible_5pct": feasible_5pct,
                                    "selection_uses_final_ood": False,
                                    "selection_uses_report_only_attack": False,
                                    "dev_score": dev_attack_min - 1.5 * dev_ood_max - dev_review_max,
                                }
                            )

    # Aggregate across seeds and select with dev-only constraints.
    summary = metric_stats(
        candidate_rows,
        ["risk_model", "risk_threshold", "strong_margin_q", "attack_outer_norm", "review_budget"],
        ["dev_attack_min", "dev_ood_max", "dev_review_max", "dev_score"],
    )
    for row in summary:
        row["feasible_1pct_all_seeds"] = (
            float(row["dev_attack_min_min"]) >= ATTACK_FLOOR
            and float(row["dev_ood_max_max"]) <= VAL_OOD_TARGET
            and float(row["dev_review_max_max"]) <= float(row["review_budget"]) + 1e-12
        )
        row["feasible_5pct_all_seeds"] = (
            float(row["dev_attack_min_min"]) >= ATTACK_FLOOR
            and float(row["dev_ood_max_max"]) <= OOD_DIAGNOSTIC_TARGET
            and float(row["dev_review_max_max"]) <= float(row["review_budget"]) + 1e-12
        )
    feasible = [r for r in summary if str(r["feasible_1pct_all_seeds"]).lower() == "true"]
    if not feasible:
        feasible = [r for r in summary if str(r["feasible_5pct_all_seeds"]).lower() == "true"]
    pool = feasible if feasible else summary
    selected = max(
        pool,
        key=lambda r: (
            bool(str(r["feasible_1pct_all_seeds"]).lower() == "true"),
            bool(str(r["feasible_5pct_all_seeds"]).lower() == "true"),
            float(r["dev_attack_min_min"]),
            -float(r["dev_ood_max_max"]),
            -float(r["dev_review_max_max"]),
        ),
    )

    # Replay selected candidate. Refit per seed using the same dev-only recipe.
    for seed in SEEDS:
        attack_model = bo.FrozenAttackHistGB(seed)
        attack_model.fit(x[id_fit], x[ood_train], x_support_train)
        attack_threshold = float(np.quantile(attack_model.score(x[id_calib]), 0.99))
        scores_replay = {role: attack_model.score(rx) for role, rx in replay_role_x.items()}
        scores_dev = {role: attack_model.score(rx) for role, rx in dev_role_x.items()}
        banks, _ = build_evidence_banks(
            x,
            stress_x,
            x_support_train,
            x_support_val,
            x_pseudo,
            id_fit,
            id_calib,
            ood_train,
            ood_val,
            stress_train,
            stress_val,
            subspaces,
        )
        feat_dev, aux_dev = {}, {}
        for role, rx in dev_role_x.items():
            feat, feat_names, aux = evidence_features(rx, scores_dev[role], attack_threshold, banks, subspaces)
            feat_dev[role] = feat
            aux_dev[role] = aux
        pos_roles = ["id_calib", "ood_val", "ood_stress_val"]
        neg_roles = ["support_val", "dev_future_near", "dev_future_mid", "dev_future_far"]
        x_train_parts, y_train_parts = [], []
        for role, label in [(r, 1) for r in pos_roles] + [(r, 0) for r in neg_roles]:
            alarm_idx = np.flatnonzero(aux_dev[role]["raw_alarm"])
            first, _second = deterministic_half(alarm_idx.size)
            idx = alarm_idx[first]
            x_train_parts.append(feat_dev[role][idx])
            y_train_parts.append(np.full(len(idx), label, dtype=np.int8))
        risk_model = fit_risk_model(str(selected["risk_model"]), np.vstack(x_train_parts), np.concatenate(y_train_parts), seed)
        margin_source = np.concatenate([aux_dev[r]["margin"][aux_dev[r]["raw_alarm"]] for r in neg_roles])
        params = {
            "risk_threshold": float(selected["risk_threshold"]),
            "strong_margin_floor": float(np.quantile(margin_source[np.isfinite(margin_source)], float(selected["strong_margin_q"]))),
            "weak_margin_ceiling": float(np.quantile(margin_source[np.isfinite(margin_source)], 0.25)),
            "attack_outer_norm": float(selected["attack_outer_norm"]),
            "review_budget": float(selected["review_budget"]),
        }
        for role, rx in replay_role_x.items():
            feat, _names, aux = evidence_features(rx, scores_replay[role], attack_threshold, banks, subspaces)
            risk = risk_score(risk_model, feat)
            masks = apply_controller(aux["raw_alarm"], aux["margin"], aux["d_attack_outer_min"], risk, params)
            replay_rows.append(
                {
                    "seed": seed,
                    "role": role,
                    "risk_model": selected["risk_model"],
                    "risk_threshold": selected["risk_threshold"],
                    "strong_margin_q": selected["strong_margin_q"],
                    "attack_outer_norm": selected["attack_outer_norm"],
                    "review_budget": selected["review_budget"],
                    "is_report_only": report_only[role],
                    **summarize_controller(role, report_only[role], risk, aux, masks),
                }
            )
        role_rows.append(
            {
                "seed": seed,
                "attack_fit_roles": "id_fit|ood_train|phase_balanced_support_train",
                "attack_threshold_roles": "id_calib",
                "ood_risk_fit_roles": "raw_alarm_subset_of_id_calib|ood_val|ood_stress_val|support_val|dev_future_near|dev_future_mid|dev_future_far",
                "controller_selection_roles": "same_as_ood_risk_dev_roles",
                "report_only_roles": "final_ood|sealed_medium_attack_eval|sealed_dev_heavy_query",
                "uses_final_ood_for_fit_threshold_selection": False,
                "uses_report_only_attack_for_fit_threshold_selection": False,
                "forbidden_role_access": False,
            }
        )

    replay_summary = metric_stats(
        replay_rows,
        ["role", "is_report_only"],
        ["raw_alarm_rate", "hard_alarm_rate", "review_rate", "suppress_rate", "risk_mean", "risk_p95"],
    )
    def get(role: str, metric: str, stat: str) -> float:
        for r in replay_summary:
            if r["role"] == role:
                return float(r[f"{metric}_{stat}"])
        return float("nan")

    dev_attack_min = min(
        get("support_val", "hard_alarm_rate", "min"),
        get("dev_future_near", "hard_alarm_rate", "min"),
        get("dev_future_mid", "hard_alarm_rate", "min"),
        get("dev_future_far", "hard_alarm_rate", "min"),
    )
    dev_ood_max = max(
        get("id_calib", "hard_alarm_rate", "max"),
        get("ood_val", "hard_alarm_rate", "max"),
        get("ood_stress_val", "hard_alarm_rate", "max"),
    )
    dev_review_max = max(
        get("id_calib", "review_rate", "max"),
        get("ood_val", "review_rate", "max"),
        get("ood_stress_val", "review_rate", "max"),
    )
    report_attack_min = min(
        get("sealed_medium_attack_eval_report_only", "hard_alarm_rate", "min"),
        get("sealed_dev_heavy_query_report_only", "hard_alarm_rate", "min"),
        get("sealed_heavy_future_near", "hard_alarm_rate", "min"),
        get("sealed_heavy_future_mid", "hard_alarm_rate", "min"),
        get("sealed_heavy_future_far", "hard_alarm_rate", "min"),
    )
    final_ood_max = get("final_ood_report_only", "hard_alarm_rate", "max")

    issue27bp_dev_ood = 0.5333333333333333
    issue27bp_final_ood = 0.086
    issue27bp_dev_attack = 0.984375
    if dev_attack_min >= ATTACK_FLOOR and dev_ood_max <= VAL_OOD_TARGET and dev_review_max <= float(selected["review_budget"]) + 1e-12:
        verdict = "decoupled_ood_risk_dev_passed_ready_for_larger_sanity"
    elif dev_attack_min >= ATTACK_FLOOR and dev_ood_max <= OOD_DIAGNOSTIC_TARGET:
        verdict = "decoupled_ood_risk_improves_frontier_needs_1pct_repair"
    elif dev_attack_min >= ATTACK_FLOOR and dev_ood_max < issue27bp_dev_ood and final_ood_max < issue27bp_final_ood:
        verdict = "decoupled_ood_risk_partial_pareto_improvement_but_ood_overbudget"
    elif dev_attack_min < ATTACK_FLOOR and dev_ood_max <= VAL_OOD_TARGET:
        verdict = "decoupled_ood_risk_still_attack_destructive"
    else:
        verdict = "decoupled_ood_risk_no_useful_improvement"
    next_action = "issue27br_strengthen_ood_risk_or_task_boundary_before_larger" if "ready_for_larger" not in verdict else "issue27br_larger_sanity_for_decoupled_ood_risk_controller"

    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "ood_risk_feature_schema.csv", feature_schema_rows)
    write_csv(OUT / "ood_risk_prototype_bank_audit.csv", bank_rows)
    write_csv(OUT / "ood_risk_training_set_audit.csv", train_audit_rows)
    write_csv(OUT / "ood_risk_candidate_grid.csv", candidate_rows)
    write_csv(OUT / "ood_risk_dev_summary.csv", summary)
    write_csv(OUT / "ood_risk_selection_audit.csv", [selected])
    write_csv(OUT / "controller_replay_by_role.csv", replay_rows)
    write_csv(OUT / "controller_replay_summary.csv", replay_summary)
    write_csv(OUT / "role_access_audit.csv", role_rows)
    write_csv(OUT / "attack_preservation_audit.csv", [r for r in replay_rows if "attack" in r["role"] or "future" in r["role"] or r["role"] == "support_val"])
    write_csv(OUT / "ood_false_alarm_reduction_audit.csv", [r for r in replay_rows if r["role"] in {"id_calib", "ood_val", "ood_stress_val", "final_ood_report_only"}])

    write_md(
        OUT / "decoupled_controller_spec.md",
        [
            "# Decoupled OOD-Risk Controller",
            "",
            "- The full-115D attack scorer and attack threshold stay frozen.",
            "- OOD-risk scoring is conditioned on raw attack alarms and uses only dev-side alarm examples for fit/selection.",
            "- Positive OOD-risk class: dev-side benign/OOD false alarms from id_calib, ood_val, and ood_stress_val.",
            "- Negative OOD-risk class: dev-side attack alarms from support_val and dev_future buckets.",
            "- Final OOD and report-only attack replay are not used to fit or select the risk scorer.",
            "",
            "Decision:",
            "",
            "```text",
            "if raw_attack_alarm is false: no_alarm",
            "elif ood_risk is high and attack evidence is weak: suppress",
            "elif ood_risk is high and attack evidence is strong: bounded review",
            "else: hard_alarm",
            "```",
        ],
    )
    write_md(
        OUT / "issue27bq_decision.md",
        [
            "# issue27bq Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            f"- selected risk model: `{selected['risk_model']}`",
            f"- selected risk threshold: `{selected['risk_threshold']}`",
            f"- dev attack min: `{dev_attack_min}`",
            f"- dev OOD hard max: `{dev_ood_max}`",
            f"- dev review max: `{dev_review_max}`",
            f"- report-only attack min: `{report_attack_min}`",
            f"- final OOD hard max report-only: `{final_ood_max}`",
            f"- issue27bp dev OOD hard max baseline: `{issue27bp_dev_ood}`",
            f"- issue27bp final OOD hard max baseline: `{issue27bp_final_ood}`",
        ],
    )
    write_md(
        OUT / "issue27br_next_action.md",
        [
            "# issue27br Next Action",
            "",
            f"recommended_next_action = `{next_action}`",
            "",
            "- If the decoupled OOD-risk scorer only partially improves the frontier, do not go full.",
            "- Next repair should either strengthen OOD-risk labels/features or run a task-boundary audit for OOD/attack overlap.",
            "- Keep final/report-only replay sealed.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27bq.md",
        [
            "# Claim Update After issue27bq",
            "",
            "- issue27bq is a medium diagnostic, not a formal benchmark.",
            "- A positive result can only support the decoupled-controller mechanism as a candidate for larger sanity.",
            "- A partial result still supports the paper problem framing: attack evidence and OOD-risk evidence must be modeled separately.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27bq Summary",
            "",
            "1. issue27bq completed: yes",
            f"2. primary_verdict: `{verdict}`",
            "3. task type: decoupled OOD-risk scorer diagnostic",
            "4. 115D frontend changed: no",
            "5. split/support changed: no",
            "6. raw attack scorer changed: no",
            "7. final/report-only used for risk fit/selection: no",
            f"8. selected risk model: `{selected['risk_model']}`",
            f"9. selected risk threshold: `{selected['risk_threshold']}`",
            f"10. dev attack min: `{dev_attack_min}`",
            f"11. dev OOD hard max: `{dev_ood_max}`",
            f"12. dev review max: `{dev_review_max}`",
            f"13. report-only attack min: `{report_attack_min}`",
            f"14. final OOD hard max report-only: `{final_ood_max}`",
            f"15. issue27bp dev OOD baseline: `{issue27bp_dev_ood}`",
            f"16. issue27bp final OOD baseline: `{issue27bp_final_ood}`",
            f"17. next action: `{next_action}`",
            "18. formal benchmark allowed: no",
            "19. commit hash: reported in final response",
        ],
    )

    (OUT / "config.json").write_text(
        json.dumps(
            {
                "issue": ISSUE,
                "primary_verdict": verdict,
                "selected": selected,
                "seeds": SEEDS,
                "risk_models": RISK_MODELS,
                "final_report_only_never_selects_risk_scorer": True,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "scope": "medium decoupled OOD-risk scorer diagnostic",
                "fit_roles": ["id_fit", "ood_train", "phase_balanced_support_train"],
                "attack_threshold_roles": ["id_calib"],
                "ood_risk_fit_selection_roles": ["raw_alarm_subset_of_id_calib", "ood_val", "ood_stress_val", "support_val", "dev_future_near", "dev_future_mid", "dev_future_far"],
                "report_only_roles": ["final_ood", "sealed_attack_replay"],
                "formal_benchmark": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    write_md(OUT / "command.txt", [f"python repo/ood/{Path(__file__).name}"])

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bq_decoupled_ood_risk -->",
        [
            "## issue27bq - decoupled OOD-risk scorer after attack recovery",
            "",
            "<!-- issue27bq_decoupled_ood_risk -->",
            f"- Verdict: `{verdict}`.",
            f"- Dev attack min: `{dev_attack_min}`; dev OOD hard max: `{dev_ood_max}`; dev review max: `{dev_review_max}`.",
            f"- Report-only attack min: `{report_attack_min}`; final OOD hard max report-only: `{final_ood_max}`.",
            "- Raw full-115D attack scorer, split, and support contract remained frozen.",
            "- Final/report-only roles were replay-only.",
            f"- Next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bq_decoupled_ood_risk -->",
        [
            "## issue27bq - decoupled OOD-risk scorer diagnostic",
            "",
            "<!-- issue27bq_decoupled_ood_risk -->",
            f"- Primary verdict: `{verdict}`.",
            "- Stage: medium diagnostic; no full/formal benchmark.",
            "- Purpose: test whether alarm-conditioned OOD-risk scoring improves the attack/OOD frontier.",
        ],
    )

    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(
        json.dumps(
            {
                "primary_verdict": verdict,
                "dev_attack_min": dev_attack_min,
                "dev_ood_max": dev_ood_max,
                "final_ood_max": final_ood_max,
                "report_attack_min": report_attack_min,
                "selected": selected,
                "out": str(OUT),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
