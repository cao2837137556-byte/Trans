from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO.parents[1] / "datasets" / "gotham2025"
ZIP_PATH = DATA_ROOT / "raw" / "GothamDataset2025.zip"
ARCHIVE_LISTING = REPO / "runs" / "issue27v_gotham_download_and_file_level_data_gate_2026-05-28" / "archive_file_listing.csv"
BW_DIR = REPO / "runs" / "issue27bw_larger_sanity_contract_construction_2026-06-11"
CB_DIR = REPO / "runs" / "issue27cb_broader_attack_support_candidate_contract_2026-06-14"
ASSET_DIR = DATA_ROOT / "derived" / "kitsune115_larger_sanity_1m_certified_v1"
OUT = REPO / "runs" / "issue27cc_targeted_multitype_attack_materialization_and_onset_realign_2026-06-14"

COMMAND_TEXT = "python repo/ood/issue27cc_targeted_multitype_attack_materialization_and_onset_realign.py"
ISSUE_ID = "issue27cc_targeted_multitype_attack_materialization_and_onset_realign_2026-06-14"

BENIGN_LABELS = {"", "Benign"}
EXCLUDED_ATTACK_LABELS = {"Unknown"}
EMBARGO_ROWS = 500
SUPPORT_TARGET_CAP_PER_FILE_LABEL = 8_000
DEV_QUERY_TARGET_CAP_PER_FILE_LABEL = 12_000
SEALED_FINAL_TARGET_CAP_PER_FILE_LABEL = 15_000
MIN_SUPPORT_FOR_TINY_LABEL = 64


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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def infer_device(csv_member: str) -> str:
    stem = Path(csv_member).stem
    stem = re.sub(r"^iotsim-", "", stem)
    stem = re.sub(r"-\d+$", "", stem)
    return stem


def phase_for(start_row: int, first_attack_row: int | None) -> str:
    if first_attack_row is None:
        return "no_attack"
    offset = max(0, start_row - first_attack_row)
    if offset < 500:
        return "early_0_500"
    if offset < 2_000:
        return "mid_500_2000"
    if offset < 10_000:
        return "late_2000_10000"
    return "tail_gt_10000"


def attack_family_hint(label: str) -> str:
    low = label.lower()
    if "merlin" in low:
        return "merlin"
    if "mirai" in low and "flood" in low:
        return "mirai-dos"
    if "mirai" in low and "c&c" in low:
        return "mirai-infection"
    if "coap" in low:
        return "coap-amplification"
    if "scan" in low or "brute" in low or "telnet" in low:
        return "network-scanning"
    if "ingress" in low or "file download" in low or "reporting" in low or "c&c communication" in low:
        return "mirai-infection_or_merlin_ambiguous"
    return "ambiguous"


def load_archive_paths() -> tuple[list[str], list[str]]:
    rows = read_csv(ARCHIVE_LISTING)
    pcaps = [r["file_path"] for r in rows if r.get("is_pcap") == "True"]
    csvs = [r["file_path"] for r in rows if r.get("is_csv") == "True"]
    return pcaps, csvs


def pcap_candidates_for(csv_member: str, label: str, pcaps: list[str]) -> dict[str, str]:
    stem = Path(csv_member).stem
    candidates = [p for p in pcaps if f"/{stem}_" in p and "/malicious/" in p]
    hint = attack_family_hint(label)
    if hint == "mirai-infection_or_merlin_ambiguous":
        preferred = [p for p in candidates if "/mirai-infection/" in p or "/merlin/" in p]
    elif hint != "ambiguous":
        preferred = [p for p in candidates if f"/{hint}/" in p]
    else:
        preferred = []
    if len(preferred) == 1:
        confidence = "medium_scenario_token_match"
    elif len(preferred) > 1:
        confidence = "medium_multiple_scenario_candidates"
    elif candidates:
        confidence = "low_device_filename_candidates_ambiguous"
    else:
        confidence = "missing"
    return {
        "preferred_pcap_candidate": preferred[0] if preferred else (candidates[0] if candidates else ""),
        "all_pcap_candidates": "|".join(candidates),
        "attack_family_hint": hint,
        "pcap_pairing_confidence": confidence,
        "requires_pcap_pairing_verification": str(confidence != "medium_scenario_token_match").lower(),
    }


def scan_label_segments(zf: zipfile.ZipFile, member: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    first_attack_row: int | None = None
    cur_label: str | None = None
    cur_start = 0
    row_idx = 0
    with zf.open(member, "r") as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
        reader = csv.DictReader(text)
        if not reader.fieldnames or "label" not in reader.fieldnames:
            raise RuntimeError(f"label column missing in {member}")
        for row in reader:
            label = row.get("label", "") or ""
            if first_attack_row is None and label not in BENIGN_LABELS:
                first_attack_row = row_idx
            if cur_label is None:
                cur_label = label
                cur_start = row_idx
            elif label != cur_label:
                end = row_idx - 1
                if cur_label not in BENIGN_LABELS:
                    segments.append(
                        {
                            "csv_member": member,
                            "segment_id": len(segments),
                            "label": cur_label,
                            "segment_start_row": cur_start,
                            "segment_end_row": end,
                            "segment_rows": end - cur_start + 1,
                            "first_attack_row": "" if first_attack_row is None else first_attack_row,
                            "phase_at_start": phase_for(cur_start, first_attack_row),
                        }
                    )
                cur_label = label
                cur_start = row_idx
            row_idx += 1
    if cur_label is not None and cur_label not in BENIGN_LABELS:
        end = row_idx - 1
        segments.append(
            {
                "csv_member": member,
                "segment_id": len(segments),
                "label": cur_label,
                "segment_start_row": cur_start,
                "segment_end_row": end,
                "segment_rows": end - cur_start + 1,
                "first_attack_row": "" if first_attack_row is None else first_attack_row,
                "phase_at_start": phase_for(cur_start, first_attack_row),
            }
        )
    return segments


def alloc_segments(
    segments: list[dict[str, Any]],
    target_rows: int,
    plan_role: str,
    source_contract_role: str,
    pcap_info: dict[str, str],
    selection_allowed: bool,
    report_only: bool,
    sealed_final: bool,
    row_selection_rule: str,
    min_start_after: int | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    rows: list[dict[str, Any]] = []
    remaining = target_rows
    max_end = -1
    for seg in sorted(segments, key=lambda x: (int(x["segment_start_row"]), int(x["segment_end_row"]))):
        if remaining <= 0:
            break
        seg_start = int(seg["segment_start_row"])
        seg_end = int(seg["segment_end_row"])
        if min_start_after is not None and seg_end <= min_start_after:
            continue
        start = max(seg_start, (min_start_after + 1) if min_start_after is not None else seg_start)
        if start > seg_end:
            continue
        take = min(remaining, seg_end - start + 1)
        end = start + take - 1
        max_end = max(max_end, end)
        payload = {
            "plan_role": plan_role,
            "source_contract_role": source_contract_role,
            "csv_member": seg["csv_member"],
            "device": infer_device(str(seg["csv_member"])),
            "attack_type": seg["label"],
            "phase": phase_for(start, int(seg["first_attack_row"]) if str(seg["first_attack_row"]) else None),
            "source_segment_id": seg["segment_id"],
            "source_segment_start_row": seg["segment_start_row"],
            "source_segment_end_row": seg["segment_end_row"],
            "planned_start_row": start,
            "planned_end_row": end,
            "planned_rows": take,
            "exact_label_required": "true",
            "allowed_exact_label": seg["label"],
            "excluded_exact_labels": "Benign|Unknown|empty",
            "selection_allowed": str(selection_allowed).lower(),
            "report_only": str(report_only).lower(),
            "sealed_final": str(sealed_final).lower(),
            "forbidden_for_fit": str(report_only or sealed_final).lower(),
            "forbidden_for_threshold": str(sealed_final).lower(),
            "forbidden_for_model_selection": str(report_only or sealed_final).lower(),
            "row_selection_rule": row_selection_rule,
            "embargo_rows": EMBARGO_ROWS if "time_forward" in row_selection_rule else 0,
            **pcap_info,
        }
        rows.append(payload)
        remaining -= take
    return rows, target_rows - remaining, max_end


def support_target_for(total_rows: int) -> int:
    if total_rows <= 0:
        return 0
    if total_rows < 512:
        return max(MIN_SUPPORT_FOR_TINY_LABEL, math.floor(total_rows * 0.7))
    if total_rows < 2_000:
        return max(256, math.floor(total_rows * 0.5))
    return min(SUPPORT_TARGET_CAP_PER_FILE_LABEL, max(512, math.floor(total_rows * 0.25)))


def main() -> None:
    start_time = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    pcaps, _csvs = load_archive_paths()
    request_rows = read_csv(CB_DIR / "targeted_multitype_materialization_request.csv")
    current_audit = read_csv(CB_DIR / "current_1m_attack_exact_label_audit.csv")
    bw_contract = json.loads((BW_DIR / "larger_sanity_contract_v1.json").read_text(encoding="utf-8"))
    roles = bw_contract["roles"]

    high_missing_keys = {
        (r["csv_member"], r["attack_type"])
        for r in request_rows
        if r.get("priority") == "high_missing_attack_type" and r.get("attack_type") not in EXCLUDED_ATTACK_LABELS
    }
    support_request_files = {m for m, _label in high_missing_keys}
    dev_query_files = set(roles["dev_future_attack_query"]) | support_request_files | set(roles["attack_support_candidate_pool"])
    sealed_final_files = set(roles["sealed_final_attack"])
    scan_files = sorted(support_request_files | dev_query_files | sealed_final_files)

    segment_rows: list[dict[str, Any]] = []
    scan_meta: list[dict[str, Any]] = []
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        for member in scan_files:
            t0 = time.time()
            segments = scan_label_segments(zf, member)
            elapsed = time.time() - t0
            segment_rows.extend(segments)
            label_counts = Counter()
            for seg in segments:
                label_counts[str(seg["label"])] += int(seg["segment_rows"])
            scan_meta.append(
                {
                    "csv_member": member,
                    "device": infer_device(member),
                    "segments": len(segments),
                    "attack_rows": sum(label_counts.values()),
                    "labels": json.dumps(dict(sorted(label_counts.items())), ensure_ascii=False),
                    "elapsed_seconds": round(elapsed, 3),
                }
            )

    segments_by_file_label: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for seg in segment_rows:
        if str(seg["label"]) in EXCLUDED_ATTACK_LABELS:
            continue
        segments_by_file_label[(str(seg["csv_member"]), str(seg["label"]))].append(seg)

    plan_rows: list[dict[str, Any]] = []
    support_end_by_file_label: dict[tuple[str, str], int] = {}

    for member, label in sorted(high_missing_keys):
        segs = segments_by_file_label.get((member, label), [])
        total = sum(int(s["segment_rows"]) for s in segs)
        target = support_target_for(total)
        pcap_info = pcap_candidates_for(member, label, pcaps)
        rows, emitted, max_end = alloc_segments(
            segs,
            target,
            "attack_support_candidate_pool_targeted",
            "development_attack_support_candidate_pool_v2",
            pcap_info,
            selection_allowed=True,
            report_only=False,
            sealed_final=False,
            row_selection_rule="earliest_exact_attack_rows_for_support_candidate_only",
        )
        plan_rows.extend(rows)
        if emitted > 0:
            support_end_by_file_label[(member, label)] = max_end

    # Development/query rows: exact labels only. If the same file-label contributed
    # support candidates, query rows are strictly time-forward after an embargo.
    dev_labels = sorted(
        (member, label)
        for (member, label), segs in segments_by_file_label.items()
        if member in dev_query_files and label not in EXCLUDED_ATTACK_LABELS
    )
    for member, label in dev_labels:
        segs = segments_by_file_label[(member, label)]
        total = sum(int(s["segment_rows"]) for s in segs)
        support_end = support_end_by_file_label.get((member, label))
        min_after = (support_end + EMBARGO_ROWS) if support_end is not None else None
        pcap_info = pcap_candidates_for(member, label, pcaps)
        role = "same_file_time_forward_dev_query_exact" if support_end is not None else "dev_future_attack_query_exact"
        target = min(DEV_QUERY_TARGET_CAP_PER_FILE_LABEL, total)
        rows, _emitted, _max_end = alloc_segments(
            segs,
            target,
            role,
            "development_attack_query_v2",
            pcap_info,
            selection_allowed=False,
            report_only=True,
            sealed_final=False,
            row_selection_rule="time_forward_after_support_embargo_exact_label" if support_end is not None else "exact_attack_rows_development_query_only",
            min_start_after=min_after,
        )
        plan_rows.extend(rows)

    for member in sorted(sealed_final_files):
        labels = sorted({label for (m, label) in segments_by_file_label if m == member and label not in EXCLUDED_ATTACK_LABELS})
        for label in labels:
            segs = segments_by_file_label[(member, label)]
            pcap_info = pcap_candidates_for(member, label, pcaps)
            rows, _emitted, _max_end = alloc_segments(
                segs,
                SEALED_FINAL_TARGET_CAP_PER_FILE_LABEL,
                "sealed_final_attack_exact_realign",
                "sealed_final_attack_v2_report_only",
                pcap_info,
                selection_allowed=False,
                report_only=True,
                sealed_final=True,
                row_selection_rule="sealed_report_only_exact_attack_rows_no_selection",
            )
            plan_rows.extend(rows)

    current_support_exact = [
        r for r in current_audit
        if r.get("role") == "attack_support_candidate_pool"
        and r.get("exact_csv_label") not in BENIGN_LABELS
        and r.get("exact_csv_label") not in EXCLUDED_ATTACK_LABELS
        and r.get("exact_csv_label") != "not_audited"
    ]
    current_support_reuse_rows = [
        {
            "csv_member": r["csv_member"],
            "device": r.get("device", infer_device(r["csv_member"])),
            "exact_attack_label": r["exact_csv_label"],
            "exact_attack_rows": r["rows"],
            "reuse_policy": "may_reuse_existing_1m_rows_only_after_exact_label_filter",
            "selection_allowed": "true",
            "must_exclude_from_support": "Benign|Unknown|not_audited",
        }
        for r in current_support_exact
    ]

    planned_summary = Counter()
    planned_by_label = Counter()
    planned_by_role_label = Counter()
    for row in plan_rows:
        planned_summary[row["plan_role"]] += int(row["planned_rows"])
        planned_by_label[row["attack_type"]] += int(row["planned_rows"])
        planned_by_role_label[(row["plan_role"], row["attack_type"])] += int(row["planned_rows"])

    exact_label_gate_rows = []
    for role, rows in defaultdict(list, ((role, [r for r in plan_rows if r["plan_role"] == role]) for role in sorted({r["plan_role"] for r in plan_rows}))).items():
        labels = sorted({r["attack_type"] for r in rows})
        exact_label_gate_rows.append(
            {
                "plan_role": role,
                "planned_rows": sum(int(r["planned_rows"]) for r in rows),
                "planned_attack_labels": "|".join(labels),
                "planned_benign_rows": 0,
                "planned_unknown_rows": 0,
                "gate": "pass" if rows else "empty",
                "notes": "all planned ranges are exact non-Benign/non-Unknown CSV label ranges",
            }
        )

    role_access_rows = [
        {
            "role": "attack_support_candidate_pool_targeted",
            "fit_allowed": "support_train_only_after_bank_split",
            "threshold_allowed": "support_val_only_after_bank_split",
            "support_selection_allowed": "true",
            "score_allowed": "diagnostic_after_selection_freeze",
            "report_only": "false",
            "sealed_final": "false",
            "forbidden_inputs": "sealed_final_ood|sealed_final_attack|dev_query_holdout_features_before_support_selection",
        },
        {
            "role": "same_file_time_forward_dev_query_exact",
            "fit_allowed": "false",
            "threshold_allowed": "false",
            "support_selection_allowed": "false",
            "score_allowed": "diagnostic_only",
            "report_only": "true",
            "sealed_final": "false",
            "forbidden_inputs": "used_as_support_or_threshold_after_support_selection",
        },
        {
            "role": "dev_future_attack_query_exact",
            "fit_allowed": "false",
            "threshold_allowed": "false",
            "support_selection_allowed": "false",
            "score_allowed": "diagnostic_only",
            "report_only": "true",
            "sealed_final": "false",
            "forbidden_inputs": "support_selection|threshold|model_selection",
        },
        {
            "role": "sealed_final_attack_exact_realign",
            "fit_allowed": "false",
            "threshold_allowed": "false",
            "support_selection_allowed": "false",
            "score_allowed": "final_replay_only_after_config_freeze",
            "report_only": "true",
            "sealed_final": "true",
            "forbidden_inputs": "fit|threshold|support_selection|model_selection|gate_selection",
        },
    ]

    support_labels = {r["attack_type"] for r in plan_rows if r["plan_role"] == "attack_support_candidate_pool_targeted"}
    support_labels |= {r["exact_attack_label"] for r in current_support_reuse_rows}
    dev_rows = sum(
        v
        for (role, _label), v in planned_by_role_label.items()
        if role in {"dev_future_attack_query_exact", "same_file_time_forward_dev_query_exact"}
    )
    final_rows = planned_summary["sealed_final_attack_exact_realign"]
    support_rows = planned_summary["attack_support_candidate_pool_targeted"] + sum(int(r["exact_attack_rows"]) for r in current_support_reuse_rows)
    alignment_ready = support_rows > 0 and dev_rows > 0 and final_rows > 0 and len(support_labels) >= 6
    verdict = (
        "targeted_multitype_attack_contract_ready_for_slurm_exact_label_materialization"
        if alignment_ready
        else "targeted_multitype_attack_contract_partial_needs_manual_review"
    )

    write_csv(OUT / "attack_label_segment_inventory_scanned.csv", segment_rows)
    write_csv(OUT / "csv_label_scan_meta.csv", scan_meta)
    write_csv(OUT / "targeted_exact_label_materialization_plan.csv", plan_rows)
    write_csv(OUT / "current_support_exact_filter_reuse_plan.csv", current_support_reuse_rows)
    write_csv(OUT / "exact_label_alignment_gate.csv", exact_label_gate_rows)
    write_csv(
        OUT / "targeted_plan_role_label_summary.csv",
        [
            {"plan_role": role, "attack_type": label, "planned_rows": rows}
            for (role, label), rows in sorted(planned_by_role_label.items())
        ],
    )
    write_csv(OUT / "role_access_audit.csv", role_access_rows)
    pcap_audit: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for r in plan_rows:
        key = (
            r["csv_member"],
            r["attack_type"],
            r["preferred_pcap_candidate"],
            r["pcap_pairing_confidence"],
        )
        item = pcap_audit.setdefault(
            key,
            {
                "csv_member": r["csv_member"],
                "attack_type": r["attack_type"],
                "preferred_pcap_candidate": r["preferred_pcap_candidate"],
                "all_pcap_candidates": r["all_pcap_candidates"],
                "pcap_pairing_confidence": r["pcap_pairing_confidence"],
                "requires_pcap_pairing_verification": r["requires_pcap_pairing_verification"],
                "planned_rows": 0,
                "plan_roles": set(),
            },
        )
        item["planned_rows"] += int(r["planned_rows"])
        item["plan_roles"].add(r["plan_role"])
    pcap_audit_rows = []
    for item in pcap_audit.values():
        item = dict(item)
        item["plan_roles"] = "|".join(sorted(item["plan_roles"]))
        pcap_audit_rows.append(item)
    write_csv(OUT / "pcap_pairing_requirement_audit.csv", sorted(pcap_audit_rows, key=lambda x: (x["csv_member"], x["attack_type"])))
    write_csv(
        OUT / "asset_mutation_audit.csv",
        [
            {"artifact": str(ASSET_DIR), "mutation_allowed": "false", "mutation_performed": "false", "notes": "issue27cc is contract planning only"},
            {"artifact": str(ZIP_PATH), "mutation_allowed": "false", "mutation_performed": "false", "notes": "read-only processed CSV label streaming"},
        ],
    )

    hpc_plan = {
        "issue": ISSUE_ID,
        "primary_verdict": verdict,
        "materialization_input_plan": str(OUT / "targeted_exact_label_materialization_plan.csv"),
        "required_extractor_change": "exact_csv_label_row_filter_before_emit",
        "forbidden_old_logic": "post_onset_binary_from_csv_first_attack_without_exact_label_filter",
        "recommended_slurm": {
            "partition": "amd",
            "array": "plan chunks from targeted_exact_label_materialization_plan.csv after pcap pairing verification",
            "cpus_per_task": 8,
            "memory": "32G-64G",
            "time": "08:00:00 to 24:00:00 depending on large ip-camera PCAP chunks",
        },
        "gates_before_submit": [
            "GothamDataset2025.zip md5 must equal 7ca78c0517ccb3d2854e823678e0f206",
            "all planned rows exact label != Benign/Unknown",
            "sealed final forbidden for support/threshold/model selection",
            "same-file dev query must be time-forward after support rows plus embargo",
            "pcap pairing confidence reviewed for ambiguous scenarios",
        ],
    }
    (OUT / "hpc_exact_label_materialization_plan.json").write_text(json.dumps(hpc_plan, indent=2, ensure_ascii=False), encoding="utf-8")

    config = {
        "issue": ISSUE_ID,
        "source_asset": str(ASSET_DIR),
        "input_issue27cb": str(CB_DIR),
        "input_issue27bw": str(BW_DIR),
        "zip_path": str(ZIP_PATH),
        "embargo_rows": EMBARGO_ROWS,
        "support_target_cap_per_file_label": SUPPORT_TARGET_CAP_PER_FILE_LABEL,
        "dev_query_target_cap_per_file_label": DEV_QUERY_TARGET_CAP_PER_FILE_LABEL,
        "sealed_final_target_cap_per_file_label": SEALED_FINAL_TARGET_CAP_PER_FILE_LABEL,
        "primary_verdict": verdict,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    run_spec = {
        "issue": ISSUE_ID,
        "command": COMMAND_TEXT,
        "model_training": False,
        "feature_extraction": False,
        "formal_benchmark": False,
        "asset_mutation": False,
        "exact_label_contract_planning": True,
        "elapsed_seconds": round(time.time() - start_time, 3),
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "command.txt").write_text(COMMAND_TEXT + "\n", encoding="utf-8")

    write_md(
        OUT / "exact_label_onset_realign_contract.md",
        [
            "# Exact Label / Onset Realign Contract",
            "",
            "This contract exists because the previous 1M asset used coarse `first_attack_label` / post-onset binary materialization for attack roles.",
            "",
            "New hard gates:",
            "",
            "1. Attack support/query/final materialization must filter by exact processed CSV `label` per planned row range.",
            "2. `Benign`, empty labels, and `Unknown` are forbidden for attack support selection.",
            "3. Same-file support/query reuse is allowed only as development-side time-forward diagnostic with an embargo.",
            "4. Same-file time-forward query is not a clean final evaluation set.",
            "5. Sealed final attack remains report-only and cannot be used for support selection, threshold, OOD-risk training, controller tuning, or model selection.",
            "6. The old `post_onset_binary_from_csv_first_attack` label source is no longer sufficient for attack roles.",
        ],
    )
    write_md(
        OUT / "issue27cd_next_action.md",
        [
            "# issue27cd Next Action",
            "",
            "Recommended next task:",
            "",
            "`issue27cd_slurm_exact_label_targeted_multitype_attack_materialization`",
            "",
            "Purpose:",
            "",
            "- Do not train models.",
            "- Do not run a benchmark.",
            "- Extend the Slurm materializer so attack roles emit 115D rows only when the corresponding processed CSV row has the exact planned attack label.",
            "- Use `targeted_exact_label_materialization_plan.csv` as the only input contract.",
            "- Preserve sealed final as report-only.",
            "",
            "Blockers to solve before submit:",
            "",
            "- Review ambiguous PCAP pairing for infection/C&C/File Download/Reporting labels.",
            "- Implement exact row-label filtering in the PCAP -> 115D materializer.",
            "- Keep current certified 1M asset immutable; write new targeted cache/asset directory.",
        ],
    )

    summary_lines = [
        "# issue27cc Summary",
        "",
        f"1. issue27cc completed: `true`.",
        f"2. primary_verdict: `{verdict}`.",
        "3. task type: targeted multi-attack exact-label contract planning; no model training and no feature extraction.",
        f"4. scanned CSV files: `{len(scan_files)}`.",
        f"5. scanned attack segments: `{len(segment_rows)}`.",
        f"6. current exact-filter reusable support rows: `{sum(int(r['exact_attack_rows']) for r in current_support_reuse_rows)}`.",
        f"7. newly planned targeted support rows: `{planned_summary['attack_support_candidate_pool_targeted']}`.",
        f"8. planned development/query attack rows: `{dev_rows}`.",
        f"9. planned sealed final attack exact rows: `{final_rows}`.",
        f"10. support labels after current reuse + targeted plan: `{sorted(support_labels)}`.",
        "11. benign/Unknown rows planned for attack roles: `0` by construction.",
        "12. same-file support/query reuse: allowed only for development-side time-forward query with embargo; not clean final.",
        "13. current certified 1M asset mutation: `false`.",
        "14. next step: implement Slurm exact-label materializer (`issue27cd`) before any model replay.",
    ]
    write_md(OUT / "summary.md", summary_lines)
    write_md(
        OUT / "issue27cc_decision.md",
        [
            "# issue27cc Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            "The 1M certified asset should not be used for the next model replay until attack roles are rebuilt or filtered by exact per-row CSV labels.",
            "",
            "The plan is ready for an exact-label Slurm materialization step if PCAP pairing ambiguities are reviewed and the materializer is changed to filter rows by CSV label before emitting 115D rows.",
        ],
    )

    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_csv(OUT / "manifest.csv", manifest_rows)

    marker = "<!-- issue27cc_targeted_multitype_attack_materialization_and_onset_realign -->"
    doc_lines = [
        marker,
        "## issue27cc Targeted Multitype Attack Materialization and Onset Realign",
        "",
        f"- Verdict: `{verdict}`.",
        "- Current 1M attack roles are not sufficient for model replay because support/query/final attack rows must be exact-label filtered.",
        f"- Reusable current exact support rows: `{sum(int(r['exact_attack_rows']) for r in current_support_reuse_rows)}`.",
        f"- Newly planned targeted support rows: `{planned_summary['attack_support_candidate_pool_targeted']}`.",
        f"- Planned dev/query attack rows: `{dev_rows}`.",
        f"- Planned sealed final exact attack rows: `{final_rows}`.",
        "- Next: run exact-label Slurm materialization before any model replay.",
    ]
    append_once(REPO / "runs" / "mainline_docs" / "mainline_handoff.md", marker, doc_lines)
    append_once(REPO / "runs" / "mainline_docs" / "mainline_experiment_map.md", marker, doc_lines)

    print(json.dumps({"issue": ISSUE_ID, "primary_verdict": verdict, "out": str(OUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
