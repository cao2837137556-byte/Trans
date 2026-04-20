from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import frontend100_negative_recipe_rescoring as resc
from kitsune_frontend_original_extract import (
    EXPRESSION_SOURCE_RICH_V1_CHANNEL_NAMES,
    EXPRESSION_SOURCE_RICH_V1_NAME,
    compute_expression_channel_audit,
)

FAMILY_NAMES = ["MI_dir", "HH", "HH_jit", "HpHp"]
SCALE_NAMES = ["5s", "3s", "1s", "0.1s", "0.01s"]
TOKEN_FAMILY_ID = np.repeat(np.arange(4), 5).astype(np.int64)
TOKEN_SCALE_ID = np.tile(np.arange(5), 4).astype(np.int64)


def load_source_rich_matrix(path: Path) -> np.ndarray:
    arr = np.load(path)
    if arr.ndim != 3 or arr.shape[1] != 20:
        raise RuntimeError(f"Expected source_rich matrix [N,20,C], got {arr.shape} from {path}")
    if arr.shape[2] != len(EXPRESSION_SOURCE_RICH_V1_CHANNEL_NAMES):
        raise RuntimeError(
            f"Channel dim mismatch: expected {len(EXPRESSION_SOURCE_RICH_V1_CHANNEL_NAMES)}, got {arr.shape[2]} from {path}"
        )
    return arr.astype(np.float64)


def build_channel_audit(id_mat: np.ndarray, ood_mat: np.ndarray, atk_mat: np.ndarray) -> pd.DataFrame:
    eps = 1e-6
    rows = []
    for token_id in range(20):
        family_id = int(TOKEN_FAMILY_ID[token_id])
        scale_id = int(TOKEN_SCALE_ID[token_id])
        family = FAMILY_NAMES[family_id]
        scale = SCALE_NAMES[scale_id]

        for ch_id, ch_name in enumerate(EXPRESSION_SOURCE_RICH_V1_CHANNEL_NAMES):
            id_vals = id_mat[:, token_id, ch_id]
            ood_vals = ood_mat[:, token_id, ch_id]
            atk_vals = atk_mat[:, token_id, ch_id]

            id_mean = float(np.mean(id_vals))
            id_std = float(np.std(id_vals))
            id_p95 = float(np.percentile(id_vals, 95))
            id_p99 = float(np.percentile(id_vals, 99))
            ood_mean = float(np.mean(ood_vals))
            ood_std = float(np.std(ood_vals))
            ood_p95 = float(np.percentile(ood_vals, 95))
            ood_p99 = float(np.percentile(ood_vals, 99))
            atk_mean = float(np.mean(atk_vals))
            atk_std = float(np.std(atk_vals))
            atk_p50 = float(np.percentile(atk_vals, 50))
            atk_p95 = float(np.percentile(atk_vals, 95))

            ood_id_shift_score = float(np.log1p(abs(ood_mean - id_mean) / (id_std + eps)))
            attack_id_separation_score = float(np.log1p(abs(atk_mean - id_mean) / (id_std + eps)))
            ood_tail_overlap_ratio = ood_p99 / (atk_p50 + eps)
            ood_tail_overlap_score = float(np.log1p(max(ood_tail_overlap_ratio, 0.0)))
            ood_tail_excess = max(ood_tail_overlap_score - np.log(2.0), 0.0)
            health_score = attack_id_separation_score / (1.0 + ood_id_shift_score + ood_tail_excess)
            problem_score = ood_id_shift_score + 1.5 * ood_tail_excess - 0.5 * attack_id_separation_score

            rows.append(
                {
                    "token_id": token_id,
                    "family": family,
                    "scale": scale,
                    "channel": ch_name,
                    "id_mean": id_mean,
                    "id_std": id_std,
                    "id_p95": id_p95,
                    "id_p99": id_p99,
                    "ood_mean": ood_mean,
                    "ood_std": ood_std,
                    "ood_p95": ood_p95,
                    "ood_p99": ood_p99,
                    "attack_mean": atk_mean,
                    "attack_std": atk_std,
                    "attack_p50": atk_p50,
                    "attack_p95": atk_p95,
                    "ood_id_shift_score": float(ood_id_shift_score),
                    "attack_id_separation_score": float(attack_id_separation_score),
                    "ood_tail_overlap_score": float(ood_tail_overlap_score),
                    "ood_tail_overlap_ratio": float(ood_tail_overlap_ratio),
                    "ood_tail_excess": float(ood_tail_excess),
                    "health_score": float(health_score),
                    "problem_score": float(problem_score),
                }
            )

    df = pd.DataFrame(rows)
    df["health_rank_desc"] = df["health_score"].rank(ascending=False, method="min").astype(int)
    df["problem_rank_desc"] = df["problem_score"].rank(ascending=False, method="min").astype(int)
    return df.sort_values(["problem_score", "token_id"], ascending=[False, True]).reset_index(drop=True)


def build_family_scale_summary(channel_df: pd.DataFrame) -> pd.DataFrame:
    metric_cols = [
        "ood_id_shift_score",
        "attack_id_separation_score",
        "ood_tail_overlap_score",
        "health_score",
        "problem_score",
    ]

    by_family_channel = (
        channel_df.groupby(["family", "channel"], as_index=False)[metric_cols].mean()
        .assign(group_type="family_channel", group_label=lambda x: x["family"] + "|" + x["channel"])
    )
    by_scale_channel = (
        channel_df.groupby(["scale", "channel"], as_index=False)[metric_cols].mean()
        .assign(group_type="scale_channel", group_label=lambda x: x["scale"] + "|" + x["channel"])
    )
    by_family = (
        channel_df.groupby(["family"], as_index=False)[metric_cols].mean()
        .assign(channel="__all__", scale="__all__", group_type="family", group_label=lambda x: x["family"])
    )
    by_scale = (
        channel_df.groupby(["scale"], as_index=False)[metric_cols].mean()
        .assign(channel="__all__", family="__all__", group_type="scale", group_label=lambda x: x["scale"])
    )
    summary = pd.concat([by_family_channel, by_scale_channel, by_family, by_scale], ignore_index=True, sort=False)
    summary["health_rank_desc"] = summary["health_score"].rank(ascending=False, method="min").astype(int)
    summary["problem_rank_desc"] = summary["problem_score"].rank(ascending=False, method="min").astype(int)
    return summary.sort_values(["group_type", "problem_score"], ascending=[True, False]).reset_index(drop=True)


def build_problem_channels(channel_df: pd.DataFrame) -> pd.DataFrame:
    shift_thr = float(channel_df["ood_id_shift_score"].quantile(0.75))
    sep_thr = float(channel_df["attack_id_separation_score"].quantile(0.35))
    overlap_thr = float(channel_df["ood_tail_overlap_score"].quantile(0.70))

    mask = (
        (channel_df["ood_id_shift_score"] >= shift_thr)
        | (channel_df["ood_tail_overlap_score"] >= overlap_thr)
    ) & (channel_df["attack_id_separation_score"] <= sep_thr)

    out = channel_df.loc[mask].copy()
    if out.empty:
        out = channel_df.head(25).copy()
    return out.sort_values("problem_score", ascending=False).reset_index(drop=True)


def build_recommendation(channel_df: pd.DataFrame, summary_df: pd.DataFrame, out_path: Path) -> dict:
    channel_agg = (
        channel_df.groupby("channel", as_index=False)[
            ["ood_id_shift_score", "attack_id_separation_score", "ood_tail_overlap_score", "health_score", "problem_score"]
        ]
        .mean()
        .sort_values("health_score", ascending=False)
        .reset_index(drop=True)
    )

    problem_q60 = float(channel_agg["problem_score"].quantile(0.60))
    problem_q75 = float(channel_agg["problem_score"].quantile(0.75))
    sep_q40 = float(channel_agg["attack_id_separation_score"].quantile(0.40))

    keep_pool = channel_agg[channel_agg["problem_score"] <= problem_q60]
    if keep_pool.empty:
        keep_pool = channel_agg.copy()
    keep = keep_pool.sort_values(
        ["health_score", "attack_id_separation_score", "problem_score"],
        ascending=[False, False, True],
    ).head(8)

    drop = channel_agg[
        (channel_agg["problem_score"] >= problem_q75)
        & (channel_agg["attack_id_separation_score"] <= sep_q40)
    ].sort_values("problem_score", ascending=False)
    if drop.empty:
        drop = channel_agg.sort_values("problem_score", ascending=False).head(5)
    else:
        drop = drop.head(5)

    drop_set = set(drop["channel"].tolist())
    keep = keep[~keep["channel"].isin(drop_set)].head(8)

    family_focus = (
        summary_df[summary_df["group_type"].eq("family")][
            ["family", "attack_id_separation_score", "ood_id_shift_score", "ood_tail_overlap_score", "health_score", "problem_score"]
        ]
        .sort_values("health_score", ascending=False)
        .reset_index(drop=True)
    )
    scale_focus = (
        summary_df[summary_df["group_type"].eq("scale")][
            ["scale", "attack_id_separation_score", "ood_id_shift_score", "ood_tail_overlap_score", "health_score", "problem_score"]
        ]
        .sort_values("health_score", ascending=False)
        .reset_index(drop=True)
    )

    keep_channels = keep["channel"].tolist()
    drop_channels = drop["channel"].tolist()
    family_order = family_focus["family"].tolist()
    scale_order = scale_focus["scale"].tolist()

    lines = [
        "# Source Rich v1 Recommendation",
        "",
        f"- Expression version: `{EXPRESSION_SOURCE_RICH_V1_NAME}`",
        "- This recommendation is generated from channel-level offline health metrics only (no training).",
        "",
        "## Suggested Keep Channels (v5 compact candidates)",
    ]
    lines.extend([f"- `{ch}`" for ch in keep_channels])
    lines.extend(
        [
            "",
            "## Suggested Downweight/Drop Channels",
        ]
    )
    lines.extend([f"- `{ch}`" for ch in drop_channels])
    lines.extend(
        [
            "",
            "## Family Focus (health high -> low)",
        ]
    )
    lines.extend([f"- `{x}`" for x in family_order])
    lines.extend(
        [
            "",
            "## Scale Focus (health high -> low)",
        ]
    )
    lines.extend([f"- `{x}`" for x in scale_order])
    lines.extend(
        [
            "",
            "## Compact v5 Candidate Table",
            "| channel | keep_rank | health_score | problem_score |",
            "|---|---:|---:|---:|",
        ]
    )
    keep_with_rank = keep.reset_index(drop=True).copy()
    keep_with_rank["keep_rank"] = np.arange(1, len(keep_with_rank) + 1)
    for _, row in keep_with_rank.iterrows():
        lines.append(
            f"| {row['channel']} | {int(row['keep_rank'])} | {row['health_score']:.4f} | {row['problem_score']:.4f} |"
        )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "keep_channels": keep_channels,
        "drop_channels": drop_channels,
        "family_focus_order": family_order,
        "scale_focus_order": scale_order,
    }


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Offline audit for Frontend-F2 source_rich_v1 channels.")
    ap.add_argument("--run-tag", default=f"frontend_f2_source_rich_audit_{today}")
    ap.add_argument(
        "--benign-data-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend_f2_source_rich_crosscapture_stage1_2026-04-20" / "data",
    )
    ap.add_argument(
        "--attack-data-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend_f2_source_rich_attack_source_2026-04-20" / "data",
    )
    ap.add_argument(
        "--stage2-manifest",
        type=Path,
        default=WORKTREE_ROOT.parents[1]
        / "KitNET-py-master"
        / "KitNET-py-master"
        / "runs"
        / "frontend100_joint_eval_stage2_2026-04-01"
        / "attack_manifest_stage2.json",
    )
    args = ap.parse_args()

    run_dir = WORKTREE_ROOT / "runs" / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)

    id_path = args.benign_data_dir / "id_source_expression_source_rich_v1_matrix.npy"
    ood_path = args.benign_data_dir / "ood_benign_source_expression_source_rich_v1_matrix.npy"
    atk_path = args.attack_data_dir / "attack_source_expression_source_rich_v1_matrix.npy"

    id_mat = load_source_rich_matrix(id_path)
    ood_mat = load_source_rich_matrix(ood_path)
    atk_mat = load_source_rich_matrix(atk_path)

    manifest = json.loads(args.stage2_manifest.read_text(encoding="utf-8-sig"))
    stage2_idx = resc.build_stage2_indices(manifest)
    atk_high = atk_mat[np.asarray(stage2_idx["high"], dtype=np.int64)]

    channel_df = build_channel_audit(id_mat, ood_mat, atk_high)
    summary_df = build_family_scale_summary(channel_df)
    problem_df = build_problem_channels(channel_df)

    channel_csv = run_dir / "source_rich_channel_audit.csv"
    summary_csv = run_dir / "source_rich_family_scale_summary.csv"
    problem_csv = run_dir / "source_rich_problem_channels.csv"
    recommend_md = run_dir / "source_rich_recommendation.md"
    summary_md = run_dir / "summary.md"
    audit_json = run_dir / "source_rich_audit.json"

    channel_df.to_csv(channel_csv, index=False)
    summary_df.to_csv(summary_csv, index=False)
    problem_df.to_csv(problem_csv, index=False)
    recommendation_payload = build_recommendation(channel_df, summary_df, recommend_md)

    audit_payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "expression_version": EXPRESSION_SOURCE_RICH_V1_NAME,
        "id_rows": int(id_mat.shape[0]),
        "ood_rows": int(ood_mat.shape[0]),
        "attack_rows": int(atk_mat.shape[0]),
        "attack_high_rows": int(atk_high.shape[0]),
        "id": compute_expression_channel_audit(id_mat, EXPRESSION_SOURCE_RICH_V1_CHANNEL_NAMES),
        "ood_benign": compute_expression_channel_audit(ood_mat, EXPRESSION_SOURCE_RICH_V1_CHANNEL_NAMES),
        "attack_high": compute_expression_channel_audit(atk_high, EXPRESSION_SOURCE_RICH_V1_CHANNEL_NAMES),
        "recommendation": recommendation_payload,
    }
    audit_json.write_text(json.dumps(audit_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    top_problem = problem_df.head(5)[["family", "scale", "channel", "problem_score"]]
    lines = [
        "# Frontend-F2 Source Rich Audit",
        "",
        f"- Date: {audit_payload['created_at']}",
        f"- Expression version: `{EXPRESSION_SOURCE_RICH_V1_NAME}`",
        f"- ID rows: {audit_payload['id_rows']}",
        f"- OOD rows: {audit_payload['ood_rows']}",
        f"- Attack rows: {audit_payload['attack_rows']}",
        f"- Attack high rows: {audit_payload['attack_high_rows']}",
        "",
        "## Outputs",
        f"- Channel audit: `{channel_csv}`",
        f"- Family/scale summary: `{summary_csv}`",
        f"- Problem channels: `{problem_csv}`",
        f"- Recommendation: `{recommend_md}`",
        f"- Numeric audit: `{audit_json}`",
        "",
        "## Top Problem Entries",
        "| family | scale | channel | problem_score |",
        "|---|---|---|---:|",
    ]
    for _, row in top_problem.iterrows():
        lines.append(f"| {row['family']} | {row['scale']} | {row['channel']} | {row['problem_score']:.4f} |")

    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[done] source-rich audit run: {run_dir}")


if __name__ == "__main__":
    main()
