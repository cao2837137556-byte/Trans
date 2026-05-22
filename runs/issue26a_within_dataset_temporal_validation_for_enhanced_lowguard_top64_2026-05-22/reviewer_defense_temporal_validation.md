# Reviewer Defense: Temporal Validation

## Q1: Are you just tuning repeatedly on one dataset?

Issue26a separates discovery, locked evidence, consistency checks, and future candidates. It does not tune topK, support budget, adapter, or thresholds. It flags repeated locked-bin analysis as a risk instead of hiding it.

## Q2: What is the difference between locked bins and temporal validation?

Locked bins 5/6/7/8 are unused leave-one-attack-window objects from issue23 and were later reused in issue25c strong baselines. They are same-dataset locked evidence. Formal temporal validation should pre-register a chronological future-window split with purge/embargo rules and no overlap with discovery or locked-evidence objects.

## Q3: Why is issue26a only feasibility, not formal validation?

Because issue26a reads and audits existing assets. It does not build a new clean temporal split, does not run a formal temporal experiment, and finds no low-leakage P0/P1 candidate ready for formal validation.

## Q4: How do you avoid temporal leakage?

By requiring row-level time/order metadata, separating train/cal/val/final windows, excluding final OOD and attack eval from all choices, checking support and threshold provenance, and using purge/embargo when windows are adjacent.

## Q5: What if there is no clean new temporal object?

Then the correct action is metadata recovery or asset construction, not repackaging consistency checks as temporal proof. Negative or insufficient-metadata outcomes remain visible.

## Q6: Why not directly do BoT-IoT / TON-IoT here?

This issue is scoped to within-dataset temporal/data-scale feasibility after issue25c. Second-environment work remains important but is deferred to issue27 so this round can close the temporal evidence inventory cleanly.

## Q7: Why is second environment still needed?

Within-dataset temporal evidence cannot prove external generalization. A second environment is still required for cross-dataset/domain validity claims.

## Q8: Do you need larger data?

Possibly. The inventory exposes small attack-eval risk for some bins, especially holdout_bin_8 with 426 attack eval rows, and single-domain risk remains.

## Q9: Do you need Slurm?

Not for issue26a. Issue26b may need Slurm only after local metadata recovery and smoke pass, especially if raw parquet scans or multi-seed formal validation are required.
