from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from paths import ARTIFACT_RUNS_DIR


OBJECT_SCORE_PREFIX = {
    "dA": "dA",
    "strongest_candidate_transformer_covreg_v2_seed101": "strongest_candidate",
    "ft_transformer_ae": "ft_transformer_ae",
}


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, tuple):
        return [clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [clean(v) for v in obj.tolist()]
    if isinstance(obj, np.generic):
        return clean(obj.item())
    if isinstance(obj, Path):
        return str(obj)
    return obj


def alarm_ratio(scores: np.ndarray, thr: float, op: str) -> float:
    if op == ">":
        return float(np.mean(scores > thr))
    if op == ">=":
        return float(np.mean(scores >= thr))
    raise ValueError(op)


def eval_policy(id_scores: np.ndarray, ood_scores: np.ndarray, attack_scores: np.ndarray, op: str, naive_budget: int) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    fixed_thr = float(np.quantile(id_scores, 0.99))
    rows.append(
        {
            "policy_name": "fixed_id_q99",
            "threshold": fixed_thr,
            "id_alarm_ratio": alarm_ratio(id_scores, fixed_thr, op),
            "ood_alarm_ratio": alarm_ratio(ood_scores, fixed_thr, op),
            "attack_detection": alarm_ratio(attack_scores, fixed_thr, op),
        }
    )
    budget = min(int(naive_budget), len(ood_scores))
    naive_thr = float(np.quantile(ood_scores[:budget], 0.99))
    rows.append(
        {
            "policy_name": f"naive_calibrated_budget{budget}_target1pct",
            "threshold": naive_thr,
            "id_alarm_ratio": alarm_ratio(id_scores, naive_thr, op),
            "ood_alarm_ratio": alarm_ratio(ood_scores, naive_thr, op),
            "attack_detection": alarm_ratio(attack_scores, naive_thr, op),
        }
    )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Threshold/operator sensitivity audit for TON object pre-run outputs.")
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--naive-budget", type=int, default=5000)
    parser.add_argument("--output-run-tag", default=None)
    args = parser.parse_args()

    source_run = ARTIFACT_RUNS_DIR / args.run_tag
    if not source_run.exists():
        raise RuntimeError(f"Run dir not found: {source_run}")
    if not (source_run / "scores").exists():
        raise RuntimeError(f"Missing score directory: {source_run / 'scores'}")

    output_tag = args.output_run_tag or f"second_environment_toniot_threshold_sensitivity_{args.run_tag}"
    out_dir = ARTIFACT_RUNS_DIR / output_tag
    out_dir.mkdir(parents=True, exist_ok=True)

    pol = pd.read_csv(source_run / "object_polarity.csv")
    pol_map = {str(r["object_label"]): int(r["chosen_sign"]) for _, r in pol.iterrows()}

    rows: List[Dict[str, object]] = []
    tie_rows: List[Dict[str, object]] = []
    for obj, prefix in OBJECT_SCORE_PREFIX.items():
        id_raw = np.load(source_run / "scores" / f"{prefix}_id_scores.npy").astype(np.float64)
        ood_raw = np.load(source_run / "scores" / f"{prefix}_ood_scores.npy").astype(np.float64)
        attack_raw = np.load(source_run / "scores" / f"{prefix}_attack_scores.npy").astype(np.float64)

        for orient_name, sign in [("raw_score", 1), ("neg_raw_score", -1)]:
            id_scores = sign * id_raw
            ood_scores = sign * ood_raw
            attack_scores = sign * attack_raw

            fixed_thr = float(np.quantile(id_scores, 0.99))
            tie_rows.append(
                {
                    "object_label": obj,
                    "orientation": orient_name,
                    "threshold_q99": fixed_thr,
                    "id_equal_threshold_ratio": float(np.mean(np.isclose(id_scores, fixed_thr, rtol=0.0, atol=1e-12))),
                    "id_gt_threshold_ratio": float(np.mean(id_scores > fixed_thr)),
                    "id_ge_threshold_ratio": float(np.mean(id_scores >= fixed_thr)),
                    "is_precheck_chosen_orientation": bool(sign == pol_map.get(obj)),
                }
            )

            for op in [">", ">="]:
                for pr in eval_policy(id_scores, ood_scores, attack_scores, op=op, naive_budget=args.naive_budget):
                    rows.append(
                        {
                            "object_label": obj,
                            "orientation": orient_name,
                            "operator": op,
                            "is_precheck_chosen_orientation": bool(sign == pol_map.get(obj)),
                            **pr,
                        }
                    )

    result_df = pd.DataFrame(rows)
    tie_df = pd.DataFrame(tie_rows)
    result_df.to_csv(out_dir / "threshold_sensitivity_results.csv", index=False)
    tie_df.to_csv(out_dir / "threshold_tie_profile.csv", index=False)

    cfg = {
        "stage": "second_environment_toniot_threshold_sensitivity",
        "source_run_tag": args.run_tag,
        "source_run_dir": str(source_run),
        "naive_budget": int(args.naive_budget),
        "objects": list(OBJECT_SCORE_PREFIX.keys()),
        "orientations": ["raw_score", "neg_raw_score"],
        "operators": [">", ">="],
    }
    (out_dir / "config.json").write_text(json.dumps(clean(cfg), indent=2), encoding="utf-8")
    (out_dir / "run_spec.json").write_text(
        json.dumps(
            clean(
                {
                    "stage": "second_environment_toniot_threshold_sensitivity",
                    "goal": "Audit whether fixed/naive detection anomalies are caused by orientation/operator thresholding details.",
                }
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "command.txt").write_text(" ".join(sys.argv) + "\n", encoding="utf-8")

    lines = [
        "# TON Threshold Sensitivity Summary",
        "",
        f"- Source run: `{args.run_tag}`",
        f"- Output run: `{output_tag}`",
        f"- Objects: `{', '.join(OBJECT_SCORE_PREFIX.keys())}`",
        f"- Operators audited: `>`, `>=`",
        "",
        "## Quick Check (FT fixed_id_q99)",
    ]
    ft = result_df[(result_df["object_label"] == "ft_transformer_ae") & (result_df["policy_name"] == "fixed_id_q99")]
    for _, r in ft.sort_values(["orientation", "operator"]).iterrows():
        lines.append(
            f"- `{r['orientation']}` / `{r['operator']}`: "
            f"id={float(r['id_alarm_ratio']):.6f}, ood={float(r['ood_alarm_ratio']):.6f}, attack={float(r['attack_detection']):.6f}, "
            f"chosen={bool(r['is_precheck_chosen_orientation'])}"
        )
    lines += ["", "## FT Tie Profile"]
    ft_tie = tie_df[tie_df["object_label"] == "ft_transformer_ae"].sort_values("orientation")
    for _, r in ft_tie.iterrows():
        lines.append(
            f"- `{r['orientation']}`: eq@q99={float(r['id_equal_threshold_ratio']):.6f}, "
            f"gt@q99={float(r['id_gt_threshold_ratio']):.6f}, ge@q99={float(r['id_ge_threshold_ratio']):.6f}, "
            f"chosen={bool(r['is_precheck_chosen_orientation'])}"
        )
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"source_run": str(source_run), "out_dir": str(out_dir)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
