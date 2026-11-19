"""Verify self-addressed host-name announcements without retaining content or queries."""

from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tempfile

from common_ton import HERE, POOLS, dump, read, require


def review(exe, paths, cfg):
    hosts = set(read(HERE / "LOCAL_CENSUS.json")["identity_evidence"])
    evidence = defaultdict(lambda: defaultdict(set))
    fields = (
        "ip.src",
        "nbns.flags.opcode",
        "nbns.flags.response",
        "nbns.nb_flags.group",
        "nbns.name",
        "nbns.addr",
        "dns.flags.response",
        "dns.resp.name",
        "dns.a",
    )
    for role in POOLS:
        match = "(" + " || ".join("ip.src==" + ip for ip in sorted(hosts)) + ") && (nbns || mdns || llmnr)"
        cmd = [
            str(exe),
            "-n",
            "-r",
            str(paths[role]),
            "-c",
            str(cfg["sources"][role]["complete_packets"]),
            "-Y",
            match,
            "-T",
            "fields",
            "-E",
            "separator=/t",
            "-E",
            "occurrence=a",
        ]
        for k in fields:
            cmd.extend(["-e", k])
        with tempfile.TemporaryFile() as err:
            with subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=err, text=True, encoding="utf-8", errors="replace"
            ) as child:
                for line in child.stdout:
                    parts = line.rstrip("\r\n").split("\t")
                    if len(parts) != len(fields) or parts[0] not in hosts:
                        continue
                    host, opcode, response, group, name, addr, dnsresp, dnsname, dnsip = parts
                    names = []
                    if (
                        opcode in ("5", "8", "15")
                        and response in ("0", "False")
                        and set(addr.split(",")) == {host}
                        and set(group.split(",")) == {"0"}
                    ):
                        base = {v.split("<")[0].strip().casefold() for v in name.split(",")}
                        if len(base) == 1:
                            names = [("nbns", base.pop())]
                    if dnsresp in ("1", "True") and dnsip == host and dnsname and "," not in dnsname:
                        names.append(("local-name", dnsname.rstrip(".").casefold()))
                    for kind, s in names:
                        if s and len(s) > 2:
                            evidence[host][role].add(kind + ":" + sha256(s.encode()).hexdigest())
                require(child.wait() == 0, "HOST_ANNOUNCEMENT_DECODER:" + role)
    out = {}
    for host in sorted(hosts):
        e = evidence[host]
        shared = e["normal1"] & e["normal2"] & e["password"]
        other = set().union(*(tokens for ip, m in evidence.items() if ip != host for tokens in m.values()))
        out[host] = dict(
            counts={p: len(e[p]) for p in POOLS},
            shared_unique=sorted(shared - other),
            shared_nonunique=sorted(shared & other),
        )
    return dict(
        scope="Source-bound unique-name registration or single IPv4 answer for the source itself. Only fingerprints exported.",
        hosts=out,
    )


if __name__ == "__main__":
    cfg = read(HERE / "SCOPED_INPUTS.json")
    files = {k: Path(v) for k, v in read(HERE / ".private/LOCAL_INPUTS.json").items()}
    result = review(Path(sys.argv[1]), files, cfg)
    dump(HERE / "RAW_HOST_EVIDENCE.json", result)
    print({k: (v["counts"], len(v["shared_unique"])) for k, v in result["hosts"].items()})
