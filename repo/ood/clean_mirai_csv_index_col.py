from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = REPO_DIR.parent

import sys

if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from csv_input import detect_index_like_col0


def write_clean_csv(
    input_csv: Path,
    output_csv: Path,
    drop_col0: bool,
    chunk_size: int = 50000,
) -> int:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    first_chunk = True
    for chunk in pd.read_csv(input_csv, header=None, chunksize=chunk_size):
        out_chunk = chunk.iloc[:, 1:] if drop_col0 else chunk
        out_chunk.to_csv(
            output_csv,
            mode="w" if first_chunk else "a",
            index=False,
            header=False,
        )
        rows_written += len(out_chunk)
        first_chunk = False
    return rows_written


def maybe_copy_labels(label_path: Optional[Path], output_path: Optional[Path]) -> Optional[int]:
    if label_path is None or output_path is None:
        return None
    y = np.load(label_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(output_path, y)
    return int(len(y))


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Clean Mirai CSV by dropping index-like col0 only when detected.")
    parser.add_argument("--run-tag", default=f"csv_input_clean_stage1_{today}")
    parser.add_argument("--input-csv", type=Path, default=ROOT_DIR / "my_gold_mirai.csv")
    parser.add_argument("--labels", type=Path, default=ROOT_DIR / "my_gold_labels.npy")
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--output-labels", type=Path, default=None)
    args = parser.parse_args()

    run_dir = ROOT_DIR / "runs" / args.run_tag
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    output_csv = args.output_csv or (data_dir / f"{args.input_csv.stem}_clean115.csv")
    output_labels = args.output_labels
    if output_labels is None and args.labels is not None:
        output_labels = data_dir / f"{args.labels.stem}_copy.npy"

    raw_dim = int(pd.read_csv(args.input_csv, header=None, nrows=1).shape[1])
    col0 = pd.read_csv(args.input_csv, header=None, usecols=[0]).iloc[:, 0].to_numpy(dtype=np.float64)
    index_like, col0_reason = detect_index_like_col0(col0)

    rows_written = write_clean_csv(
        input_csv=args.input_csv,
        output_csv=output_csv,
        drop_col0=index_like,
    )
    used_dim = raw_dim - 1 if index_like else raw_dim

    raw_head = pd.read_csv(args.input_csv, header=None, nrows=2).to_numpy(dtype=np.float64)
    clean_head = pd.read_csv(output_csv, header=None, nrows=2).to_numpy(dtype=np.float64)
    if index_like:
        aligned = bool(np.allclose(clean_head, raw_head[:, 1:], atol=1e-9))
    else:
        aligned = bool(np.allclose(clean_head, raw_head, atol=1e-9))

    label_count = maybe_copy_labels(args.labels if args.labels.exists() else None, output_labels)

    metadata = {
        "input_csv": str(args.input_csv),
        "output_csv": str(output_csv),
        "labels_in": None if args.labels is None else str(args.labels),
        "labels_out": None if output_labels is None else str(output_labels),
        "raw_dim": raw_dim,
        "used_dim": used_dim,
        "dropped_col0": bool(index_like),
        "col0_reason": col0_reason,
        "rows_written": int(rows_written),
        "label_count": label_count,
        "head_alignment_check_passed": aligned,
    }

    (run_dir / "clean_mirai_csv_metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    lines = []
    lines.append("# Mirai CSV Cleaning Result")
    lines.append("")
    lines.append(f"- Date: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- Input: `{args.input_csv}`")
    lines.append(f"- Output: `{output_csv}`")
    lines.append(f"- raw_dim: {raw_dim}")
    lines.append(f"- used_dim: {used_dim}")
    lines.append(f"- dropped_col0: {bool(index_like)}")
    lines.append(f"- col0_reason: {col0_reason}")
    lines.append(f"- rows_written: {rows_written}")
    lines.append(f"- head_alignment_check_passed: {aligned}")
    if output_labels is not None:
        lines.append(f"- labels_out: `{output_labels}`")
    (run_dir / "clean_mirai_csv_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[done] clean output: {output_csv}")
    print(f"[done] metadata: {run_dir / 'clean_mirai_csv_metadata.json'}")


if __name__ == "__main__":
    main()
