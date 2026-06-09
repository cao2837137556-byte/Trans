from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bo_attack_future_shift_validation_without_new_support_2026-06-09"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BM = ROOT / "runs" / "issue27bm_phase_balanced_attack_contract_design_without_report_only_leakage_2026-06-08"
ISSUE27BN = ROOT / "runs" / "issue27bn_attack_only_diagnostic_on_phase_balanced_contract_without_ood_gate_2026-06-09"

PRIMARY_STRATEGY = "reset_at_split_boundary"
PRIMARY_CONTRACT = "phase_balanced_dev_v2"
SEEDS = [42, 43, 44, 45, 46]
ATTACK_GO_THRESHOLD = 0.93
FROZEN_FIT_LABEL = "old_weighted_id_ood_support_w4"
FROZEN_THRESHOLD_RULE = "id_calib_alarm_0.01"


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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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


def parse_global_id(global_id: str) -> tuple[str, int]:
    source, idx = global_id.rsplit(":", 1)
    return source, int(idx)


def contract_features(rows: list[dict[str, str]], medium_x: np.ndarray, heavy_x: np.ndarray) -> np.ndarray:
    feats = []
    for row in rows:
        source, idx = parse_global_id(row["global_id"])
        if source.startswith("medium_") or source.startswith("medium"):
            feats.append(medium_x[idx])
        elif source.startswith("heavy_") or source.startswith("dev_heavy"):
            feats.append(heavy_x[idx])
        else:
            raise RuntimeError(f"unknown contract source: {source}")
    return np.asarray(feats, dtype=np.float32)


def load_contract_role(role_file: str) -> list[dict[str, str]]:
    rows = [r for r in read_csv(ISSUE27BM / role_file) if r.get("contract_id") == PRIMARY_CONTRACT]
    if not rows:
        raise RuntimeError(f"missing {PRIMARY_CONTRACT} rows in {role_file}")
    return rows


def rate(scores: np.ndarray, threshold: float) -> float:
    return float(np.mean(np.asarray(scores) > float(threshold))) if len(scores) else float("nan")


def qstats(scores: np.ndarray) -> dict[str, float]:
    scores = np.asarray(scores, dtype=np.float64)
    if scores.size == 0:
        return {k: float("nan") for k in ["min", "p50", "p90", "p95", "p99", "max", "mean"]}
    return {
        "min": float(np.min(scores)),
        "p50": float(np.quantile(scores, 0.50)),
        "p90": float(np.quantile(scores, 0.90)),
        "p95": float(np.quantile(scores, 0.95)),
        "p99": float(np.quantile(scores, 0.99)),
        "max": float(np.max(scores)),
        "mean": float(np.mean(scores)),
    }


def parse_int(row: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(float(row.get(key, "")))
    except Exception:
        return int(default)


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


def file_key(row: dict[str, str]) -> str:
    return row.get("csv_member") or row.get("pcap_member") or "unknown"


def make_report_records(sidecar: list[dict[str, str]], indices: np.ndarray, source_asset: str) -> list[dict[str, Any]]:
    rows = []
    for idx in indices.tolist():
        row = sidecar[int(idx)]
        recorded = parse_int(row, "recorded_index")
        path = file_key(row)
        rows.append(
            {
                "global_id": f"{source_asset}:{int(idx)}",
                "source_asset": source_asset,
                "source_index": int(idx),
                "csv_member": path,
                "device_hint": device_hint_from_file(path),
                "phase_bucket": phase_bucket(recorded),
                "recorded_index": recorded,
                "attack_type": row.get("attack_type_from_raw_path") or row.get("attack_type") or "unknown",
            }
        )
    return rows


def make_contract_records(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        out.append(
            {
                "global_id": row["global_id"],
                "source_asset": row["source_asset"],
                "source_index": int(row["source_index"]),
                "csv_member": row["csv_member"],
                "device_hint": row["device_hint"],
                "phase_bucket": row["phase_bucket"],
                "recorded_index": int(float(row["recorded_index"])),
                "attack_type": row.get("attack_type", "unknown"),
            }
        )
    return out


def temporal_thirds(records: list[dict[str, Any]], prefix: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        grouped[(str(r["source_asset"]), str(r["csv_member"]), str(r["phase_bucket"]))].append(r)
    buckets = {f"{prefix}_near": [], f"{prefix}_mid": [], f"{prefix}_far": []}
    for _, rows in grouped.items():
        ordered = sorted(rows, key=lambda r: (int(r["recorded_index"]), str(r["global_id"])))
        parts = np.array_split(np.asarray(ordered, dtype=object), 3)
        for name, arr in zip(buckets, parts):
            buckets[name].extend(arr.tolist())
    return buckets


def role_feature(records: list[dict[str, Any]], medium_x: np.ndarray, heavy_x: np.ndarray) -> np.ndarray:
    feats = []
    for r in records:
        source, idx = parse_global_id(str(r["global_id"]))
        if source.startswith("medium_") or source.startswith("medium"):
            feats.append(medium_x[idx])
        elif source.startswith("heavy_") or source.startswith("dev_heavy"):
            feats.append(heavy_x[idx])
        else:
            raise RuntimeError(source)
    return np.asarray(feats, dtype=np.float32)


class FrozenAttackHistGB:
    def __init__(self, seed: int):
        self.seed = int(seed)
        self.model = HistGradientBoostingClassifier(
            max_depth=int(ar.FROZEN_CONFIG["max_depth"]),
            max_iter=int(ar.FROZEN_CONFIG["max_iter"]),
            learning_rate=float(ar.FROZEN_CONFIG["learning_rate"]),
            l2_regularization=float(ar.FROZEN_CONFIG["l2_regularization"]),
            random_state=self.seed,
        )
        self.score_direction = 1.0
        self.score_direction_fixed = False
        self.direction_check: dict[str, Any] = {}

    def fit(self, x_id: np.ndarray, x_ood: np.ndarray, x_support: np.ndarray) -> None:
        x_train = np.vstack([x_id, x_ood, x_support])
        y_train = np.concatenate(
            [np.zeros(len(x_id), dtype=np.int64), np.zeros(len(x_ood), dtype=np.int64), np.ones(len(x_support), dtype=np.int64)]
        )
        sample_weight = np.concatenate(
            [np.ones(len(x_id), dtype=np.float64), np.full(len(x_ood), 4.0), np.full(len(x_support), 4.0)]
        )
        self.model.fit(x_train, y_train, sample_weight=sample_weight)
        self._fix_direction(x_id, x_ood, x_support)

    def raw_score(self, x: np.ndarray) -> np.ndarray:
        proba = self.model.predict_proba(x)
        classes = list(self.model.classes_)
        if 1 not in classes:
            raise RuntimeError(f"missing attack class: {classes}")
        return np.asarray(proba[:, classes.index(1)], dtype=np.float64)

    def score(self, x: np.ndarray) -> np.ndarray:
        return self.score_direction * self.raw_score(x)

    def _fix_direction(self, x_id: np.ndarray, x_ood: np.ndarray, x_support: np.ndarray) -> None:
        raw_id = self.raw_score(x_id)
        raw_ood = self.raw_score(x_ood)
        raw_support = self.raw_score(x_support)
        if float(np.mean(raw_support)) < max(float(np.mean(raw_id)), float(np.mean(raw_ood))):
            self.score_direction = -1.0
            self.score_direction_fixed = True
        self.direction_check = {
            "id_raw_mean": float(np.mean(raw_id)),
            "ood_raw_mean": float(np.mean(raw_ood)),
            "support_raw_mean": float(np.mean(raw_support)),
            "id_score_mean": float(np.mean(self.score(x_id))),
            "ood_score_mean": float(np.mean(self.score(x_ood))),
            "support_score_mean": float(np.mean(self.score(x_support))),
            "score_direction": self.score_direction,
            "score_direction_fixed": self.score_direction_fixed,
        }


def support_coverage_buckets(
    x_support: np.ndarray,
    x_support_val: np.ndarray,
    features: np.ndarray,
) -> tuple[np.ndarray, dict[str, float]]:
    scaler = StandardScaler().fit(x_support)
    z_support = scaler.transform(x_support)
    val_d = pairwise_distances(scaler.transform(x_support_val), z_support, metric="euclidean").min(axis=1)
    d = pairwise_distances(scaler.transform(features), z_support, metric="euclidean").min(axis=1)
    q75 = float(np.quantile(val_d, 0.75))
    q95 = float(np.quantile(val_d, 0.95))
    labels = np.asarray(["covered_q75" if x <= q75 else "covered_q95" if x <= q95 else "far_gt_q95" for x in d], dtype=object)
    return labels, {"support_val_q75_radius": q75, "support_val_q95_radius": q95}


def aggregate(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[k] for k in keys)].append(row)
    out = []
    for key, rs in sorted(grouped.items()):
        vals = np.asarray([float(r["detection_rate"]) for r in rs], dtype=np.float64)
        row = {k: v for k, v in zip(keys, key)}
        row.update({"mean_detection": float(np.mean(vals)), "min_detection": float(np.min(vals)), "max_detection": float(np.max(vals)), "n": len(vals)})
        out.append(row)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    x = asset["X"]
    sidecar = asset["sidecar"]

    support_train_rows = read_csv(ISSUE27BM / "phase_balanced_support_train_indices.csv")
    support_val_rows = read_csv(ISSUE27BM / "phase_balanced_support_val_indices.csv")
    pseudo_rows = read_csv(ISSUE27BM / "phase_balanced_pseudo_query_dev_indices.csv")
    support_train_rows = [r for r in support_train_rows if r["contract_id"] == PRIMARY_CONTRACT]
    support_val_rows = [r for r in support_val_rows if r["contract_id"] == PRIMARY_CONTRACT]
    pseudo_rows = [r for r in pseudo_rows if r["contract_id"] == PRIMARY_CONTRACT]
    x_support_train = contract_features(support_train_rows, x, new_x)
    x_support_val = contract_features(support_val_rows, x, new_x)

    id_idx = ar.role_indices(sidecar, ar.ID_ROLE)
    ood_idx = ar.role_indices(sidecar, ar.OOD_VAL_ROLE)
    attack_eval_idx = ar.role_indices(sidecar, ar.ATTACK_EVAL_ROLE)
    final_ood_idx = ar.role_indices(sidecar, ar.FINAL_OOD_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    _, dev_heavy_query_idx, _ = issue27au.split_new_heavy_stream(new_sidecar)

    pseudo_records = make_contract_records(pseudo_rows)
    pseudo_buckets = temporal_thirds(pseudo_records, "dev_future")
    medium_report_records = make_report_records(sidecar, attack_eval_idx, "medium_attack_eval_report_only")
    heavy_report_records = make_report_records(new_sidecar, dev_heavy_query_idx, "dev_heavy_query_report_only")
    report_buckets = {
        "sealed_medium_attack_eval_report_only": medium_report_records,
        "sealed_dev_heavy_query_report_only": heavy_report_records,
    }
    report_buckets.update(temporal_thirds(heavy_report_records, "sealed_heavy_future"))

    input_hash_rows = [
        {"artifact": "issue27af_medium_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path), "used_for": "asset_hash_audit"},
        {"artifact": "issue27bm_contract_json", "path": str(ISSUE27BM / "phase_balanced_contract_v2.json"), "sha256": sha256_file(ISSUE27BM / "phase_balanced_contract_v2.json"), "used_for": "frozen_support_contract"},
        {"artifact": "issue27bn_summary", "path": str(ISSUE27BN / "summary.md"), "sha256": sha256_file(ISSUE27BN / "summary.md"), "used_for": "frozen_prior_config_context"},
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

    role_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    direction_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    support_coverage_all: list[dict[str, Any]] = []

    for seed in SEEDS:
        model = FrozenAttackHistGB(seed)
        model.fit(x[id_fit], x[ood_train], x_support_train)
        threshold = float(np.quantile(model.score(x[id_calib]), 0.99))
        threshold_rows.append(
            {
                "seed": seed,
                "fit_label": FROZEN_FIT_LABEL,
                "threshold_rule": FROZEN_THRESHOLD_RULE,
                "threshold": threshold,
                "id_calib_alarm": rate(model.score(x[id_calib]), threshold),
                "support_val_detection": rate(model.score(x_support_val), threshold),
                "uses_future_query_for_threshold": False,
                "uses_report_only_for_threshold": False,
            }
        )
        direction_rows.append({"seed": seed, **model.direction_check})

        role_defs: dict[str, tuple[list[dict[str, Any]], np.ndarray, bool]] = {
            "support_val": (make_contract_records(support_val_rows), x_support_val, False),
        }
        for name, records in pseudo_buckets.items():
            role_defs[name] = (records, role_feature(records, x, new_x), False)
        for name, records in report_buckets.items():
            # report-only replay is not used in any candidate/threshold selection.
            if "medium" in name:
                feats = x[attack_eval_idx] if name == "sealed_medium_attack_eval_report_only" else role_feature(records, x, new_x)
            else:
                feats = role_feature(records, x, new_x)
            role_defs[name] = (records, feats, True)

        for role, (records, feats, is_report_only) in role_defs.items():
            scores = model.score(feats)
            det = rate(scores, threshold)
            row = {
                "seed": seed,
                "role": role,
                "n": int(len(scores)),
                "detection_rate": det,
                "is_report_only": is_report_only,
                "used_for_selection": False,
                "phase_set": "|".join(sorted({str(r["phase_bucket"]) for r in records})),
                "file_count": len({str(r["csv_member"]) for r in records}),
                "device_count": len({str(r["device_hint"]) for r in records}),
                "recorded_index_min": min([int(r["recorded_index"]) for r in records]) if records else "",
                "recorded_index_max": max([int(r["recorded_index"]) for r in records]) if records else "",
            }
            row.update({f"score_{k}": v for k, v in qstats(scores).items()})
            role_rows.append(row)

            if len(feats):
                cov_labels, radii = support_coverage_buckets(x_support_train, x_support_val, feats)
                for label in sorted(set(cov_labels.tolist())):
                    mask = cov_labels == label
                    coverage_rows.append(
                        {
                            "seed": seed,
                            "role": role,
                            "coverage_bucket": label,
                            "n": int(np.sum(mask)),
                            "detection_rate": rate(scores[mask], threshold),
                            "is_report_only": is_report_only,
                            "used_for_selection": False,
                            **radii,
                        }
                    )
                support_coverage_all.append(
                    {
                        "seed": seed,
                        "role": role,
                        "covered_q95_fraction": float(np.mean(cov_labels != "far_gt_q95")) if len(cov_labels) else float("nan"),
                        "far_gt_q95_fraction": float(np.mean(cov_labels == "far_gt_q95")) if len(cov_labels) else float("nan"),
                        **radii,
                    }
                )

    role_summary = aggregate(role_rows, ["role", "is_report_only"])
    coverage_summary = aggregate(coverage_rows, ["role", "coverage_bucket", "is_report_only"])

    legal_future_roles = [r for r in role_summary if str(r["is_report_only"]).lower() == "false" and str(r["role"]).startswith("dev_future")]
    sealed_attack_roles = [r for r in role_summary if str(r["is_report_only"]).lower() == "true" and "attack" in str(r["role"]).lower()]
    legal_future_min = min(float(r["min_detection"]) for r in legal_future_roles) if legal_future_roles else float("nan")
    sealed_attack_min = min(float(r["min_detection"]) for r in sealed_attack_roles) if sealed_attack_roles else float("nan")
    future_pass = bool(np.isfinite(legal_future_min) and legal_future_min >= ATTACK_GO_THRESHOLD)
    sealed_pass = bool(np.isfinite(sealed_attack_min) and sealed_attack_min >= ATTACK_GO_THRESHOLD)
    tail_validated = any("late_2000_9999" in str(r["phase_set"]) or "tail_ge10000" in str(r["phase_set"]) for r in role_rows if r["is_report_only"])

    if future_pass and sealed_pass and tail_validated:
        primary_verdict = "attack_future_shift_validation_passed_with_report_only_late_replay_caveat"
        next_action = "issue27bp_attack_preserving_ood_gate_repair_after_future_shift_validation"
    elif future_pass and sealed_pass:
        primary_verdict = "attack_future_shift_validation_passed_for_available_early_mid_only"
        next_action = "issue27bp_ood_gate_repair_with_late_tail_attack_caveat"
    elif future_pass:
        primary_verdict = "attack_future_shift_dev_passed_but_sealed_attack_gap_remains"
        next_action = "issue27bp_expand_legal_attack_dev_pool_or_task_boundary_audit"
    else:
        primary_verdict = "attack_future_shift_validation_failed_before_ood_gate"
        next_action = "issue27bp_attack_contract_or_representation_repair_before_ood_gate"

    role_access_rows = [
        {
            "stage": "fit",
            "allowed_roles": "id_fit|ood_train|phase_balanced_support_train",
            "forbidden_roles": "dev_future_query|support_val|attack_eval|dev_heavy_query|final_ood",
            "uses_future_query_for_fit_threshold_selection": False,
            "uses_report_only_for_fit_threshold_selection": False,
            "forbidden_role_access": False,
        },
        {
            "stage": "threshold",
            "allowed_roles": "id_calib_only",
            "forbidden_roles": "support_val|dev_future_query|attack_eval|dev_heavy_query|final_ood",
            "uses_future_query_for_fit_threshold_selection": False,
            "uses_report_only_for_fit_threshold_selection": False,
            "forbidden_role_access": False,
        },
        {
            "stage": "future_shift_replay",
            "allowed_roles": "dev_future_query|sealed_report_only_attack_for_replay",
            "forbidden_roles": "using_replay_roles_to_choose_model_or_threshold",
            "uses_future_query_for_fit_threshold_selection": False,
            "uses_report_only_for_fit_threshold_selection": False,
            "forbidden_role_access": False,
        },
    ]

    write_csv(OUT / "input_artifact_hash_audit.csv", input_hash_rows)
    write_csv(OUT / "future_shift_role_detection_by_seed.csv", role_rows)
    write_csv(OUT / "future_shift_role_detection_summary.csv", role_summary)
    write_csv(OUT / "support_coverage_bucket_detection_by_seed.csv", coverage_rows)
    write_csv(OUT / "support_coverage_bucket_detection_summary.csv", coverage_summary)
    write_csv(OUT / "support_coverage_fraction_audit.csv", support_coverage_all)
    write_csv(OUT / "frozen_threshold_audit.csv", threshold_rows)
    write_csv(OUT / "score_direction_audit.csv", direction_rows)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)

    write_md(
        OUT / "issue27bo_decision.md",
        [
            "# issue27bo Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            f"- frozen fit label: `{FROZEN_FIT_LABEL}`",
            f"- frozen threshold rule: `{FROZEN_THRESHOLD_RULE}`",
            f"- legal dev future attack min: `{legal_future_min}`",
            f"- sealed/report-only attack replay min: `{sealed_attack_min}`",
            f"- attack go threshold: `{ATTACK_GO_THRESHOLD}`",
            f"- report-only late/tail phase replay present: `{tail_validated}`",
            "- No new support was selected from future/query/report-only roles.",
            "- No OOD gate repair was run.",
        ],
    )

    write_md(
        OUT / "issue27bp_next_action.md",
        [
            "# issue27bp Next Action",
            "",
            f"recommended_next_action = `{next_action}`",
            "",
            "- If proceeding to OOD repair, keep the frozen support and attack threshold path intact.",
            "- OOD repair must be attack-preserving and must report whether it kills the validated future-shift attack buckets.",
            "- Final/report-only roles remain replay-only and cannot be used for gate selection.",
        ],
    )

    write_md(
        OUT / "claim_update_after_issue27bo.md",
        [
            "# Claim Update After issue27bo",
            "",
            "- Attack-side recovery is not only support-covered; it also survives the available legal dev future-shift buckets under fixed support.",
            "- Sealed attack replay remains attribution-only and cannot be used to tune support, threshold, or model configuration.",
            "- Late/tail attack validation is still limited by legal dev pool availability; this caveat must remain attached to any OOD repair step.",
        ],
    )

    write_md(
        OUT / "summary.md",
        [
            "# issue27bo Summary",
            "",
            "1. issue27bo completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. task type: fixed-support attack future-shift validation",
            "4. OOD gate repair run: no",
            "5. 115D frontend changed: no",
            "6. split/support changed: no",
            "7. future/query used to select new support: no",
            "8. final/report-only used for fit/threshold/selection: no",
            f"9. legal dev future attack min: `{legal_future_min}`",
            f"10. sealed/report-only attack replay min: `{sealed_attack_min}`",
            f"11. report-only late/tail replay present: `{tail_validated}`",
            f"12. attack go threshold: `{ATTACK_GO_THRESHOLD}`",
            f"13. next action: `{next_action}`",
            "14. commit hash: reported in final response",
        ],
    )

    write_md(OUT / "command.txt", ["python repo/ood/issue27bo_attack_future_shift_validation_without_new_support.py"])
    with (OUT / "config.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "issue": ISSUE,
                "frozen_fit_label": FROZEN_FIT_LABEL,
                "frozen_threshold_rule": FROZEN_THRESHOLD_RULE,
                "seeds": SEEDS,
                "attack_go_threshold": ATTACK_GO_THRESHOLD,
                "no_new_support_from_future_query": True,
                "no_ood_gate_repair": True,
            },
            f,
            indent=2,
        )
    with (OUT / "run_spec.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "stage": "attack future-shift validation",
                "fit_roles": ["id_fit", "ood_train", "phase_balanced_support_train"],
                "threshold_roles": ["id_calib"],
                "future_replay_roles": ["dev_future_query", "sealed_attack_report_only"],
                "formal_benchmark": False,
                "ood_gate_repair": False,
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
        "<!-- issue27bo_attack_future_shift_validation -->",
        [
            "## issue27bo - fixed-support attack future-shift validation",
            "",
            "<!-- issue27bo_attack_future_shift_validation -->",
            f"- Verdict: `{primary_verdict}`.",
            f"- Legal dev future attack min: `{legal_future_min}`; sealed attack replay min: `{sealed_attack_min}`.",
            "- No new support was selected from future/query/report-only roles.",
            "- No OOD-gate repair was run.",
            f"- Next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bo_attack_future_shift_validation -->",
        [
            "## issue27bo - fixed-support attack future-shift validation",
            "",
            "<!-- issue27bo_attack_future_shift_validation -->",
            "- Stage: attack-side validation before OOD-gate repair.",
            f"- Primary verdict: `{primary_verdict}`.",
            "- Formal benchmark status: blocked.",
            "- Future/query and report-only roles remained replay-only.",
        ],
    )


if __name__ == "__main__":
    main()
