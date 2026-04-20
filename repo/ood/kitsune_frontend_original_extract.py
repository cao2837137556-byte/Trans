from __future__ import annotations

import argparse
import csv
import json
import socket
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import urlretrieve

import dpkt
import numpy as np

REPO_DIR = Path(__file__).resolve().parents[1]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from paths import ROOT_DIR


FAMILY_ORDER = ["MI_dir", "HH", "HH_jit", "HpHp"]
SCALE_ORDER = ["5", "3", "1", "0.1", "0.01"]
STAT_SLOT_ORDER = ["weight", "mean", "std", "radius", "magnitude", "covariance", "pcc"]
EXPRESSION_V2_CHANNEL_ORDER = [
    "level_mean_slog",
    "level_rms_slog",
    "delta_short_mean_slog",
    "delta_mid_mean_slog",
    "delta_global_mean_slog",
]
EXPRESSION_V4A_HH_STABILIZED_NAME = "v4a_hh_stabilized"
FAMILY_PREFIXES = sorted(FAMILY_ORDER, key=len, reverse=True)


IOT23_PCAP_URL = (
    "https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset-v2/"
    "CTU-Honeypot-Capture-7-6/pcap/2019-07-07-16-41-19-192.168.1.158.pcap"
)

TSV_HEADER = [
    "frame.time_epoch",
    "frame.len",
    "eth.src",
    "eth.dst",
    "ip.src",
    "ip.dst",
    "tcp.srcport",
    "tcp.dstport",
    "udp.srcport",
    "udp.dstport",
    "icmp.type",
    "icmp.code",
    "arp.opcode",
    "arp.src.hw_mac",
    "arp.src.proto_ipv4",
    "arp.dst.hw_mac",
    "arp.dst.proto_ipv4",
    "ipv6.src",
    "ipv6.dst",
]

EXPRESSION_V3_CHANNEL_NAMES = [
    "mean_slog", "std_slog", "dispersion_slog", "number_log",
    "cov_sign", "pcc_slog", "burst_ratio", "dispersion_delta_slog",
]
EXPRESSION_V4A_HH_STABILIZED_CHANNEL_NAMES = list(EXPRESSION_V3_CHANNEL_NAMES)
EXPRESSION_V4A_HH_STABILIZED_MASK_FAMILIES = [1, 2]
EXPRESSION_V4A_HH_STABILIZED_MASK_CHANNELS = [0, 1, 3, 4]
EXPRESSION_V4B_HH_SOFT_STABILIZED_NAME = "v4b_hh_soft_stabilized"
EXPRESSION_V4B_HH_SOFT_STABILIZED_CHANNEL_NAMES = [
    "mean_rel_slog",
    "std_rel_slog",
    "dispersion_slog",
    "number_centered_log",
    "cov_relative_slog",
    "pcc_centered_slog",
    "short_long_mean_log_ratio",
    "short_long_dispersion_log_ratio",
]
EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_FAMILIES = [1, 2]
EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_CHANNELS = [0, 1, 3, 4, 5, 6, 7]
EXPRESSION_V4B_HH_SOFT_STABILIZED_CLIP_CONFIG = {
    "ch0": [-6.0, 6.0],
    "ch1": [-6.0, 6.0],
    "ch3": [-6.0, 6.0],
    "ch4": [-6.0, 6.0],
    "ch5": [-6.0, 6.0],
    "ch6": [-4.0, 4.0],
    "ch7": [-4.0, 4.0],
}


def mac_to_str(raw: bytes) -> str:
    return ":".join(f"{b:02x}" for b in raw)


def safe_ipv4(raw: bytes) -> str:
    if len(raw) != 4:
        return ""
    return socket.inet_ntoa(raw)


def safe_ipv6(raw: bytes) -> str:
    if len(raw) != 16:
        return ""
    return socket.inet_ntop(socket.AF_INET6, raw)


def parse_feature_header(header: str) -> dict:
    family = None
    for prefix in FAMILY_PREFIXES:
        if header.startswith(prefix + "_"):
            family = prefix
            break
    if family is None:
        raise ValueError(f"Unrecognized feature family in header: {header}")

    rest = header[len(family) + 1 :]
    scale = None
    for cand in SCALE_ORDER:
        if rest.startswith(cand + "_"):
            scale = cand
            break
    if scale is None:
        raise ValueError(f"Unrecognized scale in header: {header}")

    stat_raw = rest[len(scale) + 1 :]
    if stat_raw.startswith("weight"):
        stat = "weight"
    elif stat_raw.startswith("mean"):
        stat = "mean"
    elif stat_raw.startswith("std"):
        stat = "std"
    elif stat_raw.startswith("radius"):
        stat = "radius"
    elif stat_raw.startswith("magnitude"):
        stat = "magnitude"
    elif stat_raw.startswith("covariance"):
        stat = "covariance"
    elif stat_raw.startswith("pcc"):
        stat = "pcc"
    else:
        raise ValueError(f"Unrecognized stat slot in header: {header}")

    return {
        "header": header,
        "family": family,
        "scale": scale,
        "stat_slot": stat,
    }


def build_feature_schema(headers: list[str]) -> dict:
    if len(headers) != 100:
        raise ValueError(f"Expected 100 headers, got {len(headers)}")

    header_mappings = []
    token_index = {}
    token_defs = []
    for family_id, family in enumerate(FAMILY_ORDER):
        for scale_id, scale in enumerate(SCALE_ORDER):
            token_id = len(token_defs)
            token_index[(family, scale)] = token_id
            slot_mask = [1.0 if family in {"HH", "HpHp"} or slot in {"weight", "mean", "std"} else 0.0 for slot in STAT_SLOT_ORDER]
            token_defs.append(
                {
                    "token_id": token_id,
                    "token_name": f"{family}@{scale}",
                    "family": family,
                    "family_id": family_id,
                    "scale": scale,
                    "scale_id": scale_id,
                    "slot_mask": slot_mask,
                }
            )

    for flat_index, header in enumerate(headers):
        parsed = parse_feature_header(header)
        family = parsed["family"]
        scale = parsed["scale"]
        stat_slot = parsed["stat_slot"]
        header_mappings.append(
            {
                "flat_index": flat_index,
                "header": header,
                "family": family,
                "family_id": FAMILY_ORDER.index(family),
                "scale": scale,
                "scale_id": SCALE_ORDER.index(scale),
                "stat_slot": stat_slot,
                "stat_slot_id": STAT_SLOT_ORDER.index(stat_slot),
                "token_id": token_index[(family, scale)],
            }
        )

    schema = {
        "families": FAMILY_ORDER,
        "scales": SCALE_ORDER,
        "stat_slots": STAT_SLOT_ORDER,
        "expression_v2_channels": EXPRESSION_V2_CHANNEL_ORDER,
        "expression_versions": {
            "v3": {
                "name": "v3",
                "channel_names": EXPRESSION_V3_CHANNEL_NAMES,
            },
            EXPRESSION_V4A_HH_STABILIZED_NAME: {
                "name": EXPRESSION_V4A_HH_STABILIZED_NAME,
                "channel_names": EXPRESSION_V4A_HH_STABILIZED_CHANNEL_NAMES,
                "mask_families": EXPRESSION_V4A_HH_STABILIZED_MASK_FAMILIES,
                "mask_channels": EXPRESSION_V4A_HH_STABILIZED_MASK_CHANNELS,
            },
            EXPRESSION_V4B_HH_SOFT_STABILIZED_NAME: {
                "name": EXPRESSION_V4B_HH_SOFT_STABILIZED_NAME,
                "channel_names": EXPRESSION_V4B_HH_SOFT_STABILIZED_CHANNEL_NAMES,
                "soft_families": EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_FAMILIES,
                "soft_channels": EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_CHANNELS,
                "clip_config": EXPRESSION_V4B_HH_SOFT_STABILIZED_CLIP_CONFIG,
            },
        },
        "header_mappings": header_mappings,
        "token_definitions": token_defs,
        "family_major_token_order": [t["token_name"] for t in token_defs],
        "structured_shapes": {
            "family_scale_tokens": [len(FAMILY_ORDER), len(SCALE_ORDER), len(STAT_SLOT_ORDER)],
            "token_matrix": [len(token_defs), len(STAT_SLOT_ORDER)],
            "expression_v2_matrix": [len(token_defs), len(EXPRESSION_V2_CHANNEL_ORDER)],
            "expression_v2_flat": [len(token_defs) * len(EXPRESSION_V2_CHANNEL_ORDER)],
            "token_matrix_v3": [len(token_defs), len(EXPRESSION_V3_CHANNEL_NAMES)],
            "token_matrix_v4a_hh_stabilized": [len(token_defs), len(EXPRESSION_V4A_HH_STABILIZED_CHANNEL_NAMES)],
            "token_matrix_v4b_hh_soft_stabilized": [len(token_defs), len(EXPRESSION_V4B_HH_SOFT_STABILIZED_CHANNEL_NAMES)],
        },
    }
    return schema


def build_structured_feature_views(arr: np.ndarray, schema: dict) -> dict:
    if arr.ndim != 2 or arr.shape[1] != 100:
        raise ValueError(f"Expected feature matrix [N,100], got {arr.shape}")

    n = arr.shape[0]
    family_scale_tokens = np.zeros((n, len(FAMILY_ORDER), len(SCALE_ORDER), len(STAT_SLOT_ORDER)), dtype=np.float32)
    token_matrix = np.zeros((n, len(schema["token_definitions"]), len(STAT_SLOT_ORDER)), dtype=np.float32)
    token_slot_mask = np.zeros((len(schema["token_definitions"]), len(STAT_SLOT_ORDER)), dtype=np.float32)

    for token in schema["token_definitions"]:
        token_slot_mask[token["token_id"], :] = np.asarray(token["slot_mask"], dtype=np.float32)

    for item in schema["header_mappings"]:
        family_id = int(item["family_id"])
        scale_id = int(item["scale_id"])
        stat_slot_id = int(item["stat_slot_id"])
        token_id = int(item["token_id"])
        flat_index = int(item["flat_index"])
        values = arr[:, flat_index].astype(np.float32)
        family_scale_tokens[:, family_id, scale_id, stat_slot_id] = values
        token_matrix[:, token_id, stat_slot_id] = values

    token_family_id = np.asarray([int(t["family_id"]) for t in schema["token_definitions"]], dtype=np.int64)
    token_scale_id = np.asarray([int(t["scale_id"]) for t in schema["token_definitions"]], dtype=np.int64)
    flat_from_tokens = family_scale_tokens.reshape(n, -1)[:, : 4 * 5 * 7]
    # `flat_from_tokens` is only used for a strict mapping check and is not saved directly.
    return {
        "flat_features": arr.astype(np.float32),
        "family_scale_tokens": family_scale_tokens,
        "token_matrix": token_matrix,
        "token_slot_mask": token_slot_mask,
        "token_family_id": token_family_id,
        "token_scale_id": token_scale_id,
        "mapping_check_tensor": flat_from_tokens.astype(np.float32),
    }


def signed_log1p(x: np.ndarray) -> np.ndarray:
    return np.sign(x) * np.log1p(np.abs(x))


def masked_mean(x: np.ndarray, mask: np.ndarray) -> np.ndarray:
    denom = max(float(np.sum(mask)), 1.0)
    return (x * mask.reshape(1, -1)).sum(axis=1) / denom


def masked_rms(x: np.ndarray, mask: np.ndarray) -> np.ndarray:
    denom = max(float(np.sum(mask)), 1.0)
    return np.sqrt(np.clip((x * x * mask.reshape(1, -1)).sum(axis=1) / denom, a_min=1e-12, a_max=None))


def build_expression_v2_views(views: dict, schema: dict) -> dict:
    family_scale_tokens = views["family_scale_tokens"].astype(np.float32)
    token_family_id = views["token_family_id"].astype(np.int64)
    token_scale_id = views["token_scale_id"].astype(np.int64)
    token_slot_mask = views["token_slot_mask"].astype(np.float32)

    n = family_scale_tokens.shape[0]
    expression_v2_matrix = np.zeros(
        (n, len(schema["token_definitions"]), len(EXPRESSION_V2_CHANNEL_ORDER)),
        dtype=np.float32,
    )
    expression_v2_channel_mask = np.ones(
        (len(schema["token_definitions"]), len(EXPRESSION_V2_CHANNEL_ORDER)),
        dtype=np.float32,
    )

    slog = signed_log1p(family_scale_tokens)
    short_ref = 0.5 * (slog[:, :, 3, :] + slog[:, :, 4, :])
    mid_ref = slog[:, :, 2, :]
    long_ref = np.mean(slog[:, :, :3, :], axis=2)

    for token in schema["token_definitions"]:
        token_id = int(token["token_id"])
        family_id = int(token["family_id"])
        scale_id = int(token["scale_id"])
        slot_mask = token_slot_mask[token_id].astype(np.float32)
        current = slog[:, family_id, scale_id, :]

        expression_v2_matrix[:, token_id, 0] = masked_mean(current, slot_mask)
        expression_v2_matrix[:, token_id, 1] = masked_rms(current, slot_mask)
        expression_v2_matrix[:, token_id, 2] = masked_mean(current - short_ref[:, family_id, :], slot_mask)
        expression_v2_matrix[:, token_id, 3] = masked_mean(current - mid_ref[:, family_id, :], slot_mask)
        expression_v2_matrix[:, token_id, 4] = masked_mean(current - long_ref[:, family_id, :], slot_mask)

    return {
        "expression_v2_matrix": expression_v2_matrix,
        "expression_v2_flat": expression_v2_matrix.reshape(n, -1).astype(np.float32),
        "expression_v2_channel_mask": expression_v2_channel_mask,
        "expression_v2_family_id": token_family_id,
        "expression_v2_scale_id": token_scale_id,
        "expression_v2_channel_names": np.asarray(EXPRESSION_V2_CHANNEL_ORDER, dtype="<U32"),
    }


def compute_expression_v3(family_scale_tokens: np.ndarray) -> np.ndarray:
    """
    输入:  family_scale_tokens  np.ndarray [N, 4, 5, 7]  float32
    输出:  expression_v3_matrix np.ndarray [N, 20, 8]     float32
           （20 = 4 families × 5 scales，展开顺序 row-major）

    实际 slot 映射（STAT_SLOT_ORDER = ["weight","mean","std","radius","magnitude","covariance","pcc"]）：
        slot 0 = weight  （packet count，规格书称 "number"）
        slot 1 = mean
        slot 2 = std     （规格书称 "variance"，实际是 std；ch1 = slog(std)，ch2 = std/(|mean|+eps)）
        slot 5 = covariance
        slot 6 = pcc

    8 个通道定义：
        ch0: mean_slog          — slog(mean)
        ch1: std_slog           — slog(std)
        ch2: dispersion         — std / (|mean| + 1e-6)，变异系数 CV
        ch3: number_log         — log1p(clip(weight, 0))
        ch4: cov_sign           — slog(covariance)
        ch5: pcc                — 直接保留 pcc（已在 [-1,1]）
        ch6: burst_ratio        — slog(mean_0.01s) / (|slog(mean_5s)| + 1e-6)，
                                  按 family 计算，广播到该 family 全部 5 个 scale
        ch7: dispersion_delta   — dispersion(0.01s) - dispersion(5s)，
                                  按 family 计算，广播到该 family 全部 5 个 scale

    slog(x) = sign(x) * log1p(|x|)
    """
    EPS = 1e-6
    N = family_scale_tokens.shape[0]

    def slog(x: np.ndarray) -> np.ndarray:
        return np.sign(x) * np.log1p(np.abs(x))

    # slot 提取（使用实际 STAT_SLOT_ORDER 索引）
    num  = family_scale_tokens[:, :, :, 0].astype(np.float32)  # weight/count [N,4,5]
    mean = family_scale_tokens[:, :, :, 1].astype(np.float32)  # mean         [N,4,5]
    std  = family_scale_tokens[:, :, :, 2].astype(np.float32)  # std          [N,4,5]
    cov  = family_scale_tokens[:, :, :, 5].astype(np.float32)  # covariance   [N,4,5]
    pcc  = family_scale_tokens[:, :, :, 6].astype(np.float32)  # pcc          [N,4,5]

    # ch0~ch5：per-token（每个 family-scale 独立）
    ch0 = slog(mean)                                  # [N,4,5]
    ch1 = slog(std)                                   # [N,4,5]
    ch2 = slog(std / (np.abs(mean) + EPS))            # slog(dispersion)：CV 可达数百，需压缩
    ch3 = np.log1p(np.clip(num, 0.0, None))           # number_log
    ch4 = slog(cov)                                   # cov_sign
    ch5 = slog(pcc)                                   # slog(pcc)：Kitsune pcc 非 [-1,1]，需压缩

    # ch6：burst_ratio，per-family → broadcast [N,4] → [N,4,5]
    mean_long  = slog(mean[:, :, 0])  # scale=5s    [N,4]
    mean_short = slog(mean[:, :, 4])  # scale=0.01s [N,4]
    burst = mean_short / (np.abs(mean_long) + EPS)       # [N,4]
    ch6 = np.broadcast_to(burst[:, :, np.newaxis], (N, 4, 5)).copy()  # [N,4,5]

    # ch7：dispersion_delta_slog，per-family → broadcast [N,4] → [N,4,5]
    # 先分别 slog(CV)，再做差，避免原始 CV 数百级别的差值爆炸
    disp_long  = slog(std[:, :, 0] / (np.abs(mean[:, :, 0]) + EPS))  # [N,4]
    disp_short = slog(std[:, :, 4] / (np.abs(mean[:, :, 4]) + EPS))
    ddelta = disp_short - disp_long                                    # [N,4]
    ch7 = np.broadcast_to(ddelta[:, :, np.newaxis], (N, 4, 5)).copy()  # [N,4,5]

    # 拼接 [N,4,5,8]
    matrix_4d = np.stack([ch0, ch1, ch2, ch3, ch4, ch5, ch6, ch7], axis=-1)

    # 展开成 [N,20,8]（row-major: family 外层，scale 内层）
    expression_v3_matrix = matrix_4d.reshape(N, 20, 8).astype(np.float32)

    # 验证 non-finite
    n_bad = int((~np.isfinite(expression_v3_matrix)).sum())
    if n_bad > 0:
        print(f"[WARNING] expression_v3 non-finite count = {n_bad}，强制置 0")
        expression_v3_matrix = np.where(
            np.isfinite(expression_v3_matrix), expression_v3_matrix, 0.0
        ).astype(np.float32)

    return expression_v3_matrix


def compute_expression_v4a_hh_stabilized(family_scale_tokens: np.ndarray) -> np.ndarray:
    """
    Hard-masking ablation:
    - 先完整复用 compute_expression_v3(...)
    - 再仅对 HH / HH_jit（tokens 5-14）将 channels 0,1,3,4 置 0
    - MI_dir / HpHp 完全保持 v3 原值
    """
    v3_matrix = compute_expression_v3(family_scale_tokens)
    v4a_matrix = v3_matrix.copy()
    v4a_matrix[:, 5:15, EXPRESSION_V4A_HH_STABILIZED_MASK_CHANNELS] = 0.0
    return v4a_matrix.astype(np.float32, copy=False)


def compute_expression_v4b_hh_soft_stabilized(family_scale_tokens: np.ndarray) -> np.ndarray:
    """
    Soft stabilization for HH / HH_jit while preserving MI_dir / HpHp from v3.
    Input:  family_scale_tokens [N,4,5,7]
    Output: token_matrix_v4b_hh_soft_stabilized [N,20,8]
    """
    eps = 1e-6

    def slog(x: np.ndarray) -> np.ndarray:
        return np.sign(x) * np.log1p(np.abs(x))

    def sanitize_and_clip(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
        y = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        return np.clip(y, lo, hi).astype(np.float32, copy=False)

    v4b_matrix = compute_expression_v3(family_scale_tokens).astype(np.float32, copy=True)

    w_s = family_scale_tokens[:, :, :, 0].astype(np.float32)    # [N,4,5]
    m_s = family_scale_tokens[:, :, :, 1].astype(np.float32)    # [N,4,5]
    sd_s = family_scale_tokens[:, :, :, 2].astype(np.float32)   # [N,4,5]
    cov_s = family_scale_tokens[:, :, :, 5].astype(np.float32)  # [N,4,5]
    p_s = family_scale_tokens[:, :, :, 6].astype(np.float32)    # [N,4,5]
    cv_s = sd_s / (np.abs(m_s) + eps)                           # [N,4,5]

    for family_id in EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_FAMILIES:
        token_start = int(family_id * 5)
        token_end = token_start + 5

        w_f = w_s[:, family_id, :]      # [N,5]
        m_f = m_s[:, family_id, :]      # [N,5]
        sd_f = sd_s[:, family_id, :]    # [N,5]
        cov_f = cov_s[:, family_id, :]  # [N,5]
        p_f = p_s[:, family_id, :]      # [N,5]
        cv_f = cv_s[:, family_id, :]    # [N,5]

        mean_abs_ref = np.mean(np.abs(m_f), axis=1, keepdims=True)       # [N,1]
        std_ref = np.mean(sd_f, axis=1, keepdims=True)                    # [N,1]
        logw = np.log1p(np.clip(w_f, 0.0, None))                          # [N,5]
        logw_ref = np.mean(logw, axis=1, keepdims=True)                   # [N,1]
        pcc_slog = slog(p_f)                                               # [N,5]
        pcc_ref = np.mean(pcc_slog, axis=1, keepdims=True)                # [N,1]

        ch0 = sanitize_and_clip(slog(m_f / (mean_abs_ref + eps)), -6.0, 6.0)
        ch1 = sanitize_and_clip(slog(sd_f / (std_ref + eps)), -6.0, 6.0)
        ch3 = sanitize_and_clip(logw - logw_ref, -6.0, 6.0)
        ch4 = sanitize_and_clip(slog(cov_f / (sd_f * sd_f + eps)), -6.0, 6.0)
        ch5 = sanitize_and_clip(pcc_slog - pcc_ref, -6.0, 6.0)

        ch6_scalar = np.log((np.abs(m_f[:, 4]) + eps) / (np.abs(m_f[:, 0]) + eps))  # [N]
        ch6 = sanitize_and_clip(np.broadcast_to(ch6_scalar[:, np.newaxis], (len(ch6_scalar), 5)), -4.0, 4.0)

        ch7_scalar = np.log((cv_f[:, 4] + eps) / (cv_f[:, 0] + eps))  # [N]
        ch7 = sanitize_and_clip(np.broadcast_to(ch7_scalar[:, np.newaxis], (len(ch7_scalar), 5)), -4.0, 4.0)

        v4b_matrix[:, token_start:token_end, 0] = ch0
        v4b_matrix[:, token_start:token_end, 1] = ch1
        # channel 2 is intentionally kept from v3
        v4b_matrix[:, token_start:token_end, 3] = ch3
        v4b_matrix[:, token_start:token_end, 4] = ch4
        v4b_matrix[:, token_start:token_end, 5] = ch5
        v4b_matrix[:, token_start:token_end, 6] = ch6
        v4b_matrix[:, token_start:token_end, 7] = ch7

    return v4b_matrix.astype(np.float32, copy=False)


def compute_expression_channel_audit(matrix: np.ndarray, channel_names: list[str]) -> dict:
    if matrix.ndim != 3:
        raise ValueError(f"Expected [N,20,C], got {matrix.shape}")
    if matrix.shape[2] != len(channel_names):
        raise ValueError("Channel count mismatch for audit")

    channels = {}
    for cid, cname in enumerate(channel_names):
        ch = matrix[:, :, cid]
        finite_mask = np.isfinite(ch)
        finite_abs = np.abs(ch[finite_mask])
        max_abs = float(np.max(finite_abs)) if finite_abs.size else 0.0
        p99_abs = float(np.percentile(finite_abs, 99)) if finite_abs.size else 0.0
        channels[cname] = {
            "nan_count": int(np.isnan(ch).sum()),
            "inf_count": int(np.isinf(ch).sum()),
            "max_abs": max_abs,
            "p99_abs": p99_abs,
        }

    return {
        "shape": list(matrix.shape),
        "channels": channels,
    }


def validate_structured_views(arr: np.ndarray, schema: dict, views: dict) -> dict:
    recon = np.zeros_like(arr, dtype=np.float32)
    for item in schema["header_mappings"]:
        recon[:, int(item["flat_index"])] = views["token_matrix"][:, int(item["token_id"]), int(item["stat_slot_id"])]
    max_abs_diff = float(np.max(np.abs(recon - arr.astype(np.float32)))) if arr.size else 0.0
    expr = views.get("expression_v2_matrix")
    v3 = views.get("token_matrix_v3")
    v4a = views.get("token_matrix_v4a_hh_stabilized")
    v4b = views.get("token_matrix_v4b_hh_soft_stabilized")
    expr_nonfinite = 0
    expr_shape = None
    expr_flat_shape = None
    v3_nonfinite = 0
    v3_shape = None
    v4a_nonfinite = 0
    v4a_shape = None
    v4b_nonfinite = 0
    v4b_shape = None
    if expr is not None:
        expr_nonfinite = int(np.size(expr) - int(np.isfinite(expr).sum()))
        expr_shape = list(expr.shape)
        expr_flat_shape = list(views["expression_v2_flat"].shape)
    if v3 is not None:
        v3_nonfinite = int(np.size(v3) - int(np.isfinite(v3).sum()))
        v3_shape = list(v3.shape)
    if v4a is not None:
        v4a_nonfinite = int(np.size(v4a) - int(np.isfinite(v4a).sum()))
        v4a_shape = list(v4a.shape)
    if v4b is not None:
        v4b_nonfinite = int(np.size(v4b) - int(np.isfinite(v4b).sum()))
        v4b_shape = list(v4b.shape)
    return {
        "flat_reconstruction_max_abs_diff": max_abs_diff,
        "flat_reconstruction_exact": bool(max_abs_diff == 0.0),
        "structured_family_scale_shape": list(views["family_scale_tokens"].shape),
        "structured_token_matrix_shape": list(views["token_matrix"].shape),
        "expression_v2_shape": expr_shape,
        "expression_v2_flat_shape": expr_flat_shape,
        "expression_v2_nonfinite_count": expr_nonfinite,
        "token_matrix_v3_shape": v3_shape,
        "token_matrix_v3_nonfinite_count": v3_nonfinite,
        "token_matrix_v4a_hh_stabilized_shape": v4a_shape,
        "token_matrix_v4a_hh_stabilized_nonfinite_count": v4a_nonfinite,
        "token_matrix_v4b_hh_soft_stabilized_shape": v4b_shape,
        "token_matrix_v4b_hh_soft_stabilized_nonfinite_count": v4b_nonfinite,
    }


def save_structured_cache(run_dir: Path, base_stem: str, views: dict, schema: dict) -> dict:
    structured_npz_path = run_dir / f"{base_stem}_structured.npz"
    structured_schema_path = run_dir / f"{base_stem}_structured_schema.json"
    save_kwargs: dict = dict(
        flat_features=views["flat_features"],
        family_scale_tokens=views["family_scale_tokens"],
        token_matrix=views["token_matrix"],
        token_slot_mask=views["token_slot_mask"],
        token_family_id=views["token_family_id"],
        token_scale_id=views["token_scale_id"],
        expression_v2_matrix=views["expression_v2_matrix"],
        expression_v2_flat=views["expression_v2_flat"],
        expression_v2_channel_mask=views["expression_v2_channel_mask"],
        expression_v2_family_id=views["expression_v2_family_id"],
        expression_v2_scale_id=views["expression_v2_scale_id"],
        expression_v2_channel_names=views["expression_v2_channel_names"],
    )
    # expression_v3（追加，向后兼容）
    if "expression_v3_matrix" in views:
        save_kwargs["expression_v3_matrix"] = views["expression_v3_matrix"]
        save_kwargs["expression_v3_flat"] = views["expression_v3_flat"]
        save_kwargs["expression_v3_channel_names"] = views["expression_v3_channel_names"]
    if "token_matrix_v3" in views:
        save_kwargs["token_matrix_v3"] = views["token_matrix_v3"]
    if "token_matrix_v4a_hh_stabilized" in views:
        save_kwargs["token_matrix_v4a_hh_stabilized"] = views["token_matrix_v4a_hh_stabilized"]
        save_kwargs["expression_v4a_hh_stabilized_matrix"] = views["token_matrix_v4a_hh_stabilized"]
        save_kwargs["expression_v4a_hh_stabilized_flat"] = views["expression_v4a_hh_stabilized_flat"]
        save_kwargs["expression_v4a_hh_stabilized_channel_names"] = views["expression_v4a_hh_stabilized_channel_names"]
        save_kwargs["expression_v4a_hh_stabilized_mask_families"] = views["expression_v4a_hh_stabilized_mask_families"]
        save_kwargs["expression_v4a_hh_stabilized_mask_channels"] = views["expression_v4a_hh_stabilized_mask_channels"]
    if "token_matrix_v4b_hh_soft_stabilized" in views:
        save_kwargs["token_matrix_v4b_hh_soft_stabilized"] = views["token_matrix_v4b_hh_soft_stabilized"]
        save_kwargs["expression_v4b_hh_soft_stabilized_matrix"] = views["token_matrix_v4b_hh_soft_stabilized"]
        save_kwargs["expression_v4b_hh_soft_stabilized_flat"] = views["expression_v4b_hh_soft_stabilized_flat"]
        save_kwargs["expression_v4b_hh_soft_stabilized_channel_names"] = views["expression_v4b_hh_soft_stabilized_channel_names"]
        save_kwargs["expression_v4b_hh_soft_stabilized_soft_families"] = views["expression_v4b_hh_soft_stabilized_soft_families"]
        save_kwargs["expression_v4b_hh_soft_stabilized_soft_channels"] = views["expression_v4b_hh_soft_stabilized_soft_channels"]
    if "expression_versions" in views:
        save_kwargs["expression_versions"] = views["expression_versions"]
    np.savez_compressed(structured_npz_path, **save_kwargs)
    structured_schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "structured_npz_path": str(structured_npz_path),
        "structured_schema_path": str(structured_schema_path),
    }


def pcap_to_kitsune_tsv(pcap_path: Path, tsv_path: Path, packet_limit: int) -> dict:
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    counts = {
        "packet_limit": int(packet_limit),
        "packets_seen": 0,
        "rows_written": 0,
        "parse_errors": 0,
        "ipv4": 0,
        "ipv6": 0,
        "arp": 0,
        "tcp": 0,
        "udp": 0,
        "icmp": 0,
    }

    with pcap_path.open("rb") as fin, tsv_path.open("w", newline="", encoding="utf-8") as fout:
        reader = dpkt.pcap.Reader(fin)
        writer = csv.writer(fout, delimiter="\t")
        writer.writerow(TSV_HEADER)

        for ts, buf in reader:
            if counts["rows_written"] >= packet_limit:
                break
            counts["packets_seen"] += 1
            row = [""] * len(TSV_HEADER)
            row[0] = f"{float(ts):.6f}"
            row[1] = str(len(buf))

            try:
                eth = dpkt.ethernet.Ethernet(buf)
                row[2] = mac_to_str(eth.src)
                row[3] = mac_to_str(eth.dst)
                data = eth.data

                if isinstance(data, dpkt.ip.IP):
                    counts["ipv4"] += 1
                    row[4] = safe_ipv4(data.src)
                    row[5] = safe_ipv4(data.dst)
                    ip_payload = data.data
                    if isinstance(ip_payload, dpkt.tcp.TCP):
                        counts["tcp"] += 1
                        row[6] = str(ip_payload.sport)
                        row[7] = str(ip_payload.dport)
                    elif isinstance(ip_payload, dpkt.udp.UDP):
                        counts["udp"] += 1
                        row[8] = str(ip_payload.sport)
                        row[9] = str(ip_payload.dport)
                    elif isinstance(ip_payload, dpkt.icmp.ICMP):
                        counts["icmp"] += 1
                        row[10] = str(ip_payload.type)
                        row[11] = str(ip_payload.code)

                elif isinstance(data, dpkt.ip6.IP6):
                    counts["ipv6"] += 1
                    row[17] = safe_ipv6(data.src)
                    row[18] = safe_ipv6(data.dst)
                    ip_payload = data.data
                    if isinstance(ip_payload, dpkt.tcp.TCP):
                        counts["tcp"] += 1
                        row[6] = str(ip_payload.sport)
                        row[7] = str(ip_payload.dport)
                    elif isinstance(ip_payload, dpkt.udp.UDP):
                        counts["udp"] += 1
                        row[8] = str(ip_payload.sport)
                        row[9] = str(ip_payload.dport)

                elif isinstance(data, dpkt.arp.ARP):
                    counts["arp"] += 1
                    row[12] = str(data.op)
                    row[13] = mac_to_str(data.sha)
                    row[14] = safe_ipv4(data.spa)
                    row[15] = mac_to_str(data.tha)
                    row[16] = safe_ipv4(data.tpa)

            except Exception:
                counts["parse_errors"] += 1

            writer.writerow(row)
            counts["rows_written"] += 1
    return counts


def extract_features_from_tsv(tsv_path: Path, frontend_dir: Path, packet_limit: int) -> tuple[np.ndarray, list[str], dict]:
    if str(frontend_dir) not in sys.path:
        sys.path.insert(0, str(frontend_dir))

    from FeatureExtractor import FE  # noqa: PLC0415

    fe = FE(str(tsv_path), limit=packet_limit)
    headers = fe.nstat.getNetStatHeaders()

    vectors = []
    empty_vectors = 0
    eof_hits = 0

    while True:
        prev = fe.curPacketIndx
        vec = fe.get_next_vector()
        if len(vec) == 0:
            if fe.curPacketIndx == fe.limit and prev == fe.curPacketIndx:
                eof_hits += 1
                break
            empty_vectors += 1
            if fe.curPacketIndx >= fe.limit:
                eof_hits += 1
                break
            continue
        vectors.append(np.asarray(vec, dtype=np.float64))
        if len(vectors) % 5000 == 0:
            print(f"  feature extraction progress: {len(vectors)} vectors")

    if len(vectors) == 0:
        return np.empty((0, 0), dtype=np.float64), headers, {"empty_vectors": empty_vectors, "eof_hits": eof_hits}

    arr = np.vstack(vectors)
    counters = {"empty_vectors": empty_vectors, "eof_hits": eof_hits}
    return arr, headers, counters


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Run original Kitsune frontend extraction on a small IoT-23 sample.")
    parser.add_argument("--run-tag", default=f"kitsune_frontend_stage1_{today}")
    parser.add_argument("--pcap", type=Path, default=ROOT_DIR / "public_data" / "raw" / "iot23_7_6.pcap")
    parser.add_argument("--packet-limit", type=int, default=50000)
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument(
        "--emit-structured-cache",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Emit structured semantic cache alongside the original flat 100-D feature cache.",
    )
    args = parser.parse_args()

    run_dir = ROOT_DIR / "runs" / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)
    args.pcap.parent.mkdir(parents=True, exist_ok=True)

    frontend_dir = REPO_DIR / "kitsune_frontend_original"
    if not frontend_dir.exists():
        raise FileNotFoundError(f"Missing frontend dir: {frontend_dir}")

    if not args.pcap.exists():
        if args.no_download:
            raise FileNotFoundError(f"PCAP not found: {args.pcap}")
        print(f"[download] {IOT23_PCAP_URL}")
        urlretrieve(IOT23_PCAP_URL, args.pcap)
        print(f"[saved] {args.pcap}")

    input_suffix = args.pcap.suffix.lower()
    if input_suffix == ".tsv":
        tsv_path = args.pcap
        tsv_counts = {
            "packet_limit": int(args.packet_limit),
            "packets_seen": None,
            "rows_written": int(args.packet_limit),
            "parse_errors": 0,
            "ipv4": None,
            "ipv6": None,
            "arp": None,
            "tcp": None,
            "udp": None,
            "icmp": None,
            "source_mode": "existing_tsv",
        }
        print(f"[tsv] reuse existing TSV -> {tsv_path}")
    else:
        tsv_path = run_dir / f"{args.pcap.stem}_first{args.packet_limit}.tsv"
        tsv_counts = pcap_to_kitsune_tsv(args.pcap, tsv_path, args.packet_limit)
        tsv_counts["source_mode"] = "generated_from_pcap"
        print(f"[tsv] wrote {tsv_counts['rows_written']} rows -> {tsv_path}")

    features, headers, fx_counts = extract_features_from_tsv(tsv_path, frontend_dir, args.packet_limit)
    base_stem = f"{args.pcap.stem}_features_first{args.packet_limit}"
    feature_path = run_dir / f"{base_stem}.npy"
    np.save(feature_path, features)

    header_path = run_dir / "feature_headers.txt"
    header_path.write_text("\n".join(headers) + "\n", encoding="utf-8")

    structured_outputs = {}
    structured_validation = {}
    v4b_audit = None
    v4b_audit_path = None
    if args.emit_structured_cache and features.size:
        schema = build_feature_schema(headers)
        views = build_structured_feature_views(features, schema)
        views.update(build_expression_v2_views(views, schema))
        # expression views（最小侵入：保留旧 key，同时增加版本化 key）
        v3_matrix = compute_expression_v3(views["family_scale_tokens"])
        v4a_matrix = compute_expression_v4a_hh_stabilized(views["family_scale_tokens"])
        v4b_matrix = compute_expression_v4b_hh_soft_stabilized(views["family_scale_tokens"])
        views["v3"] = v3_matrix
        views[EXPRESSION_V4A_HH_STABILIZED_NAME] = v4a_matrix
        views[EXPRESSION_V4B_HH_SOFT_STABILIZED_NAME] = v4b_matrix
        views["token_matrix_v3"] = v3_matrix
        views["token_matrix_v4a_hh_stabilized"] = v4a_matrix
        views["token_matrix_v4b_hh_soft_stabilized"] = v4b_matrix
        views["expression_v3_matrix"] = v3_matrix
        views["expression_v3_flat"] = v3_matrix.reshape(len(v3_matrix), -1)  # [N,160]
        views["expression_v3_channel_names"] = np.asarray(EXPRESSION_V3_CHANNEL_NAMES, dtype="<U32")
        views["expression_v4a_hh_stabilized_flat"] = v4a_matrix.reshape(len(v4a_matrix), -1).astype(np.float32)
        views["expression_v4a_hh_stabilized_channel_names"] = np.asarray(
            EXPRESSION_V4A_HH_STABILIZED_CHANNEL_NAMES, dtype="<U32"
        )
        views["expression_v4a_hh_stabilized_mask_families"] = np.asarray(
            EXPRESSION_V4A_HH_STABILIZED_MASK_FAMILIES, dtype=np.int64
        )
        views["expression_v4a_hh_stabilized_mask_channels"] = np.asarray(
            EXPRESSION_V4A_HH_STABILIZED_MASK_CHANNELS, dtype=np.int64
        )
        views["expression_v4b_hh_soft_stabilized_flat"] = v4b_matrix.reshape(len(v4b_matrix), -1).astype(np.float32)
        views["expression_v4b_hh_soft_stabilized_channel_names"] = np.asarray(
            EXPRESSION_V4B_HH_SOFT_STABILIZED_CHANNEL_NAMES, dtype="<U48"
        )
        views["expression_v4b_hh_soft_stabilized_soft_families"] = np.asarray(
            EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_FAMILIES, dtype=np.int64
        )
        views["expression_v4b_hh_soft_stabilized_soft_channels"] = np.asarray(
            EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_CHANNELS, dtype=np.int64
        )
        views["expression_versions"] = np.asarray(
            ["v3", EXPRESSION_V4A_HH_STABILIZED_NAME, EXPRESSION_V4B_HH_SOFT_STABILIZED_NAME], dtype="<U32"
        )
        v4b_audit = {
            "all_tokens": compute_expression_channel_audit(v4b_matrix, EXPRESSION_V4B_HH_SOFT_STABILIZED_CHANNEL_NAMES),
            "hh_hh_jit_tokens": compute_expression_channel_audit(
                v4b_matrix[:, 5:15, :], EXPRESSION_V4B_HH_SOFT_STABILIZED_CHANNEL_NAMES
            ),
        }
        v4b_audit.update(
            {
                "expression_version": EXPRESSION_V4B_HH_SOFT_STABILIZED_NAME,
                "soft_families": list(EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_FAMILIES),
                "soft_channels": list(EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_CHANNELS),
                "clip_config": EXPRESSION_V4B_HH_SOFT_STABILIZED_CLIP_CONFIG,
            }
        )
        v4b_audit_path = run_dir / "expression_v4b_audit.json"
        v4b_audit_path.write_text(json.dumps(v4b_audit, indent=2, ensure_ascii=False), encoding="utf-8")
        structured_validation = validate_structured_views(features, schema, views)
        structured_outputs = save_structured_cache(run_dir, base_stem, views, schema)

    metadata = {
        "source_pcap": str(args.pcap),
        "packet_limit": int(args.packet_limit),
        "frontend_dir": str(frontend_dir),
        "tsv_path": str(tsv_path),
        "feature_path": str(feature_path),
        "tsv_counts": tsv_counts,
        "feature_counts": {
            "vectors_emitted": int(features.shape[0]),
            "output_dim": int(features.shape[1]) if features.size else 0,
            "empty_vectors": int(fx_counts["empty_vectors"]),
            "eof_hits": int(fx_counts["eof_hits"]),
        },
        "structured_cache_enabled": bool(args.emit_structured_cache),
        "structured_outputs": structured_outputs,
        "expression_v4b_audit_path": str(v4b_audit_path) if v4b_audit_path else None,
        "structured_validation": structured_validation,
        "structured_expression_versions": {
            "v3": {
                "channel_names": EXPRESSION_V3_CHANNEL_NAMES,
            },
            EXPRESSION_V4A_HH_STABILIZED_NAME: {
                "channel_names": EXPRESSION_V4A_HH_STABILIZED_CHANNEL_NAMES,
                "mask_families": EXPRESSION_V4A_HH_STABILIZED_MASK_FAMILIES,
                "mask_channels": EXPRESSION_V4A_HH_STABILIZED_MASK_CHANNELS,
            },
            EXPRESSION_V4B_HH_SOFT_STABILIZED_NAME: {
                "channel_names": EXPRESSION_V4B_HH_SOFT_STABILIZED_CHANNEL_NAMES,
                "soft_families": EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_FAMILIES,
                "soft_channels": EXPRESSION_V4B_HH_SOFT_STABILIZED_SOFT_CHANNELS,
                "clip_config": EXPRESSION_V4B_HH_SOFT_STABILIZED_CLIP_CONFIG,
            },
        },
    }
    (run_dir / "extract_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    summary = []
    summary.append("# Kitsune Frontend Stage1 Extraction")
    summary.append("")
    summary.append(f"- Date: {datetime.now().isoformat(timespec='seconds')}")
    summary.append(f"- Input pcap: `{args.pcap}`")
    summary.append(f"- Packet limit: {args.packet_limit}")
    summary.append(f"- TSV rows written: {tsv_counts['rows_written']}")
    summary.append(f"- Feature vectors emitted: {features.shape[0]}")
    summary.append(f"- Output feature dimension: {features.shape[1] if features.size else 0}")
    summary.append(f"- Empty vectors during extraction: {fx_counts['empty_vectors']}")
    summary.append("")
    summary.append("## Files")
    summary.append(f"- Feature cache: `{feature_path.name}`")
    summary.append(f"- Metadata: `extract_metadata.json`")
    summary.append(f"- Headers: `feature_headers.txt`")
    if structured_outputs:
        summary.append(f"- Structured cache: `{Path(structured_outputs['structured_npz_path']).name}`")
        summary.append(f"- Structured schema: `{Path(structured_outputs['structured_schema_path']).name}`")
        summary.append("")
        summary.append("## Structured Validation")
        summary.append(f"- Flat reconstruction max abs diff: {structured_validation['flat_reconstruction_max_abs_diff']:.8f}")
        summary.append(f"- family_scale_tokens shape: {structured_validation['structured_family_scale_shape']}")
        summary.append(f"- token_matrix shape: {structured_validation['structured_token_matrix_shape']}")
        summary.append(f"- expression_v2_matrix shape: {structured_validation['expression_v2_shape']}")
        summary.append(f"- expression_v2_flat shape: {structured_validation['expression_v2_flat_shape']}")
        summary.append(f"- expression_v2 non-finite count: {structured_validation['expression_v2_nonfinite_count']}")
        summary.append(f"- token_matrix_v3 shape: {structured_validation['token_matrix_v3_shape']}")
        summary.append(f"- token_matrix_v3 non-finite count: {structured_validation['token_matrix_v3_nonfinite_count']}")
        summary.append(
            f"- token_matrix_v4a_hh_stabilized shape: {structured_validation['token_matrix_v4a_hh_stabilized_shape']}"
        )
        summary.append(
            f"- token_matrix_v4b_hh_soft_stabilized shape: {structured_validation['token_matrix_v4b_hh_soft_stabilized_shape']}"
        )
        summary.append(
            f"- token_matrix_v4b_hh_soft_stabilized non-finite count: {structured_validation['token_matrix_v4b_hh_soft_stabilized_nonfinite_count']}"
        )
        summary.append(
            "- v4a hard mask: families=[1,2], channels=[0,1,3,4]"
        )
        summary.append(
            "- v4b soft stabilization: families=[1,2], channels=[0,1,3,4,5,6,7], ch2 kept from v3"
        )
        if v4b_audit_path:
            summary.append(f"- v4b audit: `{v4b_audit_path.name}`")
    (run_dir / "summary_extract.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    print(f"[done] run dir: {run_dir}")


if __name__ == "__main__":
    main()
