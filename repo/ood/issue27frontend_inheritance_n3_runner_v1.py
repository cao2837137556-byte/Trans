"""N3 one conservative fit with independent exact and full-context verification."""
from __future__ import annotations

import copy
import scipy
import issue27frontend_inheritance_n1_math_v1 as math1
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
import issue27frontend_inheritance_n3_support_v1 as s


def configure_runtime():
    s.require(scipy.__version__ == "1.13.1", "SCIPY_VERSION_DRIFT")
    runtime = json.loads(json.dumps(f5.configure_runtime()))
    runtime["scipy"] = scipy.__version__
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
    reference = {k: progress[k] for k in ("epoch", "cursor", "order", "steps", "stop_reached")}
    reference["selection"] = {k: progress["selection"][k] for k in ("best_epoch", "last_epoch")}
    audit["checkpoint_projection"] = {
        "retained": ["model", "identities", "terminal_progress", "selection_best_last"],
        "incidental_optimizer_rng_and_all_ledger_container_materialized": True,
        "incidental_values_used": False, "ledger_values_indexed": 0,
        "optimizer_instantiated_or_restored": False}
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
        raise s.Stop("N3_NEEDS_GOVERNED_MODEL_EXPORT") from None
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


def feature_contexts(path, contexts, budget, audit, expected_bytes=107666280):
    s.require(path.stat().st_size == expected_bytes, "FEATURE_BYTE_SIZE")
    loaded, decoded = [], 0
    s.require(len({c["split"] for c in contexts}) == 1, "MIXED_DECODE_SPLITS")
    split = contexts[0]["split"]
    s.require(split in {"train", "internal_val"}, "DECODE_SPLIT")
    counter = "decoded_train_events" if split == "train" else "decoded_dev_events"
    s.require(budget.counts[counter] == 0, "REPEATED_PREFIX_DECODE")
    with path.open("rb") as stream:
        for c in contexts:

            offset, length = c["byte_offset"], c["byte_length"]
            s.require(offset == c["offset"] * 524 and length == c["length"] * 524
                      and 0 <= offset and 1 <= c["length"] <= c["count"] <= 256
                      and offset + length <= expected_bytes, "FEATURE_SEEK_RANGE")
            budget.charge(decoded_events=c["length"], **{counter: c["length"]})
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
    audit.setdefault("feature_decode", {})[split] = {
        "events": decoded, "method": "seek_read_original_split_prefix_once", "ranges": len(contexts)}
    return loaded


def canonical_pass(model, contexts, budget, phase):
    s.require([c["key"] for c in contexts] == sorted({c["key"] for c in contexts}), "CANONICAL_CONTEXT_ORDER")
    allowed = {"baseline_dev": "internal_val", "candidate_train": "train", "candidate_dev": "internal_val"}
    s.require(phase in allowed and all(c["split"] == allowed[phase] for c in contexts), "CANONICAL_SPLIT_PHASE")
    budget.charge(passes=1, **{phase + "_passes": 1})
    model.eval()
    predictions, features, hashes = {}, {}, {}
    with torch.no_grad():
        for start in range(0, len(contexts), 32):
            batch = contexts[start:start + 32]
            budget.charge(**{phase + "_" + k: v for k, v in {
                "batches": 1, "contexts": len(batch), "events": sum(c["length"] for c in batch),
                "targets": sum(len(c["targets"]) for c in batch)}.items()})
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
            s.require(len(logits) == len(batch), "FORWARD_CONTEXT_COUNT")
            s.require(call[0] == len(order), "HOOK_CALL_COUNT")
            for context, q in zip(batch, logits):
                s.require(q.dtype == torch.float32 and q.shape == (context["length"],) and bool(torch.isfinite(q).all()), "CANONICAL_LOGIT_DRIFT")
                for row in context["targets"]:
                    uid = row["uid"]
                    s.require(uid not in predictions, "FORWARD_DUPLICATE_UID")
                    value = float(q[row["event"]])
                    predictions[uid] = {"uid": uid, "context": context["key"], "category": row["category"],
                                        "source": context["source"], "device_family": row["device_family"],
                                        "attack_family": row["attack_family"], "label": int(row["label"]),
                                        "protected": row["protected"], "logit": value, "hard": value >= 0,
                                        "signed_margin": value if int(row["label"]) else -value,
                                        "original_split": context["split"],
                                        "original_category": row["category"],
                                        "original_protected": row["protected"],
                                        "constraint_role": row["constraint_role"],
                                        "exposure_role": row["exposure_role"]}
                    features[uid] = captured[context["key"]][uid]
            budget.check()
    return predictions, features, hashes


def summarize(rows):
    margins = [r["signed_margin"] for r in rows]
    return {"targets": len(rows), "contexts": len({r["context"] for r in rows}),
            "sources": len({r["source"] for r in rows}),
            "errors": sorted(r["uid"] for r in rows if r["hard"] != bool(r["label"])),
            "hard": sum(r["hard"] for r in rows),
            "margin_min": min(margins) if margins else None,
            "margin_max": max(margins) if margins else None,
            "margin_mean": math.fsum(margins) / len(margins) if margins else None}

ATTACHMENTS = ("uid", "context", "category", "source", "device_family", "attack_family", "label", "protected")


def reference_rows(rows, contexts):
    reference = {r["uid"]: r for r in rows}
    wanted = {r["uid"]: (r, c) for c in contexts for r in c["targets"]}
    s.require(len(reference) == len(rows) == len(wanted) and set(reference) == set(wanted),
              "REFERENCE_UID_JOIN")
    for uid, p in reference.items():
        r, c = wanted[uid]
        expected = {"uid": uid, "context": c["key"], "category": r["category"], "source": c["source"],
                    "device_family": r["device_family"], "attack_family": r["attack_family"],
                    "label": int(r["label"]), "protected": r["protected"]}
        s.require(all(p[k] == v for k, v in expected.items()), "REFERENCE_ATTACHMENT")
        s.require(type(p["hard"]) is bool and math.isfinite(p["logit"])
                  and p["hard"] == (p["logit"] >= 0), "REFERENCE_DECISION")
        s.require(float(np.float32(p["logit"])) == p["logit"], "REFERENCE_FLOAT32_SCALAR")
    return reference


def freeze_roles(splits, train_ref, dev_ref, enforce_real=True):
    s.require(not set(train_ref) & set(dev_ref), "SPLIT_UID_OVERLAP")
    s.require(all(p["hard"] == bool(p["label"]) for p in train_ref.values()), "N1_TRAIN_REGRESSION")
    attached = {}
    for split, contexts in splits.items():
        for c in contexts:
            for r in c["targets"]:
                uid = r["uid"]
                s.require(uid not in attached, "ROLE_DUPLICATE_UID")
                if split == "train":
                    role = "original_train_retention"
                elif r["protected"]:
                    role = "development_protection_fit"
                elif r["category"] == "B0N" and dev_ref[uid]["hard"] is False:
                    role = "development_B_release_retention_fit"
                else:
                    role = "exposed_report_only"
                r["constraint_role"] = role
                r["exposure_role"] = "exposed_report_only" if role == "exposed_report_only" else "fitting"
                attached[uid] = {"uid": uid, "context": c["key"], "original_split": split,
                    "original_category": r["category"], "original_protected": r["protected"],
                    "label": int(r["label"]), "constraint_role": role, "exposure_role": r["exposure_role"]}
    ordered = [attached[u] for u in sorted(attached)]
    fit = [r for r in ordered if r["constraint_role"] != "exposed_report_only"]
    if enforce_real:
        s.require(Counter(r["constraint_role"] for r in ordered) == {
            "original_train_retention": 8660, "development_protection_fit": 1484,
            "development_B_release_retention_fit": 2567, "exposed_report_only": 1155}, "ROLE_COUNTS")
        s.require(len(fit) == 12711 and sum(r["label"] for r in fit) == 2253, "CONSTRAINT_COUNTS")
    return ordered, fit


def decode_train_cache(raw, index, contexts, expected, budget):
    wanted = sorted(r["uid"] for c in contexts for r in c["targets"])
    protected = sorted(r["uid"] for c in contexts for r in c["targets"] if r["protected"])
    s.require(index["uids"] == wanted and len(wanted) == len(set(wanted))
              and index["protected_uids"] == protected, "CACHE_UID_PROTECTION_JOIN")
    s.require(index["shape"] == [len(wanted), 64] and index["dtype"] == "float32_le"
              and index["sha256"] == expected == s.digest(raw)
              and len(raw) == len(wanted) * 256, "CACHE_IDENTITY_SHAPE")
    budget.charge(cache_decodes=1, cache_values=len(wanted) * 64)
    matrix = np.frombuffer(raw, dtype="<f4").reshape(len(wanted), 64).copy()
    s.require(np.isfinite(matrix).all(), "CACHE_NONFINITE")
    return {u: matrix[i] for i, u in enumerate(wanted)}


def compare_baseline(actual, reference):
    s.require(set(actual) == set(reference), "BASELINE_UID_SET")
    for uid, p in actual.items():
        old = reference[uid]
        s.require(all(p[k] == old[k] for k in ATTACHMENTS) and p["hard"] == old["hard"]
                  and struct.pack("<f", p["logit"]) == struct.pack("<f", old["logit"]),
                  "BASELINE_N2_BITWISE_MISMATCH")


def compare_vectors(actual, reference, hashes, expected_hashes):
    s.require(hashes == expected_hashes and set(actual) == set(reference), "PREHEAD_CONTEXT_IDENTITY")
    s.require(all(actual[u].dtype == np.float32 and actual[u].shape == (64,)
                  and actual[u].tobytes() == reference[u].tobytes() for u in actual), "PREHEAD_TARGET_BITS")


def b_sets(predictions):
    groups = {}
    for p in predictions.values():
        if p["category"] == "B0N":
            s.require(p["label"] == 0, "B_LABEL")
            groups.setdefault(p["device_family"], []).append(p)
    return {key: {"targets": {p["uid"] for p in rows if not p["hard"]},
                  "contexts": {p["context"] for p in rows} - {p["context"] for p in rows if p["hard"]},
                  "all_targets": {p["uid"] for p in rows}, "all_contexts": {p["context"] for p in rows}}
            for key, rows in groups.items()}


def retention(candidate, historical, enforce_real=True):
    current, old = b_sets(candidate), b_sets(historical)
    s.require(set(current) == set(old), "B_KEY_IDENTITY")
    result = {}
    retained_counts = {"iotsim-combined-cycle": (333, 282), "iotsim-domotic-monitor": (230, 50),
                       "ton-iot-external": (2004, 1906)}
    for key, previous in old.items():
        now = current[key]
        s.require(now["all_targets"] == previous["all_targets"]
                  and now["all_contexts"] == previous["all_contexts"], "B_DENOMINATOR")
        nt, nc = len(now["all_targets"]), len(now["all_contexts"])
        floors = ((nt + 9) // 10, (nc + 9) // 10)
        if enforce_real:
            s.require((nt, nc, *floors) == s.B_KEYS[key]
                      and (len(previous["targets"]), len(previous["contexts"])) == retained_counts[key],
                      "B_HISTORICAL_COUNTS")
        result[key] = {"targets": nt, "contexts": nc, "target_floor": floors[0], "context_floor": floors[1],
            "normal_targets": len(now["targets"]), "normal_contexts": len(now["contexts"]),
            "lost_targets": sorted(previous["targets"] - now["targets"]),
            "lost_contexts": sorted(previous["contexts"] - now["contexts"]),
            "new_releases": sorted(now["targets"] - previous["targets"]),
            "new_normal_contexts": sorted(now["contexts"] - previous["contexts"]),
            "historical_retained_targets": sorted(previous["targets"]),
            "historical_retained_contexts": sorted(previous["contexts"]),
            "retention_pass": previous["targets"] <= now["targets"] and previous["contexts"] <= now["contexts"],
            "original_floors_pass": len(now["targets"]) >= floors[0] and len(now["contexts"]) >= floors[1]}
    if enforce_real:
        s.require(set(result) == set(s.B_KEYS), "B_KEY_SET")
    return result


def measurements(candidate, train_ref, dev_ref, roles, enforce_real=True):
    historical = {**train_ref, **dev_ref}
    s.require(set(candidate) == set(historical) == {r["uid"] for r in roles}, "COMPLETE_REPORT_UIDS")
    for role in roles:
        p, old = candidate[role["uid"]], historical[role["uid"]]
        s.require(all(p[k] == old[k] for k in ATTACHMENTS)
                  and all(p[k] == v for k, v in role.items()), "REPORT_ATTACHMENT")
        s.require(math.isfinite(p["logit"]) and p["hard"] == (p["logit"] >= 0)
                  and p["signed_margin"] == (p["logit"] if p["label"] else -p["logit"]), "REPORT_DECISION")
    rows = list(candidate.values())
    fit = [p for p in rows if p["constraint_role"] != "exposed_report_only"]
    dev = {u: candidate[u] for u in dev_ref}
    b = retention(dev, dev_ref, enforce_real)
    wrong = sorted(p["uid"] for p in fit if p["hard"] != bool(p["label"]))
    changes = {}
    for split, ref in (("train", train_ref), ("internal_val", dev_ref)):
        changes[split] = {}
        for category in s.EXPECTED:
            uids = {u for u, p in ref.items() if p["category"] == category}
            ow = {u for u in uids if ref[u]["hard"] != bool(ref[u]["label"])}
            nw = {u for u in uids if candidate[u]["hard"] != bool(candidate[u]["label"])}
            changes[split][category] = {"targets": len(uids), "old_wrong": sorted(ow), "new_wrong": sorted(nw),
                                       "newly_wrong": sorted(nw - ow), "newly_correct": sorted(ow - nw)}
    groups = {field: {key: summarize([p for p in rows if p[field] == key])
                     for key in sorted({p[field] for p in rows})}
              for field in ("original_split", "category", "source", "device_family", "attack_family",
                            "constraint_role")}
    specials = {"normal_1_A0C": [p for p in dev.values() if p["source"] == "normal_1.pcap" and p["category"] == "A0C"],
                "normal_1_B0N": [p for p in dev.values() if p["source"] == "normal_1.pcap" and p["category"] == "B0N"],
                "other_A0C": [p for p in dev.values() if p["source"] != "normal_1.pcap" and p["category"] == "A0C"]}
    passed = not wrong and bool(b) and all(v["retention_pass"] and v["original_floors_pass"] for v in b.values())
    if enforce_real:
        s.require(len(rows) == 13866 and len(fit) == 12711 and len(dev) == 5206, "REPORT_COUNTS")
    return {"complete": True, "targets": len(rows), "constraint_targets": len(fit),
            "constraint_errors": wrong, "float32_pass": passed, "usable_joint_repair": passed,
            "groups": groups, "special_groups": {k: summarize(v) for k, v in specials.items()},
            "B_retention": b, "changes": changes,
            "development_attacks": [p for p in dev.values() if p["category"] in {"A1C", "B1N"}],
            "report_only": [p for p in rows if p["constraint_role"] == "exposed_report_only"], **s.CLAIMS}


def verdict(exact, replay, negative, stop=None):
    if stop:
        return {"status": "N3_NEEDS_GOVERNED_MODEL_EXPORT" if stop == "N3_NEEDS_GOVERNED_MODEL_EXPORT"
                else "N3_ENGINEERING_STOP", "reason": stop, **s.CLAIMS}
    s.require(not (exact and negative), "VERIFIER_INTEGRITY_CONTRADICTION")
    descriptor = ("JOINT_EXACT_FLOAT32_FIT" if exact and replay else
                  "EXACT_AFFINE_WITNESS_FLOAT32_REPLAY_MISMATCH" if exact else
                  "FLOAT32_ONLY_FIT" if replay else "NO_VERIFIED_FIT")
    return {"status": s.SCIENTIFIC[0 if exact and replay else 1 if negative else 2],
            "fit_descriptor": descriptor, **s.CLAIMS}


def install_candidate(model, theta, budget):
    s.require(theta.dtype == np.float32 and theta.shape == (65,) and np.isfinite(theta).all()
              and (np.abs(theta) <= 1).all(), "CANDIDATE_BITS_RANGE")
    budget.charge(installations=1)
    candidate = copy.deepcopy(model)
    with torch.no_grad():
        candidate.head_output.weight.copy_(torch.from_numpy(theta[:64].reshape(1, 64)))
        candidate.head_output.bias.copy_(torch.from_numpy(theta[64:]))
    s.require(non_head_hash(candidate.state_dict()) == non_head_hash(model.state_dict()), "CANDIDATE_NONHEAD")
    s.require(candidate.head_output.weight.detach().numpy().tobytes()
              + candidate.head_output.bias.detach().numpy().tobytes() == theta.tobytes(), "CANDIDATE_INSTALL_BITS")
    return candidate


def fit_once(model, loaded, train_vectors, train_hashes, train_ref, dev_ref, roles, fit, writer, budget,
             enforce_real=True, solver=None):
    baseline_hash = f5.tensor_hash(model.state_dict())
    baseline, dev_vectors, dev_hashes = canonical_pass(model, loaded["internal_val"], budget, "baseline_dev")
    compare_baseline(baseline, dev_ref)
    s.require(f5.tensor_hash(model.state_dict()) == baseline_hash, "BASELINE_MUTATED")
    writer.json("baseline_predictions.json", [baseline[u] for u in sorted(baseline)])
    dev_order = sorted(dev_vectors)
    dev_matrix = np.stack([dev_vectors[u] for u in dev_order])
    cache_sha = writer.write("dev64.f32le", dev_matrix.astype("<f4", copy=False).tobytes())
    writer.json("dev64_index.json", {"uids": dev_order, "shape": list(dev_matrix.shape),
        "dtype": "float32_le", "sha256": cache_sha,
        "row_hashes": {u: s.digest(dev_vectors[u].tobytes()) for u in dev_order}})
    writer.json("baseline_context_hashes.json", dev_hashes)
    all_vectors = {**train_vectors, **dev_vectors}
    uids = [r["uid"] for r in fit]
    s.require(uids == sorted(set(uids)), "CONSTRAINT_ORDER")
    h = np.stack([all_vectors[u] for u in uids])
    labels = np.asarray([r["label"] for r in fit], dtype=np.int64)
    writer.json("lp_problem.json", {"uids": uids, "labels": labels.tolist(), "constraints": len(uids),
        "feature_sha256": s.digest(h.tobytes()),
        "signed_matrix_sha256": s.digest(math1.problem(h, labels).astype("<f8", copy=False).tobytes()),
        "roles": fit, "options": math1.OPTIONS, "variables": 66,
        "normalization": False, "candidate_selection": "SOLE_RETURNED_VECTOR"})
    a, result, receipt = math1.solve_once(h, labels, budget, solver)
    writer.json("lp_result.json", receipt)
    # Charge the sole cast only when the inherited helper can actually cast.
    vector = getattr(result, "x", None)
    if int(result.status) in {0, 1} and vector is not None and np.shape(vector) == (66,):
        if np.isfinite(np.asarray(vector)[:65]).all():
            budget.charge(candidate_casts=1)
    theta = math1.sole_candidate(result)
    exact = {"status": "NO_FINITE_CANDIDATE", "pass": False}
    report = {"complete": False, "candidate": "NO_FINITE_CANDIDATE", "float32_pass": False,
              "roles": roles, "historical_outcomes": [p for _, p in sorted({**train_ref, **dev_ref}.items())],
              **s.CLAIMS}
    if theta is not None:
        writer.write("candidate_head.f32le", theta.tobytes())
        writer.json("candidate_head.json", {"markings": ["NOT_DEPLOYMENT", "NOT_F5_ELIGIBLE"],
                    "cast_count": 1, "coefficients": theta.tolist()})
        budget.charge(exact_positive_stages=1)
        exact = math1.exact_signs(h, labels, theta, math1.ExactBudget(budget.check))
        exact["wrong_uids"] = [uids[i] for i in exact.get("wrong_row_indices", [])]
        candidate = install_candidate(model, theta, budget)
        before = f5.tensor_hash(candidate.state_dict())
        writer.json("candidate_state_before.json", {"full": before, "non_head": non_head_hash(candidate.state_dict())})
        predictions, contexts_after = {}, {}
        for split, vectors, hashes, phase in (
                ("train", train_vectors, train_hashes, "candidate_train"),
                ("internal_val", dev_vectors, dev_hashes, "candidate_dev")):
            measured, actual, observed = canonical_pass(candidate, loaded[split], budget, phase)
            compare_vectors(actual, vectors, observed, hashes)
            predictions.update(measured)
            contexts_after[split] = observed
        s.require(f5.tensor_hash(candidate.state_dict()) == before
                  and f5.tensor_hash(model.state_dict()) == baseline_hash, "FINAL_STATE_MUTATION")
        writer.json("candidate_state_after.json", {"full": before, "baseline": baseline_hash,
                    "non_head": non_head_hash(candidate.state_dict())})
        writer.json("candidate_context_hashes.json", contexts_after)
        writer.json("all_target_predictions.json", [predictions[u] for u in sorted(predictions)])
        report = measurements(predictions, train_ref, dev_ref, roles, enforce_real)
    writer.json("exact_candidate_check.json", exact)
    writer.json("joint_measurements.json", report)
    if not exact["pass"]:
        budget.charge(exact_negative_stages=1)
    negative = math1.certificate(a, result, exact["pass"], math1.ExactBudget(budget.check))
    negative["support_rows"] = [fit[i] for i in negative.get("support", [])]
    writer.json("exact_certificate.json", negative)
    decision = verdict(exact["pass"], report["float32_pass"], negative["verified"])
    decision.update(complete=True, candidate_present=theta is not None,
                    targets=report.get("targets", 0), constraint_targets=len(fit))
    writer.json("decision.json", decision)
    return decision


def prepare_metadata(inputs):
    for name in inputs.pins:
        inputs.verify(name)
    s.verify_manifest_agreement(inputs)
    witness = s.historical_witness(inputs)
    def read(name):
        return json.loads(inputs.read(name))
    f3 = read(s.F3)
    sources = {"train": set(f3["nested_split"]["train_sources"]),
               "internal_val": set(f3["nested_split"]["internal_validation_sources"])}
    identities = read(s.F5 + "/preflight/identities.json")
    for group in ("input_pins", "code_pins"):
        for name, sha in identities[group].items():
            if name in inputs.pins:
                s.require(sha == inputs.pins[name], "P_PIN_AGREEMENT")
    census = read(s.F5 + "/preflight/census.json")
    s.require(census["categories"]["train"] == s.base.EXPECTED
              and census["categories"]["val"] == s.EXPECTED, "P_CENSUS")
    scans = inputs.audit.setdefault("metadata_scans", {})
    index, _ = s.scan_csv(inputs.read(s.F4 + "/f4_context_index.csv"), "index", scans.setdefault("index", {}), inputs.budget.check)
    ts, targets = s.scan_csv(inputs.read(s.F4 + "/f4_target_audit.csv.gz"), "target", scans.setdefault("target", {}), inputs.budget.check)
    ss, scope = s.scan_csv(inputs.read(s.F5 + "/preflight/uid_scope.csv"), "scope", scans.setdefault("scope", {}), inputs.budget.check)
    splits = s.validate_metadata(index, ts, targets, ss, scope, sources)
    receipt = read(s.CHECKPOINT + ".receipt.json")
    s.require(receipt["sha256"] == inputs.pins[s.CHECKPOINT] and receipt["identities"] == identities, "CHECKPOINT_RECEIPT")
    terminal = read(s.F5 + "/training/terminal.json")
    train_ref = reference_rows(read(s.N1_OUTPUT + "/candidate_predictions.json"), splits["train"])
    dev_ref = reference_rows(read(s.N2_OUTPUT + "/all_target_predictions.json"), splits["internal_val"])
    n2super = read(s.N2_OUTPUT + "/supervisor_terminal.json")
    n2worker = read(s.N2_OUTPUT + "/worker_terminal.json")
    n2measure = read(s.N2_OUTPUT + "/development_measurements.json")
    s.require(n2super["verdict"]["status"] == n2worker["verdict"]["status"]
              == n2measure["status"] == "N2_DEV_ATTACK_GATE_FAILURE"
              and n2super["worker_count"] == 1 and n2super["worker_exit_code"] == 0
              and n2super["restarts"] == 0 and n2super["synthetic"] is False, "N2_TERMINAL_REFERENCE")
    for key, value in {"passes": 1, "batches": 136, "targets": 5206, "contexts": 4323}.items():
        s.require(n2worker["resource"]["counts"][key] == value, "N2_ACTION_REFERENCE")
    s.require(n2worker["access"]["lp_calls"] == 0 and n2worker["access"]["training_numeric_access"] == 0,
              "N2_ACCESS_REFERENCE")
    comparison = n2measure["protected_comparison"]
    wrong = sorted(u for u, p in dev_ref.items() if p["protected"] and p["hard"] != bool(p["label"]))
    s.require(comparison["old_wrong"] == comparison["new_wrong"] == wrong and len(wrong) == 846
              and comparison["newly_wrong"] == comparison["newly_correct"] == []
              and n2measure["B_utility_pass"] is True, "N2_OUTCOME_REFERENCE")
    before = read(s.N2_OUTPUT + "/assembled_state_before_decode.json")
    after = read(s.N2_OUTPUT + "/assembled_state_after_forward.json")
    s.require(before["assembled_state"] == after["assembled_state"]
              == "386ab128a57dbcb9eb284468f39fd47697b7c82bd41c84c9cd3bc0e61f28bfd8", "N2_ASSEMBLED_REFERENCE")
    retention(dev_ref, dev_ref)
    return splits, identities, terminal, train_ref, dev_ref, witness


def real_worker(output, pins, runtime, started):
    budget, audit = s.Budget(start=started), {
        "teacher_forwards": 0, "optimizer_steps": 0, "backward_steps": 0,
        "metadata_container_tokenization_disclosed": True, "real_stage": "N3_NEW_DEVELOPMENT_FIT",
        "all_selected_prefixes_cover_parent": True}
    writer = s.Writer(output, budget)
    decision = verdict(False, False, False, "UNFINISHED_WORKER")
    try:
        writer.json("runtime_receipt.json", runtime)
        inputs = s.Inputs(s.ROOT, pins["repository_inputs"], budget, audit)
        splits, identities, terminal, train_ref, dev_ref, witness = prepare_metadata(inputs)
        roles, fit = freeze_roles(splits, train_ref, dev_ref)
        writer.json("selected_uid_range_attachment.json", {"splits": splits, "roles": roles,
                    "constraint_uids": [r["uid"] for r in fit]})
        writer.json("verified_input_receipt.json", inputs.verified)
        writer.json("historical_witness_identity.json", witness)
        path = inputs.path(s.CHECKPOINT)
        s.require(path.stat().st_size == 1712912, "CHECKPOINT_CONTAINER_SIZE")
        state, projection = restricted_checkpoint(path.read_bytes(), inputs.pins[s.CHECKPOINT],
                                                   identities, terminal, audit, budget)
        model, hashes = assemble(state, inputs.read(s.HEAD), pins["model_assembly"], budget)
        del state
        s.require(hashes["assembled_state"] == pins["n3"]["model_identity"]["n1_assembled_state_tensor_sha256"],
                  "ASSEMBLED_N2_HASH")
        writer.json("assembled_state_before_decode.json", {**hashes, "projection": projection})
        index = json.loads(inputs.read(s.N1_OUTPUT + "/target64_index.json"))
        train_vectors = decode_train_cache(inputs.read(s.CACHE), index, splits["train"], inputs.pins[s.CACHE], budget)
        reference = json.loads(inputs.read(s.N1_OUTPUT + "/baseline_model_and_context_hashes.json"))
        candidate_hashes = json.loads(inputs.read(s.N1_OUTPUT + "/candidate_context_hashes.json"))
        s.require(reference["contexts"] == candidate_hashes["contexts"]
                  and candidate_hashes["backbone_sha256"] == hashes["non_head_state"], "N1_CONTEXT_CACHE_CHAIN")
        writer.json("train_cache_reference.json", {"index": index, "context_hashes": reference["contexts"],
                    "row_hashes": {u: s.digest(v.tobytes()) for u, v in train_vectors.items()}})
        loaded = {split: feature_contexts(inputs.path(s.FEATURES), splits[split], budget, audit)
                  for split in ("train", "internal_val")}
        decision = fit_once(model, loaded, train_vectors, reference["contexts"], train_ref, dev_ref,
                            roles, fit, writer, budget)
        expected = {"loads": 1, "head_decodes": 1, "assemblies": 1, "cache_decodes": 1,
                    "cache_values": 554240, "decoded_events": 205470, "decoded_train_events": 33305,
                    "decoded_dev_events": 172165, "lp_calls": 1, "baseline_dev_passes": 1}
        expected.update({"passes": 3, "batches": 428, "contexts": 13630, "targets": 19072,
                         "events": 377635, "installations": 1, "candidate_casts": 1,
                         "candidate_train_passes": 1, "candidate_dev_passes": 1}
                        if decision["candidate_present"] else
                        {"passes": 1, "batches": 136, "contexts": 4323, "targets": 5206,
                         "events": 172165, "installations": 0, "candidate_casts": 0})
        s.require(all(budget.counts[k] == v for k, v in expected.items()), "FINAL_ACTION_COUNTS")
        for phase, values in s.PHASE_COUNTS.items():
            active = phase == "baseline_dev" or decision["candidate_present"]
            s.require(all(budget.counts[phase + "_" + k] == (v if active else 0)
                          for k, v in values.items()), "FINAL_SPLIT_COUNTS")
        writer.json("access_receipt.json", audit)
        budget.check()
    except s.Stop as exc:
        decision = verdict(False, False, False, str(exc))
    except Exception as exc:
        decision = verdict(False, False, False, "UNEXPECTED_" + type(exc).__name__)
    data = s.json_bytes({"verdict": decision, "resource": budget.receipt(), "access": audit,
                         "output_hashes": writer.members})
    s.require(len(data) < s.CAPS["reserve_bytes"] // 2, "TERMINAL_RECEIPT_SIZE")
    with (Path(output) / "worker_terminal.json").open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return decision

