"""Select original packet positions independently of any detector scores."""
import csv
import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parent / "p4_gotham_password_source_readiness_20261120"
sys.path.insert(0, str(AUDIT))
from count_connections import ARCHIVE, TARGETS, BENIGN, SUPERVISED, audit_capture, collect_labels
from count_aux_normal import FIRST


def main():
    normal = json.loads((AUDIT / "AUX_NORMAL.json").read_bytes())
    primary = json.loads((AUDIT / "CENSUS.json").read_bytes())
    captures = {}
    for device, group in primary.items():
        captures[device] = [(group["attack"], SUPERVISED), (group["pure_benign"], BENIGN)]
    for device, group in normal.items():
        if group["pure_benign"]["matched"]["connections_off_guard_data"]:
            family, unit = device.rsplit("-", 1)
            prefix, first = FIRST[family]
            captures[device] = [(group["pure_benign"], BENIGN)]
            TARGETS[device] = (prefix + str(first + int(unit) - 1), "")
    from io import TextIOWrapper
    from socket import inet_ntoa
    anchors = []
    with ZipFile(ARCHIVE) as archive:
        for device, work in captures.items():
            ip, mac = TARGETS[device]
            if not mac:
                with archive.open(f"processed/{device}.csv") as stream:
                    macs = {row[f"eth.{side}"].lower()
                            for row in csv.DictReader(TextIOWrapper(stream, encoding="utf8"))
                            if row["label"] == "Benign" for side in ("src", "dst")
                            if row[f"ip.{side}"] == ip}
                if len(macs) != 1:
                    raise ValueError(f"ambiguous device identity: {device}")
                mac = macs.pop()
                TARGETS[device] = ip, mac
            labels, _ = collect_labels(archive, device, {})
            for spec, wanted in work:
                expected = spec["matched"]["connections_off_guard_data"]
                if not expected:
                    continue
                first = {}
                def observe(connection, frame, ns, flow):
                    if connection not in first or frame < first[connection][0]:
                        first[connection] = (frame, ns, flow)
                member = spec["member"]
                actual = audit_capture(archive, member, device, labels, wanted, observe=observe)
                if actual["matched"] != spec["matched"] or len(first) != expected:
                    raise ValueError(f"recount failed: {member}")
                for connection, (frame, ns, (peer, sport, dport)) in sorted(first.items()):
                    anchors.append([member, device, ip, mac, int(wanted == SUPERVISED),
                                    connection, frame, ns, inet_ntoa(peer.to_bytes(4, "big")), sport, dport])
                print(device, wanted.decode(), len(first), flush=True)
    positives = sum(r[4] for r in anchors)
    if positives != 1519 or len(anchors) - positives != 48:
        raise ValueError("Gotham population changed")
    path = HERE / "GOTHAM_CONNECTIONS.csv"
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(("member", "device", "target", "mac", "label", "connection", "frame",
                         "timestamp_ns", "source", "source_port", "target_port"))
        writer.writerows(anchors)
    tmp.replace(path)
    print("Verified original frames:", len(anchors), hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
