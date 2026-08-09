"""CKBY: DROCC one-shot evaluation on the frozen report pools (seed 27).

Loads the trained model + frozen operating points (OP-1, OP-0.1) and evaluates
the report pools EXACTLY ONCE with the CKBW denominators.  No threshold or
checkpoint choice happens here.  Implements FROZEN prereg sections 4/5/7.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from issue27ckby_drocc_train_local_v1 import MLP

GATE_A_OOD_MACRO_MAX = 0.3027      # FrozenCKBQ 35.27% - 5pp
GATE_A_FUTURE_RECALL_MIN = 0.8483  # C1 86.834% - 2pp

ATTACK_ROLES = ["future_query", "same_file_query", "sealed_final_attack", "support_val"]
OOD_POOLS = [
    ("iotsim-ip-camera-street", "sealed_final_ood", 3_000),
    ("iotsim-predictive-maintenance", "aux_report", 9_000),
    ("iotsim-stream-consumer", "ood_stress", 3_000),
    ("iotsim-hydraulic-system", "ood_val", 3_000),
]
COMPARISON_ARMS = ["M0-C1", "M1-FrozenCKBQ", "M7-TabM-TailMargin-DualControl"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--record-table", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--ckbw-all-metrics", type=Path, required=True)
    parser.add_argument("--ckbw-strict-summary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with open(args.run_spec) as handle:
        run_spec = json.load(handle)
    mean = None  # standardization recomputed identically from the snapshot
    with np.load(Path(args.snapshot), allow_pickle=False) as snap:
        uids = snap["uid"].astype(str)
        x_all = snap["x"]
        label = snap["label"]
        global_pool = snap["global_pool"].astype(str)
    fit_mask = (global_pool == "fit") & (label == 0)
    fit_x = x_all[fit_mask].astype(np.float32)
    mean = fit_x.mean(axis=0)
    std = fit_x.std(axis=0) + 1e-4
    if hashlib.sha256(np.ascontiguousarray(mean).tobytes()).hexdigest() != run_spec[
        "standardization"
    ]["mean_sha256"]:
        raise RuntimeError("standardization statistics drift vs training run_spec")

    model = MLP()
    model.load_state_dict(torch.load(args.model, map_location="cpu"))
    model.eval()
    with torch.no_grad():
        scores = torch.squeeze(
            model(torch.from_numpy(((x_all - mean) / std).astype(np.float32))), dim=1
        ).numpy().astype(np.float64)
    if not np.isfinite(scores).all():
        raise RuntimeError("nonfinite report score")
    score_of = dict(zip(uids.tolist(), scores.tolist()))

    table = pd.read_csv(args.record_table)
    table["drocc_score"] = table["uid"].astype(str).map(score_of)
    if table["drocc_score"].isna().any():
        raise RuntimeError("record table uid missing from snapshot scores")

    thresholds = {
        "OP-1": float(run_spec["operating_points"]["op1_percentile_1pct"]),
        "OP-0.1": float(run_spec["operating_points"]["op01_percentile_0p1pct"]),
    }

    pool_rows = []
    attack_frames = {}
    # --- Attack recall pools (GLOBAL slice, label==1).
    global_table = table[table["held_value"] == "GLOBAL_ATTACK_PRESERVATION"]
    for role in ATTACK_ROLES:
        frame = global_table[(global_table["role"] == role)]
        frame = frame[frame["label_metric_only"] == 1]
        attack_frames[role] = frame
        for op, thr in thresholds.items():
            recall = float((frame["drocc_score"] < thr).mean())
            pool_rows.append(
                {"pool": role, "kind": "attack_recall", "op": op,
                 "rows": int(len(frame)), "rate": recall}
            )
    # --- 4 benign OOD pools (held slices, label==0).
    ood_rates = {op: [] for op in thresholds}
    for held, role, expected in OOD_POOLS:
        frame = table[(table["held_value"] == held) & (table["role"] == role)]
        frame = frame[frame["label_metric_only"] == 0]
        if len(frame) != expected:
            raise RuntimeError(f"OOD pool cardinality drift: {held}/{role}: {len(frame)}")
        for op, thr in thresholds.items():
            rate = float((frame["drocc_score"] < thr).mean())
            ood_rates[op].append(rate)
            pool_rows.append(
                {"pool": f"{held}/{role}", "kind": "benign_ood_hard_rate",
                 "op": op, "rows": int(len(frame)), "rate": rate}
            )
    for op in thresholds:
        macro = float(np.mean(ood_rates[op]))
        pool_rows.append({"pool": "OOD_MACRO_4POOL", "kind": "benign_ood_macro",
                          "op": op, "rows": 18_000, "rate": macro})

    # --- Per-family attack safety (GLOBAL report attack rows).
    family_rows = []
    report_attack = pd.concat(
        [attack_frames[r] for r in ["future_query", "same_file_query", "sealed_final_attack"]]
    )
    for family in sorted(report_attack["attack_family"].unique()):
        frame = report_attack[report_attack["attack_family"] == family]
        for op, thr in thresholds.items():
            family_rows.append(
                {"attack_family": family, "op": op, "rows": int(len(frame)),
                 "recall": float((frame["drocc_score"] < thr).mean())}
            )
    support = attack_frames["support_val"]
    for op, thr in thresholds.items():
        family_rows.append(
            {"attack_family": "SUPPORT_VAL_69_REPORT_ONLY", "op": op,
             "rows": int(len(support)),
             "recall": float((support["drocc_score"] < thr).mean())}
        )

    # --- Same-denominator comparison vs frozen CKBW arms.
    ckbw_all = pd.read_csv(args.ckbw_all_metrics)
    ckbw_strict = pd.read_csv(args.ckbw_strict_summary)
    comparison = []
    c1_future = ckbw_all[
        (ckbw_all["candidate"] == "M0-C1")
        & (ckbw_all["role"] == "future_query")
        & (ckbw_all["metric"] == "attack_hard_recall")
    ]["hard_rate"].iloc[0]
    for arm in COMPARISON_ARMS:
        future = ckbw_all[
            (ckbw_all["candidate"] == arm)
            & (ckbw_all["role"] == "future_query")
            & (ckbw_all["metric"] == "attack_hard_recall")
        ]["hard_rate"].iloc[0]
        ood = ckbw_strict[
            (ckbw_strict["candidate"] == arm)
            & (ckbw_strict["metric"] == "benign_ood_hard_rate")
        ]["hard_rate"]
        comparison.append(
            {"arm": arm, "future_attack_recall": float(future),
             "ood_macro_4pool": float(ood.mean())}
        )
    for op in thresholds:
        future_recall = [
            r["rate"] for r in pool_rows
            if r["pool"] == "future_query" and r["op"] == op
        ][0]
        macro = [
            r["rate"] for r in pool_rows
            if r["pool"] == "OOD_MACRO_4POOL" and r["op"] == op
        ][0]
        comparison.append(
            {"arm": f"CKBY-DROCC-{op}", "future_attack_recall": float(future_recall),
             "ood_macro_4pool": float(macro)}
        )

    # --- Gate A on the PRIMARY operating point OP-1.
    op1_future = [
        r["rate"] for r in pool_rows if r["pool"] == "future_query" and r["op"] == "OP-1"
    ][0]
    op1_macro = [
        r["rate"] for r in pool_rows if r["pool"] == "OOD_MACRO_4POOL" and r["op"] == "OP-1"
    ][0]
    gate_a = {
        "op1_future_attack_recall": op1_future,
        "op1_ood_macro_4pool": op1_macro,
        "gate_ood_macro_max": GATE_A_OOD_MACRO_MAX,
        "gate_future_recall_min": GATE_A_FUTURE_RECALL_MIN,
        "ood_leg_pass": bool(op1_macro <= GATE_A_OOD_MACRO_MAX),
        "attack_leg_pass": bool(op1_future >= GATE_A_FUTURE_RECALL_MIN),
    }
    gate_a["gate_a_pass"] = bool(gate_a["ood_leg_pass"] and gate_a["attack_leg_pass"])

    # --- Diagnostic AUC only (never fed back into any selection).
    from sklearn.metrics import roc_auc_score

    auc_rows = []
    future_scores = attack_frames["future_query"]["drocc_score"].to_numpy()
    for held, role, _ in OOD_POOLS:
        frame = table[(table["held_value"] == held) & (table["role"] == role)]
        frame = frame[frame["label_metric_only"] == 0]
        benign_scores = frame["drocc_score"].to_numpy()
        y = np.concatenate([np.zeros(len(benign_scores)), np.ones(len(future_scores))])
        # "attack detected" = low score; use -score so 1=attack is the positive class
        s = np.concatenate([-benign_scores, -future_scores])
        auc_rows.append({"vs_pool": f"{held}/{role}",
                         "auc_future_attack_vs_benign_ood": float(roc_auc_score(y, s))})

    with open(out / "ckby_drocc_pool_metrics_seed27.csv", "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["pool", "kind", "op", "rows", "rate"])
        writer.writeheader()
        writer.writerows(pool_rows)
    with open(out / "ckby_drocc_per_family_seed27.csv", "w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["attack_family", "op", "rows", "recall"]
        )
        writer.writeheader()
        writer.writerows(family_rows)
    with open(out / "ckby_drocc_comparison_seed27.csv", "w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["arm", "future_attack_recall", "ood_macro_4pool"]
        )
        writer.writeheader()
        writer.writerows(comparison)
    with open(out / "ckby_drocc_diagnostic_auc_seed27.csv", "w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["vs_pool", "auc_future_attack_vs_benign_ood"]
        )
        writer.writeheader()
        writer.writerows(auc_rows)

    verdict = {
        "issue": "issue27ckby_drocc_local_seed27",
        "gate_a": gate_a,
        "one_shot_declaration": (
            "Thresholds and checkpoint were frozen before this evaluation; all "
            "report pools were scored exactly once; no metric was fed back into "
            "any selection. FINAL (cooler-motor, seeds 37/47) untouched."
        ),
        "status": "CKBY_DROCC_EVALUATION_COMPLETE",
    }
    with open(out / "ckby_drocc_gate_a_verdict_seed27.json", "w") as handle:
        json.dump(verdict, handle, indent=2)
    print(json.dumps(verdict, indent=2))
    print(pd.DataFrame(comparison).to_string())


if __name__ == "__main__":
    main()
