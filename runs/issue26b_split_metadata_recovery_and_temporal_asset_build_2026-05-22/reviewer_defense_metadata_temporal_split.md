# Reviewer Defense: Metadata And Temporal Split

## Q1: Why did issue26a not run new temporal validation?

Because no P0/P1 low-leakage candidate existed. Running a reused locked bin would create the appearance of new evidence while actually being a consistency check.

## Q2: Why recover timestamp / packet-order / bin provenance?

Temporal validation needs a defensible chronology. Bin names alone show coarse ordering but cannot rule out adjacent-window contamination, near-duplicate flows, or session leakage.

## Q3: How do you avoid repeated locked-bin analysis being written as new evidence?

Bins `5/6/7/8` are marked as already consumed by issue23 and issue25c. Future reuse is consistency or robustness checking, not clean proof.

## Q4: How do you avoid adjacent-window contamination?

By requiring purge/embargo before formal validation. Since raw timestamps and capture boundaries are missing, issue26b does not choose a numeric gap.

## Q5: If a clean candidate does not exist, what happens to the paper?

The within-dataset temporal claim remains pending. The paper can still use issue23/25c as same-dataset locked evidence, but must state the temporal/external-validity limitation and run a metadata follow-up or second-environment feasibility step.

## Q6: How does metadata recovery lead to formal temporal validation?

It defines which windows are train/cal/val/eval, whether they were previously used, and how purge/embargo will be set before final metrics are touched.

## Q7: Why is second environment still needed?

Within-dataset temporal evidence cannot establish external generalization. A second environment is still needed for issue27-level external-validity claims.

## Q8: Is more data needed?

Likely yes for a clean temporal claim. The weakest existing locked bin has only 426 attack eval rows, and no unused future window was recovered.

## Q9: Is Slurm needed?

Not for issue26b. Slurm becomes relevant for large raw scans or formal multi-seed validation after the split protocol is frozen.
