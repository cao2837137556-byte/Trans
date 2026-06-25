"""issue27cki: full-data C4 multiclass replay.

This follow-up keeps the issue27ckh winner fixed:

    raw Kitsune115D -> four-class HistGradientBoosting head

and changes only the benign/OOD training and evaluation caps.  The purpose is
to test whether the good C4 result was a small-cap artifact, and whether using
all legal fit/select rows reduces the review burden without touching sealed
final roles.

Sealed final attack/OOD roles remain report-only.  They are never used for
model fitting, threshold selection, calibration, or candidate selection.
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
REPO_DIR = OOD_DIR.parent
ROOT = REPO_DIR.parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27ckg_basic_capability_diagnostic as ckg  # noqa: E402
import issue27ckf_hard_ood_calibrated_worst_group_veto as ckf  # noqa: E402


ISSUE = "issue27cki_c4_full_data_multiclass_replay_2026-06-25"
OUT = ROOT / "runs" / ISSUE
JOB_INDEX = 1
FULL_CAP = 10**9


def parse_caps(text: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for raw in text.split(","):
        item = raw.strip().lower()
        if not item:
            continue
        if item in {"full", "all"}:
            out.append(("full", FULL_CAP))
        else:
            value = int(item)
            if value <= 0:
                raise ValueError(f"cap must be positive, got {raw!r}")
            out.append((str(value), value))
    if not out:
        raise ValueError("no caps requested")
    return out


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    pd.DataFrame(rows, columns=fields).to_csv(path, index=False)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def role_inventory(frame_by_role: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in [
        "id_calib",
        "ood_val",
        "ood_stress",
        "support_train",
        "support_val",
        "same_file_query",
        "future_query",
        "sealed_final_ood",
        "sealed_final_attack",
    ]:
        frame = frame_by_role[role]
        phases = frame["phase"].astype(str) if "phase" in frame else pd.Series(["all"] * len(frame))
        for phase, group in phases.groupby(phases, sort=True):
            rows.append({"role": role, "phase": str(phase), "rows": int(len(group))})
        rows.append({"role": role, "phase": "all", "rows": int(len(frame))})
    return rows


def rate_count(rate: float, rows: int) -> int:
    if np.isnan(rate):
        return 0
    return int(round(float(rate) * int(rows)))


def build_readout(
    role_metrics: list[dict[str, Any]],
    group_metrics: list[dict[str, Any]],
    auc_rows: list[dict[str, Any]],
    train_audit: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
    cap_labels: list[str],
    seconds: float,
) -> list[str]:
    summary = ckh.make_summary(role_metrics, group_metrics)
    role_df = pd.DataFrame(role_metrics)
    lines = [
        "# issue27cki C4 full-data multiclass replay",
        "",
        "## Scope",
        "",
        "This run keeps the issue27ckh C4 structure fixed and changes only data caps.",
        "C4 is a four-class raw115 HistGradientBoosting head: ID benign / ordinary OOD / hard OOD / attack.",
        "Sealed final attack and sealed final OOD are report-only and are not used for fit, threshold, calibration, or model selection.",
        "",
        "## Data caps",
        "",
        f"- requested benign/OOD train caps: `{', '.join(cap_labels)}`",
        "- evaluation cap: `full legal role rows`",
        "- attack positives remain the frozen support_train view: `385` rows",
        "",
        "## Role inventory",
        "",
        "| role | phase | rows |",
        "|---|---|---:|",
    ]
    for row in inventory:
        lines.append(f"| {row['role']} | {row['phase']} | {row['rows']} |")
    lines.extend(
        [
            "",
            "## Candidate summary",
            "",
            "| candidate | train cap | ID hard | OOD-val hard | hard-OOD hard | support hard | same-file hard | future hard | sealed attack hard | sealed OOD hard | sealed OOD group max | sealed attack review | sealed OOD review |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary:
        candidate = str(row["candidate"])
        cap = candidate.rsplit("_cap", 1)[-1] if "_cap" in candidate else ""
        lines.append(
            "| "
            + " | ".join(
                [
                    candidate,
                    cap,
                    ckh.fmt(row["id_calib"]),
                    ckh.fmt(row["ood_val"]),
                    ckh.fmt(row["ood_stress"]),
                    ckh.fmt(row["support_val"]),
                    ckh.fmt(row["same_file_query"]),
                    ckh.fmt(row["future_query"]),
                    ckh.fmt(row["sealed_final_attack"]),
                    ckh.fmt(row["sealed_final_ood"]),
                    ckh.fmt(row["sealed_final_ood_group_max"]),
                    ckh.fmt(row["sealed_attack_review"]),
                    ckh.fmt(row["sealed_ood_review"] if "sealed_ood_review" in row else np.nan),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Review burden by role", ""])
    lines.extend(
        [
            "| candidate | role | rows | raw alarm | review | review count | hard alarm | hard count | threshold |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in role_df.sort_values(["candidate", "role"]).iterrows():
        rows = int(row["rows"])
        review = float(row["conflict_review_rate"])
        hard = float(row["hard_alarm_rate"])
        raw = float(row["raw_alarm_rate"])
        lines.append(
            f"| {row['candidate']} | {row['role']} | {rows} | {ckh.fmt(raw)} | {ckh.fmt(review)} | {rate_count(review, rows)} | {ckh.fmt(hard)} | {rate_count(hard, rows)} | {ckh.fmt(float(row['attack_threshold']))} |"
        )
    lines.extend(["", "## Threshold-free separability", ""])
    lines.extend(
        [
            "| candidate | comparison | positive rows | negative rows | AUC | AP |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in auc_rows:
        lines.append(
            f"| {row['candidate']} | {row['comparison']} | {row['positive_rows']} | {row['negative_rows']} | {ckh.fmt(row['auc'])} | {ckh.fmt(row['ap'])} |"
        )
    lines.extend(["", "## Training audit", ""])
    lines.extend(["| candidate | role | phase | label | rows |", "|---|---|---|---:|---:|"])
    for row in train_audit:
        lines.append(f"| {row['candidate']} | {row['role']} | {row['phase']} | {row['label']} | {row['rows']} |")
    lines.extend(
        [
            "",
            "## Interpretation guardrail",
            "",
            "- This is still a seed42 detector-capability replay, not a final benchmark.",
            "- If full-fit lowers sealed OOD review without hurting sealed attack, C4 is not merely a 1600-row artifact.",
            "- If full-fit hurts attack or increases review, the next step is not more blind data; it is invariant/causal training and stronger heads.",
            "- Sealed final roles are used only for report-only replay.",
            "",
            f"Runtime seconds: `{ckh.fmt(seconds, 1)}`.",
        ]
    )
    return lines


def prepare_roles(smoke: bool) -> tuple[dict[str, np.ndarray], dict[str, pd.DataFrame], set[str], dict[str, Any]]:
    input_audit = ckh.ckc.validate_inputs()
    attack_root = Path(input_audit["attack_root"])
    cert_x = np.load(ckh.ckc.CERT_X, mmap_mode="r")
    schema = json.loads(ckh.ckc.FEATURE_SCHEMA.read_text(encoding="utf-8"))
    subspaces = ckh.ckc.bp.build_subspaces(schema)
    benign_idx, benign_records = ckh.ckc.load_benign_roles(smoke)
    benign_records["id_benign_calib"] = ckh.ckc.add_source_disjoint_phase(benign_records["id_benign_calib"])
    benign_records["ood_benign_val"] = ckh.ckc.add_source_disjoint_phase(benign_records["ood_benign_val"])
    hard_ood_x = np.asarray(cert_x[benign_idx["ood_benign_stress"]], dtype=np.float32)
    hard_ood_records = ckf.add_hard_ood_phase(benign_records["ood_benign_stress"])
    support_x, support_records, support_train_idx, support_val_idx = ckh.ckc.load_support(attack_root)
    support_labels = set(support_records.loc[support_train_idx, "attack_label"].astype(str))

    job = next(spec for spec in ckh.ckc.JOB_SPECS if spec.job_index == JOB_INDEX)
    stack = ckf.build_stack(
        job,
        cert_x,
        benign_idx,
        benign_records,
        support_x,
        support_records,
        support_train_idx,
        support_val_idx,
        subspaces,
        attack_root,
        hard_ood_records,
        hard_ood_x,
        smoke,
        False,
    )

    same_x, same_records = ckh.ckc.load_attack_role(attack_root, "same_file_time_forward_dev_query_exact", smoke)
    future_x, future_records = ckh.ckc.load_attack_role(attack_root, "dev_future_attack_query_exact", smoke)
    sealed_attack_x, sealed_attack_records = ckh.ckc.load_attack_role(
        attack_root,
        "sealed_final_attack_exact_realign",
        smoke,
    )
    sealed_ood_x = np.asarray(cert_x[benign_idx["sealed_final_ood"]], dtype=np.float32)

    frame_by_role = dict(stack["frames"])
    x_by_role = {
        "id_calib": np.asarray(cert_x[benign_idx["id_benign_calib"]], dtype=np.float32),
        "ood_val": np.asarray(cert_x[benign_idx["ood_benign_val"]], dtype=np.float32),
        "support_val": support_x[support_val_idx],
        "ood_stress": hard_ood_x,
        "same_file_query": same_x,
        "future_query": future_x,
        "sealed_final_ood": sealed_ood_x,
        "sealed_final_attack": sealed_attack_x,
        "support_train": support_x[support_train_idx],
    }
    for role, x_role, records in [
        ("same_file_query", same_x, ckg.add_source_or_time_phase(same_records)),
        ("future_query", future_x, ckg.add_source_or_time_phase(future_records)),
        ("sealed_final_attack", sealed_attack_x, sealed_attack_records.copy()),
        ("sealed_final_ood", sealed_ood_x, benign_records["sealed_final_ood"].copy()),
    ]:
        if role in {"sealed_final_attack", "sealed_final_ood"}:
            records = records.copy()
            records["phase"] = "report_only"
        frame_by_role[role] = ckf.build_role_frame_with_temporal(
            role,
            "attack" if "attack" in role else "benign_ood",
            x_role,
            records,
            stack,
            job,
        )
    support_train_records = support_records.iloc[support_train_idx].reset_index(drop=True).copy()
    support_train_records["phase"] = "fit"
    frame_by_role["support_train"] = ckf.build_role_frame_with_temporal(
        "support_train",
        "attack",
        x_by_role["support_train"],
        support_train_records,
        stack,
        job,
    )
    return x_by_role, frame_by_role, support_labels, input_audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument(
        "--caps",
        default="full",
        help="Comma-separated benign/OOD train caps, e.g. 1600,5000,20000,full. Default: full.",
    )
    args = parser.parse_args()
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)

    caps = parse_caps(args.caps)
    x_by_role, frame_by_role, support_labels, input_audit = prepare_roles(args.smoke)
    inventory = role_inventory(frame_by_role)

    old_benign_cap = ckh.BENIGN_CAP_PER_ROLE
    old_eval_cap = ckh.EVAL_CAP_PER_ROLE
    ckh.EVAL_CAP_PER_ROLE = FULL_CAP

    role_metrics: list[dict[str, Any]] = []
    group_metrics: list[dict[str, Any]] = []
    coverage_metrics: list[dict[str, Any]] = []
    train_audit: list[dict[str, Any]] = []
    auc_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    try:
        for cap_label, cap_value in caps:
            ckh.BENIGN_CAP_PER_ROLE = cap_value
            candidate = ckh.Candidate(
                f"C4_fewshot_multiclass_raw115_cap{cap_label}",
                "fewshot_direct",
                "raw115",
                "multiclass_id_ood_hardood_attack",
                "histgb_shallow",
                f"C4 raw115 four-class head with benign/OOD train cap {cap_label} and full evaluation.",
            )
            candidate_rows.append(
                {
                    **candidate.__dict__,
                    "benign_ood_train_cap_label": cap_label,
                    "benign_ood_train_cap_value": cap_value,
                    "eval_cap_label": "full",
                    "eval_cap_value": FULL_CAP,
                }
            )
            fitted, audit = ckh.fit_candidate(candidate, x_by_role, frame_by_role)
            thresholds = ckh.benign_safe_threshold(candidate, fitted, x_by_role, frame_by_role)
            for item in audit:
                train_audit.append({"candidate": candidate.name, "train_cap": cap_label, **item})
            parts_by_role: dict[str, pd.DataFrame] = {}
            for role, phase, role_kind in ckh.ROLE_EVAL:
                row, part = ckh.eval_candidate_role(candidate, fitted, thresholds, role, phase, role_kind, x_by_role, frame_by_role)
                row["train_cap"] = cap_label
                role_metrics.append(row)
                group_metrics.extend(ckh.group_rows(candidate, role, phase, part))
                if role in {"support_val", "same_file_query", "future_query", "sealed_final_attack"}:
                    coverage_metrics.extend(ckh.support_coverage_rows(candidate, role, part, support_labels))
                parts_by_role[role] = part
            for attack_role, ood_role, name in [
                ("support_val", "ood_stress", "support_vs_hard_ood"),
                ("same_file_query", "ood_stress", "same_file_vs_hard_ood"),
                ("future_query", "ood_stress", "future_vs_hard_ood"),
                ("sealed_final_attack", "sealed_final_ood", "sealed_attack_vs_sealed_ood"),
            ]:
                pos = parts_by_role[attack_role]["attack_score"].to_numpy()
                neg = parts_by_role[ood_role]["attack_score"].to_numpy()
                auc, ap = ckh.safe_auc(pos, neg)
                auc_rows.append(
                    {
                        "candidate": candidate.name,
                        "train_cap": cap_label,
                        "comparison": name,
                        "positive_rows": len(pos),
                        "negative_rows": len(neg),
                        "auc": auc,
                        "ap": ap,
                    }
                )
    finally:
        ckh.BENIGN_CAP_PER_ROLE = old_benign_cap
        ckh.EVAL_CAP_PER_ROLE = old_eval_cap

    summary = ckh.make_summary(role_metrics, group_metrics)
    seconds = time.time() - started
    write_csv(OUT / "candidate_matrix.csv", candidate_rows)
    write_csv(OUT / "role_inventory.csv", inventory)
    write_csv(OUT / "train_audit.csv", train_audit)
    write_csv(OUT / "role_metrics.csv", role_metrics)
    write_csv(OUT / "group_metrics_by_source_device.csv", group_metrics)
    write_csv(OUT / "support_coverage_metrics.csv", coverage_metrics)
    write_csv(OUT / "threshold_free_metrics.csv", auc_rows)
    write_csv(OUT / "selected_summary.csv", summary)
    write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "C4 full-data / data-cap replay after issue27ckh",
            "smoke": args.smoke,
            "job_index": JOB_INDEX,
            "seed": ckh.SEED,
            "requested_caps": [label for label, _ in caps],
            "cap_values": {label: value for label, value in caps},
            "eval_cap": "full",
            "full_cap_sentinel": FULL_CAP,
            "benign_safe_q": ckh.BENIGN_SAFE_Q,
            "sealed_final_roles_used_for_training": False,
            "candidate_structure": "raw115 four-class HistGradientBoostingClassifier",
            "input_audit": input_audit,
            "seconds": seconds,
            "outputs": [
                "candidate_matrix.csv",
                "role_inventory.csv",
                "train_audit.csv",
                "role_metrics.csv",
                "group_metrics_by_source_device.csv",
                "support_coverage_metrics.csv",
                "threshold_free_metrics.csv",
                "selected_summary.csv",
                "summary.md",
                "codex_readout.md",
            ],
        },
    )
    readout = build_readout(
        role_metrics,
        group_metrics,
        auc_rows,
        train_audit,
        inventory,
        [label for label, _ in caps],
        seconds,
    )
    write_md(OUT / "summary.md", readout)
    write_md(OUT / "codex_readout.md", readout)
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds}, indent=2))


if __name__ == "__main__":
    main()
