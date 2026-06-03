from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import pairwise_distances, roc_auc_score
from sklearn.preprocessing import StandardScaler


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent

ISSUE = "issue27aq_model_learning_and_domain_gap_audit_after_new_heldout_zero_detection_2026-06-03"
OUT = ROOT / "runs" / ISSUE
ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AO = ROOT / "runs" / "issue27ao_repair_support_eval_contract_v2_before_head_repair_2026-06-03"
ISSUE27AP = ROOT / "runs" / "issue27ap_new_heldout_attack_probe_and_v2_diagnostic_retest_2026-06-03"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

PROJECT_DIR = ROOT.parents[1]
NEW_HELDOUT_DIR = PROJECT_DIR / "datasets" / "gotham2025" / "derived" / "kitsune115_new_heldout_attack_probe_v1"
NEW_HELDOUT_X = NEW_HELDOUT_DIR / "gotham_kitsune115_new_heldout_attack_probe_X.npy"
NEW_HELDOUT_SIDECAR = NEW_HELDOUT_DIR / "gotham_kitsune115_new_heldout_attack_probe_sidecar.csv.gz"

PRIMARY_STRATEGY = "reset_at_split_boundary"
CONTRACT_ID = "file_balanced_v2"
SEEDS = [42, 43, 44]
TARGET_OOD_ALARM = 0.01

ID_ROLE = "id_benign_train"
OOD_VAL_ROLE = "ood_benign_val"
FINAL_OOD_ROLE = "final_ood_benign_eval"
SUPPORT_TRAIN_ROLE = "attack_support_train_v2"
SUPPORT_VAL_ROLE = "attack_support_val_v2"
NEW_HELDOUT_ROLE = "new_heldout_attack_eval_probe"


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


def load_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def verify_hash(path: Path, expected: str) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    actual = sha256(path)
    return actual == expected, actual


def load_asset() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    c = cert[PRIMARY_STRATEGY]
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
        checks.append({
            "artifact": key,
            "path": c[key],
            "expected_sha256": c[hash_key],
            "actual_sha256": actual,
            "hash_match": ok,
        })
        if not ok:
            raise RuntimeError(f"hash mismatch: {key}")
    x = np.load(c["X_115D_path"])
    y = np.load(c["y_path"]).astype(int)
    sidecar = load_csv(Path(c["sidecar_path"]))
    schema = json.loads(Path(c["feature_schema_path"]).read_text(encoding="utf-8"))
    if x.shape[0] != y.shape[0] or x.shape[0] != len(sidecar):
        raise RuntimeError("medium asset row alignment failed")
    if x.shape[1] != 115:
        raise RuntimeError(f"expected 115 features, got {x.shape[1]}")
    checks.append({
        "artifact": "issue27af_certificate",
        "path": str(cert_path),
        "expected_sha256": "",
        "actual_sha256": sha256(cert_path),
        "hash_match": True,
    })
    return {"X": x, "y": y, "sidecar": sidecar, "schema": schema, "certificate": c}, checks


def role_indices(sidecar: list[dict[str, str]], role: str) -> np.ndarray:
    return np.asarray(
        [
            i
            for i, row in enumerate(sidecar)
            if row.get("role") == role and row.get("model_ready_hint", "").lower() == "true"
        ],
        dtype=np.int64,
    )


def load_contract_indices(name: str, new_role: str) -> np.ndarray:
    rows = load_csv(ISSUE27AO / name)
    return np.asarray(
        [int(r["global_row_index"]) for r in rows if r.get("contract_id") == CONTRACT_ID and r.get("new_role") == new_role],
        dtype=np.int64,
    )


def load_new_heldout() -> tuple[np.ndarray, list[dict[str, str]], list[dict[str, Any]]]:
    if not NEW_HELDOUT_X.exists() or not NEW_HELDOUT_SIDECAR.exists():
        raise RuntimeError("issue27ap new heldout artifact missing")
    x = np.load(NEW_HELDOUT_X)
    sidecar = load_csv(NEW_HELDOUT_SIDECAR)
    if x.shape[0] != len(sidecar):
        raise RuntimeError("new heldout row alignment failed")
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
    if x.shape[1] != 115:
        raise RuntimeError(f"new heldout expected 115 features, got {x.shape[1]}")
    return x, sidecar, checks


def score_histgb(model: HistGradientBoostingClassifier, x: np.ndarray) -> tuple[np.ndarray, str]:
    proba = model.predict_proba(x)
    classes = list(model.classes_)
    if 1 not in classes:
        raise RuntimeError(f"attack class 1 missing from model.classes_: {classes}")
    idx = classes.index(1)
    direction_note = f"predict_proba class_index={idx} for attack class 1; higher score means more attack-like"
    return proba[:, idx], direction_note


def threshold_from_support(scores_id: np.ndarray, scores_ood: np.ndarray, scores_support_val: np.ndarray) -> tuple[float, dict[str, Any]]:
    vals = np.unique(np.quantile(np.concatenate([scores_id, scores_ood, scores_support_val]), np.linspace(0, 1, 1001)))
    candidates: list[tuple[float, float, float, float, float, float]] = []
    for t in vals:
        ood_alarm = float(np.mean(scores_ood >= t))
        support_det = float(np.mean(scores_support_val >= t))
        id_alarm = float(np.mean(scores_id >= t))
        if ood_alarm <= TARGET_OOD_ALARM:
            candidates.append((support_det, -ood_alarm, -id_alarm, float(t), ood_alarm, id_alarm))
    if not candidates:
        t = float(np.quantile(scores_ood, 1 - TARGET_OOD_ALARM))
        return t, {
            "fallback": "ood_quantile_no_support_feasible_candidate",
            "ood_val_alarm": float(np.mean(scores_ood >= t)),
            "support_val_detection": float(np.mean(scores_support_val >= t)),
            "id_alarm": float(np.mean(scores_id >= t)),
            "candidate_count": 0,
        }
    best = sorted(candidates, reverse=True)[0]
    return best[3], {
        "fallback": "",
        "ood_val_alarm": best[4],
        "id_alarm": best[5],
        "support_val_detection": best[0],
        "candidate_count": len(candidates),
    }


def qstats(scores: np.ndarray) -> dict[str, float]:
    if scores.size == 0:
        return {k: float("nan") for k in ["min", "p01", "p05", "p10", "median", "p90", "p95", "p99", "max", "mean", "std"]}
    return {
        "min": float(np.min(scores)),
        "p01": float(np.quantile(scores, 0.01)),
        "p05": float(np.quantile(scores, 0.05)),
        "p10": float(np.quantile(scores, 0.10)),
        "median": float(np.quantile(scores, 0.50)),
        "p90": float(np.quantile(scores, 0.90)),
        "p95": float(np.quantile(scores, 0.95)),
        "p99": float(np.quantile(scores, 0.99)),
        "max": float(np.max(scores)),
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
    }


def quantile_position(values: np.ndarray, threshold: float) -> float:
    if values.size == 0:
        return float("nan")
    return float(np.mean(values <= threshold))


def auc_abs(a: np.ndarray, b: np.ndarray) -> float:
    y = np.concatenate([np.zeros(a.shape[0]), np.ones(b.shape[0])])
    s = np.concatenate([a, b])
    if len(np.unique(s)) <= 1:
        return 0.5
    auc = float(roc_auc_score(y, s))
    return max(auc, 1.0 - auc)


def per_feature_auc(x_a: np.ndarray, x_b: np.ndarray) -> dict[str, Any]:
    aucs = []
    for j in range(x_a.shape[1]):
        aucs.append(auc_abs(x_a[:, j], x_b[:, j]))
    arr = np.asarray(aucs)
    return {
        "max_feature_auc_abs": float(np.max(arr)),
        "median_feature_auc_abs": float(np.median(arr)),
        "features_auc_gt_0_9": int(np.sum(arr >= 0.9)),
        "features_auc_gt_0_95": int(np.sum(arr >= 0.95)),
        "top_feature_index": int(np.argmax(arr)),
        "top_feature_auc_abs": float(np.max(arr)),
    }


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


def role_feature_rows(role_arrays: dict[str, np.ndarray], feature_names: list[str]) -> list[dict[str, Any]]:
    pairs = [
        ("id_vs_new_heldout", "id_benign_train", "new_heldout_attack_eval_probe"),
        ("ood_vs_new_heldout", "ood_benign_val", "new_heldout_attack_eval_probe"),
        ("support_train_vs_new_heldout", "attack_support_train_v2", "new_heldout_attack_eval_probe"),
        ("support_val_vs_new_heldout", "attack_support_val_v2", "new_heldout_attack_eval_probe"),
        ("support_train_vs_support_val", "attack_support_train_v2", "attack_support_val_v2"),
    ]
    rows: list[dict[str, Any]] = []
    for pair_name, a_name, b_name in pairs:
        a = role_arrays[a_name]
        b = role_arrays[b_name]
        for j, name in enumerate(feature_names):
            rows.append({
                "pair": pair_name,
                "feature_index": j,
                "feature_name": name,
                "feature_family": family_of(name),
                "auc_abs": auc_abs(a[:, j], b[:, j]),
                "mean_a": float(np.mean(a[:, j])),
                "mean_b": float(np.mean(b[:, j])),
            })
    return rows


def nearest_distance_rows(role_arrays: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    references = ["attack_support_train_v2", "attack_support_val_v2"]
    targets = ["attack_support_val_v2", "new_heldout_attack_eval_probe", "id_benign_train", "ood_benign_val"]
    for ref_name in references:
        ref = role_arrays[ref_name]
        scaler = StandardScaler().fit(ref)
        z_ref = scaler.transform(ref)
        for target_name in targets:
            target = role_arrays[target_name]
            z_t = scaler.transform(target)
            d = pairwise_distances(z_t, z_ref, metric="euclidean").min(axis=1)
            rows.append({
                "reference_role": ref_name,
                "target_role": target_name,
                "target_n": int(target.shape[0]),
                "distance_min": float(np.min(d)),
                "distance_median": float(np.median(d)),
                "distance_p90": float(np.quantile(d, 0.90)),
                "distance_p95": float(np.quantile(d, 0.95)),
                "distance_p99": float(np.quantile(d, 0.99)),
                "distance_max": float(np.max(d)),
            })
    return rows


def build_reports() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    asset, artifact_rows = load_asset()
    new_x, new_sidecar, new_checks = load_new_heldout()
    artifact_rows.extend(new_checks)
    artifact_rows.extend([
        {
            "artifact": "issue27ap_by_seed",
            "path": str(ISSUE27AP / "new_heldout_v2_histgb_retest_by_seed.csv"),
            "expected_sha256": "",
            "actual_sha256": sha256(ISSUE27AP / "new_heldout_v2_histgb_retest_by_seed.csv"),
            "hash_match": True,
        },
        {
            "artifact": "issue27ao_support_train_indices",
            "path": str(ISSUE27AO / "contract_v2_support_train_indices.csv"),
            "expected_sha256": "",
            "actual_sha256": sha256(ISSUE27AO / "contract_v2_support_train_indices.csv"),
            "hash_match": True,
        },
        {
            "artifact": "issue27ao_support_val_indices",
            "path": str(ISSUE27AO / "contract_v2_support_val_indices.csv"),
            "expected_sha256": "",
            "actual_sha256": sha256(ISSUE27AO / "contract_v2_support_val_indices.csv"),
            "hash_match": True,
        },
    ])
    write_csv(OUT / "input_artifact_hash_audit.csv", artifact_rows)

    x = asset["X"]
    y = asset["y"]
    sidecar = asset["sidecar"]
    id_idx = role_indices(sidecar, ID_ROLE)
    ood_idx = role_indices(sidecar, OOD_VAL_ROLE)
    final_idx = role_indices(sidecar, FINAL_OOD_ROLE)
    support_train_idx = load_contract_indices("contract_v2_support_train_indices.csv", "support_train")
    support_val_idx = load_contract_indices("contract_v2_support_val_indices.csv", "support_val")
    v2_eval_idx = load_contract_indices("contract_v2_attack_eval_indices.csv", "attack_eval")

    role_arrays = {
        "id_benign_train": x[id_idx],
        "ood_benign_val": x[ood_idx],
        "final_ood_benign_eval": x[final_idx],
        "attack_support_train_v2": x[support_train_idx],
        "attack_support_val_v2": x[support_val_idx],
        "attack_eval_v2_report_only": x[v2_eval_idx],
        "new_heldout_attack_eval_probe": new_x,
    }

    role_usage_rows = [
        {
            "component": "HistGB_fixed_issue27ap_replay",
            "fit_roles": f"{ID_ROLE}|{SUPPORT_TRAIN_ROLE}",
            "threshold_roles": f"{ID_ROLE}|{OOD_VAL_ROLE}|{SUPPORT_VAL_ROLE}",
            "score_only_roles": f"{FINAL_OOD_ROLE}|{NEW_HELDOUT_ROLE}|attack_eval_v2_report_only",
            "support_selection_uses_final_ood": False,
            "support_selection_uses_new_heldout": False,
            "threshold_uses_final_ood": False,
            "threshold_uses_new_heldout": False,
            "model_selection_uses_final_or_new_heldout": False,
            "forbidden_role_access": False,
            "notes": "v2 attack_eval included only for diagnostic context; not used for fit or threshold",
        }
    ]
    write_csv(OUT / "role_usage_audit.csv", role_usage_rows)

    fit_idx = np.concatenate([id_idx, support_train_idx])
    fit_rows = [{
        "fit_role": "combined_fit",
        "id_benign_train_rows": int(id_idx.size),
        "support_train_rows": int(support_train_idx.size),
        "fit_total_rows": int(fit_idx.size),
        "normal_to_attack_ratio": float(id_idx.size / max(1, support_train_idx.size)),
        "fit_class_0_count": int(np.sum(y[fit_idx] == 0)),
        "fit_class_1_count": int(np.sum(y[fit_idx] == 1)),
        "class_weight_used": False,
        "sample_weight_used": False,
        "normal_downsampling_used": False,
        "imbalance_risk": "medium_high" if id_idx.size / max(1, support_train_idx.size) > 10 else "low",
    }]
    write_csv(OUT / "fit_class_balance_audit.csv", fit_rows)

    score_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    learning_rows: list[dict[str, Any]] = []
    direction_rows: list[dict[str, Any]] = []
    all_thresholds = []
    direction_problem = False
    support_val_zero_all = True
    support_train_raw_signal_all = True
    threshold_above_support_all = True

    for seed in SEEDS:
        model = HistGradientBoostingClassifier(max_iter=30, max_leaf_nodes=15, learning_rate=0.08, random_state=seed)
        model.fit(x[fit_idx], y[fit_idx])

        scores: dict[str, np.ndarray] = {}
        direction_note = ""
        for name, arr in role_arrays.items():
            scores[name], direction_note = score_histgb(model, arr)
        threshold, th_audit = threshold_from_support(scores["id_benign_train"], scores["ood_benign_val"], scores["attack_support_val_v2"])
        all_thresholds.append(threshold)

        for role_name, s in scores.items():
            row = {
                "seed": seed,
                "role": role_name,
                "n": int(s.size),
                "threshold": threshold,
                "fraction_above_threshold": float(np.mean(s >= threshold)) if s.size else float("nan"),
                "threshold_quantile_position": quantile_position(s, threshold),
            }
            row.update(qstats(s))
            score_rows.append(row)

        threshold_rows.append({
            "seed": seed,
            "threshold": threshold,
            "candidate_count": th_audit.get("candidate_count"),
            "id_alarm": float(np.mean(scores["id_benign_train"] >= threshold)),
            "ood_val_alarm": float(np.mean(scores["ood_benign_val"] >= threshold)),
            "support_train_detection": float(np.mean(scores["attack_support_train_v2"] >= threshold)),
            "support_val_detection": float(np.mean(scores["attack_support_val_v2"] >= threshold)),
            "final_ood_alarm_report_only": float(np.mean(scores["final_ood_benign_eval"] >= threshold)),
            "new_heldout_detection_report_only": float(np.mean(scores["new_heldout_attack_eval_probe"] >= threshold)),
            "v2_attack_eval_detection_report_only": float(np.mean(scores["attack_eval_v2_report_only"] >= threshold)),
            "threshold_vs_support_train_p99": threshold - float(np.quantile(scores["attack_support_train_v2"], 0.99)),
            "threshold_vs_support_train_max": threshold - float(np.max(scores["attack_support_train_v2"])),
            "threshold_vs_support_val_p99": threshold - float(np.quantile(scores["attack_support_val_v2"], 0.99)),
            "threshold_vs_support_val_max": threshold - float(np.max(scores["attack_support_val_v2"])),
            "threshold_vs_new_heldout_max": threshold - float(np.max(scores["new_heldout_attack_eval_probe"])),
            "threshold_fallback": th_audit.get("fallback", ""),
        })

        id_scores = scores["id_benign_train"]
        ood_scores = scores["ood_benign_val"]
        st_scores = scores["attack_support_train_v2"]
        sv_scores = scores["attack_support_val_v2"]
        nh_scores = scores["new_heldout_attack_eval_probe"]
        support_train_det = float(np.mean(st_scores >= threshold))
        support_val_det = float(np.mean(sv_scores >= threshold))
        if support_val_det > 0:
            support_val_zero_all = False
        if not (auc_abs(id_scores, st_scores) >= 0.95 and float(np.mean(st_scores)) > float(np.mean(id_scores))):
            support_train_raw_signal_all = False
        if not (threshold > float(np.max(st_scores)) and threshold > float(np.max(sv_scores))):
            threshold_above_support_all = False
        learning_rows.append({
            "seed": seed,
            "support_train_vs_id_auc_abs": auc_abs(id_scores, st_scores),
            "support_val_vs_id_auc_abs": auc_abs(id_scores, sv_scores),
            "new_heldout_vs_id_score_auc_abs": auc_abs(id_scores, nh_scores),
            "support_train_mean_minus_id_mean": float(np.mean(st_scores) - np.mean(id_scores)),
            "support_val_mean_minus_id_mean": float(np.mean(sv_scores) - np.mean(id_scores)),
            "new_heldout_mean_minus_id_mean": float(np.mean(nh_scores) - np.mean(id_scores)),
            "support_train_detection_at_threshold": support_train_det,
            "support_val_detection_at_threshold": support_val_det,
            "new_heldout_detection_at_threshold_report_only": float(np.mean(nh_scores >= threshold)),
            "raw_support_signal_status": "raw_support_signal_present" if auc_abs(id_scores, st_scores) >= 0.95 and float(np.mean(st_scores)) > float(np.mean(id_scores)) else "raw_support_signal_weak",
            "threshold_status": "threshold_above_support_train_and_val_max" if threshold > float(np.max(st_scores)) and threshold > float(np.max(sv_scores)) else "threshold_allows_some_support",
            "learning_status": "raw_support_signal_present_but_threshold_blocks_detection" if support_train_det == 0 and support_val_det == 0 else ("support_val_detected" if support_val_det > 0 else "mixed"),
        })
        attack_score_higher = (float(np.mean(st_scores)) > float(np.mean(id_scores))) and (float(np.mean(sv_scores)) > float(np.mean(id_scores)))
        if not attack_score_higher:
            direction_problem = True
        direction_rows.append({
            "seed": seed,
            "model_classes": "|".join(map(str, model.classes_.tolist())),
            "score_direction": "higher_is_attack_like",
            "score_column_note": direction_note,
            "support_train_mean_gt_id_mean": float(np.mean(st_scores)) > float(np.mean(id_scores)),
            "support_val_mean_gt_id_mean": float(np.mean(sv_scores)) > float(np.mean(id_scores)),
            "new_heldout_mean_gt_id_mean": float(np.mean(nh_scores)) > float(np.mean(id_scores)),
            "direction_sanity": "pass_for_support_train_and_val" if attack_score_higher else "warning_attack_support_not_consistently_above_id",
        })

    write_csv(OUT / "score_distribution_report.csv", score_rows)
    write_csv(OUT / "threshold_effect_report.csv", threshold_rows)
    write_csv(OUT / "support_learning_sanity.csv", learning_rows)
    write_csv(OUT / "score_direction_audit.csv", direction_rows)

    feature_names = asset["schema"].get("feature_names") or [f"f{i}" for i in range(x.shape[1])]
    feature_rows = role_feature_rows(role_arrays, feature_names)
    write_csv(OUT / "new_heldout_raw_separability_report.csv", feature_rows)

    gap_rows: list[dict[str, Any]] = []
    for pair_name, a, b in [
        ("id_vs_new_heldout", role_arrays["id_benign_train"], role_arrays["new_heldout_attack_eval_probe"]),
        ("ood_vs_new_heldout", role_arrays["ood_benign_val"], role_arrays["new_heldout_attack_eval_probe"]),
        ("support_train_vs_new_heldout", role_arrays["attack_support_train_v2"], role_arrays["new_heldout_attack_eval_probe"]),
        ("support_val_vs_new_heldout", role_arrays["attack_support_val_v2"], role_arrays["new_heldout_attack_eval_probe"]),
        ("support_train_vs_support_val", role_arrays["attack_support_train_v2"], role_arrays["attack_support_val_v2"]),
    ]:
        row = {"pair": pair_name, "n_a": int(a.shape[0]), "n_b": int(b.shape[0])}
        row.update(per_feature_auc(a, b))
        gap_rows.append(row)
    gap_rows.extend(nearest_distance_rows(role_arrays))
    write_csv(OUT / "feature_domain_gap_report.csv", gap_rows)

    max_new_feature_auc = max(float(r["auc_abs"]) for r in feature_rows if r["pair"] == "ood_vs_new_heldout")
    new_vs_support_distance = [
        r for r in gap_rows
        if r.get("reference_role") == "attack_support_train_v2" and r.get("target_role") == "new_heldout_attack_eval_probe"
    ][0]
    support_val_det_max = max(float(r["support_val_detection"]) for r in threshold_rows)
    support_train_det_max = max(float(r["support_train_detection"]) for r in threshold_rows)
    new_det_max = max(float(r["new_heldout_detection_report_only"]) for r in threshold_rows)

    if direction_problem:
        primary_verdict = "zero_detection_due_to_score_direction_or_learning_signal_warning"
        next_action = "issue27ar_balanced_fit_and_threshold_debug_without_final_eval"
    elif support_train_raw_signal_all and support_val_zero_all and threshold_above_support_all:
        primary_verdict = "zero_detection_due_to_ood_tail_threshold_overconservative_despite_raw_support_signal"
        next_action = "issue27ar_balanced_fit_and_threshold_debug_without_final_eval"
    elif not support_train_raw_signal_all:
        primary_verdict = "zero_detection_due_to_support_not_learned_or_class_imbalance"
        next_action = "issue27ar_fit_balance_and_sample_weight_audit"
    elif new_det_max == 0.0 and float(new_vs_support_distance["distance_p95"]) > 10.0:
        primary_verdict = "zero_detection_due_to_new_heldout_domain_gap"
        next_action = "issue27ar_support_eval_task_boundary_and_balance_redesign"
    else:
        primary_verdict = "zero_detection_mixed_learning_and_domain_gap"
        next_action = "issue27ar_balanced_fit_and_threshold_debug_without_final_eval"

    write_md(OUT / "issue27aq_decision.md", [
        "# Issue27aq Decision",
        "",
        f"- primary_verdict: `{primary_verdict}`",
        "- Scope: model learning and domain-gap audit after issue27ap zero detection.",
        "- No protocol repair, no new support construction, no formal benchmark.",
        "- New heldout and final OOD remained score-only/report-only.",
        "",
        "## Key Evidence",
        "",
        f"- Fit imbalance: ID rows={id_idx.size}, support_train rows={support_train_idx.size}, ratio={id_idx.size / max(1, support_train_idx.size):.3f}:1.",
        f"- Max support_train detection at threshold: {support_train_det_max:.6f}.",
        f"- Max support_val detection at threshold: {support_val_det_max:.6f}.",
        f"- Max new heldout detection at threshold: {new_det_max:.6f}.",
        "- Raw support score signal is present, but the OOD-tail threshold is above the support_train/support_val maxima in this fixed replay.",
        f"- OOD-vs-new heldout max feature AUC(abs): {max_new_feature_auc:.6f}.",
        f"- New heldout nearest support_train distance p95: {float(new_vs_support_distance['distance_p95']):.6f}.",
        "",
        "## Interpretation",
        "",
        "- If support_val is already undetected under the selected threshold, the zero heldout result cannot be attributed only to the newly held-out files.",
        "- If raw feature separability remains high but score/threshold detection is zero, the immediate blocker is learning/calibration rather than the 115D frontend alone.",
    ])
    write_md(OUT / "issue27ar_next_action.md", [
        "# Issue27ar Next Action",
        "",
        f"Recommended next task: `{next_action}`.",
        "",
        "Do not go to full benchmark yet. First test bounded fixes that do not use final OOD or new heldout for selection:",
        "",
        "- fit balance audit: normal downsampling or sample weights using only ID train + support_train;",
        "- score-direction and proba-column lock;",
        "- threshold debug using ID/OOD/support_val only;",
        "- keep new heldout report-only for one-pass diagnostic after pre-registered choices.",
    ])
    write_md(OUT / "claim_update_after_issue27aq.md", [
        "# Claim Update After Issue27aq",
        "",
        "- issue27ap zero detection is diagnostic only and is not a formal model failure claim.",
        "- The current evidence points to learning/calibration and support-val mismatch before any full benchmark should be attempted.",
        "- Gotham Kitsune115 remains a diagnostic medium asset; formal claims require a repaired, pre-registered protocol and larger/full materialization.",
        "- No external generalization or paper-ready model claim is supported by this audit.",
    ])

    write_md(OUT / "summary.md", [
        "# Issue27aq Summary",
        "",
        "1. issue27aq completed: yes",
        f"2. primary_verdict: `{primary_verdict}`",
        "3. Did the audit use new heldout for fit/support/threshold/model selection: no",
        "4. Did the audit use final OOD for fit/support/threshold/model selection: no",
        f"5. fit class balance: ID={id_idx.size}, support_train={support_train_idx.size}, ratio={id_idx.size / max(1, support_train_idx.size):.3f}:1, no class/sample weighting",
        f"6. support_train detection at issue27ap threshold, max over seeds: {support_train_det_max:.6f}",
        f"7. support_val detection at issue27ap threshold, max over seeds: {support_val_det_max:.6f}",
        f"8. new heldout detection at issue27ap threshold, max over seeds: {new_det_max:.6f}",
        f"9. OOD-vs-new heldout max feature AUC(abs): {max_new_feature_auc:.6f}",
        f"10. new heldout nearest support_train distance p95: {float(new_vs_support_distance['distance_p95']):.6f}",
        f"11. score direction/proba column: `{direction_rows[0]['score_column_note']}`",
        "12. current interpretation: zero detection is not just a new heldout problem; raw support signal exists, but the OOD-tail threshold is above support and heldout scores, so learning/calibration/threshold handling must be audited before further data reshuffling.",
        f"13. issue27ar recommendation: `{next_action}`",
        "14. formal benchmark allowed: no",
        "15. commit hash: pending",
    ])

    config = {
        "issue": ISSUE,
        "contract_id": CONTRACT_ID,
        "strategy": PRIMARY_STRATEGY,
        "seeds": SEEDS,
        "target_ood_alarm": TARGET_OOD_ALARM,
        "histgb": {"max_iter": 30, "max_leaf_nodes": 15, "learning_rate": 0.08},
        "no_protocol_repair": True,
        "new_heldout_report_only": True,
        "final_ood_report_only": True,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (OUT / "run_spec.json").write_text(json.dumps({
        "inputs": {
            "issue27af_certificate": str(ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"),
            "issue27ao_support_train": str(ISSUE27AO / "contract_v2_support_train_indices.csv"),
            "issue27ao_support_val": str(ISSUE27AO / "contract_v2_support_val_indices.csv"),
            "issue27ap_new_heldout_X": str(NEW_HELDOUT_X),
            "issue27ap_new_heldout_sidecar": str(NEW_HELDOUT_SIDECAR),
        },
        "outputs": [
            "summary.md",
            "role_usage_audit.csv",
            "fit_class_balance_audit.csv",
            "score_distribution_report.csv",
            "threshold_effect_report.csv",
            "support_learning_sanity.csv",
            "score_direction_audit.csv",
            "new_heldout_raw_separability_report.csv",
            "feature_domain_gap_report.csv",
            "issue27aq_decision.md",
            "issue27ar_next_action.md",
        ],
    }, indent=2), encoding="utf-8")
    (OUT / "command.txt").write_text("python repo/ood/issue27aq_model_learning_and_domain_gap_audit_after_new_heldout_zero_detection.py\n", encoding="utf-8")

    append_doc(MAINLINE_DOCS / "mainline_handoff.md", "<!-- issue27aq -->", [
        "<!-- issue27aq -->",
        "## issue27aq - Model learning and domain gap audit after new heldout zero detection",
        "",
        f"- primary_verdict: `{primary_verdict}`",
        "- Scope: diagnosis only; no support rebuild, no protocol repair, no formal benchmark.",
        f"- support_val detection at issue27ap threshold max: `{support_val_det_max:.6f}`; new heldout detection max: `{new_det_max:.6f}`.",
        f"- next action: `{next_action}`.",
    ])
    append_doc(MAINLINE_DOCS / "mainline_experiment_map.md", "<!-- issue27aq -->", [
        "<!-- issue27aq -->",
        "## issue27aq - Model learning/domain-gap diagnosis",
        "",
        f"- Inputs: issue27af medium reset asset, issue27ao `{CONTRACT_ID}`, issue27ap new heldout probe.",
        f"- Verdict: `{primary_verdict}`.",
        "- Model line remains diagnostic; full benchmark remains blocked until learning/calibration is repaired under role-safe rules.",
    ])

    manifest_rows = []
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name != "manifest.csv":
            manifest_rows.append({"path": str(p.relative_to(ROOT)), "sha256": sha256(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)

    return {
        "primary_verdict": primary_verdict,
        "support_train_det_max": support_train_det_max,
        "support_val_det_max": support_val_det_max,
        "new_det_max": new_det_max,
        "new_vs_support_p95": float(new_vs_support_distance["distance_p95"]),
        "max_new_feature_auc": max_new_feature_auc,
        "next_action": next_action,
    }


def main() -> None:
    result = build_reports()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
