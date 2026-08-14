# CKDA D1 local contingency addendum — DRAFT FOR INDEPENDENT REVIEW

Date: 2026-08-14
Branch: `codex/exp-mainline`
Base commit before this addendum: `7e840cc`
User authorization: run CKDA D1 locally while the school HPC is unavailable.
Review boundary: precompute/census may run now; E3 fit/select embeddings remain gated on Kimi review of this addendum and implementation. Report remains sealed.

## 1. Reason and claim boundary

The school HPC is expected to remain unavailable until 2026-08-23. This addendum permits a resumable Windows CPU execution without changing the frozen CKDA D1 scientific question, candidate, target rows, target positions, probe definitions, thresholds, action gate, or FINAL exclusion.

Local execution is contingency evidence, not a silent replacement for the preregistered AMD Slurm run. A later result-producing HPC replay must confirm the local result before a paper claim is promoted. Any material local/HPC discrepancy invalidates the affected claim and triggers diagnosis, not result selection.

No `cooler-motor`, seed 37, seed 47, or other FINAL asset may be opened. No family-specific condition or patch is permitted.

## 2. Frozen scientific identity retained

| Item | Frozen/local identity |
|---|---|
| Contract SHA-256 | `ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9` |
| Candidate progression | I1 benign gate, then frozen E3 fallback |
| E3 checkpoint SHA-256 | `e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105` |
| Frozen fit/select rows | 25,467 = 18,398 fit + 7,069 select |
| Frozen report rows | 262,050, still sealed |
| Snapshot SHA-256 | `b2ef1f7d0244cc7abb8665c25364744f794190f411482e4e202e346cb850279c` |
| Predictions SHA-256 | `d1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85` |
| D0 manifest SHA-256 | `9184cd018efcc6547832bf04ce6d3046c687b8e48cac73234482d9fb3ba89689` |
| E3 device/dtype | CPU / float32 |
| Batch size | 16 |
| Probe and gate code | Frozen D1 bundle, unmodified |

The locally regenerated fit/select role plan has SHA-256 `eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac`, matching its deterministic frozen inputs. Target metadata contains exactly 25,467 unique UIDs with 0 FINAL files opened.

The formal D0 manifest itself remains SHA-pinned. For local decoding, a generated derivative changes only `container_path` from the HPC mount to the corresponding local Gotham ZIP or ToN PCAP. All other six columns, including source ID, member, cutoff, role, and original lineage source, must be cell-identical to the formal manifest. The derivative and an audit JSON are generated atomically before census; it is not a new scientific manifest. The verified derivative has SHA-256 `afd8f700e64d799d15c2375c3a887b388423a982c7af72d1cb45b85de2ac8e01`, with 27/27 path cells rebound and zero non-path changes.

## 3. Local environment

- Windows 11, Intel i7-12700H, 16 GiB RAM.
- Python 3.9.13.
- PyTorch 2.8.0 CPU, NumPy 2.0.2, pandas 2.3.1, scikit-learn 1.6.1.
- Transformers 4.57.3, tokenizers 0.22.2, huggingface-hub 0.36.2, safetensors 0.6.2.
- TShark 4.6.6 at `C:\Program Files\Wireshark\tshark.exe`.
- Offline model loading; no network model fetch.

D0's real 100-session local pilot reproduced the frozen E3 input, config, checkpoint, and forward-shape identities. Local CPU forward time was about 3.4 times the prior AMD CPU pilot; elapsed time is an engineering estimate, not a scientific metric.

## 4. Preflight-discovered formal frontend incompatibility

The D1 formal E3 embedder decodes packets with CKBU but translates flows with the D0 netFound frontend:

- CKBU requests 24 TShark fields.
- D0 netFound requests 27 TShark fields.
- Neither set contains the other; their deterministic ordered union contains 39 fields.
- In particular, the frozen CKBU row lacks fields such as `tcp.seq_raw`, `tcp.ack_raw`, `tcp.window_size_value`, and IP header fields required by `netfound_flow`.

The unmodified formal chain therefore fails before an embedding on a real benign member (`tcp.seq_raw` missing). This is classified as `PRE_RESULT_FRONTEND_FIELDSET_INCOMPATIBILITY`; it has no scientific verdict. It would affect the HPC formal chain as well and is not caused by a target family or observed performance.

The local engineering repair requests the ordered union once and supplies the same row to CKBU identity parsing and D0 netFound translation. Missing protocol fields represented as `None`, literal `"None"`, or empty string are normalized to the Linux empty-string convention. No non-missing value, packet, target, label, family, cutoff, or order is changed.

Future HPC D1 packaging must incorporate and independently review the same union-field repair before replay.

## 5. Memory-bounded exact E3 adapter

The frozen one-pass embedder retains bounded prefix state for every encodable session encountered before a member's last target. Its formal allocation is 64 GiB; the local host has 16 GiB. The local adapter changes storage, not target semantics:

1. Pass 1 decodes only through the frozen last target and discovers which canonical sessions own frozen target positions.
2. Pass 2 decodes the same prefix and retains state only for those target sessions.
3. A target uses the same current-inclusive `BoundedNetfoundPrefix.flow()` and frozen batch order.
4. State is released only after that session's last frozen target.
5. The frozen model, tokenizer, collator, combine routine, checkpoint schema, UID order, and atomic writer are reused.

The adapter is resumable per immutable member identity. Local checkpoints are isolated under a `localwin` namespace and must not be reused by the HPC replay.

## 6. Real-input equivalence evidence

The gate selected the lexicographically deterministic cheapest real fit/select member and compared 32 target prefixes, batch size 16, width 768:

- Dataset member: `raw/benign/iotsim-building-monitor-2_0-0_to_OpenvSwitch-28_2-0.pcap`.
- Maximum event position: 149.
- Frozen one-pass checkpoint SHA-256: `f19c06bac8197a0cae88c19bb69d38c1d974b91f4525aec91fadea9f40875161`.
- Local two-pass checkpoint SHA-256: `f19c06bac8197a0cae88c19bb69d38c1d974b91f4525aec91fadea9f40875161`.
- Maximum absolute representation delta: `0.0`.
- UID, missing flag, session ID, timestamp, event position, plan, member, and contract arrays: byte-value equal.
- Local peak retained target sessions: 1.
- Verdict: `CKDA_D1_LOCAL_TWOPASS_REAL_EQUIVALENCE_PASS`.

This proves exact equality for the exercised real path. It does not prove cross-machine floating-point identity for all 25,467/262,050 rows; the later HPC replay remains required.

## 7. Staging and stop rules

### Stage L0 — authorized now

- Verify immutable hashes and Python/TShark versions.
- Run real one-pass/two-pass equivalence gate.
- Regenerate fit/select role plan.
- Run exact benign-only I1 census with member checkpoints.
- Materialize frozen I1-to-E3 progression.
- Materialize fit/select target metadata.

L0 reads no report labels or FINAL assets and generates no performance embedding.

### Stage L1 — only after Kimi PASS on this addendum and code

- Generate E3 fit/select embeddings with member checkpoints.
- Fit frozen G0/P1/P2 probes.
- Freeze thresholds.
- Stop with report still sealed.

### Stage L2 — separately gated

The report role plan, report metadata, report embeddings, scores, bootstrap metrics, scientific state, validation, and packaging remain forbidden until the threshold marker exists and the local L1 artifacts receive independent review. A local L1 PASS is not permission to open report.

## 8. Failure and resumption semantics

- Every long unit writes identity-checked checkpoints.
- Rerun reuses only checkpoints whose contract, plan, member, and UID identities match.
- An engineering failure emits a null scientific verdict and preserves completed units.
- No checkpoint is deleted or silently overwritten to recover from failure.
- A code or identity hash change refuses resume and requires a newly named route or reviewed repair.
- Available disk and RAM are engineering gates; resource exhaustion is not scientific evidence.

## 9. Requested Kimi review

Please decide:

1. Is the 39-field union the minimal correct repair of the formal CKBU/D0 E3 frontend mismatch?
2. Does the two-pass target-session filter preserve the frozen current-inclusive prefix semantics?
3. Is the 32-real-target byte-identical gate sufficient to authorize local fit/select embeddings, with HPC confirmation retained as mandatory?
4. Are the L0/L1/L2 boundaries strict enough to preserve one-shot report isolation?

Until those four answers are PASS, the local process stops after L0.
