# A-Line Mainline Experiment Handoff

Updated: 2026-04-14
Workspace: `C:\Users\28371\.codex\worktrees\f736\kitnet-exp-mainline`
Branch: `codex/exp-mainline`

## Scope

This file is the time-ordered handoff for the A-line main experiment only.

- Record only A-line mainline work.
- Record what was done, what the result was, what the current blocker is, and what should happen next.
- Exclude `frontend_f2_*` and any other branch-line exploration.
- Exclude merge, worktree management, and the global master experiment table.

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
- Reclassified the project into the A-tier strengthening stage and fixed the official execution order in `runs/master_experiment_map_v1.md`.

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
