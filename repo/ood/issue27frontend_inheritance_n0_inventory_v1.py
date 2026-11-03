"""One-shot metadata inventory. Standard library only; import performs no I/O."""
from __future__ import annotations

import argparse
import csv
import ctypes
import gzip
import hashlib
import io
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = "runs/frontend_inheritance_n0_inventory_v1_20260907"
ACCEPTANCE = "runs/frontend_inheritance_n0_implementation_20260907/synthetic_acceptance.json"
CONTRACT = "runs/mainline_docs/frontend_inheritance_n0_contract_gap_inventory_20260907.json"
DESIGN = "runs/mainline_docs/frontend_inheritance_feasibility_minimal_design_20260907.md"
D0 = "runs/frontend_f1_d0_census_v1_20260902_local_r2"
F4 = "runs/frontend_f4_fieldwise_input_feasibility_v1_20260905"
F5 = "runs/frontend_f5_unified_student_v1_20260906_local"
F3_ID = "runs/frontend_f3_full_fit_l1_identifiability_v1_20260905/f3b_identities.json"
F1_PROTOCOL = "runs/mainline_docs/frontend_f1_d1_numerical_addendum_frozen_20260902.md"
MIXED = D0 + "/f1_d0_uid_context_phase_owner_conservation.csv.gz"
AUTHORIZATION = "I_AUTHORIZE_N0_METADATA_ONLY_SELECTOR_ACCESS"
CAPS = {"wall_seconds": 600, "ram_bytes": 1024**3, "output_bytes": 50 * 1024**2,
        "input_file_bytes": 32 * 1024**2, "decompressed_table_bytes": 32 * 1024**2,
        "physical_line_bytes": 65536}

PINS = {
    DESIGN: "b888ef4414d652f31846c37fdb512fa6383e15c45e25d082d19f9edcf82e6d85",
    D0 + "/SHA256SUMS": "4c69fb519ab6fa27b5564c8cee53ed3c4217db8fc4d0541fdc23d106b0c6eba8",
    MIXED: "c02937de7c5660688c60578adb2801f5a12b709745652fa8303b6c8e0d0b0ae9",
    F4 + "/SHA256SUMS": "432c03f543e3dc9c2bdc97cc9842e53fb846e4cf62f92fb5642b2896855d4df5",
    F4 + "/f4_target_audit.csv.gz": "fa4cb5efa3af5cc65cafc562c7c5e3d71aa2416910edd213ef5535f0a2da7c51",
    F4 + "/f4_context_index.csv": "c62d9fb84db7edf6eaa733fcb5ac72b928f3c783db9f2549afa81a3a77700444",
    F4 + "/f4_nested_split_census.csv": "76da23f4ed27bea017ec3f3f36648ad730bc6e86df2246abb5435541217707da",
    F4 + "/f4_schema.json": "5d66120b8f1b224bdcb66ff46ae6923641d923cb1eee4554a6c8bf80179c3681",
    F5 + "/SHA256SUMS": "27cd3ac6575b251462fa272e3bdb7763938adde70e544bfd43571f9879863c53",
    F5 + "/preflight/uid_scope.csv": "529ec944e31463f98173ec1103920f6ca21e4a7ad9cff080bd85cebb3b9394e9",
    F5 + "/preflight/census.json": "b7924a3c40b838e483783c2feff1ec58b360959e961300d5ac93047d230815e6",
    F5 + "/preflight/identities.json": "f01f8c682b52dee1edeb43f4215731caa4658f6f0503c4388d56720952b44734",
    F3_ID: "073b28f5f3617d8c2c1ff0fd919cd02116b961d35ccc7ea5de6e7581d03f2b09",
    F1_PROTOCOL: "7cf06c5885e21b813f9f5933360bc18308f41038bdb60809e2343a612fafd860",
}
F1_COLUMNS = (
    "uid", "semantic_context_key", "phase", "owner", "label_kind", "role",
    "source_group", "device_family", "attack_family", "context_tier",
    "context_event_count", "cross_phase_context", "legal_fit",
)
SELECTORS = ("uid", "phase", "legal_fit", "cross_phase_context")
F1_PAYLOAD = tuple(c for c in F1_COLUMNS if c not in SELECTORS)
F4_COLUMNS = (
    "uid", "context_key", "event_index", "source_group", "nested_split", "owner",
    "label", "teacher_kind", "device_family", "attack_family", "l1_prefix_sha256",
    "feature_prefix_sha256", "prefix_events", "old_all_unk", "roundtrip_exact",
    "finite", "feature_width",
)
F4_PROJECT = tuple(c for c in F4_COLUMNS if c not in {
    "l1_prefix_sha256", "feature_prefix_sha256", "old_all_unk"})
INDEX_COLUMNS = ("context_key", "source_group", "nested_split", "event_offset", "event_count")
CENSUS_COLUMNS = ("nested_split", "category", "targets", "contexts")
SCOPE_COLUMNS = ("uid", "split", "source", "owner", "context")
F1_VAL_SOURCES = {
    "normal_scanning1.pcap", "iotsim-combined-cycle-3_0-0_to_OpenvSwitch-13_3-0",
    "iotsim-combined-cycle-7_0-0_to_OpenvSwitch-13_7-0",
    "iotsim-combined-cycle-8_0-0_to_OpenvSwitch-13_8-0",
    "iotsim-domotic-monitor-2_0-0_to_OpenvSwitch-23_2-0",
}
CATEGORIES = {("A", "1", "attack_hard"): "A1C", ("A", "0", "benign_normal"): "A0C",
              ("A", "0", "benign_hard"): "A0W", ("B", "1", "none"): "B1N",
              ("B", "0", "none"): "B0N"}
EXPECTED_CATEGORIES = {"train": {"A1C": 2179, "A0C": 4667, "A0W": 24, "B1N": 68, "B0N": 1722},
                       "internal_val": {"A1C": 3, "A0C": 1478, "A0W": 2, "B1N": 3, "B0N": 3720}}
F4_CATEGORY_MAP = {"a_protected_attack": "A1C", "a_protected_benign": "A0C",
                   "a_unprotected_benign": "A0W", "b_attack": "B1N", "b_benign": "B0N"}
VENDOR = "../../supercompute_transfer/issue27ckda_d0_representation_compatibility_20260811_r2/payload/vendor/netFound/src/modules/"
SOURCE_PATHS = {"repo/ood/" + name for name in (
    "issue27ckda_d0_resource_pilot_v1.py", "issue27ckda_d1_e3_embed_v1.py",
    "issue27ckda_d1_representation_probe_v1.py", "issue27frontend_f0_zero_training_semantics_v1.py",
    "issue27frontend_f1_d0_census_v1.py", "issue27frontend_f3_conflict_field_sufficiency_v1.py",
    "issue27frontend_f3_full_fit_l1_identifiability_v1.py", "issue27frontend_f4_fieldwise_input_v1.py",
)} | {VENDOR + name for name in ("netFoundTokenizer.py", "netFoundEmbeddings.py", "netFoundDataCollator.py")}


class N0Stop(RuntimeError):
    """Messages are fixed codes, never raw input values."""


def require(condition, code):
    if not condition:
        raise N0Stop(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def integer(value):
    require(bool(re.fullmatch(r"0|[1-9][0-9]*", value)), "INTEGER_SCHEMA_DRIFT")
    return int(value)


def peak_memory():
    require(os.name == "nt", "WINDOWS_RESOURCE_MONITOR_REQUIRED")

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                "PagefileUsage", "PeakPagefileUsage")]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    require(psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb),
            "MEMORY_MEASUREMENT_FAILED")
    return max(int(counters.PeakWorkingSetSize), int(counters.PeakPagefileUsage))


class Budget:
    def __init__(self, memory=peak_memory, clock=time.monotonic):
        self.memory, self.clock = memory, clock
        self.start = clock()
        self.last_memory_check = self.start - 1
        self.peak = 0
        self.output_bytes = 0

    def check(self):
        now = self.clock()
        if now - self.last_memory_check >= 0.05:
            self.peak = max(self.peak, self.memory())
            self.last_memory_check = now
        require(now - self.start <= CAPS["wall_seconds"], "WALL_CAP_STOP")
        require(self.peak <= CAPS["ram_bytes"], "RAM_CAP_STOP")
        require(self.output_bytes <= CAPS["output_bytes"], "OUTPUT_CAP_STOP")

    def receipt(self):
        return {"elapsed_seconds": self.clock() - self.start, "peak_process_memory_bytes": self.peak,
                "new_output_bytes_before_terminal_receipts": self.output_bytes, "caps": CAPS,
                "enforcement": "Cooperative checks at bounded reads, rows and writes; not an OS hard limit."}


def parse_manifest(raw):
    result = {}
    for line in raw.decode("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_./-]+)", line)
        require(match is not None, "MANIFEST_SCHEMA_DRIFT")
        sha, name = match.groups()
        require(not name.startswith("/") and ".." not in name.split("/") and name not in result,
                "MANIFEST_PATH_DRIFT")
        result[name] = sha
    return result


def select_fit(get):
    selectors = {name: get(name) for name in SELECTORS}
    require(bool(selectors["uid"]), "EMPTY_UID")
    require(selectors["phase"] in {"fit", "select"}, "PHASE_DRIFT")
    require(all(selectors[name] in {"True", "False"} for name in ("legal_fit", "cross_phase_context")),
            "SELECTOR_BOOL_DRIFT")
    lawful = selectors["phase"] == "fit" and selectors["cross_phase_context"] == "False"
    require((selectors["legal_fit"] == "True") == lawful, "SELECTOR_CONTRADICTION")
    return selectors, ({name: get(name) for name in F1_PAYLOAD} if lawful else None)


def scan_csv(blob, columns, projected, audit, check, mixed=False, compressed=False, row_cap=25467):
    """CSV tokenizes one transient full row; only the permitted projection escapes."""
    audit.update({"metadata_scans": 1, "decompressed_bytes": 0, "csv_rows_tokenized": 0,
                  "column_value_accesses": Counter(), "retained_metadata_rows": 0,
                  "nonfit_research_rows_retained": 0, "selector_counts": Counter(),
                  "nonfit_cells_transiently_tokenized": 0})
    source = gzip.GzipFile(fileobj=io.BytesIO(blob)) if compressed else io.BytesIO(blob)

    def lines():
        while True:
            check()
            raw = source.readline(CAPS["physical_line_bytes"] + 1)
            if not raw:
                return
            require(len(raw) <= CAPS["physical_line_bytes"], "LINE_CAP_STOP")
            audit["decompressed_bytes"] += len(raw)
            require(audit["decompressed_bytes"] <= CAPS["decompressed_table_bytes"], "DECOMPRESSED_CAP_STOP")
            yield raw.decode("utf-8")

    result, seen = [], set()
    csv.field_size_limit(CAPS["physical_line_bytes"])
    try:
        reader = csv.reader(lines(), strict=True)
        require(tuple(next(reader, ())) == tuple(columns), "CSV_HEADER_DRIFT")
        positions = {name: index for index, name in enumerate(columns)}
        for row in reader:
            audit["csv_rows_tokenized"] += 1
            require(audit["csv_rows_tokenized"] <= row_cap, "ROW_CAP_STOP")
            require(len(row) == len(columns), "CSV_ROW_WIDTH_DRIFT")

            def get(name):
                audit["column_value_accesses"][name] += 1
                return row[positions[name]]

            if mixed:
                selectors, payload = select_fit(get)
                uid = selectors["uid"]
                require(uid not in seen, "DUPLICATE_UID")
                seen.add(uid)
                audit["selector_counts"][selectors["phase"]] += 1
                if selectors["cross_phase_context"] == "True":
                    audit["selector_counts"]["cross_" + selectors["phase"]] += 1
                if payload is None:
                    audit["nonfit_cells_transiently_tokenized"] += len(columns) - len(SELECTORS)
                    continue
                value = {"uid": uid, **payload}
            else:
                value = {name: get(name) for name in projected}
            result.append(value)
            audit["retained_metadata_rows"] += 1
    except (csv.Error, UnicodeError, EOFError, gzip.BadGzipFile):
        raise N0Stop("N0_NEEDS_GOVERNED_EXPORT") from None
    finally:
        source.close()
    return result


class Inputs:
    def __init__(self, root, pins, budget):
        self.root, self.pins, self.budget = root, pins, budget
        self.identities, self.tables = {}, {}

    def read(self, name):
        self.budget.check()
        require(name in self.pins and name not in self.identities, "UNAUTHORIZED_OR_REPEAT_INPUT")
        path = (self.root / name).resolve()
        size = path.stat().st_size
        require(size <= CAPS["input_file_bytes"], "INPUT_SIZE_STOP")
        with path.open("rb") as handle:
            raw = handle.read(CAPS["input_file_bytes"] + 1)
        require(len(raw) == size, "INPUT_SIZE_DRIFT")
        sha = digest(raw)
        self.identities[name] = {"sha256": sha, "expected_sha256": self.pins[name], "bytes_read": len(raw),
                                 "container_reads": 1, "identity_pass": sha == self.pins[name]}
        require(sha == self.pins[name], "INPUT_IDENTITY_DRIFT")
        self.budget.check()
        return raw

    def json(self, name):
        return json.loads(self.read(name))

    def table(self, name, columns, projected=None, mixed=False, row_cap=25467):
        blob = self.read(name)
        audit = self.tables.setdefault(name, {})
        return scan_csv(blob, columns, projected or columns, audit, self.budget.check,
                        mixed=mixed, compressed=name.endswith(".gz"), row_cap=row_cap)


def unique(rows, key):
    result = {row[key]: row for row in rows}
    require(len(result) == len(rows), "DUPLICATE_JOIN_KEY")
    return result


def categorize(row):
    key = (row["owner"], row["label"], row["teacher_kind"])
    require(key in CATEGORIES, "CATEGORY_DRIFT")
    return CATEGORIES[key]


def parse_context_key(value):
    parts = value.split("\x1f")
    require(len(parts) == 3 and bool(parts[0]) and re.fullmatch(r"[0-9a-f]{64}", parts[1]) is not None,
            "CONTEXT_KEY_SCHEMA_DRIFT")
    integer(parts[2])
    return tuple(parts)


def validate_saved_census(saved, categories, category_contexts):
    census_keys = set()
    for row in saved:
        require(row["category"] in F4_CATEGORY_MAP, "F4_CENSUS_CATEGORY_DRIFT")
        key = (row["nested_split"], F4_CATEGORY_MAP[row["category"]])
        require(key not in census_keys and key in category_contexts, "F4_CENSUS_KEY_DRIFT")
        census_keys.add(key)
        require(integer(row["targets"]) == categories[key[0]][key[1]] and
                integer(row["contexts"]) == len(category_contexts[key]), "F4_CENSUS_DRIFT")
    require(census_keys == set(category_contexts), "F4_CENSUS_INCOMPLETE")


def validate_scope(scope, parent):
    p_scope = unique(scope, "uid")
    require(set(p_scope) == set(parent), "P_UID_SCOPE_DRIFT")
    for uid, row in p_scope.items():
        for source_key, target_key in (("split", "nested_split"), ("source", "source_group"),
                                       ("owner", "owner"), ("context", "context_key")):
            require(row[source_key] == parent[uid][target_key], "P_SCOPE_METADATA_DRIFT")


def validate_parent(legal, index, targets, scope, split_sources, saved_census, p_census):
    contexts, parent = unique(index, "context_key"), unique(targets, "uid")
    require(len(contexts) == 9307 and len(parent) == 13866, "F4_DENOMINATOR_DRIFT")
    require(set(parent) <= set(legal), "PARENT_NOT_LEGAL_FIT")
    cursor, context_splits = 0, Counter()
    for row in index:
        split = row["nested_split"]
        require(split in split_sources and row["source_group"] in split_sources[split], "SOURCE_SPLIT_DRIFT")
        count = integer(row["event_count"])
        require(integer(row["event_offset"]) == cursor and 1 <= count <= 256, "CONTEXT_OFFSET_DRIFT")
        cursor += count
        context_splits[split] += 1
    require(cursor == 205470 and context_splits == {"train": 4984, "internal_val": 4323},
            "CONTEXT_CENSUS_DRIFT")
    categories = {split: Counter() for split in split_sources}
    category_contexts, seen_contexts = defaultdict(set), set()
    for uid, row in parent.items():
        old = legal[uid]
        require(row["context_key"] in contexts, "TARGET_CONTEXT_DRIFT")
        context = contexts[row["context_key"]]
        for key in ("context_key", "nested_split", "source_group"):
            require(row[key] == context[key], "TARGET_CONTEXT_METADATA_DRIFT")
        for key in ("owner", "source_group", "device_family", "attack_family"):
            require(row[key] == old[key], "F1_F4_METADATA_DRIFT")
        require(row["context_key"] == old["semantic_context_key"], "F1_F4_CONTEXT_DRIFT")
        require(row["label"] == {"benign": "0", "attack": "1"}[old["label_kind"]], "LABEL_DRIFT")
        position, prefix = integer(row["event_index"]), integer(row["prefix_events"])
        require(position < integer(context["event_count"]) and prefix == position + 1, "PREFIX_COUNT_DRIFT")
        require(prefix == integer(old["context_event_count"]), "F1_F4_PREFIX_COUNT_DRIFT")
        require(row["feature_width"] == "131" and row["finite"] == row["roundtrip_exact"] == "true",
                "INHERITED_F4_METADATA_FLAG_DRIFT")
        split, category = row["nested_split"], categorize(row)
        categories[split][category] += 1
        category_contexts[(split, category)].add(row["context_key"])
        seen_contexts.add(row["context_key"])
    require(seen_contexts == set(contexts), "EMPTY_PARENT_CONTEXT")
    require(categories == EXPECTED_CATEGORIES, "PROTECTED_DENOMINATOR_DRIFT")
    require(p_census["categories"] == {"train": dict(categories["train"]), "val": dict(categories["internal_val"])},
            "P_CENSUS_DRIFT")
    validate_saved_census(saved_census, categories, category_contexts)
    validate_scope(scope, parent)
    return parent, contexts


def expose(legal, parent, split_sources):
    remainder, heldout_contexts, all_contexts = [], set(), set()
    source_exposures, member_exposures, context_exposures = defaultdict(set), defaultdict(set), defaultdict(set)
    for uid, row in legal.items():
        require(row["owner"] in {"A", "B"} and row["label_kind"] in {"attack", "benign"}, "F1_LABEL_OWNER_DRIFT")
        require(row["context_tier"] in {"H1", "H2", "H3", "H4"}, "TIER_DRIFT")
        require(1 <= integer(row["context_event_count"]) <= 256, "F1_CONTEXT_EVENT_COUNT_DRIFT")
        # This is the producer-defined serialized key, not an inferred physical identity.
        parts = parse_context_key(row["semantic_context_key"])
        row["artifact_member_id"] = parts[0]
        row["context_epoch"] = parts[2]
        if uid in parent:
            row["exposure"] = "F5_train" if parent[uid]["nested_split"] == "train" else "F5_validation_exposed"
            require(row["source_group"] not in F1_VAL_SOURCES, "F1_HELDOUT_SOURCE_IN_PARENT")
        else:
            require(row["source_group"] in F1_VAL_SOURCES, "UNKNOWN_REMAINDER_SOURCE")
            row["exposure"] = "F1_validation_exposed"
            remainder.append(row)
            heldout_contexts.add(row["semantic_context_key"])
        source_exposures[row["source_group"]].add(row["exposure"])
        member_exposures[row["artifact_member_id"]].add(row["exposure"])
        context_exposures[row["semantic_context_key"]].add(row["exposure"])
        all_contexts.add(row["semantic_context_key"])
    require(len(legal) == 18266 and len(all_contexts) == 12889, "LEGAL_FIT_DENOMINATOR_DRIFT")
    require(len(remainder) == 4400 and len(heldout_contexts) == 3582, "F1_EXPOSURE_DENOMINATOR_DRIFT")
    require({row["source_group"] for row in remainder} == F1_VAL_SOURCES, "F1_EXPOSURE_SOURCE_DRIFT")
    require(Counter((r["owner"], r["label_kind"]) for r in remainder) ==
            {("A", "benign"): 1176, ("A", "attack"): 2000, ("B", "benign"): 1224}, "F1_EXPOSURE_LABEL_DRIFT")
    require(all(len(values) == 1 for values in source_exposures.values()) and
            all(len(values) == 1 for values in member_exposures.values()) and
            all(len(values) == 1 for values in context_exposures.values()), "EXPOSURE_DEPENDENCY_CROSSING")
    require(set(source_exposures) == set().union(*split_sources.values(), F1_VAL_SOURCES), "SOURCE_SET_DRIFT")
    return {"legal_fit_targets": len(legal), "legal_fit_contexts": len(all_contexts),
            "artifact_members": len(member_exposures), "sources": len(source_exposures),
            "exposure_targets": dict(Counter(r["exposure"] for r in legal.values())),
            "physical_device_independence": "UNKNOWN", "old_session_membership": "UNKNOWN",
            "earlier_history_membership": "UNKNOWN", "untouched_confirmation": "NOT_IDENTIFIED"}


def group_rows(rows, keys):
    grouped = {}
    for row in rows:
        key = tuple(row[name] for name in keys)
        group = grouped.setdefault(key, {"targets": 0, "contexts": set(), "members": set(), "sources": set(),
                                         "minimum_prefix_events": 257, "maximum_prefix_events": 0})
        group["targets"] += 1
        group["contexts"].add(row["semantic_context_key"])
        group["members"].add(row["artifact_member_id"])
        group["sources"].add(row["source_group"])
        count = integer(row["context_event_count"])
        group["minimum_prefix_events"] = min(group["minimum_prefix_events"], count)
        group["maximum_prefix_events"] = max(group["maximum_prefix_events"], count)
    result = []
    for key, group in sorted(grouped.items()):
        result.append({**dict(zip(keys, key)), **{name: len(value) if isinstance(value, set) else value
                                               for name, value in group.items()}})
    return result


def write_output(output, name, raw, budget):
    require("/" not in name and "\\" not in name, "OUTPUT_PATH_DRIFT")
    budget.check()
    require(budget.output_bytes + len(raw) <= CAPS["output_bytes"] - 16384, "OUTPUT_CAP_STOP")
    with (output / name).open("xb") as handle:
        handle.write(raw)
    budget.output_bytes += len(raw)


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def csv_bytes(rows):
    require(bool(rows), "EMPTY_OUTPUT_TABLE")
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return text.getvalue().encode("utf-8")


def inventory(inputs, contract, output, budget):
    for base in (D0, F4, F5):
        manifest = parse_manifest(inputs.read(base + "/SHA256SUMS"))
        for name, expected in PINS.items():
            if name.startswith(base + "/") and not name.endswith("/SHA256SUMS"):
                require(manifest.get(name[len(base) + 1:]) == expected, "MANIFEST_PIN_DRIFT")
    inputs.read(DESIGN)
    protocol = inputs.read(F1_PROTOCOL).decode("utf-8")
    require(all(name in protocol for name in F1_VAL_SOURCES), "F1_LITERAL_SOURCE_LIST_DRIFT")
    identities = inputs.json(F5 + "/preflight/identities.json")
    for name, expected in PINS.items():
        if name.startswith(F4 + "/") or name == F3_ID:
            require(identities["input_pins"].get(name) == expected, "P_INPUT_PIN_DRIFT")
    f3 = inputs.json(F3_ID)
    split_sources = {"train": set(f3["nested_split"]["train_sources"]),
                     "internal_val": set(f3["nested_split"]["internal_validation_sources"])}
    require(not split_sources["train"] & split_sources["internal_val"], "SOURCE_LIST_OVERLAP")
    schema = inputs.json(F4 + "/f4_schema.json")
    require(schema["width"] == 131 and len(schema["record_keys"]) == 19, "F4_SCHEMA_DRIFT")
    for name in contract["source_sha256"]:
        inputs.read(name)
    legal = unique(inputs.table(MIXED, F1_COLUMNS, mixed=True), "uid")
    access = inputs.tables[MIXED]
    require(access["selector_counts"] == {"fit": 18398, "select": 7069, "cross_fit": 132, "cross_select": 32},
            "MIXED_SELECTOR_DENOMINATOR_DRIFT")
    require(access["csv_rows_tokenized"] == 25467 and len(legal) == 18266, "MIXED_ROW_DRIFT")
    require(all(access["column_value_accesses"][name] == 25467 for name in SELECTORS) and
            all(access["column_value_accesses"][name] == 18266 for name in F1_PAYLOAD),
            "RESTRICTED_PROJECTION_ACCESS_DRIFT")
    index = inputs.table(F4 + "/f4_context_index.csv", INDEX_COLUMNS, row_cap=9307)
    targets = inputs.table(F4 + "/f4_target_audit.csv.gz", F4_COLUMNS, F4_PROJECT, row_cap=13866)
    scope = inputs.table(F5 + "/preflight/uid_scope.csv", SCOPE_COLUMNS, row_cap=13866)
    saved_census = inputs.table(F4 + "/f4_nested_split_census.csv", CENSUS_COLUMNS, row_cap=10)
    p_census = inputs.json(F5 + "/preflight/census.json")
    parent, contexts = validate_parent(legal, index, targets, scope, split_sources, saved_census, p_census)
    summary = expose(legal, parent, split_sources)
    summary.update({"parent_targets": len(parent), "parent_contexts": len(contexts),
                    "parent_events_from_index": 205470, "protected_training_targets": 6914,
                    "inherited_crossing_context_exclusions": 19,
                    "crossing_context_count_recomputed": False,
                    "crossing_context_evidence": "Inherited sealed F1 D0 identity; only crossing row flags were recounted."})
    coverage = group_rows(legal.values(), ("exposure", "source_group", "device_family", "owner", "label_kind", "attack_family", "context_tier"))
    detail = group_rows(legal.values(), ("exposure", "source_group", "artifact_member_id", "semantic_context_key", "role", "owner", "label_kind", "device_family", "attack_family", "context_tier"))
    family_coverage = group_rows(legal.values(), ("exposure", "device_family", "label_kind"))
    normal = [r for r in legal.values() if r["device_family"] == "ton-iot-external" and r["label_kind"] == "benign"]
    summary["ton_benign_exposure_counts"] = dict(Counter(r["exposure"] for r in normal))
    summary["ton_benign_sources"] = sorted({r["source_group"] for r in normal})
    summary["ton_benign_in_f5_train"] = sum(r["exposure"] == "F5_train" for r in normal)
    findings = [
        {"use": "legal_fit_coverage_and_exposure", "status": "IDENTIFIED", "reason": "Original 18266 target lineage reconciled; no reallocation performed."},
        {"use": "ton_benign_training_coverage", "status": "INSUFFICIENT" if summary["ton_benign_in_f5_train"] == 0 else "IDENTIFIED",
         "reason": "Counts are for original F5 nested-train. Exposed development rows are not untouched confirmation."},
        {"use": "same_behavior_dependency_separated_holdout", "status": "UNKNOWN", "reason": "Artifact member/source/context labels do not certify physical-device or old-session independence or behavior equivalence."},
        {"use": "fixed_teacher_field_or_history_numeric_contrast", "status": "INSUFFICIENT", "reason": "Approved inputs contain no verified raw-field/token cache and no UID-to-old-session/earlier-prefix bridge."},
        {"use": "joint_fit_and_retention_feasibility", "status": "UNKNOWN", "reason": "Metadata cannot establish existence of weights satisfying all protection gates."},
    ]
    for name, value in (("coverage_table.csv", coverage), ("context_coverage_table.csv", detail),
                        ("family_coverage_table.csv", family_coverage), ("readiness_table.csv", findings),
                        ("contract_gap_table.csv", contract["items"])):
        write_output(output, name, csv_bytes(value), budget)
    write_output(output, "inventory_summary.json", json_bytes(summary), budget)
    return {"status": "READY_FOR_SCOPED_DIAGNOSTIC_DESIGN", "inventory_complete": True,
            "limitations": ["COVERAGE_INSUFFICIENT", "HISTORY_MEMBERSHIP_UNRESOLVED"],
            "inheritance_pass": False, "new_device_result": "NOT_EVALUATED",
            "next_execution_authorized": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorize", required=True, choices=[AUTHORIZATION])
    args = parser.parse_args()
    require(args.authorize == AUTHORIZATION, "AUTHORIZATION_REQUIRED")
    output = ROOT / OUTPUT
    require(not output.exists(), "ONE_SHOT_NAMESPACE_ALREADY_EXISTS")
    output.mkdir(parents=True, exist_ok=False)
    budget, inputs = Budget(), None
    status = {"status": "N0_ENGINEERING_STOP", "inventory_complete": False, "inheritance_pass": False}
    try:
        acceptance_raw = (ROOT / ACCEPTANCE).read_bytes()
        acceptance = json.loads(acceptance_raw)
        require(acceptance["pass"] and acceptance["implementation_sha256"] == digest(Path(__file__).read_bytes()),
                "SYNTHETIC_ACCEPTANCE_REQUIRED")
        contract_raw = (ROOT / CONTRACT).read_bytes()
        require(digest(contract_raw) == acceptance["contract_sha256"], "CONTRACT_REVIEW_IDENTITY_DRIFT")
        contract = json.loads(contract_raw)
        require(set(contract["source_sha256"]) == SOURCE_PATHS, "SOURCE_TEXT_ALLOWLIST_DRIFT")
        pins = {**PINS, **contract["source_sha256"]}
        inputs = Inputs(ROOT, pins, budget)
        write_output(output, "authorization.json", json_bytes({
            "user_instruction": "2026-09-07: proceed with the next step (N0)",
            "scope": "N0 metadata inventory including four selectors on the mixed F1 container",
            "all_row_selectors": SELECTORS, "lawful_fit_payload": F1_PAYLOAD,
            "authorization_token": args.authorize, "caps": CAPS,
            "implementation_sha256": acceptance["implementation_sha256"],
            "synthetic_acceptance_sha256": digest(acceptance_raw), "contract_sha256": digest(contract_raw),
            "numeric_or_training_authorized": False}), budget)
        print("N0_RUNNING_METADATA_ONLY", flush=True)
        status = inventory(inputs, contract, output, budget)
        budget.check()
    except Exception as error:
        status = {"status": "N0_ENGINEERING_STOP", "inventory_complete": False, "inheritance_pass": False,
                  "stop_code": str(error) if isinstance(error, N0Stop) else type(error).__name__,
                  "no_retry": True, "next_execution_authorized": False}
        if status["stop_code"] == "N0_NEEDS_GOVERNED_EXPORT":
            status["status"] = "NEEDS_GOVERNED_EXPORT"
    finally:
        # Reserve bounded terminal receipts even when the cooperative budget stops.
        receipts = {
            "identity_receipt.json": {} if inputs is None else inputs.identities,
            "access_receipt.json": {"tables": {} if inputs is None else inputs.tables,
                "boundary": "Complete authorized containers hashed; CSV parser transiently tokenizes full rows. Only selectors plus lawful-fit research projections are accessed by inventory logic or retained.",
                "scope_of_counters": "This one N0 process. Preparatory source/manifest/schema/identity reads are separate; no preparatory real CSV/GZ scan occurred.",
                "model_forward": 0, "teacher_forward": 0, "backward": 0, "optimizer_steps": 0,
                "numeric_feature_or_representation_containers": 0, "capture_decodes": 0,
                "historical_runners_executed": 0, "network_requests": 0},
            "resource_receipt.json": budget.receipt(), "verdict.json": status,
        }
        for name, value in receipts.items():
            raw = json_bytes(value)
            require(sum(p.stat().st_size for p in output.iterdir()) + len(raw) <= CAPS["output_bytes"] - 4096,
                    "TERMINAL_RECEIPT_CAP_STOP")
            (output / name).write_bytes(raw)
        members = sorted(p for p in output.iterdir() if p.is_file())
        manifest = "".join("%s  %s\n" % (digest(p.read_bytes()), p.name) for p in members)
        (output / "SHA256SUMS").write_text(manifest, encoding="ascii", newline="\n")
    print(json.dumps(status, sort_keys=True), flush=True)
    return 0 if status["inventory_complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
