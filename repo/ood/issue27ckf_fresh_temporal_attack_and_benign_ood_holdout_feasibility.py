from __future__ import annotations

import csv
import hashlib
import json
import math
import struct
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT.parents[1] / "datasets" / "gotham2025"
ZIP_PATH = DATA_ROOT / "raw" / "GothamDataset2025.zip"
ISSUE = (
    "issue27ckf_fresh_temporal_attack_and_benign_ood_holdout_"
    "feasibility_2026-06-22"
)
OUT = ROOT / "runs" / ISSUE

BZ = (
    ROOT
    / "runs"
    / "issue27bz_slurm_1m_cache_execution_and_certified_merge_2026-06-14"
)
CC = (
    ROOT
    / "runs"
    / "issue27cc_targeted_multitype_attack_materialization_and_onset_realign_2026-06-14"
)
CF = (
    ROOT
    / "runs"
    / "issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_2026-06-16"
)
CH = (
    ROOT
    / "runs"
    / "issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17"
)

DEV_BENIGN_ROLES = {
    "id_benign_train",
    "id_benign_calib",
    "ood_benign_val",
    "ood_benign_stress",
}
SEALED_ROLES = {"sealed_final_ood", "sealed_final_attack_exact_realign"}
CURRENT_ATTACK_DEV_ROLES = {
    "attack_support_candidate_pool_targeted",
    "same_file_time_forward_dev_query_exact",
    "dev_future_attack_query_exact",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in rows)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_md(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def device_key(member: str) -> str:
    name = Path(member).name
    if name.endswith(".pcap"):
        name = name[:-5]
        if "_0-0_to_" in name:
            name = name.split("_0-0_to_", 1)[0]
    elif name.endswith(".csv"):
        name = name[:-4]
    return name


def csv_for_pcap(member: str) -> str:
    return f"processed/{device_key(member)}.csv"


def scenario(member: str) -> str:
    parts = member.replace("\\", "/").split("/")
    if len(parts) >= 3 and parts[0] == "raw":
        return parts[1] if parts[1] == "benign" else parts[2]
    return ""


def label_matches_scenario(label: str, scenario_name: str) -> bool:
    if scenario_name == "coap-amplificator":
        return label == "CoAP Amplification"
    if scenario_name == "merlin":
        return label.startswith("Merlin ")
    if scenario_name == "mirai-dos":
        return label.startswith("Mirai ") and label.endswith("Flooding")
    if scenario_name == "mirai-infection":
        return label in {
            "C&C Communication",
            "File Download",
            "Ingress Tool Transfer",
            "Mirai C&C Communication",
            "Reporting",
        }
    if scenario_name == "network-scanning":
        return label in {"TCP Scan", "UDP Scan", "Telnet Brute Force"}
    return False


def pcap_stats(data: bytes) -> dict[str, Any]:
    if len(data) < 24:
        return {
            "packet_count": 0,
            "first_timestamp": "",
            "last_timestamp": "",
            "duration_seconds": "",
            "parse_complete": False,
        }
    magic = data[:4]
    little = magic in {b"\xd4\xc3\xb2\xa1", b"M<\xb2\xa1"}
    endian = "<" if little else ">"
    nano = magic in {b"M<\xb2\xa1", b"\xa1\xb2<M"}
    offset = 24
    count = 0
    first = None
    last = None
    while offset + 16 <= len(data):
        ts_sec, ts_frac, captured, _original = struct.unpack_from(
            endian + "IIII", data, offset
        )
        offset += 16
        if offset + captured > len(data):
            break
        timestamp = ts_sec + ts_frac / (1e9 if nano else 1e6)
        if first is None:
            first = timestamp
        last = timestamp
        count += 1
        offset += captured
    return {
        "packet_count": count,
        "first_timestamp": first if first is not None else "",
        "last_timestamp": last if last is not None else "",
        "duration_seconds": (
            last - first if first is not None and last is not None else ""
        ),
        "parse_complete": offset == len(data),
    }


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def intersection_length(
    intervals_a: list[tuple[int, int]],
    intervals_b: list[tuple[int, int]],
) -> int:
    a = merge_intervals(intervals_a)
    b = merge_intervals(intervals_b)
    i = 0
    j = 0
    total = 0
    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])
        if start <= end:
            total += end - start + 1
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


def tail_length(
    exact_intervals: list[tuple[int, int]],
    last_planned_row: int | None,
) -> int:
    if last_planned_row is None:
        return sum(end - start + 1 for start, end in merge_intervals(exact_intervals))
    total = 0
    for start, end in merge_intervals(exact_intervals):
        if end <= last_planned_row:
            continue
        total += end - max(start, last_planned_row + 1) + 1
    return total


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not ZIP_PATH.exists():
        raise FileNotFoundError(ZIP_PATH)

    benign_plan = read_csv(BZ / "materialization_file_plan.csv")
    certified_attack = read_csv(CH / "certified_chunk_manifest.csv")
    pairing = read_csv(CC / "pcap_pairing_requirement_audit.csv")
    segment_inventory = read_csv(CC / "attack_label_segment_inventory_scanned.csv")
    targeted_plan = read_csv(CC / "targeted_exact_label_materialization_plan.csv")
    support_allocation = read_csv(CF / "support_selection_allocation.csv")
    current_labels = {
        row["exact_attack_label"] for row in support_allocation
    }

    roles_by_pcap: dict[str, set[str]] = defaultdict(set)
    csv_roles: dict[str, set[str]] = defaultdict(set)
    for row in benign_plan:
        roles_by_pcap[row["pcap_member"]].add(row["role"])
        csv_roles[row["csv_member"]].add(row["role"])
    for row in certified_attack:
        roles_by_pcap[row["source_pcap"]].add(row["role"])
        csv_roles[row["source_csv"]].add(row["role"])

    pairing_candidates: set[str] = set()
    preferred_pairings: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pairing:
        for candidate in row["all_pcap_candidates"].split("|"):
            if candidate:
                pairing_candidates.add(candidate)
        preferred_pairings[row["preferred_pcap_candidate"]].append(row)

    label_intervals: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    label_rows: Counter[tuple[str, str]] = Counter()
    labels_by_csv: dict[str, set[str]] = defaultdict(set)
    for row in segment_inventory:
        key = (row["csv_member"], row["label"])
        start = int(row["segment_start_row"])
        end = int(row["segment_end_row"])
        label_intervals[key].append((start, end))
        label_rows[key] += int(row["segment_rows"])
        labels_by_csv[row["csv_member"]].add(row["label"])

    planned_intervals: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    planned_roles: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in targeted_plan:
        key = (row["csv_member"], row["attack_type"])
        planned_intervals[key].append(
            (int(row["planned_start_row"]), int(row["planned_end_row"]))
        )
        planned_roles[key].add(row["plan_role"])

    archive_rows: list[dict[str, Any]] = []
    malicious_members: list[str] = []
    benign_members: list[str] = []
    csv_members: list[str] = []
    zip_info: dict[str, zipfile.ZipInfo] = {}
    with zipfile.ZipFile(ZIP_PATH) as z:
        for info in z.infolist():
            zip_info[info.filename] = info
            if info.filename.endswith(".pcap"):
                category = (
                    "benign_pcap"
                    if "/benign/" in info.filename
                    else "malicious_pcap"
                )
                if category == "benign_pcap":
                    benign_members.append(info.filename)
                else:
                    malicious_members.append(info.filename)
            elif info.filename.endswith(".csv"):
                category = "processed_csv"
                csv_members.append(info.filename)
            else:
                category = "other"
            archive_rows.append(
                {
                    "member": info.filename,
                    "category": category,
                    "scenario": scenario(info.filename),
                    "device_key": device_key(info.filename),
                    "file_size": info.file_size,
                    "compressed_size": info.compress_size,
                }
            )

        pcap_ledger: list[dict[str, Any]] = []
        unused_malicious: list[dict[str, Any]] = []
        pair_candidates: list[dict[str, Any]] = []
        for member in sorted(malicious_members + benign_members):
            roles = roles_by_pcap.get(member, set())
            if roles & SEALED_ROLES:
                exposure = "reserved_report_only"
            elif roles:
                exposure = "feature_materialized_dev"
            elif member in pairing_candidates:
                exposure = "metadata_scanned_only"
            else:
                exposure = "archive_only"
            pcap_ledger.append(
                {
                    "pcap_member": member,
                    "traffic_kind": (
                        "benign" if member in benign_members else "malicious"
                    ),
                    "scenario": scenario(member),
                    "device_key": device_key(member),
                    "roles": "|".join(sorted(roles)),
                    "exposure_level": exposure,
                    "feature_materialized": bool(roles),
                    "sealed_report_only": bool(roles & SEALED_ROLES),
                    "metadata_pairing_candidate": member in pairing_candidates,
                    "file_size": zip_info[member].file_size,
                }
            )

        for member in sorted(malicious_members):
            if roles_by_pcap.get(member):
                continue
            stats = pcap_stats(z.read(member))
            source_csv = csv_for_pcap(member)
            scenario_name = scenario(member)
            matching_labels = sorted(
                label
                for label in labels_by_csv.get(source_csv, set())
                if label_matches_scenario(label, scenario_name)
            )
            current_matching = sorted(set(matching_labels) & current_labels)
            matching_rows = sum(
                label_rows[(source_csv, label)] for label in matching_labels
            )
            current_matching_rows = sum(
                label_rows[(source_csv, label)] for label in current_matching
            )
            preferred_labels = sorted(
                {
                    row["attack_type"]
                    for row in preferred_pairings.get(member, [])
                }
            )
            row = {
                "malicious_pcap": member,
                "source_csv": source_csv,
                "scenario": scenario_name,
                "device_key": device_key(member),
                **stats,
                "metadata_exposure": (
                    "pairing_candidate_scanned"
                    if member in pairing_candidates
                    else "archive_only"
                ),
                "scenario_matching_exact_labels": "|".join(matching_labels),
                "scenario_matching_exact_rows": matching_rows,
                "current_region_matching_labels": "|".join(current_matching),
                "current_region_matching_rows": current_matching_rows,
                "preferred_for_labels": "|".join(preferred_labels),
                "pairing_verification_required": (
                    member not in preferred_pairings
                    or any(
                        r["requires_pcap_pairing_verification"].lower() == "true"
                        for r in preferred_pairings.get(member, [])
                    )
                ),
                "relevant_to_current_region_certification": bool(
                    current_matching and current_matching_rows > 0
                ),
            }
            unused_malicious.append(row)

            benign_member = f"raw/benign/{Path(member).name}"
            benign_exists = benign_member in zip_info
            benign_roles = roles_by_pcap.get(benign_member, set())
            benign_fresh = (
                benign_exists
                and not benign_roles
                and benign_member not in pairing_candidates
            )
            benign_stats = (
                pcap_stats(z.read(benign_member)) if benign_exists else {}
            )
            if (
                row["relevant_to_current_region_certification"]
                and benign_fresh
            ):
                status = "eligible_fresh_pair_for_current_regions"
            elif matching_rows > 0 and benign_fresh:
                status = "fresh_pair_but_attack_labels_outside_current_regions"
            elif not matching_rows:
                status = "no_scenario_matching_exact_labels"
            elif not benign_exists:
                status = "no_matched_benign_pcap"
            else:
                status = "matched_benign_not_fresh"
            pair_candidates.append(
                {
                    **row,
                    "benign_pcap": benign_member if benign_exists else "",
                    "benign_roles": "|".join(sorted(benign_roles)),
                    "benign_fresh": benign_fresh,
                    "benign_packet_count": benign_stats.get("packet_count", ""),
                    "benign_first_timestamp": benign_stats.get(
                        "first_timestamp", ""
                    ),
                    "benign_last_timestamp": benign_stats.get(
                        "last_timestamp", ""
                    ),
                    "attack_benign_start_gap_seconds": (
                        float(row["first_timestamp"])
                        - float(benign_stats["first_timestamp"])
                        if row["first_timestamp"] != ""
                        and benign_stats.get("first_timestamp", "") != ""
                        else ""
                    ),
                    "candidate_status": status,
                }
            )

    residual_rows: list[dict[str, Any]] = []
    for key in sorted(label_intervals):
        csv_member, label = key
        if label not in current_labels:
            continue
        source_role_set = csv_roles.get(csv_member, set())
        if source_role_set & SEALED_ROLES:
            freshness_class = "reserved_report_only_forbidden"
        elif source_role_set:
            freshness_class = "same_capture_residual_development_only"
        else:
            freshness_class = "source_unmaterialized"
        exact = label_intervals[key]
        planned = planned_intervals.get(key, [])
        total = sum(end - start + 1 for start, end in merge_intervals(exact))
        covered = intersection_length(exact, planned)
        last_planned = (
            max(end for _start, end in planned) if planned else None
        )
        residual_rows.append(
            {
                "csv_member": csv_member,
                "exact_attack_label": label,
                "source_roles": "|".join(sorted(csv_roles.get(csv_member, set()))),
                "exact_rows": total,
                "planned_unique_rows": covered,
                "unplanned_exact_rows": total - covered,
                "tail_rows_after_last_planned_row": tail_length(
                    exact, last_planned
                ),
                "last_planned_row": (
                    last_planned if last_planned is not None else ""
                ),
                "freshness_class": freshness_class,
            }
        )

    csv_ledger: list[dict[str, Any]] = []
    malicious_by_csv: dict[str, list[str]] = defaultdict(list)
    benign_by_csv: dict[str, str] = {}
    for member in malicious_members:
        malicious_by_csv[csv_for_pcap(member)].append(member)
    for member in benign_members:
        benign_by_csv[csv_for_pcap(member)] = member
    for member in sorted(csv_members):
        roles = csv_roles.get(member, set())
        csv_ledger.append(
            {
                "csv_member": member,
                "device_key": device_key(member),
                "current_roles": "|".join(sorted(roles)),
                "current_role_count": len(roles),
                "benign_pcap": benign_by_csv.get(member, ""),
                "benign_pcap_roles": "|".join(
                    sorted(
                        roles_by_pcap.get(
                            benign_by_csv.get(member, ""), set()
                        )
                    )
                ),
                "malicious_pcap_count": len(malicious_by_csv.get(member, [])),
                "malicious_pcaps_materialized": sum(
                    bool(roles_by_pcap.get(p))
                    for p in malicious_by_csv.get(member, [])
                ),
                "exact_labels_scanned": "|".join(
                    sorted(labels_by_csv.get(member, set()) - {"Unknown"})
                ),
                "metadata_label_inventory_scanned": member in labels_by_csv,
            }
        )

    eligible_pairs = [
        row
        for row in pair_candidates
        if row["candidate_status"]
        == "eligible_fresh_pair_for_current_regions"
    ]
    noncurrent_pairs = [
        row
        for row in pair_candidates
        if row["candidate_status"]
        == "fresh_pair_but_attack_labels_outside_current_regions"
    ]
    unused_benign_count = sum(
        row["traffic_kind"] == "benign"
        and row["exposure_level"] in {"archive_only", "metadata_scanned_only"}
        for row in pcap_ledger
    )
    sealed_attack_pcaps = [
        row["pcap_member"]
        for row in pcap_ledger
        if row["traffic_kind"] == "malicious"
        and row["sealed_report_only"]
    ]
    residual_dev_total = sum(
        int(row["unplanned_exact_rows"]) for row in residual_rows
        if row["freshness_class"]
        == "same_capture_residual_development_only"
    )
    residual_sealed_total = sum(
        int(row["unplanned_exact_rows"]) for row in residual_rows
        if row["freshness_class"] == "reserved_report_only_forbidden"
    )

    if eligible_pairs:
        verdict = "fresh_current_region_pair_available_materialization_allowed"
        next_action = (
            "freeze_pair_contract_and_prepare_hpc_feature_materialization"
        )
    else:
        verdict = (
            "no_fresh_current_region_two_sided_pair_in_local_gotham_archive"
        )
        next_action = (
            "define_new_gotham_capture_or_second_environment_acquisition_"
            "contract"
        )

    write_csv(OUT / "archive_member_inventory.csv", archive_rows)
    write_csv(OUT / "pcap_role_ledger.csv", pcap_ledger)
    write_csv(OUT / "processed_csv_role_ledger.csv", csv_ledger)
    write_csv(
        OUT / "unused_malicious_pcap_feasibility.csv", unused_malicious
    )
    write_csv(OUT / "fresh_pair_candidates.csv", pair_candidates)
    write_csv(
        OUT / "same_capture_residual_attack_rows.csv", residual_rows
    )
    write_csv(
        OUT / "role_access_audit.csv",
        [
            {
                "stage": "archive_inventory",
                "access": "zip central directory and member metadata",
                "feature_materialization": False,
                "model_or_region_evaluation": False,
                "sealed_outcome_access": False,
            },
            {
                "stage": "small_unused_pcap_feasibility",
                "access": "packet headers for four unmaterialized malicious pcaps and matched benign pcaps",
                "feature_materialization": False,
                "model_or_region_evaluation": False,
                "sealed_outcome_access": False,
            },
            {
                "stage": "historical_role_ledger",
                "access": "existing role and exact-label manifests only",
                "feature_materialization": False,
                "model_or_region_evaluation": False,
                "sealed_outcome_access": False,
            },
        ],
    )
    result = {
        "issue": ISSUE,
        "primary_verdict": verdict,
        "archive_sha256": sha256_file(ZIP_PATH),
        "processed_csv_members": len(csv_members),
        "benign_pcaps": len(benign_members),
        "malicious_pcaps": len(malicious_members),
        "feature_materialized_malicious_pcaps": sum(
            bool(roles_by_pcap.get(member)) for member in malicious_members
        ),
        "unmaterialized_malicious_pcaps": len(unused_malicious),
        "unused_benign_pcaps": unused_benign_count,
        "eligible_fresh_current_region_pairs": len(eligible_pairs),
        "fresh_pairs_outside_current_region_labels": len(noncurrent_pairs),
        "same_capture_unplanned_current_label_rows": residual_dev_total,
        "sealed_source_unplanned_current_label_rows": residual_sealed_total,
        "same_capture_residual_is_independent_holdout": False,
        "sealed_attack_pcaps_reserved_not_consumed": sealed_attack_pcaps,
        "sealed_outcome_access": False,
        "feature_materialization": False,
        "hpc_job_authorized": bool(eligible_pairs),
        "next_action": next_action,
    }
    write_json(OUT / "results.json", result)
    write_json(
        OUT / "config.json",
        {
            "zip_path": str(ZIP_PATH),
            "fresh_pair_requires_current_support_label": True,
            "same_device_benign_pair_required": True,
            "sealed_roles_forbidden": sorted(SEALED_ROLES),
            "same_capture_residual_class": (
                "development_diagnostic_only_not_independent_holdout"
            ),
        },
    )
    write_md(
        OUT / "new_data_acquisition_contract.md",
        [
            "# New Data Acquisition Contract",
            "",
            "Use this contract only if the local archive has no eligible fresh pair.",
            "",
            "## Preferred Route",
            "",
            "Run a new reproducible Gotham capture rather than selecting more rows from an already used capture.",
            "",
            "Minimum target scope:",
            "",
            "- target attacks: Mirai GRE Flooding, Mirai UDP Flooding, and Mirai TCP Flooding;",
            "- at least two independent attack sessions per target label;",
            "- exact packet-level labels with raw PCAP and timestamp-aligned CSV metadata;",
            "- matched benign traffic from the same declared device/environment era;",
            "- at least two benign sessions and a target of at least 100,000 benign packets for stable low-FPR estimation;",
            "- at least 10,000 exact-labelled attack packets per target label, subject to session-level reporting rather than treating packets as independent;",
            "- new run IDs, seeds, timestamps, and hashes recorded before feature extraction.",
            "",
            "## Freeze Rule",
            "",
            "Before opening any region result, freeze:",
            "",
            "- B0 and the single selected repair candidate;",
            "- Kitsune115 state strategy;",
            "- S3 transform, prototype rule, shell rule, and activation gates;",
            "- attack and benign source manifests;",
            "- packet/session bootstrap reporting plan;",
            "- a one-pass decision rule with no return to support selection.",
            "",
            "A second public environment is an alternative only if raw PCAP, exact labels, timestamps, and compatible online feature extraction are available. It must not be treated as interchangeable with Gotham without a separate semantic audit.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27ckf Fresh Holdout Feasibility Summary",
            "",
            f"primary_verdict: `{verdict}`",
            "",
            f"- archive processed CSV members: `{len(csv_members)}`",
            f"- archive malicious PCAPs: `{len(malicious_members)}`",
            f"- malicious PCAPs already feature-materialized: `{result['feature_materialized_malicious_pcaps']}`",
            f"- malicious PCAPs not feature-materialized: `{len(unused_malicious)}`",
            f"- unused benign PCAPs: `{unused_benign_count}`",
            f"- eligible fresh pairs for current ten regions: `{len(eligible_pairs)}`",
            f"- fresh pairs whose labels are outside current regions: `{len(noncurrent_pairs)}`",
            f"- same-capture development residual rows for current labels: `{residual_dev_total}`",
            f"- sealed-source residual rows that remain forbidden: `{residual_sealed_total}`",
            "- same-capture residual rows are independent holdout: `false`",
            "- sealed final consumed: `false`",
            "- HPC materialization authorized: "
            f"`{str(bool(eligible_pairs)).lower()}`",
            "",
            "Interpretation:",
            "",
            "- Four malicious PCAPs were not feature-materialized.",
            "- The substantial aligned unused pair is CoAP Amplification on combined-cycle-1, which is outside the current ten-label initial region registry.",
            "- The unused Merlin/Mirai-DoS PCAPs do not have scenario-matching exact Merlin/Mirai flooding labels in their paired processed CSVs.",
            "- Many benign PCAPs remain unused, but there is no relevant fresh malicious counterpart for the current regions.",
            "- Large numbers of exact attack rows remain in already used captures; these are development residuals, not new-environment evidence.",
            "- The sealed final attack source remains reserved and cannot be consumed to choose or repair a region candidate.",
            "",
            "Close-out:",
            "",
            "```text",
            "solved: Audited the complete local Gotham archive, current role manifests, unmaterialized malicious PCAPs, matched benign counterparts, and same-capture residual rows.",
            "changed_mainline: no",
            f"active_blocker: {verdict}.",
            "frozen: archive hash, role ledger, sealed-role prohibition, and distinction between source-fresh and same-capture residual evidence.",
            "superseded: assuming that unselected rows from an already used capture constitute a fresh deployment holdout.",
            f"next_action: {next_action}.",
            "```",
        ],
    )
    write_md(
        OUT / "validation_report.md",
        [
            "# issue27ckf Validation Report",
            "",
            "Status: `PASS_PENDING_DETERMINISTIC_RERUN`",
            "",
            "- ZIP central directory inventory completed.",
            "- Historical benign, OOD, attack, query, stress, and sealed roles were joined by exact PCAP/CSV member names.",
            "- Four unmaterialized malicious PCAPs were packet-header parsed without feature extraction.",
            "- Scenario-to-exact-label compatibility was checked against the existing full label-segment inventory.",
            "- Same-capture residual exact-label rows were counted with interval unions.",
            "- No model, region, threshold, score, or sealed outcome was accessed.",
        ],
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
