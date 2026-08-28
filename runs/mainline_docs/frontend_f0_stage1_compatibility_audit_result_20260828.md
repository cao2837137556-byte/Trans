# Frontend-F0 Stage I compatibility audit — result

- Date: 2026-08-28
- Frozen contract: `frontend_f0_measurement_instrument_frozen_20260828.md`
- Contract SHA-256: `197015f0a6dd5c5510b5859d12aa19813a877392c8b985f6b1fcc4fe20f81a00`
- Primary candidate: Pcap-Encoder
- Verdict: **`F0_NO_USABLE_OFFICIAL_CHECKPOINT`**

## 1. Outcome first

Pcap-Encoder passed the code/license, declared-lineage, raw-input-shape, output-dimension,
and syntax-level compatibility portions of Stage I. It did not pass the immutable
checkpoint-identity requirement. The official repository links a `weights.pth` object,
but the official materials inspected in this authorized metadata stage publish neither
its byte count nor its SHA-256. The checkpoint itself was not downloaded. Therefore its
identity cannot be pinned before any challenger result exists.

Under the frozen state machine this is not an engineering incompatibility and does not
activate NetMamba. It is also not a scientific failure of Pcap-Encoder. It is a
reproducibility/identity stop, and no challenger embedding is authorized.

## 2. Reproduced facts

- Official code: `SmartData-Polito/Debunk_Traffic_Representation`, commit
  `1a48f44c0a09665865271e60614c1dd5ee9735b2`.
- Code license: MIT; the pinned `LICENSE` SHA-256 is
  `375f4d26364e18cef7c9c43c883ab402f63575d8fc214ce86653699dafe7cf87`.
- Encoder: T5-base; upstream representation unit is one packet, dimension 768.
- Official pretraining corpora named by the paper: MAWI, UNSW-NB15, and an anonymous
  university campus trace. No known raw-identity overlap with the current project role
  sources was established from the inspected official metadata.
- Official environment: Python 3.10.16, PyTorch 2.2.2+cu118, Transformers 4.39.1.
  A Python-3.9 grammar parse of 22 source files found zero syntax failures, but no
  Python-3.9 runtime claim is made.
- The upstream preprocessing reads raw PCAP through Scapy, strips TCP/UDP payload, keeps
  ICMP material, and constructs IPv4/IPv6 packet-header inputs. The inspected code
  does not establish an ICMPv6-specific branch, so ICMPv6 remains outside the declared scope.
- The upstream code emits packet representations; it does not define the project's
  deterministic terminal-session aggregation. A separately frozen adapter would have
  been required had checkpoint identity passed.

## 3. Protocol-support identity frozen by this audit

Declared supported scope is IPv4/IPv6 TCP and UDP plus IPv4 ICMP. Non-IP packets,
ICMPv6, and IP protocols outside TCP/UDP/ICMP remain outside scope. This conservative
matrix may not be widened
after challenger results. The project-side missing-reason dictionary is recorded in
`frontend_f0_stage1_audit.json` and `frontend_f0_stage1_protocol_support.csv`.

## 4. Resources (estimate, not benchmark)

The candidate is T5-base class (~220M parameters). Frozen inference is GPU-preferred;
CPU feasibility is not a throughput claim. The preregistered planning estimate is 8–16
GiB RAM and 2–4 GiB disk for environment/model/cache. Runtime was not measured, and
downstream head training remains a separate later authorization.

## 5. Boundary audit

All are zero: checkpoint files downloaded, embedding arrays opened, training runs,
report opens, and FINAL opens. No backup candidate was accessed or activated.

## 6. Verification

- Frontend Stage-I contract tests: **6/6 PASS**.
- Result directory: `runs/frontend_f0_stage1_compatibility_audit_20260828/`.
- Every result artifact is covered by the local `SHA256SUMS` manifest.

## 7. Claim boundary and next action

This result only says that the primary challenger's official pretrained artifact cannot
be made immutable under the frozen Stage-I evidence. It does not say the representation
is ineffective. Encoder pretraining, unofficial mirrors, or downloading the unpinned
Drive object would each require a new protocol; none is authorized here. The single-
frontend challenge therefore stops at Stage I under the present contract.
