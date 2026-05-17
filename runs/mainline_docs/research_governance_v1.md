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
