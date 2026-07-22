from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
OOD_DIR = ROOT / "repo" / "ood"
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckam_toniot_bro_groundtruth_schema_audit_v1 as ckam  # noqa: E402


ISSUE = "issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22"
OUT = ROOT / "runs" / ISSUE
DATA = (
    ROOT.parents[1]
    / "datasets"
    / "external"
    / "ton_iot_raw_network"
    / "extracted"
)
CKAN = ROOT / "runs" / "issue27ckan_toniot_route_a_loader_policy_repair_v1_2026-07-09"
CKAN_SUMMARY = CKAN / "summary.json"
CKAN_CONN_POLICY = CKAN / "conn_loader_policy.csv"
CKAN_GT_POLICY = CKAN / "groundtruth_loader_policy.csv"

PERMANENT_GOTHAM_REPORT_FAMILIES = (
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
    "iotsim-ip-camera-street",
    "iotsim-predictive-maintenance",
)


@dataclass(frozen=True)
class Pair:
    pair_id: str
    mechanism: str
    ton_label: str
    role: str
    conn_rel: str
    gt_rel: str
    hash_modulus: int
    budget: int


PAIRS = (
    Pair(
        "scanning_fit_capture_1",
        "reconnaissance_scan",
        "scanning",
        "aux_process_fit",
        "Network_dataset_Bro/normal_attack_Bro/normal_scanning/normal_scanning_1/conn.log",
        "SecurityEvents_Network_datasets/GroundTruth_Network_1.csv",
        4,
        2_000,
    ),
    Pair(
        "scanning_select_capture_2",
        "reconnaissance_scan",
        "scanning",
        "aux_process_select",
        "Network_dataset_Bro/normal_attack_Bro/normal_scanning/normal_scanning2/conn.log",
        "SecurityEvents_Network_datasets/GroundTruth_Network_2.csv",
        64,
        500,
    ),
    Pair(
        "password_fit_capture_1",
        "credential_bruteforce",
        "password",
        "aux_process_fit",
        "Network_dataset_Bro/normal_attack_Bro/normal_password/password_normal_1/conn.log",
        "SecurityEvents_Network_datasets/GroundTruth_Network_14.csv",
        16,
        2_000,
    ),
    Pair(
        "password_select_capture_4",
        "credential_bruteforce",
        "password",
        "aux_process_select",
        "Network_dataset_Bro/normal_attack_Bro/normal_password/password_normal4/conn.log",
        "SecurityEvents_Network_datasets/GroundTruth_Network_15.csv",
        16,
        500,
    ),
)

RESERVED_CONN_FILES = (
    "Network_dataset_Bro/normal_attack_Bro/normal_scanning/normal_scanning3/conn.log",
    "Network_dataset_Bro/normal_attack_Bro/normal_scanning/normal_scanning4/conn.log",
    "Network_dataset_Bro/normal_attack_Bro/normal_scanning/normal_scanning5/conn.log",
    "Network_dataset_Bro/normal_attack_Bro/normal_scanning/normal_scanning6/conn.log",
    "Network_dataset_Bro/normal_attack_Bro/normal_password/password_normal2/conn.log",
    "Network_dataset_Bro/normal_attack_Bro/normal_password/password_normal3/conn.log",
    "Network_dataset_Bro/normal_attack_Bro/normal_password/password_normal5/conn.log",
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hex(*parts: Any) -> str:
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    values = list(rows)
    fields: list[str] = []
    for row in values:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(values)


def normalize_port(value: str) -> str:
    text = str(value).strip()
    if text in {"", "-"}:
        raise ValueError("missing port")
    return str(int(float(text)))


def exact_key(
    ts: str,
    src_ip: str,
    src_port: str,
    dst_ip: str,
    dst_port: str,
    proto: str,
) -> tuple[int, str, str, str, str, str]:
    return (
        math.floor(float(ts)),
        str(src_ip).strip(),
        normalize_port(src_port),
        str(dst_ip).strip(),
        normalize_port(dst_port),
        str(proto).strip().lower(),
    )


def key_hash(key: tuple[int, str, str, str, str, str]) -> str:
    return stable_hex(*key)


def zeek_rows(path: Path) -> Iterable[tuple[int, dict[str, str]]]:
    fields, _types = ckam.parse_zeek_header(path)
    if fields != ckam.REQUIRED_CONN_FIELDS and not set(ckam.REQUIRED_CONN_FIELDS).issubset(fields):
        raise RuntimeError(f"unexpected Zeek conn schema: {path}: {fields}")
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        data_index = 0
        for line in f:
            if not line or line.startswith("#"):
                continue
            parts = line.rstrip("\r\n").split("\t")
            if len(parts) != len(fields):
                raise RuntimeError(f"Zeek column count changed at {path}:{data_index}")
            yield data_index, dict(zip(fields, parts))
            data_index += 1


def gt_time_bounds(path: Path) -> tuple[int, int]:
    low: int | None = None
    high: int | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ts = int(float(row["ts"]))
            low = ts if low is None else min(low, ts)
            high = ts if high is None else max(high, ts)
    if low is None or high is None:
        raise RuntimeError(f"empty ground truth: {path}")
    return low, high


def candidate_conn_rows(pair: Pair) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    conn_path = DATA / pair.conn_rel
    gt_path = DATA / pair.gt_rel
    low, high = gt_time_bounds(gt_path)
    sampled: dict[str, dict[str, Any]] = {}
    duplicates: Counter[str] = Counter()
    total = 0
    in_window = 0
    parse_skipped = 0
    for line_index, row in zeek_rows(conn_path):
        total += 1
        try:
            key = exact_key(
                row["ts"],
                row["id.orig_h"],
                row["id.orig_p"],
                row["id.resp_h"],
                row["id.resp_p"],
                row["proto"],
            )
        except (ValueError, TypeError):
            parse_skipped += 1
            continue
        if key[0] < low or key[0] > high:
            continue
        in_window += 1
        digest = key_hash(key)
        if int(digest[:16], 16) % pair.hash_modulus != 0:
            continue
        duplicates[digest] += 1
        if digest not in sampled:
            sampled[digest] = {
                "key": key,
                "conn_line_index": line_index,
                "ts": float(row["ts"]),
                "orig_h": row["id.orig_h"],
                "resp_h": row["id.resp_h"],
                "orig_p": normalize_port(row["id.orig_p"]),
                "resp_p": normalize_port(row["id.resp_p"]),
                "proto": row["proto"],
                "service": row["service"],
                "duration": row["duration"],
                "orig_bytes": row["orig_bytes"],
                "resp_bytes": row["resp_bytes"],
                "conn_state": row["conn_state"],
                "history": row.get("history", "-"),
                "orig_pkts": row["orig_pkts"],
                "orig_ip_bytes": row["orig_ip_bytes"],
                "resp_pkts": row["resp_pkts"],
                "resp_ip_bytes": row["resp_ip_bytes"],
            }
    for digest in [value for value, count in duplicates.items() if count != 1]:
        sampled.pop(digest, None)
    return sampled, {
        "conn_rows_total": total,
        "conn_rows_in_gt_time_window": in_window,
        "conn_parse_skipped": parse_skipped,
        "hash_sample_modulus": pair.hash_modulus,
        "sampled_unique_conn_keys": len(sampled),
        "sampled_duplicate_conn_keys_rejected": sum(count != 1 for count in duplicates.values()),
        "gt_min_second": low,
        "gt_max_second": high,
    }


def exact_join(pair: Pair) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, audit = candidate_conn_rows(pair)
    gt_counts: Counter[str] = Counter()
    gt_labels: dict[str, set[str]] = defaultdict(set)
    gt_line: dict[str, int] = {}
    gt_total = 0
    gt_expected = 0
    with (DATA / pair.gt_rel).open("r", encoding="utf-8-sig", newline="") as f:
        for line_index, row in enumerate(csv.DictReader(f)):
            gt_total += 1
            label = str(row["type"]).strip().lower()
            if label != pair.ton_label:
                continue
            gt_expected += 1
            try:
                digest = key_hash(
                    exact_key(
                        row["ts"],
                        row["src_ip"],
                        row["src_port"],
                        row["dst_ip"],
                        row["dst_port"],
                        row["proto"],
                    )
                )
            except (ValueError, TypeError):
                continue
            if digest not in candidates:
                continue
            gt_counts[digest] += 1
            gt_labels[digest].add(label)
            gt_line.setdefault(digest, line_index)

    exact = [
        {**row, "key_sha256": digest, "gt_line_index": gt_line[digest]}
        for digest, row in candidates.items()
        if gt_counts[digest] == 1 and gt_labels[digest] == {pair.ton_label}
    ]
    exact.sort(key=lambda row: stable_hex(pair.pair_id, row["key_sha256"]))
    if len(exact) < pair.budget:
        raise RuntimeError(
            f"insufficient unambiguous exact joins for {pair.pair_id}: {len(exact)} < {pair.budget}"
        )

    selected = exact[: pair.budget]
    nodes = sorted({row["orig_h"] for row in selected} | {row["resp_h"] for row in selected})
    node_ids = {node: index for index, node in enumerate(nodes)}
    output: list[dict[str, Any]] = []
    for row in selected:
        duration = row["duration"]
        duration_numeric = None if duration in {"", "-"} else float(duration)
        output.append(
            {
                "record_id": "ckbt_" + stable_hex(pair.pair_id, row["key_sha256"])[:20],
                "dataset": "ToN-IoT_raw_network_Bro",
                "role": pair.role,
                "pair_id": pair.pair_id,
                "mechanism_family": pair.mechanism,
                "ton_groundtruth_label": pair.ton_label,
                "cross_dataset_mapping": "mechanism_family_only_not_exact_Gotham_label_equivalence",
                "conn_relative_path": pair.conn_rel,
                "groundtruth_relative_path": pair.gt_rel,
                "conn_line_index": row["conn_line_index"],
                "groundtruth_line_index": row["gt_line_index"],
                "exact_join_rule": "floor(conn.ts)==gt.ts_and_direct_5tuple_proto_unique_both_sides",
                "key_sha256": row["key_sha256"],
                "ts": f"{row['ts']:.6f}",
                "source_local_orig_node_id": node_ids[row["orig_h"]],
                "source_local_resp_node_id": node_ids[row["resp_h"]],
                "orig_p": row["orig_p"],
                "resp_p": row["resp_p"],
                "proto": row["proto"],
                "service": row["service"],
                "duration": duration,
                "orig_bytes": row["orig_bytes"],
                "resp_bytes": row["resp_bytes"],
                "conn_state": row["conn_state"],
                "history": row["history"],
                "orig_pkts": row["orig_pkts"],
                "orig_ip_bytes": row["orig_ip_bytes"],
                "resp_pkts": row["resp_pkts"],
                "resp_ip_bytes": row["resp_ip_bytes"],
                "completed_record_lower_bound_epoch": ""
                if duration_numeric is None
                else f"{row['ts'] + max(0.0, duration_numeric):.6f}",
                "explicit_log_emission_time_available": False,
                "allowed_for_static_completed_connection_supervision": True,
                "allowed_for_temporal_replay": False,
                "allowed_for_Gotham_C1_fit": False,
                "allowed_for_Gotham_threshold_selection": False,
                "report_or_sealed": False,
                "selection_allowed_within_aux_role_only": True,
            }
        )
    audit.update(
        {
            "pair_id": pair.pair_id,
            "mechanism_family": pair.mechanism,
            "role": pair.role,
            "conn_relative_path": pair.conn_rel,
            "groundtruth_relative_path": pair.gt_rel,
            "groundtruth_rows_total": gt_total,
            "groundtruth_expected_label_rows": gt_expected,
            "sampled_keys_with_any_gt_match": sum(count > 0 for count in gt_counts.values()),
            "sampled_ambiguous_gt_keys_rejected": sum(count != 1 for count in gt_counts.values()),
            "unambiguous_exact_join_rows": len(exact),
            "selected_rows": len(output),
            "source_local_nodes_selected": len(nodes),
        }
    )
    return output, audit


def main() -> None:
    if not CKAN_SUMMARY.is_file():
        raise FileNotFoundError(CKAN_SUMMARY)
    ckan_summary = json.loads(CKAN_SUMMARY.read_text(encoding="utf-8"))
    if ckan_summary.get("next_gate") != "PASS_A1_READY_WITH_TIMESTAMP_SORT_AND_HEADER_INFERENCE_POLICY":
        raise RuntimeError("CKAN loader gate is not PASS")

    conn_policy = {row["relative_path"]: row for row in read_csv(CKAN_CONN_POLICY)}
    gt_policy = {row["relative_path"]: row for row in read_csv(CKAN_GT_POLICY)}
    required = [CKAN_SUMMARY, CKAN_CONN_POLICY, CKAN_GT_POLICY]
    for pair in PAIRS:
        conn = DATA / pair.conn_rel
        gt = DATA / pair.gt_rel
        required.extend([conn, gt])
        if not conn.is_file() or not gt.is_file():
            raise FileNotFoundError((conn, gt))
        if conn_policy[pair.conn_rel]["loader_blocker"]:
            raise RuntimeError(f"CKAN loader blocker for {pair.conn_rel}")
        if gt_policy[pair.gt_rel]["required_fields_pass"].lower() != "true":
            raise RuntimeError(f"CKAN groundtruth schema blocker for {pair.gt_rel}")
    for relative in RESERVED_CONN_FILES:
        path = DATA / relative
        if not path.is_file():
            raise FileNotFoundError(path)

    OUT.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for pair in PAIRS:
        selected, audit = exact_join(pair)
        manifest.extend(selected)
        audits.append(audit)

    fit_sources = {row["conn_relative_path"] for row in manifest if row["role"] == "aux_process_fit"}
    select_sources = {
        row["conn_relative_path"] for row in manifest if row["role"] == "aux_process_select"
    }
    if fit_sources & select_sources:
        raise RuntimeError("auxiliary fit/select source files overlap")
    if {row["conn_relative_path"] for row in manifest} & set(RESERVED_CONN_FILES):
        raise RuntimeError("reserved ToN source entered auxiliary support")
    counts = Counter((row["mechanism_family"], row["role"]) for row in manifest)
    expected = {
        ("reconnaissance_scan", "aux_process_fit"): 2_000,
        ("reconnaissance_scan", "aux_process_select"): 500,
        ("credential_bruteforce", "aux_process_fit"): 2_000,
        ("credential_bruteforce", "aux_process_select"): 500,
    }
    if dict(counts) != expected:
        raise RuntimeError(f"auxiliary support counts changed: {counts}")

    write_csv(OUT / "pair_exact_join_audit.csv", audits)
    write_csv(OUT / "aux_process_support_candidate_manifest.csv", manifest)
    write_csv(
        OUT / "reserved_toniot_conn_sources.csv",
        [
            {
                "relative_path": relative,
                "role": "reserved_not_used",
                "used_rows": 0,
                "future_claim": "internal_holdout_only_not_untouched_final",
            }
            for relative in RESERVED_CONN_FILES
        ],
    )
    input_rows = [
        {
            "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in required
    ]
    write_csv(OUT / "input_file_hashes.csv", input_rows)

    contract = {
        "issue": ISSUE,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "TONIOT_AUX_PROCESS_SUPPORT_CANDIDATE_READY_FOR_STATIC_EXPERT_ONLY",
        "model_training": False,
        "hpc_submission": False,
        "mature_component": "ToN-IoT provided Bro/Zeek conn.log 21-field schema",
        "active_Gotham_support_train_rows": 385,
        "active_Gotham_support_val_rows": 127,
        "Gotham_support_mutated": False,
        "auxiliary_rows": len(manifest),
        "auxiliary_counts": {f"{mechanism}|{role}": count for (mechanism, role), count in sorted(counts.items())},
        "fit_source_files": sorted(fit_sources),
        "select_source_files": sorted(select_sources),
        "fit_select_source_overlap": 0,
        "reserved_conn_files": list(RESERVED_CONN_FILES),
        "reserved_rows_used": 0,
        "permanent_Gotham_report_families_used": 0,
        "Gotham_report_or_sealed_rows_used": 0,
        "cross_dataset_label_policy": "mechanism_family_only_not_exact_attack_label_equivalence",
        "allowed_scope": "static_completed_connection_process_expert_supervision",
        "forbidden_scope": [
            "Gotham_C1_fit_or_calibration",
            "Gotham_standardization_or_threshold_selection",
            "temporal_replay_or_past_only_claim_without_explicit_log_emission_time",
            "untouched_final_external_validation_claim",
        ],
        "next_gate": (
            "independently validate every selected raw line and exact join; then design the static "
            "Zeek process expert without touching Gotham report labels"
        ),
    }
    (OUT / "contract.json").write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "summary.md").write_text(
        "\n".join(
            [
                "# CKBT ToN-IoT auxiliary process-support gate",
                "",
                "Status: `TONIOT_AUX_PROCESS_SUPPORT_CANDIDATE_READY_FOR_STATIC_EXPERT_ONLY`.",
                "",
                "- Reused the dataset-provided mature Bro/Zeek 21-field `conn.log` representation and the prior CKAN loader policy.",
                "- Built an independent auxiliary candidate bank: 2,000 fit + 500 select scanning connections and 2,000 fit + 500 select password connections.",
                "- Every selected row is a unique direct join on `floor(conn.ts)`, source/destination IP and port, and protocol to the ToN-IoT GroundTruth event.",
                "- Fit and select use different conn-log/GroundTruth file pairs. This is source-file separation, not a claim of independent campaigns.",
                "- Seven additional scan/password conn files remain unused by this route.",
                "- The mapping is generic mechanism supervision (`scan`, `credential_bruteforce`), not a claim that ToN labels equal Gotham TCP Scan/Telnet labels.",
                "- Because the provided logs lack explicit log-emission time, these rows may supervise only a static completed-connection expert. They are forbidden for temporal replay.",
                "- Gotham support stays 385/127; all Gotham report/sealed families remain at zero use. No model was trained.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(contract, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
