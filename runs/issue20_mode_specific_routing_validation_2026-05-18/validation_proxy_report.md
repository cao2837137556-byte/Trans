# Validation Proxy Report

The routing proxy uses attack validation detection at the guarded threshold plus OOD validation alarm. This is stronger than using supports directly because attack validation is split before final evaluation and does not overlap support or attack eval.

Limitations:

- It is still a finite validation proxy, not a guarantee of future drift.
- It can misroute if attack validation does not represent the final attack-side shift.
- It must be audited against wrong-routing cases and future locked validation windows.
- In this run, holdout_bin_2 lacks a usable attack validation proxy, so the pre-registered rule cannot trigger V2 there. That is a proxy-gap failure for routing validation.
