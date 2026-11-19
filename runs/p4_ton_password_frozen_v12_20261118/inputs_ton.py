"""Resolve only the three registered captures and their existing label material."""

import csv
from decimal import Decimal

from common_ton import HERE, NS, dump, read, require, sha

DATA = "datasets/external/ton_iot_raw_network"
NAMES = dict(normal1="normal_1.pcap", normal2="normal_2.pcap", password="password_normal1.pcap")
PASSWORD_LOG = "Network_dataset_Bro/normal_attack_Bro/normal_password/password_normal_1/conn.log"
PASSWORD_GT = "SecurityEvents_Network_datasets/GroundTruth_Network_14.csv"


def build_sources():
    runs = HERE.parent
    root = runs.parent
    datasets = root.parents[1] / DATA
    prior = runs / "p4_ton_nonflood_candidate_count_v1_20261118"
    census = read(prior / "NAMED_CENSUS.json")
    sample = read(prior / "FROZEN_CANDIDATE_COUNTS.json")
    name = NAMES["password"]
    expected = census["results"][name]["named_target_ip_protocol_in_both_normal_files"]
    require(
        (expected["frames"], expected["off_guard"], expected["off_guard_with_transport_data"])
        == (326961, 246398, 62087),
        "ORIGINAL_CENSUS",
    )
    verified = read(
        runs / "mainline_docs/collab/20261118_paper04_nonflood_source_augmentation_local_checks_codex.json"
    )["ton"]
    values = {}
    local = {}

    def item(key, path, tail, pin):
        require(path.is_file() and sha(path) == pin, "SOURCE_SHA:" + key)
        local[key] = str(path)
        values[key] = dict(
            file=path.name,
            bytes=path.stat().st_size,
            sha256=pin,
            paths=[
                f"{DATA}/{tail}",
                f"worktrees/kitnet-exp-mainline/{DATA}/{tail}",
                f"{DATA.split('/', 1)[1]}/{tail}",
            ],
        )

    for role, n in NAMES.items():
        tail = "raw_pcap_pilot_v1/" + n
        item(role, datasets / tail, tail, census["inputs"][n])
        x = verified["eligible_files_capinfos"][n]
        values[role].update(
            container="pcap" if role == "password" else "pcapng",
            complete_packets=x["complete_packets"],
            min_ns=int(Decimal(x["min_epoch"]) * NS),
            max_ns=int(Decimal(x["max_epoch"]) * NS),
            tail=verified["password_last_record"] if role == "password" else None,
        )
    for key, rel in [("zeek", PASSWORD_LOG), ("events", PASSWORD_GT)]:
        item(key, datasets / "extracted" / rel, "extracted/" + rel, census["label_inputs"][rel])
    # These two logs describe the two normal files; admit them as corroboration for the split.
    for key, folder in [("normal1log", "normal_1"), ("normal2log", "normal_2")]:
        rel = "extracted/Network_dataset_Bro/normal_Bro/" + folder + "/conn.log"
        p = datasets / rel
        item(key, p, rel, sha(p))
    frozen = (
        runs
        / "issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22"
        / "aux_process_support_candidate_manifest.csv"
    )
    require(sha(frozen) == census["selected_manifest_sha256"], "EXISTING_SAMPLED_CONNECTIONS_SHA")
    with frozen.open(encoding="utf-8-sig", newline="") as f:
        sampled = [
            dict(line=int(r["conn_line_index"]), key_sha256=r["key_sha256"])
            for r in csv.DictReader(f)
            if r["role"] == "aux_process_fit" and r["pair_id"] == "password_fit_capture_1"
        ]
    require(len(sampled) == len({r["line"] for r in sampled}) == 2000, "ORIGINAL_SAMPLE_SCOPE")
    cfg = dict(
        run=HERE.name,
        sources=values,
        registered_hosts=[f"192.168.1.{n}" for n in (152, 184, 190, 192, 193, 194, 195)],
        registered_origins=[f"192.168.1.{n}" for n in range(30, 40)],
        source_rule=census["topology"],
        census_sha256=sha(prior / "NAMED_CENSUS.json"),
        candidate_counts=expected,
        matching_normal_inbound=census["results"][name]["normal_frames_for_paired_target_protocols"],
        original_sample=sample["results"][name]["named_target_ip_protocol_in_both_normal_files"],
        sample_manifest_sha256=census["selected_manifest_sha256"],
    )
    dump(HERE / "SCOPED_INPUTS.json", cfg)
    dump(HERE / "PASSWORD_SAMPLE.json", sampled)
    dump(HERE / ".private/LOCAL_INPUTS.json", local)
    return cfg


if __name__ == "__main__":
    cfg = build_sources()
    print([(k, v["bytes"]) for k, v in cfg["sources"].items()])
