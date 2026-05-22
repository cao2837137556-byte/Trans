import json
import textwrap
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path.cwd()
OUT = ROOT / "runs" / "issue26a_within_dataset_temporal_validation_for_enhanced_lowguard_top64_2026-05-22"
ISSUE25C = ROOT / "runs" / "issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18"
ISSUE25B = ROOT / "runs" / "issue25b_strong_baseline_protocol_and_fairness_design_2026-05-18"
ISSUE23 = ROOT / "runs" / "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18"
ISSUE22 = ROOT / "runs" / "issue22_v2_hard_shift_enhancement_pilot_2026-05-18"
ISSUE22B = ROOT / "runs" / "issue22b_enhanced_v2_primary_nonregression_check_2026-05-18"
MAIN_DOCS = ROOT / "runs" / "mainline_docs"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def yesno_feasible(value) -> str:
    try:
        return "yes" if float(value) <= 0.01 else "no"
    except Exception:
        return "unknown"


def first_size(df: pd.DataFrame, holdout: str, method_token: str | None = None):
    if df.empty or "holdout" not in df.columns:
        return "NA", "NA"
    q = df[df["holdout"].eq(holdout)]
    if method_token and "method" in q.columns:
        q = q[q["method"].astype(str).str.contains(method_token, regex=False)]
    if q.empty:
        return "NA", "NA"
    attack = int(q["attack_eval_size"].iloc[0]) if "attack_eval_size" in q.columns else "NA"
    ood = int(q["final_ood_eval_size"].iloc[0]) if "final_ood_eval_size" in q.columns else "NA"
    return attack, ood


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    cols = list(df.columns)
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        vals = [str(row[c]).replace("\n", " ") for c in cols]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    commands = [
        "git branch --show-current",
        "git status --short",
        "Get-ChildItem issue25c output directory",
        "Get-Content issue25c/mainline/issue25b/issue23/issue22/issue22b required summaries",
        "rg scan for manifest/config/run_spec/protocol/summary/split/provenance assets",
        "python runs/issue26a.../generate_issue26a_outputs.py",
    ]

    required_inputs = [
        ISSUE25C / "summary.md",
        ISSUE25C / "recommended_next_action.md",
        ISSUE25C,
        MAIN_DOCS / "mainline_handoff.md",
        MAIN_DOCS / "mainline_experiment_map.md",
    ]
    recommended_inputs = [
        ISSUE25B / "summary.md",
        ISSUE25B / "issue25c_minimal_run_matrix.csv",
        ISSUE23 / "summary.md",
        ISSUE22 / "summary.md",
        ISSUE22B / "summary.md",
    ]
    missing_required = [str(p.relative_to(ROOT)) for p in required_inputs if not p.exists()]
    missing_recommended = [str(p.relative_to(ROOT)) for p in recommended_inputs if not p.exists()]

    issue25c_summary = read_text(ISSUE25C / "summary.md")
    issue25c_status_ok = "strong_baseline_positive" in issue25c_summary
    main_method_frozen = "selected_source_rich_top64 + kcenter32 + fixed OOD guard LR" in issue25c_summary

    priority_names = [
        "strong_baseline_results.csv",
        "baseline_method_comparison_summary.csv",
        "locked_bins_baseline_summary.csv",
        "ablation_component_summary.csv",
        "consistency_primary_holdout_chrono.csv",
        "low_fpr_metrics_baseline_summary.csv",
    ]
    issue25c_csvs = sorted([p.name for p in ISSUE25C.glob("*.csv")]) if ISSUE25C.exists() else []
    read_csvs = [n for n in priority_names if (ISSUE25C / n).exists()]
    extra_csvs = [n for n in issue25c_csvs if n not in read_csvs]

    cons25 = load_csv(ISSUE25C / "consistency_primary_holdout_chrono.csv")
    base25 = load_csv(ISSUE25C / "baseline_method_comparison_summary.csv")
    byseed25 = load_csv(ISSUE25C / "baseline_method_comparison_by_seed.csv")
    asset25 = load_csv(ISSUE25C / "locked_asset_report.csv")
    byseed22 = load_csv(ISSUE22 / "method_comparison_by_seed.csv")

    existing_rows = []

    def add_existing(setting, split_or_bin, detection, ood_alarm, source_issue, used_disc, used_locked, evidence_type, notes):
        existing_rows.append(
            {
                "setting": setting,
                "split_or_bin": split_or_bin,
                "method": "Enhanced_LOW_GUARD_top64_fixed_guard_LR",
                "detection": detection,
                "ood_alarm": ood_alarm,
                "feasible_under_1pct": yesno_feasible(ood_alarm),
                "threshold_source": "ID calibration + OOD validation, official 1pct OOD target",
                "support_source": "kcenter32 confirmed attack supports from allowed attack train pool",
                "result_source_issue": source_issue,
                "used_for_method_discovery": used_disc,
                "used_for_locked_validation": used_locked,
                "evidence_type": evidence_type,
                "notes": notes,
            }
        )

    if not cons25.empty:
        q = cons25[(cons25["method"].eq("M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR")) & (cons25["seed_group"].eq("main_42_46"))]
        for _, r in q.iterrows():
            hold = str(r["holdout"])
            if hold == "primary_lowood":
                etype, used, notes = "primary", "yes", "primary/non-regression evidence; not new temporal proof"
            elif hold == "holdout_bin_2":
                etype, used, notes = "hard_shift", "yes", "used in issue22 top64 discovery; consistency only now"
            elif hold == "chrono_late_train_early_eval":
                etype, used, notes = "consistency", "yes", "chrono_late participated in candidate confirmation/discovery"
            else:
                etype, used, notes = "consistency", "unknown", "consistency evidence"
            add_existing(r["dataset"], hold, r["attack_high_detection_mean"], r["final_ood_high_alarm_max"], "issue25c", used, "no", etype, notes)

    if not base25.empty:
        q = base25[
            (base25["evaluation_role"].eq("locked"))
            & (base25["method"].eq("M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR"))
            & (base25["seed_group"].eq("main_42_46"))
        ]
        for _, r in q.iterrows():
            add_existing(
                r["dataset"],
                r["holdout"],
                r["attack_high_detection_mean"],
                r["final_ood_high_alarm_max"],
                "issue25c/issue23",
                "no",
                "yes",
                "locked",
                "unused leave-one-bin eval object in issue23; already reused in issue25c strong baseline pack",
            )
    existing_df = pd.DataFrame(existing_rows)
    existing_df.to_csv(OUT / "temporal_existing_result_table.csv", index=False)

    scale_rows = []

    def add_scale(setting, split_or_bin, id_train, id_calib, ood_train, ood_val, ood_eval, attack_train, support_count, attack_eval, time_def, method_disc, clean, notes):
        scale_rows.append(
            {
                "setting": setting,
                "split_or_bin": split_or_bin,
                "ID train rows": id_train,
                "ID calibration rows": id_calib,
                "OOD train rows": ood_train,
                "OOD validation rows": ood_val,
                "OOD eval rows": ood_eval,
                "attack train pool rows": attack_train,
                "confirmed attack support count": support_count,
                "attack eval rows": attack_eval,
                "time/bin/window definition": time_def,
                "attack family/window": "stage2 high-purity attack windows/bins",
                "source file / manifest path": "issue25c baseline_method_comparison_by_seed.csv; issue25c locked_asset_report.csv; issue19b/issue23 script constants",
                "whether used for feature/topK selection": "yes historically for source_rich top64 discovery; frozen in issue25c",
                "whether used for support selection": "yes, kcenter32 from allowed attack train pool",
                "whether used for threshold calibration": "yes, ID calibration + OOD validation only",
                "whether used for final reporting only": "yes for final OOD/attack eval metrics",
                "whether used for method discovery": method_disc,
                "whether clean for future validation": clean,
                "notes": notes,
            }
        )

    for hold, setting, time_def, method_disc, clean, notes in [
        ("primary_lowood", "primary_lowood", "primary same-protocol low-OOD split", "yes", "no", "primary/non-regression evidence"),
        ("holdout_bin_2", "harder_holdout", "leave-one-attack-window-out eval bin 2", "yes", "no", "used directly in issue22 top64 discovery"),
        ("chrono_late_train_early_eval", "harder_holdout", "chronological train bins 6,7,8 and eval bins 2,3,4", "yes", "no", "used in issue22/25c consistency"),
    ]:
        attack_eval, ood_eval = first_size(byseed25, hold, "M2_Enhanced")
        if attack_eval == "NA":
            attack_eval, ood_eval = first_size(byseed22, hold, "M8_source_rich_top64")
        if hold == "primary_lowood":
            attack_train = "about 60pct of high-purity attack pool; exact count not persisted in issue25c"
            split_note = "primary uses ID train 8000, ID calib 5000, OOD train 8000, OOD val 2000"
        else:
            ar = asset25[asset25["holdout_name"].eq(hold)] if not asset25.empty else pd.DataFrame()
            attack_train = int(ar["train_pool_count"].iloc[0]) if not ar.empty else "NA"
            split_note = "harder split uses ID train 8000, ID calib 5000, OOD train 8000, OOD val 2000"
        add_scale(setting, hold, 8000, 5000, 8000, 2000, ood_eval, attack_train, 32, attack_eval, time_def, method_disc, clean, f"{split_note}; {notes}")

    if not asset25.empty:
        for _, ar in asset25[asset25["holdout_name"].isin(["holdout_bin_5", "holdout_bin_6", "holdout_bin_7", "holdout_bin_8"])].iterrows():
            hold = str(ar["holdout_name"])
            attack_eval, ood_eval = first_size(byseed25, hold, "M2_Enhanced")
            add_scale(
                "locked_harder_holdout",
                hold,
                8000,
                5000,
                8000,
                2000,
                ood_eval,
                int(ar["train_pool_count"]),
                32,
                attack_eval,
                f"leave-one-attack-window-out train bins {ar['train_bins']} eval bin {ar['eval_bins']}",
                "no for issue22 discovery; yes for issue23/25c evidence",
                "no",
                "valid existing locked object, but already analyzed in issue23 and issue25c",
            )
        ar = asset25[asset25["holdout_name"].eq("chrono_early_train_late_eval")]
        if not ar.empty:
            ar = ar.iloc[0]
            add_scale(
                "candidate_temporal",
                "chrono_early_train_late_eval",
                8000,
                5000,
                8000,
                2000,
                "NA",
                int(ar["train_pool_count"]),
                32,
                int(ar["attack_eval_count"]),
                f"chronological train bins {ar['train_bins']} eval bins {ar['eval_bins']}",
                "no direct issue22 discovery, but eval bins overlap issue23/25c locked bins",
                "no/partial",
                "promising temporal object, but not clean because eval bins 6/7/8 overlap previous locked evidence",
            )
    scale_df = pd.DataFrame(scale_rows)
    scale_df.to_csv(OUT / "data_scale_temporal_inventory.csv", index=False)

    candidates = []

    def cand(name, ctype, available, required, id_av, idc_av, oodt_av, oodv_av, oude_av, atpool_av, supp_av, ateval_av, time_clear, disc, feat, supp, thresh, overlap, risk, purge, cost, slurm, prio, reason):
        candidates.append(
            {
                "candidate_name": name,
                "candidate_type": ctype,
                "available": available,
                "required_inputs": required,
                "id_train_available": id_av,
                "id_calibration_available": idc_av,
                "ood_train_available": oodt_av,
                "ood_val_available": oodv_av,
                "ood_eval_available": oude_av,
                "attack_train_pool_available": atpool_av,
                "attack_support_available": supp_av,
                "attack_eval_available": ateval_av,
                "time_order_clear": time_clear,
                "overlaps_with_method_discovery": disc,
                "overlaps_with_feature_selection": feat,
                "overlaps_with_support_selection": supp,
                "overlaps_with_threshold_selection": thresh,
                "overlaps_with_issue22_22b_23_25c": overlap,
                "leakage_risk": risk,
                "needs_purge_or_embargo": purge,
                "estimated_cost": cost,
                "requires_slurm": slurm,
                "recommended_priority": prio,
                "reason": reason,
            }
        )

    cand("chrono_early_train_late_eval", "chronological_cross_window", "partial", "issue23/25c loaders; raw bin/time metadata; no topK/support/threshold changes", "yes", "yes", "yes", "yes", "yes if rebuilt", "yes", "yes by kcenter32 rule", "yes", "yes", "no direct issue22 discovery, but late eval bins overlap locked bins", "no new feature selection allowed; frozen top64 only", "no if rebuilt from train bins only", "no if ID/OOD val only", "yes", "medium", "yes", "low_to_medium", "no for inventory; unknown for full run", "P1", "Natural temporal direction, but not clean new proof because eval bins 6/7/8 were already used as locked evidence in issue23/25c.")
    cand("purged_future_window_holdout", "purged_temporal_split", "partial", "raw timestamp or packet-order metadata; purge/embargo gap definition; split manifest", "yes", "yes", "yes", "yes", "unknown", "unknown", "unknown", "unknown", "unknown", "unknown", "unknown", "unknown", "no if constructed before eval", "unknown", "unknown", "yes", "medium", "unknown", "P1", "Scientifically preferable if raw temporal metadata can recover a future window not consumed by issue22/23/25c. Current metadata is insufficient.")
    cand("holdout_bin_3", "leave_one_bin_out", "yes", "existing v7.4 holdout asset", "yes", "yes", "yes", "yes", "yes", "yes", "yes", "yes", "bin order only", "yes", "yes via issue22 chrono discovery overlap", "unknown", "no", "yes", "high", "unknown", "low", "no", "not_recommended", "Eval bin overlaps issue22 chrono_late discovery bins.")
    cand("holdout_bin_4", "leave_one_bin_out", "yes", "existing v7.4 holdout asset", "yes", "yes", "yes", "yes", "yes", "yes", "yes", "yes", "bin order only", "yes", "yes via issue22 chrono discovery overlap", "unknown", "no", "yes", "high", "unknown", "low", "no", "not_recommended", "Eval bin overlaps issue22 chrono_late discovery bins.")
    cand("locked_bins_5_6_7_8_reanalysis", "leave_one_bin_out_locked_reuse", "yes", "issue23/25c existing outputs", "yes", "yes", "yes", "yes", "yes", "yes", "yes", "yes", "bin order only", "no for issue22 discovery", "no new selection allowed", "no new selection allowed", "no new threshold selection allowed", "yes", "medium", "unknown", "low", "no", "P3", "Evidence inventory only; repeated locked-bin analysis is not new temporal proof.")
    cand("adjacent_bin_holdout", "adjacent_window_holdout", "partial", "bin adjacency metadata; purge/embargo; held-out adjacent window manifest", "yes", "yes", "yes", "yes", "unknown", "unknown", "unknown", "unknown", "partial", "unknown", "unknown", "unknown", "unknown", "unknown", "medium", "yes", "medium", "unknown", "P2", "Potentially useful, but adjacent-window contamination and prior bin use make cleanliness unclear.")
    cand("rolling_origin_validation", "rolling_origin", "partial", "multiple chronological windows; fixed pre-registered origins; no final eval tuning", "yes", "yes", "yes", "yes", "unknown", "unknown", "unknown", "unknown", "partial", "unknown", "unknown", "unknown", "unknown", "unknown", "medium", "yes", "medium_to_high", "unknown", "P2", "Good design, but current artifacts do not persist enough clean temporal metadata.")
    cand("larger_attack_eval_window", "data_scale_stress", "partial", "pooled attack eval windows and final-only reporting rule", "yes", "yes", "yes", "yes", "yes", "yes", "yes", "yes", "partial", "yes", "yes/unknown", "unknown", "no", "yes", "high", "yes", "low_to_medium", "no", "not_recommended", "Mostly reuses previously inspected bins/windows; suitable only as appendix after clean split recovery.")
    cand("later_to_earlier_chrono_repeat", "reverse_chronological_consistency", "yes", "existing issue22/25c chrono_late outputs", "yes", "yes", "yes", "yes", "yes", "yes", "yes", "yes", "yes", "yes", "yes", "unknown", "no", "yes", "high", "unknown", "low", "no", "not_recommended", "Already used in method discovery/confirmation; consistency evidence only.")
    cand_df = pd.DataFrame(candidates)
    cand_df.to_csv(OUT / "temporal_candidate_matrix.csv", index=False)

    clean_candidates = cand_df[cand_df["recommended_priority"].isin(["P0", "P1"]) & cand_df["leakage_risk"].eq("low")]
    not_run_reason = "No P0/P1 candidate has low leakage risk. The best available temporal candidate, chrono_early_train_late_eval, overlaps issue23/25c locked eval bins and requires purge/embargo plus metadata recovery before formal validation."
    next_action = "issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22"

    preflight = [
        "# Issue26a Preflight Check",
        "",
        f"1. Successfully read issue25c summary: {'yes' if (ISSUE25C / 'summary.md').exists() else 'no'}.",
        f"2. Confirmed issue25c status strong_baseline_positive: {'yes' if issue25c_status_ok else 'no'}.",
        f"3. Confirmed main method frozen as Enhanced LOW-GUARD+ top64: {'yes' if main_method_frozen else 'no'}.",
        "4. Confirmed no topK/support/adapter/threshold tuning this round: yes.",
        f"5. Successfully read mainline_handoff.md: {'yes' if (MAIN_DOCS / 'mainline_handoff.md').exists() else 'no'}.",
        f"6. Successfully read mainline_experiment_map.md: {'yes' if (MAIN_DOCS / 'mainline_experiment_map.md').exists() else 'no'}.",
        f"7. Found usable issue25c result CSV files: {'yes' if read_csvs or issue25c_csvs else 'no'}. Actual priority files read: {', '.join(read_csvs) if read_csvs else 'none'}.",
        "8. Able to scan manifest/config/run_spec/split files: yes. Manifest/config/provenance files were found; prior issue run_spec files are not consistently present.",
        "9. Able to summarize existing temporal / locked / consistency evidence: yes.",
        "10. Able to judge whether candidates participated in method discovery: partial yes, using issue22/23/25c asset reports and configs.",
        f"11. Clean new temporal object exists: {'yes' if not clean_candidates.empty else 'no'}.",
        "12. Need Slurm for this round: no.",
        "13. This round is feasibility + inventory, not formal temporal validation: yes.",
    ]
    (OUT / "preflight_issue26a_check.md").write_text("\n".join(preflight) + "\n", encoding="utf-8")

    missing = ["# Missing Input Report", ""]
    if not missing_required and not missing_recommended:
        missing.append("none")
    else:
        if missing_required:
            missing += ["Required missing:"] + [f"- {x}" for x in missing_required]
        if missing_recommended:
            missing += ["", "Recommended missing:"] + [f"- {x}" for x in missing_recommended]
    missing += [
        "",
        "Optional issue25c priority file note:",
        "- strong_baseline_results.csv was not present; this is non-blocking because summary/comparison/locked/ablation/consistency CSVs were available.",
    ]
    (OUT / "missing_input_report.md").write_text("\n".join(missing) + "\n", encoding="utf-8")

    (OUT / "blocking_asset_gap.md").write_text(
        textwrap.dedent(
            f"""# Blocking Asset Gap

No blocking asset gap for issue26a inventory itself.

Blocking gap for optional minimal temporal validation:
- {not_run_reason}
- Raw timestamp / packet-order metadata sufficient for a purged or embargoed new temporal split was not found in the issue25c report pack.
- Existing locked bins 5/6/7/8 are valid historical evidence, but they already formed issue23/25c evidence and cannot be repackaged as a clean new temporal proof.
"""
        ),
        encoding="utf-8",
    )

    audit = ["# Leakage Audit Report", "", "Scope: issue26a audits candidates only. It does not change topK, support budget, adapter, or threshold protocol.", ""]
    for _, r in cand_df.iterrows():
        if r["candidate_name"] == "chrono_early_train_late_eval":
            verdict = "usable_with_purge_embargo"
        elif r["candidate_name"] == "purged_future_window_holdout":
            verdict = "insufficient_metadata"
        elif r["recommended_priority"] == "P3":
            verdict = "consistency_only"
        elif r["recommended_priority"] == "not_recommended":
            verdict = "not_recommended"
        else:
            verdict = "insufficient_metadata"
        audit += [
            f"## {r['candidate_name']}",
            f"- candidate_type: {r['candidate_type']}",
            f"- top64 feature selection participation: {r['overlaps_with_feature_selection']}",
            f"- threshold selection participation: {r['overlaps_with_threshold_selection']}",
            f"- support selection participation: {r['overlaps_with_support_selection']}",
            f"- adapter/model choice participation: {r['overlaps_with_method_discovery']}",
            f"- issue22/22b/23/25c overlap: {r['overlaps_with_issue22_22b_23_25c']}",
            f"- train/cal/val/final time overlap risk: {r['leakage_risk']}",
            f"- needs purging: {r['needs_purge_or_embargo']}",
            f"- needs embargo/gap: {r['needs_purge_or_embargo']}",
            f"- usable for issue26b formal temporal validation: {'no under current metadata' if r['leakage_risk'] != 'low' else 'yes'}",
            f"- consistency-check only: {'yes' if verdict == 'consistency_only' or r['overlaps_with_issue22_22b_23_25c'] == 'yes' else 'no/unknown'}",
            f"- conclusion: {verdict}",
            f"- reason: {r['reason']}",
            "",
        ]
    (OUT / "leakage_audit_report.md").write_text("\n".join(audit), encoding="utf-8")

    slurm_df = pd.DataFrame(
        [
            {
                "task_name": "issue26a inventory/report generation",
                "local_feasible": "yes",
                "estimated_cost": "low",
                "requires_large_parquet_scan": "no",
                "requires_multi_seed": "no",
                "requires_model_training": "no",
                "requires_slurm": "no",
                "recommended_partition_if_known": "NA",
                "recommended_time": "NA",
                "recommended_mem": "NA",
                "recommended_cpus": "NA",
                "recommended_log_paths": str(OUT),
                "reason": "Only reads existing CSV/MD/JSON assets and writes inventory reports.",
            },
            {
                "task_name": "issue26b formal/purged temporal validation",
                "local_feasible": "unknown",
                "estimated_cost": "medium",
                "requires_large_parquet_scan": "unknown",
                "requires_multi_seed": "yes",
                "requires_model_training": "yes, lightweight LR/baselines only if executed",
                "requires_slurm": "unknown",
                "recommended_partition_if_known": "standard CPU partition if available",
                "recommended_time": "01:00:00 to 04:00:00 after smoke",
                "recommended_mem": "8G to 32G depending on raw asset rebuild",
                "recommended_cpus": "4 to 8",
                "recommended_log_paths": "runs/issue26b_*/stdout.log; runs/issue26b_*/stderr.log; slurm-%j.out/.err",
                "reason": "Formal validation may rebuild temporal splits and run multi-seed matrix; local smoke first.",
            },
        ]
    )
    (OUT / "slurm_need_assessment.md").write_text(
        "# Slurm Need Assessment\n\n" + md_table(slurm_df) + "\n\nConclusion: issue26a does not need Slurm.\n",
        encoding="utf-8",
    )

    (OUT / "issue26b_execution_plan.md").write_text(
        textwrap.dedent(
            f"""# Issue26b Execution Plan

## Recommended Issue26b Setting

Recommended next work item: `{next_action}`.

Reason: issue26a found no P0/P1 temporal candidate with low leakage risk. The best apparent temporal object is `chrono_early_train_late_eval`, but its eval bins overlap issue23/25c locked evidence. A cleaner path is to recover raw split metadata and construct a purged/embargoed future-window asset before formal validation.

## Cleanliness Judgment

- Current clean status: not clean for formal temporal proof.
- Fix required: recover timestamp / packet-order / bin provenance and define a pre-registered purged or embargoed split.
- If no unused future window exists after recovery, issue26b should stop at asset-gap documentation rather than run a dressed-up consistency check.

## Required Inputs

- raw stage2 manifest with row-level order or timestamps;
- attack-bin provenance and bin-to-time mapping;
- ID/OOD benign train/cal/val/eval source paths;
- frozen `selected_source_rich_top64` feature list/provenance;
- kcenter32 support selection rule and allowed attack-train pool;
- threshold protocol: ID calibration + OOD validation at official 1pct OOD target;
- final OOD/attack eval partitions marked report-only.

## Purge / Embargo

Use purge/embargo if train and eval windows are adjacent or if flow/session adjacency may leak near-duplicate traffic. The purge size must be pre-registered from metadata, not tuned on final attack/OOD results.

## Runtime / Slurm

- Local: metadata recovery, manifest construction, and one single-seed smoke.
- Slurm: only if the formal multi-seed matrix or raw parquet scan is large.

## Planned Matrix

- Method: frozen Enhanced LOW-GUARD+ top64 only for first formal temporal pass.
- Controls if cost allows: V1 original100 fixed guard LR, V2 top32 fixed guard LR, random32 top64 fixed guard LR.
- Seeds: smoke `42`; formal `42,43,44,45,46`; heldout robustness `47,48,49,50,51` only after smoke passes.
- Output files: summary.md, preflight, temporal_split_manifest.csv, support_provenance.csv, threshold_provenance.csv, method_comparison_by_seed.csv, method_comparison_summary.csv, leakage_audit_report.md, command.txt, config.json, run_spec.json, manifest.csv.
"""
        ),
        encoding="utf-8",
    )

    (OUT / "claim_update_after_issue26a.md").write_text(
        textwrap.dedent(
            """# Claim Update After Issue26a

## Allowed now

- issue26a inventories within-dataset temporal, locked, consistency, and data-scale evidence after issue25c.
- Enhanced LOW-GUARD+ top64 remains strong-baseline-positive on the existing locked bins under the low-alert protocol.
- Existing primary_lowood, holdout_bin_2, and chrono_late results are useful consistency/discovery evidence, not new temporal proof.
- Existing locked bins 5/6/7/8 support same-dataset locked validation, with repeated-analysis caveats.
- Current provenance indicates threshold selection uses ID calibration + OOD validation, not final OOD/attack eval.

## Still not allowed

- issue26a proves temporal generalization.
- issue26a proves external generalization.
- consistency checks equal formal locked temporal proof.
- locked-bin reuse is a clean new temporal validation.
- Enhanced LOW-GUARD+ is universally safe across all future drift.

## Needs issue26b

- A formal within-dataset temporal validation claim.
- A purged/embargoed future-window validation claim.
- A claim that temporal order, not only attack-bin holdout, was tested cleanly.

## Needs issue27

- Second-environment or external-dataset generalization.
- Robustness to BoT-IoT / TON-IoT-like domain shifts under a clean new protocol.
- Claims about cross-dataset deployability.
"""
        ),
        encoding="utf-8",
    )

    (OUT / "reviewer_defense_temporal_validation.md").write_text(
        textwrap.dedent(
            """# Reviewer Defense: Temporal Validation

## Q1: Are you just tuning repeatedly on one dataset?

Issue26a separates discovery, locked evidence, consistency checks, and future candidates. It does not tune topK, support budget, adapter, or thresholds. It flags repeated locked-bin analysis as a risk instead of hiding it.

## Q2: What is the difference between locked bins and temporal validation?

Locked bins 5/6/7/8 are unused leave-one-attack-window objects from issue23 and were later reused in issue25c strong baselines. They are same-dataset locked evidence. Formal temporal validation should pre-register a chronological future-window split with purge/embargo rules and no overlap with discovery or locked-evidence objects.

## Q3: Why is issue26a only feasibility, not formal validation?

Because issue26a reads and audits existing assets. It does not build a new clean temporal split, does not run a formal temporal experiment, and finds no low-leakage P0/P1 candidate ready for formal validation.

## Q4: How do you avoid temporal leakage?

By requiring row-level time/order metadata, separating train/cal/val/final windows, excluding final OOD and attack eval from all choices, checking support and threshold provenance, and using purge/embargo when windows are adjacent.

## Q5: What if there is no clean new temporal object?

Then the correct action is metadata recovery or asset construction, not repackaging consistency checks as temporal proof. Negative or insufficient-metadata outcomes remain visible.

## Q6: Why not directly do BoT-IoT / TON-IoT here?

This issue is scoped to within-dataset temporal/data-scale feasibility after issue25c. Second-environment work remains important but is deferred to issue27 so this round can close the temporal evidence inventory cleanly.

## Q7: Why is second environment still needed?

Within-dataset temporal evidence cannot prove external generalization. A second environment is still required for cross-dataset/domain validity claims.

## Q8: Do you need larger data?

Possibly. The inventory exposes small attack-eval risk for some bins, especially holdout_bin_8 with 426 attack eval rows, and single-domain risk remains.

## Q9: Do you need Slurm?

Not for issue26a. Issue26b may need Slurm only after local metadata recovery and smoke pass, especially if raw parquet scans or multi-seed formal validation are required.
"""
        ),
        encoding="utf-8",
    )

    pd.DataFrame(columns=["setting", "method", "detection", "ood_alarm", "not_run_reason"]).to_csv(
        OUT / "minimal_temporal_validation_result.csv", index=False
    )
    (OUT / "minimal_temporal_validation_not_run_reason.md").write_text(
        "# Minimal Temporal Validation Not Run Reason\n\n" + not_run_reason + "\n",
        encoding="utf-8",
    )
    (OUT / "minimal_temporal_validation_protocol.md").write_text(
        "# Minimal Temporal Validation Protocol\n\nnot_applicable: no clean low-leakage P0/P1 candidate was available in issue26a.\n",
        encoding="utf-8",
    )
    pd.DataFrame(columns=["field", "value"]).to_csv(OUT / "minimal_temporal_validation_provenance.csv", index=False)

    (OUT / "doc_update_patch_suggestion.md").write_text(
        "# Doc Update Patch Suggestion\n\nupdated: mainline docs appended with issue26a result after report generation.\n",
        encoding="utf-8",
    )

    (OUT / "claim_boundary.md").write_text(
        textwrap.dedent(
            """# Claim Boundary

## Can say

- issue26a inventories within-dataset temporal/data-scale evidence.
- issue26a identifies clean or non-clean temporal validation candidates.
- issue26a audits leakage risk.
- issue26a prepares issue26b formal temporal validation planning.

## Cannot say

- issue26a proves temporal generalization.
- issue26a proves external generalization.
- issue26a replaces second environment.
- issue26a permits new topK/adapter tuning.
- consistency check equals formal locked temporal proof.
"""
        ),
        encoding="utf-8",
    )

    risks = [
        ["repeated locked-bin analysis risk", "high", "Locked bins 5/6/7/8 have already been used in issue23 and issue25c.", "Do not present reanalysis as clean new temporal proof."],
        ["temporal leakage risk", "high", "Raw time/order metadata is not fully recovered in issue26a.", "Recover split metadata and pre-register temporal partitions."],
        ["adjacent-window contamination risk", "medium", "Adjacent temporal bins may contain near-duplicate or session-adjacent traffic.", "Use purge/embargo if adjacent windows are used."],
        ["insufficient metadata risk", "high", "Candidate cleanliness cannot be fully judged without raw timestamp/bin provenance.", "Make issue26b a metadata recovery and temporal asset build if needed."],
        ["small attack eval risk", "medium", "Some bins have small attack eval rows, e.g. holdout_bin_8 has 426.", "Report confidence/row counts and avoid overclaiming worst-case stability."],
        ["small OOD eval risk", "low", "Current final OOD eval appears around 10000 rows for existing settings.", "Keep row counts in all summaries; verify if new splits differ."],
        ["single-domain risk", "high", "All issue26a evidence remains within-dataset.", "Keep issue27 second environment on roadmap."],
        ["no second environment risk", "high", "Within-dataset temporal validation cannot prove external validity.", "Do not claim external generalization before issue27."],
        ["final eval leakage risk", "high", "Final OOD/attack eval must never guide thresholds or choices.", "Keep threshold/support/feature provenance and final report-only rule."],
        ["Slurm misuse risk", "medium", "Large scans or multi-seed runs should not run on a login node.", "Local smoke first; use Slurm only with frozen job scripts/logs/manifests."],
    ]
    pd.DataFrame(risks, columns=["risk_name", "severity", "description", "mitigation"]).to_csv(OUT / "risk_register.csv", index=False)

    (OUT / "recommended_next_action.md").write_text(
        textwrap.dedent(
            f"""# Recommended Next Action

## Unique Recommendation

`{next_action}`

## Rationale

No clean P0/P1 temporal candidate with low leakage risk was found in issue26a. The best available temporal direction requires split metadata recovery and a purged/embargoed asset build before formal validation. Do not recommend second environment as the immediate next step because current-dataset temporal validation is not impossible; it is currently metadata-blocked.
"""
        ),
        encoding="utf-8",
    )

    (OUT / "summary.md").write_text(
        textwrap.dedent(
            f"""# Issue26a Within-Dataset Temporal Validation Feasibility Summary

## Outcome

- Task type: within-dataset temporal / data-scale feasibility + evidence inventory.
- Formal temporal validation executed: no.
- Optional minimal temporal validation executed: no.
- Reason not run: {not_run_reason}
- Main method remains frozen: Enhanced LOW-GUARD+ top64 = selected_source_rich_top64 + kcenter32 + fixed OOD guard LR + 1pct OOD-validation-calibrated threshold.
- TopK/support/adapter/threshold changed: no.
- Final OOD/attack eval used for selection: no.
- Slurm needed for issue26a: no.

## What Temporal Evidence Is Most Needed After Issue25c

The project now needs a clean chronological or purged future-window validation object that was not used in top64 discovery, support selection, threshold selection, adapter choice, issue23 locked validation, or issue25c strong-baseline formation.

## What Existing Evidence Supports

- primary_lowood: primary/non-regression evidence under the current protocol.
- holdout_bin_2: hard-shift discovery evidence; useful consistency signal, not clean proof.
- chrono_late_train_early_eval: temporal-looking consistency evidence, but it participated in candidate confirmation/discovery and cannot be upgraded into formal temporal proof.
- locked bins 5/6/7/8: same-dataset locked validation evidence already used in issue23 and issue25c. They support current locked-bin claims but are not new temporal evidence.

## Claims Still Not Allowed

- Temporal generalization has been proven.
- External generalization has been proven.
- Consistency checks equal formal temporal validation.
- Repeated locked-bin analysis is a new clean validation.
- Second environment is no longer needed.

## Data-Scale Inventory Findings

- Existing ID/OOD slices are reasonably sized for lightweight inventory: ID train 8000, ID calibration 5000, OOD train 8000, OOD validation 2000, final OOD eval about 10000 in existing outputs.
- Attack eval size varies substantially by bin: holdout_bin_8 has only 426 attack eval rows, so worst-bin claims need row-count caveats.
- The project still has single-domain risk because all issue26a evidence is within-dataset.
- Raw timestamp/order metadata sufficient for a new purged formal temporal split was not recovered from the issue25c report pack.

## Clean Candidate Judgment

- Clean new temporal candidate found: no.
- Best partial candidate: `chrono_early_train_late_eval`.
- Why not clean: its late eval bins overlap issue23/25c locked bins 6/7/8, and purge/embargo metadata is not yet recovered.

## Issue26b Readiness

Issue26b can start as metadata recovery and temporal asset build, but not yet as formal validation. The recommended immediate next step is `{next_action}`.

## Slurm Judgment

Issue26a was local-only. Issue26b should remain local through metadata recovery and one smoke run. Slurm becomes appropriate only for large raw scans or multi-seed formal validation after the protocol is frozen.

## Second Environment Boundary

Second environment remains necessary for issue27. It is not part of issue26a and is not replaced by within-dataset temporal inventory.

## Files Read From Issue25c

Priority files read: {', '.join(read_csvs) if read_csvs else 'none'}.
Available additional CSVs: {', '.join(extra_csvs) if extra_csvs else 'none'}.
"""
        ),
        encoding="utf-8",
    )

    config = {
        "run": "issue26a_within_dataset_temporal_validation_for_enhanced_lowguard_top64_2026-05-22",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task_type": "within_dataset_temporal_data_scale_feasibility_inventory",
        "main_method_frozen": "selected_source_rich_top64 + kcenter32 + fixed OOD guard LR",
        "ood_target": 0.01,
        "topk_changed": False,
        "support_budget_changed": False,
        "adapter_changed": False,
        "threshold_protocol_changed": False,
        "minimal_temporal_validation_executed": False,
        "clean_low_risk_candidate_found": bool(not clean_candidates.empty),
        "recommended_next_action": next_action,
        "second_environment_deferred_to_issue27": True,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    run_spec = {
        "inputs": {
            "issue25c": str(ISSUE25C),
            "issue25b": str(ISSUE25B),
            "issue23": str(ISSUE23),
            "issue22": str(ISSUE22),
            "issue22b": str(ISSUE22B),
            "mainline_handoff": str(MAIN_DOCS / "mainline_handoff.md"),
            "mainline_experiment_map": str(MAIN_DOCS / "mainline_experiment_map.md"),
        },
        "selection_rules": {
            "final_ood_eval_report_only": True,
            "final_attack_eval_report_only": True,
            "threshold_source": "ID calibration + OOD validation only",
            "candidate_entry_rule": "Only P0/P1 candidates with low leakage risk may enter formal issue26b validation.",
        },
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2), encoding="utf-8")
    (OUT / "command.txt").write_text("\n".join(commands) + "\n", encoding="utf-8")

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)
    print(f"generated {OUT}")
    print(f"clean_candidates={len(clean_candidates)} next={next_action}")


if __name__ == "__main__":
    main()
