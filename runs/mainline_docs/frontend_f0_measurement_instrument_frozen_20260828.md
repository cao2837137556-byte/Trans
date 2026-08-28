# Frontend-F0 — Cross-Frontend Measurement Instrument (FROZEN)

- Date: 2026-08-28
- Status: **FROZEN; NON-EXECUTABLE pending independent SHA/diff terminal review and later stage-specific user authorization**
- Freeze basis: Kimi Round 3 review `96172df`; N1/N2 were incorporated mechanically
  before any challenger embedding existed.
- Reference frontend: frozen netFound E3
- Primary challenger: Pcap-Encoder, subject to checkpoint/license/runtime audit
- Backup: NetMamba only after a preregistered engineering-incompatibility state, never
  after a scientific Pcap-Encoder failure

## 1. Objective

Turn "less device identity while retaining attack information" into a falsifiable,
cross-frontend challenge. The challenge changes one factor at a time and does not permit
model-zoo hopping.

The Lane G *mathematical framework* is reused, but its netFound-specific arrays, rank
observation, trained P2 weights, gradients, and family eligibility are not.

## 2. Non-negotiable comparison contract

Every frontend uses:

- the same frozen fit/select target identities and causal cutoffs;
- the same source/device/session grouping and label isolation;
- equal-device/equal-session/equal-family weighting;
- a deterministic terminal-session representation;
- explicit missing/encodability rows with no silent target dropping;
- the same downstream head architecture, fit/select protocol, optimization budget, and
  threshold rules when the head-bound stage is reached; and
- Python/runtime, checkpoint, license, and pretraining-lineage identities pinned before
  real embeddings are opened.

"Same P2" means same method contract trained from scratch in each representation. Frozen
netFound-trained weights may not score another frontend.

## 3. Stage I — compatibility and resource audit (no embeddings)

Required checks:

1. official implementation and license;
2. official usable pretrained checkpoint, or explicit `NO_USABLE_OFFICIAL_CHECKPOINT`;
3. pretraining corpus lineage and possible overlap with every current fit/select/report/
   FINAL source;
4. raw packet fields and causal prefix requirements;
5. deterministic output unit and dimension;
6. unsupported protocol/session behavior and missing-state semantics;
7. CPU/GPU/RAM/disk/runtime estimate for frozen inference;
8. separate estimate for downstream head training; and
9. Python 3.9 and target-platform compatibility gates.

Stage I must also freeze a literal protocol-support matrix before any challenger
embedding exists. It must name every protocol declared supported and every protocol
declared outside scope, together with the challenger's literal missing-reason dictionary.
No protocol or family may be reclassified after challenger results are observed.

If no usable pretrained checkpoint exists, encoder pretraining is not silently folded
into Frontend-F0. It requires a new data/compute/lineage protocol.

## 4. Stage II-A — encoder-only instrument

This stage may run only after a separately frozen implementation and execution chain.
No downstream learned head is available here.

### 4.1 Availability

Report terminal-session finite rates by device and exact attack family. No target is
dropped. The challenger must expose literal missing reasons.

The advancement rule uses the following absolute gates, frozen before challenger
embeddings exist:

```text
overall terminal-session finite rate >= 0.90
every fit-benign device finite rate >= 0.80
every declared-supported exact attack family finite rate >= 0.80
```

The overall denominator is the frozen fit/select terminal-session universe restricted
only to the Stage-I declared-supported protocol matrix. All matrix-out targets remain in
the full census with a literal reason and are never silently dropped. Every attack family
outside declared support is named
`UNPROTECTED_BY_REPRESENTATION_EVIDENCE` and cannot later be claimed as
representation-protected. Declaring protocol support creates accountability: if any
declared-supported group misses at least 20% of its sessions, the gate fails.

### 4.2 Device geometry and causal stability

Apply dimensionless Lane G concepts with a count-only rank rule frozen before array
opening:

- causal early/late between-within ratio;
- leave-one-device-out projection distance;
- principal-angle stability; and
- median and worst-device guards.

Before any challenger representation array is opened, Stage I must compute:

```text
r_required = min(4, floor((D_finite - 1) / 3))
```

where `D_finite` is the count-only eligible-device total and `d_challenger` is the
declared output dimension. The mandatory feasibility condition is:

```text
r_required < d_challenger
```

If it is false, terminate literally with `F0_DEVICE_GEOMETRY_NO_GO`; there is no retry or
within-run rank reduction.

The existing absolute reference guards are proposed for reuse because they are
dimensionless:

```text
median projection distance <= 0.20
worst projection distance <= 0.35
median principal angle <= 20 degrees
worst principal angle <= 35 degrees
median between/within R >= 2.0
at least 80% of eligible devices have R >= 1.0
```

Independent review must confirm their cross-frontend applicability before freezing.
NetFound's measured `0.5757/89.3635°`, median `R=8.4643`, 13-device/rank-4 observation is
a pinned baseline table, not a replacement for absolute gates.

The guards are portable across realistic representation dimensions for explicit
dimensionless reasons. For independent random rank-`r` subspaces in `d` dimensions,
normalized projection distance has null expectation `sqrt(1-r/d)`, approximately 1 when
`d` is much larger than `r`; the random-subspace principal-angle null is near 90 degrees;
the between/within `R` guards are ratios; and the rank rule depends only on device count.
Thus the absolute constants test the same geometric properties across frontends rather
than inheriting netFound's coordinate dimension.

### 4.3 Fit-only attack information canary

Before head training, use only preregistered nonparametric geometry or a separately
authorized fixed-capacity canary. No select/report result may choose its form. The canary
asks whether exact attack-family structure remains observable; it is not a detector
claim.

### 4.4 Mandatory shallow-header control

A deterministic shallow header/statistical representation is evaluated under the same
encoder-only canary. A challenger must beat this control to show that any signal is not
merely packet-header identity leakage.

## 5. Stage II-B — head-bound attack-protection instrument

This stage is authorized only if II-A passes every frozen gate and the user separately
authorizes head training.

1. Train the same P2 architecture/protocol from scratch on challenger embeddings.
2. Freeze its fit-only state before any select/report scoring.
3. Recompute attack gradients in the challenger's coordinates.
4. Re-run equal-family attack-direction identifiability and residual-energy guards.
5. Name every unprotected family; no macro average can hide a failed family.

The old 768D P2 gradients are forbidden here. They are evidence about netFound only.

## 6. Advancement and stop states

Frozen state order:

```text
F0_ENGINEERING_INCOMPATIBLE
F0_LINEAGE_OR_LICENSE_NO_GO
F0_NO_USABLE_OFFICIAL_CHECKPOINT
F0_INSUFFICIENT_ENCODABILITY
F0_DEVICE_GEOMETRY_NO_GO
F0_ATTACK_INFORMATION_NO_GO
F0_HEADER_CONTROL_NOT_BEATEN
F0_ENCODER_ONLY_PASS
F1_ATTACK_PROTECTION_NO_GO
F1_FRONTEND_CHALLENGE_PASS
```

A relative improvement that still fails an absolute guard is NO-GO. A Pcap-Encoder
scientific failure ends the single-frontend challenge. Backup activation is allowed only
for a preregistered engineering incompatibility and requires a digest-matched blocking
review before any backup retrieval.

## 7. Later 2x2 experiment boundary

Frontend-F0 does not itself run the later attribution experiment. If both Frontend-F0
and Data-F0 qualify, the only first result design is:

```text
frontend: netFound vs qualified challenger
data role: current legal Data-T vs qualified paired Data-T
```

Evaluation is on deterministic untouched Data-E devices. No combination-only arm may run
first. This preserves attribution of frontend and data effects.

## 8. Authorization boundary

This FROZEN protocol authorizes no implementation, checkpoint retrieval, embedding
generation, head training, report/FINAL opening, network access, download, or HPC work.
Independent SHA/diff terminal review is next; every later stage requires separate user
authorization.
