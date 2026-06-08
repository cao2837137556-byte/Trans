from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au
import issue27ay_region_aware_attack_bank_and_score_gate_diagnostic as ay
import issue27ba_disjoint_ood_stress_pool_before_mixed_stream as ba
import issue27bc_attack_core_purity_unknown_band_review_budget as bc


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bl_attack_phase_onset_pseudo_contract_audit_2026-06-08"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BA = ROOT / "runs" / "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"
ISSUE27BK = ROOT / "runs" / "issue27bk_task_boundary_then_metric_shell_smoke_2026-06-08"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
ACTIVE_LABEL_BUDGET = 64
ATTACK_GO_THRESHOLD = 0.93


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


def hash_indices(indices: np.ndarray) -> str:
    return hashlib.sha256(",".join(map(str, np.asarray(indices, dtype=np.int64).tolist())).encode("utf-8")).hexdigest()


def file_key(row: dict[str, str]) -> str:
    return row.get("csv_member") or row.get("source_file") or row.get("pcap_member") or "unknown"


def attack_type_key(row: dict[str, str]) -> str:
    return row.get("attack_type_from_raw_path") or row.get("attack_type") or row.get("label") or "unknown"


def device_hint(row: dict[str, str]) -> str:
    name = Path(file_key(row)).name
    if name.startswith("iotsim-"):
        name = name[len("iotsim-") :]
    if name.endswith(".csv"):
        name = name[:-4]
    parts = name.split("-")
    if len(parts) > 1 and parts[-1].isdigit():
        parts = parts[:-1]
    return "-".join(parts) if parts else name


def parse_int(row: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(float(row.get(key, "")))
    except Exception:
        return int(default)


def parse_float(row: dict[str, str], key: str, default: float = float("nan")) -> float:
    try:
        return float(row.get(key, ""))
    except Exception:
        return float(default)


def phase_bucket(recorded_index: int) -> str:
    if recorded_index < 50:
        return "warmup_edge_0_49"
    if recorded_index < 500:
        return "early_50_499"
    if recorded_index < 2000:
        return "mid_500_1999"
    if recorded_index < 10000:
        return "late_2000_9999"
    return "tail_ge10000"


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return float(len(a & b) / len(a | b))


def summarize_counter(counter: Counter[str], top: int = 8) -> str:
    return "|".join(f"{k}:{v}" for k, v in counter.most_common(top))


def role_indices_from_rows(rows: list[dict[str, str]], role: str) -> np.ndarray:
    return np.asarray(
        [i for i, r in enumerate(rows) if r.get("role") == role and r.get("model_ready_hint", "").lower() == "true"],
        dtype=np.int64,
    )


def rows_for(sidecar: list[dict[str, str]], idx: np.ndarray) -> list[dict[str, str]]:
    return [sidecar[int(i)] for i in np.asarray(idx, dtype=np.int64)]


def role_phase_summary(seed: int, role: str, sidecar: list[dict[str, str]], idx: np.ndarray) -> dict[str, Any]:
    rs = rows_for(sidecar, idx)
    files = Counter(file_key(r) for r in rs)
    devices = Counter(device_hint(r) for r in rs)
    attacks = Counter(attack_type_key(r) for r in rs)
    phases = Counter(phase_bucket(parse_int(r, "recorded_index")) for r in rs)
    packet_vals = [parse_int(r, "packet_index") for r in rs]
    rec_vals = [parse_int(r, "recorded_index") for r in rs]
    ts_vals = [parse_float(r, "packet_timestamp_epoch") for r in rs]
    return {
        "seed": seed,
        "role": role,
        "rows": int(len(rs)),
        "file_count": int(len(files)),
        "device_hint_count": int(len(devices)),
        "attack_type_count": int(len(attacks)),
        "phase_count": int(len(phases)),
        "top_files": summarize_counter(files),
        "top_device_hints": summarize_counter(devices),
        "top_attack_types": summarize_counter(attacks),
        "phase_distribution": summarize_counter(phases),
        "packet_index_min": int(min(packet_vals)) if packet_vals else "",
        "packet_index_max": int(max(packet_vals)) if packet_vals else "",
        "recorded_index_min": int(min(rec_vals)) if rec_vals else "",
        "recorded_index_max": int(max(rec_vals)) if rec_vals else "",
        "timestamp_min": float(np.nanmin(ts_vals)) if ts_vals else "",
        "timestamp_max": float(np.nanmax(ts_vals)) if ts_vals else "",
        "role_hash": hash_indices(idx),
    }


def role_sets(sidecar: list[dict[str, str]], idx: np.ndarray) -> dict[str, set[str]]:
    rs = rows_for(sidecar, idx)
    return {
        "files": {file_key(r) for r in rs},
        "devices": {device_hint(r) for r in rs},
        "attack_types": {attack_type_key(r) for r in rs},
        "phases": {phase_bucket(parse_int(r, "recorded_index")) for r in rs},
    }


def overlap_row(seed: int, left_role: str, left_sidecar: list[dict[str, str]], left_idx: np.ndarray, right_role: str, right_sidecar: list[dict[str, str]], right_idx: np.ndarray) -> dict[str, Any]:
    l = role_sets(left_sidecar, left_idx)
    r = role_sets(right_sidecar, right_idx)
    return {
        "seed": seed,
        "left_role": left_role,
        "right_role": right_role,
        "file_jaccard": jaccard(l["files"], r["files"]),
        "device_hint_jaccard": jaccard(l["devices"], r["devices"]),
        "attack_type_jaccard": jaccard(l["attack_types"], r["attack_types"]),
        "phase_jaccard": jaccard(l["phases"], r["phases"]),
        "left_files": "|".join(sorted(l["files"])[:8]),
        "right_files": "|".join(sorted(r["files"])[:8]),
        "left_phases": "|".join(sorted(l["phases"])),
        "right_phases": "|".join(sorted(r["phases"])),
    }


def distance_audit(seed: int, source_role: str, source_x: np.ndarray, val_role: str, val_x: np.ndarray, query_role: str, query_x: np.ndarray) -> dict[str, Any]:
    if len(source_x) == 0 or len(query_x) == 0:
        return {"seed": seed, "source_role": source_role, "val_role": val_role, "query_role": query_role, "blocked": True}
    scaler = StandardScaler().fit(source_x)
    z_source = scaler.transform(source_x)
    if len(val_x):
        val_d = pairwise_distances(scaler.transform(val_x), z_source, metric="euclidean").min(axis=1)
        val_q50 = float(np.quantile(val_d, 0.50))
        val_q95 = float(np.quantile(val_d, 0.95))
    else:
        val_q50 = val_q95 = float("nan")
    query_d = pairwise_distances(scaler.transform(query_x), z_source, metric="euclidean").min(axis=1)
    return {
        "seed": seed,
        "source_role": source_role,
        "val_role": val_role,
        "query_role": query_role,
        "source_rows": int(len(source_x)),
        "val_rows": int(len(val_x)),
        "query_rows": int(len(query_x)),
        "val_nn_q50": val_q50,
        "val_nn_q95": val_q95,
        "query_nn_q50": float(np.quantile(query_d, 0.50)),
        "query_nn_q95": float(np.quantile(query_d, 0.95)),
        "q50_gap_query_minus_val": float(np.quantile(query_d, 0.50) - val_q50),
        "q95_gap_query_minus_val": float(np.quantile(query_d, 0.95) - val_q95),
    }


def contract_flag(row: dict[str, Any]) -> str:
    if float(row["attack_type_jaccard"]) < 1.0:
        return "blocked_attack_type_mismatch"
    if float(row["phase_jaccard"]) == 0.0:
        return "high_risk_phase_disjoint"
    if float(row["file_jaccard"]) == 0.0 and float(row["device_hint_jaccard"]) == 0.0:
        return "high_risk_file_device_disjoint"
    return "contract_overlap_present"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    stress_cert_path = ISSUE27BA / "ood_stress_data_certificate.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    stress_cert = json.loads(stress_cert_path.read_text(encoding="utf-8"))
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    stress_x, stress_sidecar, stress_checks = ba.load_stress_asset(stress_cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    if not new_sidecar:
        new_sidecar = ay.read_csv(ar.NEW_HELDOUT_SIDECAR)
    x = asset["X"]
    sidecar = asset["sidecar"]

    support_pool = ar.role_indices(sidecar, ar.SUPPORT_ROLE)
    attack_eval = ar.role_indices(sidecar, ar.ATTACK_EVAL_ROLE)
    active_candidate_idx, dev_query_idx, active_manifest = issue27au.split_new_heavy_stream(new_sidecar)

    input_rows = [
        {"artifact": "issue27af_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path)},
        {"artifact": "issue27ba_stress_certificate", "path": str(stress_cert_path), "sha256": sha256_file(stress_cert_path)},
        {"artifact": "issue27bk_summary", "path": str(ISSUE27BK / "summary.md"), "sha256": sha256_file(ISSUE27BK / "summary.md")},
    ]
    input_rows.extend(checks)
    input_rows.extend(stress_checks)
    input_rows.extend(new_checks)

    phase_inventory: list[dict[str, Any]] = []
    overlap_rows: list[dict[str, Any]] = []
    distance_rows: list[dict[str, Any]] = []
    contract_rows: list[dict[str, Any]] = []
    proposed_rows: list[dict[str, Any]] = []
    seed_split_rows: list[dict[str, Any]] = []
    high_risk_flags: list[str] = []

    for seed in SEEDS:
        base_support, base_audit = issue27as.kcenter_budget(x, support_pool, ay.BASE_SUPPORT_BUDGET)
        medium_train, medium_val, medium_pseudo, medium_audit = bc.split_train_val_pseudo(base_support, sidecar, seed, "medium_attack_support")
        selected_active, active_audit = issue27au.select_active_labels(
            x_base_support=x[medium_train],
            x_support_val=x[medium_val],
            x_candidates=new_x[active_candidate_idx],
            candidate_indices=active_candidate_idx,
            budget=ACTIVE_LABEL_BUDGET,
        )
        selected_confirmed = np.asarray([idx for idx in selected_active if ay.label_is_attack(new_sidecar[int(idx)])], dtype=np.int64)
        heavy_train, heavy_val, heavy_pseudo, heavy_audit = bc.split_train_val_pseudo(selected_confirmed, new_sidecar, seed, "active_heavy_attack_support")
        seed_split_rows.extend(
            [
                {"seed": seed, "split_family": "medium_attack_support", **medium_audit, "base_support_hash": hash_indices(base_support), **{f"base_{k}": v for k, v in base_audit.items()}},
                {"seed": seed, "split_family": "active_heavy_attack_support", **heavy_audit, "active_confirmed_hash": hash_indices(selected_confirmed), **{f"active_{k}": v for k, v in active_audit.items()}},
            ]
        )

        roles = {
            "medium_support_train": (sidecar, medium_train),
            "medium_support_val": (sidecar, medium_val),
            "medium_pseudo_query_dev": (sidecar, medium_pseudo),
            "medium_attack_eval_report_only": (sidecar, attack_eval),
            "heavy_active_candidate_stream": (new_sidecar, active_candidate_idx),
            "heavy_support_train": (new_sidecar, heavy_train),
            "heavy_support_val": (new_sidecar, heavy_val),
            "heavy_pseudo_query_dev": (new_sidecar, heavy_pseudo),
            "dev_heavy_query_report_only": (new_sidecar, dev_query_idx),
        }
        for role, (sc, idx) in roles.items():
            phase_inventory.append(role_phase_summary(seed, role, sc, idx))

        pairs = [
            ("medium_support_train", sidecar, medium_train, "medium_support_val", sidecar, medium_val),
            ("medium_support_train", sidecar, medium_train, "medium_pseudo_query_dev", sidecar, medium_pseudo),
            ("medium_support_train", sidecar, medium_train, "medium_attack_eval_report_only", sidecar, attack_eval),
            ("medium_pseudo_query_dev", sidecar, medium_pseudo, "medium_attack_eval_report_only", sidecar, attack_eval),
            ("heavy_support_train", new_sidecar, heavy_train, "heavy_support_val", new_sidecar, heavy_val),
            ("heavy_support_train", new_sidecar, heavy_train, "heavy_pseudo_query_dev", new_sidecar, heavy_pseudo),
            ("heavy_support_train", new_sidecar, heavy_train, "dev_heavy_query_report_only", new_sidecar, dev_query_idx),
            ("heavy_pseudo_query_dev", new_sidecar, heavy_pseudo, "dev_heavy_query_report_only", new_sidecar, dev_query_idx),
        ]
        for left_role, left_sc, left_idx, right_role, right_sc, right_idx in pairs:
            row = overlap_row(seed, left_role, left_sc, left_idx, right_role, right_sc, right_idx)
            row["contract_flag"] = contract_flag(row)
            overlap_rows.append(row)
            if row["contract_flag"].startswith("high_risk"):
                high_risk_flags.append(f"seed_{seed}:{left_role}->{right_role}:{row['contract_flag']}")

        distance_specs = [
            ("medium_support_train", x[medium_train], "medium_support_val", x[medium_val], "medium_pseudo_query_dev", x[medium_pseudo]),
            ("medium_support_train", x[medium_train], "medium_support_val", x[medium_val], "medium_attack_eval_report_only", x[attack_eval]),
            ("heavy_support_train", new_x[heavy_train], "heavy_support_val", new_x[heavy_val], "heavy_pseudo_query_dev", new_x[heavy_pseudo]),
            ("heavy_support_train", new_x[heavy_train], "heavy_support_val", new_x[heavy_val], "dev_heavy_query_report_only", new_x[dev_query_idx]),
        ]
        for spec in distance_specs:
            distance_rows.append(distance_audit(seed, *spec))

        for family, train_role, pseudo_role, report_role in [
            ("medium", "medium_support_train", "medium_pseudo_query_dev", "medium_attack_eval_report_only"),
            ("heavy", "heavy_support_train", "heavy_pseudo_query_dev", "dev_heavy_query_report_only"),
        ]:
            train_sc, train_idx = roles[train_role]
            pseudo_sc, pseudo_idx = roles[pseudo_role]
            report_sc, report_idx = roles[report_role]
            train_sets = role_sets(train_sc, train_idx)
            pseudo_sets = role_sets(pseudo_sc, pseudo_idx)
            report_sets = role_sets(report_sc, report_idx)
            contract_rows.append(
                {
                    "seed": seed,
                    "family": family,
                    "current_train_role": train_role,
                    "current_dev_query_role": pseudo_role,
                    "report_only_role": report_role,
                    "train_rows": int(len(train_idx)),
                    "pseudo_rows": int(len(pseudo_idx)),
                    "report_only_rows": int(len(report_idx)),
                    "train_phase_set": "|".join(sorted(train_sets["phases"])),
                    "pseudo_phase_set": "|".join(sorted(pseudo_sets["phases"])),
                    "report_only_phase_set": "|".join(sorted(report_sets["phases"])),
                    "train_file_count": len(train_sets["files"]),
                    "pseudo_file_count": len(pseudo_sets["files"]),
                    "report_file_count": len(report_sets["files"]),
                    "train_pseudo_phase_jaccard": jaccard(train_sets["phases"], pseudo_sets["phases"]),
                    "train_report_phase_jaccard": jaccard(train_sets["phases"], report_sets["phases"]),
                    "train_pseudo_file_jaccard": jaccard(train_sets["files"], pseudo_sets["files"]),
                    "train_report_file_jaccard": jaccard(train_sets["files"], report_sets["files"]),
                    "contract_status": "needs_phase_balanced_rebuild" if jaccard(train_sets["phases"], pseudo_sets["phases"]) < 0.5 or jaccard(train_sets["phases"], report_sets["phases"]) < 0.5 else "phase_overlap_ok",
                }
            )

    # Proposal is data-contract only. It does not materialize new support rows.
    proposed_rows.extend(
        [
            {
                "proposal_id": "phase_balanced_dev_contract_v2",
                "purpose": "ensure support_train/support_val/pseudo cover early/mid/late attack phases when available",
                "allowed_inputs": "attack_support_role_and_active_candidate_stream_only",
                "forbidden_inputs": "final_ood|medium_attack_eval_report_only|dev_heavy_query_report_only|attack_eval",
                "row_selection_rule": "stratify by attack_type/file/recorded_index_phase; reserve file-disjoint pseudo only after each phase has support coverage",
                "expected_benefit": "reduce support-query phase gap before model/head repair",
                "status": "recommended_before_more_heads",
            },
            {
                "proposal_id": "heavy_active_candidate_temporal_coverage_v2",
                "purpose": "avoid using only first_1000 rows per heavy file for support when query is later rows",
                "allowed_inputs": "development-side unlabeled active candidate windows only; labels obtained after selection",
                "forbidden_inputs": "dev_heavy_query_report_only labels for selection",
                "row_selection_rule": "sample active-label candidates from multiple time windows before query split is sealed, or create a separate dev target pool",
                "expected_benefit": "avoid support early-phase vs query late-phase mismatch",
                "status": "requires_new_materialization_plan",
            },
        ]
    )

    role_access_rows = [
        {
            "phase": "audit",
            "allowed_roles": "support/train/val/pseudo/report-only for attribution tables",
            "forbidden_selection_roles": "final_ood|medium_attack_eval_report_only|dev_heavy_query_report_only|attack_eval",
            "forbidden_access_detected": False,
            "note": "report-only roles were used for attribution only",
        },
        {
            "phase": "contract_proposal",
            "allowed_roles": "metadata from current dev-side roles",
            "forbidden_selection_roles": "final/report-only",
            "forbidden_access_detected": False,
            "note": "proposal only; no new support materialized",
        },
    ]

    high_risk_count = len(high_risk_flags)
    phase_contract_needs_rebuild = any(r["contract_status"] == "needs_phase_balanced_rebuild" for r in contract_rows)
    if phase_contract_needs_rebuild or high_risk_count:
        primary_verdict = "attack_phase_contract_mismatch_needs_rebuild_before_more_heads"
        next_action = "issue27bm_phase_balanced_attack_contract_design_without_report_only_leakage"
    else:
        primary_verdict = "attack_phase_contract_audit_passed_return_to_metric_head"
        next_action = "issue27bm_metric_head_after_phase_contract_pass"

    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "active_stream_split_manifest.csv", active_manifest)
    write_csv(OUT / "seed_split_audit.csv", seed_split_rows)
    write_csv(OUT / "attack_phase_inventory.csv", phase_inventory)
    write_csv(OUT / "file_phase_overlap_matrix.csv", overlap_rows)
    write_csv(OUT / "phase_distance_audit.csv", distance_rows)
    write_csv(OUT / "pseudo_query_contract_audit.csv", contract_rows)
    write_csv(OUT / "candidate_contract_v2_proposal.csv", proposed_rows)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)
    write_md(
        OUT / "issue27bl_decision.md",
        [
            "# issue27bl Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            f"- high_risk_overlap_flags = `{high_risk_count}`",
            f"- phase_contract_needs_rebuild = `{phase_contract_needs_rebuild}`",
            "- This task is a data-contract audit, not model repair.",
            "- No 115D frontend/split/support pool changes were made.",
            "- Report-only roles were attribution-only and not used for selection.",
        ],
    )
    write_md(
        OUT / "issue27bm_next_action.md",
        [
            "# issue27bm Next Action",
            "",
            f"recommended_next_action = `{next_action}`",
            "",
            "- Do not add stronger heads until the attack support/query phase contract is repaired or explicitly justified.",
            "- A phase-balanced contract must be designed using development-side pools only.",
            "- Report-only attack and final OOD remain sealed.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27bl.md",
        [
            "# Claim Update After issue27bl",
            "",
            "- Current medium diagnostics remain blocked for formal claims.",
            "- The immediate blocker is not just model capacity; attack support/query contract has phase/file/device mismatch risk.",
            "- Future claims require a phase-aware, report-only-clean attack contract before more head repair.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27bl Summary",
            "",
            "1. issue27bl completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. task type: attack phase/onset/pseudo-query contract audit; not model training",
            "4. 115D frontend changed: no",
            "5. split changed: no",
            "6. support pool changed: no",
            f"7. high_risk_overlap_flags: `{high_risk_count}`",
            f"8. phase_contract_needs_rebuild: `{phase_contract_needs_rebuild}`",
            "9. final/report-only used for selection: no",
            f"10. attack go threshold remains: `{ATTACK_GO_THRESHOLD}`",
            "11. OOD-gate repair allowed: no",
            f"12. next action: `{next_action}`",
            "13. commit hash: reported in final response",
        ],
    )
    config = {
        "issue": ISSUE,
        "primary_verdict": primary_verdict,
        "seeds": SEEDS,
        "active_label_budget": ACTIVE_LABEL_BUDGET,
        "attack_go_threshold": ATTACK_GO_THRESHOLD,
        "report_only_selection_forbidden": True,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    run_spec = {
        "command": "python repo/ood/issue27bl_attack_phase_onset_pseudo_contract_audit.py",
        "cwd": str(ROOT),
        "outputs": str(OUT),
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "command.txt").write_text(run_spec["command"] + "\n", encoding="utf-8")
    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest_rows.append({"file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bl_attack_phase_onset_pseudo_contract_audit -->",
        [
            "## issue27bl - attack phase/onset/pseudo-query contract audit",
            "",
            "<!-- issue27bl_attack_phase_onset_pseudo_contract_audit -->",
            f"- Verdict: `{primary_verdict}`.",
            f"- high-risk overlap flags: `{high_risk_count}`; phase contract needs rebuild: `{phase_contract_needs_rebuild}`.",
            "- No 115D frontend/split/support pool changes; no model training.",
            "- Report-only roles were attribution-only and not used for selection.",
            f"- Next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bl_attack_phase_onset_pseudo_contract_audit -->",
        [
            "## issue27bl - attack phase/onset/pseudo-query contract audit",
            "",
            "<!-- issue27bl_attack_phase_onset_pseudo_contract_audit -->",
            "- Stage: data-contract audit before more head repair.",
            f"- Primary verdict: `{primary_verdict}`.",
            "- Formal benchmark status: blocked.",
            "- OOD-gate repair remains blocked.",
        ],
    )


if __name__ == "__main__":
    main()
