# CKDB D0-P3 P0 metadata progress (2026-08-20)

## Outcome first

The metadata-only launch work has made real progress but the executable launch
appendix is **not yet eligible**:

- `P0-A` is closed. The official PNNL page publishes one stable tar object;
  a body-free `HEAD` response reports exactly `7,957,268,480` bytes,
  `application/x-tar`, and byte-range support. No publisher SHA-256 is present.
- UNSW retains its FROZEN public Dryad identity and 16 GiB stream cap. A
  conservative 32 GiB extracted ceiling is recorded above the publisher's
  approximately 26.9 GB uncompressed description.
- `P0-B` is not closed. The official CIC endpoint presents a required form
  (first name, last name, email, organization, job title, and country) before
  exposing any download inventory. No benign-only remote filename, subtree,
  byte count, checksum, or cap is visible before that user action.
- No object body was downloaded, no form was submitted, and no credential,
  cookie, token, signed URL, or form value was recorded.

The official CIC form has been opened in the user's Edge browser and marked for
handoff. The user must enter and submit their own contact/professional details;
Codex must not guess or transmit them.

## PNNL evidence

Official dataset page:
`https://data.pnnl.gov/group/nodes/dataset/13470`

Stable publisher object exposed by that page:

```text
publisher_relative_path = cartuids/14271_2329f583703f14b8991e1b9c259b8a4b.tar
expected_bytes           = 7,957,268,480
content_type             = application/x-tar
accept_ranges            = bytes
publisher_sha256         = NOT_PUBLISHED
stream_hard_cap          = 8 GiB = 8,589,934,592 bytes
extracted_size_cap       = 8 GiB = 8,589,934,592 bytes
```

The URL has no query string, credential, bearer value, cookie, or form state.
The object remained unopened; only the official HTML and HTTP headers were
read.

## CIC boundary blocker

The UNB description states that attack and benign traffic are separated and
that captures are chunked into sequential 100 MB PCAP files. That statement is
not enough for `P0-B`: the FROZEN protocol requires the exact benign-only
remote identity before transfer and forbids substituting the whole mixed
dataset.

The official inventory endpoint currently shows only the contact-information
form. Therefore this is a user-action dependency, not evidence that the
benign-only set is impossible. If the post-form official inventory still does
not expose a benign-only subtree or exact benign members, the FROZEN R1 route
consequence applies: CIC counts as zero, the industrial maximum remains two,
and D0-P3 terminates without searching for a replacement corpus.

## Storage preview (not `P0-D`)

Fresh launch measurement remains mandatory after the full appendix is closed.
The current read-only preview is already informative:

```text
D: free                              = 84,489,347,072 bytes = 78.69 GiB
known C before CIC                  = 25,137,137,664 bytes
known E before CIC                  = 42,949,672,960 bytes
derived floor D                     = 21,474,836,480 bytes
required_free before CIC            = 107,473,976,525 bytes = 100.09 GiB
shortfall before CIC                = 22,984,629,453 bytes = 21.41 GiB
```

Thus the current D: space cannot pass the frozen storage formula even before
adding CIC. No deletion is performed in this step. Exact, validated cleanup
targets must be chosen separately without touching either research project,
Codex/Kimi state, Git worktrees, or retained experiment evidence.

## Next mechanical steps

1. User completes the visible CIC official form and leaves the resulting
   inventory page open.
2. Codex reads only that inventory and records the exact benign-only object or
   member set, byte/cap evidence, final-host allowlist, and CIC extracted cap.
3. Codex generates and validates the separately hashed launch appendix.
4. At least 21.41 GiB plus the still-unknown CIC contribution must be freed on
   D: before the final fresh `P0-D` check.
5. Large transfer starts only after a new appendix-bound explicit user
   authorization; this progress note does not authorize it.

Evidence JSON:
`runs/mainline_docs/ckdb_d0_p3_p0_metadata_evidence_20260820.json`
