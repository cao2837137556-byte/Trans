# Mainline Handoff

Updated: 2026-04-21
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
