# Claim Update After Issue26a

## Allowed now

- issue26a inventories within-dataset temporal, locked, consistency, and data-scale evidence after issue25c.
- Enhanced LOW-GUARD+ top64 remains strong-baseline-positive on the existing locked bins under the low-alert protocol.
- Existing primary_lowood, holdout_bin_2, and chrono_late results are useful consistency/discovery evidence, not new temporal proof.
- Existing locked bins 5/6/7/8 support same-dataset locked validation, with repeated-analysis caveats.
- Current provenance indicates threshold selection uses ID calibration + OOD validation, not final OOD/attack eval.

## Still not allowed

- issue26a proves temporal generalization.
- issue26a proves external generalization.
- consistency checks equal formal locked temporal proof.
- locked-bin reuse is a clean new temporal validation.
- Enhanced LOW-GUARD+ is universally safe across all future drift.

## Needs issue26b

- A formal within-dataset temporal validation claim.
- A purged/embargoed future-window validation claim.
- A claim that temporal order, not only attack-bin holdout, was tested cleanly.

## Needs issue27

- Second-environment or external-dataset generalization.
- Robustness to BoT-IoT / TON-IoT-like domain shifts under a clean new protocol.
- Claims about cross-dataset deployability.
