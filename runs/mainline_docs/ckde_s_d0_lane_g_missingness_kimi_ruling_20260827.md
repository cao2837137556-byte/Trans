# CKDE-S D0 Lane G Missingness — Kimi Ruling

- Reviewer: Kimi
- Date: 2026-08-27
- Ruling request: `runs/mainline_docs/ckde_s_d0_lane_g_real_execution_missingness_ruling_request_20260827.md` (commit `5702a1e`)
- Verdict: **Option A ACCEPTED with four mandatory amendments (A1–A4).** Engineering-failure
  classification of the first run stands. No code change or retry is authorized by this
  ruling; the chain is erratum → Kimi review → implementation + regression tests → fresh
  user execution authorization.

## 1. Independent verification of the reported facts

I independently recomputed the entire missingness census from the pinned artifacts,
reading **only** the `uid`/`missing` arrays plus plan/metadata (no representation
statistics, no scientific verdict). Every Codex-reported number reproduces exactly:

| Quantity | Codex | Kimi recount | Match |
|---|---:|---:|:--:|
| rows embedded / missing | 13,827 / 11,640 | 13,827 / 11,640 | YES |
| benign terminal sessions / finite / missing | 8,372 / 2,087 / 6,285 | 8,372 / 2,087 / 6,285 | YES |
| attack terminal sessions / finite / missing | 4,262 / 4,123 / 139 | 4,262 / 4,123 / 139 | YES |
| devices with ≥64 finite sessions | 13 (rank stays 4) | 13 (rank 4) | YES |
| `normal_1.pcap` finite sessions | 29 | 29 (finite rate 0.91% of 3,186) | YES |
| `iotsim-...-tls-1_0` finite sessions | 48 | 48 (rate 21.2%) | YES |
| families ≥15: before / after availability | 8 / 5 | 8 / 5 | YES |
| missing-terminal sessions with any earlier finite target | 0 | 0 of 6,424 | YES |

The earlier-target repair path is verifiably impossible: every missing-terminal session
is missing from its very first frozen target. Missingness is a whole-session property.

## 2. Additional facts surfaced by my recount (material to Q3)

The five finite-eligible families are named here so the record cannot blur them:

| Family | terminal sessions | finite |
|---|---:|---:|
| ToN-reconnaissance_scan | 2,000 | 2,000 |
| ToN-credential_bruteforce | 1,986 | 1,986 |
| Mirai TCP Flooding | 51 | 51 |
| Merlin TCP Flooding | 50 | 50 |
| Merlin UDP Flooding | 30 | 30 |

Unprotected by representation evidence: `Merlin C&C Communication` (28 → 1),
`Merlin ICMP Flooding` (43 → 0), `Mirai GRE Flooding` (60 → 0), plus the always-small
families (`Mirai UDP Flooding` 8 → 2, `Ingress Tool Transfer`, `File Download`,
`Mirai C&C Communication` — all below 15 regardless).

Two structural facts:

1. **Finite rate is strongly family- and device-structured, not random.** The two ToN
   families are 100% finite and supply 3,986 of 4,123 finite attack sessions (96.6%);
   the ICMP/GRE flooding families are 0% finite; benign finite rates range from 0.91%
   (`normal_1.pcap`) upward. Whatever the frozen encoding rule is, it does not act
   uniformly.
2. **The missingness channel is outside the representation adapter's reach.** In the
   frozen P2, a missing row's 768 coordinates are clamped to zero and its attack
   evidence flows through the 769th missingness indicator. The analytic gradient w.r.t.
   the 768 representation coordinates is exactly zero for missing rows (as the
   implementation itself enforces). The reserved D1 mechanism
   (`z_adapted = z − λ·U_remove·β_d`, contract §8) operates on frozen E3 representations
   and cannot create, remove, or alter a missing row. Therefore a Lane-G-derived adapter
   structurally cannot touch the detection channel used for the unprotected families.

## 3. Rulings on the four questions

### Q1 — "Complete causal session embedding" = terminal target with `missing=false`: YES

A missing embedding carries no 768-dimensional geometry; it is not a zero vector and
zero-filling it would measure the missingness channel rather than device geometry. The
frozen Lane G hypothesis lives in the 768D representation space, so the only admissible
reading is: **complete = terminal session target with `missing=false`, with no
earlier-target substitution** (substitution is both impossible on the pinned data and
would redefine the causal unit).

### Q2 — Option A is admissible; Option B is rejected — with four mandatory amendments

The pre-open count gate exists to prevent *outcome-dependent* gate selection. A
missingness recensus consumes only per-row availability booleans — no geometry, no
scores, no outcome statistics — so it cannot leak information usable to shop gates, ranks,
or families. The frozen fail-closed rules (rank change → stop, `D_finite < 9` → stop)
remove any residual selection freedom. Option B is rejected because missingness is a
deterministic property of the frozen encoding pipeline, not an artifact defect: for
whole-session-missing sessions no "complete embedding" can ever exist without replacing
the encoder, which would invalidate the entire frozen E3/P2 chain. Option B would be a
*permanent* closure on a denominator technicality.

Mandatory amendments to the Option A erratum:

- **A1 — staged array access.** The recensus may read ONLY the `uid` and `missing`
  arrays from the embeddings NPZ. The `representation` array and the probe-state NPZ
  remain unopened until every recensus gate has passed; the role-open audit gains a
  distinct recensus counter, and `embedding_arrays_opened` (representation) flips only
  after the recensus gates pass. This preserves the substance of "no statistics before
  denominators".
- **A2 — determinism and fail-closed exactness.** The recensus is a pure function of the
  pinned artifacts (no sampling, no ordering dependence). Stop conditions are literal:
  `D_finite < 9`, `rank < 2`, or recensus rank ≠ pre-open metadata rank (4) → new
  scientific state (Q4), no retry, no rank shopping.
- **A3 — mandatory missingness-structure diagnostics, no gates attached.** The recensus
  stage must additionally emit, verbatim: (a) per-device finite-rate table over all fit
  benign devices; (b) the full 12-family terminal/finite table; (c) a metadata-only
  comparison of finite vs missing sessions (terminal `event_position` distribution as a
  session-length proxy, records-per-session); and (d) the verbatim quotation of the
  frozen CKDA D1 missingness rule from the CKDA D1 protocol/probe documentation. These
  diagnostics carry **no gates** — they exist to bound claims and to let review verify
  the finite subset's structure. Attaching any gate to them now would be outcome-fitted,
  since their values are already partially observed.
- **A4 — claim caps.** All downstream geometry uses only finite-eligible devices (13) and
  families (5). Every Lane G claim is capped at "geometry of the encodable
  (`missing=false`) subset of the frozen fit pool." The two excluded devices and all
  unprotected families are named in the verdict JSON itself, not only in prose.

### Q3 — A five-family protection space is scientifically meaningful, under three named
conditions

1. **Equal-family construction holds.** `V_raw` spans one robust median direction per
   eligible family, so the ToN families' 96.6% row dominance does not dominate the span.
   The result report must nevertheless print the full 12-family table verbatim.
2. **Unprotected families are declared, loudly.** Merlin C&C, Merlin ICMP, Mirai GRE and
   the sub-15 families are `UNPROTECTED_BY_REPRESENTATION_EVIDENCE`. No G4 verdict may
   imply their safety. This matters most for Merlin C&C — the stealth family the M7 arm
   previously destroyed; the record must show it was never inside the protection
   certificate.
3. **The structural-immunity argument is a hypothesis, not a D0 claim.** Section 2 fact 2
   (missing-row detection channel is structurally outside the adapter's reach) may be
   recorded as a reasoning note, but its promotion to a claim requires explicit
   verification in any future D1 protocol (e.g., proving the adapter leaves
   missing-channel behavior untouched on a frozen stress set). D0 does not verify it.

With these conditions, a G4 on five families certifies exactly what it says: an
attack-orthogonal removable device subspace exists *for the families whose detection
actually uses representation geometry*. That is a meaningful and honestly bounded
answer — and notably, it covers the flooding/scanning families where the hydraulic-class
false-positive problem lives.

### Q4 — Availability failure is a scientific state (G0-family), not an engineering
failure

The first run's classification as engineering failure was correct: the implementation
assertion tripped on a condition the contract had not modeled. Going forward, the
recensus outcome is a property of the data, not of the code. The fail-closed branch is a
new literal scientific state:

`NO_IDENTIFIABLE_COMPLETE_SESSION_EMBEDDING_DENOMINATOR`

carrying the same no-retry semantics as other terminal states. On the observed pinned
inputs the recensus yields 13 devices / rank 4 / 5 families, so this state is armed but
not expected to fire.

## 4. Process record

Codex's handling is recorded as a process positive: fail-closed on first contact with
real data, rejected all five shortcuts for the right reasons, and requested a ruling
instead of patching. The missingness blind spot also applies retroactively to my own
implementation review — I approved the "missing terminal = engineering failure"
assertion without probing the inherited artifact's missing rate; noted as a reviewer
lesson (availability census belongs in pre-implementation review from now on).

## 5. Next authorization chain

1. Codex drafts the missingness erratum implementing Q1–Q4 + A1–A4 → Kimi narrow review.
2. Implementation + new regression tests (recensus staged access, fail-closed states,
   verbatim diagnostics) under the existing implementation authorization → Kimi diff
   review.
3. **Fresh user execution authorization** for the second real Lane G run.
4. Lane M, FINAL, report, training, HPC remain sealed throughout.
