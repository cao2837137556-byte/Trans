# Mainline Handoff

Updated: 2026-05-08
Workspace: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline`
Branch: `codex/exp-mainline`
Canonical path: `runs/mainline_docs/mainline_handoff.md`

Maintenance rule:
- Keep this as the single living mainline handoff.
- Append stable updates in time order inside this file.
- Do not create dated handoff copies for mainline.

## Scope

This file is the time-ordered handoff for the A-line main experiment only.

- Record only A-line mainline work.
- Record what was done, what the result was, what the current blocker is, and what should happen next.
- Exclude `frontend_f2_*` and any other branch-line exploration.
- Exclude merge and worktree management.

## Fixed Mainline Protocol

- Feature frontend: `original-frontend 100D`
- Main problem setting: stronger benign OOD under the formal frontend100 protocol
- Primary attack metric: Stage2 high-purity attack detection
- Required operating points:
  - `fixed_id_q99`
  - `naive_calibrated_budget5000_target1pct`
  - `det_floor_50pct_min_alarm`
- Rule: all scalers, thresholds, centers, covariance estimates, and calibration statistics must be fit only on ID benign data

## Current Status

- Latest framing note: see `2026-05-08 Strategy Update` below. The current candidate direction is base-detector-agnostic guarded few-shot adaptation, but this is a next-phase proposal, not a completed experiment or current paper claim.
- The project is no longer in "close the draft quickly" mode. It has been reclassified into the A-tier strengthening stage.
- Phase 1 is complete: problem definition, main pathology localization, main candidate screening, external baseline supplements, and one round of deployability diagnosis are already in place.
- The current A-line gap is no longer "find any Transformer win." The gap is to complete the evidence package that makes the mainline argument defensible at A-tier standard.

## Current Main Blockers

1. Modern tabular baseline evidence is not complete yet. `FT-Transformer` has only finished a local smoke and has not yet been promoted into a full formal comparison package.
2. Second-dataset or second-environment self-validation is still missing.
3. Adversarial robustness evaluation is still missing.
4. Deployability closure is incomplete. The ensemble candidate is useful evidence, but a clean single-model replacement has not been established.

## Current Next Step

- Continue the A-line baseline-strengthening package under the existing `original-frontend 100D` protocol.
- First priority is to convert the `FT-Transformer` smoke path into a formal A-line run with the standard tables and cost summary.
- If the FT line remains non-threatening after formalization, keep the scope tight and decide whether `RTDL-ResNet` is still necessary.

## Time Log

### 2026-05-22 (Issue26a Within-Dataset Temporal Feasibility Inventory)

What was done:
- Completed `runs/issue26a_within_dataset_temporal_validation_for_enhanced_lowguard_top64_2026-05-22/`.
- Scope was within-dataset temporal / data-scale feasibility and leakage audit only.
- No dA/Transformer training, no topK/support/adapter/threshold change, and no manuscript edit.
- Read issue25c strong baseline outputs, issue23 locked validation assets, issue22/22b discovery and non-regression summaries, and current mainline docs.

Result:
- Preflight passed for inventory.
- issue25c remains `strong_baseline_positive` for frozen Enhanced LOW-GUARD+ top64.
- Existing evidence was separated into:
  - `primary_lowood`: primary / non-regression evidence.
  - `holdout_bin_2`: hard-shift discovery evidence, not clean future proof.
  - `chrono_late_train_early_eval`: temporal-looking consistency evidence, but already involved in candidate confirmation.
  - locked bins `5/6/7/8`: valid same-dataset locked evidence from issue23 and issue25c, but not new temporal proof.
- No clean P0/P1 temporal candidate with low leakage risk was found.
- Best partial candidate is `chrono_early_train_late_eval`, but it overlaps issue23/25c locked eval bins `6/7/8` and needs purge/embargo plus metadata recovery before formal validation.
- Minimal new temporal validation was not run.

Judgment:
- issue26a strengthens evidence-chain hygiene, not the main temporal claim.
- It should be cited as feasibility / audit / planning evidence only.
- Do not write that issue26a proves temporal generalization or replaces second-environment validation.

Next:
- Unique next action: `issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22`.
- Recover raw timestamp / packet-order / attack-bin provenance, define a purged or embargoed future-window split, and only then decide whether formal issue26b validation can run.
- Keep second environment as later issue27, not this round's immediate next step.

### 2026-05-22 (Issue26b Split Metadata Recovery + Temporal Asset Build)

What was done:
- Completed `runs/issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22/`.
- Scope was metadata recovery, split provenance reconstruction, temporal asset candidate rebuild, and purge/embargo planning only.
- No formal temporal validation, no model training, no topK/support/adapter/threshold change, no second-environment reopening, and no manuscript edit.
- Scanned issue26a handoff assets, issue22/22b/23/25c provenance and locked-asset reports, issue18 row-level score persistence assets, and current mainline docs.

Result:
- Preflight passed for metadata recovery.
- Coarse attack-bin provenance was recovered for `primary_lowood`, `holdout_bin_2`, `chrono_late`, locked bins `5/6/7/8`, and the partial `chrono_early_train_late_eval` candidate.
- Support provenance remains clean at the inspected level: selected support rows are recorded as coming from attack train pools and not from attack eval / final OOD eval.
- Threshold provenance remains clean at the inspected level: thresholds use ID calibration + OOD validation, not final OOD / attack eval.
- Raw timestamp, packet-order, capture/session boundary, window_start/window_end, and bin-to-clock-time metadata were not recovered.
- No clean formal temporal candidate was found. `earlier-to-later` remains only a partial/planning candidate because eval bins `6/7/8` overlap issue23/25c locked evidence.
- A metadata-only split smoke was completed; it checked bin-definition wiring only and did not train models or select thresholds.

Judgment:
- issue26b improves evidence-chain hygiene and makes the temporal blocker explicit.
- It does not strengthen the temporal-generalization claim.
- Reusing issue23/25c locked bins must remain consistency or repeated-evidence analysis, not new temporal proof.

Next:
- Unique next action: `issue26c_temporal_metadata_recovery_followup_or_second_environment_feasibility`.
- First try to recover raw timestamp / packet-order / capture-level metadata or a genuinely unused future-window manifest.
- If that remains impossible, keep within-dataset formal temporal validation blocked and move to a carefully scoped issue27-level second-environment feasibility path rather than tuning the method.

### 2026-05-22 (Issue27a Deployment Feasibility + Guarded Training Protocol Audit)

What was done:
- Completed `runs/issue27a_deployment_feasibility_and_guarded_training_protocol_audit_2026-05-22/`.
- Scope was deployment-facing protocol audit and reviewer-defense planning only.
- No model training, no cross-dataset validation, no temporal validation, no topK/support/adapter/threshold change, no second-environment reopening, and no manuscript edit.
- Converted issue25c locked OOD alarm results into deployment workload language and audited support/benign-OOD guard assumptions.

Result:
- Primary verdict: `deployment_protocol_plausible_needs_robustness_simulation`.
- Secondary verdict: `lowguard_should_be_framed_as_guarded_adaptation_protocol`.
- LOW-GUARD should be written as a guarded few-shot adaptation protocol; the current LR head should be named/positioned as `LOW-GUARD-LR`, a minimal deployable instance.
- Main method locked OOD max `0.0045` corresponds to about 45 alarms per 10k OOD events, under the official 1% low-alert budget.
- Strong alternatives such as DevNet-like and random32 remain deployment-risky under the official budget because their locked OOD max exceeds 1%.
- Deployment assumptions are plausible but conditional: high-purity supports and benign-OOD guard samples need provenance, delayed confirmation, and contamination checks.

Judgment:
- issue27a strengthens claim framing, not performance evidence.
- It does not prove live SOC deployment, temporal generalization, or external generalization.
- Fully autonomous self-training remains outside scope.

Next:
- Unique next action: `issue27b_deployment_robustness_simulation_for_lowguard_top64_2026-05-22`.
- Prioritize shot sensitivity, support-noise stress, OOD-benign contamination stress, support-source comparison, label-delay if metadata permits, and shadow-mode workload evaluation.
- Do not prioritize adapter upgrades until deployment robustness reveals a concrete failure mode.

### 2026-05-26 (Issue27b Guarded Protocol Transfer + Adapter Recovery)

What was done:
- Completed `runs/issue27b_guarded_protocol_transfer_and_adapter_recovery_2026-05-26/`.
- Ran a frozen locked-bin protocol-transfer matrix on holdout bins `5/6/7/8` with seeds `42..51`.
- Frozen conditions were preserved: selected source-rich top64, kcenter32 supports, locked split protocol, 1% OOD alarm target, final eval report-only, no dA/Transformer training, no temporal or cross-dataset validation, and no manuscript edit.
- Evaluated LR reference, DevNet-like MLP, HistGB shallow, DeepSAD-like center, Prototype/metric LR, and optional RFF Logistic under P0/P1/P2/P3 protocol variants.

Result:
- Primary verdict: `nonlinear_detection_gain_not_low_alert_feasible`.
- LOW-GUARD-LR P3 exactly reproduces issue25c locked mean/min/OOD max: `0.949705 / 0.882629 / 0.004500`.
- Best non-LR full LOW-GUARD head is DevNet-like MLP with locked mean/min/OOD max `0.947497 / 0.895305 / 0.010100` and feasible rate `0.975000`.
- No non-LR adapter met the LOW-GUARD++ dominance rule.
- DevNet-like remains detection-competitive but just exceeds the 1% OOD budget, so it is not a low-alert replacement for LOW-GUARD-LR under the official protocol.
- HistGB, DeepSAD-like, Prototype/metric LR, and RFF Logistic do not provide a stronger feasible instance.

Interpretation:
- The protocol framing remains useful, but broad adapter-transfer should not be overclaimed.
- LOW-GUARD-LR remains the current strongest feasible minimal instance.
- For LOW-GUARD-LR, training-side OOD guard is the decisive recovery mechanism: raw LR detects attacks but badly violates OOD alarm, while threshold-only raw LR becomes feasible by collapsing attack detection.
- The threshold guard remains necessary as a deployment safety gate because it enforces ID+OOD validation alarm control.

Current claim boundary:
- Allowed: current evidence supports LOW-GUARD-LR as the strongest feasible minimal instance under the locked low-alert protocol.
- Allowed: nonlinear heads can be diagnostic and detection-competitive, but low-alert feasibility is not automatic.
- Not allowed: LOW-GUARD works for all adapters, DevNet/DeepSAD are generally defeated, temporal generalization is proven, cross-dataset generalization is proven, or deployment robustness is proven.

Next:
- Unique next action: `issue27c_deployment_robustness_simulation_for_lowguard_lr`.
- Prioritize shot sensitivity, support-noise, OOD benign contamination, support-source comparison, and shadow-mode workload simulation.
- Do not expand the adapter space unless a concrete deployment robustness failure motivates it.

### 2026-05-26 (Issue27c LOW-GUARD Mechanism Falsification + Head Specificity Audit)

What was done:
- Completed `runs/issue27c_lowguard_mechanism_falsification_and_head_specificity_audit_2026-05-26/`.
- Scope was mechanism audit and falsification planning only.
- No deployment robustness simulation, no temporal validation, no cross-dataset validation, no topK/support/threshold change, no dA/Transformer training, and no manuscript edit.
- Reused issue27b frozen artifacts and ran a bounded score-tail / threshold-curve audit for LR, DevNet-like, HistGB, and DeepSAD-like on locked bins `5/6/7/8`.

Result:
- Primary verdict: `lowguard_lr_success_mechanistically_supported`.
- Secondary verdicts:
  - `representation_linearization_explains_lr_advantage`;
  - `lowguard_effect_head_specific_lr_only_so_far`;
  - `non_lr_results_inconclusive_due_to_proxy_implementation`.
- LR has a clean P0/P1/P2/P3 mechanism pattern:
  - raw LR detects attacks but badly violates OOD alarm;
  - threshold-only LR controls OOD by collapsing attack detection;
  - OOD-guarded training preserves detection while suppressing OOD tail;
  - full LOW-GUARD adds the validation safety gate.
- No direct final-eval leakage or protocol bug was found.
- Non-LR heads did receive OOD_train guard, but their score tails / proxy objectives did not produce a stronger low-alert instance.
- DevNet-like and DeepSAD-like remain proxy implementations, so their failures must not be written as general method defeats.

Interpretation:
- Directly moving from issue27b to deployment robustness would be a premature close.
- LOW-GUARD can still be discussed as a guarded adaptation protocol, but empirical performance claims should center on LOW-GUARD-LR unless broader transfer is later validated.
- top64 may have linearized the task in a way that favors LR; representation-vs-head causality is not fully resolved.

Current claim boundary:
- Allowed: LOW-GUARD-LR is the strongest feasible demonstrated instance, and its recovery mechanism is supported by P0/P1/P2/P3 evidence.
- Allowed: LR success appears linked to source-rich top64, OOD-guarded training, and validation-only thresholding.
- Not allowed: LOW-GUARD works for all heads, nonlinear adapters are useless, DevNet/DeepSAD are defeated, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27d_bounded_representation_and_objective_falsification_for_lowguard_lr_specificity`.
- Run a small original100-vs-top64 / LR-vs-DevNet-like-vs-HistGB control matrix.
- Do not widen the adapter zoo or move to deployment robustness until representation/head specificity is bounded.

### 2026-05-26 (Issue27d LOW-GUARD Adapter Interface + Model-Specific Objective Smoke)

What was done:
- Completed `runs/issue27d_lowguard_adapter_interface_and_model_specific_objectives_smoke_2026-05-26/`.
- Implemented a common LOW-GUARD adapter interface with `fit`, `score`, `calibrate`, `evaluate`, and `metadata`.
- Ran a bounded smoke over locked bins `5/6/7/8`, seeds `42/43/44`, representations `source_rich_top64` and `original100`, and heads `LOW-GUARD-LR`, `DevNetScore`, `DeepSADLite`, `HistGB-Conservative`, and `PrototypeMargin`.
- Preserved final-eval exclusion: OOD validation and support validation were used for selection; final OOD eval and attack eval were report-only.
- No temporal validation, cross-dataset validation, deployment robustness simulation, dA/Transformer training, or manuscript edit was performed.

Result:
- Primary verdict: `lowguard_plus_plus_candidate_found_with_model_specific_objective`.
- Stage A interface preflight passed.
- LOW-GUARD-LR on top64 exactly reproduced the issue25c reference in this smoke: locked mean/min/OOD max `0.949705 / 0.882629 / 0.004500`.
- No top64 non-LR head dominated LOW-GUARD-LR. Best top64 non-LR was `LOW_GUARD_HistGB_Conservative` with `0.659751 / 0.040689 / 0.006600`.
- A representation-control LOW-GUARD++ candidate appeared on `original100`: `LOW_GUARD_HistGB_Conservative` reached `0.994261 / 0.978091 / 0.005100` with feasible rate `1.000000`.
- Model-specific-lite objectives improved transfer for some non-LR heads relative to issue27b proxies, but DevNetScore did not improve over the old DevNet-like MLP.

Interpretation:
- This is not a main-method replacement yet. The candidate uses `original100`, while the current frozen main method uses `source_rich_top64`.
- The result is scientifically important because it challenges the idea that top64 plus LR is the only viable route; top64 may favor a linear LR boundary while original100 leaves room for a conservative nonlinear head.
- The framework/protocol direction should stay alive, but only with explicit model-specific objectives and formal validation.

Current claim boundary:
- Allowed: issue27d establishes an auditable adapter interface and identifies a representation-control LOW-GUARD++ candidate for formal validation.
- Allowed: LOW-GUARD-LR remains the strongest demonstrated top64 minimal instance.
- Not allowed: LOW-GUARD++ is proven, the main method has been replaced, LOW-GUARD works for all heads, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27e_formal_validation_for_lowguard_plus_plus`.
- Formally validate `LOW_GUARD_HistGB_Conservative` on `original100` with the full locked seed budget and the same final-eval exclusion rules before considering any main-method change.

### 2026-05-27 (Issue27e LOW-GUARD++ Candidate Freeze Audit)

What was done:
- Completed `runs/issue27e_formal_validation_for_lowguard_plus_plus_original100_histgb_conservative_2026-05-26/`.
- Scope was the formal-validation gate for the `original100 + LOW_GUARD_HistGB_Conservative` LOW-GUARD++ candidate.
- Read issue27d smoke outputs, selection trace, leakage audit, issue27c/25c summaries, issue23 locked asset report, and mainline docs.
- No full locked-seed final-eval run was executed because Stage A candidate config recovery failed.

Result:
- Primary verdict: `candidate_config_not_recoverable_needs_debug`.
- issue27d original100 HistGB-Conservative did not yield one unique frozen config:
  - `histgb_d2_lr003_l2p0_ood4_sup2_t0100` selected 7/12 smoke bin-seed combinations.
  - `histgb_d2_lr005_l2p1_ood4_sup4_t0050` selected 5/12 smoke bin-seed combinations.
- issue27e stopped before full locked validation to avoid hindsight config selection.
- No issue27e final-eval leakage occurred because final OOD / attack eval were not run for the candidate.

Interpretation:
- This does not invalidate the original100 HistGB candidate. It means the candidate is not yet a single frozen method instance.
- The smoke result should be treated as a selection-policy / aggregate candidate, not a formal LOW-GUARD++ validation result.
- LOW-GUARD-LR remains the demonstrated stable minimal instance.

Current claim boundary:
- Allowed: original100 + HistGB-Conservative remains a serious LOW-GUARD++ candidate that needs config-freeze recovery.
- Not allowed: LOW-GUARD++ is formally validated, the main method has been replaced, HistGB universally dominates LR, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27f_candidate_config_freeze_and_formal_validation_for_original100_histgb_conservative`.
- Freeze exactly one HistGB-Conservative config using only support-validation / OOD-validation trace evidence and pre-registered simplicity/low-alert rules, then run the full locked seeds.

### 2026-05-27 (Issue27f Config Freeze + Formal LOW-GUARD++ Validation)

What was done:
- Completed `runs/issue27f_config_freeze_then_formal_validation_for_original100_histgb_conservative_2026-05-27/`.
- Froze one `original100 + HistGB-Conservative` config using only train/cal/validation-side evidence from issue27d.
- Frozen config: `histgb_d2_lr005_l2p1_ood4_sup4_t0050`.
- Ran full locked seed validation over seeds `42..51` and locked bins `5/6/7/8`.
- Re-ran LOW-GUARD-LR top64 reference in the same output schema.
- No deployment robustness, temporal validation, cross-dataset validation, representation search, new model search, or manuscript edit was performed.

Result:
- Primary verdict: `lowguard_plus_plus_formal_validated`.
- LOW-GUARD++ formal locked mean/min/OOD max: `1.000000 / 1.000000 / 0.000100`.
- LOW-GUARD-LR top64 reference locked mean/min/OOD max: `0.949705 / 0.882629 / 0.004500`.
- LOW-GUARD++ dominates LOW-GUARD-LR on locked mean, locked min, and OOD max under the locked protocol.
- Feasible rate is `1.000000`.
- No seed/bin collapse was observed; every locked bin had detection mean/min `1.000000` and OOD max `0.000100`.
- Threshold target robustness remained strong:
  - target `0.0050`: `1.000000 / 1.000000 / 0.000100`;
  - target `0.0075`: `1.000000 / 1.000000 / 0.000100`;
  - target `0.0100`: `1.000000 / 1.000000 / 0.008300`.
- No final-eval leakage or support/eval overlap was found.

Interpretation:
- The paper mainline can now use a dual-instance story:
  - `LOW-GUARD-LR` as the minimal stable instance under source-rich top64;
  - `LOW-GUARD++` as the performance-oriented instance: original100 + HistGB-Conservative with frozen config.
- This supports a model-specific guarded objective interpretation, not a claim that every head works.

Current claim boundary:
- Allowed: LOW-GUARD++ is formally validated for `original100 + HistGB-Conservative` under the locked low-alert protocol.
- Allowed: LOW-GUARD-LR remains the minimal stable instance.
- Not allowed: HistGB universally dominates LR, LOW-GUARD works for all models, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27g_deployment_robustness_for_lowguard_lr_and_lowguard_plus_plus`.
- Run support-count, support-noise, OOD-contamination, support-source, and shadow-mode robustness for both LOW-GUARD-LR and LOW-GUARD++ before widening claims.

### 2026-04-08

What was done:
- Completed the covariance-aware final candidate audit and the surrounding no-retrain diagnostics on the formal stronger-OOD mainline.
- Main related runs include:
  - `runs/frontend100_final_candidate_audit_2026-04-08/`
  - `runs/frontend100_diagload_gate_multiseed_2026-04-08/`
  - `runs/frontend100_conditional_gate_multiseed_2026-04-08/`
  - `runs/frontend100_external_baselines_2026-04-08/`
  - `runs/frontend100_recurrent_deep_baselines_2026-04-08/`

Result:
- The main pathology was pinned down as latent covariance tail instability rather than complete loss of attack-separation signal.
- Covariance-aware scoring and ensemble logic improved the Transformer family in the operating region that matters, but they did not close the whole paper-readiness gap by themselves.

Judgment:
- Covariance-aware logic is real signal, not a scoring artifact.
- The project had enough evidence to move from local debugging into formal evidence packaging.

Next:
- Add stronger external references, deployment/cost evidence, and paper-facing consolidation.

### 2026-04-09

What was done:
- Added stronger external and deployment-side evidence:
  - `runs/frontend100_deep_svdd_baseline_2026-04-09/`
  - `runs/frontend100_runtime_benchmark_2026-04-09/`
  - `runs/frontend100_additional_ood_setting_smoketest_2026-04-09_b/`
  - `runs/frontend100_additional_ood_setting_smoketest_2026-04-09_c/`

Result:
- `Deep SVDD` confirmed that a modern deep one-class baseline can drive detection high while still failing badly on fixed false alarms under stronger benign OOD.
- Runtime and throughput evidence became available for the main candidate relative to the existing references.

Judgment:
- This strengthened the main claim that stronger benign OOD is an operating-region problem, not just an AUC comparison problem.
- `Deep SVDD` is useful as a negative baseline, not as a new mainline method candidate.

Current blocker after this step:
- Even with the extra evidence, the project still lacked a complete A-tier package: modern tabular baselines, cross-environment self-validation, adversarial evaluation, and a cleaner deployability story.

Next:
- Keep strengthening the evidence package instead of opening another unconstrained method branch.

### 2026-04-11

What was done:
- Completed `runs/frontend100_ensemble_distillation_v1_2026-04-11/`.

Result:
- Distillation v1 learned bulk teacher-score structure but failed to preserve the teacher's fixed operating-point behavior.
- Teacher remained strong at the target operating point, while the distilled head lost too much fixed detection.

Judgment:
- Distillation v1 cannot be promoted to the A-line main candidate.
- If distillation is revisited later, it must be a tail-aware v2 rather than another generic regression-style imitation.

Next:
- Do not spend A-line time on ordinary distillation v1 variants.
- Treat deployability as an evidence gap to be closed after the baseline and robustness packages, not before.

### 2026-04-12

What was done:
- Reclassified the project into the A-tier strengthening stage and fixed the official execution order in `runs/mainline_docs/mainline_experiment_map.md`.

Result:
- The project status changed from "close the current draft" to "expand into a system paper with stronger evidence."
- The enforced execution order became:
  1. baseline strengthening
  2. second-dataset or second-environment minimal validation
  3. adversarial robustness evaluation
  4. deployability and cost closure
  5. tail-aware distillation v2

Judgment:
- The immediate priority is not another broad method search.
- The immediate priority is to reduce reviewer attack surface on baseline strength, external validity, robustness, and deployment realism.

Current blocker after this step:
- The plan was fixed, but the first item in the queue still needed a clean modern-tabular execution path.

Next:
- Start the modern tabular baseline package with `FT-Transformer` first.

### 2026-04-13

What was done:
- Completed `runs/frontend100_modern_tabular_baselines_ft_smoke_2026-04-13/`.

Result:
- The `FT-Transformer` autoencoder smoke path ran successfully on the formal A-line input protocol.
- Single-seed local smoke showed weak fixed performance:
  - `q99 ~ alarm 0.4935 / det 0.8064`
  - `q995 ~ alarm 0.2667 / det 0.6970`

Judgment:
- The modern tabular baseline script is now operational.
- The initial signal suggests that this line does not currently threaten the strongest A-line candidate.
- This is only a smoke result, not yet formal evidence. It still needs the standard A-line reporting package before the baseline-risk question is considered closed.

Current blocker after this step:
- The modern tabular baseline evidence is still not in full formal form.

Next:
- Promote `FT-Transformer` from smoke to formal A-line evaluation with the standard operating-point table and cost summary.
- Only consider `RTDL-ResNet` if the formal FT result leaves residual baseline-risk concerns.

### 2026-04-14

What was done:
- Fixed the ownership boundary for this conversation: it is now the A-line experiment execution thread plus the A-line mainline handoff maintainer.
- Added A-line artifact path resolution so generated experiment outputs default to the D-drive mainline worktree while tracked handoff and map files remain in the current worktree.
- Patched the current A-line baseline infrastructure to use that routing:
  - `repo/paths.py`
  - `repo/ood/stage1_probe.py`
  - `repo/ood/frontend100_modern_tabular_baselines.py`
  - `repo/ood/frontend100_deep_svdd_baseline.py`
  - `repo/ood/frontend100_external_baselines.py`
  - `repo/ood/frontend100_runtime_benchmark.py`
  - `repo/ood/frontend100_additional_ood_setting_eval.py`
  - `repo/ood/frontend100_recurrent_deep_baselines.py`
- Fixed the A-line HPC usage rule:
  - Use HPC for long formal training, multi-seed runs, sweeps, second-dataset validation, larger external-baseline reproduction, and other non-smoke workloads.
  - Do not use HPC for script/path fixing, local smoke checks, offline rescoring, or table/plot collation.
  - Formal HPC runs must follow the sequence: local smoke first, then freeze code/config, ensure portable paths, prepare stable output names plus bundle/return layout, then submit and monitor logs.
- Fixed the `FT-Transformer` formal baseline HPC blocker:
  - corrected `stage2` source TSV resolution for Windows-style manifest paths inside bundled Linux runs;
  - added `--stage2-indices-json` support to the modern-tabular baseline script so formal FT runs can consume precomputed high/mixed indices without reopening the raw TSV on the cluster;
  - added a reusable `prepare_frontend100_modern_tabular_hpc.py` bundle builder;
  - refreshed `runs/frontend100_modern_tabular_baselines_ft_2026-04-13/` with a new `job.slurm`, new `upload_bundle.tar.gz`, and stable watch files.
- Fixed the FT HPC logging protocol:
  - job stdout/stderr is now mirrored into both `slurm-<jobid>.out/.err` and `stdout.log/stderr.log`;
  - submit commands now create `latest_slurm.out`, `latest_slurm.err`, and `last_job_id.txt` in the run directory so status can be opened directly in the remote file tree without running `tail -f`.
- Fixed the Windows PowerShell submit command issue:
  - the generated SSH submit sequence is now PowerShell-safe and no longer uses a local double-quoted `JOB_ID=$(...)` pattern that gets expanded on Windows before reaching the remote shell;
  - bundle pull-back is explicitly separated from submission and should only be run after the remote job has finished and the package file exists.
- Reset the FT formal rerun onto a fresh date-stamped run tag:
  - `frontend100_modern_tabular_baselines_ft_2026-04-13` remains the failed earlier attempt;
  - the corrected formal rerun package is now prepared under `frontend100_modern_tabular_baselines_ft_2026-04-14`.
- Pulled back the first real `2026-04-14` FT rerun failure signal from the cluster:
  - `latest_slurm.out` showed the wrapper itself was healthy and the Python command exited immediately with status `1`;
  - `latest_slurm.err` showed the real cause was import-time failure inside `repo/paths.py`, not FT training instability:
    - bundled cluster Python is `3.9`;
    - `repo/paths.py` still used runtime-evaluated `str | None` style annotations;
    - the bundled run directory is not a git checkout, so the artifact-path resolver also needs a no-git fallback.
- Fixed the FT formal rerun compatibility blocker in mainline code:
  - backported `repo/paths.py` to Python `3.9`-safe typing (`Optional[...]`, `List[...]`, `Tuple[...]`);
  - made `repo/paths.py` skip git worktree probing when `.git` metadata is absent;
  - made the git helper suppress stderr noise and honor `REMOTE_PROJECT_ROOT` when resolving artifact roots in bundled HPC runs;
  - rebuilt `frontend100_modern_tabular_baselines_ft_2026-04-14/` so the refreshed upload bundle now contains the fixed `repo/paths.py`.

Result:
- This file is now the single handoff entry for A-line time-ordered progress.
- From the current Codex mirror workspace, A-line generated runs now resolve to `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs`.
- This reduces C-drive pressure without redirecting tracked mainline docs into another working tree.
- A-line now has an explicit rule for when a task should stay local and when it should be escalated to HPC.
- The FT formal run package is now refreshed and locally validated against the bundled `source_root` layout.
- The first `2026-04-14` FT rerun did not fail in training; it failed before execution because the bundle still contained a Python `3.9`-incompatible `repo/paths.py`.
- The refreshed `2026-04-14` upload bundle now matches the cluster Python requirement and should clear that immediate import-time exit.
- The current environment still cannot submit to `school-hpc` non-interactively, so actual re-upload and re-submission remain a user-side action.

Judgment:
- From this point onward, only stable A-line nodes should be added here.
- A-line should treat D-drive artifact routing as the default execution mode for new formal runs.
- HPC is the default for formal heavy A-line experiments, but only after local smoke and packaging stability are both confirmed.
- The mainline blocker is no longer an unknown FT crash. The immediate blocker has been narrowed to re-uploading the refreshed `2026-04-14` bundle and checking whether the cluster then reaches real training.

Next:
- Continue the baseline-strengthening package and update this handoff after each stable A-line node.
- Use the new default D-drive routing when promoting `FT-Transformer` from smoke to formal baseline evaluation.
- When `FT-Transformer` formal evaluation is ready, decide explicitly whether it is still local or should go to HPC using the rule above.
- Re-upload and re-submit `frontend100_modern_tabular_baselines_ft_2026-04-14` using the refreshed bundle and inspect `latest_slurm.out` / `latest_slurm.err` directly in the remote run directory.
- After FT formal results return, decide whether `RTDL-ResNet` still needs a formal 3-seed run or can stay at smoke status.

### 2026-04-17

What was done:
- Pulled back the completed formal HPC result for `runs/frontend100_modern_tabular_baselines_ft_2026-04-14/`.
- Verified the run finished successfully on the cluster:
  - job id: `14459`
  - node: `node185`
  - status: Python command exited `0`
  - returned artifacts include `modern_tabular_results.csv`, `modern_tabular_aggregate.csv`, `modern_tabular_costs_aggregate.csv`, `modern_tabular_summary.md`, `stdout.log`, `stderr.log`, and the packaged return bundle.
- Read the formal FT aggregate under the stronger-OOD mainline protocol and compared it against frozen A-line references.

Result:
- `FT-Transformer AE` is now formally negative as an A-line threat under the operating points that matter.
- Key aggregate result at `fixed_id_q995`:
  - `ft_transformer_ae`: `ood_alarm_ratio_eval_mean = 0.767333`, `attack_detection_high_purity_mean = 0.928201`, `roc_auc_attack_high_vs_ood_eval_mean = 0.754077`
  - `transformer_ensemble_main_candidate`: `ood_alarm_ratio_eval_mean = 0.126067`, `attack_detection_high_purity_mean = 0.844419`, `roc_auc_attack_high_vs_ood_eval_mean = 0.878093`
  - `dA fixed_id_q0p995`: `ood_alarm_ratio_eval_mean = 0.104489`, `attack_detection_high_purity_mean = 0.769029`, `roc_auc_attack_high_vs_ood_eval_mean = 0.809622`
- Interpretation of the formal FT result:
  - FT can push attack detection high, but only by letting stronger benign OOD alarms explode.
  - Under the fixed `0.5%` ID operating point, FT fires on about `76.7%` of eval OOD, which is far outside the acceptable deployment region.
  - Under `naive_calibrated_budget5000_target1pct`, FT holds eval OOD alarm near `1.49%`, but high-purity attack detection collapses to about `0.00044`, so it does not offer a credible operating-point alternative.
  - Under `det_floor_50pct_min_alarm`, FT still needs about `10.19%` eval OOD alarm to hold `~50%` high-purity detection, again not competitive with the mainline references.
- Seed behavior is stable enough for the conclusion:
  - all three FT seeds show the same qualitative failure mode rather than one bad run.
- Cost note:
  - checkpoint size is about `1.12 MB`
  - parameter count is `275,364`
  - mean training time is about `1934.47 s` on CPU
- Residual logging issue:
  - the returned `stderr.log` still contains a benign `git rev-parse HEAD` failure because the remote bundle root is not a git checkout; this did not affect training correctness but should be cleaned in the job wrapper later.

Judgment:
- The FT formal package closes the mainline question of whether this modern tabular baseline materially threatens the stronger-OOD covariance-tail story. It does not.
- FT should not receive more A-line optimization time unless a very specific paper-facing criticism requires a targeted rebuttal.
- `RTDL-ResNet` no longer looks mandatory as a full formal 3-seed run. It can remain optional unless we decide we need one extra modern-tabular reference for presentation completeness.

Next:
- Keep the A-line scope tight and do not spend another cycle tuning FT.
- Treat the modern-tabular baseline-risk item as substantially closed by this formal FT result plus the already available external/deep baseline evidence.
- Use the saved A-line budget on the next blocker in the fixed order:
  1. second-dataset or second-environment minimal validation
  2. adversarial robustness evaluation
  3. deployability and cost closure

### 2026-04-17 (Formal HPC SOP Fixed)

What was done:
- Fixed the A-line formal HPC operating book for all future official cluster runs.
- Locked the usage boundary:
  - local smoke first, formal cluster run second;
  - HPC is for formal training, multi-seed runs, sweeps, second-dataset or second-environment validation, formal baseline reproduction, and other long CPU/GPU jobs;
  - HPC is not for path fixing, script fixing, bundle fixing, offline rescoring, plotting, table collation, or ambiguous not-yet-worthy runs.
- Locked the formal naming rule:
  - every formal cluster task must use a fresh `run_tag` with format `task_name_YYYY-MM-DD`;
  - reruns must switch to a new date;
  - local run path is fixed to `runs/<run_tag>/`;
  - remote project root must also be date-stamped;
  - remote formal run path is fixed to `<remote_project_root>/runs/<run_tag>/`;
  - return bundle path is fixed to `package/<run_tag>_bundle.tar.gz`.
- Locked the pre-submit freeze set:
  - `command.txt`
  - `config.json`
  - `run_spec.json`
  - `job.slurm`
  - `upload_bundle.tar.gz`
  - explicit return-bundle path
  - if these are not frozen in the run directory, the task is not allowed onto HPC.
- Locked the formal submission order:
  1. create remote directories by `ssh`
  2. upload `upload_bundle.tar.gz` by `scp`
  3. unpack remotely
  4. run `sbatch job.slurm` inside the remote run directory
  5. auto-create `latest_slurm.out`, `latest_slurm.err`, and `last_job_id.txt`
  6. after completion, pull back `package/<run_tag>_bundle.tar.gz`
  7. unpack locally and verify completeness before any handoff update
- Locked the remote logging rule:
  - the remote run directory must always expose `latest_slurm.out`, `latest_slurm.err`, `stdout.log`, and `stderr.log` directly in the file tree;
  - status inspection should default to opening those files directly, not to ad hoc `tail -f`;
  - program stdout/stderr must be mirrored into both Slurm files and `stdout.log` / `stderr.log`;
  - submission must auto-record `last_job_id.txt`, `latest_slurm.out`, and `latest_slurm.err`;
  - a `job_info.json` or equivalent manifest is recommended to store `job_id`, `job_name`, `node_list`, `submit_dir`, `python_bin`, `stdout_log`, and `stderr_log`.
- Locked the `job.slurm` minimum wrapper metadata:
  - `[start]`
  - `[run_dir]`
  - `[python]`
  - `[command]`
  - `[command_exit]`
  - `[bundle]`
  - `[finish]`
- Locked the PowerShell rule:
  - generated `ssh` / `scp` / `sbatch` commands must be copy-run safe under Windows PowerShell;
  - do not emit commands that require manual quoting repair or accidental local variable expansion.
- Locked the return-bundle completeness rule:
  - `summary`
  - `results`
  - `diagnostics`
  - `config`
  - `stdout.log`
  - `stderr.log`
  - `job_info` or equivalent run manifest
- Locked the post-return action order:
  1. verify `summary`, `results`, `diagnostics`, and logs
  2. update mainline handoff
  3. update mainline experiment map
  4. commit and push
  - if the result is invalid, record failure reason, fix point, and whether a fresh-date rerun is required.

Result:
- A-line now has a fixed formal HPC contract rather than a case-by-case submission habit.
- Future cluster submissions should be easier to audit, easier to resume, and less likely to fail on naming, quoting, log visibility, or incomplete return packaging.

Judgment:
- HPC is now explicitly a formal execution backend, not a debugger.
- From this point onward, no A-line job should be promoted to HPC unless the local smoke, package freeze, naming, logging, and return-bundle rules are already satisfied.

Next:
- Apply this fixed SOP to the next formal A-line cluster workload.
- Before the next submission, verify the run directory satisfies the frozen-file checklist exactly.

### 2026-04-17 (Second-Environment Feasibility Started)

What was done:
- Started the A-line second-dataset or second-environment package with a local feasibility node instead of jumping directly to formal training.
- Added `repo/ood/second_environment_feasibility.py` as an A-line-only probe for the `BoT-IoT first` entry condition.
- Created `runs/second_environment_botiot_feasibility_2026-04-17/` and ran the probe locally.
- Verified the official dataset entry pages are reachable:
  - `https://research.unsw.edu.au/projects/bot-iot-dataset`
  - `https://research.unsw.edu.au/projects/toniot-datasets`
- Extracted the official SharePoint dataset links from those pages and tested direct access from the current environment.
- Scanned the local `D:\study` tree and confirmed there is no existing `BoT-IoT` or `TON-IoT` dataset copy available for immediate smoke preparation.

Result:
- The current A-line blocker for second-environment validation is data availability, not model code.
- `BoT-IoT first` is currently blocked on this machine:
  - the official `BoT-IoT` dataset link resolves into a Microsoft login flow rather than a directly usable dataset folder from the current environment;
  - no local `BoT-IoT` copy is present;
  - no local `TON-IoT` fallback copy is present either.
- The generated feasibility node is:
  - `runs/second_environment_botiot_feasibility_2026-04-17/`
- Main artifacts include:
  - `summary.md`
  - `config.json`
  - `run_spec.json`
  - `feasibility_report.json`
  - `command.txt`

Judgment:
- The mainline should not pretend this is a model-training blocker or spend HPC budget here yet.
- The correct reading is that the second-environment package is ready at the infrastructure/protocol level for a local smoke start, but the dataset itself is not locally available.
- Until a local `BoT-IoT` or `TON-IoT` copy is placed on disk, the second-environment line cannot advance into the mandated local smoke stage.

Next:
- Obtain a local `BoT-IoT` dataset copy first if possible, because the execution order is fixed as `BoT-IoT first`.
- If `BoT-IoT` remains inaccessible but `TON-IoT` becomes locally available earlier, rerun the same feasibility probe with a local `TON-IoT` root and decide explicitly whether the mainline should switch to the documented fallback.
- After a local dataset copy exists, rerun the feasibility node with `--bot-iot-root` or `--ton-iot-root`, then build the minimal second-environment smoke package before any formal HPC run.

### 2026-04-20 (BoT-IoT Local Data Arrived + Smoke Started)

What was done:
- Confirmed local `BoT-IoT 5%` data is now present at:
  - `D:\study\paper\anomaly_detection\paper04\worktrees\data\5%`
- Re-ran feasibility with the local data root:
  - `runs/second_environment_botiot_feasibility_2026-04-20/`
  - verdict is now `bot_iot_local_ready_for_smoke`.
- Started and completed the first local second-environment smoke node:
  - added `repo/ood/second_environment_botiot_smoke.py`
  - generated `runs/second_environment_botiot_smoke_2026-04-20/`
  - used BoT-IoT official 10-best training/testing split CSVs:
    - train: `UNSW_2018_IoT_Botnet_Final_10_best_Training.csv`
    - test: `UNSW_2018_IoT_Botnet_Final_10_best_Testing.csv`
  - smoke protocol:
    - label column: `attack` (`0` as benign)
    - numeric-only features for this first pass
    - split = ID benign from train, OOD benign from test, attack from test
    - models = `isolation_forest` and `oneclass_svm`
    - policies = `fixed_id_q99`, `naive_calibrated_budget500_target1pct`, `det_floor_50pct_min_alarm`

Result:
- The second-environment line is no longer blocked by missing data and now has a runnable local smoke path.
- Smoke split scale:
  - `id_benign_train = 370`
  - `ood_benign_test = 107`
  - `attack_test = 100000` (capped for smoke speed)
  - `numeric_feature_count = 11`
- Smoke outputs are available in:
  - `summary.md`
  - `split_summary.csv`
  - `smoke_results.csv`
  - `smoke_scan.csv`
  - `feature_columns.txt`
  - `data/id_benign_numeric.csv`, `data/ood_benign_numeric.csv`, `data/attack_numeric.csv`
- Key smoke signals (not formal conclusions):
  - `isolation_forest` fixed q99: `ood_alarm = 0.0000`, `attack_det = 0.7440`, `auc = 0.9832`
  - `oneclass_svm` fixed q99: `ood_alarm = 0.0374`, `attack_det = 1.0000`, `auc = 1.0000`

Judgment:
- This node successfully proves the BoT-IoT second-environment smoke pipeline works end-to-end on local data.
- These numbers are not yet paper-grade because benign support is extremely small (`370/107`) and the split is a dataset-provided train/test partition rather than a stronger benign-OOD construction.
- The current node should be treated as a readiness milestone, not as external-validity evidence closure.

Next:
- Build the formal second-environment definition on top of this runnable path:
  - lock a defensible benign ID/OOD split rule under BoT-IoT;
  - run the required mainline objects (`dA`, current strongest candidate, `FT` line) with aligned policies.
- If BoT-IoT cannot provide enough benign support for a defensible stronger-OOD operating-point study, escalate to the documented `TON-IoT` fallback for the formal package.

### 2026-04-20 (BoT-IoT Split Gate Converged)

What was done:
- Added `repo/ood/second_environment_botiot_split_gate.py` to make the BoT-IoT split decision explicit under mainline policy constraints.
- Ran `runs/second_environment_botiot_split_gate_2026-04-20/` using:
  - `UNSW_2018_IoT_Botnet_Final_10_Best.csv` (full 10-best)
  - `UNSW_2018_IoT_Botnet_Final_10_best_Training.csv`
  - `UNSW_2018_IoT_Botnet_Final_10_best_Testing.csv`
  - `UNSW_2018_IoT_Botnet_Full5pc_4.csv`
- Evaluated multiple BoT-IoT split candidates against fixed requirements:
  - fixed point feasibility (`id>=100`, `ood>=100`)
  - required mainline naive policy budget (`ood>=5000`)
  - formal benign support gate (`id>=1000`, `ood>=1000`)

Result:
- Gate verdict is:
  - `blocked_naive_budget5000_not_supported`
- Raw benign support in BoT-IoT 5% is too small for the required naive calibration policy:
  - full 10-best benign = `477`
  - train benign = `370`
  - test benign = `107`
  - all-feature full4 benign = `477`
- Candidate table confirms none can satisfy `naive_budget5000`:
  - `official_10best_train_vs_test`: `id=370`, `ood=107`
  - `full10best_max_ood_with_id100`: `id=100`, `ood=377`
  - `full10best_benign_70_30`: `id=334`, `ood=143`
  - `full4_benign_70_30`: `id=334`, `ood=143`
- All candidates pass minimal fixed-q99 count checks but all fail both `naive_budget5000` and formal benign support.

Judgment:
- BoT-IoT can still serve smoke/readiness diagnostics, but it cannot be the formal second-environment closure under the currently fixed mainline policy set.
- The split question is now converged for BoT-IoT under A-line rules; continuing BoT-IoT split tweaking is not a productive mainline path.

Next:
- Escalate to `TON-IoT` fallback for the formal second-environment package.
- Keep BoT-IoT nodes as negative/constraint evidence in the external-validity discussion rather than as final cross-environment proof.

### 2026-04-20 (TON-IoT Fallback Intake Attempted)

What was done:
- Started the documented `TON-IoT` fallback line immediately after the BoT-IoT split gate verdict.
- Added `repo/ood/second_environment_toniot_intake.py` to perform a concrete local intake gate on the declared data root.
- Ran:
  - `runs/second_environment_toniot_intake_2026-04-20/`
  - data root: `D:\study\paper\anomaly_detection\paper04\worktrees\data`

Result:
- Intake verdict:
  - `blocked_missing_toniot_files`
- Scanner summary:
  - total tabular files under root: `7`
  - TON-like candidate files: `0`
  - TON-like labeled candidates: `0`
- Current root content is BoT-IoT 5% only; no TON-IoT file pattern was detected yet.

Judgment:
- Mainline fallback direction is correct, but fallback cannot advance into smoke until TON-IoT files are actually present (or a concrete TON subdirectory path is provided).
- This is a data-availability blocker, not a script or protocol blocker.

Next:
- Provide the TON-IoT local directory under the same data root (or the exact absolute path if stored elsewhere).
- Rerun the TON intake node on that path, then immediately proceed to TON local smoke with fixed mainline policies.

### 2026-04-20 (TON-IoT Intake Ready + First Smoke)

What was done:
- Received local TON path:
  - `D:\study\paper\anomaly_detection\paper04\worktrees\data\Train_Test_Network_dataset`
- Re-ran intake with this exact subdirectory:
  - `runs/second_environment_toniot_intake_2026-04-20_b/`
  - verdict: `toniot_intake_ready_for_smoke`
- Started and completed the first TON local smoke node:
  - added `repo/ood/second_environment_toniot_smoke.py`
  - generated `runs/second_environment_toniot_smoke_2026-04-20/`
  - source file: `train_test_network.csv`
  - split rule:
    - `label=0` as benign, `label=1` as attack
    - ID benign first `30000`
    - OOD benign next `20000`
    - attack sample `100000` (seeded subsample)
  - policy family:
    - `fixed_id_q99`
    - `naive_calibrated_budget5000_target1pct`
    - `det_floor_50pct_min_alarm`
  - models:
    - `isolation_forest`
    - `oneclass_svm`
- Verified label semantics to avoid direction errors:
  - `label=0` corresponds to `type=normal` (`50000` rows)
  - `label=1` corresponds to attack types (`161043` rows)

Result:
- TON fallback line is now unblocked and runnable end-to-end locally.
- Smoke split scale:
  - `id_benign = 30000`
  - `ood_benign = 20000`
  - `attack = 100000`
  - `numeric_feature_count = 16`
- First smoke metrics show weak/no-separation behavior for the tested unsupervised baselines on this split:
  - `isolation_forest` fixed q99: `ood_alarm=0.0037`, `attack_det=0.0097`, `auc=0.2470`
  - `oneclass_svm` fixed q99: `ood_alarm=0.4969`, `attack_det=0.1252`, `auc=0.1839`
- `naive_calibrated_budget5000_target1pct` is now executable on TON (unlike BoT-IoT), so policy-compatibility blocker is cleared.

Judgment:
- This is a valid readiness milestone for the TON fallback route, not a formal second-environment conclusion.
- The immediate problem is no longer missing benign support; it is poor baseline behavior under the current fallback split and feature treatment.
- Formal second-environment package should now focus on running the required mainline objects and checking whether the weak signal is method-specific or split/feature-specific.

Next:
- Keep this TON node as fallback-start evidence and proceed to the required mainline object set (`dA`, current strongest candidate, FT line) under the same policy family.
- Before formal HPC, run one tighter local smoke that controls for obvious confounders (feature subset/normalization and split construction) to avoid wasting a formal run on a degenerate setting.

### 2026-04-20 (TON Formal Precheck + Polarity Gate Fixed)

What was done:
- Added `repo/ood/second_environment_toniot_precheck.py` and ran:
  - `runs/second_environment_toniot_precheck_2026-04-20/`
- Precheck scope:
  - freeze deterministic split manifest for TON fallback formal runs;
  - run score-polarity gate on baseline probes;
  - re-evaluate fixed/naive/det50 policies under the chosen score orientation.
- Fixed split used by precheck:
  - source: `train_test_network.csv`
  - ID benign: `30000`
  - OOD benign: `20000`
  - attack: `100000`
  - numeric features: `16`
  - saved as `split_manifest.json`.

Result:
- Precheck verdict:
  - `polarity_checked_ready_for_formal_object_runs`
- Polarity gate outcome:
  - `isolation_forest`: choose `raw_decision` (`auc=0.752998`, other orientation `0.247002`)
  - `oneclass_svm`: choose `raw_decision` (`auc=0.816051`, other orientation `0.183949`)
- This explains the earlier smoke anomaly (`AUC < 0.5`): prior score orientation in the smoke script was inverted for TON fallback semantics.
- Policy metrics after polarity correction are now recorded in:
  - `precheck_policy_results.csv`
  - `score_distribution_stats.csv`
  - `polarity_check.csv`

Judgment:
- TON fallback now has both a fixed split manifest and a validated score orientation.
- The pipeline is ready to enter formal object runs (`dA`, current strongest candidate, FT line) without the previous directionality ambiguity.
- We should not launch formal HPC until formal object scripts consume this exact split manifest and chosen score orientation.

Next:
- Implement/patch the formal TON object-run entry so `dA`, strongest candidate, and FT line all read `split_manifest.json`.
- Keep policy family fixed (`fixed_id_q99`, `naive_calibrated_budget5000_target1pct`, `det_floor_50pct_min_alarm`) and proceed with local smoke checks before formal HPC submission.

### 2026-04-20 (TON Mainline Object Pre-Run Completed)

What was done:
- Added `repo/ood/second_environment_toniot_object_prerun.py` to run the required second-environment object pack on a fixed TON split manifest with unified policy family.
- Ran:
  - `runs/second_environment_toniot_object_prerun_2026-04-20_b/`
- This node consumed `runs/second_environment_toniot_precheck_2026-04-20/split_manifest.json` and executed:
  - `dA`
  - `strongest_candidate_transformer_covreg_v2_seed101` (migratable single-seed strongest-candidate proxy)
  - `ft_transformer_ae`
- Local pre-run scale for this node:
  - `ID train = 8000`
  - `ID eval = 4000`
  - `OOD eval = 8000`
  - `attack eval = 12000`
  - `naive budget = 5000`

Result:
- Object pack is now runnable end-to-end under one script, one split source, and one policy set.
- Polarity gate selected `neg_raw_score` for all three objects:
  - `dA`: `auc=0.679894`
  - `strongest_candidate_transformer_covreg_v2_seed101`: `auc=0.668993`
  - `ft_transformer_ae`: `auc=0.511384`
- Fixed and naive operating points are currently weak on this TON pre-run split:
  - `dA` fixed: `ood_alarm=0.007625`, `attack_det=0.076667`
  - `strongest_candidate` fixed: `ood_alarm=0.014125`, `attack_det=0.000000`
  - `ft_transformer_ae` fixed: `ood_alarm=0.000000`, `attack_det=0.000000`
  - `ft_transformer_ae` naive: `ood_alarm=0.010875`, `attack_det=0.011750`
- Detection-floor reference (`det_floor_50pct_min_alarm`) required high OOD alarm for all:
  - `dA`: `0.298500`
  - `strongest_candidate`: `0.333125`
  - `ft_transformer_ae`: `0.480000`
- Runtime diagnostics captured in `object_diagnostics.csv` indicate the strongest-candidate line is much heavier than `dA/FT` under this local setup.
- During strongest-candidate scoring, one `NaN/Inf detected in execute score` message appeared (run completed, but this is a stability warning to resolve before formal promotion).

Judgment:
- This node closes the implementation gap (“required objects can now run on TON fallback with aligned policies”), but does not close the second-environment evidence gap.
- On the current pre-run scale and settings, none of the three objects provides a strong fixed/naive operating-point result.
- Formal HPC promotion is not justified yet; the correct next action remains local diagnosis and stabilization.

Next:
- Diagnose and fix the strongest-candidate `NaN/Inf` execute-path instability on TON split.
- Run one more local stabilization pass for the same object pack (same policy family, same split source) before scaling to full TON counts.
- If stabilized local results remain weak, record as negative external-validation evidence; if stabilized signal improves, then prepare the formal date-tagged HPC package by the fixed SOP.

### 2026-04-21 (TON Engineering + Protocol Gate Passed)

What was done:
- Upgraded `repo/ood/second_environment_toniot_object_prerun.py` for engineering auditability:
  - non-finite score replacement counters per object/split;
  - optional score-array persistence under `runs/<run_tag>/scores/`;
  - hard finite-value guard before policy evaluation.
- Added `repo/ood/second_environment_toniot_engineering_gate.py` as an explicit gate checker for:
  - split-manifest integrity and label semantics;
  - required output matrix completeness (`3 objects x 3 policies`);
  - fixed policy names and `naive_budget5000` presence;
  - finite-value checks on result and polarity tables.
- Ran local engineering smoke:
  - `runs/second_environment_toniot_object_prerun_2026-04-21_engineering_smoke/`
  - scale: `ID train=4000`, `ID eval=2000`, `OOD eval=5000`, `attack eval=5000`
- Ran gate checker on this node and generated:
  - `runs/second_environment_toniot_object_prerun_2026-04-21_engineering_smoke/engineering_gate/summary.md`
  - `runs/second_environment_toniot_object_prerun_2026-04-21_engineering_smoke/engineering_gate/engineering_gate_report.json`

Result:
- Gate verdict:
  - `engineering_gate_pass`
- Split checks all pass:
  - indices in bounds;
  - ID/OOD/attack disjoint;
  - ID and OOD labels are normal (`0`);
  - attack labels are non-normal.
- Output checks all pass:
  - required files present;
  - object-policy matrix complete;
  - `naive_calibrated_budget5000_target1pct` present;
  - metrics and polarity values finite.
- Non-finite counters:
  - total `0` in this engineering smoke run.

Judgment:
- Current blocker has moved from “possible engineering/口径错误” to “性能与跨环境泛化本身不足”。
- Formal HPC should still wait, but now the wait reason is method performance, not pipeline correctness.

Next:
- Keep this gate as mandatory pre-submit check for TON object runs.
- Move to method-side diagnosis under fixed gate:
  - same split source and policy family;
  - improve detection at low alarm, or record stable negative evidence if improvement fails.

### 2026-04-21 (TON Stability Re-Run Under Fixed Gate)

What was done:
- Ran one same-scale stability rerun under the fixed object-pack protocol:
  - `runs/second_environment_toniot_object_prerun_2026-04-21_stability/`
  - scale: `ID train=8000`, `ID eval=4000`, `OOD eval=8000`, `attack eval=12000`
  - objects: `dA`, `strongest_candidate_transformer_covreg_v2_seed101`, `ft_transformer_ae`
  - policy family unchanged: `fixed_id_q99`, `naive_calibrated_budget5000_target1pct`, `det_floor_50pct_min_alarm`
- Ran engineering/protocol gate on this run:
  - `runs/second_environment_toniot_object_prerun_2026-04-21_stability/engineering_gate/`
  - verdict: `engineering_gate_pass`

Result:
- Gate status:
  - split checks pass;
  - output matrix and policy checks pass;
  - finite-value checks pass;
  - non-finite replacement count remains `0`.
- Stability signal versus prior same-scale run (`..._2026-04-20_b`):
  - `dA` is exactly reproducible across all three policies (same metrics to 6 decimals).
  - `strongest_candidate` still weak at fixed point:
    - fixed: `ood_alarm=0.002125`, `attack_det=0.003333`, `auc=0.690065`
  - `ft_transformer_ae` still fails fixed point:
    - fixed: `ood_alarm=0.000000`, `attack_det=0.000000`, `auc=0.570755`
  - `ft_transformer_ae` naive point improved in detection:
    - naive: `ood_alarm=0.009250`, `attack_det=0.126000`
    - but `id_alarm=0.395250`, still not deployment-credible.
- The stdout warning string from backend (`NaN/Inf detected in execute score`) still appeared once during strongest attack scoring, but run-level diagnostic counters remained finite-clean after replacement guard (`nonfinite_total=0` in gate report).

Judgment:
- Engineering and protocol explanations are now largely ruled out for this stage.
- Under fixed `q99`, both `strongest_candidate` and `FT` remain clearly below `dA` on TON second-environment split.
- This is now a stable method-performance gap, not an unstable pipeline artifact.

Next:
- Keep TON second-environment line in local method-diagnosis mode (no formal HPC yet).
- Prioritize strongest-candidate execute-path numerical diagnosis (source of one-off backend warning) and low-alarm detection recovery.
- If next controlled method iteration still cannot beat the `dA` fixed operating point, lock this as stable negative external-validation evidence and stop expanding this branch.

### 2026-04-21 (Threshold Sensitivity + Coupling Verification)

What was done:
- Added and ran threshold-sensitivity audit:
  - script: `repo/ood/second_environment_toniot_threshold_sensitivity.py`
  - run: `runs/second_environment_toniot_threshold_sensitivity_2026-04-21/`
  - audited dimensions:
    - score orientation (`raw_score` vs `neg_raw_score`)
    - threshold operator (`>` vs `>=`)
    - policies (`fixed_id_q99`, `naive_calibrated_budget5000_target1pct`)
- Added and ran model-expression coupling probe:
  - script: `repo/ood/second_environment_toniot_coupling_probe.py`
  - run: `runs/second_environment_toniot_coupling_probe_2026-04-21/`
  - fixed split scale: `ID train=4000`, `ID eval=2000`, `OOD eval=5000`, `attack eval=5000`
  - models: `dA`, `ft_transformer_ae`
  - expression views:
    - `standard_zscore`
    - `winsor_zscore`
    - `signed_log1p_zscore`

Result:
- Threshold sensitivity on the stability source run confirms the `FT fixed=0` observation is not a simple comparator bug:
  - chosen orientation is `neg_raw_score`;
  - under chosen orientation:
    - `fixed_id_q99`: `attack_det=0.000000` for both `>` and `>=`;
    - changing `>` to `>=` does not recover attack detection.
- FT tie profile shows substantial threshold ties on ID at chosen orientation (`eq@q99 ≈ 0.19075`), which affects ID alarm accounting but does not explain attack detection being zero.
- Coupling probe shows strong expression sensitivity:
  - `FT` fixed point:
    - `standard_zscore`: `ood_alarm=0.0000`, `attack_det=0.0000`
    - `winsor_zscore`: `ood_alarm=0.0000`, `attack_det=0.0102`
    - `signed_log1p_zscore`: `ood_alarm=0.0990`, `attack_det=0.1452`
- Interpretation:
  - `FT` detection collapse is real under current chosen orientation + standard expression, not just an operator artifact;
  - expression change can recover some detection, but currently with unacceptable OOD alarm inflation at fixed point.

Judgment:
- The new evidence supports “model + front-expression coupling” as a real factor.
- This line is still not ready for formal HPC promotion because recovered detection has not yet met low-alarm operating requirements.

Next:
- Superseded by the 2026-04-22 failure-closure decision below.
- Do not continue TON/BoT second-environment tuning under the current A-line protocol.

### 2026-04-22 (A-line Second-Environment Failure Closure + Original100 Few-Shot Official Control)

#### Task 1: A-line second-environment failure closure

Updated project-level judgment:
- BoT-IoT / TON-IoT second-environment work is no longer an active strengthening or rescue line.
- This line is now formally sealed as negative evidence, limitation, and external-validity boundary for the current mainline formal protocol.
- No further second-environment expansion, rerun, or tuning should be started under the current A-line protocol unless a future project-level decision explicitly opens a new dated protocol.

Failure ruling:
- BoT-IoT does not support formal mainline use under the current split requirements because available benign support is too small for the required ID/OOD/calibration/eval protocol; it remains a split-feasibility failure, not a main-evidence run.
- TON-IoT passed engineering/protocol gates but does not support the current mainline model claims:
  - `dA` fixed reference remains weak but nonzero (`AUC=0.679894`, `attack_det=0.076667` on the same-scale stability run).
  - `strongest_candidate_transformer_covreg_v2_seed101` fixed point remains nearly non-detecting (`attack_det=0.003333`, `AUC=0.690065`).
  - `ft_transformer_ae` fixed point remains non-detecting (`attack_det=0.000000`, `AUC=0.570755`).
- Threshold-sensitivity and coupling probes ruled out a simple comparator/threshold artifact for the FT zero-detection point; expression changes can recover some detection but not a deployable low-alarm result.

How to use this in the paper:
- Use as negative evidence and limitation: the current formal protocol does not robustly externalize to the tested second environments.
- Use as external-validity boundary: second-environment results are not part of the positive main evidence.
- Do not frame BoT-IoT / TON-IoT as ongoing evidence strengthening or as a line still being optimized.

#### Task 2: Original100 few-shot official control package

What was done:
- Added mainline official control script:
  - `repo/ood/original100_fewshot_official_control.py`
- Ran local official control package:
  - `runs/original100_fewshot_official_control_2026-04-22/`

Protocol:
- Task type: few-shot / supervised target-aligned detector, not unsupervised anomaly scoring.
- Model: L2 `LogisticRegression`, `class_weight=balanced`, `C=1.0`, `solver=liblinear`.
- Input representation: original frontend flat 100D.
- Labels:
  - negatives = ID benign train rows + OOD benign train rows;
  - positives = seeded few-shot samples from stage2 high-purity attack train split.
- Budgets and seeds:
  - budgets: `16`, `32`;
  - positive sample seeds: `42,43,44,45,46`.
- Fairness:
  - final OOD eval is never used for threshold selection;
  - positive sampling is multi-seed;
  - summary reports mean/min/max.
- Operating points:
  - `fixed_id_calib_q99`;
  - `guarded_id_calib_and_ood_val_target1pct`.
- Boundary:
  - `original100_fewshot_logistic` is the official control group;
  - `da_unsupervised_score_seed42` is only a reference baseline and is not in the same label-information setting;
  - no source-rich win/loss conclusion is made in this mainline control package.

Integrity check:
- Required package files present:
  - `command.txt`
  - `config.json`
  - `run_spec.json`
  - `official_control_manifest.json`
  - `diagnostics.json`
  - `results.csv`
  - `original100_fewshot_official_control_summary.csv`
  - `original100_fewshot_official_control_focus.csv`
  - `summary.md`
  - `stdout.log`
  - `stderr.log`
- `results.csv`: 22 rows.
- `summary`: 6 aggregate rows.

Key control results:
- `original100_fewshot_logistic`, 16-shot, fixed ID q99:
  - `AUC mean/min/max = 0.990672 / 0.958007 / 0.999974`
  - `OOD alarm mean/min/max = 0.004500 / 0.001200 / 0.009500`
  - `attack det mean/min/max = 0.967564 / 0.914182 / 0.999273`
  - `feasible_rate = 1.000000`
- `original100_fewshot_logistic`, 16-shot, guarded:
  - `AUC mean/min/max = 0.990672 / 0.958007 / 0.999974`
  - `OOD alarm mean/min/max = 0.004440 / 0.001200 / 0.009200`
  - `attack det mean/min/max = 0.967564 / 0.914182 / 0.999273`
  - `feasible_rate = 1.000000`
- `original100_fewshot_logistic`, 32-shot, fixed ID q99:
  - `AUC mean/min/max = 0.984615 / 0.967632 / 0.999910`
  - `OOD alarm mean/min/max = 0.006520 / 0.003600 / 0.009800`
  - `attack det mean/min/max = 0.940655 / 0.920727 / 0.999273`
  - `feasible_rate = 1.000000`
- `original100_fewshot_logistic`, 32-shot, guarded:
  - `AUC mean/min/max = 0.984615 / 0.967632 / 0.999910`
  - `OOD alarm mean/min/max = 0.006520 / 0.003600 / 0.009800`
  - `attack det mean/min/max = 0.940655 / 0.920727 / 0.999273`
  - `feasible_rate = 1.000000`
- `dA` unsupervised reference:
  - fixed ID q99: `AUC=0.806365`, `OOD alarm=0.128600`, `attack det=0.686545`, `feasible_rate=0.000000`
  - guarded: `AUC=0.806365`, `OOD alarm=0.010800`, `attack det=0.002909`, `feasible_rate=0.000000`

Current next:
- Treat second-environment as closed negative evidence unless the project opens a new protocol.
- Treat the original100 few-shot package as the mainline official control group for the v7 target-aligned methodology port.
- Commit/push the script plus mainline doc updates; keep generated run artifacts local unless explicitly requested otherwise because `/runs/*` is ignored except the two mainline docs.

### 2026-05-08 (Strategy Update: From LR Replacement to Base-Detector-Agnostic Guarded Few-Shot Adaptation)

What was done:
- Recorded a strategy update only. No experiment was started, no model was trained, and the manuscript was not modified.
- Added the interpretation of `runs/issue02_original_da_normal_attack_sanity_run_2026-05-08/` into the mainline handoff.
- Reframed the next candidate direction as base-detector-agnostic guarded few-shot adaptation rather than "replace dA with few-shot LR".

Key evidence added:
- `issue02_original_da_normal_attack_sanity_run_2026-05-08/` uses clean115 original normal-vs-attack data:
  - rows: `200000`
  - feature_dim: `115`
  - benign rows: `121621`
  - attack rows: `78379`
- dA in the original normal-vs-attack setting is strong:
  - ROC-AUC `0.9340`
  - PR-AUC `0.9487`
  - benign-calibration q99 attack detection `0.8642`
  - benign eval false alarm `0.0107`
- few-shot LR on the same original setting is seed-sensitive:
  - 16-shot q99 AUC mean/min/max `0.6944 / 0.0777 / 0.9292`
  - 16-shot q99 detection mean/min/max `0.6249 / 0.0112 / 0.8648`
  - 32-shot q99 AUC mean/min/max `0.6085 / 0.1113 / 0.9312`
  - 32-shot q99 detection mean/min/max `0.5320 / 0.0316 / 0.8655`

Judgment:
- dA is not invalidated as a detector. It remains a classic lightweight cold-start unsupervised detector.
- The low-OOD collapse evidence should be interpreted as a deployment working-point problem under benign OOD and strict low-OOD-alarm constraints, not as proof that dA lacks normal-vs-attack detection ability.
- L2 `LogisticRegression` remains the minimal target-alignment baseline. It should not be written as a universal replacement for dA or as the final adapter architecture.
- The next method framing should be candidate-level only:
  - base detectors may include dA as a classic lightweight detector and Transformer as a modern contextual detector;
  - few-shot adapters use high-purity attack positives plus ID/OOD benign negatives to learn an attack-oriented score;
  - the guarded low-OOD-alarm threshold remains the deployment operating point.

Candidate next-phase names:
- `Guarded Few-shot Adapter (GFA)`
- `Base-Detector-Agnostic Guarded Few-shot Adapter`
- `Guarded Deviation Adapter (GDA)`

Candidate adapter inputs:
- base representation, such as `original100` or a future Transformer hidden representation;
- base detector score, such as dA RMSE or Transformer anomaly score;
- few-shot high-purity attack positives;
- ID benign + OOD benign negatives.

Candidate adapter output:
- an attack-oriented score evaluated under `guarded_id_calib_and_ood_val_target1pct`;
- final OOD eval and attack eval remain held out from threshold/model selection.

Transformer evidence status:
- A repository search did not find a formal ordinary normal-vs-attack result proving that Transformer is stronger than dA.
- Found assets are weaker or different in scope:
  - clean115 `trans115_min` / `da115_min` are ID-only minimal checks, not normal-vs-attack evidence;
  - stronger-OOD Transformer/FT/ensemble results are operating-point evidence, not ordinary closed-set normal-vs-attack proof.
- Therefore the Transformer role is currently `needs evidence retrieval`, not a completed claim.

Boundary:
- Do not write "few-shot LR replaces dA".
- Do not write "GFA/GDA is proven".
- Do not write "Transformer-assisted adapter is effective" until a same-protocol experiment exists.
- Do not move this strategy update into the manuscript as a claim without a future evidence package.

Next:
- First retrieve or construct a clean Transformer ordinary-setting evidence inventory.
- Then run a base-detector adapter feasibility inventory.
- Only after those gates decide whether to start a formal GFA/GDA experiment.

### 2026-05-17 Strategy Update: Problem-Driven Reframing after 2022–2026 Frontier Survey

Source report received and accepted:

- `D:\study\paper\anomaly_detection\paper04\worktrees\gpt deep\22年-26年问题定义报告.md`
- SHA-256: `d7d8649029a2bae5a5cdc6f4ca9ea07a3ea4256391d21d8cabc1345e8940c4f9`

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

## issue27g suspicious perfect score audit (2026-05-27)

- primary_verdict: `lowguard_plus_plus_formal_result_passes_anomaly_audit`
- audited result: issue27f LOW-GUARD++ `original100 + HistGB-Conservative` reported `1.000000 / 1.000000 / 0.000100`.
- scope: final-eval usage, split/sample identity, original100 leakage screening, score distribution, negative controls, scratch recompute, and artifact/cache audit.
- claim boundary: do not use 27f as a broad LOW-GUARD claim; keep it bounded to tested representation/head/protocol and keep temporal/cross-dataset/deployment robustness unclaimed. Because original100 has high-cardinality near-perfect separator features, add feature-provenance evidence before strong main-text upgrading.
- next action: `issue27h_original100_feature_provenance_and_independent_verification_before_claim_upgrade`.

## issue27h feature provenance claim gate (2026-05-27)

- primary_verdict: `lowguard_plus_plus_depends_on_high_risk_separators`
- scope: maps the three original100 high-cardinality near-perfect separators, audits split distributions, runs frozen-config feature ablations, performs report-only non-locked consistency checks, and explains HistGB feature reliance.
- claim boundary: LOW-GUARD++ can remain an audited locked result, but broad/main-text performance-instance upgrading still needs clean independent validation or stronger original100 provenance.
- next action: `issue27i_separator_dependency_deeper_audit_or_demote_lowguard_plus_plus`.

## issue27i separator validation feasibility (2026-05-27)

- primary_verdict: `lowguard_plus_plus_promising_needs_clean_independent_validation`
- scope: inventories clean independent assets, checks HH separator stability on non-locked consistency objects, reports frozen LOW-GUARD++ outside locked bins, evaluates safer feature variants without tuning, and plans data expansion.
- claim boundary: LOW-GUARD++ is not abandoned, but cannot be upgraded to main-text performance instance until clean independent validation or raw provenance resolves separator dependency.
- next action: `issue27j_raw_provenance_recovery_and_clean_independent_split_construction`.

## issue27j raw provenance and clean split audit (2026-05-27)

- primary_verdict: `clean_independent_validation_blocked_but_recoverable`
- scope: recovers raw pcap/TSV/source-code provenance for original100, audits HH separator lineage, checks clean split feasibility, and blocks formal clean validation until a row-level clean split is built.
- claim boundary: LOW-GUARD++ remains a high-potential candidate; current evidence does not justify main-text performance-instance upgrade without clean independent validation.
- next action: `issue27k_row_level_original100_rebuild_and_purged_split_construction`.

## issue27k row-level original100 rebuild and purged split construction (2026-05-27)

- primary_verdict: `row_manifest_recovered_but_clean_split_blocked`
- scope: builds row-level sidecar provenance for ID/OOD/attack original100 assets, verifies source-vs-extracted feature alignment, and designs purged split candidates.
- claim boundary: row provenance is recovered, but clean/purged LOW-GUARD++ validation remains blocked until split-aware feature rebuild and sufficient independent eval assets exist.
- next action: `issue27l_split_aware_original100_rebuild_with_sufficient_clean_eval_asset`.

## issue27l clean eval asset and split-aware rebuild gate (2026-05-27)

- primary_verdict: `clean_eval_asset_found_rebuild_eval_next`
- scope: searches sufficient clean eval assets, identifies full Mirai/Botnet labeled datasets plus the extended unused-segment candidate, and blocks evaluation until feature compatibility, prior-use audit, and split-aware rebuild are resolved.
- claim boundary: LOW-GUARD++ remains high-potential, but still cannot be upgraded to a main-text performance instance.
- next action: `issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild`.

## issue27m full Mirai compatibility audit (2026-05-27)

- primary_verdict: `full_mirai_incompatible_needs_new_frontend_path`
- scope: audited full Mirai/Botnet asset identity, feature schema compatibility, prior-use risk, split feasibility, and split-aware rebuild feasibility before any LOW-GUARD++ score run.
- key result: full Mirai is a large labeled asset (`764137` rows; benign `121621`, attack `642516`), but it is `dirty116`/`clean115-restored115` style rather than the current frozen `original100` LOW-GUARD++ input.
- claim boundary: no full Mirai LOW-GUARD++ validation was run; clean115/restored115 must not be mixed with the frozen original100 claim.
- next action: `issue27n_full_mirai_restored115_feature_mapping_and_lowguardpp_interface_smoke` or, if original100 must be preserved, full Mirai original100 frontend re-extraction.

## issue27n full Mirai restored115 mapping gate (2026-05-27)

- primary_verdict: `restored115_feature_mapping_blocked`
- scope: audits dirty116-to-clean115 construction, restored115 feature mapping, historical prior-use isolation, clean115 split proposal, and LOW-GUARD interface-smoke gates.
- key result: clean115 can be defined by dropping the index-like col0, but restored115 feature names/order remain unverified and historical `my_gold` overlap contains all benign rows.
- claim boundary: no restored115 LOW-GUARD++ smoke or formal full Mirai validation was run; clean115/restored115 remains a separate candidate input track, not the frozen original100 claim.
- next action: `issue27o_restored115_mapping_recovery_or_original100_reextraction_for_full_mirai`.

## issue27o full Mirai protocol reset spec (2026-05-27)

- primary_verdict: `full_mirai_protocol_reset_ready_with_anonymous_clean115`
- scope: redefines issue20-27n as exploration, adopts full Mirai as a protocol-reset within-dataset benchmark, writes split/fairness/feature-study contracts, and runs a small anonymous-clean115 interface smoke.
- key boundary: full Mirai is not a completely unseen external test; restored115/common100 mapping remains low confidence; all baselines must be rerun under the reset protocol.
- next action: `issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution`.

## issue27p full Mirai anonymous clean115 formal benchmark execution (2026-05-27)

- primary_verdict: `baseline_dominates_needs_method_rethink`
- scope: executes the full Mirai protocol-reset benchmark on `anonymous_clean115_all` with fixed split, train/validation-only selection, and report-only final eval.
- baseline rerun status: complete for planned local reset methods; old issue20-27n numbers remain exploratory.
- current benchmark leader by feasibility-first ranking: `DeepSADStyle_Lite`.
- claim boundary: this is within-dataset protocol-reset evidence, not external generalization and not restored115/original100 evidence.
- next action: `issue27q_protocol_reset_result_audit_and_seed_expansion`.

## issue27q plan for protocol reset audit (2026-05-27)

- primary_verdict: `issue27q_execution_plan_ready`
- scope: plan-only audit package for DeepSADStyle_Lite, LOW-GUARD++ reset-protocol failure, and paired LOW-GUARD protocol universality.
- key boundary: issue27p changes the mainline question but does not yet make DeepSADStyle_Lite claim-safe or permanently demote LOW-GUARD++.
- next action: execute P0/P1 DeepSAD audit, then LOW-GUARD++ failure diagnosis and paired universality matrix.

## issue27q P0P1 DeepSAD-lite audit and seed expansion (2026-05-27)

- primary_verdict: `deepsad_lite_result_suspicious_needs_artifact_debug`
- scope: audits DeepSADStyle_Lite replay, score direction, split separation, negative controls, feature artifacts, seed expansion, and stratified behavior.
- claim boundary: DeepSADStyle_Lite remains a weighted-center lite candidate under anonymous clean115, not exact Deep SAD and not external generalization.
- next action: `issue27r_deepsad_lite_artifact_debug_and_feature_provenance`.

<!-- issue27r_semantic_validity_audit -->

## issue27r Benchmark Semantic Validity Gate

- primary_verdict: `attack_benign_artifact_risk`.
- ID/OOD drift is distinguishable but row-order/distributional, not temporal/capture/deployment drift.
- OOD benign labels are pure by sidecar, but deployment semantics are weak without timestamp/capture/session metadata.
- attack/benign semantics are blocked by high artifact risk: benign prefix, attack suffix, anonymous features, no source/capture provenance.
- anonymous_clean115 remains diagnostic only for protocol reset; it is not restored115/original100/common100.
- issue27p model rankings are diagnostic only and should not drive mainline claims until raw provenance or second-dataset semantic validation passes.
- next: `issue27s_raw_provenance_or_second_dataset_semantic_reconstruction_for_low_ood_alert_benchmark`.

<!-- issue27s_raw_provenance_or_second_dataset -->

## issue27s Raw Provenance Or Second Dataset Decision

- primary_verdict: `dual_track_raw_rebuild_and_second_dataset_intake`.
- issue27r data semantics gate did not pass for full Mirai anonymous_clean115.
- full Mirai paired raw pcap/input stream was not found; local pcaps are unrelated IoT23/public_data assets.
- full 764k timestamp/capture/session provenance is missing; `mirai3_ts.csv` is only a smaller related path.
- current full Mirai anonymous_clean115 is diagnostic only, not main low-OOD-alert benchmark.
- model experiments remain blocked by Data validity gate.
- next: dual-track full Mirai raw provenance search plus second-dataset semantic intake.

<!-- issue27t_second_dataset_intake -->

## issue27t Second Dataset Intake

- primary_verdict: `second_dataset_candidates_need_manual_access_or_download_confirmation`.
- full Mirai paired raw missing is confirmed; full Mirai anonymous_clean115 remains diagnostic only.
- current model experiments remain blocked by Data validity gate.
- recommended candidates: Gotham Dataset 2025 first, ToN-IoT network second; local IoT-23 is auxiliary for semantic-gate rehearsal.
- all future downloads must use `D:\study\paper\anomaly_detection\paper04\datasets\<dataset_name>\...`; do not stage raw/large data.
- next: `issue27u_gotham_metadata_intake_and_data_gate_precheck`.

<!-- issue27u_gotham_metadata_intake -->

## issue27u Gotham Metadata Intake

- primary_verdict: `gotham_ready_for_full_download_with_user_confirmation`.
- Gotham metadata reports raw PCAP, processed CSV, metadata with timestamps/attacker IPs/attack types, device-level traces from 78 heterogeneous IoT devices, and deterministic labels.
- Zenodo exposes a single `23.825GB decimal / 22.189GiB` zip; no large download was performed.
- model experiments remain blocked by Data validity gate.
- next: user-confirmed Gotham download and file-level Data Gate, or ToN-IoT metadata intake if Gotham is blocked.

<!-- issue27v_gotham_file_level_data_gate -->

## issue27v Gotham Download And File-Level Data Gate

- primary_verdict: `gotham_file_level_gate_passed_ready_for_sample_data_gate`.
- storage_preflight_verdict: `pass_user_approved_download_only`; user approved download-only mode below the original 80GB safety recommendation.
- planned data path: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025`; raw zip target `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\raw\GothamDataset2025.zip`.
- Gotham zip was downloaded/resumed to the approved D: dataset path and verified with expected md5 `7ca78c0517ccb3d2854e823678e0f206`; local sha256 is recorded in issue27v outputs.
- Archive listing passed with no unsafe paths; it contains `110` PCAP files and `78` processed CSV files. CSV previews show a `label` column and `frame.time` timestamp, while device/source/capture information is partial via README, filenames, packet fields, and directory structure rather than a separate metadata JSON sidecar.
- model experiments remain blocked; this issue is not evidence for or against Gotham's semantic suitability.
- next: `issue27w_gotham_sample_data_gate`; do small sample-level validation only, with no full PCAP extraction or model execution.

<!-- issue27w_gotham_sample_data_gate -->

## issue27w Gotham Sample Data Gate

- primary_verdict: `gotham_sample_gate_promising_needs_more_space_and_larger_sample`.
- sample gate read selected processed CSVs from the zip stream and wrote only first-1000-row previews under the external dataset directory; no PCAP or full large CSV extraction was performed.
- labels, `frame.time`, packet fields, device/file names, and matching PCAP paths are usable at sample level.
- most promising split is device-disjoint benign drift, with protocol-disjoint as a secondary route.
- largest artifact risk is label/source/time coupling, especially benign-prefix then attack-label structure in mixed attack files.
- model experiments remain blocked; next is a larger sample manifest and split gate.

<!-- issue27x_gotham_larger_sample_gate -->

## issue27x Gotham Larger Sample Manifest And Split Gate

- primary_verdict: `gotham_larger_sample_promising_needs_full_manifest`.
- allowed mode was `limited_csv_extract`, but execution used streaming sampled manifest construction and did not extract PCAP or full large CSV files.
- sampled row-level manifest was built across representative benign and mixed attack processed CSVs; PCAP/CSV pairing is medium-confidence by filename/path matching.
- most promising split remains device-disjoint benign drift; protocol-disjoint is a secondary route.
- largest blocker is file/device/time shortcut risk; Gotham is not yet ready for Feature/interface gate or model experiments.
- next: fuller manifest and pre-registered split contract.

<!-- issue27y_gotham_preregistered_data_contract -->

## issue27y Gotham Fuller Manifest And Preregistered Data Contract

- primary_verdict: `gotham_data_contract_promising_needs_feature_pairing_or_full_manifest`.
- all 78 processed CSVs were summarized from the zip stream; sampled row manifest has `13,372` rows.
- best split-contract candidate is `gotham_device_disjoint_v1`; it can construct ID benign train, OOD benign validation, final OOD benign eval, and file-level disjoint attack support/eval.
- size adequacy is promising for the primary contract, but PCAP/CSV pairing remains medium-confidence filename/path matching and source-identifier feature policy is not yet defined.
- artifact risk remains material, especially label/file/device/protocol coupling; model experiments remain blocked.
- next: issue27z should strengthen PCAP/CSV pairing and define IP/MAC/port/timestamp/source handling before Feature/interface gate.


<!-- issue27z_gotham_pairing_source_policy_gate -->

## issue27z Gotham Pairing And Source Policy Gate

- primary_verdict: `gotham_ready_for_feature_interface_diagnostic_only`.
- readiness_verdict: `ready_for_feature_interface_diagnostic_only`.
- PCAP/CSV pairing status: {'medium_filename_path_match': 74, 'high_packet_count_timestamp_match': 1, 'medium_plus_frame_timestamp_hint': 3} after streaming PCAP metadata from the zip; no PCAP extraction or feature extraction was performed.
- source policy status: `gotham_feature_source_policy_v1` defined; labels, file/device/source/path, IP/MAC, and absolute timestamps are forbidden from main model inputs.
- ports/protocol fields are diagnostic-only until a later shortcut audit.
- current model experiments remain blocked; next action is Feature/interface gate work only.


<!-- issue27aa_gotham_strict_packet_dataset -->

## issue27aa Gotham Strict Packet Dataset Materialization

- primary_verdict: `gotham_strict_feature_dataset_ready_for_model_interface_smoke`.
- Materialized `gotham_strict_packet_header_v1` with 26736743 rows outside the git worktree under `datasets/gotham2025/derived/strict_packet_feature_dataset_v1/`.
- Feature matrix excludes labels, file/source/device/path, timestamps, IP/MAC, ports, and protocol fields.
- Split roles are frozen from `gotham_device_disjoint_v1`; final eval remains report-only.
- Model experiments remain blocked; next is interface smoke only.

## issue27ab Gotham Kitsune115 frontend feasibility (2026-06-01)

- primary_verdict: `kitsune115_blocked_by_pcap_label_alignment`
- scope: restores the commented Kitsune Host BW H-stat block as an explicit 115D frontend smoke, reads selected Gotham raw PCAPs from the zip, and audits split-aware frontend state behavior.
- key result: the formal route is now Gotham raw PCAP -> Kitsune/AfterImage/netStat 115D, while the strict 8D packet-header asset is downgraded to engineering smoke/provenance proof.
- state policy: compares reset-at-boundary with branch-based train-state-then-eval-online; final OOD eval is report-only and discarded.
- current model experiments allowed: no formal benchmark yet; next is issue27ac attack-onset alignment before broader 115D materialization.

<!-- issue27ac_gotham_attack_onset_alignment -->

## issue27ac Gotham Kitsune115 Attack-Onset Alignment

- primary_verdict: `attack_onset_alignment_partial_ready_for_kitsune115_smoke_expansion`.
- role: attack-side data/feature gate for Gotham Kitsune115.
- result: first-attack timestamps from processed CSVs can select causal malicious PCAP windows for support/eval smoke; support must start after confirmed attack onset.
- caveat: 6/8 attack contract CSVs aligned within the current scan budget; two ip-camera attack files still need deeper onset scan before full-contract materialization.
- model experiments remain blocked; next is a larger onset-aligned Kitsune115 smoke dataset plus unresolved attack-file deep scan.

<!-- issue27ad_gotham_kitsune115_smoke_expansion -->

## issue27ad Gotham Kitsune115 Split-Aware Smoke Expansion

- primary_verdict: `kitsune115_split_aware_smoke_dataset_ready_heavy_attack_deferred`.
- ID/OOD/final OOD use only preregistered benign split files; attack files are used only after confirmed attack onset.
- both reset-at-boundary and train-state-then-eval-online strategies output 115D finite features; no model metrics were computed.
- all 8 attack files have onset alignment, but 2 ip-camera files are deferred from local materialization because their pre-onset fast-forward is heavy.
- model experiments remain blocked unless explicitly limited to interface shape smoke.

<!-- issue27ae_gotham_kitsune115_interface_shape_smoke -->

## issue27ae Gotham Kitsune115 Model Interface Shape Smoke

- primary_verdict: `kitsune115_model_interface_smoke_passed`.
- fixed issue27ad artifacts only; no resplit, support change, thresholding, ranking, or performance metric.
- LR, HistGB, DeepSAD-style Lite, and LOW-GUARD shell adapters passed shape/finite interface checks.
- next: larger 115D materialization or fast frontend before formal benchmark.

<!-- issue27af_gotham_kitsune115_medium_materialization -->

## issue27af Gotham Kitsune115 Medium Materialization

- primary_verdict: `kitsune115_medium_materialization_ready_full_needs_slurm`.
- medium materialization executed for scalability/stability/hash/sidecar/state checks; it is not formal benchmark data.
- full_contract still needs Slurm/fast frontend for heavy ip-camera attack files.
- no model performance metrics were computed.

<!-- issue27ag_gotham_kitsune115_larger_asset_sanity -->

## issue27ag Gotham Kitsune115 Larger Asset Interface Sanity

- primary_verdict: `kitsune115_larger_asset_ready_with_full_contract_pending`.
- immutable loader verifies issue27af medium certificate hashes and role access policy.
- final OOD eval and attack eval remain report-only and selection-forbidden.
- full_contract remains pending for heavy ip-camera files; no model performance metrics were computed.

<!-- issue27ah_gotham_kitsune115_guarded_protocol_dry_run -->

## issue27ah Gotham Kitsune115 Guarded Protocol Dry Run

- primary_verdict: `guarded_protocol_medium_dry_run_completed_diagnostic_only`.
- medium 115D asset was used only for diagnostic guarded-protocol behavior checks.
- final OOD benign eval and attack eval remained report-only and were not used for thresholding or selection.
- full_contract remains pending; issue27ah results are not formal model rankings.

<!-- issue27ai_medium_protocol_audit_then_diagnostic -->

## issue27ai Medium Protocol Audit Then Diagnostic

- primary_verdict: `medium_protocol_audit_passed_diagnostic_completed`.
- A protocol correctness audit gates B diagnostic execution.
- support size fixed to `32` from preregistered attack_support role; no final eval or attack eval selection.
- output is medium diagnostic only; formal benchmark still requires full_contract or an exclusion policy and protocol freeze.

## issue27aj - Protocol Lineage Recovery And Support Selector Audit

- Status: completed.
- Primary verdict: `recovered_kcenter_mainline_protocol_ready_for_gotham115_migration`.
- Key recovery: old mainline support selector is `kcenter32`, not issue27ai
  `fixed_first32`.
- Evidence: issue23 locked validation and issue25c strong baseline pack name
  the main candidate as `selected_source_rich_top64 + kcenter32 + fixed OOD
  guard LR`; executable code calls `issue19b.kcenter_support(...)` on the
  train-side attack pool only.
- Selector mechanics: selector-local `StandardScaler`, Euclidean farthest-first
  k-center, budget 32, no attack eval or final OOD eval access.
- Gotham migration: migrate selector/protocol permissions only to Gotham
  Kitsune115 medium diagnostics; do not migrate old frontend or old performance
  claims.
- Next: `issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic`.

<!-- issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic -->

## issue27ak Recovered Kcenter32 Gotham115 Medium Diagnostic

- primary_verdict: `recovered_kcenter32_medium_diagnostic_completed`.
- Migrates recovered historical `kcenter32` support selector to the fixed Gotham Kitsune115 medium asset.
- support size fixed to `32` from preregistered attack_support role; no final eval or attack eval selection.
- output is medium diagnostic only; formal benchmark still requires full_contract or an exclusion policy and protocol freeze.

<!-- issue27am -->
## issue27am_medium_bounded_protocol_repair_validation_2026-06-03

- primary_verdict: `medium_repair_insufficient_pause_feature_state_onset_audit`
- Medium Gotham Kitsune115 bounded protocol repair validation only; not formal benchmark.
- Tested fixed split/support pool with kcenter32, stratified_kcenter64, and stratified_kcenter128 plus support_val/NP threshold rules.
- Final OOD and attack eval remain report-only; no model ranking or full benchmark claim is made.
- next action: `issue27an_feature_state_onset_or_protocol_repair_reassessment`

<!-- issue27an -->
## issue27an_gotham_kitsune115_feature_state_onset_label_alignment_audit_2026-06-03

- primary_verdict: `support_eval_distribution_mismatch_blocker_found`
- Failure attribution audit after issue27am; no new model training or protocol repair.
- Audited feature separability, onset/label density, state/warmup/carryover, support/eval coverage, and label semantics.
- next action: `issue27ao_repair_support_eval_contract_before_head_repair`

<!-- issue27ao -->
## issue27ao_repair_support_eval_contract_v2_before_head_repair_2026-06-03

- primary_verdict: `contract_v2_ready_for_medium_detection_retest`
- Support/eval contract v2 validation only; no model training.
- Benign split and Kitsune115 frontend unchanged.
- Previous medium attack_eval is consumed for diagnostic contract design, so follow-up retest remains diagnostic only.
- next action: `issue27ap_medium_detection_retest_on_contract_v2_diagnostic_only`

<!-- issue27ap -->
## issue27ap_new_heldout_attack_probe_and_v2_diagnostic_retest_2026-06-03

- primary_verdict: `new_heldout_v2_diagnostic_signal_weak_support_shift_persists`
- Newly materialized held-out heavy ip-camera attack probe; support fixed from issue27ao v2.
- Diagnostic only; not formal benchmark.

<!-- issue27aq -->
## issue27aq - Model learning and domain gap audit after new heldout zero detection

- primary_verdict: `zero_detection_due_to_ood_tail_threshold_overconservative_despite_raw_support_signal`
- Scope: diagnosis only; no support rebuild, no protocol repair, no formal benchmark.
- support_val detection at issue27ap threshold max: `0.000000`; new heldout detection max: `0.000000`.
- raw support score signal exists, but the OOD-tail threshold is above support and heldout scores.
- next action: `issue27ar_balanced_fit_and_threshold_debug_without_final_eval`.

<!-- issue27ar -->
## issue27ar - Old LOW-GUARD++ protocol fidelity on Gotham115 medium

- primary_verdict: `old_protocol_fidelity_mixed_needs_bounded_calibration_repair`
- Migrated issue27f HistGB frozen B protocol skeleton to Gotham Kitsune115 medium.
- Uses old kcenter32, old HistGB config, OOD train guard, sample weights, and guarded ID/OOD threshold.
- Diagnostic only; final OOD, attack_eval, and new heldout remain report-only.

<!-- issue27as -->
## issue27as - Bounded old-protocol calibration and coverage repair

- primary_verdict: `bounded_repair_suggests_feature_or_task_boundary`
- Medium diagnostic only; no formal benchmark.
- Keeps Gotham Kitsune115 medium frontend/split fixed and varies only bounded old HistGB weights, k-center budgets, and train-side threshold rules.
- Candidate selection uses id_calib, ood_val, and support_val only; final OOD, attack_eval, and new heldout remain report-only.

<!-- issue27at -->
## issue27at - Coverage hypothesis validation before protocol redesign

- primary_verdict: `coverage_hypothesis_partially_supported_needs_more_attack_pool`
- Diagnostic only; deterministic replay of issue27as selected candidate to compute per-sample coverage vs detection.
- New heldout remains report-only; final OOD tail risk is not resolved.

<!-- issue27au -->
## issue27au - Coverage-aware active labeling viability diagnostic

- primary_verdict: `active_labeling_viability_supported_but_ood_tail_blocked`
- Diagnostic only; previous new heldout probe is consumed as a development stream.
- Active selection is feature-only and prospective; final OOD remains report-only and not solved.

<!-- issue27av -->
## issue27av - Prototype-aware triage and OOD tail attribution

- primary_verdict: `ood_tail_needs_benign_prototype_veto`
- Diagnostic only; final OOD report-only attribution.
- Adds ID/OOD/attack prototype distance and score-margin analysis before OOD gate repair.

<!-- issue27aw -->
## issue27aw - OOD-safe gate repair diagnostic

- primary_verdict: `benign_veto_tradeoff_unresolved_ood_safe_but_attack_damaged`
- Diagnostic only; dev-selected margin gate preserves attack but does not fix final-OOD tail; fixed benign veto fixes OOD but damages attack.
- Current final OOD remains diagnostic-only; clean sealed-final replay is required before formal claims.

<!-- issue27ax -->
## issue27ax - Attack support bank detection recovery diagnostic

- primary_verdict: `support_bank_overfits_heavy_underrepresents_medium`
- Diagnostic only; tests retained-medium plus active-heavy support bank before OOD gate repair.
- No formal benchmark; final OOD not optimized.

<!-- issue27ay -->
## issue27ay - Region-aware attack bank and score gate diagnostic

- primary_verdict: `region_aware_attack_recovery_supported_ready_for_ood_gate`
- Diagnostic only; tests region weighting, per-region heads, and low-score attack-covered review routing.
- Final/report-only roles were not used for support, threshold, or model selection.
- Formal benchmark remains blocked until OOD-safe calibration and larger/full replay are ready.

<!-- issue27az -->
## issue27az - Region-aware attack-preserving OOD gate diagnostic

- primary_verdict: `needs_disjoint_ood_stress_pool_final_tail_uncovered`
- Diagnostic only; evaluates OOD-safe gates after region-aware heads.
- Final/report-only roles were not used for gate/radius/threshold selection.
- next action: `issue27ba_disjoint_ood_stress_pool_before_mixed_stream`.

<!-- issue27ba -->
## issue27ba - Disjoint OOD stress pool before mixed stream

- primary_verdict: `stress_gate_kills_attack_repair_needed`
- Diagnostic only; materializes a dev-side OOD stress pool from unused OOD-val benign files.
- Final OOD, attack eval, and dev-heavy query were not used for gate selection.
- next action: `issue27bb_attack_preserving_ood_gate_repair_on_disjoint_stress_pool`.

<!-- issue27bb -->
## issue27bb - Three prototype bank attack-preserving OOD gate

- primary_verdict: `three_bank_gate_still_kills_attack`
- Diagnostic only; adds ID/OOD/Attack prototype banks after raw attack score alarms.
- Final OOD, attack eval, and dev-heavy query were not used for prototype or gate selection.
- next action: `issue27bc_attack_core_and_review_cost_repair`.

<!-- model_protocol_open_problems_2026_06_05 -->
## Model / Protocol Open Problems Before Formal Benchmark

These are the current unresolved system problems. Do not treat any medium diagnostic result as a formal benchmark until these are resolved or explicitly bounded.

1. **Attack-preserving OOD gate remains unresolved.**
   - Solved so far: dev-side OOD stress can be materialized legally, and prototype gates can reduce OOD/stress hard alarms.
   - Still open: once OOD is suppressed, report-only attack hard detection still drops too much.
   - Next work must preserve strong attack-core alarms while suppressing only weak attack-score benign/OOD-like alarms.

2. **Attack region expansion is not scalable yet.**
   - Current diagnostics use separate medium/heavy heads as a proof of mechanism.
   - This cannot become `one new attack region -> one new model head` in the final system.
   - Needed: bounded region registry, top-k region routing, shared/global attack head or limited expert set, region prototypes, merge/split policy, and region-balanced weights.

3. **Support bank / attack-core generalization is insufficient.**
   - issue27bb shows support validation is strong, but report-only medium/heavy attack can still drop.
   - This means the support bank and attack-core definition are too close to support validation and not robust enough for broader attack evaluation.
   - Fix support-query gap before full/larger benchmark.

4. **Active labeling is still a dev-side oracle simulation.**
   - Current active labeling assumes a development stream where selected labels are available after query.
   - Real incoming traffic may be ID, OOD benign, attack, or noise.
   - Before system claims, run mixed-stream triage where feature-only routing decides hard/review/suppress/unknown before labels are revealed.

5. **Review / unknown cost must be bounded.**
   - Review cannot become a dumping ground for every difficult sample.
   - Every gate must report hard alarm, review, suppress, and unknown rates by role.
   - Review/unknown are safety states, not detection success.

6. **ID/OOD/Attack prototype banks need stable online policy.**
   - Prototype compression is required for real-time use; online detection cannot compare every sample to all ID/OOD/support rows.
   - Still open: prototype budget, radius source, top-k region routing, update cadence, and whether banks are rebuilt or incrementally updated.

7. **OOD stress coverage of final OOD tail is not fully settled.**
   - issue27ba created a legal OOD stress pool from unused OOD-val benign files.
   - Final OOD remains report-only and must not be used to tune gates.
   - If legal stress pools miss final OOD tails, broaden only from development-side benign/OOD sources.

8. **Training/sample-weight policy still needs freezing.**
   - ID/OOD data are much larger than attack support; support can be drowned out, but ID/OOD cannot be underlearned.
   - Freeze ID/OOD/support sampling, sample weights, region weights, and per-region balancing before formal benchmark.

9. **Online update policy is not frozen.**
   - The final system should not retrain for every new packet.
   - Define when support bank expands, when prototypes update, when region registry changes, and when detector/head retraining is allowed.

10. **Formal benchmark remains blocked.**
    - Required before formal benchmark: OOD hard <= 1%, high and stable attack hard detection, bounded review cost, scalable region handling, mixed-stream realism, and larger/full 115D data contract.

<!-- issue27bc -->
## issue27bc - Attack-core purity, unknown band, and review budget

- primary_verdict: `pseudo_query_reveals_support_core_overfit`
- Added file-held-out pseudo-query on dev attack support to reduce support-val overfitting.
- Added prototype purity states: hard_alarm, suppress, review_conflict, review_unknown, review_overflow_no_alarm.
- Key result: raw attack alarms remain high, but strict pure-attack-core hard alarms collapse to 0 because attack rows are also near benign/OOD prototypes and become conflict/overflow.
- Final OOD, medium attack eval, and dev-heavy query remained report-only.
- next action: `issue27bd_attack_region_generalization_before_temporal_gate`.

<!-- issue27bd -->
## issue27bd - Conflict-aware attack shell and gate subspace diagnostic

- primary_verdict: `subspace_conflict_gate_promising_attack_recovered_ood_relaxed`
- selected prototype gate subspace: `HH`; raw detector remains full Kitsune115.
- Added pseudo-query-calibrated outer attack shell and conflict-aware hard override.
- Final OOD, medium attack eval, and dev-heavy query remained report-only.
- next action: `issue27be_past_only_temporal_consistency_on_conflict_gate`.

<!-- issue27be -->
## issue27be - Past-only replay audit on conflict gate

- primary_verdict: `past_only_replay_passed_with_dev_pseudo_caveat_ready_for_attack_region_bank`
- purpose: replay the frozen issue27bd conflict-aware shell gate under role-access and past-only visibility audit.
- replay matches issue27bd metrics: `True`; forbidden role access: `False`.
- caveat: dev-side pseudo-query rows remain part of gate calibration, so this is diagnostic rather than formal.
- next action: `issue27bf_bounded_attack_region_bank`.

<!-- issue27bf -->
## issue27bf - Bounded attack region bank

- primary_verdict: `bounded_attack_bank_heavy_gain_medium_retention_failure`
- purpose: test a bank-only bounded attack region memory with top-k routing while preserving the issue27bd full-115D raw score.
- dev attack hard min: `0.6428571428571429`; report-only attack hard min: `0.6415`.
- OOD stress hard max: `0.002456140350877193`; final OOD hard max report-only: `0.154`.
- attack >=0.93 gate passed: `False`; bottleneck is medium/pseudo-medium retention, not OOD stress or review budget.
- formal benchmark remains disallowed.
- next action: `issue27bg_shared_scorer_region_refinement_before_ood_gate`; do not enter OOD repair until attack hard min reaches at least `0.93`.

<!-- issue27bg -->
## issue27bg - Shared scorer region refinement before OOD gate

- primary_verdict: `shared_scorer_no_sufficient_attack_recovery`
- purpose: replace the issue27bd/issue27bf two-head raw scorer with one shared 115D HistGB attack scorer plus bounded region evidence.
- dev attack hard min: `0.6428571428571429`; report-only attack hard min: `0.4062222222222222`.
- OOD stress hard max: `0.0`; final OOD hard max report-only: `0.0006666666666666666`.
- formal benchmark remains disallowed.
- next action: `issue27bh_attack_scorer_region_design_rethink_before_ood_gate`.

<!-- issue27bh -->
## issue27bh - Attack scorer/region failure anatomy before new head

- primary_verdict: `support_query_gap_primary_blocker_before_new_head`
- purpose: decompose attack-side failure across raw scorer, support-query gap, region/gate, and feature-family evidence.
- dominant two-head failure layer: `raw_score_layer`; dominant shared failure layer: `raw_score_layer`.
- no 115D frontend/split changes; no OOD-gate repair; no formal benchmark.
- next action: `issue27bi_region_aware_metric_or_calibrated_two_head_design`.
