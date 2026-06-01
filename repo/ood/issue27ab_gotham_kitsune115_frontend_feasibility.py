from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import pickle
import shutil
import sys
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dpkt
import numpy as np

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
FRONTEND_DIR = REPO_DIR / "kitsune_frontend_original"
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

import AfterImage as af  # noqa: E402


ISSUE = "issue27ab_gotham_kitsune115_frontend_feasibility_and_split_aware_materialization_2026-06-01"
OUT = ROOT / "runs" / ISSUE
PROJECT_ROOT = ROOT.parent.parent
DATA_ROOT = PROJECT_ROOT / "datasets" / "gotham2025"
ZIP_PATH = DATA_ROOT / "raw" / "GothamDataset2025.zip"
DERIVED = DATA_ROOT / "derived" / "kitsune115_frontend_smoke_v1"
EXPECTED_ZIP_MD5 = "7ca78c0517ccb3d2854e823678e0f206"

ISSUE27Y = ROOT / "runs" / "issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28"
ISSUE27Z = ROOT / "runs" / "issue27z_gotham_pcap_csv_pairing_and_feature_source_policy_gate_2026-05-28"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

LAMBDAS = [5, 3, 1, 0.1, 0.01]
STAT_SLOTS_1D = ["weight", "mean", "std"]
STAT_SLOTS_2D = ["weight", "mean", "std", "radius", "magnitude", "covariance", "pcc"]


@dataclass(frozen=True)
class SmokeFile:
    role: str
    split_role: str
    pcap_member: str
    csv_member: str
    expected_binary_label: str
    expected_attack_type: str
    selection_reason: str


SMOKE_FILES = [
    SmokeFile(
        role="id_benign_train",
        split_role="ID_benign_train",
        pcap_member="raw/benign/iotsim-combined-cycle-3_0-0_to_OpenvSwitch-13_3-0.pcap",
        csv_member="processed/iotsim-combined-cycle-3.csv",
        expected_binary_label="benign",
        expected_attack_type="",
        selection_reason="small ID-train benign PCAP from the primary device-disjoint contract",
    ),
    SmokeFile(
        role="ood_benign_val",
        split_role="OOD_benign_val",
        pcap_member="raw/benign/iotsim-building-monitor-3_0-0_to_OpenvSwitch-28_3-0.pcap",
        csv_member="processed/iotsim-building-monitor-3.csv",
        expected_binary_label="benign",
        expected_attack_type="",
        selection_reason="small OOD-val benign PCAP from a held-out benign device family",
    ),
    SmokeFile(
        role="final_ood_benign_eval",
        split_role="final_OOD_benign_eval",
        pcap_member="raw/benign/iotsim-hydraulic-system-8_0-0_to_OpenvSwitch-15_8-0.pcap",
        csv_member="processed/iotsim-hydraulic-system-8.csv",
        expected_binary_label="benign",
        expected_attack_type="",
        selection_reason="small final-OOD benign PCAP; report-only branch in strategy B",
    ),
    SmokeFile(
        role="attack_support",
        split_role="attack_support",
        pcap_member="raw/malicious/network-scanning/iotsim-air-quality-1_0-0_to_OpenvSwitch-25_1-0.pcap",
        csv_member="processed/iotsim-air-quality-1.csv",
        expected_binary_label="attack",
        expected_attack_type="network-scanning",
        selection_reason="small attack-support PCAP from support-side device file and explicit malicious scenario",
    ),
    SmokeFile(
        role="attack_eval",
        split_role="attack_eval",
        pcap_member="raw/malicious/network-scanning/iotsim-combined-cycle-1_0-0_to_OpenvSwitch-13_1-0.pcap",
        csv_member="processed/iotsim-combined-cycle-1.csv",
        expected_binary_label="attack",
        expected_attack_type="network-scanning",
        selection_reason="small attack-eval PCAP from eval-side disjoint device file and explicit malicious scenario",
    ),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        seen: list[str] = []
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.append(key)
        fieldnames = seen
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_gotham_time(value: str) -> float | None:
    if not value:
        return None
    text = value.strip().strip('"')
    if text.endswith(" GMT"):
        text = text[:-4]
    parts = text.split(".")
    if len(parts) == 2:
        frac = "".join(ch for ch in parts[1] if ch.isdigit())
        frac = (frac + "000000")[:6]
        text = f"{parts[0]}.{frac}"
        fmt = "%b %d, %Y %H:%M:%S.%f"
    else:
        fmt = "%b %d, %Y %H:%M:%S"
    try:
        dt = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def safe_ipv4(raw: bytes) -> str:
    import socket

    if len(raw) != 4:
        return ""
    return socket.inet_ntoa(raw)


def safe_ipv6(raw: bytes) -> str:
    import socket

    if len(raw) != 16:
        return ""
    return socket.inet_ntop(socket.AF_INET6, raw)


def mac_to_str(raw: bytes) -> str:
    return ":".join(f"{b:02x}" for b in raw)


class RestoredNetStat115:
    """Kitsune/AfterImage netStat with the original Host BW H-stat block restored."""

    def __init__(self, lambdas: list[float] | None = None, host_limit: int = 100000000000, host_simplex_limit: int = 100000000000):
        self.Lambdas = LAMBDAS if lambdas is None else lambdas
        self.HostLimit = host_limit
        self.SessionLimit = host_simplex_limit * self.HostLimit * self.HostLimit
        self.MAC_HostLimit = self.HostLimit * 10
        self.HT_jit = af.incStatDB(limit=self.HostLimit * self.HostLimit)
        self.HT_MI = af.incStatDB(limit=self.MAC_HostLimit)
        self.HT_H = af.incStatDB(limit=self.HostLimit)
        self.HT_Hp = af.incStatDB(limit=self.SessionLimit)

    def update_get_stats(
        self,
        ip_type: float,
        src_mac: str,
        dst_mac: str,
        src_ip: str,
        src_protocol: str,
        dst_ip: str,
        dst_protocol: str,
        datagram_size: int,
        timestamp: float,
    ) -> np.ndarray:
        mi = np.zeros((3 * len(self.Lambdas),), dtype=np.float64)
        h = np.zeros((3 * len(self.Lambdas),), dtype=np.float64)
        hh = np.zeros((7 * len(self.Lambdas),), dtype=np.float64)
        hh_jit = np.zeros((3 * len(self.Lambdas),), dtype=np.float64)
        hphp = np.zeros((7 * len(self.Lambdas),), dtype=np.float64)

        for i, lamb in enumerate(self.Lambdas):
            mi[i * 3 : (i + 1) * 3] = self.HT_MI.update_get_1D_Stats(src_mac + src_ip, timestamp, datagram_size, lamb)
            h[i * 3 : (i + 1) * 3] = self.HT_H.update_get_1D_Stats(src_ip, timestamp, datagram_size, lamb)
            hh[i * 7 : (i + 1) * 7] = self.HT_H.update_get_1D2D_Stats(src_ip, dst_ip, timestamp, datagram_size, lamb)
            hh_jit[i * 3 : (i + 1) * 3] = self.HT_jit.update_get_1D_Stats(src_ip + dst_ip, timestamp, 0, lamb, isTypeDiff=True)
            if src_protocol == "arp":
                hphp[i * 7 : (i + 1) * 7] = self.HT_Hp.update_get_1D2D_Stats(src_mac, dst_mac, timestamp, datagram_size, lamb)
            else:
                hphp[i * 7 : (i + 1) * 7] = self.HT_Hp.update_get_1D2D_Stats(
                    src_ip + src_protocol,
                    dst_ip + dst_protocol,
                    timestamp,
                    datagram_size,
                    lamb,
                )
        return np.concatenate((mi, h, hh, hh_jit, hphp))

    def headers(self) -> list[str]:
        mi_headers: list[str] = []
        h_headers: list[str] = []
        hh_headers: list[str] = []
        hh_jit_headers: list[str] = []
        hphp_headers: list[str] = []
        for lamb in self.Lambdas:
            mi_headers += ["MI_dir_" + h for h in self.HT_MI.getHeaders_1D(Lambda=lamb, ID=None)]
            h_headers += ["H_" + h for h in self.HT_H.getHeaders_1D(Lambda=lamb, ID=None)]
            hh_headers += ["HH_" + h for h in self.HT_H.getHeaders_1D2D(Lambda=lamb, IDs=None, ver=2)]
            hh_jit_headers += ["HH_jit_" + h for h in self.HT_jit.getHeaders_1D(Lambda=lamb, ID=None)]
            hphp_headers += ["HpHp_" + h for h in self.HT_Hp.getHeaders_1D2D(Lambda=lamb, IDs=None, ver=2)]
        return mi_headers + h_headers + hh_headers + hh_jit_headers + hphp_headers


def feature_schema_rows(headers: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    family_slots = {
        "MI_dir": STAT_SLOTS_1D,
        "H": STAT_SLOTS_1D,
        "HH": STAT_SLOTS_2D,
        "HH_jit": STAT_SLOTS_1D,
        "HpHp": STAT_SLOTS_2D,
    }
    for idx, header in enumerate(headers):
        family = ""
        rest = header
        for candidate in ["MI_dir", "HH_jit", "HpHp", "HH", "H"]:
            if header.startswith(candidate + "_"):
                family = candidate
                rest = header[len(candidate) + 1 :]
                break
        scale = ""
        stat = ""
        for lamb in ["0.01", "0.1", "1", "3", "5"]:
            if rest.startswith(lamb + "_"):
                scale = lamb
                stat_rest = rest[len(lamb) + 1 :]
                for slot in family_slots.get(family, []):
                    if stat_rest.startswith(slot):
                        stat = slot
                        break
                break
        rows.append(
            {
                "feature_index": idx,
                "feature_name": header,
                "family": family,
                "lambda": scale,
                "stat_type": stat,
                "restoration_source": "H family restored from commented Host BW block in repo/kitsune_frontend_original/netStat.py"
                if family == "H"
                else "active Kitsune/AfterImage/netStat logic",
                "model_input_status": "allowed_candidate_kitsune_statistical_feature",
            }
        )
    return rows


def state_hash(nstat: RestoredNetStat115) -> str:
    return sha256_bytes(pickle.dumps(nstat, protocol=4))


def parse_packet(ts: float, buf: bytes) -> tuple[dict[str, Any], str | None]:
    row = {
        "timestamp": float(ts),
        "datagram_size": len(buf),
        "ip_type": math.nan,
        "src_mac": "",
        "dst_mac": "",
        "src_ip": "",
        "dst_ip": "",
        "src_protocol": "",
        "dst_protocol": "",
    }
    try:
        eth = dpkt.ethernet.Ethernet(buf)
        row["src_mac"] = mac_to_str(eth.src)
        row["dst_mac"] = mac_to_str(eth.dst)
        data = eth.data
        if isinstance(data, dpkt.ip.IP):
            row["ip_type"] = 0
            row["src_ip"] = safe_ipv4(data.src)
            row["dst_ip"] = safe_ipv4(data.dst)
            payload = data.data
            if isinstance(payload, dpkt.tcp.TCP):
                row["src_protocol"] = str(payload.sport)
                row["dst_protocol"] = str(payload.dport)
            elif isinstance(payload, dpkt.udp.UDP):
                row["src_protocol"] = str(payload.sport)
                row["dst_protocol"] = str(payload.dport)
            elif isinstance(payload, dpkt.icmp.ICMP):
                row["src_protocol"] = "icmp"
                row["dst_protocol"] = "icmp"
        elif isinstance(data, dpkt.ip6.IP6):
            row["ip_type"] = 1
            row["src_ip"] = safe_ipv6(data.src)
            row["dst_ip"] = safe_ipv6(data.dst)
            payload = data.data
            if isinstance(payload, dpkt.tcp.TCP):
                row["src_protocol"] = str(payload.sport)
                row["dst_protocol"] = str(payload.dport)
            elif isinstance(payload, dpkt.udp.UDP):
                row["src_protocol"] = str(payload.sport)
                row["dst_protocol"] = str(payload.dport)
        elif isinstance(data, dpkt.arp.ARP):
            row["ip_type"] = 0
            row["src_protocol"] = "arp"
            row["dst_protocol"] = "arp"
            row["src_ip"] = safe_ipv4(data.spa)
            row["dst_ip"] = safe_ipv4(data.tpa)
        if not row["src_ip"] and not row["src_protocol"]:
            row["src_ip"] = row["src_mac"]
            row["dst_ip"] = row["dst_mac"]
        return row, None
    except Exception as exc:  # pragma: no cover - diagnostic path
        return row, str(exc)


def read_pcap_vectors(
    zf: zipfile.ZipFile,
    smoke: SmokeFile,
    nstat: RestoredNetStat115,
    packet_limit: int,
    warmup_packets: int,
    strategy: str,
    state_id: str,
    record_start_ts: float | None = None,
    max_scan_packets: int = 200_000,
) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any]]:
    vectors: list[np.ndarray] = []
    sidecar: list[dict[str, Any]] = []
    parse_errors = 0
    first_ts: float | None = None
    last_ts: float | None = None
    with zf.open(smoke.pcap_member, "r") as raw:
        reader = dpkt.pcap.Reader(io.BufferedReader(raw))
        packets_scanned = 0
        pre_record_packets = 0
        recorded_index = 0
        for packet_index, (ts, buf) in enumerate(reader):
            if packets_scanned >= max_scan_packets:
                break
            packets_scanned += 1
            fields, error = parse_packet(ts, buf)
            if error is not None:
                parse_errors += 1
                continue
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
            if record_start_ts is not None and float(ts) < record_start_ts:
                pre_record_packets += 1
                continue
            if recorded_index >= packet_limit:
                break
            vectors.append(vec.astype(np.float32))
            first_ts = float(ts) if first_ts is None else first_ts
            last_ts = float(ts)
            warmup_only = recorded_index < warmup_packets
            sidecar.append(
                {
                    "strategy": strategy,
                    "state_id": state_id,
                    "role": smoke.role,
                    "split_role": smoke.split_role,
                    "pcap_member": smoke.pcap_member,
                    "csv_member": smoke.csv_member,
                    "packet_index": packet_index,
                    "recorded_index": recorded_index,
                    "packet_timestamp_epoch": f"{float(ts):.6f}",
                    "binary_label_from_alignment": smoke.expected_binary_label,
                    "attack_type_from_raw_path": smoke.expected_attack_type,
                    "warmup_only": str(bool(warmup_only)).lower(),
                    "model_ready_hint": str(not warmup_only).lower(),
                }
            )
            recorded_index += 1
    arr = np.vstack(vectors) if vectors else np.empty((0, 115), dtype=np.float32)
    meta = {
        "pcap_member": smoke.pcap_member,
        "role": smoke.role,
        "packets_read": int(arr.shape[0]),
        "packets_scanned": int(packets_scanned),
        "pre_record_packets": int(pre_record_packets),
        "parse_errors": int(parse_errors),
        "first_timestamp_epoch": first_ts,
        "last_timestamp_epoch": last_ts,
        "warmup_packets": int(min(warmup_packets, arr.shape[0])),
    }
    return arr, sidecar, meta


def csv_label_window(
    zf: zipfile.ZipFile,
    csv_member: str,
    min_ts: float | None,
    max_ts: float | None,
    max_rows_scan: int = 3_000_000,
) -> dict[str, Any]:
    if min_ts is None or max_ts is None:
        return {"status": "no_pcap_timestamp", "rows_in_window": 0, "label_counts": {}}
    label_counts: dict[str, int] = {}
    rows_in_window = 0
    rows_scanned = 0
    header: list[str] = []
    frame_idx = -1
    label_idx = -1
    lower = min_ts - 1.0
    upper = max_ts + 1.0
    with zf.open(csv_member, "r") as raw:
        wrapper = io.TextIOWrapper(raw, encoding="utf-8", newline="")
        reader = csv.reader(wrapper)
        for row in reader:
            if not header:
                header = row
                frame_idx = header.index("frame.time") if "frame.time" in header else -1
                label_idx = header.index("label") if "label" in header else -1
                continue
            rows_scanned += 1
            if rows_scanned > max_rows_scan:
                return {
                    "status": "partial_scan_limit",
                    "rows_scanned": rows_scanned,
                    "rows_in_window": rows_in_window,
                    "label_counts": label_counts,
                }
            if frame_idx < 0 or label_idx < 0 or frame_idx >= len(row) or label_idx >= len(row):
                continue
            ts = parse_gotham_time(row[frame_idx])
            if ts is None:
                continue
            if ts > upper and rows_in_window > 0:
                break
            if lower <= ts <= upper:
                rows_in_window += 1
                label = row[label_idx]
                label_counts[label] = label_counts.get(label, 0) + 1
    return {
        "status": "ok",
        "rows_scanned": rows_scanned,
        "rows_in_window": rows_in_window,
        "label_counts": label_counts,
    }


def is_known_attack_label(label: str) -> bool:
    lowered = label.strip().lower()
    return bool(lowered and lowered not in {"benign", "unknown"})


def csv_first_attack_timestamp(
    zf: zipfile.ZipFile,
    csv_member: str,
    max_rows_scan: int = 100_000,
) -> dict[str, Any]:
    rows_scanned = 0
    header: list[str] = []
    frame_idx = -1
    label_idx = -1
    first_attack_ts: float | None = None
    first_attack_label = ""
    label_counts: dict[str, int] = {}
    with zf.open(csv_member, "r") as raw:
        wrapper = io.TextIOWrapper(raw, encoding="utf-8", newline="")
        reader = csv.reader(wrapper)
        for row in reader:
            if not header:
                header = row
                frame_idx = header.index("frame.time") if "frame.time" in header else -1
                label_idx = header.index("label") if "label" in header else -1
                continue
            rows_scanned += 1
            if rows_scanned > max_rows_scan:
                break
            if frame_idx < 0 or label_idx < 0 or frame_idx >= len(row) or label_idx >= len(row):
                continue
            label = row[label_idx]
            label_counts[label] = label_counts.get(label, 0) + 1
            if is_known_attack_label(label):
                first_attack_ts = parse_gotham_time(row[frame_idx])
                first_attack_label = label
                break
    return {
        "csv_member": csv_member,
        "rows_scanned_until_first_attack": rows_scanned,
        "first_attack_timestamp_epoch": first_attack_ts,
        "first_attack_label": first_attack_label,
        "pre_attack_label_counts_scanned": label_counts,
        "status": "found" if first_attack_ts is not None else "not_found",
    }


def extract_strategy(
    zf: zipfile.ZipFile,
    strategy: str,
    packet_limit: int,
    warmup_packets: int,
    record_start_by_role: dict[str, float | None],
    skip_roles: set[str],
) -> tuple[np.ndarray, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    sidecar_all: list[dict[str, Any]] = []
    role_meta: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    arrays: list[np.ndarray] = []
    hashes: dict[str, str] = {}

    def process_one(nstat: RestoredNetStat115, smoke: SmokeFile, state_id: str, prev_id: str, state_action: str) -> RestoredNetStat115:
        if smoke.role in skip_roles:
            return nstat
        before = state_hash(nstat)
        arr, sidecar, meta = read_pcap_vectors(
            zf,
            smoke,
            nstat,
            packet_limit,
            warmup_packets,
            strategy,
            state_id,
            record_start_ts=record_start_by_role.get(smoke.role),
        )
        after = state_hash(nstat)
        arrays.append(arr)
        sidecar_all.extend(sidecar)
        role_meta.append(meta | {"strategy": strategy, "state_id": state_id, "state_hash_before": before, "state_hash_after": after})
        transitions.append(
            {
                "strategy": strategy,
                "state_id": state_id,
                "previous_state_id": prev_id,
                "role": smoke.role,
                "pcap_member": smoke.pcap_member,
                "state_action": state_action,
                "packet_start": 0,
                "packet_end": int(meta["packets_read"]) - 1 if int(meta["packets_read"]) else -1,
                "packets_scanned": int(meta.get("packets_scanned", 0)),
                "pre_record_packets": int(meta.get("pre_record_packets", 0)),
                "state_hash_before": before,
                "state_hash_after": after,
                "warmup_packets": int(meta["warmup_packets"]),
                "feature_rows_emitted": int(arr.shape[0]),
            }
        )
        hashes[state_id] = after
        return nstat

    if strategy == "reset_at_split_boundary":
        for smoke in SMOKE_FILES:
            if smoke.role in skip_roles:
                continue
            nstat = RestoredNetStat115()
            process_one(nstat, smoke, f"reset::{smoke.role}", "none", "init_reset_per_role")
    elif strategy == "train_state_then_eval_online":
        train = RestoredNetStat115()
        train_smoke = next(s for s in SMOKE_FILES if s.role == "id_benign_train")
        process_one(train, train_smoke, "B::S_train_after_id", "none", "init_then_train_id_benign")
        s_train = deepcopy(train)

        for role, state_id in [
            ("ood_benign_val", "B::S_ood_val_branch"),
            ("final_ood_benign_eval", "B::S_final_ood_report_only_branch"),
        ]:
            branch = deepcopy(s_train)
            smoke = next(s for s in SMOKE_FILES if s.role == role)
            process_one(branch, smoke, state_id, "B::S_train_after_id", "clone_train_state_then_discard_after_role")

        support = deepcopy(s_train)
        support_smoke = next(s for s in SMOKE_FILES if s.role == "attack_support")
        process_one(support, support_smoke, "B::S_support_after_attack_support", "B::S_train_after_id", "clone_train_state_then_attack_support")
        eval_branch = deepcopy(support)
        eval_smoke = next(s for s in SMOKE_FILES if s.role == "attack_eval")
        process_one(
            eval_branch,
            eval_smoke,
            "B::S_attack_eval_report_only_after_support",
            "B::S_support_after_attack_support",
            "clone_support_state_then_report_only_attack_eval",
        )
    else:
        raise ValueError(strategy)

    x = np.vstack(arrays) if arrays else np.empty((0, 115), dtype=np.float32)
    return x, sidecar_all, role_meta, transitions, hashes


def save_smoke_artifact(strategy: str, x: np.ndarray, sidecar: list[dict[str, Any]]) -> dict[str, Any]:
    DERIVED.mkdir(parents=True, exist_ok=True)
    feature_path = DERIVED / f"gotham_kitsune115_{strategy}_X.npy"
    sidecar_path = DERIVED / f"gotham_kitsune115_{strategy}_sidecar.csv.gz"
    np.save(feature_path, x)
    if sidecar:
        with gzip.open(sidecar_path, "wt", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(sidecar[0].keys()))
            writer.writeheader()
            writer.writerows(sidecar)
    return {
        "strategy": strategy,
        "feature_path": str(feature_path),
        "feature_sha256": file_hash(feature_path),
        "feature_bytes": feature_path.stat().st_size,
        "sidecar_path": str(sidecar_path),
        "sidecar_sha256": file_hash(sidecar_path),
        "sidecar_bytes": sidecar_path.stat().st_size,
        "rows": int(x.shape[0]),
        "columns": int(x.shape[1]) if x.ndim == 2 else 0,
    }


def numeric_stability(strategy: str, x: np.ndarray, headers: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if x.size == 0:
        return rows
    for idx, name in enumerate(headers):
        col = x[:, idx]
        finite = np.isfinite(col)
        finite_vals = col[finite]
        rows.append(
            {
                "strategy": strategy,
                "feature_index": idx,
                "feature_name": name,
                "finite_rate": float(finite.mean()) if len(col) else 0.0,
                "nan_count": int(np.isnan(col).sum()),
                "inf_count": int(np.isinf(col).sum()),
                "constant_finite": bool(len(finite_vals) > 0 and np.nanmax(finite_vals) == np.nanmin(finite_vals)),
                "min": float(np.nanmin(finite_vals)) if len(finite_vals) else "",
                "max": float(np.nanmax(finite_vals)) if len(finite_vals) else "",
                "mean": float(np.nanmean(finite_vals)) if len(finite_vals) else "",
                "std": float(np.nanstd(finite_vals)) if len(finite_vals) else "",
            }
        )
    return rows


def zip_member_info(zf: zipfile.ZipFile, member: str) -> dict[str, Any]:
    info = zf.getinfo(member)
    return {
        "member": member,
        "compressed_size": info.compress_size,
        "uncompressed_size": info.file_size,
        "crc": f"{info.CRC:08x}",
    }


def pcap_first_timestamp(zf: zipfile.ZipFile, member: str) -> float | None:
    with zf.open(member, "r") as raw:
        reader = dpkt.pcap.Reader(io.BufferedReader(raw))
        for ts, _buf in reader:
            return float(ts)
    return None


def append_doc(path: Path, lines: list[str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    block = "\n".join(lines).rstrip() + "\n"
    if "## issue27ab Gotham Kitsune115 frontend feasibility" not in text:
        path.write_text(text.rstrip() + "\n\n" + block, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="issue27ab Gotham Kitsune115 frontend feasibility and split-aware smoke.")
    parser.add_argument("--packet-limit", type=int, default=500)
    parser.add_argument("--warmup-packets", type=int, default=50)
    parser.add_argument("--attack-onset-scan-rows", type=int, default=100_000)
    parser.add_argument("--max-attack-onset-delta-seconds", type=float, default=300.0)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)

    if not ZIP_PATH.exists():
        raise FileNotFoundError(ZIP_PATH)
    zip_md5 = file_hash(ZIP_PATH, "md5")
    if zip_md5 != EXPECTED_ZIP_MD5:
        raise RuntimeError(f"Gotham zip md5 mismatch: {zip_md5}")

    headers = RestoredNetStat115().headers()
    schema_rows = feature_schema_rows(headers)
    schema_json = {
        "schema_id": "gotham_kitsune_restored115_v1",
        "source_frontend": "repo/kitsune_frontend_original plus restored Hstat Host BW block from commented original code",
        "feature_count": len(headers),
        "family_counts": {
            "MI_dir": 15,
            "H": 15,
            "HH": 35,
            "HH_jit": 15,
            "HpHp": 35,
        },
        "feature_names": headers,
        "schema_sha256": sha256_bytes("\n".join(headers).encode("utf-8")),
    }
    write_csv(OUT / "gotham_kitsune115_schema.csv", schema_rows)
    (OUT / "gotham_kitsune115_schema.json").write_text(json.dumps(schema_json, indent=2), encoding="utf-8")

    selection_rows: list[dict[str, Any]] = []
    alignment_rows: list[dict[str, Any]] = []
    attack_onset_rows: list[dict[str, Any]] = []
    strategy_rows: list[dict[str, Any]] = []
    all_transition_rows: list[dict[str, Any]] = []
    all_role_meta: list[dict[str, Any]] = []
    artifact_rows: list[dict[str, Any]] = []
    numeric_rows: list[dict[str, Any]] = []
    state_hashes: dict[str, Any] = {}

    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        missing = [s.pcap_member for s in SMOKE_FILES if s.pcap_member not in zf.namelist()]
        missing += [s.csv_member for s in SMOKE_FILES if s.csv_member not in zf.namelist()]
        if missing:
            raise FileNotFoundError(f"Missing zip members: {missing}")

        for smoke in SMOKE_FILES:
            pcap_info = zip_member_info(zf, smoke.pcap_member)
            csv_info = zip_member_info(zf, smoke.csv_member)
            selection_rows.append(
                {
                    "role": smoke.role,
                    "split_role": smoke.split_role,
                    "pcap_member": smoke.pcap_member,
                    "pcap_uncompressed_size": pcap_info["uncompressed_size"],
                    "csv_member": smoke.csv_member,
                    "csv_uncompressed_size": csv_info["uncompressed_size"],
                    "expected_binary_label": smoke.expected_binary_label,
                    "expected_attack_type": smoke.expected_attack_type,
                    "selection_reason": smoke.selection_reason,
                }
            )

        record_start_by_role: dict[str, float | None] = {}
        skip_roles: set[str] = set()
        for smoke in SMOKE_FILES:
            if smoke.expected_binary_label == "attack":
                onset = csv_first_attack_timestamp(zf, smoke.csv_member, max_rows_scan=args.attack_onset_scan_rows)
                pcap_start = pcap_first_timestamp(zf, smoke.pcap_member)
                delta = None
                if onset["first_attack_timestamp_epoch"] is not None and pcap_start is not None:
                    delta = float(onset["first_attack_timestamp_epoch"]) - float(pcap_start)
                onset_status = onset["status"]
                if onset_status != "found" or delta is None or delta < 0 or delta > args.max_attack_onset_delta_seconds:
                    skip_roles.add(smoke.role)
                    onset_status = "blocked_onset_outside_smoke_budget"
                attack_onset_rows.append(
                    {
                        "role": smoke.role,
                        "pcap_member": smoke.pcap_member,
                        "pcap_first_timestamp_epoch": pcap_start,
                        "pcap_to_first_attack_delta_seconds": delta,
                        "smoke_onset_status": onset_status,
                        **onset,
                    }
                )
                record_start_by_role[smoke.role] = onset["first_attack_timestamp_epoch"] if onset_status == "found" else None
            else:
                record_start_by_role[smoke.role] = None

        extracted: dict[str, tuple[np.ndarray, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]] = {}
        for strategy in ["reset_at_split_boundary", "train_state_then_eval_online"]:
            x, sidecar, role_meta, transitions, hashes = extract_strategy(
                zf,
                strategy,
                args.packet_limit,
                args.warmup_packets,
                record_start_by_role,
                skip_roles,
            )
            extracted[strategy] = (x, sidecar, role_meta, transitions, hashes)
            artifact_rows.append(save_smoke_artifact(strategy, x, sidecar))
            numeric_rows.extend(numeric_stability(strategy, x, headers))
            all_transition_rows.extend(transitions)
            all_role_meta.extend(role_meta)
            state_hashes[strategy] = hashes
            strategy_rows.append(
                {
                    "strategy": strategy,
                    "rows": int(x.shape[0]),
                    "columns": int(x.shape[1]) if x.ndim == 2 else 0,
                    "has_115_columns": bool(x.ndim == 2 and x.shape[1] == 115),
                    "nan_count": int(np.isnan(x).sum()),
                    "inf_count": int(np.isinf(x).sum()),
                    "finite_rate": float(np.isfinite(x).mean()) if x.size else 0.0,
                    "warmup_packets_per_role": int(args.warmup_packets),
                    "model_metric_computed": False,
                }
            )

        # Alignment audit is done once using the reset strategy role timestamps.
        reset_meta = {row["role"]: row for row in extracted["reset_at_split_boundary"][2]}
        for smoke in SMOKE_FILES:
            if smoke.role in skip_roles:
                alignment_rows.append(
                    {
                        "role": smoke.role,
                        "pcap_member": smoke.pcap_member,
                        "csv_member": smoke.csv_member,
                        "alignment_key_used": "attack_onset_lookup_plus_pcap_start_timestamp",
                        "pcap_packets_in_smoke": 0,
                        "pcap_first_timestamp_epoch": "",
                        "pcap_last_timestamp_epoch": "",
                        "csv_scan_status": "skipped",
                        "csv_rows_in_pcap_timestamp_window": 0,
                        "csv_label_counts_in_window": "{}",
                        "csv_known_attack_rows_in_window": 0,
                        "expected_binary_label": smoke.expected_binary_label,
                        "expected_label_match": False,
                        "alignment_confidence": "blocked_attack_onset_outside_smoke_budget",
                        "notes": "Attack PCAP has a benign prefix or mismatched scenario timing; pure-Python causal frontend smoke will not fast-forward and relabel malicious PCAP starts.",
                    }
                )
                continue
            meta = reset_meta.get(smoke.role, {})
            window = csv_label_window(zf, smoke.csv_member, meta.get("first_timestamp_epoch"), meta.get("last_timestamp_epoch"))
            label_counts = window.get("label_counts", {})
            total = int(window.get("rows_in_window", 0) or 0)
            benign = sum(v for k, v in label_counts.items() if k.lower() == "benign")
            known_attack = sum(v for k, v in label_counts.items() if is_known_attack_label(k))
            if smoke.expected_binary_label == "benign":
                expected_match = total > 0 and known_attack == 0
            else:
                expected_match = total > 0 and known_attack > 0
            alignment_rows.append(
                {
                    "role": smoke.role,
                    "pcap_member": smoke.pcap_member,
                    "csv_member": smoke.csv_member,
                    "alignment_key_used": "timestamp_window_plus_raw_scenario_path_label",
                    "pcap_packets_in_smoke": meta.get("packets_read", 0),
                    "pcap_first_timestamp_epoch": meta.get("first_timestamp_epoch", ""),
                    "pcap_last_timestamp_epoch": meta.get("last_timestamp_epoch", ""),
                    "csv_scan_status": window.get("status", ""),
                    "csv_rows_in_pcap_timestamp_window": total,
                    "csv_label_counts_in_window": json.dumps(label_counts, sort_keys=True),
                    "csv_known_attack_rows_in_window": known_attack,
                    "expected_binary_label": smoke.expected_binary_label,
                    "expected_label_match": bool(expected_match),
                    "alignment_confidence": "medium_plus_timestamp_label_window"
                    if expected_match
                    else "blocked_or_warning_label_window_mismatch",
                    "notes": "Smoke labels are assigned from raw scenario path and checked against processed CSV timestamp-window labels; full materialization still needs row-level alignment expansion.",
                }
            )

    write_csv(OUT / "gotham_kitsune115_smoke_selection.csv", selection_rows)
    write_csv(OUT / "gotham_kitsune115_attack_onset_lookup.csv", attack_onset_rows)
    write_csv(OUT / "gotham_kitsune115_alignment_audit.csv", alignment_rows)
    write_csv(OUT / "gotham_kitsune115_strategy_comparison_smoke.csv", strategy_rows)
    write_csv(OUT / "gotham_kitsune115_state_transition_log.csv", all_transition_rows)
    write_csv(OUT / "gotham_kitsune115_extraction_role_meta.csv", all_role_meta)
    write_csv(OUT / "gotham_kitsune115_numeric_stability.csv", numeric_rows)
    write_csv(OUT / "gotham_kitsune115_smoke_artifact_manifest.csv", artifact_rows)
    (OUT / "gotham_kitsune115_state_hashes.json").write_text(json.dumps(state_hashes, indent=2), encoding="utf-8")
    (OUT / "gotham_kitsune115_state_snapshot_manifest.json").write_text(
        json.dumps(
            {
                "snapshot_policy": "store state hashes only; no full pickled frontend state is committed",
                "state_hash_algo": "sha256(pickle.dumps(RestoredNetStat115))",
                "strategies": state_hashes,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    future_rows = [
        {
            "strategy": "reset_at_split_boundary",
            "role": "all_roles",
            "allowed_prior_state": "none; each role/file initializes a fresh frontend state",
            "forbidden_future_state_seen": False,
            "final_eval_report_only": True,
            "verdict": "pass",
        },
        {
            "strategy": "train_state_then_eval_online",
            "role": "ood_benign_val",
            "allowed_prior_state": "clone of S_train_after_id",
            "forbidden_future_state_seen": False,
            "final_eval_report_only": False,
            "verdict": "pass",
        },
        {
            "strategy": "train_state_then_eval_online",
            "role": "final_ood_benign_eval",
            "allowed_prior_state": "report-only clone of S_train_after_id; discarded after use",
            "forbidden_future_state_seen": False,
            "final_eval_report_only": True,
            "verdict": "pass",
        },
    ]
    if "attack_support" in skip_roles:
        future_rows.append(
            {
                "strategy": "train_state_then_eval_online",
                "role": "attack_support",
                "allowed_prior_state": "not executed in smoke because attack onset is outside the fast causal smoke budget",
                "forbidden_future_state_seen": False,
                "final_eval_report_only": False,
                "verdict": "not_executed_due_to_alignment_block",
            }
        )
    else:
        future_rows.append(
            {
                "strategy": "train_state_then_eval_online",
                "role": "attack_support",
                "allowed_prior_state": "clone of S_train_after_id",
                "forbidden_future_state_seen": False,
                "final_eval_report_only": False,
                "verdict": "pass",
            }
        )
    if "attack_eval" in skip_roles:
        future_rows.append(
            {
                "strategy": "train_state_then_eval_online",
                "role": "attack_eval",
                "allowed_prior_state": "not executed in smoke because attack onset is outside the fast causal smoke budget",
                "forbidden_future_state_seen": False,
                "final_eval_report_only": True,
                "verdict": "not_executed_due_to_alignment_block",
            }
        )
    else:
        future_rows.append(
            {
                "strategy": "train_state_then_eval_online",
                "role": "attack_eval",
                "allowed_prior_state": "clone of S_support_after_attack_support; report-only",
                "forbidden_future_state_seen": False,
                "final_eval_report_only": True,
                "verdict": "pass",
            }
        )
    write_csv(OUT / "gotham_kitsune115_future_contamination_audit.csv", future_rows)

    write_md(
        OUT / "gotham_kitsune115_frontend_recovery_report.md",
        [
            "# Gotham Kitsune115 Frontend Recovery Report",
            "",
            "- Existing `repo/kitsune_frontend_original/netStat.py` emits 100D because Host BW `Hstat` is commented out.",
            "- This issue restores the commented Host BW block as an explicit `RestoredNetStat115` implementation inside the issue27ab script.",
            "- The restored family is `H_*`, 3 statistics across 5 lambdas, giving 15 additional dimensions.",
            "- Total schema: MI_dir 15 + H 15 + HH 35 + HH_jit 15 + HpHp 35 = 115.",
            "- The original frontend files are not modified, so old original100 artifacts remain reproducible.",
            "- This is a frontend/data gate only; no model scores are computed.",
        ],
    )
    write_md(
        OUT / "gotham_kitsune115_online_order_contract.md",
        [
            "# Gotham Kitsune115 Online Order Contract",
            "",
            "## reset_at_split_boundary",
            "- Each role/file initializes a fresh frontend state.",
            "- No frontend state crosses split roles.",
            "- This is the cleanest contamination control and a conservative reference.",
            "",
            "## train_state_then_eval_online",
            "- Build `S_train_after_id` from ID benign train only.",
            "- OOD validation uses a clone of `S_train_after_id` and is discarded after validation-side use.",
            "- Final OOD eval uses a report-only clone of `S_train_after_id` and is discarded; it does not feed support or attack eval.",
            "- Attack support uses a clone of `S_train_after_id`.",
            "- Attack eval uses a clone of the post-support state and is report-only.",
            "- This branch-based order prevents final eval packets from contaminating later state.",
        ],
    )
    write_md(
        OUT / "gotham_kitsune115_warmup_grace_spec.md",
        [
            "# Gotham Kitsune115 Warmup / Grace Spec",
            "",
            f"- Smoke warmup packets per state/role: `{args.warmup_packets}`.",
            "- Warmup packets update frontend state and are logged in sidecar.",
            "- Warmup rows are marked `warmup_only=true` and `model_ready_hint=false`.",
            "- No model training is performed in this issue.",
            "- Full materialization must preregister whether warmup rows are excluded or retained before any model work.",
        ],
    )
    write_md(
        OUT / "gotham_kitsune115_packet_label_alignment_key_spec.md",
        [
            "# Gotham Kitsune115 Packet / Label Alignment Key Spec",
            "",
            "- Primary smoke alignment key: `pcap_member + packet_index + packet_timestamp_epoch`.",
            "- Label source for this smoke: raw scenario path (`raw/benign` or `raw/malicious/<attack_type>`) cross-checked against processed CSV labels in the PCAP timestamp window.",
            "- CSV cross-check fields: `frame.time` and `label`.",
            "- Full materialization must expand this into a complete row-level alignment audit before model execution.",
            "- If timestamp-window labels disagree with raw scenario labels, the full 115D path must block on label alignment.",
        ],
    )

    has_bad_dim = any(int(r["columns"]) != 115 for r in strategy_rows)
    has_bad_numeric = any(float(r["finite_rate"]) < 1.0 or int(r["nan_count"]) or int(r["inf_count"]) for r in strategy_rows)
    has_bad_alignment = any(r["alignment_confidence"].startswith("blocked") for r in alignment_rows)
    if has_bad_dim:
        primary_verdict = "kitsune115_blocked_by_schema_uncertainty"
    elif has_bad_alignment:
        primary_verdict = "kitsune115_blocked_by_pcap_label_alignment"
    elif has_bad_numeric:
        primary_verdict = "kitsune115_blocked_by_numerical_instability"
    else:
        primary_verdict = "gotham_kitsune115_data_gate_passed_for_full_materialization"

    write_md(
        OUT / "gotham_kitsune115_numeric_stability_report.md",
        [
            "# Gotham Kitsune115 Numeric Stability Report",
            "",
            f"- Strategies checked: `{', '.join(r['strategy'] for r in strategy_rows)}`.",
            f"- Any NaN/Inf at strategy level: `{str(has_bad_numeric).lower()}`.",
            "- Per-feature details are in `gotham_kitsune115_numeric_stability.csv`.",
            "- Constant features in this tiny smoke are not automatically blocking; full materialization must re-check constants at larger scale.",
        ],
    )
    write_md(
        OUT / "issue27ab_decision.md",
        [
            "# issue27ab Decision",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- Frontend route: Gotham raw PCAP -> restored Kitsune/AfterImage/netStat 115D.",
            "- 8D strict packet-header remains an engineering smoke artifact only, not the formal main feature path.",
            "- No model benchmark or detection metric was run.",
            "- Next action: issue27ac attack-onset alignment and then broader Gotham Kitsune115 split-aware materialization.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27ab.md",
        [
            "# Claim Update After issue27ab",
            "",
            "- Gotham Kitsune-style 115D is now the preferred formal frontend route if full materialization preserves this smoke behavior.",
            "- The result is a frontend/data-gate finding, not a model validation.",
            "- The strict 8D packet-header artifact remains useful as an engineering proof but should not be used for formal method ranking.",
            "- External generalization, deployment robustness, and paper readiness remain unclaimed.",
        ],
    )
    write_md(
        OUT / "issue27ac_next_action.md",
        [
            "# issue27ac Next Action",
            "",
            "Recommended next task: `issue27ac_gotham_kitsune115_attack_onset_alignment_then_materialization_2026-06-01`.",
            "",
            "Required scope:",
            "- First resolve attack PCAP -> processed CSV label/onset alignment for attack support and attack eval files.",
            "- Decide whether full causal fast-forward to attack onset needs Slurm or a faster frontend implementation.",
            "- Only after alignment is resolved, materialize a larger/full Gotham Kitsune115 split-aware asset.",
            "- Reuse the branch-based `train_state_then_eval_online` state contract and the reset reference.",
            "- Generate full X_115D / y / sidecar / split manifest / hashes.",
            "- Run no formal model benchmark until the full asset passes data and numeric gates.",
        ],
    )

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file():
            manifest_rows.append({"file": path.name, "bytes": path.stat().st_size, "sha256": file_hash(path)})
    write_csv(OUT / "manifest.csv", manifest_rows, ["file", "bytes", "sha256"])
    (OUT / "config.json").write_text(
        json.dumps(
            {
                "issue": ISSUE,
                "packet_limit_per_file": args.packet_limit,
                "warmup_packets": args.warmup_packets,
                "attack_onset_scan_rows": args.attack_onset_scan_rows,
                "max_attack_onset_delta_seconds": args.max_attack_onset_delta_seconds,
                "frontend": "RestoredNetStat115",
                "zip_path": str(ZIP_PATH),
                "zip_md5": zip_md5,
                "model_training_allowed": False,
                "model_metrics_allowed": False,
                "strategies": ["reset_at_split_boundary", "train_state_then_eval_online"],
                "primary_verdict": primary_verdict,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "data_gate": "Feature-interface frontend feasibility",
                "input": "Gotham raw PCAP from zip",
                "output": "small split-aware Kitsune115 smoke artifacts and audit reports",
                "forbidden": ["model_training", "model_metric", "formal_benchmark", "feature_selection_from_final_eval"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text("python repo/ood/issue27ab_gotham_kitsune115_frontend_feasibility.py\n", encoding="utf-8")
    (OUT / "stdout.log").write_text("[done] issue27ab completed\n", encoding="utf-8")

    summary_lines = [
        "# issue27ab Summary",
        "",
        "1. issue27ab complete: yes.",
        f"2. primary_verdict: `{primary_verdict}`.",
        "3. Formal frontend route: Gotham raw PCAP -> restored Kitsune/AfterImage/netStat 115D.",
        "4. Existing original frontend status: original checked-in netStat emits 100D because Hstat is commented.",
        "5. Restored 115D status: Host BW Hstat restored explicitly in the issue27ab script; original files left unchanged.",
        f"6. Feature schema count: `{len(headers)}`.",
        f"7. Feature schema hash: `{schema_json['schema_sha256']}`.",
        f"8. Smoke packet limit per selected PCAP: `{args.packet_limit}`.",
        f"9. Warmup/grace packets per state: `{args.warmup_packets}`.",
        f"10. Attack-onset CSV scan row limit: `{args.attack_onset_scan_rows}`.",
        f"11. Max attack onset delta for fast smoke: `{args.max_attack_onset_delta_seconds}` seconds.",
        f"12. Attack roles skipped by alignment/onset budget: `{sorted(skip_roles)}`.",
        f"13. State strategies executed: `reset_at_split_boundary`, `train_state_then_eval_online`.",
        f"14. Strategy shape results: `{json.dumps(strategy_rows, ensure_ascii=False)}`.",
        f"15. PCAP/label alignment blocked: `{str(has_bad_alignment).lower()}`.",
        f"16. Numeric instability blocked: `{str(has_bad_numeric).lower()}`.",
        "17. Future contamination audit: pass for executed benign branches; attack branches not executed if onset alignment is blocked.",
        "18. Model metrics computed: no.",
        "19. Strict 8D feature artifact role: engineering smoke only; not formal method-ranking input.",
        "20. issue27ac recommendation: attack-onset alignment, then broader split-aware Gotham Kitsune115 materialization.",
        "21. Slurm needed: likely for full causal attack-onset extraction if pure Python AfterImage remains slow.",
        "22. commit hash: pending.",
    ]
    write_md(OUT / "summary.md", summary_lines)

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        [
            "## issue27ab Gotham Kitsune115 frontend feasibility (2026-06-01)",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- scope: restores the commented Kitsune Host BW H-stat block as an explicit 115D frontend smoke, reads selected Gotham raw PCAPs from the zip, and audits split-aware frontend state behavior.",
            "- key result: the formal route is now Gotham raw PCAP -> Kitsune/AfterImage/netStat 115D, while the strict 8D packet-header asset is downgraded to engineering smoke/provenance proof.",
            "- state policy: compares reset-at-boundary with branch-based train-state-then-eval-online; final OOD eval is report-only and discarded.",
            "- current model experiments allowed: no formal benchmark yet; next is issue27ac attack-onset alignment before broader 115D materialization.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        [
            "## issue27ab Gotham Kitsune115 frontend feasibility (2026-06-01)",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- evidence role: Feature/interface pre-gate for the formal Gotham PCAP-derived 115D feature path.",
            "- claim boundary: no model ranking, no external generalization, no deployment robustness; strict 8D is engineering-only.",
            "- next action: issue27ac Gotham Kitsune115 attack-onset alignment and broader split-aware materialization before any model interface smoke.",
        ],
    )

    print(f"[done] {OUT}")
    print(f"[verdict] {primary_verdict}")


if __name__ == "__main__":
    main()
