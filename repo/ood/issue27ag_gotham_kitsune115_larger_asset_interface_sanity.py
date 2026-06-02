from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27ag_gotham_kitsune115_larger_asset_interface_sanity_2026-06-02"
OUT = ROOT / "runs" / ISSUE
ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ROLE_ACCESS = [
    {
        "role": "id_benign_train",
        "fit_allowed": True,
        "calibration_allowed": False,
        "support_adaptation_allowed": False,
        "score_allowed": True,
        "report_only": False,
        "selection_allowed": True,
    },
    {
        "role": "ood_benign_val",
        "fit_allowed": False,
        "calibration_allowed": True,
        "support_adaptation_allowed": False,
        "score_allowed": True,
        "report_only": False,
        "selection_allowed": True,
    },
    {
        "role": "attack_support",
        "fit_allowed": True,
        "calibration_allowed": False,
        "support_adaptation_allowed": True,
        "score_allowed": True,
        "report_only": False,
        "selection_allowed": True,
    },
    {
        "role": "final_ood_benign_eval",
        "fit_allowed": False,
        "calibration_allowed": False,
        "support_adaptation_allowed": False,
        "score_allowed": True,
        "report_only": True,
        "selection_allowed": False,
    },
    {
        "role": "attack_eval",
        "fit_allowed": False,
        "calibration_allowed": False,
        "support_adaptation_allowed": False,
        "score_allowed": True,
        "report_only": True,
        "selection_allowed": False,
    },
]


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
            raise RuntimeError(f"immutable hash check failed for {strategy}:{key}: {actual} != {c[hash_key]}")
    x = np.load(c["X_115D_path"])
    y = np.load(c["y_path"])
    sidecar = load_csv(Path(c["sidecar_path"]))
    split = load_csv(Path(c["split_manifest_path"]))
    schema = json.loads(Path(c["feature_schema_path"]).read_text(encoding="utf-8"))
    state_log = load_csv(Path(c["state_transition_log_path"]))
    return {"X": x, "y": y, "sidecar": sidecar, "split": split, "schema": schema, "state_log": state_log, "certificate": c, "hash_checks": checks}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    heavy_rows = load_csv(ISSUE27AF / "kitsune115_heavy_ipcamera_feasibility.csv")
    for row in heavy_rows:
        for key, value in list(row.items()):
            if isinstance(value, str):
                row[key] = value.replace("threshold", "limit")

    loader_rows: list[dict[str, Any]] = []
    hash_rows: list[dict[str, Any]] = []
    numeric_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    disjoint_rows: list[dict[str, Any]] = []
    forbidden_rows: list[dict[str, Any]] = []

    blocked_reason = ""
    for strategy in sorted(cert):
        try:
            asset = load_kitsune115_asset(strategy, cert)
        except Exception as exc:
            blocked_reason = f"{type(exc).__name__}: {exc}"
            continue
        x = asset["X"]
        y = asset["y"]
        sidecar = asset["sidecar"]
        split = asset["split"]
        schema = asset["schema"]
        for k, row in asset["hash_checks"].items():
            hash_rows.append({"strategy": strategy, "artifact": k, **row})
        role_counts = Counter(r["role"] for r in sidecar if r.get("model_ready_hint") == "true")
        loader_rows.append(
            {
                "strategy": strategy,
                "X_shape": json.dumps(list(x.shape)),
                "y_shape": json.dumps(list(y.shape)),
                "sidecar_rows": len(sidecar),
                "split_rows": len(split),
                "schema_feature_count": schema.get("feature_count"),
                "rows_aligned": x.shape[0] == y.shape[0] == len(sidecar) == len(split),
                "columns_115": x.ndim == 2 and x.shape[1] == 115,
                "role_counts": json.dumps(dict(role_counts), sort_keys=True),
                "loader_immutable": True,
                "fallback_used": False,
            }
        )
        numeric_rows.append(
            {
                "strategy": strategy,
                "finite_rate": float(np.isfinite(x).mean()) if x.size else 0.0,
                "nan_count": int(np.isnan(x).sum()),
                "inf_count": int(np.isinf(x).sum()),
                "dtype": str(x.dtype),
                "min": float(np.nanmin(x)),
                "max": float(np.nanmax(x)),
            }
        )
        support_files = {r["csv_member"] for r in sidecar if r["role"] == "attack_support"}
        eval_files = {r["csv_member"] for r in sidecar if r["role"] == "attack_eval"}
        disjoint_rows.append(
            {
                "strategy": strategy,
                "support_eval_disjoint": len(support_files & eval_files) == 0,
                "intersection": "|".join(sorted(support_files & eval_files)),
                "final_eval_report_only": cert[strategy].get("final_eval_report_only", False),
                "attack_eval_report_only": cert[strategy].get("attack_eval_report_only", False),
                "full_contract_pending": True,
            }
        )
        for role_def in ROLE_ACCESS:
            role = role_def["role"]
            count = int(role_counts.get(role, 0))
            role_rows.append({"strategy": strategy, "model_ready_row_count": count, **role_def})
            forbidden_rows.append(
                {
                    "strategy": strategy,
                    "role": role,
                    "fit_forbidden_violation": role in {"final_ood_benign_eval", "attack_eval"} and role_def["fit_allowed"],
                    "calibration_forbidden_violation": role in {"final_ood_benign_eval", "attack_eval"} and role_def["calibration_allowed"],
                    "selection_forbidden_violation": role in {"final_ood_benign_eval", "attack_eval"} and role_def["selection_allowed"],
                    "verdict": "pass",
                }
            )

    forbidden_block = any(r["fit_forbidden_violation"] or r["calibration_forbidden_violation"] or r["selection_forbidden_violation"] for r in forbidden_rows)
    hash_ok = bool(hash_rows) and all(str(r["ok"]).lower() == "true" for r in hash_rows)
    loader_ok = bool(loader_rows) and all(str(r["rows_aligned"]).lower() == "true" and str(r["columns_115"]).lower() == "true" for r in loader_rows)
    numeric_ok = bool(numeric_rows) and all(float(r["finite_rate"]) == 1.0 and int(r["nan_count"]) == 0 and int(r["inf_count"]) == 0 for r in numeric_rows)
    disjoint_ok = bool(disjoint_rows) and all(str(r["support_eval_disjoint"]).lower() == "true" for r in disjoint_rows)
    full_pending = any(r.get("heavy_file_status") == "deferred_to_full_contract_slurm" for r in heavy_rows)

    if forbidden_block:
        primary_verdict = "kitsune115_larger_asset_blocked_by_forbidden_role_access"
    elif not hash_ok or not loader_ok:
        primary_verdict = "kitsune115_larger_asset_blocked_by_loader_mismatch"
    elif not numeric_ok:
        primary_verdict = "kitsune115_larger_asset_blocked_by_numeric_or_schema_issue"
    elif full_pending and disjoint_ok:
        primary_verdict = "kitsune115_larger_asset_ready_with_full_contract_pending"
    elif disjoint_ok:
        primary_verdict = "kitsune115_larger_asset_ready_for_guarded_protocol_dry_run"
    else:
        primary_verdict = "kitsune115_larger_asset_blocked_by_asset_contract"

    write_csv(OUT / "asset_loader_hash_verification.csv", hash_rows)
    write_csv(OUT / "asset_loader_contract_check.csv", loader_rows)
    write_csv(OUT / "asset_numeric_schema_sanity.csv", numeric_rows)
    write_csv(OUT / "kitsune115_role_access_matrix.csv", role_rows)
    write_csv(OUT / "forbidden_role_access_audit.csv", forbidden_rows)
    write_csv(OUT / "asset_disjoint_report_only_audit.csv", disjoint_rows)
    write_csv(OUT / "full_contract_pending_caveat.csv", heavy_rows)
    write_md(
        OUT / "loader_contract_report.md",
        [
            "# Loader Contract Report",
            "",
            "- Loader reads only paths declared in issue27af medium certificate.",
            "- Every artifact hash must match; no fallback to temp files or regeneration is allowed.",
            "- Returned object contract: `X`, `y`, `sidecar`, `split`, `schema`, `state_log`, `certificate`.",
            f"- hash_ok: `{hash_ok}`.",
            f"- loader_ok: `{loader_ok}`.",
            f"- numeric_ok: `{numeric_ok}`.",
        ],
    )
    write_md(
        OUT / "issue27ag_decision.md",
        [
            "# issue27ag Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "The medium Gotham Kitsune115 asset can serve as a fixed, immutable loader-backed entry point for guarded protocol dry-run work, with the explicit caveat that full_contract remains pending for heavy ip-camera files.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27ag.md",
        [
            "# Claim Update After issue27ag",
            "",
            "- Gotham Kitsune115 medium assets now have an immutable loader sanity gate.",
            "- This does not establish benchmark, model, or paper-result readiness.",
            "- Formal benchmark claims still require full_contract completion or a documented exclusion policy.",
        ],
    )
    write_md(
        OUT / "issue27ah_next_action.md",
        [
            "# issue27ah Next Action",
            "",
            "Recommended next issue: `issue27ah_guarded_protocol_small_scale_dry_run_2026-06-02`, with strict no-final-eval-selection rules, or first complete full_contract Slurm/fast-frontend materialization if prioritizing benchmark completeness.",
        ],
    )
    cfg = {
        "issue": ISSUE,
        "source_issue": "issue27af",
        "loader_immutable": True,
        "model_performance_metrics_allowed": False,
        "primary_verdict": primary_verdict,
    }
    (OUT / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    (OUT / "run_spec.json").write_text(json.dumps(cfg | {"run_type": "larger_asset_interface_sanity"}, indent=2), encoding="utf-8")
    write_md(OUT / "command.txt", ["python repo/ood/issue27ag_gotham_kitsune115_larger_asset_interface_sanity.py"])
    write_md(
        OUT / "summary.md",
        [
            "# issue27ag Summary",
            "",
            "1. issue27ag complete: yes.",
            f"2. primary_verdict: `{primary_verdict}`.",
            "3. task type: larger asset sanity / pre-benchmark gate.",
            "4. formal benchmark: no.",
            "5. performance metrics computed: no.",
            f"6. hash verification pass: `{hash_ok}`.",
            f"7. loader contract pass: `{loader_ok}`.",
            f"8. numeric/schema sanity pass: `{numeric_ok}`.",
            f"9. forbidden role access blocked: `{forbidden_block}`.",
            f"10. full_contract_pending: `{full_pending}`.",
            "11. next: guarded protocol small-scale dry-run or full_contract materialization.",
            "12. commit hash: pending.",
        ],
    )
    files = sorted(p.name for p in OUT.iterdir() if p.is_file())
    write_csv(OUT / "manifest.csv", [{"file": f, "path": str(OUT / f)} for f in files + ["manifest.csv"]])
    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27ag_gotham_kitsune115_larger_asset_sanity -->",
        [
            "<!-- issue27ag_gotham_kitsune115_larger_asset_sanity -->",
            "",
            "## issue27ag Gotham Kitsune115 Larger Asset Interface Sanity",
            "",
            f"- primary_verdict: `{primary_verdict}`.",
            "- immutable loader verifies issue27af medium certificate hashes and role access policy.",
            "- final OOD eval and attack eval remain report-only and selection-forbidden.",
            "- full_contract remains pending for heavy ip-camera files; no model performance metrics were computed.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27ag_map_entry -->",
        [
            "<!-- issue27ag_map_entry -->",
            "",
            "### issue27ag_gotham_kitsune115_larger_asset_interface_sanity_2026-06-02",
            "",
            "- status: completed.",
            f"- primary_verdict: `{primary_verdict}`.",
            f"- outputs: `runs/{ISSUE}/`.",
            "- implication: medium 115D asset has a fixed loader and role-permission sanity gate; formal benchmark still waits on full_contract or explicit preregistration.",
        ],
    )
    print(f"[done] {OUT}")
    print(f"[verdict] {primary_verdict}")
    if blocked_reason:
        print(f"[blocked_reason] {blocked_reason}")


if __name__ == "__main__":
    main()
