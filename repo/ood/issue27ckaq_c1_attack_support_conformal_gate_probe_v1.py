"""issue27ckaq: C1 attack-support conformal gate probe.

Targeted follow-up after issue27ckap:
Class prototypes learned by CE/SupCon still mapped held OOD into the attack
region.  This probe tests a stricter open-set idea:

    hard attack = attack score high AND close to the legal attack support
                  manifold in C1 feature space.

If attack score is high but support distance is too large, the sample is
counted as review for the review variant, or suppressed for the suppress
variant.  This is a probe, not the final policy.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckg_basic_capability_diagnostic as ckg  # noqa: E402
import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27ckai_external_flow_feature_probe_v1 as ckai  # noqa: E402
import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckaq_c1_attack_support_conformal_gate_probe_v1_2026-07-09"
OUT_BASE = cko.ROOT / "runs" / ISSUE


def c1_candidate() -> ckai.Candidate:
    return next(c for c in ckai.CANDIDATES if c.name == "C1_cicflow_style_only_histgb")


def standardize_fit(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu = np.mean(x, axis=0, keepdims=True)
    sig = np.std(x, axis=0, keepdims=True)
    sig = np.where(sig < 1e-6, 1.0, sig)
    return mu.astype(np.float32), sig.astype(np.float32)


def standardize(x: np.ndarray, mu: np.ndarray, sig: np.ndarray) -> np.ndarray:
    return np.nan_to_num((x.astype(np.float32) - mu) / sig, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def min_chunked_sqdist(x: np.ndarray, refs: np.ndarray, chunk: int = 2048) -> np.ndarray:
    if len(x) == 0:
        return np.zeros(0, dtype=np.float64)
    if len(refs) == 0:
        return np.full(len(x), np.inf, dtype=np.float64)
    out = np.empty(len(x), dtype=np.float64)
    refs_t = refs.T
    refs_norm = np.sum(refs * refs, axis=1)[None, :]
    for start in range(0, len(x), chunk):
        part = x[start : start + chunk]
        d = np.sum(part * part, axis=1)[:, None] + refs_norm - 2.0 * (part @ refs_t)
        out[start : start + chunk] = np.min(d, axis=1)
    return out


def loo_support_dist(x: np.ndarray) -> np.ndarray:
    if len(x) <= 1:
        return np.zeros(len(x), dtype=np.float64)
    d = np.sum((x[:, None, :] - x[None, :, :]) ** 2, axis=2)
    np.fill_diagonal(d, np.inf)
    return np.min(d, axis=1).astype(np.float64)


def role_idx(frame_by_role: dict[str, pd.DataFrame], role: str, phase: str, held: str, cap: int, include: bool) -> np.ndarray:
    return ckao.role_indices_filtered(
        frame_by_role,
        role,
        phase,
        cap,
        include=("device_family", held) if include else None,
        exclude=None if include else ("device_family", held),
    )


def fit_histgb_and_support_gate(
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held: str,
    train_cap: int,
    eval_cap: int,
    support_q: float,
) -> tuple[Any, dict[str, float], list[dict[str, Any]]]:
    candidate = c1_candidate()
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    def add(role: str, phase: str, label: int, cap: int) -> np.ndarray:
        before = len(ckao.role_indices_filtered(frame_by_role, role, phase, cap))
        idx = role_idx(frame_by_role, role, phase, held, cap, include=False)
        mat = frontend.matrix(candidate, role, idx)
        xs.append(mat)
        ys.append(np.full(len(idx), int(label), dtype=np.int64))
        audit.append(
            {
                "held_value": held,
                "role": role,
                "phase": phase,
                "label": int(label),
                "rows_before_exclude": before,
                "rows_after_exclude": int(len(idx)),
                "held_rows_removed": int(before - len(idx)),
                "feature_dim": int(mat.shape[1]) if mat.ndim == 2 else 0,
            }
        )
        return mat

    attack_train = add("support_train", "fit", ckh.CLASS_ATTACK, cko.FULL_CAP)
    add("id_calib", "fit", ckh.CLASS_ID, train_cap)
    add("ood_val", "fit", ckh.CLASS_OOD, train_cap)
    add("ood_stress", "fit", ckh.CLASS_HARD_OOD, train_cap)
    x_train = np.vstack(xs).astype(np.float32)
    y_train = np.concatenate(ys).astype(np.int64)
    model = ckh.balanced_fit(ckh.build_model("histgb_shallow", multiclass=True), x_train, y_train)

    # Calibration attack score threshold: non-held benign/OOD select q99.
    attack_parts = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = role_idx(frame_by_role, role, "select", held, eval_cap, include=False)
        if len(idx):
            attack_parts.append(ckai.score_attack(model, frontend.matrix(candidate, role, idx)))
    attack_thr = float(max(np.quantile(v, 0.99) for v in attack_parts if len(v)))

    # Support manifold threshold from legal support train LOO and support_val.
    mu, sig = standardize_fit(x_train)
    refs = standardize(attack_train, mu, sig)
    dists = []
    if len(refs):
        dists.append(loo_support_dist(refs))
    sidx = role_idx(frame_by_role, "support_val", "select", held, eval_cap, include=False)
    if len(sidx) and len(refs):
        sx = standardize(frontend.matrix(candidate, "support_val", sidx), mu, sig)
        dists.append(min_chunked_sqdist(sx, refs))
    if dists:
        support_dist_thr = float(np.quantile(np.concatenate(dists), float(support_q)))
    else:
        support_dist_thr = float("inf")

    thresholds = {
        "attack_threshold": attack_thr,
        "support_dist_threshold": support_dist_thr,
        "support_q": float(support_q),
    }
    for row in audit:
        row.update(thresholds)
        row["attack_train_rows"] = int(len(attack_train))
    return model, thresholds | {"mu": mu, "sig": sig, "refs": refs}, audit


def eval_role(
    model: Any,
    gate: dict[str, Any],
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held: str,
    role: str,
    phase: str,
    kind: str,
    eval_cap: int,
    policy: str,
) -> dict[str, Any]:
    candidate = c1_candidate()
    idx = role_idx(frame_by_role, role, phase, held, eval_cap, include=True)
    desired = "high" if "attack" in kind else "low"
    if len(idx) == 0:
        return {"policy": policy, "held_value": held, "role": role, "phase": phase, "role_kind": kind, "rows": 0}
    x = frontend.matrix(candidate, role, idx)
    attack = ckai.score_attack(model, x)
    xz = standardize(x, gate["mu"], gate["sig"])
    dist = min_chunked_sqdist(xz, gate["refs"])
    raw = attack > float(gate["attack_threshold"])
    near = dist <= float(gate["support_dist_threshold"])
    hard = raw & near
    review = raw & ~near if policy == "review_if_far" else np.zeros_like(raw, dtype=bool)
    hard_rate = ckg.rate(hard)
    err = 1.0 - hard_rate if desired == "high" else hard_rate
    return {
        "policy": policy,
        "held_value": held,
        "role": role,
        "phase": phase,
        "role_kind": kind,
        "rows": int(len(idx)),
        "attack_threshold": float(gate["attack_threshold"]),
        "support_dist_threshold": float(gate["support_dist_threshold"]),
        "raw_alarm_rate": ckg.rate(raw),
        "near_support_rate": ckg.rate(near),
        "hard_alarm_rate": hard_rate,
        "review_rate": ckg.rate(review),
        "desired_hard_direction": desired,
        "error_rate_for_role": float(err),
        "attack_score_mean": float(np.mean(attack)),
        "support_dist_mean": float(np.mean(dist)),
    }


def build_readout(selected: list[dict[str, Any]], rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        f"# {ISSUE}",
        "",
        "## Held-family support-conformal gate probe",
        "",
        "| policy | held family | role | rows | raw | near support | hard | review | desired | error |",
        "|---|---|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for row in rows:
        if int(row.get("rows", 0)) <= 0 or row["role"] not in {"ood_val", "ood_stress", "sealed_final_ood", "future_query", "sealed_final_attack"}:
            continue
        lines.append(
            f"| {row['policy']} | {row['held_value']} | {row['role']} | {row['rows']} | "
            f"{cko.fmt(row['raw_alarm_rate'])} | {cko.fmt(row['near_support_rate'])} | {cko.fmt(row['hard_alarm_rate'])} | "
            f"{cko.fmt(row['review_rate'])} | {row['desired_hard_direction']} | {cko.fmt(row['error_rate_for_role'])} |"
        )
    lines.extend(["", "## Guardrail", "", "- Strict leave-device-family; fit/select exclude held.", "- C1 frontend fixed.", f"- Runtime seconds: {cko.fmt(seconds, 1)}."])
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    out = OUT_BASE if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{args.run_tag}"
    out.mkdir(parents=True, exist_ok=True)
    x_by_role, frame_by_role, input_audit, _ = cko.load_role_inputs(not bool(args.full))
    x_by_role, frame_by_role, cap_rows = ckai.filter_roles_by_recorded_index(x_by_role, frame_by_role, int(args.max_recorded_index))
    ckao.add_family_columns(frame_by_role)
    selected = ckao.select_leave_groups(frame_by_role, int(args.eval_cap), int(args.max_leave_groups), int(args.min_eval_rows), str(args.held_values))
    cache = ckai.ExternalFlowFeatureCache(cko.GOTHAM_ZIP)
    frontend = ckai.ExternalFlowFrontend(x_by_role, frame_by_role, cache)
    rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    for held in selected:
        held_value = str(held["held_value"])
        model, gate, audit = fit_histgb_and_support_gate(frontend, frame_by_role, held_value, int(args.train_cap), int(args.eval_cap), float(args.support_q))
        train_rows.extend(audit)
        for policy in ["review_if_far", "suppress_if_far"]:
            for role, phase, kind in cko.ROLE_EVAL:
                rows.append(eval_role(model, gate, frontend, frame_by_role, held_value, role, phase, kind, int(args.eval_cap), policy))
    seconds = time.time() - started
    cko.write_csv(out / "selected_leave_groups.csv", selected)
    cko.write_csv(out / "role_cap_audit.csv", cap_rows)
    cko.write_csv(out / "train_threshold_audit.csv", train_rows)
    cko.write_csv(out / "leave_role_metrics.csv", rows)
    cko.write_csv(out / "external_extraction_audit.csv", cache.audit_rows)
    cko.write_md(out / "codex_readout.md", build_readout(selected, rows, seconds))
    cko.write_json(out / "run_spec.json", {"issue": ISSUE, "args": vars(args), "selected_leave_groups": selected, "input_audit": input_audit, "seconds": seconds})
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--max-recorded-index", type=int, default=300000)
    ap.add_argument("--train-cap", type=int, default=4000)
    ap.add_argument("--eval-cap", type=int, default=4000)
    ap.add_argument("--max-leave-groups", type=int, default=5)
    ap.add_argument("--min-eval-rows", type=int, default=128)
    ap.add_argument("--held-values", default="")
    ap.add_argument("--support-q", type=float, default=0.95)
    ap.add_argument("--run-tag", default="")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
