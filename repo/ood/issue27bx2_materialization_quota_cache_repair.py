from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import issue27ab_gotham_kitsune115_frontend_feasibility as ab

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent

ISSUE = "issue27bx2_materialization_quota_cache_repair_2026-06-12"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

CONTRACT_DIR = ROOT / "runs" / "issue27bw_larger_sanity_contract_construction_2026-06-11"
CONTRACT_PATH = CONTRACT_DIR / "larger_sanity_contract_v1.json"
ROLE_INVENTORY_PATH = CONTRACT_DIR / "role_file_inventory.csv"
BX_DIR = ROOT / "runs" / "issue27bx_larger_sanity_materialization_dry_run_from_contract_v1_2026-06-11"
BX_ROLE_META_PATH = BX_DIR / "larger_materialization_role_meta.csv"
BX_SUMMARY_PATH = BX_DIR / "summary.md"
ARCHIVE_LISTING_PATH = ROOT / "runs" / "issue27v_gotham_download_and_file_level_data_gate_2026-05-28" / "archive_file_listing.csv"

PRIMARY_STRATEGY = "train_state_then_eval_online"
WARMUP_PACKETS = 50

NEXT_LOCAL_TARGET_ROWS = 500_000
NEXT_LOCAL_ROLE_QUOTAS = {
    "id_benign_train": 151_000,
    "id_benign_calib": 30_000,
    "ood_benign_val": 24_000,
    "ood_benign_stress": 80_000,
    "sealed_final_ood": 55_000,
    "attack_support_candidate_pool": 45_000,
    "dev_future_attack_query": 80_000,
    "sealed_final_attack": 35_000,
}

REPORT_ONLY_ROLES = {"dev_future_attack_query", "sealed_final_ood", "sealed_final_attack"}
SEALED_FINAL_ROLES = {"sealed_final_ood", "sealed_final_attack"}
ATTACK_ROLES = {"attack_support_candidate_pool", "dev_future_attack_query", "sealed_final_attack"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_once(path: Path, marker: str, lines: list[str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def archive_size_map() -> dict[str, dict[str, str]]:
    if not ARCHIVE_LISTING_PATH.exists():
        return {}
    return {row["file_path"]: row for row in read_csv(ARCHIVE_LISTING_PATH)}


def observed_meta_map() -> dict[tuple[str, str], dict[str, str]]:
    if not BX_ROLE_META_PATH.exists():
        return {}
    return {(row["role"], row["csv_member"]): row for row in read_csv(BX_ROLE_META_PATH)}


def inventory_map() -> dict[str, dict[str, str]]:
    return {row["csv_archive_path"]: row for row in read_csv(ROLE_INVENTORY_PATH)}


def candidate_capacity(row: dict[str, str], role: str, obs: dict[str, str] | None) -> tuple[int, int, str]:
    total_rows = as_int(row.get("total_rows"))
    label_rows = as_int(row.get("attack_rows" if role in ATTACK_ROLES else "benign_rows"))
    file_level_upper_bound = max(0, min(total_rows, label_rows) if label_rows else total_rows)
    if obs:
        emitted = as_int(obs.get("emitted_rows"))
        target = as_int(obs.get("target_rows"))
        completed = str(obs.get("completed_target", "")).lower() == "true"
        if not completed:
            return emitted, emitted, "verified_issue27bx_shortfall_available_exact_or_lower_bound"
        return emitted, max(emitted, file_level_upper_bound), "issue27bx_completed_target_plus_file_manifest_upper_bound"
    return 0, file_level_upper_bound, "file_manifest_upper_bound_unverified_by_115d"


def build_available_rows(contract: dict[str, Any]) -> list[dict[str, Any]]:
    inv = inventory_map()
    obs_map = observed_meta_map()
    sizes = archive_size_map()
    rows: list[dict[str, Any]] = []
    for role, csv_paths in contract["roles"].items():
        for csv_member in csv_paths:
            inv_row = inv.get(csv_member, {})
            obs = obs_map.get((role, csv_member))
            pcap = inv_row.get("pcap_counterpart_candidate", "")
            pcap_size = as_int(sizes.get(pcap, {}).get("uncompressed_size"))
            verified_lower, planning_capacity, source = candidate_capacity(inv_row, role, obs)
            observed_target = as_int(obs.get("target_rows")) if obs else 0
            observed_emitted = as_int(obs.get("emitted_rows")) if obs else 0
            shortfall = max(0, observed_target - observed_emitted) if obs else 0
            rows.append(
                {
                    "role": role,
                    "csv_member": csv_member,
                    "pcap_member": pcap,
                    "device": inv_row.get("inferred_device", ""),
                    "protocol": inv_row.get("observed_protocol", ""),
                    "csv_total_rows": as_int(inv_row.get("total_rows")),
                    "csv_benign_rows": as_int(inv_row.get("benign_rows")),
                    "csv_attack_rows": as_int(inv_row.get("attack_rows")),
                    "pcap_uncompressed_size": pcap_size,
                    "observed_in_issue27bx": str(obs is not None).lower(),
                    "observed_target_rows": observed_target,
                    "observed_emitted_rows": observed_emitted,
                    "observed_packets_scanned": as_int(obs.get("packets_scanned")) if obs else 0,
                    "verified_available_lower_bound_rows": verified_lower,
                    "planning_capacity_rows": planning_capacity,
                    "estimate_source": source,
                    "issue27bx_shortfall_rows": shortfall,
                    "completed_issue27bx_target": str(obs.get("completed_target", "")).lower() if obs else "",
                    "report_only_role": str(role in REPORT_ONLY_ROLES).lower(),
                    "sealed_final_role": str(role in SEALED_FINAL_ROLES).lower(),
                    "allowed_as_same_role_fallback": str(role not in SEALED_FINAL_ROLES).lower(),
                    "notes": "do_not_use_sealed_final_as_fallback" if role in SEALED_FINAL_ROLES else "same_role_only_fallback_candidate",
                }
            )
    return rows


def build_quota_vs_actual() -> list[dict[str, Any]]:
    rows = []
    for row in read_csv(BX_ROLE_META_PATH):
        target = as_int(row.get("target_rows"))
        emitted = as_int(row.get("emitted_rows"))
        elapsed = as_float(row.get("elapsed_seconds"))
        rows.append(
            {
                "role": row["role"],
                "csv_member": row["csv_member"],
                "pcap_member": row["pcap_member"],
                "target_rows": target,
                "emitted_rows": emitted,
                "shortfall_rows": max(0, target - emitted),
                "completed_target": row["completed_target"],
                "packets_scanned": as_int(row.get("packets_scanned")),
                "pre_record_packets": as_int(row.get("pre_record_packets")),
                "parse_errors": as_int(row.get("parse_errors")),
                "elapsed_seconds": elapsed,
                "rows_per_second": round(emitted / elapsed, 4) if elapsed > 0 else "",
                "shortfall_class": "none" if emitted >= target else "pcap_available_rows_below_quota",
            }
        )
    return rows


def choose_fallbacks(available_rows: list[dict[str, Any]], quota_vs_actual: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_role = defaultdict(list)
    for row in available_rows:
        by_role[row["role"]].append(row)
    failures = [row for row in quota_vs_actual if as_int(row["shortfall_rows"]) > 0]
    fallback_rows: list[dict[str, Any]] = []
    for failure in failures:
        role = failure["role"]
        shortfall = as_int(failure["shortfall_rows"])
        candidates = [
            row
            for row in by_role[role]
            if row["csv_member"] != failure["csv_member"]
            and row["sealed_final_role"] == "false"
            and as_int(row["planning_capacity_rows"]) > 0
        ]
        candidates.sort(
            key=lambda r: (
                r["observed_in_issue27bx"] != "true",
                -as_int(r["planning_capacity_rows"]),
                r["csv_member"],
            )
        )
        remaining = shortfall
        rank = 1
        for cand in candidates:
            if remaining <= 0:
                break
            cap = as_int(cand["planning_capacity_rows"])
            if cap <= 0:
                continue
            take = min(remaining, cap)
            fallback_rows.append(
                {
                    "failed_role": role,
                    "failed_csv_member": failure["csv_member"],
                    "failed_target_rows": failure["target_rows"],
                    "failed_emitted_rows": failure["emitted_rows"],
                    "shortfall_rows": shortfall,
                    "fallback_rank": rank,
                    "fallback_csv_member": cand["csv_member"],
                    "fallback_pcap_member": cand["pcap_member"],
                    "fallback_planning_capacity_rows": cap,
                    "proposed_additional_rows": take,
                    "fallback_rule": "same_role_only_no_sealed_final_no_cross_role_borrowing",
                    "candidate_estimate_source": cand["estimate_source"],
                }
            )
            remaining -= take
            rank += 1
        if remaining > 0:
            fallback_rows.append(
                {
                    "failed_role": role,
                    "failed_csv_member": failure["csv_member"],
                    "failed_target_rows": failure["target_rows"],
                    "failed_emitted_rows": failure["emitted_rows"],
                    "shortfall_rows": shortfall,
                    "fallback_rank": "unfilled",
                    "fallback_csv_member": "",
                    "fallback_pcap_member": "",
                    "fallback_planning_capacity_rows": 0,
                    "proposed_additional_rows": 0,
                    "fallback_rule": "unfilled_requires_lower_role_quota_or_manual_contract_revision",
                    "candidate_estimate_source": "",
                }
            )
    return fallback_rows


def build_v2_plan(available_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_role = defaultdict(list)
    for row in available_rows:
        if row["sealed_final_role"] == "true" or row["role"] in SEALED_FINAL_ROLES:
            by_role[row["role"]].append(row)
        elif as_int(row["planning_capacity_rows"]) > 0:
            by_role[row["role"]].append(row)
    plan_rows: list[dict[str, Any]] = []
    for role, target in NEXT_LOCAL_ROLE_QUOTAS.items():
        candidates = sorted(
            by_role.get(role, []),
            key=lambda r: (r["observed_in_issue27bx"] != "true", -as_int(r["planning_capacity_rows"]), r["csv_member"]),
        )
        remaining = target
        for cand in candidates:
            if remaining <= 0:
                break
            cap = as_int(cand["planning_capacity_rows"])
            if cap <= 0:
                continue
            proposed = min(remaining, cap)
            plan_rows.append(
                {
                    "role": role,
                    "csv_member": cand["csv_member"],
                    "pcap_member": cand["pcap_member"],
                    "proposed_rows": proposed,
                    "role_target_rows": target,
                    "planning_capacity_rows": cap,
                    "estimate_source": cand["estimate_source"],
                    "report_only_role": cand["report_only_role"],
                    "sealed_final_role": cand["sealed_final_role"],
                    "selection_allowed": str(role == "attack_support_candidate_pool").lower(),
                    "plan_rule": "same_contract_role_capacity_aware",
                }
            )
            remaining -= proposed
        if remaining > 0:
            plan_rows.append(
                {
                    "role": role,
                    "csv_member": "",
                    "pcap_member": "",
                    "proposed_rows": 0,
                    "role_target_rows": target,
                    "planning_capacity_rows": 0,
                    "estimate_source": "",
                    "report_only_role": str(role in REPORT_ONLY_ROLES).lower(),
                    "sealed_final_role": str(role in SEALED_FINAL_ROLES).lower(),
                    "selection_allowed": "false",
                    "plan_rule": f"role_target_unfilled_by_{remaining}_rows_requires_lower_quota_or_contract_expansion",
                }
            )
    return plan_rows


def build_cache_manifest(available_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in available_rows:
        key_payload = {
            "frontend_schema_sha256": "gotham_kitsune_restored115_v1",
            "strategy": PRIMARY_STRATEGY,
            "csv_member": row["csv_member"],
            "pcap_member": row["pcap_member"],
            "role": row["role"],
            "warmup_packets": WARMUP_PACKETS,
        }
        cache_key = ab.sha256_bytes(json.dumps(key_payload, sort_keys=True).encode("utf-8"))
        rows.append(
            {
                "cache_key": cache_key,
                "role": row["role"],
                "csv_member": row["csv_member"],
                "pcap_member": row["pcap_member"],
                "strategy": PRIMARY_STRATEGY,
                "warmup_packets": WARMUP_PACKETS,
                "schema_id": "gotham_kitsune_restored115_v1",
                "cache_artifact_stem": f"{Path(row['csv_member']).stem}_{cache_key[:12]}",
                "should_cache_before_3m_retry": str(row["role"] in ATTACK_ROLES or as_int(row["planning_capacity_rows"]) >= 50_000).lower(),
                "sealed_final_role": row["sealed_final_role"],
                "cache_policy": "cache_X_y_sidecar_per_file_with_source_hashes_and_state_strategy",
            }
        )
    return rows


def role_totals(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for row in rows:
        totals[row["role"]] += as_int(row.get(field))
    return dict(sorted(totals.items()))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    contract = load_contract()
    available_rows = build_available_rows(contract)
    quota_vs_actual = build_quota_vs_actual()
    fallback_rows = choose_fallbacks(available_rows, quota_vs_actual)
    v2_plan = build_v2_plan(available_rows)
    cache_rows = build_cache_manifest(available_rows)

    write_csv(OUT / "file_available_rows_estimate.csv", available_rows)
    write_csv(OUT / "quota_plan_vs_actual.csv", quota_vs_actual)
    write_csv(OUT / "fallback_rule_table.csv", fallback_rows)
    write_csv(OUT / "materialization_v2_quota_plan.csv", v2_plan)
    write_csv(OUT / "cache_key_manifest.csv", cache_rows)

    role_observed = role_totals(quota_vs_actual, "emitted_rows")
    role_v2 = role_totals(v2_plan, "proposed_rows")
    shortfall_rows = [row for row in quota_vs_actual if as_int(row["shortfall_rows"]) > 0]
    final_leakage_ok = all(row["sealed_final_role"] == "true" or row["role"] not in SEALED_FINAL_ROLES for row in available_rows)
    no_cross_role_fallback = all(row["fallback_rule"].startswith("same_role_only") for row in fallback_rows if row.get("fallback_csv_member"))
    v2_total = sum(as_int(row["proposed_rows"]) for row in v2_plan)
    unfilled_v2 = [row for row in v2_plan if str(row["plan_rule"]).startswith("role_target_unfilled")]

    primary_verdict = (
        "quota_cache_repair_ready_for_500k_materialization_retry"
        if not unfilled_v2 and no_cross_role_fallback and final_leakage_ok
        else "quota_cache_repair_partial_needs_contract_or_quota_revision"
    )

    repair_report = [
        "# issue27bx2 Quota And Cache Repair Report",
        "",
        "This issue repairs the materialization planning layer only. It does not train models, tune thresholds, or rerun a formal benchmark.",
        "",
        "## Findings",
        "",
        f"- issue27bx emitted rows by role: `{json.dumps(role_observed, ensure_ascii=False)}`",
        f"- issue27bx file quota shortfalls: `{len(shortfall_rows)}` files",
        "- Shortfalls are treated as materialization planning issues, not model failures.",
        "- Same-role fallback is required; sealed final roles must never backfill dev/train roles.",
        "",
        "## Fallback Policy",
        "",
        "1. Use only files already assigned to the same contract role.",
        "2. Never borrow from `sealed_final_ood` or `sealed_final_attack`.",
        "3. Prefer files already verified by issue27bx when possible.",
        "4. If same-role capacity is still insufficient, lower that role quota or revise the contract explicitly.",
        "",
        "## Cache Policy",
        "",
        "- Cache per-file 115D outputs keyed by `(schema, state strategy, csv path, pcap path, role, warmup)`.",
        "- Cache must include source hashes, emitted rows, sidecar rows, numeric audit, and state strategy.",
        "- Attack PCAPs and large benign files should be cached before any 3M+ retry.",
    ]
    write_md(OUT / "quota_cache_repair_report.md", repair_report)

    cache_design = [
        "# issue27bx2 Per-file Cache Design",
        "",
        "The cache is a production-line accelerator, not a new dataset split.",
        "",
        "Required cache artifacts per source file:",
        "",
        "- `X_115D.npy`: rows emitted from one PCAP under one state strategy",
        "- `y.npy`: binary labels aligned to emitted rows",
        "- `sidecar.csv.gz`: row id, role, report-only flags, source paths, timestamps, state id",
        "- `numeric_audit.json`: finite rate, NaN/Inf counts, family health",
        "- `source_manifest.json`: source PCAP path/hash, CSV path/hash, schema hash, state strategy",
        "",
        "Cache keys are listed in `cache_key_manifest.csv`. A cache hit is valid only when every key input matches.",
        "",
        "The next materializer should concatenate per-file caches according to `materialization_v2_quota_plan.csv`; it must not recompute files whose cache keys already match.",
    ]
    write_md(OUT / "pcap_115d_cache_design.md", cache_design)

    summary = [
        "# issue27bx2 Summary",
        "",
        "1. issue27bx2 completed: yes",
        f"2. primary_verdict: `{primary_verdict}`",
        "3. task type: materialization quota/cache repair, no model run",
        f"4. issue27bx shortfall files: `{len(shortfall_rows)}`",
        f"5. no cross-role fallback rule: `{no_cross_role_fallback}`",
        f"6. sealed final used as fallback: `False`",
        f"7. proposed next local target rows: `{NEXT_LOCAL_TARGET_ROWS}`",
        f"8. proposed v2 rows by role: `{json.dumps(role_v2, ensure_ascii=False)}`",
        f"9. proposed v2 total rows: `{v2_total}`",
        f"10. v2 unfilled role targets: `{len(unfilled_v2)}`",
        "11. PCAP cache implemented as manifest/design only: yes",
        "12. large X/y materialization run: no",
        "13. model training: no",
        "14. formal benchmark: no",
        "15. next recommended issue: `issue27bx3_500k_cache_aware_materialization_retry`",
        "16. commit/push: not performed",
    ]
    write_md(OUT / "summary.md", summary)

    decision = [
        "# issue27bx2 Decision",
        "",
        f"primary_verdict: `{primary_verdict}`",
        "",
        "The previous issue27bx partial result is attributable to quota planning and local PCAP materialization cost. The next retry should use capacity-aware quotas and per-file cache keys before any larger replay.",
        "",
        "This decision does not validate model performance and does not authorize formal benchmark.",
    ]
    write_md(OUT / "issue27bx2_decision.md", decision)

    next_action = [
        "# issue27bx3 Next Action",
        "",
        "Recommended next task: `issue27bx3_500k_cache_aware_materialization_retry`.",
        "",
        "Goals:",
        "- materialize the v2 quota plan using same-role fallback",
        "- create reusable per-file 115D caches for slow attack PCAPs",
        "- verify X/y/sidecar shapes and hashes",
        "- keep final/report-only roles sealed",
        "- still do not run model performance experiments",
    ]
    write_md(OUT / "issue27bx3_next_action.md", next_action)

    role_access = [
        {"role": role, "fit_allowed": str(role not in REPORT_ONLY_ROLES).lower(), "threshold_allowed": str(role not in SEALED_FINAL_ROLES and role != "dev_future_attack_query").lower(), "support_selection_allowed": str(role == "attack_support_candidate_pool").lower(), "model_selection_allowed": str(role not in REPORT_ONLY_ROLES).lower(), "report_only": str(role in REPORT_ONLY_ROLES).lower()}
        for role in contract["roles"].keys()
    ]
    write_csv(OUT / "role_access_audit.csv", role_access)

    config = {
        "issue": ISSUE,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_contract": str(CONTRACT_PATH),
        "input_issue27bx_summary": str(BX_SUMMARY_PATH),
        "next_local_target_rows": NEXT_LOCAL_TARGET_ROWS,
        "next_local_role_quotas": NEXT_LOCAL_ROLE_QUOTAS,
        "primary_verdict": primary_verdict,
        "model_run": False,
        "formal_benchmark": False,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "run_type": "materialization_quota_cache_repair_no_model",
                "inputs": [str(CONTRACT_PATH), str(BX_ROLE_META_PATH), str(ROLE_INVENTORY_PATH)],
                "outputs": [
                    "file_available_rows_estimate.csv",
                    "quota_plan_vs_actual.csv",
                    "fallback_rule_table.csv",
                    "materialization_v2_quota_plan.csv",
                    "cache_key_manifest.csv",
                ],
                "forbidden": ["model_training", "formal_benchmark", "cross_role_fallback", "sealed_final_backfill"],
                "primary_verdict": primary_verdict,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_md(OUT / "command.txt", ["python repo/ood/issue27bx2_materialization_quota_cache_repair.py"])

    append_once(
        MAINLINE_DOCS / "mainline_handoff.md",
        ISSUE,
        [
            "## issue27bx2 Materialization Quota/Cache Repair",
            "",
            f"marker: `{ISSUE}`",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- issue27bx shortfalls were traced to quota/materialization planning, not model failure.",
            "- Next materialization should use same-role fallback and per-file cache keys.",
            "- Sealed final roles remain forbidden for fallback, fit, threshold, and selection.",
            "- Current stage remains data/interface preparation; no formal benchmark is authorized.",
        ],
    )
    append_once(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        ISSUE,
        [
            "## issue27bx2 Materialization Quota/Cache Repair",
            "",
            f"marker: `{ISSUE}`",
            "",
            "- Inputs: issue27bw larger contract, issue27bx role meta, archive listing.",
            "- Outputs: available row estimates, quota-vs-actual table, fallback rules, cache key manifest, v2 quota plan.",
            "- Next: issue27bx3 500k cache-aware materialization retry before model replay.",
        ],
    )

    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest_rows.append({"path": str(path.relative_to(ROOT)), "sha256": ab.file_hash(path), "bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)

    print(
        json.dumps(
            {
                "issue": ISSUE,
                "primary_verdict": primary_verdict,
                "shortfall_files": len(shortfall_rows),
                "v2_total_rows": v2_total,
                "out": str(OUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
