"""F5 deterministic numerical core. This CLI is synthetic-only, not a real runner.

No module import reads experiment artifacts. A real P/T/K orchestration layer
must be separately completed and authorized before consuming this core.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import platform
import random
import statistics
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence, pad_sequence

SEED = 2705
PROTOCOL_SHA = "b8069e6556d6719eef3e689b1ab9a8676c24a00a82e8b5f810a401c9c42786b6"
PROTOCOL_REL = "runs/mainline_docs/frontend_f5_unified_student_one_shot_training_frozen_20260906.md"
LABEL_GROUPS = ("A1", "A0", "B1", "B0")
TEACHER_GROUPS = ("T1", "T0")
ALL_GROUPS = LABEL_GROUPS + TEACHER_GROUPS + ("semantic",)
CAP_SECONDS = 47494.34391
THETA_OLD = 0.065159872174263
Z0_OLD = -2.6635317063752599


class ContractError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    data = json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    atomic_bytes(path, data)


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def configure_runtime() -> dict:
    expected = {"PYTHONHASHSEED": "2705", "OMP_NUM_THREADS": "4", "MKL_NUM_THREADS": "4"}
    require(all(os.environ.get(k) == v for k, v in expected.items()), "pre-interpreter environment mismatch")
    require(platform.python_version() == "3.9.13", "Python pin mismatch")
    require(np.__version__ == "2.0.2" and torch.__version__ == "2.8.0+cpu", "package pin mismatch")
    torch.set_num_threads(4)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    reseed()
    return {"python": platform.python_version(), "executable": sys.executable,
            "numpy": np.__version__, "torch": torch.__version__, "os": platform.platform(),
            "processor": platform.processor(), "threads": torch.get_num_threads(),
            "interop_threads": torch.get_num_interop_threads(), "environment": expected}


def reseed() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)


class Student(nn.Module):
    def __init__(self):
        super().__init__()
        self.event_projection = nn.Linear(131, 64, bias=True)
        self.event_activation = nn.GELU(approximate="none")
        self.encoder = nn.GRU(64, 128, num_layers=1, bias=True, batch_first=True,
                              dropout=0.0, bidirectional=False)
        self.head_hidden = nn.Linear(128, 64, bias=True)
        self.head_activation = nn.GELU(approximate="none")
        self.head_output = nn.Linear(64, 1, bias=True)
        self.semantic_head = nn.Linear(128, 27, bias=True)
        require(sum(p.numel() for p in self.parameters()) == 94748, "model identity")

    def forward(self, sequences: Sequence[torch.Tensor], keys: Sequence[str]):
        require(len(sequences) == len(keys) > 0 and len(set(keys)) == len(keys), "batch identities")
        for x in sequences:
            require(x.dtype == torch.float32 and x.device.type == "cpu", "input dtype/device")
            require(x.ndim == 2 and x.shape[1] == 131 and 1 <= len(x) <= 256, "input dimensions")
            require(bool(torch.isfinite(x).all()), "nonfinite input")
        order = sorted(range(len(keys)), key=lambda i: (-len(sequences[i]), keys[i]))
        lengths = [len(sequences[i]) for i in order]
        padded = pad_sequence([sequences[i] for i in order], batch_first=True)
        embedded = self.event_activation(self.event_projection(padded))
        packed = pack_padded_sequence(embedded, lengths, batch_first=True, enforce_sorted=True)
        encoded, _ = self.encoder(packed)  # h0 is reset; never shared across contexts.
        hidden, _ = pad_packed_sequence(encoded, batch_first=True)
        states = [None] * len(keys)
        logits = [None] * len(keys)
        semantic = [None] * len(keys)
        for sorted_i, original_i in enumerate(order):
            h = hidden[sorted_i, :lengths[sorted_i]]
            q = self.head_output(self.head_activation(self.head_hidden(h))).squeeze(-1)
            require(bool(torch.isfinite(h).all() and torch.isfinite(q).all()), "nonfinite student output")
            states[original_i], logits[original_i] = h, q
            semantic[original_i] = self.semantic_head(h)
        return logits, semantic, states

    def inference_state(self):
        return {k: v.detach().clone() for k, v in self.state_dict().items() if not k.startswith("semantic_head.")}


def tensor_hash(state: dict) -> str:
    h = hashlib.sha256()
    for name, value in sorted(state.items()):
        a = value.detach().cpu().contiguous().numpy()
        h.update(name.encode() + b"\0" + str(a.dtype).encode() + str(a.shape).encode())
        h.update(a.tobytes())
    return h.hexdigest()


@dataclass(frozen=True)
class Target:
    uid: str
    event: int
    owner: str
    label: int
    teacher_correct: bool = False
    strength: Optional[float] = None


@dataclass
class Context:
    key: str
    x: torch.Tensor
    targets: List[Target]
    split: str = "train"
    device: str = "synthetic"

    def validate(self):
        require(self.split in ("train", "val", "kill"), "unknown split")
        require(bool(self.targets), "empty target context")
        require(len({t.uid for t in self.targets}) == len(self.targets), "duplicate target UID")
        for t in self.targets:
            require(t.owner in ("A", "B") and t.label in (0, 1), "target role")
            require(0 <= t.event < len(self.x), "target causal offset")
            if t.strength is not None:
                require(self.split == "train" and t.owner == "A" and t.teacher_correct,
                        "forbidden numeric teacher strength")
                require(math.isfinite(t.strength) and 0 <= t.strength <= 6, "teacher strength domain")


def group_counts(contexts: Sequence[Context]) -> Dict[str, int]:
    require(len({c.key for c in contexts}) == len(contexts), "duplicate contexts")
    seen = set()
    counts = dict.fromkeys(ALL_GROUPS, 0)
    for c in contexts:
        c.validate()
        groups = set()
        for t in c.targets:
            require(t.uid not in seen, "duplicate UID across contexts")
            seen.add(t.uid)
            groups.add(t.owner + str(t.label))
            if t.owner == "A" and t.teacher_correct:
                groups.add("T" + str(t.label))
        if max(t.event for t in c.targets) >= 1:
            groups.add("semantic")
        for g in groups:
            counts[g] += 1
    return counts


def huber_nonnegative(v: torch.Tensor):
    return torch.where(v <= 1, 0.5 * v.square(), v - 0.5)


def context_terms(c: Context, q: torch.Tensor, semantic: torch.Tensor):
    require(c.split == "train", "validation/kill cannot supply training gradients")
    c.validate()
    terms = {g: [] for g in ALL_GROUPS}
    attacks = []
    z = q[torch.tensor([t.event for t in c.targets], dtype=torch.int64)]
    y = z.new_tensor([float(t.label) for t in c.targets])
    label_values = F.binary_cross_entropy_with_logits(z, y, reduction="none") / math.log(2)
    for g in LABEL_GROUPS:
        mask = torch.tensor([t.owner + str(t.label) == g for t in c.targets], dtype=torch.bool)
        if bool(mask.any()):
            terms[g].append(label_values[mask].mean())
    for g in TEACHER_GROUPS:
        indices = [i for i, t in enumerate(c.targets) if t.owner == "A" and t.teacher_correct and "T" + str(t.label) == g]
        if indices:
            require(all(c.targets[i].strength is not None for i in indices), "missing authorized teacher")
            strengths = z.new_tensor([c.targets[i].strength for i in indices])
            v = F.relu(strengths - (2 * y[indices] - 1) * z[indices]) / 2
            terms[g].append(huber_nonnegative(v).mean())
    for g in ("A1", "B1"):
        indices = [i for i, t in enumerate(c.targets) if t.label and t.owner + "1" == g]
        if indices:
            attacks.append((g, huber_nonnegative(F.relu(1 - z[indices]))))
    last = max(t.event for t in c.targets)
    if last:
        losses = []
        for output_start, width, feature_start in ((0, 7, 39), (7, 3, 4), (10, 8, 68), (18, 9, 76)):
            labels = c.x[1:last + 1, feature_start:feature_start + width].argmax(dim=1)
            losses.append(F.cross_entropy(semantic[:last, output_start:output_start + width], labels,
                                          reduction="none") / math.log(width))
        terms["semantic"].append(torch.stack(losses).mean())
    return {g: torch.stack(values).mean() for g, values in terms.items() if values}, attacks


def batch_loss(contexts: Sequence[Context], logits, semantic, global_n: int, counts: dict):
    require(global_n >= len(contexts) > 0 and all(counts[g] > 0 for g in ALL_GROUPS), "global eligibility")
    zero = logits[0].sum() * 0
    sums = {g: zero for g in ALL_GROUPS}
    attack_sums = {g: zero for g in ("A1", "B1")}
    all_attacks = []
    for c, q, sem in zip(contexts, logits, semantic):
        terms, attacks = context_terms(c, q, sem)
        for g, value in terms.items():
            sums[g] = sums[g] + value
        for g in attack_sums:
            values = [v for group, v in attacks if group == g]
            if values:
                attack_sums[g] = attack_sums[g] + torch.cat(values).mean()
        all_attacks.extend(v for _, v in attacks)
    def mean(g, value):
        return value * (global_n / (len(contexts) * counts[g]))
    label = sum(mean(g, sums[g]) for g in LABEL_GROUPS) / 4
    teacher = sum(mean(g, sums[g]) for g in TEACHER_GROUPS) / 2
    attack_mean = sum(mean(g, attack_sums[g]) for g in attack_sums) / 2
    worst = torch.cat(all_attacks).amax() if all_attacks else zero
    aux = mean("semantic", sums["semantic"])
    total = label + teacher + attack_mean + worst + 0.1 * aux
    require(bool(torch.isfinite(total)), "nonfinite loss")
    return total, {"label": label, "teacher": teacher, "attack_mean": attack_mean,
                   "attack_batch_worst": worst, "semantic": aux}


def optimizer_for(model):
    return torch.optim.AdamW(model.parameters(), lr=0.001, betas=(0.9, 0.999), eps=1e-8,
                            weight_decay=0.0001, amsgrad=False, foreach=False, fused=False)


def train_batch(model, optimizer, contexts, n, counts):
    require(all(c.split == "train" for c in contexts), "nontrain batch")
    model.train()
    optimizer.zero_grad(set_to_none=True)
    logits, semantic, _ = model([c.x for c in contexts], [c.key for c in contexts])
    loss, pieces = batch_loss(contexts, logits, semantic, n, counts)
    loss.backward()
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
    optimizer.step()
    require(all(bool(torch.isfinite(p).all()) for p in model.parameters()), "nonfinite updated parameter")
    return {k: float(v.detach()) for k, v in pieces.items()} | {"total": float(loss.detach()), "grad_norm": float(norm)}


def epoch_order(keys: Sequence[str], epoch: int):
    require(epoch >= 1 and len(set(keys)) == len(keys), "epoch order identity")
    ordered = sorted(keys)
    generator = torch.Generator(device="cpu").manual_seed(SEED + epoch)
    return [ordered[i] for i in torch.randperm(len(keys), generator=generator).tolist()]


def canonical_teacher(representation, state, labels, correct):
    """Pure numerical function; caller must enforce the 6870-row whitelist."""
    z = np.asarray(representation)
    require(z.dtype == np.float32 and z.ndim == 2 and z.shape[1] == 768, "teacher representation shape")
    shapes = {"normalizer_mean": (768,), "normalizer_scale": (768,),
              "p2__0.weight": (128, 769), "p2__0.bias": (128,),
              "p2__3.weight": (1, 128), "p2__3.bias": (1,)}
    require(set(state) == set(shapes), "probe allowlist")
    for k, shape in shapes.items():
        require(state[k].shape == shape and np.isfinite(state[k]).all(), "probe shape/nonfinite")
    require(np.isfinite(z).all() and (state["normalizer_scale"] > 0).all(), "teacher finite/scale")
    normalized = (z.astype(np.float64) - state["normalizer_mean"].astype(np.float64)) / state["normalizer_scale"].astype(np.float64)
    x = torch.from_numpy(np.concatenate((normalized, np.zeros((len(z), 1))), axis=1).astype(np.float32))
    with torch.no_grad():
        hidden = F.relu(F.linear(x, torch.as_tensor(state["p2__0.weight"], dtype=torch.float32),
                                torch.as_tensor(state["p2__0.bias"], dtype=torch.float32)))
        raw = F.linear(hidden, torch.as_tensor(state["p2__3.weight"], dtype=torch.float32),
                       torch.as_tensor(state["p2__3.bias"], dtype=torch.float32)).flatten()
        scores = raw.sigmoid().numpy().astype(np.float64)
    require(bool(torch.isfinite(raw).all()), "nonfinite raw teacher")
    labels = np.asarray(labels, dtype=np.int64)
    correct = np.asarray(correct, dtype=bool)
    require(labels.shape == correct.shape == (len(z),), "teacher kind shape")
    require(np.array_equal((scores >= THETA_OLD) == labels.astype(bool), correct), "teacher kind drift")
    strengths = np.clip((2 * labels - 1) * (raw.numpy().astype(np.float64) - Z0_OLD), 0, 6).astype(np.float32)
    return raw.numpy(), scores, [float(s) if ok else None for s, ok in zip(strengths, correct)]


def selective_npy_rows(npz_path: Path, member: str, indices: Sequence[int], expected_shape, audit: dict):
    """Stream opaque unrequested bytes; never np.load the full representation."""
    require(list(indices) == sorted(set(indices)), "selective row order")
    require(all(0 <= i < expected_shape[0] for i in indices), "selective row range")
    selected = []
    with zipfile.ZipFile(npz_path) as archive:
        require(archive.namelist().count(member) == 1, "duplicate/absent NPZ member")
        with archive.open(member) as stream:
            version = np.lib.format.read_magic(stream)
            if version == (1, 0):
                shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream)
            elif version == (2, 0):
                shape, fortran, dtype = np.lib.format.read_array_header_2_0(stream)
            else:
                raise ContractError("unsupported NPY version")
            require(tuple(shape) == tuple(expected_shape) and not fortran and dtype == np.dtype("<f4"), "NPY contract")
            wanted = set(indices)
            row_bytes = expected_shape[1] * 4
            for i in range(expected_shape[0]):
                data = stream.read(row_bytes)
                require(len(data) == row_bytes, "short NPZ row")
                audit["opaque_bytes_streamed"] = audit.get("opaque_bytes_streamed", 0) + len(data)
                if i in wanted:
                    row = np.frombuffer(data, dtype="<f4").copy()
                    audit["numeric_rows_opened"] = audit.get("numeric_rows_opened", 0) + 1
                    require(np.isfinite(row).all(), "selected nonfinite row")
                    selected.append(row)
            require(stream.read(1) == b"", "NPY trailing bytes")
    return np.stack(selected) if selected else np.empty((0, expected_shape[1]), dtype=np.float32)


@torch.no_grad()
def evaluate(model, contexts, budget_check=None):
    """No teacher values needed: only labels and categorical correct-kind flags."""
    model.eval()
    groups = {g: [] for g in LABEL_GROUPS}
    predictions, violations = [], []
    seen = set()
    for start in range(0, len(contexts), 32):
        if budget_check is not None:
            budget_check()
        batch = contexts[start:start + 32]
        qlist, _, _ = model([c.x for c in batch], [c.key for c in batch])
        for c, q in zip(batch, qlist):
            c.validate()
            local = {g: [] for g in LABEL_GROUPS}
            for t in c.targets:
                require(t.uid not in seen, "evaluation UID duplication")
                seen.add(t.uid)
                z = q[t.event]
                hard = bool(z >= 0)
                loss = F.binary_cross_entropy_with_logits(z, z.new_tensor(float(t.label))) / math.log(2)
                local[t.owner + str(t.label)].append(float(loss))
                protected = bool(t.label or (t.owner == "A" and t.teacher_correct))
                if protected and hard != bool(t.label):
                    violations.append(t.uid)
                predictions.append({"uid": t.uid, "context": c.key, "device": c.device,
                                    "split": c.split, "owner": t.owner, "label": t.label,
                                    "logit": float(z), "hard": hard, "protected": protected})
            for g, values in local.items():
                if values:
                    groups[g].append(sum(values) / len(values))
    require(all(groups.values()), "evaluation global empty label group")
    return {"label_loss": sum(sum(v) / len(v) for v in groups.values()) / 4,
            "eligible": not violations, "violations": violations, "predictions": predictions,
            "targets": len(predictions), "contexts": len(contexts)}


@dataclass
class Selection:
    best_epoch: Optional[int] = None
    best_loss: Optional[float] = None
    without_improvement: int = 0
    last_epoch: int = 0

    def update(self, epoch: int, eligible: bool, validation_label_loss: float):
        require(epoch == self.last_epoch + 1 and math.isfinite(validation_label_loss), "selection sequence/nonfinite")
        improved = eligible and (self.best_loss is None or self.best_loss - validation_label_loss >= 0.0001)
        if improved:
            self.best_epoch, self.best_loss = epoch, validation_label_loss
            self.without_improvement = 0
        else:
            self.without_improvement += 1
        self.last_epoch = epoch
        return improved, epoch >= 100 or (epoch >= 20 and self.without_improvement >= 12)


def benign_gain(predictions: Sequence[dict]):
    groups = {}
    for p in predictions:
        if p["split"] == "val" and p["owner"] == "B" and p["label"] == 0:
            group = groups.setdefault(p["device"], {})
            group.setdefault(p["context"], []).append(not p["hard"])
    result = {}
    for key, contexts in sorted(groups.items()):
        total = sum(len(values) for values in contexts.values())
        normal = sum(sum(values) for values in contexts.values())
        all_normal = sum(all(values) for values in contexts.values())
        target_min, context_min = (total + 9) // 10, (len(contexts) + 9) // 10
        result[key] = {"targets": total, "contexts": len(contexts), "normal_targets": normal,
                       "normal_contexts": all_normal, "target_min": target_min, "context_min": context_min,
                       "pass": normal >= target_min and all_normal >= context_min}
    return result


def terminal_status(complete: bool, selected: bool, gain_pass: bool, kill_hard: Optional[Sequence[bool]]):
    require(complete, "incomplete trajectory cannot make a scientific verdict")
    if not selected:
        require(kill_hard is None, "premature kill access")
        return "F5_NO_ELIGIBLE_CHECKPOINT"
    if not gain_pass:
        require(kill_hard is None, "premature kill access")
        return "F5_NO_MATERIAL_BENIGN_GAIN"
    require(kill_hard is not None and len(kill_hard) == 5, "kill-only denominator")
    return "F5_DEVELOPMENT_CANDIDATE_PASS" if all(kill_hard) else "F5_KILL_ONLY_ATTACK_FAILURE"


def save_checkpoint(path: Path, model, optimizer, progress: dict, identities: dict):
    state = {"model": model.state_dict(), "optimizer": optimizer.state_dict(), "progress": progress,
             "identities": identities, "torch_rng": torch.get_rng_state(), "numpy_rng": np.random.get_state(),
             "python_rng": random.getstate()}
    buffer = io.BytesIO()
    torch.save(state, buffer)
    data = buffer.getvalue()
    atomic_bytes(path, data)
    atomic_json(path.with_suffix(path.suffix + ".receipt.json"), {"sha256": hashlib.sha256(data).hexdigest(), "identities": identities})


def load_checkpoint(path: Path, model, optimizer, identities: dict):
    receipt = json.loads(path.with_suffix(path.suffix + ".receipt.json").read_text())
    require(receipt["identities"] == identities and receipt["sha256"] == sha_file(path), "checkpoint identity/corruption")
    # Only a locally generated, receipt-verified checkpoint. Never external pickle.
    state = torch.load(path, map_location="cpu", weights_only=False)
    require(state["identities"] == identities, "checkpoint embedded identity")
    model.load_state_dict(state["model"], strict=True)
    optimizer.load_state_dict(state["optimizer"])
    torch.set_rng_state(state["torch_rng"])
    np.random.set_state(state["numpy_rng"])
    random.setstate(state["python_rng"])
    return state["progress"]


def recover_elapsed(receipt: dict, utc_now: float):
    elapsed = float(receipt["elapsed"])
    require(math.isfinite(elapsed) and elapsed >= 0 and utc_now >= receipt["last_utc"], "time receipt rollback")
    if receipt.get("open_batch_utc") is not None:
        start = receipt["open_batch_utc"]
        require(start <= utc_now and start >= receipt["last_utc"], "open batch time")
        elapsed += utc_now - start
    return elapsed


def resource_projection(t: float, v: float):
    require(math.isfinite(t) and math.isfinite(v) and t >= 0 and v >= 0, "pilot timing")
    projected = 100 * (math.ceil(4984 / 32) * t + (math.ceil(4984 / 32) + math.ceil(4323 / 32)) * v)
    return {"projected_seconds": projected, "threefold_seconds": 3 * projected,
            "cap_seconds": CAP_SECONDS, "pass": 3 * projected <= CAP_SECONDS}


def synthetic_contexts(count=32, length=256):
    """Deterministic typed field fixture. Never loads a real F4 array."""
    contexts = []
    for i in range(count):
        owner, label = ("A" if i % 4 < 2 else "B"), i % 2
        x = torch.zeros(length, 131)
        # H1, direction A_TO_B, no L2/ethertype, IPv4/TCP, ports present.
        x[:, 0], x[:, 4], x[:, 28], x[:, 30], x[:, 39], x[:, 46] = 1, 1, 1, 1, 1, 1
        # Optional protocol byte 6, LSB-first per F4; zero length and delta.
        x[:, 32], x[:, 33], x[:, 68], x[:, 76], x[:, 108] = 1, 1, 1, 1, 1
        targets = [Target("syn-%d-%d" % (i, j), j, owner, label, owner == "A", 2.0 if owner == "A" else None)
                   for j in range(length)]
        contexts.append(Context("syn-%04d" % i, x, targets))
    return contexts


def synthetic_pilot():
    reseed()
    model = Student()
    initial_hash = tensor_hash(model.state_dict())
    optimizer = optimizer_for(model)
    contexts = synthetic_contexts()
    counts = group_counts(contexts)
    train_times = []
    for i in range(10):
        start = time.perf_counter()
        train_batch(model, optimizer, contexts, len(contexts), counts)
        duration = time.perf_counter() - start
        if i >= 2:
            train_times.append(duration)
    model.eval()
    inference_times = []
    with torch.no_grad():
        for _ in range(8):
            start = time.perf_counter()
            model([c.x for c in contexts], [c.key for c in contexts])
            inference_times.append(time.perf_counter() - start)
    result = resource_projection(statistics.median(train_times), statistics.median(inference_times))
    result.update({"train_seconds": train_times, "inference_seconds": inference_times,
                   "initial_tensor_sha256": initial_hash, "synthetic_contexts": 32,
                   "events_per_context": 256, "targets_per_context": 256,
                   "real_array_opens": 0, "real_teacher_opens": 0, "real_optimizer_steps": 0,
                   "synthetic_optimizer_steps": 10})
    reseed()
    require(tensor_hash(Student().state_dict()) == initial_hash, "initialization restore")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-pilot", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refuse existing output")
    root = Path(__file__).resolve().parents[2]
    require(sha_file(root / PROTOCOL_REL) == PROTOCOL_SHA, "FROZEN identity drift")
    runtime = configure_runtime()
    result = synthetic_pilot()
    result["runtime"] = runtime
    result["code_sha256"] = sha_file(Path(__file__))
    result["protocol_sha256"] = PROTOCOL_SHA
    result["status"] = "F5_SYNTHETIC_RESOURCE_PASS" if result["pass"] else "F5_RESOURCE_NO_GO"
    atomic_json(args.output, result)
    print(json.dumps({k: result[k] for k in ("status", "projected_seconds", "threefold_seconds", "cap_seconds")}), flush=True)


if __name__ == "__main__":
    main()
