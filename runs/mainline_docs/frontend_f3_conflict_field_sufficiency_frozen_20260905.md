# Frontend-F3 conflict-field sufficiency audit — FROZEN

Status: `FROZEN_BEFORE_TCP_CONFLICT_RAW_FIELD_OPEN`

## 1. Question and boundary

Frontend-F2 D0 found two exact H1–H4 token-prefix buckets containing both a protected incumbent-hard attack and a protected incumbent-normal benign target. A deterministic encoder receiving those tokens cannot reproduce both incumbent decisions. This audit asks one narrow question before any further training:

> Can a small, endpoint-free, causal packet-header field extension separate both observed hard-conflict buckets?

This is a necessary-condition audit only. A PASS does not authorize training and does not show OOD improvement. It only permits a later full-fit collision and shortcut audit.

The audit may read only the 28 already identified fit targets and their causal prefixes from the eight registered PCAP members. It may not read select, viewed, report, FINAL, model outputs, embeddings, or payload bytes, and it performs no optimizer step.

## 2. Prior observation disclosure

Before this freeze, the two-row UDP bucket's target frames were inspected once. Their exact frame lengths were observed as 109 and 84 bytes, and both were DNS queries to port 53. Consequently, separation of that UDP bucket by any field is descriptive/kill-only and supplies no positive evidence for field selection.

No raw additional field values from the 26-row TCP bucket were opened before this freeze. The TCP bucket is the only outcome-bearing bucket in this audit. Both buckets must nevertheless be separated for a candidate to survive.

## 3. Prohibited shortcuts

No ladder may contain raw IP address, MAC address, first-seen endpoint token, source/member/device identifier, capture ordinal, absolute timestamp, raw high/ephemeral port number, label, role, old score, or old representation. Packet payload bytes and payload-derived content are prohibited.

The context router remains the already frozen deterministic H1–H4 router. This audit changes only event signatures, never context membership.

## 4. Frozen field ladder

The following cumulative ladder is evaluated in this exact order. The first level that separates every hard-conflict bucket is the only surviving candidate; later levels are not promoted.

### L0 — incumbent semantic signature

The current Frontend-F1 canonical signature, unchanged.

### L1 — causal shape refinement

Append:

- exact `frame.len` integer;
- causal inter-arrival bucket `delta_log2_us`: `ZERO` when delta is zero, otherwise `floor(log2(max(1, round(delta_seconds * 1e6))))`;
- exact transport data length (`tcp.len` for TCP, `udp.length` for UDP, otherwise `NONE`);
- TCP flags as the normalized numeric bit mask (`NONE` outside TCP).

### L2 — endpoint-free port taxonomy

Append to L1, separately for source and destination:

- `SYSTEM` for 0–1023, `REGISTERED` for 1024–49151, `DYNAMIC` for 49152–65535, `NONE` when absent;
- an exact service value only when the port is 0–1023; all other exact values are replaced by their class.

This level exposes well-known service semantics but never raw high/ephemeral ports.

### L3 — coarse network-header shape

Append to L2:

- exact `ip.len` integer or `NONE`;
- TTL/hop-limit bucket: `0_31`, `32_63`, `64_127`, `128_191`, `192_255`, or `NONE`.

L3 is last. No post-result field addition is allowed.

## 5. Identity and extraction rules

- Target identities and member locations come only from the already pinned CKDA fit/select target metadata.
- Every target frame must match `target_event_position_within_capture + 1`.
- Prefix rows are reconstructed by the same context route and epoch semantics used by Frontend-F1; target conservation must be 28/28.
- TShark field extraction is header-only. Exact TShark executable identity and every input member identity are recorded.
- Canonical serialization is UTF-8 JSON with sorted keys and compact separators; prefix identity is SHA-256 of the ordered event-signature list through the target.

## 6. Mechanical outcomes

For every ladder level, report exact mixed-label bucket count and hard-protected mixed-label bucket count, plus all row memberships.

- `F3_CONFLICT_FIELDS_CANDIDATE_PASS`: L1, L2, or L3 is the first level with zero hard-protected mixed-label buckets, and 28/28 targets are conserved. This authorizes only a later full 13,866-fit-target re-decode audit with the selected level frozen.
- `F3_CONFLICT_FIELDS_NO_GO`: L3 retains any hard-protected mixed-label bucket.
- `F3_CONFLICT_FIELDS_ENGINEERING_FAILURE`: any identity, conservation, parser, causality, or boundary check fails; no scientific verdict is emitted.

Even a candidate PASS cannot be called ability inheritance, detection improvement, or OOD improvement.

## 7. Stop-loss and next decision

There is no field sweep beyond L3 and no training in this lineage. If L3 fails, the route `enriched H1–H4 -> new encoder -> frozen P2` is closed. The preferred deployment architecture then becomes structural inheritance: A remains byte-identical incumbent E3/P2; B receives a separately validated specialist branch. A full replacement or unified new head would require a separate protocol and stronger evidence.

