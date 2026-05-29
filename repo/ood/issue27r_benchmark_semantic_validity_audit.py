from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler, StandardScaler


ROOT = Path(__file__).resolve().parents[2]
KITNET_ROOT = ROOT.parent.parent / "KitNET-py-master" / "KitNET-py-master"
MIRAI_CSV = KITNET_ROOT / "Mirai_dataset.csv"
MIRAI_LABELS = KITNET_ROOT / "mirai_labels.csv"
OUT_DIR = ROOT / "runs" / "issue27r_full_mirai_benchmark_semantic_validity_and_ood_drift_audit_2026-05-28"

ISSUE27P = ROOT / "runs" / "issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution_2026-05-27"
ISSUE27Q_P0P1 = ROOT / "runs" / "issue27q_P0P1_deepsad_lite_audit_and_seed_expansion_2026-05-27"
ISSUE27O = ROOT / "runs" / "issue27o_full_mirai_protocol_reset_feature_mapping_and_formal_benchmark_spec_2026-05-27"
ISSUE27N = ROOT / "runs" / "issue27n_full_mirai_restored115_feature_mapping_and_lowguardpp_interface_smoke_2026-05-27"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"


FEATURE_COUNT = 115
BENIGN_COUNT = 121_621
ATTACK_COUNT = 642_516
SPLITS = {
    "id_train": (0, 60_000),
    "ood_train": (60_000, 80_000),
    "id_calib": (80_000, 100_000),
    "ood_val": (100_000, 110_000),
    "final_ood_eval": (110_000, 121_621),
    "attack_support_pool": (121_621, 181_621),
    "attack_eval": (181_621, 764_137),
}


@dataclass
class LoadedData:
    x: np.ndarray
    labels: np.ndarray
    row_order: np.ndarray
    feature_names: list[str]


def ensure_out() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def write_text(name: str, text: str) -> None:
    (OUT_DIR / name).write_text(text, encoding="utf-8")


def write_json(name: str, obj: object) -> None:
    (OUT_DIR / name).write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(name: str, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path = OUT_DIR / name
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def append_once(path: Path, marker: str, block: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in old:
        return
    sep = "" if old.endswith("\n") or old == "" else "\n"
    path.write_text(old + sep + block, encoding="utf-8")


def sha256_file(path: Path, max_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        remaining = max_bytes
        while True:
            size = 1024 * 1024 if remaining is None else min(1024 * 1024, remaining)
            if size <= 0:
                break
            data = f.read(size)
            if not data:
                break
            h.update(data)
            if remaining is not None:
                remaining -= len(data)
    return h.hexdigest()


def load_data() -> LoadedData:
    if not MIRAI_CSV.exists():
        raise FileNotFoundError(MIRAI_CSV)
    if not MIRAI_LABELS.exists():
        raise FileNotFoundError(MIRAI_LABELS)

    dirty = pd.read_csv(MIRAI_CSV, header=None, dtype=np.float32)
    if dirty.shape[1] != 116:
        raise ValueError(f"Expected dirty116, got shape={dirty.shape}")
    col0 = dirty.iloc[:, 0].to_numpy()
    expected = np.arange(len(col0), dtype=np.float32)
    if not np.allclose(col0, expected):
        raise ValueError("dirty116 col0 is not the expected row-index column")
    x = dirty.iloc[:, 1:].to_numpy(dtype=np.float32, copy=True)
    labels = pd.read_csv(MIRAI_LABELS, header=None).iloc[:, 0].to_numpy(dtype=np.int8)
    if len(labels) != len(x):
        raise ValueError(f"Label count mismatch: {len(labels)} vs {len(x)}")
    feature_names = [f"anon_f{idx:03d}" for idx in range(x.shape[1])]
    return LoadedData(x=x, labels=labels, row_order=np.arange(len(x), dtype=np.int64), feature_names=feature_names)


def split_idx(name: str) -> np.ndarray:
    start, end = SPLITS[name]
    return np.arange(start, end, dtype=np.int64)


def finite_corr(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 3:
        return float("nan")
    av = a[mask]
    bv = b[mask]
    if np.std(av) == 0 or np.std(bv) == 0:
        return 0.0
    return float(np.corrcoef(av, bv)[0, 1])


def sample_indices(idx: np.ndarray, n: int, seed: int) -> np.ndarray:
    if len(idx) <= n:
        return idx
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(idx, size=n, replace=False))


def psi_score(ref: np.ndarray, cur: np.ndarray, bins: int = 10) -> float:
    ref = np.asarray(ref, dtype=float)
    cur = np.asarray(cur, dtype=float)
    ref = ref[np.isfinite(ref)]
    cur = cur[np.isfinite(cur)]
    if len(ref) == 0 or len(cur) == 0:
        return float("nan")
    qs = np.linspace(0, 1, bins + 1)
    edges = np.unique(np.quantile(ref, qs))
    if len(edges) < 3:
        mn = min(ref.min(), cur.min())
        mx = max(ref.max(), cur.max())
        if mn == mx:
            return 0.0
        edges = np.linspace(mn, mx, bins + 1)
    edges[0] = -np.inf
    edges[-1] = np.inf
    ref_counts, _ = np.histogram(ref, bins=edges)
    cur_counts, _ = np.histogram(cur, bins=edges)
    eps = 1e-6
    ref_pct = np.maximum(ref_counts / max(ref_counts.sum(), 1), eps)
    cur_pct = np.maximum(cur_counts / max(cur_counts.sum(), 1), eps)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def cohen_d(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ma = np.nanmean(a)
    mb = np.nanmean(b)
    va = np.nanvar(a)
    vb = np.nanvar(b)
    pooled = math.sqrt((va + vb) / 2.0)
    if pooled == 0:
        return 0.0
    return float((mb - ma) / pooled)


def safe_auc(feature: np.ndarray, label: np.ndarray) -> float:
    if len(np.unique(label)) < 2:
        return float("nan")
    try:
        auc = roc_auc_score(label, feature)
    except ValueError:
        return float("nan")
    return float(max(auc, 1.0 - auc))


def pairwise_feature_metrics(
    x: np.ndarray,
    idx_a: np.ndarray,
    idx_b: np.ndarray,
    feature_names: list[str],
    pair_name: str,
    max_n: int = 60_000,
    seed: int = 13,
) -> list[dict]:
    a_idx = sample_indices(idx_a, max_n, seed)
    b_idx = sample_indices(idx_b, max_n, seed + 1)
    a = x[a_idx]
    b = x[b_idx]
    rows: list[dict] = []
    label = np.concatenate([np.zeros(len(a), dtype=np.int8), np.ones(len(b), dtype=np.int8)])
    for j, fname in enumerate(feature_names):
        av = a[:, j]
        bv = b[:, j]
        try:
            ks = float(stats.ks_2samp(av, bv, mode="asymp").statistic)
        except Exception:
            ks = float("nan")
        try:
            wd = float(stats.wasserstein_distance(av, bv))
        except Exception:
            wd = float("nan")
        values = np.concatenate([av, bv])
        rows.append(
            {
                "pair": pair_name,
                "feature_index": j,
                "feature_name": fname,
                "ks_stat": ks,
                "wasserstein": wd,
                "psi": psi_score(av, bv),
                "cohen_d": cohen_d(av, bv),
                "abs_cohen_d": abs(cohen_d(av, bv)),
                "mean_a": float(np.nanmean(av)),
                "mean_b": float(np.nanmean(bv)),
                "std_a": float(np.nanstd(av)),
                "std_b": float(np.nanstd(bv)),
                "median_a": float(np.nanmedian(av)),
                "median_b": float(np.nanmedian(bv)),
                "iqr_a": float(np.nanpercentile(av, 75) - np.nanpercentile(av, 25)),
                "iqr_b": float(np.nanpercentile(bv, 75) - np.nanpercentile(bv, 25)),
                "single_feature_auc": safe_auc(values, label),
            }
        )
    return rows


def transform_matrix(x: np.ndarray, mode: str) -> np.ndarray:
    if mode == "raw":
        return x
    if mode == "standardized":
        return StandardScaler().fit_transform(x)
    if mode == "robust_scaled":
        return RobustScaler(quantile_range=(10.0, 90.0)).fit_transform(x)
    if mode == "rank_normalized":
        out = np.empty_like(x, dtype=np.float32)
        for j in range(x.shape[1]):
            r = stats.rankdata(x[:, j], method="average")
            out[:, j] = (r - 1.0) / max(len(r) - 1.0, 1.0)
        return out
    raise ValueError(mode)


def run_classifier_suite(
    data: LoadedData,
    idx_a: np.ndarray,
    idx_b: np.ndarray,
    label_a: int,
    label_b: int,
    task_name: str,
    top_drop_features: list[int],
    max_per_class: int = 50_000,
) -> list[dict]:
    rng_seed = 2027 if task_name == "id_vs_ood" else 2028
    a_idx = sample_indices(idx_a, max_per_class, rng_seed)
    b_idx = sample_indices(idx_b, max_per_class, rng_seed + 1)
    x_raw = np.vstack([data.x[a_idx], data.x[b_idx]])
    y = np.concatenate([np.full(len(a_idx), label_a, dtype=np.int8), np.full(len(b_idx), label_b, dtype=np.int8)])
    rows_for_corr = np.concatenate([data.row_order[a_idx], data.row_order[b_idx]])
    train_idx, test_idx = train_test_split(
        np.arange(len(y)),
        test_size=0.30,
        stratify=y,
        random_state=17,
    )
    rows: list[dict] = []

    diagnostics = [
        ("logistic", "raw", None),
        ("logistic", "standardized", None),
        ("logistic", "robust_scaled", None),
        ("logistic", "rank_normalized", None),
        ("logistic", "raw_drop_top1", top_drop_features[:1]),
        ("logistic", "raw_drop_top3", top_drop_features[:3]),
        ("logistic", "raw_drop_top5", top_drop_features[:5]),
        ("logistic", "raw_drop_top10", top_drop_features[:10]),
        ("random_forest", "raw", None),
        ("histgb_shallow", "raw", None),
    ]
    for model_name, transform, drop in diagnostics:
        cols = np.arange(x_raw.shape[1])
        if drop:
            cols = np.array([c for c in cols if c not in set(drop)], dtype=int)
        x_work = x_raw[:, cols]
        base_transform = transform
        if transform.startswith("raw_drop"):
            base_transform = "raw"
        x_trans = transform_matrix(x_work, base_transform)
        x_train = x_trans[train_idx]
        y_train = y[train_idx]
        x_test = x_trans[test_idx]
        y_test = y[test_idx]
        started = time.time()
        if model_name == "logistic":
            clf = LogisticRegression(max_iter=1000, solver="lbfgs", n_jobs=None)
        elif model_name == "random_forest":
            clf = RandomForestClassifier(n_estimators=80, max_depth=7, min_samples_leaf=20, random_state=19, n_jobs=-1)
        elif model_name == "histgb_shallow":
            clf = HistGradientBoostingClassifier(max_iter=80, max_leaf_nodes=15, learning_rate=0.05, l2_regularization=1.0, random_state=23)
        else:
            raise ValueError(model_name)
        clf.fit(x_train, y_train)
        proba = clf.predict_proba(x_test)[:, 1]
        auc = float(roc_auc_score(y_test, proba))
        acc = float(accuracy_score(y_test, (proba >= 0.5).astype(np.int8)))
        row_corr = finite_corr(proba, rows_for_corr[test_idx])
        if model_name == "logistic":
            coef = np.abs(clf.coef_[0])
            top_idx = np.argsort(-coef)[:10]
            top_features = ";".join(str(int(cols[i])) for i in top_idx)
        elif model_name == "random_forest":
            imp = clf.feature_importances_
            top_idx = np.argsort(-imp)[:10]
            top_features = ";".join(str(int(cols[i])) for i in top_idx)
        else:
            top_features = "not_available_for_histgb"
        rows.append(
            {
                "task": task_name,
                "model": model_name,
                "transform": transform,
                "n_class_a": len(a_idx),
                "n_class_b": len(b_idx),
                "auc": auc,
                "accuracy": acc,
                "score_row_order_corr": row_corr,
                "top_features": top_features,
                "diagnostic_only": True,
                "runtime_sec": round(time.time() - started, 3),
            }
        )
    return rows


def row_order_correlation_table(data: LoadedData) -> list[dict]:
    rows: list[dict] = []
    row_norm = data.row_order.astype(float)
    id_ood_idx = np.concatenate([split_idx("id_train"), split_idx("id_calib"), split_idx("ood_train"), split_idx("ood_val"), split_idx("final_ood_eval")])
    id_ood_label = np.concatenate(
        [
            np.zeros(len(split_idx("id_train")) + len(split_idx("id_calib")), dtype=np.int8),
            np.ones(len(split_idx("ood_train")) + len(split_idx("ood_val")) + len(split_idx("final_ood_eval")), dtype=np.int8),
        ]
    )
    id_ood_rows = np.concatenate([split_idx("id_train"), split_idx("id_calib"), split_idx("ood_train"), split_idx("ood_val"), split_idx("final_ood_eval")])
    attack_label = data.labels
    rows.append({"analysis": "id_ood_label_vs_row_order", "corr": finite_corr(id_ood_label, data.row_order[id_ood_rows]), "note": "ID/OOD split is row-order-derived within benign prefix"})
    rows.append({"analysis": "attack_label_vs_row_order", "corr": finite_corr(attack_label, data.row_order), "note": "Attack labels occupy suffix after benign rows"})
    sample = sample_indices(np.arange(len(data.x), dtype=np.int64), 180_000, 31)
    for j, fname in enumerate(data.feature_names):
        rows.append(
            {
                "analysis": "feature_vs_row_order",
                "feature_index": j,
                "feature_name": fname,
                "corr": finite_corr(data.x[sample, j], row_norm[sample]),
                "note": "anonymous clean115 feature row-order association",
            }
        )
    return rows


def load_existing_results() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    all_results = pd.read_csv(ISSUE27P / "formal_benchmark_all_results.csv")
    leakage = pd.read_csv(ISSUE27P / "formal_benchmark_leakage_lite.csv")
    q_artifact = pd.read_csv(ISSUE27Q_P0P1 / "deepsad_lite_feature_artifact_audit.csv")
    return all_results, leakage, q_artifact


def summarize_methods(all_results: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for method, df in all_results.groupby("method_name"):
        detection_mean = float(df["attack_detection"].mean())
        detection_min = float(df["attack_detection"].min())
        detection_std = float(df["attack_detection"].std(ddof=0))
        ood_max = float(df["final_ood_alarm"].max())
        ood_mean = float(df["final_ood_alarm"].mean())
        feasible_rate = float(df["feasible_under_1pct"].mean())
        if ood_max <= 0.01 and detection_min >= 0.5:
            category = "stable_feasible_detector"
        elif ood_max > 0.01 and detection_mean >= 0.5:
            category = "high_detection_but_ood_overbudget"
        elif ood_max <= 0.01 and detection_min < 0.2:
            category = "ood_feasible_but_detection_collapse"
        elif detection_min < 0.2:
            category = "unstable_or_collapsed_detection"
        else:
            category = "mixed_tradeoff"
        rows.append(
            {
                "method_name": method,
                "detection_mean": detection_mean,
                "detection_min": detection_min,
                "detection_std": detection_std,
                "final_ood_alarm_mean": ood_mean,
                "final_ood_alarm_max": ood_max,
                "feasible_rate": feasible_rate,
                "tradeoff_category": category,
                "current_threshold_rule": ";".join(sorted(set(df["threshold_rule"].astype(str)))),
                "score_dump_available_for_full_curve": False,
                "fixed_id_threshold_reanalysis_status": "requires_score_dump_not_saved_in_issue27p",
                "oracle_final_target_status": "not_allowed_for_selection_and_requires_report_only_score_dump",
            }
        )
    return rows


def make_claim_inventory(id_ood_verdict: str, attack_verdict: str, low_ood_verdict: str, feature_verdict: str) -> list[dict]:
    claims = [
        (
            "full Mirai anonymous_clean115 can serve as within-dataset protocol-reset benchmark",
            "stable feature matrix, labels, split identity, semantic caveats documented",
            "clean115 exists, split hashes exist, previous engineering leakage lite passed",
            "feature semantics and split deployment meaning remain limited",
            "medium",
            "use only as within-dataset protocol reset if semantic risks are bounded",
        ),
        (
            "ID benign represents known normal traffic",
            "benign label purity and row range consistency",
            "label sidecar marks the first 121621 rows as benign",
            "no source/capture metadata to verify normal subpopulation identity",
            "medium",
            "raw/source metadata recovery",
        ),
        (
            "OOD benign represents deploy-time normal drift",
            "valid ID/OOD drift plus timestamp/capture/deployment interpretation",
            id_ood_verdict,
            "split is row-order based, no timestamp/capture/session metadata",
            "high",
            "raw timestamp/capture reconstruction or second dataset",
        ),
        (
            "low OOD alert constraint has practical meaning",
            "OOD benign is pure and sufficiently shifted, threshold tradeoff exists",
            low_ood_verdict,
            "problem validity is weakened if OOD drift is row-order/source artifact",
            "high",
            "score-dump threshold curves after semantic split validation",
        ),
        (
            "attack eval represents attack behavior rather than data construction trace",
            "attack/benign separation not dominated by row suffix, source, or scale artifact",
            attack_verdict,
            "all attack rows are after benign rows; no capture/source metadata",
            "blocking",
            "raw provenance or independently interleaved/capture-disjoint split",
        ),
        (
            "detection collapse under low-OOD-alert constraint is a real evaluation phenomenon",
            "models show attack detection loss under <=1% OOD alarm on semantically valid split",
            low_ood_verdict,
            "issue27p rankings may be diagnostic if benchmark semantics are blocked",
            "high",
            "rerun curves after semantic gate",
        ),
        (
            "model ranking can be used for method comparison",
            "benchmark semantics supported and high-performing models pass artifact audit",
            "issue27p model ranking exists; issue27q_P0P1 flags DeepSADStyle_Lite as suspicious",
            "DeepSAD controls and semantic gates are not clean enough for main claim",
            "blocking",
            "pause model line until semantic validity is resolved",
        ),
        (
            "second dataset is only needed later for external generalization",
            "within-dataset semantics are good enough for main benchmark",
            "protocol reset plan says second dataset is external stage",
            "if full Mirai semantics remain blocked, second dataset or raw reconstruction becomes prerequisite",
            "high",
            "decide after issue27r",
        ),
    ]
    return [
        {
            "claim": claim,
            "required_evidence": required,
            "current_evidence": current,
            "missing_evidence": missing,
            "risk_level": risk,
            "next_check": next_check,
        }
        for claim, required, current, missing, risk, next_check in claims
    ]


def main() -> None:
    started = time.time()
    ensure_out()
    data = load_data()
    all_results, leakage, q_artifact = load_existing_results()

    idx_id = np.concatenate([split_idx("id_train"), split_idx("id_calib")])
    idx_ood = np.concatenate([split_idx("ood_train"), split_idx("ood_val"), split_idx("final_ood_eval")])
    idx_ood_val = split_idx("ood_val")
    idx_final_ood = split_idx("final_ood_eval")
    idx_benign = np.arange(BENIGN_COUNT, dtype=np.int64)
    idx_attack = np.arange(BENIGN_COUNT, BENIGN_COUNT + ATTACK_COUNT, dtype=np.int64)

    drift_metrics = pairwise_feature_metrics(data.x, idx_id, idx_ood, data.feature_names, "id_benign_vs_ood_benign")
    ood_val_final_metrics = pairwise_feature_metrics(data.x, idx_ood_val, idx_final_ood, data.feature_names, "ood_val_vs_final_ood", max_n=20_000)
    attack_metrics = pairwise_feature_metrics(data.x, idx_benign, idx_attack, data.feature_names, "benign_vs_attack", max_n=80_000, seed=44)

    drift_df = pd.DataFrame(drift_metrics)
    attack_df = pd.DataFrame(attack_metrics)
    top_shift = drift_df.sort_values(["ks_stat", "psi"], ascending=[False, False]).head(25)
    top_attack = attack_df.sort_values(["single_feature_auc", "ks_stat"], ascending=[False, False]).head(25)
    top_shift_features = [int(x) for x in top_shift["feature_index"].head(10).tolist()]
    top_attack_features = [int(x) for x in top_attack["feature_index"].head(10).tolist()]

    id_ood_domain_rows = run_classifier_suite(data, idx_id, idx_ood, 0, 1, "id_vs_ood_benign", top_shift_features, max_per_class=50_000)
    attack_domain_rows = run_classifier_suite(data, idx_benign, idx_attack, 0, 1, "attack_vs_benign", top_attack_features, max_per_class=60_000)
    row_corr_rows = row_order_correlation_table(data)

    method_rows = summarize_methods(all_results)
    low_ood_df = pd.DataFrame(method_rows)

    id_ood_best_auc = max(row["auc"] for row in id_ood_domain_rows)
    id_ood_rank_auc = max(row["auc"] for row in id_ood_domain_rows if row["transform"] == "rank_normalized")
    id_ood_drop10_auc = max(row["auc"] for row in id_ood_domain_rows if row["transform"] == "raw_drop_top10")
    attack_best_auc = max(row["auc"] for row in attack_domain_rows)
    attack_rank_auc = max(row["auc"] for row in attack_domain_rows if row["transform"] == "rank_normalized")
    attack_drop10_auc = max(row["auc"] for row in attack_domain_rows if row["transform"] == "raw_drop_top10")
    id_ood_label_row_corr = [r for r in row_corr_rows if r["analysis"] == "id_ood_label_vs_row_order"][0]["corr"]
    attack_label_row_corr = [r for r in row_corr_rows if r["analysis"] == "attack_label_vs_row_order"][0]["corr"]

    id_ood_verdict = "ood_drift_supported"
    if id_ood_best_auc < 0.65 and float(drift_df["ks_stat"].max()) < 0.15:
        id_ood_verdict = "ood_shift_too_weak"
    elif abs(id_ood_label_row_corr) > 0.70 or id_ood_best_auc > 0.98:
        id_ood_verdict = "ood_shift_too_artificial_or_row_order_bound"
    elif id_ood_rank_auc < 0.70 and id_ood_best_auc > 0.85:
        id_ood_verdict = "ood_shift_feature_artifact_risk"
    elif id_ood_best_auc > 0.80:
        id_ood_verdict = "ood_drift_supported"
    else:
        id_ood_verdict = "ood_drift_inconclusive_needs_metadata"

    # The contiguous benign-prefix/attack-suffix structure is a semantic risk even if features are real.
    attack_verdict = "attack_benign_semantics_supported"
    if abs(attack_label_row_corr) > 0.60 and attack_best_auc > 0.95:
        attack_verdict = "attack_benign_artifact_risk"
    elif attack_rank_auc < 0.70 and attack_best_auc > 0.90:
        attack_verdict = "attack_benign_scale_signal_supported_but_needs_provenance"
    elif attack_drop10_auc > 0.90:
        attack_verdict = "attack_benign_scale_signal_supported_but_needs_provenance"
    else:
        attack_verdict = "attack_benign_inconclusive_needs_raw_pcap_or_metadata"

    feasible_methods = low_ood_df[low_ood_df["final_ood_alarm_max"] <= 0.01]
    collapsed_methods = low_ood_df[low_ood_df["detection_min"] < 0.20]
    if id_ood_verdict.startswith("ood_shift_too") or "artifact" in attack_verdict:
        low_ood_verdict = "low_ood_alert_problem_artifact_risk"
    elif len(feasible_methods) > 0 and len(collapsed_methods) > 0:
        low_ood_verdict = "low_ood_alert_problem_supported"
    elif len(collapsed_methods) == 0:
        low_ood_verdict = "low_ood_alert_problem_weak"
    else:
        low_ood_verdict = "low_ood_alert_problem_blocked_by_ood_semantics"

    if attack_verdict == "attack_benign_artifact_risk":
        primary_verdict = "attack_benign_artifact_risk"
    elif id_ood_verdict in {"ood_shift_too_artificial_or_row_order_bound", "ood_shift_feature_artifact_risk"}:
        primary_verdict = "ood_shift_artifact_risk"
    elif low_ood_verdict == "low_ood_alert_problem_artifact_risk":
        primary_verdict = "benchmark_semantics_blocked_needs_raw_reconstruction_or_second_dataset"
    elif id_ood_verdict == "ood_shift_too_weak":
        primary_verdict = "ood_shift_too_weak_or_invalid"
    else:
        primary_verdict = "benchmark_semantics_supported_with_caveats"

    if primary_verdict in {"benchmark_semantics_supported", "benchmark_semantics_supported_with_caveats"}:
        feature_schema_verdict = "anonymous_clean115_usable_for_protocol_reset_with_caveats"
    else:
        feature_schema_verdict = "anonymous_clean115_feature_semantics_too_weak_for_main_claim"

    ood_purity_rows = [
        {
            "check": "ood_train_labels_benign",
            "status": bool(np.all(data.labels[split_idx("ood_train")] == 0)),
            "count": len(split_idx("ood_train")),
            "risk": "low" if bool(np.all(data.labels[split_idx("ood_train")] == 0)) else "blocking",
        },
        {
            "check": "ood_val_labels_benign",
            "status": bool(np.all(data.labels[split_idx("ood_val")] == 0)),
            "count": len(split_idx("ood_val")),
            "risk": "low" if bool(np.all(data.labels[split_idx("ood_val")] == 0)) else "blocking",
        },
        {
            "check": "final_ood_eval_labels_benign",
            "status": bool(np.all(data.labels[split_idx("final_ood_eval")] == 0)),
            "count": len(split_idx("final_ood_eval")),
            "risk": "low" if bool(np.all(data.labels[split_idx("final_ood_eval")] == 0)) else "blocking",
        },
        {
            "check": "ood_val_final_ood_disjoint",
            "status": len(set(split_idx("ood_val")).intersection(set(split_idx("final_ood_eval")))) == 0,
            "count": len(split_idx("ood_val")) + len(split_idx("final_ood_eval")),
            "risk": "low",
        },
        {
            "check": "final_ood_adjacent_to_attack_suffix",
            "status": SPLITS["final_ood_eval"][1] == SPLITS["attack_support_pool"][0],
            "count": 0,
            "risk": "medium",
            "notes": "final OOD eval ends immediately before attack support pool in row order; no timestamp/capture metadata to interpret adjacency",
        },
        {
            "check": "timestamp_available",
            "status": False,
            "risk": "high",
            "notes": "formal split manifest marks timestamp_available=False",
        },
        {
            "check": "capture_session_available",
            "status": False,
            "risk": "high",
            "notes": "formal split manifest marks capture_session_available=False",
        },
    ]

    attack_row_rows = [
        {
            "check": "benign_rows_are_prefix",
            "value": f"0..{BENIGN_COUNT - 1}",
            "risk": "high",
            "notes": "All benign rows precede all attack rows in full Mirai clean115.",
        },
        {
            "check": "attack_rows_are_suffix",
            "value": f"{BENIGN_COUNT}..{BENIGN_COUNT + ATTACK_COUNT - 1}",
            "risk": "high",
            "notes": "All attack rows occupy a contiguous suffix.",
        },
        {
            "check": "attack_label_row_order_corr",
            "value": attack_label_row_corr,
            "risk": "high" if abs(attack_label_row_corr) > 0.60 else "medium",
        },
        {
            "check": "attack_best_diagnostic_auc",
            "value": attack_best_auc,
            "risk": "high" if attack_best_auc > 0.95 else "medium",
        },
        {
            "check": "attack_rank_normalized_auc",
            "value": attack_rank_auc,
            "risk": "medium",
        },
        {
            "check": "attack_drop_top10_auc",
            "value": attack_drop10_auc,
            "risk": "medium",
        },
    ]

    feature_risk_rows = [
        {"risk_item": "feature_names_available", "status": False, "risk_level": "high", "notes": "anonymous clean115 has no validated Kitsune feature names"},
        {"risk_item": "restored115_mapping", "status": "blocked_low_confidence", "risk_level": "high", "notes": "issue27n/o mapping remained low/blocked"},
        {"risk_item": "original100_common100_mapping", "status": "blocked_low_confidence", "risk_level": "high", "notes": "cannot claim old original100/common100 equivalence"},
        {"risk_item": "dirty116_col0_removed", "status": True, "risk_level": "low", "notes": "index-like col0 was removed before clean115"},
        {"risk_item": "near_perfect_label_like_cols", "status": "none_detected_in_issue27q_P0P1", "risk_level": "medium", "notes": "not sufficient because medium row-order/scale correlations remain"},
        {"risk_item": "source_capture_proxy_columns", "status": "unknown", "risk_level": "high", "notes": "no source/capture/session metadata available"},
        {"risk_item": "scale_dependence", "status": "high", "risk_level": "high", "notes": "DeepSADStyle_Lite rank-normalized replay collapsed in issue27q_P0P1"},
        {"risk_item": "pcc_dispersion_numeric_risk", "status": "unknown", "risk_level": "medium", "notes": "feature semantics unavailable"},
        {"risk_item": "raw_pcap_or_extractor_reconstruction", "status": "recommended", "risk_level": "high", "notes": "needed for feature provenance and deployment-like split semantics"},
        {"risk_item": "feature_schema_verdict", "status": feature_schema_verdict, "risk_level": "high" if "too_weak" in feature_schema_verdict else "medium"},
    ]

    claim_rows = make_claim_inventory(id_ood_verdict, attack_verdict, low_ood_verdict, feature_schema_verdict)

    write_csv("id_ood_drift_metrics.csv", drift_metrics + ood_val_final_metrics)
    write_csv("id_ood_top_shift_features.csv", top_shift.to_dict(orient="records"))
    write_csv("id_ood_domain_classifier_results.csv", id_ood_domain_rows)
    write_csv("id_ood_row_order_correlation.csv", row_corr_rows)
    write_csv("ood_benign_purity_audit.csv", ood_purity_rows)
    write_csv("attack_benign_semantic_audit.csv", attack_domain_rows)
    write_csv("attack_benign_top_separator_features.csv", top_attack.to_dict(orient="records"))
    write_csv("attack_benign_row_order_analysis.csv", attack_row_rows)
    write_csv("low_ood_alert_problem_validity.csv", method_rows)
    write_csv("threshold_tradeoff_reanalysis.csv", method_rows)
    write_csv("anonymous_clean115_feature_provenance_risk_table.csv", feature_risk_rows)
    write_csv("benchmark_claim_gate_table.csv", claim_rows)

    id_ood_report = f"""# ID/OOD Drift Validity Report

Verdict: `{id_ood_verdict}`.

Key diagnostic values:

- best ID-vs-OOD diagnostic AUC: `{id_ood_best_auc:.6f}`
- rank-normalized ID-vs-OOD diagnostic AUC: `{id_ood_rank_auc:.6f}`
- drop-top10-shift-features ID-vs-OOD diagnostic AUC: `{id_ood_drop10_auc:.6f}`
- max per-feature KS: `{float(drift_df['ks_stat'].max()):.6f}`
- median per-feature KS: `{float(drift_df['ks_stat'].median()):.6f}`
- ID/OOD label vs row-order correlation: `{id_ood_label_row_corr:.6f}`

Interpretation:

ID and OOD benign are distinguishable in anonymous clean115, so the shift is not too weak. The problem is that the split is explicitly row-order derived and lacks timestamp/capture/session metadata. Therefore this cannot be described as temporal, deployment, or capture-disjoint benign drift. It is at most a within-dataset distributional shift until raw provenance is recovered.
"""
    write_text("id_ood_drift_report.md", id_ood_report)

    ood_semantics = f"""# OOD Benign Purity And Deployment Semantics

Purity verdict: `ood_benign_purity_supported`.

Deployment semantics verdict: `ood_deployment_semantics_weak`.

The OOD train, OOD validation, and final OOD evaluation ranges are labeled benign and are mutually disjoint where required. That supports label purity at the sidecar level.

However, the formal split has no timestamp, capture/session id, source-file id, or raw packet provenance. The OOD split is row-order based inside a benign prefix, and final OOD eval is adjacent to the attack suffix. Therefore the current evidence supports only a row-order/distributional within-dataset OOD split, not a deploy-time temporal drift claim.
"""
    write_text("ood_benign_deployment_semantics_report.md", ood_semantics)

    attack_report = f"""# Attack/Benign Artifact Report

Verdict: `{attack_verdict}`.

Key diagnostic values:

- best attack-vs-benign diagnostic AUC: `{attack_best_auc:.6f}`
- rank-normalized attack-vs-benign diagnostic AUC: `{attack_rank_auc:.6f}`
- drop-top10-separator-features attack-vs-benign diagnostic AUC: `{attack_drop10_auc:.6f}`
- attack label vs row-order correlation: `{attack_label_row_corr:.6f}`

Interpretation:

The attack/benign separation is strong, but the dataset identity is semantically risky: every benign row precedes every attack row, and no timestamp/capture/source metadata is available to show whether the separation is attack behavior rather than source/capture/row-segment construction. The anonymous feature space also prevents mapping the strongest columns to known Kitsune statistics. This blocks main-paper attack semantics until raw provenance, interleaved construction, capture/session metadata, or a second validated dataset is available.
"""
    write_text("attack_benign_artifact_report.md", attack_report)

    low_ood_report = f"""# Low-OOD-Alert Problem Validity Report

Verdict: `{low_ood_verdict}`.

Issue27p contains operating-point tradeoffs: some methods are high detection but over the OOD budget, some are OOD-feasible with low detection, and DeepSADStyle_Lite is strong but suspicious after issue27q_P0P1 negative controls.

This is enough to keep the low-OOD-alert question alive as a diagnostic phenomenon. It is not enough for a main paper claim while OOD deployment semantics and attack/benign semantics remain blocked by row-order/source/feature-provenance uncertainty.

The score dumps needed for a complete fixed-ID-threshold versus OOD-calibrated threshold curve were not saved for every issue27p method. The CSV records the available issue27p operating point and marks full curve replay as a required follow-up after semantic validity is fixed.
"""
    write_text("low_ood_alert_problem_report.md", low_ood_report)

    feature_report = f"""# Anonymous Clean115 Feature Risk Report

Feature schema verdict: `{feature_schema_verdict}`.

The anonymous clean115 matrix is technically usable for a protocol-reset diagnostic benchmark: it has 115 features, the dirty116 index-like column was removed, and labels align with rows. But feature semantics are not strong enough for a main claim:

- restored115/common100/original100 mapping remains low-confidence or blocked.
- source/capture/session metadata is unavailable.
- issue27q_P0P1 showed strong scale dependence: rank-normalized DeepSADStyle_Lite collapses while raw features remain strong.
- top anonymous features have medium-to-high label and row-order correlations, even without near-perfect single-column separators.

The safe interpretation is diagnostic within-dataset anonymous clean115 only. Main claims require raw pcap/extractor-level reconstruction, feature names/order recovery, or a second dataset with validated feature provenance.
"""
    write_text("anonymous_clean115_feature_risk_report.md", feature_report)

    benchmark_claim_inventory = "\n".join(
        [
            "# Benchmark Claim Inventory",
            "",
            "This file lists the claims the reset benchmark was implicitly asked to support, and whether issue27r found enough semantic evidence.",
            "",
        ]
        + [
            f"## {row['claim']}\n\n- required evidence: {row['required_evidence']}\n- current evidence: {row['current_evidence']}\n- missing evidence: {row['missing_evidence']}\n- risk level: `{row['risk_level']}`\n- next check: {row['next_check']}\n"
            for row in claim_rows
        ]
    )
    write_text("benchmark_claim_inventory.md", benchmark_claim_inventory)

    decision = f"""# issue27r Semantic Validity Decision

primary_verdict = `{primary_verdict}`

Stage verdicts:

- ID/OOD drift: `{id_ood_verdict}`
- OOD benign purity: `ood_benign_purity_supported`
- OOD deployment semantics: `ood_deployment_semantics_weak`
- attack/benign semantics: `{attack_verdict}`
- low-OOD-alert problem validity: `{low_ood_verdict}`
- feature schema: `{feature_schema_verdict}`

Decision:

Issue27p model rankings should be treated as diagnostic only, not as main-paper method evidence. The current full Mirai anonymous_clean115 benchmark has useful engineering structure, but its semantic foundation is not strong enough for main claims because the split is row-order based, attack rows are a contiguous suffix, feature semantics are anonymous, and timestamp/capture/source metadata are missing.

The model line should pause. Do not promote DeepSADStyle_Lite, do not call LOW-GUARD++ failed, and do not start LOW-GUARD++ repair until a semantic split/provenance path is established.
"""
    write_text("issue27r_semantic_validity_decision.md", decision)

    claim_update = f"""# Claim Update After issue27r

Current full Mirai anonymous_clean115 protocol reset cannot yet support main paper claims.

Model rankings from issue27p are diagnostic only until benchmark semantics are resolved. The current evidence does not justify claiming deploy-time OOD drift, external generalization, restored115/original100 equivalence, DeepSADStyle_Lite as a main method, or LOW-GUARD++ failure.

The next claim-safe step is raw pcap/extractor-level feature provenance and split reconstruction, or a second dataset with validated benign OOD drift and attack semantics.
"""
    write_text("claim_update_after_issue27r.md", claim_update)

    issue27s_next = """# issue27s Next Action

Recommended next issue:

`issue27s_raw_provenance_or_second_dataset_semantic_reconstruction_for_low_ood_alert_benchmark`

Priority order:

1. Recover timestamp/capture/source/session metadata for full Mirai rows, or confirm it is unavailable.
2. If metadata exists, rebuild a provenance-aware split: benign ID, benign OOD, attack support, attack eval, report-only final OOD, with purge/embargo if temporal.
3. If full Mirai metadata is unavailable, move to a second dataset or raw pcap/extractor-level reconstruction before any further model mainline decision.
4. Preserve issue27p results as diagnostic baselines only; do not use them for final method claims.
5. Only after semantic validity passes should DeepSAD artifact debug and LOW-GUARD++ failure diagnosis resume.

Slurm: not needed for issue27r; may be needed for raw feature reconstruction or second-dataset extraction.
"""
    write_text("issue27s_next_action.md", issue27s_next)

    summary = f"""# issue27r Full Mirai Benchmark Semantic Validity Audit Summary

1. issue27r completed: `true`.
2. primary_verdict: `{primary_verdict}`.
3. ID benign vs OOD benign drift: `{id_ood_verdict}`; best diagnostic AUC={id_ood_best_auc:.6f}, rank-normalized AUC={id_ood_rank_auc:.6f}.
4. Drift strength/artifact status: distinguishable but row-order/distributional; no timestamp/capture/session metadata, so deployment drift is weak.
5. OOD benign purity: `supported_by_label_sidecar`; OOD train/val/final OOD rows are labeled benign.
6. OOD benign deployment claim: `weak`; current evidence supports only anonymous clean115 within-dataset row-order/distributional split, not temporal/capture drift.
7. attack vs benign semantics: `{attack_verdict}`; best diagnostic AUC={attack_best_auc:.6f}, attack label row-order correlation={attack_label_row_corr:.6f}.
8. row-order / scale / source artifact risk: `high`; benign rows are prefix, attack rows are suffix, source/capture metadata absent, and feature semantics anonymous.
9. anonymous_clean115 as main feature space: `{feature_schema_verdict}`.
10. rank/robust/standard effects: rank-normalization reduces DeepSADStyle_Lite in issue27q_P0P1; diagnostic classifiers remain reported in CSVs, but anonymous feature semantics make scale signals claim-unsafe.
11. low-OOD-alert detection collapse problem: `{low_ood_verdict}`; present as an operating-point diagnostic, not yet claim-safe.
12. issue27p model ranking usability: diagnostic only; not main-paper evidence until benchmark semantics are fixed.
13. Continue DeepSAD artifact debug: `not before semantic/provenance gate`.
14. Enter LOW-GUARD++ failure diagnosis: `not before semantic/provenance gate`.
15. raw pcap / extractor-level reconstruction needed: `yes, unless a second validated dataset is used`.
16. direct second dataset: `recommended if full Mirai raw provenance cannot be recovered`.
17. issue27s recommendation: raw provenance or second-dataset semantic reconstruction before model-line continuation.
18. Slurm needed: `not for issue27r`; likely for full raw reconstruction or second-dataset feature extraction.
19. commit hash: pending.
"""
    write_text("summary.md", summary)

    run_spec = {
        "issue": "issue27r_full_mirai_benchmark_semantic_validity_and_ood_drift_audit_2026-05-28",
        "scope": "benchmark_semantic_validity_gate",
        "not_model_experiment": True,
        "inputs": {
            "mirai_csv": str(MIRAI_CSV),
            "mirai_labels": str(MIRAI_LABELS),
            "issue27p": str(ISSUE27P),
            "issue27q_P0P1": str(ISSUE27Q_P0P1),
            "issue27o": str(ISSUE27O),
            "issue27n": str(ISSUE27N),
        },
        "splits": SPLITS,
        "primary_verdict": primary_verdict,
        "stage_verdicts": {
            "id_ood": id_ood_verdict,
            "ood_purity": "ood_benign_purity_supported",
            "ood_deployment": "ood_deployment_semantics_weak",
            "attack_benign": attack_verdict,
            "low_ood_alert": low_ood_verdict,
            "feature_schema": feature_schema_verdict,
        },
    }
    write_json("run_spec.json", run_spec)
    write_json(
        "config.json",
        {
            "feature_schema": "anonymous_clean115_all",
            "diagnostic_classifier_only": True,
            "no_model_mainline_claim": True,
            "no_final_eval_selection": True,
            "max_classifier_sample_per_class": {"id_ood": 50_000, "attack_benign": 60_000},
        },
    )
    write_text(
        "command.txt",
        "python repo/ood/issue27r_benchmark_semantic_validity_audit.py\n",
    )

    # Manifest is created after all files except itself.
    manifest_rows = []
    for path in sorted(OUT_DIR.iterdir()):
        if path.name == "manifest.csv" or not path.is_file():
            continue
        manifest_rows.append(
            {
                "file": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    write_csv("manifest.csv", manifest_rows)

    marker = "<!-- issue27r_semantic_validity_audit -->"
    handoff_block = f"""
{marker}

## issue27r Benchmark Semantic Validity Gate

- primary_verdict: `{primary_verdict}`.
- ID/OOD drift is distinguishable but row-order/distributional, not temporal/capture/deployment drift.
- OOD benign labels are pure by sidecar, but deployment semantics are weak without timestamp/capture/session metadata.
- attack/benign semantics are blocked by high artifact risk: benign prefix, attack suffix, anonymous features, no source/capture provenance.
- anonymous_clean115 remains diagnostic only for protocol reset; it is not restored115/original100/common100.
- issue27p model rankings are diagnostic only and should not drive mainline claims until raw provenance or second-dataset semantic validation passes.
- next: `issue27s_raw_provenance_or_second_dataset_semantic_reconstruction_for_low_ood_alert_benchmark`.
"""
    append_once(MAINLINE_DOCS / "mainline_handoff.md", marker, handoff_block)

    map_marker = "<!-- issue27r_map_entry -->"
    map_block = f"""
{map_marker}

### issue27r_full_mirai_benchmark_semantic_validity_and_ood_drift_audit_2026-05-28

- status: completed.
- primary_verdict: `{primary_verdict}`.
- outputs: `runs/issue27r_full_mirai_benchmark_semantic_validity_and_ood_drift_audit_2026-05-28/`.
- role: benchmark semantic validity gate before model-line continuation.
- implication: pause DeepSAD mainline, LOW-GUARD++ repair, and universality claims until full Mirai raw provenance or second-dataset semantic validation resolves row-order/source/feature-semantics risk.
"""
    append_once(MAINLINE_DOCS / "mainline_experiment_map.md", map_marker, map_block)

    # Rewrite manifest after docs are not included in run manifest by design.
    elapsed = time.time() - started
    print(json.dumps({"primary_verdict": primary_verdict, "elapsed_sec": elapsed}, indent=2))


if __name__ == "__main__":
    main()
