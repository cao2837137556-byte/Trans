# Issue25c Execution Plan

## Stage 0: Execution Preflight

- Verify feature assets for selected_source_rich_top64 and optional full_source_rich.
- Verify locked bins 5/6/7/8 splits, labels, ID calibration, OOD validation, final OOD eval, and attack eval.
- Verify kcenter32 support provenance.
- Verify all candidate methods can emit scalar scores.
- Verify final eval is not used in any configuration selection.

## Stage 1: Reproduce Internal Baselines

Run or reuse protocol-identical outputs:

- V1 original100 fixed guard LR.
- V2_top32 source_rich fixed guard LR.
- Enhanced LOW-GUARD+ top64 fixed guard LR.
- top64 no guard.
- top64 random32.

These establish the internal ablation backbone.

## Stage 2: Required External-Style Baselines

Run:

- Isolation Forest.
- OC-SVM.
- HistGB shallow.
- DevNet-like lightweight.
- DeepSAD-like lightweight.

Use main seeds 42-46 first. If all are protocol-clean and runtime is acceptable, extend to held-out seeds 47-51.

## Stage 3: Consistency Checks

Report a reduced method subset on:

- primary_lowood.
- holdout_bin_2.
- chrono_late_train_early_eval.

These are not the main locked proof but check whether strong baselines change the interpretation of earlier settings.

## Stage 4: Optional / Appendix

Run optional baselines only after required methods finish:

- LOF.
- full_source_rich variants.
- RoSAS-like if implementation is clean.
- issue24c fusion as reference, not replacement.

## Stop Rule

If a baseline cannot satisfy final-eval isolation or common 1% OOD validation thresholding, stop that baseline and mark it diagnostic-only rather than forcing an unfair result.
