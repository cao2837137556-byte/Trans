from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
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


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, tuple):
        return [clean(v) for v in obj]
    if isinstance(obj, np.generic):
        return clean(obj.item())
    return obj


def count_label(path: Path, label_col: str, normal_label: str, sep: str) -> Dict[str, int]:
    df = pd.read_csv(path, sep=sep, usecols=[label_col], low_memory=False)
    labels = df[label_col].astype(str)
    benign = int((labels == normal_label).sum())
    attack = int((labels != normal_label).sum())
    return {"total": int(len(df)), "benign": benign, "attack": attack}


def evaluate_candidate(
    name: str,
    id_benign: int,
    ood_benign: int,
    attack_pool: int,
    naive_budget: int,
    min_id_formal: int,
    min_ood_formal: int,
) -> Dict[str, object]:
    return {
        "candidate": name,
        "id_benign": int(id_benign),
        "ood_benign": int(ood_benign),
        "attack_pool": int(attack_pool),
        "supports_fixed_q99_min100": bool(id_benign >= 100 and ood_benign >= 100),
        "supports_naive_budget5000": bool(ood_benign >= naive_budget),
        "supports_formal_min_benign": bool(id_benign >= min_id_formal and ood_benign >= min_ood_formal),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="BoT-IoT split readiness gate for second-environment formal package.")
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--full10best-csv", type=Path, required=True)
    parser.add_argument("--train10best-csv", type=Path, required=True)
    parser.add_argument("--test10best-csv", type=Path, required=True)
    parser.add_argument("--full4-csv", type=Path, required=True)
    parser.add_argument("--label-col", default="attack")
    parser.add_argument("--normal-label", default="0")
    parser.add_argument("--naive-budget", type=int, default=5000)
    parser.add_argument("--min-id-formal", type=int, default=1000)
    parser.add_argument("--min-ood-formal", type=int, default=1000)
    args = parser.parse_args()

    run_dir = ARTIFACT_RUNS_DIR / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)

    full10 = count_label(args.full10best_csv, args.label_col, args.normal_label, sep=";")
    train10 = count_label(args.train10best_csv, args.label_col, args.normal_label, sep=",")
    test10 = count_label(args.test10best_csv, args.label_col, args.normal_label, sep=",")
    full4 = count_label(args.full4_csv, args.label_col, args.normal_label, sep=",")

    candidates: List[Dict[str, object]] = []
    candidates.append(
        evaluate_candidate(
            name="official_10best_train_vs_test",
            id_benign=train10["benign"],
            ood_benign=test10["benign"],
            attack_pool=test10["attack"],
            naive_budget=args.naive_budget,
            min_id_formal=args.min_id_formal,
            min_ood_formal=args.min_ood_formal,
        )
    )

    # Full 10-best: maximize OOD while still allowing q99 ID threshold.
    max_ood_id_floor = 100
    candidates.append(
        evaluate_candidate(
            name="full10best_max_ood_with_id100",
            id_benign=max_ood_id_floor,
            ood_benign=max(0, full10["benign"] - max_ood_id_floor),
            attack_pool=full10["attack"],
            naive_budget=args.naive_budget,
            min_id_formal=args.min_id_formal,
            min_ood_formal=args.min_ood_formal,
        )
    )

    # Full 10-best: balanced 70/30 benign split.
    id_bal = int(round(full10["benign"] * 0.7))
    ood_bal = max(0, full10["benign"] - id_bal)
    candidates.append(
        evaluate_candidate(
            name="full10best_benign_70_30",
            id_benign=id_bal,
            ood_benign=ood_bal,
            attack_pool=full10["attack"],
            naive_budget=args.naive_budget,
            min_id_formal=args.min_id_formal,
            min_ood_formal=args.min_ood_formal,
        )
    )

    # Full-feature file4 normal-only support check.
    id_full4 = int(round(full4["benign"] * 0.7))
    ood_full4 = max(0, full4["benign"] - id_full4)
    candidates.append(
        evaluate_candidate(
            name="full4_benign_70_30",
            id_benign=id_full4,
            ood_benign=ood_full4,
            attack_pool=full4["attack"],
            naive_budget=args.naive_budget,
            min_id_formal=args.min_id_formal,
            min_ood_formal=args.min_ood_formal,
        )
    )

    cand_df = pd.DataFrame(candidates)
    cand_df.to_csv(run_dir / "split_candidates.csv", index=False)

    any_naive_ready = bool(cand_df["supports_naive_budget5000"].any())
    any_formal_ready = bool(cand_df["supports_formal_min_benign"].any())
    any_fixed_ready = bool(cand_df["supports_fixed_q99_min100"].any())

    if not any_fixed_ready:
        verdict = "blocked_even_fixed_policy_not_supported"
        reason = "BoT-IoT benign support cannot satisfy even minimal fixed q99 ID/OOD sample requirements."
    elif not any_naive_ready:
        verdict = "blocked_naive_budget5000_not_supported"
        reason = (
            "No BoT-IoT split candidate can provide enough OOD benign samples for the required "
            f"`naive_calibrated_budget{args.naive_budget}` operating point."
        )
    elif not any_formal_ready:
        verdict = "warning_formal_min_benign_not_met"
        reason = "BoT-IoT can pass fixed/basic checks but fails formal benign support thresholds."
    else:
        verdict = "botiot_formal_split_ready"
        reason = "At least one BoT-IoT split candidate satisfies fixed, naive-budget, and formal benign thresholds."

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": str(run_dir),
        "inputs": {
            "full10best_csv": str(args.full10best_csv),
            "train10best_csv": str(args.train10best_csv),
            "test10best_csv": str(args.test10best_csv),
            "full4_csv": str(args.full4_csv),
            "label_col": args.label_col,
            "normal_label": args.normal_label,
            "naive_budget": int(args.naive_budget),
            "min_id_formal": int(args.min_id_formal),
            "min_ood_formal": int(args.min_ood_formal),
        },
        "raw_counts": {
            "full10best": full10,
            "train10best": train10,
            "test10best": test10,
            "full4": full4,
        },
        "verdict": verdict,
        "reason": reason,
    }
    (run_dir / "split_gate_report.json").write_text(json.dumps(clean(report), indent=2), encoding="utf-8")

    summary_lines = [
        "# BoT-IoT Split Gate Summary",
        "",
        f"- Run tag: `{args.run_tag}`",
        f"- Verdict: `{verdict}`",
        f"- Reason: {reason}",
        "",
        "## Raw Benign/Attack Counts",
        f"- `10-best full`: benign={full10['benign']}, attack={full10['attack']}, total={full10['total']}",
        f"- `10-best train`: benign={train10['benign']}, attack={train10['attack']}, total={train10['total']}",
        f"- `10-best test`: benign={test10['benign']}, attack={test10['attack']}, total={test10['total']}",
        f"- `all-feature full4`: benign={full4['benign']}, attack={full4['attack']}, total={full4['total']}",
        "",
        "## Gate",
        f"- Required naive budget for mainline policy: `{args.naive_budget}` OOD benign samples",
        f"- Formal benign support threshold: `id>={args.min_id_formal}`, `ood>={args.min_ood_formal}`",
        "",
        "## Next",
    ]
    if verdict in {"blocked_even_fixed_policy_not_supported", "blocked_naive_budget5000_not_supported"}:
        summary_lines.append("- Do not treat BoT-IoT as formal second-environment closure under current mainline policy set.")
        summary_lines.append("- Escalate to TON-IoT fallback for the formal second-environment package.")
    else:
        summary_lines.append("- Continue BoT-IoT formal package with the best split candidate from `split_candidates.csv`.")
    (run_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    config = {
        "run_tag": args.run_tag,
        "naive_budget": int(args.naive_budget),
        "min_id_formal": int(args.min_id_formal),
        "min_ood_formal": int(args.min_ood_formal),
    }
    run_spec = {
        "stage": "second_environment_botiot_split_gate",
        "goal": "Converge on whether BoT-IoT can satisfy formal second-environment split requirements under fixed mainline policies.",
    }
    (run_dir / "config.json").write_text(json.dumps(clean(config), indent=2) + "\n", encoding="utf-8")
    (run_dir / "run_spec.json").write_text(json.dumps(clean(run_spec), indent=2) + "\n", encoding="utf-8")
    (run_dir / "command.txt").write_text(" ".join(sys.argv) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(run_dir), "verdict": verdict}, ensure_ascii=True))


if __name__ == "__main__":
    main()
