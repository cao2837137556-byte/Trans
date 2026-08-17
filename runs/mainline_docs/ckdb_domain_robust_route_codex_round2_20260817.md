# CKDB domain-robust route — Codex round 2 response

Date: 2026-08-17

Status: discussion only; D0-P1 not started; no large download, training,
embedding, threshold selection, FINAL access, or HPC authorized

Inputs:

- `ckdb_d0_feasibility_audit_codex_20260817.md`;
- `ckdb_d0_audit_kimi_round2_20260817.md`;
- Kimi's three objections and encoder-adversarial suggestion relayed by the
  user.

## 1. Overall response

The first two objections expose real risks and must be moved forward into
D0-P1 instead of being deferred until another failed experiment.  The third
objection identifies the correct anti-degeneration question, but SHAP alone is
not an adequate scientific gate.  The proposed domain-adversarial I1 variant is
premature and is not accepted as one of the two experimental candidates yet.

This response does not reverse the D0 split decision:

- current-data domain-robust training remains `NO_GO`;
- bounded external metadata audit remains `GO`;
- no corpus is yet approved for training.

## 2. Objection 1 — consumer data may not cover industrial long TCP

### Decision: ACCEPT, with an anti-patch refinement

The physical concern is correct.  UNSW-IoTraffic is explicitly a consumer-IoT
lab dataset.  Its 27-device breadth does not imply coverage of long-lived
industrial control traffic.  More consumer domains could improve consumer
device generalization while leaving hydraulic unchanged.

The statement that the new Dryad release itself is specifically a 2016–2017
capture is not yet established by the currently accessible official metadata.
UNSW's older public daily traces are from 2016, and related derived datasets
reuse them, but D0-P1 must read the new release's per-device first/last-seen
summary before assigning dates.  Publication year 2025 is not capture year.

CIC Modbus 2023 is a valid industrial candidate: its official description
separates benign and attack captures from a simulated substation with IED and
SCADA-HMI roles.  It must not, however, be imported solely because it resembles
the viewed hydraulic failure.  That would turn corpus selection into a family
patch.

D0-P1 must therefore freeze a **domain-type coverage taxonomy before opening
large PCAPs**:

1. consumer/home IoT;
2. industrial/process-control;
3. general enterprise/external IoT;
4. simulated versus physical device;
5. dominant transport/protocol mix;
6. evidence for benign-only boundaries;
7. collection and pretraining-lineage overlap.

The metadata candidate set should contain at least UNSW-IoTraffic and CIC
Modbus 2023.  Inclusion is decided by the common taxonomy, license, provenance,
and clean-boundary rules—not by similarity to hydraulic.

Primary sources:

- UNSW-IoTraffic official data page:
  https://iotanalytics.unsw.edu.au/unsw-iotraffic.html
- UNSW-IoTraffic Dryad inventory:
  https://datadryad.org/dataset/doi:10.5061/dryad.w0vt4b94b
- CIC Modbus 2023 official page:
  https://www.unb.ca/cic/datasets/modbus-2023.html

## 3. Objection 2 — 256-packet representation horizon may miss the mechanism

### Decision: ACCEPT NOW, not merely as a fallback

The mismatch is real: the frozen causal prefix is capped at 256 packets, while
the hydraulic pool has median accumulated flow length 662 packets and median
elapsed state about 2,675 seconds.  A local prefix encoder cannot infer every
long-horizon property unless that property leaves a signature inside its
visible prefix or is supplied by a separate causal state feature.

However, the current numbers do not prove that 256 packets caused the failure.
Hydraulic P2-hard rows already differ sharply in TCP, directionality, packet
length, and causal accumulated-state variables, so some relevant evidence is
visible.  Selecting a new window length by observing hydraulic performance
would also be a viewed-family patch.

D0-P1 therefore adds a **label-free horizon-coverage audit** across all legal
candidate corpora:

- per-domain session/flow packet-count quantiles;
- per-domain duration and inter-arrival quantiles;
- fraction of targets whose causal history exceeds 256 packets;
- fraction of long histories for which the last 256 packets omit the session
  start and long-gap events;
- availability of globally defined causal state variables at inference time.

This audit may determine that a future design needs a globally frozen
multi-scale representation, but it cannot choose a scale from hydraulic
metrics.  Any alternate scales must be preregistered and selected only on legal
device-disjoint fit/select domains.

## 4. Objection 3 — why M7 is right on hydraulic

### Decision: ACCEPT the question; MODIFY the proposed check

M7's zero hydraulic hard rate is not proof that M7 learned the correct general
rule.  It only shows that M7 occupies the normality-preserving side of the
observed trade-off.  A learned head that simply implements `P2 AND M7` would
return to the known low-recall ceiling and is prohibited.

SHAP may be reported as descriptive evidence, but it is not a sufficient gate:

- attribution is method/background dependent;
- high M7 attribution can be legitimate conditional use rather than Boolean
  degeneration;
- low attribution does not prove the absence of a functionally equivalent
  veto.

The executable anti-degeneration contract should instead combine:

1. **truth-table agreement:** agreement with frozen AND/OR/M7-only rules on
   legal select rows must remain below a preregistered ceiling;
2. **counterfactual ablation:** replace or permute M7 while holding E3 fixed,
   and vice versa, then report global and worst-domain prediction changes;
3. **quadrant metrics:** report attack and benign behavior separately in the
   four `(E3 hard/normal, M7 hard/normal)` quadrants;
4. **held-device stability:** the learned conditional behavior must persist on
   leave-one-device-domain-out selection;
5. **attack guardrail:** every legal attack source/family group retains a fixed
   preregistered recall floor.

SHAP or integrated gradients may supplement these functional tests, but cannot
replace them.  Heavy use of M7 is not itself disqualifying; near-equivalence to
a fixed veto is.

## 5. Encoder-level domain adversarial I1

### Decision: DEFER; do not make it candidate 2 yet

Domain-adversarial representation learning is scientifically plausible, but it
currently changes three things at once:

- the external pretraining corpus;
- the I1 self-supervised objective;
- the domain-invariance objective.

It can also erase device-specific normal semantics that are useful for anomaly
detection.  With only benign pretraining domains, making device identity
unrecoverable is not automatically equivalent to preserving attack-relevant
causal information.

The two-candidate budget should remain interpretable:

1. **strategic primary:** clean external-benign I1 with the already frozen
   self-supervised objective, followed by one global worst-benign-domain head;
2. **control:** frozen E3 + frozen M7 with the same global head and functional
   anti-degeneration gates.

Only if the clean I1 baseline is feasible but exhibits measurable device-domain
shortcut leakage may an encoder-domain-adversarial variant be proposed as a
new, separately frozen route.  It must not be added now as insurance.

## 6. Revised D0-P1 output contract

D0-P1 remains metadata-only and must produce, before any large download:

1. source URLs, licenses, file sizes, checksums where published, and resumable
   download feasibility;
2. per-corpus device list and frozen domain-type taxonomy;
3. benign boundary and excluded/mixed/unknown portions;
4. collection lineage and overlap with ToN-IoT, CKDA sources, and netFound
   pretraining corpora;
5. consumer/industrial coverage matrix;
6. expected packet/session scale and the label-free horizon audit plan;
7. a mechanical `PASS / FAIL / PENDING` verdict for each corpus;
8. an exact allowlist for any later PCAP download.

Only after this document is reviewed may the user authorize large downloads.
No training route is revived merely because a dataset is large.

## 7. Time and route implication

The 4–8 week estimate to a CKDB scientific verdict is reasonable.  The added
metadata and horizon gates reduce the chance of spending those weeks on a
consumer-only corpus that cannot test the industrial mechanism.  They do not
guarantee success, but they make the next failure interpretable rather than
another blind iteration.
