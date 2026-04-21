from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
if str(REPO_DIR) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(REPO_DIR))

from paths import ARTIFACT_RUNS_DIR


REQUIRED_POLICIES = {"fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"}
REQUIRED_OBJECTS = {"dA", "strongest_candidate_transformer_covreg_v2_seed101", "ft_transformer_ae"}


def check_split_manifest(manifest_path: Path, csv_path_override: Path | None, label_col: str, normal_label: str) -> Dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    csv_path = csv_path_override if csv_path_override is not None else Path(manifest["csv_path"])
    df = pd.read_csv(csv_path, low_memory=False)
    if label_col not in df.columns:
        raise RuntimeError(f"Missing label column: {label_col}")
    labels = df[label_col].astype(str).to_numpy()

    id_idx = np.asarray(manifest["id_indices"], dtype=np.int64)
    ood_idx = np.asarray(manifest["ood_indices"], dtype=np.int64)
    attack_idx = np.asarray(manifest["attack_indices"], dtype=np.int64)
    all_idx = np.concatenate([id_idx, ood_idx, attack_idx])

    checks = {
        "indices_in_bounds": bool(np.all((all_idx >= 0) & (all_idx < len(df)))),
        "id_ood_disjoint": bool(len(np.intersect1d(id_idx, ood_idx)) == 0),
        "id_attack_disjoint": bool(len(np.intersect1d(id_idx, attack_idx)) == 0),
        "ood_attack_disjoint": bool(len(np.intersect1d(ood_idx, attack_idx)) == 0),
        "id_label_is_normal": bool(np.all(labels[id_idx] == str(normal_label))),
        "ood_label_is_normal": bool(np.all(labels[ood_idx] == str(normal_label))),
        "attack_label_not_normal": bool(np.all(labels[attack_idx] != str(normal_label))),
    }
    return {
        "csv_path": str(csv_path),
        "n_rows": int(len(df)),
        "id_n": int(len(id_idx)),
        "ood_n": int(len(ood_idx)),
        "attack_n": int(len(attack_idx)),
        "checks": checks,
    }


def check_run_outputs(run_dir: Path) -> Dict[str, object]:
    required_files = [
        "command.txt",
        "config.json",
        "run_spec.json",
        "summary.md",
        "object_prerun_results.csv",
        "object_polarity.csv",
        "object_diagnostics.csv",
    ]
    exists = {f: bool((run_dir / f).exists()) for f in required_files}
    missing = [k for k, v in exists.items() if not v]

    if missing:
        return {
            "required_files_present": False,
            "missing_files": missing,
            "matrix_ok": False,
            "nonfinite_ok": False,
            "naive_budget_ok": False,
        }

    result_df = pd.read_csv(run_dir / "object_prerun_results.csv")
    diag_df = pd.read_csv(run_dir / "object_diagnostics.csv")
    pol_df = pd.read_csv(run_dir / "object_polarity.csv")

    objects = set(result_df["object_label"].astype(str).unique().tolist())
    policies = set(result_df["policy_name"].astype(str).unique().tolist())
    matrix_ok = REQUIRED_OBJECTS.issubset(objects) and REQUIRED_POLICIES.issubset(policies)

    nonfinite_cols = [c for c in diag_df.columns if c.startswith("nonfinite_")]
    nonfinite_count = int(diag_df[nonfinite_cols].fillna(0).to_numpy(dtype=np.int64).sum()) if nonfinite_cols else -1
    nonfinite_ok = (nonfinite_count == 0)

    metric_cols = ["ood_alarm_ratio", "attack_detection", "id_alarm_ratio", "roc_auc_attack_vs_ood"]
    metric_finite = bool(np.isfinite(result_df[metric_cols].to_numpy(dtype=np.float64)).all())
    polarity_finite = bool(np.isfinite(pol_df[["auc_chosen", "auc_other_orientation", "improvement_over_other"]].to_numpy(dtype=np.float64)).all())
    naive_budget_ok = bool(result_df["policy_name"].astype(str).str.contains("naive_calibrated_budget5000_target1pct").any())

    return {
        "required_files_present": True,
        "missing_files": [],
        "objects": sorted(objects),
        "policies": sorted(policies),
        "matrix_ok": bool(matrix_ok),
        "nonfinite_ok": bool(nonfinite_ok),
        "nonfinite_total": int(nonfinite_count),
        "metric_finite_ok": metric_finite,
        "polarity_finite_ok": polarity_finite,
        "naive_budget_ok": naive_budget_ok,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Engineering/protocol gate for TON object pre-run.")
    parser.add_argument("--run-tag", required=True)
    parser.add_argument(
        "--split-manifest",
        type=Path,
        default=ARTIFACT_RUNS_DIR / "second_environment_toniot_precheck_2026-04-20" / "split_manifest.json",
    )
    parser.add_argument("--csv-path", type=Path, default=None)
    parser.add_argument("--label-col", default="label")
    parser.add_argument("--normal-label", default="0")
    args = parser.parse_args()

    run_dir = ARTIFACT_RUNS_DIR / args.run_tag
    gate_dir = run_dir / "engineering_gate"
    gate_dir.mkdir(parents=True, exist_ok=True)

    split_report = check_split_manifest(args.split_manifest, args.csv_path, args.label_col, args.normal_label)
    output_report = check_run_outputs(run_dir)

    split_ok = bool(all(bool(v) for v in split_report["checks"].values()))
    output_ok = bool(
        output_report.get("required_files_present", False)
        and output_report.get("matrix_ok", False)
        and output_report.get("metric_finite_ok", False)
        and output_report.get("polarity_finite_ok", False)
        and output_report.get("naive_budget_ok", False)
    )
    verdict = "engineering_gate_pass"
    notes: List[str] = []
    if not split_ok:
        verdict = "engineering_gate_fail_split"
        notes.append("Split manifest integrity/label checks failed.")
    if not output_ok:
        verdict = "engineering_gate_fail_outputs"
        notes.append("Output matrix or finite-value policy checks failed.")
    if output_report.get("required_files_present", False) and not output_report.get("nonfinite_ok", True):
        if verdict == "engineering_gate_pass":
            verdict = "engineering_gate_warning_nonfinite"
        notes.append(f"Detected non-finite replacements in diagnostics: total={output_report.get('nonfinite_total')}.")

    report = {
        "run_tag": args.run_tag,
        "run_dir": str(run_dir),
        "split_manifest": str(args.split_manifest),
        "split_report": split_report,
        "output_report": output_report,
        "verdict": verdict,
        "notes": notes,
    }
    (gate_dir / "engineering_gate_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# TON Object Pre-Run Engineering Gate",
        "",
        f"- Run tag: `{args.run_tag}`",
        f"- Verdict: `{verdict}`",
        "",
        "## Split Checks",
    ]
    for k, v in split_report["checks"].items():
        lines.append(f"- `{k}`: `{bool(v)}`")
    lines += [
        "",
        "## Output Checks",
        f"- required_files_present: `{output_report.get('required_files_present')}`",
        f"- matrix_ok: `{output_report.get('matrix_ok')}`",
        f"- naive_budget_ok: `{output_report.get('naive_budget_ok')}`",
        f"- metric_finite_ok: `{output_report.get('metric_finite_ok')}`",
        f"- polarity_finite_ok: `{output_report.get('polarity_finite_ok')}`",
        f"- nonfinite_ok: `{output_report.get('nonfinite_ok')}`",
        f"- nonfinite_total: `{output_report.get('nonfinite_total', 'n/a')}`",
    ]
    if notes:
        lines += ["", "## Notes"] + [f"- {n}" for n in notes]
    (gate_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(run_dir), "gate_dir": str(gate_dir), "verdict": verdict}, ensure_ascii=True))


if __name__ == "__main__":
    main()
