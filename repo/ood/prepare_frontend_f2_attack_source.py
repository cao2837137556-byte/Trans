from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd


REQUIRED_KEYS = {
    "flat_features",
    "family_scale_tokens",
    "token_matrix",
    "token_slot_mask",
    "token_family_id",
    "token_scale_id",
}


def load_structured_npz(path: Path) -> Dict[str, np.ndarray]:
    data = np.load(path)
    keys = set(data.files)
    missing = REQUIRED_KEYS - keys
    if missing:
        raise RuntimeError(f"Missing keys {sorted(missing)} in {path}")
    return {k: data[k] for k in data.files}


def take_first(x: np.ndarray, n: int) -> np.ndarray:
    return x[: min(len(x), n)].copy()


def stats_flat(x: np.ndarray) -> Dict[str, float]:
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
    ap = argparse.ArgumentParser(description="Prepare Frontend-F2 structured attack source aligned with stage2 manifest.")
    ap.add_argument("--run-tag", default=f"frontend_f2_attack_source_{today}")
    ap.add_argument("--attack-structured-npz", type=Path, required=True)
    ap.add_argument("--attack-manifest-stage2", type=Path, required=True)
    args = ap.parse_args()

    run_dir = args.attack_structured_npz.parents[1] / args.run_tag
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    attack = load_structured_npz(args.attack_structured_npz)
    manifest = json.loads(args.attack_manifest_stage2.read_text(encoding="utf-8-sig"))
    use_first_n = int(manifest["use_first_n"])

    payload = {
        "flat_features": take_first(attack["flat_features"], use_first_n).astype(np.float32),
        "family_scale_tokens": take_first(attack["family_scale_tokens"], use_first_n).astype(np.float32),
        "token_matrix": take_first(attack["token_matrix"], use_first_n).astype(np.float32),
        "token_slot_mask": attack["token_slot_mask"].astype(np.float32),
        "token_family_id": attack["token_family_id"].astype(np.int64),
        "token_scale_id": attack["token_scale_id"].astype(np.int64),
    }

    structured_path = data_dir / "attack_source_structured.npz"
    np.savez_compressed(structured_path, **payload)
    flat_npy = data_dir / "attack_source_100.npy"
    flat_csv = data_dir / "attack_source_100.csv"
    np.save(flat_npy, payload["flat_features"])
    pd.DataFrame(payload["flat_features"]).to_csv(flat_csv, header=False, index=False)

    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "attack_structured_npy": str(args.attack_structured_npz),
        "attack_manifest_stage2": str(args.attack_manifest_stage2),
        "use_first_n": use_first_n,
        "attack_stats": stats_flat(payload["flat_features"]),
        "outputs": {
            "attack_structured": str(structured_path),
            "attack_flat_npy": str(flat_npy),
            "attack_flat_csv": str(flat_csv),
        },
    }
    (run_dir / "frontend_f2_attack_source_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Frontend-F2 Attack Source Prep",
        "",
        f"- Date: {metadata['created_at']}",
        f"- Attack structured cache: `{args.attack_structured_npz}`",
        f"- Stage2 manifest: `{args.attack_manifest_stage2}`",
        f"- use_first_n: {use_first_n}",
        "",
        "## Outputs",
        f"- Attack structured: `{structured_path}`",
        f"- Attack flat csv: `{flat_csv}`",
    ]
    (run_dir / "frontend_f2_attack_source_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[done] frontend-f2 attack metadata: {run_dir / 'frontend_f2_attack_source_metadata.json'}")


if __name__ == "__main__":
    main()
