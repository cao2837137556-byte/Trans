# Frontend-F1 D1 implementation report (implementation-only)

Date: 2026-09-02

Frozen protocol: `runs/mainline_docs/frontend_f1_d1_numerical_addendum_frozen_20260902.md`

Frozen protocol SHA-256: `7cf06c5885e21b813f9f5933360bc18308f41038bdb60809e2343a612fafd860`

## 1. Scope and result

The authorized implementation-only step is complete. No real fit corpus was
materialized, no optimizer step was run on real data, and no select, viewed,
report, or FINAL artifact was opened.

Implemented files:

- `repo/ood/issue27frontend_f1_d1_train_v1.py`
- `repo/ood/issue27frontend_f1_d1_train_contract_tests_v1.py`

The implementation is ready for independent code review. Real corpus
materialization and the one-shot local training remain separately gated.

## 2. Physical authorization boundaries

The runner exposes three separate modes and three distinct literal tokens:

1. `materialize-fit`: legal-fit semantic replay only;
2. `train-fit`: consumes only the frozen fit corpus and cannot open select;
3. `evaluate-select`: remains deliberately fail-closed until a separately
   reviewed frozen checkpoint and explicit select authorization exist.

All outputs must remain below repository `runs/`. Workspace-scope checks and
literal forbidden-path checks prevent viewed/report/FINAL paths from entering
fit materialization or training.

## 3. Implemented frozen semantics

- exact H1-H4 causal replay through the pinned zero-training semantic engine;
- two-pass member processing, tail release, no post-tail re-entry, and exact
  target-prefix indexing;
- train-only deterministic vocabulary (`PAD=0`, `UNK=1`, maximum 4,094 learned
  signatures) and frozen 4,096-token interface;
- the exact 300,576-parameter training graph and 292,352-parameter inference
  encoder;
- frozen old normalizer and P2 as parameter-free buffers;
- four context-equal normalized losses with the frozen label-aware teacher
  rules and attack margin;
- source-group internal validation, deterministic batch order, eligibility,
  early stop, one seed, and no hyperparameter fallback;
- byte-stable checkpoints, complete RNG/optimizer/loss-ledger resume identity,
  cumulative wall-time accounting, and scientific-identity checks;
- deterministic 4,097D same-token order-free control;
- fit-only availability precheck, collapse, device leakage, inherited rank-4
  geometry, linear attack-information canary, permutation nulls, and reported
  nearest-centroid cosine AUROC;
- atomic deterministic JSON/CSV/gzip/NPZ outputs and SHA256SUMS;
- 12 GiB launch-space, 8 GiB peak-RAM, 5 GiB durable-output, component wall,
  and 24-hour process-chain guards.

The fit availability output is explicitly named and bounded as a
`LEGAL_FIT_PRECHECK_ONLY_SELECT_UNOPENED`; it is not presented as the frozen
25,467-row availability verdict.

## 4. Fail-closed states

Scientific stops (for example vocabulary or resource NO-GO) are written as
scientific stops and are not mislabeled engineering failures. Protocol,
identity, implementation, or runtime faults delete any scientific verdict and
write `F1_ENGINEERING_OR_PROTOCOL_FAILURE` diagnostics.

If a frozen checkpoint exists, fit representation gates run before any select
opening. A failure emits `F1_REPRESENTATION_NO_GO`; a pass stops at
`F1_D1_FIT_GATE_PASS_AWAITING_SELECT_AUTHORIZATION` with all downstream-open
counters equal to zero.

## 5. Independent executable checks performed locally

Runtime identity was exercised under the frozen launch environment:

```text
Python 3.9.13
NumPy 2.0.2
PyTorch 2.8.0+cpu
scikit-learn 1.6.1
PYTHONHASHSEED=2701
OMP_NUM_THREADS=4
MKL_NUM_THREADS=4
torch threads=4 / interop=1
RUNTIME_PASS
```

Test result:

```text
F1_D1_CONTRACT_TESTS passed=70 failures=0 errors=0
```

The tests include causal-prefix mutation, H1/H4 replay, target/context
conservation, label-aware teacher behavior, parameter counts, exact loss
denominators, attack/benign checkpoint flips, nonfinite representations,
deterministic interruption/resume tensors and ledgers, collapse fixtures,
device leakage, inherited geometry, attack canary/control/null behavior,
scientific-vs-engineering failure classification, resource probes, and real
count-only input identity pins.

## 6. Current authorization state

```text
real fit corpus materialization = NOT RUN / NOT AUTHORIZED BY THIS STEP
real one-shot training          = NOT RUN / NOT AUTHORIZED BY THIS STEP
select evaluation               = LOCKED
viewed/report/FINAL             = UNOPENED
network/HPC                     = UNUSED
```

The next legal action after implementation review is a separate user decision
on fit-corpus materialization. Training must not be bundled into that decision.
