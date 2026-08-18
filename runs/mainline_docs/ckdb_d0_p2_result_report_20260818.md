# CKDB D0-P2 PNNL metadata audit result

Status: `RESULT_COMPLETE_PENDING_INDEPENDENT_REVIEW`

Date: 2026-08-18

Active implementation commit: `0b48e71`

Independent implementation review: commit `5e1ca71`, `PASS`

Active retrieval-plan SHA-256:
`5d1a313ca73acb8f42342bc8a58057ccb830c80a1d930eafef30f06a57e80072`

FROZEN scientific-contract SHA-256:
`16926b7eb860322dc380a45c98bcb9d116d78dabcee32e8743d0639fef41c4b6`

## Terminal result

The clean metadata-only execution exited with code 0 and emitted:

`CKDB_D0_P2_PENDING_METADATA`

Candidate state:

`PNNL_CORPUS_METADATA_PENDING`

Mechanical missing evidence:

`PENDING_ARCHIVE_INVENTORY`

The result does **not** authorize registration, a large download, member use,
training, HPC, or FINAL contact.

## Retrieved Tier-A evidence

Exactly the six frozen metadata objects were retrieved. All returned HTTP 200,
passed their content/safety checks, and were hashed:

| Object | Final first-party identity | Bytes | SHA-256 |
|---|---|---:|---|
| PNNL DataHub page | `data.pnnl.gov/group/nodes/dataset/13470` | 32,841 | `ce308387fc26819460412110e905c887848edc342c87d0e48dbeeb00ef379d1c` |
| DOI landing | redirected to the same PNNL DataHub page | 32,841 | `ce308387fc26819460412110e905c887848edc342c87d0e48dbeeb00ef379d1c` |
| OSTI record page | `www.osti.gov/biblio/1838670` | 41,869 | `71162f0486ad268410187dc13678e73f275dd668963868904fcfc504429a8881` |
| PNNL policy | `data.pnnl.gov/policy` | 22,126 | `5843c61d96b1c8b88c28b869e741c664825a08e5bb65964a170b59bf8c315d28` |
| DataCite JSON | DOI `10.25584/PNNLDH/1838670` | 6,674 | `84125bc8b573e7070c6383fc6a42d350308e4c8027df63140c76ffec5cf81652` |
| OSTI JSON | record `1838670` | 1,686 | `064a0ae800f7d868aa5abd8d61c1afed17c70c01b5526448ecd9fe9dc4e6e11b` |

Total retrieved bytes: `138,037`, below the frozen 20 MiB aggregate cap.
No HEAD or Range request was used.

## Four-condition independence gate

| Condition | Result | Evidence status |
|---|---|---|
| C1 distinct process model | TRUE | official descriptions distinguish electricity and natural-gas process models |
| C2 distinct field-device fleet | TRUE | sector-specific electrical and gas device names are present |
| C3 distinct control enclave | TRUE | official descriptions distinguish sector control networks |
| C4 separable normal unit | PENDING | opaque tar has no pre-open member inventory |

The frozen conjunction requires all four conditions. Therefore PNNL contributes
one post-clustering domain at this stage, not two:

- PNNL post-cluster domains: `1`;
- inherited CIC Modbus post-cluster domains: `1`;
- combined industrial domains: `2`;
- required route gate: `3`.

C1–C3 evidence channels are affirmative. C4 is neither silently accepted nor
proven false; its missing evidence can only be resolved by a separately
preregistered, user-authorized download followed by the fail-closed
post-download/pre-use benign-boundary check. Kimi's reserved F1 adjudication
remains for independent result review.

## Benign boundary and claim ceilings

- official narrative names a normal-traffic baseline;
- pre-open benign boundary remains `PENDING_ARCHIVE_INVENTORY`;
- system-fault material remains excluded as an abnormal physical state;
- protocol names are descriptive only and do not create domain identity;
- netFound remains `POSSIBLE_OVERLAP` and comparison-only;
- FINAL remains identity-only and unopened.

No small-flow metadata was available, so the frozen long-TCP descriptor and I1
scale census both remain pending. Neither was used to change the corpus verdict.

## Boundary counters

- retrieved objects: `6` Tier A metadata objects;
- retrieved bytes: `138,037`;
- PNNL tar/PCAP files opened: `0`;
- FINAL files opened: `0`;
- labels read: `0`;
- models or embeddings opened: `0`;
- registration automated: `0`;
- training/HPC operations: `0`;
- large download authorized: `false`.

## Independent integrity checks

- result `SHA256SUMS`: 17/17 entries independently recomputed PASS;
- downloaded evidence entries: 6/6 hashed and safety status PASS;
- pullback archive bytes: `39,678`;
- pullback archive members: `18`;
- pullback SHA-256:
  `914df8463e77f228dd6461844e2600c1cffe66a747e449c1a7ab789c5711a24c`;
- verdict present: yes;
- engineering-failure marker: absent.

Terminal artifacts:

- `runs/issue27ckdb_d0_p2_pnnl_metadata_audit_v1_2026-08-18_local/`;
- `runs/issue27ckdb_d0_p2_pnnl_metadata_audit_v1_2026-08-18_local_pullback.tar.gz`;
- matching `.sha256` sidecar.

## Scientific interpretation and next gate

PNNL official metadata supports two structurally distinct industrial process
systems, but the frozen scientific contract does not permit those systems to
count as two usable benign domains until the opaque archive's normal units are
separable under a post-download/pre-use boundary check. The present result is
therefore a designed pending state, not an engineering failure and not a route
success.

The next step is independent result review. Only after that review may a new
combined large-download/census protocol be drafted. Any registration or large
download remains a manual, separately authorized user action; no data use or
training may begin from this result alone.
