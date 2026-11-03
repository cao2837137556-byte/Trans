"""N2 immutable identities, selective development metadata and bounded I/O."""
from __future__ import annotations

import csv
import gzip
import io
import json
import re
from collections import Counter
from pathlib import Path

import issue27frontend_inheritance_n1_support_v1 as base
from issue27frontend_inheritance_n1_support_v1 import (
    ROOT, F4, F5, F3, N0, FEATURES, CHECKPOINT, CORE, CATEGORIES, PROTECTED,
    INDEX_COLUMNS, TARGET_COLUMNS, SCOPE_COLUMNS, SELECTORS, PAYLOAD,
    Stop, require, digest, json_bytes, sha_file, integer, relative_name,
    manifest, peak_memory, Writer, Inputs)

DESIGN = "runs/mainline_docs/frontend_inheritance_n2_fixed_witness_development_check_frozen_20260908.md"
PINS_FILE = "runs/mainline_docs/frontend_inheritance_n2_input_and_evidence_pins_20260908.json"
DESIGN_SHA = "06b530f43a5bde8f10fbdbcfc438ab3d577a039a1792b764efe46658f0309388"
PINS_SHA = "bb7491f87d5228b31357714eca84d6cfd1a7f46fa469cfd410726c8bab34e3de"
IMPLEMENTATION = "runs/frontend_inheritance_n2_implementation_v1_20260908"
REAL_OUTPUT = "runs/frontend_inheritance_n2_fixed_witness_development_v1_20260908"
N1_OUTPUT = "runs/frontend_inheritance_n1_fixed_terminal_head_v1_20260908"
N1_ACCEPTANCE = "runs/frontend_inheritance_n1_implementation_v2_20260908/synthetic_acceptance.json"
HEAD = N1_OUTPUT + "/candidate_head.f32le"
AUTHORIZATION = "I_AUTHORIZE_ONE_REAL_N2_DEV_CHECK_AND_FINAL_REFERENCE_CONTAINER_ACCESS"
CODE = tuple("repo/ood/issue27frontend_inheritance_n2_" + name + "_v1.py"
             for name in ("support", "runner", "control", "tests", "verify")) + (
    "scripts/start_frontend_inheritance_n2_local.ps1",
    "scripts/show_frontend_inheritance_n2_status.ps1",
    "repo/ood/issue27frontend_inheritance_n1_support_v1.py")
CAPS = {"wall_seconds": 1800, "memory_bytes": 8 * 1024**3,
        "output_bytes": 100 * 1024**2, "reserve_bytes": 1024**2,
        "loads": 1, "head_decodes": 1, "assemblies": 1, "passes": 1,
        "batches": 136, "targets": 5206, "contexts": 4323, "events": 205470,
        "decoded_events": 205470, "padded_slots": 1106688,
        **{k: 0 for k in ("lp_calls", "optimizer_steps", "backward_steps",
                         "teacher_forwards", "train_events", "train_targets",
                         "threshold_fits", "retries", "pilots", "hpc_jobs")}}
EXPECTED = {"A1C": 3, "A0C": 1478, "B1N": 3, "A0W": 2, "B0N": 3720}
SOURCES = {"iotsim-combined-cycle-6_0-0_to_OpenvSwitch-13_6-0": (600, 464),
           "iotsim-domotic-monitor-3_0-0_to_OpenvSwitch-23_3-0": (600, 189),
           "normal_1.pcap": (4000, 3667),
           "processed/iotsim-combined-cycle-10.csv": (6, 3)}
B_KEYS = {"iotsim-combined-cycle": (333, 282, 34, 29),
          "iotsim-domotic-monitor": (230, 50, 23, 5),
          "ton-iot-external": (3157, 2995, 316, 300)}
SCIENTIFIC = ("N2_DEV_ATTACK_GATE_FAILURE", "N2_DEV_PROTECTED_BENIGN_FAILURE",
              "N2_DEV_B_UTILITY_INSUFFICIENT", "N2_EXPOSED_DEV_GATES_PASS")
STATUSES = set(SCIENTIFIC) | {"N2_ENGINEERING_STOP", "N2_NEEDS_GOVERNED_MODEL_EXPORT"}


class Budget(base.Budget):
    def __init__(self, **kwargs):
        kwargs.setdefault("caps", CAPS)
        super().__init__(**kwargs)


def frozen_design(root=ROOT):
    for name, expected in ((DESIGN, DESIGN_SHA), (PINS_FILE, PINS_SHA)):
        path = root / name
        require(sha_file(path) == expected, "FROZEN_DESIGN_DRIFT")
        require(manifest(path.with_suffix(".sha256").read_bytes()) == {path.name: expected},
                "DESIGN_SIDECAR_DRIFT")
    n2 = json.loads((root / PINS_FILE).read_text(encoding="utf-8"))
    inherited = n2["inherited_bundle"]
    path = root / inherited["path"]
    require(sha_file(path) == inherited["sha256"] == base.PINS_SHA, "INHERITED_PIN_DRIFT")
    require(manifest((root / inherited["sidecar"]).read_bytes()) == {path.name: base.PINS_SHA},
            "INHERITED_SIDECAR_DRIFT")
    pins = json.loads(path.read_text(encoding="utf-8"))
    require(len(pins["repository_inputs"]) == 17 and len(pins["runtime_file_sha256"]) == 7,
            "INHERITED_PIN_COUNTS")
    require(len(n2["additional_repository_inputs"]) == 18, "ADDITIONAL_PIN_COUNTS")
    merged = dict(pins["repository_inputs"])
    for name, value in n2["additional_repository_inputs"].items():
        require(name not in merged or merged[name] == value, "OVERLAPPING_PIN_DRIFT")
        merged[name] = value
    # Read only the hash-pinned historical acceptance metadata, never its tests.
    require(sha_file(root / N1_ACCEPTANCE) == merged[N1_ACCEPTANCE], "N1_ACCEPTANCE_HASH")
    receipt = json.loads((root / N1_ACCEPTANCE).read_text(encoding="utf-8"))
    require(receipt["status"] == "N1_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS"
            and receipt["tests_run"] == 36 and len(receipt["powershell_parser_checks"]) == 2
            and all(p["exit_code"] == 0 for p in receipt["powershell_parser_checks"])
            and len(receipt["code_pins"]) == 9
            and receipt["runtime_file_sha256"] == pins["runtime_file_sha256"], "N1_ACCEPTANCE_SCHEMA")
    for name, value in receipt["code_pins"].items():
        require(name not in merged or merged[name] == value, "HISTORICAL_CODE_OVERLAP")
        require(sha_file(root / name) == value, "HISTORICAL_CODE_DRIFT")
    pins["repository_inputs"], pins["model_assembly"] = merged, n2["model_assembly"]
    pins["historical_code_pins"] = receipt["code_pins"]
    return pins


def project_dev(get, kind):
    selectors = {key: get(key) for key in SELECTORS[kind]}
    split = selectors["nested_split" if kind == "target" else "split"]
    require(split in {"train", "internal_val"} and bool(selectors["uid"]), "SELECTOR_DRIFT")
    return selectors, ({key: get(key) for key in PAYLOAD[kind]} if split == "internal_val" else None)


def scan_csv(blob, kind, audit, check=lambda: None):
    columns = {"target": TARGET_COLUMNS, "scope": SCOPE_COLUMNS, "index": INDEX_COLUMNS}[kind]
    source = gzip.GzipFile(fileobj=io.BytesIO(blob)) if kind == "target" else io.BytesIO(blob)
    audit.update(rows_tokenized=0, bytes_decompressed=0, column_accesses=Counter(),
                 excluded_payload_cells_transiently_tokenized=0, dev_payload_rows_retained=0)
    selectors, payloads, seen = {}, {}, set()
    def lines():
        while True:
            check()
            data = source.readline(65537)
            if not data:
                break
            audit["bytes_decompressed"] += len(data)
            require(len(data) <= 65536 and audit["bytes_decompressed"] <= 32 * 1024**2, "METADATA_SIZE_STOP")
            yield data.decode("utf-8")
    try:
        csv.field_size_limit(65536)
        reader = csv.reader(lines(), strict=True)
        require(tuple(next(reader, ())) == columns, "CSV_HEADER_DRIFT")
        positions = {key: i for i, key in enumerate(columns)}
        for row in reader:
            check()
            audit["rows_tokenized"] += 1
            audit["cells_tokenized"] = audit["rows_tokenized"] * len(columns)
            require(audit["rows_tokenized"] <= 13866 and len(row) == len(columns), "CSV_ROW_DRIFT")
            def get(key):
                audit["column_accesses"][key] += 1
                return row[positions[key]]
            if kind == "index":
                select = {key: get(key) for key in columns}
                payload, uid = select, select["context_key"]
            else:
                select, payload = project_dev(get, kind)
                uid = select["uid"]
            require(uid and uid not in seen, "DUPLICATE_UID_OR_CONTEXT")
            seen.add(uid)
            selectors[uid] = select
            if payload is not None:
                payloads[uid] = {**select, **payload}
                audit["dev_payload_rows_retained"] += int(kind != "index")
            if kind != "index":
                audit["excluded_payload_cells_transiently_tokenized"] += len(columns) - len(SELECTORS[kind]) - (len(PAYLOAD[kind]) if payload is not None else 0)
    except (csv.Error, UnicodeError, EOFError, gzip.BadGzipFile):
        raise Stop("METADATA_PARSE_STOP") from None
    finally:
        source.close()
    return selectors, payloads


def validate_metadata(index, target_select, targets, scope_select, scope, sources,
                      expected=EXPECTED, context_count=4323, all_contexts=9307,
                      all_targets=13866, all_events=205470, train_sources=13):
    require(len(index) == all_contexts and len(target_select) == len(scope_select) == all_targets,
            "METADATA_DENOMINATOR")
    require(len(sources["train"]) == train_sources and not sources["train"] & sources["internal_val"],
            "SOURCE_MEMBERSHIP")
    require(set(target_select) == set(scope_select), "SELECTOR_UID_JOIN")
    contexts, cursor = {}, 0
    for key, row in index.items():
        split = row["nested_split"]
        require(split in sources and row["source_group"] in sources[split], "CONTEXT_SOURCE_SPLIT")
        count, offset = integer(row["event_count"]), integer(row["event_offset"])
        require(offset == cursor and 1 <= count <= 256, "CONTEXT_RANGE")
        cursor += count
        if split == "internal_val":
            contexts[key] = {"key": key, "offset": offset, "count": count,
                             "source": row["source_group"], "targets": []}
    require(cursor == all_events and len(contexts) == context_count, "CONTEXT_EVENT_DENOMINATOR")
    require({c["source"] for c in contexts.values()} == sources["internal_val"], "DEV_SOURCE_COVERAGE")
    represented = set()
    for uid, row in target_select.items():
        peer = scope_select[uid]
        key = row["context_key"]
        require(key in index and peer["context"] == key and peer["split"] == row["nested_split"]
                == index[key]["nested_split"], "SELECTOR_CONTEXT_JOIN")
        represented.add(key)
    require(represented == set(index), "EMPTY_CONTEXT")
    require(set(targets) == set(scope) == {uid for uid, row in target_select.items()
                                        if row["nested_split"] == "internal_val"}, "DEV_UID_JOIN")
    counts = Counter()
    for uid, row in targets.items():
        c = contexts[row["context_key"]]
        require(row["source_group"] == c["source"] == scope[uid]["source"]
                and row["owner"] == scope[uid]["owner"], "DEV_METADATA_JOIN")
        category = CATEGORIES.get((row["owner"], row["label"], row["teacher_kind"]))
        require(category is not None, "CATEGORY_DRIFT")
        event = integer(row["event_index"])
        require(0 <= event < c["count"] and integer(row["prefix_events"]) == event + 1, "PREFIX_RANGE")
        require(row["finite"] == row["roundtrip_exact"] == "true" and row["feature_width"] == "131",
                "F4_INPUT_IDENTITY")
        require(re.fullmatch(r"[0-9a-f]{64}", row["feature_prefix_sha256"]), "PREFIX_HASH_SCHEMA")
        counts[category] += 1
        c["targets"].append({**row, "category": category, "event": event,
                             "protected": category in PROTECTED})
    require(dict(counts) == expected and len(targets) == sum(expected.values()), "CATEGORY_DENOMINATOR")
    selected_events = 0
    for c in contexts.values():
        require(bool(c["targets"]), "EMPTY_DEV_CONTEXT")
        require(len({r["device_family"] for r in c["targets"]}) == 1, "CONTEXT_DEVICE_DRIFT")
        c["length"] = max(r["event"] for r in c["targets"]) + 1
        c["byte_offset"], c["byte_length"] = c["offset"] * 524, c["length"] * 524
        selected_events += c["length"]
    require(selected_events <= all_events, "SELECTED_EVENT_CAP")
    return [contexts[key] for key in sorted(contexts)], dict(counts), selected_events


def group_size(rows):
    return (len(rows), len({r["context_key"] for r in rows}))


def validate_groups(contexts):
    rows = [r for c in contexts for r in c["targets"]]
    require({r["source_group"] for r in rows} == set(SOURCES), "DEV_SOURCE_KEYS")
    for source, wanted in SOURCES.items():
        require(group_size([r for r in rows if r["source_group"] == source]) == wanted,
                "DEV_SOURCE_COUNTS")
    normal = [r for r in rows if r["source_group"] == "normal_1.pcap"]
    for category, wanted in (("A0C", (843, 672)), ("B0N", (3157, 2995))):
        require(group_size([r for r in normal if r["category"] == category]) == wanted,
                "NORMAL1_COUNTS")
    require(sum(r["category"] == "A0C" and r["source_group"] != "normal_1.pcap"
                for r in rows) == 635, "OTHER_A0C_COUNTS")
    for category, family, wanted in (("A1C", "Ingress Tool Transfer", (3, 1)),
                                      ("B1N", "File Download", (3, 2))):
        attack = [r for r in rows if r["category"] == category]
        require(group_size(attack) == wanted and {r["attack_family"] for r in attack} == {family},
                "DEV_ATTACK_SUPPORT")
    benign = [r for r in rows if r["category"] == "B0N"]
    require({r["device_family"] for r in benign} == set(B_KEYS), "B_KEY_SET")
    for key, wanted in B_KEYS.items():
        require(group_size([r for r in benign if r["device_family"] == key]) == wanted[:2],
                "B_KEY_DENOMINATOR")


def verify_manifest_agreement(inputs):
    for name in inputs.pins:
        if name.endswith("/SHA256SUMS"):
            entries = manifest(inputs.read(name))
            prefix = name[:-len("SHA256SUMS")]
            for member, sha in inputs.pins.items():
                if member.startswith(prefix) and member != name:
                    require(entries.get(member[len(prefix):]) == sha, "MANIFEST_PIN_AGREEMENT")


def historical_witness(inputs):
    def read(name):
        return json.loads(inputs.read(N1_OUTPUT + "/" + name + ".json"))
    supervisor, worker = read("supervisor_terminal"), read("worker_terminal")
    require(supervisor["verdict"]["status"] == worker["verdict"]["status"] == "N1_JOINT_HEAD_WITNESS"
            and supervisor["worker_count"] == 1 and supervisor["worker_exit_code"] == 0
            and supervisor["restarts"] == 0 and supervisor["synthetic"] is False, "N1_WITNESS_STATUS")
    counts = worker["resource"]["counts"]
    require(all(counts[k] == v for k, v in
                {"lp_calls": 1, "passes": 2, "batches": 312, "contexts": 9968, "targets": 17320}.items()),
            "N1_WITNESS_COUNTS")
    access = worker["access"]
    require(all(access[k] == 0 for k in ("validation_numeric_access", "teacher_forwards",
                                        "backward_steps", "optimizer_steps"))
            and access["feature_decode"]["validation_events"] == 0, "N1_WITNESS_ACCESS")
    exact, outcomes = read("exact_candidate_check"), read("all_category_outcomes")
    require(exact["status"] == "VERIFIED" and exact["pass"] is True
            and exact["wrong_row_indices"] == [], "N1_EXACT_REFERENCE")
    require(set(outcomes) == set(base.EXPECTED)
            and all(outcomes[k]["targets"] == v and outcomes[k]["candidate_errors"] == []
                    and outcomes[k]["newly_wrong"] == [] for k, v in base.EXPECTED.items()),
            "N1_OUTCOME_REFERENCE")
    for member, sha in worker["output_hashes"].items():
        name = N1_OUTPUT + "/" + member
        if name in inputs.pins:
            require(inputs.pins[name] == sha, "N1_WORKER_MEMBER_DRIFT")
    return {"status": "N1_JOINT_HEAD_WITNESS", "protected_training_targets": 6914,
            "all_training_targets": 8660, "preservation": "IDENTITY_ONLY_NO_REPLAY"}
