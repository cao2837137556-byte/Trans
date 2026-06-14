from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
OOD_DIR = REPO_DIR / "ood"
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ab_gotham_kitsune115_frontend_feasibility as ab  # noqa: E402

ISSUE = "issue27cb_broader_attack_support_candidate_contract_2026-06-14"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ASSET_DIR = ab.DATA_ROOT / "derived" / "kitsune115_larger_sanity_1m_certified_v1"
SIDECAR_PATH = ASSET_DIR / "gotham_kitsune115_1m_certified_train_state_then_eval_online_sidecar.csv.gz"
SPLIT_MANIFEST_PATH = ASSET_DIR / "gotham_kitsune115_1m_certified_train_state_then_eval_online_split_manifest.csv.gz"
ZIP_PATH = ab.DATA_ROOT / "raw" / "GothamDataset2025.zip"

ISSUE27Y_DIR = ROOT / "runs" / "issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28"
ALL_CSV_MANIFEST = ISSUE27Y_DIR / "gotham_all_csv_file_manifest.csv"
PREREG_CONTRACT = ISSUE27Y_DIR / "gotham_preregistered_split_contract_v1.json"

ATTACK_ROLES = {"attack_support_candidate_pool", "dev_future_attack_query", "sealed_final_attack"}
LEGAL_SUPPORT_ROLE = "attack_support_candidate_pool"
PHASES = [
    ("early_0_500", 0, 500),
    ("mid_500_2000", 500, 2_000),
    ("late_2000_10000", 2_000, 10_000),
    ("tail_gt_10000", 10_000, None),
]
SUPPORT_BUDGETS = [32, 64, 128, 256]
DEFAULT_SUPPORT_BUDGET = 128
MAX_TARGET_ROWS_PER_ATTACK_TYPE_FILE = 20_000
MIN_TARGET_ROWS_PER_ATTACK_TYPE_FILE = 256


def boolish(value: str) -> bool:
    return str(value).strip().lower() == "true"


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


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def infer_device(csv_member: str) -> str:
    name = Path(csv_member).name
    if name.startswith("iotsim-"):
        name = name[len("iotsim-") :]
    if name.endswith(".csv"):
        name = name[:-4]
    parts = name.split("-")
    if parts and parts[-1].isdigit():
        parts = parts[:-1]
    return "-".join(parts)


def onset_phase(recorded_index: int) -> str:
    for name, lo, hi in PHASES:
        if recorded_index >= lo and (hi is None or recorded_index < hi):
            return name
    return "unknown"


def load_preregistered_contract() -> dict[str, Any]:
    obj = json.loads(PREREG_CONTRACT.read_text(encoding="utf-8"))
    return obj["contract"]


def load_all_csv_manifest() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with ALL_CSV_MANIFEST.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["attack_rows_int"] = int(row.get("attack_rows") or 0)
            try:
                row["attack_type_counts_obj"] = json.loads(row.get("attack_type_counts") or "{}")
            except json.JSONDecodeError:
                row["attack_type_counts_obj"] = {}
            out[row["csv_archive_path"]] = row
    return out


def load_sidecar_attack_rows() -> tuple[list[dict[str, Any]], dict[str, set[int]]]:
    rows: list[dict[str, Any]] = []
    indices_by_file: dict[str, set[int]] = defaultdict(set)
    with gzip.open(SIDECAR_PATH, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["role"] not in ATTACK_ROLES:
                continue
            row = dict(row)
            row["global_row_id_int"] = int(row["global_row_id"])
            row["recorded_index_int"] = int(row["recorded_index_within_file"])
            row["model_ready_bool"] = boolish(row["model_ready_hint"])
            row["selection_allowed_bool"] = boolish(row["selection_allowed"])
            row["report_only_bool"] = boolish(row["report_only"])
            row["sealed_final_bool"] = boolish(row["sealed_final"])
            row["phase"] = onset_phase(row["recorded_index_int"])
            row["device"] = infer_device(row["csv_member"])
            rows.append(row)
            if row["model_ready_bool"]:
                indices_by_file[row["csv_member"]].add(row["recorded_index_int"])
    return rows, indices_by_file


def exact_labels_for_indices(indices_by_file: dict[str, set[int]]) -> dict[tuple[str, int], str]:
    exact: dict[tuple[str, int], str] = {}
    with zipfile.ZipFile(ZIP_PATH) as zf:
        for member, indices in sorted(indices_by_file.items()):
            if not indices:
                continue
            max_idx = max(indices)
            with zf.open(member) as raw:
                text_iter = (line.decode("utf-8", errors="replace") for line in raw)
                reader = csv.DictReader(text_iter)
                if not reader.fieldnames or "label" not in reader.fieldnames:
                    raise RuntimeError(f"label column missing in {member}")
                for row_idx, row in enumerate(reader):
                    if row_idx > max_idx:
                        break
                    if row_idx in indices:
                        exact[(member, row_idx)] = row.get("label", "") or ""
    return exact


def segment_inventory_for_files(files: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(ZIP_PATH) as zf:
        for member in files:
            if member not in zf.namelist():
                rows.append(
                    {
                        "csv_member": member,
                        "segment_id": "",
                        "label": "missing_csv_member",
                        "segment_start_row": "",
                        "segment_end_row": "",
                        "segment_rows": 0,
                        "phase_at_start": "",
                        "materialization_allowed_role": LEGAL_SUPPORT_ROLE,
                        "notes": "zip_member_missing",
                    }
                )
                continue
            seg_id = 0
            cur_label = None
            cur_start = 0
            cur_count = 0
            with zf.open(member) as raw:
                text_iter = (line.decode("utf-8", errors="replace") for line in raw)
                reader = csv.DictReader(text_iter)
                if not reader.fieldnames or "label" not in reader.fieldnames:
                    continue
                for row_idx, row in enumerate(reader):
                    label = row.get("label", "") or ""
                    if cur_label is None:
                        cur_label = label
                        cur_start = row_idx
                        cur_count = 1
                        continue
                    if label == cur_label:
                        cur_count += 1
                        continue
                    if cur_label and cur_label != "Benign":
                        rows.append(
                            {
                                "csv_member": member,
                                "segment_id": seg_id,
                                "label": cur_label,
                                "segment_start_row": cur_start,
                                "segment_end_row": row_idx - 1,
                                "segment_rows": cur_count,
                                "phase_at_start": onset_phase(cur_start),
                                "materialization_allowed_role": LEGAL_SUPPORT_ROLE,
                                "notes": "support_candidate_file_only",
                            }
                        )
                    seg_id += 1
                    cur_label = label
                    cur_start = row_idx
                    cur_count = 1
                if cur_label and cur_label != "Benign":
                    rows.append(
                        {
                            "csv_member": member,
                            "segment_id": seg_id,
                            "label": cur_label,
                            "segment_start_row": cur_start,
                            "segment_end_row": cur_start + cur_count - 1,
                            "segment_rows": cur_count,
                            "phase_at_start": onset_phase(cur_start),
                            "materialization_allowed_role": LEGAL_SUPPORT_ROLE,
                            "notes": "support_candidate_file_only",
                        }
                    )
    return rows


def requested_rows(n: int) -> int:
    return min(MAX_TARGET_ROWS_PER_ATTACK_TYPE_FILE, n)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for path in [SIDECAR_PATH, SPLIT_MANIFEST_PATH, ZIP_PATH, ALL_CSV_MANIFEST, PREREG_CONTRACT]:
        if not path.exists():
            raise FileNotFoundError(path)

    contract = load_preregistered_contract()
    support_files = list(contract.get("attack_support_files") or [])
    attack_eval_files = list(contract.get("attack_eval_files") or [])
    manifest = load_all_csv_manifest()
    sidecar_rows, indices_by_file = load_sidecar_attack_rows()
    exact = exact_labels_for_indices(indices_by_file)

    current_rows: list[dict[str, Any]] = []
    role_file_label = Counter()
    support_exact = Counter()
    support_phase_label = Counter()
    sidecar_first_label = Counter()
    benign_contamination = 0
    attack_support_model_ready = 0

    for row in sidecar_rows:
        exact_label = exact.get((row["csv_member"], row["recorded_index_int"]), "not_audited")
        is_exact_attack = exact_label not in {"", "Benign", "not_audited"}
        is_legal_support_row = (
            row["role"] == LEGAL_SUPPORT_ROLE
            and row["model_ready_bool"]
            and row["selection_allowed_bool"]
            and not row["report_only_bool"]
            and not row["sealed_final_bool"]
        )
        if is_legal_support_row:
            attack_support_model_ready += 1
            support_exact[exact_label] += 1
            support_phase_label[(row["phase"], exact_label)] += 1
            if not is_exact_attack:
                benign_contamination += 1
        sidecar_first_label[(row["role"], row["first_attack_label"] or "empty")] += 1
        role_file_label[(row["role"], row["csv_member"], exact_label)] += 1
        current_rows.append(
            {
                "role": row["role"],
                "csv_member": row["csv_member"],
                "device": row["device"],
                "global_row_id": row["global_row_id"],
                "recorded_index_within_file": row["recorded_index_within_file"],
                "phase": row["phase"],
                "sidecar_first_attack_label": row["first_attack_label"] or "",
                "exact_csv_label": exact_label,
                "model_ready_hint": row["model_ready_hint"],
                "selection_allowed": row["selection_allowed"],
                "report_only": row["report_only"],
                "sealed_final": row["sealed_final"],
                "legal_for_support_selection": str(is_legal_support_row and is_exact_attack).lower(),
                "notes": "csv_label_stream_audit_only_no_asset_modification",
            }
        )

    invalid_exact_labels = {"", "Benign", "Unknown", "not_audited", "missing_csv_member"}
    current_summary_rows = [
        {
            "role": role,
            "csv_member": csv_member,
            "device": infer_device(csv_member),
            "exact_csv_label": label,
            "rows": count,
            "selection_allowed_for_support": str(role == LEGAL_SUPPORT_ROLE and label not in invalid_exact_labels).lower(),
        }
        for (role, csv_member, label), count in sorted(role_file_label.items())
    ]
    sidecar_label_rows = [
        {"role": role, "sidecar_first_attack_label": label, "rows": count}
        for (role, label), count in sorted(sidecar_first_label.items())
    ]
    support_phase_rows = [
        {"phase": phase, "exact_csv_label": label, "rows": count}
        for (phase, label), count in sorted(support_phase_label.items())
    ]

    support_file_rows: list[dict[str, Any]] = []
    current_support_labels = {k for k in support_exact if k not in {"", "Benign"}}
    support_manifest_labels = Counter()
    for member in support_files:
        row = manifest.get(member, {})
        counts = row.get("attack_type_counts_obj", {}) if row else {}
        for label, count in counts.items():
            support_manifest_labels[label] += int(count)
        support_file_rows.append(
            {
                "csv_member": member,
                "device": row.get("inferred_device", infer_device(member)) if row else infer_device(member),
                "attack_rows_in_full_csv": row.get("attack_rows", "") if row else "",
                "attack_type_count_in_full_csv": len(counts),
                "attack_type_counts_in_full_csv": json.dumps(counts, ensure_ascii=False, sort_keys=True),
                "current_1m_role_for_this_file": "|".join(sorted({r["role"] for r in sidecar_rows if r["csv_member"] == member})) or "not_materialized_in_current_attack_roles",
                "current_1m_support_exact_attack_labels": json.dumps(
                    {
                        label: count
                        for label, count in sorted(
                            Counter(
                                exact.get((r["csv_member"], r["recorded_index_int"]), "")
                                for r in sidecar_rows
                                if r["csv_member"] == member and r["role"] == LEGAL_SUPPORT_ROLE and r["model_ready_bool"]
                            ).items()
                        )
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "contract_status": "support_candidate_file_from_preregistered_contract",
            }
        )

    attack_segment_rows = segment_inventory_for_files(support_files)
    missing_labels = sorted(set(support_manifest_labels) - current_support_labels)
    covered_labels = sorted(current_support_labels)
    taxonomy_gap_rows = []
    for label in sorted(set(support_manifest_labels) | current_support_labels):
        taxonomy_gap_rows.append(
            {
                "attack_type": label,
                "rows_in_preregistered_support_files": support_manifest_labels.get(label, 0),
                "rows_in_current_1m_legal_support_exact_label": support_exact.get(label, 0),
                "covered_by_current_1m_support": str(label in current_support_labels).lower(),
                "needs_targeted_materialization": str(label in missing_labels).lower(),
            }
        )

    request_buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
    for seg in attack_segment_rows:
        label = str(seg["label"])
        n = int(seg["segment_rows"])
        key = (str(seg["csv_member"]), label, str(seg["phase_at_start"]))
        bucket = request_buckets.setdefault(
            key,
            {
                "requested_role": LEGAL_SUPPORT_ROLE,
                "csv_member": seg["csv_member"],
                "attack_type": label,
                "phase": seg["phase_at_start"],
                "available_rows": 0,
                "segment_count": 0,
                "first_segment_start_row": seg["segment_start_row"],
                "last_segment_end_row": seg["segment_end_row"],
                "selection_allowed": "true",
                "report_only": "false",
                "sealed_final": "false",
            },
        )
        bucket["available_rows"] += n
        bucket["segment_count"] += 1
        bucket["first_segment_start_row"] = min(int(bucket["first_segment_start_row"]), int(seg["segment_start_row"]))
        bucket["last_segment_end_row"] = max(int(bucket["last_segment_end_row"]), int(seg["segment_end_row"]))

    request_rows: list[dict[str, Any]] = []
    for (_member, label, _phase), bucket in sorted(request_buckets.items()):
        n = int(bucket["available_rows"])
        if label in {"", "Benign", "Unknown"}:
            priority = "excluded_label_not_support"
        elif label in current_support_labels and support_exact[label] >= MIN_TARGET_ROWS_PER_ATTACK_TYPE_FILE:
            priority = "low_existing_label_covered"
        elif n < MIN_TARGET_ROWS_PER_ATTACK_TYPE_FILE:
            priority = "low_tiny_segment_diagnostic_only"
        else:
            priority = "high_missing_attack_type"
        target = 0 if priority in {"low_existing_label_covered", "excluded_label_not_support", "low_tiny_segment_diagnostic_only"} else requested_rows(n)
        request_rows.append(
            {
                "requested_role": LEGAL_SUPPORT_ROLE,
                "csv_member": bucket["csv_member"],
                "attack_type": label,
                "phase": bucket["phase"],
                "first_segment_start_row": bucket["first_segment_start_row"],
                "last_segment_end_row": bucket["last_segment_end_row"],
                "segment_count": bucket["segment_count"],
                "available_rows": n,
                "requested_target_rows": target,
                "selection_allowed": "true",
                "report_only": "false",
                "sealed_final": "false",
                "priority": priority,
                "notes": "future_targeted_materialization_only_do_not_reassign_current_report_only_rows",
            }
        )

    role_access_rows = [
        {
            "role": LEGAL_SUPPORT_ROLE,
            "may_select_support": "true",
            "may_fit_attack_head": "support_train_only_after_exact_label_filter",
            "may_use_for_threshold": "support_val_only_after_exact_label_filter",
            "may_use_for_model_selection": "false",
            "notes": "must exclude exact_csv_label=Benign and unknown labels before support bank selection",
        },
        {
            "role": "dev_future_attack_query",
            "may_select_support": "false",
            "may_fit_attack_head": "false",
            "may_use_for_threshold": "false",
            "may_use_for_model_selection": "false",
            "notes": "report-only dev query for replay; can be audited for data validity but cannot seed support",
        },
        {
            "role": "sealed_final_attack",
            "may_select_support": "false",
            "may_fit_attack_head": "false",
            "may_use_for_threshold": "false",
            "may_use_for_model_selection": "false",
            "notes": "sealed final remains report-only; current exact-label audit shows onset alignment must be fixed before use",
        },
        {
            "role": "sealed_final_ood",
            "may_select_support": "false",
            "may_fit_attack_head": "false",
            "may_use_for_threshold": "false",
            "may_use_for_model_selection": "false",
            "notes": "never used for support construction",
        },
    ]

    exact_attack_rows = sum(v for k, v in support_exact.items() if k not in {"", "Benign"})
    support_purity = exact_attack_rows / max(1, attack_support_model_ready)
    query_or_final_has_alignment_blocker = any(
        role in {"dev_future_attack_query", "sealed_final_attack"} and label == "Benign" and count > 0
        for (role, _csv_member, label), count in role_file_label.items()
    )
    support_multitype_ready = len(current_support_labels) >= 3 and support_purity >= 0.95
    needs_targeted = len(missing_labels) > 0 or query_or_final_has_alignment_blocker
    primary_verdict = (
        "broader_support_contract_partial_needs_targeted_multitype_materialization_and_onset_realign"
        if needs_targeted
        else "broader_support_contract_ready_on_current_1m_asset"
    )

    write_csv(OUT / "current_1m_attack_exact_label_audit.csv", current_summary_rows)
    write_csv(OUT / "sidecar_first_label_vs_exact_label_warning.csv", sidecar_label_rows)
    write_csv(OUT / "support_phase_exact_label_coverage.csv", support_phase_rows)
    write_csv(OUT / "broader_support_candidate_files.csv", support_file_rows)
    write_csv(OUT / "broader_attack_taxonomy_gap.csv", taxonomy_gap_rows)
    write_csv(OUT / "attack_segment_inventory_support_files.csv", attack_segment_rows)
    write_csv(OUT / "targeted_multitype_materialization_request.csv", request_rows)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)
    write_csv(
        OUT / "asset_mutation_audit.csv",
        [
            {
                "asset_dir": str(ASSET_DIR),
                "modified_asset_files": 0,
                "read_sidecar": str(SIDECAR_PATH),
                "read_split_manifest": str(SPLIT_MANIFEST_PATH),
                "read_zip_processed_csv_labels": str(ZIP_PATH),
                "verdict": "pass_read_only_audit",
            }
        ],
    )

    contract_obj = {
        "contract_id": "gotham115_broader_attack_support_candidate_contract_v1",
        "source_asset": str(ASSET_DIR),
        "source_preregistered_contract": str(PREREG_CONTRACT),
        "asset_mutation_allowed": False,
        "model_training_allowed": False,
        "formal_benchmark_allowed": False,
        "legal_support_source_role": LEGAL_SUPPORT_ROLE,
        "forbidden_support_source_roles": ["dev_future_attack_query", "sealed_final_attack", "sealed_final_ood"],
        "exact_label_filter": {
            "required": True,
            "exclude_labels": ["", "Benign", "Unknown"],
            "reason": "sidecar first_attack_label is too coarse for multi-attack taxonomy",
        },
        "current_1m_support_exact_attack_types": dict(sorted((k, v) for k, v in support_exact.items() if k not in {"", "Benign"})),
        "current_1m_support_benign_contamination_rows": benign_contamination,
        "current_1m_support_purity": support_purity,
        "preregistered_support_files": support_files,
        "attack_types_missing_from_current_support": missing_labels,
        "support_budgets_to_audit_later": SUPPORT_BUDGETS,
        "default_support_budget": DEFAULT_SUPPORT_BUDGET,
        "next_materialization_request": "targeted_multitype_materialization_request.csv",
        "primary_verdict": primary_verdict,
    }
    (OUT / "broader_attack_support_contract_v1.json").write_text(json.dumps(contract_obj, indent=2, ensure_ascii=False), encoding="utf-8")

    write_md(
        OUT / "broader_attack_support_contract_report.md",
        [
            "# Broader Attack Support Candidate Contract v1",
            "",
            f"primary_verdict: `{primary_verdict}`",
            "",
            "## What This Issue Did",
            "",
            "- Read the certified 1M sidecar and split manifest in read-only mode.",
            "- Streamed only the relevant processed CSV label rows from `GothamDataset2025.zip` to verify exact per-row attack labels.",
            "- Did not modify extracted 115D assets, did not rerun feature extraction, and did not train models.",
            "",
            "## Key Finding",
            "",
            "`sidecar.first_attack_label` is too coarse for multi-attack support taxonomy. Exact CSV label audit shows the current legal support pool is broader than issue27ca suggested, but still incomplete.",
            "",
            f"- Current legal support model-ready rows: `{attack_support_model_ready}`.",
            f"- Exact attack rows after excluding benign labels: `{exact_attack_rows}`.",
            f"- Support exact-label purity: `{support_purity:.6f}`.",
            f"- Current support attack types: `{dict(sorted((k, v) for k, v in support_exact.items() if k not in {'', 'Benign'}))}`.",
            f"- Benign contamination inside rows previously marked attack by alignment: `{benign_contamination}`.",
            f"- Missing attack types from preregistered support files: `{missing_labels}`.",
            "",
            "## Boundary",
            "",
            "- This is still a data-contract issue, not a model-performance issue.",
            "- Do not use `dev_future_attack_query` or `sealed_final_attack` rows as support.",
            "- Current 1M query/final attack rows also need onset/label realignment before performance replay because some role rows audit as benign by exact CSV labels.",
        ],
    )

    write_md(
        OUT / "issue27cc_next_action.md",
        [
            "# issue27cc Next Action",
            "",
            "Recommended next task:",
            "",
            "`issue27cc_targeted_multitype_attack_materialization_and_onset_realign`",
            "",
            "Purpose:",
            "",
            "- Do not train models.",
            "- Do not change the 115D frontend.",
            "- Do not use final/report-only rows for support selection.",
            "- Use `targeted_multitype_materialization_request.csv` to materialize development-side attack support candidates across multiple attack types and onset phases.",
            "- Rebuild dev query / sealed final attack only with exact label/onset checks, keeping them report-only.",
            "- Require exact per-row CSV label audit before any later support bank or model replay.",
            "",
            "Why:",
            "",
            "- Current 1M support pool has useful multi-type signal after exact-label audit, but it misses major support-file attack types.",
            "- Current dev/final attack roles contain substantial benign-prefix/onset alignment risk.",
            "- Running model replay before this would mix support taxonomy uncertainty with model behavior.",
        ],
    )

    write_md(
        OUT / "summary.md",
        [
            f"# {ISSUE} Summary",
            "",
            "1. issue27cb completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. task type: broader attack support candidate contract and exact-label audit",
            "4. model training: no",
            "5. formal benchmark: no",
            "6. extracted 1M asset modified: no",
            "7. zip/processed CSV usage: read-only streaming label audit only",
            f"8. current legal support rows before exact-label filtering: `{attack_support_model_ready}`",
            f"9. current exact attack support rows after filtering: `{exact_attack_rows}`",
            f"10. current support exact attack labels: `{dict(sorted((k, v) for k, v in support_exact.items() if k not in {'', 'Benign'}))}`",
            f"11. support benign contamination rows: `{benign_contamination}`",
            f"12. current support purity: `{support_purity:.6f}`",
            f"13. preregistered support-file attack types missing from current support: `{missing_labels}`",
            f"14. current 1M support is multi-type ready enough for contract-only audit: `{support_multitype_ready}`",
            f"15. query/final attack onset-label blocker found: `{query_or_final_has_alignment_blocker}`",
            "16. next recommended issue: `issue27cc_targeted_multitype_attack_materialization_and_onset_realign`",
            "17. commit/push: not performed",
        ],
    )
    write_md(OUT / "command.txt", ["python repo/ood/issue27cb_broader_attack_support_candidate_contract.py"])
    (OUT / "config.json").write_text(
        json.dumps(
            {
                "issue": ISSUE,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "asset_dir": str(ASSET_DIR),
                "zip_path": str(ZIP_PATH),
                "preregistered_contract": str(PREREG_CONTRACT),
                "model_training": False,
                "formal_benchmark": False,
                "asset_mutation_allowed": False,
                "support_budgets": SUPPORT_BUDGETS,
                "primary_verdict": primary_verdict,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "run_type": "broader_attack_support_candidate_contract",
                "inputs": [str(SIDECAR_PATH), str(SPLIT_MANIFEST_PATH), str(ALL_CSV_MANIFEST), str(PREREG_CONTRACT), str(ZIP_PATH)],
                "outputs": [
                    "current_1m_attack_exact_label_audit.csv",
                    "broader_support_candidate_files.csv",
                    "broader_attack_taxonomy_gap.csv",
                    "targeted_multitype_materialization_request.csv",
                    "broader_attack_support_contract_v1.json",
                ],
                "forbidden": ["model_training", "formal_benchmark", "asset_mutation", "support_selection_from_report_only"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    append_once(
        MAINLINE_DOCS / "mainline_handoff.md",
        ISSUE,
        [
            "## issue27cb Broader Attack Support Candidate Contract",
            "",
            f"marker: `{ISSUE}`",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- Read-only audit; no extracted 1M asset files were modified.",
            f"- Current legal support exact attack labels: `{dict(sorted((k, v) for k, v in support_exact.items() if k not in {'', 'Benign'}))}`.",
            f"- Support benign contamination rows that must be filtered before support selection: `{benign_contamination}`.",
            f"- Missing preregistered support-file attack types: `{missing_labels}`.",
            "- Next: targeted multi-type attack materialization and onset realignment before model replay.",
        ],
    )
    append_once(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        ISSUE,
        [
            "## issue27cb Broader Attack Support Candidate Contract",
            "",
            f"marker: `{ISSUE}`",
            "",
            "- Role: exact-label support taxonomy audit on certified 1M before any model replay.",
            "- Main output: broader attack support contract v1 plus targeted materialization request.",
            "- Boundary: data contract only; not performance.",
        ],
    )

    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"path": str(path.relative_to(ROOT)), "sha256": file_hash(path), "bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)
    print(
        json.dumps(
            {
                "issue": ISSUE,
                "primary_verdict": primary_verdict,
                "support_exact_attack_types": dict(sorted((k, v) for k, v in support_exact.items() if k not in {"", "Benign"})),
                "benign_contamination": benign_contamination,
                "missing_attack_types": missing_labels,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
