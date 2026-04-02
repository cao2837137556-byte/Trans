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

    tsv_path = run_dir / f"{args.pcap.stem}_first{args.packet_limit}.tsv"
    tsv_counts = pcap_to_kitsune_tsv(args.pcap, tsv_path, args.packet_limit)
    print(f"[tsv] wrote {tsv_counts['rows_written']} rows -> {tsv_path}")

    features, headers, fx_counts = extract_features_from_tsv(tsv_path, frontend_dir, args.packet_limit)
    feature_path = run_dir / f"{args.pcap.stem}_features_first{args.packet_limit}.npy"
    np.save(feature_path, features)

    header_path = run_dir / "feature_headers.txt"
    header_path.write_text("\n".join(headers) + "\n", encoding="utf-8")

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
    (run_dir / "summary_extract.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    print(f"[done] run dir: {run_dir}")


if __name__ == "__main__":
    main()
