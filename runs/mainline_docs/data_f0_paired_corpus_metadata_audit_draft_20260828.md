# Data-F0 — Paired Cross-Device Corpus Metadata Audit (DRAFT)

- Date: 2026-08-28
- Status: **DRAFT; NON-EXECUTABLE**
- Candidate 1: CIC IoT 2022
- Candidate 2: CICIoT2023, sealed behind a digest-matched blocking review
- Structural reference: N-BaIoT; not a raw-PCAP candidate until raw PCAP and license are
  established

## 1. Objective

Determine, from official metadata only, whether an external corpus can support both:

- `Data-T`: method development/training/calibration devices; and
- `Data-E`: deterministic untouched evaluation devices with same-device benign history
  and attacks.

This audit cannot conclude that data, frontend, or their interaction is the cause of the
current failure. It only determines whether a later attributable experiment is legally
and statistically identifiable.

## 2. Candidate order and cognitive isolation

1. Audit candidate 1 against the frozen fields and gates.
2. If candidate 1 passes, stop permanently; candidate 2 remains unopened.
3. If candidate 1 fails, atomically write the complete reason-coded verdict and its
   SHA-256.
4. Independent review must match that digest and issue exactly
   `PROCEED_CANDIDATE_2` before candidate 2 metadata is accessed.
5. Candidate-2 fields, gates, and thresholds may not change after candidate-1 reasons
   are known.

An engineering HTTP failure does not activate candidate 2; it yields a retryable
engineering state under an unchanged protocol.

## 3. Metadata-only retrieval boundary

The FROZEN execution plan must enumerate exact official first-party objects, allowed
hosts, byte ceilings, redirect hosts, expected media types, and destination names.

Allowed content is limited to:

- dataset landing pages and README/license/citation files;
- device/capture/member inventories;
- published labels/scenario descriptions at file or capture level;
- published sizes and checksums; and
- official papers needed to interpret acquisition and identity.

Forbidden:

- PCAP/PCAPNG, flow archives, payload bytes, bulk ZIP/TAR objects;
- credentials, cookies, signed URLs, or personal form data in Git or result bundles;
- model training, embedding generation, scoring, or FINAL/report access.

## 4. Frozen audit fields per candidate

### A. Identity, provenance, and license

- official dataset identity, version, DOI/citation, publisher, and acquisition dates;
- license or explicit research-use terms;
- exact relationship to any frontend pretraining corpus and to current
  ToN/UNSW/Bot-IoT-derived sources;
- raw-PCAP claim supported by official member inventory, not prose alone.

### B. Device and scenario identity

- stable device identifiers and device type;
- benign capture/member identities per device;
- attack capture/member identities per victim device;
- attack family/scenario identity and whether the victim device is explicit or inferred;
- simulator/shared-network clustering information.

### C. Same-device pairing and causal commissioning shape

For a device to be `PAIRED_METADATA_ELIGIBLE`, metadata must prove:

1. at least one benign-only capture/member attributable to that exact device;
2. at least one attack capture/member attributable to that exact victim device;
3. benign material can be assigned to a commissioning role without attack contamination;
4. attack material is outside the commissioning prefix; and
5. the file/member boundary permits deterministic role enforcement before bulk data is
   opened.

Unknown victim identity, mixed benign/attack archives without pre-open inventory, or a
dataset-level device list without per-member lineage is PENDING, not a positive pairing.

### D. Count and split identifiability

Before bulk download, report the number of paired devices and the availability of counts
for independent benign sessions and attack sessions/families. Proposed later minimum:

```text
at least 8 paired devices total
at least 2 deterministic untouched Data-E devices
at least 6 Data-T devices
```

These numbers are open for independent review now and must be literal in the FROZEN
protocol. If metadata cannot provide session counts, emit
`PENDING_MEMBER_INVENTORY_AFTER_DOWNLOAD`; do not pretend record counts are sessions.

### E. Task relevance

Metadata must state whether the corpus can later measure:

- packets per session and duration;
- bidirectional TCP share;
- protocol mix;
- long/high-density session share; and
- coverage of the preregistered hydraulic failure region using descriptors defined
  without reference to outcome labels.

Consumer smart-home pairing may qualify a consumer commissioning claim. It does not
establish industrial high-density long-connection coverage.

### F. Resource planning

Record published compressed bytes, estimated extracted bytes, derived-artifact budget,
download resumability, checksum availability, and minimum free-space formula. No bulk
authorization can be requested without a fresh local-disk and compute plan.

## 5. Deterministic Data-E / Data-T split

If the paired-device minimum is met, form a canonical device key from the official
dataset version and device identifier, then sort by:

```text
SHA256(contract_sha256 || dataset_version || canonical_device_key)
```

The first two devices become `Data-E`; all remaining eligible devices become `Data-T`.
Data-E identities are committed before any bulk object is opened and may never enter
frontend/head training, calibration, model selection, thresholding, or method design.

If fewer than eight paired devices exist, terminate with
`NO_IDENTIFIABLE_PAIRED_DEVICE_SPLIT`. The split may not be rescued by treating dates,
files, roles, or attacks from the same device as independent devices.

## 6. Required outputs

1. `data_f0_candidate_audit.csv` — all fields for every candidate/device/member
2. `data_f0_pairing_matrix.csv` — device x benign/attack family availability
3. `data_f0_lineage_and_license.json`
4. `data_f0_task_relevance.json`
5. `data_f0_resource_plan.json`
6. `data_f0_data_e_t_split.json` or a reason-coded non-identifiable state
7. `data_f0_verdict.json`
8. `SHA256SUMS`

## 7. Terminal states

```text
DATA_F0_METADATA_ELIGIBLE
PENDING_MEMBER_INVENTORY_AFTER_DOWNLOAD
NO_RAW_PCAP
NO_CLEAR_LICENSE
NO_SAME_DEVICE_BENIGN_ATTACK_PAIRING
NO_IDENTIFIABLE_PAIRED_DEVICE_SPLIT
NO_TASK_RELEVANCE_METADATA
LINEAGE_CONTAMINATION_NO_GO
```

`DATA_F0_METADATA_ELIGIBLE` authorizes only a later bulk-download protocol draft. It is
not download authorization and not evidence of a detector improvement.

## 8. Later experimental claim boundary

If a later bulk audit passes, Data-E supports an untouched consumer-device
commissioning evaluation only within its observed device/capture graph. It does not
replace the sealed project FINAL, and it does not support broad industrial-domain claims
without matched industrial evidence.

## 9. Authorization boundary

This draft authorizes no HTTP request, browser automation, login, form submission,
download, implementation, training, embedding, report/FINAL opening, or HPC work.
