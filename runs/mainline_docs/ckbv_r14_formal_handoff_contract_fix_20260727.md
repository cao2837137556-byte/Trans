# CKBV r14 formal handoff contract fix

## Failure classification

Jobs `154761` (AMD) and `154762` (Intel) crossed the real-input and
checkpoint gates. The AMD job completed all preprocessing and source
aggregation, then failed on entry to `formal_seed27_model`.

The failure is a stage-handoff contract bug, not scientific evidence and not
a TShark, data, memory, model, threshold, or Slurm resource failure. The
formal program retained an older CKBU output-directory whitelist and rejected
legitimate CKBV checkpoint artifacts in the same run root.

## Minimal repair

The fail-closed directory guard remains in force. r14 replaces the stale
implicit whitelist with exact file and directory contracts for every artifact
that the CKBV launcher can legally create before formal scoring. It also
checks the expected file type. Unknown files, wrong-type paths, partial
scientific outputs, and a failed run root remain rejected.

The contract unit now materializes the complete legal staged run root, proves
that it is accepted, then proves that an unknown scientific CSV and a
wrong-type checkpoint directory are rejected. This directly reproduces the
boundary that failed after three hours in job `154761`.

## Resume boundary

The validated AMD `154761` run root is prepended to the immutable reuse-donor
list. A new r14 job receives a new partition/job-isolated run root and copies
only validated checkpoints from donors. It does not resume inside or
overwrite the failed root.

An earlier live snapshot already showed 58/62 Gotham member checkpoints,
25/30 aggregated Gotham sources, all 31 auxiliary sources, and all 4 ToN
files. The later transition into `formal_seed27_model` proves that the
pre-formal readiness and aggregation gates subsequently completed. The new
run nevertheless makes no count assumption: it scans the `154761` donor and
reuses only individual source/member/file checkpoint pairs accepted by the
existing schema, coverage, identity, and hash validators. Any incomplete or
hash-invalid donor artifact remains rejected.

## Scientific invariants

- Frozen target manifests and `raw51_observable_v1` mask are unchanged.
- 51D causal features and feature availability semantics are unchanged.
- Fit/select/report roles and held-family exclusions are unchanged.
- C1, CKBQ, model architecture, optimization, gates, thresholds, seed 27,
  review=0, and go/no-go rules are unchanged.
- AMD and Intel retain independent output/checkpoint roots.
- This repair changes only legal stage handoff and validated checkpoint reuse.
