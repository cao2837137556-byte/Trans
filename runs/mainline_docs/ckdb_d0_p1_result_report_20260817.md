# CKDB D0-P1 external benign-corpus metadata audit result

Status: RESULT_COMPLETE_PENDING_SECOND_INDUSTRIAL_CORPUS

Date: 2026-08-17

Active implementation commit: `106a136`

Active retrieval-plan SHA-256:
`0abf7b61faf4259caefc106c65ea0128a69b0c460ea7a772d72fac53d6fe161b`

FROZEN scientific-contract SHA-256:
`9e96ad2860f812595d51376bc7b0bc1c3ae30e264e1918c946750689d363a3ba`

## Terminal result

The clean `local_r10` execution exited with code 0 and emitted:

`CKDB_D0_P1_PENDING_METADATA`

Mechanical missing evidence:

`SECOND_INDUSTRIAL_PROCESS_CORPUS`

The result does **not** authorize a large download.

## Corpus audit

| Candidate | Metadata identity | Benign boundary | Raw units | Post-cluster independent domains |
|---|---|---|---:|---:|
| UNSW-IoTraffic | PASS | PASS_WITH_CLAIM_CEILING | 27 physical consumer devices | 27 |
| CIC Modbus 2023 | PASS | PASS | 6 simulated roles | 1 shared-simulator domain |

UNSW's claim ceiling remains `UNLABELED_NORMAL_CLAIM`; it is not represented
as attack ground truth.  CIC's benign material is separable at folder level,
while attack-tree access remains prohibited.

## Tier-B flow evidence

The authorized `flows.zip` object was retrieved from the official Dryad object
identity and independently verified:

- bytes: `95,513,089`;
- SHA-256:
  `91d99c0f6074df6552db2c224c34023ba6b9bbdb18a3d18e6b156c5e6affce64`;
- archive members: `27`, all safe flow CSVs;
- flow rows: `4,944,041`;
- published packets: `95,543,405`;
- long-bidirectional-TCP flows under the preregistered descriptor: `863,417`;
- long-bidirectional-TCP fraction: `0.17463791259012618`;
- packet-count q50/q90/q99: `2 / 10 / 20`;
- duration-seconds q50/q90/q99:
  `5 / 7072 / 458197.59999999404`;
- horizon state: `PREFIX_256_COVERS_MOST_OBSERVED_FLOWS`;
- I1 scale state: `SCALE_PLAUSIBLE_PENDING_EXACT_CENSUS`.

Long-TCP presence is descriptive only and was not used as a per-corpus
inclusion patch.

## Boundary counters

- downloaded objects: `9` (8 Tier A + 1 Tier B);
- PCAP files opened: `0`;
- FINAL files opened: `0`;
- labels read: `0`;
- models opened: `0`;
- training/embedding/threshold operations: `0`;
- HPC submissions: `0`;
- large download authorized: `false`.

## Independent integrity checks

- result `SHA256SUMS`: 20/20 entries independently recomputed PASS;
- downloaded evidence entries: 9/9 hashed;
- pullback archive bytes: `95,232,347`;
- pullback SHA-256:
  `67e7895bfb7dbdd105d8febf09825bc6d7d7ee3b027d070e15da39bd20da2e03`;
- pullback members: 25;
- verdict present: yes;
- engineering-failure marker in terminal package: no.

Terminal artifacts:

- `runs/issue27ckdb_d0_p1_external_metadata_audit_v1_2026-08-17_local_r10/`;
- `runs/issue27ckdb_d0_p1_external_metadata_audit_v1_2026-08-17_local_r10_pullback.tar.gz`;
- matching `.sha256` sidecar.

## Engineering history

Earlier fresh output roots are retained as fail-closed engineering evidence.
None emitted a scientific verdict.  Permanent regressions now cover:

1. explicit Dryad Anubis authorization and bounded proof;
2. current wrapped challenge schema;
3. same-origin pass responses and authenticated direct asset redirects;
4. exact official Dryad Merritt S3 host plus `/v3/` path;
5. DOI-registered CSL-JSON metadata instead of an IEEE WAF shell;
6. verified Windows `ROOT` plus `CA` trust without disabling TLS checks.

Final suite: 30/30 contract tests PASS.

## Scientific interpretation and next gate

The consumer corpus is identifiable and large enough to remain a candidate for
future exact census.  The single CIC simulator cannot satisfy the frozen
industrial-side requirement of at least three post-clustering independent
domains.  Therefore CKDB may not download PCAPs or start training yet.

The next scientific action is the already preregistered deficiency remedy:
identify one second industrial/process-control benign corpus whose clustered
domains bring the industrial total to at least three, then subject that corpus
to the same eight audits in a separately frozen amendment.  Candidate choice
must not use viewed hydraulic/CKDA outcomes as a family patch, and any download
requires new user authorization.
