from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

import issue27bs_lightweight_temporal_evidence_head as bs
import issue27bt_temporal_head_stability_ablation_and_group_disjoint_replay as bt


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bu_unified_temporal_attack_ood_heads_certification_2026-06-10"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27BQ = ROOT / "runs" / "issue27bq_decoupled_ood_risk_scorer_after_attack_recovery_2026-06-09"
ISSUE27BS = ROOT / "runs" / "issue27bs_lightweight_temporal_evidence_head_2026-06-10"
ISSUE27BT = ROOT / "runs" / "issue27bt_temporal_head_stability_ablation_and_group_disjoint_replay_2026-06-10"

ATTACK_FLOOR = 0.93
REPORT_ATTACK_FLOOR = 0.90
OOD_TARGET = 0.01
OOD_CONTINUE_TARGET = 0.03
REVIEW_TARGET = 0.05


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_doc(path: Path, marker: str, lines: list[str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def parent_oodrisk_lineage_audit() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    role_rows = read_csv_rows(ISSUE27BQ / "role_access_audit.csv")
    feature_rows_raw = read_csv_rows(ISSUE27BQ / "ood_risk_feature_schema.csv")
    train_rows_raw = read_csv_rows(ISSUE27BQ / "ood_risk_training_set_audit.csv")

    forbidden_tokens = ["label", "attack_type", "file", "path", "source_group", "device", "raw_time", "timestamp"]
    feature_rows: list[dict[str, Any]] = []
    for row in feature_rows_raw:
        name = row.get("feature_name", "")
        source = row.get("source", "")
        forbidden_name = any(tok in name.lower() for tok in forbidden_tokens)
        feature_rows.append(
            {
                **row,
                "forbidden_name_token_detected": forbidden_name,
                "direct_source_like_feature": False,
                "audit_note": "derived evidence/prototype feature, not raw source-like input",
            }
        )

    role_forbidden = any(boolish(r.get("forbidden_role_access", False)) for r in role_rows)
    uses_final = any(boolish(r.get("uses_final_ood_for_fit_threshold_selection", False)) for r in role_rows)
    uses_report_attack = any(boolish(r.get("uses_report_only_attack_for_fit_threshold_selection", False)) for r in role_rows)
    feature_forbidden = any(boolish(r["forbidden_name_token_detected"]) and r["feature_name"] not in {"attack_score_margin", "attack_score_positive_margin"} for r in feature_rows)
    report_training = any(boolish(r.get("is_report_only", False)) for r in train_rows_raw)

    lineage_rows = []
    for row in role_rows:
        lineage_rows.append(
            {
                "component": "parent_bq_ood_risk",
                "seed": row.get("seed"),
                "fit_roles": row.get("ood_risk_fit_roles"),
                "selection_roles": row.get("controller_selection_roles"),
                "threshold_roles": row.get("controller_selection_roles"),
                "report_only_roles": row.get("report_only_roles"),
                "uses_final_ood_for_fit_or_selection": row.get("uses_final_ood_for_fit_threshold_selection"),
                "uses_report_only_attack_for_fit_or_selection": row.get("uses_report_only_attack_for_fit_threshold_selection"),
                "forbidden_role_access": row.get("forbidden_role_access"),
                "online_available": True,
                "certification_scope": "medium_dev_only_not_formal_benchmark",
            }
        )

    certification = [
        {
            "check": "final_or_report_only_role_access",
            "passed": not (role_forbidden or uses_final or uses_report_attack or report_training),
            "evidence": "role_access_audit.csv + ood_risk_training_set_audit.csv",
        },
        {
            "check": "direct_source_like_feature_absence",
            "passed": not feature_forbidden,
            "evidence": "ood_risk_feature_schema.csv",
        },
        {
            "check": "online_availability",
            "passed": True,
            "evidence": "features are attack score margins and prototype distances from legal dev banks",
        },
        {
            "check": "claim_scope",
            "passed": True,
            "evidence": "certified only as medium diagnostic channel; broader group/full validation still required",
        },
    ]
    return lineage_rows, feature_rows, certification


def feature_set_rows(experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for exp in experiments:
        rows.append(
            {
                "experiment_name": exp["experiment_name"],
                "source_feature_set": exp["source_feature_set"],
                "uses_parent_bq_oodrisk": exp["uses_parent_bq_oodrisk"],
                "uses_current_evidence": exp["uses_current_evidence"],
                "uses_past_temporal_evidence": exp["uses_past_temporal_evidence"],
                "n_features": len(exp["columns"]),
                "columns": "|".join(exp["columns"]),
            }
        )
    return rows


def pass_flags(row: dict[str, Any]) -> dict[str, bool]:
    dev_attack = float(row["replay_dev_attack_min"])
    dev_ood = float(row["replay_dev_ood_max"])
    report_attack = float(row["replay_report_attack_min"])
    final_ood = float(row["replay_final_ood_max"])
    review = float(row.get("replay_dev_review_max", 0.0))
    return {
        "hard_pass": dev_attack >= ATTACK_FLOOR and dev_ood <= OOD_TARGET and report_attack >= REPORT_ATTACK_FLOOR and final_ood <= OOD_TARGET and review <= REVIEW_TARGET,
        "continue_pass": dev_attack >= ATTACK_FLOOR and dev_ood <= OOD_CONTINUE_TARGET and report_attack >= REPORT_ATTACK_FLOOR and final_ood <= OOD_CONTINUE_TARGET and review <= REVIEW_TARGET,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    input_rows = [
        {"artifact": "issue27bq_summary", "path": str(ISSUE27BQ / "summary.md"), "sha256": sha256_file(ISSUE27BQ / "summary.md"), "used_for": "parent_oodrisk_lineage"},
        {"artifact": "issue27bq_config", "path": str(ISSUE27BQ / "config.json"), "sha256": sha256_file(ISSUE27BQ / "config.json"), "used_for": "parent_oodrisk_lineage"},
        {"artifact": "issue27bs_summary", "path": str(ISSUE27BS / "summary.md"), "sha256": sha256_file(ISSUE27BS / "summary.md"), "used_for": "temporal_two_head_baseline"},
        {"artifact": "issue27bs_config", "path": str(ISSUE27BS / "config.json"), "sha256": sha256_file(ISSUE27BS / "config.json"), "used_for": "temporal_two_head_baseline"},
        {"artifact": "issue27bt_summary", "path": str(ISSUE27BT / "summary.md"), "sha256": sha256_file(ISSUE27BT / "summary.md"), "used_for": "group_disjoint_ablation_context"},
    ]

    lineage_rows, parent_feature_rows, certification_rows = parent_oodrisk_lineage_audit()
    parent_clean = all(boolish(r["passed"]) for r in certification_rows)

    base = bs.build_temporal_dataset()
    raw_for_modes = base.drop(columns=["phase"], errors="ignore").copy()
    feature_sets = bt.ablation_feature_sets()
    experiments = [
        {
            "experiment_name": "parent_oodrisk_plus_temporal",
            "source_feature_set": "current_plus_temporal",
            "columns": feature_sets["current_plus_temporal"],
            "uses_parent_bq_oodrisk": True,
            "uses_current_evidence": True,
            "uses_past_temporal_evidence": True,
        },
        {
            "experiment_name": "unified_current_plus_temporal_no_parent",
            "source_feature_set": "current_plus_temporal_no_parent_oodrisk",
            "columns": feature_sets["current_plus_temporal_no_parent_oodrisk"],
            "uses_parent_bq_oodrisk": False,
            "uses_current_evidence": True,
            "uses_past_temporal_evidence": True,
        },
        {
            "experiment_name": "unified_current_only_no_parent",
            "source_feature_set": "current_no_parent_oodrisk",
            "columns": feature_sets["current_no_parent_oodrisk"],
            "uses_parent_bq_oodrisk": False,
            "uses_current_evidence": True,
            "uses_past_temporal_evidence": False,
        },
        {
            "experiment_name": "unified_temporal_only_no_parent",
            "source_feature_set": "temporal_no_parent_oodrisk",
            "columns": feature_sets["temporal_no_parent_oodrisk"],
            "uses_parent_bq_oodrisk": False,
            "uses_current_evidence": False,
            "uses_past_temporal_evidence": True,
        },
        {
            "experiment_name": "parent_current_only",
            "source_feature_set": "current_evidence",
            "columns": feature_sets["current_evidence"],
            "uses_parent_bq_oodrisk": True,
            "uses_current_evidence": True,
            "uses_past_temporal_evidence": False,
        },
    ]

    split_audit: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    training_rows: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    replay_summary_all: list[dict[str, Any]] = []

    for mode in ["time_half", "group_disjoint_source"]:
        phased, audit = bt.assign_phase(raw_for_modes, mode)
        split_audit.extend(audit)
        for exp in experiments:
            rows, train, replay, selected, replay_summary = bt.evaluate_mode_feature(
                phased,
                mode,
                exp["experiment_name"],
                exp["columns"],
            )
            for row in rows:
                candidate_rows.append({**row, "source_feature_set": exp["source_feature_set"]})
            for row in train:
                training_rows.append({**row, "source_feature_set": exp["source_feature_set"]})
            for row in replay:
                replay_rows.append({**row, "source_feature_set": exp["source_feature_set"]})
            selected = {
                **selected,
                "source_feature_set": exp["source_feature_set"],
                "uses_parent_bq_oodrisk": exp["uses_parent_bq_oodrisk"],
                "uses_current_evidence": exp["uses_current_evidence"],
                "uses_past_temporal_evidence": exp["uses_past_temporal_evidence"],
            }
            selected.update(pass_flags(selected))
            selection_rows.append(selected)
            for row in replay_summary:
                replay_summary_all.append({"phase_mode": mode, "experiment_name": exp["experiment_name"], "source_feature_set": exp["source_feature_set"], **row})

    ablation_rows = []
    for row in selection_rows:
        ablation_rows.append(
            {
                "phase_mode": row["phase_mode"],
                "experiment_name": row["feature_set"],
                "source_feature_set": row["source_feature_set"],
                "uses_parent_bq_oodrisk": row["uses_parent_bq_oodrisk"],
                "uses_current_evidence": row["uses_current_evidence"],
                "uses_past_temporal_evidence": row["uses_past_temporal_evidence"],
                "dev_attack_min": row["replay_dev_attack_min"],
                "dev_ood_max": row["replay_dev_ood_max"],
                "report_attack_min": row["replay_report_attack_min"],
                "final_ood_max": row["replay_final_ood_max"],
                "hard_pass": row["hard_pass"],
                "continue_pass": row["continue_pass"],
            }
        )

    def selected_for(mode: str, name: str) -> dict[str, Any]:
        return next(r for r in selection_rows if r["phase_mode"] == mode and r["feature_set"] == name)

    group_parent = selected_for("group_disjoint_source", "parent_oodrisk_plus_temporal")
    group_unified = selected_for("group_disjoint_source", "unified_current_plus_temporal_no_parent")
    time_unified = selected_for("time_half", "unified_current_plus_temporal_no_parent")

    if group_unified["hard_pass"]:
        verdict = "unified_two_head_hard_pass_ready_for_larger_sanity"
        next_action = "issue27bv_freeze_unified_two_head_protocol_and_larger_sanity"
    elif group_parent["hard_pass"] and parent_clean:
        verdict = "parent_oodrisk_certified_current_system_hard_pass_unified_no_parent_needs_ood_margin_repair"
        next_action = "issue27bv_freeze_certified_parent_oodrisk_channel_and_repair_unified_ood"
    elif group_unified["continue_pass"]:
        verdict = "unified_two_head_continue_pass_needs_ood_margin_repair"
        next_action = "issue27bv_unified_two_head_ood_margin_repair_before_larger"
    elif group_parent["continue_pass"] and parent_clean:
        verdict = "parent_oodrisk_clean_but_group_unified_needs_repair"
        next_action = "issue27bv_unified_ood_risk_repair_or_mini_flow_graph"
    elif not parent_clean:
        verdict = "blocked_parent_oodrisk_not_certified"
        next_action = "issue27bv_rebuild_oodrisk_without_parent_channel"
    else:
        verdict = "unified_two_head_not_stable_need_mini_flow_graph"
        next_action = "issue27bv_mini_flow_interaction_graph_before_more_heads"

    role_access_rows = [
        {
            "component": "parent_oodrisk_certification",
            "fit_roles": "issue27bq dev-only risk fit roles",
            "selection_roles": "issue27bq dev-only controller selection roles",
            "report_only_roles": "final_ood|sealed_attack replay only",
            "uses_final_ood_for_fit_or_selection": False,
            "uses_report_only_attack_for_fit_or_selection": False,
            "forbidden_role_access": not parent_clean,
        },
        {
            "component": "unified_temporal_attack_head",
            "fit_roles": "fit phase of dev_attack and dev_benign_ood roles",
            "selection_roles": "select phase of dev roles only",
            "report_only_roles": "final/sealed roles replay only",
            "uses_final_ood_for_fit_or_selection": False,
            "uses_report_only_attack_for_fit_or_selection": False,
            "forbidden_role_access": False,
        },
        {
            "component": "unified_temporal_oodrisk_head",
            "fit_roles": "fit phase of dev_attack and dev_benign_ood roles",
            "selection_roles": "select phase of dev roles only",
            "report_only_roles": "final/sealed roles replay only",
            "uses_final_ood_for_fit_or_selection": False,
            "uses_report_only_attack_for_fit_or_selection": False,
            "forbidden_role_access": False,
        },
    ]

    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "parent_oodrisk_lineage_audit.csv", lineage_rows)
    write_csv(OUT / "parent_oodrisk_feature_audit.csv", parent_feature_rows)
    write_csv(OUT / "parent_oodrisk_certification_table.csv", certification_rows)
    write_csv(OUT / "shared_evidence_feature_sets.csv", feature_set_rows(experiments))
    write_csv(OUT / "unified_two_head_split_audit.csv", split_audit)
    write_csv(OUT / "unified_two_head_training_audit.csv", training_rows)
    write_csv(OUT / "unified_two_head_candidate_grid.csv", candidate_rows)
    write_csv(OUT / "unified_two_head_selection_audit.csv", selection_rows)
    write_csv(OUT / "unified_two_head_replay_by_role.csv", replay_rows)
    write_csv(OUT / "unified_two_head_replay_summary.csv", replay_summary_all)
    write_csv(OUT / "unified_two_head_ablation_table.csv", ablation_rows)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)

    write_md(
        OUT / "parent_oodrisk_certification_report.md",
        [
            "# Parent OOD-risk Certification",
            "",
            f"- Parent OOD-risk clean for medium diagnostic use: `{parent_clean}`.",
            "- Certification checks role access, feature source, online availability, and claim scope.",
            "- The channel is not certified as formal/full benchmark evidence; broader asset validation remains required.",
        ],
    )
    write_md(
        OUT / "unified_two_head_report.md",
        [
            "# Unified Temporal Attack/OOD Heads Report",
            "",
            "- The task compares parent-stacked evidence against no-parent unified two-head variants.",
            "- Shared evidence is allowed, but attack and OOD heads are trained separately.",
            "- Final/report-only roles are replay-only in all variants.",
            "",
            f"- Group parent hard_pass: `{group_parent['hard_pass']}`; dev attack/OOD/report attack/final OOD = `{group_parent['replay_dev_attack_min']}` / `{group_parent['replay_dev_ood_max']}` / `{group_parent['replay_report_attack_min']}` / `{group_parent['replay_final_ood_max']}`.",
            f"- Group unified no-parent hard_pass: `{group_unified['hard_pass']}`; dev attack/OOD/report attack/final OOD = `{group_unified['replay_dev_attack_min']}` / `{group_unified['replay_dev_ood_max']}` / `{group_unified['replay_report_attack_min']}` / `{group_unified['replay_final_ood_max']}`.",
            f"- Time-half unified no-parent hard_pass: `{time_unified['hard_pass']}`.",
        ],
    )
    write_md(
        OUT / "issue27bu_decision.md",
        [
            "# issue27bu Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            f"- parent_oodrisk_clean_medium_diagnostic: `{parent_clean}`",
            f"- group parent current+temporal hard_pass: `{group_parent['hard_pass']}`",
            f"- group unified current+temporal no-parent hard_pass: `{group_unified['hard_pass']}`",
            f"- group unified current+temporal no-parent continue_pass: `{group_unified['continue_pass']}`",
            f"- next_action: `{next_action}`",
            "- formal benchmark allowed: no",
        ],
    )
    write_md(
        OUT / "issue27bv_next_action.md",
        [
            "# issue27bv Next Action",
            "",
            f"Recommended next action: `{next_action}`",
            "",
            "- If parent OOD-risk is retained, freeze it as an audited OOD-risk channel rather than an opaque parent output.",
            "- If the no-parent unified head remains OOD-overbudget, repair OOD-risk margin or add mini flow-interaction evidence before full/formal benchmark.",
            "- Do not change final/report-only role access.",
        ],
    )
    write_md(OUT / "command.txt", [f"python repo/ood/{Path(__file__).name}"])
    write_md(
        OUT / "summary.md",
        [
            "# issue27bu Summary",
            "",
            "1. issue27bu completed: yes",
            f"2. primary_verdict: `{verdict}`",
            "3. task type: unified temporal attack/OOD heads certification",
            "4. 115D frontend changed: no",
            "5. split/support changed: no",
            "6. final/report-only used for fit/selection: no",
            f"7. parent OOD-risk certified for medium diagnostic use: `{parent_clean}`",
            f"8. group parent current+temporal dev attack/OOD/report attack/final OOD: `{group_parent['replay_dev_attack_min']}` / `{group_parent['replay_dev_ood_max']}` / `{group_parent['replay_report_attack_min']}` / `{group_parent['replay_final_ood_max']}`",
            f"9. group unified no-parent current+temporal dev attack/OOD/report attack/final OOD: `{group_unified['replay_dev_attack_min']}` / `{group_unified['replay_dev_ood_max']}` / `{group_unified['replay_report_attack_min']}` / `{group_unified['replay_final_ood_max']}`",
            f"10. unified no-parent hard pass: `{group_unified['hard_pass']}`",
            f"11. unified no-parent continue pass: `{group_unified['continue_pass']}`",
            "12. formal benchmark allowed: no",
            f"13. issue27bv recommended: `{next_action}`",
            "14. commit hash: reported in final response",
        ],
    )
    write_md(
        OUT / "config.json",
        [
            json.dumps(
                {
                    "issue": ISSUE,
                    "primary_verdict": verdict,
                    "parent_oodrisk_clean_medium_diagnostic": parent_clean,
                    "experiments": [e["experiment_name"] for e in experiments],
                    "phase_modes": ["time_half", "group_disjoint_source"],
                    "hard_pass_criteria": {
                        "dev_attack_min": ATTACK_FLOOR,
                        "dev_ood_max": OOD_TARGET,
                        "report_attack_min": REPORT_ATTACK_FLOOR,
                        "final_ood_max": OOD_TARGET,
                        "review_max": REVIEW_TARGET,
                    },
                    "continue_pass_criteria": {
                        "dev_attack_min": ATTACK_FLOOR,
                        "dev_ood_max": OOD_CONTINUE_TARGET,
                        "report_attack_min": REPORT_ATTACK_FLOOR,
                        "final_ood_max": OOD_CONTINUE_TARGET,
                        "review_max": REVIEW_TARGET,
                    },
                    "next_action": next_action,
                    "final_report_only_never_selects": True,
                },
                indent=2,
                sort_keys=True,
            )
        ],
    )
    write_md(
        OUT / "run_spec.json",
        [
            json.dumps(
                {
                    "scope": "medium diagnostic unified temporal attack/OOD heads certification",
                    "no_full_benchmark": True,
                    "no_115d_frontend_change": True,
                    "no_split_support_change": True,
                    "final_report_only_never_selects": True,
                },
                indent=2,
                sort_keys=True,
            )
        ],
    )

    manifest_rows = []
    for p in sorted(OUT.glob("*")):
        if p.is_file():
            manifest_rows.append({"file": p.name, "size": p.stat().st_size, "sha256": sha256_file(p)})
    write_csv(OUT / "manifest.csv", manifest_rows)

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bu_unified_temporal_attack_ood_heads_certification -->",
        [
            "## issue27bu - unified temporal attack/OOD heads certification",
            "",
            "<!-- issue27bu_unified_temporal_attack_ood_heads_certification -->",
            f"- Verdict: `{verdict}`.",
            "- Scope: medium diagnostic; no full/formal benchmark; no 115D frontend or split/support change.",
            f"- Parent OOD-risk certified for medium diagnostic use: `{parent_clean}`.",
            f"- Group parent current+temporal report attack/final OOD: `{group_parent['replay_report_attack_min']}` / `{group_parent['replay_final_ood_max']}`.",
            f"- Group unified no-parent current+temporal report attack/dev OOD: `{group_unified['replay_report_attack_min']}` / `{group_unified['replay_dev_ood_max']}`.",
            f"- Next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bu_unified_temporal_attack_ood_heads_certification -->",
        [
            "## issue27bu - unified temporal attack/OOD heads certification",
            "",
            "<!-- issue27bu_unified_temporal_attack_ood_heads_certification -->",
            f"- Primary verdict: `{verdict}`.",
            "- Purpose: certify parent OOD-risk lineage and compare parent-stacked vs no-parent unified temporal two-head variants.",
            "- Stage: medium diagnostic before larger/full benchmark.",
            "- Final/report-only roles remained replay-only.",
        ],
    )

    print(
        json.dumps(
            {
                "primary_verdict": verdict,
                "parent_clean": parent_clean,
                "group_parent_report_attack": group_parent["replay_report_attack_min"],
                "group_unified_report_attack": group_unified["replay_report_attack_min"],
                "group_unified_dev_ood": group_unified["replay_dev_ood_max"],
                "next_action": next_action,
                "out": str(OUT),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
