# Issue27b Next Experiment Decision

## Recommended Next Step

`issue27b_deployment_robustness_simulation_for_lowguard_top64_2026-05-22`

## Why This Now

Issue25c already handled strong baselines, while issue26a/26b showed formal temporal validation is blocked by metadata. The most direct remaining reviewer attack is deployment realism: support availability, support noise, OOD benign contamination, label delay, and update safety.

## Why Not Adapter Failure Archaeology First

Adapter upgrades reopen model-search space and weaken the claim boundary. Current LOW-GUARD-LR already survives strong baselines under the locked protocol. Upgrade work should wait until deployment robustness reveals a concrete failure mode.

## Why Not Data-Scale / Cross-Dataset Rebuild First

External validity remains important, but issue27a is about deployment protocol. Cross-dataset work can proceed later as issue27/28, ideally with a new clean protocol. It should not be mixed into this deployment audit.

## Required Inputs

- Frozen selected_source_rich_top64 features.
- Existing kcenter32 support provenance and attack train pools.
- ID/OOD train/cal/validation slices.
- Locked bins 5/6/7/8 and consistency settings for report-only evaluation.
- Contamination candidates that do not overlap final eval.

## Slurm Need

Likely no for LR-only simulations. Slurm is only needed if the matrix expands to many neural baselines or large stream replay.

## Expected Paper Evidence

- Label-budget sensitivity table.
- Support-noise robustness table.
- OOD benign contamination sensitivity table.
- Label-delay / earlier-support-later-eval boundary if metadata permits.
- Shadow-mode workload interpretation under the 1% alarm budget.
