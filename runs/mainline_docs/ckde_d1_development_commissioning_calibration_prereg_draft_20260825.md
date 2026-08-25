# CKDE D1 — development-only benign commissioning calibration (POST-D0 DRAFT)

**Date:** 2026-08-25  
**Status:** DRAFT for independent review; no score opening or execution authorized  
**Parent D0 verdict:** `CKDE_D0_UNPAIRED_DEVELOPMENT_ONLY`

## 1. Question and claim ceiling

CKDE D1 asks whether one globally fixed commissioning algorithm can consume an explicitly benign,
causal prefix from an enrolled device and raise that device's frozen E3/P2 alarm threshold enough
to reduce later benign false positives without exceeding a precomputed attack-safety bound.

This is a capability change in what evidence the deployed system may consume. It is not a
device-family patch and it does not improve zero-shot first contact.

D0 found no device with both a legal benign prefix/suffix and same-device attack evidence.
Therefore this D1 is limited to a **development-level prefix-quantile study**:

- no strict conformal coverage claim;
- no positive same-device attack-preservation claim;
- no cross-device or unseen-industrial-domain positive claim;
- no paper-level capability claim without a separately frozen untouched/FINAL confirmation;
- cross-product attack stress is safety evidence only, never paired-device evidence.

## 2. Frozen D0 evidence

The following post-D0 facts are fixed before any D1 score access:

| Fact | Value |
|---|---:|
| Stable device-lineage groups | 28 |
| Devices with causal benign prefix and suffix | 23 |
| Eligible prefix sessions | 7,493 |
| Eligible suffix sessions | 7,550 |
| Devices with same-device attack pairing | 0 |
| Untouched non-FINAL devices in allowed artifacts | 0 |

Pinned D0 artifacts:

| Artifact | SHA-256 |
|---|---|
| `ckde_d0_verdict.json` | `c1953c55d999ac151426d5d9f6fa9fdcbaddfd725fe966ebf09def1c62f47033` |
| `ckde_d0_device_lineage_census.csv` | `9ce04164ce6db9917d9fe8d1dedae612ed727f78460e1db0882afe6dc1d69f9b` |
| `ckde_d0_prefix_suffix_summary.json` | `81ed488ad8a81372b121243ca4f57b4398cdb791f2da822ab98c176205e02a91` |
| `ckde_d0_role_open_audit.json` | `99a1c2b7c85f9a3956a00ede684fb534e1d098e7af8a69d4ce6e15c4268a714b` |
| D0 `SHA256SUMS` | `14a12e6d671c27706e9541403f3229ea32a84b1c8c77c5946081f7c0ae1e58e4` |

The frozen P2 identity is inherited unchanged:

- probe state SHA-256: `50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38`;
- fit/select embeddings SHA-256: `b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099`;
- fit/select plan SHA-256: `eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac`;
- zero-shot P2 threshold `theta_0 = 0.065159872174263`;
- threshold marker SHA-256: `84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b`.

Any identity drift is an engineering failure with no scientific verdict.

## 3. Arms and non-selection rule

Only two executable arm families are proposed:

- **Z — zero-shot baseline:** unchanged P2 score and `theta_0`.
- **Q — one-sided prefix-quantile calibration:** same score, globally identical rule, device-local
  threshold derived only from that device's legal commissioning prefix.

The previously reserved embedding-centering arm C is **deferred and non-executable** in this D1.
The reason is governance, not an observed result: D0 already limits the study to development-only,
and C would add a second representation transformation and another selection surface before Q has
established any clean signal. C may be reconsidered only in a separately named preregistration.

The primary arm is `Q-S64`. Larger session budgets and record-budget arms are resource curves,
not candidates. No result may promote `Q-S128`, `Q-S256`, or a record arm over `Q-S64`.

## 4. Device, session, and causal split

The eligible device set is mechanically defined as the 23 rows with
`causal_prefix_and_suffix_identifiable=True` in the pinned D0 census. Device identity, session
identity, and the count-only median-event-position prefix/suffix split are inherited byte-for-byte
from D0. D1 may not rebuild them using scores or labels.

For each device:

1. prefix sessions are ordered by their first causal event position, then by frozen session key;
2. calibration consumes only complete prefix sessions;
3. evaluation consumes only the already separated benign suffix sessions;
4. a session never appears on both sides;
5. rows arriving after the D0 cut cannot change any prefix statistic.

The frozen session score is the maximum finite P2 record score in that complete session. A
non-finite record score invalidates that session. An empty or invalid calibration set falls back
to Z.

## 5. Literal calibration budgets

The D0 prefix-session counts are:

- all 23 eligible devices have at least 64 sessions;
- 20/23 have at least 128 sessions;
- 11/23 have at least 256 sessions.

The session curve is therefore frozen in the draft as:

```text
S = {0, 64, 128, 256} complete independent prefix sessions
primary = 64
```

`S=0` is Z. A device with fewer than a requested nonzero budget is reported as
`INSUFFICIENT_SESSION_BUDGET_ZERO_SHOT` for that resource-curve point; it is not backfilled,
resampled, or upgraded by record count.

The required record-resource negative-control curve is:

```text
R = {0, 100, 500, 1000} causal prefix records
```

For record budget `R>0`, complete sessions are added in the same frozen order only while the
cumulative number of their records remains `<=R`. A session that would cross the budget is not
partially included. If no complete session fits, the arm falls back to Z. Record arms are
pseudo-replication diagnostics and cannot become the primary arm.

## 6. Fixed quantile rule

The draft calibration level is globally fixed at `alpha=0.05`. For `n` complete calibration
session scores sorted ascending as `x[1]...x[n]`:

```text
k = min(n, ceil((n + 1) * (1 - alpha)))
q_raw = nextafter(x[k], +infinity)
```

The `nextafter` operation makes the tie behavior explicit under the unchanged alarm rule
`score >= threshold`. No interpolation is allowed.

The device update is one-sided:

```text
delta_raw = max(0, q_raw - theta_0)
theta_d = q_raw                 if 0 <= delta_raw <= cap_fit_attack
theta_d = theta_0               otherwise, with CAP_EXCEEDED_ZERO_SHOT
```

The cap is a fail-closed trust region, not a clipping target. A prefix asking for more movement
than the attack-derived cap receives no calibration. This prevents an extreme or contaminated
prefix from silently parking at the maximum permitted threshold.

## 7. Attack-derived cap: mandatory staged materialization

This DRAFT freezes the cap algorithm but deliberately does not invent its numerical value. The
number must be materialized from the 4,385 legal fit attacks before any benign calibration score
or support-val score is opened.

Let `T` range over `theta_0` and every finite fit-attack P2 score `>=theta_0`. For each candidate
threshold, apply the unchanged hard rule `score >= T`. A candidate is admissible only if, relative
to Z:

- global fit-attack recall loss is `<=0.5` percentage points; and
- every frozen major attack family with at least 15 fit rows loses `<=2` percentage points.

Choose the largest admissible `T`; define:

```text
T_cap = max(admissible T)
cap_fit_attack = T_cap - theta_0
```

Exact ties remain hard. The attack-family dictionary must be the existing frozen CKCZ scope
clarification; CKDE may not create a new mapping.

The governance sequence is mandatory:

1. independent review of this DRAFT and cap formula;
2. user authorization for cap-only materialization;
3. open only 4,385 fit-attack scores and emit a hashed cap artifact;
4. insert the literal `T_cap` and `cap_fit_attack` into a newly named D1 FROZEN document;
5. independent hash/diff review and separate user authorization;
6. only then may benign prefix scores or the 69 support-val scores be opened.

The 69 support-val attacks are a one-time sentinel after the cap and all Q thresholds are frozen.
All 69 must remain hard under every non-fallback device threshold. Their values cannot alter the
cap, alpha, budgets, quantile rule, or any threshold.

## 8. Contamination stress

Only the primary `Q-S64` arm is stress-tested. The fixed contamination grid is:

```text
{0%, 0.1%, 0.5%, 1%, 5%, 10%} of independent calibration sessions
```

For each nonzero level, at least one session is contaminated. Legal fit-attack sessions are
assigned deterministically by SHA-256 ordering of
`device_key|level|pattern|replicate|attack_session_key`. There are 200 fixed replicates per
nonzero level and pattern; replicate identifiers are `0..199` and cannot be extended after
results.

Two patterns are mandatory:

1. whole-session replacement;
2. exactly one frozen attack record injected into each contaminated benign session before the
   session maximum is computed.

The stress grid cannot select a budget, alpha, cap, arm, or fallback rule. Every replicate reports
`q_raw`, requested movement, accepted movement, cap-exceeded fallback, benign suffix FPR, and
cross-product fit-attack recall. A non-finite value or cap exceedance must visibly fall back to Z.

## 9. Execution stages and isolation

Each stage has its own authorization and immutable inputs.

### P — cap-only materialization

Reads fit identities, fit labels/families, frozen embeddings/state, and 4,385 fit-attack scores.
It must not read benign prefix scores, support-val values, report values, or FINAL. Output is the
literal cap plus complete recall-loss tables.

### A — calibration materialization

After the literal cap is frozen, reads only eligible device prefix scores and materializes every
Z/Q threshold before suffix outcomes are opened. It emits a threshold manifest and a one-time
`CALIBRATION_FROZEN` marker.

### B — development evaluation and sentinel

After A is frozen, opens benign suffix scores, fit-attack cross-product stress, and the 69
support-val sentinel once. It cannot change any upstream value.

### C — viewed-report kill-only falsification

Requires a separate authorization after A/B review. All viewed report attack rows are evaluated;
the previously named conflict subset is reported separately. Viewed rows may only kill the route,
never improve, tune, or rank it. Failure closes CKDE without iteration.

FINAL remains sealed in every stage.

## 10. Metrics and denominators

All benign results are reported at three levels: device, independent session, and record. Required
outputs include per-device values, equal-device macro, clustered device bootstrap intervals, and
the number of eligible devices at each budget.

The development 2x2 matrix is explicit:

| Cell | D1 treatment |
|---|---|
| fit-context benign FPR | Z reference only; not used to choose Q |
| fit attack recall | Z and cross-product Q safety |
| calibrated-device benign FPR | Z versus Q on the 23 causal suffixes |
| calibrated-device attack recall | `NOT_IDENTIFIABLE_PAIRED`; cross-product stress separate |

Report-level attack recall, if stage C is later authorized, is kill-only and retains global,
unseen-source, family, source, session, and record denominators.

## 11. Predeclared development verdicts

The primary verdict is determined only from `Q-S64`.

`CKDE_D1_DEVELOPMENT_SIGNAL` requires all of:

1. all 23 eligible devices receive a valid S64 evaluation result (calibrated or explicit
   cap-exceeded Z fallback);
2. equal-device benign suffix macro FPR is `<=15%` and improves by at least `10` absolute
   percentage points versus Z;
3. at least 12/23 devices improve benign suffix FPR by at least `5` points;
4. no device is worse than Z (structurally expected from a one-sided threshold);
5. fit-attack global loss is `<=0.5` points and every major family loss is `<=2` points under
   every accepted device threshold;
6. 69/69 support-val attacks remain hard under every accepted device threshold;
7. contamination stress produces no silent threshold beyond the cap and no non-finite success;
8. all role, lineage, causality, hash, and one-shot markers pass.

Other terminal states:

- `CKDE_D1_NO_MATERIAL_BENIGN_GAIN` — safety passes but conditions 2 or 3 fail;
- `CKDE_D1_ATTACK_SAFETY_FAIL` — fit, family, or support sentinel fails;
- `CKDE_D1_CONTAMINATION_FAIL_CLOSED` — stress exposes a silent or non-finite success;
- `CKDE_D1_DEVELOPMENT_SIGNAL_KILLED_BY_VIEWED_ATTACKS` — separately authorized stage C fails;
- `CKDE_D1_ENGINEERING_FAILURE_NO_VERDICT`.

Even `CKDE_D1_DEVELOPMENT_SIGNAL` authorizes only a request for separately preregistered untouched
confirmation. It is not a paper-level positive result.

If stage C is authorized, it passes only when every frozen report attack denominator satisfies:

- global and unseen-source recall loss `<=0.5` points versus Z;
- each major attack family loss `<=2` points;
- no source/session denominator is silently omitted;
- the named 51,057 conflict subset is reported verbatim but cannot define the verdict alone.

## 12. Required implementation contracts

At minimum, tests must pin:

1. every input SHA and the parent D0 verdict;
2. exactly 23 eligible device keys from the D0 census;
3. source/member state isolation and canonical bidirectional session keys;
4. complete-session causal ordering and future-mutation invariance;
5. S64/S128/S256 eligibility counts of 23/20/11;
6. record-budget whole-session behavior and no partial-session inclusion;
7. session maximum, `alpha=0.05`, order statistic, `nextafter`, and tie behavior;
8. one-sided threshold movement and cap-exceeded fallback to exact Z;
9. cap derived from fit attacks only and before support access;
10. support sentinel one-shot isolation;
11. both contamination patterns and all six levels;
12. no score-derived device/session/budget selection;
13. no report access before separately authorized stage C;
14. no FINAL access in any stage;
15. Python 3.9 syntax and observed runtime APIs;
16. atomic readback, hashes, and engineering failure with no scientific verdict.

## 13. Review requests for Kimi

Please rule explicitly on:

1. the primary session budget `64`, diagnostic budgets `128/256`, and record-budget negative
   controls `100/500/1000`;
2. the staged cap-only materialization procedure and exact max-admissible-threshold formula;
3. fail-closed fallback when `q_raw` exceeds the cap rather than clipping at the cap;
4. deferring optional arm C so Q is the sole calibration mechanism in this development study;
5. the `alpha=0.05` higher-order-statistic plus `nextafter` convention;
6. the numerical benign-gain gates (`<=15%` macro, `>=10pp` macro improvement, 12/23 devices
   improving by `>=5pp`);
7. whether 200 deterministic contamination replicates per nonzero level/pattern are sufficient;
8. the Phase P/A/B/C isolation and viewed-report kill-only conditions.

## 14. Authorization boundary

This is a DRAFT only. It authorizes no implementation, score opening, cap materialization,
calibration, report access, FINAL access, training, download, or HPC submission. After independent
review, any revised FROZEN protocol must still keep D1 non-executable until the literal cap has
been materialized, inserted, hash-reviewed, and separately authorized. CKDD remains closed; CKDB
and CKDC remain closed; the formal CKDA HPC replay remains a separate obligation when the cluster
is available.
