# CKBV r21: masked-source evidence closure for the AMD 154917 pullback

2026-07-29 · ledger section 19 · supersedes nothing in r20 (recovery unchanged)

## What happened

The r20 run-grounded recovery succeeded on HPC (`CKBV_POSTFORMAL_RUN_GROUNDED_RECOVERY`,
idempotent, scientific hashes unchanged).  Validation then advanced into two
stages no earlier attempt had ever reached and stopped twice:

1. `invalid member checkpoints: ['0..3:missing_pair']` — the four members of
   `iotsim-air-quality-1` never existed in the CKBV chain because the run
   reused that source's aggregate whole from job 154761 (`missing_sources=1
   pending_members=0 reused_members=58`).  This was the original r16 death
   in `validate_and_pack`.
2. `invalid source checkpoints: ['iotsim-hydraulic-system-1:missing_pair']` —
   the fully-masked raw51 source has no observable rows, hence no causal
   aggregate by design; the pair-level source check and the aggregation
   coverage check still assumed 30 sources / 30 rows while the plan-level
   checks were already mask-aware (29 sources).

## Repairs (evidence-only, no science touched)

- The four air-quality-1 members were re-materialized on the login node with
  the byte-identical frozen r16 frontend (no Slurm submission; ~13.5 MB of
  PCAPs; each member self-validated on write, `matched_target_rows=0` is the
  legitimate account for this source).  The run's causal chain never read
  these files; they exist for evidence completeness only.
- The validator now applies a bounded exemption: the named masked source may
  lack a causal aggregate only with `missing_pair` and only while its
  source-plan `target_rows` is exactly 1,353; the aggregation audit must have
  exactly 29 rows with the masked source absent, and the masked source must
  never gain a pair or an audit row.

## What did NOT change

- recovery program, recovery status, and all run-grounded constants from r20;
- the `NO_GO` decision, every scientific file hash, models, scores, gates,
  thresholds, denominators, seeds;
- the member/source evidence checks themselves — they were completed and
  bounded, not weakened.

## Bundle contents

Same payload as r20 plus this document and ledger section 19.  The recovery
remains idempotent: re-running the r21 bundle's recover script re-validates
and then packages the pullback.
