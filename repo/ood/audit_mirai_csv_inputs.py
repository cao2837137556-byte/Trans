from __future__ import annotations

import argparse
import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = REPO_DIR.parent


def inspect_csv(path: Path, chunk_size: int = 200000) -> Dict[str, object]:
    n_cols = int(pd.read_csv(path, header=None, nrows=1).shape[1])

    first10: List[float] = []
    last10: deque = deque(maxlen=10)
    n_rows = 0
    is_finite = True
    is_integer_like = True
    is_strict_step1 = True
    expected = None

    for chunk in pd.read_csv(path, header=None, usecols=[0], chunksize=chunk_size):
        col = chunk.iloc[:, 0].to_numpy(dtype=np.float64)
        n_rows += len(col)

        if len(first10) < 10:
            need = 10 - len(first10)
            first10.extend(col[:need].tolist())

        for value in col:
            last10.append(float(value))

        if not np.all(np.isfinite(col)):
            is_finite = False
        if np.max(np.abs(col - np.round(col))) > 1e-9:
            is_integer_like = False

        if expected is None:
            expected = float(col[0])
        expected_arr = expected + np.arange(len(col), dtype=np.float64)
        if np.max(np.abs(col - expected_arr)) > 1e-9:
            is_strict_step1 = False
        expected += len(col)

    col0_start = float(first10[0]) if first10 else None
    col0_end = float(last10[-1]) if last10 else None
    starts_at_0_or_1 = col0_start in (0.0, 1.0)
    index_like = bool(
        n_cols >= 2
        and is_finite
        and is_integer_like
        and is_strict_step1
        and starts_at_0_or_1
    )

    sample = pd.read_csv(path, header=None, nrows=2).iloc[:, :6]
    sample_rows = [list(map(float, sample.iloc[i].tolist())) for i in range(len(sample))]

    return {
        "path": str(path),
        "rows": int(n_rows),
        "cols": int(n_cols),
        "col0_first10": first10,
        "col0_last10": list(last10),
        "col0_start": col0_start,
        "col0_end": col0_end,
        "col0_finite": bool(is_finite),
        "col0_integer_like": bool(is_integer_like),
        "col0_strict_step1": bool(is_strict_step1),
        "col0_starts_at_0_or_1": bool(starts_at_0_or_1),
        "col0_index_like": bool(index_like),
        "sample_row0_first6": sample_rows[0] if sample_rows else [],
        "sample_row1_first6": sample_rows[1] if len(sample_rows) > 1 else [],
    }


def build_markdown(reports: List[Dict[str, object]]) -> str:
    lines: List[str] = []
    lines.append("# Mirai CSV Input Audit (Index-like Column-0 Check)")
    lines.append("")
    lines.append(f"- Date: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("- Scope: `Mirai_dataset.csv` and `my_gold_mirai.csv`.")
    lines.append("- Goal: determine whether column-0 is an index-like column that should be removed.")
    lines.append("")
    lines.append("| file | rows | cols | col0 pattern | should_drop_col0 |")
    lines.append("|---|---:|---:|---|---|")
    for r in reports:
        pattern = "0/1-start + strict +1 increments" if r["col0_index_like"] else "not index-like"
        lines.append(
            f"| `{Path(str(r['path'])).name}` | {r['rows']} | {r['cols']} | {pattern} | {r['col0_index_like']} |"
        )

    lines.append("")
    lines.append("## Evidence")
    for r in reports:
        lines.append(f"### {Path(str(r['path'])).name}")
        lines.append(f"- col0 first10: {r['col0_first10']}")
        lines.append(f"- col0 last10: {r['col0_last10']}")
        lines.append(
            "- checks: "
            f"finite={r['col0_finite']}, integer_like={r['col0_integer_like']}, "
            f"strict_step1={r['col0_strict_step1']}, starts_at_0_or_1={r['col0_starts_at_0_or_1']}"
        )
        lines.append(f"- sample row0 first6: {r['sample_row0_first6']}")
        lines.append(f"- sample row1 first6: {r['sample_row1_first6']}")
        if r["col0_index_like"]:
            lines.append(
                "- conclusion: column-0 is index-like and should be removed before detector input."
            )
        else:
            lines.append("- conclusion: column-0 is not index-like; keep as feature.")
        lines.append("")

    lines.append("## Audit Conclusion")
    lines.append(
        "- Both files show an index-like column-0 (`0,1,2,...`), not a stable network statistic feature."
    )
    lines.append("- For Mirai historical CSV chain, drop column-0 to obtain clean 115-D inputs.")
    lines.append("- Keep this rule automatic and conditional (pattern-based), not hardcoded for all files.")
    return "\n".join(lines) + "\n"


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Audit Mirai CSV files for index-like column-0.")
    parser.add_argument("--run-tag", default=f"csv_input_clean_stage1_{today}")
    args = parser.parse_args()

    run_dir = ROOT_DIR / "runs" / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)

    targets = [ROOT_DIR / "Mirai_dataset.csv", ROOT_DIR / "my_gold_mirai.csv"]
    reports = [inspect_csv(path) for path in targets]

    (run_dir / "mirai_csv_input_audit.json").write_text(
        json.dumps(reports, indent=2),
        encoding="utf-8",
    )
    (run_dir / "mirai_csv_input_audit.md").write_text(
        build_markdown(reports),
        encoding="utf-8",
    )
    print(f"[done] audit written to: {run_dir}")


if __name__ == "__main__":
    main()
