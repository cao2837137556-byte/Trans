# CKDB D0-P2 second industrial/process corpus amendment — FROZEN preregistration

Date: 2026-08-18

Status: `FROZEN_PREREGISTERED`

Authority:

- CKDB D0-P1 FROZEN preregistration and its pre-frozen deficiency remedy;
- D0-P1 result commit `0385ff4`;
- Kimi D0-P1 result review `dbf6d8c`;
- Kimi D0-P2 draft review and rulings `14e281a`.

This FROZEN preregistration does not authorize implementation, retrieval
(including HEAD), download, registration/form submission, HPC, training,
embedding, threshold work, or FINAL contact.

## 1. Decision to make

D0-P1 ended mechanically at:

```text
status = CKDB_D0_P1_PENDING_METADATA
missing_evidence = SECOND_INDUSTRIAL_PROCESS_CORPUS
consumer_postcluster_domains = 27
industrial_postcluster_domains = 1
large_download_authorized = false
```

D0-P2 asks one bounded question:

> Can one prespecified second industrial/process-control network corpus add at
> least two post-clustering independent industrial domains, so that the
> combined CIC + second-corpus total reaches the inherited minimum of three?

The candidate is fixed before any candidate object is opened:

```text
PNNL_ELECTRICITY_AND_GAS_IDS
DOI = 10.25584/PNNLDH/1838670
owner = Pacific Northwest National Laboratory
```

There is no fallback candidate inside D0-P2. If this candidate cannot meet the
metadata and independence gates, D0-P2 ends NO-GO; the implementation may not
silently search for another corpus.

## 2. Why this candidate is taxonomy-selected

The candidate is selected from the frozen `INDUSTRIAL_PROCESS` taxonomy, not
from resemblance to any viewed CKDA family or hydraulic score pattern.

Before opening candidate files, the official PNNL and DOE/OSTI descriptions
establish all of the following:

1. the corpus is an industrial cybersecurity dataset with a persistent DOI;
2. the environment uses simulated components plus hardware-in-the-loop assets;
3. it contains both an electrical distribution process and a natural-gas
   distribution process;
4. the two sectors use named industrial field devices and multiple networks;
5. a `Normal traffic` scenario exists to establish baseline operation;
6. raw network traffic is distributed from the official PNNL DataHub path.

These facts make two independent process domains plausible, but do not prove
them. D0-P2 is specifically designed to test that proposition without opening
the large archive.

The following facts are not selection reasons and may not become patches:

- whether the corpus contains long TCP flows;
- whether its packet-count distribution resembles hydraulic;
- whether it improves CKDA/P2 predictions;
- whether electricity or gas traffic is easier to classify.

## 3. Frozen candidate identity and source allowlist

### 3.1 Primary identities

- PNNL DataHub landing page:
  `https://data.pnnl.gov/group/nodes/dataset/13470`
- persistent DOI:
  `https://doi.org/10.25584/PNNLDH/1838670`
- DOE/OSTI record:
  `https://www.osti.gov/biblio/1838670`
- PNNL DataHub policy:
  `https://data.pnnl.gov/policy`

### 3.2 Metadata-only objects permitted after separate execution authorization

Tier A may retrieve only:

- the four primary pages above;
- DOI/DataCite/OSTI bibliographic JSON for the exact DOI;
- the official DataHub dataset description;
- the official Globus/download-object filename, HTTP headers, byte size,
  checksum, and server-side inventory when exposed without downloading the
  archive;
- an official README, manifest, data dictionary, scenario inventory, license,
  checksum file, or file listing only when separately exposed outside the
  large archive;
- the official report/paper metadata linked by PNNL or OSTI.

The default PNNL DataHub download object currently resolves to an opaque `.tar`
asset. D0-P2 may issue `HEAD` or equivalent metadata requests but may not read
the tar body, request byte ranges from it, or infer internal members from a
partial archive.

### 3.3 Prohibited objects

D0-P2 may not retrieve:

- the PNNL tar payload or any PCAP/PCAPNG;
- any packet, flow, label, attack-log, payload, or sensor-value table;
- CIC Modbus PCAPs or its manual-access form contents;
- UNSW `pcaps.zip` or any other D0-P1 large object;
- any third corpus or candidate-search result;
- any CKDA/CKCZ report-level row, cooler-motor, seed 37/47, or FINAL asset.

No DataHub account creation, login, Globus transfer, credential entry, or terms
acceptance is automated by this protocol. Any future PNNL registration is a
manual user action. Registration, form submission, or access approval never
constitutes download authorization.

## 4. Inherited taxonomy and eight audits

D0-P2 inherits the D0-P1 taxonomy and all eight audits without weakening:

1. source identity, license, and integrity;
2. collection and pretraining lineage;
3. benign-use boundary;
4. device/source census and domain independence;
5. consumer/industrial coverage matrix;
6. 256-packet horizon coverage;
7. scale and future census feasibility;
8. mechanical verdict and later-download allowlist.

Every inherited unknown remains explicit. Absence of small flow metadata yields
`PENDING_NO_SMALL_FLOW_METADATA`, never zero prevalence. The inherited global
long-flow descriptor remains:

```text
bidirectional TCP flow AND
(packet_count > 256 OR duration_seconds >= 300)
```

It is descriptive only and cannot decide candidate eligibility.

## 5. PNNL-specific post-clustering independence gate

The official description creates two provisional process clusters:

```text
PNNL_ELECTRIC_DISTRIBUTION
PNNL_NATURAL_GAS_DISTRIBUTION
```

Device names, protocols, scenarios, days, subnets, and files do not create
additional domains by themselves.

The PNNL candidate contributes two post-clustering independent domains only if
Tier-A primary evidence establishes all four conditions below for electricity
versus gas:

1. `DISTINCT_PROCESS_MODEL` — distinct electrical and gas physical/process
   simulators or process models;
2. `DISTINCT_FIELD_DEVICE_FLEET` — sector-specific field-device fleets rather
   than aliases for the same endpoints;
3. `DISTINCT_CONTROL_ENCLAVE` — separate control-network/enclave membership,
   even if both are observed by one campaign collector;
4. `SEPARABLE_NORMAL_UNIT` — the normal baseline can be identified at a
   pre-open archive member, folder, capture, or manifest unit for each sector.

Mechanical count:

```text
if all four conditions are primary-evidence TRUE:
    pnnl_postcluster_independent_domains = 2
else:
    pnnl_postcluster_independent_domains = 1
```

`UNKNOWN` is not TRUE. Shared campaign dates or one orchestration host do not
automatically collapse the domains; a shared process simulator/generator,
shared control enclave, or inseparable normal unit does.

The combined route count is:

```text
combined_industrial_domains =
    cic_modbus_postcluster_domains (frozen at 1)
    + pnnl_postcluster_independent_domains
```

The inherited route minimum is met only at `combined_industrial_domains >= 3`.

## 6. Benign-boundary gate

The official landing page names a normal-traffic scenario, but this narrative
alone does not authorize training material.

Metadata eligibility requires an official inventory or manifest that identifies
the normal baseline before any archive body is opened. Acceptable smallest units
are:

- `BENIGN_ONLY_FILE`;
- `BENIGN_ONLY_FOLDER`;
- `MIXED_WITH_EXACT_BOUNDARY` only when the exact boundary is a pre-open
  member/folder/capture identity, not a packet/row label.

If the single tar object exposes no server-side or separately published member
inventory, the benign boundary is `PENDING_ARCHIVE_INVENTORY`; it cannot be
recovered by downloading the tar under D0-P2. This is metadata pending, not
proof of inseparability and not an immediate NO-GO.

If D0-P2 later reaches download eligibility while this reason remains, the
combined large-download/census preregistration must freeze a post-download,
pre-use boundary verification. The archive may be downloaded only after a new
user authorization, but no member may enter training, fitting, census-derived
selection, embedding, or threshold work until the verification proves a
separable normal unit for each sector. Failure or ambiguity at that point is
fail-closed `NO_IDENTIFIABLE_SECOND_INDUSTRIAL_CORPUS`; the archive is isolated
and no replacement corpus is searched. This explicitly accepts the risk of one
scientifically unusable download rather than weakening the benign boundary.

System-fault scenarios are not silently treated as benign. They are abnormal
physical states: neither baseline operation nor cyber-attack. Mixing them into
normal training would contaminate the normality model. They remain excluded
until a separate future preregistration assigns them a scientific role before
opening them.

## 7. Lineage and claim ceilings

The audit must record OSTI/DataCite publication and capture-date evidence as the
PNNL timeline anchor, then compare the PNNL campaign, devices, and public
release against:

- existing ToN-IoT and IoTSIM fit/select/report sources;
- UNSW-IoTraffic and CIC Modbus 2023 candidates;
- netFound documented pretraining corpora;
- cooler-motor and all FINAL source identities without opening FINAL content.

`KNOWN_DISJOINT` requires positive evidence. No detected match is at most
`NO_KNOWN_OVERLAP`; unresolved public-pretraining exposure is
`POSSIBLE_OVERLAP`.

The I1 arm may use a corpus only if the later large-download protocol preserves
a clean benign self-supervision boundary. E3 remains comparison-only and may
not receive a disjoint-pretraining claim.

Protocol families are recorded descriptively. PNNL gas and CIC both using
Modbus neither merges nor proves separation of their domains; independence is
established only by the process-model, device-fleet, control-enclave, and
separable-normal-unit evidence in §5.

## 8. Metadata byte and network contract

After separate user authorization, D0-P2 metadata execution must:

- use only HTTPS primary/DOI infrastructure hosts;
- cap cumulative downloaded response bodies at 20 MiB;
- cap every individual response at 8 MiB;
- reject redirects to an unlisted host until the exact official redirect is
  recorded and added through an auditable engineering update;
- record request URL, final URL, status, content length/type, UTC, local bytes,
  and SHA-256;
- use temporary files and atomic rename;
- reject login/error/challenge HTML masquerading as data;
- create no scientific verdict after an engineering/network failure.

The PNNL tar itself has an effective byte cap of zero in D0-P2.

## 9. Mechanical verdict

Candidate-level status is one of:

- `PNNL_CORPUS_METADATA_ELIGIBLE`;
- `PNNL_CORPUS_METADATA_PENDING`;
- `PNNL_CORPUS_METADATA_INELIGIBLE`.

Overall status is generated in this order:

1. any engineering failure before validated evidence:
   `CKDB_D0_P2_ENGINEERING_FAILURE_NO_SCIENTIFIC_VERDICT`;
2. no primary identity, prohibited/ambiguous research use, known route overlap,
   unresolved benign boundary that primary metadata proves cannot be separated,
   or fewer than two PNNL post-clustering domains:
   `CKDB_D0_P2_NO_IDENTIFIABLE_SECOND_INDUSTRIAL_CORPUS`;
3. missing official file inventory, license attachment, capture lineage, or
   independence evidence that could still be supplied without choosing a new
   corpus:
   `CKDB_D0_P2_PENDING_METADATA` with one or more named reason codes, including
   `PENDING_ARCHIVE_INVENTORY` when the opaque tar has no pre-open member list;
4. candidate passes Audits 1–4, contributes exactly two independent domains,
   and the combined industrial count reaches three:
   `CKDB_D0_P2_LARGE_DOWNLOAD_ELIGIBLE`.

Even in state 4:

```text
large_download_authorized = false
training_authorized = false
hpc_authorized = false
final_opened = 0
```

The verdict only permits Codex to draft a combined large-download/census
preregistration and ask the user for a new authorization.

## 10. Required outputs

1. `ckdb_d0_p2_retrieval_manifest.csv`;
2. `ckdb_d0_p2_corpus_identity_and_license.csv`;
3. `ckdb_d0_p2_lineage_overlap_matrix.csv`;
4. `ckdb_d0_p2_benign_boundary.csv`;
5. `ckdb_d0_p2_device_process_inventory.csv`;
6. `ckdb_d0_p2_independence_evidence.csv` containing the four conditions in §5;
7. `ckdb_d0_p2_domain_type_coverage.csv`;
8. `ckdb_d0_p2_horizon_and_scale.csv`;
9. `ckdb_d0_p2_later_download_allowlist.csv`;
10. `ckdb_d0_p2_verdict.json`;
11. `ckdb_d0_p2_result_report.md`;
12. `SHA256SUMS` for every downloaded/generated object.

All schemas must be fixed at implementation review. Empty values are forbidden;
use explicit `UNKNOWN`/`PENDING_*` reason codes.

## 11. Fail-closed execution order

1. verify the eventual FROZEN hash and empty output root;
2. validate that the candidate count is exactly one and DOI is exact;
3. retrieve only the primary landing/DOI/policy metadata;
4. complete identity, license, and access-path checks;
5. retrieve only separately exposed small manifests/inventories;
6. apply the four-condition independence gate;
7. complete inherited Audits 2–7;
8. generate the mechanical Audit-8 verdict;
9. validate schemas, boundary counters, hashes, and zero large-object bytes;
10. package metadata-only evidence.

No verdict is emitted from partial or unvalidated metadata.

## 12. Minimum implementation contract tests

The later implementation review must independently pass at least:

1. candidate count exactly one and DOI exact;
2. metadata total and per-object byte caps;
3. PNNL tar body/range request prohibited;
4. PCAP magic/member rejection;
5. HTML login/challenge rejection;
6. official-host and final-redirect enforcement;
7. temp-download and atomic-rename behavior;
8. exact SHA manifest generation/readback;
9. same inherited taxonomy values as D0-P1;
10. all four independence conditions required for count 2;
11. any `UNKNOWN` independence condition collapses count to 1;
12. device/role/day/subnet rows cannot inflate the count;
13. normal narrative alone cannot create a benign unit;
14. fault scenarios excluded from normal training scope;
15. missing small flow metadata yields `PENDING`, not zero;
16. long-TCP descriptor remains literal and nonselective;
17. no third-corpus search/import path;
18. no CIC form, UNSW PCAP, report, cooler-motor, seed37/47, or FINAL path;
19. no label/model/training/embedding/threshold imports;
20. verdict cannot authorize a large download;
21. Python 3.9 syntax and runtime API compatibility if Python is used;
22. engineering failure removes scientific verdict;
23. `PENDING_ARCHIVE_INVENTORY` cannot authorize member use and is propagated
    into the later post-download/pre-use fail-closed verification contract.

## 13. Freeze closure

Kimi review `14e281a` closed the five draft questions mechanically:

1. the single fixed PNNL candidate and no-fallback rule are accepted;
2. the four-condition independence gate is accepted;
3. absent pre-open inventory is `PENDING_ARCHIVE_INVENTORY`, with the later
   post-download/pre-use fail-closed consequence frozen in §6;
4. system-fault scenarios are excluded for the rationale recorded in §6;
5. success authorizes only drafting the next preregistration, never a download.

Notes N1--N3 are frozen in §§3, 6, and 7: the OSTI/DataCite timeline is recorded,
protocol is descriptive rather than a domain identity, and registration is a
manual user action.

This document becomes authoritative only with its reviewed SHA-256 sidecar. It
still authorizes no implementation, retrieval, registration, download, HPC,
training, embedding, threshold work, or FINAL contact.
