"""Endpoint-only fixed-threshold comparison. No optimizer or calibration.

Real entry receives two sealed endpoints, prepared CHECK caches, and the pinned
fixed-P2 ledger. Existing representation rows are streamed selectively for B/C.
"""
from __future__ import annotations

import csv
import gzip
import json
from fractions import Fraction
from pathlib import Path

import numpy as np

import legacy_p2_supported_capability_ledger_v1 as ledger


ARMS = ("R", "B", "C")
REFERENCE_SHA = "129b8b5420f9d3f58087195d41817d0f71c04d300f8488abc8ff58504f9dc57f"
REFERENCE_PATH = "runs/legacy_p2_supported_capability_ledger_v1_20260915/P2_fixed_scores.csv.gz"
require = ledger.require


def confined(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(path == root or root in path.parents, "ARTIFACT_OUTSIDE_ROOT")
    return path


def pinned(root, item):
    path = confined(root, item["path"])
    require(ledger.sha256(path) == item["sha256"], "ARTIFACT_SHA:" + str(path))
    return path


def load_cache(root, item, expected_role):
    path = pinned(root, item)
    meta = confined(root, item["metadata_path"])
    require(ledger.sha256(meta) == item["metadata_sha256"], "CACHE_METADATA_SHA")
    if meta.suffix == ".jsonl":
        targets = [json.loads(s) for s in meta.read_text(encoding="utf-8").splitlines() if s.strip()]
    else:
        targets = json.loads(meta.read_text(encoding="utf-8"))
    require(isinstance(targets, list), "CACHE_METADATA_LIST")
    with np.load(path, allow_pickle=False) as f:
        require(set(f.files) == {"uid", "x", "y"}, "CACHE_FIELDS")
        uids, features, labels = f["uid"], f["x"], f["y"]
    require(features.dtype == np.float32 and features.shape == (len(targets), 768), "CACHE_FEATURE_SHAPE")
    require(bool(np.isfinite(features).all()), "CACHE_NONFINITE")
    require(labels.dtype == np.int64 and labels.shape == (len(targets),), "CACHE_LABELS")
    require(uids.dtype.kind == "U" and uids.tolist() == [r["uid"] for r in targets], "CACHE_UID_ORDER")
    require(len(set(uids.tolist())) == len(uids) == item["rows"], "CACHE_ROW_COUNT")
    require(labels.tolist() == [int(r["label"]) for r in targets], "CACHE_LABEL_JOIN")
    require(all(r["planned_role"] == expected_role for r in targets), "CACHE_ROLE_ACCESS")
    return features, targets


def load_reference(path, plans):
    """Read only sealed fixed-P2 output; align metadata before interpreting scores."""
    by_subset = {name: {r["uid"]: i for i, r in enumerate(rows)} for name, rows in plans.items()}
    result = {}
    for name, rows in plans.items():
        require(len(by_subset[name]) == len(rows), "REFERENCE_PLAN_DUPLICATE")
        result[name] = dict(probability=np.full(len(rows), np.nan), logit=np.full(len(rows), np.nan),
                            missing=np.zeros(len(rows), dtype=bool), hard=np.zeros(len(rows), dtype=bool),
                            seen=np.zeros(len(rows), dtype=bool))
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name, uid = row["subset"], row["uid"]
            require(name in plans and uid in by_subset[name], "REFERENCE_UNKNOWN_TARGET")
            i = by_subset[name][uid]
            target, values = plans[name][i], result[name]
            require(not values["seen"][i], "REFERENCE_DUPLICATE")
            for key in ("role", "source_group", "device_family", "attack_family"):
                require(row[key] == target[key], "REFERENCE_METADATA:" + key)
            require(int(row["label"]) == int(target["label_metric_only"]), "REFERENCE_LABEL")
            require(row["missing"] in {"0", "1"}, "REFERENCE_MISSING")
            missing = row["missing"] == "1"
            values["missing"][i], values["seen"][i] = missing, True
            if not missing:
                p, z = float(row["fixed_rescore_probability"]), float(row["raw_logit"])
                require(np.isfinite(p) and 0 <= p <= 1 and np.isfinite(z), "REFERENCE_FINITE")
                require(row["canonical_hard"] in {"0", "1"}, "REFERENCE_HARD")
                require((p >= ledger.THETA) == (row["canonical_hard"] == "1"), "REFERENCE_THRESHOLD")
                if row["immutable_archived_probability"]:
                    require(p == float(row["immutable_archived_probability"]), "REFERENCE_EQUIVALENCE")
                    p = float(row["immutable_archived_probability"])
                values["probability"][i], values["logit"][i], values["hard"][i] = p, z, p >= ledger.THETA
            elif row["canonical_hard"]:
                require(row["canonical_hard"] in {"0", "1"}, "REFERENCE_MISSING_HARD")
                values["hard"][i] = row["canonical_hard"] == "1"
    require(all(bool(v["seen"].all()) for v in result.values()), "REFERENCE_INCOMPLETE")
    return result


def metric(mask, labels, missing, probabilities, numerator_label):
    mask = np.asarray(mask, dtype=bool) & (labels == numerator_label)
    valid = mask & ~missing
    n = int(valid.sum())
    values = {}
    for arm in ARMS:
        require(bool(np.isfinite(probabilities[arm][valid]).all()), "METRIC_MISSING_SCORE")
        hard = probabilities[arm] >= ledger.THETA
        count = int((hard & valid).sum())
        values[arm] = dict(alarms=count, rows=n, rate=count / n if n else None)
    flips = {}
    for baseline, candidate in (("R", "B"), ("R", "C"), ("B", "C")):
        before, after = probabilities[baseline] >= ledger.THETA, probabilities[candidate] >= ledger.THETA
        flips[baseline + "_to_" + candidate] = {
            "alarm_to_accept": int((valid & before & ~after).sum()),
            "accept_to_alarm": int((valid & ~before & after).sum()),
        }
    return dict(metric="attack_recall" if numerator_label else "normal_FPR", total_rows=int(mask.sum()),
                valid_rows=n, missing_rows=int((mask & missing).sum()), arms=values, flips=flips)


def pool_summary(rows, missing, probabilities, family_seen=None):
    labels = np.asarray([int(r["label_metric_only"]) for r in rows])
    out = {"attack": metric(np.ones(len(rows), bool), labels, missing, probabilities, 1)}
    if family_seen is not None:
        seen = np.asarray([r["attack_family"] in family_seen for r in rows])
        out["attack_exact_family_seen"] = metric(seen, labels, missing, probabilities, 1)
        out["attack_exact_family_absent"] = metric(~seen, labels, missing, probabilities, 1)
    for family in sorted({r["attack_family"] for r in rows if int(r["label_metric_only"]) == 1}):
        out["attack_family:" + family] = metric([r["attack_family"] == family for r in rows], labels, missing, probabilities, 1)
    for role in sorted({r["role"] for r in rows if int(r["label_metric_only"]) == 1}):
        out["attack_role:" + role] = metric([r["role"] == role for r in rows], labels, missing, probabilities, 1)
    for source in sorted({r["source_group"] for r in rows if int(r["label_metric_only"]) == 1}):
        out["attack_source:" + source] = metric([r["source_group"] == source for r in rows], labels, missing, probabilities, 1)
    for device in sorted({r["device_family"] for r in rows if int(r["label_metric_only"]) == 1}):
        out["attack_device:" + device] = metric([r["device_family"] == device for r in rows], labels, missing, probabilities, 1)
    for family in sorted({r["device_family"] for r in rows if int(r["label_metric_only"]) == 0}):
        out["normal:" + family] = metric([r["device_family"] == family for r in rows], labels, missing, probabilities, 0)
    for source in sorted({r["source_group"] for r in rows if int(r["label_metric_only"]) == 0}):
        out["normal_source:" + source] = metric([r["source_group"] == source for r in rows], labels, missing, probabilities, 0)
    return out


def id_session_summary(targets, probabilities):
    sessions = {}
    for i, row in enumerate(targets):
        key = row["canonical_session_sha256"] if "canonical_session_sha256" in row else row.get("session_id")
        require(bool(key), "ID_SESSION_IDENTITY")
        sessions.setdefault(key, []).append(i)
    return dict(session_count=len(sessions), packet_targets=len(targets),
                interpretation="Source-local held-out UDP sessions; dependent packet observations; no confidence guarantee",
                per_session={key: {"packet_targets": len(indices), "arms": {arm: {
                    "false_positive_packets": int(np.count_nonzero(probabilities[arm][indices] >= ledger.THETA)),
                    "any_alarm": bool(np.any(probabilities[arm][indices] >= ledger.THETA))} for arm in ARMS}}
                    for key, indices in sessions.items()})


def assess_contrasts(metrics):
    """Descriptive finite-pool directions, never a replacement scientific PASS."""
    result = {}
    for baseline, candidate in (("R", "B"), ("R", "C"), ("B", "C")):
        better, worse, equal, undefined = [], [], [], []
        for name, item in metrics.items():
            before, after = item["arms"][baseline], item["arms"][candidate]
            require(before["rows"] == after["rows"], "CONTRAST_DENOMINATOR")
            if not before["rows"]:
                undefined.append(name)
                continue
            if item.get("hierarchically_weighted"):
                delta = Fraction(*after["exact_rate"]) - Fraction(*before["exact_rate"])
            else:
                delta = after["alarms"] - before["alarms"]
            if item["metric"] == "normal_FPR":
                delta = -delta
            (better if delta > 0 else worse if delta < 0 else equal).append(name)
        status = "TRADEOFF" if better and worse else "REGRESSION" if worse else "FINITE_POOL_NONWORSE" if better else "UNCHANGED"
        result[baseline + "_to_" + candidate] = dict(status=status, better=better, worse=worse, equal=equal, undefined=undefined,
                                                    deployment_promotion=False, independent_confirmation=False)
    return result


def weighted_cic_metrics(targets, probabilities):
    out = {}
    for label in (0, 1):
        mask = np.asarray([int(r["label"]) == label for r in targets])
        weights = np.asarray([r["evaluation_label_weight_numerator"] / r["evaluation_label_weight_denominator"] for r in targets])
        require(abs(float(weights[mask].sum()) - 1.0) < 1e-12, "CHECK_WEIGHT_SUM")
        out[str(label)] = {arm: float(np.sum(weights[mask] * (probabilities[arm][mask] >= ledger.THETA))) for arm in ARMS}
    return out


def weighted_cic_summaries(targets, probabilities):
    result = {}
    for label in (0, 1):
        positions = [i for i, r in enumerate(targets) if int(r["label"]) == label]
        weights = {i: Fraction(targets[i]["evaluation_label_weight_numerator"], targets[i]["evaluation_label_weight_denominator"]) for i in positions}
        require(sum(weights.values(), Fraction(0)) == 1, "EXACT_CHECK_WEIGHT_SUM")
        arms = {}
        for arm in ARMS:
            alarms = [i for i in positions if probabilities[arm][i] >= ledger.THETA]
            value = sum((weights[i] for i in alarms), Fraction(0))
            arms[arm] = dict(rows=len(positions), alarms=len(alarms), rate=float(value), exact_rate=[value.numerator, value.denominator])
        result[str(label)] = dict(metric="attack_recall" if label else "normal_FPR", hierarchically_weighted=True,
                                 total_rows=len(positions), valid_rows=len(positions), missing_rows=0, arms=arms)
    return result


def comparison_curves(report, familiar, fit_seen):
    joined_rows = report["rows"] + familiar["rows"]
    selected = ~np.concatenate((report["missing"], familiar["missing"]))
    labels = np.asarray([r["label_metric_only"] for r in joined_rows])[selected]
    pools = np.asarray(["" if r["label_metric_only"] else ledger.NORMAL_POOLS.get(r["device_family"], "familiar_normal")
                        for r in joined_rows])[selected]
    future = np.asarray([r["role"] == "future_query" for r in joined_rows])[selected]
    seen = np.asarray([r["attack_family"] in fit_seen for r in joined_rows])[selected]
    low = {}
    for arm in ARMS:
        low[arm] = {}
        for score_type, key in (("native_probability", "p"), ("raw_logit", "z")):
            values = np.concatenate((report[key][arm], familiar[key][arm]))[selected]
            low[arm][score_type] = ledger.low_fpr_points(values, labels, pools, future, seen)
    return low


def _score_history(path, plan, plan_sha, selected, states, expected_missing, progress, name, audit):
    mapping, physical_missing = ledger.embedding_metadata(path, plan, plan_sha)
    target_physical = [mapping[r["uid"]] for r in selected]
    missing = np.asarray([physical_missing[i] for i in target_physical], dtype=bool)
    require(np.array_equal(missing, expected_missing), "HISTORY_MISSING_IDENTITY")
    reverse = {physical: i for i, physical in enumerate(target_physical) if not missing[i]}
    require(len(reverse) == int((~missing).sum()), "HISTORY_TARGET_DUPLICATE")
    probs, logits = {}, {}
    for arm in ("B", "C"):
        probs[arm], logits[arm] = np.full(len(selected), np.nan), np.full(len(selected), np.nan)
    done = 0
    for physical, x in ledger.selective_batches(path, sorted(reverse), len(plan), audit=audit):
        positions = np.asarray([reverse[int(i)] for i in physical])
        for arm in ("B", "C"):
            z, p = ledger.canonical_p2(x, states[arm])
            logits[arm][positions], probs[arm][positions] = z, p
        done += len(x)
        if progress:
            progress(dict(stage="CHECK_" + name, done=done, total=len(reverse)))
    require(done == len(reverse), "HISTORY_FORWARD_COVERAGE")
    return probs, logits, missing


def _prepared_scores(root, artifact, states, role):
    x, targets = load_cache(root, artifact, role)
    probabilities, logits = {}, {}
    for arm in ARMS:
        zz, pp = [], []
        for start in range(0, len(x), 1024):
            z, p = ledger.canonical_p2(x[start:start + 1024], states[arm])
            zz.extend(z.tolist()); pp.extend(p.tolist())
        logits[arm], probabilities[arm] = np.asarray(zz), np.asarray(pp)
    return targets, probabilities, logits


def evaluate(recipe, prepared_dir, checkpoint_b, checkpoint_c, output_dir, *, progress=None):
    """Called only by the controller after both endpoints are sealed."""
    recipe = json.loads(Path(recipe).read_text(encoding="utf-8")) if isinstance(recipe, (str, Path)) else recipe
    require(recipe["evaluation"]["probability_threshold"] == ledger.THETA, "EVALUATION_THRESHOLD_DRIFT")
    import legacy_cic2022_enhancement_train_v1 as train
    train.configure_runtime()
    root, prepared, out = Path.cwd(), Path(prepared_dir), Path(output_dir)
    require(not out.exists(), "EVALUATION_OUTPUT_EXISTS")
    manifest = json.loads((prepared / "prepare_manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest["artifacts"]
    require("id_cache" in artifacts and manifest.get("id_qualification", {}).get("qualified") is True, "QUALIFIED_ID_REQUIRED")
    states = {"R": ledger.load_p2_state(pinned(prepared, artifacts["reference_state"]))}
    for arm, checkpoint in (("B", Path(checkpoint_b)), ("C", Path(checkpoint_c))):
        receipt = json.loads(checkpoint.with_suffix(".json").read_text(encoding="utf-8"))
        require(receipt["arm"] == arm and receipt["optimizer_updates"] == recipe["optimization"]["full_batch_updates_per_arm"]
                and receipt["status"] == "COMPLETE" and not receipt["synthetic"], "ENDPOINT_IDENTITY")
        require(receipt["checkpoint_sha256"] == ledger.sha256(checkpoint), "ENDPOINT_SHA")
        states[arm] = ledger.load_p2_state(checkpoint)
        for key in ("normalizer_mean", "normalizer_scale"):
            require(np.array_equal(states[arm][key], states["R"][key]), "ENDPOINT_NORMALIZER_CHANGED")
    pins = recipe["legacy_asset_pins"]["files"]
    def asset(suffix):
        matches = [p for p in pins if p.endswith(suffix)]
        require(len(matches) == 1, "ASSET_UNIQUE:" + suffix)
        path = root / matches[0]
        require(ledger.sha256(path) == pins[matches[0]], "ASSET_SHA:" + suffix)
        return path
    fit_path, report_path = asset("/ckda_d1_fit_select_plan.csv"), asset("/ckda_d1_report_plan.csv")
    fit, report = ledger.read_plan(fit_path), ledger.read_plan(report_path)
    familiar = [r for r in fit if r["role"] in {"aux_select", "aux_normal_select"} and not r["label_metric_only"]]
    id_fit = [r for r in fit if r["role"] == "id_calib" and not r["label_metric_only"]]
    plans = dict(expanded=report, familiar_normal=familiar, id_fit_diagnostic=id_fit)
    reference_path = root / REFERENCE_PATH
    require(ledger.sha256(reference_path) == REFERENCE_SHA, "FIXED_LEDGER_SHA")
    reference = load_reference(reference_path, plans)
    out.mkdir(parents=True)
    audit, metrics, scores = {}, {}, {}
    fit_seen, _ = ledger.exposure_sets(fit)
    for name, targets in plans.items():
        historical_plan = report if name == "expanded" else fit
        plan_path = report_path if name == "expanded" else fit_path
        embeddings = asset("/ckda_d1_report_embeddings.npz" if name == "expanded" else "/ckda_d1_fit_select_embeddings.npz")
        p, z, missing = _score_history(embeddings, historical_plan, ledger.sha256(plan_path), targets, states,
                                       reference[name]["missing"], progress, name, audit)
        p["R"], z["R"] = reference[name]["probability"], reference[name]["logit"]
        scores[name] = dict(rows=targets, p=p, z=z, missing=missing)
        for key, value in pool_summary(targets, missing, p, fit_seen if name == "expanded" else None).items():
            metrics[name + "/" + key] = value
    require(audit["numeric_representation_rows"] == 200216, "CHECK_HISTORY_DENOMINATOR")
    for name, role, key in (("new_cic_check", "CHECK", "new_check_cache"), ("ID_test", "ID_TEST", "id_cache")):
        targets, p, z = _prepared_scores(prepared, artifacts[key], states, role)
        require(len(targets) > 0, "EMPTY_CHECK_POOL")
        if name == "new_cic_check":
            require(len(targets) == recipe["new_data"]["check_rows"], "NEW_CHECK_DENOMINATOR")
        else:
            require(all(int(r["label"]) == 0 for r in targets), "ID_NORMAL_ONLY")
            id_sessions = id_session_summary(targets, p)
        rows = [dict(r, role=role, source_group=r.get("member_path", r.get("member", "")),
                     device_family=r.get("device", r.get("device_family", "ID")),
                     attack_family="Hydra" if int(r["label"]) else "benign", label_metric_only=int(r["label"])) for r in targets]
        missing = np.zeros(len(rows), dtype=bool)
        scores[name] = dict(rows=rows, p=p, z=z, missing=missing)
        for field, value in pool_summary(rows, missing, p).items():
            metrics[name + "/" + field] = value
        if name == "new_cic_check":
            weighted = weighted_cic_metrics(targets, p)
            for label, value in weighted_cic_summaries(targets, p).items():
                metrics["new_cic_check/weighted_label:" + label] = value
            for capture in sorted({r["member_path"] for r in targets}):
                for label in (0, 1):
                    labels = np.asarray([int(r["label"]) for r in targets])
                    metrics["new_cic_capture/" + capture + "/" + str(label)] = metric(
                        [r["member_path"] == capture for r in targets], labels, missing, p, label)
    rdata, fdata = scores["expanded"], scores["familiar_normal"]
    low = comparison_curves(rdata, fdata, fit_seen)
    score_path = out / "endpoint_scores.csv.gz"
    columns = ["subset", "uid", "role", "source_group", "device_family", "attack_family", "label", "missing"] + [a + "_" + s for a in ARMS for s in ("probability", "logit", "hard")]
    with gzip.open(score_path, "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns); writer.writeheader()
        for name, data in scores.items():
            for i, r in enumerate(data["rows"]):
                row = {k: r[k] for k in ("uid", "role", "source_group", "device_family", "attack_family")}
                row.update(subset=name, label=r["label_metric_only"], missing=int(data["missing"][i]))
                for arm in ARMS:
                    for suffix, key in (("probability", "p"), ("logit", "z")):
                        value = data[key][arm][i]
                        row[arm + "_" + suffix] = "" if data["missing"][i] else repr(float(value))
                    row[arm + "_hard"] = "" if data["missing"][i] else int(data["p"][arm][i] >= ledger.THETA)
                writer.writerow(row)
    primary = dict(ID_test={k: v for k, v in metrics.items() if k.startswith("ID_test/normal:")},
                   attack=metrics["expanded/attack"],
                   OOD_training_uncovered={k: v for k, v in metrics.items() if k.startswith("expanded/normal:")},
                   OOD_training_covered_new_CIC={k: v for k, v in metrics.items() if k.startswith("new_cic_check/normal:")})
    result = dict(status="ENDPOINT_CHECK_COMPLETE", probability_threshold=ledger.THETA, primary_metrics=primary, metrics=metrics,
                  contrasts=assess_contrasts(metrics), new_CIC_label_weighted_alarm_rates=weighted,
                  ID_session_diagnostic=id_sessions,
                  ID_qualification=manifest["id_qualification"], historical_coverage={k: {
                      "rows": len(v["missing"]), "missing": int(v["missing"].sum()),
                      "archived_missing_alarms": int((v["missing"] & v["hard"]).sum()) if k == "expanded" else None}
                      for k, v in reference.items()}, access_audit=audit, old_R_forward_rows=0,
                  new_R_forward_rows=sum(len(scores[k]["rows"]) for k in ("new_cic_check", "ID_test")),
                  training_steps=0, threshold_recalibration=False, independent_final_claim=False,
                  score_sha256=ledger.sha256(score_path), reference_ledger_sha256=REFERENCE_SHA)
    ledger.atomic_json(out / "summary.json", result)
    ledger.atomic_json(out / "low_FPR_points.json", dict(purpose="Five fixed development normal pools; ID/new CIC excluded; no deployment threshold selection", arms=low))
    (out / "SHA256SUMS").write_text("".join(ledger.sha256(out / p) + "  " + p + "\n" for p in
                                               ("summary.json", "low_FPR_points.json", "endpoint_scores.csv.gz")), encoding="ascii")
    return result
