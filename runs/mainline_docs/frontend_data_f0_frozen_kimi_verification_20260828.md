# Frontend-F0 / Data-F0 FROZEN Protocols — Kimi Freeze Terminal Review

- Reviewer: Kimi
- Date: 2026-08-28
- Freeze commit: `6d6fd11`; freeze basis: Kimi Round 3 review `96172df`
- Verdict: **FREEZE PASS × 3.** All three protocols are frozen; each execution stage now
  awaits its own separate user authorization.

## 1. SHA verification (independently recomputed)

| Protocol | Recomputed SHA-256 | Match |
|---|---|:--:|
| `frontend_f0_missingness_mechanism_audit_frozen_20260828.md` | `f188afc0f9a0564a9f193b2e13637efdb660077f6ce74ba5c1d9cfc638fb1e8e` | YES |
| `frontend_f0_measurement_instrument_frozen_20260828.md` | `197015f0a6dd5c5510b5859d12aa19813a877392c8b985f6b1fcc4fe20f81a00` | YES |
| `data_f0_paired_corpus_metadata_audit_frozen_20260828.md` | `e699008656ced7120bf6eacf71129ca416cd98e9c3d8d3e653f97e2e90ef0079` | YES |

## 2. Diff review: draft → FROZEN (each file read hunk by hunk)

**Step-0 missingness protocol:** status mechanics; the promised availability-NPZ byte
identity is now pinned (`b1b4f2fd...b6099` — matches the identity I independently
recomputed during the CKDE-S erratum review) with only `uid`/`missing` arrays permitted
and `representation`/probe-state explicitly forbidden. No scientific rule, predicate,
precedence, conservation law, or claim boundary changed. PASS.

**Measurement instrument:** N1 incorporated verbatim — `≥0.90` overall / `≥0.80` per
benign device / `≥0.80` per declared-supported attack family, restricted to the Stage-I
declared protocol matrix, matrix-out targets named with literal reasons and never
dropped, unsupported families inherit `UNPROTECTED_BY_REPRESENTATION_EVIDENCE`, and the
accountability clause (declared support + ≥20% miss → gate fail). N2 incorporated
verbatim — `r_required < d_challenger` feasibility clause decidable from Stage I
metadata, fail-closed with no retry, plus the null-model portability justification
recorded in the protocol text as required. No other drift. PASS.

**Data-F0:** N3 incorporated verbatim — `N ≥ 8`, `N_E = max(2, ceil(N/4))`,
`Data-T ≥ 6`, both shortfalls fail-closed to
`NO_IDENTIFIABLE_PAIRED_DEVICE_SPLIT`; hash-ordered deterministic split unchanged;
Data-E sealing unchanged. I verified the arithmetic: at N=8 the rule yields exactly
2/6, and no N ≥ 8 can produce Data-T < 6 under the formula, so the two stop conditions
are consistent. No other drift. PASS.

**.gitattributes:** two scoped LF-eol lines for `frontend_f0_*` and `data_f0_*`,
extending the existing per-route pattern (ckbu/ckbv/ckdd/ckde). This is the correct way
to keep SHA sidecars stable across checkouts; reviewed, no concern.

## 3. Ruling

All three protocols are **FROZEN**. Authorization state:

1. **Step-0 missingness mechanism audit** — implementation + execution each await
   explicit user authorization. Reads only pinned code/metadata/`uid`/`missing`;
   representation and probe-state remain forbidden; PCAP re-decode remains sealed.
2. **Measurement instrument** — Stage I (compatibility/resource/lineage audit,
   checkpoint metadata) awaits its own user authorization, including any network
   retrieval of official documentation. No embedding, no training.
3. **Data-F0** — metadata retrieval execution awaits its own user authorization
   (network, byte ceilings, candidate-1 only; candidate 2 sealed behind the
   digest-matched blocking review).

FINAL, report, training, HPC, bulk download, and challenger embeddings remain sealed
throughout.
