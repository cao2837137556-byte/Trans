from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = REPO_DIR.parent
THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
from kitsune_frontend_original_extract import (
    EXPRESSION_V3_CHANNEL_NAMES,
    EXPRESSION_V4A_HH_STABILIZED_CHANNEL_NAMES,
    EXPRESSION_V4A_HH_STABILIZED_MASK_CHANNELS,
    EXPRESSION_V4A_HH_STABILIZED_MASK_FAMILIES,
    EXPRESSION_V4A_HH_STABILIZED_NAME,
    compute_expression_v3,
    compute_expression_v4a_hh_stabilized,
)


REQUIRED_KEYS = {
    "flat_features",
    "family_scale_tokens",
    "token_matrix",
    "token_slot_mask",
    "token_family_id",
    "token_scale_id",
}
ROW_OPTIONAL_KEYS = {
    "expression_v2_matrix",
    "expression_v2_flat",
}
STATIC_OPTIONAL_KEYS = {
    "expression_v2_channel_mask",
    "expression_v2_family_id",
    "expression_v2_scale_id",
    "expression_v2_channel_names",
}
EXPRESSION_VERSION_CHOICES = ["v3", EXPRESSION_V4A_HH_STABILIZED_NAME]


def load_structured_npz(path: Path) -> Dict[str, np.ndarray]:
    data = np.load(path)
    keys = set(data.files)
    missing = REQUIRED_KEYS - keys
    if missing:
        raise RuntimeError(f"Missing keys {sorted(missing)} in {path}")
    out = {k: data[k] for k in data.files}
    if out["flat_features"].ndim != 2 or out["flat_features"].shape[1] != 100:
        raise RuntimeError(f"Expected flat_features [N,100], got {out['flat_features'].shape} in {path}")
    if out["family_scale_tokens"].ndim != 4 or out["family_scale_tokens"].shape[1:] != (4, 5, 7):
        raise RuntimeError(f"Expected family_scale_tokens [N,4,5,7], got {out['family_scale_tokens'].shape} in {path}")
    if out["token_matrix"].ndim != 3 or out["token_matrix"].shape[1:] != (20, 7):
        raise RuntimeError(f"Expected token_matrix [N,20,7], got {out['token_matrix'].shape} in {path}")
    if out["token_slot_mask"].shape != (20, 7):
        raise RuntimeError(f"Expected token_slot_mask [20,7], got {out['token_slot_mask'].shape} in {path}")
    if "expression_v2_matrix" in out and out["expression_v2_matrix"].ndim != 3:
        raise RuntimeError(f"Expected expression_v2_matrix [N,20,5], got {out['expression_v2_matrix'].shape} in {path}")
    if "expression_v2_flat" in out and out["expression_v2_flat"].ndim != 2:
        raise RuntimeError(f"Expected expression_v2_flat [N,100], got {out['expression_v2_flat'].shape} in {path}")
    return out


def take_first(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 0:
        raise ValueError("n must be positive")
    return x[: min(len(x), n)].copy()


def save_flat_outputs(base: Path, flat_features: np.ndarray) -> Dict[str, str]:
    npy_path = base.with_suffix(".npy")
    csv_path = base.with_suffix(".csv")
    np.save(npy_path, flat_features.astype(np.float32))
    pd.DataFrame(flat_features.astype(np.float32)).to_csv(csv_path, header=False, index=False)
    return {"npy": str(npy_path), "csv": str(csv_path)}


def save_structured_output(path: Path, payload: Dict[str, np.ndarray]) -> str:
    np.savez_compressed(path, **payload)
    return str(path)


def attach_optional_payload(src: Dict[str, np.ndarray], n_rows: int, payload: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    for key in ROW_OPTIONAL_KEYS:
        if key in src:
            payload[key] = take_first(src[key], n_rows).copy()
    for key in STATIC_OPTIONAL_KEYS:
        if key in src:
            payload[key] = src[key].copy()
    return payload


def stats_flat(x: np.ndarray) -> Dict[str, float]:
    return {
        "rows": int(x.shape[0]),
        "dim": int(x.shape[1]),
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def resolve_expression_matrix(
    src: Dict[str, np.ndarray],
    payload: Dict[str, np.ndarray],
    n_rows: int,
    version: str,
) -> tuple[np.ndarray, str, list[str], Dict[str, list[int]]]:
    if version == "v3":
        channel_names = list(EXPRESSION_V3_CHANNEL_NAMES)
        if "token_matrix_v3" in src:
            return take_first(src["token_matrix_v3"], n_rows).astype(np.float32), "token_matrix_v3", channel_names, {}
        if "expression_v3_matrix" in src:
            return take_first(src["expression_v3_matrix"], n_rows).astype(np.float32), "expression_v3_matrix", channel_names, {}
        return compute_expression_v3(payload["family_scale_tokens"]), "computed_now", channel_names, {}

    if version == EXPRESSION_V4A_HH_STABILIZED_NAME:
        channel_names = list(EXPRESSION_V4A_HH_STABILIZED_CHANNEL_NAMES)
        version_meta = {
            "mask_families": list(EXPRESSION_V4A_HH_STABILIZED_MASK_FAMILIES),
            "mask_channels": list(EXPRESSION_V4A_HH_STABILIZED_MASK_CHANNELS),
        }
        if "token_matrix_v4a_hh_stabilized" in src:
            return (
                take_first(src["token_matrix_v4a_hh_stabilized"], n_rows).astype(np.float32),
                "token_matrix_v4a_hh_stabilized",
                channel_names,
                version_meta,
            )
        if "expression_v4a_hh_stabilized_matrix" in src:
            return (
                take_first(src["expression_v4a_hh_stabilized_matrix"], n_rows).astype(np.float32),
                "expression_v4a_hh_stabilized_matrix",
                channel_names,
                version_meta,
            )
        return (
            compute_expression_v4a_hh_stabilized(payload["family_scale_tokens"]),
            "computed_now",
            channel_names,
            version_meta,
        )

    raise ValueError(f"Unsupported expression version: {version}")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Prepare cross-capture structured frontend sources from Frontend-F2 caches.")
    ap.add_argument("--run-tag", default=f"frontend_f2_crosscapture_stage1_{today}")
    ap.add_argument("--expression-version", default="v3", choices=EXPRESSION_VERSION_CHOICES)
    ap.add_argument("--id-structured-npz", type=Path, required=True)
    ap.add_argument("--ood-structured-npz", type=Path, required=True)
    ap.add_argument("--schema-json", type=Path, required=True)
    ap.add_argument("--id-max-rows", type=int, default=50000)
    ap.add_argument("--ood-max-rows", type=int, default=20000)
    args = ap.parse_args()

    run_dir = ROOT_DIR / "runs" / args.run_tag
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    id_src = load_structured_npz(args.id_structured_npz)
    ood_src = load_structured_npz(args.ood_structured_npz)
    schema = json.loads(args.schema_json.read_text(encoding="utf-8-sig"))

    for key in ["token_slot_mask", "token_family_id", "token_scale_id"]:
        if not np.array_equal(id_src[key], ood_src[key]):
            raise RuntimeError(f"Structured metadata mismatch for key={key}")
    for key in STATIC_OPTIONAL_KEYS:
        if key in id_src or key in ood_src:
            if key not in id_src or key not in ood_src:
                raise RuntimeError(f"Optional key presence mismatch for key={key}")
            if not np.array_equal(id_src[key], ood_src[key]):
                raise RuntimeError(f"Structured metadata mismatch for optional key={key}")

    id_n = min(len(id_src["flat_features"]), args.id_max_rows)
    ood_n = min(len(ood_src["flat_features"]), args.ood_max_rows)

    id_payload = {
        "flat_features": take_first(id_src["flat_features"], id_n).astype(np.float32),
        "family_scale_tokens": take_first(id_src["family_scale_tokens"], id_n).astype(np.float32),
        "token_matrix": take_first(id_src["token_matrix"], id_n).astype(np.float32),
        "token_slot_mask": id_src["token_slot_mask"].astype(np.float32),
        "token_family_id": id_src["token_family_id"].astype(np.int64),
        "token_scale_id": id_src["token_scale_id"].astype(np.int64),
    }
    id_payload = attach_optional_payload(id_src, id_n, id_payload)
    ood_payload = {
        "flat_features": take_first(ood_src["flat_features"], ood_n).astype(np.float32),
        "family_scale_tokens": take_first(ood_src["family_scale_tokens"], ood_n).astype(np.float32),
        "token_matrix": take_first(ood_src["token_matrix"], ood_n).astype(np.float32),
        "token_slot_mask": ood_src["token_slot_mask"].astype(np.float32),
        "token_family_id": ood_src["token_family_id"].astype(np.int64),
        "token_scale_id": ood_src["token_scale_id"].astype(np.int64),
    }
    ood_payload = attach_optional_payload(ood_src, ood_n, ood_payload)

    id_structured_path = data_dir / "id_source_structured.npz"
    ood_structured_path = data_dir / "ood_benign_source_structured.npz"
    save_structured_output(id_structured_path, id_payload)
    save_structured_output(ood_structured_path, ood_payload)
    id_flat_paths = save_flat_outputs(data_dir / "id_source_100", id_payload["flat_features"])
    ood_flat_paths = save_flat_outputs(data_dir / "ood_benign_source_100", ood_payload["flat_features"])
    id_expression_v2_paths = None
    ood_expression_v2_paths = None
    if "expression_v2_flat" in id_payload:
        id_expression_v2_paths = save_flat_outputs(data_dir / "id_source_expression_v2_100", id_payload["expression_v2_flat"])
    if "expression_v2_flat" in ood_payload:
        ood_expression_v2_paths = save_flat_outputs(data_dir / "ood_benign_source_expression_v2_100", ood_payload["expression_v2_flat"])

    version = args.expression_version
    id_expr, id_expr_source, channel_names, version_meta = resolve_expression_matrix(id_src, id_payload, id_n, version)
    ood_expr, ood_expr_source, _, _ = resolve_expression_matrix(ood_src, ood_payload, ood_n, version)
    expr_matrix_name = f"expression_{version}_matrix"
    expr_flat_name = f"expression_{version}_160"
    id_expr_matrix_path = data_dir / f"id_source_{expr_matrix_name}.npy"
    ood_expr_matrix_path = data_dir / f"ood_benign_source_{expr_matrix_name}.npy"
    id_expr_flat_path = data_dir / f"id_source_{expr_flat_name}.npy"
    ood_expr_flat_path = data_dir / f"ood_benign_source_{expr_flat_name}.npy"
    np.save(id_expr_flat_path, id_expr.reshape(len(id_expr), -1).astype(np.float32))
    np.save(ood_expr_flat_path, ood_expr.reshape(len(ood_expr), -1).astype(np.float32))
    np.save(id_expr_matrix_path, id_expr)
    np.save(ood_expr_matrix_path, ood_expr)

    schema_copy = data_dir / "structured_schema.json"
    shutil.copyfile(args.schema_json, schema_copy)

    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "id_structured_npy": str(args.id_structured_npz),
        "ood_structured_npy": str(args.ood_structured_npz),
        "schema_json": str(args.schema_json),
        "expression_version": version,
        "channel_names": channel_names,
        "id_used_rows": int(id_n),
        "ood_used_rows": int(ood_n),
        "id_stats": stats_flat(id_payload["flat_features"]),
        "ood_stats": stats_flat(ood_payload["flat_features"]),
        "expression_selection": {
            "id": id_expr_source,
            "ood": ood_expr_source,
            **version_meta,
        },
        "outputs": {
            "id_structured": str(id_structured_path),
            "ood_structured": str(ood_structured_path),
            "id_flat": id_flat_paths,
            "ood_flat": ood_flat_paths,
            "id_expression_v2_flat": id_expression_v2_paths,
            "ood_expression_v2_flat": ood_expression_v2_paths,
            f"id_expression_{version}_matrix": str(id_expr_matrix_path),
            f"ood_expression_{version}_matrix": str(ood_expr_matrix_path),
            f"id_expression_{version}_160": str(id_expr_flat_path),
            f"ood_expression_{version}_160": str(ood_expr_flat_path),
            "schema_copy": str(schema_copy),
        },
    }
    (run_dir / "frontend_f2_source_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Frontend-F2 Cross-capture Source Prep",
        "",
        f"- Date: {metadata['created_at']}",
        f"- ID structured cache: `{args.id_structured_npz}`",
        f"- OOD structured cache: `{args.ood_structured_npz}`",
        f"- Expression version: `{version}`",
        f"- ID used rows: {id_n}",
        f"- OOD used rows: {ood_n}",
        "",
        "## Outputs",
        f"- ID structured: `{id_structured_path}`",
        f"- OOD structured: `{ood_structured_path}`",
        f"- ID flat csv: `{id_flat_paths['csv']}`",
        f"- OOD flat csv: `{ood_flat_paths['csv']}`",
        f"- ID expression matrix: `{id_expr_matrix_path}`",
        f"- OOD expression matrix: `{ood_expr_matrix_path}`",
    ]
    if id_expression_v2_paths and ood_expression_v2_paths:
        lines.extend(
            [
                f"- ID expression_v2 csv: `{id_expression_v2_paths['csv']}`",
                f"- OOD expression_v2 csv: `{ood_expression_v2_paths['csv']}`",
            ]
        )
    lines.extend(
        [
        f"- Schema copy: `{schema_copy}`",
        ]
    )
    (run_dir / "frontend_f2_source_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[done] frontend-f2 source metadata: {run_dir / 'frontend_f2_source_metadata.json'}")


if __name__ == "__main__":
    main()
