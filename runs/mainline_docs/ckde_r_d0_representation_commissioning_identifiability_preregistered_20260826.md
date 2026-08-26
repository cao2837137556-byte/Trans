# CKDE-R D0 — representation commissioning identifiability audit (FROZEN)

**Date:** 2026-08-26
**Status:** FROZEN; non-executable pending independent hash/diff review and separate user authorization
**Route:** CKDE-R / deterministic representation-level commissioning
**Reviewed design basis:** `ckde_r_route_kimi_round2_convergence_20260826.md` at commit `c730a17`
**Independent draft review:** `ckde_r_d0_draft_kimi_review_20260826.md` at commit `54c4a3f`

## 1. Question and claim ceiling

CKDE-R keeps the operational premise that a newly enrolled device may provide a causal,
explicitly benign commissioning prefix. It changes how that prefix is used. Rather than moving
the scalar P2 threshold, CKDE-R asks whether the prefix identifies a stable device-domain shift
in the frozen E3 representation that can be removed by one globally fixed, deterministic affine
rule before the unchanged P2 attack head is applied.

This D0 does **not** implement an adapter and does not measure benign suffix improvement. It asks
whether the proposed representation shift is:

1. identifiable from legal same-device evidence;
2. stable at independent-session scale;
3. sufficiently separated from attack evidence to justify a later experiment; and
4. safe under a predeclared synthetic-shift falsification test.

The highest possible D0 result is authorization to draft a separately named D1 protocol. No D0
result is a detector improvement, an attack-preservation result, or a paper-level cross-device
claim.

With no same-device benign-prefix plus attack evidence, synthetic translations and cross-device
stress remain falsification tools only. They can kill CKDE-R but can never establish positive
within-device attack safety. That positive claim requires a separately preregistered untouched or
FINAL one-shot confirmation.

## 2. Frozen identities and dimensionality correction

The following existing artifacts are the only proposed inputs. Every SHA must pass before any
row or array is opened.

| Artifact | SHA-256 |
|---|---|
| `runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local/ckde_d0_verdict.json` | `c1953c55d999ac151426d5d9f6fa9fdcbaddfd725fe966ebf09def1c62f47033` |
| `runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local/ckde_d0_device_lineage_census.csv` | `9ce04164ce6db9917d9fe8d1dedae612ed727f78460e1db0882afe6dc1d69f9b` |
| `runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local/ckde_d0_same_device_pairing.csv` | `6f904325c712fcbe081eb8250780d32479862dc468e5fbcaf3d88e3f9667d9ee` |
| `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_embeddings.npz` | `b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099` |
| `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_embeddings.npz.metadata.csv.gz` | `120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd` |
| `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_plan.csv` | `eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac` |
| `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_probe_state.npz` | `50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38` |

### 2.1 Blocking factual correction to the discussion shorthand

The live frozen E3 representation is **768-dimensional**, not 132-dimensional:

```text
ckda_d1_fit_select_embeddings.npz["representation"].shape = (25,467, 768)
normalizer_mean.shape = normalizer_scale.shape = (768,)
P2 first-layer input width = 769 = 768 normalized coordinates + 1 missingness indicator
```

Therefore a device-local diagonal estimator contains 768 location and 768 scale coordinates.
The earlier 132D small-sample argument understated, rather than overstated, the stability risk.
This D0 uses the actual 768D identity and allows the stability ladder to reject diagonal affine
calibration without substituting a post-result dimension-reduction candidate.

No report embedding, report score, support-val value, FINAL object, PCAP, new download, or newly
trained representation is an allowed input.

## 3. Stage isolation and irreversible order

D0 executes in the following order. Later stages may not run if an earlier stage terminates.

```text
I0  identity/hash/schema validation
I1  Audit-0 metadata-only paired-device identifiability
I2  benign-prefix session representation census and stability ladder
I3  same-family device/attack entanglement audit
I4  synthetic-shift fit-attack falsification
I5  verdict, validation, hashes, and package
```

At the end of I1, the exact eligible device/family incidence graph and the Audit-0 verdict are
atomically written and hashed. If Audit-0 fails, D0 emits state A and stops before opening any
embedding vector. It may not continue "for diagnostic interest."

I2 chooses the candidate class from benign-prefix stability only. I3 and I4 are kill-only: they
may demote the selected class to state B, but may not promote center-only to diagonal affine,
change a constant, or select another transformation.

## 4. Audit-0 — paired-device identifiability

### 4.1 Units and legal roles

Device identity is the frozen `source_group` only when lineage proves one deployment/capture
device and one-to-one raw-source identity. Dataset name, attack family, held-pool name, or an
outcome-derived cluster is never a device key.

The global fit-benign reference may use only the fit roles:

```text
id_calib, aux_fit, aux_normal_fit
```

Attack evidence may use only:

```text
support_train, aux_process_fit
```

Select benign roles may later supply commissioning prefixes, but they cannot create a benign
center for a fit-attack device in Audit-0. `support_val`, all viewed/report roles, and FINAL are
forbidden.

Session identity remains the frozen causal key:

```text
source_id + pcap_member + canonical_bidirectional_5tuple_with_protocol
```

One long session counts once regardless of record volume.

### 4.2 Four mechanical checks

Audit-0 must produce all of the following without reading an embedding value:

1. every legal fit-attack row maps to one stable `device_key` and session key;
2. an attack device has at least **64 complete, causally prior fit-benign sessions** from the
   allowed fit-benign roles, sufficient to estimate its device center;
3. an eligible device-family cell has at least **15 independent attack sessions**;
4. the eligible device-family incidence graph contains at least one complete `2 devices x 2
   attack families` cycle: two devices each contain both families, and each of the four cells
   meets condition 3.

Condition 4 is the minimum design that separates device movement from family identity. A graph
without a 2x2 cycle is treated as device/family confounding, even if it contains many records.

Audit-0 passes only if all four checks pass. Otherwise D0 returns:

```text
A = NO_IDENTIFIABLE_PAIRED_DEVICE_SUPPORT
```

with one or more literal reason codes:

```text
ATTACK_DEVICE_UNMAPPED
NO_SAME_DEVICE_FIT_BENIGN_CENTER
INSUFFICIENT_ATTACK_SESSIONS_PER_CELL
NO_TWO_BY_TWO_DEVICE_FAMILY_CYCLE
DEVICE_FAMILY_CONFOUNDED
```

No viewed/report/FINAL evidence may repair this result. Synthetic shifts cannot upgrade state A.

## 5. Representation units and fixed estimators

This section is reached only after Audit-0 passes.

### 5.1 Equal-session aggregation

For every complete session, the session representation is the coordinate-wise median of its
finite 768D record representations. A session with any dimensional drift, missing UID join, or
no finite complete record vector is invalid. Sessions are never weighted by record count.

For each device, commissioning sessions are ordered by first causal event position and then by
the frozen session key. D0 consumes exactly the first **64** complete legal prefix sessions. It
does not backfill from suffix events or use 128/256-session outcomes to select a class.

### 5.2 Global reference

Let `m_s` be one session vector from the legal fit-benign roles. The global reference is:

```text
mu_g[j] = median_s m_s[j]
sigma_g[j] = max(1.4826 * median_s |m_s[j] - mu_g[j]|, 1e-6)
```

The `1e-6` floor is literal. A coordinate at the floor is reported and remains identity-scaled;
it cannot receive device-specific scale amplification.

### 5.3 Device estimates and globally frozen shrinkage

For device `d`, using its 64 session vectors:

```text
mu_raw_d[j] = median_s m_s[j]
sigma_raw_d[j] = max(1.4826 * median_s |m_s[j] - mu_raw_d[j]|,
                     0.10 * sigma_g[j])

lambda_center = 0.50
lambda_scale  = 0.25

mu_d[j] = mu_g[j] + lambda_center * (mu_raw_d[j] - mu_g[j])
log_sigma_d[j] = log(sigma_g[j]) + lambda_scale *
                 (log(sigma_raw_d[j]) - log(sigma_g[j]))
```

The shrinkage constants are global literals. They are not functions of device, family, score,
bootstrap result, or suffix outcome.

The two possible later transformation classes are defined now only to make stability auditable:

```text
CENTER_ONLY:
  T_d(z) = z - (mu_d - mu_g)

DIAGONAL_AFFINE:
  T_d(z)[j] = mu_g[j] + sigma_g[j] / exp(log_sigma_d[j]) * (z[j] - mu_d[j])
```

Coordinates with `sigma_g[j] == 1e-6` use scale ratio exactly `1.0` in both full and bootstrap
calculations. Neither class is executable on suffix or report data in D0.

## 6. Literal bootstrap stability ladder

### 6.1 Bootstrap procedure

For each device, generate exactly **1,000** session bootstrap replicates of size 64 with
replacement. Replicate seeds are the first 64 bits of:

```text
SHA256("CKDE-R-D0|device_key|replicate_id")
```

where `replicate_id = 0..999`. Recompute the shrunken center and scale from each replicate.

For each replicate `b`:

```text
E_center[d,b] = sqrt(mean_j(((mu_d_b[j] - mu_d_full[j]) / sigma_g[j])^2))
E_scale[d,b]  = sqrt(mean_j((log_sigma_d_b[j] - log_sigma_d_full[j])^2))
```

For each device, define `Q95_center[d]` and `Q95_scale[d]` as the higher empirical 95th
percentile: sorted element `ceil(1000*0.95)-1`, zero-based, without interpolation.

### 6.2 Frozen gates

Center stability passes only if:

```text
at least 80% of eligible devices (ceil(0.80*N)) have Q95_center <= 0.15
AND every eligible device has Q95_center <= 0.35
```

Diagonal-scale stability passes only if:

```text
center stability passes
AND at least 80% of eligible devices have Q95_scale <= 0.10
AND every eligible device has Q95_scale <= 0.25
```

The interpretation is literal: `0.15` is 15% RMS of the global robust coordinate scale;
`0.10` log-scale error is approximately 10.5% multiplicative RMS. The worst-device guards
prevent an equal-device macro from hiding one unstable commissioned device.

The ladder is mechanical and uses no score or suffix result:

```text
if diagonal-scale stability passes: provisional class = DIAGONAL_AFFINE
else if center stability passes:     provisional class = CENTER_ONLY
else:                                state B, reason CENTER_SHIFT_UNSTABLE
```

No PCA dimension, shrinkage value, session budget, or alternative estimator may be introduced
after observing these results.

## 7. Same-family device/attack entanglement audit

This section runs only for the Audit-0 2x2-supported device-family cells and the I2 provisional
class. For each eligible family `f` and unordered device pair `(d1,d2)`, compute:

```text
Delta_b = mu_raw_d1 - mu_raw_d2
Delta_a = attack_median[f,d1] - attack_median[f,d2]

cosine = dot(Delta_a, Delta_b) / (||Delta_a|| * ||Delta_b||)
projection = max(0, dot(Delta_a, Delta_b) / ||Delta_b||^2)
```

`attack_median[f,d]` is the coordinate-wise median of equal-weight independent attack-session
vectors in the eligible cell. Zero-norm pairs are invalid and fail closed.

Use exactly 1,000 deterministic cluster bootstrap replicates over attack sessions within each
device-family cell, with device pairs retained as clusters. The route is declared sufficiently
disentangled only if both one-sided 95% upper confidence bounds satisfy:

```text
upper95(weighted-median cosine) <= 0.25
upper95(weighted-median projection) <= 0.25
```

Pair weights are equal; record counts never weight a pair. Failing either gate produces state B
with reason `ATTACK_SHIFT_ENTANGLED`. The values are reported verbatim and cannot tune the affine
class.

This audit is positive evidence only about the eligible fit device-family graph. It is not
same-device attack confirmation for the 23 development commissioning devices.

## 8. Synthetic-shift attack falsification

For every eligible development benign device shift `v_d = mu_raw_d - mu_g`, construct a synthetic
device context for every legal fit-attack representation `z_a`:

```text
z_synthetic = z_a + v_d
z_test = T_d(z_synthetic)
```

Apply the frozen E3 normalizer, unchanged missingness convention, frozen P2 head, and frozen P2
threshold. This test explicitly assumes additive transport of device context. Section 7 tests
whether that assumption is even approximately compatible with observed same-family movement.

The provisional class passes only when, for **every** eligible device transform:

```text
global fit-attack recall loss <= 0.5 percentage points versus frozen P2
each frozen major family with >=15 fit rows loses <=2 percentage points
no non-finite representation or score is classified as success
```

Any failure produces state B with reason `SYNTHETIC_SHIFT_ATTACK_SAFETY_FAIL`. Passing remains
falsification survival, not positive device-internal attack safety.

## 9. Non-degeneration record

CKDE-R is representation-space calibration. A scalar-score z-score or per-device scalar affine
score map is excluded because it is only a threshold transformation. Per-coordinate 768D
standardization followed by the nonlinear P2 head is not scalar-threshold-equivalent and belongs
to the diagonal-affine class above.

Likewise, only a device-normality p-value used directly as the alarm is excluded as a replay of
the M7 normality-filter mechanism. This protocol makes no claim about conformal methods in
general.

D0 records, but does not select on, the relationship between original and transformed fit scores:
Spearman rank correlation, maximum absolute score delta, and hard-decision disagreement. If the
later D1 candidate is observationally equivalent to a scalar threshold on every audited row,
that D1 must terminate as `DEGENERATE_SCORE_SPACE_RECALIBRATION`; D0 survival does not waive this
later functional contract.

## 10. Verdict state machine

Exactly one scientific state is allowed:

### A — `NO_IDENTIFIABLE_PAIRED_DEVICE_SUPPORT`

Audit-0 fails. Stop before embeddings. No representation commissioning experiment is justified
from current evidence.

### B — `NO_STABLE_DEVICE_SHIFT`

Audit-0 passes, but at least one required safety property fails. The verdict must include one or
more literal subreasons:

```text
CENTER_SHIFT_UNSTABLE
ATTACK_SHIFT_ENTANGLED
SYNTHETIC_SHIFT_ATTACK_SAFETY_FAIL
```

Here "stable" means safely usable: a reproducible benign shift that is entangled with attack
evidence is not an admissible device shift.

### C — `GO_CENTER_ONLY`

Audit-0, center stability, entanglement, and synthetic safety all pass; diagonal scale stability
fails. This authorizes only a request to draft a center-only D1 protocol.

### D — `GO_DIAGONAL_AFFINE`

Audit-0, center stability, diagonal scale stability, entanglement, and synthetic safety all pass.
This authorizes only a request to draft a diagonal-affine D1 protocol.

Engineering failure is separate:

```text
CKDE_R_D0_ENGINEERING_FAILURE_NO_VERDICT
```

An engineering failure deletes any partial scientific verdict and preserves only failure and
pre-open audit evidence.

## 11. Required outputs

D0 must emit at least:

```text
ckde_r_d0_input_identity.json
ckde_r_d0_pairing_incidence.csv
ckde_r_d0_pairing_graph_audit.json
ckde_r_d0_session_denominators.csv
ckde_r_d0_global_reference_audit.json
ckde_r_d0_bootstrap_stability_by_device.csv
ckde_r_d0_stability_summary.json
ckde_r_d0_entanglement_pairs.csv
ckde_r_d0_entanglement_bootstrap.json
ckde_r_d0_synthetic_shift_attack_metrics.csv
ckde_r_d0_non_degeneracy_diagnostic.csv
ckde_r_d0_role_open_audit.json
ckde_r_d0_verdict.json
ckde_r_d0_validation_report.json
SHA256SUMS
```

For state A, embedding-derived outputs must be absent and the role/open audit must prove zero
embedding array opens. Every table reports device, independent-session, and record denominators
where applicable.

## 12. Required implementation contracts

At minimum, tests must pin:

1. every input path, SHA, schema, and row/array shape;
2. actual E3 width 768 and P2 input width 769; any 132D assumption fails closed;
3. exact role allowlists and pre-open rejection of support-val/report/FINAL;
4. stable device lineage and exact UID/session joins;
5. source/member protocol-state isolation and canonical bidirectional session keys;
6. Audit-0 runs before any embedding open and state A leaves no embedding-derived output;
7. 64 complete sessions, causal order, equal-session weighting, and no record pseudoreplication;
8. future mutation cannot change a prefix session vector or device estimate;
9. coordinate median, MAD constants/floors, shrinkage literals, and scale-floor identity behavior;
10. 1,000 deterministic bootstrap seeds and higher-percentile indexing;
11. literal center and scale stability thresholds including worst-device guards;
12. the 2x2 incidence-cycle test and device/family confounding rejection;
13. pairwise cosine/projection formulas and zero-norm failure;
14. entanglement bootstrap and one-sided upper-bound gates;
15. synthetic additive shift, unchanged P2 state, and all-device attack-safety gates;
16. state priority A before B before C/D and no post-result candidate substitution;
17. three denominator levels and explicit invalid/missing counts;
18. no PCAP, download, training, suffix outcome, report, or FINAL access;
19. Python 3.9 grammar and the previously observed runtime-API regression scan;
20. atomic readback, complete hashes, and engineering failure with no scientific verdict.

## 13. Review questions

1. Is the Audit-0 `2 devices x 2 families`, 15 independent sessions per cell cycle the minimum
   defensible identifiability gate, or is a stronger graph required?
2. Are `lambda_center=0.50` and `lambda_scale=0.25` conservative enough given the corrected 768D
   representation identity?
3. Are the literal stability gates (`0.15/0.35` center, `0.10/0.25` log-scale) interpretable and
   sufficiently selection-proof?
4. Are the entanglement upper bounds of `0.25` too permissive, too strict, or scientifically
   justified as a quarter-shift ceiling?
5. Should an entanglement failure remain a subreason of state B, or require a fifth named state?
6. Is synthetic additive translation acceptable as kill-only falsification under the stated
   claim ceiling?
7. Does state A correctly stop before opening embeddings even though this forfeits descriptive
   stability statistics?

## 14. Authorization boundary

This FROZEN D0 authorizes no implementation, no execution, no embedding or score opening, no benign
suffix evaluation, no support-val/report/FINAL access, no PCAP decode, no download, no training,
and no HPC submission.

After independent hash/diff review of this FROZEN D0 and its SHA sidecar, implementation and execution
remain separately authorization-gated. CKDE-Q Stage A is an independent one-shot archival task
and is not authorized by this document. CKDB, CKDC, and CKDD remain closed. The formal CKDA D1
HPC replay remains pending cluster recovery.
