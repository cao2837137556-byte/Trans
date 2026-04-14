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
        "header_mappings": header_mappings,
        "token_definitions": token_defs,
        "family_major_token_order": [t["token_name"] for t in token_defs],
        "structured_shapes": {
            "family_scale_tokens": [len(FAMILY_ORDER), len(SCALE_ORDER), len(STAT_SLOT_ORDER)],
            "token_matrix": [len(token_defs), len(STAT_SLOT_ORDER)],
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


def validate_structured_views(arr: np.ndarray, schema: dict, views: dict) -> dict:
    recon = np.zeros_like(arr, dtype=np.float32)
    for item in schema["header_mappings"]:
        recon[:, int(item["flat_index"])] = views["token_matrix"][:, int(item["token_id"]), int(item["stat_slot_id"])]
    max_abs_diff = float(np.max(np.abs(recon - arr.astype(np.float32)))) if arr.size else 0.0
    return {
        "flat_reconstruction_max_abs_diff": max_abs_diff,
        "flat_reconstruction_exact": bool(max_abs_diff == 0.0),
        "structured_family_scale_shape": list(views["family_scale_tokens"].shape),
        "structured_token_matrix_shape": list(views["token_matrix"].shape),
    }


def save_structured_cache(run_dir: Path, base_stem: str, views: dict, schema: dict) -> dict:
    structured_npz_path = run_dir / f"{base_stem}_structured.npz"
    structured_schema_path = run_dir / f"{base_stem}_structured_schema.json"
    np.savez_compressed(
        structured_npz_path,
        flat_features=views["flat_features"],
        family_scale_tokens=views["family_scale_tokens"],
        token_matrix=views["token_matrix"],
        token_slot_mask=views["token_slot_mask"],
        token_family_id=views["token_family_id"],
        token_scale_id=views["token_scale_id"],
    )
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
    if args.emit_structured_cache and features.size:
        schema = build_feature_schema(headers)
        views = build_structured_feature_views(features, schema)
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
        "structured_validation": structured_validation,
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
    (run_dir / "summary_extract.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    print(f"[done] run dir: {run_dir}")


if __name__ == "__main__":
    main()
