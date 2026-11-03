"""N3 immutable identities, both original splits and bounded numerical I/O."""
from __future__ import annotations

import csv
import gzip
import io
import json
import re
from collections import Counter
from pathlib import Path

import issue27frontend_inheritance_n1_support_v1 as base
import issue27frontend_inheritance_n2_support_v1 as old
from issue27frontend_inheritance_n1_support_v1 import (
    ROOT, F4, F5, F3, N0, FEATURES, CHECKPOINT, CORE, CATEGORIES, PROTECTED,
    INDEX_COLUMNS, TARGET_COLUMNS, SCOPE_COLUMNS, SELECTORS, PAYLOAD,
    Stop, require, digest, json_bytes, sha_file, integer, relative_name,
    manifest, peak_memory, Writer, Inputs)

DESIGN = "runs/mainline_docs/frontend_inheritance_n3_conservative_joint_repair_frozen_20260908.md"
PINS_FILE = "runs/mainline_docs/frontend_inheritance_n3_input_and_evidence_pins_20260908.json"
EVIDENCE = "runs/mainline_docs/frontend_inheritance_n3_same_behavior_evidence_contract_20260908.md"
DESIGN_SHA = "dcc54d50e130f21d1f49a48082a28744673a28cfa44a64f564c279f03e676843"
PINS_SHA = "202d15b3e5aaee736da401a083cd10b48f379cf66fb43ab48647649c1ae569ed"
EVIDENCE_SHA = "3b8f5d40d24df3c8434f4324811dbb4d5a09a220a5f7b02ea7e16b2d4793d3e2"
IMPLEMENTATION = "runs/frontend_inheritance_n3_implementation_v1_20260908"
REAL_OUTPUT = "runs/frontend_inheritance_n3_conservative_joint_repair_v1_20260908"
N1_OUTPUT, N2_OUTPUT = old.N1_OUTPUT, old.REAL_OUTPUT
HEAD = old.HEAD
CACHE = N1_OUTPUT + "/target64.f32le"
AUTHORIZATION = "I_AUTHORIZE_ONE_REAL_N3_CONSERVATIVE_FIT_AND_RESTRICTED_INPUT_ACCESS"
CODE = tuple("repo/ood/issue27frontend_inheritance_n3_" + name + "_v1.py"
             for name in ("support", "runner", "control", "tests", "verify")) + (
    "scripts/start_frontend_inheritance_n3_local.ps1",
    "scripts/show_frontend_inheritance_n3_status.ps1",
    "repo/ood/issue27frontend_inheritance_n1_support_v1.py",
    "repo/ood/issue27frontend_inheritance_n1_math_v1.py",
    "repo/ood/issue27frontend_inheritance_n2_support_v1.py")
CAPS = {"wall_seconds": 1800, "memory_bytes": 8 * 1024**3,
        "output_bytes": 100 * 1024**2, "reserve_bytes": 1024**2,
        "loads": 1, "head_decodes": 1, "assemblies": 1, "installations": 1,
        "cache_decodes": 1, "cache_values": 554240, "candidate_casts": 1,
        "exact_positive_stages": 1, "exact_negative_stages": 1,
        "lp_calls": 1, "passes": 3, "batches": 428, "targets": 19072,
        "contexts": 13630, "events": 377635, "decoded_events": 205470,
        "decoded_train_events": 33305, "decoded_dev_events": 172165,
        "baseline_dev_passes": 1, "candidate_train_passes": 1, "candidate_dev_passes": 1,
        "padded_slots": 3489280,
        **{k: 0 for k in ("optimizer_steps", "backward_steps", "teacher_forwards",
                         "baseline_train_passes", "old_terminal_passes",
                         "threshold_fits", "retries", "pilots", "hpc_jobs")}}
EXPECTED, SOURCES, B_KEYS = old.EXPECTED, old.SOURCES, old.B_KEYS
PHASE_COUNTS = {
    "baseline_dev": {"batches": 136, "contexts": 4323, "targets": 5206, "events": 172165},
    "candidate_train": {"batches": 156, "contexts": 4984, "targets": 8660, "events": 33305},
    "candidate_dev": {"batches": 136, "contexts": 4323, "targets": 5206, "events": 172165}}
CAPS.update({phase + "_" + key: value for phase, values in PHASE_COUNTS.items()
             for key, value in values.items()})
SCIENTIFIC = ("N3_CONSERVATIVE_JOINT_REPAIR_WITNESS", "N3_EXACT_AFFINE_NONSEPARABLE",
              "N3_NUMERICAL_UNKNOWN")
STATUSES = set(SCIENTIFIC) | {"N3_ENGINEERING_STOP", "N3_NEEDS_GOVERNED_MODEL_EXPORT"}
CLAIMS = {"broader_inheritance": "NOT_PROVED", "inheritance": "NOT_PROVED",
          "F5_eligible": False, "deployment": False, "K": "NOT_AUTHORIZED",
          "new_device": "NOT_EVALUATED"}


class Budget(base.Budget):
    def __init__(self, **kwargs):
        kwargs.setdefault("caps", CAPS)
        super().__init__(**kwargs)


def merge_pins(first, second):
    merged = dict(first)
    for name, value in second.items():
        require(name not in merged or merged[name] == value, "OVERLAPPING_PIN_DRIFT")
        merged[name] = value
    return merged


def frozen_design(root=ROOT):
    for name, expected in ((DESIGN, DESIGN_SHA), (PINS_FILE, PINS_SHA), (EVIDENCE, EVIDENCE_SHA)):
        path = root / name
        require(sha_file(path) == expected, "FROZEN_DESIGN_DRIFT")
        require(manifest(path.with_suffix(".sha256").read_bytes()) == {path.name: expected},
                "DESIGN_SIDECAR_DRIFT")
    pins = old.frozen_design(root)
    n3 = json.loads((root / PINS_FILE).read_text(encoding="utf-8"))
    require(n3["inherited_bundle"]["sha256"] == old.PINS_SHA, "INHERITED_PIN_DRIFT")
    pins["repository_inputs"] = merge_pins(pins["repository_inputs"], n3["additional_repository_inputs"])
    require(len(pins["repository_inputs"]) == 57, "PIN_COUNT")
    codes = dict(pins["historical_code_pins"])
    for att in n3["historical_implementation_attestations"]:
        path = root / att["source"]
        require(sha_file(path) == att["sha256"] == pins["repository_inputs"][att["source"]],
                "HISTORICAL_ACCEPTANCE_HASH")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        require(receipt["status"] == att["status"] and receipt["tests_run"] == att["tests_run"]
                and len(receipt["powershell_parser_checks"]) == 2
                and all(p["exit_code"] == 0 for p in receipt["powershell_parser_checks"])
                and len(receipt["code_pins"]) == 9
                and receipt["runtime_file_sha256"] == pins["runtime_file_sha256"],
                "HISTORICAL_ACCEPTANCE_SCHEMA")
        codes = merge_pins(codes, receipt["code_pins"])
    require(len(codes) == 16, "HISTORICAL_CODE_COUNT")
    for name, sha in codes.items():
        require(sha_file(root / name) == sha, "HISTORICAL_CODE_DRIFT")
    pins["historical_code_pins"], pins["n3"] = codes, n3
    pins["model_assembly"] = {**n3["model_identity"],
        "head_float32_le_sha256": n3["model_identity"]["n1_head_float32_le_sha256"]}
    return pins


class Inputs(base.Inputs):
    def read(self, name):
        raw = super().read(name)
        if name in {HEAD, CACHE}:
            self.audit["metadata_containers_read"].remove(name)
            self.audit.setdefault("numerical_containers_read", []).append(
                {"name": name, "bytes": len(raw), "decode_accounted_separately": True})
        return raw


def project_both(get, kind):
    selectors = {key: get(key) for key in SELECTORS[kind]}
    split = selectors["nested_split" if kind == "target" else "split"]
    require(split in {"train", "internal_val"} and bool(selectors["uid"]), "SELECTOR_DRIFT")
    return selectors, {key: get(key) for key in PAYLOAD[kind]}


def scan_csv(blob, kind, audit, check=lambda: None):
    columns = {"target": TARGET_COLUMNS, "scope": SCOPE_COLUMNS, "index": INDEX_COLUMNS}[kind]
    source = gzip.GzipFile(fileobj=io.BytesIO(blob)) if kind == "target" else io.BytesIO(blob)
    audit.update(rows_tokenized=0, bytes_decompressed=0, column_accesses=Counter(),
                 excluded_payload_cells_transiently_tokenized=0, both_split_payload_rows_retained=0)
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
                select, payload = project_both(get, kind)
                uid = select["uid"]
            require(uid and uid not in seen, "DUPLICATE_UID_OR_CONTEXT")
            seen.add(uid)
            selectors[uid] = select
            if payload is not None:
                payloads[uid] = {**select, **payload}
                audit["both_split_payload_rows_retained"] += int(kind != "index")
            if kind != "index":
                audit["excluded_payload_cells_transiently_tokenized"] += len(columns) - len(SELECTORS[kind]) - (len(PAYLOAD[kind]) if payload is not None else 0)
    except (csv.Error, UnicodeError, EOFError, gzip.BadGzipFile):
        raise Stop("METADATA_PARSE_STOP") from None
    finally:
        source.close()
    return selectors, payloads


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

def validate_metadata(index, ts, targets, ss, scope, sources):
    result = {}
    for split, module in (("train", base), ("internal_val", old)):
        chosen = {u: r for u, r in targets.items() if r["nested_split"] == split}
        peers = {u: r for u, r in scope.items() if r["split"] == split}
        contexts, counts, events = module.validate_metadata(index, ts, chosen, ss, peers, sources)
        for context in contexts:
            context["split"] = split
        require(events == (33305 if split == "train" else 172165), "SPLIT_EVENT_COUNT")
        result[split] = contexts
    validate_groups(result["internal_val"])
    return result
