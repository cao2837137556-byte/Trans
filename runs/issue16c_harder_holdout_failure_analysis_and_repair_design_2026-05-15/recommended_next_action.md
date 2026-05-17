# Recommended Next Action

## Unique First Choice

Run `issue17_support_diversity_selection_harder_holdout_2026-05-15`.

Purpose: test whether the holdout_bin_2 failure can be repaired by better support coverage. This is a minimal mechanism test for the attack-window shift hypothesis, not a claim that support mismatch is already the proven dominant cause. Use only the attack train pool for diversity selection, keep OOD weight=2 fixed, keep the same local-calibration protocol, and evaluate on both pre-registered hard holdouts.

## Backup

If support diversity fails, run a row-level score persistence pass and pre-registered OOD target sensitivity at 0.5%, 1%, and 2% to separate threshold stringency from representation failure.

## Do Not Do Yet

Do not upgrade to MLP/prototype/margin-GDA before support coverage and threshold diagnostics are complete.
