# CKDA D0 formal chain implementation — ready for Kimi review

Date: 2026-08-11

Scope: implementation and bundle construction authorization only

FROZEN contract: `ckda_d0_representation_compatibility_audit_preregistered_20260811.md`

Contract SHA-256: `ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5`

## 1. Outcome

The CKDA D0 result-producing chain is implemented. It performs the already
FROZEN fit-only census, a bounded compatibility/resource pilot, deterministic
candidate ranking, strict result validation, and atomic result packaging.

This implementation does **not** train an encoder, inspect labels or scores,
persist performance embeddings, open FINAL, or authorize D1. No HPC job has
been submitted by this implementation step.

The two P0 rulings in commit `c42fcf9` are literal implementation contracts:

- the candidate audit has the 50 mechanically enumerated fields;
- `processed/iotsim-hydraulic-system-1.csv` remains unopened with reason
  `UPSTREAM_RAW51_UNOBSERVABLE_MASK`;
- `processed/iotsim-cooler-motor-5.csv` remains unopened with reason
  `FINAL_DENYLIST`.

## 2. Implemented files

- `repo/ood/issue27ckda_d0_representation_compatibility_audit_v1.py`
  - preserves frozen pilot-session selection order;
  - accepts the formal ToN manifest plus separately pinned PCAP root;
  - emits the P0-B boundary audit with exact reason codes.
- `repo/ood/issue27ckda_d0_resource_pilot_v1.py`
  - fixed first 100 nonempty sessions or 100,000 raw packets;
  - one warmup and three measured repetitions;
  - E3 uses the official netFound source and complete official checkpoint;
  - I1 is only a D0 token-interface pilot when its frozen data gate passes;
  - persists aggregate timing/resource/shape/finiteness evidence, never
    embedding values.
- `repo/ood/issue27ckda_d0_validate_and_pack_v1.py`
  - read-back validation of all mandatory artifacts;
  - recomputes I1 conjunctive gate, candidate order, ranking and verdict;
  - fails on engineering/final/label/embedding boundary violations;
  - emits report, `SHA256SUMS`, and terminal validation JSON.
- `scripts/issue27ckda_d0_representation_compatibility_audit_formal.slurm`
  - one AMD result-producing job, 8 CPU, 32 GiB, 12-hour limit;
  - named real-input phases and per-source census checkpoints;
  - content-addressed checkpoint reuse and no mixed run roots;
  - no-progress guards for census and pilot;
  - atomic stage-to-result promotion and pullback package.
- `scripts/issue27ckda_d0_install_and_submit.sh`
  - exact bundle and immutable-input hash gates;
  - compute dependency/scheduler dry checks;
  - explicit `CKDA_D0_SUBMIT_AUTHORIZATION=YES` requirement;
  - duplicate-submission prevention and durable job record.
- `scripts/issue27ckda_d0_status.sh`
  - reports scheduler state, phase, completed checkpoints, logs, failure
    markers, and terminal pullback identity.
- `scripts/issue27ckda_d0_build_bundle.ps1`
  - scoped LF-only bundle with official netFound source/checkpoint and pinned
    Linux Python dependencies;
  - FROZEN contract hash is rechecked after line-ending normalization;
  - clean-extraction full hash verification.

## 3. E3 adapter boundary

The E3 pilot follows the official netFound inference representation rather
than inventing a detector:

- bidirectional 5-tuple plus protocol session key;
- same-direction burst split at 10 ms;
- first 12 bursts and first 6 packets per burst;
- official header-field ordering and tokenizer/model classes;
- the six payload slots are zero placeholders and are removed by the
  official no-payload tokenizer configuration.

The adapter is measured as compatibility glue and its file/LOC cost is exposed
to the frozen ranking rule. It does not change netFound weights or architecture.

## 4. I1 boundary

I1 is eligible for its token-interface resource pilot only if both frozen
minimums pass:

- fit sessions >= 500,000; and
- fit tokens >= 10,000,000.

D0 does not choose or train an I1 encoder architecture. If eligible, D0 only
measures the already specified causal tokenization path so that a later,
separately frozen stage can make an honest engineering decision.

## 5. Regression evidence

Local checks completed:

- 31/31 contract tests PASS;
- the 31st test runs compile -> P0-B boundary finalization -> strict validator
  end to end on a synthetic real-shaped artifact set;
- Python byte compilation PASS for audit, pilot, validator and tests;
- Bash syntax PASS for Slurm, installer and status scripts;
- PowerShell parser PASS for the builder;
- a genuine official netFound checkpoint load and minimal CPU forward PASS
  (finite output, no persisted embedding, no label/FINAL access);
- checkpoint identity fixed at 698,780,900 bytes and SHA-256
  `e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105`.

## 6. Result semantics

The D0 terminal result can only establish representation compatibility and a
primary/optional-backup choice. It cannot claim detection improvement.

- engineering failure -> no scientific verdict;
- no compatible candidate -> `CKDA_D0_NO_COMPATIBLE_REPRESENTATION`;
- at least one compatible candidate ->
  `CKDA_D0_PRIMARY_AND_OPTIONAL_BACKUP_FROZEN`;
- either successful state authorizes only a separately frozen D1 decision.

## 7. Review request and authorization boundary

Kimi is requested to review the implementation and, after the archive exists,
the exact bundle identity. Building and reviewing the bundle are authorized by
the P0 review. Formal HPC submission remains blocked until Kimi's bundle PASS
and a new explicit user authorization.
