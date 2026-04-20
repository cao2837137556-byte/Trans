from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from paths import ARTIFACT_RUNS_DIR


TON_TOKENS = ["ton", "ton-iot", "ton_iot", "train_test_network", "network dataset"]
TABULAR_SUFFIXES = {".csv", ".tsv", ".txt", ".parquet"}
LABEL_CANDIDATES = ["label", "Label", "type", "Type", "attack", "Attack", "category", "Category", "class", "Class"]


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, tuple):
        return [clean(v) for v in obj]
    return obj


def is_ton_candidate(path: Path) -> bool:
    text = str(path).lower()
    return any(tok in text for tok in TON_TOKENS)


def inspect_table(path: Path, sample_rows: int) -> Dict[str, object]:
    try:
        if path.suffix.lower() == ".parquet":
            df = pd.read_parquet(path).head(sample_rows)
        else:
            sep = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
            df = pd.read_csv(path, sep=sep, nrows=sample_rows, low_memory=False)
    except Exception as exc:
        return {"read_ok": False, "error": str(exc)}

    label_col: Optional[str] = None
    for c in LABEL_CANDIDATES:
        if c in df.columns:
            label_col = c
            break
    out: Dict[str, object] = {
        "read_ok": True,
        "rows_sampled": int(len(df)),
        "n_columns": int(df.shape[1]),
        "columns_preview": [str(c) for c in df.columns[:30]],
        "label_column": label_col,
    }
    if label_col is not None:
        vc = df[label_col].astype(str).value_counts(dropna=False).head(12).to_dict()
        out["label_top_counts"] = {str(k): int(v) for k, v in vc.items()}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="TON-IoT local intake gate for second-environment fallback.")
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--sample-rows", type=int, default=2048)
    args = parser.parse_args()

    run_dir = ARTIFACT_RUNS_DIR / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)

    root = args.data_root.expanduser().resolve()
    all_tabular = []
    if root.exists():
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in TABULAR_SUFFIXES:
                all_tabular.append(p)
    all_tabular.sort()

    ton_candidates = [p for p in all_tabular if is_ton_candidate(p)]
    inspected_rows: List[Dict[str, object]] = []
    for p in ton_candidates[:80]:
        inspected_rows.append({"path": str(p), "suffix": p.suffix.lower(), **inspect_table(p, args.sample_rows)})

    labeled_count = sum(1 for r in inspected_rows if r.get("read_ok") and r.get("label_column"))
    if not root.exists():
        verdict = "blocked_data_root_missing"
        reason = "Provided data root does not exist."
    elif len(ton_candidates) == 0:
        verdict = "blocked_missing_toniot_files"
        reason = "No TON-IoT-like tabular files were found under the provided data root."
    elif labeled_count == 0:
        verdict = "blocked_toniot_labels_not_detected"
        reason = "TON-IoT-like files were found, but no recognizable label column was detected in sampled rows."
    else:
        verdict = "toniot_intake_ready_for_smoke"
        reason = "TON-IoT-like labeled tabular files are available for local smoke preparation."

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": str(run_dir),
        "data_root": str(root),
        "exists": bool(root.exists()),
        "n_tabular_files_total": int(len(all_tabular)),
        "n_toniot_candidates": int(len(ton_candidates)),
        "n_toniot_labeled_candidates": int(labeled_count),
        "verdict": verdict,
        "reason": reason,
    }

    pd.DataFrame(inspected_rows).to_csv(run_dir / "toniot_candidate_files.csv", index=False)
    (run_dir / "intake_report.json").write_text(json.dumps(clean(report), indent=2), encoding="utf-8")
    (run_dir / "config.json").write_text(
        json.dumps({"run_tag": args.run_tag, "data_root": str(root), "sample_rows": int(args.sample_rows)}, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "run_spec.json").write_text(
        json.dumps({"stage": "second_environment_toniot_intake", "goal": "Gate whether TON-IoT fallback can start."}, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "command.txt").write_text(" ".join(sys.argv) + "\n", encoding="utf-8")

    summary_lines = [
        "# TON-IoT Intake Summary",
        "",
        f"- Run tag: `{args.run_tag}`",
        f"- Data root: `{root}`",
        f"- Verdict: `{verdict}`",
        f"- Reason: {reason}",
        "",
        "## Counts",
        f"- all tabular files: `{len(all_tabular)}`",
        f"- TON-like candidate files: `{len(ton_candidates)}`",
        f"- TON-like labeled candidates: `{labeled_count}`",
        "",
        "## Next",
    ]
    if verdict == "toniot_intake_ready_for_smoke":
        summary_lines.append("- Proceed to TON-IoT local smoke with fixed mainline policies.")
    else:
        summary_lines.append("- Add TON-IoT files into this root (or provide the exact TON-IoT subdirectory), then rerun intake.")
    (run_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(run_dir), "verdict": verdict}, ensure_ascii=True))


if __name__ == "__main__":
    main()
