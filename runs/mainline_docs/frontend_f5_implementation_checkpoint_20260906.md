# Frontend-F5 implementation checkpoint: numerical core verified

Date: 2026-09-06

Status: `F5_I1_NUMERICAL_CORE_VERIFIED_I2_RUNNER_PENDING`

## Authorization and delivered scope

The user selected the current Astra implementation setting and authorized
starting the next step. This consumes authority for mechanical freezing,
implementation, synthetic contracts and the frozen synthetic resource pilot.
It does **not** consume authority for real P/T/K, teacher scores or training.
No model-choice-dependent scientific rule was added.

Accepted design commit: `6f9e0d0`. FROZEN SHA:
`b8069e6556d6719eef3e689b1ab9a8676c24a00a82e8b5f810a401c9c42786b6`.
The freeze only changes heading/status, provenance/authorization and the
closing lifecycle paragraph. Losses, model, constants, split and gates are
unchanged. The historical Sol-named handoff is now role-based.

This is an implementation checkpoint, **not full Stage I acceptance**. The
numeric core is executable on synthetic fixtures; its CLI intentionally offers
only `--synthetic-pilot`. There is no real-training command to accidentally run.
The 22 tests below are core regressions, not a claim that every item of the
protocol's 22 acceptance categories has been fully integrated.

## Verified core

- Sole 131D -> projection -> GRU -> own head: 94,748 training parameters;
  auxiliary removal leaves 91,265 inference parameters. Seeded initialization
  SHA `4e3220fb9848f1eebe08226d75c2cc3b9d28630b0168fd0ce537584119332909`.
- Packed/individual prefix equivalence, deterministic length/key restoration,
  future-event causality and context reset; metadata is not a model input.
- Context-balanced four-group label loss, label-aware continuous teacher loss,
  attack mean plus batch maximum and causal 27D auxiliary objective.
  Independently hand-computed zero-logit fixture: 1 + .5 + .5 + .5 + .1 = 2.6.
  Full-corpus eligible denominators, absent batch groups and tied-max gradient
  are tested; there is no silent rare-group renormalization.
- Pure canonical teacher math: float64 normalization, float32 P2/sigmoid,
  widening before threshold comparison, raw-logit saturation handling and
  teacher-kind mismatch refusal. Production scope enforcement is still pending.
- Streaming selective NPZ reader converts only requested rows. A synthetic NPZ
  with NaNs exclusively outside the allowlist verifies opaque/numeric separation.
- Categorical protected-decision gates, raw-logit `>=0`, selection/patience,
  per-key ceil/all-target context utility and terminal precedence.
- Synthetic save/reload reproduces model tensors, optimizer tensors, RNG,
  cursor and loss ledger exactly; corrupt checkpoints are refused. Separate
  elapsed-time recovery logic tests conservative open-batch downtime charging.

22/22 core tests PASS in 3.024 s (test-body time). An initial test used a wrong
pure F4 codec helper name (`parse_signature` instead of `parse_l1`); the test
was corrected, then the entire suite rerun. No scientific rule changed.

## Single synthetic resource pilot

Verified runtime: Python 3.9.13, NumPy 2.0.2, torch 2.8.0+cpu, 4 intra-op /
1 inter-op threads. No packages were installed. Fixture shape: 32 contexts x
256 events, targets at every event, all four task groups. F4 codec round-trip
of fixture fields passes. This is not a performance-learning dataset.

Two warm-up + eight timed optimizer batches; eight timed inference batches.
Frozen projection: 9,320.99668 s (2.589 h); threefold: 27,962.99004 s (7.767 h),
below 47,494.34391 s (13.193 h). Result: `F5_SYNTHETIC_RESOURCE_PASS`.
This screen does not guarantee total real execution time; production accounting
must include evaluation, I/O and checkpointing and enforce the unchanged cap.
No real trajectory has started. No model trained in this pilot is retained for
use as the real initialization; reseeded initialization matches the original.

## Remaining implementation, no new design authorization required

1. Production preflight: all 19 input pins, exact F4/F3 UID/source/census joins,
   cross-context exclusion, counts-before-numeric gates and scoped teacher cache.
2. Real controller: one attempt, durable time ledger, 25-batch checkpoints,
   per-batch RAM/storage/time limits, heartbeat, refusal to overwrite completion.
3. Full split/category/source/device/family output accounting, sealed selected
   checkpoint, exact B denominator checks and deferred one-shot five-row gate.
4. Operator launcher/read-only monitor and synthetic integration tests covering
   the entire production control flow. Only then may full Stage I be PASS.

Do not mistake passing the core tests for a training-ready runner. These tasks
remain within the user's implementation authorization. Real P/T/K still needs
an explicit later authorization; do not ask for that before I is complete.

## Evidence and boundary

`runs/frontend_f5_implementation_v1_20260906/` contains the test transcript,
synthetic resource receipt, implementation checkpoint and SHA256SUMS.
Core source and test hashes are recorded in the checkpoint JSON. Real feature,
real teacher, select/report/FINAL opens and real optimizer steps are all zero.
Existing incumbent files and deployment were not changed. There is no F5
scientific result, inherited-capability claim, B utility gain, OOD gain or
commissioning claim at this checkpoint.
