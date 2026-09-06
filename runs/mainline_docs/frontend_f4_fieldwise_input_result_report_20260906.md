# Frontend-F4 fieldwise input audit: result report

Date: 2026-09-06

Status: `F4_FIELDWISE_INPUT_PASS`

Scope: deterministic input feasibility on exposed development evidence. No
model, score, learned representation, optimizer, PCAP, network, report, or
FINAL access; no training.

## Result

The fixed 131-dimensional float32 map preserves every declared F3 L1 field
without a train-built dictionary or UNK token. All eight frozen gates pass.

| Check | Result |
|---|---:|
| Parent targets / contexts | 13,866 / 9,307 |
| Parent events encoded | 205,470 |
| Nested train targets / contexts | 8,660 / 4,984 |
| Nested internal-validation targets / contexts | 5,206 / 4,323 |
| Exact event round trips | 205,470 / 205,470 |
| Exact target-prefix feature hashes independently recomputed | 13,866 / 13,866 |
| Old all-UNK targets now losslessly represented | 3,173 / 3,173 |
| Unique canonical events / unique fieldwise vectors | 12,524 / 12,524 |
| New event or prefix collisions | 0 |
| Canonical / feature mixed-label buckets | 0 / 0 |
| Kill-only attack prefixes encoded / colliding with train benign | 5 / 0 |
| Synthetic contract tests | 28 / 28 PASS |
| Result-package SHA-256 entries independently verified | 14 / 14 |

Every target remained in its inherited source-based nested split. The 26 A
benign rows that the old teacher marked hard remained present as the separate
`a_unprotected_benign` category; no row was hidden to make the input pass.

## Meaning

F3 failed because it treated the complete 19-field event signature as one
categorical word. An unseen combination became UNK even when every individual
field was valid. F4 encodes those fields separately with fixed one-hots, bits,
and exact UInt32 limbs. The observed OOV failure is therefore repaired at the
model-input boundary without adding packet fields, fitting a vocabulary, or
changing the source split.

This PASS means only that the available event information reaches a numerical
model input without categorical collapse. It does **not** show that a GRU or
classifier can learn useful attack semantics, inherit the old P2 capability,
reduce hydraulic/OOD false positives, or generalize to a newly commissioned
device. Internal-validation inheritance support remains only one independent A
attack context / three rows, and the five older attack failures remain
kill-only evidence.

## Independent result verification

After the run, a separate read-only verifier:

- recomputed all 14 immediate result hashes;
- checked 9,307 contiguous context offsets and the 205,470-row binary size;
- scanned all 131 coordinates for finiteness;
- recomputed all 13,866 parent and five kill-only prefix hashes directly from
  the saved little-endian float32 binaries and their indexes;
- joined every target to the pinned F3 audit and confirmed its L1 identity,
  source, split, label, owner, teacher, device family, and attack family;
- confirmed that equal fieldwise feature prefixes never map to different L1
  prefixes or mixed labels;
- rechecked the FROZEN SHA and verified that draft-to-FROZEN differences are
  only the title, status, provenance, and trailing blank lines.

Runtime was 54.484 seconds, peak process working set 388,538,368 bytes, and
durable output 110,306,450 bytes, all below the frozen caps. The 107,666,280-byte
parent feature binary is retained locally and identified by the result
`SHA256SUMS`; it is not added to Git because it exceeds GitHub's ordinary
single-file limit. All smaller reports and audit tables are versioned.

## Engineering receipts

Two attempts stopped before a scientific verdict:

1. Windows returned failure from `GetProcessMemoryInfo` because the 64-bit
   pseudo-handle lacked an explicit ctypes signature. The fix declares the
   handle and API argument/result widths and adds a live resource-counter test.
2. The first parent feature-prefix hash had no prior bucket, and `.get()`
   returned `None` where the code expected a list. The fix uses the declared
   `defaultdict` bucket directly. The same change also confirms kill-only
   collisions by underlying bytes after a hash match.

Both failures are preserved in numbered engineering directories. Neither
attempt emitted a scientific verdict or touched any model/score/training path.
The final run reused the identical frozen science and passed.

## Durable identities and boundary

- Frozen protocol SHA-256:
  `6c5408d2437cf53aafefad6b68dd7932ffefe9309004b9a4ee673cc8f3ffc8dd`.
- Implementation SHA-256:
  `9c729a3165d19042549723f029235734595131d5e7ba344a3f605cca89677200`.
- Contract-test SHA-256:
  `0e026c4ab93b6310a441282a2a3945d23ba1892e5a17b7cec9325781b19fc16a`.
- Result `SHA256SUMS` SHA-256:
  `432c03f543e3dc9c2bdc97cc9842e53fb846e4cf62f92fb5642b2896855d4df5`.
- Result directory:
  `runs/frontend_f4_fieldwise_input_feasibility_v1_20260905`.

The only next action permitted by this PASS is drafting a separate one-shot
training protocol. Training remains unauthorized. Incumbent deployment, CE,
select/report/FINAL, commissioning, external downloads, and HPC are unchanged.
