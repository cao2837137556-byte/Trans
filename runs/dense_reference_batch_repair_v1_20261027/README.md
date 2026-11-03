# Dense reference singleton batch repair

Status: engineering preparation. This package has no execution authorization and does not submit jobs.

The completed source8 diagnostic (179591, exit 0, 36 seconds) reproduced all eight failed B1 vectors and restored all eight historical vectors with identical B16 clones. The original 104-row numerical gate remains failed until an independent repaired replay passes. This evidence motivates a batch compatibility repair, not a new scientific result.

## Exact change

Only a physical batch of one is expanded to 16 identical copies of the already collated input tensors. All 16 input tensor hashes and all 16 float32 output byte strings must agree. Exactly one logical output is returned. Batches of size 2–16 are passed through unchanged. Frozen selection, tokenizer, UID order, ORIGINAL104 zero-tolerance comparison and bank merge are unchanged. Copies never enter a reference bank.

The adapter runs inside the encoder child process. After encoding, an additional receipt binds actual physical counts, UID order, the batch ledger and the raw and canonical budget hashes. CAL cannot start without this receipt and an exact ORIGINAL104 pass. A late adapter failure revokes any earlier frozen encoder COMPLETE result.

## Files and entry points

- `encoder_adapter.py`: batch compatibility adapter and standard-library budget reconstruction.
- `run_repaired_chain.py`: default read-only dry-run; explicit execution delegates only runtime → encode → source_cal to the frozen chain.
- `repair_gate.py`: immutable seals, approval scope, launch status and completion checks.
- `ENCODER_PHYSICAL_BUDGET.json`: exact shape-group and UID-queue budget from frozen reference snapshots.
- `RUNTIME_BINDING_179536.json`: runtime identity retained from the failed job and successful diagnostic.
- `run_repair.slurm`: 4 CPU / 16 GiB / 12 hours, no requeue, no automatic retry.
- `inert_test_support.py` and `test_*.py`: synthetic tests, including real frozen encoder/chain orchestration with inert workers; no checkpoint/model forward.
- `EXECUTION_CARD.md`, `REPAIR_MANIFEST.json`, `APPROVAL_TEMPLATE.json`: scope and required new execution permission.

The original r2 package and old launch/diagnostic overlays remain sealed and untouched. Output belongs in a fresh external job directory. The original package has 1,492 sealed files; this overlay is separate.

## Validation and deployment

Set `PAPER04_FROZEN_R2_TEST_ROOT` to the sealed r2 root when testing an extracted overlay. Run `python -B -m unittest discover -s OVERLAY -p 'test_*.py' -v`, then `python -B OVERLAY/run_repaired_chain.py --original SEALED_R2`. The latter verifies all seals and recomputes the complete budget without importing a model, loading a checkpoint or forwarding data.

Do not use a working preparation directory as SEALED_R2. Do not edit seal line endings or create runtime files inside the original package. Upload only the completed distribution archive, verify its archive SHA and extracted seal, and retain the existing original assets.

The false approval template is intentionally non-executable. A new scope-bound approval, filled with the final overlay seal SHA and user authorization evidence, is stored separately in `.private/APPROVED.json` only after permission. Earlier job permissions are consumed and are not reused.

## Scientific limits

This prefix produces reference features and source-CAL calibration results. It performs zero optimizer updates and zero target-query evaluations. Full target matrix execution remains blocked by missing frozen third-pool BASE/B2 assets. No A/B-only substitution is allowed. The 8-row diagnostic and synthetic tests do not certify the full 104-row replay or predict a target FPR/recall.
