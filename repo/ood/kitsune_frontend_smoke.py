from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import urlretrieve

import dpkt

REPO_DIR = Path(__file__).resolve().parents[1]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from paths import ROOT_DIR


IOT23_PCAP_URL = (
    "https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset-v2/"
    "CTU-Honeypot-Capture-7-6/pcap/2019-07-07-16-41-19-192.168.1.158.pcap"
)


def mac_to_str(raw: bytes) -> str:
    return ":".join(f"{b:02x}" for b in raw)


def ipv4_to_str(raw: bytes) -> str:
    return ".".join(str(b) for b in raw)


def parse_packets(pcap_path: Path, limit: int):
    rows = []
    counts = {
        "total": 0,
        "ready": 0,
        "ipv4": 0,
        "ipv6": 0,
        "arp": 0,
        "tcp": 0,
        "udp": 0,
        "icmp": 0,
        "other_l2_l3": 0,
    }

    with pcap_path.open("rb") as f:
        reader = dpkt.pcap.Reader(f)
        for ts, buf in reader:
            if counts["total"] >= limit:
                break
            counts["total"] += 1
            framelen = len(buf)
            src_mac = ""
            dst_mac = ""
            src_ip = ""
            dst_ip = ""
            src_proto = ""
            dst_proto = ""
            ip_type = ""

            try:
                eth = dpkt.ethernet.Ethernet(buf)
                src_mac = mac_to_str(eth.src)
                dst_mac = mac_to_str(eth.dst)
                data = eth.data
                if isinstance(data, dpkt.ip.IP):
                    counts["ipv4"] += 1
                    ip_type = "0"
                    src_ip = ipv4_to_str(data.src)
                    dst_ip = ipv4_to_str(data.dst)
                    if isinstance(data.data, dpkt.tcp.TCP):
                        counts["tcp"] += 1
                        src_proto = str(data.data.sport)
                        dst_proto = str(data.data.dport)
                    elif isinstance(data.data, dpkt.udp.UDP):
                        counts["udp"] += 1
                        src_proto = str(data.data.sport)
                        dst_proto = str(data.data.dport)
                    elif isinstance(data.data, dpkt.icmp.ICMP):
                        counts["icmp"] += 1
                        src_proto = "icmp"
                        dst_proto = "icmp"
                elif isinstance(data, dpkt.ip6.IP6):
                    counts["ipv6"] += 1
                    ip_type = "1"
                    src_ip = str(data.src.hex())
                    dst_ip = str(data.dst.hex())
                    if isinstance(data.data, dpkt.tcp.TCP):
                        counts["tcp"] += 1
                        src_proto = str(data.data.sport)
                        dst_proto = str(data.data.dport)
                    elif isinstance(data.data, dpkt.udp.UDP):
                        counts["udp"] += 1
                        src_proto = str(data.data.sport)
                        dst_proto = str(data.data.dport)
                elif isinstance(data, dpkt.arp.ARP):
                    counts["arp"] += 1
                    ip_type = "0"
                    src_proto = "arp"
                    dst_proto = "arp"
                    src_ip = ipv4_to_str(data.spa)
                    dst_ip = ipv4_to_str(data.tpa)
                else:
                    counts["other_l2_l3"] += 1
                    # Same fallback principle as Kitsune FE: use MACs if no L3 signal.
                    src_ip = src_mac
                    dst_ip = dst_mac
            except Exception:
                counts["other_l2_l3"] += 1

            ready = all(
                [
                    str(ts) != "",
                    str(framelen) != "",
                    src_mac != "",
                    dst_mac != "",
                    src_ip != "",
                    dst_ip != "",
                ]
            )
            if ready:
                counts["ready"] += 1

            rows.append(
                {
                    "timestamp": float(ts),
                    "framelen": int(framelen),
                    "srcMAC": src_mac,
                    "dstMAC": dst_mac,
                    "srcIP": src_ip,
                    "srcProtocol": src_proto,
                    "dstIP": dst_ip,
                    "dstProtocol": dst_proto,
                    "IPtype": ip_type,
                    "ready_for_kitsune_updateGetStats": int(ready),
                }
            )
    return rows, counts


def write_md(path: Path, pcap_path: Path, rows, counts, limit: int) -> None:
    ready_ratio = 0.0 if counts["total"] == 0 else counts["ready"] / counts["total"]
    lines = []
    lines.append("# Kitsune Frontend Smoke Test")
    lines.append("")
    lines.append(f"- Date: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- Input pcap: `{pcap_path}`")
    lines.append(f"- Packet limit: {limit}")
    lines.append(f"- Packets parsed: {counts['total']}")
    lines.append(f"- Ready ratio (required fields present): {ready_ratio:.4f}")
    lines.append("")
    lines.append("## Packet type counts")
    for k in ["ipv4", "ipv6", "arp", "tcp", "udp", "icmp", "other_l2_l3"]:
        lines.append(f"- {k}: {counts[k]}")
    lines.append("")
    lines.append("## Required field set (aligned with Kitsune FeatureExtractor/netStat)")
    lines.append("- timestamp, framelen, srcMAC, dstMAC, srcIP, srcProtocol, dstIP, dstProtocol, IPtype")
    lines.append("")
    lines.append("## Assessment")
    if ready_ratio > 0.95:
        lines.append("- Smoke test passed: packet-level fields needed by Kitsune frontend are available on this dataset.")
    else:
        lines.append("- Smoke test partial: field completeness is insufficient; further parser adaptation is needed.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal smoke test for Kitsune-like packet frontend readiness.")
    parser.add_argument("--run-tag", default=f"kitsune_frontend_feasibility_{datetime.now().strftime('%Y-%m-%d')}")
    parser.add_argument("--pcap", type=Path, default=ROOT_DIR / "public_data" / "raw" / "iot23_7_6.pcap")
    parser.add_argument("--no-download", action="store_true", help="Do not auto-download pcap when missing.")
    parser.add_argument("--packet-limit", type=int, default=5000)
    args = parser.parse_args()

    run_dir = ROOT_DIR / "runs" / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)
    args.pcap.parent.mkdir(parents=True, exist_ok=True)

    if not args.pcap.exists() and not args.no_download:
        print(f"[download] {IOT23_PCAP_URL}")
        urlretrieve(IOT23_PCAP_URL, args.pcap)
        print(f"[saved] {args.pcap}")

    if not args.pcap.exists():
        raise FileNotFoundError(f"PCAP not found: {args.pcap}")

    rows, counts = parse_packets(args.pcap, args.packet_limit)
    csv_path = run_dir / "iot23_packet_fields_sample.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    json_path = run_dir / "smoke_report.json"
    json_path.write_text(
        json.dumps(
            {
                "input_pcap": str(args.pcap),
                "packet_limit": args.packet_limit,
                "counts": counts,
                "ready_ratio": 0.0 if counts["total"] == 0 else counts["ready"] / counts["total"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_md(run_dir / "smoke_report.md", args.pcap, rows, counts, args.packet_limit)
    print(f"[done] run dir: {run_dir}")


if __name__ == "__main__":
    main()
