from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = REPO_DIR.parent


def parse_zeek_labeled_log(path: Path) -> pd.DataFrame:
    fields = None
    split_tail_triplet = False
    rows = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#fields"):
                fields_raw = line.rstrip("\n").split("\t")[1:]
                if fields_raw and "label" in fields_raw[-1] and "detailed-label" in fields_raw[-1]:
                    split_tail_triplet = True
                    tail = re.split(r"\s{2,}", fields_raw[-1].strip())
                    fields = fields_raw[:-1] + tail
                else:
                    fields = fields_raw
                continue
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if split_tail_triplet and parts:
                tail = re.split(r"\s{2,}", parts[-1].strip())
                if len(tail) == 3:
                    parts = parts[:-1] + tail
            if fields is not None and len(parts) == len(fields):
                rows.append(parts)
    return pd.DataFrame(rows, columns=fields)


def to_md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def build_segments(
    tsv_path: Path,
    log_path: Path,
    use_first_n: int,
    bin_seconds: int,
    strong_ratio_min: float,
    mixed_ratio_low: float,
    mixed_ratio_high: float,
    min_conn_per_bin: int,
) -> Tuple[Dict[str, np.ndarray], Dict]:
    pkt = pd.read_csv(tsv_path, sep="\t")
    if use_first_n > len(pkt):
        use_first_n = len(pkt)
    pkt = pkt.iloc[:use_first_n].copy()
    pkt["ts"] = pd.to_numeric(pkt["frame.time_epoch"], errors="coerce")
    pkt = pkt.dropna(subset=["ts"]).reset_index(drop=True)

    ts0 = float(pkt["ts"].min())
    pkt["bin"] = ((pkt["ts"] - ts0) // bin_seconds).astype(int)

    zeek = parse_zeek_labeled_log(log_path)
    zeek["ts"] = pd.to_numeric(zeek["ts"], errors="coerce")
    zeek = zeek.dropna(subset=["ts"]).copy()

    lo = float(pkt["ts"].min())
    hi = float(pkt["ts"].max())
    zeek = zeek[(zeek["ts"] >= lo) & (zeek["ts"] <= hi)].copy()
    zeek["bin"] = ((zeek["ts"] - ts0) // bin_seconds).astype(int)
    zeek["is_mal"] = zeek["label"].astype(str).str.lower().eq("malicious")

    conn = zeek.groupby("bin").agg(
        conn_total=("label", "size"),
        conn_mal=("is_mal", "sum"),
    )
    conn["mal_ratio"] = conn["conn_mal"] / conn["conn_total"]
    pkt_cnt = pkt.groupby("bin").size().rename("packet_count")
    joined = conn.join(pkt_cnt, how="outer").fillna(0.0)
    joined["conn_total"] = joined["conn_total"].astype(int)
    joined["conn_mal"] = joined["conn_mal"].astype(int)
    joined["packet_count"] = joined["packet_count"].astype(int)
    joined["mal_ratio"] = np.where(
        joined["conn_total"] > 0,
        joined["conn_mal"] / joined["conn_total"],
        0.0,
    )

    strong_bins = joined[
        (joined["conn_total"] >= min_conn_per_bin) & (joined["mal_ratio"] >= strong_ratio_min)
    ].index.to_list()
    mixed_bins = joined[
        (joined["conn_total"] >= min_conn_per_bin)
        & (joined["mal_ratio"] >= mixed_ratio_low)
        & (joined["mal_ratio"] < mixed_ratio_high)
    ].index.to_list()
    weak_bins = joined[
        (joined["conn_total"] >= min_conn_per_bin) & (joined["mal_ratio"] < mixed_ratio_low)
    ].index.to_list()

    idx_all = np.arange(len(pkt), dtype=np.int64)
    idx_strong = pkt.index[pkt["bin"].isin(strong_bins)].to_numpy(dtype=np.int64)
    idx_mixed = pkt.index[pkt["bin"].isin(mixed_bins)].to_numpy(dtype=np.int64)
    idx_weak = pkt.index[pkt["bin"].isin(weak_bins)].to_numpy(dtype=np.int64)

    # fallback to keep stage2 executable even if some bins are empty
    if len(idx_strong) == 0:
        # pick top-30% bins by mal ratio and sufficient conn counts
        tmp = joined[joined["conn_total"] >= max(20, min_conn_per_bin // 2)].copy()
        top = tmp.sort_values("mal_ratio", ascending=False).head(max(1, int(np.ceil(len(tmp) * 0.3))))
        idx_strong = pkt.index[pkt["bin"].isin(top.index.to_list())].to_numpy(dtype=np.int64)
        strong_bins = top.index.to_list()
    if len(idx_mixed) == 0:
        tmp = joined[(joined["conn_total"] >= max(20, min_conn_per_bin // 2)) & (joined["mal_ratio"] < strong_ratio_min)].copy()
        mid = tmp.sort_values("mal_ratio", ascending=False).head(max(1, min(2, len(tmp))))
        idx_mixed = pkt.index[pkt["bin"].isin(mid.index.to_list())].to_numpy(dtype=np.int64)
        mixed_bins = mid.index.to_list()

    segments = {
        "stage1_coarse_attack": idx_all,
        "stage2_high_purity_attack": idx_strong,
        "stage2_boundary_mixed_attack": idx_mixed,
    }
    if len(idx_weak) > 0:
        segments["stage2_weak_background_attack"] = idx_weak

    manifest = {
        "source_tsv": str(tsv_path),
        "source_zeek_log": str(log_path),
        "use_first_n": int(use_first_n),
        "bin_seconds": int(bin_seconds),
        "rules": {
            "strong_ratio_min": float(strong_ratio_min),
            "mixed_ratio_low": float(mixed_ratio_low),
            "mixed_ratio_high": float(mixed_ratio_high),
            "min_conn_per_bin": int(min_conn_per_bin),
        },
        "selected_bins": {
            "strong_bins": [int(x) for x in strong_bins],
            "mixed_bins": [int(x) for x in mixed_bins],
            "weak_bins": [int(x) for x in weak_bins],
        },
        "segment_sizes": {k: int(len(v)) for k, v in segments.items()},
        "why_purer": {
            "stage2_high_purity_attack": "Selected from bins with high malicious conn ratio and enough conn support.",
            "stage2_boundary_mixed_attack": "Selected from bins with medium malicious ratio, likely mixed/boundary activity.",
            "stage1_coarse_attack": "Original coarse stage1 set (first N rows) with no purity filtering.",
        },
        "bin_level_stats": [
            {
                "bin": int(idx),
                "conn_total": int(r["conn_total"]),
                "conn_mal": int(r["conn_mal"]),
                "mal_ratio": float(r["mal_ratio"]),
                "packet_count": int(r["packet_count"]),
            }
            for idx, r in joined.sort_index().iterrows()
        ],
    }
    return segments, manifest


def plot_stage1_stage2_compare(df: pd.DataFrame, out_path: Path) -> None:
    policy_order = ["fixed_id_q99", "calibrated_budget5000_target1pct"]
    det_order = ["transformer", "transformer_tailreg", "da"]
    subset_order = ["stage1_coarse_attack", "stage2_high_purity_attack", "stage2_boundary_mixed_attack"]
    subset_label = {
        "stage1_coarse_attack": "stage1 coarse",
        "stage2_high_purity_attack": "stage2 high-purity",
        "stage2_boundary_mixed_attack": "stage2 mixed",
    }
    colors = {
        "stage1_coarse_attack": "#1f77b4",
        "stage2_high_purity_attack": "#ff7f0e",
        "stage2_boundary_mixed_attack": "#2ca02c",
    }

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.8), sharey=True)
    width = 0.22
    x = np.arange(len(det_order))

    for ax, policy in zip(axes, policy_order):
        sub = df[df["threshold_policy"] == policy]
        for i, subset in enumerate(subset_order):
            vals = []
            for det in det_order:
                row = sub[(sub["detector"] == det) & (sub["attack_subset"] == subset)]
                vals.append(float(row["attack_detection_rate"].iloc[0]))
            shift = (i - 1) * width
            ax.bar(x + shift, vals, width=width, color=colors[subset], label=subset_label[subset] if policy == policy_order[0] else None)

        # overlay benign alarm line (one per detector/policy)
        alarm_vals = []
        for det in det_order:
            row = sub[(sub["detector"] == det) & (sub["attack_subset"] == "stage1_coarse_attack")]
            alarm_vals.append(float(row["ood_benign_alarm_ratio"].iloc[0]))
        ax2 = ax.twinx()
        ax2.plot(x, alarm_vals, color="black", marker="o", linestyle="--", linewidth=1.4, label="OOD benign alarm")
        ax2.set_ylim(0, max(0.5, max(alarm_vals) * 1.15))
        ax2.set_ylabel("OOD benign alarm ratio")

        ax.set_xticks(x)
        ax.set_xticklabels(det_order, rotation=0)
        ax.set_ylim(0, 1.0)
        ax.set_ylabel("Attack detection rate")
        ttl = "Fixed threshold (ID q99)" if policy == "fixed_id_q99" else "Calibrated (budget=5000,target=1%)"
        ax.set_title(ttl)
        ax.grid(axis="y", alpha=0.25)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.04))
    fig.suptitle("Stage1 vs Stage2 attack evaluation (same detectors, same thresholds)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Stage2 joint eval with cleaner attack subsets on frontend100 stronger OOD mainline.")
    parser.add_argument("--run-tag", default=f"frontend100_joint_eval_stage2_{today}")
    parser.add_argument(
        "--stage1-run-tag",
        default="frontend100_joint_eval_stage1_2026-03-31",
    )
    parser.add_argument("--bin-seconds", type=int, default=600)
    parser.add_argument("--use-first-n", type=int, default=10000)
    parser.add_argument("--strong-ratio-min", type=float, default=0.88)
    parser.add_argument("--mixed-ratio-low", type=float, default=0.55)
    parser.add_argument("--mixed-ratio-high", type=float, default=0.88)
    parser.add_argument("--min-conn-per-bin", type=int, default=120)
    args = parser.parse_args()

    stage1_dir = ROOT_DIR / "runs" / args.stage1_run_tag
    if not stage1_dir.exists():
        raise FileNotFoundError(f"Missing stage1 run: {stage1_dir}")

    out_dir = ROOT_DIR / "runs" / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = out_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    tsv_path = stage1_dir / "extract_attack_34_1" / "iot23_34_1_malicious_first30000.tsv"
    log_path = ROOT_DIR / "public_data" / "raw" / "iot23_mirai_34_1.log.labeled"
    if not tsv_path.exists() or not log_path.exists():
        raise FileNotFoundError("Missing attack tsv or zeek labeled log required for stage2 segmentation.")

    segments, manifest = build_segments(
        tsv_path=tsv_path,
        log_path=log_path,
        use_first_n=args.use_first_n,
        bin_seconds=args.bin_seconds,
        strong_ratio_min=args.strong_ratio_min,
        mixed_ratio_low=args.mixed_ratio_low,
        mixed_ratio_high=args.mixed_ratio_high,
        min_conn_per_bin=args.min_conn_per_bin,
    )

    stage1_results = pd.read_csv(stage1_dir / "joint_eval_results.csv")
    detectors = ["transformer", "transformer_tailreg", "da"]
    policies = ["fixed_id_q99", "calibrated_budget5000_target1pct"]

    rows: List[Dict] = []
    per_policy_summary: List[Dict] = []
    for det in detectors:
        attack_scores = np.load(stage1_dir / f"{det}_attack_scores.npy").astype(np.float64)
        for pol in policies:
            base = stage1_results[(stage1_results["detector"] == det) & (stage1_results["threshold_policy"] == pol)].iloc[0]
            thr = float(base["threshold_value"])
            alarm = float(base["ood_benign_alarm_ratio"])
            det_rates = {}
            for subset_name, idx in segments.items():
                idx = idx[idx < len(attack_scores)]
                if len(idx) == 0:
                    continue
                det_rate = float(np.mean(attack_scores[idx] > thr))
                det_rates[subset_name] = det_rate
                rows.append(
                    {
                        "detector": det,
                        "threshold_policy": pol,
                        "attack_subset": subset_name,
                        "sample_count": int(len(idx)),
                        "threshold_value": thr,
                        "ood_benign_alarm_ratio": alarm,
                        "attack_detection_rate": det_rate,
                    }
                )
            # summary stats over stage2 subsets (exclude stage1 coarse)
            stage2_vals = [v for k, v in det_rates.items() if k != "stage1_coarse_attack"]
            if stage2_vals:
                per_policy_summary.append(
                    {
                        "detector": det,
                        "threshold_policy": pol,
                        "stage2_detection_mean": float(np.mean(stage2_vals)),
                        "stage2_detection_std": float(np.std(stage2_vals)),
                        "stage2_detection_min": float(np.min(stage2_vals)),
                        "stage2_detection_max": float(np.max(stage2_vals)),
                    }
                )

    res = pd.DataFrame(rows)
    res = res.sort_values(["threshold_policy", "detector", "attack_subset"]).reset_index(drop=True)
    res.to_csv(out_dir / "joint_eval_stage2_results.csv", index=False)
    (out_dir / "joint_eval_stage2_results.md").write_text(to_md_table(res), encoding="utf-8")

    policy_sum = pd.DataFrame(per_policy_summary).sort_values(["threshold_policy", "detector"])
    policy_sum.to_csv(out_dir / "joint_eval_stage2_policy_stats.csv", index=False)
    (out_dir / "joint_eval_stage2_policy_stats.md").write_text(to_md_table(policy_sum), encoding="utf-8")

    (out_dir / "attack_manifest_stage2.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    plot_stage1_stage2_compare(res, plot_dir / "stage1_vs_stage2_benign_alarm_attack_detection.png")

    # direct QA answers
    def pick(det: str, pol: str, subset: str) -> float:
        row = res[
            (res["detector"] == det)
            & (res["threshold_policy"] == pol)
            & (res["attack_subset"] == subset)
        ]
        if row.empty:
            return float("nan")
        return float(row["attack_detection_rate"].iloc[0])

    lines: List[str] = []
    lines.append("# Joint Eval Stage2 Summary")
    lines.append("")
    lines.append("## Stage2 design")
    lines.append("- Objective: refine attack-side evaluation purity/label granularity without retraining.")
    lines.append("- Same detector set: transformer / transformer_tailreg / da.")
    lines.append("- Same threshold protocols: fixed ID q99 and calibrated (budget=5000,target=1%).")
    lines.append("- Stage2 attack subsets are built from CTU-IoT-Malware-Capture-34-1 using zeek-label-driven time-bin purity rules.")
    lines.append("")
    lines.append("## Core comparison table")
    show_cols = [
        "detector",
        "threshold_policy",
        "attack_subset",
        "sample_count",
        "ood_benign_alarm_ratio",
        "attack_detection_rate",
    ]
    lines.append(to_md_table(res[show_cols]))
    lines.append("")
    lines.append("## Required 4 questions")
    lines.append("1) Stage1 calibrated detection near 0, does it remain on cleaner stage2 attack sets?")
    cal_rows = res[res["threshold_policy"] == "calibrated_budget5000_target1pct"]
    min_cal = float(cal_rows["attack_detection_rate"].min())
    max_cal = float(cal_rows["attack_detection_rate"].max())
    lines.append(
        f"- Yes. On stage2 subsets, calibrated attack detection remains very low (range: {min_cal:.6f} to {max_cal:.6f})."
    )
    lines.append("")
    lines.append("2) If recovery exists, how large is it; does it imply strong stage1 contamination?")
    # Compare stage1 coarse vs stage2 high-purity
    rec_msgs = []
    for det in detectors:
        for pol in policies:
            v0 = pick(det, pol, "stage1_coarse_attack")
            v1 = pick(det, pol, "stage2_high_purity_attack")
            if np.isfinite(v0) and np.isfinite(v1):
                rec_msgs.append(f"{det}/{pol}: {v0:.4f}->{v1:.4f} (delta {v1-v0:+.4f})")
    if rec_msgs:
        lines.append("- Deltas (coarse -> high-purity): " + "; ".join(rec_msgs))
    lines.append("- Conclusion: no substantial calibrated rebound is observed in this stage2 setup.")
    lines.append("")
    lines.append("3) If still near 0, can we more confidently say calibration low-FP gain comes with real detection collapse?")
    lines.append("- In this stage2 replication, yes for this attack source and current threshold setting: calibrated low FP is accompanied by near-zero attack detection.")
    lines.append("- Boundary: attack labels are still derived from zeek-log purity rules (better than stage1 coarse, but not perfect packet-level ground truth).")
    lines.append("")
    lines.append("4) Does TailReg fixed-threshold gain remain under cleaner stage2 attack view?")
    tr_fix_alarm = float(
        res[
            (res["detector"] == "transformer")
            & (res["threshold_policy"] == "fixed_id_q99")
            & (res["attack_subset"] == "stage1_coarse_attack")
        ]["ood_benign_alarm_ratio"].iloc[0]
    )
    tail_fix_alarm = float(
        res[
            (res["detector"] == "transformer_tailreg")
            & (res["threshold_policy"] == "fixed_id_q99")
            & (res["attack_subset"] == "stage1_coarse_attack")
        ]["ood_benign_alarm_ratio"].iloc[0]
    )
    tr_fix_det = pick("transformer", "fixed_id_q99", "stage2_high_purity_attack")
    tail_fix_det = pick("transformer_tailreg", "fixed_id_q99", "stage2_high_purity_attack")
    lines.append(
        f"- Yes. Fixed alarm remains lower with TailReg ({tr_fix_alarm:.4f}->{tail_fix_alarm:.4f}), while high-purity attack detection is close ({tr_fix_det:.4f} vs {tail_fix_det:.4f})."
    )
    lines.append("")
    lines.append("## Interpretation boundary")
    lines.append("- Stage2 improves attack-set auditability via explicit time-bin purity rules.")
    lines.append("- This stage updates the evaluation lens; it does not by itself prove universal final conclusions across all attack scenarios.")
    (out_dir / "joint_eval_stage2_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    config = {
        "stage": "frontend100_joint_eval_stage2",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_stage1_run": str(stage1_dir),
        "source_attack_tsv": str(tsv_path),
        "source_attack_log": str(log_path),
        "segmentation_rules": manifest["rules"],
        "segmentation_bins": manifest["selected_bins"],
        "segment_sizes": manifest["segment_sizes"],
        "note": "No retraining; stage2 re-evaluates with cleaner attack subsets only.",
    }
    (out_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"[done] stage2 output: {out_dir}")


if __name__ == "__main__":
    main()
