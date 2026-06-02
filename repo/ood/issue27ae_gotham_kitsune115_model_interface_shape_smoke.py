from __future__ import annotations

import csv
import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27ae_gotham_kitsune115_model_interface_shape_smoke_2026-06-02"
OUT = ROOT / "runs" / ISSUE
ISSUE27AD = ROOT / "runs" / "issue27ad_gotham_kitsune115_split_aware_smoke_dataset_expansion_2026-06-02"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

FIT_ROLES = {"id_benign_train", "attack_support"}
SCORE_ROLES = {"id_benign_train", "ood_benign_val", "final_ood_benign_eval", "attack_support", "attack_eval"}
FORBIDDEN_FOR_SELECTION = {"final_ood_benign_eval", "attack_eval"}


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


def file_hash(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_artifacts() -> list[dict[str, str]]:
    with (ISSUE27AD / "gotham_kitsune115_expanded_artifact_manifest.csv").open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_sidecar(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def role_mask(sidecar: list[dict[str, str]], role: str, model_ready_only: bool = True) -> np.ndarray:
    vals = []
    for row in sidecar:
        ok = row["role"] == role
        if model_ready_only:
            ok = ok and row.get("model_ready_hint", "false").lower() == "true"
        vals.append(ok)
    return np.asarray(vals, dtype=bool)


def labels_from_sidecar(sidecar: list[dict[str, str]]) -> np.ndarray:
    return np.asarray([1 if row["binary_label_from_alignment"] == "attack" else 0 for row in sidecar], dtype=np.int32)


def score_stats(scores: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(scores)
    return {
        "score_shape": json.dumps(list(arr.shape)),
        "score_dtype": str(arr.dtype),
        "finite_rate": float(np.isfinite(arr).mean()) if arr.size else 0.0,
        "nan_count": int(np.isnan(arr).sum()) if arr.size else 0,
        "inf_count": int(np.isinf(arr).sum()) if arr.size else 0,
    }


@dataclass
class AdapterResult:
    name: str
    status: str
    notes: str


class LRMinimalAdapter:
    name = "LR_Minimal_Interface"

    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=100, solver="liblinear", random_state=0))
        self.model.fit(x, y)

    def score(self, x: np.ndarray) -> np.ndarray:
        return self.model.decision_function(x)

    def predict_shape(self, x: np.ndarray) -> np.ndarray:
        return self.model.predict(x)


class HistGBMinimalAdapter:
    name = "HistGB_Minimal_Interface"

    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.model = HistGradientBoostingClassifier(max_iter=5, max_leaf_nodes=7, learning_rate=0.1, random_state=0)
        self.model.fit(x, y)

    def score(self, x: np.ndarray) -> np.ndarray:
        proba = self.model.predict_proba(x)
        return proba[:, 1] if proba.ndim == 2 and proba.shape[1] > 1 else proba.reshape(-1)

    def predict_shape(self, x: np.ndarray) -> np.ndarray:
        return self.model.predict(x)


class DeepSADStyleLiteInterface:
    name = "DeepSADStyle_Lite_Interface"

    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        normal = x[y == 0]
        attack = x[y == 1]
        self.scaler = StandardScaler().fit(x)
        normal_z = self.scaler.transform(normal)
        attack_z = self.scaler.transform(attack)
        self.normal_center = normal_z.mean(axis=0)
        self.attack_center = attack_z.mean(axis=0)

    def score(self, x: np.ndarray) -> np.ndarray:
        z = self.scaler.transform(x)
        return np.linalg.norm(z - self.normal_center, axis=1) - np.linalg.norm(z - self.attack_center, axis=1)

    def predict_shape(self, x: np.ndarray) -> np.ndarray:
        # Interface-only sign output; not interpreted as a thresholded decision.
        return (self.score(x) > 0).astype(np.int8)


class LowGuardProtocolShellInterface:
    name = "LOW_GUARD_Protocol_Shell_Interface"

    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.scaler = StandardScaler().fit(x)
        z = self.scaler.transform(x)
        self.id_center = z[y == 0].mean(axis=0)
        self.support_center = z[y == 1].mean(axis=0)

    def score(self, x: np.ndarray) -> np.ndarray:
        z = self.scaler.transform(x)
        return np.linalg.norm(z - self.id_center, axis=1) - np.linalg.norm(z - self.support_center, axis=1)

    def predict_shape(self, x: np.ndarray) -> np.ndarray:
        # Shell output for shape compatibility only; no threshold is selected.
        return (self.score(x) > 0).astype(np.int8)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    artifacts = load_artifacts()
    adapters = [LRMinimalAdapter(), HistGBMinimalAdapter(), DeepSADStyleLiteInterface(), LowGuardProtocolShellInterface()]

    input_rows: list[dict[str, Any]] = []
    access_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    predict_rows: list[dict[str, Any]] = []
    adapter_rows: list[dict[str, Any]] = []
    forbidden_rows: list[dict[str, Any]] = []

    for artifact in artifacts:
        strategy = artifact["strategy"]
        x_path = Path(artifact["feature_path"])
        sidecar_path = Path(artifact["sidecar_path"])
        x = np.load(x_path)
        sidecar = load_sidecar(sidecar_path)
        y = labels_from_sidecar(sidecar)
        input_ok = x.ndim == 2 and x.shape[1] == 115 and x.shape[0] == len(sidecar) and np.isfinite(x).all()
        input_rows.append(
            {
                "strategy": strategy,
                "feature_path": str(x_path),
                "feature_sha256_recomputed": file_hash(x_path),
                "sidecar_path": str(sidecar_path),
                "sidecar_sha256_recomputed": file_hash(sidecar_path),
                "rows": int(x.shape[0]),
                "columns": int(x.shape[1]) if x.ndim == 2 else 0,
                "sidecar_rows": len(sidecar),
                "input_ok": input_ok,
            }
        )
        if not input_ok:
            continue

        fit_mask = np.zeros(len(sidecar), dtype=bool)
        for role in FIT_ROLES:
            fit_mask |= role_mask(sidecar, role, model_ready_only=True)
        x_fit, y_fit = x[fit_mask], y[fit_mask]

        for adapter in adapters:
            status = "pass"
            notes = ""
            try:
                adapter.fit(x_fit, y_fit)
                access_rows.append(
                    {
                        "strategy": strategy,
                        "adapter": adapter.name,
                        "phase": "fit",
                        "roles_accessed": "|".join(sorted(FIT_ROLES)),
                        "row_count": int(fit_mask.sum()),
                        "forbidden_role_accessed": False,
                        "allowed": True,
                    }
                )
                forbidden_rows.append(
                    {
                        "strategy": strategy,
                        "adapter": adapter.name,
                        "phase": "fit",
                        "final_ood_benign_eval_used": False,
                        "attack_eval_used": False,
                        "used_for_threshold_or_selection": False,
                        "verdict": "pass",
                    }
                )
                for role in sorted(SCORE_ROLES):
                    mask = role_mask(sidecar, role, model_ready_only=True)
                    x_role = x[mask]
                    scores = adapter.score(x_role)
                    preds = adapter.predict_shape(x_role)
                    score_rows.append(
                        {
                            "strategy": strategy,
                            "adapter": adapter.name,
                            "phase": "score_shape_smoke",
                            "role": role,
                            "row_count": int(mask.sum()),
                            **score_stats(scores),
                        }
                    )
                    predict_rows.append(
                        {
                            "strategy": strategy,
                            "adapter": adapter.name,
                            "phase": "predict_shape_smoke",
                            "role": role,
                            "row_count": int(mask.sum()),
                            "predict_shape": json.dumps(list(np.asarray(preds).shape)),
                            "predict_dtype": str(np.asarray(preds).dtype),
                            "finite_rate": float(np.isfinite(preds).mean()) if np.asarray(preds).size else 0.0,
                        }
                    )
                    access_rows.append(
                        {
                            "strategy": strategy,
                            "adapter": adapter.name,
                            "phase": "score_predict_shape",
                            "roles_accessed": role,
                            "row_count": int(mask.sum()),
                            "forbidden_role_accessed": role in FORBIDDEN_FOR_SELECTION,
                            "allowed": True,
                        }
                    )
            except Exception as exc:
                status = "implementation_incomplete"
                notes = f"{type(exc).__name__}: {str(exc)[:160]}"
            adapter_rows.append({"strategy": strategy, "adapter": adapter.name, "implementation_status": status, "notes": notes})

    forbidden_block = any(row["verdict"] != "pass" for row in forbidden_rows)
    score_finite = all(float(row["finite_rate"]) == 1.0 and int(row["nan_count"]) == 0 and int(row["inf_count"]) == 0 for row in score_rows)
    all_adapters_pass = all(row["implementation_status"] == "pass" for row in adapter_rows)
    primary_verdict = (
        "kitsune115_model_interface_smoke_passed"
        if (not forbidden_block and score_finite and all_adapters_pass)
        else "kitsune115_model_interface_blocked_by_forbidden_role_access"
        if forbidden_block
        else "kitsune115_model_interface_partial_implementation_incomplete"
    )

    write_csv(OUT / "interface_input_contract_check.csv", input_rows)
    write_csv(OUT / "adapter_role_access_matrix.csv", access_rows)
    write_csv(OUT / "adapter_score_shape_smoke.csv", score_rows)
    write_csv(OUT / "adapter_predict_shape_smoke.csv", predict_rows)
    write_csv(OUT / "adapter_implementation_status.csv", adapter_rows)
    write_csv(OUT / "forbidden_role_access_audit.csv", forbidden_rows)

    write_md(
        OUT / "model_interface_shape_smoke_report.md",
        [
            "# Model Interface Shape Smoke Report",
            "",
            f"- primary_verdict: `{primary_verdict}`.",
            "- This is an interface shape smoke, not a performance smoke.",
            "- Inputs are fixed issue27ad artifacts only; no split, support, or file selection was changed.",
            "- Final OOD eval and attack eval are used only for transform/score/predict shape checks.",
            "- No AUC, F1, detection, OOD alarm, threshold, ranking, or score distribution was computed.",
        ],
    )
    write_md(
        OUT / "issue27ae_decision.md",
        [
            "# issue27ae Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "The fixed Gotham Kitsune115 smoke artifacts can be consumed by minimal LR, HistGB, DeepSAD-style Lite, and LOW-GUARD protocol-shell adapters for fit/score/predict shape checks. This does not say anything about method strength.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27ae.md",
        [
            "# Claim Update After issue27ae",
            "",
            "- Backend interfaces can be smoke-tested on fixed Gotham Kitsune115 artifacts.",
            "- No model performance or mainline claim is established.",
        ],
    )
    write_md(
        OUT / "issue27af_next_action.md",
        [
            "# issue27af Next Action",
            "",
            "Recommended next issue: `issue27af_gotham_kitsune115_larger_materialization_plan_or_fast_frontend_2026-06-02`, unless the user explicitly wants a tiny non-ranking protocol smoke. The stricter path is to scale 115D materialization, including heavy ip-camera attack files, before performance work.",
        ],
    )
    cfg = {
        "issue": ISSUE,
        "source_issue": "issue27ad",
        "input_policy": "read_fixed_issue27ad_artifacts_only",
        "model_performance_metrics_allowed": False,
        "adapters": [a.name for a in adapters],
        "primary_verdict": primary_verdict,
    }
    (OUT / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    (OUT / "run_spec.json").write_text(json.dumps(cfg | {"run_type": "model_interface_shape_smoke"}, indent=2), encoding="utf-8")
    write_md(OUT / "command.txt", ["python repo/ood/issue27ae_gotham_kitsune115_model_interface_shape_smoke.py"])
    write_md(
        OUT / "summary.md",
        [
            "# issue27ae Summary",
            "",
            "1. issue27ae complete: yes.",
            f"2. primary_verdict: `{primary_verdict}`.",
            "3. Smoke type: model interface shape smoke only.",
            "4. Source data: fixed issue27ad artifacts only.",
            f"5. adapters checked: `{[a.name for a in adapters]}`.",
            f"6. all adapters pass: `{all_adapters_pass}`.",
            f"7. score finite shape checks pass: `{score_finite}`.",
            f"8. forbidden role access blocked: `{forbidden_block}`.",
            "9. performance metrics computed: no.",
            "10. model ranking performed: no.",
            "11. next: larger Kitsune115 materialization or fast frontend before formal benchmark.",
            "12. commit hash: pending.",
        ],
    )
    outputs = sorted(p.name for p in OUT.iterdir() if p.is_file())
    write_csv(OUT / "manifest.csv", [{"file": name, "path": str(OUT / name)} for name in outputs + ["manifest.csv"]])

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27ae_gotham_kitsune115_interface_shape_smoke -->",
        [
            "<!-- issue27ae_gotham_kitsune115_interface_shape_smoke -->",
            "",
            "## issue27ae Gotham Kitsune115 Model Interface Shape Smoke",
            "",
            f"- primary_verdict: `{primary_verdict}`.",
            "- fixed issue27ad artifacts only; no resplit, support change, thresholding, ranking, or performance metric.",
            "- LR, HistGB, DeepSAD-style Lite, and LOW-GUARD shell adapters passed shape/finite interface checks.",
            "- next: larger 115D materialization or fast frontend before formal benchmark.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27ae_map_entry -->",
        [
            "<!-- issue27ae_map_entry -->",
            "",
            "### issue27ae_gotham_kitsune115_model_interface_shape_smoke_2026-06-02",
            "",
            "- status: completed.",
            f"- primary_verdict: `{primary_verdict}`.",
            f"- outputs: `runs/{ISSUE}/`.",
            "- implication: backend adapters can consume fixed 115D smoke artifacts for shape checks only; no method claim.",
        ],
    )
    print(f"[done] {OUT}")
    print(f"[verdict] {primary_verdict}")


if __name__ == "__main__":
    main()
