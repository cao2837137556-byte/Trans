# Frontend-F1 D1 GPT review absorption and freeze record

- Date: 2026-09-02
- Reviewed DRAFT commit: `1d7433b`
- GPT review attachment SHA-256: `036e5f69eb9c5f62946b84e87129b4db5ef9717e5e151991f9a5554960dc870d`
- Resulting FROZEN SHA-256: `7cf06c5885e21b813f9f5933360bc18308f41038bdb60809e2343a612fafd860`
- Scope: scientific review absorption and numerical freeze only

## 1. Independent ruling

The external review's overall `MODIFY, then FROZEN` recommendation is accepted.
Its three substantive modifications address real risks rather than adding a
result-driven search surface.

### M1 — threshold-relative, label-aware teacher protection: ACCEPT

The original `z_old`-relative loss could force the new encoder to reproduce an
incumbent logit distance even when functional classification inheritance was
already satisfied. The frozen rule instead protects the known-correct side of
the incumbent threshold:

- true attack and old-hard: require `z_new >= z_0 + 0.25`;
- true benign and old-normal: require `z_new <= z_0 - 0.25`;
- true benign and old-hard remain excluded from teacher preservation and stay
  eligible for the fit-label loss.

The universal true-attack margin at `z_0 + 0.5` remains unchanged. Therefore
the attack-side teacher term is deliberately redundant as a functional
inheritance sentinel; it is not claimed as an independent optimization gain.

### M2 — same-input order-free control: ACCEPT WITH NARROWING

The prior 35D handcrafted summary did not isolate the value of sequence order,
because it used a different information interface from the GRU. It is replaced
by a deterministic 4097D control:

- 4096 normalized token-frequency coordinates from the exact frozen GRU token
  sequence;
- one normalized event-count coordinate, which is also derivable from that
  sequence.

The suggested exact-span feature is intentionally rejected: the GRU sees only
the frozen delta-bin tokens, not exact span seconds, so adding exact span would
give the control extra information. The resulting comparison changes only one
property—event order.

### M3 — full local determinism identity: ACCEPT

The FROZEN document now pins the Python executable and version, NumPy,
PyTorch, scikit-learn, Windows build, CPU identity, process-level thread
variables, Python/NumPy/PyTorch seeds, PyTorch thread counts, and deterministic
algorithm mode. Initial execution and resume must match the hashed runtime
manifest exactly.

## 2. Claim-boundary clarification

The source-held-out internal-validation split contains no B-side attack
contexts. Its attack AUROC is therefore a unified-encoder/A-dominated
representation diagnostic, not independent evidence that the blind-spot branch
detects attacks. B-side evidence remains limited to 29 legal-fit attack
contexts and the frozen 23-row select kill-only sentinel. No per-family positive
claim is authorized from those small denominators.

## 3. Zero-drift record

All other DRAFT choices are retained without change:

- single GRU candidate, one seed, no hyperparameter sweep or fallback;
- 4096-token vocabulary and 32/128/768 architecture;
- all-one normalized loss weights, `0.5` universal attack margin, and `0.25`
  teacher tolerance;
- AdamW, epoch/patience/checkpoint rules, resource caps, and local-only target;
- frozen A deployment path, deterministic old-missing routing, 69-row attack
  inheritance gate, and 4,812/482 B-benign utility gate;
- no select/viewed/report/FINAL access during training or checkpoint selection.

No implementation, corpus materialization, optimizer step, select opening, or
performance claim is authorized by this record.
