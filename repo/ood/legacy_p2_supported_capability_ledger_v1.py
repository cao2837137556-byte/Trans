"""Bounded fixed-P2 capability ledger. No optimizer, raw PCAP or E3 forward.

Only P2 numeric columns are parsed from the archived mixed-probe score CSV.
Representation members are streamed; unrequested row bytes stay opaque.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import time
import traceback
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np


THETA = 0.065159872174263
CONTRACT = "ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9"
META = ("uid", "role", "phase", "source_group", "device_family", "attack_family", "label_metric_only")
ALIASES = {"fit_plan", "report_plan", "report_scores", "fit_embeddings", "report_embeddings", "state", "threshold_marker"}
STATE_SHAPES = {"normalizer_mean": (768,), "normalizer_scale": (768,),
                "p2__0.weight": (128, 769), "p2__0.bias": (128,),
                "p2__3.weight": (1, 128), "p2__3.bias": (1,)}
REPORT_ROLES = {"support_val": 69, "same_file_query": 2486, "future_query": 131391,
                "sealed_final_attack": 110104, "ood_val": 3000, "sealed_final_ood": 3000,
                "aux_report": 9000, "ood_stress": 3000}
NORMAL_POOLS = {"iotsim-hydraulic-system": "hydraulic", "iotsim-ip-camera-street": "street",
                "iotsim-predictive-maintenance": "predictive", "iotsim-stream-consumer": "stream"}
EXPECTED_POOLS = {"hydraulic": (3000, 2974), "street": (3000, 3000),
                  "predictive": (9000, 7916), "stream": (3000, 3000)}


class Stop(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Stop(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


class Progress:
    def __init__(self, out):
        self.out = Path(out)
        self.started = time.monotonic()
        self.last = {}

    def emit(self, stage, done=0, total=0, **extra):
        self.last = dict(status="RUNNING", stage=stage, done=int(done), total=int(total),
                         elapsed_seconds=round(time.monotonic() - self.started, 3), **extra)
        atomic_json(self.out / "status.json", self.last)
        (self.out / "status.md").write_text(
            "# Fixed old P2 capability ledger\n\n" + json.dumps(self.last, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        with (self.out / "progress.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(self.last, ensure_ascii=False) + "\n")
        print(json.dumps(self.last, ensure_ascii=False), flush=True)

    def finish(self, status, **extra):
        value = dict(self.last, status=status, elapsed_seconds=round(time.monotonic() - self.started, 3), **extra)
        atomic_json(self.out / "finalstatus.json", value)
        atomic_json(self.out / "status.json", value)
        (self.out / "status.md").write_text(
            "# Fixed old P2 capability ledger\n\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")


def read_plan(path):
    """Project metadata fields only, without converting other CSV columns."""
    rows, seen = [], set()
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        require(set(META) <= set(reader.fieldnames or []), "PLAN_HEADER")
        for raw in reader:
            row = {key: raw[key] for key in META}
            require(row["uid"] and row["uid"] not in seen, "PLAN_UID_DUPLICATE")
            require(row["label_metric_only"] in ("0", "1"), "PLAN_LABEL")
            row["label_metric_only"] = int(row["label_metric_only"])
            seen.add(row["uid"])
            rows.append(row)
    return rows


def read_p2_archive(path, plan, theta=THETA):
    mapping = {r["uid"]: i for i, r in enumerate(plan)}
    require(len(mapping) == len(plan), "ARCHIVE_PLAN_DUPLICATE")
    n = len(plan)
    scores = np.full(n, np.nan, dtype=np.float64)
    hard = np.zeros(n, dtype=bool)
    missing = np.zeros(n, dtype=bool)
    seen = np.zeros(n, dtype=bool)
    skipped = Counter()
    required = {"candidate_id", "probe_id", "uid", "role", "source_group", "device_family",
                "attack_family", "label_metric_only", "score", "hard", "missing"}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        require(required <= set(reader.fieldnames or []), "SCORE_HEADER")
        for raw in reader:
            probe = raw["probe_id"]
            if probe != "P2":
                require(probe in {"G0", "P1"}, "UNEXPECTED_PROBE")
                skipped[probe] += 1
                continue  # No numerical conversion, metadata join, or score access for these probes.
            require(raw["candidate_id"] == "E3", "SCORE_CANDIDATE")
            uid = raw["uid"]
            require(uid in mapping, "SCORE_UNKNOWN_UID")
            i = mapping[uid]
            require(not seen[i], "SCORE_DUPLICATE_UID")
            row = plan[i]
            for key in ("role", "source_group", "device_family", "attack_family"):
                require(raw[key] == row[key], "SCORE_METADATA_JOIN:" + key)
            require(raw["label_metric_only"] in {"0", "1"} and int(raw["label_metric_only"]) == row["label_metric_only"], "SCORE_LABEL_JOIN")
            require(raw["hard"] in {"0", "1"} and raw["missing"] in {"0", "1"}, "SCORE_BOOLEAN")
            value = float(raw["score"])
            require(math.isfinite(value) and 0.0 <= value <= 1.0, "P2_PROBABILITY")
            scores[i], hard[i], missing[i], seen[i] = value, raw["hard"] == "1", raw["missing"] == "1", True
            require(bool(value >= theta) == bool(hard[i]), "ARCHIVE_THRESHOLD_MISMATCH")
    require(bool(seen.all()), "ARCHIVE_UID_COVERAGE")
    return scores, hard, missing, dict(skipped)


def read_npz_arrays(path, names):
    """Open only explicitly allowed NPY members, never the representation member."""
    result = {}
    with zipfile.ZipFile(path) as z:
        members = z.namelist()
        for name in names:
            require(name != "representation", "FULL_REPRESENTATION_READ_FORBIDDEN")
            member = name + ".npy"
            require(members.count(member) == 1, "NPZ_MEMBER:" + name)
            with z.open(member) as f:
                result[name] = np.lib.format.read_array(f, allow_pickle=False)
                require(f.read(1) == b"", "NPY_TRAILING:" + name)
    return result


def embedding_metadata(path, plan, plan_sha):
    names = ("uid", "missing", "candidate_id", "plan_sha256", "contract_sha256")
    values = read_npz_arrays(path, names)
    uids, missing = values["uid"], values["missing"]
    require(uids.ndim == 1 and uids.dtype.kind == "U" and missing.dtype == np.bool_ and missing.shape == uids.shape, "EMBEDDING_METADATA_SCHEMA")
    require(len(uids) == len(plan), "EMBEDDING_METADATA_COUNT")
    require(values["candidate_id"].tolist() == ["E3"], "EMBEDDING_CANDIDATE")
    require(values["plan_sha256"].tolist() == [plan_sha], "EMBEDDING_PLAN_IDENTITY")
    require(values["contract_sha256"].tolist() == [CONTRACT], "EMBEDDING_CONTRACT")
    mapping = {str(uid): i for i, uid in enumerate(uids)}
    require(len(mapping) == len(uids) and set(mapping) == {r["uid"] for r in plan}, "EMBEDDING_UID_JOIN")
    return mapping, missing


def selective_batches(path, indices, expected_rows, width=768, batch_size=1024, audit=None):
    """Yield (physical indices, float32 rows); skipped bytes are never decoded."""
    audit = audit if audit is not None else {}
    indices = list(indices)
    require(indices == sorted(set(indices)) and all(0 <= i < expected_rows for i in indices), "ROW_INDICES")
    wanted, kept, physical = set(indices), [], []
    with zipfile.ZipFile(path) as z:
        require(z.namelist().count("representation.npy") == 1, "REPRESENTATION_MEMBER")
        with z.open("representation.npy") as f:
            version = np.lib.format.read_magic(f)
            require(version in {(1, 0), (2, 0)}, "NPY_VERSION")
            header = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
            shape, fortran, dtype = header(f)
            require(tuple(shape) == (expected_rows, width) and not fortran and dtype == np.dtype("<f4"), "REPRESENTATION_HEADER")
            for i in range(expected_rows):
                raw = f.read(width * 4)
                require(len(raw) == width * 4, "SHORT_REPRESENTATION")
                audit["opaque_representation_bytes"] = audit.get("opaque_representation_bytes", 0) + len(raw)
                if i in wanted:
                    row = np.frombuffer(raw, dtype="<f4").copy()
                    require(bool(np.isfinite(row).all()), "SELECTED_NONFINITE")
                    kept.append(row)
                    physical.append(i)
                    audit["numeric_representation_rows"] = audit.get("numeric_representation_rows", 0) + 1
                    if len(kept) == batch_size:
                        yield np.asarray(physical, dtype=np.int64), np.stack(kept)
                        kept, physical = [], []
            require(f.read(1) == b"", "REPRESENTATION_TRAILING_BYTES")
    if kept:
        yield np.asarray(physical, dtype=np.int64), np.stack(kept)


def load_p2_state(path):
    state = read_npz_arrays(path, STATE_SHAPES)
    for key, shape in STATE_SHAPES.items():
        require(state[key].shape == shape and state[key].dtype.kind == "f" and bool(np.isfinite(state[key]).all()), "P2_STATE:" + key)
    require(bool((state["normalizer_scale"] > 0).all()), "P2_SCALE")
    return state


def canonical_p2(representations, state):
    """Literal valid-input float64-normalize -> complete float32 row -> P2."""
    import torch
    import torch.nn.functional as F
    z = np.asarray(representations)
    require(z.dtype == np.float32 and z.ndim == 2 and z.shape[1] == 768 and bool(np.isfinite(z).all()), "CANONICAL_INPUT")
    normalized = (z.astype(np.float64) - state["normalizer_mean"].astype(np.float64)) / state["normalizer_scale"].astype(np.float64)
    x = np.concatenate((normalized, np.zeros((len(z), 1), dtype=np.float64)), axis=1).astype(np.float32)
    require(bool(np.isfinite(x).all()), "CANONICAL_STANDARDIZATION")
    with torch.inference_mode():
        h = F.relu(F.linear(torch.from_numpy(x), torch.as_tensor(state["p2__0.weight"], dtype=torch.float32), torch.as_tensor(state["p2__0.bias"], dtype=torch.float32)))
        logits = F.linear(h, torch.as_tensor(state["p2__3.weight"], dtype=torch.float32), torch.as_tensor(state["p2__3.bias"], dtype=torch.float32)).reshape(-1)
        probs = torch.sigmoid(logits)
        require(bool(torch.isfinite(logits).all()) and bool(torch.isfinite(probs).all()), "P2_NONFINITE")
        return logits.numpy().astype(np.float64), probs.numpy().astype(np.float64)


def score_selected(path, mapping, physical_missing, targets, state, progress, stage, audit):
    require(len({r["uid"] for r in targets}) == len(targets), "TARGET_DUPLICATE")
    physical_to_target = {}
    missing = np.zeros(len(targets), dtype=bool)
    for i, row in enumerate(targets):
        require(row["uid"] in mapping, "TARGET_UNKNOWN_UID")
        j = mapping[row["uid"]]
        missing[i] = physical_missing[j]
        if not missing[i]:
            physical_to_target[j] = i
    logits = np.full(len(targets), np.nan)
    probs = np.full(len(targets), np.nan)
    done = 0
    for physical, z in selective_batches(path, sorted(physical_to_target), len(mapping), audit=audit):
        raw, probability = canonical_p2(z, state)
        dest = [physical_to_target[int(j)] for j in physical]
        logits[dest], probs[dest] = raw, probability
        done += len(dest)
        audit["P2_forward_batches"] = audit.get("P2_forward_batches", 0) + 1
        if done % (16 * 1024) == 0 or done == len(physical_to_target):
            progress.emit(stage, done, len(physical_to_target))
    require(done == len(physical_to_target) and bool(np.isfinite(logits[~missing]).all()), "FORWARD_COVERAGE")
    return logits, probs, missing


def exposure_sets(fit):
    trained = Counter(r["attack_family"] for r in fit if r["phase"] == "fit" and r["label_metric_only"] == 1)
    calibrated = Counter(r["attack_family"] for r in fit if r["phase"] == "select" and r["label_metric_only"] == 1)
    return trained, calibrated


def ledger_metric(hard, missing, mask):
    mask = np.asarray(mask, dtype=bool)
    valid = mask & ~missing
    missing_mask = mask & missing
    n, v, m = int(mask.sum()), int(valid.sum()), int(missing_mask.sum())
    def fraction(num, den):
        return None if den == 0 else float(num / den)
    hard_all = int(hard[mask].sum())
    hard_valid = int(hard[valid].sum())
    return {"all_rows": n, "valid_rows": v, "missing_rows": m,
            "coverage": fraction(v, n), "archived_hard_all": hard_all,
            "archived_hard_missing": int(hard[missing_mask].sum()),
            "hard_valid": hard_valid, "soft_valid": v - hard_valid,
            "hard_rate_valid": fraction(hard_valid, v), "hard_rate_all_original": fraction(hard_all, n)}


def low_fpr_points(scores, labels, pools, future, family_seen, denominators=(100, 1000)):
    """Exact score groups and integer FPR bounds; no interpolation or tuning."""
    scores = np.asarray(scores, dtype=np.float64)
    labels, future, family_seen = (np.asarray(x, dtype=bool) for x in (labels, future, family_seen))
    pools = np.asarray(pools, dtype=str)
    require(scores.shape == labels.shape == pools.shape == future.shape == family_seen.shape, "CURVE_SHAPE")
    require(bool(np.isfinite(scores).all()), "CURVE_FINITE")
    names = sorted(set(pools[~labels]))
    require(names and "" not in names and bool((pools[labels] == "").all()), "CURVE_POOLS")
    pool_counts = np.asarray([int(((pools == name) & ~labels).sum()) for name in names], dtype=np.int64)
    require(bool((pool_counts > 0).all()) and bool(labels.any()), "CURVE_DENOMINATORS")
    pool_index = {name: i for i, name in enumerate(names)}
    targets = {"attack": labels, "future": labels & future,
               "fit_exact_family_seen": labels & family_seen,
               "fit_exact_family_not_seen": labels & ~family_seen}
    target_names = list(targets)
    total_tp = np.asarray([int(targets[k].sum()) for k in target_names], dtype=np.int64)
    tp, fp = np.zeros(len(targets), dtype=np.int64), np.zeros(len(names), dtype=np.int64)

    def point(threshold):
        return {"threshold_kind": "NO_HARD" if threshold is None else "FINITE", "diagnostic_threshold": threshold,
                "worst_pool_fpr": float(np.max(fp / pool_counts)),
                "normal_pools": {name: {"false_positives": int(fp[i]), "rows": int(pool_counts[i]), "fpr": float(fp[i] / pool_counts[i])} for i, name in enumerate(names)},
                "attack": {name: {"detected": int(tp[i]), "rows": int(total_tp[i]), "recall": None if total_tp[i] == 0 else float(tp[i] / total_tp[i])} for i, name in enumerate(target_names)}}

    best = {str(d): point(None) for d in denominators}
    order = np.argsort(-scores, kind="stable")
    positions = np.flatnonzero(np.r_[True, scores[order][1:] != scores[order][:-1], True])
    frontier = [point(None)]
    for start, stop in zip(positions[:-1], positions[1:]):
        group = order[start:stop]
        for j in group[~labels[group]]:
            fp[pool_index[pools[j]]] += 1
        for i, name in enumerate(target_names):
            tp[i] += int(targets[name][group].sum())
        admissible = [d for d in denominators if bool(np.all(fp * d <= pool_counts))]
        if not admissible:
            break  # Every subsequent lower threshold can only increase each pool FPR.
        current = point(float(scores[order[start]]))
        # All target recalls are monotone under this common threshold.
        for d in admissible:
            best[str(d)] = current
        if len(frontier) == 1 or current["worst_pool_fpr"] != frontier[-1]["worst_pool_fpr"]:
            frontier.append(current)
        else:
            frontier[-1] = current
    return {"score_groups_indivisible": True, "comparison": ">=", "no_interpolation": True,
            "deployment_threshold_selected": False, "empirical_only": True,
            "points": {str(1 / d): best[str(d)] for d in denominators},
            "frontier_through_max_requested_fpr": frontier,
            "normal_pool_rows": dict(zip(names, (int(n) for n in pool_counts))),
            "attack_rows": dict(zip(target_names, (int(n) for n in total_tp)))}


def write_scores(out, batches, theta):
    fields = ["subset", "uid", "role", "source_group", "device_family", "attack_family", "label", "missing",
              "raw_logit", "immutable_archived_probability", "fixed_rescore_probability", "canonical_hard"]
    path = out / "P2_fixed_scores.csv.gz"
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for subset, rows, missing, raw, fresh, archived, hard in batches:
            for i, row in enumerate(rows):
                item = {key: row[key] for key in ("uid", "role", "source_group", "device_family", "attack_family")}
                item.update(subset=subset, label=row["label_metric_only"], missing=int(missing[i]),
                            raw_logit="" if missing[i] else float(raw[i]),
                            immutable_archived_probability="" if archived is None else float(archived[i]),
                            fixed_rescore_probability="" if missing[i] else float(fresh[i]),
                            canonical_hard=(int(hard[i]) if archived is not None else ("" if missing[i] else int(fresh[i] >= theta))))
                writer.writerow(item)
    return path


def run(scope_path, out, authorized=False):
    require(authorized, "EXECUTION_AUTHORIZATION_REQUIRED")
    scope = json.loads(Path(scope_path).read_text(encoding="utf-8"))
    require(scope.get("schema") == "legacy-p2-supported-ledger-v1", "SCOPE_SCHEMA")
    auth = scope.get("authorization", {})
    require(auth.get("real_fixed_scoring") is True and all(auth.get(k) is False for k in ("training", "raw_pcap", "new_CIC_CHECK")), "SCOPE_AUTHORIZATION")
    require(float(scope.get("theta", math.nan)) == THETA and set(scope.get("assets", {})) == ALIASES, "SCOPE_FIXED_IDENTITY")
    root = Path(scope["workspace_root"]).resolve()
    require(root.is_dir(), "WORKSPACE_ROOT")
    if "code_sha256" in scope:
        require(scope["code_sha256"] == sha256(Path(__file__)), "CODE_IDENTITY")
    out = Path(out).resolve()
    require(root == out or root in out.parents, "OUTPUT_OUTSIDE_WORKSPACE")
    out.mkdir(parents=True, exist_ok=True)
    require(not any((out / name).exists() for name in ("finalstatus.json", "status.json", "summary.json", "P2_fixed_scores.csv.gz")), "OUTPUT_ALREADY_USED_ZERO_RETRY")
    progress = Progress(out)
    try:
        progress.emit("VERIFY_INPUT_IDENTITIES", 0, len(ALIASES))
        paths = {}
        for i, (alias, spec) in enumerate(scope["assets"].items()):
            p = (root / spec["path"]).resolve()
            require(root in p.parents and p.is_file(), "ASSET_PATH:" + alias)
            require(sha256(p) == spec["sha256"], "ASSET_SHA:" + alias)
            paths[alias] = p
            progress.emit("VERIFY_INPUT_IDENTITIES", i + 1, len(ALIASES), asset=alias)
        marker = json.loads(paths["threshold_marker"].read_text(encoding="utf-8"))
        require(marker.get("status") == "CKDA_D1_THRESHOLDS_FROZEN" and marker.get("candidate_id") == "E3" and marker.get("contract_sha256") == CONTRACT, "THRESHOLD_MARKER")
        p2_threshold = marker.get("thresholds", {}).get("P2", {})
        require(p2_threshold.get("kind") == "FINITE" and float(p2_threshold.get("value", math.nan)) == THETA, "P2_THRESHOLD")
        require(marker.get("probe_state_sha256") == scope["assets"]["state"]["sha256"], "MARKER_STATE_SHA")
        fit, report = read_plan(paths["fit_plan"]), read_plan(paths["report_plan"])
        require(len(fit) == 25467 and Counter(r["phase"] for r in fit) == {"fit": 18398, "select": 7069}, "FIT_COUNTS")
        require(len(report) == 262050 and Counter(r["role"] for r in report) == REPORT_ROLES, "REPORT_COUNTS")
        trained, calibrated = exposure_sets(fit)
        require(sum(trained.values()) == 4385 and len(trained) == 12 and sum(calibrated.values()) == 69 and len(calibrated) == 10, "FAMILY_EXPOSURE_COUNTS")
        progress.emit("READ_ARCHIVED_P2_ONLY", 0, len(report))
        archived, original_hard, archive_missing, skipped = read_p2_archive(paths["report_scores"], report)
        require(skipped == {"G0": 262050, "P1": 262050}, "SKIPPED_PROBE_COUNTS")
        report_map, report_missing_physical = embedding_metadata(paths["report_embeddings"], report, scope["assets"]["report_plan"]["sha256"])
        fit_map, fit_missing_physical = embedding_metadata(paths["fit_embeddings"], fit, scope["assets"]["fit_plan"]["sha256"])
        require(np.array_equal(archive_missing, [report_missing_physical[report_map[r["uid"]]] for r in report]), "REPORT_MISSING_JOIN")
        labels = np.asarray([r["label_metric_only"] for r in report], dtype=bool)
        valid = ~archive_missing
        require(int(valid.sum()) == 197268 and int((valid & labels).sum()) == 180378 and int((valid & ~labels).sum()) == 16890, "REPORT_VALID_COUNTS")
        familiar = [r for r in fit if r["role"] in {"aux_select", "aux_normal_select"}]
        ident = [r for r in fit if r["role"] == "id_calib"]
        require(len(familiar) == 7000 and len(ident) == 809 and all(r["label_metric_only"] == 0 for r in familiar + ident), "FAMILIAR_ID_SCOPE")
        import torch
        torch.set_num_threads(4)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
        state = load_p2_state(paths["state"])
        audit = {"training_steps": 0, "raw_captures_read": 0, "E3_forward_calls": 0, "G0_P1_numeric_rows_read": 0, "state_arrays_read": list(STATE_SHAPES)}
        report_raw, report_fresh, rescored_missing = score_selected(paths["report_embeddings"], report_map, report_missing_physical, report, state, progress, "FIXED_P2_REPORT_LOGITS", audit)
        require(np.array_equal(rescored_missing, archive_missing), "RESCORE_MISSING")
        mismatch = int(np.count_nonzero((report_fresh[valid] >= THETA) != original_hard[valid]))
        equivalence = {"rows": int(valid.sum()), "hard_mismatches": mismatch,
                       "max_probability_absolute_difference": float(np.max(np.abs(report_fresh[valid] - archived[valid]))),
                       "mean_probability_absolute_difference": float(np.mean(np.abs(report_fresh[valid] - archived[valid])))}
        atomic_json(out / "fixed_rescore_equivalence.json", equivalence)
        require(mismatch == 0, "FIXED_P2_ARCHIVED_HARD_MISMATCH")
        other = familiar + ident
        other_raw, other_prob, other_missing = score_selected(paths["fit_embeddings"], fit_map, fit_missing_physical, other, state, progress, "FIXED_P2_FAMILIAR_AND_ID", audit)
        fraw, iraw = other_raw[:7000], other_raw[7000:]
        fprob, iprob = other_prob[:7000], other_prob[7000:]
        fmissing, imissing = other_missing[:7000], other_missing[7000:]
        require(int((~fmissing).sum()) == 2188 and int((~imissing).sum()) == 760, "FAMILIAR_ID_VALID_COUNTS")
        require(audit["numeric_representation_rows"] == 200216, "NUMERIC_ROW_BUDGET")
        progress.emit("AGGREGATE_FIXED_BASELINE", len(report), len(report))
        families = np.asarray([r["attack_family"] for r in report])
        roles = np.asarray([r["role"] for r in report])
        devices = np.asarray([r["device_family"] for r in report])
        fit_seen = np.asarray([r["attack_family"] in trained for r in report])
        calibration_seen = np.asarray([r["attack_family"] in calibrated for r in report])
        future = roles == "future_query"
        summary = {"status": "FIXED_OLD_P2_SUPPORTED_CAPABILITY_LEDGER_COMPLETE", "probability_threshold": THETA,
                   "primary_report_source": "Immutable archived P2 probability and hard decision",
                   "scope": "Previously exposed development pools; not independent final evidence",
                   "coverage": ledger_metric(original_hard, archive_missing, np.ones(len(report), dtype=bool)),
                   "attack": ledger_metric(original_hard, archive_missing, labels),
                   "future_query": ledger_metric(original_hard, archive_missing, labels & future),
                   "family_exposure": {"basis": "All original 18398 P2 fit rows, including missing inputs; family-string supervision exposure is not proof of learned detection or novel mechanism generalization",
                                       "original_fit_attack_rows_by_family": dict(trained), "original_threshold_support_rows_by_family": dict(calibrated)},
                   "attack_by_family": {}, "attack_by_role": {}, "attack_by_exposure": {}, "normal_pools": {},
                   "numerical_equivalence": equivalence, "access_audit": audit,
                   "limitations": ["Same campaign/device and historical fitting/calibration exposure remain", "Exact novel family strings may overlap trained scan, credential-bruteforce or C&C behavior", "Missing input outputs retained only in original coverage ledger", "No baseline retraining, new threshold calibration, or commissioning evidence"]}
        for family in sorted(set(families[labels])):
            value = ledger_metric(original_hard, archive_missing, labels & (families == family))
            value.update(fit_family_seen=family in trained, threshold_family_seen=family in calibrated)
            summary["attack_by_family"][family] = value
        for role in sorted(set(roles[labels])):
            summary["attack_by_role"][role] = ledger_metric(original_hard, archive_missing, labels & (roles == role))
        for name, mask in (("fit_family_seen", fit_seen), ("fit_family_not_seen", ~fit_seen),
                           ("threshold_family_seen", calibration_seen), ("threshold_family_not_seen", ~calibration_seen)):
            summary["attack_by_exposure"][name] = ledger_metric(original_hard, archive_missing, labels & mask)
        report_pool = np.full(len(report), "", dtype="U32")
        for device, name in NORMAL_POOLS.items():
            mask = ~labels & (devices == device)
            value = ledger_metric(original_hard, archive_missing, mask)
            require((value["all_rows"], value["valid_rows"]) == EXPECTED_POOLS[name], "NORMAL_POOL_COUNTS:" + name)
            summary["normal_pools"][name] = value
            report_pool[mask] = name
        require(bool((report_pool[~labels] != "").all()), "NORMAL_POOL_MAPPING")
        for name, rows, probabilities, missing in (("familiar_normal", familiar, fprob, fmissing), ("id_fit_diagnostic", ident, iprob, imissing)):
            ok = ~missing
            count, fp = int(ok.sum()), int((probabilities[ok] >= THETA).sum())
            summary[name] = {"all_rows": len(rows), "valid_rows": count, "missing_rows": int(missing.sum()),
                             "false_positives": fp, "true_negatives": count - fp, "fpr": fp / count,
                             "acceptance": (count - fp) / count, "historical_missing_scores_not_opened": True,
                             "purpose": "Old fit preservation only" if name == "id_fit_diagnostic" else "Exposed familiar-normal development check; not fresh ID test"}
        curve_labels = np.r_[labels[valid], np.zeros(int((~fmissing).sum()), dtype=bool)]
        curve_pools = np.r_[report_pool[valid], np.full(int((~fmissing).sum()), "familiar_normal")]
        curve_future = np.r_[future[valid], np.zeros(int((~fmissing).sum()), dtype=bool)]
        curve_seen = np.r_[fit_seen[valid], np.zeros(int((~fmissing).sum()), dtype=bool)]
        probability_curve = low_fpr_points(np.r_[archived[valid], fprob[~fmissing]], curve_labels, curve_pools, curve_future, curve_seen)
        logit_curve = low_fpr_points(np.r_[report_raw[valid], fraw[~fmissing]], curve_labels, curve_pools, curve_future, curve_seen)
        low = {"purpose": "Both fixed beforehand: archived-native probability and rescored raw-logit descriptive diagnostics; no deployment threshold selection",
               "normal_rows": 19078, "attack_rows": 180378, "ID_fit_excluded": True,
               "native_probability": probability_curve, "raw_logit": logit_curve,
               "native_probability_ties": {"attack_at_one": int((archived[valid & labels] == 1.0).sum()), "normal_at_one": int((np.r_[archived[valid & ~labels], fprob[~fmissing]] == 1.0).sum()),
                                            "raw_logit_recovers_order_only_where_present": True}}
        atomic_json(out / "low_FPR_points.json", low)
        score_path = write_scores(out, [("expanded", report, archive_missing, report_raw, report_fresh, archived, original_hard),
                                       ("familiar_normal", familiar, fmissing, fraw, fprob, None, None),
                                       ("id_fit_diagnostic", ident, imissing, iraw, iprob, None, None)], THETA)
        summary["output_score_rows"] = len(report) + len(other)
        summary["P2_fixed_scores_sha256"] = sha256(score_path)
        summary["scope_sha256"] = sha256(scope_path)
        summary["script_sha256"] = sha256(Path(__file__))
        atomic_json(out / "summary.json", summary)
        files = ["summary.json", "low_FPR_points.json", "P2_fixed_scores.csv.gz", "fixed_rescore_equivalence.json"]
        (out / "SHA256SUMS").write_text("".join(sha256(out / name) + "  " + name + "\n" for name in files), encoding="utf-8")
        progress.finish("COMPLETE", exit_code=0, artifacts_sealed=True, training_steps=0,
                        report_rows=262050, fixed_forward_rows=200216)
        return summary
    except Exception as error:
        (out / "error_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        progress.finish("STOP", exit_code=1, reason=str(error), exception_type=type(error).__name__, retries=0)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    args = parser.parse_args()
    try:
        run(args.scope, args.out, args.execute_authorized)
    except Exception as error:
        print("STOP: " + str(error), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
