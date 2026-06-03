from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent

ISSUE = "issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium_2026-06-03"
OUT = ROOT / "runs" / ISSUE

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AP = ROOT / "runs" / "issue27ap_new_heldout_attack_probe_and_v2_diagnostic_retest_2026-06-03"
ISSUE27AQ = ROOT / "runs" / "issue27aq_model_learning_and_domain_gap_audit_after_new_heldout_zero_detection_2026-06-03"
ISSUE27D = ROOT / "runs" / "issue27d_lowguard_adapter_interface_and_model_specific_objectives_smoke_2026-05-26"
ISSUE27F = ROOT / "runs" / "issue27f_config_freeze_then_formal_validation_for_original100_histgb_conservative_2026-05-27"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

PROJECT_DIR = ROOT.parents[1]
NEW_HELDOUT_DIR = PROJECT_DIR / "datasets" / "gotham2025" / "derived" / "kitsune115_new_heldout_attack_probe_v1"
NEW_HELDOUT_X = NEW_HELDOUT_DIR / "gotham_kitsune115_new_heldout_attack_probe_X.npy"
NEW_HELDOUT_SIDECAR = NEW_HELDOUT_DIR / "gotham_kitsune115_new_heldout_attack_probe_sidecar.csv.gz"

ID_ROLE = "id_benign_train"
OOD_VAL_ROLE = "ood_benign_val"
FINAL_OOD_ROLE = "final_ood_benign_eval"
SUPPORT_ROLE = "attack_support"
ATTACK_EVAL_ROLE = "attack_eval"
NEW_HELDOUT_ROLE = "new_heldout_attack_eval_probe"

SEEDS = [42, 43, 44, 45, 46]
SUPPORT_BUDGET = 32
SUPPORT_TRAIN_FOR_SELECTION = 24
TARGETS = [0.005, 0.0075, 0.01]
PRIMARY_TARGET = 0.005

FROZEN_CONFIG_ID = "histgb_d2_lr005_l2p1_ood4_sup4_t0050"
FROZEN_CONFIG = {
    "max_depth": 2,
    "learning_rate": 0.05,
    "l2_regularization": 0.1,
    "ood_weight": 4.0,
    "support_weight": 4.0,
    "validation_target": 0.005,
    "max_iter": 60,
}


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


def load_asset(strategy: str, cert: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    c = cert[strategy]
    checks: list[dict[str, Any]] = []
    for key, hash_key in [
        ("X_115D_path", "X_115D_sha256"),
        ("y_path", "y_sha256"),
        ("sidecar_path", "sidecar_sha256"),
        ("split_manifest_path", "split_manifest_sha256"),
        ("feature_schema_path", "feature_schema_sha256"),
        ("state_transition_log_path", "state_transition_log_sha256"),
    ]:
        ok, actual = verify_hash(Path(c[key]), c[hash_key])
        checks.append(
            {
                "strategy": strategy,
                "artifact": key,
                "path": c[key],
                "expected_sha256": c[hash_key],
                "actual_sha256": actual,
                "hash_match": ok,
            }
        )
        if not ok:
            raise RuntimeError(f"hash mismatch for {strategy}:{key}")
    x = np.load(c["X_115D_path"]).astype(np.float32)
    y = np.load(c["y_path"]).astype(np.int64)
    sidecar = load_csv(Path(c["sidecar_path"]))
    schema = json.loads(Path(c["feature_schema_path"]).read_text(encoding="utf-8"))
    if x.shape[0] != y.shape[0] or x.shape[0] != len(sidecar):
        raise RuntimeError(f"row alignment failed for {strategy}")
    if x.shape[1] != 115:
        raise RuntimeError(f"expected Gotham Kitsune115, got {x.shape[1]} columns for {strategy}")
    return {"X": x, "y": y, "sidecar": sidecar, "schema": schema, "certificate": c, "strategy": strategy}, checks


def load_new_heldout() -> tuple[np.ndarray, list[dict[str, str]], list[dict[str, Any]]]:
    if not NEW_HELDOUT_X.exists() or not NEW_HELDOUT_SIDECAR.exists():
        return np.empty((0, 115), dtype=np.float32), [], [
            {
                "artifact": "new_heldout",
                "path": str(NEW_HELDOUT_X),
                "hash_match": False,
                "actual_sha256": "missing",
                "expected_sha256": "",
            }
        ]
    x = np.load(NEW_HELDOUT_X).astype(np.float32)
    sidecar = load_csv(NEW_HELDOUT_SIDECAR)
    if x.shape[0] != len(sidecar) or x.shape[1] != 115:
        raise RuntimeError("new heldout alignment or feature count failed")
    checks = [
        {
            "artifact": "new_heldout_X",
            "path": str(NEW_HELDOUT_X),
            "expected_sha256": "c4c01ba7bb832704202934340abdc577e792a5c5f80ef154939e4b833c31b03c",
            "actual_sha256": sha256(NEW_HELDOUT_X),
            "hash_match": sha256(NEW_HELDOUT_X) == "c4c01ba7bb832704202934340abdc577e792a5c5f80ef154939e4b833c31b03c",
        },
        {
            "artifact": "new_heldout_sidecar",
            "path": str(NEW_HELDOUT_SIDECAR),
            "expected_sha256": "411b0808ad62286fb087ea90ca8d69d1c0200c960007e3f6024049e71583a783",
            "actual_sha256": sha256(NEW_HELDOUT_SIDECAR),
            "hash_match": sha256(NEW_HELDOUT_SIDECAR) == "411b0808ad62286fb087ea90ca8d69d1c0200c960007e3f6024049e71583a783",
        },
    ]
    return x, sidecar, checks


def role_indices(sidecar: list[dict[str, str]], role: str) -> np.ndarray:
    return np.asarray(
        [i for i, r in enumerate(sidecar) if r.get("role") == role and r.get("model_ready_hint", "").lower() == "true"],
        dtype=np.int64,
    )


def deterministic_role_subsplit(idx: np.ndarray, first_fraction: float) -> tuple[np.ndarray, np.ndarray]:
    idx = np.asarray(sorted(map(int, idx.tolist())), dtype=np.int64)
    cut = int(round(len(idx) * first_fraction))
    cut = max(1, min(cut, len(idx) - 1))
    return idx[:cut], idx[cut:]


def farthest_first(z: np.ndarray, budget: int, start_idx: int) -> np.ndarray:
    if z.shape[0] == 0:
        return np.asarray([], dtype=np.int64)
    if budget >= z.shape[0]:
        return np.arange(z.shape[0], dtype=np.int64)
    selected = [int(start_idx)]
    min_dist = pairwise_distances(z, z[[start_idx]], metric="euclidean").ravel()
    min_dist[start_idx] = -1.0
    while len(selected) < budget:
        nxt = int(np.argmax(min_dist))
        selected.append(nxt)
        dist = pairwise_distances(z, z[[nxt]], metric="euclidean").ravel()
        min_dist = np.minimum(min_dist, dist)
        min_dist[selected] = -1.0
    return np.asarray(selected, dtype=np.int64)


def old_kcenter32(x: np.ndarray, support_pool_idx: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    x_pool = x[support_pool_idx]
    scaler = StandardScaler().fit(x_pool)
    z = scaler.transform(x_pool)
    centroid = z.mean(axis=0, keepdims=True)
    start_idx = int(np.argmin(pairwise_distances(z, centroid, metric="euclidean").ravel()))
    local = farthest_first(z, SUPPORT_BUDGET, start_idx)
    selected = np.asarray(sorted(support_pool_idx[local].tolist()), dtype=np.int64)
    return selected, {
        "selector": "old_kcenter32",
        "support_pool_role": SUPPORT_ROLE,
        "support_pool_size": int(len(support_pool_idx)),
        "support_size": int(len(selected)),
        "selector_scaler_fit_roles": SUPPORT_ROLE,
        "distance_metric": "euclidean_after_selector_local_standard_scaler",
        "start_rule": "closest_to_attack_support_centroid",
        "uses_final_ood": False,
        "uses_attack_eval": False,
        "selected_indices_sha256": hash_indices(selected),
    }


def split_support_for_selection(support_rows: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rows = np.asarray(support_rows, dtype=np.int64).copy()
    rng = np.random.default_rng(seed + 27027)
    rng.shuffle(rows)
    return np.asarray(sorted(rows[:SUPPORT_TRAIN_FOR_SELECTION].tolist()), dtype=np.int64), np.asarray(
        sorted(rows[SUPPORT_TRAIN_FOR_SELECTION:].tolist()), dtype=np.int64
    )


def guarded_val_threshold(score_id_calib: np.ndarray, score_ood_val: np.ndarray, target_alarm: float, n_candidates: int = 4000) -> dict[str, Any]:
    pool = np.concatenate([score_id_calib, score_ood_val]).astype(np.float64)
    q_levels = np.linspace(0.0, 1.0, int(n_candidates) + 1)[1:]
    candidates = np.unique(np.quantile(pool, q_levels))
    for thr in sorted(candidates):
        id_alarm = float(np.mean(score_id_calib > thr))
        ood_alarm = float(np.mean(score_ood_val > thr))
        if id_alarm <= float(target_alarm) and ood_alarm <= float(target_alarm):
            return {
                "threshold": float(thr),
                "id_calib_alarm_at_selection": id_alarm,
                "ood_val_alarm_at_selection": ood_alarm,
                "selection_feasible": True,
                "threshold_source": "guarded_val_threshold_id_calib_ood_val",
            }
    thr = float(np.max(pool))
    return {
        "threshold": thr,
        "id_calib_alarm_at_selection": float(np.mean(score_id_calib > thr)),
        "ood_val_alarm_at_selection": float(np.mean(score_ood_val > thr)),
        "selection_feasible": False,
        "threshold_source": "guarded_val_threshold_fallback_max_pool",
    }


class OldLowGuardHistGB:
    def __init__(self, seed: int):
        self.seed = int(seed)
        self.score_direction = 1.0
        self.score_direction_fixed = False
        self.direction_check: dict[str, Any] = {}
        self.model = HistGradientBoostingClassifier(
            max_depth=int(FROZEN_CONFIG["max_depth"]),
            max_iter=int(FROZEN_CONFIG["max_iter"]),
            learning_rate=float(FROZEN_CONFIG["learning_rate"]),
            l2_regularization=float(FROZEN_CONFIG["l2_regularization"]),
            random_state=self.seed,
        )

    def fit(self, x_id_train: np.ndarray, x_ood_train: np.ndarray, x_support_attack: np.ndarray) -> None:
        x_train = np.vstack([x_id_train, x_ood_train, x_support_attack])
        y_train = np.concatenate(
            [
                np.zeros(len(x_id_train), dtype=np.int64),
                np.zeros(len(x_ood_train), dtype=np.int64),
                np.ones(len(x_support_attack), dtype=np.int64),
            ]
        )
        sample_weight = np.concatenate(
            [
                np.ones(len(x_id_train), dtype=np.float64),
                np.full(len(x_ood_train), float(FROZEN_CONFIG["ood_weight"]), dtype=np.float64),
                np.full(len(x_support_attack), float(FROZEN_CONFIG["support_weight"]), dtype=np.float64),
            ]
        )
        self.fit_shape = {
            "id_rows": int(len(x_id_train)),
            "ood_train_rows": int(len(x_ood_train)),
            "support_rows": int(len(x_support_attack)),
            "total_rows": int(len(x_train)),
            "id_weight": 1.0,
            "ood_weight": float(FROZEN_CONFIG["ood_weight"]),
            "support_weight": float(FROZEN_CONFIG["support_weight"]),
            "weighted_normal_to_attack_ratio": float((len(x_id_train) + len(x_ood_train) * float(FROZEN_CONFIG["ood_weight"])) / max(1.0, len(x_support_attack) * float(FROZEN_CONFIG["support_weight"]))),
        }
        self.model.fit(x_train, y_train, sample_weight=sample_weight)
        self._fix_score_direction(x_id_train, x_ood_train, x_support_attack)

    def raw_score(self, x: np.ndarray) -> np.ndarray:
        proba = self.model.predict_proba(x)
        classes = list(self.model.classes_)
        if 1 not in classes:
            raise RuntimeError(f"attack class 1 missing: {classes}")
        return proba[:, classes.index(1)]

    def score(self, x: np.ndarray) -> np.ndarray:
        return self.score_direction * self.raw_score(x)

    def _fix_score_direction(self, x_id_train: np.ndarray, x_ood_train: np.ndarray, x_support_attack: np.ndarray) -> None:
        raw_id = np.asarray(self.raw_score(x_id_train), dtype=np.float64)
        raw_ood = np.asarray(self.raw_score(x_ood_train), dtype=np.float64)
        raw_support = np.asarray(self.raw_score(x_support_attack), dtype=np.float64)
        support_raw_mean = float(np.mean(raw_support))
        id_raw_mean = float(np.mean(raw_id))
        ood_raw_mean = float(np.mean(raw_ood))
        if support_raw_mean < id_raw_mean and support_raw_mean < ood_raw_mean:
            self.score_direction = -1.0
            self.score_direction_fixed = True
        self.direction_check = {
            "support_raw_mean": support_raw_mean,
            "id_train_raw_mean": id_raw_mean,
            "ood_train_raw_mean": ood_raw_mean,
            "support_score_mean": float(np.mean(self.score(x_support_attack))),
            "id_train_score_mean": float(np.mean(self.score(x_id_train))),
            "ood_train_score_mean": float(np.mean(self.score(x_ood_train))),
            "score_direction": self.score_direction,
            "score_direction_fixed": self.score_direction_fixed,
        }


def rate(scores: np.ndarray, threshold: float) -> float:
    return float(np.mean(scores > threshold)) if scores.size else float("nan")


def qstats(scores: np.ndarray) -> dict[str, float]:
    if scores.size == 0:
        return {k: float("nan") for k in ["min", "p50", "p90", "p95", "p99", "max", "mean", "std"]}
    return {
        "min": float(np.min(scores)),
        "p50": float(np.quantile(scores, 0.50)),
        "p90": float(np.quantile(scores, 0.90)),
        "p95": float(np.quantile(scores, 0.95)),
        "p99": float(np.quantile(scores, 0.99)),
        "max": float(np.max(scores)),
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
    }


def run_variant(
    strategy: str,
    asset: dict[str, Any],
    new_x: np.ndarray,
    support_rows: np.ndarray,
    seed: int,
    variant: str,
    id_fit: np.ndarray,
    id_calib: np.ndarray,
    ood_train: np.ndarray,
    ood_val: np.ndarray,
    final_ood: np.ndarray,
    attack_eval: np.ndarray,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    x = asset["X"]
    if variant == "old_formal_fit32":
        support_train = support_rows
        support_val = np.asarray([], dtype=np.int64)
        variant_note = "closest_to_issue27f_formal_refit_full_kcenter32"
    elif variant == "old_selection_style_24_8":
        support_train, support_val = split_support_for_selection(support_rows, seed)
        variant_note = "closest_to_issue27d_config_selection_trace_24_train_8_support_val"
    else:
        raise ValueError(variant)

    model = OldLowGuardHistGB(seed)
    model.fit(x[id_fit], x[ood_train], x[support_train])

    scores = {
        "id_calib": model.score(x[id_calib]),
        "ood_val": model.score(x[ood_val]),
        "final_ood_eval": model.score(x[final_ood]),
        "attack_eval": model.score(x[attack_eval]),
        "support_train": model.score(x[support_train]),
        "support_val": model.score(x[support_val]) if len(support_val) else np.asarray([], dtype=np.float64),
        NEW_HELDOUT_ROLE: model.score(new_x) if new_x.size else np.asarray([], dtype=np.float64),
    }

    result_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    for role, arr in scores.items():
        row = {
            "strategy": strategy,
            "variant": variant,
            "seed": seed,
            "score_role": role,
            "n": int(arr.size),
        }
        row.update(qstats(arr))
        score_rows.append(row)

    for target in TARGETS:
        th = guarded_val_threshold(scores["id_calib"], scores["ood_val"], target)
        threshold = float(th["threshold"])
        row = {
            "strategy": strategy,
            "variant": variant,
            "variant_note": variant_note,
            "seed": seed,
            "config_id": FROZEN_CONFIG_ID,
            "threshold_target": float(target),
            "threshold": threshold,
            "threshold_source": th["threshold_source"],
            "selection_feasible": bool(th["selection_feasible"]),
            "id_calib_alarm": rate(scores["id_calib"], threshold),
            "ood_val_alarm": rate(scores["ood_val"], threshold),
            "support_train_detection": rate(scores["support_train"], threshold),
            "support_val_detection": rate(scores["support_val"], threshold),
            "final_ood_alarm_report_only": rate(scores["final_ood_eval"], threshold),
            "attack_eval_detection_report_only": rate(scores["attack_eval"], threshold),
            "new_heldout_detection_report_only": rate(scores[NEW_HELDOUT_ROLE], threshold),
            "fit_roles": "id_fit_from_id_benign_train|ood_train_guard_from_ood_benign_val|attack_support_kcenter_train",
            "threshold_roles": "id_calib_from_id_benign_train|ood_val_calib_from_ood_benign_val",
            "report_only_roles": f"{FINAL_OOD_ROLE}|{ATTACK_EVAL_ROLE}|{NEW_HELDOUT_ROLE}",
            "final_ood_used_for_selection": False,
            "attack_eval_used_for_selection": False,
            "new_heldout_used_for_selection": False,
            "formal_benchmark": False,
            **model.fit_shape,
            **model.direction_check,
            "support_train_hash": hash_indices(support_train),
            "support_val_hash": hash_indices(support_val),
        }
        result_rows.append(row)
        threshold_rows.append(
            {
                "strategy": strategy,
                "variant": variant,
                "seed": seed,
                "threshold_target": target,
                "threshold": threshold,
                "id_calib_alarm": row["id_calib_alarm"],
                "ood_val_alarm": row["ood_val_alarm"],
                "support_train_detection": row["support_train_detection"],
                "support_val_detection": row["support_val_detection"],
                "final_ood_alarm_report_only": row["final_ood_alarm_report_only"],
                "attack_eval_detection_report_only": row["attack_eval_detection_report_only"],
                "new_heldout_detection_report_only": row["new_heldout_detection_report_only"],
                "selection_feasible": bool(th["selection_feasible"]),
                "uses_final_or_attack_eval_for_threshold": False,
            }
        )
    return result_rows, threshold_rows, score_rows, {
        "strategy": strategy,
        "variant": variant,
        "seed": seed,
        "support_train_size": int(len(support_train)),
        "support_val_size": int(len(support_val)),
        "support_train_hash": hash_indices(support_train),
        "support_val_hash": hash_indices(support_val),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    new_x, _, new_checks = load_new_heldout()

    all_hash_rows: list[dict[str, Any]] = []
    all_result_rows: list[dict[str, Any]] = []
    all_threshold_rows: list[dict[str, Any]] = []
    all_score_rows: list[dict[str, Any]] = []
    support_selector_rows: list[dict[str, Any]] = []
    support_index_rows: list[dict[str, Any]] = []
    subsplit_rows: list[dict[str, Any]] = []
    role_access_rows: list[dict[str, Any]] = []
    support_split_rows: list[dict[str, Any]] = []

    all_hash_rows.extend(new_checks)
    all_hash_rows.append(
        {
            "artifact": "issue27af_medium_certificate",
            "path": str(cert_path),
            "expected_sha256": "",
            "actual_sha256": sha256(cert_path),
            "hash_match": True,
        }
    )
    for p in [ISSUE27F / "summary.md", ISSUE27F / "config_freeze_decision_report.md", ISSUE27D / "run_issue27d_model_specific_objective_smoke.py", ISSUE27AQ / "summary.md"]:
        if p.exists():
            all_hash_rows.append({"artifact": p.name, "path": str(p), "expected_sha256": "", "actual_sha256": sha256(p), "hash_match": True})

    for strategy in sorted(cert.keys()):
        asset, checks = load_asset(strategy, cert)
        all_hash_rows.extend(checks)
        x = asset["X"]
        sidecar = asset["sidecar"]
        id_idx = role_indices(sidecar, ID_ROLE)
        ood_idx = role_indices(sidecar, OOD_VAL_ROLE)
        final_idx = role_indices(sidecar, FINAL_OOD_ROLE)
        support_pool = role_indices(sidecar, SUPPORT_ROLE)
        attack_eval = role_indices(sidecar, ATTACK_EVAL_ROLE)

        id_fit, id_calib = deterministic_role_subsplit(id_idx, 0.80)
        ood_train, ood_val = deterministic_role_subsplit(ood_idx, 0.50)
        support_rows, selector_audit = old_kcenter32(x, support_pool)
        selector_audit["strategy"] = strategy
        support_selector_rows.append(selector_audit)
        for rank, idx in enumerate(support_rows.tolist()):
            support_index_rows.append(
                {
                    "strategy": strategy,
                    "selector": "old_kcenter32",
                    "rank_sorted_output": rank,
                    "global_row_index": int(idx),
                    "role": sidecar[int(idx)].get("role", ""),
                    "label": sidecar[int(idx)].get("label", ""),
                    "attack_type": sidecar[int(idx)].get("attack_type", ""),
                    "source_file": sidecar[int(idx)].get("source_file", ""),
                }
            )
        subsplit_rows.append(
            {
                "strategy": strategy,
                "id_source_role": ID_ROLE,
                "id_fit_rows": int(len(id_fit)),
                "id_calib_rows": int(len(id_calib)),
                "id_subsplit_rule": "row_order_first_80pct_fit_last_20pct_calib_within_train_side_only",
                "ood_source_role": OOD_VAL_ROLE,
                "ood_train_guard_rows": int(len(ood_train)),
                "ood_val_calib_rows": int(len(ood_val)),
                "ood_subsplit_rule": "row_order_first_50pct_fit_guard_last_50pct_calib_within_ood_val_side_only",
                "final_ood_rows": int(len(final_idx)),
                "attack_eval_rows": int(len(attack_eval)),
                "new_heldout_rows": int(new_x.shape[0]),
                "uses_final_or_attack_eval_for_subsplit": False,
                "diagnostic_caveat": "Gotham medium asset lacks old separate id_calib/ood_train roles; train-side/val-side deterministic subsplits are used for fidelity diagnostic only.",
            }
        )
        for seed in SEEDS:
            tr24, val8 = split_support_for_selection(support_rows, seed)
            support_split_rows.append(
                {
                    "strategy": strategy,
                    "seed": seed,
                    "old_support_budget": SUPPORT_BUDGET,
                    "support_train_for_selection": int(len(tr24)),
                    "support_val_for_selection": int(len(val8)),
                    "split_rng": "seed_plus_27027",
                    "support_train_hash": hash_indices(tr24),
                    "support_val_hash": hash_indices(val8),
                }
            )
            for variant in ["old_formal_fit32", "old_selection_style_24_8"]:
                res, th_rows, score_rows, _ = run_variant(
                    strategy=strategy,
                    asset=asset,
                    new_x=new_x,
                    support_rows=support_rows,
                    seed=seed,
                    variant=variant,
                    id_fit=id_fit,
                    id_calib=id_calib,
                    ood_train=ood_train,
                    ood_val=ood_val,
                    final_ood=final_idx,
                    attack_eval=attack_eval,
                )
                all_result_rows.extend(res)
                all_threshold_rows.extend(th_rows)
                all_score_rows.extend(score_rows)
                role_access_rows.append(
                    {
                        "strategy": strategy,
                        "variant": variant,
                        "seed": seed,
                        "fit_roles": "id_fit_from_id_benign_train|ood_train_guard_from_ood_benign_val|attack_support_kcenter_train",
                        "threshold_roles": "id_calib_from_id_benign_train|ood_val_calib_from_ood_benign_val",
                        "support_selector_roles": SUPPORT_ROLE,
                        "report_only_roles": f"{FINAL_OOD_ROLE}|{ATTACK_EVAL_ROLE}|{NEW_HELDOUT_ROLE}",
                        "uses_final_ood_for_fit_threshold_or_selection": False,
                        "uses_attack_eval_for_fit_threshold_or_selection": False,
                        "uses_new_heldout_for_fit_threshold_or_selection": False,
                        "forbidden_role_access": False,
                    }
                )

    write_csv(OUT / "input_artifact_hash_audit.csv", all_hash_rows)
    write_csv(OUT / "protocol_mismatch_table.csv", protocol_mismatch_rows())
    write_csv(OUT / "gotham_train_side_subsplit_audit.csv", subsplit_rows)
    write_csv(OUT / "old_kcenter32_support_selector_audit.csv", support_selector_rows)
    write_csv(OUT / "old_kcenter32_selected_indices.csv", support_index_rows)
    write_csv(OUT / "old_support_24_8_split_audit.csv", support_split_rows)
    write_csv(OUT / "old_lowguardpp_fidelity_by_seed.csv", all_result_rows)
    write_csv(OUT / "old_lowguardpp_threshold_audit.csv", all_threshold_rows)
    write_csv(OUT / "old_lowguardpp_score_distribution_audit.csv", all_score_rows)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)

    primary_rows = [
        r
        for r in all_result_rows
        if r["variant"] == "old_formal_fit32" and abs(float(r["threshold_target"]) - PRIMARY_TARGET) < 1e-12
    ]
    if not primary_rows:
        primary_verdict = "old_lowguardpp_fidelity_blocked_no_primary_rows"
    else:
        attack = np.asarray([float(r["attack_eval_detection_report_only"]) for r in primary_rows])
        new_attack = np.asarray([float(r["new_heldout_detection_report_only"]) for r in primary_rows if r["new_heldout_detection_report_only"] == r["new_heldout_detection_report_only"]])
        final = np.asarray([float(r["final_ood_alarm_report_only"]) for r in primary_rows])
        support = np.asarray([float(r["support_train_detection"]) for r in primary_rows])
        if bool(any(r["forbidden_role_access"] for r in role_access_rows)):
            primary_verdict = "old_lowguardpp_fidelity_blocked_by_forbidden_role_access"
        elif final.max(initial=1.0) <= 0.01 and attack.min(initial=0.0) >= 0.6:
            primary_verdict = "old_protocol_mismatch_likely_explains_prior_weak_signal"
        elif support.max(initial=0.0) > 0 and attack.max(initial=0.0) < 0.2:
            primary_verdict = "old_protocol_fidelity_still_weak_support_query_shift_or_task_boundary"
        elif support.max(initial=0.0) == 0:
            primary_verdict = "old_protocol_fidelity_blocked_by_learning_or_threshold"
        else:
            primary_verdict = "old_protocol_fidelity_mixed_needs_bounded_calibration_repair"

    summary_rows = summarize_rows(all_result_rows)
    write_csv(OUT / "old_lowguardpp_fidelity_summary.csv", summary_rows)
    write_md(
        OUT / "old_lowguardpp_protocol_fidelity_report.md",
        [
            "# Old LOW-GUARD++ Protocol Fidelity Report",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- Scope: Gotham Kitsune115 medium diagnostic only, not formal benchmark.",
            "- Historical protocol target: issue27f LOW-GUARD++ HistGB original100 frozen B.",
            f"- Frozen config: `{FROZEN_CONFIG_ID}` with max_depth=2, learning_rate=0.05, l2=0.1, ood_weight=4, support_weight=4, max_iter=60.",
            "- Support selector: old kcenter32 over the preregistered `attack_support` role only.",
            "- Formal-like variant uses all 32 kcenter support rows for fit.",
            "- Selection-trace-like variant splits support 24/8 using `seed + 27027` for support_val diagnostics.",
            "- Because the Gotham medium asset has no separate `id_calib` or `ood_train` roles, this run uses train/val-side deterministic subsplits and records that caveat.",
            "- Final OOD, attack_eval, and new heldout are report-only and never used for support, fit, threshold, or selection.",
            "",
            "## Why This Is Not Formal",
            "",
            "- Medium asset only; full_contract remains pending.",
            "- Dataset/frontend changed from old original100 to Gotham Kitsune115.",
            "- Internal train-side/val-side subsplits are diagnostic approximations of old roles.",
            "- Results can indicate protocol mismatch but cannot be a paper model ranking.",
        ],
    )
    write_md(
        OUT / "issue27ar_decision.md",
        [
            "# Issue27ar Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "This issue migrates the old LOW-GUARD++ HistGB frozen protocol to the fixed Gotham Kitsune115 medium asset as a fidelity diagnostic. It does not change the split, does not rebuild the frontend, and does not use final/new-heldout roles for selection.",
        ],
    )
    next_action = "issue27as_old_protocol_fidelity_interpretation_or_threshold_repair_without_final_eval"
    write_md(
        OUT / "issue27as_next_action.md",
        [
            "# Issue27as Next Action",
            "",
            f"Recommended next issue: `{next_action}`.",
            "",
            "- If old fidelity restores support/attack signal under low OOD alarm, proceed with a bounded calibration repair that keeps this old protocol skeleton.",
            "- If old fidelity is still weak, do not go full; return to feature/state/support-query boundary or the coverage-aware framework.",
            "- In either route, keep Gotham115 fixed and keep final OOD / attack eval report-only.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27ar.md",
        [
            "# Claim Update After issue27ar",
            "",
            "- The previous Gotham medium weak signal cannot be attributed to LOW-GUARD++ until the old protocol fidelity comparison is interpreted.",
            "- issue27ar is diagnostic only and cannot be written as formal performance.",
            "- Historical issue27f scores remain exploratory evidence from a different asset; they do not transfer as Gotham results.",
            "- Formal claims still require a frozen full/larger Gotham115 asset and pre-registered protocol.",
        ],
    )
    write_md(
        OUT / "summary.md",
        build_summary(primary_verdict, primary_rows, all_result_rows),
    )
    config = {
        "issue": ISSUE,
        "scope": "old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium",
        "formal_benchmark": False,
        "frozen_config_id": FROZEN_CONFIG_ID,
        "frozen_config": FROZEN_CONFIG,
        "support_budget": SUPPORT_BUDGET,
        "support_split": {"train": SUPPORT_TRAIN_FOR_SELECTION, "val": SUPPORT_BUDGET - SUPPORT_TRAIN_FOR_SELECTION, "rng": "seed+27027"},
        "threshold_targets": TARGETS,
        "primary_target": PRIMARY_TARGET,
        "seeds": SEEDS,
        "state_strategies": sorted(cert.keys()),
        "final_eval_report_only": True,
        "new_heldout_report_only": True,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "issue27af_medium_certificate": str(cert_path),
                    "issue27f_old_frozen_summary": str(ISSUE27F / "summary.md"),
                    "issue27d_old_protocol_code": str(ISSUE27D / "run_issue27d_model_specific_objective_smoke.py"),
                    "issue27ap_new_heldout_X": str(NEW_HELDOUT_X),
                },
                "outputs": "runs/issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium_2026-06-03/",
                "selection_policy": "no final OOD, attack_eval, or new heldout used for support, fit, threshold, or model selection",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27ar -->",
        [
            "<!-- issue27ar -->",
            "## issue27ar - Old LOW-GUARD++ protocol fidelity on Gotham115 medium",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- Migrated issue27f HistGB frozen B protocol skeleton to Gotham Kitsune115 medium.",
            "- Uses old kcenter32, old HistGB config, OOD train guard, sample weights, and guarded ID/OOD threshold.",
            "- Diagnostic only; final OOD, attack_eval, and new heldout remain report-only.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27ar -->",
        [
            "<!-- issue27ar -->",
            "## issue27ar - Old LOW-GUARD++ protocol fidelity migration",
            "",
            f"- verdict: `{primary_verdict}`",
            "- purpose: determine whether current Gotham weak signal is partly due to protocol mismatch against old issue27f LOW-GUARD++.",
            f"- outputs: `runs/{ISSUE}/`.",
        ],
    )
    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(json.dumps({"primary_verdict": primary_verdict, "out": str(OUT)}, indent=2))


def protocol_mismatch_rows() -> list[dict[str, Any]]:
    return [
        {
            "component": "frontend",
            "old_issue27f": "original100 static asset",
            "current_issue27ap_aq": "Gotham Kitsune115 medium",
            "issue27ar_fidelity": "Gotham Kitsune115 medium",
            "aligned_in_issue27ar": False,
            "residual_caveat": "frontend and dataset necessarily differ",
        },
        {
            "component": "support_selector",
            "old_issue27f": "kcenter32 from train-side attack pool",
            "current_issue27ap_aq": "file_balanced_v2 / larger stratified support, not old kcenter32",
            "issue27ar_fidelity": "old kcenter32 from preregistered attack_support role",
            "aligned_in_issue27ar": True,
            "residual_caveat": "Gotham support pool differs from old attack_train_pool",
        },
        {
            "component": "support_fit_size",
            "old_issue27f": "formal refit uses all 32 selected support rows",
            "current_issue27ap_aq": "support_train=128 from v2 contract",
            "issue27ar_fidelity": "old_formal_fit32 variant uses all 32",
            "aligned_in_issue27ar": True,
            "residual_caveat": "medium only",
        },
        {
            "component": "support_selection_trace",
            "old_issue27f": "issue27d trace: 24 support_train / 8 support_val by seed+27027 for config selection",
            "current_issue27ap_aq": "v2 support_train/support_val contract",
            "issue27ar_fidelity": "old_selection_style_24_8 variant included",
            "aligned_in_issue27ar": True,
            "residual_caveat": "diagnostic only; frozen config already fixed",
        },
        {
            "component": "histgb_config",
            "old_issue27f": FROZEN_CONFIG_ID,
            "current_issue27ap_aq": "max_iter=30, max_leaf_nodes=15, learning_rate=0.08, no old l2/max_depth",
            "issue27ar_fidelity": FROZEN_CONFIG_ID,
            "aligned_in_issue27ar": True,
            "residual_caveat": "",
        },
        {
            "component": "fit_roles",
            "old_issue27f": "id_train + ood_train + support attack",
            "current_issue27ap_aq": "id_benign_train + support_train only",
            "issue27ar_fidelity": "id_fit + ood_train_guard + support_train",
            "aligned_in_issue27ar": True,
            "residual_caveat": "Gotham lacks explicit ood_train role; uses deterministic subrole from ood_benign_val",
        },
        {
            "component": "sample_weight",
            "old_issue27f": "ID=1, OOD=4, support=4",
            "current_issue27ap_aq": "none",
            "issue27ar_fidelity": "ID=1, OOD=4, support=4",
            "aligned_in_issue27ar": True,
            "residual_caveat": "",
        },
        {
            "component": "threshold",
            "old_issue27f": "guarded_val_threshold(id_calib, ood_val, target=0.005)",
            "current_issue27ap_aq": "support-val constrained threshold over ID/OOD/support_val",
            "issue27ar_fidelity": "guarded_val_threshold(id_calib_subrole, ood_val_subrole, 0.005/0.0075/0.01)",
            "aligned_in_issue27ar": True,
            "residual_caveat": "Gotham lacks explicit id_calib; uses deterministic ID train-side subrole",
        },
        {
            "component": "final_eval_policy",
            "old_issue27f": "report-only",
            "current_issue27ap_aq": "report-only",
            "issue27ar_fidelity": "report-only",
            "aligned_in_issue27ar": True,
            "residual_caveat": "",
        },
    ]


def summarize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, float], list[dict[str, Any]]] = {}
    for r in rows:
        key = (str(r["strategy"]), str(r["variant"]), float(r["threshold_target"]))
        groups.setdefault(key, []).append(r)
    out: list[dict[str, Any]] = []
    for (strategy, variant, target), items in sorted(groups.items()):
        def arr(name: str) -> np.ndarray:
            vals = [float(r[name]) for r in items if r[name] == r[name]]
            return np.asarray(vals, dtype=np.float64)

        attack = arr("attack_eval_detection_report_only")
        new_attack = arr("new_heldout_detection_report_only")
        final = arr("final_ood_alarm_report_only")
        support = arr("support_train_detection")
        support_val = arr("support_val_detection")
        out.append(
            {
                "strategy": strategy,
                "variant": variant,
                "threshold_target": target,
                "seed_count": len(items),
                "attack_eval_detection_mean": float(np.mean(attack)) if attack.size else float("nan"),
                "attack_eval_detection_min": float(np.min(attack)) if attack.size else float("nan"),
                "new_heldout_detection_mean": float(np.mean(new_attack)) if new_attack.size else float("nan"),
                "new_heldout_detection_min": float(np.min(new_attack)) if new_attack.size else float("nan"),
                "final_ood_alarm_max": float(np.max(final)) if final.size else float("nan"),
                "support_train_detection_mean": float(np.mean(support)) if support.size else float("nan"),
                "support_train_detection_min": float(np.min(support)) if support.size else float("nan"),
                "support_val_detection_mean": float(np.mean(support_val)) if support_val.size else float("nan"),
                "feasible_under_1pct_all_seeds": bool(final.size and np.max(final) <= 0.01),
                "diagnostic_only": True,
            }
        )
    return out


def build_summary(primary_verdict: str, primary_rows: list[dict[str, Any]], all_rows: list[dict[str, Any]]) -> list[str]:
    summary = summarize_rows(all_rows)
    primary_summary = [
        r
        for r in summary
        if r["variant"] == "old_formal_fit32" and abs(float(r["threshold_target"]) - PRIMARY_TARGET) < 1e-12
    ]
    best = primary_summary[0] if primary_summary else {}
    return [
        "# Issue27ar Summary",
        "",
        "1. issue27ar completed: yes",
        f"2. primary_verdict: `{primary_verdict}`",
        "3. scope: old LOW-GUARD++ protocol fidelity migration on Gotham Kitsune115 medium; not formal benchmark",
        f"4. frozen old config: `{FROZEN_CONFIG_ID}`",
        "5. old support selector restored: `kcenter32` from preregistered attack_support only",
        "6. old HistGB fit roles restored: `id_fit + ood_train_guard + support_attack`",
        "7. old sample weights restored: `ID=1, OOD=4, support=4`",
        "8. old threshold rule restored: `guarded_val_threshold(id_calib, ood_val, target=0.005)`",
        "9. final OOD / attack_eval / new heldout used for selection: no",
        "10. Gotham caveat: explicit old `id_calib` and `ood_train` roles are absent, so deterministic train/val-side subroles were used for diagnostic fidelity",
        f"11. primary old-formal attack_eval_detection_mean/min: `{best.get('attack_eval_detection_mean', 'NA')}` / `{best.get('attack_eval_detection_min', 'NA')}`",
        f"12. primary old-formal new_heldout_detection_mean/min: `{best.get('new_heldout_detection_mean', 'NA')}` / `{best.get('new_heldout_detection_min', 'NA')}`",
        f"13. primary old-formal final_ood_alarm_max: `{best.get('final_ood_alarm_max', 'NA')}`",
        "14. formal benchmark allowed: no",
        "15. next action: `issue27as_old_protocol_fidelity_interpretation_or_threshold_repair_without_final_eval`",
        "16. commit hash: pending",
    ]


if __name__ == "__main__":
    main()
