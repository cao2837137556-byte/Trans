from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
from kitsune_frontend_original_extract import (
    EXPRESSION_V3_CHANNEL_NAMES,
    EXPRESSION_V4A_HH_STABILIZED_CHANNEL_NAMES,
    EXPRESSION_V4A_HH_STABILIZED_MASK_CHANNELS,
    EXPRESSION_V4A_HH_STABILIZED_MASK_FAMILIES,
    EXPRESSION_V4A_HH_STABILIZED_NAME,
    EXPRESSION_V4B_HH_SOFT_STABILIZED_CHANNEL_NAMES,
    EXPRESSION_V4B_HH_SOFT_STABILIZED_CLIP_CONFIG,
    EXPRESSION_V4B_HH_SOFT_STABILIZED_NAME,
    EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_CHANNELS,
    EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_FAMILIES,
    EXPRESSION_SOURCE_RICH_V1_CHANNEL_NAMES,
    EXPRESSION_SOURCE_RICH_V1_CLIP_RATIO,
    EXPRESSION_SOURCE_RICH_V1_CLIP_RAW_REL,
    EXPRESSION_SOURCE_RICH_V1_NAME,
    EXPRESSION_V5_COMPACT_V1_CHANNEL_NAMES,
    EXPRESSION_V5_COMPACT_V1_DERIVED_FROM,
    EXPRESSION_V5_COMPACT_V1_NAME,
    EXPRESSION_V5_COMPACT_V1_SELECTED_CHANNELS,
    EXPRESSION_V6_INPUT_ALIGNED_V1_CHANNEL_NAMES,
    EXPRESSION_V6_INPUT_ALIGNED_V1_DERIVED_FROM,
    EXPRESSION_V6_INPUT_ALIGNED_V1_NAME,
    EXPRESSION_V6_INPUT_ALIGNED_V1_SELECTED_CHANNELS,
    EXPRESSION_V6_INPUT_ALIGNED_V1_SHORT_SCALE_IDS,
    EXPRESSION_V6_INPUT_ALIGNED_V1_SOFT_FAMILIES,
    compute_expression_channel_audit,
    compute_expression_source_rich_v1,
    compute_expression_v6_input_aligned_v1,
    compute_expression_v5_compact_v1,
    compute_expression_v3,
    compute_expression_v4a_hh_stabilized,
    compute_expression_v4b_hh_soft_stabilized,
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
EXPRESSION_VERSION_CHOICES = [
    "v3",
    EXPRESSION_V4A_HH_STABILIZED_NAME,
    EXPRESSION_V4B_HH_SOFT_STABILIZED_NAME,
    EXPRESSION_SOURCE_RICH_V1_NAME,
    EXPRESSION_V5_COMPACT_V1_NAME,
    EXPRESSION_V6_INPUT_ALIGNED_V1_NAME,
]


def load_structured_npz(path: Path) -> Dict[str, np.ndarray]:
    data = np.load(path)
    keys = set(data.files)
    missing = REQUIRED_KEYS - keys
    if missing:
        raise RuntimeError(f"Missing keys {sorted(missing)} in {path}")
    return {k: data[k] for k in data.files}


def take_first(x: np.ndarray, n: int) -> np.ndarray:
    return x[: min(len(x), n)].copy()


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

    if version == EXPRESSION_V4B_HH_SOFT_STABILIZED_NAME:
        channel_names = list(EXPRESSION_V4B_HH_SOFT_STABILIZED_CHANNEL_NAMES)
        version_meta = {
            "soft_families": list(EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_FAMILIES),
            "soft_channels": list(EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_CHANNELS),
            "clip_config": EXPRESSION_V4B_HH_SOFT_STABILIZED_CLIP_CONFIG,
        }
        if "token_matrix_v4b_hh_soft_stabilized" in src:
            return (
                take_first(src["token_matrix_v4b_hh_soft_stabilized"], n_rows).astype(np.float32),
                "token_matrix_v4b_hh_soft_stabilized",
                channel_names,
                version_meta,
            )
        if "expression_v4b_hh_soft_stabilized_matrix" in src:
            return (
                take_first(src["expression_v4b_hh_soft_stabilized_matrix"], n_rows).astype(np.float32),
                "expression_v4b_hh_soft_stabilized_matrix",
                channel_names,
                version_meta,
            )
        return (
            compute_expression_v4b_hh_soft_stabilized(payload["family_scale_tokens"]),
            "computed_now",
            channel_names,
            version_meta,
        )

    if version == EXPRESSION_SOURCE_RICH_V1_NAME:
        channel_names = list(EXPRESSION_SOURCE_RICH_V1_CHANNEL_NAMES)
        version_meta = {
            "clip_raw_rel": EXPRESSION_SOURCE_RICH_V1_CLIP_RAW_REL,
            "clip_ratio": EXPRESSION_SOURCE_RICH_V1_CLIP_RATIO,
        }
        if "token_matrix_source_rich_v1" in src:
            return (
                take_first(src["token_matrix_source_rich_v1"], n_rows).astype(np.float32),
                "token_matrix_source_rich_v1",
                channel_names,
                version_meta,
            )
        if "expression_source_rich_v1_matrix" in src:
            return (
                take_first(src["expression_source_rich_v1_matrix"], n_rows).astype(np.float32),
                "expression_source_rich_v1_matrix",
                channel_names,
                version_meta,
            )
        return (
            compute_expression_source_rich_v1(payload["family_scale_tokens"]),
            "computed_now",
            channel_names,
            version_meta,
        )

    if version == EXPRESSION_V5_COMPACT_V1_NAME:
        channel_names = list(EXPRESSION_V5_COMPACT_V1_CHANNEL_NAMES)
        version_meta = {
            "derived_from": EXPRESSION_V5_COMPACT_V1_DERIVED_FROM,
            "selected_channels": list(EXPRESSION_V5_COMPACT_V1_SELECTED_CHANNELS),
        }
        if "token_matrix_v5_compact_v1" in src:
            return (
                take_first(src["token_matrix_v5_compact_v1"], n_rows).astype(np.float32),
                "token_matrix_v5_compact_v1",
                channel_names,
                version_meta,
            )
        if "expression_v5_compact_v1_matrix" in src:
            return (
                take_first(src["expression_v5_compact_v1_matrix"], n_rows).astype(np.float32),
                "expression_v5_compact_v1_matrix",
                channel_names,
                version_meta,
            )
        return (
            compute_expression_v5_compact_v1(payload["family_scale_tokens"]),
            "computed_now",
            channel_names,
            version_meta,
        )

    if version == EXPRESSION_V6_INPUT_ALIGNED_V1_NAME:
        channel_names = list(EXPRESSION_V6_INPUT_ALIGNED_V1_CHANNEL_NAMES)
        version_meta = {
            "derived_from": EXPRESSION_V6_INPUT_ALIGNED_V1_DERIVED_FROM,
            "selected_channels": list(EXPRESSION_V6_INPUT_ALIGNED_V1_SELECTED_CHANNELS),
            "short_scale_ids": list(EXPRESSION_V6_INPUT_ALIGNED_V1_SHORT_SCALE_IDS),
            "soft_families": list(EXPRESSION_V6_INPUT_ALIGNED_V1_SOFT_FAMILIES),
        }
        if "token_matrix_v6_input_aligned_v1" in src:
            return (
                take_first(src["token_matrix_v6_input_aligned_v1"], n_rows).astype(np.float32),
                "token_matrix_v6_input_aligned_v1",
                channel_names,
                version_meta,
            )
        if "expression_v6_input_aligned_v1_matrix" in src:
            return (
                take_first(src["expression_v6_input_aligned_v1_matrix"], n_rows).astype(np.float32),
                "expression_v6_input_aligned_v1_matrix",
                channel_names,
                version_meta,
            )
        return (
            compute_expression_v6_input_aligned_v1(payload["family_scale_tokens"]),
            "computed_now",
            channel_names,
            version_meta,
        )

    raise ValueError(f"Unsupported expression version: {version}")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Prepare Frontend-F2 structured attack source aligned with stage2 manifest.")
    ap.add_argument("--run-tag", default=f"frontend_f2_attack_source_{today}")
    ap.add_argument("--expression-version", default="v3", choices=EXPRESSION_VERSION_CHOICES)
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
    payload = attach_optional_payload(attack, use_first_n, payload)

    structured_path = data_dir / "attack_source_structured.npz"
    np.savez_compressed(structured_path, **payload)
    flat_npy = data_dir / "attack_source_100.npy"
    flat_csv = data_dir / "attack_source_100.csv"
    np.save(flat_npy, payload["flat_features"])
    pd.DataFrame(payload["flat_features"]).to_csv(flat_csv, header=False, index=False)
    expression_v2_npy = None
    expression_v2_csv = None
    if "expression_v2_flat" in payload:
        expression_v2_npy = data_dir / "attack_source_expression_v2_100.npy"
        expression_v2_csv = data_dir / "attack_source_expression_v2_100.csv"
        np.save(expression_v2_npy, payload["expression_v2_flat"])
        pd.DataFrame(payload["expression_v2_flat"]).to_csv(expression_v2_csv, header=False, index=False)

    version = args.expression_version
    atk_expr, attack_expr_source, channel_names, version_meta = resolve_expression_matrix(
        attack, payload, use_first_n, version
    )
    expr_matrix_name = f"expression_{version}_matrix"
    expr_flat_dim = int(atk_expr.shape[1] * atk_expr.shape[2])
    expr_flat_name = f"expression_{version}_{expr_flat_dim}"
    atk_expr_flat_path = data_dir / f"attack_source_{expr_flat_name}.npy"
    atk_expr_matrix_path = data_dir / f"attack_source_{expr_matrix_name}.npy"
    np.save(atk_expr_flat_path, atk_expr.reshape(len(atk_expr), -1).astype(np.float32))
    np.save(atk_expr_matrix_path, atk_expr)
    expression_audit_path = None
    if version == EXPRESSION_V4B_HH_SOFT_STABILIZED_NAME:
        expression_audit_path = run_dir / "expression_v4b_audit.json"
        audit_payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "expression_version": version,
            "attack": {
                "all_tokens": compute_expression_channel_audit(atk_expr, channel_names),
                "hh_hh_jit_tokens": compute_expression_channel_audit(atk_expr[:, 5:15, :], channel_names),
            },
        }
        expression_audit_path.write_text(
            json.dumps(audit_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    elif version == EXPRESSION_SOURCE_RICH_V1_NAME:
        expression_audit_path = run_dir / "source_rich_audit.json"
        audit_payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "expression_version": version,
            "attack": {
                "all_tokens": compute_expression_channel_audit(atk_expr, channel_names),
                "hh_hh_jit_tokens": compute_expression_channel_audit(atk_expr[:, 5:15, :], channel_names),
            },
        }
        expression_audit_path.write_text(
            json.dumps(audit_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    elif version == EXPRESSION_V6_INPUT_ALIGNED_V1_NAME:
        expression_audit_path = run_dir / "expression_v6_input_aligned_audit.json"
        audit_payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "expression_version": version,
            "attack": {
                "all_tokens": compute_expression_channel_audit(atk_expr, channel_names),
                "hh_hh_jit_tokens": compute_expression_channel_audit(atk_expr[:, 3:9, :], channel_names),
            },
        }
        expression_audit_path.write_text(
            json.dumps(audit_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "attack_structured_npy": str(args.attack_structured_npz),
        "attack_manifest_stage2": str(args.attack_manifest_stage2),
        "expression_version": version,
        "channel_names": channel_names,
        "use_first_n": use_first_n,
        "attack_stats": stats_flat(payload["flat_features"]),
        "expression_selection": {
            "attack": attack_expr_source,
            **version_meta,
        },
        "expression_audit": str(expression_audit_path) if expression_audit_path else None,
        "outputs": {
            "attack_structured": str(structured_path),
            "attack_flat_npy": str(flat_npy),
            "attack_flat_csv": str(flat_csv),
            "attack_expression_v2_npy": str(expression_v2_npy) if expression_v2_npy else None,
            "attack_expression_v2_csv": str(expression_v2_csv) if expression_v2_csv else None,
            f"attack_expression_{version}_matrix": str(atk_expr_matrix_path),
            f"attack_expression_{version}_{expr_flat_dim}": str(atk_expr_flat_path),
        },
    }
    (run_dir / "frontend_f2_attack_source_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Frontend-F2 Attack Source Prep",
        "",
        f"- Date: {metadata['created_at']}",
        f"- Attack structured cache: `{args.attack_structured_npz}`",
        f"- Stage2 manifest: `{args.attack_manifest_stage2}`",
        f"- Expression version: `{version}`",
        f"- use_first_n: {use_first_n}",
        "",
        "## Outputs",
        f"- Attack structured: `{structured_path}`",
        f"- Attack flat csv: `{flat_csv}`",
        f"- Attack expression matrix: `{atk_expr_matrix_path}`",
    ]
    if expression_v2_csv is not None:
        lines.append(f"- Attack expression_v2 csv: `{expression_v2_csv}`")
    if expression_audit_path is not None:
        lines.append(f"- Expression audit: `{expression_audit_path}`")
    (run_dir / "frontend_f2_attack_source_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[done] frontend-f2 attack metadata: {run_dir / 'frontend_f2_attack_source_metadata.json'}")


if __name__ == "__main__":
    main()
