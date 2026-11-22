"""Bind the previous coverage-only false-positive cohort to original connections."""
from collections import Counter, defaultdict
from hashlib import sha256

import numpy as np

from history_common import artifact, save, uid_sha, write
from roles import NAMES


def partition(a, before, after):
    normal = (a["kind"] == "normal") & a["active"]
    assert normal.sum() == 74444
    assert np.all(before <= after)
    origin = set(a["group"][normal & before])
    all_normal = set(a["group"][normal])
    new = np.flatnonzero(normal & ~before & after)
    new_conn = set(a["group"][new]) - origin
    assert len(new) == 6550 and len(set(a["uid"][new])) == 6550 and len(new_conn) == 26
    assert len(all_normal) == 18177 and len(origin) == 62
    return new, origin, new_conn


def audit(out, data, parent, qr):
    a = data["a"]
    before = parent["v12"][:, 3]
    after = parent["COVER_R2_U1"][:, 3]
    assert np.all(after <= parent["RAW"][:, 3])
    new, old_conn, gained_conn = partition(a, before, after)
    cohorts = defaultdict(Counter)
    conns = defaultdict(Counter)
    status_count = Counter()
    status_groups = defaultdict(set)
    claims = []
    for i in new:
        row = data["rows"][i]
        group = str(a["group"][i])
        assert group == "|".join(map(str, (row["capture_id"], row["device"], row["protocol"], row["stream_id"])))
        cap = str(row["capture_id"])
        device = str(row["device"])
        proto = int(row["protocol"])
        role = NAMES[qr[i, 0]]
        port = int(qr[i, 1])
        status = "previously_alerted" if group in old_conn else "previously_quiet"
        key = (status, device, proto, role, port)
        cohorts[key][group] += 1
        conns[group][key] += 1
        status_count[status] += 1
        status_groups[status].add(group)
        claims.append((str(a["uid"][i]), group, cap, device, int(a["frame"][i]), role, port, status))
    assert sum(status_count.values()) == 6550 and status_groups["previously_quiet"] == gained_conn
    def columns(k):
        status, device, proto, role, port = k
        return dict(original_connection=status, device=device, ip_protocol=proto,
                    role=role, service_port=(port if port >= 0 else "not_identified"))
    summary = []
    for key, groups in sorted(cohorts.items()):
        summary.append(dict(**columns(key), queries=sum(groups.values()), affected_connections=len(groups)))
    details = []
    for group, roles in sorted(conns.items()):
        capture, _, _, stream = group.rsplit("|", 3)
        for key, count in sorted(roles.items()):
            details.append(dict(capture=capture, stream=stream,
                           connection_sha256=sha256(group.encode()).hexdigest(), **columns(key), queries=count))
    assert sum(v["queries"] for v in summary) == sum(v["queries"] for v in details) == 6550
    q = out / "UNSW_ATTRIBUTION_BY_DEVICE_ROLE_PORT.csv"
    c = out / "UNSW_ATTRIBUTION_BY_CONNECTION.csv"
    save(q, summary)
    save(c, details)
    ledger = out / "UNSW_ATTRIBUTED_UID.npz"
    np.savez(ledger, uid=[x[0] for x in claims], original_connection=[x[1] for x in claims],
             capture=[x[2] for x in claims], device=[x[3] for x in claims], indexed_frame=[x[4] for x in claims],
             role=[x[5] for x in claims], service_port=[x[6] for x in claims], status=[x[7] for x in claims])
    note = out / "UNSW_ATTRIBUTION.json"
    write(note, dict(scope="UNSW post-enrollment normal ensemble v12 to COVER_R2_U1",
                    normal_queries=74444, normal_connections=18177, original_alarm_connections=62,
                    added_queries=6550, new_alarm_connections=26,
                    queries_by_original_connection={k:status_count[k] for k in ("previously_alerted","previously_quiet")},
                    affected_connections={k:len(status_groups[k]) for k in ("previously_alerted","previously_quiet")},
                    uid_in_frozen_order_sha256=uid_sha(x[0] for x in claims), sha=artifact(ledger),
                    tables={p.name:artifact(p) for p in (q, c)}))
    return {p.name:artifact(p) for p in (q, c, note)}
