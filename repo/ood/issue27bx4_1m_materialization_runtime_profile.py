from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import issue27ab_gotham_kitsune115_frontend_feasibility as ab
import issue27bx3_500k_cache_aware_materialization_retry as bx3
from issue27bx_larger_sanity_materialization_dry_run import ATTACK_PCAP_CACHE


ISSUE = "issue27bx4_1m_materialization_runtime_profile_2026-06-12"
ROOT = Path(__file__).resolve().parents[1].parent
OUT = ROOT / "runs" / ISSUE
BASE_PLAN = ROOT / "runs" / "issue27bx2_materialization_quota_cache_repair_2026-06-12" / "materialization_v2_quota_plan.csv"
INVENTORY = ROOT / "runs" / "issue27bw_larger_sanity_contract_construction_2026-06-11" / "role_file_inventory.csv"
PLAN_PATH = OUT / "materialization_1m_runtime_profile_plan.csv"
DERIVED = ab.DATA_ROOT / "derived" / "kitsune115_larger_sanity_1m_runtime_profile_v1"
BASE_CACHE_DIR = ab.DATA_ROOT / "derived" / "kitsune115_larger_sanity_500k_v1" / "per_file_cache"

TARGET_TOTAL_ROWS = 1_000_000

ROLE_FLAGS = {
    "id_benign_train": ("false", "false", "false"),
    "id_benign_calib": ("false", "false", "false"),
    "ood_benign_val": ("false", "false", "false"),
    "ood_benign_stress": ("false", "false", "false"),
    "sealed_final_ood": ("true", "true", "false"),
    "attack_support_candidate_pool": ("false", "false", "true"),
    "dev_future_attack_query": ("true", "false", "false"),
    "sealed_final_attack": ("true", "true", "false"),
}

ADDITIONS = [
    ("id_benign_calib", "processed/iotsim-cooler-motor-5.csv", 22471),
    ("id_benign_calib", "processed/iotsim-cooler-motor-6.csv", 22468),
    ("id_benign_calib", "processed/iotsim-cooler-motor-8.csv", 5061),
    ("ood_benign_stress", "processed/iotsim-stream-consumer-1.csv", 150000),
    ("sealed_final_ood", "processed/iotsim-ip-camera-street-2.csv", 100000),
    ("attack_support_candidate_pool", "processed/iotsim-air-quality-1.csv", 45000),
    ("dev_future_attack_query", "processed/iotsim-building-monitor-1.csv", 80000),
    ("dev_future_attack_query", "processed/iotsim-domotic-monitor-1.csv", 75000),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def inventory_by_csv() -> dict[str, dict[str, str]]:
    return {row["csv_archive_path"]: row for row in read_csv(INVENTORY)}


def strict_pcap_member(role: str, csv_member: str, inv_row: dict[str, str]) -> str:
    if role in {"attack_support_candidate_pool", "dev_future_attack_query", "sealed_final_attack"}:
        return ATTACK_PCAP_CACHE[csv_member]["pcap"]
    return inv_row["pcap_counterpart_candidate"]


def role_target_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for row in rows:
        totals[row["role"]] = totals.get(row["role"], 0) + int(row["proposed_rows"])
    return totals


def build_plan() -> list[dict[str, Any]]:
    inv = inventory_by_csv()
    rows: list[dict[str, Any]] = []
    for row in read_csv(BASE_PLAN):
        out = dict(row)
        if out["role"] in {"attack_support_candidate_pool", "dev_future_attack_query", "sealed_final_attack"}:
            out["pcap_member"] = ATTACK_PCAP_CACHE[out["csv_member"]]["pcap"]
        out["estimate_source"] = "issue27bx3_exact_cache_reuse_candidate"
        out["plan_rule"] = "cache_preserving_base_500k_exact_target"
        rows.append(out)

    for role, csv_member, proposed_rows in ADDITIONS:
        inv_row = inv[csv_member]
        report_only, sealed_final, selection_allowed = ROLE_FLAGS[role]
        capacity = int(inv_row["attack_rows"] if role in {"attack_support_candidate_pool", "dev_future_attack_query", "sealed_final_attack"} else inv_row["benign_rows"])
        if proposed_rows > capacity:
            raise RuntimeError(f"proposed rows exceed inventory capacity for {csv_member}: {proposed_rows}>{capacity}")
        rows.append(
            {
                "role": role,
                "csv_member": csv_member,
                "pcap_member": strict_pcap_member(role, csv_member, inv_row),
                "proposed_rows": proposed_rows,
                "role_target_rows": 0,
                "planning_capacity_rows": capacity,
                "estimate_source": "issue27bx4_inventory_capacity_same_role_extension",
                "report_only_role": report_only,
                "sealed_final_role": sealed_final,
                "selection_allowed": selection_allowed,
                "plan_rule": "cache_preserving_id_train_fixed_same_role_extension_no_cross_role_fallback",
            }
        )

    totals = role_target_rows(rows)
    if sum(totals.values()) != TARGET_TOTAL_ROWS:
        raise RuntimeError(f"planned rows {sum(totals.values())} != {TARGET_TOTAL_ROWS}: {totals}")
    for row in rows:
        row["role_target_rows"] = totals[row["role"]]
    return rows


def write_plan_audit(rows: list[dict[str, Any]]) -> None:
    totals = role_target_rows(rows)
    audit_rows = [
        {"role": role, "target_rows": target, "notes": "id_train_fixed_to_preserve_train_state_cache_signature" if role == "id_benign_train" else "strict_same_role_extension_or_base_cache_reuse"}
        for role, target in totals.items()
    ]
    bx3.write_csv(OUT / "strict_role_quota_audit.csv", audit_rows)
    bx3.write_md(
        OUT / "data_cleanliness_contract.md",
        [
            "# issue27bx4 Data Cleanliness Contract",
            "",
            "- No model training, threshold tuning, OOD gate repair, or formal benchmark.",
            "- ID train is fixed to issue27bx3 to preserve train-state semantics and cache validity.",
            "- 500k base rows are exact cache-reuse candidates; 500k new rows are same-role extensions.",
            "- No cross-role fallback is allowed.",
            "- Sealed final OOD and sealed final attack remain report-only and forbidden for fit, threshold, support selection, and model selection.",
            "- Attack roles use malicious PCAP members from the audited attack onset cache, not filename-only benign PCAP pairings.",
        ],
    )


def configure_bx3_for_bx4() -> None:
    bx3.ISSUE = ISSUE
    bx3.OUT = OUT
    bx3.PLAN_PATH = PLAN_PATH
    bx3.DERIVED = DERIVED
    bx3.CACHE_DIR = DERIVED / "per_file_cache"
    bx3.LOG_PATH = DERIVED / "issue27bx4_materialization_log.txt"
    bx3.ASSET_TAG = "1m_runtime_profile"
    bx3.TARGET_TOTAL_ROWS = TARGET_TOTAL_ROWS
    bx3.SUCCESS_VERDICT = "cache_aware_1m_runtime_profile_ready_for_larger_replay_sanity"
    bx3.PARTIAL_VERDICT = "cache_aware_1m_runtime_profile_partial_needs_quota_or_frontend_fix"
    bx3.NEXT_RECOMMENDED_ISSUE = "issue27by_larger_sanity_replay_on_1m_asset"
    bx3.DECISION_FILE = "issue27bx4_decision.md"
    bx3.NEXT_ACTION_FILE = "issue27by_next_action.md"
    bx3.COMMAND_TEXT = "python repo/ood/issue27bx4_1m_materialization_runtime_profile.py"
    bx3.RUN_TYPE = "cache_aware_1m_materialization_runtime_profile"
    bx3.DOC_TITLE = "issue27bx4 1M Materialization Runtime Profile"
    bx3.CACHE_READ_DIRS = [BASE_CACHE_DIR]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plan_rows = build_plan()
    fieldnames = list(read_csv(BASE_PLAN)[0].keys())
    write_csv(PLAN_PATH, plan_rows, fieldnames)
    write_plan_audit(plan_rows)
    configure_bx3_for_bx4()
    bx3.main()


if __name__ == "__main__":
    main()
