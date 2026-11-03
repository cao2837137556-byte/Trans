# Frontend-F5 T failure: read-only diagnosis

Date: 2026-09-07. Review of existing P/T artifacts and source text only.
No new inference, checkpoint loading, optimization, feature decoding or K access.

## Result and integrity

`F5_NO_ELIGIBLE_CHECKPOINT`: 20 epochs, 3,120 optimizer steps, 595.812 seconds.
All 17 final manifest hashes independently verified. Saved target evaluations
equal 20 * 8,660 train and 20 * 5,206 validation. No epoch was eligible.
The selection counter reached 20 without improvement; the frozen rule stops
at epoch >=20 with counter >=12. The 100-epoch limit was a maximum.
This is a completed scientific failure, not evidence of an execution crash.
B utility and K remain NOT_EVALUATED.

## Protected target errors

Epoch snapshots are descriptive, never replacement candidates.

| Epoch | Train A attack /2179 | Train B attack /68 | Train A normal /4667 | Val A attack /3 | Val B attack /3 | Val A normal /1478 |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 44 | 6 | 288 | 0 | 0 | 863 |
| 2 | 0 | 0 | 288 | 0 | 0 | 867 |
| 5 | 6 | 5 | 0 | 3 | 3 | 843 |
| 10 | 6 | 0 | 0 | 3 | 1 | 843 |
| 20 | 5 | 0 | 0 | 3 | 0 | 843 |

All 843 final validation normal errors are from `normal_1.pcap`; 839 UIDs
fail in all 20 epochs. The three final A validation attack errors are from
`processed/iotsim-combined-cycle-10.csv`. The 846 final validation errors
occupy 673 semantic contexts, not asserted independent samples.

The five final train attack errors share one semantic context in
`processed/iotsim-ip-camera-museum-1.csv`. Their canonical old teacher strengths
are all clipped to 6. Weak or absent teacher targets do not explain these five
errors; their actual failure mechanism remains unknown.

Epoch 2 -> 20 full-split supervised loss: train 0.02519775 -> 0.00095190;
validation 1.70844692 -> 7.99748871. Epoch 20 mean attack loss is 0.00141383,
but whole-corpus worst attack loss is 6.27879143. The latter is a diagnostic,
not the batch-worst training objective. Mean loss reduction did not establish
the required protected decisions.

## Next decision

This is more than a near-pass blocked by five training rows. There is a large,
persistent validation protection failure plus a rare-context training failure.
The observed train/validation gap is consistent with failed transfer on the
frozen source split. It does not prove input insufficiency, shortcut learning,
optimization conflict or insufficient model capacity as the cause. F4 input
preservation does not prove preservation of all discriminative information
available to the old teacher. Synthetic checks do not exclude every code defect.

Recommend a high-reasoning diagnostic/design review before another experiment:
map the persistent validation errors and rare training context to existing
feature/schema and teacher contracts; audit aggregation, batch-worst protection
and causal-prefix code against the frozen protocol. Separate conclusions from
stored artifacts from any proposed tests requiring new feature/model access.
Do not redo F4, extend this trajectory, relax gates, select another epoch or
open K. A new model/loss/seed requires a distinct justified proposal and explicit
authorization, not failure-driven tuning disguised as repair.

Before proposing another run, require a concrete mechanism addressing both
observed failure patterns, a falsifiable predeclared test and a stop condition.
If these remain unidentified, do not launch variants merely to rank them.
New-device commissioning remains downstream of a defensible inheritance path;
its evidence cannot rescue this failed result.

Sources: final manifest, `training/epoch_ledger.json`, `training/terminal.json`,
`training/time.json`, `role_open_audit.json`, `preflight/uid_scope.csv` and
`preflight/teacher.csv` under `runs/frontend_f5_unified_student_v1_20260906_local/`;
F5 runner/core selection source read as text only.
