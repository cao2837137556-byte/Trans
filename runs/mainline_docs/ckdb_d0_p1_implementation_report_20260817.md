# CKDB D0-P1 metadata audit implementation report (2026-08-17)

Status: `IMPLEMENTED_FOR_INDEPENDENT_REVIEW`

This report records implementation and local contract validation only. No metadata object, flow table, PCAP, model, label, CKDA report, FINAL asset, or HPC resource was opened or downloaded. Execution remains gated on independent implementation review under the FROZEN protocol.

## 1. Frozen identity

- FROZEN protocol: `runs/mainline_docs/ckdb_d0_p1_external_metadata_audit_preregistered_20260817.md`
- FROZEN SHA-256: `9e96ad2860f812595d51376bc7b0bc1c3ae30e264e1918c946750689d363a3ba`
- Kimi freeze verification: `runs/mainline_docs/ckdb_d0_p1_kimi_freeze_verification_20260817.md`
- Retrieval plan: `runs/mainline_docs/ckdb_d0_p1_retrieval_plan_20260817.json`
- Retrieval-plan SHA-256: `07eddd242b49b71b81a0421017bdf85a5682254bb794ea703aa32b964ef5d74f`

## 2. Implemented files

| File | SHA-256 | Lines | Purpose |
|---|---|---:|---|
| `repo/ood/issue27ckdb_d0_p1_external_metadata_audit_v1.py` | `a8841047c6b79b67873c519a0819073af87fc493458025b57edac2bcf5258560` | 1220 | Explicit metadata-only executor, validators, eight audits, verdict, result packaging |
| `repo/ood/test_issue27ckdb_d0_p1_external_metadata_audit_v1.py` | `6f35c2f4c0f9b0b9478ed469dee9872f770cc8601fe7c37e0414e3666dc7ceb0` | 378 | Offline contract suite with synthetic metadata/flow fixtures |
| `runs/mainline_docs/ckdb_d0_p1_retrieval_plan_20260817.json` | `07eddd242b49b71b81a0421017bdf85a5682254bb794ea703aa32b964ef5d74f` | 122 | Exact object identities, byte caps, host allowlists, and future-large-object identities |

The executor has no import-time side effect. Network access exists only behind the explicit `execute` subcommand.

## 3. Retrieval boundary

The plan contains exactly two candidates: `UNSW_IOTRAFFIC` and `CIC_MODBUS_2023`.

- Tier A contains official landing pages, inventory/readme/device/protocol summaries, and the descriptor DOI landing page.
- Tier A has a hard 20 MiB per-candidate cap.
- Tier B contains only UNSW `flows.zip`, with a hard 128 MiB per-candidate cap, and is reachable only if both candidates pass Tier A.
- Current Tier-B `flows.zip` is explicitly excluded from the later large-download allowlist.
- Future large-object identities are recorded but not executable: UNSW `pcaps.zip` and the unresolved CIC benign-tree inventory placeholder. They require the later, separate user authorization mandated by the FROZEN protocol.

No generic crawler, recursive mirror, directory downloader, or PCAP reader is present.

## 4. Fail-closed implementation

The executor enforces:

1. FROZEN and retrieval-plan SHA verification before network access.
2. HTTPS-only retrieval and final-redirect host allowlists.
3. Resume only when local partial metadata proves the same object identity.
4. Per-object and per-candidate hard byte caps during streaming.
5. Temporary-file download and atomic promotion after validation.
6. PCAP magic, HTML-as-data, archive traversal, links, encryption, nested archives, executable members, raw-payload fields, and per-packet flow-disguise rejection.
7. Physical quarantine plus an audit JSON for rejected objects.
8. No scientific verdict after an engineering failure.
9. Exact fixed schemas with explicit `UNKNOWN`/`PENDING` states rather than silent blanks.
10. A verdict that can never authorize a later large download.
11. SHA-256 coverage of every downloaded and generated result object, followed by a pullback archive and sidecar.

## 5. Frozen scientific mechanics

- The UNSW flow archive must contain exactly 27 aggregate-flow CSV members. Per-packet or payload-like content fails closed.
- The global long-TCP descriptor is exactly: bidirectional TCP and (`packets_total > 256` or `duration_seconds >= 300`). It is descriptive only.
- Repeated dates of one device remain one clustered domain.
- All roles from the single CIC simulated substation remain one clustered industrial domain; role names cannot inflate independence.
- If the two candidates are metadata-eligible but clustered industrial domains are fewer than three, the result is `PENDING_METADATA` with the frozen missing-evidence code `SECOND_INDUSTRIAL_PROCESS_CORPUS`.
- If no identifiable corpus mix exists, the result is `NO_IDENTIFIABLE_CORPUS_MIX`.
- E3/netFound overlap can never be upgraded to a `KNOWN_DISJOINT` statement.

## 6. Local validation

Command:

```text
python -m unittest -v repo.ood.test_issue27ckdb_d0_p1_external_metadata_audit_v1
```

Result: `23/23 PASS` in an offline synthetic-fixture run.

The suite covers all 18 FROZEN §8 contracts and five extra regression gates:

- exact two-candidate and equal-schema contracts;
- immutable FROZEN/plan hashes and literal byte caps;
- Tier-A-before-Tier-B ordering;
- final/report/model/label/training/PCAP import absence;
- atomic writes, resume identity, and SHA round-trip;
- archive/content safety and disguised-flow rejection;
- clustered-domain independence and fixed long-TCP semantics;
- Python 3.9 AST compatibility and the historical `Path.write_text(newline=...)` ban;
- engineering failure produces no scientific verdict;
- rejected objects are physically quarantined;
- later large-download allowlist cannot contain the currently opened Tier-B flow archive.

Additional checks:

- `python -m py_compile`: PASS
- Python 3.9 AST parse for executor and tests: PASS
- CLI help/import without network: PASS
- `git diff --check` on task-owned implementation files: PASS

## 7. Independent-review questions

1. Is the fail-closed requirement for an explicit Dryad reuse-license phrase sufficient for Audit 1, or should execution require an even narrower dataset-level license token?
2. Is the implemented UNSW benign-boundary status `UNLABELED_NORMAL_CLAIM` with a corresponding claim ceiling the intended reading of the source metadata?
3. Is it correct that E3 remains comparison-only under `POSSIBLE_OVERLAP`, regardless of later empirical performance?
4. Is the mechanical CIC clustering outcome (one simulator = one industrial domain) the intended realization of R1, even though it will normally force `SECOND_INDUSTRIAL_PROCESS_CORPUS`?
5. Are the Tier-B aggregate-flow safety rules sufficient to reject any payload/per-packet masquerade without opening PCAP content?

## 8. Authorization boundary

This implementation report requests independent implementation review only. It does not authorize execution. After review PASS, the user's already stated authorization may be consumed only for the metadata-level D0-P1 execution described by the FROZEN protocol. Any PCAP/large-package download, training, embedding, threshold selection, FINAL access, or HPC activity remains forbidden without a new explicit user authorization.
