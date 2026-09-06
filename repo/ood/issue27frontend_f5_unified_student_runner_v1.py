"""Gated F5 P/T/K controller. No real stage runs without its explicit token.

Import is inert. Synthetic integration tests inject in-memory contexts into
the same trajectory and output routines; production inputs have no overrides.
"""
from __future__ import annotations

import argparse
import ast
import csv
import ctypes
import dataclasses
import gzip
import hashlib
import io
import json
import math
import os
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

import issue27frontend_f5_unified_student_v1 as core

ROOT = Path(__file__).resolve().parents[2]
P4 = "runs/frontend_f4_fieldwise_input_feasibility_v1_20260905"
PT = "runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage"
F3 = "runs/frontend_f3_full_fit_l1_identifiability_v1_20260905/f3b_identities.json"
OUTPUT = ROOT / "runs/frontend_f5_unified_student_v1_20260906_local"
IROOT = ROOT / "runs/frontend_f5_implementation_v1_20260906"
AUDIT_PATH = None
TOKENS = {"preflight": "I_AUTHORIZE_F5_REAL_P_TEACHER_ONLY",
          "train": "I_AUTHORIZE_F5_REAL_T_ONE_TRAJECTORY",
          "evaluate": "I_AUTHORIZE_F5_REAL_K_ONCE"}
EXPECTED_CATEGORIES = {"train": {"A1C": 2179, "A0C": 4667, "A0W": 24, "B1N": 68, "B0N": 1722},
                       "val": {"A1C": 3, "A0C": 1478, "A0W": 2, "B1N": 3, "B0N": 3720}}
VAL_SOURCES = {"iotsim-combined-cycle-6_0-0_to_OpenvSwitch-13_6-0",
               "iotsim-domotic-monitor-3_0-0_to_OpenvSwitch-23_3-0", "normal_1.pcap",
               "processed/iotsim-combined-cycle-10.csv"}
B_COUNTS = {"iotsim-combined-cycle": (333, 282), "iotsim-domotic-monitor": (230, 50), "ton-iot-external": (3157, 2995)}
CLAIMS = {"positive_general_inheritance_evidence": False,
          "untouched_confirmation_status": "NOT_IDENTIFIED_OR_OPENED",
          "deployment_authorized": False, "ce_pass": False, "ood_or_commissioning_claim": False}


class ResourceStop(RuntimeError):
    pass


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def persist_audit(audit):
    if AUDIT_PATH is not None:
        core.atomic_json(AUDIT_PATH, audit)


def write_csv(path, rows, fields=None):
    rows = list(rows)
    fields = list(fields or (rows[0].keys() if rows else []))
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    core.atomic_bytes(Path(path), text.getvalue().encode("utf-8"))


def read_csv(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def code_pins():
    paths = [Path(core.__file__), Path(__file__),
             ROOT / "repo/ood/issue27frontend_f5_unified_student_contract_tests_v1.py",
             ROOT / "repo/ood/issue27frontend_f5_unified_student_integration_tests_v1.py",
             ROOT / "repo/ood/issue27frontend_f5_verify_implementation_v1.py",
             ROOT / "scripts/start_frontend_f5_local.ps1", ROOT / "scripts/watch_frontend_f5_local.ps1"]
    return {str(p.relative_to(ROOT)).replace("\\", "/"): core.sha_file(p) for p in paths}


def pilot_kernel_hash(source):
    names = {"Student", "Target", "Context", "require", "reseed", "configure_runtime", "tensor_hash",
             "group_counts", "huber_nonnegative", "context_terms", "batch_loss", "optimizer_for", "train_batch",
             "synthetic_contexts", "synthetic_pilot", "resource_projection"}
    constants = {"SEED", "LABEL_GROUPS", "TEACHER_GROUPS", "ALL_GROUPS", "CAP_SECONDS"}
    selected = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            selected[node.name] = ast.dump(node, include_attributes=False)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in constants:
                    selected[target.id] = ast.dump(node, include_attributes=False)
    core.require(set(selected) == names | constants, "pilot kernel dependency list")
    return digest_json(selected)


def protocol_pins(root=ROOT):
    protocol = root / core.PROTOCOL_REL
    core.require(core.sha_file(protocol) == core.PROTOCOL_SHA, "FROZEN SHA mismatch")
    pins = {}
    for line in protocol.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"\| `([^`]+)` \| `([a-f0-9]{64})` \|", line)
        if match:
            path, sha = match.groups()
            path = path.replace("P4/", P4 + "/", 1) if path.startswith("P4/") else path
            path = path.replace("PT/", PT + "/", 1) if path.startswith("PT/") else path
            core.require(path not in pins and not Path(path).is_absolute() and ".." not in Path(path).parts, "pin path")
            pins[path] = sha
    core.require(len(pins) == 19, "nineteen input identities required")
    return pins


def verify_pins(root=ROOT):
    pins = protocol_pins(root)
    for name, sha in pins.items():
        core.require(core.sha_file(root / name) == sha, "input identity mismatch: " + name)
    return pins


def check_implementation_receipt():
    receipt = read_json(IROOT / "stage_i_acceptance.json")
    core.require(receipt["status"] == "F5_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS", "I acceptance required")
    core.require(receipt["code_pins"] == code_pins(), "I code/test identity drift")
    core.require(receipt["protocol_sha256"] == core.PROTOCOL_SHA, "I protocol drift")
    pilot = read_json(IROOT / "synthetic_resource_pilot.json")
    core.require(pilot["pass"] and receipt["pilot_sha256"] == core.sha_file(IROOT / "synthetic_resource_pilot.json"), "pilot gate")
    core.require(receipt["pilot_numeric_path_sha256"] == pilot_kernel_hash(Path(core.__file__).read_text(encoding="utf-8")), "measured pilot kernel drift")
    return receipt, pilot


def peak_working_set():
    if os.name != "nt":
        raise core.ContractError("production resource monitor is Windows-only")
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    core.require(bool(psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb)), "RAM measurement failed")
    return int(counters.PeakWorkingSetSize)


class Budget:
    """Independent durable time ledger; model rollback never rolls this back."""
    def __init__(self, path, cap, output, resource_fn=peak_working_set, clock=time.time, monotonic=time.monotonic):
        self.path, self.cap, self.output = Path(path), cap, Path(output)
        self.clock, self.monotonic, self.resource_fn = clock, monotonic, resource_fn
        self.peak = 0
        self.last_heartbeat = 0.0
        if self.path.exists():
            previous = read_json(self.path)
            self.elapsed = core.recover_elapsed(previous, self.clock())
        else:
            self.elapsed = 0.0
        self.started = None
        self.closed_monotonic = self.monotonic()
        self.open_utc = None
        self.last_utc = self.clock()
        self.persist()
        self.check()

    def persist(self):
        core.atomic_json(self.path, {"elapsed": self.elapsed, "last_utc": self.last_utc,
                                    "open_batch_utc": self.open_utc, "cap_seconds": self.cap})

    def begin(self):
        core.require(self.started is None, "nested budget block")
        now = self.clock()
        core.require(now >= self.last_utc, "wall clock rollback")
        self.elapsed += self.monotonic() - self.closed_monotonic
        self.open_utc, self.started = now, self.monotonic()
        self.persist()

    def end(self):
        core.require(self.started is not None, "no budget block")
        now, mono = self.clock(), self.monotonic()
        core.require(now >= self.open_utc and mono >= self.started, "clock rollback")
        self.elapsed += mono - self.started
        self.closed_monotonic = mono
        self.last_utc, self.open_utc, self.started = now, None, None
        self.persist()
        self.check()

    def check(self):
        elapsed = self.elapsed + self.monotonic() - (self.started if self.started is not None else self.closed_monotonic)
        self.peak = max(self.peak, self.resource_fn())
        size = sum(p.stat().st_size for p in self.output.rglob("*") if p.is_file())
        if self.clock() - self.last_heartbeat >= 60:
            heartbeat = self.output / "heartbeat.json"
            previous = read_json(heartbeat) if heartbeat.exists() else {}
            core.atomic_json(heartbeat, {**previous, "utc": self.clock(), "phase": self.path.parent.name,
                             "elapsed_seconds": elapsed, "cap_seconds": self.cap, "peak_working_set": self.peak})
            self.last_heartbeat = self.clock()
        if elapsed > self.cap or self.peak > 8 * 1024**3 or size > 5 * 1024**3:
            raise ResourceStop("F5_RESOURCE_NO_GO")


def category(row):
    key = (row["owner"], int(row["label"]), row["teacher_kind"])
    names = {("A", 1, "attack_hard"): "A1C", ("A", 0, "benign_normal"): "A0C",
             ("A", 0, "benign_hard"): "A0W", ("B", 1, "none"): "B1N", ("B", 0, "none"): "B0N"}
    core.require(key in names, "illegal teacher-kind/owner/label")
    return names[key]


def validate_metadata(index, rows, sources, expected=EXPECTED_CATEGORIES,
                      expected_contexts=None, expected_events=205470):
    """Counts and identities BEFORE opening features or teacher arrays."""
    expected_contexts = expected_contexts or {"train": 4984, "val": 4323}
    contexts = {}
    cursor = 0
    splitmap = {"train": "train", "internal_val": "val"}
    for row in index:
        key = row["context_key"]
        core.require(key not in contexts and row["nested_split"] in splitmap, "context duplication/split")
        split = splitmap[row["nested_split"]]
        offset, count = int(row["event_offset"]), int(row["event_count"])
        core.require(offset == cursor and 1 <= count <= 256, "context offsets/length")
        core.require(row["source_group"] in sources[split], "source split violation")
        cursor += count
        contexts[key] = {**row, "split": split, "offset": offset, "count": count, "targets": []}
    core.require(cursor == expected_events, "event conservation")
    seen = set()
    census = {s: Counter() for s in expected}
    for row in rows:
        uid, key = row["uid"], row["context_key"]
        core.require(uid not in seen and key in contexts, "target UID/context mismatch")
        seen.add(uid)
        c = contexts[key]
        core.require(row["source_group"] == c["source_group"] and row["nested_split"] == c["nested_split"], "context crosses source/split")
        position = int(row["event_index"])
        core.require(0 <= position < c["count"] and int(row["prefix_events"]) == position + 1, "target prefix drift")
        core.require(row["feature_width"] == "131" and row["finite"] == "true" and row["roundtrip_exact"] == "true", "F4 input gate")
        c["targets"].append(row)
        census[c["split"]][category(row)] += 1
    core.require(all(c["targets"] for c in contexts.values()), "target-empty context")
    for split in expected:
        core.require(dict(census[split]) == expected[split], "category denominator mismatch: " + split)
        core.require(sum(c["split"] == split for c in contexts.values()) == expected_contexts[split], "context denominator mismatch")
    return contexts, {s: dict(v) for s, v in census.items()}


def load_parent(root, audit):
    index, rows = read_csv(root / P4 / "f4_context_index.csv"), read_csv(root / P4 / "f4_target_audit.csv.gz")
    identities = read_json(root / F3)["nested_split"]
    sources = {"train": set(identities["train_sources"]), "val": set(identities["internal_validation_sources"])}
    core.require(len(sources["train"]) == 13 and sources["val"] == VAL_SOURCES and not sources["train"] & sources["val"], "source identity")
    contexts, census = validate_metadata(index, rows, sources)
    feature_path = root / P4 / "f4_parent_features.f32le"
    core.require(feature_path.stat().st_size == 205470 * 131 * 4, "feature byte size")
    values = np.fromfile(feature_path, dtype="<f4").reshape(205470, 131)
    audit["student_parent_feature_events_numeric"] += len(values)
    persist_audit(audit)
    core.require(np.isfinite(values).all(), "nonfinite F4 parent")
    result = {"train": [], "val": []}
    metadata = {}
    for key, c in sorted(contexts.items()):
        last = max(int(row["event_index"]) for row in c["targets"])
        # Only the authorized terminal prefix is fitted, even if storage has trailing events.
        x = torch.from_numpy(values[c["offset"]:c["offset"] + last + 1].copy())
        targets = []
        for row in c["targets"]:
            targets.append(core.Target(row["uid"], int(row["event_index"]), row["owner"], int(row["label"]),
                                       row["teacher_kind"] in ("attack_hard", "benign_normal")))
            metadata[row["uid"]] = row
        device_keys = {row["device_family"] for row in c["targets"]}
        core.require(len(device_keys) == 1, "context device-family identity")
        result[c["split"]].append(core.Context(key, x, targets, c["split"], next(iter(device_keys))))
    return result, metadata, census


def teacher_materialize(root, contexts, metadata, destination, audit):
    wanted = sorted(t.uid for c in contexts for t in c.targets if t.owner == "A")
    core.require(len(wanted) == len(set(wanted)) == 6870, "teacher whitelist denominator")
    npz_path = root / PT / "ckda_d1_fit_select_embeddings.npz"
    with np.load(npz_path, allow_pickle=False) as archive:
        uid = archive["uid"]
        missing = archive["missing"]
    core.require(uid.shape == missing.shape == (25467,) and missing.dtype == np.bool_, "teacher metadata shape")
    mapping = {str(u): i for i, u in enumerate(uid)}
    core.require(len(mapping) == 25467 and all(u in mapping and not missing[mapping[u]] for u in wanted), "teacher UID/missing mismatch")
    indices = sorted(mapping[u] for u in wanted)
    numeric_audit = {}
    try:
        values = core.selective_npy_rows(npz_path, "representation.npy", indices, (25467, 768), numeric_audit)
    finally:
        audit["teacher_representation_rows_numeric"] += numeric_audit.get("numeric_rows_opened", 0)
        audit["teacher_representation_opaque_bytes"] += numeric_audit.get("opaque_bytes_streamed", 0)
        persist_audit(audit)
    index_row = {index: i for i, index in enumerate(indices)}
    values = values[[index_row[mapping[u]] for u in wanted]]
    allowed = ("normalizer_mean", "normalizer_scale", "p2__0.weight", "p2__0.bias", "p2__3.weight", "p2__3.bias")
    with np.load(root / PT / "ckda_d1_probe_state.npz", allow_pickle=False) as archive:
        state = {name: archive[name] for name in allowed}
    audit["teacher_state_arrays_numeric"] += len(state)
    persist_audit(audit)
    labels = [int(metadata[u]["label"]) for u in wanted]
    correct = [metadata[u]["teacher_kind"] != "benign_hard" for u in wanted]
    raw, scores, strength = core.canonical_teacher(values, state, labels, correct)
    rows = [{"uid": u, "label": labels[i], "teacher_kind": metadata[u]["teacher_kind"],
             "raw_logit": float(raw[i]), "score_float64": float(scores[i]),
             "signed_raw_margin": (2 * labels[i] - 1) * (float(raw[i]) - core.Z0_OLD),
             "strength": strength[i], "strength_clipped": correct[i] and not 0 <= (2 * labels[i] - 1) * (float(raw[i]) - core.Z0_OLD) <= 6}
            for i, u in enumerate(wanted)]
    write_csv(destination, rows)
    return {u: value for u, value in zip(wanted, strength)}


def attach_teacher(contexts, strengths):
    actual = {t.uid for c in contexts for t in c.targets if t.owner == "A"}
    core.require(set(strengths) == actual, "teacher cache UID scope")
    for c in contexts:
        core.require(c.split == "train", "teacher attachment split")
        c.targets = [dataclasses.replace(t, strength=strengths[t.uid]) if t.owner == "A" else t for t in c.targets]


def fresh_audit():
    return {"student_parent_feature_events_numeric": 0, "teacher_representation_rows_numeric": 0,
            "teacher_representation_opaque_bytes": 0, "teacher_state_arrays_numeric": 0,
            "teacher_validation_rows_numeric": 0, "teacher_B_rows_numeric": 0,
            "student_train_target_evaluations": 0, "student_validation_target_evaluations": 0,
            "student_kill_targets_numeric": 0, "kill_evaluation_calls": 0,
            "select_opens": 0, "report_opens": 0, "FINAL_opens": 0, "pcap_opens": 0,
            "network_requests": 0, "real_optimizer_steps": 0}


def protected_metrics(predictions, metadata):
    groups = defaultdict(lambda: {"targets": 0, "hard": 0, "protected_flips": 0, "contexts": set(), "sources": set(),
                                  "tp": 0, "tn": 0, "fp": 0, "fn": 0, "min_signed_margin": None})
    for p in predictions:
        row = metadata[p["uid"]]
        dimensions = (("category", category(row)), ("source", row["source_group"]),
                      ("device_family", row["device_family"]), ("attack_family", row["attack_family"]), ("owner", p["owner"]))
        for kind, name in dimensions:
            g = groups[(p["split"], kind, name)]
            g["targets"] += 1
            g["hard"] += int(p["hard"])
            g["protected_flips"] += int(p["protected"] and p["hard"] != bool(p["label"]))
            g["contexts"].add(p["context"])
            g["sources"].add(row["source_group"])
            g[("tp" if p["hard"] else "fn") if p["label"] else ("fp" if p["hard"] else "tn")] += 1
            margin = (2 * p["label"] - 1) * p["logit"]
            g["min_signed_margin"] = margin if g["min_signed_margin"] is None else min(margin, g["min_signed_margin"])
    return [{"split": split, "group_kind": kind, "group": name, **{k: len(v) if k in ("contexts", "sources") else v for k, v in g.items()},
             "attack_evidence": "INSUFFICIENT" if kind == "attack_family" and len(g["contexts"]) < 3 else "DEVELOPMENT_ONLY"}
            for (split, kind, name), g in sorted(groups.items())]


def per_gate_counts(predictions):
    groups = {}
    for row in predictions:
        key = row["split"] + ":" + row["owner"] + str(row["label"]) + (":protected" if row["protected"] else ":unprotected")
        g = groups.setdefault(key, {"targets": 0, "hard": 0, "flips": 0, "min_signed_margin": None})
        g["targets"] += 1
        g["hard"] += int(row["hard"])
        g["flips"] += int(row["protected"] and row["hard"] != bool(row["label"]))
        signed = (2 * row["label"] - 1) * row["logit"]
        g["min_signed_margin"] = signed if g["min_signed_margin"] is None else min(g["min_signed_margin"], signed)
    return groups


@torch.no_grad()
def full_training_loss(model, contexts, counts, budget=None):
    """Recomputed at one checkpoint; includes an explicitly whole-corpus max."""
    sums = {g: 0.0 for g in core.ALL_GROUPS}
    attack_sums = {g: 0.0 for g in ("A1", "B1")}
    worst = 0.0
    model.eval()
    for start in range(0, len(contexts), 32):
        if budget:
            budget.check()
        batch = contexts[start:start + 32]
        q, sem, _ = model([c.x for c in batch], [c.key for c in batch])
        for c, logits, semantic in zip(batch, q, sem):
            terms, attacks = core.context_terms(c, logits, semantic)
            for g, value in terms.items():
                sums[g] += float(value)
            for g, values in attacks:
                attack_sums[g] += float(values.mean())
                worst = max(worst, float(values.amax()))
    label = sum(sums[g] / counts[g] for g in core.LABEL_GROUPS) / 4
    teacher = sum(sums[g] / counts[g] for g in core.TEACHER_GROUPS) / 2
    attack_mean = sum(attack_sums[g] / counts[g] for g in attack_sums) / 2
    auxiliary = sums["semantic"] / counts["semantic"]
    return {"label": label, "teacher": teacher, "attack_mean": attack_mean,
            "attack_whole_corpus_worst": worst, "semantic": auxiliary,
            "total_diagnostic": label + teacher + attack_mean + worst + .1 * auxiliary}


@torch.no_grad()
def hidden_diagnostics(model, contexts, budget):
    model.eval()
    groups = defaultdict(lambda: {"norms": [], "hashes": []})
    for start in range(0, len(contexts), 32):
        budget.check()
        batch = contexts[start:start + 32]
        _, _, states = model([c.x for c in batch], [c.key for c in batch])
        for c, h in zip(batch, states):
            for t in c.targets:
                vector = h[t.event].numpy()
                key = c.split + ":" + t.owner
                groups[key]["norms"].append(float(np.linalg.norm(vector)))
                groups[key]["hashes"].append(hashlib.sha256(vector.tobytes()).hexdigest())
    return {key: {"targets": len(g["norms"]), "norm_min": min(g["norms"]), "norm_median": float(np.median(g["norms"])),
                  "norm_max": max(g["norms"]), "exact_duplicate_fraction": 1 - len(set(g["hashes"])) / len(g["hashes"]),
                  "descriptive_only": True} for key, g in groups.items()}


def assert_b_denominators(gain, expected=B_COUNTS):
    core.require(set(gain) == set(expected), "B validation device-family identities")
    for key, (targets, contexts) in expected.items():
        core.require((gain[key]["targets"], gain[key]["contexts"]) == (targets, contexts), "B target/context denominator: " + key)


def seal_checkpoint(path, destination):
    core.require(path.exists() and not destination.exists(), "seal identity/existing")
    receipt = {"checkpoint": str(path.resolve()), "sha256": core.sha_file(path), "sealed_utc": time.time()}
    core.atomic_json(destination, receipt)
    return receipt


def require_seal(path, seal):
    core.require(str(path.resolve()) == seal["checkpoint"] and core.sha_file(path) == seal["sha256"], "sealed checkpoint mismatch")


def write_manifest(output):
    files = sorted(p for p in output.rglob("*") if p.is_file() and p.name not in {"SHA256SUMS", "run.lock"})
    lines = [core.sha_file(p) + "  " + p.relative_to(output).as_posix() for p in files]
    core.atomic_bytes(output / "SHA256SUMS", ("\n".join(lines) + "\n").encode())


def run_preflight(root, output, runtime, ireceipt, pilot):
    core.require(not (output / "preflight" / "complete.json").exists(), "P already complete")
    core.require(not (output / "training").exists(), "cannot reopen P after T")
    core.require(shutil.disk_usage(output.parent).free >= 12 * 1024**3, "free space below 12 GiB")
    destination = output / "preflight"
    destination.mkdir(parents=True, exist_ok=True)
    budget = Budget(destination / "time.json", 1800, output)
    budget.begin()
    pins = verify_pins(root)
    audit = fresh_audit()
    contexts, metadata, census = load_parent(root, audit)
    strengths = teacher_materialize(root, contexts["train"], metadata, destination / "teacher.csv", audit)
    attach_teacher(contexts["train"], strengths)
    counts = core.group_counts(contexts["train"])
    core.require(all(counts.values()), "required training groups empty")
    core.reseed()
    initial = core.Student()
    initial_hash = core.tensor_hash(initial.state_dict())
    core.require(initial_hash == pilot["initial_tensor_sha256"], "initial tensor pin")
    identities = {"protocol_sha256": core.PROTOCOL_SHA, "input_pins": pins,
                  "code_pins": code_pins(), "runtime": runtime,
                  "teacher_sha256": core.sha_file(destination / "teacher.csv"),
                  "initial_tensor_sha256": initial_hash, "group_counts": counts,
                  "implementation_receipt_sha256": core.sha_file(IROOT / "stage_i_acceptance.json")}
    core.atomic_json(destination / "identities.json", identities)
    core.atomic_json(destination / "census.json", {"categories": census, "training_eligible_contexts": counts})
    write_csv(destination / "uid_scope.csv", [{"uid": u, "split": row["nested_split"], "source": row["source_group"],
                                               "owner": row["owner"], "context": row["context_key"]} for u, row in sorted(metadata.items())])
    core.atomic_json(output / "role_open_audit.json", audit)
    budget.end()
    core.atomic_json(destination / "complete.json", {"status": "F5_PREFLIGHT_PASS", "identities_sha256": core.sha_file(destination / "identities.json")})
    budget.check()


def load_preflight(root, output, runtime, with_teacher=True):
    destination = output / "preflight"
    complete = read_json(destination / "complete.json")
    core.require(complete["status"] == "F5_PREFLIGHT_PASS" and complete["identities_sha256"] == core.sha_file(destination / "identities.json"), "P not complete/identity")
    identities = read_json(destination / "identities.json")
    core.require(identities["code_pins"] == code_pins() and identities["runtime"] == runtime, "runtime/code change on resume")
    core.require(identities["input_pins"] == verify_pins(root), "input pins changed")
    core.require(identities["teacher_sha256"] == core.sha_file(destination / "teacher.csv"), "teacher cache drift")
    audit = read_json(output / "role_open_audit.json")
    contexts, metadata, _ = load_parent(root, audit)
    if with_teacher:
        strengths = {row["uid"]: None if row["strength"] == "" else float(row["strength"]) for row in read_csv(destination / "teacher.csv")}
        attach_teacher(contexts["train"], strengths)
    core.require(core.group_counts(contexts["train"]) == identities["group_counts"], "eligibility drift")
    core.atomic_json(output / "role_open_audit.json", audit)
    return identities, contexts, metadata, audit


def write_heartbeat(output, phase, progress, budget):
    core.atomic_json(output / "heartbeat.json", {"utc": time.time(), "phase": phase,
                     "epoch": progress.get("epoch"), "batch_cursor": progress.get("cursor"),
                     "durable_steps": progress.get("steps"), "elapsed_seconds": budget.elapsed,
                     "cap_seconds": budget.cap, "peak_working_set": budget.peak})


def train_trajectory(contexts, output, identities, budget, audit, max_epochs=100, stop_after_steps=None,
                     stop_after_epoch_checkpoint=None):
    """Same controller for synthetic integration; production always uses defaults.

    stop_after_steps is a test-only controlled interruption, never exposed in CLI.
    """
    destination = output / "training"
    destination.mkdir(parents=True, exist_ok=True)
    core.require(not (destination / "terminal.json").exists(), "completed T cannot restart")
    core.reseed()
    model = core.Student()
    core.require(core.tensor_hash(model.state_dict()) == identities["initial_tensor_sha256"], "initialization drift")
    optimizer = core.optimizer_for(model)
    checkpoint = destination / "resume.pt"
    marker = destination / "attempt_started.json"
    if marker.exists():
        progress = core.load_checkpoint(checkpoint, model, optimizer, identities)
    else:
        core.require(not checkpoint.exists(), "orphan checkpoint requires engineering review")
        progress = {"epoch": 1, "cursor": 0, "order": [], "steps": 0, "stop_reached": False, "selection": dataclasses.asdict(core.Selection()),
                    "epoch_ledger": [], "batch_ledger": []}
        core.save_checkpoint(checkpoint, model, optimizer, progress, identities)
        core.atomic_json(marker, {"utc": time.time(), "identities_digest": digest_json(identities)})
    require_marker = read_json(marker)
    core.require(require_marker["identities_digest"] == digest_json(identities), "attempt identity")
    lookup = {c.key: c for c in contexts["train"]}
    n, counts = len(lookup), identities["group_counts"]
    core.require(n == len(contexts["train"]), "duplicate train contexts")
    last_heartbeat = 0.0
    while progress["epoch"] <= max_epochs and not progress["stop_reached"]:
        epoch = progress["epoch"]
        order = core.epoch_order(list(lookup), epoch)
        core.require(0 <= progress["cursor"] <= len(order), "resume cursor out of range")
        if progress["cursor"]:
            core.require(progress["order"] == order, "saved epoch order drift")
        progress["order"] = order
        while progress["cursor"] < len(order):
            budget.begin()
            keys = order[progress["cursor"]:progress["cursor"] + 32]
            losses = core.train_batch(model, optimizer, [lookup[k] for k in keys], n, counts)
            progress["cursor"] += len(keys)
            progress["steps"] += 1
            audit["real_optimizer_steps"] += 1
            progress["batch_ledger"].append({"epoch": epoch, "cursor": progress["cursor"], "step": progress["steps"], **losses})
            if progress["steps"] % 25 == 0:
                core.save_checkpoint(checkpoint, model, optimizer, progress, identities)
            if time.monotonic() - last_heartbeat >= 60:
                write_heartbeat(output, "T", progress, budget)
                last_heartbeat = time.monotonic()
            core.atomic_json(output / "role_open_audit.json", audit)
            budget.end()
            if stop_after_steps is not None and progress["steps"] >= stop_after_steps:
                # Test interruption can retain its last checkpoint; production never calls this branch.
                return {"status": "SYNTHETIC_INTERRUPTED", "progress": progress}
        budget.begin()
        train = core.evaluate(model, contexts["train"], budget.check)
        val = core.evaluate(model, contexts["val"], budget.check)
        diagnostic_loss = full_training_loss(model, contexts["train"], counts, budget)
        audit["student_train_target_evaluations"] += train["targets"]
        audit["student_validation_target_evaluations"] += val["targets"]
        selection = core.Selection(**progress["selection"])
        eligible = train["eligible"] and val["eligible"]
        improved, stop = selection.update(epoch, eligible, val["label_loss"])
        progress["selection"] = dataclasses.asdict(selection)
        progress["stop_reached"] = stop or epoch >= max_epochs
        progress["epoch_ledger"].append({"epoch": epoch, "eligible": eligible,
                        "train_label_loss": train["label_loss"], "val_label_loss": val["label_loss"],
                        "train_protected_flips": len(train["violations"]), "val_protected_flips": len(val["violations"]),
                        "train_violations": train["violations"], "val_violations": val["violations"],
                        "gate_counts": per_gate_counts(train["predictions"] + val["predictions"]),
                        "same_checkpoint_training_losses": diagnostic_loss,
                        "improved": improved, "best_epoch": selection.best_epoch})
        if improved:
            core.save_checkpoint(destination / "best.pt", model, optimizer, progress, identities)
        progress["epoch"], progress["cursor"], progress["order"] = epoch + 1, 0, []
        core.save_checkpoint(checkpoint, model, optimizer, progress, identities)
        core.atomic_json(destination / "epoch_ledger.json", progress["epoch_ledger"])
        core.atomic_json(output / "role_open_audit.json", audit)
        budget.end()
        if stop_after_epoch_checkpoint == epoch:
            return {"status": "SYNTHETIC_INTERRUPTED", "progress": progress}
        if stop:
            break
    budget.begin()
    selection = core.Selection(**progress["selection"])
    status = "F5_NO_ELIGIBLE_CHECKPOINT" if selection.best_epoch is None else "F5_T_COMPLETE_CHECKPOINT_SELECTED"
    if selection.best_epoch is not None:
        seal_checkpoint(destination / "best.pt", destination / "selected_seal.json")
    terminal = {"status": status, "selected_epoch": selection.best_epoch, "epochs": selection.last_epoch,
                "steps": progress["steps"], "selection": dataclasses.asdict(selection), "complete": True}
    budget.end()
    core.atomic_json(destination / "terminal.json", terminal)
    budget.check()
    return terminal


def run_train(root, output, runtime):
    destination = output / "training"
    destination.mkdir(parents=True, exist_ok=True)
    budget = Budget(destination / "time.json", core.CAP_SECONDS, output)
    budget.begin()
    identities, contexts, metadata, audit = load_preflight(root, output, runtime)
    budget.end()
    terminal = train_trajectory(contexts, output, identities, budget, audit)
    if terminal["status"] == "F5_NO_ELIGIBLE_CHECKPOINT":
        core.atomic_json(output / "verdict.json", {**terminal, **CLAIMS, "B_gain": "NOT_EVALUATED", "K": "NOT_EVALUATED"})
    return terminal


def load_kill(root, audit):
    index = read_csv(root / P4 / "f4_kill_only_index.csv")
    core.require(len(index) == 5 and len({r["uid"] for r in index}) == 5, "five-row kill denominator")
    path = root / P4 / "f4_kill_only_features.f32le"
    count = sum(int(row["event_count"]) for row in index)
    core.require(path.stat().st_size == count * 131 * 4, "kill byte length")
    features = np.fromfile(path, dtype="<f4").reshape(count, 131)
    audit["student_kill_targets_numeric"] += 5
    persist_audit(audit)
    core.require(np.isfinite(features).all(), "kill nonfinite features")
    contexts, cursor = [], 0
    for row in index:
        n = int(row["event_count"])
        core.require(int(row["event_offset"]) == cursor and 1 <= n <= 256, "kill offsets")
        target = core.Target(row["uid"], n - 1, "A", 1, True, None)
        contexts.append(core.Context(row["uid"], torch.from_numpy(features[cursor:cursor+n].copy()), [target], "kill"))
        cursor += n
    return contexts


def guarded_kill(model, checkpoint, seal, destination, audit, gain, loader):
    """Loader is not called until utility passed and checkpoint identity is sealed."""
    if not gain or not all(g["pass"] for g in gain.values()):
        return None
    require_seal(checkpoint, seal)
    marker = destination / "kill_open_started.json"
    core.require(not marker.exists(), "kill-only already opened; no automatic retry")
    core.atomic_json(marker, {"utc": time.time(), "selected_sha256": seal["sha256"]})
    kill = loader()
    core.require(len(kill) == 5 and len({c.targets[0].uid for c in kill}) == 5, "kill caller denominator")
    model.eval()
    with torch.no_grad():
        logits, _, _ = model([c.x for c in kill], [c.key for c in kill])
    kill_hard = [bool(q[c.targets[0].event] >= 0) for c, q in zip(kill, logits)]
    audit["kill_evaluation_calls"] += 1
    persist_audit(audit)
    write_csv(destination / "kill_predictions.csv", [{"uid": c.targets[0].uid,
               "logit": float(q[c.targets[0].event]), "hard": hard} for c, q, hard in zip(kill, logits, kill_hard)])
    return kill_hard


def run_evaluate(root, output, runtime):
    destination = output / "evaluation"
    destination.mkdir(parents=True, exist_ok=True)
    budget = Budget(destination / "time.json", 1800, output)
    budget.begin()
    terminal = read_json(output / "training" / "terminal.json")
    core.require(terminal["status"] == "F5_T_COMPLETE_CHECKPOINT_SELECTED", "no completed selected trajectory")
    identities, contexts, metadata, audit = load_preflight(root, output, runtime, with_teacher=False)
    checkpoint = output / "training" / "best.pt"
    seal = read_json(output / "training" / "selected_seal.json")
    require_seal(checkpoint, seal)
    core.reseed()
    model = core.Student()
    optimizer = core.optimizer_for(model)
    core.load_checkpoint(checkpoint, model, optimizer, identities)
    train, val = core.evaluate(model, contexts["train"], budget.check), core.evaluate(model, contexts["val"], budget.check)
    core.require(train["eligible"] and val["eligible"], "selected checkpoint gate drift")
    audit["student_train_target_evaluations"] += train["targets"]
    audit["student_validation_target_evaluations"] += val["targets"]
    predictions = train["predictions"] + val["predictions"]
    core.require(len(predictions) == len({p["uid"] for p in predictions}) == 13866, "final parent denominator")
    write_csv(destination / "parent_predictions.csv", sorted(predictions, key=lambda r: r["uid"]))
    write_csv(destination / "per_group_metrics.csv", protected_metrics(predictions, metadata))
    core.atomic_json(destination / "hidden_diagnostics.json", hidden_diagnostics(model, contexts["train"] + contexts["val"], budget))
    gain = core.benign_gain(predictions)
    assert_b_denominators(gain)
    core.atomic_json(destination / "B_gain.json", gain)
    train_as_val = [{**p, "split": "val"} for p in train["predictions"]]
    core.atomic_json(destination / "B_train_utility_descriptive.json", core.benign_gain(train_as_val))
    passed = all(g["pass"] for g in gain.values())
    kill_hard = guarded_kill(model, checkpoint, seal, destination, audit, gain, lambda: load_kill(root, audit))
    status = core.terminal_status(True, True, passed, kill_hard)
    core.atomic_json(output / "role_open_audit.json", audit)
    budget.end()
    verdict = {"status": status, "selected_sha256": seal["sha256"], "selected_epoch": terminal["selected_epoch"],
               "B_gain": gain, "K": "NOT_EVALUATED" if kill_hard is None else {"hard": sum(kill_hard), "targets": 5}, **CLAIMS}
    core.atomic_json(output / "verdict.json", verdict)
    budget.check()
    return verdict


def main():
    global AUDIT_PATH
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=tuple(TOKENS), required=True)
    parser.add_argument("--authorization", required=True)
    args = parser.parse_args()
    core.require(args.authorization == TOKENS[args.stage], "explicit stage authorization required")
    # CLI token is an operator confirmation, not a substitute for user authority.
    runtime = core.configure_runtime()
    ireceipt, pilot = check_implementation_receipt()
    core.require(runtime == pilot["runtime"], "pilot runtime mismatch")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH = OUTPUT / "role_open_audit.json"
    core.require(not (OUTPUT / "verdict.json").exists(), "finished result cannot be overwritten")
    core.require(not (OUTPUT / "engineering_failure.json").exists() and not (OUTPUT / "resource_stop.json").exists(), "prior stop requires review")
    lock = OUTPUT / "run.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump({"pid": os.getpid(), "stage": args.stage, "utc": time.time()}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        core.atomic_json(OUTPUT / ("authorization_" + args.stage + ".json"), {"stage": args.stage, "confirmation": args.authorization, "utc": time.time()})
        if args.stage == "preflight":
            run_preflight(ROOT, OUTPUT, runtime, ireceipt, pilot)
            result = {"status": "F5_PREFLIGHT_PASS"}
        elif args.stage == "train":
            result = run_train(ROOT, OUTPUT, runtime)
        else:
            result = run_evaluate(ROOT, OUTPUT, runtime)
        write_manifest(OUTPUT)
        print(json.dumps(result), flush=True)
    except ResourceStop as error:
        if (OUTPUT / "verdict.json").exists():
            (OUTPUT / "verdict.json").replace(OUTPUT / "unsealed_verdict.resource-only.json")
        core.atomic_json(OUTPUT / "resource_stop.json", {"status": "F5_RESOURCE_NO_GO", "stage": args.stage, "error": str(error)})
        raise
    except Exception as error:
        if (OUTPUT / "verdict.json").exists():
            (OUTPUT / "verdict.json").replace(OUTPUT / "unsealed_verdict.engineering-only.json")
        core.atomic_json(OUTPUT / "engineering_failure.json", {"stage": args.stage, "error": type(error).__name__ + ": " + str(error), "scientific_verdict": None})
        raise
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
