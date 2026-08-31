# Frontend-F0 Zero-Training Semantic Prototype Implementation Report

- Date: 2026-08-31
- Branch: `codex/exp-mainline`
- Status: **IMPLEMENTATION PASS; SYNTHETIC ZT-1 PASS; REAL ZT-2 NOT AUTHORIZED**
- Governing protocol: `frontend_f0_controlled_zero_training_semantics_protocol_frozen_20260831.md`
- Governing protocol SHA-256: `532bb52e4d03c0321f1e874cc4bd7a49fca3391943c0dd23a1968fd69ac3c0ee`
- Review mode: owner explicitly waived another Kimi review for this implementation; Codex performed implementation self-review and exact contract execution

## 1. Authorization consumed

The user's authorization is interpreted narrowly as:

1. implement the deterministic H1-H4 semantic prototype;
2. implement and execute synthetic contract tests;
3. verify Python 3.9 compatibility;
4. write, commit, and push implementation evidence.

This work did **not** open any real PCAP, label, report, FINAL, model, score,
weight, or representation artifact. It did not train, fit, tune, retrieve a
checkpoint, use the network, submit HPC work, or alter an incumbent decision.

## 2. Implemented files and byte identities

| File | Lines | SHA-256 |
|---|---:|---|
| `repo/ood/issue27frontend_f0_zero_training_semantics_v1.py` | 639 | `00366fdef9d644c2ac60fab68047938e6bcc4425aab68e1f6c1ae552db40affa` |
| `repo/ood/issue27frontend_f0_zero_training_semantics_contract_tests_v1.py` | 414 | `dc425738a2ee2c07eb65f30c33272f8f5d0cef37238b8aaec2ceda56a59a8b10` |

The implementation contains no real-input command. A later authorized ZT-2
runner may import the engine only after a new execution gate.

## 3. Implemented semantics

The implementation mechanically realizes the frozen hierarchy:

- H1: IPv4/IPv6 TCP/UDP transport contexts with token-and-port keys;
- H2: every other IP protocol, including port-bearing non-TCP/UDP protocols,
  with ports excluded from the key;
- H3: non-IP paired link-event contexts;
- H4: bounded keyless blocks split by base-class change, strict idle/span/event
  overflow, and never forced to singleton or capture-wide pseudo-session form.

All tiers share:

- per-member first-seen endpoint tokens;
- opaque SHA-256 context identifiers;
- current-inclusive limits of 256 events, 300.0 surrogate seconds, and a
  strict-greater-than 60.0 second idle split;
- monotone timestamp clamping without sorting;
- source/member isolation;
- two-pass discovery of the last frozen target per base context;
- release after the last target and refusal to rebuild from irrelevant tail
  packets;
- exact one-row-per-target conservation and a closed missing-reason dictionary.

The module exposes explicit construction-role guards. Any label, report,
FINAL, model, score, representation, or weight request fails closed. The
decoder adapter requests only declared semantic fields and never requests a
payload field.

## 4. Synthetic contract result

Command executed under the actual installed Python 3.9 runtime:

```text
py -3.9 repo/ood/issue27frontend_f0_zero_training_semantics_contract_tests_v1.py
```

Result:

```json
{"status": "PASS", "tests": 36}
```

The 36 tests cover all 32 minimum frozen obligations plus four additional
guards:

1. port-bearing non-TCP/UDP remains H2 and ports do not partition contexts;
2. corrupt decode receives the exact literal reason;
3. missing packet ordinal receives the exact literal reason;
4. an H4 base class that returns after an intervening class starts a new epoch.

The minimum battery includes bidirectional H1, ICMP/GRE/other-IP H2, H3, H4
anti-degeneracy, member/source reset, exact boundary equality, 256/257 split,
current inclusion, future invariance, timestamp regression, endpoint bijection,
raw-identity exclusion, no payload request, UID conservation, all prohibited
role gates, empty final state, tail non-reentry, clean/resume byte identity,
Python 3.9 syntax/runtime, no-learning static AST inspection, engineering
failure verdict removal, and complete SHA256SUMS coverage.

## 5. Self-review findings

### 5.1 Scientific-rule drift

No frozen constant, hierarchy rule, denominator, terminal state, or PASS
meaning was changed. The implementation has no observed-data-dependent branch.

### 5.2 Python 3.9 gate

The full battery passed on the machine's actual Python 3.9 interpreter, not
only through a newer interpreter's compatibility parser. The implementation
does not use `match`, `Path.write_text(newline=...)`, or another known project
incompatibility class.

### 5.3 Zero-training boundary

An AST-based audit rejects learning-library imports and fitting/backpropagation
calls. It intentionally analyzes syntax rather than raw source substrings, so
the audit cannot flag its own denylist literals as false positives.

### 5.4 Residual risk

Synthetic PASS proves that the declared semantic engine obeys the frozen
contract on adversarial fixtures. It does **not** prove that the 30 real packet
members expose every required decoder field, that the real 25,467 targets meet
the availability gates, or that any learned representation will be useful.
Those are ZT-2 and later questions and remain unopened.

## 6. Current terminal and next gate

Current status:

```text
IMPLEMENTATION_PASS
ZT_1_SYNTHETIC_SEMANTICS_PASS
ZT_2_REAL_EXECUTION_NOT_AUTHORIZED
```

The next legal action is a separately authorized ZT-2 real count-only causal
re-decode using the reviewed 30 packet members and exact Step-0b cutoffs. A
future runner must add pre-open identity checks, member-atomic checkpoints,
fresh storage/resource gates, output identities, and durable failure markers.
No learned embedding or detector evaluation is authorized by this result.
