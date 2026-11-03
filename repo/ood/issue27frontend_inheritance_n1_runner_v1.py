"""N1 train-only diagnostic worker. Real execution is gated by the controller."""
from __future__ import annotations

import copy
import io
import json
import os
import pickle
import struct
from collections import Counter
from pathlib import Path

import numpy as np
import scipy
import torch

import issue27frontend_f5_unified_student_v1 as f5
import issue27frontend_inheritance_n1_support_v1 as s
import issue27frontend_inheritance_n1_math_v1 as math1


def configure_runtime():
    s.require(scipy.__version__ == "1.13.1", "SCIPY_VERSION_DRIFT")
    # F5's constructor/runtime is inert with respect to experiment artifacts.
    runtime = json.loads(json.dumps(f5.configure_runtime()))
    runtime["scipy"] = scipy.__version__
    s.require(torch.get_num_threads() == 4 and torch.get_num_interop_threads() == 1
              and torch.are_deterministic_algorithms_enabled(), "CANONICAL_RUNTIME_DRIFT")
    return runtime


def restricted_checkpoint(blob, expected_digest, expected_identities, terminal, audit):
    s.require(s.digest(blob) == expected_digest, "CHECKPOINT_CHANGED_AFTER_HASH")
    s.require(terminal["status"] == "F5_NO_ELIGIBLE_CHECKPOINT" and terminal["complete"] is True
              and terminal["selected_epoch"] is None and terminal["epochs"] == 20
              and terminal["steps"] == 3120, "TERMINAL_REFERENCE_DRIFT")
    allow = [np._core.multiarray._reconstruct, np.ndarray, np.dtype, np.dtypes.UInt32DType]
    previous = torch.serialization.get_safe_globals()
    torch.serialization.clear_safe_globals()
    try:
        with torch.serialization.safe_globals(allow):
            container = torch.load(io.BytesIO(blob), map_location="cpu", weights_only=True)
    except (pickle.UnpicklingError, RuntimeError, TypeError, ValueError, EOFError):
        raise s.Stop("N1_NEEDS_GOVERNED_MODEL_EXPORT") from None
    finally:
        torch.serialization.clear_safe_globals()
        torch.serialization.add_safe_globals(previous)
    audit["checkpoint_container"] = {
        "loads": 1, "weights_only": True,
        "safe_globals": ["numpy._core.multiarray._reconstruct", "numpy.ndarray", "numpy.dtype",
                         "numpy.dtypes.UInt32DType"],
        "incidental_optimizer_rng_and_old_validation_ledger_materialized": True,
        "incidental_values_used": False, "optimizer_instantiated_or_restored": False,
        "retained": ["model", "identities", "terminal_progress", "final_train_violations", "train_gate_counts"]}
    s.require(container["identities"] == expected_identities, "CHECKPOINT_EMBEDDED_IDENTITY")
    progress = container["progress"]
    s.require(progress["epoch"] == 21 and progress["cursor"] == 0 and progress["order"] == []
              and progress["steps"] == 3120 and progress["stop_reached"] is True
              and progress["selection"]["best_epoch"] is None
              and progress["selection"]["last_epoch"] == 20, "CHECKPOINT_PROGRESS_DRIFT")
    final = progress["epoch_ledger"][-1]
    s.require(final["epoch"] == 20, "FINAL_TRAIN_EPOCH_DRIFT")
    gates = {key: dict(final["gate_counts"][key]) for key in final["gate_counts"] if key.startswith("train:")}
    reference = {"epoch": final["epoch"], "train_violations": list(final["train_violations"]),
                 "gate_counts": gates, "steps": progress["steps"]}
    state = container["model"]
    del container, progress, final
    return state, reference


def feature_contexts(path, contexts, budget, audit, expected_bytes=107666280):
    s.require(path.stat().st_size == expected_bytes, "FEATURE_BYTE_SIZE")
    loaded, decoded = [], 0
    with path.open("rb") as stream:
        for context in contexts:
            budget.check()
            offset, length = context["byte_offset"], context["byte_length"]
            s.require(offset >= 0 and length == context["length"] * 524 and offset + length <= expected_bytes,
                      "FEATURE_SEEK_RANGE")
            stream.seek(offset)
            raw = stream.read(length)
            s.require(len(raw) == length, "FEATURE_SHORT_READ")
            values = np.frombuffer(raw, dtype="<f4").reshape(context["length"], 131).copy()
            s.require(np.isfinite(values).all(), "FEATURE_NONFINITE")
            for row in context["targets"]:
                budget.check()
                prefix = row["event"] + 1
                wanted = s.digest(b"F4_INPUT_V1\0" + struct.pack("<II", prefix, 131) + raw[:prefix * 524])
                s.require(wanted == row["feature_prefix_sha256"], "FEATURE_PREFIX_IDENTITY")
            loaded.append({**context, "x": torch.from_numpy(values)})
            decoded += context["length"]
    audit["feature_decode"] = {"train_prefix_events": decoded, "validation_events": 0,
                               "method": "seek_read_train_prefix_only", "ranges": len(contexts)}
    return loaded


def canonical_pass(model, contexts, budget):
    s.require([c["key"] for c in contexts] == sorted({c["key"] for c in contexts}), "CANONICAL_CONTEXT_ORDER")
    budget.charge(passes=1)
    model.eval()
    predictions, features, hashes = {}, {}, {}
    with torch.no_grad():
        for start in range(0, len(contexts), 32):
            batch = contexts[start:start + 32]
            budget.charge(batches=1, contexts=len(batch), events=sum(c["length"] for c in batch),
                          targets=sum(len(c["targets"]) for c in batch),
                          padded_slots=len(batch) * max(c["length"] for c in batch))
            order = sorted(range(len(batch)), key=lambda i: (-batch[i]["length"], batch[i]["key"]))
            captured, call = {}, [0]
            def hook(module, args):
                s.require(call[0] < len(order) and len(args) == 1 and not torch.is_grad_enabled(), "HOOK_CALL_DRIFT")
                context = batch[order[call[0]]]
                matrix = args[0].detach().cpu().contiguous().numpy()
                s.require(matrix.dtype == np.float32 and matrix.shape == (context["length"], 64)
                          and np.isfinite(matrix).all(), "HOOK_MATRIX_DRIFT")
                key = context["key"]
                hashes[key] = {"rows": len(matrix), "sha256": s.digest(matrix.astype("<f4", copy=False).tobytes())}
                captured[key] = {row["uid"]: matrix[row["event"]].copy() for row in context["targets"]}
                call[0] += 1
                return None
            handle = model.head_output.register_forward_pre_hook(hook)
            try:
                logits, _, _ = model([c["x"] for c in batch], [c["key"] for c in batch])
            finally:
                handle.remove()
            s.require(call[0] == len(order), "HOOK_CALL_COUNT")
            for context, q in zip(batch, logits):
                s.require(q.shape == (context["length"],) and bool(torch.isfinite(q).all()), "CANONICAL_LOGIT_DRIFT")
                for row in context["targets"]:
                    uid = row["uid"]
                    s.require(uid not in predictions, "FORWARD_DUPLICATE_UID")
                    value = float(q[row["event"]])
                    predictions[uid] = {"uid": uid, "context": context["key"], "category": row["category"],
                                        "source": context["source"], "device_family": row["device_family"],
                                        "attack_family": row["attack_family"], "label": int(row["label"]),
                                        "protected": row["protected"], "logit": value, "hard": value >= 0}
                    features[uid] = captured[context["key"]][uid]
            budget.check()
    return predictions, features, hashes


def errors(predictions, protected_only=False):
    return sorted(uid for uid, p in predictions.items()
                  if (p["protected"] or not protected_only) and p["hard"] != bool(p["label"]))


def validate_baseline(predictions, reference, wanted):
    s.require(set(predictions) == set(wanted), "BASELINE_UID_SET")
    actual, expected = errors(predictions, True), reference["train_violations"]
    s.require(len(expected) == len(set(expected)) == 5 and actual == sorted(expected), "BASELINE_FIVE_ERROR_SET")
    s.require(all(predictions[uid]["category"] == "A1C" for uid in actual), "BASELINE_ERROR_CATEGORY")
    for category, key in (("A1C", "train:A1:protected"), ("A0C", "train:A0:protected"),
                          ("B1N", "train:B1:protected")):
        rows = [p for p in predictions.values() if p["category"] == category]
        gate = reference["gate_counts"][key]
        s.require(gate["targets"] == len(rows) and gate["hard"] == sum(p["hard"] for p in rows)
                  and gate["flips"] == sum(p["hard"] != bool(p["label"]) for p in rows), "BASELINE_GATE_REFERENCE")


def outcomes(baseline, candidate):
    s.require(candidate is None or set(baseline) == set(candidate), "REPLAY_UID_SET")
    result = {}
    for category in s.EXPECTED:
        uids = sorted(uid for uid, p in baseline.items() if p["category"] == category)
        old = {uid for uid in uids if baseline[uid]["hard"] != bool(baseline[uid]["label"])}
        if candidate is None:
            result[category] = {"targets": len(uids), "baseline_errors": sorted(old),
                                "candidate_errors": None, "newly_wrong": None, "newly_correct": None,
                                "candidate_status": "NO_FINITE_CANDIDATE"}
            continue
        new = {uid for uid in uids if candidate[uid]["hard"] != bool(candidate[uid]["label"])}
        result[category] = {"targets": len(uids), "baseline_errors": sorted(old), "candidate_errors": sorted(new),
                            "newly_wrong": sorted(new - old), "newly_correct": sorted(old - new)}
    return result


def replay_candidate(model, contexts, theta, baseline_hashes, budget):
    before = {key: value for key, value in model.state_dict().items() if not key.startswith("head_output.")}
    before_hash = f5.tensor_hash(before)
    candidate = copy.deepcopy(model)
    with torch.no_grad():
        candidate.head_output.weight.copy_(torch.from_numpy(theta[:64].reshape(1, 64)))
        candidate.head_output.bias.copy_(torch.from_numpy(theta[64:]))
    after = {key: value for key, value in candidate.state_dict().items() if not key.startswith("head_output.")}
    s.require(f5.tensor_hash(after) == before_hash, "CANDIDATE_BACKBONE_CHANGED")
    predictions, _, hashes = canonical_pass(candidate, contexts, budget)
    s.require(hashes == baseline_hashes and f5.tensor_hash(after) == before_hash
              and f5.tensor_hash(before) == before_hash, "REPLAY_FIXED_FEATURE_IDENTITY")
    return predictions, hashes, before_hash


def diagnose(model, contexts, reference, writer, budget, enforce_real_baseline=True):
    baseline, feature_rows, context_hashes = canonical_pass(model, contexts, budget)
    uids = sorted(baseline)
    writer.json("baseline_predictions.json", [baseline[uid] for uid in uids])
    writer.json("baseline_model_and_context_hashes.json", {"model": f5.tensor_hash(model.state_dict()),
                                                         "contexts": context_hashes})
    if enforce_real_baseline:
        validate_baseline(baseline, reference, [r["uid"] for c in contexts for r in c["targets"]])
    selected = [uid for uid in uids if baseline[uid]["protected"]]
    features = np.stack([feature_rows[uid] for uid in uids])
    feature_hash = writer.write("target64.f32le", features.astype("<f4", copy=False).tobytes())
    writer.json("target64_index.json", {"uids": uids, "protected_uids": selected, "shape": [len(uids), 64],
                                        "dtype": "float32_le", "sha256": feature_hash})
    h = np.stack([feature_rows[uid] for uid in selected])
    labels = np.asarray([baseline[uid]["label"] for uid in selected], dtype=np.int64)
    writer.json("lp_problem.json", {"protected_uids": selected, "labels": labels.tolist(),
                                    "feature_sha256": s.digest(h.astype("<f4", copy=False).tobytes()),
                                    "variables": 66, "constraints": len(selected), "theta_bounds": [-1, 1],
                                    "gamma_bounds": [None, None], "objective": "maximize_gamma",
                                    "method": "highs-ds", "options": math1.OPTIONS})
    a, result, receipt = math1.solve_once(h, labels, budget)
    writer.json("lp_result.json", receipt)
    theta = math1.sole_candidate(result)
    exact, replay_pass = {"status": "NO_FINITE_CANDIDATE", "pass": False}, False
    candidate = None
    if theta is not None:
        writer.write("candidate_head.f32le", theta.astype("<f4", copy=False).tobytes())
        writer.json("candidate_head.json", {"coefficients": theta.tolist(), "cast_count": 1,
                                            "markings": ["NOT_DEPLOYMENT", "NOT_F5_ELIGIBLE"],
                                            "model_scope": "head_output_only"})
        exact = math1.exact_signs(h, labels, theta, math1.ExactBudget(budget.check))
        writer.json("exact_candidate_check.json", exact)
        candidate, hashes, backbone = replay_candidate(model, contexts, theta, context_hashes, budget)
        replay_pass = not errors(candidate, True)
        writer.json("candidate_predictions.json", [candidate[uid] for uid in uids])
        writer.json("candidate_context_hashes.json", {"contexts": hashes, "backbone_sha256": backbone})
    else:
        writer.json("exact_candidate_check.json", exact)
    writer.json("all_category_outcomes.json", outcomes(baseline, candidate))
    negative = math1.certificate(a, result, exact["pass"], math1.ExactBudget(budget.check))
    if "support" in negative:
        negative["support_uids"] = [selected[i] for i in negative["support"]]
    writer.json("exact_certificate.json", negative)
    budget.check()
    return math1.verdict(exact["pass"], replay_pass, negative["verified"])


def prepare_metadata(inputs):
    pins = inputs.pins
    for name in pins:
        inputs.verify(name)
    for prefix in (s.F4, s.F5):
        members = s.manifest(inputs.read(prefix + "/SHA256SUMS"))
        for name, expected in pins.items():
            if name.startswith(prefix + "/") and name != prefix + "/SHA256SUMS":
                s.require(members.get(name[len(prefix) + 1:]) == expected, "MANIFEST_PIN_AGREEMENT")
    f3 = json.loads(inputs.read(s.F3))
    sources = {"train": set(f3["nested_split"]["train_sources"]),
               "internal_val": set(f3["nested_split"]["internal_validation_sources"])}
    identities = json.loads(inputs.read(s.F5 + "/preflight/identities.json"))
    for name, sha in identities["input_pins"].items():
        if name in pins:
            s.require(sha == pins[name], "P_PIN_AGREEMENT")
    for name, sha in identities["code_pins"].items():
        if name in pins:
            s.require(sha == pins[name], "P_CODE_AGREEMENT")
    census = json.loads(inputs.read(s.F5 + "/preflight/census.json"))
    s.require(census["categories"]["train"] == s.EXPECTED, "P_TRAIN_CENSUS")
    n0 = json.loads(inputs.read(s.N0))
    s.require(n0["legal_fit_targets"] == 18266 and n0["legal_fit_contexts"] == 12889,
              "N0_REFERENCE_COUNTS")
    scans = inputs.audit.setdefault("metadata_scans", {})
    index, _ = s.scan_csv(inputs.read(s.F4 + "/f4_context_index.csv"), "index", scans.setdefault("index", {}), inputs.budget.check)
    target_select, targets = s.scan_csv(inputs.read(s.F4 + "/f4_target_audit.csv.gz"), "target", scans.setdefault("target", {}), inputs.budget.check)
    scope_select, scope = s.scan_csv(inputs.read(s.F5 + "/preflight/uid_scope.csv"), "scope", scans.setdefault("scope", {}), inputs.budget.check)
    contexts, counts, events = s.validate_metadata(index, target_select, targets, scope_select, scope, sources)
    receipt = json.loads(inputs.read(s.CHECKPOINT + ".receipt.json"))
    s.require(receipt["sha256"] == pins[s.CHECKPOINT] and receipt["identities"] == identities, "CHECKPOINT_RECEIPT")
    terminal = json.loads(inputs.read(s.F5 + "/training/terminal.json"))
    return contexts, counts, events, identities, terminal


def real_worker(output, pins, runtime, started):
    budget = s.Budget(start=started)
    writer = s.Writer(output, budget)
    audit = {"validation_numeric_access": 0, "teacher_forwards": 0, "backward_steps": 0,
             "optimizer_steps": 0, "metadata_container_tokenization_disclosed": True}
    verdict = {"status": "N1_ENGINEERING_STOP", "reason": "UNFINISHED_WORKER"}
    try:
        writer.json("runtime_receipt.json", runtime)
        inputs = s.Inputs(s.ROOT, pins["repository_inputs"], budget, audit)
        contexts, counts, events, identities, terminal = prepare_metadata(inputs)
        writer.json("train_uid_range_attachment.json", {"contexts": contexts, "categories": counts,
                                                       "selected_events": events, "split": "train"})
        writer.json("verified_input_receipt.json", inputs.verified)
        writer.json("metadata_access_receipt.json", audit)
        path = inputs.path(s.CHECKPOINT)
        s.require(path.stat().st_size == 1712912, "CHECKPOINT_CONTAINER_SIZE")
        state, reference = restricted_checkpoint(path.read_bytes(), inputs.pins[s.CHECKPOINT], identities, terminal, audit)
        model = f5.Student()
        model.load_state_dict(state, strict=True)
        s.require(all(v.dtype == torch.float32 and bool(torch.isfinite(v).all()) for v in state.values()),
                  "CHECKPOINT_MODEL_DTYPE_FINITE")
        del state
        writer.json("terminal_training_reference.json", reference)
        loaded = feature_contexts(inputs.path(s.FEATURES), contexts, budget, audit)
        verdict = diagnose(model, loaded, reference, writer, budget)
    except s.Stop as exc:
        verdict = {"status": "N1_NEEDS_GOVERNED_MODEL_EXPORT" if str(exc) == "N1_NEEDS_GOVERNED_MODEL_EXPORT"
                   else "N1_ENGINEERING_STOP", "reason": str(exc)}
    except Exception as exc:
        verdict = {"status": "N1_ENGINEERING_STOP", "reason": "UNEXPECTED_" + type(exc).__name__}
    # Reserved terminal receipts are written by the supervisor after worker exit.
    terminal_receipt = {"verdict": verdict, "resource": budget.receipt(), "access": audit,
                        "output_hashes": writer.members}
    data = s.json_bytes(terminal_receipt)
    s.require(len(data) < s.CAPS["reserve_bytes"] // 2, "TERMINAL_RECEIPT_SIZE")
    with (Path(output) / "worker_terminal.json").open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return verdict
