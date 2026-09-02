# Frontend-F1 D1 one-shot local training result

Date: 2026-09-02

Authorization: one real local training attempt only. Select, viewed, report,
FINAL, HPC, hyperparameter sweeps, and a second attempt were not authorized.

Frozen numerical contract:
`runs/mainline_docs/frontend_f1_d1_numerical_addendum_frozen_20260902.md`

Input corpus:
`runs/frontend_f1_d1_fit_corpus_v1_20260902_local/f1_d1_fit_contexts.jsonl.gz`

Output:
`runs/frontend_f1_d1_one_shot_training_v1_20260902_local`

## Result

```text
status = F1_D1_NO_ELIGIBLE_CHECKPOINT
epochs completed = 31
cumulative training seconds = 9152.1472516
best epoch = none
best checkpoint = absent
select opened = 0 (by construction; no eligible checkpoint)
viewed/report/FINAL opened = 0
engineering failure = absent
```

All 31 ledger rows have `eligible=false`. The early-stop counter reached the
frozen value 12 at epoch 30, so the runner stopped without substituting the
last epoch or relaxing a gate.

## Independent package verification

The four entries in the result `SHA256SUMS` file were independently recomputed
from disk and all matched:

```text
f1_d1_internal_split.json
f1_d1_resume.pt
f1_d1_training_status.json
f1_d1_vocabulary.json
```

No training process remained after the terminal status was written. There is
no `engineering_failure.json`, no `scientific_stop.json`, and no
`f1_d1_best.pt`.

## Fit-only terminal-state diagnostic

A read-only diagnostic loaded the terminal epoch-31 resume state and evaluated
only the frozen 4,400-row internal-validation split. It did not open select,
viewed, report, or FINAL data and did not change or resume training.

```text
representations finite = true
protected A benign-normal rows = 1,174
new hard benign rows = 0
protected A attack-hard rows = 2,000
attack rows flipped to normal = 5
terminal checkpoint eligible = false
```

This terminal diagnostic explains why the final state could not be accepted;
the per-epoch ledger proves that no earlier epoch was eligible but does not
persist per-gate violation counts for every earlier epoch. The diagnostic must
therefore not be generalized into a claim that the same five rows were the
only violation at every epoch.

## Claim boundary and next state

This is a clean scientific `NO_ELIGIBLE_CHECKPOINT`, not an engineering
failure. The frozen incumbent netFound + P2 deployment was never modified, so
the negative result does not reduce existing system capability. It also does
not authorize a second seed, changed loss, changed margin, hyperparameter
sweep, select evaluation, or a new encoder.

The one-shot Frontend-F1 training branch is closed under the frozen protocol.
Any further route requires a new design discussion and a separately frozen
protocol; this run itself supplies no positive capability claim.
