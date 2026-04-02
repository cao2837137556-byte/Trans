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


def load_feature_npy(path: Path) -> np.ndarray:
    x = np.load(path).astype(np.float32)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    if x.ndim != 2:
        raise RuntimeError(f"Expected 2-D feature array, got shape={x.shape}")
    if x.shape[1] != 100:
        raise RuntimeError(f"Expected 100-D features, got dim={x.shape[1]} in {path}")
    return x


def trim_rows(x: np.ndarray, max_rows: int) -> np.ndarray:
    if max_rows <= 0:
        raise ValueError("max_rows must be positive")
    return x[: min(len(x), max_rows)].copy()


def save_csv_npy(base: Path, x: np.ndarray) -> Tuple[Path, Path]:
    csv_path = base.with_suffix(".csv")
    npy_path = base.with_suffix(".npy")
    pd.DataFrame(x.astype(np.float32)).to_csv(csv_path, header=False, index=False)
    np.save(npy_path, x.astype(np.float32))
    return csv_path, npy_path


def stats(x: np.ndarray) -> Dict[str, float]:
    return {
        "rows": int(x.shape[0]),
        "dim": int(x.shape[1]),
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Prepare cross-capture 100-D source CSVs from extracted feature caches.")
    parser.add_argument("--run-tag", default=f"frontend100_crosscapture_stage1_{today}")
    parser.add_argument("--id-feature-npy", type=Path, required=True)
    parser.add_argument("--ood-feature-npy", type=Path, required=True)
    parser.add_argument("--id-max-rows", type=int, default=50000)
    parser.add_argument("--ood-max-rows", type=int, default=20000)
    args = parser.parse_args()

    run_dir = ROOT_DIR / "runs" / args.run_tag
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    id_all = load_feature_npy(args.id_feature_npy)
    ood_all = load_feature_npy(args.ood_feature_npy)
    id_src = trim_rows(id_all, args.id_max_rows)
    ood_src = trim_rows(ood_all, args.ood_max_rows)

    id_csv, id_npy = save_csv_npy(data_dir / "id_source_100", id_src)
    ood_csv, ood_npy = save_csv_npy(data_dir / "ood_benign_source_100", ood_src)

    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "id_feature_npy": str(args.id_feature_npy),
        "ood_feature_npy": str(args.ood_feature_npy),
        "id_all_stats": stats(id_all),
        "ood_all_stats": stats(ood_all),
        "id_used_stats": stats(id_src),
        "ood_used_stats": stats(ood_src),
        "id_max_rows": int(args.id_max_rows),
        "ood_max_rows": int(args.ood_max_rows),
        "outputs": {
            "id_csv": str(id_csv),
            "id_npy": str(id_npy),
            "ood_csv": str(ood_csv),
            "ood_npy": str(ood_npy),
        },
    }
    (run_dir / "crosscapture_source_metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    lines = []
    lines.append("# Frontend100 Cross-capture Source Prep")
    lines.append("")
    lines.append(f"- Date: {metadata['created_at']}")
    lines.append(f"- ID source cache: `{args.id_feature_npy}`")
    lines.append(f"- OOD benign source cache: `{args.ood_feature_npy}`")
    lines.append(f"- ID used: rows={id_src.shape[0]}, dim={id_src.shape[1]}")
    lines.append(f"- OOD used: rows={ood_src.shape[0]}, dim={ood_src.shape[1]}")
    lines.append("")
    lines.append("## Outputs")
    lines.append(f"- ID csv: `{id_csv}`")
    lines.append(f"- OOD benign csv: `{ood_csv}`")
    (run_dir / "crosscapture_source_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[done] source metadata: {run_dir / 'crosscapture_source_metadata.json'}")


if __name__ == "__main__":
    main()
