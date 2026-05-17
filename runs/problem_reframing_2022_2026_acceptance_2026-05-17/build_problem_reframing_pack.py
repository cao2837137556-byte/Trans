from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "problem_reframing_2022_2026_acceptance_2026-05-17"
REPORT = ROOT.parent / "gpt deep" / "22年-26年问题定义报告.md"
HANDOFF = ROOT / "runs" / "mainline_docs" / "mainline_handoff.md"
EXPERIMENT_MAP = ROOT / "runs" / "mainline_docs" / "mainline_experiment_map.md"
GOVERNANCE = ROOT / "runs" / "mainline_docs" / "research_governance_v1.md"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def append_once(path: Path, heading: str, block: str) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    if heading in text:
        return False
    path.write_text(text.rstrip() + "\n\n" + block.strip() + "\n", encoding="utf-8")
    return True


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    if not REPORT.exists():
        raise FileNotFoundError(f"Missing deep research report: {REPORT}")

    report_text = REPORT.read_text(encoding="utf-8", errors="replace")
    report_snapshot = OUT / "received_22年-26年问题定义报告.md"
    # Store a repository-friendly snapshot while preserving the original hash in metadata.
    normalized_report_text = "\n".join(line.rstrip() for line in report_text.splitlines())
    write_text(report_snapshot, normalized_report_text)
    report_meta = {
        "source_report": str(REPORT),
        "source_report_exists": True,
        "source_report_size_bytes": REPORT.stat().st_size,
        "source_report_sha256": sha256(REPORT),
        "accepted_at": "2026-05-17",
        "key_phrases_observed": {
            "Problem B": "Problem B" in report_text,
            "LOW-GUARD": "LOW-GUARD" in report_text,
            "benign-OOD": "benign-OOD" in report_text or "良性 OOD" in report_text,
            "fixed OOD guard": "fixed OOD guard" in report_text,
        },
    }
    write_text(OUT / "source_report_metadata.json", json.dumps(report_meta, ensure_ascii=False, indent=2))

    governance = """
# Research Governance v1

Date: 2026-05-17

This document is the project-level governance layer for the few-shot / LOW-GUARD mainline. It supersedes executor-style experiment chaining. New experiments must be justified by the paper problem, target claim, and reviewer-risk defense before any run starts.

## 1. Problem-First Principle

The project is no longer framed as "few-shot LR improves dA / Transformer" or "LR replaces the original detector." The current problem framing is:

**Low-Alert Intrusion Detection under Benign-OOD Drift**, implemented as **deployment-stage guarded few-shot adaptation for low-alert intrusion detection under benign-OOD drift**.

Current locked route: **Problem B / balanced hybrid paper**. This route treats the paper as a problem-driven hybrid of protocol definition, guarded adaptation mechanism, deployment coexistence, and carefully bounded system evidence.

Any new experiment must first answer:

1. Which frontier problem does this experiment serve?
2. Which exact paper claim does it support?
3. Which reviewer attack does it defend against?
4. How will positive and negative outcomes be interpreted?
5. Should the result enter the main text, appendix, or negative-result archive?

If these cannot be answered, do not run the experiment.

## 2. Claim Gate

Before starting any experiment, write a short claim gate with:

| Gate item | Required answer |
|---|---|
| Target claim | The exact sentence or claim family the experiment can support. |
| Expected evidence | The metrics, provenance, tables, or plots required for the claim. |
| If positive | Paper role and claim strength. |
| If negative | Fallback interpretation and stop/pivot rule. |
| Paper location | Main text, appendix, discussion, or negative-result record. |
| Protocol lock | Split, seed, threshold, support pool, scaler, and no-final-eval-tuning statement. |

Passing the claim gate does not mean the experiment must be positive. It means the experiment is scientifically interpretable.

## 3. Reviewer Gate

Each experiment must defend at least one plausible reviewer attack, such as:

- Single dataset / single split.
- LR is too simple or just cost-sensitive logistic regression.
- Few-shot anomaly detection already exists.
- Threshold or calibration leakage.
- OOD setting is artificial.
- Review queue has low attack fraction.
- Scalar score fusion failed.
- Transformer hidden gives no stable gain.
- Detector-agnostic adaptation is overclaimed.
- Source-rich is not a stable main-gain representation.
- Second environment is missing or weak.

If an experiment does not defend a reviewer attack, it is probably not a priority.

## 4. Evidence Level

| Level | Definition | Current examples |
|---|---|---|
| A-level evidence | Can support a main claim if provenance is clean and wording is bounded. | low-OOD collapse; fixed OOD guard; original100 fixed guard / LOW-GUARD-minimal on the primary split; support and threshold provenance. |
| B-level evidence | Supports auxiliary or system-context claims but should not carry the main claim alone. | source_rich useful but unstable; Transformer hidden integration feasible; mode-gated arbitration; bounded review as safety net. |
| C-level evidence | Negative, boundary, or appendix-only evidence. | scalar score fusion; hidden-only failure; source_rich as stable main gain; review queue as attack-rich detection source. |
| Missing evidence | Must be completed before high-level submission claims are safe. | formal harder holdout; second environment; few-shot anomaly baselines; OOD budget sensitivity; LOW-GUARD shot sensitivity; modern unsupervised baselines; runtime/efficiency; threshold transfer. |

## 5. Stop Rule

If a line produces two consecutive rounds of weak positive, unstable, or non-main-driver evidence, stop treating it as a main route.

Current stop rules:

- Do not continue source_rich as the main gain route. It is a useful but unstable representation signal.
- Do not continue Transformer hidden as the main gain route until a stronger representation or formal holdout result justifies it.
- Do not optimize review queue as a new detection contribution. It is a safety net, not a confirmed attack pool.
- Do not pursue complex adapter upgrades before harder-holdout and baseline evidence are addressed.
- Do not continue scalar score fusion as a main route after dA and Transformer score-level fusion failed to provide stable added value.

## 6. Naming Rule

Internal planning can retain "GDA" as a shorthand for guarded/deviation-style adapter directions. Paper writing should prefer:

- **LOW-GUARD**
- **LOW-GUARD-minimal**
- **Deployment-stage guarded adaptation**

Current implementation name:

**LOW-GUARD-minimal = original100 representation + fixed OOD-benign guard + few-shot LR adapter.**

Avoid naming that implies a complete neural GDA, a detector-agnostic proof, or a replacement for base detectors.

## 7. System Role Rule

Base detectors, including dA and Transformer, remain:

- cold-start detectors,
- ordinary anomaly models,
- background monitors,
- review evidence providers.

LOW-GUARD-minimal activates only after low-OOD operating-point collapse and a small set of high-purity confirmed attack supports are available. It controls high-priority alerting in adaptation mode. Base-high / LOW-GUARD-low samples enter bounded review; they are not high-priority alerts and not discarded.

The review queue is a safety net, not a confirmed attack pool.
"""
    write_text(GOVERNANCE, governance)

    handoff_heading = "### 2026-05-17 Strategy Update: Problem-Driven Reframing after 2022–2026 Frontier Survey"
    handoff_block = f"""
{handoff_heading}

Source report received and accepted:

- `D:\\study\\paper\\anomaly_detection\\paper04\\worktrees\\gpt deep\\22年-26年问题定义报告.md`
- SHA-256: `{report_meta['source_report_sha256']}`

Main framing is now changed from **few-shot LR repair** to **low-alert IDS under benign-OOD drift**. The recommended paper route is **Problem B / balanced hybrid paper**: problem definition + deployment-stage guarded adaptation + bounded coexistence with base detectors.

Current method naming:

- Preferred paper name: `LOW-GUARD` / `LOW-GUARD-minimal`.
- Internal shorthand `GDA` may remain for later guarded/deviation adapter ideas, but the current paper should not imply full neural GDA has been completed.
- Current stable implementation: `original100 representation + fixed OOD-benign guard + few-shot LR adapter`.

Current strongest evidence:

- Ordinary sanity checks show dA / Transformer are not useless cold-start detectors.
- Low-OOD collapse shows deployment mismatch: ordinary ranking quality does not guarantee low-alert attack detection under benign-OOD drift.
- Scalar score fusion is negative / not a main route.
- Fixed OOD guard is positive and currently the strongest mechanism.
- LOW-GUARD-minimal high-priority channel is positive on the current primary split.
- Mode-gated arbitration and bounded review define system coexistence with base detectors.
- Review queue is a safety net only, not a confirmed attack pool.

Current missing evidence:

- Formal harder holdout.
- Second environment / external dataset.
- Few-shot anomaly baselines such as DevNet-like / Deep SAD-like / RoSAS-like comparisons.
- OOD budget sensitivity.
- LOW-GUARD shot sensitivity.
- Modern unsupervised baselines.
- Efficiency / runtime.
- Calibration / threshold transfer.

Immediate next decision should use issue16 results to choose among:

- issue16b formal harder holdout,
- baseline recovery,
- second environment plan,
- or stop/pivot.
"""
    handoff_updated = append_once(HANDOFF, handoff_heading, handoff_block)

    map_heading = "## 6. Problem-Driven Reframing and Evidence Roadmap"
    map_block = f"""
{map_heading}

Date: 2026-05-17

This section records the post-survey reframing from few-shot LR repair to **Low-Alert Intrusion Detection under Benign-OOD Drift**. The current recommended route is **Problem B / balanced hybrid paper**.

### 6.1 New Evidence Map

| Evidence level | Items | Paper role |
|---|---|---|
| A-level | low-OOD collapse; fixed OOD guard; original100 fixed guard / LOW-GUARD-minimal; clean support and threshold provenance | Can support main claims if harder-holdout and baseline gaps are handled. |
| B-level | source_rich useful but unstable; Transformer hidden integration feasible; mode-gated arbitration as deployment policy; bounded review as safety net | Auxiliary and system-context evidence. |
| C-level / negative | scalar score fusion; hidden-only failure; source_rich as stable main gain | Boundary evidence and appendix / negative-result record. |
| Missing | formal harder holdout; second environment; DevNet / Deep SAD / RoSAS-like baselines; OOD target sensitivity; shot sensitivity; runtime / efficiency; threshold transfer | Must be addressed before strong submission claims. |

### 6.2 Experiment Priority

| Priority | Experiments | Purpose |
|---|---|---|
| S-level | formal harder holdout validation; few-shot anomaly baseline comparison; OOD target sensitivity 0.5 / 1 / 2; shot sensitivity 8 / 16 / 32 / 64; threshold/provenance audit preserved | Defend the main problem definition and prevent reviewer collapse into "cost-sensitive LR on one split." |
| A-level | second environment pilot; modern unsupervised baselines; efficiency / runtime; calibration transfer | Strengthen external validity and deployment credibility. |
| B-level | adapter upgrade such as margin-GDA / deviation-GDA / prototype-GDA; Transformer hidden improvement; explainability / feature attribution | Only after S-level gaps are addressed. |
| C-level | further source_rich tinkering as main route; large neural model upgrade before generalization evidence; more score-level fusion | Do not prioritize as mainline. |

### 6.3 Current Stop Rule

- Do not continue source_rich as the main route.
- Do not continue Transformer hidden as the main route.
- Do not optimize review queue as an added attack-detection contribution.
- Do not perform complex adapter upgrades before harder-holdout and baseline recovery.
- Do not reopen score-level fusion unless a new, pre-registered reason exists.

### 6.4 Current Naming

Use `LOW-GUARD-minimal` for the current implementation:

`original100 representation + fixed OOD-benign guard + few-shot LR adapter`.

Avoid writing that full GDA, detector-agnostic adaptation, source_rich superiority, or Transformer-hidden improvement has already been proven.
"""
    map_updated = append_once(EXPERIMENT_MAP, map_heading, map_block)

    summary = """
# Problem Reframing Acceptance Summary

## 1. 接收结论

`22年-26年问题定义报告.md` 已读取并接收为当前科研总控升级依据。本轮不跑实验、不训练模型、不改论文主稿、不改历史实验数字。

## 2. 新问题定义

当前主问题重构为：

**Low-Alert Intrusion Detection under Benign-OOD Drift**

更具体的论文表述为：

**Deployment-stage guarded few-shot adaptation for low-alert intrusion detection under benign-OOD drift.**

## 3. 新方法命名

推荐论文命名：

- `LOW-GUARD`
- `LOW-GUARD-minimal`
- `Deployment-stage guarded adaptation`

当前实现：

`LOW-GUARD-minimal = original100 representation + fixed OOD-benign guard + few-shot LR adapter`.

`GDA` 可以继续作为内部方法演化术语，但不应在论文中暗示 full neural GDA 已完成。

## 4. 当前最强证据

- ordinary sanity 表明 dA / Transformer 不是无效模型。
- low-OOD collapse 表明问题来自部署工作点与 benign-OOD drift，而不是 base detector 普通能力缺失。
- scalar score fusion 是负结果，不应继续作为主路线。
- fixed OOD guard 是当前最稳机制。
- original100 fixed guard / LOW-GUARD-minimal 是当前最稳主方法。
- mode-gated arbitration 与 bounded review 支撑 base detector 和 LOW-GUARD 共存。
- review queue 是 safety net，不是 confirmed attack pool。

## 5. 当前最大风险

- 单数据集 / 单 split 泛化不足。
- LR 太简单，容易被压成 cost-sensitive LR。
- few-shot anomaly detection 已有，必须做同协议 baseline。
- review queue attack fraction 低，不能写成新增检出贡献。
- OOD 设置可能被质疑人为。
- detector-agnostic 证据不足。
- second environment 缺失或不稳。

## 6. 下一步

下一步必须由 issue16 结果决定：优先考虑 issue16b formal harder-holdout fixed-guard validation；同时规划 few-shot anomaly baseline comparison。不要在 harder-holdout / baseline 之前继续复杂 adapter upgrade。
"""
    write_text(OUT / "summary.md", summary)

    problem_candidates = """
# Problem Definition Candidates

## Problem A: Conservative

Problem A frames the paper as a measurement/protocol paper: ordinary IDS benchmark metrics do not reliably reflect low-alert deployment under benign-OOD drift, and fixed-guard minimal adaptation is a strong baseline.

Why not choose A as the main route:

- It is safe but may look method-light.
- It risks becoming a protocol paper with a simple baseline.
- It does not fully use the current system evidence around activation and arbitration.

## Problem B: Balanced

Problem B frames the paper as a hybrid contribution:

**Low-alert intrusion detection under benign-OOD drift, with deployment-stage guarded few-shot adaptation and bounded coexistence with base detectors.**

Why choose B:

- It matches the strongest current evidence.
- It makes LOW-GUARD-minimal a system/mechanism contribution rather than an LR replacement claim.
- It can absorb negative score-fusion, unstable source_rich, and bounded review as honest system boundaries.
- It identifies clear missing evidence: harder holdout and few-shot anomaly baselines.

Recommended status: **current main route**.

## Problem C: Ambitious

Problem C frames the paper as a universal detector-agnostic adaptive IDS framework.

Why not choose C now:

- Detector-agnostic evidence is not complete.
- Transformer hidden is feasible but not a stable improvement source.
- dA latent / multi-detector representation success is missing.
- It would require second environment, adapter upgrades, and broader baselines before the claim is safe.

Problem C can remain a future direction after Problem B is defensible.
"""
    write_text(OUT / "problem_definition_candidates.md", problem_candidates)

    claim_boundary = """
# Paper Claim Boundary

## Allowed Claims

- LOW-GUARD-minimal is a deployment-stage guarded adaptation mechanism.
- Fixed OOD guard is currently validated under the current low-OOD protocol.
- Base detector remains necessary for cold-start and bounded review safety net.
- Review is a safety net, not confirmed attack detection.
- Current system requires harder-holdout and second-environment validation.
- Scalar score fusion did not provide stable added value under the current protocol.
- source_rich and Transformer hidden are useful diagnostic or integration signals, but not the stable main gain.

## Forbidden Claims

- Full GDA completed.
- Detector-agnostic adaptation proven.
- Transformer hidden improves reliably.
- source_rich is stable main gain.
- Review queue is attack-rich or confirmed attack detection.
- CCF-A / A-zone readiness achieved.
- GDA or LOW-GUARD replaces the base detector.
- OOD weight=2 is globally optimal.
- Current evidence proves external validity.
"""
    write_text(OUT / "paper_claim_boundary.md", claim_boundary)

    priority_rows = [
        {
            "priority": "S",
            "experiment": "formal harder holdout validation",
            "purpose": "Test whether LOW-GUARD-minimal survives harder cross-window evaluation.",
            "target_reviewer_attack": "single split / cherry-picked primary split",
            "required_inputs": "v7.4 hard-holdout features, labels, support/eval manifests",
            "output_files": "method_comparison_summary.csv; support_id_provenance.csv; threshold_provenance.csv",
            "positive_interpretation": "Mechanism transfers to a harder holdout under fixed config.",
            "negative_interpretation": "Current method is primary-split limited; keep as limitation or pivot to protocol paper.",
            "stopping_rule": "If fixed guard fails on two pre-registered holdouts, stop adapter upgrade and analyze failure.",
        },
        {
            "priority": "S",
            "experiment": "few-shot anomaly baseline comparison",
            "purpose": "Defend against existing DevNet / Deep SAD / RoSAS-like few-shot anomaly methods.",
            "target_reviewer_attack": "few-shot anomaly detection already exists",
            "required_inputs": "same low-OOD split, same supports, same threshold protocol",
            "output_files": "baseline_comparison.csv; protocol.md; threshold_provenance.csv",
            "positive_interpretation": "LOW-GUARD problem/protocol and fixed guard are competitive under fair baselines.",
            "negative_interpretation": "Reframe as problem/protocol contribution or adopt stronger baseline as implementation.",
            "stopping_rule": "If baselines dominate under clean protocol, do not claim method superiority.",
        },
        {
            "priority": "S",
            "experiment": "OOD target sensitivity 0.5 / 1 / 2",
            "purpose": "Show the mechanism is not tuned only to 1 percent OOD alarm.",
            "target_reviewer_attack": "OOD budget is arbitrary",
            "required_inputs": "current fixed-config score/provenance or rerun with pre-registered budgets",
            "output_files": "ood_budget_sensitivity.csv; figures; summary.md",
            "positive_interpretation": "LOW-GUARD degrades smoothly across operating budgets.",
            "negative_interpretation": "Claim only applies to the 1 percent low-alert point.",
            "stopping_rule": "If only one budget works, do not broaden operating-region claim.",
        },
        {
            "priority": "S",
            "experiment": "shot sensitivity 8 / 16 / 32 / 64",
            "purpose": "Clarify label-budget boundary for LOW-GUARD-minimal.",
            "target_reviewer_attack": "chosen support budget is arbitrary",
            "required_inputs": "same split, deterministic support sampling, full provenance",
            "output_files": "shot_sensitivity_table.csv; seed_level_results.csv; support_id_provenance.csv",
            "positive_interpretation": "Recovery is not tied to a single lucky positive budget.",
            "negative_interpretation": "Method requires a narrower label-budget condition.",
            "stopping_rule": "If low budgets fail, report boundary; do not chase support choices.",
        },
        {
            "priority": "S",
            "experiment": "threshold/provenance audit preserved",
            "purpose": "Keep leakage defense intact for every new experiment.",
            "target_reviewer_attack": "threshold or support leakage",
            "required_inputs": "split manifest, support IDs, threshold source records",
            "output_files": "support_id_provenance.csv; threshold_provenance.csv; audit_summary.md",
            "positive_interpretation": "Protocol is auditable.",
            "negative_interpretation": "Do not use the result as paper evidence.",
            "stopping_rule": "Any leakage or missing provenance blocks claim use.",
        },
        {
            "priority": "A",
            "experiment": "second environment pilot",
            "purpose": "Probe external validity beyond the current capture.",
            "target_reviewer_attack": "single dataset",
            "required_inputs": "external role manifest, comparable features, row IDs",
            "output_files": "second_env_protocol.md; result_summary.csv; risk_register.csv",
            "positive_interpretation": "External pilot supports generality cautiously.",
            "negative_interpretation": "External validity remains limitation; analyze mismatch.",
            "stopping_rule": "If role manifest is dirty, stop before model runs.",
        },
        {
            "priority": "A",
            "experiment": "modern unsupervised baselines",
            "purpose": "Show low-OOD collapse is not a weak dA-only artifact.",
            "target_reviewer_attack": "old baseline",
            "required_inputs": "same low-OOD split and threshold protocol",
            "output_files": "modern_baseline_table.csv; cost_summary.csv",
            "positive_interpretation": "Problem persists under stronger base detectors.",
            "negative_interpretation": "If a baseline solves it, reposition LOW-GUARD as deployment adaptation baseline.",
            "stopping_rule": "Do not expand baseline zoo after two strong representative baselines.",
        },
        {
            "priority": "B",
            "experiment": "adapter upgrade",
            "purpose": "Test margin-GDA / deviation-GDA / prototype-GDA only after S-level evidence.",
            "target_reviewer_attack": "LR too simple",
            "required_inputs": "formal harder-holdout and baseline results",
            "output_files": "adapter_ablation.csv; claim_boundary.md",
            "positive_interpretation": "A stronger adapter improves beyond LOW-GUARD-minimal.",
            "negative_interpretation": "Keep LOW-GUARD-minimal as the clean baseline.",
            "stopping_rule": "If no stable gain over fixed guard in two runs, stop.",
        },
        {
            "priority": "C",
            "experiment": "more score-level fusion",
            "purpose": "Not recommended unless a new pre-registered reason exists.",
            "target_reviewer_attack": "none currently",
            "required_inputs": "new score source with explicit hypothesis",
            "output_files": "negative_record.md if attempted",
            "positive_interpretation": "Only auxiliary unless it beats fixed guard.",
            "negative_interpretation": "Confirms scalar score compression is insufficient.",
            "stopping_rule": "Default stop.",
        },
    ]
    write_csv(OUT / "experiment_priority_plan.csv", priority_rows)

    plan_md = ["# Experiment Priority Plan", "", "Every future experiment must pass the claim gate and reviewer gate before execution.", ""]
    for row in priority_rows:
        plan_md.extend(
            [
                f"## {row['priority']}-level: {row['experiment']}",
                "",
                f"- Purpose: {row['purpose']}",
                f"- Target reviewer attack: {row['target_reviewer_attack']}",
                f"- Required inputs: {row['required_inputs']}",
                f"- Output files: {row['output_files']}",
                f"- Positive interpretation: {row['positive_interpretation']}",
                f"- Negative interpretation: {row['negative_interpretation']}",
                f"- Stopping rule: {row['stopping_rule']}",
                "",
            ]
        )
    write_text(OUT / "experiment_priority_plan.md", "\n".join(plan_md))

    codex_role = """
# Codex Research Role

Future Codex work on this project should treat Codex as a research collaborator, not only an executor.

## Required Behavior

- Preserve provenance before optimizing metrics.
- Flag overclaim risk before writing or running.
- Produce a claim boundary for each experiment.
- Stop if evidence is insufficient or protocol gates fail.
- Do not optimize for pretty numbers over clean protocol.
- Ask which reviewer attack an experiment defends before running it.
- Separate main-text evidence, appendix evidence, and negative/boundary records.

## Pre-Experiment Checklist

1. Target problem.
2. Target claim.
3. Reviewer attack.
4. Positive interpretation.
5. Negative interpretation.
6. Paper location.
7. Protocol lock.
8. Stop rule.

If the checklist is incomplete, pause and produce a feasibility or design pack instead of running.
"""
    write_text(OUT / "codex_research_role.md", codex_role)

    doc_report = f"""
# Document Update Report

## Modified files

- `runs/mainline_docs/research_governance_v1.md` created/updated.
- `runs/mainline_docs/mainline_handoff.md` contains the 2026-05-17 strategy update: True.
- `runs/mainline_docs/mainline_experiment_map.md` contains the problem-driven roadmap: True.
- `runs/mainline_docs/mainline_handoff.md` appended during this script invocation: {handoff_updated}.
- `runs/mainline_docs/mainline_experiment_map.md` appended during this script invocation: {map_updated}.

## New files

- `runs/problem_reframing_2022_2026_acceptance_2026-05-17/summary.md`
- `runs/problem_reframing_2022_2026_acceptance_2026-05-17/problem_definition_candidates.md`
- `runs/problem_reframing_2022_2026_acceptance_2026-05-17/paper_claim_boundary.md`
- `runs/problem_reframing_2022_2026_acceptance_2026-05-17/experiment_priority_plan.md`
- `runs/problem_reframing_2022_2026_acceptance_2026-05-17/experiment_priority_plan.csv`
- `runs/problem_reframing_2022_2026_acceptance_2026-05-17/codex_research_role.md`
- `runs/problem_reframing_2022_2026_acceptance_2026-05-17/source_report_metadata.json`
- `runs/problem_reframing_2022_2026_acceptance_2026-05-17/received_22年-26年问题定义报告.md`

## Safety

- Manuscript modified: False.
- Experimental numbers modified: False.
- Models trained: False.
- Historical negative results deleted: False.
- Full GDA claim introduced: False.
- Detector-agnostic claim introduced: False.
- Commit/push status: generated for staging in this turn; final assistant response records the actual commit and push.

## Current next step

Current next step awaits issue16 result review and should likely choose issue16b formal harder-holdout validation or baseline recovery before any complex adapter upgrade.
"""
    write_text(OUT / "doc_update_report.md", doc_report)

    manifest_rows = []
    generated = [
        report_snapshot,
        OUT / "summary.md",
        OUT / "problem_definition_candidates.md",
        OUT / "paper_claim_boundary.md",
        OUT / "experiment_priority_plan.md",
        OUT / "experiment_priority_plan.csv",
        OUT / "codex_research_role.md",
        OUT / "source_report_metadata.json",
        OUT / "doc_update_report.md",
        GOVERNANCE,
        HANDOFF,
        EXPERIMENT_MAP,
    ]
    for path in generated:
        manifest_rows.append(
            {
                "asset_name": path.name,
                "file_path": str(path),
                "asset_type": "project_governance" if path == GOVERNANCE else "acceptance_pack",
                "role": "problem-driven reframing governance",
                "modified_or_created": "yes",
            }
        )
    write_csv(OUT / "manifest.csv", manifest_rows)

    # Refresh doc report and manifest after manifest exists.
    manifest_rows.append(
        {
            "asset_name": "manifest.csv",
            "file_path": str(OUT / "manifest.csv"),
            "asset_type": "acceptance_pack",
            "role": "asset manifest",
            "modified_or_created": "yes",
        }
    )
    write_csv(OUT / "manifest.csv", manifest_rows)

    status = {
        "report_read": True,
        "report_path": str(REPORT),
        "research_governance_created": True,
        "mainline_handoff_updated": handoff_updated,
        "mainline_experiment_map_updated": map_updated,
        "manuscript_modified": False,
        "experimental_numbers_modified": False,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    write_text(OUT / "acceptance_status.json", json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
