from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import re

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from paths import ARTIFACT_RUNS_DIR


BOT_IOT_PAGE = "https://research.unsw.edu.au/projects/bot-iot-dataset"
TON_IOT_PAGE = "https://research.unsw.edu.au/projects/toniot-datasets"
KNOWN_LABEL_COLUMNS = [
    "label",
    "Label",
    "attack",
    "Attack",
    "class",
    "Class",
    "subcategory",
    "Subcategory",
    "category",
    "Category",
]
TABULAR_SUFFIXES = {".csv", ".tsv", ".txt", ".parquet"}


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, tuple):
        return [clean(v) for v in obj]
    return obj


def http_get_text(url: str, timeout: int = 30) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def probe_url(url: str, timeout: int = 30) -> Dict[str, object]:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            final_url = str(resp.geturl())
            return {
                "url": url,
                "ok": True,
                "status": int(getattr(resp, "status", 200)),
                "final_url": final_url,
                "requires_login": "login.microsoftonline.com" in final_url.lower(),
            }
    except HTTPError as exc:
        return {
            "url": url,
            "ok": False,
            "status": int(exc.code),
            "reason": str(exc.reason),
            "requires_login": False,
        }
    except URLError as exc:
        return {
            "url": url,
            "ok": False,
            "status": None,
            "reason": str(exc.reason),
            "requires_login": False,
        }


def extract_sharepoint_links(html: str) -> List[str]:
    links = re.findall(r'href=["\']([^"\']+)["\']', html)
    out = []
    for link in links:
        if "sharepoint.com" in link.lower():
            out.append(link)
    dedup: List[str] = []
    seen = set()
    for link in out:
        if link not in seen:
            dedup.append(link)
            seen.add(link)
    return dedup


def find_tabular_files(root: Path) -> List[Path]:
    files: List[Path] = []
    if not root.exists():
        return files
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in TABULAR_SUFFIXES:
            files.append(path)
    files.sort()
    return files


def sniff_table(path: Path, sample_rows: int) -> Tuple[List[str], Optional[str], Dict[str, object]]:
    try:
        if path.suffix.lower() == ".parquet":
            df = pd.read_parquet(path).head(sample_rows)
        else:
            sep = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
            df = pd.read_csv(path, sep=sep, nrows=sample_rows, low_memory=False)
    except Exception as exc:
        return [], None, {"read_ok": False, "error": str(exc)}

    columns = [str(c) for c in df.columns]
    label_col = None
    for col in KNOWN_LABEL_COLUMNS:
        if col in df.columns:
            label_col = col
            break
    stats: Dict[str, object] = {"read_ok": True, "rows_sampled": int(len(df)), "n_columns": int(len(columns))}
    if label_col is not None:
        values = df[label_col].astype(str).fillna("")
        vc = values.value_counts().head(12)
        stats["label_column"] = label_col
        stats["label_top_counts"] = {str(k): int(v) for k, v in vc.items()}
    return columns, label_col, stats


def analyze_local_root(root: Optional[Path], sample_rows: int) -> Dict[str, object]:
    if root is None:
        return {"provided": False, "exists": False, "files": []}
    root = root.expanduser().resolve()
    result: Dict[str, object] = {"provided": True, "path": str(root), "exists": bool(root.exists())}
    if not root.exists():
        result["files"] = []
        return result

    files = find_tabular_files(root)
    analyzed = []
    for path in files[:40]:
        columns, label_col, stats = sniff_table(path, sample_rows=sample_rows)
        analyzed.append(
            {
                "path": str(path),
                "suffix": path.suffix.lower(),
                "label_column": label_col,
                "columns_preview": columns[:30],
                **stats,
            }
        )
    result["files"] = analyzed
    result["n_tabular_files"] = len(files)
    result["n_labeled_candidates"] = sum(1 for row in analyzed if row.get("label_column"))
    return result


def choose_verdict(bot_probe: Dict[str, object], local_bot: Dict[str, object], local_ton: Dict[str, object]) -> Tuple[str, str]:
    if local_bot.get("exists") and int(local_bot.get("n_labeled_candidates", 0)) > 0:
        return (
            "bot_iot_local_ready_for_smoke",
            "BoT-IoT local root exists and contains at least one labeled tabular candidate.",
        )
    if bot_probe.get("status") == 403 or bot_probe.get("requires_login"):
        return (
            "blocked_bot_iot_official_access_forbidden",
            "BoT-IoT official SharePoint dataset folder is not directly usable from this environment because it returns HTTP 403 or redirects to Microsoft login, and no local BoT-IoT copy is present.",
        )
    if local_ton.get("exists") and int(local_ton.get("n_labeled_candidates", 0)) > 0:
        return (
            "ton_iot_local_fallback_ready",
            "BoT-IoT is not locally available, but TON-IoT local root appears usable as a fallback second-environment source.",
        )
    return (
        "blocked_missing_second_environment_dataset",
        "No local BoT-IoT or TON-IoT labeled tabular source is available yet.",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="A-line second-environment feasibility probe.")
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--bot-iot-root", type=Path, default=None)
    parser.add_argument("--ton-iot-root", type=Path, default=None)
    parser.add_argument("--sample-rows", type=int, default=2048)
    args = parser.parse_args()

    run_dir = ARTIFACT_RUNS_DIR / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)

    bot_html = http_get_text(BOT_IOT_PAGE)
    ton_html = http_get_text(TON_IOT_PAGE)
    bot_links = extract_sharepoint_links(bot_html)
    ton_links = extract_sharepoint_links(ton_html)

    bot_probe = probe_url(bot_links[0]) if bot_links else {"ok": False, "status": None, "reason": "no_sharepoint_link_found"}
    ton_probe = probe_url(ton_links[0]) if ton_links else {"ok": False, "status": None, "reason": "no_sharepoint_link_found"}

    local_bot = analyze_local_root(args.bot_iot_root, sample_rows=args.sample_rows)
    local_ton = analyze_local_root(args.ton_iot_root, sample_rows=args.sample_rows)
    verdict, verdict_reason = choose_verdict(bot_probe=bot_probe, local_bot=local_bot, local_ton=local_ton)

    config = {
        "run_tag": args.run_tag,
        "bot_iot_root": None if args.bot_iot_root is None else str(args.bot_iot_root),
        "ton_iot_root": None if args.ton_iot_root is None else str(args.ton_iot_root),
        "sample_rows": int(args.sample_rows),
    }
    run_spec = {
        "stage": "second_environment_feasibility",
        "line": "A-line",
        "goal": "Decide whether BoT-IoT-first second-environment smoke can proceed from this machine without violating the mainline execution order.",
        "success_condition": [
            "BoT-IoT official access works or a local BoT-IoT copy is present",
            "At least one labeled tabular source is visible for smoke preparation",
        ],
    }
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": str(run_dir),
        "config": config,
        "run_spec": run_spec,
        "official_sources": {
            "bot_iot": {
                "page": BOT_IOT_PAGE,
                "sharepoint_links": bot_links,
                "probe": bot_probe,
            },
            "ton_iot": {
                "page": TON_IOT_PAGE,
                "sharepoint_links": ton_links,
                "probe": ton_probe,
            },
        },
        "local_roots": {
            "bot_iot": local_bot,
            "ton_iot": local_ton,
        },
        "verdict": verdict,
        "verdict_reason": verdict_reason,
    }

    command_text = " ".join(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--run-tag",
            args.run_tag,
        ]
    )
    if args.bot_iot_root is not None:
        command_text += f' --bot-iot-root "{args.bot_iot_root}"'
    if args.ton_iot_root is not None:
        command_text += f' --ton-iot-root "{args.ton_iot_root}"'
    command_text += f" --sample-rows {int(args.sample_rows)}"

    write_text(run_dir / "command.txt", command_text + "\n")
    write_text(run_dir / "config.json", json.dumps(clean(config), indent=2) + "\n")
    write_text(run_dir / "run_spec.json", json.dumps(clean(run_spec), indent=2) + "\n")
    write_text(run_dir / "feasibility_report.json", json.dumps(clean(report), indent=2) + "\n")

    candidate_rows = []
    for dataset_name, local in [("bot_iot", local_bot), ("ton_iot", local_ton)]:
        for row in local.get("files", []):
            candidate_rows.append(
                {
                    "dataset": dataset_name,
                    "path": row.get("path"),
                    "suffix": row.get("suffix"),
                    "read_ok": row.get("read_ok"),
                    "label_column": row.get("label_column"),
                    "rows_sampled": row.get("rows_sampled"),
                    "n_columns": row.get("n_columns"),
                }
            )
    if candidate_rows:
        pd.DataFrame(candidate_rows).to_csv(run_dir / "local_candidate_files.csv", index=False)

    summary_lines = [
        "# Second Environment Feasibility Summary",
        "",
        f"- Run tag: `{args.run_tag}`",
        f"- Verdict: `{verdict}`",
        f"- Reason: {verdict_reason}",
        "",
        "## Official Source Probe",
        f"- `BoT-IoT` page: `{BOT_IOT_PAGE}`",
        f"- `BoT-IoT` official dataset probe status: `{bot_probe.get('status')}`",
        f"- `TON-IoT` page: `{TON_IOT_PAGE}`",
        f"- `TON-IoT` official dataset probe status: `{ton_probe.get('status')}`",
        "",
        "## Local Dataset Probe",
        f"- `BoT-IoT` local root provided: `{local_bot.get('provided')}`",
        f"- `BoT-IoT` local root exists: `{local_bot.get('exists')}`",
        f"- `BoT-IoT` labeled candidates: `{local_bot.get('n_labeled_candidates', 0)}`",
        f"- `TON-IoT` local root provided: `{local_ton.get('provided')}`",
        f"- `TON-IoT` local root exists: `{local_ton.get('exists')}`",
        f"- `TON-IoT` labeled candidates: `{local_ton.get('n_labeled_candidates', 0)}`",
        "",
        "## Next",
    ]
    if verdict == "bot_iot_local_ready_for_smoke":
        summary_lines.append("- Proceed to a local BoT-IoT smoke run with the minimal second-environment package.")
    elif verdict == "ton_iot_local_fallback_ready":
        summary_lines.append("- BoT-IoT is not ready locally; if the mainline rule permits, use the available TON-IoT root for the next smoke.")
    else:
        summary_lines.append("- Do not start formal second-environment training yet.")
        summary_lines.append("- First obtain a local BoT-IoT or TON-IoT dataset copy and rerun this feasibility probe.")
    write_text(run_dir / "summary.md", "\n".join(summary_lines) + "\n")

    print(json.dumps({"run_dir": str(run_dir), "verdict": verdict}, ensure_ascii=True))


if __name__ == "__main__":
    main()
