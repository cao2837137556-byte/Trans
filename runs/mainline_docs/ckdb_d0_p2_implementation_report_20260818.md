# CKDB D0-P2 metadata executor implementation report

Date: 2026-08-18

Status: `IMPLEMENTED_FOR_INDEPENDENT_REVIEW`

Scope: offline implementation and contract validation only

## 1. Frozen identity

- Frozen protocol: `ckdb_d0_p2_second_industrial_corpus_amendment_preregistered_20260818.md`
- Frozen protocol SHA-256: `16926b7eb860322dc380a45c98bcb9d116d78dabcee32e8743d0639fef41c4b6`
- Freeze verification: commit `38a7270`, result `PASS`
- Retrieval plan SHA-256: `5d1a313ca73acb8f42342bc8a58057ccb830c80a1d930eafef30f06a57e80072`

The implementation refuses to run if either frozen identity differs from these
literal values.

## 2. Implemented files

| file | lines | bytes | SHA-256 |
|---|---:|---:|---|
| `repo/ood/issue27ckdb_d0_p2_pnnl_metadata_audit_v1.py` | 737 | 31,639 | `5fcd0059d9046d76bbd9965028e458852c4b0935f1945219f9f4c2ad1efd50a9` |
| `repo/ood/test_issue27ckdb_d0_p2_pnnl_metadata_audit_v1.py` | 385 | 18,927 | `63012a7392aa3ae8413a1bae890e360c2aeddfef150cbe88b5968747c3bdf35c` |
| `runs/mainline_docs/ckdb_d0_p2_retrieval_plan_20260818.json` | 95 | 2,991 | `5d1a313ca73acb8f42342bc8a58057ccb830c80a1d930eafef30f06a57e80072` |

## 3. Executable boundary

The only executable network path is the explicit `execute` subcommand. It can
retrieve exactly six frozen Tier-A metadata objects over HTTPS from per-object
allowlisted first-party hosts. Each response is streamed under its literal byte
cap and promoted from a temporary file only after final-host, content-type,
magic-byte, and login/challenge checks pass.

The following remain structurally outside the executable graph:

- the opaque PNNL tar and every PCAP/PCAPNG or packet payload;
- range requests or archive-member reads;
- account registration, form submission, or credential handling;
- labels, embeddings, models, thresholds, training, HPC, or FINAL assets;
- candidate search, fallback corpora, or a third corpus.

The six metadata caps sum to 16 MiB, below the frozen 20 MiB total cap; no
single object exceeds the frozen 8 MiB per-object cap. The future tar entry is
identity-only, has no executable URL, and keeps `large_download_authorized`
hard-coded false.

## 4. Scientific and safety logic

The executor emits the frozen audit schemas and mechanically evaluates:

1. dataset identity and explicit research-use evidence;
2. lineage and claim ceilings, including E3 comparison-only status;
3. benign normal-unit separability with system-fault excluded;
4. the four-way PNNL independence conjunction: process model, device fleet,
   control enclave, and separable normal unit;
5. coverage plus the frozen long-TCP descriptors, kept descriptive only;
6. combined industrial-domain count using the inherited CIC single-cluster
   identity.

An unknown independence condition collapses PNNL to one domain. An absent
pre-open archive inventory yields `PENDING_ARCHIVE_INVENTORY`; it cannot be
silently treated as benign evidence or authorize later use. Even a fully
eligible metadata verdict authorizes no download, training, HPC, or FINAL use.

Any engineering exception removes scientific verdict/report/hash outputs,
removes partial result-package artifacts, and leaves only
`engineering_failure.json`.

## 5. Independent-rerunnable validation

Executed locally without network access:

```text
python -m unittest -v repo.ood.test_issue27ckdb_d0_p2_pnnl_metadata_audit_v1
Ran 31 tests in 0.450s
OK
```

The suite includes all 23 frozen minimum contracts plus eight hardening tests:
exact output/hash round-trip, pending propagation, eligible-but-not-authorized,
proved-independence failure, no Range header, empty output root, import/help
without network, and explicit research-use evidence.

Additional gates passed:

- `python -m py_compile` on implementation and tests;
- Python 3.9 AST parsing and observed runtime-API regression scan;
- CLI `--help` with no network side effect;
- complete offline fixture generation, validation, and result-package hashing.

No metadata request, HEAD request, registration, download, model execution,
training, HPC submission, or FINAL access occurred during implementation or
validation.

## 6. Requested independent review

Please review:

1. whether the six-object allowlist and literal caps implement the frozen
   metadata boundary exactly;
2. whether explicit research-use evidence is conservatively fail-closed;
3. whether `PENDING_ARCHIVE_INVENTORY` correctly dominates any apparent domain
   count until a separately authorized post-download boundary check exists;
4. whether the four independence conditions can only reduce, never inflate,
   the PNNL domain count;
5. whether failure cleanup and the non-executable opaque-tar identity prevent a
   scientific verdict or later-use authorization from leaking through an
   engineering failure.

This report requests implementation review only. It does not request or imply
authorization for PNNL retrieval (including HEAD), registration, download,
HPC, training, embeddings, thresholds, or FINAL access.
