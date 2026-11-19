"""Audit observed donor identities, separating compatible evidence, ports, and endpoint roles."""

from collections import defaultdict
from hashlib import sha256
from ipaddress import ip_address
import json
import struct

import numpy as np

from analysis_core import guard
from common_round1 import artifact, require, write_rows


def identity(row):
    key = row.get("canonical_key")
    if not (isinstance(key, (tuple, list)) and len(key) == 3 and key[0] == row["protocol"]):
        return None
    owner = row.get("owner")
    if (
        not owner
        or sha256(json.dumps([owner, key], separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        != row["component_id"]
    ):
        return None
    try:
        endpoints = tuple(sorted((str(ip_address(ip)), port) for ip, port in key[1:]))
    except (ValueError, TypeError):
        return None
    if endpoints[0][0] == endpoints[1][0] or any(
        type(p) is not int or not 0 <= p <= 65535 for _, p in endpoints
    ):
        return None
    return owner, row["protocol"], endpoints


def packet_role(row, packet, descriptor, canonical):
    if not packet or canonical is None:
        return None
    proto, _, src, dst, sp, dp, dm, sm = packet
    src, dst = str(ip_address(src)), str(ip_address(dst))
    observed = tuple(sorted(((src, sp), (dst, dp))))
    mac = row["owner"].replace(":", "").lower()
    require(canonical[2] == observed and proto == row["protocol"], "NORMAL_DONOR_PACKET_BINDING")
    if (sm == mac) == (dm == mac):
        return None
    local = src if sm == mac else dst
    initiator = None
    if proto == 6 and descriptor[2] == 1:
        initiator = dst if descriptor[5] == 1 else src
    return local, initiator


def normal_header_roles(store, refs, q14, targets, pins, identities):
    """Read only witnessed normal donor headers. Older rows without a usable binding stay unknown."""
    from vendor import history_context
    from vendor.source_packets import packets, decode

    role = {}
    evidence = {}
    by_raw = defaultdict(list)
    for i in sorted(targets):
        r = refs[i]
        by_raw[r.get("origin_raw_sha256", r["source_sha256"])].append(i)
    for spec in pins:
        selected = by_raw.get(spec["sha256"], [])
        if not selected:
            continue
        try:
            raw = store.get(spec["raw_key"])
            index_path = store.get(spec["index_key"]) if "index_key" in spec else None
        except FileNotFoundError:
            evidence[spec["raw_key"]] = dict(
                status="HEADER_UNAVAILABLE_OR_SHA_MISMATCH", requested=len(selected)
            )
            continue
        require(store.checked[spec["raw_key"]]["sha256"] == spec["sha256"], "NORMAL_HEADER_RAW_SHA")
        before = len(role)
        if index_path is None:
            wanted = defaultdict(list)
            for i in selected:
                wanted[refs[i]["frame"]].append(i)
            last = max(wanted)
            for fr, ns, p, _ in packets(raw):
                for i in wanted.get(fr, ()):
                    require(abs(refs[i]["timestamp"] - ns / 1e9) < 1e-6, "NORMAL_HEADER_FRAME_TIME")
                    v = packet_role(refs[i], p, q14[i], identities[i])
                    if v:
                        role[i] = v
                if fr == last:
                    break
        else:
            index = np.load(index_path, mmap_mode="r", allow_pickle=False)
            with raw.open("rb") as stream:
                kind, _, endian = history_context.block(stream)
                require(kind == 0x0A0D0D0A, "PCAPNG_SECTION")
                for i in selected:
                    r = refs[i]
                    pos = r.get("origin_packet_ordinal")
                    if (
                        type(pos) is not int
                        or not 1 <= pos <= len(index)
                        or r["frame"] > spec["bank_end_frame"]
                    ):
                        continue
                    item = index[pos - 1]
                    require(
                        int(item["original_packet_ordinal"]) == pos
                        and int(item["timestamp_us"]) == r["timestamp_us"],
                        "HIST_REF_PACKET_INDEX",
                    )
                    stream.seek(int(item["block_offset"]))
                    kind, data, _ = history_context.block(stream, endian)
                    iface, hi, lo, cap, wire = struct.unpack_from(endian + "IIIII", data, 8)
                    require(
                        kind == 6
                        and iface == int(item["interface_id"])
                        and cap == int(item["captured_bytes"])
                        and wire == int(item["wire_bytes"])
                        and (hi << 32 | lo) + spec["clock_offset"] * 10**6 == r["timestamp_us"],
                        "HIST_REF_BLOCK_IDENTITY",
                    )
                    p, _ = decode(data[28 : 28 + cap])
                    v = packet_role(r, p, q14[i], identities[i])
                    if v:
                        role[i] = v
        evidence[spec["raw_key"]] = dict(
            status="READ", requested=len(selected), role_bound=len(role) - before, sha256=spec["sha256"]
        )
    return role, evidence


def classify_pair(a, b, roles, ids):
    left, right = ids[a], ids[b]
    if left is None or right is None or left[:2] != right[:2]:
        return "UNKNOWN_IDENTITY", "NA", "NA"
    lx, rx = dict(left[2]), dict(right[2])
    if lx.keys() != rx.keys():
        return "DIFFERENT_IP_PAIR", "NA", "NA"
    diff = {ip for ip in lx if lx[ip] != rx[ip]}
    if not diff:
        return "UNKNOWN_IDENTITY", "NA", "NA"

    def which(j):
        v, w = roles.get(a, (None, None))[j], roles.get(b, (None, None))[j]
        if not v or v != w or v not in lx:
            return "UNKNOWN"
        return "BOTH" if len(diff) == 2 else "IDENTIFIED_END" if v in diff else "OTHER_END"

    return ("BOTH_PORTS" if len(diff) == 2 else "ONE_PORT"), which(0), which(1)


def run(pool, d, refs, q14, cache, arms, store, contract, *, header_lookup=True, detail_path=None):
    donors = cache["bank_rows"]
    compatible = arms["admitted"]
    changed = (arms["raw"] != arms["k2"]) | (arms["k2"] != arms["k1"]) | (arms["k2"] != arms["mean"])
    ranked = donors[:, 1] >= 0
    lookup = set(donors[ranked & changed.any(1)].ravel().tolist())
    ids = [identity(r) for r in refs]
    roles, proof = ({}, {})
    if header_lookup:
        roles, proof = normal_header_roles(store, refs, q14, lookup, contract["normal_headers"], ids)
    if pool == "EDGE":
        e = contract["edge_binding"]
        for i in set(donors[ranked].ravel()):
            c = ids[i]
            if c and refs[i]["owner"] == e["owner"] and e["ip"] in dict(c[2]):
                roles[i] = (e["ip"], None)
        proof["edge_published_endpoint"] = e
    n = len(d["rows"])
    pair_kind = np.full(n, "NO_RANKED_SECOND", dtype="U22")
    local = np.full(n, "NA", dtype="U15")
    initiator = local.copy()
    patterns = {}
    for i in np.flatnonzero(ranked):
        key = tuple(donors[i])
        if key not in patterns:
            patterns[key] = classify_pair(*key, roles, ids)
        pair_kind[i], local[i], initiator[i] = patterns[key]
    same_ranked = (pair_kind == "ONE_PORT") | (pair_kind == "BOTH_PORTS")
    same = compatible & same_ranked
    outside = ranked & ~compatible
    unknown = pair_kind == "UNKNOWN_IDENTITY"
    opened = cache["opening"] == ""
    masks = dict(
        no_second_ranked=~ranked,
        reference_not_open=~opened,
        open_geometry_unavailable=opened & ~cache["geometry_ready"],
        open_ready_too_few=opened & cache["geometry_ready"] & (cache["legal_components"] < 2),
        two_legal_outside=outside,
        ranked_two=ranked,
        ranked_identified=ranked & ~unknown,
        ranked_same_ips_ports_differ=same_ranked,
        outside_unknown=outside & unknown,
        outside_different_ips=outside & (pair_kind == "DIFFERENT_IP_PAIR"),
        outside_same_ips_ports_differ=outside & same_ranked,
        two_compatible=compatible,
        identity_unknown=compatible & unknown,
        different_ip_pair=compatible & (pair_kind == "DIFFERENT_IP_PAIR"),
        same_ips_ports_differ=same,
        one_endpoint_port_differs=compatible & (pair_kind == "ONE_PORT"),
        both_endpoint_ports_differ=compatible & (pair_kind == "BOTH_PORTS"),
        port_only_exactly_two_legal=same & (cache["legal_components"] == 2),
        port_only_more_than_two_legal=same & (cache["legal_components"] > 2),
    )
    for field, vec, labels in [
        ("local", local, ("target_only", "peer_only")),
        ("handshake", initiator, ("initiator_only", "responder_only")),
    ]:
        for code, suffix in zip(
            ("IDENTIFIED_END", "OTHER_END", "BOTH", "UNKNOWN"), (*labels, "both", "unknown")
        ):
            masks[field + "_" + suffix] = same & (vec == code)
    require(
        np.array_equal(compatible, (masks["identity_unknown"] | masks["different_ip_pair"] | same)),
        "PORT_DENOMINATOR",
    )
    from analysis_core import HEADS

    guards = guard(d["q"])
    roles_q = np.array([r.get("source_role", "") for r in d["rows"]])
    labels = np.array([r["label"] for r in d["rows"]])
    groups = {"NORMAL": labels == 0, "ATTACK": labels == 1}
    if pool == "EDGE":
        groups.update(HTTP=roles_q == "HTTP", UDP=roles_q == "UDP")
    device_proto = defaultdict(list)
    for i, r in enumerate(d["rows"]):
        device_proto[r["device"], r["protocol"], r["label"]].append(i)
    scopes = [
        ("ALL_QUERIES", np.ones((n, 1), bool)),
        ("RAW_TO_K2", arms["raw"] & ~arms["k2"]),
        ("K2_TO_K1", arms["k2"] & ~arms["k1"]),
        ("K2_TO_MEAN", arms["k2"] & ~arms["mean"]),
    ]
    for reason in ("new_positive_from_zero", "stronger_existing_dual"):
        scopes.append(
            ("K2_TO_K1_" + reason, (arms["k2"] & ~arms["k1"]) & (arms["pathway"] == reason)[:, None])
        )

    def count(ii, w):
        result = {k: int(np.count_nonzero(m[ii])) for k, m in masks.items()}
        den = result["two_compatible"] - result["identity_unknown"]
        result.update(
            rows=len(ii),
            identified_compatible_pairs=den,
            port_only_fraction_of_identified=(result["same_ips_ports_differ"] / den if den else None),
            weighted_denominator=float(w[ii].sum()),
            weighted_port_only=float(w[ii[same[ii]]].sum()),
        )
        if d["expansion"] is not None:
            result["ht_port_only_total"] = float(d["expansion"][ii[same[ii]]].sum())
        return result

    totals, details = [], []
    for view, (ix, w) in d["views"].items():
        selected = np.zeros(n, bool)
        selected[ix] = True
        for scope, pred in scopes:
            for j in range(pred.shape[1]):
                head = "ALL_HEADS" if pred.shape[1] == 1 else HEADS[j]
                keep = selected & pred[:, j]
                for group, g in groups.items():
                    for name, gm in (("ALL", True), ("GUARD_ON", guards), ("GUARD_OFF", ~guards)):
                        ii = np.flatnonzero(keep & g & gm)
                        totals.append(
                            dict(
                                pool=pool,
                                view=view,
                                scope=scope,
                                head=head,
                                group=group,
                                guard_stratum=name,
                                **count(ii, w),
                            )
                        )
                if scope != "ALL_QUERIES":
                    for (dev, proto, label), positions in device_proto.items():
                        ii = np.asarray(positions)
                        ii = ii[keep[ii]]
                        if len(ii):
                            details.append(
                                dict(
                                    pool=pool,
                                    view=view,
                                    scope=scope,
                                    head=head,
                                    device=dev,
                                    protocol=proto,
                                    label=label,
                                    **count(ii, w),
                                )
                            )
    result = dict(
        role_evidence=proof,
        ranked_donor_rows_requested=len(lookup),
        canonical_id_bound=sum(x is not None for x in ids),
        canonical_unknown=sum(x is None for x in ids),
        ref_rows=len(refs),
        ephemeral_allocation="unknown without operating-system allocation evidence",
    )
    if detail_path is not None:
        changed_rows = np.flatnonzero(changed.any(1))
        count = write_rows(
            detail_path,
            (
                dict(
                    query_uid=d["ids"][i],
                    row=int(i),
                    device=d["rows"][i]["device"],
                    label=d["rows"][i]["label"],
                    source_role=d["rows"][i].get("source_role"),
                    pathway=str(arms["pathway"][i]),
                    two_compatible=bool(compatible[i]),
                    legal_components=int(cache["legal_components"][i]),
                    donor_rows=donors[i].tolist(),
                    donor_uids=[refs[j]["uid"] if j >= 0 else None for j in donors[i]],
                    component_ids=[refs[j]["component_id"] if j >= 0 else None for j in donors[i]],
                    port_comparison=str(pair_kind[i]),
                    target_port_role=str(local[i]),
                    handshake_role=str(initiator[i]),
                    alarms={k: arms[k][i].tolist() for k in ("raw", "k2", "k1", "mean")},
                )
                for i in changed_rows
            ),
        )
        result["changed_donor_index"] = dict(path=str(detail_path), **artifact(detail_path, count))
    return totals, details, result
