# Frontend-F1 D1 terminal no-eligible diagnostic result

Date: 2026-09-04

Scope: read-only diagnosis of the terminal epoch-31 model on the frozen
4,400-row fit/internal-validation split. No training/resume, parameter change,
select, viewed, report, FINAL, PCAP, network, or HPC access occurred.

Result directory:
`runs/frontend_f1_d1_terminal_no_eligible_diagnostic_v1_20260904`

## Reproducibility and boundaries

- Six inputs were byte-pinned before model or corpus access: trainer, fit
  corpus, terminal resume state, terminal status, frozen P2 state, and frozen
  numerical contract.
- The terminal state and the previously reported denominators were reproduced:
  31/31 epochs ineligible, 2,000 protected A attacks, five terminal flips,
  1,174 protected A benign rows, zero new benign hard rows, and finite
  representations.
- A second complete diagnostic execution produced a byte-identical
  `SHA256SUMS` file (`b8ffd08c...9ff3e39`).
- Result-member hashes independently recorded in `SHA256SUMS`: 3/3.

Two serializer-only implementation errors were encountered before the first
complete result (strict CSV extra fields and a Python-3.9 `Path.write_text`
API difference). Both failed before a terminal diagnostic JSON or checksum
set existed; they changed no scientific calculation. The fixes only made the
declared columns explicit and used a Python-3.9-compatible atomic text writer.

## Exact finding

All five terminal attack flips are distinct contexts from the frozen
`normal_scanning1.pcap` / `ToN-reconnaissance_scan` internal-validation
denominator. This does not localize the problem to a special family or source:
all 2,000 protected internal-validation attacks come from the same frozen
source/family.

| property | result |
|---|---:|
| unique failed contexts | 5 |
| target protocols | 4 TCP, 1 UDP |
| prefix event counts | 2, 3, 28, 29, 49 |
| rows with any UNK prefix token | 1/5 |
| threshold probability | 0.0651598722 |
| best failed probability | 0.0318678211 |
| other failed probabilities | 0.0053388836, 0.0004593436, 1.63e-33, 1.36e-34 |
| failed logit margin range | -75.3146940 to -0.7502402 |

The protected-attack median logit margin is `+27.5247912`; the failure median
is `-5.0217210`. The five failures are therefore not a floating-point or
one-ULP threshold accident. Two are extremely confident normal-side mappings.

The failures are also not explained by one context-length regime, by the old
missing route, or by vocabulary mismatch: all five are ordinary keyable H1
TCP/UDP A-side contexts, their lengths span short and longer prefixes, and four
contain no UNK token at all.

## Scientific interpretation

The terminal GRU learned finite representations and preserved benign-normal
behavior, but it did not preserve the frozen P2 attack semantics for a small
set of reconnaissance sequences. This is a representation-alignment failure,
not a threshold-calibration failure and not a recurrence of the solved
semantic-coverage problem.

The authorized fit corpus persists only the old teacher's categorical
`attack_hard` bit, not its continuous incumbent score. Consequently this
diagnostic cannot tell whether those five targets were barely or strongly hard
under the incumbent. It would be improper to reconstruct or invent that
margin, or to open the combined fit/select score artifact without a new narrow
authorization boundary.

## Decision consequence

The current frozen one-shot model remains rejected and the incumbent remains
unchanged. A parameter tweak or second training run is not justified by this
diagnostic. The evidence rules out cheap fixes based only on threshold epsilon,
vocabulary expansion, or longer prefixes.

The next design decision is therefore between:

1. materializing the incumbent continuous margins for these fit-only targets
   under a separately frozen, physically fit-only procedure, to distinguish
   approximate-teacher error from severe semantic forgetting; or
2. closing this student/P2 interface and treating attack-preserving B-side
   learning as data-limited until stronger paired B attack evidence exists.

Neither option is authorized by this diagnostic.
