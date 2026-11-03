"""N2 one fixed candidate, one exposed-development pass, no fitting."""
from __future__ import annotations

import io
import json
import math
import os
import pickle
import struct
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import issue27frontend_f5_unified_student_v1 as f5
import issue27frontend_inheritance_n2_support_v1 as s


def configure_runtime():
    runtime = json.loads(json.dumps(f5.configure_runtime()))
    s.require(torch.get_num_threads() == 4 and torch.get_num_interop_threads() == 1
              and torch.are_deterministic_algorithms_enabled(), "CANONICAL_RUNTIME_DRIFT")
    return runtime


def project_checkpoint(container, identities, audit):
    s.require(container["identities"] == identities, "CHECKPOINT_EMBEDDED_IDENTITY")
    progress = container["progress"]
    s.require(progress["epoch"] == 21 and progress["cursor"] == 0 and progress["order"] == []
              and progress["steps"] == 3120 and progress["stop_reached"] is True
              and progress["selection"]["best_epoch"] is None
              and progress["selection"]["last_epoch"] == 20, "CHECKPOINT_PROGRESS_DRIFT")
    final = progress["epoch_ledger"][-1]
    s.require(final["epoch"] == 20, "FINAL_DEV_EPOCH_DRIFT")
    reference = {"epoch": final["epoch"], "val_violations": list(final["val_violations"]),
                 "gate_counts": {key: dict(final["gate_counts"][key]) for key in final["gate_counts"]
                                 if key.startswith("val:")}}
    audit["checkpoint_projection"] = {
        "retained": ["model", "identities", "terminal_progress", "last_epoch_val_violations",
                     "last_epoch_val_prefixed_gate_counts"],
        "incidental_optimizer_rng_earlier_ledger_and_other_fields_materialized": True,
        "incidental_values_used": False, "optimizer_instantiated_or_restored": False}
    return container["model"], reference


def restricted_checkpoint(blob, expected, identities, terminal, audit, budget):
    s.require(s.digest(blob) == expected, "CHECKPOINT_CHANGED_AFTER_HASH")
    s.require(terminal["status"] == "F5_NO_ELIGIBLE_CHECKPOINT" and terminal["complete"] is True
              and terminal["selected_epoch"] is None and terminal["epochs"] == 20
              and terminal["steps"] == 3120, "TERMINAL_REFERENCE_DRIFT")
    budget.charge(loads=1)
    previous = torch.serialization.get_safe_globals()
    torch.serialization.clear_safe_globals()
    try:
        with torch.serialization.safe_globals([np._core.multiarray._reconstruct, np.ndarray,
                                               np.dtype, np.dtypes.UInt32DType]):
            container = torch.load(io.BytesIO(blob), map_location="cpu", weights_only=True)
    except (pickle.UnpicklingError, RuntimeError, TypeError, ValueError, EOFError):
        raise s.Stop("N2_NEEDS_GOVERNED_MODEL_EXPORT") from None
    finally:
        torch.serialization.clear_safe_globals()
        torch.serialization.add_safe_globals(previous)
    audit["restricted_load"] = {"loads": 1, "weights_only": True, "ambient_globals_excluded": True,
        "safe_globals": ["numpy._core.multiarray._reconstruct", "numpy.ndarray", "numpy.dtype",
                         "numpy.dtypes.UInt32DType"]}
    return project_checkpoint(container, identities, audit)


def non_head_hash(state):
    return f5.tensor_hash({k: v for k, v in state.items() if not k.startswith("head_output.")})


def assemble(state, head, pins, budget):
    s.require(all(v.dtype == torch.float32 and v.device.type == "cpu" and bool(torch.isfinite(v).all())
                  for v in state.values()), "CHECKPOINT_MODEL_DTYPE_FINITE")
    s.require(f5.tensor_hash(state) == pins["terminal_state_tensor_sha256"], "TERMINAL_STATE_HASH")
    s.require(non_head_hash(state) == pins["non_head_state_tensor_sha256"], "NON_HEAD_STATE_HASH")
    s.require(len(head) == 260 and s.digest(head) == pins["head_float32_le_sha256"], "HEAD_BYTE_IDENTITY")
    budget.charge(head_decodes=1, assemblies=1)
    theta = np.frombuffer(head, dtype="<f4").copy()
    s.require(theta.shape == (65,) and np.isfinite(theta).all(), "HEAD_DTYPE_FINITE")
    model = f5.Student()
    model.load_state_dict(state, strict=True)
    with torch.no_grad():
        model.head_output.weight.copy_(torch.from_numpy(theta[:64].reshape(1, 64)))
        model.head_output.bias.copy_(torch.from_numpy(theta[64:]))
    installed = (model.head_output.weight.detach().numpy().tobytes()
                 + model.head_output.bias.detach().numpy().tobytes())
    s.require(installed == head and non_head_hash(model.state_dict()) == pins["non_head_state_tensor_sha256"],
              "ASSEMBLY_BIT_PRESERVATION")
    return model, {"terminal_state": pins["terminal_state_tensor_sha256"],
                   "non_head_state": pins["non_head_state_tensor_sha256"],
                   "head_bytes": s.digest(head), "assembled_state": f5.tensor_hash(model.state_dict())}


def protected_reference(contexts, reference, enforce_real=True):
    rows = {r["uid"]: r for c in contexts for r in c["targets"] if r["protected"]}
    violations = reference["val_violations"]
    s.require(len(violations) == len(set(violations)) and set(violations) <= set(rows), "REFERENCE_UID_SET")
    wrong = set(violations)
    if enforce_real:
        s.require(len(wrong) == 846 and Counter(rows[u]["category"] for u in wrong)
                  == {"A1C": 3, "A0C": 843}, "REFERENCE_VIOLATION_COUNTS")
        s.require(all(rows[u]["source_group"] == "normal_1.pcap" for u in wrong
                      if rows[u]["category"] == "A0C"), "REFERENCE_NORMAL_SOURCE")
    baseline = {uid: (not bool(int(r["label"])) if uid in wrong else bool(int(r["label"])))
                for uid, r in rows.items()}
    for category, key in (("A1C", "val:A1:protected"), ("A0C", "val:A0:protected"),
                          ("B1N", "val:B1:protected")):
        uids = [u for u, r in rows.items() if r["category"] == category]
        gate = reference["gate_counts"][key]
        s.require(gate["targets"] == len(uids) and gate["hard"] == sum(baseline[u] for u in uids)
                  and gate["flips"] == sum(u in wrong for u in uids), "REFERENCE_GATE_COUNTS")
    return baseline


def feature_contexts(path, contexts, budget, audit, expected_bytes=107666280):
    s.require(path.stat().st_size == expected_bytes, "FEATURE_BYTE_SIZE")
    loaded, decoded = [], 0
    with path.open("rb") as stream:
        for c in contexts:
            s.require(c["split"] == "internal_val", "TRAIN_FEATURE_ACCESS_FORBIDDEN")
            offset, length = c["byte_offset"], c["byte_length"]
            s.require(offset == c["offset"] * 524 and length == c["length"] * 524
                      and 0 <= offset and 1 <= c["length"] <= c["count"] <= 256
                      and offset + length <= expected_bytes, "FEATURE_SEEK_RANGE")
            budget.charge(decoded_events=c["length"])
            stream.seek(offset)
            raw = stream.read(length)
            s.require(len(raw) == length, "FEATURE_SHORT_READ")
            for r in c["targets"]:
                prefix = r["event"] + 1
                s.require(1 <= prefix <= c["length"], "FEATURE_TARGET_RANGE")
                s.require(s.digest(b"F4_INPUT_V1\0" + struct.pack("<II", prefix, 131)
                                   + raw[:prefix * 524]) == r["feature_prefix_sha256"], "FEATURE_PREFIX_IDENTITY")
            values = np.frombuffer(raw, dtype="<f4").reshape(c["length"], 131).copy()
            s.require(np.isfinite(values).all(), "FEATURE_NONFINITE")
            loaded.append({**c, "x": torch.from_numpy(values)})
            decoded += c["length"]
    audit["feature_decode"] = {"train_events": 0, "internal_val_events": decoded,
                               "method": "seek_read_internal_val_prefix_only", "ranges": len(contexts)}
    return loaded


def canonical_pass(model, contexts, budget):
    s.require([c["key"] for c in contexts] == sorted({c["key"] for c in contexts}), "CANONICAL_CONTEXT_ORDER")
    budget.charge(passes=1)
    model.eval()
    predictions = {}
    with torch.no_grad():
        for start in range(0, len(contexts), 32):
            batch = contexts[start:start + 32]
            s.require(all(c["split"] == "internal_val" for c in batch), "TRAIN_FORWARD_FORBIDDEN")
            budget.charge(batches=1, contexts=len(batch), events=sum(c["length"] for c in batch),
                          targets=sum(len(c["targets"]) for c in batch),
                          padded_slots=len(batch) * max(c["length"] for c in batch))
            logits, _, _ = model([c["x"] for c in batch], [c["key"] for c in batch])
            s.require(len(logits) == len(batch), "FORWARD_CONTEXT_COUNT")
            for c, q in zip(batch, logits):
                s.require(q.dtype == torch.float32 and q.shape == (c["length"],)
                          and bool(torch.isfinite(q).all()), "CANONICAL_LOGIT_DRIFT")
                for r in c["targets"]:
                    uid, value, label = r["uid"], float(q[r["event"]]), int(r["label"])
                    s.require(uid not in predictions, "FORWARD_DUPLICATE_UID")
                    predictions[uid] = {"uid": uid, "context": c["key"], "category": r["category"],
                        "source": c["source"], "device_family": r["device_family"],
                        "attack_family": r["attack_family"], "label": label, "protected": r["protected"],
                        "logit": value, "hard": value >= 0, "signed_margin": value if label else -value}
            budget.check()
    return predictions


def summarize(rows):
    margins = [r["signed_margin"] for r in rows]
    return {"targets": len(rows), "contexts": len({r["context"] for r in rows}),
            "sources": len({r["source"] for r in rows}),
            "errors": sorted(r["uid"] for r in rows if r["hard"] != bool(r["label"])),
            "hard": sum(r["hard"] for r in rows),
            "margin_min": min(margins) if margins else None,
            "margin_max": max(margins) if margins else None,
            "margin_mean": math.fsum(margins) / len(margins) if margins else None}


def measurements(predictions, contexts, baseline, enforce_real=True):
    wanted = {r["uid"]: (r, c) for c in contexts for r in c["targets"]}
    s.require(len(wanted) == sum(len(c["targets"]) for c in contexts)
              and set(predictions) == set(wanted), "INCOMPLETE_PREDICTIONS")
    for uid, p in predictions.items():
        r, c = wanted[uid]
        s.require(p["uid"] == uid and p["context"] == c["key"] and p["category"] == r["category"]
                  and p["source"] == c["source"] and p["device_family"] == r["device_family"]
                  and p["attack_family"] == r["attack_family"] and p["label"] == int(r["label"])
                  and p["protected"] == r["protected"], "PREDICTION_ATTACHMENT")
        s.require(math.isfinite(p["logit"]) and p["hard"] == (p["logit"] >= 0)
                  and p["signed_margin"] == (p["logit"] if p["label"] else -p["logit"]), "PREDICTION_DECISION")
    rows = list(predictions.values())
    categories = {k: summarize([r for r in rows if r["category"] == k]) for k in s.EXPECTED}
    if enforce_real:
        s.require({k: v["targets"] for k, v in categories.items()} == s.EXPECTED
                  and len({r["context"] for r in rows}) == 4323, "EVALUATION_DENOMINATOR")
    b = [r for r in rows if r["category"] == "B0N"]
    keys = sorted({r["device_family"] for r in b})
    if enforce_real:
        s.require(set(keys) == set(s.B_KEYS), "B_KEY_SET")
    utility = {}
    for key in keys:
        selected = [r for r in b if r["device_family"] == key]
        ctx = {r["context"] for r in selected}
        normal = sum(not r["hard"] for r in selected)
        normal_contexts = len(ctx - {r["context"] for r in selected if r["hard"]})
        floors = ((len(selected) + 9) // 10, (len(ctx) + 9) // 10)
        if enforce_real:
            s.require((len(selected), len(ctx), *floors) == s.B_KEYS[key], "B_UTILITY_DENOMINATOR")
        utility[key] = {"targets": len(selected), "contexts": len(ctx), "normal_targets": normal,
            "all_B_benign_normal_contexts": normal_contexts, "target_floor": floors[0],
            "context_floor": floors[1], "pass": normal >= floors[0] and normal_contexts >= floors[1],
            "baseline": "incumbent_missing_hard_by_convention"}
    attack_ok = not categories["A1C"]["errors"] and not categories["B1N"]["errors"]
    benign_ok = not categories["A0C"]["errors"]
    utility_ok = bool(utility) and all(v["pass"] for v in utility.values())
    status = s.SCIENTIFIC[0 if not attack_ok else 1 if not benign_ok else 2 if not utility_ok else 3]
    protected = {u for u, r in predictions.items() if r["protected"]}
    s.require(set(baseline) == protected, "PROTECTED_BASELINE_SCOPE")
    old_wrong = {u for u in protected if baseline[u] != bool(predictions[u]["label"])}
    new_wrong = {u for u in protected if predictions[u]["hard"] != bool(predictions[u]["label"])}
    special = {"normal_1_A0C": summarize([r for r in rows if r["source"] == "normal_1.pcap" and r["category"] == "A0C"]),
               "normal_1_B0N": summarize([r for r in rows if r["source"] == "normal_1.pcap" and r["category"] == "B0N"]),
               "other_A0C": summarize([r for r in rows if r["source"] != "normal_1.pcap" and r["category"] == "A0C"])}
    groups = {field: {key: summarize([r for r in rows if r[field] == key])
                      for key in sorted({r[field] for r in rows})}
              for field in ("source", "device_family", "attack_family")}
    return {"status": status, "complete": True, "targets": len(rows), "contexts": len(contexts),
            "categories": categories, "groups": groups, "special_groups": special,
            "attacks": [r for r in rows if r["category"] in {"A1C", "B1N"}],
            "attack_gate_pass": attack_ok, "protected_benign_pass": benign_ok, "B_utility": utility,
            "B_totals": {"targets": len(b), "contexts": len({r["context"] for r in b}),
                "normal_targets": sum(not r["hard"] for r in b),
                "all_B_benign_normal_contexts": len({r["context"] for r in b}
                                                    - {r["context"] for r in b if r["hard"]}),
                "target_floor_sum": sum(v["target_floor"] for v in utility.values()),
                "context_floor_sum": sum(v["context_floor"] for v in utility.values())},
            "B_utility_pass": utility_ok, "usable_joint_utility": attack_ok and benign_ok and utility_ok,
            "protected_comparison": {"old_wrong": sorted(old_wrong), "new_wrong": sorted(new_wrong),
                "newly_wrong": sorted(new_wrong - old_wrong), "newly_correct": sorted(old_wrong - new_wrong),
                "unprotected_baseline": "NOT_AVAILABLE_NOT_INVENTED"},
            "inheritance": "NOT_PROVED", "F5_eligible": False, "K": "NOT_AUTHORIZED", "deployment": False}


def prepare_metadata(inputs):
    for name in inputs.pins:
        inputs.verify(name)
    s.verify_manifest_agreement(inputs)
    witness = s.historical_witness(inputs)
    f3 = json.loads(inputs.read(s.F3))
    sources = {"train": set(f3["nested_split"]["train_sources"]),
               "internal_val": set(f3["nested_split"]["internal_validation_sources"])}
    identities = json.loads(inputs.read(s.F5 + "/preflight/identities.json"))
    for group in ("input_pins", "code_pins"):
        for name, sha in identities[group].items():
            if name in inputs.pins:
                s.require(sha == inputs.pins[name], "P_PIN_AGREEMENT")
    census = json.loads(inputs.read(s.F5 + "/preflight/census.json"))
    s.require(census["categories"]["val"] == s.EXPECTED, "P_DEV_CENSUS")
    scans = inputs.audit.setdefault("metadata_scans", {})
    index, _ = s.scan_csv(inputs.read(s.F4 + "/f4_context_index.csv"), "index", scans.setdefault("index", {}), inputs.budget.check)
    ts, targets = s.scan_csv(inputs.read(s.F4 + "/f4_target_audit.csv.gz"), "target", scans.setdefault("target", {}), inputs.budget.check)
    ss, scope = s.scan_csv(inputs.read(s.F5 + "/preflight/uid_scope.csv"), "scope", scans.setdefault("scope", {}), inputs.budget.check)
    contexts, counts, events = s.validate_metadata(index, ts, targets, ss, scope, sources)
    for c in contexts:
        c["split"] = "internal_val"
    s.validate_groups(contexts)
    receipt = json.loads(inputs.read(s.CHECKPOINT + ".receipt.json"))
    s.require(receipt["sha256"] == inputs.pins[s.CHECKPOINT] and receipt["identities"] == identities,
              "CHECKPOINT_RECEIPT")
    terminal = json.loads(inputs.read(s.F5 + "/training/terminal.json"))
    return contexts, counts, events, identities, terminal, witness


def real_worker(output, pins, runtime, started):
    budget, audit = s.Budget(start=started), {"training_numeric_access": 0,
        "teacher_forwards": 0, "optimizer_steps": 0, "backward_steps": 0, "lp_calls": 0,
        "metadata_container_tokenization_disclosed": True}
    writer = s.Writer(output, budget)
    verdict = {"status": "N2_ENGINEERING_STOP", "reason": "UNFINISHED_WORKER"}
    try:
        writer.json("runtime_receipt.json", runtime)
        inputs = s.Inputs(s.ROOT, pins["repository_inputs"], budget, audit)
        contexts, counts, events, identities, terminal, witness = prepare_metadata(inputs)
        writer.json("selected_uid_range_attachment.json", {"contexts": contexts, "categories": counts,
                    "selected_events": events, "split": "internal_val"})
        writer.json("verified_input_receipt.json", inputs.verified)
        writer.json("historical_witness_identity.json", witness)
        path = inputs.path(s.CHECKPOINT)
        s.require(path.stat().st_size == 1712912, "CHECKPOINT_CONTAINER_SIZE")
        state, reference = restricted_checkpoint(path.read_bytes(), inputs.pins[s.CHECKPOINT], identities, terminal, audit, budget)
        model, hashes = assemble(state, inputs.read(s.HEAD), pins["model_assembly"], budget)
        del state
        writer.json("assembled_state_before_decode.json", hashes)
        baseline = protected_reference(contexts, reference)
        writer.json("final_old_development_reference.json", reference)
        loaded = feature_contexts(inputs.path(s.FEATURES), contexts, budget, audit)
        predictions = canonical_pass(model, loaded, budget)
        after = f5.tensor_hash(model.state_dict())
        s.require(after == hashes["assembled_state"], "ASSEMBLED_STATE_CHANGED")
        writer.json("assembled_state_after_forward.json", {"assembled_state": after, "unchanged": True})
        expected = {"loads": 1, "head_decodes": 1, "assemblies": 1, "passes": 1, "batches": 136,
                    "contexts": 4323, "targets": 5206, "events": events, "decoded_events": events}
        s.require(all(budget.counts[k] == v for k, v in expected.items()), "FINAL_ACTION_COUNTS")
        result = measurements(predictions, contexts, baseline)
        writer.json("all_target_predictions.json", [predictions[u] for u in sorted(predictions)])
        writer.json("development_measurements.json", result)
        writer.json("access_receipt.json", audit)
        budget.check()
        verdict = {k: result[k] for k in ("status", "complete", "targets", "contexts", "inheritance",
                                         "F5_eligible", "K", "deployment", "usable_joint_utility")}
    except s.Stop as exc:
        verdict = {"status": "N2_NEEDS_GOVERNED_MODEL_EXPORT" if str(exc) == "N2_NEEDS_GOVERNED_MODEL_EXPORT"
                   else "N2_ENGINEERING_STOP", "reason": str(exc)}
    except Exception as exc:
        verdict = {"status": "N2_ENGINEERING_STOP", "reason": "UNEXPECTED_" + type(exc).__name__}
    data = s.json_bytes({"verdict": verdict, "resource": budget.receipt(), "access": audit,
                         "output_hashes": writer.members})
    s.require(len(data) < s.CAPS["reserve_bytes"] // 2, "TERMINAL_RECEIPT_SIZE")
    with (Path(output) / "worker_terminal.json").open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return verdict
