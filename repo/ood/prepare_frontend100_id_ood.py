from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = REPO_DIR.parent


def slice_block(x: np.ndarray, start: int, count: int) -> np.ndarray:
    end = start + count
    if start < 0 or count <= 0 or end > len(x):
        raise ValueError(f"invalid slice start={start} count={count} for len={len(x)}")
    return x[start:end]


def block_stats(x: np.ndarray) -> Dict[str, float]:
    return {
        "rows": int(x.shape[0]),
        "dim": int(x.shape[1]),
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def save_block(base_path: Path, arr: np.ndarray) -> Tuple[Path, Path]:
    npy_path = base_path.with_suffix(".npy")
    csv_path = base_path.with_suffix(".csv")
    np.save(npy_path, arr.astype(np.float32))
    pd.DataFrame(arr.astype(np.float32)).to_csv(csv_path, header=False, index=False)
    return npy_path, csv_path


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Prepare ID/OOD benign 100-D sources from extracted frontend features.")
    parser.add_argument("--run-tag", default=f"frontend100_ood_stage1_{today}")
    parser.add_argument(
        "--feature-npy",
        type=Path,
        default=ROOT_DIR
        / "runs"
        / f"frontend100_ood_stage1_{today}"
        / "extract_full_iot23_7_6"
        / "iot23_7_6_features_first115000.npy",
    )
    parser.add_argument("--id-start", type=int, default=0)
    parser.add_argument("--id-count", type=int, default=50000)
    parser.add_argument("--ood-start", type=int, default=90000)
    parser.add_argument("--ood-count", type=int, default=20000)
    args = parser.parse_args()

    run_dir = ROOT_DIR / "runs" / args.run_tag
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    x = np.load(args.feature_npy).astype(np.float32)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    if x.ndim != 2:
        raise RuntimeError(f"Expected 2-D feature matrix, got shape={x.shape}")
    if x.shape[1] != 100:
        raise RuntimeError(f"Expected 100-D features, got dim={x.shape[1]}")

    id_block = slice_block(x, args.id_start, args.id_count)
    ood_block = slice_block(x, args.ood_start, args.ood_count)

    id_npy, id_csv = save_block(data_dir / "id_source_100", id_block)
    ood_npy, ood_csv = save_block(data_dir / "ood_benign_source_100", ood_block)

    overlap = not (args.id_start + args.id_count <= args.ood_start or args.ood_start + args.ood_count <= args.id_start)

    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "feature_npy": str(args.feature_npy),
        "source_total_rows": int(x.shape[0]),
        "source_dim": int(x.shape[1]),
        "id_slice": {"start": int(args.id_start), "count": int(args.id_count), "overlap_with_ood": bool(overlap)},
        "ood_slice": {"start": int(args.ood_start), "count": int(args.ood_count), "overlap_with_id": bool(overlap)},
        "id_paths": {"npy": str(id_npy), "csv": str(id_csv)},
        "ood_paths": {"npy": str(ood_npy), "csv": str(ood_csv)},
        "id_stats": block_stats(id_block),
        "ood_stats": block_stats(ood_block),
        "note": "single benign pcap fallback: ID and OOD benign are non-overlapping time segments from same IoT-23 capture",
    }
    (run_dir / "source_split_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    lines = []
    lines.append("# Frontend100 Source Split")
    lines.append("")
    lines.append(f"- Date: {metadata['created_at']}")
    lines.append(f"- Input feature cache: `{args.feature_npy}`")
    lines.append(f"- Source shape: {x.shape[0]} x {x.shape[1]}")
    lines.append(f"- ID slice: start={args.id_start}, count={args.id_count}")
    lines.append(f"- OOD benign slice: start={args.ood_start}, count={args.ood_count}")
    lines.append(f"- Overlap: {overlap}")
    lines.append("")
    lines.append("## Output")
    lines.append(f"- ID csv: `{id_csv}`")
    lines.append(f"- OOD benign csv: `{ood_csv}`")
    lines.append("")
    lines.append("## Notes")
    lines.append("- This run uses one local benign pcap and splits by time segment as fallback.")
    lines.append("- No adapter and no 115/116 conversion are used.")
    (run_dir / "source_split_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[done] split metadata: {run_dir / 'source_split_metadata.json'}")
    print(f"[done] ID csv: {id_csv}")
    print(f"[done] OOD csv: {ood_csv}")


if __name__ == "__main__":
    main()
