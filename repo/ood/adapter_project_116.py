from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd


TARGET_DIM = 116


def _to_float(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for c in cols:
        if c in df.columns:
            out[c] = pd.to_numeric(df[c], errors="coerce")
        else:
            out[c] = 0.0
    return out.fillna(0.0)


def _add_binary_col(df: pd.DataFrame, name: str, mask: pd.Series) -> None:
    df[name] = mask.astype(np.float32)


def _base_features_iot23(df: pd.DataFrame) -> pd.DataFrame:
    base_cols = [
        "duration",
        "orig_bytes",
        "resp_bytes",
        "missed_bytes",
        "orig_pkts",
        "resp_pkts",
        "orig_ip_bytes",
        "resp_ip_bytes",
        "id.orig_p",
        "id.resp_p",
    ]
    x = _to_float(df, base_cols)

    proto = df.get("proto", "").astype(str).str.lower()
    _add_binary_col(x, "proto_tcp", proto.eq("tcp"))
    _add_binary_col(x, "proto_udp", proto.eq("udp"))
    _add_binary_col(x, "proto_icmp", proto.eq("icmp"))

    state = df.get("conn_state", "").astype(str).str.upper()
    for s in ["S0", "SF", "REJ", "RSTO", "OTH"]:
        _add_binary_col(x, f"state_{s}", state.eq(s))

    x["bytes_total"] = x["orig_bytes"] + x["resp_bytes"]
    x["pkts_total"] = x["orig_pkts"] + x["resp_pkts"]
    x["resp_orig_bytes_ratio"] = x["resp_bytes"] / (x["orig_bytes"] + 1.0)
    x["resp_orig_pkts_ratio"] = x["resp_pkts"] / (x["orig_pkts"] + 1.0)
    return x


def _base_features_ciciot(df: pd.DataFrame) -> pd.DataFrame:
    base_cols = [
        "flow_duration",
        "Duration",
        "Header_Length",
        "Protocol_Type",
        "Rate",
        "Srate",
        "Tot_sum",
        "Tot_size",
        "Min",
        "Max",
        "AVG",
        "Std",
        "IAT",
        "Number",
        "Weight",
        "Variance",
        "Covariance",
        "Radius",
    ]
    x = _to_float(df, base_cols)

    for c in ["TCP", "UDP", "ICMP", "ARP", "HTTP", "HTTPS", "DNS", "IPv", "LLC"]:
        if c in df.columns:
            x[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        else:
            x[c] = 0.0

    x["range"] = x["Max"] - x["Min"]
    x["sum_per_packet"] = x["Tot_sum"] / (x["Number"] + 1.0)
    x["size_per_packet"] = x["Tot_size"] / (x["Number"] + 1.0)
    return x


def _project_to_116(arr: np.ndarray, seed: int) -> np.ndarray:
    if arr.shape[1] == TARGET_DIM:
        return arr
    if arr.shape[1] > TARGET_DIM:
        return arr[:, :TARGET_DIM]
    rng = np.random.default_rng(seed)
    proj = rng.standard_normal((arr.shape[1], TARGET_DIM)).astype(np.float32)
    return arr.astype(np.float32) @ proj


def _log_scale(arr: np.ndarray) -> np.ndarray:
    return np.sign(arr) * np.log1p(np.abs(arr))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build minimal 116-d adapter for OOD probing.")
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--dataset", choices=["iot23", "ciciot2023"], required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-labels", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--label-col", type=str, default="label")
    parser.add_argument("--benign-token", type=str, default="benign")
    args = parser.parse_args()

    df = pd.read_csv(args.input_csv, low_memory=False)
    if args.dataset == "iot23":
        base = _base_features_iot23(df)
    else:
        base = _base_features_ciciot(df)

    features = _project_to_116(_log_scale(base.to_numpy(dtype=np.float32)), args.seed)
    out_df = pd.DataFrame(features)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.output_csv, header=False, index=False)

    labels = np.zeros(len(df), dtype=np.int64)
    if args.label_col in df.columns:
        s = df[args.label_col].astype(str).str.lower()
        labels = (~s.str.contains(args.benign_token.lower())).astype(np.int64).to_numpy()
    args.output_labels.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output_labels, labels)

    meta = {
        "input_csv": str(args.input_csv),
        "dataset": args.dataset,
        "rows": int(len(df)),
        "base_dim": int(base.shape[1]),
        "output_dim": int(TARGET_DIM),
        "label_col": args.label_col,
        "seed": int(args.seed),
    }
    (args.output_csv.parent / f"{args.output_csv.stem}_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(f"[done] features={args.output_csv} labels={args.output_labels}")


if __name__ == "__main__":
    main()
