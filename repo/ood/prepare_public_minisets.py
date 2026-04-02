from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Optional
from urllib.request import urlretrieve

import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from paths import ROOT_DIR


IOT23_BENIGN_URL = (
    "https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset-v2/"
    "CTU-Honeypot-Capture-7-6/"
    "2019-07-07-16-41-19-192.168.1.158-zeek-conn-log.labeled"
)
IOT23_MALICIOUS_URL = (
    "https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset-v2/"
    "CTU-IoT-Malware-Capture-34-1/"
    "2018-12-21-15-50-14-192.168.1.195-zeek-conn-log.labeled"
)
CICIOT2023_URL = (
    "https://zenodo.org/records/16054391/files/CICIoT2023%20(2).csv?download=1"
)
CICIOT2023_BENIGN_URL = (
    "https://huggingface.co/datasets/baalajimaestro/DDoS-CICIoT2023/"
    "resolve/main/BenignTraffic3.pcap.csv?download=true"
)


def download_if_missing(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        print(f"[skip] exists: {target}")
        return
    print(f"[download] {url}")
    urlretrieve(url, target)
    print(f"[saved] {target}")


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
            if line.startswith("#"):
                continue
            if not line.strip():
                continue
            if fields is None:
                raise RuntimeError(f"Missing #fields header in {path}")
            parts = line.rstrip("\n").split("\t")
            if split_tail_triplet and parts:
                tail = re.split(r"\s{2,}", parts[-1].strip())
                if len(tail) == 3:
                    parts = parts[:-1] + tail
            if len(parts) != len(fields):
                continue
            rows.append(parts)
    return pd.DataFrame(rows, columns=fields)


def resolve_label_column(df: pd.DataFrame) -> Optional[str]:
    for col in ["label", "Label", "attack", "Attack", "class", "Class"]:
        if col in df.columns:
            return col
    return None


def is_benign_series(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.lower()
    numeric = pd.to_numeric(series, errors="coerce")
    return (
        text.str.contains("benign")
        | text.str.contains("normal")
        | numeric.eq(0)
    )


def sample_rows(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    if len(df) <= n:
        return df.copy()
    return df.sample(n=n, random_state=seed)


def sanitize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = []
    for c in df.columns:
        c = re.sub(r"[^0-9a-zA-Z_]+", "_", str(c)).strip("_")
        if not c:
            c = "col"
        cleaned.append(c)
    df = df.copy()
    df.columns = cleaned
    return df


def prepare_iot23(raw_dir: Path, subset_dir: Path, n_per_class: int, seed: int) -> Dict[str, Dict[str, int]]:
    benign_raw = raw_dir / "iot23_benign_7_6.log.labeled"
    malicious_raw = raw_dir / "iot23_mirai_34_1.log.labeled"

    download_if_missing(IOT23_BENIGN_URL, benign_raw)
    download_if_missing(IOT23_MALICIOUS_URL, malicious_raw)

    benign_df = parse_zeek_labeled_log(benign_raw)
    malicious_df = parse_zeek_labeled_log(malicious_raw)

    benign_label_col = resolve_label_column(benign_df)
    if benign_label_col is not None:
        benign_df = benign_df[is_benign_series(benign_df[benign_label_col])]
    benign_df = sample_rows(benign_df, n_per_class, seed)

    mal_label_col = resolve_label_column(malicious_df)
    if mal_label_col is not None:
        malicious_only = malicious_df[~is_benign_series(malicious_df[mal_label_col])]
    else:
        malicious_only = malicious_df.copy()
    malicious_only = sample_rows(malicious_only, n_per_class, seed)

    benign_out = subset_dir / "iot23_benign_min.csv"
    mal_out = subset_dir / "iot23_mirai_malicious_min.csv"
    benign_df.to_csv(benign_out, index=False)
    malicious_only.to_csv(mal_out, index=False)

    return {
        "iot23_benign_min.csv": {
            "rows": int(len(benign_df)),
            "cols": int(benign_df.shape[1]),
        },
        "iot23_mirai_malicious_min.csv": {
            "rows": int(len(malicious_only)),
            "cols": int(malicious_only.shape[1]),
        },
    }


def prepare_ciciot2023(raw_dir: Path, subset_dir: Path, n_per_class: int, seed: int) -> Dict[str, Dict[str, int]]:
    attack_raw_path = raw_dir / "CICIoT2023_2.csv"
    benign_raw_path = raw_dir / "CICIoT2023_BenignTraffic3.csv"
    download_if_missing(CICIOT2023_URL, attack_raw_path)
    download_if_missing(CICIOT2023_BENIGN_URL, benign_raw_path)

    attack_df = sanitize_column_names(pd.read_csv(attack_raw_path, low_memory=False))
    benign_df = sanitize_column_names(pd.read_csv(benign_raw_path, low_memory=False))

    attack_label_col = resolve_label_column(attack_df)
    benign_label_col = resolve_label_column(benign_df)

    if attack_label_col is None:
        attack_df = attack_df.copy()
        attack_df["label"] = "attack"
        attack_label_col = "label"
    if benign_label_col is None:
        benign_df = benign_df.copy()
        benign_df["label"] = "Benign"
        benign_label_col = "label"

    benign = benign_df[is_benign_series(benign_df[benign_label_col])]
    if benign.empty:
        benign = benign_df.copy()

    attack = attack_df[~is_benign_series(attack_df[attack_label_col])]
    if attack.empty:
        attack = attack_df.copy()

    benign = sample_rows(benign, n_per_class, seed)
    attack = sample_rows(attack, n_per_class, seed)

    benign_out = subset_dir / "ciciot2023_benign_min.csv"
    attack_out = subset_dir / "ciciot2023_attack_min.csv"
    benign.to_csv(benign_out, index=False)
    attack.to_csv(attack_out, index=False)

    return {
        "ciciot2023_benign_min.csv": {
            "rows": int(len(benign)),
            "cols": int(benign.shape[1]),
        },
        "ciciot2023_attack_min.csv": {
            "rows": int(len(attack)),
            "cols": int(attack.shape[1]),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and prepare minimal OOD public subsets.")
    parser.add_argument("--samples-per-class", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out-root",
        type=Path,
        default=ROOT_DIR / "public_data",
        help="Root output directory for downloaded files and subsets.",
    )
    args = parser.parse_args()

    raw_dir = args.out_root / "raw"
    subset_dir = args.out_root / "subsets"
    subset_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "samples_per_class": args.samples_per_class,
        "seed": args.seed,
        "sources": {
            "iot23_benign": IOT23_BENIGN_URL,
            "iot23_malicious": IOT23_MALICIOUS_URL,
            "ciciot2023": CICIOT2023_URL,
            "ciciot2023_benign": CICIOT2023_BENIGN_URL,
        },
        "generated": {},
    }

    report["generated"].update(prepare_iot23(raw_dir, subset_dir, args.samples_per_class, args.seed))
    report["generated"].update(prepare_ciciot2023(raw_dir, subset_dir, args.samples_per_class, args.seed))

    report_path = subset_dir / "metadata.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[done] metadata: {report_path}")


if __name__ == "__main__":
    main()
