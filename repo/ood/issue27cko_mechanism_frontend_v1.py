"""issue27cko: mechanism frontend v1.

This is the first *real traffic-mechanism* frontend audit after the raw115 C4
baseline.  It keeps the detector head fixed:

    four-class HistGB: ID benign / ordinary OOD / hard OOD / attack

and changes only the input representation:

    M0_raw115
    M1_mechanism_only
    M2_raw115_plus_mechanism

Mechanism features are extracted from the corresponding processed Gotham CSV
rows inside the raw dataset zip.  They use packet fields only
(length/protocol/IP/port/TCP flags) plus past-only rolling state within the
same processed source file and the same source endpoint.  The processed `label`
column is never used as a feature.  Report-only rows are never used for fitting
or threshold selection.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
import zipfile
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

OOD_DIR = Path(__file__).resolve().parent
REPO_DIR = OOD_DIR.parent
ROOT = REPO_DIR.parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckc_frozen_medium_mainline_replay_on_certified_1m as ckc  # noqa: E402
import issue27ckf_hard_ood_calibrated_worst_group_veto as ckf  # noqa: E402
import issue27ckg_basic_capability_diagnostic as ckg  # noqa: E402
import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27cki_c4_full_data_multiclass_replay as cki  # noqa: E402


ISSUE = "issue27cko_mechanism_frontend_v1_2026-06-29"
OUT = ROOT / "runs" / ISSUE
JOB_INDEX = 1
TRAIN_CAP = 20_000
SMOKE_TRAIN_CAP = 1_200
SMOKE_EVAL_CAP = 4_000
FULL_CAP = 10**9
WINDOWS = [8, 32, 128]
BENIGN_SAFE_Q = 0.99
ALIGNMENT_AUDIT_SAMPLE_PER_ROLE = 64

GOTHAM_ZIP = ckc.PROJECT_ROOT / "datasets" / "gotham2025" / "raw" / "GothamDataset2025.zip"
PROCESSED_USECOLS = [
    "frame.len",
    "frame.protocols",
    "eth.src",
    "eth.dst",
    "ip.src",
    "ip.dst",
    "ip.proto",
    "tcp.srcport",
    "tcp.dstport",
    "tcp.flags",
    "udp.srcport",
    "udp.dstport",
    # Read for audit only; never converted into features.
    "label",
]


CURRENT_FEATURES = [
    "cur_log_frame_len",
    "cur_is_tcp",
    "cur_is_udp",
    "cur_is_icmp",
    "cur_src_port_log",
    "cur_dst_port_log",
    "cur_dst_well_known",
    "cur_is_dns",
    "cur_is_coap",
    "cur_is_http",
    "cur_is_tls",
    "cur_tcp_syn",
    "cur_tcp_ack",
    "cur_tcp_rst",
    "cur_tcp_fin",
]

ROLLING_BASE = [
    "count_frac",
    "len_mean_log",
    "tcp_rate",
    "udp_rate",
    "unique_src_frac",
    "unique_dst_frac",
    "unique_dport_frac",
]

MECHANISM_FEATURES = list(CURRENT_FEATURES)
for scope in ["file", "src"]:
    for window in WINDOWS:
        for base in ROLLING_BASE:
            if scope == "src" and base == "unique_src_frac":
                continue
            MECHANISM_FEATURES.append(f"prior_{scope}_{base}_w{window}")


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    kind: str
    description: str


FEATURE_SPECS = [
    FeatureSpec("M0_raw115", "raw", "C4 raw115 control."),
    FeatureSpec(
        "M1_mechanism_only",
        "mechanism",
        "Current packet + past-only flow/source behavior features from processed CSV fields.",
    ),
    FeatureSpec(
        "M2_raw115_plus_mechanism",
        "raw_plus_mechanism",
        "C4 raw115 plus current/past-only mechanism features.",
    ),
]


ROLE_EVAL = [
    ("id_calib", "select", "benign_id"),
    ("ood_val", "select", "benign_ood"),
    ("ood_stress", "select", "hard_ood"),
    ("support_val", "select", "attack"),
    ("same_file_query", "select", "attack"),
    ("future_query", "select", "attack"),
    ("sealed_final_ood", "all", "benign_ood_report"),
    ("sealed_final_attack", "all", "attack_report"),
]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: clean(row.get(key, "")) for key in fields} for row in rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def fmt(value: Any, digits: int = 4) -> str:
    try:
        val = float(value)
    except Exception:
        return "nan"
    if not math.isfinite(val):
        return "nan"
    return f"{val:.{digits}f}"


def deterministic_cap(indices: np.ndarray, cap: int) -> np.ndarray:
    indices = np.asarray(indices, dtype=np.int64)
    if len(indices) <= cap:
        return indices
    keep = np.linspace(0, len(indices) - 1, num=cap, dtype=np.int64)
    return indices[keep]


def role_indices(frame_by_role: dict[str, pd.DataFrame], role: str, phase: str, cap: int) -> np.ndarray:
    frame = frame_by_role[role]
    if phase == "all":
        idx = np.arange(len(frame), dtype=np.int64)
    else:
        idx = np.flatnonzero(frame["phase"].astype(str).to_numpy() == phase)
    return deterministic_cap(idx, cap)


def safe_num(values: Any, default: float = 0.0) -> np.ndarray:
    arr = pd.to_numeric(values, errors="coerce").to_numpy(dtype=np.float64)
    return np.nan_to_num(arr, nan=default, posinf=default, neginf=default)


def coalesce_str(a: Any, b: Any, fallback: str) -> str:
    av = "" if pd.isna(a) else str(a)
    if av and av.lower() != "nan":
        return av
    bv = "" if pd.isna(b) else str(b)
    if bv and bv.lower() != "nan":
        return bv
    return fallback


def parse_tcp_flags(value: Any) -> int:
    if pd.isna(value):
        return 0
    text = str(value).strip().lower()
    if not text or text == "nan":
        return 0
    try:
        if text.startswith("0x"):
            return int(text, 16)
        return int(float(text))
    except Exception:
        return 0


class RollingState:
    def __init__(self, window: int):
        self.window = int(window)
        self.lengths: deque[float] = deque(maxlen=self.window)
        self.is_tcp: deque[float] = deque(maxlen=self.window)
        self.is_udp: deque[float] = deque(maxlen=self.window)
        self.src: deque[str] = deque(maxlen=self.window)
        self.dst: deque[str] = deque(maxlen=self.window)
        self.dport: deque[int] = deque(maxlen=self.window)

    def features(self, include_src_unique: bool) -> list[float]:
        n = len(self.lengths)
        if n == 0:
            if include_src_unique:
                return [0.0] * 7
            return [0.0] * 6
        out = [
            n / self.window,
            float(np.mean(self.lengths)),
            float(np.mean(self.is_tcp)),
            float(np.mean(self.is_udp)),
        ]
        if include_src_unique:
            out.append(len(set(self.src)) / self.window)
        out.extend(
            [
                len(set(self.dst)) / self.window,
                len(set(self.dport)) / self.window,
            ]
        )
        return out

    def update(self, length_log: float, is_tcp: float, is_udp: float, src: str, dst: str, dport: int) -> None:
        self.lengths.append(float(length_log))
        self.is_tcp.append(float(is_tcp))
        self.is_udp.append(float(is_udp))
        self.src.append(str(src))
        self.dst.append(str(dst))
        self.dport.append(int(dport))


class MechanismZipFeatureCache:
    def __init__(self, zip_path: Path, smoke: bool = False):
        if not zip_path.exists():
            raise FileNotFoundError(f"Missing Gotham raw zip: {zip_path}")
        self.zip_path = zip_path
        self.smoke = bool(smoke)
        self._features: dict[str, dict[int, np.ndarray]] = {}
        self._row_audits: dict[str, dict[int, dict[str, Any]]] = {}
        self.audit_rows: list[dict[str, Any]] = []

    def read_processed(self, member: str) -> pd.DataFrame:
        with zipfile.ZipFile(self.zip_path) as zf:
            if member not in zf.namelist():
                raise FileNotFoundError(f"{member} not found inside {self.zip_path}")
            with zf.open(member) as f:
                return pd.read_csv(f, usecols=lambda col: col in PROCESSED_USECOLS, low_memory=False)

    def features_for_member(self, member: str, row_indices: np.ndarray) -> dict[int, np.ndarray]:
        requested = sorted({int(v) for v in np.asarray(row_indices, dtype=np.int64) if int(v) >= 0})
        if not requested:
            return {}
        known = self._features.get(member, {})
        missing = [idx for idx in requested if idx not in known]
        if not missing:
            return {idx: known[idx] for idx in requested}
        started = time.time()
        df = self.read_processed(member)
        max_needed = min(max(missing), len(df) - 1)
        target = set(idx for idx in missing if idx < len(df))
        missing_oob = len(missing) - len(target)
        features: dict[int, np.ndarray] = dict(known)
        row_audits: dict[int, dict[str, Any]] = dict(self._row_audits.get(member, {}))
        file_state = {w: RollingState(w) for w in WINDOWS}
        src_state: dict[str, dict[int, RollingState]] = defaultdict(lambda: {w: RollingState(w) for w in WINDOWS})

        label_col = df.get("label", pd.Series([""] * len(df))).astype(str).to_numpy()
        proto_text = df.get("frame.protocols", pd.Series([""] * len(df))).astype(str).to_numpy()
        ip_proto = safe_num(df.get("ip.proto", pd.Series([0] * len(df))), 0.0)
        frame_len = np.log1p(safe_num(df.get("frame.len", pd.Series([0] * len(df))), 0.0))
        frame_len_raw = safe_num(df.get("frame.len", pd.Series([0] * len(df))), 0.0)
        tcp_src = safe_num(df.get("tcp.srcport", pd.Series([0] * len(df))), 0.0)
        tcp_dst = safe_num(df.get("tcp.dstport", pd.Series([0] * len(df))), 0.0)
        udp_src = safe_num(df.get("udp.srcport", pd.Series([0] * len(df))), 0.0)
        udp_dst = safe_num(df.get("udp.dstport", pd.Series([0] * len(df))), 0.0)
        tcp_flags = [parse_tcp_flags(v) for v in df.get("tcp.flags", pd.Series([0] * len(df))).to_numpy()]
        ip_src = df.get("ip.src", pd.Series([""] * len(df))).to_numpy()
        ip_dst = df.get("ip.dst", pd.Series([""] * len(df))).to_numpy()
        eth_src = df.get("eth.src", pd.Series([""] * len(df))).to_numpy()
        eth_dst = df.get("eth.dst", pd.Series([""] * len(df))).to_numpy()

        for i in range(max_needed + 1):
            proto = str(proto_text[i]).lower()
            is_tcp = float(ip_proto[i] == 6 or tcp_src[i] > 0 or tcp_dst[i] > 0 or "tcp" in proto)
            is_udp = float(ip_proto[i] == 17 or udp_src[i] > 0 or udp_dst[i] > 0 or "udp" in proto)
            is_icmp = float(ip_proto[i] == 1 or "icmp" in proto)
            src_port = float(tcp_src[i] if tcp_src[i] > 0 else udp_src[i])
            dst_port = float(tcp_dst[i] if tcp_dst[i] > 0 else udp_dst[i])
            dst_port_i = int(dst_port) if np.isfinite(dst_port) and dst_port > 0 else 0
            flags = int(tcp_flags[i])
            src = coalesce_str(ip_src[i], eth_src[i], f"row{i}:src")
            dst = coalesce_str(ip_dst[i], eth_dst[i], f"row{i}:dst")
            cur = [
                float(frame_len[i]),
                is_tcp,
                is_udp,
                is_icmp,
                float(np.log1p(max(src_port, 0.0))),
                float(np.log1p(max(dst_port, 0.0))),
                float(0 < dst_port <= 1024),
                float(dst_port_i == 53 or "dns" in proto),
                float(dst_port_i == 5683 or "coap" in proto),
                float(dst_port_i in {80, 8080} or "http" in proto),
                float(dst_port_i == 443 or "tls" in proto or "ssl" in proto),
                float(bool(flags & 0x02)),
                float(bool(flags & 0x10)),
                float(bool(flags & 0x04)),
                float(bool(flags & 0x01)),
            ]
            if i in target:
                vals = list(cur)
                for w in WINDOWS:
                    vals.extend(file_state[w].features(include_src_unique=True))
                for w in WINDOWS:
                    vals.extend(src_state[src][w].features(include_src_unique=False))
                features[i] = np.asarray(vals, dtype=np.float32)
                row_audits[i] = {
                    "processed_row_exists": True,
                    "processed_label": label_col[i],
                    "processed_frame_protocols": proto_text[i],
                    "processed_frame_len": float(frame_len_raw[i]),
                    "processed_ip_proto": float(ip_proto[i]),
                    "processed_src": src,
                    "processed_dst": dst,
                    "processed_src_port": float(src_port),
                    "processed_dst_port": float(dst_port),
                    "processed_tcp_flags": int(flags),
                }
            for w in WINDOWS:
                file_state[w].update(frame_len[i], is_tcp, is_udp, src, dst, dst_port_i)
                src_state[src][w].update(frame_len[i], is_tcp, is_udp, src, dst, dst_port_i)
        self._features[member] = features
        self._row_audits[member] = row_audits
        self.audit_rows.append(
            {
                "csv_member": member,
                "requested_rows": len(requested),
                "computed_new_rows": len(target),
                "out_of_bounds_rows": missing_oob,
                "processed_rows_read": len(df),
                "max_requested_row": max(requested),
                "seconds": time.time() - started,
                "label_column_read_for_audit_not_feature": "label" in df.columns,
            }
        )
        return {idx: features[idx] for idx in requested if idx in features}

    def row_audits_for_member(self, member: str, row_indices: np.ndarray) -> dict[int, dict[str, Any]]:
        requested = sorted({int(v) for v in np.asarray(row_indices, dtype=np.int64) if int(v) >= 0})
        if not requested:
            return {}
        self.features_for_member(member, np.asarray(requested, dtype=np.int64))
        known = self._row_audits.get(member, {})
        return {
            idx: known.get(
                idx,
                {
                    "processed_row_exists": False,
                    "processed_label": "",
                    "processed_frame_protocols": "",
                    "processed_frame_len": "",
                    "processed_ip_proto": "",
                    "processed_src": "",
                    "processed_dst": "",
                    "processed_src_port": "",
                    "processed_dst_port": "",
                    "processed_tcp_flags": "",
                },
            )
            for idx in requested
        }


class FeatureBuilder:
    def __init__(self, x_by_role: dict[str, np.ndarray], frame_by_role: dict[str, pd.DataFrame], cache: MechanismZipFeatureCache):
        self.x_by_role = x_by_role
        self.frame_by_role = frame_by_role
        self.cache = cache
        self.role_mechanism_cache: dict[str, np.ndarray] = {}

    def precompute_roles(self, roles: list[str]) -> None:
        need_by_member: dict[str, set[int]] = defaultdict(set)
        for role in roles:
            frame = self.frame_by_role[role].reset_index(drop=True)
            if len(frame) == 0:
                continue
            if "source_group" not in frame or "recorded_index" not in frame:
                raise RuntimeError(f"{role} frame lacks source_group/recorded_index for mechanism extraction")
            for member, group in frame.groupby(frame["source_group"].astype(str), sort=True):
                row_idx = pd.to_numeric(group["recorded_index"], errors="coerce").fillna(-1).astype(int).to_numpy()
                need_by_member[member].update(int(v) for v in row_idx if int(v) >= 0)
        for member, rows in sorted(need_by_member.items()):
            self.cache.features_for_member(member, np.asarray(sorted(rows), dtype=np.int64))

    def mechanism_for_role(self, role: str) -> np.ndarray:
        if role in self.role_mechanism_cache:
            return self.role_mechanism_cache[role]
        frame = self.frame_by_role[role].reset_index(drop=True)
        out = np.zeros((len(frame), len(MECHANISM_FEATURES)), dtype=np.float32)
        if len(frame) == 0:
            self.role_mechanism_cache[role] = out
            return out
        if "source_group" not in frame or "recorded_index" not in frame:
            raise RuntimeError(f"{role} frame lacks source_group/recorded_index for mechanism extraction")
        for member, group in frame.groupby(frame["source_group"].astype(str), sort=True):
            row_idx = pd.to_numeric(group["recorded_index"], errors="coerce").fillna(-1).astype(int).to_numpy()
            mapping = self.cache.features_for_member(member, row_idx)
            for pos, ridx in zip(group.index.to_numpy(dtype=np.int64), row_idx):
                feat = mapping.get(int(ridx))
                if feat is not None:
                    out[pos] = feat
        self.role_mechanism_cache[role] = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
        return self.role_mechanism_cache[role]

    def matrix(self, spec: FeatureSpec, role: str, idx: np.ndarray) -> np.ndarray:
        raw = np.asarray(self.x_by_role[role][idx], dtype=np.float32)
        if spec.kind == "raw":
            return raw
        mech = self.mechanism_for_role(role)[idx]
        if spec.kind == "mechanism":
            return mech
        if spec.kind == "raw_plus_mechanism":
            return np.hstack([raw, mech]).astype(np.float32)
        raise ValueError(spec.kind)


def build_alignment_audit(
    builder: FeatureBuilder,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    sample_per_role: int = ALIGNMENT_AUDIT_SAMPLE_PER_ROLE,
) -> list[dict[str, Any]]:
    """Sample row-level raw115-to-mechanism alignment evidence.

    This is report-only.  It proves the join path used by M2:
    role row -> sidecar source_group/recorded_index -> processed CSV row.
    It never feeds processed labels or audit fields back into fitting.
    """

    rows: list[dict[str, Any]] = []
    for role in sorted(frame_by_role):
        frame = frame_by_role[role].reset_index(drop=True)
        x_role = x_by_role.get(role)
        x_rows = int(len(x_role)) if x_role is not None else -1
        x_dim = int(x_role.shape[1]) if x_role is not None and getattr(x_role, "ndim", 0) == 2 else -1
        length_match = x_rows == len(frame)
        if len(frame) == 0:
            rows.append(
                {
                    "role": role,
                    "sampled": False,
                    "x_rows": x_rows,
                    "frame_rows": len(frame),
                    "x_dim": x_dim,
                    "x_frame_length_match": length_match,
                    "alignment_ok": length_match,
                }
            )
            continue
        positions = deterministic_cap(np.arange(len(frame), dtype=np.int64), sample_per_role)
        sample = frame.iloc[positions].copy()
        if "source_group" not in sample or "recorded_index" not in sample:
            rows.append(
                {
                    "role": role,
                    "sampled": False,
                    "x_rows": x_rows,
                    "frame_rows": len(frame),
                    "x_dim": x_dim,
                    "x_frame_length_match": length_match,
                    "alignment_ok": False,
                    "reason": "missing source_group or recorded_index",
                }
            )
            continue
        mech = builder.mechanism_for_role(role)
        for member, group in sample.groupby(sample["source_group"].astype(str), sort=True):
            row_idx = pd.to_numeric(group["recorded_index"], errors="coerce").fillna(-1).astype(int).to_numpy()
            audits = builder.cache.row_audits_for_member(member, row_idx)
            for pos, ridx in zip(group.index.to_numpy(dtype=np.int64), row_idx):
                record = frame.iloc[int(pos)]
                audit = audits.get(int(ridx), {})
                feat = mech[int(pos)] if 0 <= int(pos) < len(mech) else np.asarray([], dtype=np.float32)
                processed_exists = bool(audit.get("processed_row_exists", False))
                rows.append(
                    {
                        "role": role,
                        "sampled": True,
                        "row_index_in_role": int(pos),
                        "x_rows": x_rows,
                        "frame_rows": len(frame),
                        "x_dim": x_dim,
                        "x_frame_length_match": length_match,
                        "source_group": member,
                        "recorded_index": int(ridx),
                        "global_id": record.get("global_id", ""),
                        "phase": record.get("phase", ""),
                        "role_attack_label": record.get("attack_label", ""),
                        "device": record.get("device", ""),
                        "packet_timestamp_epoch": record.get("packet_timestamp_epoch", ""),
                        "processed_row_exists": processed_exists,
                        "processed_label": audit.get("processed_label", ""),
                        "processed_frame_protocols": audit.get("processed_frame_protocols", ""),
                        "processed_frame_len": audit.get("processed_frame_len", ""),
                        "processed_ip_proto": audit.get("processed_ip_proto", ""),
                        "processed_src": audit.get("processed_src", ""),
                        "processed_dst": audit.get("processed_dst", ""),
                        "processed_src_port": audit.get("processed_src_port", ""),
                        "processed_dst_port": audit.get("processed_dst_port", ""),
                        "processed_tcp_flags": audit.get("processed_tcp_flags", ""),
                        "mechanism_dim": int(len(feat)),
                        "mechanism_nonzero": int(np.count_nonzero(feat)) if len(feat) else 0,
                        "alignment_ok": bool(length_match and processed_exists and int(ridx) >= 0),
                    }
                )
    return rows


def load_role_inputs(smoke: bool) -> tuple[dict[str, np.ndarray], dict[str, pd.DataFrame], dict[str, Any], set[str]]:
    input_audit = ckc.validate_inputs()
    attack_root = Path(input_audit["attack_root"])
    cert_x = np.load(ckc.CERT_X, mmap_mode="r")
    schema = json.loads(ckc.FEATURE_SCHEMA.read_text(encoding="utf-8"))
    subspaces = ckc.bp.build_subspaces(schema)
    benign_idx, benign_records = ckc.load_benign_roles(smoke)
    benign_records["id_benign_calib"] = ckc.add_source_disjoint_phase(benign_records["id_benign_calib"])
    benign_records["ood_benign_val"] = ckc.add_source_disjoint_phase(benign_records["ood_benign_val"])
    hard_ood_x = np.asarray(cert_x[benign_idx["ood_benign_stress"]], dtype=np.float32)
    hard_ood_records = ckf.add_hard_ood_phase(benign_records["ood_benign_stress"])
    support_x, support_records, support_train_idx, support_val_idx = ckc.load_support(attack_root)
    support_labels = set(support_records.loc[support_train_idx, "attack_label"].astype(str))
    job = next(spec for spec in ckc.JOB_SPECS if spec.job_index == JOB_INDEX)
    stack = ckf.build_stack(
        job,
        cert_x,
        benign_idx,
        benign_records,
        support_x,
        support_records,
        support_train_idx,
        support_val_idx,
        subspaces,
        attack_root,
        hard_ood_records,
        hard_ood_x,
        smoke,
        False,
    )
    same_x, same_records = ckc.load_attack_role(attack_root, "same_file_time_forward_dev_query_exact", smoke)
    future_x, future_records = ckc.load_attack_role(attack_root, "dev_future_attack_query_exact", smoke)
    sealed_attack_x, sealed_attack_records = ckc.load_attack_role(
        attack_root,
        "sealed_final_attack_exact_realign",
        smoke,
    )
    sealed_ood_x = np.asarray(cert_x[benign_idx["sealed_final_ood"]], dtype=np.float32)
    frame_by_role = dict(stack["frames"])
    x_by_role = {
        "id_calib": np.asarray(cert_x[benign_idx["id_benign_calib"]], dtype=np.float32),
        "ood_val": np.asarray(cert_x[benign_idx["ood_benign_val"]], dtype=np.float32),
        "support_val": support_x[support_val_idx],
        "ood_stress": hard_ood_x,
        "same_file_query": same_x,
        "future_query": future_x,
        "sealed_final_ood": sealed_ood_x,
        "sealed_final_attack": sealed_attack_x,
        "support_train": support_x[support_train_idx],
    }
    for role, x_role, records in [
        ("same_file_query", same_x, ckg.add_source_or_time_phase(same_records)),
        ("future_query", future_x, ckg.add_source_or_time_phase(future_records)),
        ("sealed_final_attack", sealed_attack_x, sealed_attack_records.copy()),
        ("sealed_final_ood", sealed_ood_x, benign_records["sealed_final_ood"].copy()),
    ]:
        if role in {"sealed_final_attack", "sealed_final_ood"}:
            records = records.copy()
            records["phase"] = "report_only"
        frame_by_role[role] = ckf.build_role_frame_with_temporal(
            role,
            "attack" if "attack" in role else "benign_ood",
            x_role,
            records,
            stack,
            job,
        )
    support_train_records = support_records.iloc[support_train_idx].reset_index(drop=True).copy()
    support_train_records["phase"] = "fit"
    frame_by_role["support_train"] = ckf.build_role_frame_with_temporal(
        "support_train",
        "attack",
        x_by_role["support_train"],
        support_train_records,
        stack,
        job,
    )
    return x_by_role, frame_by_role, input_audit, support_labels


def fit_spec(
    spec: FeatureSpec,
    builder: FeatureBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
) -> tuple[Any, list[dict[str, Any]]]:
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    def add(role: str, phase: str, label: int, cap: int) -> None:
        idx = role_indices(frame_by_role, role, phase, cap)
        xs.append(builder.matrix(spec, role, idx))
        ys.append(np.full(len(idx), label, dtype=np.int64))
        audit.append({"feature_set": spec.name, "role": role, "phase": phase, "label": label, "rows": len(idx)})

    add("support_train", "fit", ckh.CLASS_ATTACK, FULL_CAP)
    add("id_calib", "fit", ckh.CLASS_ID, train_cap)
    add("ood_val", "fit", ckh.CLASS_OOD, train_cap)
    add("ood_stress", "fit", ckh.CLASS_HARD_OOD, train_cap)
    model = ckh.balanced_fit(ckh.build_model("histgb_shallow", multiclass=True), np.vstack(xs), np.concatenate(ys))
    return model, audit


def class_score(model: Any, x: np.ndarray, label: int) -> np.ndarray:
    return ckh.class_score(model, x, label)


def scores(model: Any, x: np.ndarray) -> dict[str, np.ndarray]:
    attack = class_score(model, x, ckh.CLASS_ATTACK)
    hard_ood = class_score(model, x, ckh.CLASS_HARD_OOD)
    ood = class_score(model, x, ckh.CLASS_OOD)
    identity = class_score(model, x, ckh.CLASS_ID)
    return {
        "attack_score": attack,
        "hard_ood_score": hard_ood,
        "conflict_score": np.maximum.reduce([identity, ood, hard_ood]),
    }


def threshold_for(
    spec: FeatureSpec,
    model: Any,
    builder: FeatureBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
) -> float:
    parts = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = role_indices(frame_by_role, role, "select", eval_cap)
        x = builder.matrix(spec, role, idx)
        parts.append(scores(model, x)["attack_score"])
    return float(max(np.quantile(part, BENIGN_SAFE_Q) for part in parts))


def eval_role(
    spec: FeatureSpec,
    model: Any,
    threshold: float,
    role: str,
    phase: str,
    role_kind: str,
    builder: FeatureBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    idx = role_indices(frame_by_role, role, phase, eval_cap)
    x = builder.matrix(spec, role, idx)
    score = scores(model, x)
    raw = score["attack_score"] > threshold
    conflict = raw & (score["conflict_score"] > score["attack_score"])
    hard = raw & (~conflict)
    part = frame_by_role[role].iloc[idx].copy().reset_index(drop=True)
    part["attack_score"] = score["attack_score"]
    part["hard_ood_score"] = score["hard_ood_score"]
    part["conflict_score"] = score["conflict_score"]
    part["raw_alarm"] = raw
    part["conflict_review"] = conflict
    part["hard_alarm"] = hard
    row = {
        "feature_set": spec.name,
        "role": role,
        "phase": phase,
        "role_kind": role_kind,
        "rows": len(part),
        "attack_threshold": threshold,
        "raw_alarm_rate": ckg.rate(raw),
        "conflict_review_rate": ckg.rate(conflict),
        "hard_alarm_rate": ckg.rate(hard),
        "attack_score_mean": float(np.mean(score["attack_score"])) if len(part) else float("nan"),
        "conflict_score_mean": float(np.mean(score["conflict_score"])) if len(part) else float("nan"),
    }
    return row, part


def group_rows(spec: FeatureSpec, role: str, part: pd.DataFrame) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if len(part) == 0:
        return out
    for cols in [["source_group"], ["device"], ["source_group", "device"]]:
        missing = [col for col in cols if col not in part]
        if missing:
            continue
        for key, group in part.groupby(cols, dropna=False, sort=True):
            if not isinstance(key, tuple):
                key = (key,)
            row = {
                "feature_set": spec.name,
                "role": role,
                "rows": len(group),
                "raw_alarm_rate": ckg.rate(group["raw_alarm"]),
                "conflict_review_rate": ckg.rate(group["conflict_review"]),
                "hard_alarm_rate": ckg.rate(group["hard_alarm"]),
            }
            for col, value in zip(cols, key):
                row[col] = value
            out.append(row)
    return out


def aggregate(role_rows: list[dict[str, Any]], group_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    df = pd.DataFrame(role_rows)
    gf = pd.DataFrame(group_metrics)
    for feature_set, group in df.groupby("feature_set", sort=True):
        def val(role: str, col: str, agg: str = "mean") -> float:
            vals = pd.to_numeric(group[group["role"] == role][col], errors="coerce")
            if vals.empty:
                return float("nan")
            return float(vals.min() if agg == "min" else vals.max() if agg == "max" else vals.mean())

        sealed_group = gf[(gf["feature_set"] == feature_set) & (gf["role"] == "sealed_final_ood")]
        out.append(
            {
                "feature_set": feature_set,
                "future_hard": val("future_query", "hard_alarm_rate"),
                "same_file_hard": val("same_file_query", "hard_alarm_rate"),
                "support_hard": val("support_val", "hard_alarm_rate"),
                "sealed_attack_hard": val("sealed_final_attack", "hard_alarm_rate"),
                "sealed_attack_review": val("sealed_final_attack", "conflict_review_rate"),
                "sealed_ood_hard": val("sealed_final_ood", "hard_alarm_rate"),
                "sealed_ood_review": val("sealed_final_ood", "conflict_review_rate"),
                "sealed_ood_group_hard_max": float(pd.to_numeric(sealed_group["hard_alarm_rate"], errors="coerce").max())
                if not sealed_group.empty
                else float("nan"),
                "ood_stress_hard": val("ood_stress", "hard_alarm_rate"),
                "ood_stress_review": val("ood_stress", "conflict_review_rate"),
            }
        )
    return out


def build_readout(matrix: list[dict[str, Any]], audit: list[dict[str, Any]], seconds: float, smoke: bool) -> list[str]:
    lines = [
        "# issue27cko mechanism frontend v1",
        "",
        "## Scope",
        "",
        "Fixed detector: C4 four-class HistGB.",
        "Changed input: raw115 vs processed-CSV mechanism features vs raw115+mechanism.",
        "Mechanism features use packet fields and past-only rolling source/file state; processed CSV label is audit-only and not a feature.",
        f"Mode: `{'smoke' if smoke else 'full'}`.",
        "",
        "## Main matrix",
        "",
        "| feature set | future hard | same-file hard | sealed attack hard/review | sealed OOD hard/review | sealed OOD group hard max | OOD-stress hard/review |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in matrix:
        lines.append(
            f"| {row['feature_set']} | {fmt(row['future_hard'])} | {fmt(row['same_file_hard'])} | "
            f"{fmt(row['sealed_attack_hard'])}/{fmt(row['sealed_attack_review'])} | "
            f"{fmt(row['sealed_ood_hard'])}/{fmt(row['sealed_ood_review'])} | "
            f"{fmt(row['sealed_ood_group_hard_max'])} | {fmt(row['ood_stress_hard'])}/{fmt(row['ood_stress_review'])} |"
        )
    lines.extend(
        [
            "",
            "## Mechanism extraction audit",
            "",
            "| files read | requested rows | computed rows | out-of-bounds rows | seconds |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    if audit:
        df = pd.DataFrame(audit)
        lines.append(
            f"| {len(df)} | {int(df['requested_rows'].sum())} | {int(df['computed_new_rows'].sum())} | "
            f"{int(df['out_of_bounds_rows'].sum())} | {fmt(df['seconds'].sum(), 1)} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- A useful mechanism frontend must reduce sealed OOD review/hard without hurting future/sealed attack hard detection.",
            "- Lower review alone is not success if it becomes hard OOD false alarm or loses attack retention.",
            "- This run does not use report-only rows for fitting, thresholding, or model selection.",
            "- Full flow/fanout extraction may need HPC because it reads many large processed CSV members from the 23GB Gotham zip.",
            "",
            f"Runtime seconds: `{fmt(seconds, 1)}`.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    x_by_role, frame_by_role, input_audit, _support_labels = load_role_inputs(args.smoke)
    train_cap = SMOKE_TRAIN_CAP if args.smoke else TRAIN_CAP
    eval_cap = SMOKE_EVAL_CAP if args.smoke else FULL_CAP
    cache = MechanismZipFeatureCache(GOTHAM_ZIP, smoke=args.smoke)
    builder = FeatureBuilder(x_by_role, frame_by_role, cache)
    specs = FEATURE_SPECS if not args.raw_only else FEATURE_SPECS[:1]
    if not args.raw_only:
        builder.precompute_roles(list(frame_by_role.keys()))

    train_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    group_metrics: list[dict[str, Any]] = []
    for spec in specs:
        model, audit = fit_spec(spec, builder, frame_by_role, train_cap)
        threshold = threshold_for(spec, model, builder, frame_by_role, eval_cap)
        for row in audit:
            train_rows.append(row)
        for role, phase, kind in ROLE_EVAL:
            row, part = eval_role(spec, model, threshold, role, phase, kind, builder, frame_by_role, eval_cap)
            role_rows.append(row)
            group_metrics.extend(group_rows(spec, role, part))

    matrix = aggregate(role_rows, group_metrics)
    alignment_rows = [] if args.raw_only else build_alignment_audit(builder, x_by_role, frame_by_role)
    seconds = time.time() - started
    write_csv(OUT / "candidate_matrix.csv", [spec.__dict__ for spec in FEATURE_SPECS])
    write_csv(OUT / "train_audit.csv", train_rows)
    write_csv(OUT / "role_metrics.csv", role_rows)
    write_csv(OUT / "group_metrics_by_source_device.csv", group_metrics)
    write_csv(OUT / "mechanism_extraction_audit.csv", cache.audit_rows)
    write_csv(OUT / "alignment_audit.csv", alignment_rows)
    write_csv(OUT / "candidate_summary_matrix.csv", matrix)
    write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "mechanism frontend v1; fixed C4 HistGB head",
            "smoke": args.smoke,
            "train_cap": train_cap,
            "eval_cap": eval_cap,
            "feature_specs": [spec.__dict__ for spec in FEATURE_SPECS],
            "mechanism_features": MECHANISM_FEATURES,
            "processed_usecols": PROCESSED_USECOLS,
            "gotham_zip": str(GOTHAM_ZIP),
            "input_audit": input_audit,
            "alignment_audit": {
                "sample_per_role": ALIGNMENT_AUDIT_SAMPLE_PER_ROLE,
                "rows": len(alignment_rows),
                "purpose": "report-only raw115-to-mechanism row pairing evidence",
            },
            "data_use_boundary": {
                "detector_fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "threshold_roles": ["id_calib select", "ood_val select", "ood_stress select"],
                "report_only_roles_used_for_training": False,
                "processed_label_used_as_feature": False,
                "alignment_audit_used_for_training": False,
                "mechanism_state": "past-only within processed source file and source endpoint",
            },
            "outputs": [
                "candidate_matrix.csv",
                "candidate_summary_matrix.csv",
                "train_audit.csv",
                "role_metrics.csv",
                "group_metrics_by_source_device.csv",
                "mechanism_extraction_audit.csv",
                "alignment_audit.csv",
                "codex_readout.md",
            ],
            "seconds": seconds,
        },
    )
    write_md(OUT / "codex_readout.md", build_readout(matrix, cache.audit_rows, seconds, args.smoke))
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds, "smoke": args.smoke}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--raw-only", action="store_true", help="debug only: skip zip mechanism extraction")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
