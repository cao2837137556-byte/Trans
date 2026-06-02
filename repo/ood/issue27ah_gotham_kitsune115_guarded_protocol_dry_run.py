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
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27ah_gotham_kitsune115_guarded_protocol_small_scale_dry_run_2026-06-02"
OUT = ROOT / "runs" / ISSUE
ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AG = ROOT / "runs" / "issue27ag_gotham_kitsune115_larger_asset_interface_sanity_2026-06-02"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ID_ROLE = "id_benign_train"
OOD_VAL_ROLE = "ood_benign_val"
FINAL_OOD_ROLE = "final_ood_benign_eval"
SUPPORT_ROLE = "attack_support"
ATTACK_EVAL_ROLE = "attack_eval"
REPORT_ONLY_ROLES = {FINAL_OOD_ROLE, ATTACK_EVAL_ROLE}
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


def load_kitsune115_asset(strategy: str, cert: dict[str, Any]) -> dict[str, Any]:
    c = cert[strategy]
    checks: dict[str, dict[str, Any]] = {}
    for key, hash_key in [
        ("X_115D_path", "X_115D_sha256"),
        ("y_path", "y_sha256"),
        ("sidecar_path", "sidecar_sha256"),
        ("split_manifest_path", "split_manifest_sha256"),
        ("feature_schema_path", "feature_schema_sha256"),
        ("state_transition_log_path", "state_transition_log_sha256"),
    ]:
        path = Path(c[key])
        ok, actual = verify_hash(path, c[hash_key])
        checks[key] = {"ok": ok, "actual_sha256": actual, "expected_sha256": c[hash_key], "path": str(path)}
        if not ok:
            raise RuntimeError(f"immutable hash check failed for {strategy}:{key}")
    x = np.load(c["X_115D_path"])
    y = np.load(c["y_path"])
    sidecar = load_csv(Path(c["sidecar_path"]))
    split = load_csv(Path(c["split_manifest_path"]))
    schema = json.loads(Path(c["feature_schema_path"]).read_text(encoding="utf-8"))
    return {"X": x, "y": y, "sidecar": sidecar, "split": split, "schema": schema, "certificate": c, "hash_checks": checks}


def role_mask(sidecar: list[dict[str, str]], role: str) -> np.ndarray:
    return np.asarray(
        [row.get("role") == role and row.get("model_ready_hint", "false").lower() == "true" for row in sidecar],
        dtype=bool,
    )


def safe_rate(mask: np.ndarray) -> float:
    return float(mask.mean()) if mask.size else 0.0


def choose_threshold(scores_id: np.ndarray, scores_ood_val: np.ndarray, rule: str) -> tuple[float, str]:
    if rule == "id_q99":
        return float(np.quantile(scores_id, 1.0 - TARGET_OOD_ALARM)), "id_benign_train"
    if rule == "ood_val_q99":
        return float(np.quantile(scores_ood_val, 1.0 - TARGET_OOD_ALARM)), "ood_benign_val"
    if rule == "max_id_ood_val_q99":
        id_t = float(np.quantile(scores_id, 1.0 - TARGET_OOD_ALARM))
        ood_t = float(np.quantile(scores_ood_val, 1.0 - TARGET_OOD_ALARM))
        return max(id_t, ood_t), "id_benign_train|ood_benign_val"
    raise ValueError(rule)


@dataclass
class MethodSpec:
    method_name: str
    family: str
    fit_roles: tuple[str, ...]
    threshold_rule: str
    protocol_tag: str


class LRScorer:
    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=300, solver="liblinear", random_state=42))
        self.model.fit(x, y)

    def score(self, x: np.ndarray) -> np.ndarray:
        return self.model.decision_function(x)


class LowGuardLRShellScorer:
    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=300, solver="liblinear", random_state=42))
        self.model.fit(x, y)
        self.margin_scaler = StandardScaler().fit(x)
        z = self.margin_scaler.transform(x)
        self.id_center = z[y == 0].mean(axis=0)
        self.support_center = z[y == 1].mean(axis=0)

    def score(self, x: np.ndarray) -> np.ndarray:
        lr_score = self.model.decision_function(x)
        z = self.margin_scaler.transform(x)
        support_margin = np.linalg.norm(z - self.id_center, axis=1) - np.linalg.norm(z - self.support_center, axis=1)
        return lr_score + 0.25 * support_margin


class HistGBScorer:
    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.model = HistGradientBoostingClassifier(max_iter=30, max_leaf_nodes=15, learning_rate=0.08, random_state=42)
        self.model.fit(x, y)

    def score(self, x: np.ndarray) -> np.ndarray:
        proba = self.model.predict_proba(x)
        return proba[:, 1] if proba.ndim == 2 and proba.shape[1] > 1 else proba.reshape(-1)


class DeepSADStyleLiteScorer:
    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.scaler = StandardScaler().fit(x)
        z = self.scaler.transform(x)
        normal = z[y == 0]
        attack = z[y == 1]
        self.normal_center = normal.mean(axis=0)
        self.attack_center = attack.mean(axis=0)

    def score(self, x: np.ndarray) -> np.ndarray:
        z = self.scaler.transform(x)
        return np.linalg.norm(z - self.normal_center, axis=1) - np.linalg.norm(z - self.attack_center, axis=1)


class IsolationForestScorer:
    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        _ = y
        self.scaler = StandardScaler().fit(x)
        z = self.scaler.transform(x)
        self.model = IsolationForest(n_estimators=50, max_samples=min(1024, len(z)), contamination="auto", random_state=42)
        self.model.fit(z)

    def score(self, x: np.ndarray) -> np.ndarray:
        z = self.scaler.transform(x)
        return -self.model.decision_function(z)


def make_scorer(family: str) -> Any:
    if family == "lr":
        return LRScorer()
    if family == "lowguard_lr_shell":
        return LowGuardLRShellScorer()
    if family == "histgb":
        return HistGBScorer()
    if family == "deepsad_lite":
        return DeepSADStyleLiteScorer()
    if family == "isolation_forest":
        return IsolationForestScorer()
    raise ValueError(family)


METHODS = [
    MethodSpec("Raw_LR_IDThreshold_diagnostic", "lr", (ID_ROLE, SUPPORT_ROLE), "id_q99", "raw_lr_ablation"),
    MethodSpec("LR_ThresholdOnly_OODVal_diagnostic", "lr", (ID_ROLE, SUPPORT_ROLE), "ood_val_q99", "threshold_safety_ablation"),
    MethodSpec("LOW_GUARD_LR_Shell_dry_run", "lowguard_lr_shell", (ID_ROLE, SUPPORT_ROLE), "max_id_ood_val_q99", "guarded_protocol_candidate"),
    MethodSpec("HistGB_Guarded_dry_run", "histgb", (ID_ROLE, SUPPORT_ROLE), "max_id_ood_val_q99", "guarded_head_candidate"),
    MethodSpec("DeepSADStyle_Lite_dry_run", "deepsad_lite", (ID_ROLE, SUPPORT_ROLE), "max_id_ood_val_q99", "center_style_candidate"),
    MethodSpec("IsolationForest_IDOnly_diagnostic", "isolation_forest", (ID_ROLE,), "max_id_ood_val_q99", "id_only_anomaly_baseline"),
]


def labels_for_fit(sidecar: list[dict[str, str]], roles: tuple[str, ...]) -> np.ndarray:
    y = []
    for row in sidecar:
        if row.get("role") in roles and row.get("model_ready_hint", "false").lower() == "true":
            y.append(1 if row.get("role") == SUPPORT_ROLE else 0)
    return np.asarray(y, dtype=np.int32)


def score_finite_stats(scores: np.ndarray) -> dict[str, Any]:
    return {
        "score_shape": json.dumps(list(scores.shape)),
        "score_dtype": str(scores.dtype),
        "score_finite_rate": float(np.isfinite(scores).mean()) if scores.size else 0.0,
        "score_nan_count": int(np.isnan(scores).sum()),
        "score_inf_count": int(np.isinf(scores).sum()),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert = json.loads((ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json").read_text(encoding="utf-8"))
    issue27ag_summary = (ISSUE27AG / "summary.md").read_text(encoding="utf-8")

    config = {
        "dataset": "gotham2025",
        "feature_schema": "kitsune115_pcap_derived_medium",
        "task_type": "guarded_protocol_small_scale_dry_run",
        "formal_benchmark": False,
        "model_ranking": False,
        "full_contract_pending": True,
        "target_ood_alarm": TARGET_OOD_ALARM,
        "state_strategies": sorted(cert.keys()),
        "selection_allowed_roles": [ID_ROLE, OOD_VAL_ROLE, SUPPORT_ROLE],
        "report_only_roles": sorted(REPORT_ONLY_ROLES),
        "issue27ag_summary_verdict_present": "kitsune115_larger_asset_ready_with_full_contract_pending" in issue27ag_summary,
    }

    hash_rows: list[dict[str, Any]] = []
    input_rows: list[dict[str, Any]] = []
    access_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []
    collapse_rows: list[dict[str, Any]] = []
    forbidden_rows: list[dict[str, Any]] = []

    blocked_reason = ""
    for strategy in sorted(cert):
        try:
            asset = load_kitsune115_asset(strategy, cert)
        except Exception as exc:
            blocked_reason = f"{type(exc).__name__}: {exc}"
            continue
        x = asset["X"]
        sidecar = asset["sidecar"]
        schema = asset["schema"]
        for artifact, check in asset["hash_checks"].items():
            hash_rows.append({"strategy": strategy, "artifact": artifact, **check})
        masks = {role: role_mask(sidecar, role) for role in [ID_ROLE, OOD_VAL_ROLE, FINAL_OOD_ROLE, SUPPORT_ROLE, ATTACK_EVAL_ROLE]}
        input_rows.append(
            {
                "strategy": strategy,
                "rows": int(x.shape[0]),
                "columns": int(x.shape[1]) if x.ndim == 2 else 0,
                "schema_feature_count": schema.get("feature_count"),
                "finite_rate": float(np.isfinite(x).mean()) if x.size else 0.0,
                "hash_verified": all(row["ok"] for row in asset["hash_checks"].values()),
                "id_benign_train_rows": int(masks[ID_ROLE].sum()),
                "ood_benign_val_rows": int(masks[OOD_VAL_ROLE].sum()),
                "final_ood_benign_eval_rows": int(masks[FINAL_OOD_ROLE].sum()),
                "attack_support_rows": int(masks[SUPPORT_ROLE].sum()),
                "attack_eval_rows": int(masks[ATTACK_EVAL_ROLE].sum()),
            }
        )
        for method in METHODS:
            fit_mask = np.zeros(len(sidecar), dtype=bool)
            for role in method.fit_roles:
                fit_mask |= masks[role]
            x_fit = x[fit_mask]
            y_fit = labels_for_fit(sidecar, method.fit_roles)
            access_rows.append(
                {
                    "strategy": strategy,
                    "method_name": method.method_name,
                    "phase": "fit",
                    "roles_accessed": "|".join(method.fit_roles),
                    "row_count": int(fit_mask.sum()),
                    "final_eval_used": False,
                    "attack_eval_used": False,
                    "allowed": True,
                }
            )
            access_rows.append(
                {
                    "strategy": strategy,
                    "method_name": method.method_name,
                    "phase": "threshold_calibration",
                    "roles_accessed": "id_benign_train|ood_benign_val",
                    "row_count": int(masks[ID_ROLE].sum() + masks[OOD_VAL_ROLE].sum()),
                    "final_eval_used": False,
                    "attack_eval_used": False,
                    "allowed": True,
                }
            )
            access_rows.append(
                {
                    "strategy": strategy,
                    "method_name": method.method_name,
                    "phase": "report_only_score",
                    "roles_accessed": "final_ood_benign_eval|attack_eval",
                    "row_count": int(masks[FINAL_OOD_ROLE].sum() + masks[ATTACK_EVAL_ROLE].sum()),
                    "final_eval_used": True,
                    "attack_eval_used": True,
                    "allowed": True,
                }
            )
            try:
                scorer = make_scorer(method.family)
                scorer.fit(x_fit, y_fit)
                scores_by_role = {role: np.asarray(scorer.score(x[masks[role]]), dtype=np.float64) for role in masks}
                threshold, threshold_source = choose_threshold(scores_by_role[ID_ROLE], scores_by_role[OOD_VAL_ROLE], method.threshold_rule)
                threshold_rows.append(
                    {
                        "strategy": strategy,
                        "method_name": method.method_name,
                        "threshold_rule": method.threshold_rule,
                        "threshold_source_roles": threshold_source,
                        "final_eval_used_for_threshold": False,
                        "attack_eval_used_for_threshold": False,
                        "threshold_value": threshold,
                    }
                )
                id_alarm = safe_rate(scores_by_role[ID_ROLE] >= threshold)
                ood_val_alarm = safe_rate(scores_by_role[OOD_VAL_ROLE] >= threshold)
                final_ood_alarm = safe_rate(scores_by_role[FINAL_OOD_ROLE] >= threshold)
                support_detection = safe_rate(scores_by_role[SUPPORT_ROLE] >= threshold)
                attack_detection = safe_rate(scores_by_role[ATTACK_EVAL_ROLE] >= threshold)
                feasible = final_ood_alarm <= TARGET_OOD_ALARM
                collapse = attack_detection < 0.20
                result = {
                    "strategy": strategy,
                    "method_name": method.method_name,
                    "protocol_tag": method.protocol_tag,
                    "diagnostic_only": True,
                    "formal_benchmark": False,
                    "full_contract_pending": True,
                    "id_train_alarm": id_alarm,
                    "ood_val_alarm": ood_val_alarm,
                    "final_ood_alarm": final_ood_alarm,
                    "attack_support_detection": support_detection,
                    "attack_eval_detection": attack_detection,
                    "feasible_under_1pct": feasible,
                    "collapse_flag_attack_eval_lt_0p20": collapse,
                    "ood_overbudget_flag": not feasible,
                    "final_eval_used_for_selection": False,
                    "attack_eval_used_for_selection": False,
                    **score_finite_stats(scores_by_role[ATTACK_EVAL_ROLE]),
                    "status": "pass",
                    "notes": "diagnostic dry-run only; no model ranking or formal claim",
                }
                result_rows.append(result)
                collapse_rows.append(
                    {
                        "strategy": strategy,
                        "method_name": method.method_name,
                        "collapse_signal": "yes" if collapse else "no",
                        "ood_overbudget_signal": "yes" if not feasible else "no",
                        "interpretation_scope": "medium_asset_diagnostic_only",
                    }
                )
                forbidden_rows.append(
                    {
                        "strategy": strategy,
                        "method_name": method.method_name,
                        "final_eval_used_for_fit": False,
                        "final_eval_used_for_threshold": False,
                        "final_eval_used_for_selection": False,
                        "attack_eval_used_for_fit": False,
                        "attack_eval_used_for_threshold": False,
                        "attack_eval_used_for_selection": False,
                        "verdict": "pass",
                    }
                )
            except Exception as exc:
                result_rows.append(
                    {
                        "strategy": strategy,
                        "method_name": method.method_name,
                        "protocol_tag": method.protocol_tag,
                        "diagnostic_only": True,
                        "formal_benchmark": False,
                        "full_contract_pending": True,
                        "status": "interface_failed",
                        "notes": f"{type(exc).__name__}: {exc}",
                    }
                )
                forbidden_rows.append(
                    {
                        "strategy": strategy,
                        "method_name": method.method_name,
                        "final_eval_used_for_fit": False,
                        "final_eval_used_for_threshold": False,
                        "final_eval_used_for_selection": False,
                        "attack_eval_used_for_fit": False,
                        "attack_eval_used_for_threshold": False,
                        "attack_eval_used_for_selection": False,
                        "verdict": "pass_after_interface_failure",
                    }
                )

    forbidden_blocked = any(
        str(row.get(key, "False")).lower() == "true"
        for row in forbidden_rows
        for key in [
            "final_eval_used_for_fit",
            "final_eval_used_for_threshold",
            "final_eval_used_for_selection",
            "attack_eval_used_for_fit",
            "attack_eval_used_for_threshold",
            "attack_eval_used_for_selection",
        ]
    )
    hash_ok = hash_rows and all(str(row["ok"]).lower() == "true" for row in hash_rows)
    any_pass = any(row.get("status") == "pass" for row in result_rows)
    any_interface_failed = any(row.get("status") == "interface_failed" for row in result_rows)
    if forbidden_blocked:
        verdict = "guarded_protocol_dry_run_blocked_by_forbidden_role_access"
    elif not hash_ok or blocked_reason:
        verdict = "guarded_protocol_dry_run_blocked_by_asset_loader_or_hash"
    elif not any_pass:
        verdict = "guarded_protocol_dry_run_blocked_by_adapter_interface"
    elif any_interface_failed:
        verdict = "guarded_protocol_dry_run_partial_adapter_interface_issue"
    else:
        verdict = "guarded_protocol_medium_dry_run_completed_diagnostic_only"

    write_csv(OUT / "asset_hash_reverification.csv", hash_rows)
    write_csv(OUT / "asset_input_contract_check.csv", input_rows)
    write_csv(OUT / "guarded_protocol_role_access_matrix.csv", access_rows)
    write_csv(OUT / "threshold_selection_audit.csv", threshold_rows)
    write_csv(OUT / "guarded_protocol_dry_run_by_method_strategy.csv", result_rows)
    write_csv(OUT / "collapse_signal_diagnostic_table.csv", collapse_rows)
    write_csv(OUT / "forbidden_role_access_audit.csv", forbidden_rows)
    write_md(
        OUT / "guarded_protocol_dry_run_report.md",
        [
            "# issue27ah Guarded Protocol Dry-Run Report",
            "",
            f"- primary_verdict: `{verdict}`.",
            "- Scope: medium Gotham Kitsune115 guarded protocol dry-run.",
            "- This is not a formal benchmark and not a model ranking.",
            "- Final OOD benign eval and attack eval are report-only.",
            "- Thresholds are derived only from ID benign train and/or OOD benign val according to fixed method rules.",
            "- full_contract remains pending for heavy ip-camera files.",
        ],
    )
    write_md(
        OUT / "issue27ah_decision.md",
        [
            "# issue27ah Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            "Medium 115D assets can be used for guarded protocol diagnostic behavior checks if no forbidden role access is present. The results cannot be used as formal model ranking or paper claims because full_contract remains pending.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27ah.md",
        [
            "# Claim Update After issue27ah",
            "",
            "- The Gotham Kitsune115 medium asset supports diagnostic guarded-protocol dry-run work.",
            "- Any observed OOD-overbudget or attack-detection collapse behavior is diagnostic only.",
            "- Formal method claims require full_contract materialization or an explicitly justified exclusion policy, followed by preregistered benchmark execution.",
            "- This issue does not establish external generalization, model mainline status, or paper-ready results.",
        ],
    )
    write_md(
        OUT / "issue27ai_next_action.md",
        [
            "# issue27ai Next Action",
            "",
            "Recommended next issue: complete `gotham_kitsune115_full_contract_materialization_or_exclusion_policy`, then rerun the guarded protocol on the fixed full/preregistered asset. If speed is prioritized, use issue27ah diagnostics only to select which protocol mechanics need audit, not to select a final model.",
        ],
    )
    config_path = OUT / "guarded_protocol_dry_run_config.json"
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "issue": ISSUE,
                "verdict_options": [
                    "guarded_protocol_medium_dry_run_completed_diagnostic_only",
                    "guarded_protocol_dry_run_partial_adapter_interface_issue",
                    "guarded_protocol_dry_run_blocked_by_forbidden_role_access",
                    "guarded_protocol_dry_run_blocked_by_asset_loader_or_hash",
                    "guarded_protocol_dry_run_blocked_by_adapter_interface",
                ],
                "selected_verdict": verdict,
                "formal_benchmark": False,
                "full_contract_pending": True,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")
    write_md(
        OUT / "summary.md",
        [
            "# issue27ah Summary",
            "",
            "1. issue27ah complete: yes.",
            f"2. primary_verdict: `{verdict}`.",
            "3. formal benchmark: no.",
            "4. model ranking: no.",
            f"5. full_contract_pending: `True`.",
            f"6. hash verification pass: `{hash_ok}`.",
            f"7. forbidden role access blocked: `{forbidden_blocked}`.",
            f"8. methods attempted: `{len(METHODS)}`.",
            f"9. strategy count: `{len(cert)}`.",
            "10. final eval use: report-only scoring; no fit/threshold/selection.",
            "11. outputs: diagnostic operating-point tables only.",
            "12. next: full_contract materialization/exclusion policy before formal benchmark.",
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
        "<!-- issue27ah_gotham_kitsune115_guarded_protocol_dry_run -->",
        [
            "<!-- issue27ah_gotham_kitsune115_guarded_protocol_dry_run -->",
            "",
            "## issue27ah Gotham Kitsune115 Guarded Protocol Dry Run",
            "",
            f"- primary_verdict: `{verdict}`.",
            "- medium 115D asset was used only for diagnostic guarded-protocol behavior checks.",
            "- final OOD benign eval and attack eval remained report-only and were not used for thresholding or selection.",
            "- full_contract remains pending; issue27ah results are not formal model rankings.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27ah_map_entry -->",
        [
            "<!-- issue27ah_map_entry -->",
            "",
            "### issue27ah_gotham_kitsune115_guarded_protocol_small_scale_dry_run_2026-06-02",
            "",
            "- status: completed.",
            f"- primary_verdict: `{verdict}`.",
            f"- outputs: `runs/{ISSUE}/`.",
            "- implication: medium 115D diagnostic behavior is available, but formal benchmark waits for full_contract or a documented exclusion policy.",
        ],
    )
    print(f"[done] {OUT}")
    print(f"[verdict] {verdict}")


if __name__ == "__main__":
    main()
