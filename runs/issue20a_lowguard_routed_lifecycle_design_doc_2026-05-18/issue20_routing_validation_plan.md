# Issue20 Routing Validation Plan

## A. Experimental Goal

Validate whether LOW-GUARD-Routed is better than:

- always V1;
- always V2;
- OR ensemble;
- AND ensemble;
- review-all;
- oracle upper bound, if applicable.

## B. Data Settings

Required:

- primary low-OOD;
- holdout_bin_2;
- chrono_late_train_early_eval.

Optional:

- ordinary compatibility, only if a comparable guarded protocol can be defined without leakage.

## C. Pre-Registered Routing Rule

A simple first routing rule:

- If V2 validation OOD alarm <= 1%, and V2 attack validation or support-holdout detection proxy exceeds V1 by at least 5 percentage points, activate V2.
- Otherwise activate V1.

If attack validation is unavailable or too small, use a held-out support proxy and mark the limitation. The rule must not use final OOD eval or attack eval.

## D. Output Metrics

- Attack high detection.
- OOD high alarm.
- Feasible rate.
- Review burden.
- Conflict count.
- Selected champion.
- Wrong-routing cases.
- Routing decision provenance.

## E. Success Standard

- Primary low-OOD selects V1 and avoids V2's OOD over-budget failure.
- holdout_bin_2 selects V2 and recovers detection.
- chrono_late selects V2 or remains feasible with the selected champion.
- Routed system improves the worst-case tradeoff over always-V1 and always-V2.
- Review burden remains bounded.
