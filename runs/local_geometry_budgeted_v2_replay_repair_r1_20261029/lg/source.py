"""Explicit source experiment; importing this module never reads scientific data.

The six completed BASE heads are reused without an optimizer.  Source and main
head ensembles deliberately have different adapters.  All source bank scoring
is shared across seeds, and all input files are sealed before any new forward.
"""
from __future__ import annotations

import gc
import gzip
import json
import os
from pathlib import Path
import platform
import sys
import zipfile

import numpy as np

from .common import require, sha, read_json, array_sha, uid_sha


SEEDS = (27, 127, 227)
SUFFIXES = ("27", "127", "227", "ensemble")
LAMBDAS = (0.0, 0.05, 0.1, 0.25)
MAIN_FILES = "runs/one_component_readonly_inventory_v1_20261028/analysis/MAIN_ASSET_FILES.json"
MAIN_FILES_SHA = "59c4d83c15fcd9da4dc9ddde590f07538a56369dc72ba491d7212f5c4737e574"
SOURCE_ADAPTER_ASSETS = "runs/phase_conditioned_calibration_v1_20261028/ASSETS.json"
SOURCE_ADAPTER_ASSETS_SHA = "b311015454464967dfa59cadd00f4e2205f7e6bec73503831bd6d89f2d9b4ec3"
PREP = "runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared"
SOURCE = "runs/source_controls_base_ctx_v1_20261026"
RETRIEVAL = "runs/source_controls_base_ctx_repair_v2_20261026/result_retrieval_20261027"
EVIDENCE = RETRIEVAL + "/evidence179460"
OLD_REFS = "runs/diagnostics_d1_d2_v1_20261022/assets/reference_scores"
DENSE = ("runs/dense_reference_batch_repair_deployment_20261027/"
         "result_retrieval_r2_20261027/evidence179602/science/encode/banks/SOURCE_REFS")
SOURCE_PLAN = "runs/dense_reference_matrix_v1_20261027/vendor/encoding_v2/data/SOURCE_REFS/DENSE_PLAN.json"
FEATURES = "runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/features/LEARN.npy"
BRANCHES = {"ONE_COMPONENT": "1C", "TWO_COMPONENT_ZERO": "2C_ZERO",
            "TWO_COMPONENT_POSITIVE": "2C_POS", "NONE": "OTHER"}


def source_ensemble(logits):
    """179460 sequential float64 accumulator, never an N-by-3 mean."""
    x = np.asarray(logits)
    require(x.ndim == 2 and x.shape[1] == 3 and np.isfinite(x).all(), "SOURCE_LOGITS")
    total = np.zeros(len(x), dtype=np.float64)
    for column in range(3):
        total += x[:, column].astype(np.float64)
    total /= 3
    require(np.isfinite(total).all(), "SOURCE_ENSEMBLE_NONFINITE")
    return total


def score_columns(logits, support, scales, lambda_value):
    """Apply the original correction directly to RAW; add source ensemble."""
    x = np.asarray(logits, dtype=np.float64)
    a = np.asarray(support, dtype=np.float64)
    s = np.asarray(scales, dtype=np.float64)
    require(x.ndim == 2 and x.shape[1] == 3 and a.shape == (len(x),)
            and s.shape == (3,) and np.isfinite(x).all() and np.isfinite(a).all()
            and np.isfinite(s).all() and np.all((a >= 0) & (a <= 1))
            and np.all(s >= 0) and lambda_value in LAMBDAS, "SOURCE_CORRECTION_INPUT")
    corrected = x.copy()
    if lambda_value:
        active = a > 0
        for column in range(3):
            if s[column] > 0:
                corrected[active, column] = (x[active, column]
                                            - float(lambda_value) * s[column] * a[active])
    require(np.isfinite(corrected).all(), "SOURCE_CORRECTION_NONFINITE")
    return np.column_stack((corrected, source_ensemble(corrected)))


def select_source_lambda(raw_logits, d0_support, d0_eligible, scales, cuts):
    """Original grid/zero-withdrawal selector with SOURCE ensemble arithmetic."""
    x = np.asarray(raw_logits)
    a, legal = np.asarray(d0_support), np.asarray(d0_eligible)
    cut = np.asarray(cuts, dtype=np.float64)
    require(a.ndim == 2 and legal.dtype == np.bool_ and legal.shape == a.shape
            and a.shape[0] == len(x) and cut.shape == (4,)
            and np.all(a[~legal] == 0), "SOURCE_LAMBDA_MATRIX")
    raw = score_columns(x, np.zeros(len(x)), scales, 0.)
    baseline = raw > cut
    receipts, selected = [], 0.
    for value in LAMBDAS:
        withdrawn = np.zeros_like(baseline)
        for donor in range(a.shape[1]):
            changed = score_columns(x, a[:, donor], scales, value) > cut
            withdrawn |= baseline & ~changed & legal[:, donor, None]
        passes = not bool(np.any(withdrawn))
        if passes:
            selected = value
        receipts.append({"lambda_value": value, "passes": passes,
                         "withdrawals": dict(zip(SUFFIXES, withdrawn.sum(0).astype(int).tolist()))})
    return {"selected_lambda": selected, "candidates": receipts,
            "arithmetic": "source sequential float64 accumulator / 3",
            "selection": "largest original-grid value with zero original TP withdrawals in all suffixes"}


def _canonical(branch):
    return np.asarray([BRANCHES.get(str(item), str(item) if str(item) in
                       ("1C", "2C_ZERO", "2C_POS") else "OTHER")
                       for item in np.asarray(branch).reshape(-1)], dtype="<U8").reshape(np.shape(branch))


def paired_scenarios(raw_logits, matrix, scales, lambda_value, cuts, checkpoint=None):
    """Use D0/L legality union; ineligible arms independently fall back to RAW.

    The candidate's new 1C eligibility must never be masked by D0 eligibility.
    Returns every donor for audit and UID-wise minima for conservative safety.
    """
    x = np.asarray(raw_logits)
    a0, al = np.asarray(matrix["d0"]), np.asarray(matrix["local"])
    e0, el = np.asarray(matrix["eligible_d0"]), np.asarray(matrix["eligible_local"])
    require(a0.ndim == 2 and al.shape == e0.shape == el.shape == a0.shape
            and e0.dtype == el.dtype == np.bool_ and a0.shape[0] == len(x)
            and np.all(a0[~e0] == 0) and np.all(al[~el] == 0), "PAIRED_SCENARIO_SCHEMA")
    require(np.all(al >= a0), "NONMONOTONE_LOCAL_SUPPORT")
    raw = score_columns(x, np.zeros(len(x)), scales, 0.)
    cap = score_columns(x, np.ones(len(x)), scales, lambda_value)
    cut = np.asarray(cuts)
    branches = _canonical(matrix["branch"])
    d0 = np.empty(a0.shape + (4,), dtype=np.float64)
    local = np.empty_like(d0)
    safety0, safety_l = raw.copy(), raw.copy()
    branch_scores = {name: {"d0": raw.copy(), "local": raw.copy()}
                     for name in ("1C", "2C_ZERO", "2C_POS", "OTHER")}
    exposed = np.zeros((len(x), 4), dtype=bool)
    exposed_branches = {name: np.zeros_like(exposed) for name in ("1C", "2C_ZERO", "2C_POS", "OTHER")}
    for donor in range(a0.shape[1]):
        if checkpoint:
            checkpoint("SOURCE_DONOR_SCORES", donor=donor, donors=a0.shape[1])
        d0[:, donor] = score_columns(x, np.where(e0[:, donor], a0[:, donor], 0.), scales, lambda_value)
        local[:, donor] = score_columns(x, np.where(el[:, donor], al[:, donor], 0.), scales, lambda_value)
        union = e0[:, donor] | el[:, donor]
        safety0 = np.minimum(safety0, d0[:, donor])
        safety_l = np.minimum(safety_l, local[:, donor])
        hit = (d0[:, donor] > cut) & (cap <= cut) & union[:, None]
        exposed |= hit
        for name in exposed_branches:
            member = (branches[:, donor] == name)[:, None]
            exposed_branches[name] |= hit & member
            branch_scores[name]["d0"] = np.minimum(branch_scores[name]["d0"],
                                                   np.where(member, d0[:, donor], raw))
            branch_scores[name]["local"] = np.minimum(branch_scores[name]["local"],
                                                      np.where(member, local[:, donor], raw))
    return {"raw": raw, "d0": d0, "local": local, "safety_d0": safety0,
            "safety_local": safety_l, "exposure": exposed,
            "exposure_branches": exposed_branches, "branches": branches,
            "eligible_union": e0 | el, "safety_branch_scores": branch_scores}


def _pin(root, relative, expected, seals):
    relative = str(relative).replace("\\", "/")
    measured = sha(root / relative)
    require(measured == expected, "SOURCE_INPUT_SHA:" + relative)
    if relative in seals:
        require(seals[relative] == measured, "SOURCE_INPUT_IDENTITY_CONFLICT:" + relative)
    seals[relative] = measured
    return root / relative


def _rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def _npz_headers(path):
    answer = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            require(name.endswith(".npy"), "NPZ_NON_ARRAY_MEMBER")
            with archive.open(name) as stream:
                version = np.lib.format.read_magic(stream)
                require(version in ((1, 0), (2, 0)), "NPY_HEADER_VERSION")
                reader = (np.lib.format.read_array_header_1_0 if version == (1, 0)
                          else np.lib.format.read_array_header_2_0)
                shape, fortran, dtype = reader(stream)
                require(not dtype.hasobject, "NPZ_OBJECT_ARRAY")
                answer[name[:-4]] = {"shape": list(shape), "dtype": str(dtype), "fortran": bool(fortran)}
    return answer


def _load_assets(root, legacy):
    """Only saved RAW/metadata/header reads; no head or geometric operations."""
    root = Path(root).resolve()
    data = legacy["source_data"]
    seals = {}
    main_index_path = _pin(root, MAIN_FILES, MAIN_FILES_SHA, seals)
    main_index = read_json(main_index_path)["files"]
    _pin(root, SOURCE_ADAPTER_ASSETS, SOURCE_ADAPTER_ASSETS_SHA, seals)
    _pin(root, PREP + "/SHA256SUMS", main_index[PREP + "/SHA256SUMS"]["sha256"], seals)
    p1 = data.load_p1(root)
    for relative, expected in p1["seals"].items():
        require(relative not in seals or seals[relative] == expected, "SOURCE_PARENT_SEAL_CONFLICT")
        seals[relative] = expected
    config = read_json(root / SOURCE / "config/local.json")
    contract = read_json(root / SOURCE / "config/contract.json")
    manifest = read_json(root / RETRIEVAL / "manifest.json")
    export = {entry["path"]: entry for entry in manifest["files"]}
    for relative in (PREP + "/LEARN.jsonl.gz", FEATURES, OLD_REFS + "/SOURCE_REFS.npz",
                     OLD_REFS + "/SOURCE_REFS.jsonl.gz", DENSE + "/bank.npz",
                     DENSE + "/references.jsonl.gz", DENSE + "/receipt.json", SOURCE_PLAN):
        require(relative in main_index, "SOURCE_ASSET_NOT_IN_AUDITED_INDEX:" + relative)
        _pin(root, relative, main_index[relative]["sha256"], seals)
    require(seals[FEATURES] == config["files"]["values"]["sha256"], "SOURCE_FEATURE_PARENT_CONFLICT")
    # Files consumed by load_model/load_normalizer are pinned to the export,
    # rather than merely trusting a mutable endpoint.json beside its weights.
    for fold in ("G0", "G1"):
        for seed in SEEDS:
            endpoint = "endpoints/%s_BASE_%s" % (fold, seed)
            for name in ("endpoint.json", "head.npz", "initial.npz", "normalizer.npz", "losses.npy"):
                relative = endpoint + "/" + name
                require(relative in export, "SOURCE_EXPORT_MISSING:" + relative)
                _pin(root, EVIDENCE + "/" + relative, export[relative]["sha256"], seals)
    full_rows = _rows(root / PREP / "LEARN.jsonl.gz")
    fields = ("uid", "device", "activity", "capture_id", "session_id", "source_sha256",
              "component_id", "partition", "fit_role", "use", "label", "protocol", "timestamp", "frame")
    rows = [{key: original[key] for key in fields} for original in full_rows]
    del full_rows
    require(len(rows) == 766727 and len({row["uid"] for row in rows}) == len(rows), "SOURCE_ALL_UIDS")
    index_path = root / SOURCE / "config/FROZEN_INDICES.npz"
    with np.load(index_path, allow_pickle=False) as saved:
        indices = {key: saved[key].copy() for key in saved.files}
    for fold in ("G0", "G1"):
        for role in ("FIT", "CAL", "HELD"):
            ix = indices[fold + "_" + role]
            expected = contract["folds"][fold][role]
            require(ix.dtype == np.int64 and len(ix) == expected["rows"]
                    and array_sha(np.asarray(ix, dtype="<i8")) == expected["indices_sha256"]
                    and uid_sha(rows[int(i)]["uid"] for i in ix) == expected["uid_sha256"], "SOURCE_ROLE_BINDING")
            own = fold if role != "HELD" else ("G1" if fold == "G0" else "G0")
            require(all(rows[int(i)]["device"] in data.GROUPS[own] for i in ix), "SOURCE_DEVICE_ROLE")
            if role != "HELD":
                require(all(rows[int(i)]["fit_role"] == role for i in ix), "SOURCE_FIT_CAL_ROLE")
            else:
                require(set(rows[int(i)]["fit_role"] for i in ix) <= {"FIT", "CAL"}, "SOURCE_HELD_ROLE")
            if role in ("CAL", "HELD"):
                old_rows = p1["folds"][fold][role].pop("rows")
                require([row["uid"] for row in old_rows] == [rows[int(i)]["uid"] for i in ix], "SOURCE_FULL_METADATA_JOIN")
    dense_rows = _rows(root / DENSE / "references.jsonl.gz")
    old_rows = _rows(root / OLD_REFS / "SOURCE_REFS.jsonl.gz")
    plan = read_json(root / SOURCE_PLAN)
    receipt = read_json(root / DENSE / "receipt.json")
    require(len(dense_rows) == len({row["uid"] for row in dense_rows}) == 4728
            and len(old_rows) == 104 and set(plan["selected_uids"]) == {row["uid"] for row in dense_rows}, "SOURCE_REFERENCE_ROSTER")
    require(receipt["status"] == "COMPLETE" and receipt["rows"] == 4728
            and receipt["frozen_selection"] is True and receipt["reselection"] is False
            and receipt["bank_sha256"] == seals[DENSE + "/bank.npz"]
            and receipt["metadata_sha256"] == seals[DENSE + "/references.jsonl.gz"], "SOURCE_DENSE_RECEIPT")
    require(all(row["partition"] == "LEARN" and row["use"] == "REFERENCE" and row["label"] == 0
                and row["timestamp"] <= row["reference_end"] for row in dense_rows + old_rows), "SOURCE_REFERENCE_ROLE")
    headers = {"dense": _npz_headers(root / DENSE / "bank.npz"),
               "old": _npz_headers(root / OLD_REFS / "SOURCE_REFS.npz")}
    require(headers["dense"]["e3"]["shape"] == [4728, 768]
            and headers["dense"]["q14"]["shape"] == [4728, 14], "SOURCE_DENSE_HEADER")
    values = np.load(root / FEATURES, mmap_mode="r", allow_pickle=False)
    q = np.load(root / PREP / "LEARN_q.npy", mmap_mode="r", allow_pickle=False)
    require(values.shape == (766727, 794) and values.dtype == np.float32
            and q.shape == (766727, 14) and q.dtype == np.float32, "SOURCE_QUERY_HEADER")
    return dict(root=root, p1=p1, seals=seals, rows=rows, indices=indices,
                contract=contract, dense_rows=dense_rows, old_rows=old_rows,
                reference_headers=headers, plan=plan, values=values, q=q)


def preflight(root):
    """Read-only executable input acceptance; no models, distances or support."""
    from .legacy import load_legacy
    assets = _load_assets(root, load_legacy(root, with_training=False))
    return {"status": "SOURCE_INPUTS_VERIFIED_NOT_EXECUTED", "inputs_sha256": assets["seals"],
            "source_rows": len(assets["rows"]), "reference_rows": len(assets["dense_rows"]),
            "reference_headers": assets["reference_headers"],
            "fold_d0": "NOT_BUILT", "new_forwards": 0, "new_distances": 0,
            "new_training": 0, "new_support": 0, "A_B_inputs": 0}


def _bank_subset(rows, arrays, devices):
    ix = np.asarray([i for i, row in enumerate(rows) if row["device"] in devices], dtype=np.int64)
    chosen = [rows[int(i)] for i in ix]
    return chosen, arrays["e3"][ix], arrays["q14"][ix], [row["uid"] for row in chosen]


def _predict(training, model, values, q, ix, normalizer, runtime, stage):
    completed = 0
    def report(event):
        nonlocal completed
        now = int(event.get("completed", completed))
        require(completed <= now <= len(ix), "SOURCE_FORWARD_PROGRESS")
        runtime.add_forwards(now - completed)
        completed = now
        runtime.checkpoint(stage, completed=completed, total=len(ix))
    answer = training.scores(model, values, q, None, ix, normalizer, "BASE", progress=report)
    require(completed == len(ix), "SOURCE_FORWARD_COUNTER")
    return answer


def _save_npz(output, relative, runtime, **arrays):
    path = Path(output) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), "OUTPUT_ALREADY_EXISTS:" + str(path))
    require(all(np.asarray(value).dtype.kind != "O" for value in arrays.values()), "OUTPUT_OBJECT_ARRAY")
    np.savez_compressed(path, **arrays)
    runtime.checkpoint("SOURCE_OUTPUT_WRITTEN", file=relative)
    return {"path": relative, "sha256": sha(path)}


def _replay_environment(training):
    """Read process/build metadata; never import or execute another model."""
    torch = getattr(training, "torch", None)
    result = {"python": platform.python_version(), "python_full": sys.version,
              "executable": sys.executable, "numpy": np.__version__,
              "platform": platform.platform(), "machine": platform.machine(),
              "processor": platform.processor(), "logical_cpu_count": os.cpu_count(),
              "thread_environment": {key: os.environ.get(key) for key in
                  ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
              "torch": None}
    if torch is not None:
        result.update(torch=str(torch.__version__), torch_build=torch.__config__.show(),
                      torch_num_threads=torch.get_num_threads(),
                      torch_num_interop_threads=torch.get_num_interop_threads())
    return result


def _replay_number(value):
    value = float(value)
    return value if np.isfinite(value) else str(value)


def _record_raw_replay(output, runtime, training, *, fold, seed, role,
                       expected, reproduced, indices, rows, cut):
    """Persist evidence before the unchanged strict RAW replay assertion.

    Diagnostics share the stage's wall/RSS/output budget. No tolerance, score
    mutation, extra forward, population reduction or alternative gate is used.
    Shape mismatches deliberately have no invented row-wise numeric comparison.
    """
    runtime.checkpoint("SOURCE_RAW_REPLAY_DIAGNOSTICS", fold=fold, seed=seed, role=role)
    same_shape, same_dtype = expected.shape == reproduced.shape, expected.dtype == reproduced.dtype
    expected_bytes, reproduced_bytes = expected.tobytes(), reproduced.tobytes()
    same_bytes = expected_bytes == reproduced_bytes
    strict_pass = same_shape and same_dtype and same_bytes
    eb = np.frombuffer(expected_bytes, dtype=np.uint8)
    rb = np.frombuffer(reproduced_bytes, dtype=np.uint8)
    overlap = min(len(eb), len(rb))
    byte_mismatch_count = int(np.count_nonzero(eb[:overlap] != rb[:overlap])) + abs(len(eb) - len(rb))
    prefix = "RAW_REPLAY/%s/%s/%s" % (fold, seed, role)
    summary = {"fold": fold, "seed": seed, "role": role,
        "expected": {"dtype": str(expected.dtype), "dtype_str": expected.dtype.str,
                     "shape": list(expected.shape), "nbytes": expected.nbytes,
                     "bytes_sha256": array_sha(expected)},
        "reproduced": {"dtype": str(reproduced.dtype), "dtype_str": reproduced.dtype.str,
                       "shape": list(reproduced.shape), "nbytes": reproduced.nbytes,
                       "bytes_sha256": array_sha(reproduced)},
        "dtype_equal": same_dtype, "shape_equal": same_shape, "bytes_equal": same_bytes,
        "values_equal": bool(np.array_equal(expected, reproduced)),
        "strict_gate_pass": strict_pass, "byte_mismatch_count": byte_mismatch_count,
        "value_mismatch_count": None, "element_bytes_mismatch_count": None,
        "max_absolute_difference": None, "threshold_comparison": "score > frozen seed cut",
        "threshold": _replay_number(cut), "decision_mismatch_count": None,
        "expected_positive_to_reproduced_negative": None,
        "expected_negative_to_reproduced_positive": None,
        "first_mismatches": [], "first_mismatch_limit": 16,
        "source_index_sha256": array_sha(indices),
        "environment": _replay_environment(training), "failure_scores": None}
    if same_shape:
        value_diff = np.not_equal(expected, reproduced).reshape(-1)
        if expected.dtype.itemsize == reproduced.dtype.itemsize:
            element_diff = np.any(eb.reshape(-1, expected.dtype.itemsize)
                                  != rb.reshape(-1, reproduced.dtype.itemsize), axis=1)
        else:
            element_diff = np.ones(expected.size, dtype=bool)
        with np.errstate(invalid="ignore", over="ignore"):
            absolute = np.abs(expected.astype(np.float64) - reproduced.astype(np.float64))
        # Use explicit float64 arrays, matching downstream score_columns/cuts.
        expected_decision = expected.astype(np.float64) > float(cut)
        reproduced_decision = reproduced.astype(np.float64) > float(cut)
        summary.update(value_mismatch_count=int(np.count_nonzero(value_diff)),
            element_bytes_mismatch_count=int(np.count_nonzero(element_diff)),
            max_absolute_difference=_replay_number(np.max(absolute)) if absolute.size else 0.,
            decision_mismatch_count=int(np.count_nonzero(expected_decision != reproduced_decision)),
            expected_positive_to_reproduced_negative=int(np.count_nonzero(expected_decision & ~reproduced_decision)),
            expected_negative_to_reproduced_positive=int(np.count_nonzero(~expected_decision & reproduced_decision)))
        different = np.flatnonzero(value_diff | element_diff)
    else:
        summary["row_comparison_unavailable"] = "shape mismatch; flattened values are shown only as evidence"
        different = np.arange(min(max(expected.size, reproduced.size), 16))
    ef, rf = expected.reshape(-1), reproduced.reshape(-1)
    for position in different[:16]:
        position = int(position)
        source_index = int(indices[position]) if position < len(indices) else None
        summary["first_mismatches"].append({"role_index": position,
            "source_index": source_index, "uid": str(rows[source_index]["uid"]) if source_index is not None else None,
            "expected": _replay_number(ef[position]) if position < ef.size else None,
            "reproduced": _replay_number(rf[position]) if position < rf.size else None,
            "expected_bytes_hex": expected_bytes[position * expected.dtype.itemsize:(position + 1) * expected.dtype.itemsize].hex(),
            "reproduced_bytes_hex": reproduced_bytes[position * reproduced.dtype.itemsize:(position + 1) * reproduced.dtype.itemsize].hex()})
    runtime.checkpoint("SOURCE_RAW_REPLAY_DIAGNOSTICS_READY", fold=fold, seed=seed, role=role)
    runtime.write_json(prefix + "/SUMMARY.json", summary)
    if not strict_pass:
        summary["failure_scores"] = _save_npz(output, prefix + "/FAILURE_SCORES.npz", runtime,
            expected=expected, reproduced=reproduced, source_index=indices,
            uid=np.asarray([str(rows[int(i)]["uid"]) for i in indices]), threshold=np.asarray(cut))
        runtime.write_json(prefix + "/SUMMARY.json", summary)
    return summary


def _support_set(bank, rows, indices, assets, runtime):
    # Query labels only separate deployment-own metrics from conservative attack
    # audit scenarios. They never choose support, the bank, or a candidate rule.
    normal = np.flatnonzero([row["label"] == 0 for row in rows])
    attack = np.flatnonzero([row["label"] == 1 for row in rows])
    from .legacy import load_legacy
    indexed = load_legacy(assets["root"], with_training=False)["indexed"].IndexedMatrix
    def features(selected):
        ix = indices[selected]
        return indexed(assets["values"], ix, slice(0, 768)), indexed(assets["q"], ix)
    nr, ar = [rows[int(i)] for i in normal], [rows[int(i)] for i in attack]
    nz, nq = features(normal)
    az, aq = features(attack)
    runtime.checkpoint("SOURCE_NORMAL_SUPPORT", rows=len(nr))
    nids, aids = [row["uid"] for row in nr], [row["uid"] for row in ar]
    own = bank.own(nr, nz, nq, feature_uids=nids, q_uids=nids)
    runtime.checkpoint("SOURCE_ATTACK_DONOR_SUPPORT", rows=len(ar))
    matrix = bank.matrix(ar, az, aq, feature_uids=aids, q_uids=aids)
    return normal, attack, own, matrix


def _population_scores(rows, raw_logits, support_set, scales, lambda_value, cuts, runtime):
    normal, attack, own, matrix = support_set
    n = len(rows)
    a0, al = np.zeros(n), np.zeros(n)
    e0, el = np.zeros(n, bool), np.zeros(n, bool)
    branch = np.full(n, "OTHER", dtype="<U8")
    a0[normal], al[normal] = own["d0"], own["local"]
    e0[normal], el[normal] = own["eligible_d0"], own["eligible_local"]
    branch[normal] = _canonical(own["branch"])
    lookup = {(item["partition"], item["device"], item["protocol"]): i
              for i, item in enumerate(matrix["roster"])}
    require(len(lookup) == len(matrix["roster"]), "SOURCE_DUPLICATE_DONOR")
    for position, index in enumerate(attack):
        row = rows[int(index)]
        donor = lookup.get((row["partition"], row["device"], row["protocol"]))
        if donor is not None:
            a0[index], al[index] = matrix["d0"][position, donor], matrix["local"][position, donor]
            e0[index], el[index] = matrix["eligible_d0"][position, donor], matrix["eligible_local"][position, donor]
            branch[index] = _canonical(np.asarray(matrix["branch"][position, donor])).item()
    raw = score_columns(raw_logits, np.zeros(n), scales, 0.)
    d0 = score_columns(raw_logits, a0, scales, lambda_value)
    local = score_columns(raw_logits, al, scales, lambda_value)
    scenarios = paired_scenarios(raw_logits[attack], matrix, scales, lambda_value, cuts, runtime.checkpoint)
    safety0, safety_l = d0.copy(), local.copy()
    safety0[attack], safety_l[attack] = scenarios["safety_d0"], scenarios["safety_local"]
    exposure = np.zeros((n, 4), bool)
    exposure[attack] = scenarios["exposure"]
    exposure_branches = {}
    for name, values in scenarios["exposure_branches"].items():
        exposed = np.zeros((n, 4), bool)
        exposed[attack] = values
        exposure_branches[name] = exposed
    safety_branch_scores = {}
    for name, values in scenarios["safety_branch_scores"].items():
        safety_branch_scores[name] = {"d0": raw.copy(), "local": raw.copy()}
        for arm in ("d0", "local"):
            safety_branch_scores[name][arm][attack] = values[arm]
    maximum = score_columns(raw_logits, np.ones(n), scales, lambda_value)
    normal_cap = np.zeros((n, 4), dtype=bool)
    normal_cap[normal] = ((d0[normal] > cuts) & (maximum[normal] <= cuts)
                          & (e0[normal] | el[normal])[:, None])
    return dict(raw=raw, d0=d0, local=local, safety_d0=safety0, safety_local=safety_l,
                exposure=exposure, exposure_branches=exposure_branches, branches=branch,
                safety_branch_scores=safety_branch_scores, normal_cap=normal_cap,
                own_support_d0=a0, own_support_local=al, own_eligible_d0=e0,
                own_eligible_local=el, scenarios=scenarios, attack_indices=attack)


def _save_population(output, prefix, rows, indices, weights, phases, scores, support_set, runtime):
    normal, attack, own, matrix = support_set
    ledger = {key: scores[key] for key in ("raw", "d0", "local", "safety_d0", "safety_local", "exposure",
              "own_support_d0", "own_support_local", "own_eligible_d0", "own_eligible_local", "branches", "normal_cap")}
    ledger.update(uid=np.asarray([row["uid"] for row in rows]), source_index=indices,
                  weight=weights, phase=phases, label=np.asarray([row["label"] for row in rows], dtype=np.uint8))
    files = [_save_npz(output, prefix + "/SCORES.npz", runtime, **ledger)]
    scenario = scores["scenarios"]
    files.append(_save_npz(output, prefix + "/ATTACK_DONORS.npz", runtime,
        uid=np.asarray([rows[int(i)]["uid"] for i in attack]), attack_index=attack,
        support_d0=matrix["d0"], support_local=matrix["local"],
        eligible_d0=matrix["eligible_d0"], eligible_local=matrix["eligible_local"],
        donor_d0=scenario["d0"], donor_local=scenario["local"],
        exposure=scenario["exposure"], branches=scenario["branches"]))
    runtime.write_json(prefix + "/DONOR_ROSTER.json", matrix["roster"])
    return files


def run_source(root, output, runtime):
    """One explicit source execution. No target loading or automatic successor."""
    from .legacy import load_legacy
    from .geometry import DualBank
    from . import metrics
    root, output = Path(root).resolve(), Path(output).resolve()
    runtime.checkpoint("SOURCE_INPUT_IDENTITY")
    legacy = load_legacy(root, with_training=True)
    training = legacy["source_training"]
    if hasattr(training, "torch"):
        training.torch.set_num_threads(4)
        if training.torch.get_num_interop_threads() != 1:
            try:
                training.torch.set_num_interop_threads(1)
            except RuntimeError as exc:
                raise ValueError("SOURCE_INTEROP_THREADS_REQUIRE_FRESH_PROCESS") from exc
        require(training.torch.get_num_threads() <= 4 and training.torch.get_num_interop_threads() == 1,
                "SOURCE_TORCH_THREAD_LIMIT")
    assets = _load_assets(root, legacy)
    runtime.write_json("INPUT_SEAL.json", {"inputs_sha256": assets["seals"], "A_B_inputs": 0})
    core, training, data = legacy["core"], legacy["source_training"], legacy["source_data"]
    indexed = legacy["indexed"].IndexedMatrix
    rows, ix, p1 = assets["rows"], assets["indices"], assets["p1"]
    with np.load(root / DENSE / "bank.npz", allow_pickle=False) as saved:
        dense = {key: saved[key].copy() for key in ("uid", "e3", "q14")}
    with np.load(root / OLD_REFS / "SOURCE_REFS.npz", allow_pickle=False) as saved:
        old = {key: saved[key].copy() for key in ("uid", "e3", "q14")}
    legacy["dense_source"].validate_bank(assets["dense_rows"], dense, assets["plan"], assets["old_rows"], old)
    prepared = {}
    artifacts = []
    for fold in ("G0", "G1"):
        fit_index = ix[fold + "_FIT"]
        fit_rows = [rows[int(i)] for i in fit_index]
        fit_logits = []
        norm0 = None
        runtime.checkpoint("SOURCE_RAW_REPLAY", fold=fold)
        for seed in SEEDS:
            endpoint = root / EVIDENCE / ("endpoints/%s_BASE_%s" % (fold, seed))
            model, norm = training.load_model(endpoint, seed, "BASE"), training.load_normalizer(endpoint)
            if norm0 is None:
                norm0 = {key: value.copy() for key, value in norm.items()}
            require(set(norm) == set(norm0) and all(np.array_equal(norm[key], norm0[key]) for key in norm),
                    "SOURCE_NORMALIZER_SEED_MISMATCH")
            for role in ("CAL", "HELD"):
                reproduced = _predict(training, model, assets["values"], assets["q"],
                                      ix[fold + "_" + role], norm, runtime, "SOURCE_RAW_REPLAY")
                expected = p1["folds"][fold]["scores"][str(seed)][role]
                _record_raw_replay(output, runtime, training, fold=fold, seed=seed, role=role,
                    expected=expected, reproduced=reproduced, indices=ix[fold + "_" + role],
                    rows=rows, cut=p1["folds"][fold]["cuts"][str(seed)])
                require(reproduced.dtype == expected.dtype and reproduced.shape == expected.shape
                        and reproduced.tobytes() == expected.tobytes(), "SOURCE_RAW_REPLAY_MISMATCH:" + fold + str(seed) + role)
                del reproduced
            fit_logits.append(_predict(training, model, assets["values"], assets["q"], fit_index,
                                       norm, runtime, "SOURCE_FIT_FORWARD"))
            del model, norm
        fit_logits = np.column_stack(fit_logits)
        artifacts.append(_save_npz(output, fold + "/FIT_LOGITS.npz", runtime,
                                   source_index=fit_index, logits=fit_logits,
                                   uid=np.asarray([row["uid"] for row in fit_rows])))
        normalizer = norm0["e3_mean"], norm0["e3_scale"]
        own_devices = data.GROUPS[fold]
        held_devices = data.GROUPS["G1" if fold == "G0" else "G0"]
        rr, rz, rq, rids = _bank_subset(assets["old_rows"], old, own_devices)
        sparse = DualBank(rr, rz, rq, normalizer, None, core=core, counter=runtime.add_pairs,
                          checkpoint=runtime.checkpoint, allow_prebank_history=True,
                          feature_uids=rids, q_uids=rids, allowed_partitions={"LEARN"})
        normal_ix = np.asarray([i for i, row in enumerate(fit_rows) if row["label"] == 0], dtype=np.int64)
        normals = [fit_rows[int(i)] for i in normal_ix]
        nids = [row["uid"] for row in normals]
        runtime.checkpoint("SOURCE_FIT_GEOMETRY", fold=fold)
        geometry = core.fit_geometry(normals, indexed(assets["values"], fit_index[normal_ix], slice(0, 768)),
                                     indexed(assets["q"], fit_index[normal_ix]), sparse,
                                     feature_uids=nids, q_uids=nids)
        scales = core.fit_scales(fit_rows, fit_logits)
        runtime.write_json(fold + "/GEOMETRY.json", geometry)
        runtime.write_json(fold + "/SCALES.json", scales)
        banks = {}
        for role, devices in (("CAL", own_devices), ("S", held_devices)):
            rr, rz, rq, rids = _bank_subset(assets["dense_rows"], dense, devices)
            banks[role] = DualBank(rr, rz, rq, normalizer, geometry, core=core,
                                  counter=runtime.add_pairs, checkpoint=runtime.checkpoint,
                                  allow_prebank_history=True, feature_uids=rids, q_uids=rids,
                                  allowed_partitions={"LEARN"})
            runtime.write_json(fold + "/" + role + "_LOCAL_SCALES.json", banks[role].scale_summary)
            artifacts.append(_save_npz(output, fold + "/" + role + "_LOCAL_SCALES.npz", runtime,
                                       **banks[role].scale_arrays()))
        cuts = np.asarray([p1["folds"][fold]["cuts"][suffix] for suffix in SUFFIXES], dtype=np.float64)
        prepared[fold] = {"banks": banks, "geometry": geometry, "scales": scales["scales"], "cuts": cuts}
        runtime.write_json(fold + "/BASELINE_IDENTITY.json", {"fold": fold, "cuts": cuts.tolist(),
            "fit_uid_sha256": uid_sha(row["uid"] for row in fit_rows), "fit_rows": len(fit_rows),
            "geometry_reference": "training-device subset of original104", "existing_fold_D0": False})
        del fit_logits, sparse, fit_rows, normals
        gc.collect()
    if not any(prepared[fold]["banks"]["S"].has_2c_expansion for fold in prepared):
        no_op_gate = {"pass": False, "status": "NO_2C_EXPANSION",
                      "reasons": ["Both held-device banks cannot increase original 2C support under the fixed local radii"],
                      "query_support_evaluated": False, "no_parameter_retry": True}
        runtime.write_json("SOURCE_GATE.json", no_op_gate)
        for relative, expected in assets["seals"].items():
            runtime.checkpoint("SOURCE_FINAL_INPUT_IDENTITY", file=relative)
            require(sha(root / relative) == expected, "SOURCE_INPUT_CHANGED:" + relative)
        return {"status": "COMPLETE", "scientific_status": "NO_2C_EXPANSION", "source_pass": False,
                "reason": "Both held-device banks cannot increase old 2C support under the fixed local radii",
                "gate": no_op_gate, "artifacts": artifacts, "next_stage_automatic": False, "A_B_inputs": 0,
                "new_training": 0, "new_E3": 0, "input_seal_sha256": sha(output / "INPUT_SEAL.json")}
    fold_reports, cal_reports = {}, {}
    for fold, setup in prepared.items():
        cal_index = ix[fold + "_CAL"]
        cal_rows = [rows[int(i)] for i in cal_index]
        cal_bank = setup["banks"]["CAL"]
        require(not {row["component_id"] for row in cal_rows}.intersection(
                    row["component_id"] for row in cal_bank.rows), "SOURCE_CAL_REFERENCE_COMPONENT_LEAKAGE")
        cal_raw = np.column_stack([p1["folds"][fold]["scores"][str(seed)]["CAL"] for seed in SEEDS])
        cal_support = _support_set(cal_bank, cal_rows, cal_index, assets, runtime)
        normal, attack, _, matrix = cal_support
        selection = select_source_lambda(cal_raw[attack], matrix["d0"], matrix["eligible_d0"],
                                         setup["scales"], setup["cuts"])
        lam = selection["selected_lambda"]
        setup["lambda"] = lam
        runtime.write_json(fold + "/LAMBDA.json", selection)
        cal_scores = _population_scores(cal_rows, cal_raw, cal_support, setup["scales"], lam, setup["cuts"], runtime)
        baseline = cal_scores["raw"][attack] > setup["cuts"]
        withdrawn0 = baseline & ~(cal_scores["safety_d0"][attack] > setup["cuts"])
        withdrawn_l = baseline & ~(cal_scores["safety_local"][attack] > setup["cuts"])
        require(not withdrawn0.any(), "SOURCE_D0_SELECTOR_CONTRADICTION")
        cal_pass = not bool(withdrawn_l.any())
        cal_reports[fold] = {"passes": cal_pass, "lambda": lam,
            "d0_withdrawals": dict(zip(SUFFIXES, withdrawn0.sum(0).astype(int).tolist())),
            "local_withdrawals": dict(zip(SUFFIXES, withdrawn_l.sum(0).astype(int).tolist()))}
        runtime.write_json(fold + "/CAL_CHECK.json", cal_reports[fold])
        cal_weights = 1. / p1["folds"][fold]["CAL"]["denominators"].astype(np.float64)
        artifacts += _save_population(output, fold + "/CAL", cal_rows, cal_index, cal_weights,
                                      p1["folds"][fold]["CAL"]["phases"], cal_scores, cal_support, runtime)
        del cal_scores, cal_support, matrix, cal_raw
        held_index = ix[fold + "_HELD"]
        selection = np.asarray([i for i, index in enumerate(held_index) if rows[int(index)]["fit_role"] == "FIT"], dtype=np.int64)
        s_index = held_index[selection]
        opposite = "G1" if fold == "G0" else "G0"
        require(np.array_equal(s_index, ix[opposite + "_FIT"]), "SOURCE_HELD_FIT_MAPPING")
        s_rows = [rows[int(i)] for i in s_index]
        raw = np.column_stack([p1["folds"][fold]["scores"][str(seed)]["HELD"][selection] for seed in SEEDS])
        weights = 1. / p1["folds"][fold]["HELD"]["denominators"][selection].astype(np.float64)
        phases = p1["folds"][fold]["HELD"]["phases"][selection]
        support = _support_set(setup["banks"]["S"], s_rows, s_index, assets, runtime)
        scores = _population_scores(s_rows, raw, support, setup["scales"], lam, setup["cuts"], runtime)
        fold_reports[fold] = metrics.evaluate_source_fold(name=fold, rows=s_rows, weights=weights,
            denominators=p1["folds"][fold]["HELD"]["denominators"][selection],
            raw=scores["raw"], d0=scores["d0"], local=scores["local"], cuts=setup["cuts"],
            phases=phases, branches=scores["branches"], safety_d0=scores["safety_d0"],
            safety_local=scores["safety_local"], exposure=scores["exposure"],
            exposure_branches=scores["exposure_branches"],
            safety_branch_scores=scores["safety_branch_scores"], normal_cap=scores["normal_cap"],
            lambda_value=lam, cal_pass=cal_pass)
        artifacts += _save_population(output, fold + "/S", s_rows, s_index, weights, phases, scores, support, runtime)
        runtime.write_json(fold + "/S_REPORT.json", fold_reports[fold])
        del scores, support, s_rows, raw
        gc.collect()
    gate = metrics.source_gate(fold_reports, cal_pass=all(x["passes"] for x in cal_reports.values()),
                               lambdas={fold: prepared[fold]["lambda"] for fold in prepared})
    runtime.write_json("SOURCE_GATE.json", gate)
    for relative, expected in assets["seals"].items():
        runtime.checkpoint("SOURCE_FINAL_INPUT_IDENTITY", file=relative)
        require(sha(root / relative) == expected, "SOURCE_INPUT_CHANGED:" + relative)
    passes = bool(gate["pass"])
    return {"status": "COMPLETE", "scientific_status": "SOURCE_SIGNAL_PASS" if passes else "SOURCE_SIGNAL_FAIL",
            "source_pass": passes, "gate": gate, "calibration": cal_reports,
            "folds": fold_reports, "artifacts": artifacts, "next_stage_automatic": False,
            "new_training": 0, "new_E3": 0, "A_B_inputs": 0,
            "input_seal_sha256": sha(output / "INPUT_SEAL.json")}
