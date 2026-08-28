# Frontend-F0 Step-0 Missingness Mechanism Audit — Result

- Date: 2026-08-28
- Frozen contract: `frontend_f0_missingness_mechanism_audit_frozen_20260828.md`
- Status: **RESULT — NO_IDENTIFIABLE_MISSINGNESS_MECHANISM_WITHOUT_REDECODE**

## Outcome

M0 passed: all pinned hashes and the four literal missingness predicates were
mechanically verified. The implementation opened only `uid` and `missing` from the
pinned fit/select availability NPZ.

M1 found that the existing legal metadata cannot reconstruct every primitive predicate
for every missing target. The legal target metadata covers all 11,640 missing rows, but
does not persist IP protocol or a reversible IP session key, and it does not persist the
per-session timestamp-regression state. Member checkpoints contain only the generic,
hashed `session_id` and the same missing flag; the reason hash is intentionally
non-invertible. Therefore M2 and M3 were not entered.

## Frozen denominator

| Quantity | Value |
|---|---:|
| fit/select terminal rows | 25,467 |
| finite rows | 13,827 |
| missing rows | 11,640 |

## Boundary audit

All forbidden-open and mutation counters are zero: PCAP, report, FINAL,
representation arrays, probe state, model weights, and training runs.

## Interpretation

This result does not show that the frozen E3 front end is adequate. It shows that the
existing committed artifacts discarded the target-level information required to split
the generic missing state into the four frozen causes. Exact attribution now requires a
separately preregistered causal re-decode; correlation by device or attack family cannot
replace that evidence.

No claim is made that missingness causes the hydraulic false-positive failure. The
existing committed diagnosis already shows that failure survives after excluding missing
embeddings.

## Reproduction

```text
python repo/ood/issue27frontend_f0_missingness_mechanism_audit_contract_tests_v1.py
python repo/ood/issue27frontend_f0_missingness_mechanism_audit_v1.py \
  --repo-root . \
  --output runs/frontend_f0_missingness_mechanism_audit_20260828
```

The result directory contains the six FROZEN outputs and `SHA256SUMS`.
