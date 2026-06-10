from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au
import issue27ba_disjoint_ood_stress_pool_before_mixed_stream as ba
import issue27bo_attack_future_shift_validation_without_new_support as bo
import issue27bp_attack_preserving_ood_gate_repair_after_future_shift_validation as bp
import issue27bq_decoupled_ood_risk_scorer_after_attack_recovery as bq


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27br_past_only_temporal_interaction_evidence_feasibility_2026-06-10"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BA = ROOT / "runs" / "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"
ISSUE27BM = ROOT / "runs" / "issue27bm_phase_balanced_attack_contract_design_without_report_only_leakage_2026-06-08"
ISSUE27BQ = ROOT / "runs" / "issue27bq_decoupled_ood_risk_scorer_after_attack_recovery_2026-06-09"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
WINDOWS = [8, 32, 128]

VAL_OOD_TARGET = 0.01
OOD_DIAGNOSTIC_TARGET = 0.05
ATTACK_FLOOR = 0.93


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


def rate(mask: np.ndarray | pd.Series) -> float:
    arr = np.asarray(mask)
    if arr.size == 0:
        return float("nan")
    return float(np.mean(arr.astype(bool)))


def parse_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return float("nan")


def parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def qstats(vals: np.ndarray | pd.Series) -> dict[str, float]:
    arr = np.asarray(vals, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {k: float("nan") for k in ["min", "p50", "p90", "p95", "p99", "max", "mean"]}
    return {
        "min": float(np.min(arr)),
        "p50": float(np.quantile(arr, 0.50)),
        "p90": float(np.quantile(arr, 0.90)),
        "p95": float(np.quantile(arr, 0.95)),
        "p99": float(np.quantile(arr, 0.99)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
    }


def device_from_record(record: dict[str, Any]) -> str:
    if record.get("device_hint"):
        return str(record["device_hint"])
    path = str(record.get("csv_member") or record.get("pcap_member") or "")
    return bo.device_hint_from_file(path) if path else "unknown"


def sidecar_records(sidecar: list[dict[str, str]], indices: np.ndarray, source_asset: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in np.asarray(indices, dtype=np.int64).tolist():
        row = dict(sidecar[int(i)])
        row["global_id"] = f"{source_asset}:{int(i)}"
        row["source_asset"] = source_asset
        row["source_index"] = int(i)
        row["device_hint"] = device_from_record(row)
        row["phase_bucket"] = bo.phase_bucket(parse_int(row.get("recorded_index")))
        row["attack_type"] = row.get("attack_type_from_raw_path") or row.get("attack_type") or "benign"
        out.append(row)
    return out


def role_type(role: str) -> str:
    if role in {"id_calib", "ood_val", "ood_stress_val"}:
        return "dev_benign_ood"
    if role == "final_ood_report_only":
        return "report_only_benign_ood"
    if role in {"support_val", "dev_future_near", "dev_future_mid", "dev_future_far"}:
        return "dev_attack"
    if role.startswith("sealed_") or "attack_eval_report_only" in role:
        return "report_only_attack"
    return "unknown"


def role_is_report_only(role: str) -> bool:
    return role.startswith("sealed_") or role.endswith("report_only") or role == "final_ood_report_only"


def build_base_context() -> dict[str, Any]:
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

    role_x_extra, _, role_records_extra = bp.role_records_and_features(
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
    role_x = {
        "id_calib": x[id_calib],
        "ood_val": x[ood_val],
        "ood_stress_val": stress_x[stress_val],
        "support_val": x_support_val,
        "dev_future_near": role_x_extra["dev_future_near"],
        "dev_future_mid": role_x_extra["dev_future_mid"],
        "dev_future_far": role_x_extra["dev_future_far"],
        "sealed_medium_attack_eval_report_only": role_x_extra["sealed_medium_attack_eval_report_only"],
        "sealed_dev_heavy_query_report_only": role_x_extra["sealed_dev_heavy_query_report_only"],
        "sealed_heavy_future_near": role_x_extra["sealed_heavy_future_near"],
        "sealed_heavy_future_mid": role_x_extra["sealed_heavy_future_mid"],
        "sealed_heavy_future_far": role_x_extra["sealed_heavy_future_far"],
        "final_ood_report_only": x[final_ood_idx],
    }
    role_records = {
        "id_calib": sidecar_records(sidecar, id_calib, "medium_id_calib"),
        "ood_val": sidecar_records(sidecar, ood_val, "medium_ood_val"),
        "ood_stress_val": sidecar_records(stress_sidecar, stress_val, "ood_stress_val"),
        "support_val": bo.make_contract_records(support_val_rows),
        "final_ood_report_only": sidecar_records(sidecar, final_ood_idx, "medium_final_ood_report_only"),
    }
    for role in [
        "dev_future_near",
        "dev_future_mid",
        "dev_future_far",
        "sealed_medium_attack_eval_report_only",
        "sealed_dev_heavy_query_report_only",
        "sealed_heavy_future_near",
        "sealed_heavy_future_mid",
        "sealed_heavy_future_far",
    ]:
        role_records[role] = role_records_extra[role]

    selected = json.loads((ISSUE27BQ / "config.json").read_text(encoding="utf-8"))["selected"]
    input_rows = [
        {"artifact": "issue27af_medium_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path), "used_for": "fixed_medium_asset"},
        {"artifact": "issue27ba_ood_stress_certificate", "path": str(stress_cert_path), "sha256": sha256_file(stress_cert_path), "used_for": "dev_ood_stress_asset"},
        {"artifact": "issue27bm_phase_balanced_contract", "path": str(ISSUE27BM / "phase_balanced_contract_v2.json"), "sha256": sha256_file(ISSUE27BM / "phase_balanced_contract_v2.json"), "used_for": "fixed_support_contract"},
        {"artifact": "issue27bq_config", "path": str(ISSUE27BQ / "config.json"), "sha256": sha256_file(ISSUE27BQ / "config.json"), "used_for": "frozen_decoupled_ood_risk_candidate"},
    ]
    for check in checks + stress_checks + new_checks:
        input_rows.append({**check, "used_for": "hash_validation"})

    return {
        "x": x,
        "sidecar": sidecar,
        "stress_x": stress_x,
        "stress_sidecar": stress_sidecar,
        "new_x": new_x,
        "new_sidecar": new_sidecar,
        "subspaces": subspaces,
        "role_x": role_x,
        "role_records": role_records,
        "selected": selected,
        "id_fit": id_fit,
        "id_calib": id_calib,
        "ood_train": ood_train,
        "ood_val": ood_val,
        "stress_train": stress_train,
        "stress_val": stress_val,
        "x_support_train": x_support_train,
        "x_support_val": x_support_val,
        "x_pseudo": x_pseudo,
        "input_rows": input_rows,
    }


def fit_bq_seed(ctx: dict[str, Any], seed: int) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    x = ctx["x"]
    stress_x = ctx["stress_x"]
    subspaces = ctx["subspaces"]
    selected = ctx["selected"]
    role_x = ctx["role_x"]

    attack_model = bo.FrozenAttackHistGB(seed)
    attack_model.fit(x[ctx["id_fit"]], x[ctx["ood_train"]], ctx["x_support_train"])
    attack_threshold = float(np.quantile(attack_model.score(x[ctx["id_calib"]]), 0.99))

    banks, _audit = bq.build_evidence_banks(
        x,
        stress_x,
        ctx["x_support_train"],
        ctx["x_support_val"],
        ctx["x_pseudo"],
        ctx["id_fit"],
        ctx["id_calib"],
        ctx["ood_train"],
        ctx["ood_val"],
        ctx["stress_train"],
        ctx["stress_val"],
        subspaces,
    )
    dev_roles = ["id_calib", "ood_val", "ood_stress_val", "support_val", "dev_future_near", "dev_future_mid", "dev_future_far"]
    feat_dev: dict[str, np.ndarray] = {}
    aux_dev: dict[str, dict[str, np.ndarray]] = {}
    for role in dev_roles:
        score = attack_model.score(role_x[role])
        feat, _names, aux = bq.evidence_features(role_x[role], score, attack_threshold, banks, subspaces)
        feat_dev[role] = feat
        aux_dev[role] = aux

    pos_roles = ["id_calib", "ood_val", "ood_stress_val"]
    neg_roles = ["support_val", "dev_future_near", "dev_future_mid", "dev_future_far"]
    x_train_parts, y_train_parts = [], []
    for role, label in [(r, 1) for r in pos_roles] + [(r, 0) for r in neg_roles]:
        alarm_idx = np.flatnonzero(aux_dev[role]["raw_alarm"])
        first, _second = bq.deterministic_half(alarm_idx.size)
        idx = alarm_idx[first]
        x_train_parts.append(feat_dev[role][idx])
        y_train_parts.append(np.full(len(idx), label, dtype=np.int8))
    risk_model = bq.fit_risk_model(str(selected["risk_model"]), np.vstack(x_train_parts), np.concatenate(y_train_parts), seed)

    margin_source = np.concatenate([aux_dev[r]["margin"][aux_dev[r]["raw_alarm"]] for r in neg_roles])
    margin_source = margin_source[np.isfinite(margin_source)]
    params = {
        "risk_threshold": float(selected["risk_threshold"]),
        "strong_margin_floor": float(np.quantile(margin_source, float(selected["strong_margin_q"]))),
        "weak_margin_ceiling": float(np.quantile(margin_source, 0.25)),
        "attack_outer_norm": float(selected["attack_outer_norm"]),
        "review_budget": float(selected["review_budget"]),
    }

    out: dict[str, dict[str, Any]] = {}
    row_records: list[dict[str, Any]] = []
    for role, rx in role_x.items():
        score = attack_model.score(rx)
        feat, _names, aux = bq.evidence_features(rx, score, attack_threshold, banks, subspaces)
        risk = bq.risk_score(risk_model, feat)
        masks = bq.apply_controller(aux["raw_alarm"], aux["margin"], aux["d_attack_outer_min"], risk, params)
        out[role] = {"score": score, "risk": risk, "aux": aux, "masks": masks}
        records = ctx["role_records"][role]
        if len(records) != len(rx):
            raise RuntimeError(f"record/feature row mismatch for {role}: {len(records)} vs {len(rx)}")
        for i, record in enumerate(records):
            row_records.append(
                {
                    "seed": seed,
                    "role": role,
                    "role_type": role_type(role),
                    "is_report_only": role_is_report_only(role),
                    "row_position": i,
                    "source_asset": record.get("source_asset", "unknown"),
                    "source_index": parse_int(record.get("source_index", i), i),
                    "global_id": record.get("global_id", f"{role}:{i}"),
                    "csv_member": record.get("csv_member", ""),
                    "pcap_member": record.get("pcap_member", ""),
                    "state_id": record.get("state_id", ""),
                    "source_group": record.get("csv_member") or record.get("pcap_member") or role,
                    "device_hint": device_from_record(record),
                    "attack_type": record.get("attack_type") or record.get("attack_type_from_raw_path") or "benign",
                    "phase_bucket": record.get("phase_bucket") or bo.phase_bucket(parse_int(record.get("recorded_index"))),
                    "recorded_index": parse_int(record.get("recorded_index"), i),
                    "packet_index": parse_int(record.get("packet_index"), i),
                    "packet_timestamp_epoch": parse_float(record.get("packet_timestamp_epoch")),
                    "warmup_only": str(record.get("warmup_only", "")).lower() == "true",
                    "raw_alarm": bool(masks["raw_alarm"][i]),
                    "hard_alarm": bool(masks["hard_alarm"][i]),
                    "review": bool(masks["review"][i]),
                    "suppress": bool(masks["suppress"][i]),
                    "strong_attack": bool(masks["strong_attack"][i]),
                    "high_ood_risk": bool(masks["high_ood_risk"][i]),
                    "weak_attack": bool(masks["weak_attack"][i]),
                    "conflict": bool(masks["conflict"][i]),
                    "attack_score": float(score[i]),
                    "attack_margin": float(aux["margin"][i]),
                    "ood_risk": float(risk[i]),
                    "d_attack_outer_min": float(aux["d_attack_outer_min"][i]),
                    "d_benign_core_min": float(aux["d_benign_core_min"][i]),
                    "benign_minus_attack_distance": float(aux["benign_minus_attack_distance"][i]),
                }
            )
    return out, row_records, params


def add_group_temporal_features(df: pd.DataFrame, group_cols: list[str], prefix: str) -> pd.DataFrame:
    out = pd.Series(index=df.index, dtype=np.float64)
    df = df.sort_values(group_cols + ["packet_timestamp_epoch", "recorded_index", "row_position"], kind="mergesort")
    grouped = df.groupby(group_cols, sort=False, dropna=False)
    for w in WINDOWS:
        for col in ["raw_alarm", "hard_alarm", "suppress", "high_ood_risk", "strong_attack"]:
            name = f"{prefix}_{col}_rate_w{w}"
            df[name] = grouped[col].transform(lambda s: s.astype(float).shift(1).rolling(w, min_periods=1).mean()).fillna(0.0)
        for col in ["attack_margin", "ood_risk", "d_attack_outer_min", "d_benign_core_min"]:
            name = f"{prefix}_{col}_mean_w{w}"
            df[name] = grouped[col].transform(lambda s: s.astype(float).shift(1).rolling(w, min_periods=1).mean()).fillna(0.0)
    run_values = []
    for _key, g in grouped:
        run = 0
        vals = []
        for raw in g["raw_alarm"].astype(bool).tolist():
            vals.append(run)
            run = run + 1 if raw else 0
        run_values.extend(zip(g.index.tolist(), vals))
    run_series = pd.Series({idx: val for idx, val in run_values})
    df[f"{prefix}_raw_alarm_run_before"] = run_series.reindex(df.index).fillna(0).astype(int)
    return df


def build_temporal_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["packet_timestamp_epoch"] = pd.to_numeric(df["packet_timestamp_epoch"], errors="coerce")
    for col in ["raw_alarm", "hard_alarm", "suppress", "high_ood_risk", "strong_attack", "weak_attack", "conflict", "is_report_only"]:
        df[col] = df[col].astype(bool)
    df = add_group_temporal_features(df, ["seed", "role"], "past_role")
    df = add_group_temporal_features(df, ["seed", "role", "source_group"], "past_source")
    return df.sort_values(["seed", "role", "source_group", "packet_timestamp_epoch", "recorded_index", "row_position"], kind="mergesort").reset_index(drop=True)


def summarize_by_role(df: pd.DataFrame, hard_col: str = "hard_alarm", review_col: str = "review", suppress_col: str = "suppress") -> list[dict[str, Any]]:
    rows = []
    for (seed, role), g in df.groupby(["seed", "role"], sort=True):
        rows.append(
            {
                "seed": int(seed),
                "role": role,
                "role_type": role_type(role),
                "is_report_only": bool(g["is_report_only"].iloc[0]),
                "n": int(len(g)),
                "raw_alarm_rate": rate(g["raw_alarm"]),
                "hard_alarm_rate": rate(g[hard_col]),
                "review_rate": rate(g[review_col]),
                "suppress_rate": rate(g[suppress_col]),
                "high_ood_risk_rate": rate(g["high_ood_risk"]),
                "attack_margin_p50": qstats(g["attack_margin"])["p50"],
                "ood_risk_p50": qstats(g["ood_risk"])["p50"],
                "past_source_raw_alarm_rate_w32_p50": qstats(g["past_source_raw_alarm_rate_w32"])["p50"],
                "past_source_raw_alarm_rate_w32_p95": qstats(g["past_source_raw_alarm_rate_w32"])["p95"],
            }
        )
    return rows


def aggregate_role_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(rows)
    out = []
    for (role, is_report_only), g in df.groupby(["role", "is_report_only"], sort=True):
        row = {"role": role, "is_report_only": bool(is_report_only), "seeds": int(len(g))}
        for metric in ["raw_alarm_rate", "hard_alarm_rate", "review_rate", "suppress_rate", "high_ood_risk_rate"]:
            vals = g[metric].astype(float)
            row[f"{metric}_mean"] = float(vals.mean())
            row[f"{metric}_min"] = float(vals.min())
            row[f"{metric}_max"] = float(vals.max())
        out.append(row)
    return out


def group_label(row: pd.Series) -> str:
    if row["role_type"] == "dev_benign_ood" and row["suppress"]:
        return "dev_ood_suppressed"
    if row["role_type"] == "report_only_benign_ood" and row["suppress"]:
        return "report_only_ood_suppressed"
    if row["role_type"] == "dev_attack" and row["suppress"]:
        return "dev_attack_suppressed"
    if row["role_type"] == "report_only_attack" and row["suppress"]:
        return "report_only_attack_suppressed"
    if row["role_type"] == "dev_attack" and row["hard_alarm"]:
        return "dev_attack_hard"
    if row["role_type"] == "report_only_attack" and row["hard_alarm"]:
        return "report_only_attack_hard"
    return "other"


def temporal_signal_audit(df: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    feature_cols = [
        "past_role_raw_alarm_rate_w8",
        "past_role_raw_alarm_rate_w32",
        "past_role_raw_alarm_rate_w128",
        "past_source_raw_alarm_rate_w8",
        "past_source_raw_alarm_rate_w32",
        "past_source_raw_alarm_rate_w128",
        "past_source_attack_margin_mean_w32",
        "past_source_ood_risk_mean_w32",
        "past_source_d_attack_outer_min_mean_w32",
        "past_source_d_benign_core_min_mean_w32",
        "past_source_raw_alarm_run_before",
    ]
    x = df.copy()
    x["diagnostic_group"] = x.apply(group_label, axis=1)
    summary_rows = []
    for (role_type_name, diag), g in x.groupby(["role_type", "diagnostic_group"], sort=True):
        if diag == "other":
            continue
        row = {"role_type": role_type_name, "diagnostic_group": diag, "n": int(len(g))}
        for col in feature_cols:
            stats = qstats(g[col])
            row[f"{col}_p50"] = stats["p50"]
            row[f"{col}_p95"] = stats["p95"]
        summary_rows.append(row)

    sep_rows = []
    comparisons = [
        ("suppressed_report_attack_vs_suppressed_dev_ood", "report_only_attack_suppressed", "dev_ood_suppressed"),
        ("suppressed_report_attack_vs_suppressed_final_ood", "report_only_attack_suppressed", "report_only_ood_suppressed"),
        ("hard_report_attack_vs_suppressed_final_ood", "report_only_attack_hard", "report_only_ood_suppressed"),
    ]
    for name, pos, neg in comparisons:
        sub = x[x["diagnostic_group"].isin([pos, neg])].copy()
        if sub["diagnostic_group"].nunique() < 2:
            continue
        y = (sub["diagnostic_group"] == pos).astype(int).to_numpy()
        for col in feature_cols:
            vals = sub[col].astype(float).to_numpy()
            try:
                auc = float(roc_auc_score(y, vals))
            except Exception:
                auc = float("nan")
            sep_rows.append(
                {
                    "comparison": name,
                    "feature": col,
                    "auc_pos_higher": auc,
                    "auc_abs": max(auc, 1.0 - auc) if np.isfinite(auc) else float("nan"),
                    "pos_group": pos,
                    "neg_group": neg,
                    "pos_n": int(np.sum(y == 1)),
                    "neg_n": int(np.sum(y == 0)),
                }
            )
    return summary_rows, sep_rows


def evaluate_temporal_candidates(df: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], pd.DataFrame]:
    dev_df = df[~df["is_report_only"]].copy()
    attack_dev = dev_df[dev_df["role_type"] == "dev_attack"]
    # Threshold candidates are dev-only. They are intentionally simple and
    # past-only; report-only rows are replayed after selection.
    margin_thresholds = [float(np.quantile(attack_dev["past_source_attack_margin_mean_w32"], q)) for q in [0.25, 0.50, 0.75]]
    raw_rate_thresholds = [0.0, 0.05, 0.10, 0.25, 0.50]
    d_attack_thresholds = [0.75, 1.00, 1.25, 1.50]
    candidate_rows: list[dict[str, Any]] = []
    role_rows_all: list[dict[str, Any]] = []
    for raw_thr in raw_rate_thresholds:
        for margin_thr in margin_thresholds:
            for d_thr in d_attack_thresholds:
                tmp = df.copy()
                protect = (
                    tmp["suppress"]
                    & tmp["raw_alarm"]
                    & (tmp["past_source_raw_alarm_rate_w32"] >= raw_thr)
                    & (tmp["past_source_attack_margin_mean_w32"] >= margin_thr)
                    & (tmp["past_source_d_attack_outer_min_mean_w32"] <= d_thr)
                )
                tmp["temporal_override"] = protect
                tmp["temporal_hard"] = tmp["hard_alarm"] | protect
                tmp["temporal_suppress"] = tmp["suppress"] & (~protect)
                tmp["temporal_review"] = tmp["review"]
                role_rows = summarize_by_role(tmp, "temporal_hard", "temporal_review", "temporal_suppress")
                for row in role_rows:
                    role_rows_all.append(
                        {
                            "raw_rate_thr": raw_thr,
                            "margin_thr": margin_thr,
                            "d_attack_thr": d_thr,
                            **row,
                        }
                    )
                rdf = pd.DataFrame(role_rows)
                def metric(role: str, metric_name: str, agg: str) -> float:
                    vals = rdf[rdf["role"] == role][metric_name].astype(float)
                    if vals.empty:
                        return float("nan")
                    return float(vals.min() if agg == "min" else vals.max())
                dev_attack_min = min(
                    metric("support_val", "hard_alarm_rate", "min"),
                    metric("dev_future_near", "hard_alarm_rate", "min"),
                    metric("dev_future_mid", "hard_alarm_rate", "min"),
                    metric("dev_future_far", "hard_alarm_rate", "min"),
                )
                dev_ood_max = max(
                    metric("id_calib", "hard_alarm_rate", "max"),
                    metric("ood_val", "hard_alarm_rate", "max"),
                    metric("ood_stress_val", "hard_alarm_rate", "max"),
                )
                dev_review_max = max(
                    metric("id_calib", "review_rate", "max"),
                    metric("ood_val", "review_rate", "max"),
                    metric("ood_stress_val", "review_rate", "max"),
                )
                candidate_rows.append(
                    {
                        "raw_rate_thr": raw_thr,
                        "margin_thr": margin_thr,
                        "d_attack_thr": d_thr,
                        "dev_attack_min": dev_attack_min,
                        "dev_ood_max": dev_ood_max,
                        "dev_review_max": dev_review_max,
                        "feasible_1pct": dev_attack_min >= ATTACK_FLOOR and dev_ood_max <= VAL_OOD_TARGET,
                        "feasible_5pct": dev_attack_min >= ATTACK_FLOOR and dev_ood_max <= OOD_DIAGNOSTIC_TARGET,
                        "selection_uses_final_ood": False,
                        "selection_uses_report_only_attack": False,
                        "dev_score": dev_attack_min - 1.5 * dev_ood_max - dev_review_max,
                    }
                )
    pool = candidate_rows
    feasible = [r for r in pool if r["feasible_1pct"]]
    if not feasible:
        feasible = [r for r in pool if r["feasible_5pct"]]
    select_pool = feasible if feasible else pool
    selected = max(select_pool, key=lambda r: (r["feasible_1pct"], r["feasible_5pct"], r["dev_attack_min"], -r["dev_ood_max"], r["dev_score"]))

    replay = df.copy()
    protect = (
        replay["suppress"]
        & replay["raw_alarm"]
        & (replay["past_source_raw_alarm_rate_w32"] >= float(selected["raw_rate_thr"]))
        & (replay["past_source_attack_margin_mean_w32"] >= float(selected["margin_thr"]))
        & (replay["past_source_d_attack_outer_min_mean_w32"] <= float(selected["d_attack_thr"]))
    )
    replay["temporal_override"] = protect
    replay["temporal_hard"] = replay["hard_alarm"] | protect
    replay["temporal_suppress"] = replay["suppress"] & (~protect)
    replay["temporal_review"] = replay["review"]
    return candidate_rows, role_rows_all, selected, replay


def compute_key_metrics(replay_summary: list[dict[str, Any]]) -> dict[str, float]:
    df = pd.DataFrame(replay_summary)
    def get(role: str, metric: str, agg: str) -> float:
        vals = df[df["role"] == role][metric].astype(float)
        if vals.empty:
            return float("nan")
        return float(vals.min() if agg == "min" else vals.max())
    return {
        "dev_attack_min": min(
            get("support_val", "hard_alarm_rate", "min"),
            get("dev_future_near", "hard_alarm_rate", "min"),
            get("dev_future_mid", "hard_alarm_rate", "min"),
            get("dev_future_far", "hard_alarm_rate", "min"),
        ),
        "dev_ood_max": max(
            get("id_calib", "hard_alarm_rate", "max"),
            get("ood_val", "hard_alarm_rate", "max"),
            get("ood_stress_val", "hard_alarm_rate", "max"),
        ),
        "report_attack_min": min(
            get("sealed_medium_attack_eval_report_only", "hard_alarm_rate", "min"),
            get("sealed_dev_heavy_query_report_only", "hard_alarm_rate", "min"),
            get("sealed_heavy_future_near", "hard_alarm_rate", "min"),
            get("sealed_heavy_future_mid", "hard_alarm_rate", "min"),
            get("sealed_heavy_future_far", "hard_alarm_rate", "min"),
        ),
        "final_ood_max": get("final_ood_report_only", "hard_alarm_rate", "max"),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = build_base_context()

    all_rows: list[dict[str, Any]] = []
    params_rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        _role_out, seed_rows, params = fit_bq_seed(ctx, seed)
        all_rows.extend(seed_rows)
        params_rows.append({"seed": seed, **params})
    df = build_temporal_frame(all_rows)

    field_rows = [
        {"field": "state_id", "available": True, "use": "past-only state/source ordering"},
        {"field": "csv_member", "available": True, "use": "source_group proxy"},
        {"field": "pcap_member", "available": True, "use": "source_group fallback"},
        {"field": "recorded_index", "available": True, "use": "within-source packet order"},
        {"field": "packet_timestamp_epoch", "available": True, "use": "past-only ordering"},
        {"field": "ip.src/ip.dst", "available": False, "use": "not available in materialized sidecar; no full flow graph this round"},
        {"field": "ports/protocol", "available": False, "use": "not available in materialized sidecar; no HyperVision-style graph this round"},
    ]

    base_role_rows = summarize_by_role(df)
    base_summary = aggregate_role_summary(base_role_rows)
    base_metrics = compute_key_metrics(base_role_rows)
    signal_summary, separability_rows = temporal_signal_audit(df)

    candidate_rows, candidate_role_rows, selected, temporal_df = evaluate_temporal_candidates(df)
    temporal_role_rows = summarize_by_role(temporal_df, "temporal_hard", "temporal_review", "temporal_suppress")
    temporal_summary = aggregate_role_summary(temporal_role_rows)
    temporal_metrics = compute_key_metrics(temporal_role_rows)

    # Report-only temporal replay is after dev-only selection; it is not used to
    # choose the thresholds above.
    report_only_replay = [
        row for row in temporal_role_rows if row["is_report_only"]
    ]
    false_suppressed = df[(df["suppress"]) & (df["role_type"].isin(["dev_attack", "report_only_attack", "dev_benign_ood", "report_only_benign_ood"]))]
    false_rows = []
    for (role, seed), g in false_suppressed.groupby(["role", "seed"], sort=True):
        row = {"seed": int(seed), "role": role, "role_type": role_type(role), "n_suppressed": int(len(g))}
        for col in ["past_source_raw_alarm_rate_w32", "past_source_attack_margin_mean_w32", "past_source_d_attack_outer_min_mean_w32", "past_source_raw_alarm_run_before"]:
            stats = qstats(g[col])
            row[f"{col}_p50"] = stats["p50"]
            row[f"{col}_p95"] = stats["p95"]
        false_rows.append(row)

    role_access_rows = [
        {
            "component": "bq_base_attack_scorer_and_ood_risk",
            "fit_roles": "id_fit|ood_train|phase_balanced_support_train|raw_alarm_subset_of_id_calib|ood_val|ood_stress_val|support_val|dev_future_near|dev_future_mid|dev_future_far",
            "selection_roles": "id_calib|ood_val|ood_stress_val|support_val|dev_future_near|dev_future_mid|dev_future_far",
            "score_replay_roles": "|".join(sorted(ctx["role_x"].keys())),
            "uses_final_ood_for_fit_or_selection": False,
            "uses_report_only_attack_for_fit_or_selection": False,
        },
        {
            "component": "issue27br_past_only_temporal_candidate_selection",
            "fit_roles": "none",
            "selection_roles": "id_calib|ood_val|ood_stress_val|support_val|dev_future_near|dev_future_mid|dev_future_far",
            "score_replay_roles": "|".join(sorted(ctx["role_x"].keys())),
            "uses_final_ood_for_fit_or_selection": False,
            "uses_report_only_attack_for_fit_or_selection": False,
        },
    ]

    best_auc = max([float(r["auc_abs"]) for r in separability_rows if np.isfinite(float(r["auc_abs"]))] or [float("nan")])
    report_gain = temporal_metrics["report_attack_min"] - base_metrics["report_attack_min"]
    dev_ood_delta = temporal_metrics["dev_ood_max"] - base_metrics["dev_ood_max"]
    if temporal_metrics["dev_attack_min"] >= ATTACK_FLOOR and temporal_metrics["dev_ood_max"] <= VAL_OOD_TARGET:
        verdict = "past_only_temporal_controller_dev_passed_ready_for_ood_gate_recheck"
    elif report_gain > 0.05 and dev_ood_delta <= 0.10:
        verdict = "temporal_interaction_evidence_promising_needs_controller_repair"
    elif np.isfinite(best_auc) and best_auc >= 0.70:
        verdict = "past_only_temporal_signal_present_needs_mini_interaction_graph"
    elif temporal_metrics["dev_ood_max"] > base_metrics["dev_ood_max"] + 0.10:
        verdict = "temporal_controller_attack_restoration_ood_overbudget"
    else:
        verdict = "past_only_temporal_evidence_insufficient_need_mini_interaction_graph"

    next_action = "issue27bs_mini_interaction_graph_or_temporal_controller_repair_without_final_leakage"

    write_csv(OUT / "input_artifact_hash_audit.csv", ctx["input_rows"])
    write_csv(OUT / "temporal_field_availability.csv", field_rows)
    write_csv(OUT / "bq_selected_controller_params_by_seed.csv", params_rows)
    write_csv(OUT / "bq_base_temporal_replay_summary.csv", base_summary)
    write_csv(OUT / "false_suppressed_attack_temporal_audit.csv", false_rows)
    write_csv(OUT / "temporal_signal_audit.csv", signal_summary)
    write_csv(OUT / "temporal_feature_separability.csv", separability_rows)
    write_csv(OUT / "temporal_controller_candidate_grid.csv", candidate_rows)
    write_csv(OUT / "temporal_controller_candidate_by_role.csv", candidate_role_rows)
    write_csv(OUT / "temporal_controller_selection_audit.csv", [selected])
    write_csv(OUT / "temporal_controller_replay_summary.csv", temporal_summary)
    write_csv(OUT / "temporal_controller_report_only_replay.csv", report_only_replay)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)

    write_md(
        OUT / "past_only_temporal_feature_spec.md",
        [
            "# Past-Only Temporal Feature Spec",
            "",
            "- Scope: diagnostic/controller feasibility only; no 115D frontend changes.",
            "- Ordering key: `packet_timestamp_epoch`, then `recorded_index`, then materialized row position.",
            "- Grouping: role-level and source-group-level (`csv_member`/`pcap_member`) past windows.",
            "- Windows: 8, 32, 128 previous rows.",
            "- Every rolling feature uses `shift(1)` before the rolling computation, so the current row and future rows are never included.",
            "- Available interaction evidence is limited to source/file/state metadata; no IP/port/flow graph fields are present in the current sidecar.",
            "- Report-only roles are replayed only after dev-side temporal thresholds are selected.",
        ],
    )
    write_md(
        OUT / "issue27br_decision.md",
        [
            "# issue27br Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            f"- bq base dev attack min: `{base_metrics['dev_attack_min']}`",
            f"- bq base dev OOD max: `{base_metrics['dev_ood_max']}`",
            f"- bq base report-only attack min: `{base_metrics['report_attack_min']}`",
            f"- bq base final OOD max report-only: `{base_metrics['final_ood_max']}`",
            f"- temporal selected raw_rate_thr: `{selected['raw_rate_thr']}`",
            f"- temporal selected margin_thr: `{selected['margin_thr']}`",
            f"- temporal selected d_attack_thr: `{selected['d_attack_thr']}`",
            f"- temporal dev attack min: `{temporal_metrics['dev_attack_min']}`",
            f"- temporal dev OOD max: `{temporal_metrics['dev_ood_max']}`",
            f"- temporal report-only attack min: `{temporal_metrics['report_attack_min']}`",
            f"- temporal final OOD max report-only: `{temporal_metrics['final_ood_max']}`",
            f"- best temporal separability AUC(abs): `{best_auc}`",
            "- Interpretation: this is a past-only feasibility diagnostic, not a formal benchmark.",
        ],
    )
    write_md(
        OUT / "issue27bs_next_action.md",
        [
            "# issue27bs Next Action",
            "",
            f"recommended_next_action = `{next_action}`",
            "",
            "- If past-only temporal features have signal but the controller remains overbudget, test a controller repair with bounded review and sealed final replay.",
            "- If temporal signal is weak because sidecar lacks flow fields, build a mini interaction-graph diagnostic from PCAP/sidecar metadata before rejecting the graph route.",
            "- Do not move to full/formal benchmark until attack evidence and OOD-risk are both stable under dev-side constraints.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27br.md",
        [
            "# Claim Update After issue27br",
            "",
            "- issue27br only tests whether past-only temporal/source evidence is available and useful as an auxiliary signal.",
            "- It cannot prove graph/causal detection, because current materialized sidecar lacks IP/port/flow interaction fields.",
            "- It preserves final/report-only independence: final OOD and sealed attack replay do not select temporal thresholds.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27br Summary",
            "",
            "1. issue27br completed: yes",
            f"2. primary_verdict: `{verdict}`",
            "3. task type: past-only temporal/interaction evidence feasibility diagnostic",
            "4. 115D frontend changed: no",
            "5. split/support changed: no",
            "6. final/report-only used for temporal fit/selection: no",
            "7. full flow graph built: no; sidecar lacks IP/port/flow interaction fields",
            f"8. bq base dev attack min: `{base_metrics['dev_attack_min']}`",
            f"9. bq base dev OOD max: `{base_metrics['dev_ood_max']}`",
            f"10. bq base report-only attack min: `{base_metrics['report_attack_min']}`",
            f"11. bq base final OOD max report-only: `{base_metrics['final_ood_max']}`",
            f"12. temporal dev attack min: `{temporal_metrics['dev_attack_min']}`",
            f"13. temporal dev OOD max: `{temporal_metrics['dev_ood_max']}`",
            f"14. temporal report-only attack min: `{temporal_metrics['report_attack_min']}`",
            f"15. temporal final OOD max report-only: `{temporal_metrics['final_ood_max']}`",
            f"16. best temporal separability AUC(abs): `{best_auc}`",
            f"17. next action: `{next_action}`",
            "18. formal benchmark allowed: no",
            "19. commit hash: reported in final response",
        ],
    )
    write_md(OUT / "command.txt", [f"python repo/ood/{Path(__file__).name}"])
    (OUT / "config.json").write_text(
        json.dumps(
            {
                "issue": ISSUE,
                "primary_verdict": verdict,
                "seeds": SEEDS,
                "windows": WINDOWS,
                "selected_temporal_candidate": selected,
                "final_report_only_never_selects_temporal_thresholds": True,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "scope": "past-only temporal/source evidence diagnostic",
                "fixed_parent": "issue27bq selected decoupled OOD-risk controller",
                "selection_roles": ["id_calib", "ood_val", "ood_stress_val", "support_val", "dev_future_near", "dev_future_mid", "dev_future_far"],
                "report_only_roles": ["final_ood_report_only", "sealed_medium_attack_eval_report_only", "sealed_dev_heavy_query_report_only", "sealed_heavy_future_near", "sealed_heavy_future_mid", "sealed_heavy_future_far"],
                "formal_benchmark": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27br_past_only_temporal_interaction -->",
        [
            "## issue27br - past-only temporal/interaction evidence feasibility",
            "",
            "<!-- issue27br_past_only_temporal_interaction -->",
            f"- Verdict: `{verdict}`.",
            "- Scope: medium diagnostic; no full/formal benchmark; no 115D frontend or split/support change.",
            "- Temporal features use past-only role/source windows with `shift(1)`; final/report-only replay is not used for selection.",
            "- Current sidecar supports timestamp/source/state ordering but not full IP/port flow graph construction.",
            f"- BQ base report-only attack min: `{base_metrics['report_attack_min']}`; temporal report-only attack min: `{temporal_metrics['report_attack_min']}`.",
            f"- BQ base dev OOD max: `{base_metrics['dev_ood_max']}`; temporal dev OOD max: `{temporal_metrics['dev_ood_max']}`.",
            f"- Next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27br_past_only_temporal_interaction -->",
        [
            "## issue27br - past-only temporal/interaction diagnostic",
            "",
            "<!-- issue27br_past_only_temporal_interaction -->",
            f"- Primary verdict: `{verdict}`.",
            "- Purpose: test whether causal/past-only temporal-source evidence can help explain or repair BQ's suppressed attack tail without final leakage.",
            "- Stage: medium diagnostic before any larger/full benchmark.",
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
                "base_metrics": base_metrics,
                "temporal_metrics": temporal_metrics,
                "best_temporal_auc_abs": best_auc,
                "selected": selected,
                "out": str(OUT),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
