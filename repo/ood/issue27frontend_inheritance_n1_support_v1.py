"""N1 bounded I/O and train-only contracts. Import performs no experiment I/O."""
from __future__ import annotations

import csv
import ctypes
import gzip
import hashlib
import io
import json
import os
import re
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STEM = "frontend_inheritance_n1_"
DESIGN = "runs/mainline_docs/" + STEM + "fixed_terminal_head_feasibility_frozen_20260908.md"
PINS_FILE = "runs/mainline_docs/" + STEM + "input_and_runtime_pins_20260908.json"
DESIGN_SHA = "9826ceee1befd63258b563f5741da2ae69e70f810e009ae728777054529819c5"
PINS_SHA = "a78014b1977f27d85ca34180d8254b9a16b61e0d04d88aa11d517ccc7eb25a97"
IMPLEMENTATION = "runs/frontend_inheritance_n1_implementation_v2_20260908"
REAL_OUTPUT = "runs/frontend_inheritance_n1_fixed_terminal_head_v1_20260908"
AUTHORIZATION = "I_AUTHORIZE_ONE_REAL_N1_FIT_AND_RESTRICTED_CHECKPOINT_CONTAINER_ACCESS"
F4 = "runs/frontend_f4_fieldwise_input_feasibility_v1_20260905"
F5 = "runs/frontend_f5_unified_student_v1_20260906_local"
F3 = "runs/frontend_f3_full_fit_l1_identifiability_v1_20260905/f3b_identities.json"
N0 = "runs/frontend_inheritance_n0_inventory_v1_20260907/inventory_summary.json"
FEATURES = F4 + "/f4_parent_features.f32le"
CHECKPOINT = F5 + "/training/resume.pt"
CORE = "repo/ood/issue27frontend_f5_unified_student_v1.py"
CODE = tuple("repo/ood/issue27frontend_inheritance_n1_" + name + "_v1.py"
             for name in ("support", "math", "runner", "control", "tests", "verify")) + (
                 "scripts/start_frontend_inheritance_n1_local.ps1",
                 "scripts/show_frontend_inheritance_n1_status.ps1")
CAPS = {"wall_seconds": 1800, "memory_bytes": 8 * 1024**3,
        "output_bytes": 100 * 1024**2, "reserve_bytes": 1024**2,
        "lp_calls": 1, "passes": 2, "batches": 312, "targets": 17320,
        "contexts": 9968, "events": 410940, "padded_slots": 2551808}
EXPECTED = {"A1C": 2179, "A0C": 4667, "A0W": 24, "B1N": 68, "B0N": 1722}
CATEGORIES = {("A", "1", "attack_hard"): "A1C", ("A", "0", "benign_normal"): "A0C",
              ("A", "0", "benign_hard"): "A0W", ("B", "1", "none"): "B1N",
              ("B", "0", "none"): "B0N"}
PROTECTED = {"A1C", "A0C", "B1N"}
INDEX_COLUMNS = ("context_key", "source_group", "nested_split", "event_offset", "event_count")
TARGET_COLUMNS = ("uid", "context_key", "event_index", "source_group", "nested_split", "owner",
                  "label", "teacher_kind", "device_family", "attack_family", "l1_prefix_sha256",
                  "feature_prefix_sha256", "prefix_events", "old_all_unk", "roundtrip_exact",
                  "finite", "feature_width")
SCOPE_COLUMNS = ("uid", "split", "source", "owner", "context")
SELECTORS = {"target": ("uid", "nested_split", "context_key"),
             "scope": ("uid", "split", "context")}
PAYLOAD = {"target": tuple(k for k in TARGET_COLUMNS if k not in
                          {"uid", "nested_split", "context_key", "l1_prefix_sha256", "old_all_unk"}),
           "scope": ("source", "owner")}


class Stop(RuntimeError):
    """Stable codes only; no uncontrolled input values in receipts."""


def require(condition, code):
    if not condition:
        raise Stop(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def sha_file(path, check=lambda: None):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while True:
            check()
            block = stream.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def integer(value):
    require(isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value), "INTEGER_DRIFT")
    return int(value)


def relative_name(name):
    require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_./-]+", name)
            and not name.startswith("/") and all(p not in {"", ".", ".."} for p in name.split("/")),
            "PATH_DRIFT")
    return name


def manifest(raw):
    result = {}
    for line in raw.decode("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_./-]+)", line)
        require(match is not None, "MANIFEST_SCHEMA_DRIFT")
        sha, name = match.groups()
        relative_name(name)
        require(name not in result, "MANIFEST_DUPLICATE")
        result[name] = sha
    return result


def frozen_design(root=ROOT):
    for name, expected in ((DESIGN, DESIGN_SHA), (PINS_FILE, PINS_SHA)):
        path = root / name
        require(sha_file(path) == expected, "FROZEN_DESIGN_DRIFT")
        require(manifest(path.with_suffix(".sha256").read_bytes()) == {path.name: expected},
                "DESIGN_SIDECAR_DRIFT")
    return json.loads((root / PINS_FILE).read_text(encoding="utf-8"))


def peak_memory(pid=None):
    require(os.name == "nt", "WINDOWS_MONITOR_REQUIRED")
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
             "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
             "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.GetCurrentProcess() if pid is None else kernel.OpenProcess(0x410, False, pid)
    require(bool(handle), "MEMORY_PROCESS_HANDLE")
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    try:
        require(psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb), "MEMORY_READ_FAILED")
        return max(int(counters.PeakWorkingSetSize), int(counters.PeakPagefileUsage))
    finally:
        if pid is not None:
            kernel.CloseHandle(handle)


class Budget:
    def __init__(self, clock=time.monotonic, memory=peak_memory, caps=None, start=None):
        self.clock, self.memory = clock, memory
        self.caps = dict(CAPS if caps is None else caps)
        self.start = clock() if start is None else start
        self.peak, self.output_bytes = 0, 0
        self.last_sample = -float("inf")
        self.counts = Counter()

    def check(self):
        now = self.clock()
        if now - self.last_sample >= 0.05:
            self.peak = max(self.peak, self.memory())
            self.last_sample = now
        require(now - self.start <= self.caps["wall_seconds"], "GLOBAL_WALL_STOP")
        require(self.peak <= self.caps["memory_bytes"], "GLOBAL_MEMORY_STOP")
        require(self.output_bytes <= self.caps["output_bytes"] - self.caps["reserve_bytes"], "GLOBAL_OUTPUT_STOP")
        for key, value in self.counts.items():
            require(value <= self.caps[key], "ACTION_CAP_" + key.upper())

    def charge(self, **values):
        self.counts.update(values)
        self.check()

    def receipt(self):
        return {"elapsed_seconds": self.clock() - self.start, "peak_memory_bytes": self.peak,
                "output_bytes": self.output_bytes, "counts": dict(self.counts), "caps": self.caps}


class Writer:
    def __init__(self, path, budget):
        self.path, self.budget = Path(path), budget
        self.members = {}

    def write(self, name, data):
        relative_name(name)
        require(name not in self.members and not (self.path / name).exists(), "OUTPUT_ALREADY_EXISTS")
        self.budget.output_bytes += len(data)
        self.budget.check()
        destination = self.path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        self.members[name] = digest(data)
        return self.members[name]

    def json(self, name, value):
        return self.write(name, json_bytes(value))


def project_train(get, kind):
    selectors = {key: get(key) for key in SELECTORS[kind]}
    split = selectors["nested_split" if kind == "target" else "split"]
    require(split in {"train", "internal_val"} and bool(selectors["uid"]), "SELECTOR_DRIFT")
    return selectors, ({key: get(key) for key in PAYLOAD[kind]} if split == "train" else None)


def scan_csv(blob, kind, audit, check=lambda: None):
    columns = {"target": TARGET_COLUMNS, "scope": SCOPE_COLUMNS, "index": INDEX_COLUMNS}[kind]
    source = gzip.GzipFile(fileobj=io.BytesIO(blob)) if kind == "target" else io.BytesIO(blob)
    audit.update(rows_tokenized=0, bytes_decompressed=0, column_accesses=Counter(),
                 excluded_payload_cells_transiently_tokenized=0, train_payload_rows_retained=0)
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
            require(audit["rows_tokenized"] <= 13866 and len(row) == len(columns), "CSV_ROW_DRIFT")
            def get(key):
                audit["column_accesses"][key] += 1
                return row[positions[key]]
            if kind == "index":
                select = {key: get(key) for key in columns}
                payload, uid = select, select["context_key"]
            else:
                select, payload = project_train(get, kind)
                uid = select["uid"]
            require(uid and uid not in seen, "DUPLICATE_UID_OR_CONTEXT")
            seen.add(uid)
            selectors[uid] = select
            if payload is not None:
                payloads[uid] = {**select, **payload}
                audit["train_payload_rows_retained"] += int(kind != "index")
            elif kind != "index":
                audit["excluded_payload_cells_transiently_tokenized"] += len(columns) - len(SELECTORS[kind])
    except (csv.Error, UnicodeError, EOFError, gzip.BadGzipFile):
        raise Stop("METADATA_PARSE_STOP") from None
    finally:
        source.close()
    return selectors, payloads


def validate_metadata(index, target_select, targets, scope_select, scope, sources,
                      expected=EXPECTED, context_count=4984, all_contexts=9307,
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
        if split == "train":
            contexts[key] = {"key": key, "offset": offset, "count": count,
                             "source": row["source_group"], "targets": []}
    require(cursor == all_events and len(contexts) == context_count, "CONTEXT_EVENT_DENOMINATOR")
    require({c["source"] for c in contexts.values()} == sources["train"], "TRAIN_SOURCE_COVERAGE")
    represented = set()
    for uid, row in target_select.items():
        peer = scope_select[uid]
        key = row["context_key"]
        require(key in index and peer["context"] == key and peer["split"] == row["nested_split"]
                == index[key]["nested_split"], "SELECTOR_CONTEXT_JOIN")
        represented.add(key)
    require(represented == set(index), "EMPTY_CONTEXT")
    require(set(targets) == set(scope) == {uid for uid, row in target_select.items()
                                        if row["nested_split"] == "train"}, "TRAIN_UID_JOIN")
    counts = Counter()
    for uid, row in targets.items():
        c = contexts[row["context_key"]]
        require(row["source_group"] == c["source"] == scope[uid]["source"]
                and row["owner"] == scope[uid]["owner"], "TRAIN_METADATA_JOIN")
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
        require(bool(c["targets"]), "EMPTY_TRAIN_CONTEXT")
        require(len({r["device_family"] for r in c["targets"]}) == 1, "CONTEXT_DEVICE_DRIFT")
        c["length"] = max(r["event"] for r in c["targets"]) + 1
        c["byte_offset"], c["byte_length"] = c["offset"] * 524, c["length"] * 524
        selected_events += c["length"]
    require(selected_events <= all_events, "SELECTED_EVENT_CAP")
    return [contexts[key] for key in sorted(contexts)], dict(counts), selected_events


class Inputs:
    def __init__(self, root, pins, budget, audit):
        self.root, self.pins, self.budget, self.audit = Path(root), pins, budget, audit
        self.verified, self.reads = {}, set()

    def path(self, name):
        require(name in self.pins, "UNAUTHORIZED_INPUT")
        relative_name(name)
        path = self.root / name
        require(path.resolve().is_relative_to(self.root.resolve()), "INPUT_PATH_ESCAPE")
        return path

    def verify(self, name):
        path = self.path(name)
        require(name not in self.verified, "REPEATED_INPUT_HASH")
        require(sha_file(path, self.budget.check) == self.pins[name], "INPUT_HASH_DRIFT")
        self.verified[name] = self.pins[name]
        self.audit.setdefault("opaque_hashes", []).append(name)
        return path

    def read(self, name):
        require(name in self.verified and name not in self.reads, "UNVERIFIED_OR_REPEATED_INPUT")
        require(name not in {FEATURES, CHECKPOINT}, "NUMERIC_CONTAINER_REQUIRES_RESTRICTED_READER")
        path = self.path(name)
        require(path.stat().st_size <= 32 * 1024**2, "INPUT_SIZE_STOP")
        self.budget.check()
        raw = path.read_bytes()
        require(digest(raw) == self.pins[name], "INPUT_CHANGED_AFTER_HASH")
        self.reads.add(name)
        self.audit.setdefault("metadata_containers_read", []).append(name)
        return raw
