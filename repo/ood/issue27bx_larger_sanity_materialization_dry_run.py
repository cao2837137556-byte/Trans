from __future__ import annotations

import csv
import gzip
import io
import json
import sys
import time
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dpkt
import numpy as np

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
OOD_DIR = REPO_DIR / "ood"
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ab_gotham_kitsune115_frontend_feasibility as ab  # noqa: E402

ISSUE = "issue27bx_larger_sanity_materialization_dry_run_from_contract_v1_2026-06-11"
OUT = ROOT / "runs" / ISSUE
CONTRACT_DIR = ROOT / "runs" / "issue27bw_larger_sanity_contract_construction_2026-06-11"
CONTRACT_PATH = CONTRACT_DIR / "larger_sanity_contract_v1.json"
DERIVED = ab.DATA_ROOT / "derived" / "kitsune115_larger_sanity_v1"
LOG_PATH = DERIVED / "issue27bx_materialization_log.txt"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

PRIMARY_STRATEGY = "train_state_then_eval_online"
WARMUP_PACKETS = 50
TARGET_TOTAL_ROWS = 250_000
MAX_TOTAL_ROWS_WITHOUT_CONFIRMATION = 10_000_000
SCAN_SLACK_PACKETS = 5_000

ROLE_QUOTAS = {
    "id_benign_train": 75_000,
    "id_benign_calib": 15_000,
    "ood_benign_val": 20_000,
    "ood_benign_stress": 35_000,
    "sealed_final_ood": 35_000,
    "attack_support_candidate_pool": 20_000,
    "dev_future_attack_query": 35_000,
    "sealed_final_attack": 15_000,
}

LOCAL_INCLUDE_BY_ROLE = {
    "id_benign_train": {
        "processed/iotsim-cooler-motor-1.csv",
        "processed/iotsim-cooler-motor-2.csv",
        "processed/iotsim-cooler-motor-3.csv",
        "processed/iotsim-cooler-motor-4.csv",
        "processed/iotsim-cooler-motor-10.csv",
        "processed/iotsim-cooler-motor-11.csv",
        "processed/iotsim-cooler-motor-12.csv",
        "processed/iotsim-cooler-motor-13.csv",
        "processed/iotsim-cooler-motor-14.csv",
        "processed/iotsim-cooler-motor-15.csv",
        "processed/iotsim-combined-cycle-tls-1.csv",
        "processed/iotsim-combined-cycle-tls-2.csv",
    },
    "id_benign_calib": {
        "processed/iotsim-predictive-maintenance-10.csv",
        "processed/iotsim-predictive-maintenance-11.csv",
        "processed/iotsim-combined-cycle-tls-3.csv",
        "processed/iotsim-combined-cycle-tls-4.csv",
        "processed/iotsim-combined-cycle-tls-5.csv",
    },
    "dev_future_attack_query": {
        "processed/iotsim-ip-camera-museum-1.csv",
        "processed/iotsim-combined-cycle-10.csv",
        "processed/iotsim-domotic-monitor-1.csv",
    },
}

STATE_HASH_MODE = "lightweight_local_pilot_no_pickle_state_hash"

ATTACK_PCAP_CACHE = {
    "processed/iotsim-air-quality-1.csv": {
        "pcap": "raw/malicious/mirai-infection/iotsim-air-quality-1_0-0_to_OpenvSwitch-25_1-0.pcap",
        "first_attack_ts": 1737235793.490203,
        "first_attack_label": "Telnet Brute Force",
        "pre_onset_packets": 2032,
    },
    "processed/iotsim-city-power-1.csv": {
        "pcap": "raw/malicious/mirai-infection/iotsim-city-power-1_0-0_to_OpenvSwitch-26_1-0.pcap",
        "first_attack_ts": 1737235783.576491,
        "first_attack_label": "Telnet Brute Force",
        "pre_onset_packets": 863,
    },
    "processed/iotsim-combined-cycle-10.csv": {
        "pcap": "raw/malicious/mirai-infection/iotsim-combined-cycle-10_0-0_to_OpenvSwitch-13_10-0.pcap",
        "first_attack_ts": 1737235781.420146,
        "first_attack_label": "Telnet Brute Force",
        "pre_onset_packets": 966,
    },
    "processed/iotsim-ip-camera-museum-1.csv": {
        "pcap": "raw/malicious/mirai-infection/iotsim-ip-camera-museum-1_0-0_to_OpenvSwitch-29_1-0.pcap",
        "first_attack_ts": 1737235770.488062,
        "first_attack_label": "Telnet Brute Force",
        "pre_onset_packets": 644553,
    },
    "processed/iotsim-building-monitor-1.csv": {
        "pcap": "raw/malicious/mirai-infection/iotsim-building-monitor-1_0-0_to_OpenvSwitch-28_1-0.pcap",
        "first_attack_ts": 1737235764.020608,
        "first_attack_label": "Telnet Brute Force",
        "pre_onset_packets": 1254,
    },
    "processed/iotsim-combined-cycle-1.csv": {
        "pcap": "raw/malicious/mirai-infection/iotsim-combined-cycle-1_0-0_to_OpenvSwitch-13_1-0.pcap",
        "first_attack_ts": 1737235781.420146,
        "first_attack_label": "Telnet Brute Force",
        "pre_onset_packets": 1042,
    },
    "processed/iotsim-domotic-monitor-1.csv": {
        "pcap": "raw/malicious/mirai-infection/iotsim-domotic-monitor-1_0-0_to_OpenvSwitch-23_1-0.pcap",
        "first_attack_ts": 1737235794.490721,
        "first_attack_label": "Telnet Brute Force",
        "pre_onset_packets": 2016,
    },
    "processed/iotsim-ip-camera-street-1.csv": {
        "pcap": "raw/malicious/mirai-infection/iotsim-ip-camera-street-1_0-0_to_OpenvSwitch-24_1-0.pcap",
        "first_attack_ts": 1737235800.982347,
        "first_attack_label": "Telnet Brute Force",
        "pre_onset_packets": 413113,
    },
}


@dataclass(frozen=True)
class FilePlan:
    role: str
    csv_member: str
    pcap_member: str
    target_rows: int
    expected_binary_label: str
    report_only: bool
    selection_allowed: bool
    record_start_ts: float | None
    first_attack_label: str
    planned_pre_onset_packets: int


def log(message: str) -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    print(message, flush=True)


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


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def load_role_inventory() -> dict[str, dict[str, str]]:
    with (CONTRACT_DIR / "role_file_inventory.csv").open("r", encoding="utf-8", newline="") as f:
        return {row["csv_archive_path"]: row for row in csv.DictReader(f)}


def split_quota(paths: list[str], total: int, inventory: dict[str, dict[str, str]], attack_only: bool) -> dict[str, int]:
    weights: dict[str, int] = {}
    for p in paths:
        row = inventory[p]
        weights[p] = int(row["attack_rows"] if attack_only else row["total_rows"])
    available = sum(weights.values())
    if available <= 0:
        return {p: 0 for p in paths}
    total = min(total, available)
    quotas = {p: int(total * weights[p] / available) for p in paths}
    for p in paths:
        if weights[p] > 0 and quotas[p] == 0:
            quotas[p] = 1
    while sum(quotas.values()) < total:
        p = max(paths, key=lambda x: weights[x] - quotas[x])
        quotas[p] += 1
    while sum(quotas.values()) > total:
        p = max(paths, key=lambda x: quotas[x])
        quotas[p] -= 1
    return quotas


def local_paths_for_role(role: str, paths: list[str]) -> list[str]:
    allowed = LOCAL_INCLUDE_BY_ROLE.get(role)
    if not allowed:
        return paths
    return [p for p in paths if p in allowed]


def lightweight_state_hash(role: str, csv_member: str, marker: str) -> str:
    return ab.sha256_bytes(f"{STATE_HASH_MODE}|{role}|{csv_member}|{marker}".encode("utf-8"))


def build_file_plans(contract: dict[str, Any], inventory: dict[str, dict[str, str]]) -> list[FilePlan]:
    roles = contract["roles"]
    plans: list[FilePlan] = []
    for role, paths in roles.items():
        if role not in ROLE_QUOTAS:
            continue
        paths = local_paths_for_role(role, paths)
        attack_role = role in {"attack_support_candidate_pool", "dev_future_attack_query", "sealed_final_attack"}
        quotas = split_quota(paths, ROLE_QUOTAS[role], inventory, attack_only=attack_role)
        for csv_member, target in quotas.items():
            if target <= 0:
                continue
            row = inventory[csv_member]
            if attack_role:
                cache = ATTACK_PCAP_CACHE[csv_member]
                plans.append(
                    FilePlan(
                        role=role,
                        csv_member=csv_member,
                        pcap_member=cache["pcap"],
                        target_rows=target,
                        expected_binary_label="attack",
                        report_only=role in {"dev_future_attack_query", "sealed_final_attack"},
                        selection_allowed=role == "attack_support_candidate_pool",
                        record_start_ts=float(cache["first_attack_ts"]),
                        first_attack_label=str(cache["first_attack_label"]),
                        planned_pre_onset_packets=int(cache["pre_onset_packets"]),
                    )
                )
            else:
                plans.append(
                    FilePlan(
                        role=role,
                        csv_member=csv_member,
                        pcap_member=row["pcap_counterpart_candidate"],
                        target_rows=target,
                        expected_binary_label="benign",
                        report_only=role in {"sealed_final_ood"},
                        selection_allowed=role not in {"sealed_final_ood"},
                        record_start_ts=None,
                        first_attack_label="",
                        planned_pre_onset_packets=0,
                    )
                )
    return plans


def sidecar_fieldnames() -> list[str]:
    return [
        "global_row_id",
        "strategy",
        "state_id",
        "role",
        "split_role",
        "pcap_member",
        "csv_member",
        "pcap_packet_index",
        "recorded_index_within_file",
        "packet_timestamp_epoch",
        "binary_label_from_alignment",
        "label_source",
        "first_attack_label",
        "warmup_only",
        "model_ready_hint",
        "report_only",
        "selection_allowed",
        "sealed_final",
        "forbidden_for_fit",
        "forbidden_for_threshold",
        "forbidden_for_model_selection",
    ]


def update_vec(nstat: ab.RestoredNetStat115, ts: float, buf: bytes) -> tuple[np.ndarray | None, str | None]:
    fields, error = ab.parse_packet(ts, buf)
    if error is not None:
        return None, error
    vec = nstat.update_get_stats(
        fields["ip_type"],
        fields["src_mac"],
        fields["dst_mac"],
        fields["src_ip"],
        fields["src_protocol"],
        fields["dst_ip"],
        fields["dst_protocol"],
        int(fields["datagram_size"]),
        float(fields["timestamp"]),
    )
    return vec.astype(np.float32), None


def emit_file(
    zf: zipfile.ZipFile,
    plan: FilePlan,
    nstat: ab.RestoredNetStat115,
    x_mm: np.memmap,
    y_mm: np.memmap,
    sidecar_writer: csv.DictWriter,
    row_offset: int,
) -> tuple[int, dict[str, Any]]:
    parse_errors = 0
    scanned = 0
    pre_record = 0
    emitted = 0
    first_ts = None
    last_ts = None
    state_before = lightweight_state_hash(plan.role, plan.csv_member, "before")
    max_scan_packets = plan.planned_pre_onset_packets + plan.target_rows + WARMUP_PACKETS + SCAN_SLACK_PACKETS
    with zf.open(plan.pcap_member, "r") as raw:
        reader = dpkt.pcap.Reader(io.BufferedReader(raw))
        for packet_index, (ts, buf) in enumerate(reader):
            if scanned >= max_scan_packets:
                break
            scanned += 1
            vec, error = update_vec(nstat, ts, buf)
            if error is not None or vec is None:
                parse_errors += 1
                continue
            if plan.record_start_ts is not None and float(ts) < plan.record_start_ts:
                pre_record += 1
                continue
            if emitted >= plan.target_rows:
                break
            global_row = row_offset + emitted
            x_mm[global_row, :] = vec
            y_mm[global_row] = 1 if plan.expected_binary_label == "attack" else 0
            warmup = emitted < WARMUP_PACKETS
            first_ts = float(ts) if first_ts is None else first_ts
            last_ts = float(ts)
            sealed = plan.role in {"sealed_final_ood", "sealed_final_attack"}
            sidecar_writer.writerow(
                {
                    "global_row_id": global_row,
                    "strategy": PRIMARY_STRATEGY,
                    "state_id": f"{PRIMARY_STRATEGY}::{plan.role}::{Path(plan.csv_member).stem}",
                    "role": plan.role,
                    "split_role": plan.role,
                    "pcap_member": plan.pcap_member,
                    "csv_member": plan.csv_member,
                    "pcap_packet_index": packet_index,
                    "recorded_index_within_file": emitted,
                    "packet_timestamp_epoch": f"{float(ts):.6f}",
                    "binary_label_from_alignment": plan.expected_binary_label,
                    "label_source": "post_onset_binary_from_csv_first_attack" if plan.expected_binary_label == "attack" else "all_benign_file_contract",
                    "first_attack_label": plan.first_attack_label,
                    "warmup_only": str(warmup).lower(),
                    "model_ready_hint": str(not warmup).lower(),
                    "report_only": str(plan.report_only).lower(),
                    "selection_allowed": str(plan.selection_allowed).lower(),
                    "sealed_final": str(sealed).lower(),
                    "forbidden_for_fit": str(sealed or plan.report_only).lower(),
                    "forbidden_for_threshold": str(sealed).lower(),
                    "forbidden_for_model_selection": str(sealed or plan.report_only).lower(),
                }
            )
            emitted += 1
    state_after = lightweight_state_hash(plan.role, plan.csv_member, "after")
    meta = {
        "role": plan.role,
        "csv_member": plan.csv_member,
        "pcap_member": plan.pcap_member,
        "target_rows": plan.target_rows,
        "emitted_rows": emitted,
        "packets_scanned": scanned,
        "pre_record_packets": pre_record,
        "parse_errors": parse_errors,
        "first_timestamp_epoch": first_ts,
        "last_timestamp_epoch": last_ts,
        "state_hash_before": state_before,
        "state_hash_after": state_after,
        "max_scan_packets": max_scan_packets,
        "completed_target": emitted == plan.target_rows,
        "report_only": plan.report_only,
        "selection_allowed": plan.selection_allowed,
    }
    return emitted, meta


def numeric_audit(x_path: Path, row_count: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    x = np.load(x_path, mmap_mode="r")
    rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    headers = ab.RestoredNetStat115().headers()
    for i, name in enumerate(headers):
        col = np.asarray(x[:row_count, i])
        finite = np.isfinite(col)
        rows.append(
            {
                "feature_index": i,
                "feature_name": name,
                "finite_rate": float(finite.mean()) if col.size else 0.0,
                "nan_count": int(np.isnan(col).sum()),
                "inf_count": int(np.isinf(col).sum()),
                "std": float(np.std(col[finite])) if finite.any() else "",
                "min": float(np.min(col[finite])) if finite.any() else "",
                "max": float(np.max(col[finite])) if finite.any() else "",
            }
        )
    for fam, start, end in [("MI_dir", 0, 15), ("H", 15, 30), ("HH", 30, 65), ("HH_jit", 65, 80), ("HpHp", 80, 115)]:
        block = np.asarray(x[:row_count, start:end])
        family_rows.append(
            {
                "family": fam,
                "columns": end - start,
                "finite_rate": float(np.isfinite(block).mean()) if block.size else 0.0,
                "nan_count": int(np.isnan(block).sum()),
                "inf_count": int(np.isinf(block).sum()),
                "max_abs": float(np.nanmax(np.abs(block))) if block.size else "",
            }
        )
    return rows, family_rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists():
        LOG_PATH.unlink()
    contract = load_contract()
    inventory = load_role_inventory()
    plans = build_file_plans(contract, inventory)
    planned_pairs = {(p.role, p.csv_member) for p in plans}
    deferred_rows: list[dict[str, Any]] = []
    for role, paths in contract["roles"].items():
        if role not in ROLE_QUOTAS:
            continue
        for csv_member in paths:
            if (role, csv_member) not in planned_pairs:
                deferred_rows.append(
                    {
                        "role": role,
                        "csv_member": csv_member,
                        "deferred_reason": "outside_local_pilot_subset_or_zero_quota",
                        "still_in_larger_contract": "true",
                    }
                )
    planned_rows = sum(p.target_rows for p in plans)
    if planned_rows > MAX_TOTAL_ROWS_WITHOUT_CONFIRMATION:
        raise RuntimeError(f"planned rows {planned_rows} exceeds local confirmation ceiling")
    if not ab.ZIP_PATH.exists():
        raise FileNotFoundError(ab.ZIP_PATH)

    prefix = DERIVED / f"gotham_kitsune115_larger_sanity_{PRIMARY_STRATEGY}"
    x_path = prefix.with_name(prefix.name + "_X.npy")
    y_path = prefix.with_name(prefix.name + "_y.npy")
    sidecar_path = prefix.with_name(prefix.name + "_sidecar.csv.gz")
    schema_path = prefix.with_name(prefix.name + "_feature_schema.json")
    split_manifest_path = prefix.with_name(prefix.name + "_split_manifest.csv.gz")
    role_meta_path = DERIVED / "gotham_kitsune115_larger_sanity_role_meta.csv"
    state_log_path = DERIVED / "gotham_kitsune115_larger_sanity_state_transition_log.csv"

    log(f"[start] {ISSUE} planned_rows={planned_rows}")
    log(f"[paths] x={x_path}")

    x_mm = np.lib.format.open_memmap(x_path, mode="w+", dtype=np.float32, shape=(planned_rows, 115))
    y_mm = np.lib.format.open_memmap(y_path, mode="w+", dtype=np.int8, shape=(planned_rows,))

    sidecar_f = gzip.open(sidecar_path, "wt", newline="", encoding="utf-8")
    sidecar_writer = csv.DictWriter(sidecar_f, fieldnames=sidecar_fieldnames())
    sidecar_writer.writeheader()

    role_meta: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    row_offset = 0

    try:
        with zipfile.ZipFile(ab.ZIP_PATH, "r") as zf:
            members = set(zf.namelist())
            missing = [p.pcap_member for p in plans if p.pcap_member not in members]
            if missing:
                raise RuntimeError(f"missing PCAP members: {missing[:5]}")
            train_state = ab.RestoredNetStat115()

            # ID train updates the shared train state. All other roles use isolated clones.
            for plan in plans:
                start = time.time()
                if plan.role == "id_benign_train":
                    nstat = train_state
                    state_action = "carry_train_state_within_id_train"
                    previous_state_id = "shared_train_state"
                else:
                    nstat = deepcopy(train_state)
                    state_action = "clone_train_state_then_discard_after_role"
                    previous_state_id = "shared_train_state_after_id_train"
                log(f"[file-start] role={plan.role} rows={plan.target_rows} csv={plan.csv_member}")
                emitted, meta = emit_file(zf, plan, nstat, x_mm, y_mm, sidecar_writer, row_offset)
                elapsed = time.time() - start
                meta["elapsed_seconds"] = round(elapsed, 3)
                role_meta.append(meta)
                state_rows.append(
                    {
                        "strategy": PRIMARY_STRATEGY,
                        "state_id": f"{PRIMARY_STRATEGY}::{plan.role}::{Path(plan.csv_member).stem}",
                        "previous_state_id": previous_state_id,
                        "role": plan.role,
                        "csv_member": plan.csv_member,
                        "pcap_member": plan.pcap_member,
                        "state_action": state_action,
                        "row_start": row_offset,
                        "row_end": row_offset + emitted - 1,
                        "emitted_rows": emitted,
                        "packets_scanned": meta["packets_scanned"],
                        "pre_record_packets": meta["pre_record_packets"],
                        "state_hash_before": meta["state_hash_before"],
                        "state_hash_after": meta["state_hash_after"],
                    }
                )
                row_offset += emitted
                log(f"[file-done] role={plan.role} emitted={emitted}/{plan.target_rows} total={row_offset} elapsed={elapsed:.1f}s")
    finally:
        sidecar_f.close()
        x_mm.flush()
        y_mm.flush()
        del x_mm
        del y_mm

    # The arrays are preallocated to planned_rows, while local PCAPs can emit fewer
    # rows than their requested quota. Persist only emitted rows so downstream
    # loaders cannot accidentally consume an unfilled tail.
    if row_offset < planned_rows:
        x_tmp = x_path.with_name(x_path.stem + "_trimmed.npy")
        y_tmp = y_path.with_name(y_path.stem + "_trimmed.npy")
        np.save(x_tmp, np.asarray(np.load(x_path, mmap_mode="r")[:row_offset], dtype=np.float32))
        np.save(y_tmp, np.asarray(np.load(y_path, mmap_mode="r")[:row_offset], dtype=np.int8))
        x_path.unlink()
        y_path.unlink()
        x_tmp.replace(x_path)
        y_tmp.replace(y_path)
        log(f"[trim] arrays trimmed from planned_rows={planned_rows} to emitted_rows={row_offset}")

    headers = ab.RestoredNetStat115().headers()
    schema = {
        "schema_id": "gotham_kitsune_restored115_v1",
        "feature_count": 115,
        "family_counts": {"MI_dir": 15, "H": 15, "HH": 35, "HH_jit": 15, "HpHp": 35},
        "feature_names": headers,
        "schema_sha256": ab.sha256_bytes("\n".join(headers).encode("utf-8")),
        "source_frontend": "repo/ood/issue27ab_gotham_kitsune115_frontend_feasibility.py::RestoredNetStat115",
    }
    schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    # A compressed split manifest mirrors the sidecar's role fields without copying feature data into the worktree.
    with gzip.open(sidecar_path, "rt", encoding="utf-8") as src, gzip.open(split_manifest_path, "wt", newline="", encoding="utf-8") as dst:
        reader = csv.DictReader(src)
        fields = [
            "global_row_id",
            "role",
            "split_role",
            "binary_label_from_alignment",
            "model_ready_hint",
            "report_only",
            "selection_allowed",
            "sealed_final",
            "csv_member",
            "pcap_member",
        ]
        writer = csv.DictWriter(dst, fieldnames=fields)
        writer.writeheader()
        for row in reader:
            writer.writerow({k: row[k] for k in fields})

    write_csv(role_meta_path, role_meta)
    write_csv(state_log_path, state_rows)
    write_csv(OUT / "larger_materialization_file_plan.csv", [p.__dict__ for p in plans])
    write_csv(OUT / "larger_materialization_deferred_contract_files.csv", deferred_rows)
    write_csv(OUT / "larger_materialization_role_meta.csv", role_meta)
    write_csv(OUT / "larger_materialization_state_transition_log.csv", state_rows)

    numeric_rows, family_rows = numeric_audit(x_path, row_offset)
    write_csv(OUT / "numeric_stability_report.csv", numeric_rows)
    write_csv(OUT / "per_family_feature_health.csv", family_rows)

    role_counts: dict[str, int] = {}
    model_ready_counts: dict[str, int] = {}
    for meta in role_meta:
        role_counts[meta["role"]] = role_counts.get(meta["role"], 0) + int(meta["emitted_rows"])
        model_ready_counts[meta["role"]] = model_ready_counts.get(meta["role"], 0) + max(0, int(meta["emitted_rows"]) - WARMUP_PACKETS)

    role_access_rows = []
    for role in ROLE_QUOTAS:
        sealed = role in {"sealed_final_ood", "sealed_final_attack"}
        report_only = sealed or role == "dev_future_attack_query"
        role_access_rows.append(
            {
                "role": role,
                "fit_allowed": str(not report_only).lower(),
                "threshold_allowed": str(role in {"id_benign_calib", "ood_benign_val", "ood_benign_stress", "attack_support_candidate_pool"}).lower(),
                "support_selection_allowed": str(role == "attack_support_candidate_pool").lower(),
                "model_selection_allowed": str(not report_only and not sealed).lower(),
                "score_replay_allowed": "true",
                "report_only": str(report_only).lower(),
                "sealed_final": str(sealed).lower(),
            }
        )
    write_csv(OUT / "role_access_audit.csv", role_access_rows)

    final_seal_rows = [
        {
            "role": "sealed_final_ood",
            "emitted_rows": role_counts.get("sealed_final_ood", 0),
            "used_for_fit_threshold_or_selection": "false",
            "verdict": "pass",
        },
        {
            "role": "sealed_final_attack",
            "emitted_rows": role_counts.get("sealed_final_attack", 0),
            "used_for_fit_threshold_or_selection": "false",
            "verdict": "pass",
        },
    ]
    write_csv(OUT / "final_seal_replay_audit.csv", final_seal_rows)

    artifact_rows = [
        {"artifact": "X_115D", "path": str(x_path), "sha256": ab.file_hash(x_path), "rows": row_offset, "columns": 115},
        {"artifact": "y", "path": str(y_path), "sha256": ab.file_hash(y_path), "rows": row_offset, "columns": 1},
        {"artifact": "sidecar", "path": str(sidecar_path), "sha256": ab.file_hash(sidecar_path), "rows": row_offset, "columns": len(sidecar_fieldnames())},
        {"artifact": "split_manifest", "path": str(split_manifest_path), "sha256": ab.file_hash(split_manifest_path), "rows": row_offset, "columns": 10},
        {"artifact": "feature_schema", "path": str(schema_path), "sha256": ab.file_hash(schema_path), "rows": 115, "columns": 1},
        {"artifact": "role_meta", "path": str(role_meta_path), "sha256": ab.file_hash(role_meta_path), "rows": len(role_meta), "columns": len(role_meta[0]) if role_meta else 0},
        {"artifact": "state_transition_log", "path": str(state_log_path), "sha256": ab.file_hash(state_log_path), "rows": len(state_rows), "columns": len(state_rows[0]) if state_rows else 0},
    ]
    write_csv(OUT / "larger_materialization_artifact_manifest.csv", artifact_rows)

    completed_all_targets = all(bool(m["completed_target"]) for m in role_meta)
    finite_ok = all(float(r["finite_rate"]) == 1.0 and int(r["nan_count"]) == 0 and int(r["inf_count"]) == 0 for r in family_rows)
    primary_verdict = (
        "larger_sanity_materialization_ready_for_frozen_system_replay"
        if completed_all_targets and finite_ok and row_offset >= TARGET_TOTAL_ROWS * 0.95
        else "larger_sanity_materialization_partial_needs_quota_or_frontend_fix"
    )

    summary_lines = [
        "# issue27bx Summary",
        "",
        "1. issue27bx completed: yes",
        f"2. primary_verdict: `{primary_verdict}`",
        f"3. strategy materialized: `{PRIMARY_STRATEGY}`",
        f"4. emitted rows: `{row_offset}`",
        "5. feature columns: `115`",
        f"6. role counts: `{json.dumps(role_counts, ensure_ascii=False)}`",
        f"7. model-ready counts after warmup: `{json.dumps(model_ready_counts, ensure_ascii=False)}`",
        f"8. numeric finite pass: `{finite_ok}`",
        f"9. completed all file quotas: `{completed_all_targets}`",
        "10. final/report-only used for fit/selection: `False`",
        "11. model run: no",
        "12. formal benchmark: no",
        f"13. state hash mode: `{STATE_HASH_MODE}`",
        "14. local pilot caveat: role-complete ~250k local smoke after the 1M local attempt exposed slow attack-PCAP extraction; exact pickle state hashes are deferred",
        f"15. X path: `{x_path}`",
        f"16. sidecar path: `{sidecar_path}`",
        "17. next recommended issue: `issue27by_larger_sanity_replay_current_frozen_system` if pilot passes, otherwise quota/frontend repair",
        "18. commit/push: not performed",
    ]
    write_md(OUT / "summary.md", summary_lines)

    decision_lines = [
        "# issue27bx Decision",
        "",
        f"primary_verdict: `{primary_verdict}`",
        "",
        "A bounded local larger sanity Kitsune115 asset was materialized from the issue27bw contract. This is a data/interface readiness asset, not a formal benchmark result.",
        "",
        "No model training, threshold tuning, OOD gate repair, or performance metric computation was performed.",
    ]
    write_md(OUT / "issue27bx_decision.md", decision_lines)

    next_lines = [
        "# issue27by Next Action",
        "",
        "Recommended next task: `issue27by_larger_sanity_replay_current_frozen_system`.",
        "",
        "Boundary:",
        "- load only the issue27bx frozen asset and hashes",
        "- replay the already-frozen current strongest system",
        "- do not select parameters from sealed final roles",
        "- report dev-side metrics separately from sealed report-only replay",
        "- if larger replay fails, diagnose role/scale/front-end/state before changing model logic",
    ]
    write_md(OUT / "issue27by_next_action.md", next_lines)

    cfg = {
        "issue": ISSUE,
        "input_contract": str(CONTRACT_PATH),
        "target_total_rows": TARGET_TOTAL_ROWS,
        "planned_rows": planned_rows,
        "emitted_rows": row_offset,
        "strategy": PRIMARY_STRATEGY,
        "warmup_packets": WARMUP_PACKETS,
        "scan_slack_packets": SCAN_SLACK_PACKETS,
        "state_hash_mode": STATE_HASH_MODE,
        "model_run": False,
        "formal_benchmark": False,
        "primary_verdict": primary_verdict,
    }
    (OUT / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "run_type": "larger_sanity_materialization_dry_run",
                "forbidden": ["model_training", "threshold_selection_from_final", "support_selection_from_final", "formal_benchmark"],
                "data_outputs": [str(x_path), str(y_path), str(sidecar_path), str(split_manifest_path)],
                "primary_verdict": primary_verdict,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_md(OUT / "command.txt", ["python repo/ood/issue27bx_larger_sanity_materialization_dry_run.py"])

    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest_rows.append({"path": str(path.relative_to(ROOT)), "sha256": ab.file_hash(path), "bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)

    append_once(
        MAINLINE_DOCS / "mainline_handoff.md",
        "issue27bx_larger_sanity_materialization_dry_run_from_contract_v1_2026-06-11",
        [
            "## issue27bx Larger Sanity Materialization Dry Run",
            "",
            "marker: `issue27bx_larger_sanity_materialization_dry_run_from_contract_v1_2026-06-11`",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            f"- emitted rows: `{row_offset}` with 115D Kitsune features",
            "- strategy: `train_state_then_eval_online`",
            "- no model run, no formal benchmark, no final-role selection",
            "- next action: `issue27by_larger_sanity_replay_current_frozen_system`",
        ],
    )
    append_once(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "issue27bx - Larger Sanity Materialization Dry Run",
        [
            "## issue27bx - Larger Sanity Materialization Dry Run",
            "",
            f"- output_dir: `runs/{ISSUE}/`",
            f"- decision: `{primary_verdict}`",
            "- stage: bounded local larger sanity asset materialization",
            "- no model run; data artifacts live under `datasets/gotham2025/derived/kitsune115_larger_sanity_v1/`",
            "- next: issue27by frozen-system replay",
        ],
    )

    log(f"[done] rows={row_offset} verdict={primary_verdict}")
    print(json.dumps({"issue": ISSUE, "primary_verdict": primary_verdict, "rows": row_offset, "x_path": str(x_path)}, indent=2))


if __name__ == "__main__":
    main()
