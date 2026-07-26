#!/usr/bin/env python3
"""One-shot local analysis of a pulled-back CKBV seed-27 run root.

Reads the validator-approved pullback (extracted run root), independently
recomputes the preregistered GO/NO_GO subconditions from the raw tables, and
produces the three upgrade-ladder diagnostics agreed on 2026-07-26:

1. independent GO/NO_GO recheck against ``ckbu_single_seed_go_no_go.json``;
2. process-head separation (AUROC) per attack mechanism, using Gotham
   family names as mechanism proxies (ToN mechanism rows are fit-only and
   never scored, so no direct ToN readout exists);
3. rescue-branch trigger rates on the four held benign-OOD families;
4. per-family rescue map C1 -> FrozenCKBQ -> final system.

Diagnostic only: writes nothing into the run root, changes no protocol.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
import sys
import tempfile
from pathlib import Path

PRIMARY = "M4-CKBQ-TabMProcessRescue"
C1 = "M0-C1"
FROZEN = "M1-FrozenCKBQ"
HEAD = "H2-TabMProcessHead"
GLOBAL = "GLOBAL_ATTACK_PRESERVATION"
HELD_FAMILIES = [
    "iotsim-ip-camera-street",
    "iotsim-predictive-maintenance",
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
]
MECHANISMS = {
    "scan": ("TCP Scan", "UDP Scan"),
    "bruteforce": ("Telnet Brute Force",),
    "flood": ("Flood",),
    "cnc": ("C&C", "Reporting"),
}


def read_rows(path: Path) -> list[dict[str, str]]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def auroc(attack_scores: list[float], benign_scores: list[float]) -> float | None:
    if not attack_scores or not benign_scores:
        return None
    merged = sorted(
        [(score, 1) for score in attack_scores] + [(score, 0) for score in benign_scores]
    )
    rank_sum = 0.0
    index = 0
    while index < len(merged):
        tie_end = index
        while tie_end + 1 < len(merged) and merged[tie_end + 1][0] == merged[index][0]:
            tie_end += 1
        average_rank = (index + tie_end) / 2.0 + 1.0
        for position in range(index, tie_end + 1):
            if merged[position][1] == 1:
                rank_sum += average_rank
        index = tie_end + 1
    n_attack = len(attack_scores)
    n_benign = len(benign_scores)
    return (rank_sum - n_attack * (n_attack + 1) / 2.0) / (n_attack * n_benign)


def family_mechanism(family: str) -> str | None:
    for mechanism, needles in MECHANISMS.items():
        if any(needle.lower() in family.lower() for needle in needles):
            return mechanism
    return None


def analyze(run_root: Path) -> dict:
    result: dict = {"run_root": str(run_root), "problems": []}

    phase = (run_root / "current_phase.txt")
    if phase.exists():
        result["current_phase"] = phase.read_text(encoding="utf-8").strip()
    if (run_root / "job_failure.txt").exists():
        result["problems"].append(
            "job_failure.txt present: "
            + (run_root / "job_failure.txt").read_text(encoding="utf-8").strip()
        )
    validation = run_root / "ckbv_result_validation.json"
    if validation.exists():
        result["result_validation"] = json.loads(validation.read_text(encoding="utf-8"))

    official = json.loads(
        (run_root / "ckbu_single_seed_go_no_go.json").read_text(encoding="utf-8")
    )
    result["official_decision"] = official.get("decision")
    result["official_checks"] = official.get("checks")

    preservation = read_rows(run_root / "attack_preservation_summary.csv")
    level2 = read_rows(run_root / "strict_level2_summary.csv")
    selection = read_rows(run_root / "ckbu_candidate_selection.csv")
    support = read_rows(run_root / "ckbu_support_training_usage.csv")
    scope = read_rows(run_root / "ckbu_protocol_scope_audit.csv")
    review = read_rows(run_root / "ckbu_review_audit.csv")
    roles = read_rows(run_root / "ckbu_role_usage_audit.csv")

    checks: dict[str, bool | None] = {}

    overall = [
        row
        for row in preservation
        if row["candidate"] == PRIMARY and row["metric"] == "overall_attack_hard_recall"
    ]
    overall_delta = float(overall[0]["delta_vs_c1_pp"]) if overall else math.nan
    result["overall_attack_delta_pp"] = overall_delta
    checks["overall_delta_at_least_minus_0.5pp"] = overall_delta >= -0.5

    family_rows = [
        row
        for row in preservation
        if row["candidate"] == PRIMARY
        and row["metric"] == "attack_family_recall"
        and int(float(row["rows"])) >= 15
    ]
    worst_family = None
    family_ok = True
    for row in family_rows:
        delta = float(row["delta_vs_c1_pp"])
        if worst_family is None or delta < worst_family[1]:
            worst_family = (row["attack_family"], delta)
        if delta < -2.0:
            family_ok = False
    checks["major_families_within_2pp"] = family_ok
    result["worst_major_family"] = worst_family

    held_report: dict[str, dict] = {}
    held_ok = True
    for family in HELD_FAMILIES:
        primary_rows = [
            row
            for row in level2
            if row["candidate"] == PRIMARY and row["held_value"] == family
        ]
        if not primary_rows:
            held_ok = False
            result["problems"].append(f"missing strict_level2 row for {family}")
            continue
        rate = float(primary_rows[0]["hard_rate"])
        c1_rate = float(primary_rows[0]["c1_hard_rate"])
        frozen_rows = [
            row
            for row in level2
            if row["candidate"] == FROZEN and row["held_value"] == family
        ]
        held_report[family] = {
            "final_hard_rate": rate,
            "c1_hard_rate": c1_rate,
            "frozen_ckbq_hard_rate": float(frozen_rows[0]["hard_rate"]) if frozen_rows else None,
            "improves_5pp": rate <= c1_rate - 0.05,
            "at_most_90pct": rate <= 0.90,
        }
        if not (rate <= c1_rate - 0.05 and rate <= 0.90):
            held_ok = False
    checks["held_improve_5pp_and_at_most_90pct"] = held_ok
    result["held_families"] = held_report

    gate_rows = [
        row
        for row in selection
        if row["candidate"] == HEAD
        and row["held_value"] == GLOBAL
        and truthy(row["selected"])
    ]
    checks["gate_constraint_pass"] = bool(gate_rows) and truthy(
        gate_rows[0]["gate_constraint_pass"]
    )

    support_rows = [row for row in support if row["candidate"] == HEAD]
    checks["support_385_all_used"] = len(support_rows) == 385 and all(
        truthy(row["used_at_least_once_each_epoch"]) for row in support_rows
    )

    leak = sum(
        int(float(row.get("report_fit_use_count", 0) or 0))
        + int(float(row.get("report_select_use_count", 0) or 0))
        for row in scope
    )
    checks["report_leakage_zero"] = leak == 0

    checks["review_zero"] = all(
        int(float(row.get("review_count", 0) or 0)) == 0
        and float(row.get("review_rate", 0) or 0) == 0.0
        for row in review
    )

    alignment_values = [
        int(float(row["target_alignment_incomplete"] or 0))
        for row in roles
        if row.get("target_alignment_incomplete") not in (None, "")
    ]
    checks["alignment_complete"] = bool(alignment_values) and sum(alignment_values) == 0

    result["independent_checks"] = checks
    result["independent_decision"] = (
        "GO_SIGNAL" if all(bool(value) for value in checks.values()) else "NO_GO"
    )
    result["matches_official"] = result["independent_decision"] == result["official_decision"]

    predictions = read_rows(run_root / "ckbu_record_predictions.csv.gz")

    global_rows = [row for row in predictions if row["held_value"] == GLOBAL]
    mechanism_auroc: dict[str, dict] = {}
    benign_scores = {
        "tabm": [
            float(row["tabm_process_score"])
            for row in global_rows
            if row["label_metric_only"] == "0"
        ],
        "extra": [
            float(row["extra_process_score"])
            for row in global_rows
            if row["label_metric_only"] == "0"
        ],
    }
    for mechanism in list(MECHANISMS) + ["all_attacks"]:
        attack_rows = [
            row
            for row in global_rows
            if row["label_metric_only"] == "1"
            and (
                mechanism == "all_attacks"
                or family_mechanism(row["attack_family"]) == mechanism
            )
        ]
        mechanism_auroc[mechanism] = {
            "attack_rows": len(attack_rows),
            "tabm_auroc": auroc(
                [float(row["tabm_process_score"]) for row in attack_rows],
                benign_scores["tabm"],
            ),
            "extra_auroc": auroc(
                [float(row["extra_process_score"]) for row in attack_rows],
                benign_scores["extra"],
            ),
        }
    result["mechanism_separation"] = mechanism_auroc

    rescue: dict[str, dict] = {}
    for family in HELD_FAMILIES:
        rows = [
            row
            for row in predictions
            if row["held_value"] == family and row["label_metric_only"] == "0"
        ]
        triggered = [
            row
            for row in rows
            if float(row["tabm_process_score"]) >= float(row["tabm_process_threshold"])
        ]
        reinflated = [
            row
            for row in rows
            if truthy(row[f"hard__{PRIMARY}"]) and not truthy(row["frozen_ckbq_hard"])
        ]
        rescue[family] = {
            "benign_rows": len(rows),
            "process_trigger_rate": len(triggered) / len(rows) if rows else None,
            "reinflated_vs_frozen_rate": len(reinflated) / len(rows) if rows else None,
        }
    result["rescue_branch_on_held_ood"] = rescue

    family_map: dict[str, dict] = {}
    for row in preservation:
        if row["metric"] != "attack_family_recall":
            continue
        family = row["attack_family"]
        entry = family_map.setdefault(
            family, {"mechanism": family_mechanism(family), "rows": int(float(row["rows"]))}
        )
        if row["candidate"] in (C1, FROZEN, PRIMARY):
            entry[row["candidate"]] = float(row["hard_recall"])
    for entry in family_map.values():
        if C1 in entry and PRIMARY in entry:
            entry["final_minus_c1_pp"] = round((entry[PRIMARY] - entry[C1]) * 100.0, 3)
        if FROZEN in entry and PRIMARY in entry:
            entry["rescued_from_frozen_pp"] = round(
                (entry[PRIMARY] - entry[FROZEN]) * 100.0, 3
            )
    result["family_rescue_map"] = family_map
    return result


def render(result: dict) -> str:
    out = io.StringIO()
    out.write(f"# CKBV seed-27 pullback analysis\nrun_root: {result['run_root']}\n")
    out.write(f"phase: {result.get('current_phase', 'MISSING')}\n")
    out.write(
        f"official decision: {result['official_decision']} | independent recheck: "
        f"{result['independent_decision']} | match: {result['matches_official']}\n"
    )
    out.write(f"overall attack delta vs C1: {result['overall_attack_delta_pp']:+.3f} pp\n")
    out.write("\n## independent checks\n")
    for name, value in result["independent_checks"].items():
        out.write(f"- [{'PASS' if value else 'FAIL'}] {name}\n")
    out.write("\n## held benign-OOD families (final vs C1 vs frozen-CKBQ)\n")
    for family, entry in result["held_families"].items():
        out.write(
            f"- {family}: final {entry['final_hard_rate']:.4f} | C1 "
            f"{entry['c1_hard_rate']:.4f} | frozen {entry['frozen_ckbq_hard_rate']} | "
            f"improve5pp={entry['improves_5pp']} le90={entry['at_most_90pct']}\n"
        )
    out.write("\n## process-head separation by mechanism (GLOBAL protocol)\n")
    for mechanism, entry in result["mechanism_separation"].items():
        tabm = entry["tabm_auroc"]
        out.write(
            f"- {mechanism}: rows={entry['attack_rows']} tabm_auroc="
            f"{tabm if tabm is None else round(tabm, 4)} extra_auroc="
            f"{entry['extra_auroc'] if entry['extra_auroc'] is None else round(entry['extra_auroc'], 4)}\n"
        )
    out.write("\n## rescue-branch trigger on held benign OOD\n")
    for family, entry in result["rescue_branch_on_held_ood"].items():
        out.write(
            f"- {family}: benign_rows={entry['benign_rows']} process_trigger="
            f"{entry['process_trigger_rate']} reinflated={entry['reinflated_vs_frozen_rate']}\n"
        )
    out.write("\n## family rescue map (hard recall)\n")
    for family, entry in sorted(result["family_rescue_map"].items()):
        out.write(
            f"- {family} [{entry.get('mechanism')}] rows={entry['rows']}: "
            f"C1={entry.get(C1)} frozen={entry.get(FROZEN)} final={entry.get(PRIMARY)} "
            f"final-C1={entry.get('final_minus_c1_pp')}pp "
            f"rescued={entry.get('rescued_from_frozen_pp')}pp\n"
        )
    if result["problems"]:
        out.write("\n## problems\n")
        for problem in result["problems"]:
            out.write(f"- {problem}\n")
    return out.getvalue()


def write_fixture(root: Path) -> None:
    """Synthetic minimal run root for --selftest."""

    def dump(name: str, rows: list[dict], gz: bool = False) -> None:
        fields = list(rows[0].keys())
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        data = buffer.getvalue().encode("utf-8")
        if gz:
            with gzip.open(root / name, "wb") as handle:
                handle.write(data)
        else:
            (root / name).write_bytes(data)

    (root / "current_phase.txt").write_text("phase=complete", encoding="utf-8")
    (root / "ckbu_single_seed_go_no_go.json").write_text(
        json.dumps({"decision": "NO_GO", "checks": {"demo": False}}), encoding="utf-8"
    )
    preservation = [
        {
            "candidate": PRIMARY, "metric": "overall_attack_hard_recall", "rows": "1000",
            "hard_recall": "0.905", "c1_hard_recall": "0.913", "delta_vs_c1_pp": "-0.8",
            "attack_family": "",
        }
    ]
    for candidate, recall in ((C1, "0.97"), (FROZEN, "0.75"), (PRIMARY, "0.94")):
        preservation.append(
            {
                "candidate": candidate, "metric": "attack_family_recall", "rows": "40",
                "hard_recall": recall, "c1_hard_recall": "0.97",
                "delta_vs_c1_pp": str(round((float(recall) - 0.97) * 100, 3)),
                "attack_family": "TCP Scan",
            }
        )
    dump("attack_preservation_summary.csv", preservation)
    level2 = []
    for family in HELD_FAMILIES:
        for candidate, rate in ((C1, "1.0"), (FROZEN, "0.2"), (PRIMARY, "0.3")):
            level2.append(
                {
                    "candidate": candidate, "held_value": family, "rows": "100",
                    "metric": "benign_ood_hard_rate", "hard_rate": rate,
                    "c1_hard_rate": "1.0", "delta_vs_c1_pp": "0",
                }
            )
    dump("strict_level2_summary.csv", level2)
    dump(
        "ckbu_candidate_selection.csv",
        [{
            "candidate": HEAD, "held_value": GLOBAL, "selected": "True",
            "gate_constraint_pass": "True", "process_threshold": "0.7",
        }],
    )
    dump(
        "ckbu_support_training_usage.csv",
        [
            {"candidate": HEAD, "uid": str(index), "used_at_least_once_each_epoch": "True"}
            for index in range(385)
        ],
    )
    dump(
        "ckbu_protocol_scope_audit.csv",
        [{"held_value": GLOBAL, "report_fit_use_count": "0", "report_select_use_count": "0"}],
    )
    dump("ckbu_review_audit.csv", [{"review_count": "0", "review_rate": "0.0"}])
    dump("ckbu_role_usage_audit.csv", [{"target_alignment_incomplete": "0"}])
    predictions = []
    for index in range(60):
        attack = index < 20
        predictions.append(
            {
                "held_value": GLOBAL, "role": "future_query", "attack_family":
                    "TCP Scan" if attack else "", "label_metric_only": "1" if attack else "0",
                "c1_hard": "True", "frozen_ckbq_hard": "False",
                "extra_process_score": str(0.9 if attack else 0.1 + index * 0.001),
                "extra_process_threshold": "0.7",
                "tabm_process_score": str(0.95 if attack else 0.05 + index * 0.001),
                "tabm_process_threshold": "0.7",
                f"hard__{PRIMARY}": "True" if attack else "False",
            }
        )
    for family in HELD_FAMILIES:
        for index in range(50):
            predictions.append(
                {
                    "held_value": family, "role": "ood_val", "attack_family": "",
                    "label_metric_only": "0", "c1_hard": "True",
                    "frozen_ckbq_hard": "False",
                    "extra_process_score": "0.1", "extra_process_threshold": "0.7",
                    "tabm_process_score": "0.9" if index < 5 else "0.1",
                    "tabm_process_threshold": "0.7",
                    f"hard__{PRIMARY}": "True" if index < 5 else "False",
                }
            )
    dump("ckbu_record_predictions.csv.gz", predictions, gz=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_fixture(root)
            result = analyze(root)
            expectations = [
                result["independent_decision"] == "NO_GO",
                result["independent_checks"]["overall_delta_at_least_minus_0.5pp"] is False,
                result["independent_checks"]["held_improve_5pp_and_at_most_90pct"] is True,
                result["independent_checks"]["support_385_all_used"] is True,
                result["mechanism_separation"]["scan"]["attack_rows"] == 20,
                result["mechanism_separation"]["scan"]["tabm_auroc"] == 1.0,
                abs(
                    result["rescue_branch_on_held_ood"][HELD_FAMILIES[0]][
                        "process_trigger_rate"
                    ]
                    - 0.1
                ) < 1e-9,
                result["family_rescue_map"]["TCP Scan"]["rescued_from_frozen_pp"] == 19.0,
            ]
            if not all(expectations):
                print(f"SELFTEST_FAIL {expectations}", file=sys.stderr)
                return 2
            print(render(result))
            print("SELFTEST_OK")
            return 0
    if not args.run_root:
        parser.error("--run-root is required unless --selftest")
    result = analyze(Path(args.run_root))
    report = render(result)
    print(report)
    if args.out:
        Path(args.out).write_text(
            json.dumps(result, indent=1, sort_keys=True), encoding="utf-8"
        )
        print(f"json written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
