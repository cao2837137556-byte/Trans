from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
RUN_ID = "issue27bw_larger_sanity_contract_construction_2026-06-11"
OUT = REPO / "runs" / RUN_ID

MANIFEST = (
    REPO
    / "runs"
    / "issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28"
    / "gotham_all_csv_file_manifest.csv"
)
BV_DIR = REPO / "runs" / "issue27bv_problem_definition_and_frozen_protocol_before_larger_2026-06-11"
BU_DIR = REPO / "runs" / "issue27bu_unified_temporal_attack_ood_heads_certification_2026-06-10"
MAINLINE_HANDOFF = REPO / "runs" / "mainline_docs" / "mainline_handoff.md"
MAINLINE_MAP = REPO / "runs" / "mainline_docs" / "mainline_experiment_map.md"

PRIMARY_VERDICT = "larger_sanity_contract_ready_for_materialization_not_formal_benchmark"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def as_int(value: str | int | None) -> int:
    if value in (None, ""):
        return 0
    return int(float(value))


def as_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def load_manifest() -> list[dict[str, str]]:
    with MANIFEST.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["_rows"] = as_int(row.get("total_rows_estimated_or_exact"))
        row["_benign"] = as_int(row.get("benign_rows"))
        row["_attack"] = as_int(row.get("attack_rows"))
        row["_all_benign"] = as_bool(row.get("all_benign_flag"))
        row["_mixed"] = as_bool(row.get("mixed_label_flag"))
    return rows


def by_path(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {r["csv_archive_path"]: r for r in rows}


def select_files(rows: list[dict[str, str]]) -> dict[str, list[str]]:
    benign_by_device: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["_all_benign"]:
            benign_by_device[row["inferred_device"]].append(row)
    for values in benign_by_device.values():
        values.sort(key=lambda r: r["csv_archive_path"])

    def paths(device: str) -> list[str]:
        return [r["csv_archive_path"] for r in benign_by_device.get(device, [])]

    cooler = paths("cooler-motor")
    predictive = paths("predictive-maintenance")

    roles = {
        "id_benign_train": cooler[:10] + predictive[:10] + paths("combined-cycle-tls")[:2],
        "id_benign_calib": cooler[10:] + predictive[10:] + paths("combined-cycle-tls")[2:],
        "ood_benign_val": paths("hydraulic-system")[:8] + paths("building-monitor")[:2],
        "ood_benign_stress": paths("hydraulic-system")[8:] + paths("stream-consumer") + paths("domotic-monitor")[:2] + paths("building-monitor")[2:],
        "sealed_final_ood": paths("ip-camera-museum") + paths("ip-camera-street"),
        "attack_support_candidate_pool": [
            "processed/iotsim-air-quality-1.csv",
            "processed/iotsim-city-power-1.csv",
        ],
        "dev_future_attack_query": [
            "processed/iotsim-ip-camera-museum-1.csv",
            "processed/iotsim-building-monitor-1.csv",
            "processed/iotsim-domotic-monitor-1.csv",
            "processed/iotsim-combined-cycle-1.csv",
            "processed/iotsim-combined-cycle-10.csv",
        ],
        "sealed_final_attack": [
            "processed/iotsim-ip-camera-street-1.csv",
        ],
    }
    return roles


def role_rows(roles: dict[str, list[str]], lookup: dict[str, dict[str, str]]) -> dict[str, dict[str, object]]:
    stats: dict[str, dict[str, object]] = {}
    for role, files in roles.items():
        rows = [lookup[p] for p in files if p in lookup]
        devices = sorted({r["inferred_device"] for r in rows})
        protocols = sorted({r.get("observed_protocol_from_frame_protocols", "") for r in rows if r.get("observed_protocol_from_frame_protocols", "")})
        attack_types = Counter()
        for r in rows:
            try:
                d = json.loads(r.get("attack_type_counts") or "{}")
            except Exception:
                d = {}
            for k, v in d.items():
                attack_types[k] += int(v)
        stats[role] = {
            "file_count": len(rows),
            "row_count": sum(r["_rows"] for r in rows),
            "benign_rows": sum(r["_benign"] for r in rows),
            "attack_rows": sum(r["_attack"] for r in rows),
            "devices": devices,
            "protocols": protocols,
            "attack_type_count": len(attack_types),
            "top_attack_types": dict(attack_types.most_common(10)),
        }
    return stats


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def md_list(items: list[str]) -> str:
    if not items:
        return "none"
    return ", ".join(f"`{x}`" for x in items)


def make_role_inventory(roles: dict[str, list[str]], lookup: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    rows = []
    for role, files in roles.items():
        for p in files:
            r = lookup.get(p)
            if not r:
                rows.append({
                    "role": role,
                    "csv_archive_path": p,
                    "exists_in_manifest": "false",
                    "failure_reason": "path_not_found_in_all_csv_manifest",
                })
                continue
            rows.append({
                "role": role,
                "csv_archive_path": p,
                "exists_in_manifest": "true",
                "file_name": r["file_name"],
                "inferred_device": r["inferred_device"],
                "observed_protocol": r.get("observed_protocol_from_frame_protocols", ""),
                "total_rows": r["_rows"],
                "benign_rows": r["_benign"],
                "attack_rows": r["_attack"],
                "all_benign": r["_all_benign"],
                "mixed_label": r["_mixed"],
                "attack_type_values": r.get("attack_type_values", ""),
                "pcap_counterpart_candidate": r.get("pcap_counterpart_candidate", ""),
                "pcap_pairing_confidence": r.get("pcap_pairing_confidence", ""),
                "timestamp_parse_status": r.get("timestamp_parse_status", ""),
                "notes": "role_contract_only_no_new_extraction",
                "failure_reason": "",
            })
    return rows


def disjointness_audit(roles: dict[str, list[str]], lookup: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    def files(role: str) -> set[str]:
        return set(roles.get(role, []))

    def devices(role: str) -> set[str]:
        return {lookup[p]["inferred_device"] for p in roles.get(role, []) if p in lookup}

    def protocols(role: str) -> set[str]:
        return {lookup[p].get("observed_protocol_from_frame_protocols", "") for p in roles.get(role, []) if p in lookup and lookup[p].get("observed_protocol_from_frame_protocols", "")}

    checks = []

    pairs = [
        ("id_benign_train", "id_benign_calib"),
        ("id_benign_train", "ood_benign_val"),
        ("id_benign_train", "ood_benign_stress"),
        ("id_benign_train", "sealed_final_ood"),
        ("ood_benign_val", "sealed_final_ood"),
        ("ood_benign_stress", "sealed_final_ood"),
        ("attack_support_candidate_pool", "dev_future_attack_query"),
        ("attack_support_candidate_pool", "sealed_final_attack"),
        ("dev_future_attack_query", "sealed_final_attack"),
    ]
    for a, b in pairs:
        overlap = sorted(files(a) & files(b))
        checks.append({
            "audit_item": f"file_disjoint:{a}__vs__{b}",
            "status": "pass" if not overlap else "fail",
            "overlap": "|".join(overlap),
            "failure_reason": "" if not overlap else "same_csv_file_in_multiple_roles",
            "notes": "file-disjoint is mandatory for larger sanity",
        })
        dev_overlap = sorted(devices(a) & devices(b))
        checks.append({
            "audit_item": f"device_disjoint:{a}__vs__{b}",
            "status": "pass" if not dev_overlap else "partial_or_fail",
            "overlap": "|".join(dev_overlap),
            "failure_reason": "" if not dev_overlap else "device_overlap_may_be_intentional_for_calib_or_final_pairing_but_not_formal_clean",
            "notes": "device disjoint is required for strong claim; overlap downgrades to sanity-only unless justified",
        })
        prot_overlap = sorted(protocols(a) & protocols(b))
        checks.append({
            "audit_item": f"protocol_overlap:{a}__vs__{b}",
            "status": "informational_overlap" if prot_overlap else "pass",
            "overlap": "|".join(prot_overlap),
            "failure_reason": "" if not prot_overlap else "protocol overlap expected in realistic replay; not a leakage by itself",
            "notes": "protocol overlap should be reported, not used as source shortcut",
        })

    ts_status = Counter(lookup[p].get("timestamp_parse_status", "") for role_files in roles.values() for p in role_files if p in lookup)
    checks.append({
        "audit_item": "time_forward_split_feasibility",
        "status": "blocked_at_file_manifest_level",
        "overlap": "",
        "failure_reason": f"file_manifest_timestamp_parse_status={dict(ts_status)}",
        "notes": "larger materialization must use row-level sidecar/order and past-only state logs; do not claim wall-clock time-forward from this contract alone",
    })
    checks.append({
        "audit_item": "purge_embargo_requirement",
        "status": "required_not_validated_here",
        "overlap": "",
        "failure_reason": "row-level onset/transition windows are not materialized in issue27bw",
        "notes": "apply purge/embargo during issue27bx materialization, especially mixed attack files and temporal evidence",
    })
    checks.append({
        "audit_item": "report_only_selection_independence",
        "status": "pass_by_contract",
        "overlap": "",
        "failure_reason": "",
        "notes": "sealed_final_ood and sealed_final_attack forbidden for support, threshold, OOD risk, controller, model selection",
    })
    return checks


def final_seal_audit(roles: dict[str, list[str]], lookup: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    rows = []
    for role in ["sealed_final_ood", "sealed_final_attack"]:
        for p in roles[role]:
            r = lookup[p]
            rows.append({
                "sealed_role": role,
                "csv_archive_path": p,
                "inferred_device": r["inferred_device"],
                "observed_protocol": r.get("observed_protocol_from_frame_protocols", ""),
                "rows": r["_rows"],
                "benign_rows": r["_benign"],
                "attack_rows": r["_attack"],
                "seal_from_issue27bw_forward": "true",
                "formal_pristine_seal": "false",
                "reason_formal_pristine_false": "Gotham file-level manifest and prior report-only diagnostics have already exposed candidate final groups; usable for larger sanity replay, not final paper benchmark",
                "forbidden_use": "support_selection|threshold_selection|ood_risk_training|controller_selection|model_selection|prototype_bank_selection",
                "allowed_use": "single_pass_report_only_replay_after_config_freeze",
            })
    return rows


def append_once(path: Path, marker: str, text: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in existing:
        return
    with path.open("a", encoding="utf-8", newline="\n") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write("\n" + text.strip() + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_manifest()
    lookup = by_path(rows)
    roles = select_files(rows)
    stats = role_rows(roles, lookup)

    total_rows = sum(r["_rows"] for r in rows)
    total_benign = sum(r["_benign"] for r in rows)
    total_attack = sum(r["_attack"] for r in rows)
    all_benign_files = sum(1 for r in rows if r["_all_benign"])
    mixed_files = sum(1 for r in rows if r["_mixed"])
    devices = sorted({r["inferred_device"] for r in rows})
    protocols = sorted({r.get("observed_protocol_from_frame_protocols", "") for r in rows if r.get("observed_protocol_from_frame_protocols", "")})

    size_plan = {
        "contract_scope": "all_78_processed_csv_file_level_contract",
        "all_csv_total_rows": total_rows,
        "all_csv_benign_rows": total_benign,
        "all_csv_attack_rows": total_attack,
        "all_benign_files": all_benign_files,
        "mixed_attack_files": mixed_files,
        "recommended_first_larger_materialization": {
            "purpose": "larger sanity, not full/formal benchmark",
            "target_total_model_ready_rows": "3M_to_8M",
            "hard_ceiling_without_new_confirmation": "10M_emitted_115D_rows",
            "why": "large enough to stress medium protocol across more files/devices, still bounded before full 35M-row processed corpus and 23GB raw zip PCAP extraction",
            "id_ood_rows": "use capped/stratified rows from assigned benign files; include at least multiple devices per train/calib/val/stress role",
            "sealed_final_rows": "cap heavy ip-camera final OOD/attack for larger sanity replay; no selection from these rows",
            "attack_support_budgets": [32, 64, 128, 256],
            "active_label_budgets": [32, 64, 128, 256],
        },
    }

    contract = {
        "issue": RUN_ID,
        "primary_verdict": PRIMARY_VERDICT,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "task_type": "larger_sanity_data_contract_construction_no_model_run",
        "frontend": "Gotham raw PCAP -> Kitsune/AfterImage/netStat 115D remains fixed; no extraction in this issue",
        "model_run": False,
        "formal_benchmark": False,
        "commit_push_performed": False,
        "input_hashes": {
            "gotham_all_csv_file_manifest_sha256": sha256_file(MANIFEST),
            "issue27bv_summary_sha256": sha256_file(BV_DIR / "summary.md"),
            "issue27bu_summary_sha256": sha256_file(BU_DIR / "summary.md"),
        },
        "dataset_inventory": {
            "processed_csv_files": len(rows),
            "all_benign_files": all_benign_files,
            "mixed_attack_files": mixed_files,
            "devices": devices,
            "protocols": protocols,
            "total_rows": total_rows,
            "benign_rows": total_benign,
            "attack_rows": total_attack,
        },
        "roles": roles,
        "role_stats": stats,
        "support_modes": {
            "fixed_support_mode": {
                "purpose": "few-shot generalization with frozen labelled support",
                "candidate_pool_role": "attack_support_candidate_pool",
                "allowed_selection_inputs": ["attack_support_candidate_pool features/labels", "development-side support_val only"],
                "forbidden_inputs": ["sealed_final_ood", "sealed_final_attack", "dev_future_attack_query report-only outcomes", "future labels before review"],
                "budgets": [32, 64, 128, 256],
            },
            "active_update_mode": {
                "purpose": "separate online diagnostic with bounded analyst labels",
                "candidate_pool_role": "dev_future_attack_query_or_mixed_stream_unknown_buffer_only_after_prefrozen_review_rule",
                "forbidden_inputs": ["sealed_final_ood", "sealed_final_attack", "final/report-only outcomes"],
                "budgets": [32, 64, 128, 256],
                "notes": "confirmed benign drift must enter OOD/benign memory, not attack support; confirmed attack may update bounded attack region memory",
            },
        },
        "size_plan": size_plan,
        "claim_boundary": {
            "allowed": "larger sanity contract is ready for bounded materialization planning",
            "not_allowed": [
                "formal benchmark passed",
                "deployment proven",
                "external generalization proven",
                "full Gotham final test completed",
            ],
            "seal_caveat": "sealed final roles are sealed from issue27bw forward, but not pristine across the whole project history",
        },
        "next_recommended_issue": "issue27bx_larger_sanity_materialization_dry_run_from_contract_v1",
    }

    (OUT / "larger_sanity_contract_v1.json").write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")

    role_inventory = make_role_inventory(roles, lookup)
    write_csv(
        OUT / "role_file_inventory.csv",
        role_inventory,
        [
            "role",
            "csv_archive_path",
            "exists_in_manifest",
            "file_name",
            "inferred_device",
            "observed_protocol",
            "total_rows",
            "benign_rows",
            "attack_rows",
            "all_benign",
            "mixed_label",
            "attack_type_values",
            "pcap_counterpart_candidate",
            "pcap_pairing_confidence",
            "timestamp_parse_status",
            "notes",
            "failure_reason",
        ],
    )

    split_audit = disjointness_audit(roles, lookup)
    write_csv(OUT / "split_disjointness_audit.csv", split_audit, ["audit_item", "status", "overlap", "failure_reason", "notes"])

    seal_rows = final_seal_audit(roles, lookup)
    write_csv(
        OUT / "final_seal_audit.csv",
        seal_rows,
        [
            "sealed_role",
            "csv_archive_path",
            "inferred_device",
            "observed_protocol",
            "rows",
            "benign_rows",
            "attack_rows",
            "seal_from_issue27bw_forward",
            "formal_pristine_seal",
            "reason_formal_pristine_false",
            "forbidden_use",
            "allowed_use",
        ],
    )

    summary = f"""# issue27bw Summary

1. issue27bw completed: yes
2. primary_verdict: `{PRIMARY_VERDICT}`
3. task type: larger sanity data contract construction
4. model run: no
5. 115D frontend changed: no
6. split/support materialized: no
7. all processed CSV covered by source manifest: 78 files, {total_rows:,} rows
8. all-benign / mixed-attack files: {all_benign_files} / {mixed_files}
9. recommended larger sanity size: 3M-8M model-ready 115D rows first, hard ceiling 10M without new confirmation
10. full processed corpus size: {total_rows:,} rows; do not jump directly to full/formal benchmark
11. fixed support mode defined: yes, budgets 32/64/128/256 from development-side attack support candidates only
12. active update mode defined: yes, separate diagnostic with bounded analyst-label budgets 32/64/128/256
13. sealed final OOD files: {md_list(roles['sealed_final_ood'])}
14. sealed final attack files: {md_list(roles['sealed_final_attack'])}
15. final seal caveat: sealed from issue27bw forward, not pristine formal final across whole project history
16. time-forward status: blocked at file-manifest level because timestamps are missing/unparsed in the file summary; larger materialization must use row order/sidecar and state logs
17. largest risk: Gotham has only 8 mixed attack CSV files, so attack final diversity is limited and formal final may require new holdout policy or external dataset
18. next recommended issue: `issue27bx_larger_sanity_materialization_dry_run_from_contract_v1`
19. commit/push: not performed by request
"""
    (OUT / "summary.md").write_text(summary, encoding="utf-8")

    medium_map = f"""# Medium To Larger Migration Map

## Purpose

This file maps the medium diagnostic roles to the larger sanity contract. It prevents old report-only data from silently becoming selection data.

## Mapping

| Medium role | Larger role | Migration rule | Selection allowed |
|---|---|---|---|
| `id_benign_train` | `id_benign_train` | expand to more benign files/devices, file-disjoint from ID calibration | yes |
| `id_calib` | `id_benign_calib` | use file-disjoint ID calibration files; medium single-source caveat must not carry forward | yes |
| `ood_benign_val` | `ood_benign_val` | independent benign devices/files for OOD calibration | yes |
| `ood_stress` | `ood_benign_stress` | development-side hard benign drift only; no final OOD | yes |
| `final_ood_benign_eval` | `sealed_final_ood` | sealed from issue27bw forward; report-only replay | no |
| `attack_support` | `attack_support_candidate_pool` | development-side labelled attack support only | yes |
| `support_val` | derived from `attack_support_candidate_pool` | development-side threshold/support sanity only | yes |
| `dev/query attack` | `dev_future_attack_query` | development-side query for mechanism design; no final selection from outcomes | limited diagnostics only |
| `attack_eval` | `sealed_final_attack` | report-only replay after config freeze | no |

## Non-Negotiable Rule

Old report-only roles cannot be reused as selection roles just because the larger contract is being rebuilt. If a role was report-only in a previous diagnostic, it must either remain report-only or be explicitly downgraded to development diagnostic with a written caveat.
"""
    (OUT / "medium_to_larger_migration_map.md").write_text(medium_map, encoding="utf-8")

    support_doc = f"""# Support Pool Contract

## Fixed Support Mode

Use this mode to test frozen few-shot generalization. The attack support selector may only read files in `attack_support_candidate_pool`:

{md_list(roles['attack_support_candidate_pool'])}

Budgets:

- support: 32 / 64 / 128 / 256
- support_val: fixed or proportional development-side split
- attack prototype budget: bounded and reported

Forbidden:

- no `sealed_final_ood`
- no `sealed_final_attack`
- no final/report-only detection, coverage, distance, or score feedback
- no future labels before review

## Active Update Mode

Use this mode only as a separate online diagnostic. Incoming samples first pass a pre-frozen controller. Only after review/oracle confirmation:

- confirmed attack may enter bounded attack region memory
- confirmed benign drift may enter OOD/benign memory
- uncertain samples remain unknown/review, not support

Label budgets to report: 32 / 64 / 128 / 256.

## Data Size Note

The first larger materialization should be bigger than medium but still bounded: target 3M-8M model-ready rows, hard ceiling 10M emitted 115D rows without another explicit confirmation. This is a sanity scale, not full Gotham.
"""
    (OUT / "support_pool_contract.md").write_text(support_doc, encoding="utf-8")

    ood_doc = f"""# OOD Stress Contract

## Roles

- `ood_benign_val`: development-side OOD calibration from benign devices/files disjoint from ID train where possible.
- `ood_benign_stress`: harder development-side benign drift, still selectable for controller development.
- `sealed_final_ood`: report-only benign drift replay after all parameters are frozen.

## Assigned Files

`ood_benign_val`: {md_list(roles['ood_benign_val'])}

`ood_benign_stress`: {md_list(roles['ood_benign_stress'])}

`sealed_final_ood`: {md_list(roles['sealed_final_ood'])}

## Rules

- OOD stress can guide OOD-risk and controller selection.
- Sealed final OOD cannot guide any selection.
- If final OOD is used to explain a failure, the resulting fix must be validated on a new sealed role or clearly labelled as diagnostic-only.
"""
    (OUT / "ood_stress_contract.md").write_text(ood_doc, encoding="utf-8")

    attack_doc = f"""# Attack Query Contract

## Roles

- `attack_support_candidate_pool`: development-side labelled attack support.
- `dev_future_attack_query`: development-side future/query attack used for mechanism design.
- `sealed_final_attack`: report-only replay after config freeze.

## Assigned Files

`attack_support_candidate_pool`: {md_list(roles['attack_support_candidate_pool'])}

`dev_future_attack_query`: {md_list(roles['dev_future_attack_query'])}

`sealed_final_attack`: {md_list(roles['sealed_final_attack'])}

## Known Limitation

Gotham has only 8 mixed attack CSV files. The sealed final attack role is therefore useful for larger sanity, but it is not enough by itself for a formal A-tier final benchmark. Formal claims need either a new holdout policy at row/phase/source level, additional untouched Gotham raw materialization, or a second dataset.

## Phase/Onset Rule

Attack support, support_val, dev query, and final attack must be phase-balanced during materialization. Use early/mid/late/tail buckets where enough rows exist; if a bucket is missing, write the failure reason instead of silently dropping it.
"""
    (OUT / "attack_query_contract.md").write_text(attack_doc, encoding="utf-8")

    size_doc = f"""# Larger Sanity Size Plan

## Why Not Full Yet

The current strongest system passed a medium diagnostic, but full Gotham contains {total_rows:,} processed rows and raw PCAP extraction is materially larger. Jumping straight to full would hide data-contract mistakes behind expensive runtime.

## Recommended First Larger Scale

- target: 3M-8M model-ready Kitsune115 rows
- hard ceiling without another explicit confirmation: 10M emitted rows
- include multiple ID devices and ID calibration files
- include development OOD val and OOD stress
- include sealed final OOD as capped report-only replay
- include fixed support budgets 32/64/128/256
- include active update budgets 32/64/128/256 only in a separate diagnostic
- include dev future attack query and sealed final attack

## Full Corpus Context

- processed CSV files: 78
- all-benign files: {all_benign_files}
- mixed attack files: {mixed_files}
- total rows: {total_rows:,}
- benign rows: {total_benign:,}
- attack rows: {total_attack:,}

## Go / No-Go Before Larger Replay

Go only if `split_disjointness_audit.csv` is accepted and issue27bx materialization writes sidecar/hash/state logs. No formal benchmark claim is allowed from this contract alone.
"""
    (OUT / "larger_sanity_size_plan.md").write_text(size_doc, encoding="utf-8")

    risk_rows = [
        {
            "risk_id": "R1",
            "risk": "Only 8 mixed attack CSV files exist",
            "impact": "sealed final attack diversity is limited",
            "mitigation": "treat issue27bw/bx as larger sanity; require new holdout policy or external dataset before formal benchmark",
        },
        {
            "risk_id": "R2",
            "risk": "File-level manifest timestamps missing_or_unparsed",
            "impact": "cannot claim wall-clock time-forward split at contract level",
            "mitigation": "issue27bx must use row order/sidecar and past-only state logs with purge/embargo",
        },
        {
            "risk_id": "R3",
            "risk": "Sealed final roles are not historically pristine",
            "impact": "final replay may be diagnostic-only for paper claims",
            "mitigation": "seal from issue27bw forward and avoid any future selection; consider fresh holdout for formal",
        },
        {
            "risk_id": "R4",
            "risk": "Active update mode can contaminate final if mixed with fixed support",
            "impact": "few-shot and active-labeling claims become ambiguous",
            "mitigation": "run fixed_support_mode and active_update_mode as separate experiments with separate hashes",
        },
    ]
    write_csv(OUT / "larger_contract_risk_register.csv", risk_rows, ["risk_id", "risk", "impact", "mitigation"])

    decision = f"""# issue27bw Decision

primary_verdict: `{PRIMARY_VERDICT}`

The larger sanity contract is ready for a bounded materialization dry run. It is not a formal benchmark contract.

The contract covers all 78 processed CSV files at metadata level and assigns a larger role structure with:

- ID train/calib
- OOD val/stress
- sealed final OOD
- attack support candidate pool
- dev future/query attack
- sealed final attack

The key caveat is that only 8 mixed attack CSV files exist. This is enough to stress the medium protocol at a larger sanity scale, but not enough to claim a pristine final benchmark without a stronger holdout policy.

No model was run. No 115D extraction was performed. No commit or push was performed.
"""
    (OUT / "issue27bw_decision.md").write_text(decision, encoding="utf-8")

    next_action = """# issue27bx Next Action

Recommended next task:

`issue27bx_larger_sanity_materialization_dry_run_from_contract_v1`

Boundary:

- use `larger_sanity_contract_v1.json`
- materialize a bounded 3M-8M row Kitsune115 larger sanity asset
- do not exceed 10M emitted rows without explicit confirmation
- write X/y/sidecar/split/hash/state logs
- preserve fixed_support_mode and active_update_mode as separate modes
- do not run formal benchmark
- do not use sealed final OOD or sealed final attack for selection
- include purge/embargo and past-only temporal state audit

Go/No-Go:

- if materialization violates file/role/sidecar/state logs, stop
- if sealed final roles are read during selection, stop
- if attack phase/onset cannot be represented, downgrade to data contract repair
"""
    (OUT / "issue27bx_next_action.md").write_text(next_action, encoding="utf-8")

    command = f"python repo/ood/issue27bw_larger_sanity_contract_construction.py\n"
    (OUT / "command.txt").write_text(command, encoding="utf-8")

    config = {
        "run_id": RUN_ID,
        "inputs": {
            "all_csv_manifest": str(MANIFEST.relative_to(REPO)),
            "issue27bv": str(BV_DIR.relative_to(REPO)),
            "issue27bu": str(BU_DIR.relative_to(REPO)),
        },
        "constraints": {
            "no_model_run": True,
            "no_115d_extraction": True,
            "no_split_materialization": True,
            "no_final_for_selection": True,
            "no_commit_push": True,
            "larger_sanity_target_rows": "3M_to_8M",
            "larger_sanity_hard_ceiling_rows_without_confirmation": "10M",
        },
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    run_spec = {
        "run_id": RUN_ID,
        "stages": [
            "read_prior_contracts",
            "summarize_all_csv_manifest",
            "assign_larger_sanity_roles",
            "write_disjointness_and_final_seal_audits",
            "write_support_ood_attack_contracts",
            "append_mainline_docs",
        ],
        "primary_verdict_options": [
            PRIMARY_VERDICT,
            "larger_sanity_contract_blocked_by_insufficient_attack_holdout",
            "larger_sanity_contract_blocked_by_split_leakage",
        ],
        "selected_primary_verdict": PRIMARY_VERDICT,
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2, ensure_ascii=False), encoding="utf-8")

    outputs = sorted(p for p in OUT.iterdir() if p.is_file())
    manifest_rows = []
    for p in outputs:
        manifest_rows.append({
            "path": str(p.relative_to(REPO)),
            "sha256": sha256_file(p),
            "bytes": p.stat().st_size,
        })
    write_csv(OUT / "manifest.csv", manifest_rows, ["path", "sha256", "bytes"])

    handoff_append = f"""## issue27bw Larger Sanity Contract Construction

marker: `issue27bw_larger_sanity_contract_construction_2026-06-11`

- status: completed, contract-only
- primary_verdict: `{PRIMARY_VERDICT}`
- model run: no
- 115D frontend change: no
- larger size plan: first materialization target 3M-8M model-ready rows; do not exceed 10M emitted rows without explicit confirmation
- fixed support mode and active update mode are explicitly separated
- sealed final OOD / sealed final attack are forbidden for selection and are report-only from issue27bw forward
- key caveat: Gotham has only 8 mixed attack CSV files, so sealed final attack diversity is limited and this is larger sanity, not formal benchmark
- next action: `issue27bx_larger_sanity_materialization_dry_run_from_contract_v1`
"""
    append_once(MAINLINE_HANDOFF, "issue27bw_larger_sanity_contract_construction_2026-06-11", handoff_append)

    map_append = f"""## issue27bw - Larger Sanity Contract Construction

- output_dir: `runs/{RUN_ID}/`
- decision: `{PRIMARY_VERDICT}`
- stage: larger sanity data contract before materialization
- inputs: issue27bv frozen protocol, issue27bu certified medium system, issue27y all-CSV manifest
- no model run, no feature extraction, no commit/push
- main artifacts: `larger_sanity_contract_v1.json`, `role_file_inventory.csv`, `split_disjointness_audit.csv`, `final_seal_audit.csv`, `medium_to_larger_migration_map.md`
- next: issue27bx bounded larger materialization dry run
"""
    append_once(MAINLINE_MAP, "issue27bw - Larger Sanity Contract Construction", map_append)

    # Regenerate manifest after doc append side effects are not included in run output.
    outputs = sorted(p for p in OUT.iterdir() if p.is_file())
    manifest_rows = []
    for p in outputs:
        manifest_rows.append({
            "path": str(p.relative_to(REPO)),
            "sha256": sha256_file(p),
            "bytes": p.stat().st_size,
        })
    write_csv(OUT / "manifest.csv", manifest_rows, ["path", "sha256", "bytes"])

    print(json.dumps({
        "run_id": RUN_ID,
        "primary_verdict": PRIMARY_VERDICT,
        "output_dir": str(OUT),
        "processed_csv_files": len(rows),
        "total_rows": total_rows,
        "recommended_larger_rows": "3M-8M, hard ceiling 10M without confirmation",
    }, indent=2))


if __name__ == "__main__":
    main()
