# Frontend-F0 / Data-F0 — Kimi Round 3 Review (Three Drafts + Three Open Numerical Items)

- Reviewer: Kimi
- Date: 2026-08-28
- Inputs: Codex Round 2 (`6e8225e`) + three DRAFT protocols
- Verdict: **ROUND 2 ACCEPTED; all three drafts DRAFT-PASS with one MODIFY each on the
  numerical open items (N1, N2-amendment, N3).** Codex may freeze after mechanical
  incorporation. Drafting-stage only: no implementation, network, download, training,
  embedding, FINAL, or HPC authorized.

## 1. Independent verification of the Round 2 static-inspection claims

Codex's narrowing of K1 to four literal missing predicates is the load-bearing claim of
this round, so I verified it against the pinned source myself:

- Pinned hashes recomputed and matched: embedder `360cbaa7...de14`, local two-pass
  adapter `9f11d03b...4ca2`, my CKDE-S terminal review `fddd32a9...b61f`.
- Source read of `issue27ckda_d1_e3_embed_v1.py` (missing branch): a target is marked
  missing exactly when — session is `None` (no IPv4/IPv6 session key), OR
  `ip_proto not in {6, 17}`, OR non-finite timestamp, OR the session is in the
  poisoned `unencodable_sessions` set (timestamp regression). **Four predicates
  confirmed verbatim.** Only two reason classes are stored, and the reason is hashed
  into the missing session identity rather than kept as a reversible field — exactly as
  Codex reported, which is why the audit must reconstruct predicate booleans rather than
  read a stored label.
- The 144-packet bound (`BoundedNetfoundPrefix`) does not appear in the missing
  condition; batch failure raises an engineering error. Confirmed: neither is a
  missingness branch.
- Mechanistic cross-check: the TCP/UDP-only gate `{6, 17}` explains the zero finite
  coverage of `Merlin ICMP Flooding` (ICMP = protocol 1) and `Mirai GRE Flooding`
  (GRE = protocol 47) — they are unencodable *by design*, not by budget. This turns one
  of our open mysteries into a confirmed mechanism, and it means the Step-0 audit's real
  open question is where the **benign** 75% sits among the four predicates
  (session-key vs regression vs protocol).

I also endorse Codex's honest caveat, which now becomes a binding claim boundary:
missingness repair cannot be marketed as a hydraulic-false-positive fix; the committed
CKDB diagnosis (hydraulic error survives after excluding missing rows) stands.

## 2. Rulings on the three open numerical items

### N1 — Absolute encodability gate for the challenger (instrument draft §4.1)

Proposed literals, to be frozen before challenger embeddings exist:

```text
overall terminal-session finite rate >= 0.90        (frozen fit/select universe)
every fit-benign device finite rate >= 0.80         (worst-device guard)
every declared-supported exact attack family >= 0.80 (worst-family guard)
```

Rationale and conditions:

1. The netFound baseline (24.9% benign overall; worst device 0.91%) makes these gates
   demanding but absolute — a challenger that cannot encode the traffic is not a
   challenger, and a relative improvement over 24.9% that still leaves half the pool
   missing is a NO-GO.
2. The gates apply **within a protocol-support matrix declared in Stage I**, before any
   embedding exists. Sessions outside declared support are named exclusions carrying the
   challenger's own literal missing-reason dictionary — never silent drops.
3. A family outside declared support inherits our existing discipline: it is
   `UNPROTECTED_BY_REPRESENTATION_EVIDENCE` for that frontend and can never be claimed
   as representation-protected later.
4. If the challenger declares support for a protocol and still misses ≥20% of a
   group's sessions, the gate fails — declared support creates accountability.

### N2 — Cross-dimension reuse of 0.20/0.35 and 20°/35° (instrument draft §4.2)

**ACCEPT, with one mandatory amendment (dimension-rank feasibility) and a documentation
requirement.** The guards are mathematically dimension-free:

- Normalized projection distance `||P−P'||_F / sqrt(2r)`: for two independent random
  rank-r subspaces in d dimensions the null expectation is `sqrt(1 − r/d) ≈ 1` whenever
  d ≫ r — essentially independent of d. The 0.20/0.35 guards therefore measure the same
  thing at any realistic challenger dimension.
- Largest principal angle: inherently dimension-free; the null for random subspaces at
  d ≫ r is near 90° (our observed worst failure was 89.36° ≈ orthogonal). The 20°/35°
  guards retain full discriminative power at any d ≫ r.
- Between/within R gates are ratios of norms — dimension-free.
- The count-only rank rule `min(4, floor((D−1)/3))` depends only on device count.

Mandatory amendment — the rank rule needs a dimension-feasibility clause, frozen now:

```text
r_required = min(4, floor((D_finite − 1)/3))
if d_challenger <= r_required:  F0_DEVICE_GEOMETRY_NO_GO (literal, no retry)
```

A challenger whose representation is too small to host the required rank cannot
participate; this must be decidable from Stage I metadata (declared output dimension),
before embeddings exist. The FROZEN protocol must also record the null-model
justification above so the constants' portability is auditable, not asserted.

### N3 — Data-F0 minimum split 8 = 6 Data-T + 2 Data-E (Data-F0 draft §D/§5)

**ACCEPT the minimum; MODIFY the split rule to scale with observed N, frozen now:**

```text
minimum: N >= 8 paired devices, else NO_IDENTIFIABLE_PAIRED_DEVICE_SPLIT
Data-E count = max(2, ceil(N/4))   (deterministic hash order as drafted, first
                                    Data-E count devices become Data-E)
Data-T = remainder, must satisfy Data-T >= 6
```

Rationale: at N = 8 the formula yields exactly the proposed 2/6 minimum, so nothing is
weakened. But fixing Data-E at 2 regardless of N wastes confirmation power when a corpus
offers more: with N = 30, two untouched devices confirm on 6.7% of the evidence while 28
devices feed development. Since the formula is fixed **before N is observed**, it is not
outcome-fitted — it is a pre-committed allocation rule. The untouched confirmation set
should grow with the evidence base. (Data-E uses remain sealed from
training/calibration/selection/thresholding/design exactly as drafted.)

## 3. Draft-specific review notes

**Missingness Mechanism Audit (Step 0):** PASS. The four-predicate dictionary matches
the verified source; the frozen precedence affects only a descriptive `primary_reason`
column and cannot erase secondary booleans; M1's identifiability gate
(`NO_IDENTIFIABLE_MISSINGNESS_MECHANISM_WITHOUT_REDECODE`) correctly forbids inferring
causes from device/family rates; the M2 conservation laws are the right integrity
invariants; M3's configuration-only classification (seven preserved properties) cleanly
separates "re-encode repair" from "new frontend semantics". One expectation for the
record: the audit's real open question is the benign-cause distribution; the attack-side
zero-coverage of ICMP/GRE is already mechanistically explained by the protocol gate.

**Measurement Instrument:** PASS with N1/N2 incorporated. The K2-A/K2-B split is
dimensionally and scientifically correct; "same P2 = same contract retrained from
scratch, never reused weights" is the only valid reading. The mandatory shallow-header
control (§4.4) is an excellent addition — it prevents "signal" that is merely
packet-header identity leakage from promoting a challenger; I explicitly endorse it.
The backup-frontend activation only via preregistered engineering-incompatibility plus
digest-matched blocking review correctly prevents model-zoo hopping after a scientific
failure.

**Data-F0:** PASS with N3 incorporated. The five pairing gates (§C), PENDING-not-positive
for unknown victim identity, hash-ordered deterministic split, task-relevance descriptors
defined without outcome labels, and "engineering HTTP failure does not activate
candidate 2" are all correct. The Q7-style digest-matched blocking review for candidate
2 is faithfully reproduced.

## 4. Authorization state

Drafting-stage review complete. Next steps per draft: mechanical incorporation of
N1/N2/N3 → FROZEN + SHA sidecar per protocol → my SHA/diff terminal review per
protocol → separate user authorizations for each execution stage (Step-0 audit
execution; Data-F0 metadata retrieval; instrument Stage I). No implementation, network,
download, training, embedding, FINAL, report, or HPC is authorized by this review.
