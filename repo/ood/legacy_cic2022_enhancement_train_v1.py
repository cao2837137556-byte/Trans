"""Matched, bounded P2 continuation on already prepared TRAIN arrays.

The caller owns file identities and real-execution authorization. This module
never opens a feature cache, checkpoint input, CHECK data, raw PCAP, or E3 model.
Its only file writes are the requested arm's terminal artifacts.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F


THETA = 0.065159872174263
SCHEMA = "legacy-cic2022-p2-enhancement-small-v1"
STATE_KEYS = ("normalizer_mean", "normalizer_scale", "p2__0.weight", "p2__0.bias", "p2__3.weight", "p2__3.bias")
REAL_PLAN_PINS = {
    "old_replay_target_plan.jsonl": "8bb5b0305659a31659fcd3391ddc515fa019ba8e421682bd1a6d9b11e39ead10",
    "new_train_target_plan.jsonl": "b20a274097928daec0714a55590c4252bec005e5e5e57a8f900aa1c3f64370f1",
}
REAL_OLD_UID_SHA = "06df1e11dc7f02be39f7e3ec53fb5f23c2342c32fd6f40ff909d50d01e8440ad"
TRAIN_FILES = [1, 4, 5, 6, 7, 9, 11, 12, 13, 16, 19, 22]
FIXED_OPT = {
    "seed": 27, "optimizer": "AdamW", "lr": 3e-4, "betas": [0.9, 0.999],
    "eps": 1e-8, "weight_decay": 1e-4, "amsgrad": False, "foreach": False,
    "full_batch_updates_per_arm": 200, "microbatch": 256, "gradient_clip_global_norm": 1.0,
    "old_weight": 0.8, "new_weight": 0.2, "rank_coefficient": {"B": 0.0, "C": 0.05},
    "rank_pairs": 29304, "rank_reuses_new_logits": True, "old_bce_class_balanced": True,
    "new_bce_device_label_capture_stream_balanced": True,
    "reset_identical_rng_before_each_arm": True, "rank_extra_forward_calls": 0,
    "training_row_exposures_per_arm": 2419800, "scheduler": None, "early_stopping": False,
    "checkpoint_selection": "Update200 only", "arm_order": ["B", "C"],
    "validation_during_training": False, "loss_trace_interval_updates": 10,
    "gradient_nonfinite_policy": "STOP", "retries": 0, "search": False,
}


class Stop(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise Stop(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def _json_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def target_plan_digest(targets):
    # Match the frozen JSONL writer, preserving dictionary field order.
    text = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n" for row in targets)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _array_digest(values):
    value = np.ascontiguousarray(values)
    h = hashlib.sha256()
    h.update(str(value.dtype).encode("ascii"))
    h.update(json.dumps(list(value.shape)).encode("ascii"))
    h.update(value.tobytes())
    return h.hexdigest()


def state_digest(state):
    require(set(state) == set(STATE_KEYS), "STATE_ALLOWLIST")
    return _json_digest({key: _array_digest(state[key]) for key in STATE_KEYS})


def _atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


def _dimensions(state, synthetic=False):
    require(set(state) == set(STATE_KEYS), "STATE_ALLOWLIST")
    require(all(isinstance(state[k], np.ndarray) for k in STATE_KEYS), "STATE_ARRAY_TYPES")
    d = int(state["normalizer_mean"].size)
    h = int(state["p2__0.bias"].size)
    shapes = {"normalizer_mean": (d,), "normalizer_scale": (d,),
              "p2__0.weight": (h, d + 1), "p2__0.bias": (h,),
              "p2__3.weight": (1, h), "p2__3.bias": (1,)}
    if synthetic:
        require((1 <= d <= 32 and 1 <= h <= 32) or (d, h) == (768, 128), "SYNTHETIC_SUPPORTED_DIMENSIONS")
    else:
        require((d, h) == (768, 128), "REAL_STATE_DIMENSIONS")
    for key, shape in shapes.items():
        dtype = np.float64 if key.startswith("normalizer") else np.float32
        require(state[key].shape == shape and state[key].dtype == dtype, "STATE_SCHEMA:" + key)
        require(bool(np.isfinite(state[key]).all()), "STATE_NONFINITE:" + key)
    require(bool((state["normalizer_scale"] > 0).all()), "NORMALIZER_SCALE")
    return d, h


def normalize_features(features, state, *, synthetic=False):
    """Return a fresh complete float32 input, with fixed-normalizer missing=0."""
    d, _ = _dimensions(state, synthetic)
    require(isinstance(features, np.ndarray) and features.dtype == np.float32,
            "FEATURE_FLOAT32_ARRAY")
    require(features.ndim == 2 and features.shape[1] == d and bool(np.isfinite(features).all()), "FEATURE_SHAPE_FINITE")
    z = (features.astype(np.float64) - state["normalizer_mean"]) / state["normalizer_scale"]
    result = np.concatenate((z, np.zeros((len(z), 1), dtype=np.float64)), axis=1).astype(np.float32)
    require(bool(np.isfinite(result).all()), "NORMALIZED_NONFINITE")
    return result


def build_model(state, dropout=0.1, *, synthetic=False):
    """Independent CPU float32 model, without changing the caller's RNG."""
    d, h = _dimensions(state, synthetic)
    require(math.isfinite(dropout) and (dropout == 0.1 or (synthetic and dropout == 0.0)), "DROPOUT")
    with torch.random.fork_rng(devices=[]):
        model = torch.nn.Sequential(torch.nn.Linear(d + 1, h), torch.nn.ReLU(),
                                    torch.nn.Dropout(dropout), torch.nn.Linear(h, 1)).to(dtype=torch.float32, device="cpu")
    values = {key[len("p2__"):]: torch.from_numpy(state[key].copy()) for key in STATE_KEYS if key.startswith("p2__")}
    model.load_state_dict(values, strict=True)
    return model


def score_fixed(state, features, *, batch_size=1024, theta=THETA, synthetic=False):
    require(type(batch_size) is int and batch_size > 0 and theta == THETA, "SCORE_CONFIGURATION")
    x = normalize_features(features, state, synthetic=synthetic)
    model = build_model(state, synthetic=synthetic).eval()
    raw, probabilities = [], []
    with torch.inference_mode():
        for start in range(0, len(x), batch_size):
            logits = model(torch.from_numpy(x[start:start + batch_size])).reshape(-1)
            require(bool(torch.isfinite(logits).all()), "SCORE_LOGITS_NONFINITE")
            raw.append(logits.numpy().astype(np.float64))
            probabilities.append(logits.sigmoid().numpy().astype(np.float64))
    logits = np.concatenate(raw) if raw else np.empty(0, dtype=np.float64)
    probability = np.concatenate(probabilities) if probabilities else np.empty(0, dtype=np.float64)
    return {"logits": logits, "probabilities": probability, "hard": probability >= theta}


def configure_runtime():
    torch.set_num_threads(4)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    require(torch.get_num_threads() == 4 and torch.get_num_interop_threads() == 1, "RUNTIME_THREADS")


def _fraction(row, numerator, denominator):
    require(type(row.get(numerator)) is int and type(row.get(denominator)) is int,
            "WEIGHT_INTEGER_SCHEMA:" + denominator)
    require(row[numerator] == 1 and row[denominator] > 0, "WEIGHT_POSITIVE_UNIT_NUMERATOR")
    return Fraction(row[numerator], row[denominator])


def validate_targets(old_targets, new_targets, recipe, *, synthetic=False):
    """Validate all weights from observed grouping, independently of floats."""
    require(isinstance(old_targets, list) and isinstance(new_targets, list) and old_targets and new_targets, "TARGET_LISTS")
    for rows in (old_targets, new_targets):
        require(all(isinstance(r, dict) and isinstance(r.get("uid"), str) and r["uid"] for r in rows), "TARGET_UID_SCHEMA")
        require([r["uid"] for r in rows] == sorted({r["uid"] for r in rows}), "TARGET_UID_SORT_OR_DUPLICATE")
        require(all(type(r.get("label")) is int and r["label"] in {0, 1} for r in rows), "TARGET_BINARY_LABEL")
    require(not {r["uid"] for r in old_targets} & {r["uid"] for r in new_targets}, "OLD_NEW_UID_OVERLAP")
    old_counts = Counter(r["label"] for r in old_targets)
    require(set(old_counts) == {0, 1}, "OLD_BOTH_CLASSES")
    old_weights = []
    for row in old_targets:
        require(row.get("owner") == "A" and row.get("planned_role") == "OLD_REPLAY", "OLD_ROLE")
        w = _fraction(row, "class_balanced_weight_numerator", "class_balanced_weight_denominator")
        require(w == Fraction(1, 2 * old_counts[row["label"]]), "OLD_CLASS_WEIGHT")
        old_weights.append(float(w))
    cells, captures, streams = defaultdict(set), defaultdict(set), defaultdict(list)
    capture_identity, stream_identity = {}, {}
    for row in new_targets:
        require(row.get("planned_role") == "TRAIN", "NEW_ROLE")
        require(isinstance(row.get("device"), str) and row["device"], "NEW_DEVICE")
        capture, stream = row.get("member_sha256"), row.get("stream")
        require(isinstance(capture, str) and len(capture) == 64 and isinstance(stream, str) and stream, "NEW_CAPTURE_STREAM")
        require(row.get("capture_dependency_group") == capture, "NEW_DEPENDENCY_GROUP")
        identity = (row["device"], row["label"], row.get("file_id"))
        require(capture_identity.setdefault(capture, identity) == identity, "CAPTURE_IDENTITY")
        key = (capture, stream)
        require(stream_identity.setdefault(key, identity[:2]) == identity[:2], "STREAM_IDENTITY")
        cells[identity[:2]].add(capture)
        captures[capture].add(stream)
        streams[key].append(row)
    devices = sorted({r["device"] for r in new_targets})
    require(len(devices) == 2 and set(cells) == {(d, label) for d in devices for label in (0, 1)}, "FOUR_DEVICE_LABEL_CELLS")
    for key, rows in streams.items():
        require(1 <= len(rows) <= 3, "STREAM_TARGET_CAP")
        candidates = {r.get("candidates_in_stream") for r in rows}
        require(len(candidates) == 1 and type(next(iter(candidates))) is int and next(iter(candidates)) >= len(rows), "CANDIDATE_COUNT")
        n = next(iter(candidates))
        require({r.get("candidate_ordinal_0based") for r in rows} == {0, (n - 1) // 2, n - 1}, "TARGET_ORDINALS")
        require(len({r.get("frame_number_1based") for r in rows}) == len(rows)
                and all(type(r.get("frame_number_1based")) is int and r["frame_number_1based"] >= 1 for r in rows), "TARGET_FRAME_IDENTITY")
    q, new_weights = [], []
    cell_sums = defaultdict(Fraction)
    for row in new_targets:
        cell = (row["device"], row["label"])
        capture, stream = row["member_sha256"], row["stream"]
        f, s, k = len(cells[cell]), len(captures[capture]), len(streams[(capture, stream)])
        require((row.get("captures_in_device_label_cell"), row.get("streams_in_capture"), row.get("selected_in_stream")) == (f, s, k), "HIERARCHY_DENOMINATORS")
        conditional = _fraction(row, "conditional_weight_numerator", "conditional_weight_denominator")
        bce = _fraction(row, "balanced_bce_weight_numerator", "balanced_bce_weight_denominator")
        evaluation = _fraction(row, "evaluation_label_weight_numerator", "evaluation_label_weight_denominator")
        require(conditional == Fraction(1, f * s * k) and bce == conditional / 4 and evaluation == conditional / 2, "NEW_EXACT_WEIGHT")
        cell_sums[cell] += conditional
        q.append(float(conditional))
        new_weights.append(float(bce))
    require(set(cell_sums.values()) == {Fraction(1)}, "CONDITIONAL_WEIGHT_SUMS")
    pairs, pair_count = [], 0
    for device in devices:
        pos = [i for i, r in enumerate(new_targets) if r["device"] == device and r["label"] == 1]
        neg = [i for i, r in enumerate(new_targets) if r["device"] == device and r["label"] == 0]
        pairs.append((device, np.asarray(pos, dtype=np.int64), np.asarray(neg, dtype=np.int64)))
        pair_count += len(pos) * len(neg)
    require(len(old_targets) == recipe["old_replay"]["rows"]
            and dict(old_counts) == {0: recipe["old_replay"]["benign"], 1: recipe["old_replay"]["attack"]}, "OLD_COUNTS")
    require(len(new_targets) == recipe["new_data"]["train_rows"]
            and Counter(r["label"] for r in new_targets) == {0: recipe["new_data"]["train_labels"]["benign"], 1: recipe["new_data"]["train_labels"]["attack"]}, "NEW_COUNTS")
    require(pair_count == recipe["optimization"]["rank_pairs"], "RANK_PAIR_COUNT")
    plan_hashes = {"old_replay_target_plan.jsonl": target_plan_digest(old_targets),
                   "new_train_target_plan.jsonl": target_plan_digest(new_targets)}
    if not synthetic:
        require(plan_hashes == REAL_PLAN_PINS, "FROZEN_TARGET_PLAN_IDENTITIES")
        uid_sha = hashlib.sha256("".join(r["uid"] + "\n" for r in old_targets).encode("utf-8")).hexdigest()
        require(uid_sha == recipe["old_replay"]["sorted_uid_lines_sha256"] == REAL_OLD_UID_SHA, "OLD_UID_IDENTITY")
        require(sorted({r["file_id"] for r in new_targets}) == TRAIN_FILES, "TRAIN_CAPTURE_SCOPE")
    else:
        require(len(old_targets) <= 128 and len(new_targets) <= 128, "SYNTHETIC_SMALL_TARGETS_ONLY")
    return {"old_labels": np.asarray([r["label"] for r in old_targets], dtype=np.float32),
            "new_labels": np.asarray([r["label"] for r in new_targets], dtype=np.float32),
            "old_weights": np.asarray(old_weights, dtype=np.float32),
            "new_weights": np.asarray(new_weights, dtype=np.float32),
            "conditional_weights": np.asarray(q, dtype=np.float32),
            "pairs": pairs, "pair_count": pair_count, "plan_hashes": plan_hashes}


def validate_recipe(recipe, state, *, synthetic=False):
    require(recipe.get("schema") == SCHEMA, "RECIPE_SCHEMA")
    d, h = _dimensions(state, synthetic)
    model, opt = recipe["model"], recipe["optimization"]
    require(model.get("head") == [d + 1, h, 1] and model.get("activation") == "ReLU", "MODEL_RECIPE")
    require(model.get("encoder_frozen") is True and model.get("normalizer_frozen") is True, "FROZEN_E3_NORMALIZER")
    require(model.get("state_array_allowlist") == list(STATE_KEYS), "STATE_RECIPE_ALLOWLIST")
    require(recipe["evaluation"].get("probability_threshold") == THETA and recipe["evaluation"].get("calibration") is False, "FIXED_THRESHOLD_RECIPE")
    exceptions = {"full_batch_updates_per_arm", "microbatch", "rank_pairs", "training_row_exposures_per_arm", "checkpoint_selection", "loss_trace_interval_updates"} if synthetic else set()
    for key, value in FIXED_OPT.items():
        if key not in exceptions:
            require(opt.get(key) == value, "FROZEN_OPTIMIZATION:" + key)
    if synthetic:
        mark = recipe.get("synthetic_fixture", {})
        require(mark.get("synthetic_only") is True and isinstance(mark.get("id"), str) and mark["id"], "SYNTHETIC_FIXTURE_MARKER")
        require(1 <= opt["full_batch_updates_per_arm"] <= 5 and 1 <= opt["microbatch"] <= 128, "SYNTHETIC_BUDGET")
        require(model.get("dropout") in {0.0, 0.1}, "SYNTHETIC_DROPOUT")
    else:
        require("synthetic_fixture" not in recipe and model.get("dropout") == 0.1 and model.get("parameter_count") == 98689, "REAL_MODEL_RECIPE")
        require(recipe["old_replay"]["rows"] == 11529 and recipe["new_data"]["train_rows"] == 570, "REAL_TRAIN_DENOMINATORS")
    runtime = recipe["runtime"]
    require(runtime.get("device") == "cpu" and runtime.get("dtype") == "float32" and runtime.get("amp") is False
            and runtime.get("deterministic_algorithms") is True and runtime.get("intraop_threads") == 4 and runtime.get("interop_threads") == 1, "RUNTIME_RECIPE")
    require(type(opt["full_batch_updates_per_arm"]) is int and type(opt["microbatch"]) is int, "INTEGER_BUDGET")
    require(opt["training_row_exposures_per_arm"] == opt["full_batch_updates_per_arm"] * (recipe["old_replay"]["rows"] + recipe["new_data"]["train_rows"]), "EXPOSURE_BUDGET")
    return d, h


def rank_loss(logits, plan):
    q = torch.from_numpy(plan["conditional_weights"])
    total = logits.new_zeros(())
    for _device, positive, negative in plan["pairs"]:
        a, b = torch.from_numpy(positive), torch.from_numpy(negative)
        differences = logits[a][:, None] - logits[b][None, :]
        total = total + 0.5 * (q[a][:, None] * q[b][None, :] * F.softplus(-differences)).sum()
    require(bool(torch.isfinite(total)), "RANK_LOSS_NONFINITE")
    return total


def accumulate_gradients(model, old_x, new_x, plan, optimization, arm):
    """One full objective, accumulated microbatches; no clip or optimizer step."""
    require(arm in {"B", "C"}, "ARM")
    require(old_x.dtype == new_x.dtype == torch.float32 and old_x.device.type == new_x.device.type == "cpu", "TRAIN_TENSOR_TYPE")
    model.train()
    model.zero_grad(set_to_none=True)
    microbatch = optimization["microbatch"]
    old_labels, old_weights = torch.from_numpy(plan["old_labels"]), torch.from_numpy(plan["old_weights"])
    new_labels, new_weights = torch.from_numpy(plan["new_labels"]), torch.from_numpy(plan["new_weights"])
    old_value, batches = 0.0, 0
    old_hash, new_hash = hashlib.sha256(), hashlib.sha256()
    for start in range(0, len(old_x), microbatch):
        stop = start + microbatch
        logits = model(old_x[start:stop]).reshape(-1)
        require(bool(torch.isfinite(logits).all()), "OLD_LOGITS_NONFINITE")
        old_hash.update(logits.detach().numpy().tobytes())
        part = (F.binary_cross_entropy_with_logits(logits, old_labels[start:stop], reduction="none") * old_weights[start:stop]).sum()
        require(bool(torch.isfinite(part)), "OLD_LOSS_NONFINITE")
        (optimization["old_weight"] * part).backward()
        old_value += float(part.detach())
        batches += 1
    pending = []
    for start in range(0, len(new_x), microbatch):
        logits = model(new_x[start:start + microbatch]).reshape(-1)
        require(bool(torch.isfinite(logits).all()), "NEW_LOGITS_NONFINITE")
        new_hash.update(logits.detach().numpy().tobytes())
        pending.append(logits)
        batches += 1
    logits = torch.cat(pending)
    new_loss = (F.binary_cross_entropy_with_logits(logits, new_labels, reduction="none") * new_weights).sum()
    coefficient = optimization["rank_coefficient"][arm]
    # B executes the same pair operations for diagnosis, without a rank graph.
    if arm == "B":
        with torch.no_grad():
            ranking = rank_loss(logits.detach(), plan)
    else:
        ranking = rank_loss(logits, plan)
    combined = optimization["new_weight"] * new_loss
    if coefficient:
        combined = combined + coefficient * ranking
    require(bool(torch.isfinite(combined)), "NEW_OBJECTIVE_NONFINITE")
    combined.backward()
    for parameter in model.parameters():
        require(parameter.grad is not None and bool(torch.isfinite(parameter.grad).all()), "GRADIENT_NONFINITE")
    new_value, rank_value = float(new_loss.detach()), float(ranking.detach())
    return {"old_bce": old_value, "new_bce": new_value, "rank_diagnostic": rank_value,
            "total_objective": optimization["old_weight"] * old_value + optimization["new_weight"] * new_value + coefficient * rank_value,
            "forward_batches": batches, "row_exposures": len(old_x) + len(new_x),
            "rank_pairs": plan["pair_count"], "old_forward_logits_sha256": old_hash.hexdigest(),
            "new_forward_logits_sha256": new_hash.hexdigest()}


def _export_state(model, original):
    result = {key: original[key].copy() for key in ("normalizer_mean", "normalizer_scale")}
    for key, value in model.state_dict().items():
        result["p2__" + key] = value.detach().cpu().numpy().copy()
    require(set(result) == set(STATE_KEYS), "EXPORTED_STATE_ALLOWLIST")
    return result


def train_arm(state, old_features, old_targets, new_features, new_targets, recipe,
              output_dir, arm, progress=None, *, synthetic=False):
    """Train exactly one endpoint; never read any paths other than own outputs.

    progress, if supplied, accepts one dictionary. It must not select epochs,
    modify tensors/model/RNG, or read CHECK data. Its failures stop this arm.
    """
    require(arm in {"B", "C"}, "ARM")
    out = Path(output_dir)
    if out.exists():
        require(out.is_dir() and not any(out.iterdir()), "OUTPUT_NOT_EMPTY_ZERO_RETRY")
    else:
        out.mkdir(parents=True)
    started = time.monotonic()
    status = {"status": "RUNNING", "stage": "TRAIN_" + arm, "arm": arm, "optimizer_update": 0, "synthetic": bool(synthetic)}

    def emit():
        status["elapsed_seconds"] = round(time.monotonic() - started, 6)
        _atomic_json(out / "status.json", status)
        if progress is not None:
            # Monitoring must not consume the model's dropout RNG stream.
            with torch.random.fork_rng(devices=[]):
                progress(dict(status))

    try:
        emit()
        validate_recipe(recipe, state, synthetic=synthetic)
        plan = validate_targets(old_targets, new_targets, recipe, synthetic=synthetic)
        require(len(old_features) == len(old_targets) and len(new_features) == len(new_targets), "FEATURE_TARGET_COUNT")
        before_state = state_digest(state)
        old_input_digest, new_input_digest = _array_digest(old_features), _array_digest(new_features)
        old_x = torch.from_numpy(normalize_features(old_features, state, synthetic=synthetic))
        new_x = torch.from_numpy(normalize_features(new_features, state, synthetic=synthetic))
        configure_runtime()
        opt = recipe["optimization"]
        updates = opt["full_batch_updates_per_arm"]
        expected_batches = updates * (math.ceil(len(old_x) / opt["microbatch"]) + math.ceil(len(new_x) / opt["microbatch"]))
        status.update(total=updates, old_rows=len(old_x), new_rows=len(new_x))
        trace_path = out / "loss_trace.jsonl"
        row_exposures, forward_batches = 0, 0
        first_forward = None
        with torch.random.fork_rng(devices=[]):
            model = build_model(state, recipe["model"]["dropout"], synthetic=synthetic)
            torch.manual_seed(opt["seed"])
            rng_start = _array_digest(torch.get_rng_state().numpy())
            optimizer = torch.optim.AdamW(model.parameters(), lr=opt["lr"], betas=tuple(opt["betas"]), eps=opt["eps"],
                                          weight_decay=opt["weight_decay"], amsgrad=opt["amsgrad"], foreach=opt["foreach"])
            with trace_path.open("x", encoding="utf-8") as trace:
                for update in range(1, updates + 1):
                    record = accumulate_gradients(model, old_x, new_x, plan, opt, arm)
                    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), opt["gradient_clip_global_norm"],
                                                          error_if_nonfinite=True, foreach=False)
                    require(bool(torch.isfinite(norm)), "GRADIENT_NORM_NONFINITE")
                    optimizer.step()
                    require(all(bool(torch.isfinite(p).all()) for p in model.parameters()), "UPDATED_PARAMETER_NONFINITE")
                    row_exposures += record["row_exposures"]
                    forward_batches += record["forward_batches"]
                    if first_forward is None:
                        first_forward = {key: record[key] for key in ("old_forward_logits_sha256", "new_forward_logits_sha256")}
                    if update == 1 or update % opt["loss_trace_interval_updates"] == 0 or update == updates:
                        record.update(update=update, measured_at="before_this_update", post_update_completed=True,
                                      gradient_norm_before_clip=float(norm), dropout_rng_after_forward_sha256=_array_digest(torch.get_rng_state().numpy()))
                        trace.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                        trace.flush()
                    status.update(optimizer_update=update, done=update, row_exposures=row_exposures, forward_batches=forward_batches)
                    if update == 1 or update % 10 == 0 or update == updates:
                        emit()
            rng_end = _array_digest(torch.get_rng_state().numpy())
            final_state = _export_state(model, state)
        require(row_exposures == opt["training_row_exposures_per_arm"] and forward_batches == expected_batches, "EXPOSURE_OR_FORWARD_BUDGET")
        require(state_digest(state) == before_state and _array_digest(old_features) == old_input_digest
                and _array_digest(new_features) == new_input_digest, "INPUTS_MUTATED")
        for key in ("normalizer_mean", "normalizer_scale"):
            require(np.array_equal(final_state[key], state[key]) and final_state[key].dtype == state[key].dtype, "NORMALIZER_MUTATED")
        checkpoint = out / "checkpoint.npz"
        temporary = out / "checkpoint.npz.tmp"
        with temporary.open("xb") as f:
            np.savez_compressed(f, **{key: final_state[key] for key in STATE_KEYS})
        with np.load(temporary, allow_pickle=False) as saved:
            require(set(saved.files) == set(STATE_KEYS) and all(np.array_equal(saved[key], final_state[key]) for key in STATE_KEYS), "CHECKPOINT_READBACK")
        os.replace(str(temporary), str(checkpoint))
        metadata = {"schema": "legacy-cic2022-enhancement-p2-endpoint-v1", "status": "COMPLETE", "arm": arm,
                    "synthetic": bool(synthetic), "optimizer_updates": updates, "checkpoint_selection": "fixed-final-update",
                    "row_exposures": row_exposures, "forward_batches": forward_batches, "rank_pairs_per_update": plan["pair_count"],
                    "rank_extra_forward_calls": 0, "encoder_updates": 0, "normalizer_unchanged": True,
                    "initial_state_digest": before_state, "final_state_digest": state_digest(final_state),
                    "initial_dropout_rng_sha256": rng_start, "final_dropout_rng_sha256": rng_end,
                    "first_update_forward_digests": first_forward, "recipe_digest": _json_digest(recipe),
                    "plan_digests": plan["plan_hashes"], "old_features_digest": old_input_digest, "new_features_digest": new_input_digest,
                    "checkpoint_path": str(checkpoint.resolve()), "checkpoint_sha256": sha256(checkpoint),
                    "loss_trace_path": str(trace_path.resolve()), "loss_trace_sha256": sha256(trace_path),
                    "mean_scale_digests": {key: _array_digest(final_state[key]) for key in ("normalizer_mean", "normalizer_scale")}}
        _atomic_json(out / "checkpoint.json", metadata)
        names = ("checkpoint.npz", "checkpoint.json", "loss_trace.jsonl")
        (out / "SHA256SUMS").write_text("".join(sha256(out / name) + "  " + name + "\n" for name in names), encoding="utf-8")
        status.update(status="COMPLETE", endpoint_sealed=True, checkpoint_sha256=metadata["checkpoint_sha256"])
        emit()
        return metadata
    except Exception as error:
        status.update(status="STOP", reason=str(error), exception_type=type(error).__name__, retries=0)
        # Error reporting must not turn a callback failure into a retry or hide it.
        status["elapsed_seconds"] = round(time.monotonic() - started, 6)
        _atomic_json(out / "status.json", status)
        raise


def make_synthetic_recipe(old_targets, new_targets, input_width=3, hidden_width=4,
                          updates=2, microbatch=2, dropout=0.1):
    """Small target/update fixtures; generated full-width arrays are supported."""
    old_counts, new_counts = Counter(r["label"] for r in old_targets), Counter(r["label"] for r in new_targets)
    devices = {r["device"] for r in new_targets}
    pair_count = sum(sum(r["device"] == d and r["label"] == 1 for r in new_targets) * sum(r["device"] == d and r["label"] == 0 for r in new_targets) for d in devices)
    opt = json.loads(json.dumps(FIXED_OPT))
    opt.update(full_batch_updates_per_arm=updates, microbatch=microbatch, rank_pairs=pair_count,
               training_row_exposures_per_arm=updates * (len(old_targets) + len(new_targets)),
               checkpoint_selection="Synthetic final update only", loss_trace_interval_updates=1)
    return {"schema": SCHEMA, "synthetic_fixture": {"id": "small-generated-only-v1", "synthetic_only": True},
            "model": {"head": [input_width + 1, hidden_width, 1], "activation": "ReLU", "dropout": dropout,
                      "encoder_frozen": True, "normalizer_frozen": True, "state_array_allowlist": list(STATE_KEYS)},
            "old_replay": {"rows": len(old_targets), "benign": old_counts[0], "attack": old_counts[1]},
            "new_data": {"train_rows": len(new_targets), "train_labels": {"benign": new_counts[0], "attack": new_counts[1]}},
            "optimization": opt, "evaluation": {"probability_threshold": THETA, "calibration": False},
            "runtime": {"device": "cpu", "dtype": "float32", "amp": False, "deterministic_algorithms": True,
                        "intraop_threads": 4, "interop_threads": 1}}
