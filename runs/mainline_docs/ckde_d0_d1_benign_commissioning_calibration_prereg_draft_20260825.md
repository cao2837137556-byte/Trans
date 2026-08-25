# CKDE D0/D1 — new-device benign commissioning calibration (DRAFT)

**Date:** 2026-08-25
**Status:** design draft; not frozen; no execution authorized

## 1. Capability being added

CKDE changes the operational question.  It does not claim that a detector can identify every new
device zero-shot.  It asks whether a globally fixed algorithm can use a small, explicitly benign
commissioning prefix from a newly enrolled device to calibrate the frozen E3/P2 attack score,
then reduce that device's later benign false alarms without erasing attacks.

This is a system-capability upgrade through **per-device evidence**, not a device-family patch:

- the algorithm and all constants are global and frozen;
- each device contributes only its own causal commissioning prefix;
- device/family identity is never a learned routing feature;
- the zero-shot P2 arm remains the baseline;
- a device with no valid prefix stays fail-closed on the zero-shot decision.

Existing viewed pools can support development, stress testing, and kill-only gates.  They cannot
support the final cross-device positive claim.  That requires a separately preregistered
untouched-device/FINAL one-shot confirmation.

## 2. D0 first: is the problem identifiable in current artifacts?

Before any calibration formula is frozen, a metadata-only D0 must answer five hard questions.
It may read immutable manifests, role plans, source/member identity, timestamps/recorded order,
and session keys.  It may not read report scores or labels, fit a threshold, access FINAL, or
decode a PCAP.

### 2.1 Deployment-device identity

There must be a stable device key that can be reproduced before score access.  A `source_group`
is acceptable only if lineage proves it denotes one deployment device/capture context.  Dataset,
attack family, held-pool name, or an outcome-derived cluster is not a device key.

### 2.2 Causal commissioning prefix

For each eligible device, D0 must prove that the proposed benign prefix precedes every evaluation
event under real timestamp or source-local causal order.  Random record splits and future-to-past
calibration are forbidden.  The prefix must come from a role whose publisher/protocol semantics
declare it benign; labels cannot be consulted row by row to carve a clean prefix.

### 2.3 Same-device benign and attack evaluation

D0 must census how many devices have all of:

1. a legal benign commissioning prefix;
2. a later benign suffix for FPR evaluation;
3. a later attack population attributable to the same device key for recall evaluation.

If attack and benign corpora cannot be paired to the same deployment device, CKDE cannot claim
that calibration preserves attack detection on the calibrated device.  Cross-product stress
(applying one device's threshold to unrelated attacks) may be reported as conservative
development evidence, but it is not a paired-device confirmation.

### 2.4 Independent-session support

Session identity inherits CKDA's causal key:

```text
source_id + pcap_member + canonical_bidirectional_5tuple
```

with protocol included and state reset at each source/member boundary.  D0 reports, for every
device and candidate prefix, three denominators: devices, independent sessions, records.
Thousands of records from one long TCP session count as one independent session.

### 2.5 Untouched confirmation inventory

D0 inventories untouched eligible devices after excluding all fit/select development devices,
all already-viewed report devices, and FINAL.  Absence of such devices does not permit recycling
viewed pools into positive evidence; it limits D1 to development and leaves final confirmation
pending.

## 3. D0 verdicts

Exactly one is allowed:

1. `CKDE_D0_PAIRED_CALIBRATION_IDENTIFIABLE` — enough same-device causal prefixes, benign
   suffixes, attack suffixes, and independent sessions exist to design session-level CKDE.
2. `CKDE_D0_UNPAIRED_DEVELOPMENT_ONLY` — benign calibration/FPR can be tested, but same-device
   attack preservation cannot; only development and cross-product stress are authorized.
3. `CKDE_D0_INSUFFICIENT_INDEPENDENT_SESSIONS` — record volume is pseudo-replication.
4. `CKDE_D0_NO_CAUSAL_BENIGN_PREFIX` — the deployment assumption cannot be instantiated.
5. `CKDE_D0_ENGINEERING_FAILURE_NO_VERDICT`.

Only state 1 may support a later strict session/block conformal claim.  State 2 may still support
a prefix-quantile engineering study with no strict coverage guarantee and no positive
same-device attack claim.  States 3/4 stop the route unless genuinely new evidence is separately
authorized; they do not permit a record-level workaround.

## 4. D1 baseline and candidate arms (frozen only after D0)

The D1 protocol may contain one baseline and at most two calibration arms:

- **Z — zero-shot baseline:** unchanged frozen E3/P2 score and threshold.
- **Q — primary score-space calibration:** a globally identical causal benign-prefix quantile or
  session-conformal rule that maps the device prefix to a device-local alarm threshold.
- **C — optional mechanistic comparison:** frozen E3 embedding centering against the device's
  benign-prefix prototype, followed by one globally frozen scoring rule.

Q is the preregistered primary.  C cannot replace Q based on viewed results and cannot create a
third candidate.  The encoder, original P2 identity, device key, session key, prefix selection,
aggregation, quantile convention, tie behavior, and missing-data behavior are immutable before
any development score is opened.

## 5. Independent-session gate and calibration sizes

The calibration-size curve must be frozen after D0 count-only evidence but before D1 scores.  The
draft target is:

```text
record budgets: 0, 100, 500, 1000
independent-session budgets: 0 plus three globally fixed feasible levels chosen from D0 counts
```

The final FROZEN document must replace the second line with literal numbers and a deterministic
rule for devices that have fewer sessions.

If a prefix meets the frozen independent-session minimum, D1 may use session/block conformal and
state its finite-sample guarantee under the declared exchangeability assumptions.  If not, it
must downgrade automatically to prefix-quantile calibration and label the result
`NO_STRICT_COVERAGE_GUARANTEE`.  Record count can never upgrade that state.

The session score and record-to-session decision mapping must be frozen.  A conservative starting
proposal for review is session score = maximum frozen P2 record score in that session; no result
has yet authorized this aggregator.

## 6. Uniformity and fail-closed behavior

No per-device hyperparameter search is allowed.  Every device receives the same:

- prefix construction;
- session aggregation;
- calibration alpha/quantile convention;
- minimum-session gate;
- threshold cap or trust-region rule;
- missing/non-finite behavior.

No prefix, insufficient prefix, failed lineage, or suspected contamination preserves the
zero-shot P2 decision.  Calibration may not lower attack evidence by an unbounded amount.  The
later FROZEN protocol must specify a global bound using legal fit/select attacks only.

## 7. Contamination stress

Commissioning prefixes may contain attacks despite being operationally declared benign.  D1 must
predeclare a stress grid before score access.  Proposed review grid:

```text
0%, 0.1%, 0.5%, 1%, 5% contaminated independent sessions
```

Injection draws only from legal development attacks and respects whole-session units.  It cannot
use report/FINAL attacks or individual records.  Results report threshold movement, benign FPR,
attack recall, and fail-closed activation by contamination level.  The grid is a robustness test,
not a selector.

## 8. Development gates and final claim boundary

D1 development output must fill the 2x2 matrix with explicit denominators:

| | benign FPR | attack recall |
|---|---:|---:|
| known/fit-context device | required | required |
| new/calibrated device | required | required only when D0 proves paired identity |

Every cell reports devices, independent sessions, and records.  Macro averages cannot conceal a
failed device; per-device values and clustered intervals are mandatory.

The later D1 FROZEN protocol must set literal development gates before score opening.  Proposed
starting constraints for review are:

- 69/69 support-val attacks remain hard;
- global and unseen-source attack recall no more than 0.5 percentage points below zero-shot P2;
- no major attack family more than 2 percentage points below zero-shot P2;
- every eligible benign device is no worse than zero-shot P2;
- benign-OOD macro is materially reduced, with no device-specific exception;
- contamination stress never produces silent calibration success after its fail-closed gate.

A development pass authorizes only a request for untouched one-shot confirmation.  It does not
authorize FINAL access or a paper-level positive claim.

## 9. Non-goals and negative controls

- CKDE does not repair zero-shot first contact; Z remains the honest baseline.
- No family/source patch, hydraulic-specific threshold, generic episode classifier, or new data
  download is allowed.
- CKDB stays closed; CKDC stays closed; CKDD cannot be silently folded into CKDE.
- A record-level conformal claim is forbidden for long dependent sessions.
- C is rejected as degenerate if it is observationally equivalent to a Boolean P2/M7 AND rule or
  merely memorizes device identity.
- The outstanding formal CKDA HPC replay remains a separate obligation when the cluster returns.

## 10. Required D0 outputs and tests

D0 must emit device-lineage census, prefix/suffix causality, same-device pairing table,
independent-session counts, untouched-device inventory, role/open audit, verdict, validation
report, and `SHA256SUMS`.

Tests must cover exact identity joins, source/member reset, canonical bidirectional session key,
future mutation invariance, prefix strictly preceding suffix, one-session pseudo-replication,
paired versus unpaired devices, viewed/FINAL pre-open rejection, zero report-score/label reads,
Python 3.9 grammar and observed runtime APIs, atomic readback, and failure without verdict.

## 11. Review questions

1. Does the existing lineage support same-device benign-prefix and attack-suffix pairing, or is
   CKDE currently development-only?
2. What literal independent-session budgets should be frozen after the D0 count-only census?
3. Is session-maximum P2 score the right conservative aggregator, or should a different single
   aggregator be preregistered?
4. How should the global calibration trust-region cap be tied to legal attacks without turning
   support-val into a repeatedly tuned selector?
5. Is the proposed contamination grid adequate and operationally plausible?
6. Should optional arm C remain in D1, or should it be deferred until Q supplies a clean signal?

## 12. Authorization boundary

This DRAFT authorizes no implementation or execution.  D0 implementation, D0 execution, D1
freezing, embedding/score access, calibration, report opening, FINAL access, downloads, training,
and HPC each require the applicable review and explicit user authorization.
