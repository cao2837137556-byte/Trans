from __future__ import annotations

import csv
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler


REPO = Path(r"D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline")
KITNET = Path(r"D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master")
OUT = REPO / "runs" / "issue27o_full_mirai_protocol_reset_feature_mapping_and_formal_benchmark_spec_2026-05-27"
MAINLINE_DOCS = REPO / "runs" / "mainline_docs"

FULL_MIRAI = KITNET / "Mirai_dataset.csv"
FULL_LABELS = KITNET / "mirai_labels.csv"
ISSUE27N = REPO / "runs" / "issue27n_full_mirai_restored115_feature_mapping_and_lowguardpp_interface_smoke_2026-05-27"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for k in row:
                if k not in fieldnames:
                    fieldnames.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "NA") for k in fieldnames})


def read_labels() -> np.ndarray:
    vals = []
    with FULL_LABELS.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if s:
                vals.append(int(float(s.split(",")[0])))
    return np.asarray(vals, dtype=np.int8)


def load_range(start: int, count: int) -> np.ndarray:
    # Feature matrix is dirty116. Drop col0 index-like column to get anonymous clean115.
    df = pd.read_csv(FULL_MIRAI, header=None, skiprows=range(0, start), nrows=count)
    return df.iloc[:, 1:].to_numpy(dtype=np.float32)


def kcenter_select(X: np.ndarray, k: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    first = int(rng.integers(0, n))
    selected = [first]
    min_dist = np.sum((X - X[first]) ** 2, axis=1)
    for _ in range(1, min(k, n)):
        idx = int(np.argmax(min_dist))
        selected.append(idx)
        dist = np.sum((X - X[idx]) ** 2, axis=1)
        min_dist = np.minimum(min_dist, dist)
    return np.asarray(selected, dtype=int)


def calibrate_threshold(id_scores: np.ndarray, ood_val_scores: np.ndarray, target: float = 0.01) -> float:
    # Higher score = more attack/anomalous. Use validation only.
    q = 1.0 - target
    return float(max(np.quantile(id_scores, q), np.quantile(ood_val_scores, q)))


def safe_auc(y: np.ndarray, scores: np.ndarray) -> tuple[float | str, float | str]:
    try:
        return float(roc_auc_score(y, scores)), float(average_precision_score(y, scores))
    except Exception:
        return "NA", "NA"


def run_smoke() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # Small, fixed, row-order split. This is an interface smoke, not validation.
    split = {
        "id_train": (0, 5000),
        "ood_train": (50000, 5000),
        "id_calib": (70000, 2000),
        "ood_val": (90000, 2000),
        "final_ood_eval": (110000, 2000),
        "attack_support_pool": (121621, 5000),
        "attack_eval": (200000, 5000),
    }
    X_id = load_range(*split["id_train"])
    X_ood = load_range(*split["ood_train"])
    X_id_cal = load_range(*split["id_calib"])
    X_ood_val = load_range(*split["ood_val"])
    X_final_ood = load_range(*split["final_ood_eval"])
    X_pool = load_range(*split["attack_support_pool"])
    X_attack_eval = load_range(*split["attack_eval"])

    rows: list[dict[str, Any]] = []
    seeds = [42, 43, 44]
    for seed in seeds:
        support_idx = kcenter_select(X_pool, 32, seed)
        X_support = X_pool[support_idx]
        X_neg = np.vstack([X_id, X_ood])
        X_train = np.vstack([X_neg, X_support])
        y_train = np.concatenate([np.zeros(X_neg.shape[0], dtype=int), np.ones(X_support.shape[0], dtype=int)])
        weights = np.concatenate(
            [
                np.ones(X_id.shape[0], dtype=np.float32),
                np.full(X_ood.shape[0], 4.0, dtype=np.float32),
                np.full(X_support.shape[0], 4.0, dtype=np.float32),
            ]
        )

        methods = []

        t0 = time.time()
        hist = HistGradientBoostingClassifier(
            max_depth=2,
            learning_rate=0.05,
            l2_regularization=0.1,
            max_iter=100,
            random_state=seed,
        )
        hist.fit(X_train, y_train, sample_weight=weights)
        methods.append(("LOW_GUARD_HistGB_Conservative", "anonymous_clean115_all", hist, "predict_proba", time.time() - t0))

        t0 = time.time()
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        lr = LogisticRegression(max_iter=1000, solver="liblinear", random_state=seed)
        lr.fit(X_train_s, y_train, sample_weight=weights)
        methods.append(("LOW_GUARD_LR", "anonymous_clean115_all", (scaler, lr), "scaled_predict_proba", time.time() - t0))

        # Collapse-prone score baseline: distance from guarded benign center, no final eval selection.
        t0 = time.time()
        center = np.vstack([X_id, X_ood]).mean(axis=0)
        methods.append(("DeepSAD_center_baseline", "anonymous_clean115_all", center, "distance_to_center", time.time() - t0))

        for method_name, schema, model, mode, train_time in methods:
            t1 = time.time()
            if mode == "predict_proba":
                score_id_cal = model.predict_proba(X_id_cal)[:, 1]
                score_ood_val = model.predict_proba(X_ood_val)[:, 1]
                score_final_ood = model.predict_proba(X_final_ood)[:, 1]
                score_attack = model.predict_proba(X_attack_eval)[:, 1]
                score_support = model.predict_proba(X_support)[:, 1]
            elif mode == "scaled_predict_proba":
                scaler, lr = model
                score_id_cal = lr.predict_proba(scaler.transform(X_id_cal))[:, 1]
                score_ood_val = lr.predict_proba(scaler.transform(X_ood_val))[:, 1]
                score_final_ood = lr.predict_proba(scaler.transform(X_final_ood))[:, 1]
                score_attack = lr.predict_proba(scaler.transform(X_attack_eval))[:, 1]
                score_support = lr.predict_proba(scaler.transform(X_support))[:, 1]
            else:
                center = model
                score_id_cal = np.linalg.norm(X_id_cal - center, axis=1)
                score_ood_val = np.linalg.norm(X_ood_val - center, axis=1)
                score_final_ood = np.linalg.norm(X_final_ood - center, axis=1)
                score_attack = np.linalg.norm(X_attack_eval - center, axis=1)
                score_support = np.linalg.norm(X_support - center, axis=1)
            infer_time = time.time() - t1
            threshold = calibrate_threshold(score_id_cal, score_ood_val, target=0.01)
            y_auc = np.concatenate([np.zeros(score_final_ood.shape[0], dtype=int), np.ones(score_attack.shape[0], dtype=int)])
            s_auc = np.concatenate([score_final_ood, score_attack])
            roc, pr = safe_auc(y_auc, s_auc)
            rows.append(
                {
                    "seed": seed,
                    "method_name": method_name,
                    "feature_schema": schema,
                    "split_name": "issue27o_micro_smoke_row_order",
                    "attack_detection": float(np.mean(score_attack >= threshold)),
                    "final_ood_alarm": float(np.mean(score_final_ood >= threshold)),
                    "id_calib_alarm": float(np.mean(score_id_cal >= threshold)),
                    "ood_val_alarm": float(np.mean(score_ood_val >= threshold)),
                    "threshold": threshold,
                    "feasible_under_1pct": float(np.mean(score_final_ood >= threshold)) <= 0.01,
                    "roc_auc_attack_vs_ood": roc,
                    "pr_auc_attack_vs_ood": pr,
                    "support_mean_score": float(np.mean(score_support)),
                    "attack_mean_score": float(np.mean(score_attack)),
                    "final_ood_mean_score": float(np.mean(score_final_ood)),
                    "train_time_sec": train_time,
                    "inference_time_sec": infer_time,
                    "support_eval_disjoint": True,
                    "final_eval_used_for_selection": False,
                    "hyperparam_search": False,
                    "claim_level": "interface_smoke_only",
                }
            )
    summary = []
    for method in sorted(set(r["method_name"] for r in rows)):
        sub = [r for r in rows if r["method_name"] == method]
        summary.append(
            {
                "method_name": method,
                "feature_schema": sub[0]["feature_schema"],
                "detection_mean": float(np.mean([r["attack_detection"] for r in sub])),
                "detection_min": float(np.min([r["attack_detection"] for r in sub])),
                "final_ood_alarm_max": float(np.max([r["final_ood_alarm"] for r in sub])),
                "feasible_rate": float(np.mean([r["feasible_under_1pct"] for r in sub])),
                "smoke_status": "ran",
                "claim_level": "interface_smoke_only_not_formal_validation",
            }
        )
    return rows, summary


def write_specs(primary_verdict: str, smoke_summary: list[dict[str, Any]]) -> None:
    write_text(
        OUT / "protocol_reset_rationale.md",
        """
# Protocol Reset Rationale

issue20-27n are treated as the exploratory phase. They discovered the LOW-GUARD++ candidate, exposed feature-schema risks, found full Mirai, and clarified why original100 / clean115 / restored115 cannot be mixed.

Full Mirai can still be used as a formal within-dataset benchmark because a protocol reset makes data identity explicit: all methods are retrained from scratch under one declared split, one feature schema, and one final-eval report-only rule.

Full Mirai cannot be called a completely unseen external test because the historical `my_gold` subset is the first 200k rows of the same asset and was used in earlier exploration. The honest framing is protocol-reset within-dataset benchmarking. A second dataset remains necessary for external generalization.
""",
    )
    write_text(
        OUT / "formal_benchmark_scope.md",
        """
# Formal Benchmark Scope

## Dataset Role

- Dataset: full Mirai/Botnet labeled feature asset.
- Role: main within-dataset protocol-reset benchmark.
- Not external: historical exploration used a prefix subset.

## Allowed Claims After Formal Rerun

- Within-dataset clean protocol result.
- Feature representation comparison under a reset benchmark.
- Fair baseline rerun under identical split/feature/threshold rules.

## Not Allowed

- External generalization.
- Completely unseen independent test.
- Final validation before a second dataset.
- Reusing old issue20-27n scores as final main-text evidence.
""",
    )

    schema_rows = [
        {
            "schema": "dirty116",
            "available": True,
            "usable": False,
            "mapping_confidence": "high_for_index_artifact",
            "decision": "drop_col0",
            "notes": "col0 is index-like and must not enter models",
        },
        {
            "schema": "anonymous_clean115_all",
            "available": True,
            "usable": True,
            "mapping_confidence": "high_shape_low_semantics",
            "decision": "use_for_protocol_reset_benchmark_if_named_anonymous_clean115",
            "notes": "feature semantics/order unknown; benchmark can proceed but not as Kitsune restored115",
        },
        {
            "schema": "restored115_all",
            "available": "shape_only",
            "usable": False,
            "mapping_confidence": "low",
            "decision": "blocked_until_header_or_generator_recovered",
            "notes": "cannot claim restored115 semantics yet",
        },
        {
            "schema": "restored115_common100",
            "available": "tentative_only",
            "usable": False,
            "mapping_confidence": "blocked",
            "decision": "do_not_construct",
            "notes": "do not delete tentative extra15 columns without proof",
        },
        {
            "schema": "restored115_extra15_only",
            "available": "tentative_only",
            "usable": False,
            "mapping_confidence": "blocked",
            "decision": "diagnostic_blocked",
            "notes": "extra15 semantics unverified",
        },
    ]
    write_csv(OUT / "feature_schema_recovery_decision.csv", schema_rows)
    write_text(
        OUT / "feature_schema_recovery_report.md",
        """
# Feature Schema Recovery Report

clean115 is stable as an anonymous 115D matrix: dirty116 col0 is removed, labels align, and the full scan from issue27n found no NaN/Inf/constant columns.

restored115/common100 mapping is still not recovered. The only safe route for issue27p is therefore an **anonymous clean115 protocol-reset benchmark** unless a header/generator is found before execution.

Important boundary: anonymous clean115 is not claim-equivalent to Kitsune restored115 and not claim-equivalent to old original100. It can support fair within-dataset model comparisons after reset, not feature-semantics claims.
""",
    )

    split_rows = [
        {
            "split_name": "full_mirai_protocol_reset_row_order_v1",
            "feature_schema": "anonymous_clean115_all",
            "evidence_level": "within_dataset_protocol_reset_not_external",
            "id_benign_train_rows": 60000,
            "ood_benign_train_rows": 20000,
            "id_calibration_rows": 20000,
            "ood_validation_rows": 10000,
            "final_ood_eval_rows": 11621,
            "attack_support_pool_rows": 60000,
            "attack_support_count": 32,
            "attack_eval_rows": 582516,
            "timestamp_available": False,
            "capture_session_available": False,
            "split_type": "row_order_benign_prefix_and_attack_suffix",
            "temporal_claim_allowed": False,
            "external_claim_allowed": False,
            "my_gold_overlap_handling": "declared_exploration_used_source; all methods rerun under reset protocol",
            "final_eval_report_only": True,
            "final_eval_used_for_selection": False,
        }
    ]
    write_csv(OUT / "formal_full_mirai_split_manifest.csv", split_rows)
    write_text(
        OUT / "formal_full_mirai_split_contract.md",
        """
# Formal Full Mirai Split Contract

Split: `full_mirai_protocol_reset_row_order_v1`

This is not temporal, not capture-disjoint, and not external. It is a declared within-dataset protocol-reset split.

Rules:

- final OOD eval and attack eval are report-only.
- OOD validation is used only for threshold/validation feasibility.
- attack support is selected only from the attack support pool.
- all models and baselines must be retrained under this exact split.
- `my_gold` overlap is handled by declaring issue20-27n exploratory and rerunning all methods from scratch. It does not make full Mirai external or unseen.
""",
    )

    write_text(
        OUT / "formal_baseline_list.md",
        """
# Formal Baseline List

Required rerun methods:

- LOW-GUARD++ HistGB-Conservative
- LOW-GUARD-LR minimal instance
- raw LR without guard
- threshold-only LR
- no OOD guard
- no threshold guard
- HistGB shallow
- Isolation Forest
- OC-SVM
- DevNet-style score head
- DeepSAD-style lite objective
- random support / random32
- PrototypeMargin, optional if cheap

Every method must be rerun. Old issue27b/27d collapse results are exploration and cannot be copied into the reset benchmark.
""",
    )
    write_text(
        OUT / "formal_fairness_contract.md",
        """
# Formal Fairness Contract

- Same split for every method.
- Same feature schema for every method.
- No final eval for model, threshold, feature, support, or hyperparameter selection.
- Same official OOD alarm budget: 1%.
- Report detection mean/min, final OOD alarm max, feasible rate, OOD val alarm, threshold, and seed stability.
- Interface-incomplete models must be labeled `implementation_incomplete`, not method failure.
- Collapse-prone models must be retested; old collapse does not carry into the reset benchmark.
""",
    )
    write_text(
        OUT / "feature_representation_study_contract.md",
        """
# Feature Representation Study Contract

Allowed now:

- `anonymous_clean115_all`

Blocked until mapping recovery:

- `clean115_common100`
- `clean115_extra15_only`
- drop top-HH / rank normalize HH
- restored115 semantic claims
- original100 equivalence claims

If mapping remains low-confidence, issue27p should run an anonymous clean115 benchmark. It must name the input exactly that way and avoid describing it as Kitsune restored115 or old original100.
""",
    )

    phases = [
        ("Phase 1", "feature schema + split contract", "full Mirai files + labels", "contract docs and manifests", "no", "schema and split declared", "fallback to anonymous clean115"),
        ("Phase 2", "formal rerun of LOW-GUARD++/LR/baselines", "contract + code", "formal benchmark tables", "maybe", "all baselines complete", "mark implementation gaps"),
        ("Phase 3", "feature representation study", "mapped schemas", "feature comparison", "maybe", "mapping-safe comparison", "use anonymous naming"),
        ("Phase 4", "collapse models re-evaluation", "DevNet/DeepSAD specs", "new collapse/recovery evidence", "maybe", "no old collapse reuse", "debug objectives"),
        ("Phase 5", "component ablation", "full benchmark assets", "guard/support/threshold ablation", "maybe", "mechanism confirmed", "bound claims"),
        ("Phase 6", "support/label/OOD robustness", "formal benchmark", "shot/noise/contamination curves", "maybe", "deployment assumption bounded", "state limitations"),
        ("Phase 7", "temporal/row-order robustness", "timestamps or ordered assets", "temporal evidence", "maybe", "no leakage", "report blocked if metadata absent"),
        ("Phase 8", "second dataset external generalization", "external dataset", "external validity table", "likely", "external claim supported", "keep within-dataset claim only"),
        ("Phase 9", "efficiency/deployment robustness", "validated method", "runtime and update simulation", "maybe", "deployment feasibility bounded", "no broad deployment claim"),
        ("Phase 10", "paper writing", "all accepted evidence", "main/appendix claims", "no", "claim matrix clean", "move weak evidence to appendix"),
    ]
    write_csv(
        OUT / "formal_experiment_task_table.csv",
        [
            {
                "phase": p,
                "goal": goal,
                "inputs": inputs,
                "outputs": outputs,
                "requires_slurm": slurm,
                "success_standard": success,
                "failure_interpretation": fail,
            }
            for p, goal, inputs, outputs, slurm, success, fail in phases
        ],
    )
    write_text(
        OUT / "formal_experiment_roadmap.md",
        """
# Formal Experiment Roadmap

The reset route is:

1. Finish feature schema and split contract.
2. Rerun LOW-GUARD++ / LR / all baselines under full Mirai protocol reset.
3. Run feature representation study only when mappings are safe.
4. Re-evaluate collapse models rather than importing old failures.
5. Run component ablation, support/noise/OOD contamination, row-order or temporal robustness if metadata supports it.
6. Use a second dataset for external generalization.
7. Only then move to deployment robustness and paper writing.
""",
    )

    smoke_note = "ran" if smoke_summary else "blocked"
    write_text(
        OUT / "protocol_reset_interface_smoke_diagnosis.md",
        f"""
# Protocol Reset Interface Smoke Diagnosis

Smoke status: `{smoke_note}`

The smoke uses only `anonymous_clean115_all`. It does not use restored115_common100 or extra15 because those mappings remain blocked. It is not formal validation and does not support a main claim.

The smoke verifies that:

- the anonymous clean115 matrix can feed LOW-GUARD-style heads;
- thresholding uses ID calibration + OOD validation only;
- final OOD and attack eval are report-only;
- a collapse-prone baseline can be included under the same interface.
""",
    )

    write_text(
        OUT / "issue27p_next_action.md",
        """
# issue27p Next Action

Recommended:

`issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution_2026-05-27`

Scope:

- Execute the formal benchmark on `anonymous_clean115_all`.
- Rerun LOW-GUARD++ HistGB, LOW-GUARD-LR, LR variants, HistGB shallow, Isolation Forest, OC-SVM, DevNet-style, DeepSAD-style, random support, and ablations.
- Do not report restored115/common100 semantics unless mapping is recovered before execution.

Parallel optional preparation:

`issue27p_feature_mapping_recovery_for_restored115_common100`

This can upgrade the feature-study branch, but it should not block the anonymous clean115 reset benchmark.
""",
    )

    write_text(
        OUT / "issue27o_decision.md",
        f"""
# issue27o Decision

primary_verdict = `{primary_verdict}`

Full Mirai is adopted as a protocol-reset within-dataset benchmark. Earlier issue20-27n results are exploration and cannot be used as final main-text results. Feature mapping remains low-confidence, so the formal route should proceed as an anonymous clean115 benchmark unless mapping is recovered before issue27p.
""",
    )
    write_text(
        OUT / "claim_update_after_issue27o.md",
        """
# Claim Update After issue27o

Allowed:

- Full Mirai is adopted as a protocol-reset within-dataset benchmark.
- Earlier experiments are exploratory evidence for method and data design.
- External generalization is reserved for a second dataset.
- Formal claims require rerunning LOW-GUARD++ and all baselines under the reset protocol.

Forbidden:

- Full Mirai is a completely unseen external test.
- LOW-GUARD++ is validated before formal rerun.
- Old baseline results remain final after protocol reset.
- Restored115/common100 are verified while mapping remains low confidence.
- Deployment robustness is completed.
""",
    )
    write_text(
        OUT / "reviewer_defense_protocol_reset.md",
        """
# Reviewer Defense: Protocol Reset

**Q1: Did you tune on full Mirai and then test on it?**
We explicitly mark issue20-27n as exploration. The reset benchmark retrains every method under one split and does not call full Mirai external or unseen.

**Q2: Why is full Mirai still valid?**
It is valid as a within-dataset benchmark after protocol reset, not as an external test.

**Q3: What about my_gold prior use?**
It is disclosed as exploration-used source. It motivates the reset rather than invalidating the dataset.

**Q4: Can anonymous clean115 support claims?**
It can support fair within-dataset model comparisons if named as anonymous clean115. It cannot support restored115/common100 semantic claims.

**Q5: Are old baseline failures final?**
No. All baselines must be rerun under the reset protocol.
""",
    )


def update_docs(primary_verdict: str) -> None:
    handoff = MAINLINE_DOCS / "mainline_handoff.md"
    expmap = MAINLINE_DOCS / "mainline_experiment_map.md"
    entry = f"""

## issue27o full Mirai protocol reset spec (2026-05-27)

- primary_verdict: `{primary_verdict}`
- scope: redefines issue20-27n as exploration, adopts full Mirai as a protocol-reset within-dataset benchmark, writes split/fairness/feature-study contracts, and runs a small anonymous-clean115 interface smoke.
- key boundary: full Mirai is not a completely unseen external test; restored115/common100 mapping remains low confidence; all baselines must be rerun under the reset protocol.
- next action: `issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution`.
"""
    if "issue27o full Mirai protocol reset spec" not in handoff.read_text(encoding="utf-8", errors="ignore"):
        handoff.write_text(handoff.read_text(encoding="utf-8", errors="ignore").rstrip() + entry + "\n", encoding="utf-8")
    map_entry = f"""
| issue27o | full Mirai protocol reset spec | `{primary_verdict}` | Adopts full Mirai as within-dataset protocol-reset benchmark; old issues are exploration; restored115/common100 remain unmapped; baselines must be rerun. Next: `issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution`. |
"""
    if "| issue27o |" not in expmap.read_text(encoding="utf-8", errors="ignore"):
        expmap.write_text(expmap.read_text(encoding="utf-8", errors="ignore").rstrip() + "\n" + map_entry, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    primary_verdict = "full_mirai_protocol_reset_ready_with_anonymous_clean115"
    smoke_rows, smoke_summary = run_smoke()
    write_csv(OUT / "protocol_reset_interface_smoke_by_seed.csv", smoke_rows)
    write_csv(OUT / "protocol_reset_interface_smoke_summary.csv", smoke_summary)
    write_specs(primary_verdict, smoke_summary)

    summary = f"""
# issue27o Full Mirai Protocol Reset Spec

## Verdict

- primary_verdict = `{primary_verdict}`

## Answers

1. full Mirai is formally defined as the protocol-reset main within-dataset benchmark.
2. issue20-27n are reclassified as exploration.
3. full Mirai is not a completely unseen external test.
4. second dataset = future external generalization.
5. clean115 is usable as `anonymous_clean115_all`.
6. restored115/common100 mapping is not recovered; confidence remains low/blocked.
7. Because mapping is untrusted, anonymous clean115 benchmark is allowed with strict naming.
8. formal split contract was constructed.
9. my_gold overlap is handled by protocol reset disclosure; not external/unseen.
10. all baseline rerun fairness protocol is defined.
11. collapse models must be rerun under reset protocol.
12. interface smoke was executed on anonymous clean115 only.
13. smoke ran successfully; no formal claim is made from smoke.
14. issue27p recommendation: `issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution`.
15. Slurm: not needed for this spec/smoke; likely useful for full baseline rerun.
"""
    write_text(OUT / "summary.md", summary)

    config = {
        "issue": "issue27o_full_mirai_protocol_reset_feature_mapping_and_formal_benchmark_spec_2026-05-27",
        "primary_verdict": primary_verdict,
        "formal_dataset_role": "within_dataset_protocol_reset_benchmark",
        "feature_schema": "anonymous_clean115_all",
        "restored115_common100_mapping": "blocked",
        "interface_smoke_executed": True,
        "final_eval_report_only": True,
        "ood_alarm_target": 0.01,
    }
    write_text(OUT / "config.json", json.dumps(config, indent=2))
    run_spec = {
        "inputs": [str(ISSUE27N / "summary.md"), str(FULL_MIRAI), str(FULL_LABELS)],
        "smoke_methods": ["LOW_GUARD_HistGB_Conservative", "LOW_GUARD_LR", "DeepSAD_center_baseline"],
        "smoke_seeds": [42, 43, 44],
        "formal_claim_from_smoke": False,
        "next_issue": "issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution_2026-05-27",
    }
    write_text(OUT / "run_spec.json", json.dumps(run_spec, indent=2))
    write_text(
        OUT / "command.txt",
        "\n".join(
            [
                "git branch --show-current; git status --short",
                "Get-Content issue27n/summary.md and issue27m/summary.md",
                "python runs/issue27o_full_mirai_protocol_reset_feature_mapping_and_formal_benchmark_spec_2026-05-27/run_issue27o_protocol_reset_spec.py",
            ]
        ),
    )
    manifest = []
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p), "file_name": p.name, "size_bytes": p.stat().st_size, "role": "issue27o_output"})
    write_csv(OUT / "manifest.csv", manifest)
    update_docs(primary_verdict)


if __name__ == "__main__":
    main()
