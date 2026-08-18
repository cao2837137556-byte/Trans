# CKDB D0-P3 combined large-download, boundary-verification, and census protocol — DRAFT

Date: 2026-08-18

Status: `DRAFT_FOR_INDEPENDENT_REVIEW_NOT_EXECUTABLE`

Author: Codex (design and implementation side)

Authority chain:

- D0-P1 result review `dbf6d8c`;
- D0-P2 frozen protocol hash
  `16926b7eb860322dc380a45c98bcb9d116d78dabcee32e8743d0639fef41c4b6`;
- D0-P2 result review `115fde9`, including F1 closure;
- U1--U6 convergence verification `38a7270`.

This draft does not authorize an HTTP request, account use, object-body
download, archive opening, PCAP decoding, training, embedding, threshold work,
HPC submission, or FINAL contact. It has no SHA sidecar and is not FROZEN.

## 1. Decision to make

D0-P3 asks whether three preregistered external benign sources can be
materialized and censused under one immutable role contract:

1. `UNSW_IOTRAFFIC` consumer-device PCAPs;
2. `CIC_MODBUS_2023` benign-only capture tree;
3. `PNNL_ELECTRICITY_AND_GAS_IDS` normal-baseline units, only after a
   download-complete but pre-use boundary check.

The protocol may establish:

- whether PNNL contributes two post-clustering industrial domains;
- whether the combined industrial total reaches three;
- whether the legal external-benign fit corpus passes the inherited I1 gate;
- which preregistered traffic-structure regions are covered or missing;
- an immutable consumer report-only holdout and the industrial claim ceiling;
- storage and replay identities for a later D-design.

It cannot establish detection performance and cannot authorize training.

## 2. Freeze blockers and launch-time blocker

The following identity cells are still unavailable from public metadata and
must be closed from the user's authenticated official inventory before freeze:

```text
P0-A = exact PNNL tar object identity, published bytes or hard cap, and
       publisher SHA when available
P0-B = exact CIC benign-only object/member identities, bytes or hard caps, and
       publisher SHAs when available
P0-C = extracted-size ceilings for PNNL and CIC, derived from official
       inventory or a conservative archive expansion cap
P0-D = launch destination free-space evidence under the formula in §11
```

`P0-A`--`P0-C` are freeze blockers because they define the object identities
and maximum materialization scope. `P0-D` is deliberately a launch-time
blocker, not a freeze blocker: the formula and destination policy are frozen,
but free space is volatile and must be measured again immediately before the
authorized transfer. Historical free-space evidence cannot close `P0-D`.

Direct URLs containing credentials, cookies, signed query strings, bearer
tokens, or form state are secrets. They must never enter Git, this document,
logs, bundles, screenshots, or command history. A stable identity consists of
the official dataset ID/DOI, publisher-relative object/member path, byte count,
and publisher checksum when one exists. A transient transport URL is supplied
only at launch through a mode-0600 runtime secret file and is deleted after use.

If P0-A or P0-B cannot be closed without opening an object body, the draft
returns to review. No approximate URL is substituted.

## 3. Frozen-candidate object registry

### 3.1 UNSW-IoTraffic PCAP object — public identity closed

```text
candidate_id       = UNSW_IOTRAFFIC
dataset_doi        = 10.5061/dryad.w0vt4b94b
object_id          = unsw_pcaps
official_url       = https://datadryad.org/downloads/file_stream/4322593
destination        = UNSW_IOTRAFFIC/pcaps.zip
published_size     = 13.92 GB (publisher display value)
exact_bytes        = NOT_PUBLISHED
publisher_sha256   = NOT_PUBLISHED
stream_hard_cap    = 16 GiB = 17,179,869,184 bytes
```

Absence of a publisher checksum is not represented as a match. Exact bytes and
SHA-256 are recorded after the one authorized transfer. A body exceeding the
hard cap is an engineering failure with no scientific verdict.

### 3.2 PNNL object — dataset identity closed, transport identity blocked

```text
candidate_id       = PNNL_ELECTRICITY_AND_GAS_IDS
dataset_id         = PNNL DataHub 13470
dataset_doi        = 10.25584/PNNLDH/1838670
object_id          = pnnl_opaque_tar
destination        = PNNL_ELECTRICITY_AND_GAS_IDS/official_opaque_tar
relative_path      = P0-A_PENDING_AUTHENTICATED_INVENTORY
expected_bytes     = P0-A_PENDING_AUTHENTICATED_INVENTORY
publisher_sha256   = P0-A_PENDING_AUTHENTICATED_INVENTORY_OR_NOT_PUBLISHED
hard_cap           = P0-A_PENDING_AUTHENTICATED_INVENTORY
```

The object is initially quarantine-only. No member becomes a usable input
until §7 passes.

### 3.3 CIC object set — dataset identity closed, benign members blocked

```text
candidate_id       = CIC_MODBUS_2023
dataset_id         = CICModbusDataset2023
official_page      = https://www.unb.ca/cic/datasets/modbus-2023.html
object_id          = cic_benign_pcaps
destination        = CIC_MODBUS_2023/benign_only_tree
relative_members   = P0-B_PENDING_FORM_RESOLVED_OFFICIAL_INVENTORY
expected_bytes     = P0-B_PENDING_FORM_RESOLVED_OFFICIAL_INVENTORY
publisher_sha256   = P0-B_PENDING_OFFICIAL_INVENTORY_OR_NOT_PUBLISHED
hard_cap           = P0-B_PENDING_OFFICIAL_INVENTORY
```

Only publisher-identified benign members are eligible. A whole-dataset object
that cannot exclude the attack tree before transfer is not an acceptable
replacement for `cic_benign_pcaps` and blocks launch.

## 4. Immutable scientific roles

| Source/unit | Role in D0-P3 | May train later? | May select later? | May report later? |
|---|---|---:|---:|---:|
| UNSW non-holdout devices | `external_benign_fit_candidate` | only under later D-design | only under later D-design | descriptive census only now |
| Five UNSW devices in §5 | `EXTERNAL_BENIGN_REPORT_HOLDOUT` | no | no | benign-only report after later authorization |
| CIC benign-only cluster | `external_industrial_fit_candidate` | only under later D-design | only under later D-design | descriptive census only now |
| PNNL electric normal unit | `external_industrial_fit_candidate` if §7 passes | only under later D-design | only under later D-design | descriptive census only now |
| PNNL gas normal unit | same | same | same | same |
| PNNL system-fault | `EXCLUDED_ABNORMAL_PHYSICAL_STATE` | no | no | no |
| Any attack tree/member | `PROHIBITED_ATTACK_MATERIAL` | no | no | no |
| Ambiguous/unmapped traffic | `EXCLUDED_UNRESOLVED_IDENTITY` | no | no | count/exclusion only |

`UNLABELED_NORMAL_CLAIM` remains the UNSW ceiling. It is not attack ground
truth. The external report holdout cannot support attack-recall claims and is
not FINAL.

## 5. U3 deterministic holdout and industrial option

### 5.1 Consumer holdout

The pre-body device inventory has 27 physical UNSW devices. Define:

```text
salt = CKDB_EXTERNAL_BENIGN_REPORT_HOLDOUT_V1
key  = SHA256(UTF8(salt + NUL + candidate_id + NUL + source_unit_id))
n_holdout = floor(0.20 * 27) = 5
```

Sort ascending by `(key, source_unit_id)` and select the first five. The exact
result, computed before `pcaps.zip` is opened, is:

| rank | source unit | published device | selection SHA-256 |
|---:|---|---|---|
| 1 | `UNSW_DEVICE_001` | AmazonEcho | `0093f3253c7ef8410efb1dc68595a000ef7a814b2baec1c4232ba068c1704b53` |
| 2 | `UNSW_DEVICE_027` | WithingsSmartScale | `04abb6f50d5ff163bd55f71b754c0e3b8d982ffc178e3c6a2dd68f18cbb0f378` |
| 3 | `UNSW_DEVICE_018` | PixStarPhotoFrame | `066720e1d0171a6716afa161b63a8a506a01c14086106327a3615767f4086062` |
| 4 | `UNSW_DEVICE_009` | HelloBarbie | `10d3908880342bf5648385477b7c6209826da7936b289e2741a2a816dd8a2d2e` |
| 5 | `UNSW_DEVICE_024` | TribySpeaker | `186b4f4f87ae280a51358a96be373a9480c55384284d144f039e757e83de5728` |

These devices are excluded from tokenizer/bucket fitting, self-supervision,
supervised fitting, threshold fitting, model/horizon/loss selection, early
stopping, and debugging. Ambiguous packets that cannot be mapped to exactly one
published device are excluded rather than reassigned.

### 5.2 Industrial option

The coarse-domain maximum is fixed at CIC 1 + PNNL 2 = 3. Therefore the
metadata-count rule mechanically selects U3 option 2:

```text
USE_ALL_THREE_INDUSTRIAL_DOMAINS_FOR_FIT_SELECT
FORBID_BROAD_UNSEEN_INDUSTRIAL_DOMAIN_CLAIM_BEFORE_FINAL
```

No industrial coarse domain is held out. Fine roles/devices never inflate this
count. If PNNL fails §7, the industrial route is NO-GO rather than silently
changing the holdout rule.

## 6. Safe transfer and immutable-object gate

Each object is transferred independently to `<object>.partial` with resume
enabled when the official server supports byte ranges. Completion requires:

1. final host and stable dataset/object identity match the frozen registry;
2. streamed bytes do not exceed the object hard cap;
3. final exact byte count is recorded;
4. publisher checksum matches when published;
5. a local SHA-256 is computed over the completed bytes;
6. archive magic/type matches the expected type;
7. atomic rename from `.partial` to the immutable quarantine name;
8. the immutable manifest is written before any inventory or extraction.

Retries never append to an unverified byte range. If resume semantics are not
provable, the partial object is retained as engineering evidence and a fresh
temporary identity is used. Transfer completion is not scientific success.

## 7. PNNL post-download/pre-use boundary verification

Only safe archive inventory operations are permitted at first. Packet payloads
and labels remain unopened. The verification order is:

1. reject absolute paths, `..`, symlinks, hardlinks, devices, FIFOs, encrypted
   entries, nested archive bombs, duplicate normalized paths, and expansion
   beyond P0-C;
2. produce the complete recursive member manifest with path, type, compressed
   size, uncompressed size, and archive-member hash when available;
3. map members using publisher scenario names only into:
   `electric_normal`, `gas_normal`, `system_fault`, `attack`, or `ambiguous`;
4. require at least one nonempty capture unit mapped uniquely to
   `electric_normal` and at least one mapped uniquely to `gas_normal`;
5. require that neither normal allowlist intersects `system_fault`, `attack`,
   or `ambiguous` after path normalization;
6. freeze the two normal allowlists and their aggregate bytes/hashes before
   any listed capture is decoded.

PASS yields two PNNL post-clustering domains. Any failure or ambiguity yields:

```text
NO_IDENTIFIABLE_SECOND_INDUSTRIAL_CORPUS
PNNL_ARCHIVE_ISOLATED_NO_MEMBER_USE
NO_REPLACEMENT_CORPUS_SEARCH
```

The scientifically unusable download is retained only in quarantine until
result review and cleanup authorization. No result from the other corpora may
override this failure.

## 8. CIC pre-use boundary

The authenticated inventory must identify a benign-only subtree or exact
benign member list before launch. After transfer:

1. the same archive-safety checks as §7 apply;
2. every member must normalize under the frozen benign subtree/member list;
3. no path may contain or resolve into an attack/log subtree;
4. only PCAP/PCAPNG and minimal publisher metadata types are allowed;
5. the benign member allowlist is hashed before decoding.

Violation is `CIC_BENIGN_BOUNDARY_FAILURE_NO_USE`. Downloading a mixed whole
archive and filtering it after packet access is prohibited.

## 9. Frozen census unit and I1 scale identity

The census inherits the CKDA D1 causal session identity:

```text
external_source_unit + pcap_member + canonical_bidirectional_5tuple
```

Packets retain capture order; equal timestamps retain event position. Member
boundaries reset state. Negative timestamp/IAT or missing endpoint/protocol
makes that session unencodable from the first violation onward; packets are not
reordered to rescue it.

I1 token counts inherit the frozen four fields and buckets from CKDA D1:
direction, length bucket, protocol, and causal within-session IAT bucket.
Packets are counted once per session, not once per prefix. D0-P3 does not fit a
tokenizer or train I1.

The inherited precondition is reported after excluding the five consumer
holdout devices and every prohibited/ambiguous unit:

```text
benign_fit_sessions >= 500,000
AND benign_fit_tokens >= 10,000,000
```

PASS only states `I1_EXTERNAL_BENIGN_SCALE_GATE_PASS`; it does not authorize
training or imply detection performance.

## 10. U2 corpus-global coverage census

### 10.1 Frozen descriptors

For every encodable benign session, emit:

- packet count bins: `1-2`, `3-8`, `9-32`, `33-128`, `129-256`,
  `257-1024`, `>=1025`;
- duration bins in seconds: `<1`, `1-<10`, `10-<60`, `60-<300`,
  `300-<1800`, `>=1800`;
- directionality: `UNIDIRECTIONAL` or `BIDIRECTIONAL`;
- transport: `TCP`, `UDP`, or `OTHER`;
- polling proxy: maximum share of one exact
  `(direction,length_bucket,protocol)` token, binned as `<0.25`,
  `0.25-<0.50`, `0.50-<0.75`, `>=0.75`;
- burstiness `B=(std(IAT)-mean(IAT))/(std(IAT)+mean(IAT))`, binned as
  `<-1/3`, `-1/3..1/3`, `>1/3`; fewer than three positive IATs is
  `INSUFFICIENT_IAT`.

The implementation emits marginals plus the joint
`packet_count × duration × directionality × transport` table by coarse domain,
source unit, and immutable role. No threshold is estimated from hydraulic,
family labels, report holdout results, or FINAL.

### 10.2 Preregistered regions and quality support

The following generic regions are checked:

```text
R1 sparse-short       packet_count <= 8 AND duration < 60
R2 packet-dense       packet_count > 256
R3 long-lived         duration >= 300
R4 bidirectional-TCP  BIDIRECTIONAL AND TCP
R5 polling-like       polling_proxy >= 0.75
R6 bursty             B > 1/3
```

A region has `QUALITY_SUPPORTED_MASS` only when it contains at least 100
sessions, at least 10,000 packets, and at least two independent source units.
Otherwise it is named `THIN_OR_MISSING_<region>` with exact counts.

### 10.3 No U2 route-kill threshold

This draft chooses **no numerical U2 minimum-mass kill gate**. The six support
thresholds classify evidence quality; they do not determine corpus admission.
The reason is that a coverage kill threshold would conflate three distinct
questions already governed elsewhere: benign-boundary validity, independent
domain count, and the inherited I1 scale gate.

If all six regions have quality-supported mass, emit
`COVERAGE_SPANS_PREREGISTERED_REGIONS`. Otherwise emit
`COVERAGE_GAP_NAMED`, list every thin/missing region, activate the later U1
horizon audit, and cap the paper claim. No gap may add data, change a window,
tune a threshold, or create a device/family patch.

## 11. U6 storage, transfer, and cleanup plan

Let:

```text
C = sum of exact compressed object bytes
E = sum of frozen maximum extracted bytes
D = max(ceil(0.10 * E), 20 GiB) for manifests/checkpoints/census artifacts
required_free = ceil(1.20 * max(2*C, C + E + D))
```

The factor `2*C` covers resumable partial plus final compressed objects. The
other branch covers retained compressed sources, bounded extraction, and
derived census state. Launch requires `available_bytes >= required_free` on
the resolved destination filesystem and inode use below 85%.

Current read-only evidence after user-authorized cache/download cleanup on
2026-08-18:

```text
C: free 21.32 GiB
D: free 40.48 GiB
minimum UNSW-only partial+final need: 27.84 GB before safety margin
decision: D_PASSES_COMPRESSED_UNSW_STAGING_FLOOR_ONLY
full D0-P3 decision: PENDING_P0_A_TO_P0_C_AND_FRESH_P0_D
```

The user has fixed the execution site to local Windows D: while the school HPC
is unavailable. The proposed destination, outside every Git worktree and
subject to a fresh launch-time free-space gate, is:

```text
D:\study\paper\anomaly_detection\paper04\external_corpora\ckdb_d0_p3\
  partial/
  quarantine/
  boundary_verified/
  census/
  control/
```

All three objects are downloaded directly on the local destination host with a
resumable client. Authenticated PNNL and CIC transport uses a short-lived
official URL supplied through a local ACL-restricted runtime secret file; the
selected method is recorded without secrets before launch. Passwords, cookies,
tokens, and signed URLs are never written to Git, task logs, or screenshots.
No HPC fallback is part of this protocol revision.

Cleanup order after result review:

1. delete failed `.partial` identities only after their failure hashes/logs are
   recorded;
2. retain immutable compressed objects and publisher/manifests;
3. retain only allowlisted benign extraction; never extract attack/fault data;
4. derived temporary decode shards may be deleted only after census hashes and
   replay checks pass;
5. any deletion is explicit and separately authorized; no automatic recursive
   deletion targets a computed or broad path.

## 12. Fail-closed state machine

```text
S0 DRAFT_NOT_FROZEN
  if any P0 identity/storage blocker remains -> BLOCKED_IDENTITY_OR_STORAGE

S1 AUTHORIZED_TRANSFER
  if object/cap/host/checksum fails -> ENGINEERING_FAILURE_NO_VERDICT

S2 IMMUTABLE_QUARANTINE_COMPLETE
  run PNNL and CIC pre-use boundary gates before packet decoding

S3 BOUNDARY_VERIFIED
  if PNNL fails/ambiguous -> NO_IDENTIFIABLE_SECOND_INDUSTRIAL_CORPUS
  if CIC fails -> CIC_BENIGN_BOUNDARY_FAILURE_NO_USE
  else freeze benign member allowlists

S4 CENSUS_COMPLETE
  require combined industrial domains = 3
  emit holdout manifest, I1 scale gate, coverage tables/gaps, storage report

S5 RESULT_PACKAGED
  no training/download extension/HPC/FINAL authorization is produced
```

Scientific verdict files are absent on an engineering failure. A boundary
failure is a valid scientific result and includes no replacement-corpus path.

## 13. Required outputs

1. exact object registry with stable and transient identities separated;
2. transfer manifest with bytes, hashes, hosts, resume history, and caps;
3. archive-safety and expansion audit;
4. PNNL five-way member classification and two normal allowlists;
5. CIC benign-only member allowlist;
6. immutable coarse-domain and fine-source manifest;
7. `EXTERNAL_BENIGN_REPORT_HOLDOUT` manifest with the five fixed UNSW devices;
8. excluded/ambiguous unit manifest;
9. per-source session/token census and inherited I1 scale verdict;
10. descriptor marginals and joint coverage table;
11. six-region support table and named coverage gaps;
12. current/peak storage, inode, throughput, and checkpoint report;
13. boundary counter report: attack/fault/FINAL/labels/models/training/HPC all 0;
14. result report, `SHA256SUMS`, and deterministic pullback package.

## 14. Minimum implementation contract tests

At least the following 30 cases must pass before a download command exists:

1. frozen protocol/plan hash match;
2. exactly three candidate identities and no corpus-search path;
3. all P0 cells closed before launch;
4. transient secrets absent from plan/log/bundle;
5. exact host/object cap enforcement;
6. resumable partial never promoted before hash completion;
7. wrong Content-Range cannot append;
8. published checksum mismatch fails closed;
9. archive type/magic mismatch fails closed;
10. path traversal/link/device/encryption rejection;
11. archive expansion cap enforcement;
12. PNNL inventory happens before packet decode;
13. both normal units required for PNNL=2;
14. attack/system-fault/ambiguous never enter a normal allowlist;
15. PNNL ambiguity yields isolation + no replacement;
16. CIC attack tree cannot enter the transfer/member allowlist;
17. CIC mixed whole archive is rejected when benign-only transfer is impossible;
18. exact five-device consumer holdout and hash order;
19. holdout exclusion from every fit/select/debug role;
20. industrial option 2 and broad-claim prohibition;
21. fine units cannot inflate coarse-domain count;
22. causal session/member reset and timestamp regression behavior;
23. exact inherited I1 token buckets and count-once behavior;
24. I1 scale gate excludes holdout/prohibited/ambiguous units;
25. exact descriptor bin edges and low-IAT state;
26. exact six coverage regions and quality-mass thresholds;
27. coverage gap limits claims but cannot kill/add/tune;
28. storage formula, inode gate, and current-local-volume rejection;
29. engineering failure emits no scientific verdict;
30. Python 3.9 syntax/runtime regression, deterministic hashes, and package
    round-trip.

## 15. Explicit non-authorizations

Even after this draft is reviewed and frozen, implementation review and a new
explicit user authorization are required before transfer. D0-P3 never
authorizes:

- registration automation or credential persistence;
- attack/system-fault member use;
- model training, embeddings, probes, thresholds, or D-design selection;
- HPC compute submission;
- FINAL identity expansion or FINAL opening;
- a replacement corpus after PNNL boundary failure;
- claims that consumer coverage proves unseen-industrial generalization.

## 16. Questions for independent review

1. Must P0-A/P0-B be closed before FROZEN, or may a separately hashed,
   metadata-only launch appendix close them without body access?
2. Is the decision to use quality-support thresholds but no U2 route-kill gate
   scientifically preferable to a numerical kill threshold?
3. Is the fixed five-device UNSW holdout large enough while preserving useful
   consumer fit diversity?
4. Do the current coarse-domain counts correctly force industrial option 2?
5. Is the PNNL boundary test strong enough to turn the two official process
   systems into two usable normal domains without reading packet bodies first?
6. Should CIC remain launch-blocked unless a benign-only remote object/member
   set is available, even if the publisher offers only a mixed whole archive?
7. Is the storage formula sufficiently conservative for the user-selected D:
   destination, given that 40.48 GiB only clears the UNSW compressed staging
   floor and full clearance awaits P0-A--P0-C?

No item in this draft is executable until these questions are reviewed,
`P0-A`--`P0-C` are closed, a FROZEN sidecar is verified, implementation passes
its contract suite and independent review, fresh launch-time evidence closes
`P0-D`, and the user explicitly authorizes the large transfer.
