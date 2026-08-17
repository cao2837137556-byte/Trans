# CKDB D0-P1 Dryad Anubis engineering repair

Status: IMPLEMENTED_AND_LOCALLY_VALIDATED

Date: 2026-08-17

## Failure classification

The first authorized metadata execution stopped before producing a scientific
verdict because Dryad's official `downloads/file_stream` endpoints now require
an Anubis proof-of-work browser validation.  The executor correctly failed
closed on HTTP 403.  This is an official-access engineering failure, not a
corpus, model, or scientific result.

## Repair boundary

The repair adds an explicit `--allow-dryad-anubis` execution flag.  The adapter:

- is restricted to HTTPS host `datadryad.org` and path prefix
  `/downloads/file_stream/`;
- accepts only the observed `fast` challenge with bounded difficulty;
- preserves the official same-origin cookie session while solving the
  SHA-256 proof of work;
- returns only the originally allowlisted official file-stream URL;
- leaves all frozen host, byte, type, archive, quarantine, Tier A/Tier B,
  FINAL, PCAP, label, training, and verdict gates unchanged;
- records no cookie or challenge secret in outputs.

The user explicitly authorized solving this official access challenge.  The
flag remains off by default.

## Validation

- Existing and new contract tests: 25/25 PASS.
- New regression gates cover exact host/path restriction, explicit
  authorization, challenge schema/difficulty bounds, and deterministic proof
  verification.
- A one-object live canary fetched official Dryad file 4322597 and matched the
  published identity: 1,840 bytes, SHA-256
  `34455dadf9aaada1110ca130082cec643430a6d456f1b7ce1303cd3da6f53e95`.

## Retry rule

The failed first output is retained as engineering evidence.  The repaired
execution must use a fresh output root.  It remains metadata-only and does not
authorize PCAP, the 13.92 GB archive, HPC, model work, or FINAL access.
