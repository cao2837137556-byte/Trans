# CKDB D0 feasibility audit and route decision

Date: 2026-08-17

Author: Codex

Status: `D0 COMPLETE — CURRENT-DATA TRAINING NO_GO / EXTERNAL-BENIGN IMPORT GO`

## 1. Executive decision

CKDB must **not** wait for an advisor-provided loss formula.  Loss design is a
project responsibility; an advisor formula, if one is later supplied, is only
an optional candidate.

The five read-only audits lead to a split decision:

- **NO_GO** for immediately training a domain-robust head on the current legal
  CKDA fit pool.  The available domains are too few and label/domain identity
  is almost deterministic, so GroupDRO/IRM/CORAL-style training is not
  scientifically identifiable.
- **GO** for a bounded external-benign-corpus import stage, led by
  UNSW-IoTraffic.  This supplies genuinely new benign device domains and may
  also provide enough clean traffic to revive the domain-specific
  self-supervised encoder I1.
- The still-sealed cooler-motor family remains the only fresh in-project benign
  final.  It may be opened once, only after the entire method is frozen.  It is
  prohibited for route selection, hyperparameter selection, or another repair
  cycle.

This is not a claim that CKDB already works.  It is authorization to acquire
and audit new benign information before freezing a new experiment.

## 2. Boundary and reproducible evidence

This D0 performed no training, threshold selection, model selection, PCAP
decoding, or FINAL access.  It consumed already-open CKDA D1 metadata/scores,
the legal fit/select plan, and the already-exported CKCZ causal caches.

Reproducible artifacts:

- audit program: `scripts/issue27ckdb_d0_structural_audit.py`;
- machine-readable result:
  `runs/mainline_docs/ckdb_d0_structural_audit_20260817.json`;
- result SHA-256:
  `4b6ec3c7de76dcc628dc6516746fd69125757d5f9641395a5feea3b141c3047d`;
- Python 3.9 syntax compile: PASS;
- independent rerun: byte-identical result SHA, PASS;
- claim boundary in the result:
  `diagnostic_only_no_training_no_selection_no_final_open`.

The structural variables are causal, current-row features computed before the
state update.  The diagnostic therefore does not use future packets.

## 3. Fresh unseen benign evaluation audit

The existing project contains exactly one defensible fresh benign device
family:

- `iotsim-cooler-motor`, five sources, status `SEALED_NOT_OPENED` in
  `ckbk_untouched_final_holdout_manifest_v1.json`.

Its manifest explicitly prohibits route go/no-go, model/threshold selection,
and hard-pair construction before final open.  The four other OOD families are
not fresh: stream-consumer and hydraulic-system are development canaries;
ip-camera-street and predictive-maintenance are repeated-view report pools.

Decision:

- fresh-final availability: **PASS-CONDITIONAL**;
- spare fresh non-FINAL development domain: **FAIL**;
- cooler-motor remains sealed; CKDB gets no feedback after opening it.

Therefore the project needs external benign domains for development.  The
cooler-motor final cannot be spent to decide whether CKDB is worth pursuing.

## 4. Current training-domain identifiability audit

The legal CKDA fit plan contains 18,398 rows from 22 source files.  Collapsing
minor source variants into physical/collection domains yields only five benign
coarse domains (effective count by inverse HHI: 4.42):

| Benign domain | Rows |
|---|---:|
| building-monitor | 3,204 |
| combined-cycle | 3,600 |
| combined-cycle-tls | 1,409 |
| domotic-monitor | 1,800 |
| ToN-IoT external | 4,000 |

The attack side is even less balanced: 4,000 of 4,385 attack rows (91.22%) are
from ToN-IoT.  Outside ToN-IoT, a classifier that predicts only from the domain
name attains **99.68% label accuracy**.  Several domains are benign-only or
attack-only.

This is a hard identifiability failure.  A domain-robust optimizer could reduce
training loss by learning dataset identity rather than invariant attack
semantics.  It would be impossible to distinguish a real invariance from a
dataset shortcut on the legal development data.

Consequences:

- current-data-only GroupDRO: **NO_GO**;
- current-data-only IRM: **NO_GO**;
- current-data-only CORAL/domain adversarial training: **NO_GO**;
- adding source weights or hydraulic-specific weights: prohibited family/domain
  patch, **NO_GO**.

This restraint follows the known limitations of naïve worst-group optimization
and invariant-risk methods: group robustness requires meaningful predefined
groups and regularization, while invariance methods can fail when the available
training environments do not identify the desired invariant predictor.

Primary references:

- [GroupDRO, Sagawa et al.](https://arxiv.org/abs/1911.08731)
- [Invariant Risk Minimization](https://arxiv.org/abs/1907.02893)
- [Risks of Invariant Risk Minimization](https://arxiv.org/abs/2010.05761)
- [Deep CORAL](https://arxiv.org/abs/1607.01719)

## 5. Hydraulic mechanism diagnostic

The diagnostic covers 253,050 already-open causal report rows.  It compares
3,000 hydraulic benign rows with 6,000 viewed benign controls and 244,050
attack rows.  It does not turn the result into a hydraulic rule.

### 5.1 Hydraulic is structurally unlike the viewed benign controls

| Statistic | Hydraulic | Viewed benign controls | Attacks |
|---|---:|---:|---:|
| TCP fraction | 75.43% | 0.20% | 64.80% |
| UDP fraction | 23.70% | 99.80% | 27.12% |
| bidirectional-state fraction | 76.67% | 46.90% | 46.40% |
| median frame length | 90 B | 1,514 B | 69 B |
| median flow packets | 662 | 8,666.5 | 6 |
| median flow elapsed | 2,674.9 s | 56.1 s | 0.064 s |

On protocol prevalence, frame length, flow packet count, and pair-IAT
distributions, hydraulic is closer to the attack pool than to the viewed benign
controls.  This explains why two unrelated discriminators can agree that it
looks attack-like; it is not evidence of a random scoring accident.

### 5.2 The failure is concentrated in a coherent component

Among hydraulic rows:

- P2 marks 2,289 as attack.  They are 98.86% TCP, 99.83% bidirectional,
  with median 952 accumulated flow packets and 3,815.8 s flow elapsed.
- P2 marks 711 as normal.  They are 100% UDP, only 2.11% bidirectional,
  with median one flow packet and 0.029 ms flow elapsed.

So the 76.3% hard rate is almost exactly a long-lived bidirectional TCP
component.  That is a useful mechanism diagnosis, but using `TCP` or
`hydraulic` as a special exemption would be the forbidden family patch and
would also risk suppressing real TCP attacks.

Decision: hydraulic mechanism diagnosis **PASS**; family-specific repair
**NO_GO**.  The only acceptable response is to learn normal-device diversity
from additional domains.

## 6. External benign-corpus audit

### 6.1 Strategic primary: UNSW-IoTraffic

Official records describe 27 device-specific raw PCAPs, 95,543,405 packets,
4,944,041 flows, and 203 days of setup, idle, and interaction traffic.  Raw
PCAPs are approximately 26.9 GB uncompressed; Dryad lists `pcaps.zip` as
13.92 GB.  The archive has no event/interaction ground-truth annotations, so
the dataset cannot be assumed benign row-by-row without a provenance and file
manifest audit.

- [UNSW-IoTraffic official page](https://iotanalytics.unsw.edu.au/unsw-iotraffic.html)
- [Dryad DOI and file inventory](https://datadryad.org/dataset/doi%3A10.5061/dryad.w0vt4b94b)

Why rank first:

- 27 physical device domains give a credible leave-device-out design;
- packet and flow layers are both present;
- scale is comfortably above the I1 token threshold in packets, although the
  frozen session threshold still requires an exact census;
- it adds normal device diversity rather than tuning to hydraulic.

Required caveats:

- its pretraining/collection relationship to existing UNSW/ToN data must be
  checked before claiming `KNOWN_DISJOINT`;
- absence of attack labels means only explicitly verified benign capture
  portions may enter self-supervision;
- first import only the README and small summary manifest; the 13.92 GB PCAP
  archive is downloaded only after the metadata gate passes.

### 6.2 Supplementary candidates

| Dataset | Useful evidence | Limitation / role |
|---|---|---|
| [IoT-23](https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/) | Three real benign devices with PCAPs, CC-BY | Only about 427k benign packets; supplement, not enough alone for I1 |
| [CIC Modbus 2023](https://www.unb.ca/cic/datasets/modbus-2023.html) | Separate benign PCAPs from a simulated substation | Structurally relevant, but cannot be chosen only because hydraulic failed; include only in a broad preregistered corpus mix |
| [CICIoT2023](https://www.unb.ca/cic/datasets/iotdataset-2023.html) | Large mixed benign/attack IoT collection with PCAPs | Requires exact benign-directory, license/access, and overlap audit before use |

Decision: external corpus availability **GO**, with UNSW-IoTraffic metadata
audit first.  No corpus is yet authorized for model fitting.

## 7. Independent loss design (no advisor dependency)

The project can define the candidate objective itself.  Once enough legal
device domains exist, the conservative starting point is a global
worst-benign-domain objective, not IRM and not a hydraulic-specific term.

For head `h` over a frozen representation, let `G_B` be legal benign device
domains and `G_A` be legal attack source/family groups:

```text
L_attack = mean_{g in G_A} mean_{i in g} BCE(h(x_i), 1)
L_benign_worst = tau * log sum_{g in G_B}
                 exp(mean_{i in g} BCE(h(x_i), 0) / tau)
L_total = L_attack + lambda * L_benign_worst + beta * L_regularization
```

Interpretation: preserve attack evidence while minimizing the smooth maximum
false-alarm loss across benign device domains.  It is global and uses the same
rule for every domain.

This formula is only a D0 candidate, not frozen or authorized.  Before any
training, the next preregistration must define:

- exact domain keys and minimum per-domain support;
- leave-one-device-domain-out selection;
- fixed candidate grid for `lambda`, `tau`, and regularization;
- worst-domain OOD and attack-source guardrails;
- anti-degeneration check showing the learned head is not merely rediscovering
  Boolean AND/OR or an M7 veto;
- one-shot cooler-motor opening with no post-open repair.

The strategic primary remains external-benign I1 self-supervision if its clean
session/token census passes.  A frozen E3-based global worst-domain head is the
control route, not an unlimited second search.

## 8. GO/NO_GO matrix and next action

| D0 item | Decision | Meaning |
|---|---|---|
| fresh benign final | PASS-CONDITIONAL | cooler-motor exists but remains one-shot FINAL |
| spare fresh development domain | FAIL | current four OOD pools are viewed |
| current training-domain identifiability | FAIL | five benign domains; near-deterministic label/domain confounding |
| advisor formula availability | NOT A GATE | project defines its own candidate loss |
| external clean benign corpus | GO-TO-METADATA-AUDIT | UNSW-IoTraffic ranked first |
| hydraulic mechanism | PASS | structural shift confirmed; no family patch allowed |

### Authorized scientific recommendation

The next bounded stage should be `CKDB D0-P1 external-benign manifest and
census`, with these steps:

1. download only the UNSW-IoTraffic README and device summary;
2. freeze file/device allowlists, collection/overlap status, and benign-use
   criteria before opening PCAPs;
3. if metadata passes, resumably download `pcaps.zip`, verify repository hashes,
   and perform a label-free session/token census;
4. freeze device-disjoint fit/select partitions before any embedding or model
   training;
5. return for review and explicit authorization.

No training, HPC submission, FINAL access, or threshold search is authorized
by this report.  CKDA formal HPC replay remains a separate confirmation task
when the school cluster returns.
