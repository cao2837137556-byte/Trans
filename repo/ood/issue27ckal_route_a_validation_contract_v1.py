"""issue27ckal: strict Route-A external validation contract v1.

This is a planning/audit artifact generator, not a detector.  It freezes the
scientific contract for the next external validation stage while the ToN-IoT
Bro/Zeek and ground-truth archives are being downloaded.

Core rule:

    Gotham training data -> Gotham-selected frontend/model
    ToN-IoT raw/Bro data -> report-only external validation

No ToN-IoT report rows may be used for fitting, thresholding, feature
selection, imputation policy, representation selection, or model choice.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ISSUE = "issue27ckal_route_a_validation_contract_v1_2026-07-09"
WORKTREE = Path(__file__).resolve().parents[2]
PAPER04 = WORKTREE.parent.parent
OUT = WORKTREE / "runs" / ISSUE

RAW_ROUTE_A_DIR = PAPER04 / "datasets" / "external" / "ton_iot_raw_network" / "raw"
EXTRACTED_ROUTE_A_DIR = PAPER04 / "datasets" / "external" / "ton_iot_raw_network" / "extracted"
INTAKE_ISSUE = "issue27ckak_toniot_route_a_raw_intake_v1_2026-07-09"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, obj: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    ensure_dir(path.parent)
    if fieldnames is None:
        keys: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


FRONTIER_PRINCIPLES: list[dict[str, str]] = [
    {
        "principle_id": "P1_realistic_distribution_shift",
        "borrowed_from": "WILDS benchmark",
        "source_url": "https://arxiv.org/abs/2012.07421",
        "what_we_borrow": "Evaluate domain/subpopulation shifts explicitly instead of relying on one iid split.",
        "paper04_translation": "Report Gotham-internal Level-1, leave-family/source Level-2, and ToN-IoT external Level-3 separately.",
        "not_allowed_interpretation": "Do not claim cross-dataset robustness from Gotham-only sealed results.",
    },
    {
        "principle_id": "P2_worst_group_not_mean_only",
        "borrowed_from": "GroupDRO / group-shift robust learning",
        "source_url": "https://arxiv.org/abs/1911.08731",
        "what_we_borrow": "Mean metrics can hide atypical-group collapse; worst-group evidence must be visible.",
        "paper04_translation": "Every formal run reports attack family, benign/source group, and worst-group hard/review rates.",
        "not_allowed_interpretation": "Do not promote a model that wins only by average while failing rare attack families.",
    },
    {
        "principle_id": "P3_domain_invariant_representation",
        "borrowed_from": "DANN / domain-adversarial representation learning",
        "source_url": "https://arxiv.org/abs/1505.07818",
        "what_we_borrow": "Representations should preserve task signal while reducing domain/source discriminability.",
        "paper04_translation": "Neural-head stage may add source/device/domain adversary, but only after clean splits and source groups are audited.",
        "not_allowed_interpretation": "Do not train DANN with external report labels or sealed rows.",
    },
    {
        "principle_id": "P4_integrated_review_cost",
        "borrowed_from": "SelectiveNet / selective prediction",
        "source_url": "https://arxiv.org/abs/1901.09192",
        "what_we_borrow": "Reject/review should be part of the decision objective, not only a post-hoc confidence threshold.",
        "paper04_translation": "Review rate is a primary cost metric with separate benign/attack review reporting.",
        "not_allowed_interpretation": "Do not call OOD hard reduction a win if review explodes.",
    },
    {
        "principle_id": "P5_embedding_separation",
        "borrowed_from": "Supervised Contrastive Learning",
        "source_url": "https://arxiv.org/abs/2004.11362",
        "what_we_borrow": "Build a representation map that pulls matching mechanisms together and pushes conflicting mechanisms apart.",
        "paper04_translation": "Later neural map tests can compare CE-only vs CE+SupCon on legal fit roles only.",
        "not_allowed_interpretation": "Do not use support/query/report rows interchangeably to make prettier embeddings.",
    },
    {
        "principle_id": "P6_flow_interaction_frontend",
        "borrowed_from": "HyperVision flow interaction graph",
        "source_url": "https://arxiv.org/abs/2301.13686",
        "what_we_borrow": "Unknown malicious traffic can be expressed by interaction structure, sparsity, connectivity, and statistics.",
        "paper04_translation": "Bro/Zeek route should extract source-target-port interaction and time-window graph/context evidence, not just single-flow scalars.",
        "not_allowed_interpretation": "Do not copy GPL code into the paper mainline; borrow the design principle and cite separately.",
    },
    {
        "principle_id": "P7_zeek_transaction_logs",
        "borrowed_from": "Zeek documentation",
        "source_url": "https://docs.zeek.org/en/lts/monitoring.html",
        "what_we_borrow": "Zeek/Bro logs summarize protocol transactions and extracted network-security monitoring data.",
        "paper04_translation": "Network_dataset_Bro is a valid strict Route-A first target if it contains conn/dns/http/ssl/tls-style logs with auditable timestamps.",
        "not_allowed_interpretation": "Do not treat arbitrary processed Train_Test CSV as equivalent to Bro/Zeek raw logs.",
    },
    {
        "principle_id": "P8_toniot_raw_network_basis",
        "borrowed_from": "UNSW ToN-IoT official dataset page",
        "source_url": "https://research.unsw.edu.au/projects/toniot-datasets",
        "what_we_borrow": "ToN-IoT network data includes PCAP, log files, and Zeek/Bro CSV.",
        "paper04_translation": "Download Network_dataset_Bro plus SecurityEvents_Network as the minimum strict raw/log external-validation package.",
        "not_allowed_interpretation": "Do not use processed or train-test versions as the main Route-A proof.",
    },
]


DATA_USE_LEDGER: list[dict[str, Any]] = [
    {
        "asset": "Gotham legal fit roles",
        "stage": "fit",
        "allowed_use": "frontend normalization, feature policy selection, model fitting",
        "forbidden_use": "none if role-legal and already frozen",
        "notes": "All active model choice must be explainable from Gotham legal development roles.",
    },
    {
        "asset": "Gotham select/support-val roles",
        "stage": "select",
        "allowed_use": "threshold/model selection where the current protocol explicitly permits it",
        "forbidden_use": "final report or sealed rows as hidden validation",
        "notes": "Selection trace must be saved before external ToN-IoT report.",
    },
    {
        "asset": "Gotham sealed/final report roles",
        "stage": "report",
        "allowed_use": "final reporting only",
        "forbidden_use": "fit, feature selection, cleaning-policy tuning, thresholding",
        "notes": "Preserves internal Level-1 evidence credibility.",
    },
    {
        "asset": "ToN-IoT Network_dataset_Bro",
        "stage": "external_report_zero_shot",
        "allowed_use": "schema audit and report-only external evaluation after frontend parity is frozen",
        "forbidden_use": "fit, thresholding, model choice, frontend selection",
        "notes": "May be used for loader engineering only if no labels/metrics drive method choices.",
    },
    {
        "asset": "ToN-IoT SecurityEvents_Network",
        "stage": "external_report_zero_shot",
        "allowed_use": "label/time alignment audit and final metric labeling",
        "forbidden_use": "training, cleaning-policy tuning, thresholding",
        "notes": "Groundtruth labels audit the report; they do not steer the detector.",
    },
    {
        "asset": "ToN-IoT explicit few-shot support if later opened",
        "stage": "external_fewshot_adaptation_optional",
        "allowed_use": "only if a future issue freezes support/calibration roles before looking at report metrics",
        "forbidden_use": "retroactive selection from poor zero-shot errors",
        "notes": "Few-shot adaptation is a separate experiment, not the zero-shot claim.",
    },
]


EXPERIMENT_MATRIX: list[dict[str, Any]] = [
    {
        "exp_id": "A0_intake_only",
        "purpose": "Prove the downloaded external assets are raw/log suitable and auditable.",
        "train_data": "none",
        "select_data": "none",
        "test_data": "none",
        "frontend": "none",
        "head": "none",
        "required_before": "Network_dataset_Bro.zip and SecurityEvents_Network archive complete",
        "success_metrics": "route_a_gate passes schema/time/label audit",
        "stop_if": "only processed CSV or duplicated Flow ID without stable timestamp/key",
        "claim_level": "data-readiness only",
    },
    {
        "exp_id": "A1_frontend_parity_smoke",
        "purpose": "Check whether the same Bro/Zeek-style frontend schema can be produced for Gotham and ToN-IoT.",
        "train_data": "Gotham legal fit only for scaler policy if needed",
        "select_data": "Gotham legal select only",
        "test_data": "ToN-IoT report-only rows, labels hidden from feature construction",
        "frontend": "Bro/Zeek conn/log parser + interaction/context features",
        "head": "none or frozen diagnostic scorer only",
        "required_before": "A0 pass",
        "success_metrics": "same column contract, no future-label context, non-finite policy fit-only",
        "stop_if": "ToN schema cannot map to Gotham schema without target-specific features",
        "claim_level": "frontend readiness, not model performance",
    },
    {
        "exp_id": "A2_zero_shot_external_report",
        "purpose": "Strict external validation: Gotham-trained model evaluates ToN-IoT without target fitting.",
        "train_data": "Gotham legal fit/support only",
        "select_data": "Gotham legal select/support-val only",
        "test_data": "ToN-IoT report-only",
        "frontend": "frozen A1 frontend",
        "head": "frozen Gotham-selected baseline head and frozen neural candidate if already selected on Gotham",
        "required_before": "A1 pass and Gotham selection frozen",
        "success_metrics": "ToN benign hard attack false alarm, ToN attack hard detection, ToN review, per-family/worst-group",
        "stop_if": "any ToN report metric changes model/threshold selection",
        "claim_level": "Level-3 zero-shot external evidence",
    },
    {
        "exp_id": "A3_external_fewshot_adaptation_optional",
        "purpose": "Measure recoverability when a small, pre-frozen target support/calib set is allowed.",
        "train_data": "Gotham legal fit + frozen ToN support/calib only",
        "select_data": "frozen ToN select/calib only if preregistered",
        "test_data": "remaining ToN sealed/report-only",
        "frontend": "same A1 frontend; no target-specific schema",
        "head": "adaptation head with explicit budget",
        "required_before": "A2 reported; few-shot roles frozen before seeing few-shot test metrics",
        "success_metrics": "recovery in attack hard without benign hard/review explosion",
        "stop_if": "support is mined from failures or report rows",
        "claim_level": "open-world update ability, not zero-shot generalization",
    },
    {
        "exp_id": "A4_neural_invariant_selective_head",
        "purpose": "Test the intended method innovation: representation + source/domain invariance + integrated review cost.",
        "train_data": "Gotham legal fit roles only; optional ToN support only in A3 variant",
        "select_data": "Gotham legal select roles only for zero-shot version",
        "test_data": "Gotham sealed and ToN report-only",
        "frontend": "best frozen Bro/interaction frontend plus selected Gotham-compatible features",
        "head": "CE baseline vs CE+SupCon vs CE+domain-adversary vs selective-head ablations",
        "required_before": "A2 proves external loader and baseline behavior are measurable",
        "success_metrics": "attack hard high, benign hard low, review bounded, source/device probe lower, worst-group improved",
        "stop_if": "improvement is only review inflation or target leakage",
        "claim_level": "method contribution candidate",
    },
]


BRO_ZEEK_AUDIT: list[dict[str, str]] = [
    {
        "check_id": "Z1_archive_integrity",
        "question": "Are Network_dataset_Bro and SecurityEvents_Network complete non-crdownload archives?",
        "pass_condition": "archives have stable size and full or skip-large hash record",
        "failure_action": "wait/download again; do not extract partial archives",
    },
    {
        "check_id": "Z2_expected_logs",
        "question": "Does the Bro archive contain conn.log or conn-like CSV/log files?",
        "pass_condition": "conn fields include ts/time, uid or stable key, id.orig_h/src, id.resp_h/dst, proto, service, duration, bytes/packets/state where available",
        "failure_action": "inspect alternate network logs; if none, Route A blocked",
    },
    {
        "check_id": "Z3_time_semantics",
        "question": "Can flow/log timestamps be ordered without trusting file order?",
        "pass_condition": "timestamp parse rate high and monotonic/order policy documented",
        "failure_action": "sort by timestamp; if impossible, report as temporal-context blocker",
    },
    {
        "check_id": "Z4_groundtruth_alignment",
        "question": "Can SecurityEvents_Network align to Bro records by time window plus source/destination/protocol fields?",
        "pass_condition": "alignment keys and tolerance are preregistered before model scoring",
        "failure_action": "do not tune tolerance on final metrics; create alignment audit only",
    },
    {
        "check_id": "Z5_context_past_only",
        "question": "Do interaction/window features use only past/current records in timestamp order?",
        "pass_condition": "no future records and no groundtruth labels enter feature construction",
        "failure_action": "disable temporal context or redesign loader",
    },
    {
        "check_id": "Z6_identifier_policy",
        "question": "Are high-cardinality identifiers handled safely?",
        "pass_condition": "raw IPs/ports/uid not directly used as shortcut attack evidence; derived interaction counts may be used",
        "failure_action": "demote identifiers to grouping/audit only",
    },
    {
        "check_id": "Z7_sanitizer_policy",
        "question": "How are non-finite/missing/extreme values handled?",
        "pass_condition": "policy is fit on Gotham legal fit or fixed a priori; never fitted on ToN report rows",
        "failure_action": "record blocked until sanitizer source is legal",
    },
]


PAPER_EVIDENCE_REQUIREMENTS: list[dict[str, str]] = [
    {
        "evidence_id": "E1_internal_capability",
        "reviewer_question": "Does the detector work on the main dataset without hiding failures in review?",
        "required_table": "Gotham role summary: ID benign, OOD, support/future/sealed attack hard and review rates",
        "minimum_standard": "high attack hard, low OOD hard, bounded benign and attack review",
    },
    {
        "evidence_id": "E2_frontend_ablation",
        "reviewer_question": "Is the frontend designed for the task rather than blindly using Kitsune115?",
        "required_table": "raw115 vs CICFlow-style vs Bro/Zeek/interaction vs combined frontend",
        "minimum_standard": "clear explanation of which features support attack, context, or review/conflict",
    },
    {
        "evidence_id": "E3_head_ablation",
        "reviewer_question": "Is the neural/causal/selective head doing real work?",
        "required_table": "HistGB vs MLP/CE vs SupCon map vs domain-adversarial vs selective cost ablation",
        "minimum_standard": "improvement is not only threshold tuning or review inflation",
    },
    {
        "evidence_id": "E4_level2_generalization",
        "reviewer_question": "Does it survive internal drift and weak groups?",
        "required_table": "leave-family/source/device/worst-group stress",
        "minimum_standard": "worst-group and rare attack families are visible; collapse is honestly reported",
    },
    {
        "evidence_id": "E5_level3_external_zero_shot",
        "reviewer_question": "Is it just a Gotham memorizer?",
        "required_table": "Gotham train -> ToN-IoT report-only external test",
        "minimum_standard": "no target fitting; per-family hard/review/benign false alarm reported",
    },
    {
        "evidence_id": "E6_fewshot_recovery",
        "reviewer_question": "If zero-shot is hard, can the open-world update recover safely?",
        "required_table": "0-shot vs small support budget vs larger support budget with frozen target roles",
        "minimum_standard": "attack recovery without OOD hard/review explosion",
    },
    {
        "evidence_id": "E7_leakage_audit",
        "reviewer_question": "Did you tune on the test set?",
        "required_table": "role ledger, selection trace, sanitizer source, threshold source, model choice source",
        "minimum_standard": "all tuning decisions trace back to legal fit/select roles only",
    },
    {
        "evidence_id": "E8_runtime_deployability",
        "reviewer_question": "Can this run as a plausible IDS component?",
        "required_table": "feature extraction cost, model scoring latency, memory, review volume",
        "minimum_standard": "bounded review and clear online/offline mode claim",
    },
]


def build_contract_md() -> str:
    return f"""# issue27ckal Route-A validation contract

Generated: `{datetime.now(tz=timezone.utc).isoformat()}`

## Current decision

We keep the already downloaded/available processed flow CSVs as diagnostics, but
the formal external-validation line is now strict Route A:

```text
ToN-IoT Network_dataset_Bro / PCAP
-> same family of frontend code we control
-> Gotham-trained and Gotham-selected model
-> ToN-IoT report-only metrics
```

The immediate minimum package is:

```text
Raw_datasets/network_data/Network_dataset_Bro
+ SecurityEvents_GroundTruth_datasets/SecurityEvents_Network_datasets
```

The 56GB `Network_dataset_pcaps` package is useful later, but not required for
the first strict Bro/Zeek external-validation pass.

## Non-negotiable data rule

No ToN-IoT report/sealed row may affect:

```text
fit, scaler/imputer policy, feature selection, frontend choice,
thresholding, calibration, model choice, review policy, or stopping criteria
```

Engineering loader fixes are allowed only when they are label-free and recorded
before model scoring.  If a fix is driven by external report metrics, it becomes
a new dated experiment and cannot be backported into the already reported
zero-shot result.

## What we borrow from front-line work

We borrow principles, not copy systems blindly:

* WILDS: evaluate realistic domain/subpopulation shifts separately.
* GroupDRO: expose worst-group failure instead of hiding behind mean metrics.
* DANN: later neural maps may reduce source/device/domain shortcuts.
* SelectiveNet: review/reject is a trained cost, not a post-hoc garbage bin.
* SupCon: mechanism embeddings should separate attack/OOD structure.
* HyperVision: network interaction graph/context can reveal unknown attacks
  better than isolated single-flow scalars.
* Zeek/Bro: transaction logs are a valid raw/log frontend substrate.

## Output files

* `frontier_borrowed_principles.csv`
* `data_use_ledger.csv`
* `route_a_experiment_matrix.csv`
* `bro_zeek_loader_audit_checklist.csv`
* `paper_evidence_requirements.csv`
* `route_a_stop_rules.md`
"""


def build_stop_rules_md() -> str:
    return """# issue27ckal stop rules

Stop the Route-A formal line if any of these happen:

1. Only processed Train_Test/CICFlow/NetFlow CSVs are available.
2. The Bro/Zeek loader cannot recover stable timestamp and source/destination
   semantics.
3. External report labels are needed to choose features, thresholds, sanitizer
   policy, or model family.
4. OOD hard reduction is achieved mainly by moving benign/attack samples into
   review.
5. The same frontend schema cannot be run on Gotham and ToN-IoT.
6. Mean performance improves while rare attack family or worst-group collapses.
7. Few-shot adaptation is mixed into the zero-shot claim.

Allowed negative outcome:

If strict zero-shot external validation fails, record it as external-boundary
evidence and proceed to a separately frozen few-shot adaptation experiment.
Do not repair it retroactively with target-test information.
"""


def main() -> int:
    ensure_dir(OUT)
    write_csv(OUT / "frontier_borrowed_principles.csv", FRONTIER_PRINCIPLES)
    write_csv(OUT / "data_use_ledger.csv", DATA_USE_LEDGER)
    write_csv(OUT / "route_a_experiment_matrix.csv", EXPERIMENT_MATRIX)
    write_csv(OUT / "bro_zeek_loader_audit_checklist.csv", BRO_ZEEK_AUDIT)
    write_csv(OUT / "paper_evidence_requirements.csv", PAPER_EVIDENCE_REQUIREMENTS)
    write_text(OUT / "route_a_validation_contract.md", build_contract_md())
    write_text(OUT / "route_a_stop_rules.md", build_stop_rules_md())

    summary = {
        "issue": ISSUE,
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "raw_route_a_dir": str(RAW_ROUTE_A_DIR),
        "extracted_route_a_dir": str(EXTRACTED_ROUTE_A_DIR),
        "intake_issue": INTAKE_ISSUE,
        "frontier_principles": len(FRONTIER_PRINCIPLES),
        "data_use_ledger_rows": len(DATA_USE_LEDGER),
        "experiment_matrix_rows": len(EXPERIMENT_MATRIX),
        "bro_zeek_audit_rows": len(BRO_ZEEK_AUDIT),
        "paper_evidence_requirements": len(PAPER_EVIDENCE_REQUIREMENTS),
        "status": "contract_frozen_waiting_for_downloaded_bro_and_groundtruth_archives",
    }
    write_json(OUT / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
