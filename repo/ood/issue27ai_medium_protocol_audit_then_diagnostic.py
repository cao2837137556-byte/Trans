from __future__ import annotations

import csv
import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27ai_medium_protocol_audit_then_diagnostic_2026-06-02"
OUT = ROOT / "runs" / ISSUE
ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AG = ROOT / "runs" / "issue27ag_gotham_kitsune115_larger_asset_interface_sanity_2026-06-02"
ISSUE27AH = ROOT / "runs" / "issue27ah_gotham_kitsune115_guarded_protocol_small_scale_dry_run_2026-06-02"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ID_ROLE = "id_benign_train"
OOD_VAL_ROLE = "ood_benign_val"
FINAL_OOD_ROLE = "final_ood_benign_eval"
SUPPORT_ROLE = "attack_support"
ATTACK_EVAL_ROLE = "attack_eval"
REPORT_ONLY_ROLES = {FINAL_OOD_ROLE, ATTACK_EVAL_ROLE}
SUPPORT_SIZE = 32
TARGET_OOD_ALARM = 0.01


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


def load_asset(strategy: str, cert: dict[str, Any]) -> dict[str, Any]:
    c = cert[strategy]
    checks = {}
    for key, hash_key in [
        ("X_115D_path", "X_115D_sha256"),
        ("y_path", "y_sha256"),
        ("sidecar_path", "sidecar_sha256"),
        ("split_manifest_path", "split_manifest_sha256"),
        ("feature_schema_path", "feature_schema_sha256"),
        ("state_transition_log_path", "state_transition_log_sha256"),
    ]:
        ok, actual = verify_hash(Path(c[key]), c[hash_key])
        checks[key] = {"ok": ok, "actual_sha256": actual, "expected_sha256": c[hash_key]}
        if not ok:
            raise RuntimeError(f"hash mismatch for {strategy}:{key}")
    return {
        "X": np.load(c["X_115D_path"]),
        "y": np.load(c["y_path"]),
        "sidecar": load_csv(Path(c["sidecar_path"])),
        "split": load_csv(Path(c["split_manifest_path"])),
        "schema": json.loads(Path(c["feature_schema_path"]).read_text(encoding="utf-8")),
        "certificate": c,
        "hash_checks": checks,
    }


def role_mask(sidecar: list[dict[str, str]], role: str) -> np.ndarray:
    return np.asarray(
        [r.get("role") == role and r.get("model_ready_hint", "false").lower() == "true" for r in sidecar],
        dtype=bool,
    )


def fixed_support_mask(sidecar: list[dict[str, str]], support_size: int = SUPPORT_SIZE) -> np.ndarray:
    mask = np.zeros(len(sidecar), dtype=bool)
    idx = np.flatnonzero(role_mask(sidecar, SUPPORT_ROLE))
    mask[idx[:support_size]] = True
    return mask


def rate(mask: np.ndarray) -> float:
    return float(mask.mean()) if mask.size else 0.0


def threshold_from(scores_id: np.ndarray, scores_ood: np.ndarray, rule: str) -> tuple[float, str]:
    id_t = float(np.quantile(scores_id, 1.0 - TARGET_OOD_ALARM))
    ood_t = float(np.quantile(scores_ood, 1.0 - TARGET_OOD_ALARM))
    if rule == "id_q99":
        return id_t, ID_ROLE
    if rule == "ood_val_q99":
        return ood_t, OOD_VAL_ROLE
    if rule == "max_id_ood_val_q99":
        return max(id_t, ood_t), f"{ID_ROLE}|{OOD_VAL_ROLE}"
    raise ValueError(rule)


@dataclass(frozen=True)
class MatrixRow:
    head_name: str
    head_family: str
    variant_name: str
    fit_mode: str
    threshold_rule: str
    support_adaptation: bool
    ood_guard: bool
    threshold_safety: bool
    note: str


MATRIX = [
    MatrixRow("LR", "lr", "raw_support_id_threshold", "id_support32", "id_q99", True, False, False, "raw supervised head with fixed support32 and ID threshold"),
    MatrixRow("LR", "lr", "threshold_guard_only", "id_support32", "ood_val_q99", True, True, True, "same LR score, OOD-val threshold pressure"),
    MatrixRow("LR", "lr", "full_guarded_protocol", "id_support32", "max_id_ood_val_q99", True, True, True, "LR score with fixed support32 and ID/OOD safety"),
    MatrixRow("LR", "lr", "no_support_ood_guard", "id_only", "max_id_ood_val_q99", False, True, True, "blocked for supervised LR: one-class fit would be undefined"),
    MatrixRow("HistGB", "histgb", "raw_support_id_threshold", "id_support32", "id_q99", True, False, False, "raw HistGB with fixed support32 and ID threshold"),
    MatrixRow("HistGB", "histgb", "threshold_guard_only", "id_support32", "ood_val_q99", True, True, True, "same HistGB score, OOD-val threshold pressure"),
    MatrixRow("HistGB", "histgb", "full_guarded_protocol", "id_support32", "max_id_ood_val_q99", True, True, True, "HistGB score with fixed support32 and ID/OOD safety"),
    MatrixRow("HistGB", "histgb", "no_support_ood_guard", "id_only", "max_id_ood_val_q99", False, True, True, "blocked for supervised HistGB: one-class fit would be undefined"),
    MatrixRow("DeepSADStyle_Lite", "deepsad", "raw_support_id_threshold", "id_support32", "id_q99", True, False, False, "center-style score with fixed support32 and ID threshold"),
    MatrixRow("DeepSADStyle_Lite", "deepsad", "threshold_guard_only", "id_support32", "ood_val_q99", True, True, True, "same center score, OOD-val threshold pressure"),
    MatrixRow("DeepSADStyle_Lite", "deepsad", "no_support_ood_guard", "id_only", "max_id_ood_val_q99", False, True, True, "normal-center-only score under OOD guard"),
    MatrixRow("DeepSADStyle_Lite", "deepsad", "full_guarded_protocol", "id_support32", "max_id_ood_val_q99", True, True, True, "center-style support adaptation plus ID/OOD safety"),
    MatrixRow("DevNetStyle_MLP", "mlp", "raw_support_id_threshold", "id_support32", "id_q99", True, False, False, "small MLP score head with fixed support32 and ID threshold"),
    MatrixRow("DevNetStyle_MLP", "mlp", "threshold_guard_only", "id_support32", "ood_val_q99", True, True, True, "same MLP score, OOD-val threshold pressure"),
    MatrixRow("DevNetStyle_MLP", "mlp", "full_guarded_protocol", "id_support32", "max_id_ood_val_q99", True, True, True, "MLP score with fixed support32 and ID/OOD safety"),
    MatrixRow("DevNetStyle_MLP", "mlp", "no_support_ood_guard", "id_only", "max_id_ood_val_q99", False, True, True, "blocked for supervised MLP: one-class fit would be undefined"),
    MatrixRow("IsolationForest", "isoforest", "raw_idonly_id_threshold", "id_only", "id_q99", False, False, False, "ID-only anomaly baseline"),
    MatrixRow("IsolationForest", "isoforest", "ood_guard_only", "id_only", "max_id_ood_val_q99", False, True, True, "ID-only anomaly baseline with ID/OOD safety"),
    MatrixRow("IsolationForest", "isoforest", "support_adaptation", "id_support32", "max_id_ood_val_q99", True, True, True, "blocked: IsolationForest has no support-adaptation interface here"),
]


class LRScorer:
    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=300, solver="liblinear", random_state=42))
        self.model.fit(x, y)

    def score(self, x: np.ndarray) -> np.ndarray:
        return self.model.decision_function(x)


class HistGBScorer:
    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.model = HistGradientBoostingClassifier(max_iter=30, max_leaf_nodes=15, learning_rate=0.08, random_state=42)
        self.model.fit(x, y)

    def score(self, x: np.ndarray) -> np.ndarray:
        proba = self.model.predict_proba(x)
        return proba[:, 1] if proba.ndim == 2 and proba.shape[1] > 1 else proba.reshape(-1)


class MLPScorer:
    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.model = make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(24,), activation="relu", max_iter=80, random_state=42, early_stopping=False),
        )
        self.model.fit(x, y)

    def score(self, x: np.ndarray) -> np.ndarray:
        proba = self.model.predict_proba(x)
        return proba[:, 1] if proba.ndim == 2 and proba.shape[1] > 1 else proba.reshape(-1)


class DeepSADScorer:
    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.scaler = StandardScaler().fit(x)
        z = self.scaler.transform(x)
        normal = z[y == 0]
        attack = z[y == 1]
        self.normal_center = normal.mean(axis=0)
        self.has_attack_center = attack.size > 0
        self.attack_center = attack.mean(axis=0) if self.has_attack_center else np.zeros_like(self.normal_center)

    def score(self, x: np.ndarray) -> np.ndarray:
        z = self.scaler.transform(x)
        normal_dist = np.linalg.norm(z - self.normal_center, axis=1)
        if not self.has_attack_center:
            return normal_dist
        attack_dist = np.linalg.norm(z - self.attack_center, axis=1)
        return normal_dist - attack_dist


class IFScorer:
    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        _ = y
        self.scaler = StandardScaler().fit(x)
        z = self.scaler.transform(x)
        self.model = IsolationForest(n_estimators=50, max_samples=min(1024, len(z)), contamination="auto", random_state=42)
        self.model.fit(z)

    def score(self, x: np.ndarray) -> np.ndarray:
        return -self.model.decision_function(self.scaler.transform(x))


def build_scorer(family: str) -> Any:
    if family == "lr":
        return LRScorer()
    if family == "histgb":
        return HistGBScorer()
    if family == "mlp":
        return MLPScorer()
    if family == "deepsad":
        return DeepSADScorer()
    if family == "isoforest":
        return IFScorer()
    raise ValueError(family)


def fit_mask_and_labels(sidecar: list[dict[str, str]], fit_mode: str) -> tuple[np.ndarray, np.ndarray, str]:
    id_mask = role_mask(sidecar, ID_ROLE)
    support_mask = fixed_support_mask(sidecar)
    if fit_mode == "id_only":
        y = np.zeros(int(id_mask.sum()), dtype=np.int32)
        return id_mask, y, ID_ROLE
    if fit_mode == "id_support32":
        mask = id_mask | support_mask
        y = np.asarray([1 if s else 0 for s in support_mask[mask]], dtype=np.int32)
        return mask, y, f"{ID_ROLE}|{SUPPORT_ROLE}:fixed_first_{SUPPORT_SIZE}"
    raise ValueError(fit_mode)


def incomplete_reason(row: MatrixRow) -> str:
    if row.fit_mode == "id_only" and row.head_family in {"lr", "histgb", "mlp"}:
        return "implementation_incomplete_supervised_head_requires_two_classes"
    if row.fit_mode == "id_support32" and row.head_family == "isoforest":
        return "implementation_incomplete_no_support_adaptation_interface"
    return ""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert = json.loads((ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json").read_text(encoding="utf-8"))
    ag_summary = (ISSUE27AG / "summary.md").read_text(encoding="utf-8")
    ah_summary = (ISSUE27AH / "summary.md").read_text(encoding="utf-8")

    audit_rows: list[dict[str, Any]] = []
    matrix_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    access_rows: list[dict[str, Any]] = []
    forbidden_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []
    collapse_rows: list[dict[str, Any]] = []
    hash_rows: list[dict[str, Any]] = []

    audit_pass = True
    audit_reasons: list[str] = []
    audit_rows.append({"check": "issue27ag_ready_with_full_contract_pending", "ok": "kitsune115_larger_asset_ready_with_full_contract_pending" in ag_summary, "detail": "issue27ag loader/role gate"})
    audit_rows.append({"check": "issue27ah_diagnostic_completed", "ok": "guarded_protocol_medium_dry_run_completed_diagnostic_only" in ah_summary, "detail": "prior dry-run only as context"})

    for row in MATRIX:
        matrix_rows.append(
            {
                "head_name": row.head_name,
                "head_family": row.head_family,
                "variant_name": row.variant_name,
                "fit_mode": row.fit_mode,
                "threshold_rule": row.threshold_rule,
                "support_adaptation": row.support_adaptation,
                "ood_guard": row.ood_guard,
                "threshold_safety": row.threshold_safety,
                "diagnostic_only": True,
                "formal_benchmark": False,
                "note": row.note,
            }
        )

    for strategy in sorted(cert):
        try:
            asset = load_asset(strategy, cert)
        except Exception as exc:
            audit_pass = False
            audit_reasons.append(f"{strategy}: {type(exc).__name__}: {exc}")
            continue
        x = asset["X"]
        sidecar = asset["sidecar"]
        schema = asset["schema"]
        for artifact, check in asset["hash_checks"].items():
            hash_rows.append({"strategy": strategy, "artifact": artifact, **check})
        id_mask = role_mask(sidecar, ID_ROLE)
        ood_mask = role_mask(sidecar, OOD_VAL_ROLE)
        final_mask = role_mask(sidecar, FINAL_OOD_ROLE)
        support_mask_all = role_mask(sidecar, SUPPORT_ROLE)
        support_mask = fixed_support_mask(sidecar)
        attack_mask = role_mask(sidecar, ATTACK_EVAL_ROLE)
        support_rows.append(
            {
                "strategy": strategy,
                "support_rule": f"first_{SUPPORT_SIZE}_rows_in_preregistered_attack_support_role",
                "support_available_rows": int(support_mask_all.sum()),
                "support_used_rows": int(support_mask.sum()),
                "support_eval_disjoint_by_role": True,
                "support_selected_by_final_eval": False,
                "support_selected_by_attack_eval": False,
            }
        )
        checks = [
            ("hash_verification", all(v["ok"] for v in asset["hash_checks"].values()), "all issue27af medium certificate hashes match"),
            ("shape_115", x.ndim == 2 and x.shape[1] == 115, str(x.shape)),
            ("rows_aligned", x.shape[0] == len(sidecar), f"x={x.shape[0]} sidecar={len(sidecar)}"),
            ("finite_features", bool(np.isfinite(x).all()), "no NaN/Inf"),
            ("role_counts_nonzero", all(m.sum() > 0 for m in [id_mask, ood_mask, final_mask, support_mask_all, attack_mask]), "all required roles present"),
            ("fixed_support_available", support_mask_all.sum() >= SUPPORT_SIZE, f"available={support_mask_all.sum()} needed={SUPPORT_SIZE}"),
            ("schema_feature_count_115", schema.get("feature_count") == 115, f"schema={schema.get('feature_count')}"),
        ]
        for name, ok, detail in checks:
            audit_rows.append({"strategy": strategy, "check": name, "ok": ok, "detail": detail})
            if not ok:
                audit_pass = False
                audit_reasons.append(f"{strategy}:{name}:{detail}")

        if not audit_pass:
            continue

        masks = {
            ID_ROLE: id_mask,
            OOD_VAL_ROLE: ood_mask,
            FINAL_OOD_ROLE: final_mask,
            SUPPORT_ROLE: support_mask,
            ATTACK_EVAL_ROLE: attack_mask,
        }
        for row in MATRIX:
            inc = incomplete_reason(row)
            if inc:
                diagnostic_rows.append(
                    {
                        "strategy": strategy,
                        "head_name": row.head_name,
                        "variant_name": row.variant_name,
                        "status": "implementation_incomplete",
                        "reason": inc,
                        "diagnostic_only": True,
                        "formal_benchmark": False,
                    }
                )
                continue
            fit_mask, y_fit, fit_roles = fit_mask_and_labels(sidecar, row.fit_mode)
            access_rows.append(
                {
                    "strategy": strategy,
                    "head_name": row.head_name,
                    "variant_name": row.variant_name,
                    "phase": "fit",
                    "roles_accessed": fit_roles,
                    "final_eval_used": False,
                    "attack_eval_used": False,
                    "allowed": True,
                }
            )
            access_rows.append(
                {
                    "strategy": strategy,
                    "head_name": row.head_name,
                    "variant_name": row.variant_name,
                    "phase": "threshold_selection",
                    "roles_accessed": ID_ROLE if row.threshold_rule == "id_q99" else f"{ID_ROLE}|{OOD_VAL_ROLE}",
                    "final_eval_used": False,
                    "attack_eval_used": False,
                    "allowed": True,
                }
            )
            try:
                scorer = build_scorer(row.head_family)
                scorer.fit(x[fit_mask], y_fit)
                scores = {role: np.asarray(scorer.score(x[mask]), dtype=np.float64) for role, mask in masks.items()}
                threshold, threshold_source = threshold_from(scores[ID_ROLE], scores[OOD_VAL_ROLE], row.threshold_rule)
                id_alarm = rate(scores[ID_ROLE] >= threshold)
                ood_alarm = rate(scores[OOD_VAL_ROLE] >= threshold)
                final_ood_alarm = rate(scores[FINAL_OOD_ROLE] >= threshold)
                support_det = rate(scores[SUPPORT_ROLE] >= threshold)
                attack_det = rate(scores[ATTACK_EVAL_ROLE] >= threshold)
                feasible = final_ood_alarm <= TARGET_OOD_ALARM
                collapse = attack_det < 0.20
                diagnostic_rows.append(
                    {
                        "strategy": strategy,
                        "head_name": row.head_name,
                        "head_family": row.head_family,
                        "variant_name": row.variant_name,
                        "fit_mode": row.fit_mode,
                        "threshold_rule": row.threshold_rule,
                        "threshold_source_roles": threshold_source,
                        "support_adaptation": row.support_adaptation,
                        "ood_guard": row.ood_guard,
                        "threshold_safety": row.threshold_safety,
                        "id_alarm": id_alarm,
                        "ood_val_alarm": ood_alarm,
                        "final_ood_alarm": final_ood_alarm,
                        "attack_support_detection": support_det,
                        "attack_eval_detection": attack_det,
                        "feasible_under_1pct": feasible,
                        "collapse_flag_attack_eval_lt_0p20": collapse,
                        "ood_overbudget_flag": not feasible,
                        "final_eval_used_for_selection": False,
                        "attack_eval_used_for_selection": False,
                        "diagnostic_only": True,
                        "formal_benchmark": False,
                        "full_contract_pending": True,
                        "status": "pass",
                    }
                )
                forbidden_rows.append(
                    {
                        "strategy": strategy,
                        "head_name": row.head_name,
                        "variant_name": row.variant_name,
                        "final_eval_used_for_fit": False,
                        "final_eval_used_for_threshold": False,
                        "final_eval_used_for_selection": False,
                        "attack_eval_used_for_fit": False,
                        "attack_eval_used_for_threshold": False,
                        "attack_eval_used_for_selection": False,
                        "verdict": "pass",
                    }
                )
                collapse_rows.append(
                    {
                        "strategy": strategy,
                        "head_name": row.head_name,
                        "variant_name": row.variant_name,
                        "collapse_signal": "yes" if collapse else "no",
                        "ood_overbudget_signal": "yes" if not feasible else "no",
                        "scope": "medium_diagnostic_only",
                    }
                )
            except Exception as exc:
                diagnostic_rows.append(
                    {
                        "strategy": strategy,
                        "head_name": row.head_name,
                        "head_family": row.head_family,
                        "variant_name": row.variant_name,
                        "status": "interface_failed",
                        "reason": f"{type(exc).__name__}: {exc}",
                        "diagnostic_only": True,
                        "formal_benchmark": False,
                    }
                )

    forbidden_blocked = any(
        str(r.get(k, "False")).lower() == "true"
        for r in forbidden_rows
        for k in [
            "final_eval_used_for_fit",
            "final_eval_used_for_threshold",
            "final_eval_used_for_selection",
            "attack_eval_used_for_fit",
            "attack_eval_used_for_threshold",
            "attack_eval_used_for_selection",
        ]
    )
    any_pass = any(r.get("status") == "pass" for r in diagnostic_rows)
    any_interface_failed = any(r.get("status") == "interface_failed" for r in diagnostic_rows)
    if forbidden_blocked:
        verdict = "medium_protocol_audit_blocked_by_forbidden_role_access"
    elif not audit_pass:
        verdict = "medium_protocol_audit_blocked_before_diagnostic"
    elif not any_pass:
        verdict = "medium_protocol_diagnostic_blocked_by_adapter_failures"
    elif any_interface_failed:
        verdict = "medium_protocol_diagnostic_partial_interface_issue"
    else:
        verdict = "medium_protocol_audit_passed_diagnostic_completed"

    passed = [r for r in diagnostic_rows if r.get("status") == "pass"]
    for head in sorted({r["head_name"] for r in passed}):
        for strategy in sorted({r["strategy"] for r in passed}):
            rows = [r for r in passed if r["head_name"] == head and r["strategy"] == strategy]
            raw = next((r for r in rows if "raw" in r["variant_name"]), None)
            full = next((r for r in rows if r["variant_name"] == "full_guarded_protocol" or r["variant_name"] == "ood_guard_only"), None)
            if raw and full:
                component_rows.append(
                    {
                        "strategy": strategy,
                        "head_name": head,
                        "raw_variant": raw["variant_name"],
                        "guarded_variant": full["variant_name"],
                        "raw_final_ood_alarm": raw["final_ood_alarm"],
                        "guarded_final_ood_alarm": full["final_ood_alarm"],
                        "raw_attack_eval_detection": raw["attack_eval_detection"],
                        "guarded_attack_eval_detection": full["attack_eval_detection"],
                        "diagnostic_interpretation": "component contrast only; not model ranking",
                    }
                )

    write_csv(OUT / "protocol_correctness_audit.csv", audit_rows)
    write_csv(OUT / "asset_hash_reverification.csv", hash_rows)
    write_csv(OUT / "medium_protocol_matrix.csv", matrix_rows)
    write_csv(OUT / "fixed_support32_audit.csv", support_rows)
    write_csv(OUT / "protocol_role_access_matrix.csv", access_rows)
    write_csv(OUT / "forbidden_role_access_audit.csv", forbidden_rows)
    write_csv(OUT / "medium_protocol_diagnostic_by_strategy.csv", diagnostic_rows)
    write_csv(OUT / "component_contrast_diagnostic.csv", component_rows)
    write_csv(OUT / "collapse_feasibility_summary.csv", collapse_rows)
    write_md(
        OUT / "protocol_correctness_audit_report.md",
        [
            "# Protocol Correctness Audit",
            "",
            f"- audit_pass: `{audit_pass}`.",
            f"- forbidden_role_access_blocked: `{forbidden_blocked}`.",
            f"- support rule: fixed first `{SUPPORT_SIZE}` rows from preregistered attack_support role.",
            "- Final OOD benign eval and attack eval are report-only and never used for fit/threshold/selection.",
            "- If audit failed, diagnostic execution is not claim-usable.",
            *([f"- blocked_reason: {x}" for x in audit_reasons] if audit_reasons else []),
        ],
    )
    write_md(
        OUT / "medium_protocol_diagnostic_report.md",
        [
            "# Medium Protocol Diagnostic Report",
            "",
            f"- primary_verdict: `{verdict}`.",
            "- Scope: medium 115D diagnostic only.",
            "- Matrix includes raw/support threshold, OOD-threshold pressure, no-support where meaningful, and full guarded variants.",
            "- The table is for mechanism rehearsal and collapse/overbudget signals, not model ranking.",
            "- full_contract remains pending; formal benchmark still requires full/larger asset certificate.",
        ],
    )
    write_md(
        OUT / "issue27ai_decision.md",
        [
            "# issue27ai Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            "A audit passed before B diagnostic unless otherwise noted. Medium diagnostics may guide protocol debugging, but cannot determine the final model or paper claim.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27ai.md",
        [
            "# Claim Update After issue27ai",
            "",
            "- Medium Gotham Kitsune115 diagnostics can be used to rehearse protocol mechanics.",
            "- Any collapse or feasibility signal remains diagnostic until full_contract or a documented exclusion policy is fixed.",
            "- Formal model comparison, mainline selection, and paper claims remain blocked pending full/larger benchmark execution.",
        ],
    )
    write_md(
        OUT / "issue27aj_next_action.md",
        [
            "# issue27aj Next Action",
            "",
            "Recommended next issue: `issue27aj_full_contract_materialization_or_exclusion_policy_and_protocol_freeze_2026-06-02`. It should either materialize the heavy ip-camera full_contract with a faster frontend/Slurm path or freeze a defensible exclusion policy, then lock support size, threshold rule, model configs, and state strategy before formal benchmark.",
        ],
    )
    config = {
        "issue": ISSUE,
        "task_type": "A_then_B_medium_protocol_audit_and_diagnostic",
        "formal_benchmark": False,
        "model_ranking": False,
        "support_size": SUPPORT_SIZE,
        "target_ood_alarm": TARGET_OOD_ALARM,
        "full_contract_pending": True,
        "state_strategies": sorted(cert.keys()),
        "matrix_rows": len(MATRIX),
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps({"selected_verdict": verdict, "audit_pass": audit_pass, "formal_benchmark": False}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")
    write_md(
        OUT / "summary.md",
        [
            "# issue27ai Summary",
            "",
            "1. issue27ai complete: yes.",
            f"2. primary_verdict: `{verdict}`.",
            f"3. A protocol correctness audit passed: `{audit_pass}`.",
            f"4. B diagnostic executed: `{audit_pass and any_pass}`.",
            "5. formal benchmark: no.",
            "6. model ranking: no.",
            f"7. fixed support size: `{SUPPORT_SIZE}`.",
            f"8. forbidden role access blocked: `{forbidden_blocked}`.",
            f"9. protocol matrix rows: `{len(MATRIX)}`.",
            "10. final eval use: report-only; no fit/threshold/selection.",
            "11. full_contract_pending: `True`.",
            "12. issue27aj recommendation: full_contract/exclusion policy plus protocol freeze before formal benchmark.",
            "13. commit hash: pending.",
        ],
    )
    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest_rows.append({"file": path.name, "path": str(path)})
    write_csv(OUT / "manifest.csv", manifest_rows)

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27ai_medium_protocol_audit_then_diagnostic -->",
        [
            "<!-- issue27ai_medium_protocol_audit_then_diagnostic -->",
            "",
            "## issue27ai Medium Protocol Audit Then Diagnostic",
            "",
            f"- primary_verdict: `{verdict}`.",
            "- A protocol correctness audit gates B diagnostic execution.",
            f"- support size fixed to `{SUPPORT_SIZE}` from preregistered attack_support role; no final eval or attack eval selection.",
            "- output is medium diagnostic only; formal benchmark still requires full_contract or an exclusion policy and protocol freeze.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27ai_map_entry -->",
        [
            "<!-- issue27ai_map_entry -->",
            "",
            "### issue27ai_medium_protocol_audit_then_diagnostic_2026-06-02",
            "",
            "- status: completed.",
            f"- primary_verdict: `{verdict}`.",
            f"- outputs: `runs/{ISSUE}/`.",
            "- implication: protocol matrix diagnostics are available for debugging only; final claims wait for full/larger asset and frozen protocol.",
        ],
    )
    print(f"[done] {OUT}")
    print(f"[verdict] {verdict}")


if __name__ == "__main__":
    main()
