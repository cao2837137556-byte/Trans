from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from paths import ROOT_DIR


def is_float_token(value: str) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False


def quick_file_stats(path: Path) -> Dict[str, object]:
    first_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    tokens = first_line.split(",")
    has_header_like = any(not is_float_token(tok) for tok in tokens)
    return {
        "path": str(path),
        "first_row_cols": len(tokens),
        "first_row_has_non_numeric_token": has_header_like,
    }


def inspect_external_dataset(path: Path) -> Dict[str, object]:
    info = quick_file_stats(path)
    df = pd.read_csv(path, low_memory=False)
    numeric_cols = 0
    non_numeric_cols = 0
    for c in df.columns:
        s = pd.to_numeric(df[c], errors="coerce")
        if s.notna().mean() > 0.98:
            numeric_cols += 1
        else:
            non_numeric_cols += 1
    label_candidates = [
        c
        for c in df.columns
        if str(c).lower() in {"label", "attack", "class", "detailed-label", "detailed_label"}
    ]
    info.update(
        {
            "rows": int(len(df)),
            "cols": int(df.shape[1]),
            "numeric_cols_approx": int(numeric_cols),
            "non_numeric_cols_approx": int(non_numeric_cols),
            "label_candidates": label_candidates,
        }
    )

    # Mirror current pipeline loader behavior: header=None and numeric array expectation.
    direct_loader_ok = True
    direct_loader_reason = "ok"
    try:
        raw = pd.read_csv(path, header=None, nrows=128, low_memory=False).values
        _ = raw.astype(float)
    except Exception as exc:
        direct_loader_ok = False
        direct_loader_reason = f"{type(exc).__name__}: {exc}"

    blockers: List[str] = []
    if info["cols"] != 116:
        blockers.append(f"dimension mismatch ({info['cols']} != 116)")
    if info["non_numeric_cols_approx"] > 0:
        blockers.append("contains non-numeric categorical/string fields")
    if info["first_row_has_non_numeric_token"]:
        blockers.append("has header row; current pipeline uses header=None")
    if not direct_loader_ok:
        blockers.append("cannot cast to float under current loader")

    info["direct_loader_ok"] = direct_loader_ok
    info["direct_loader_reason"] = direct_loader_reason
    info["direct_compatible_with_current_pipeline"] = len(blockers) == 0
    info["blockers"] = blockers
    return info


def find_checkpoints(root: Path) -> List[str]:
    pats = ["*.pt", "*.pth", "*.ckpt", "*.bin", "*.pkl", "*.joblib"]
    found = []
    for pat in pats:
        for f in root.rglob(pat):
            found.append(str(f.relative_to(root)))
    return sorted(found)


def write_markdown(
    run_dir: Path,
    current_input_cols: int,
    checkpoint_paths: List[str],
    external_infos: Dict[str, Dict[str, object]],
) -> None:
    md = []
    md.append("# OOD Preflight Audit")
    md.append("")
    md.append(f"- Generated at: {datetime.now().isoformat(timespec='seconds')}")
    md.append(f"- Workspace: `{ROOT_DIR}`")
    md.append("")
    md.append("## 1) Current Project Audit")
    md.append("- Training/eval entry: `repo/example.py` (online train then execute in one pass).")
    md.append("- Model definition: `repo/KitNET.py` (ensemble wrapper) + `repo/Trans.py` (Transformer detector).")
    md.append("- Feature generation in this repo: pre-extracted CSV slices via `repo/prepare_gold_data.py`; no raw pcap->116 extractor script is present here.")
    md.append("- Current input format in `example.py`: CSV loaded with `header=None`, expected numeric matrix with `n=116` features per row.")
    md.append("- Existing metrics in `example.py`: ROC-AUC and PR-AUC after grace windows, plus RMSE curve plot.")
    md.append("- Legacy eval helper: `repo/evaluate_auc.py` computes ROC-AUC from saved RMSE and aligned labels.")
    if checkpoint_paths:
        md.append("- Checkpoints found:")
        for p in checkpoint_paths:
            md.append(f"  - `{p}`")
    else:
        md.append("- Checkpoints found: none (`.pt/.pth/.ckpt` not present).")
    md.append("")
    md.append("## 2) Schema / Compatibility Report")
    md.append("| Dataset | Rows | Cols | Numeric Cols (approx) | Label Col Candidates | Direct Compatible | Main Blockers |")
    md.append("|---|---:|---:|---:|---|---|---|")
    for name, info in external_infos.items():
        blockers = "; ".join(info["blockers"]) if info["blockers"] else "none"
        labels = ",".join(info["label_candidates"]) if info["label_candidates"] else "-"
        md.append(
            f"| {name} | {info['rows']} | {info['cols']} | {info['numeric_cols_approx']} | {labels} | "
            f"{'yes' if info['direct_compatible_with_current_pipeline'] else 'no'} | {blockers} |"
        )
    md.append("")
    md.append("## 3) Compatibility Conclusion")
    md.append(f"- Current Mirai chain expects fixed {current_input_cols}-dim numeric vectors representing Kitsune-style statistics.")
    md.append("- IoT-23/CICIoT2023 subsets are flow/tabular schemas with different semantics and dimensions (21/39/40 here).")
    md.append("- Direct OOD inference with existing Mirai-trained state is blocked by schema mismatch and missing persisted checkpoint.")
    md.append("")
    md.append("## 4) Minimal Adapter Plan (No Major Refactor)")
    md.append("- Step A: add checkpoint persistence for trained KitNET/Transformer state + min/max normalizer stats.")
    md.append("- Step B: implement a narrow adapter script mapping public flow columns to a stable 116-dim vector (select numeric subset + deterministic projection/padding) only for probe-level drift validation.")
    md.append("- Step C: run OOD probe outputs in `runs/ood_probe_<date>/` with benign alarm ratio, score histogram drift, ROC-AUC/PR-AUC when labels exist.")
    md.append("- Step D: for publication-grade comparison, replace projection adapter with a true common feature extractor (raw packet -> unified feature space).")
    md.append("")
    md.append("## 5) Data Staging")
    md.append("- Public raw files: `public_data/raw/`")
    md.append("- Public minimal subsets: `public_data/subsets/`")
    md.append("- Subset metadata: `public_data/subsets/metadata.json`")

    (run_dir / "preflight_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build OOD preflight audit report.")
    parser.add_argument("--date-tag", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output run dir; defaults to runs/ood_probe_<date>.",
    )
    args = parser.parse_args()

    run_dir = args.out_dir or (ROOT_DIR / "runs" / f"ood_probe_{args.date_tag}")
    run_dir.mkdir(parents=True, exist_ok=True)

    current_data = ROOT_DIR / "my_gold_mirai.csv"
    current_info = quick_file_stats(current_data)
    current_input_cols = int(current_info["first_row_cols"])

    checkpoint_paths = find_checkpoints(ROOT_DIR)

    targets = {
        "iot23_benign_min": ROOT_DIR / "public_data" / "subsets" / "iot23_benign_min.csv",
        "iot23_mirai_malicious_min": ROOT_DIR / "public_data" / "subsets" / "iot23_mirai_malicious_min.csv",
        "ciciot2023_benign_min": ROOT_DIR / "public_data" / "subsets" / "ciciot2023_benign_min.csv",
        "ciciot2023_attack_min": ROOT_DIR / "public_data" / "subsets" / "ciciot2023_attack_min.csv",
    }

    external_infos: Dict[str, Dict[str, object]] = {}
    for name, path in targets.items():
        if not path.exists():
            external_infos[name] = {"rows": 0, "cols": 0, "numeric_cols_approx": 0, "label_candidates": [], "blockers": ["missing file"], "direct_compatible_with_current_pipeline": False}
            continue
        external_infos[name] = inspect_external_dataset(path)

    write_markdown(run_dir, current_input_cols, checkpoint_paths, external_infos)

    json_report = {
        "run_dir": str(run_dir),
        "current_input_cols": current_input_cols,
        "checkpoint_paths": checkpoint_paths,
        "external_infos": external_infos,
    }
    (run_dir / "schema_compatibility.json").write_text(
        json.dumps(json_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[done] report: {run_dir / 'preflight_report.md'}")


if __name__ == "__main__":
    main()
