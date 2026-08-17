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

The first integrated retry exposed the current Anubis wrapper shape
(`rules` plus `challenge`) rather than the flat fixture shape.  It again
failed closed before a verdict.  The parser now normalizes both forms, checks
that the two difficulty declarations agree, and ignores challenge metadata;
the suite is extended to 26 tests.  That retry is retained as a second
engineering-failure artifact and is not reused.

The next fail-closed retry established that successful validation serves the
official file body directly from the same-origin Anubis pass endpoint instead
of redirecting the response URL back to `file_stream`.  The adapter now
accepts that exact official endpoint as a transport response while the audit
manifest always records the original allowlisted `file_stream` identity; no
challenge query parameter is persisted.  A 27th regression test freezes this
identity separation.

The official pass subsequently exposed the exact final transport host as
`dryad-assetstore-merritt-west.s3.us-west-2.amazonaws.com` under `/v3/`.
Because the original retrieval plan did not allow that host, the next retry
also failed closed.  A separate frozen engineering erratum adds only this
exact host to the four pre-existing Dryad file-stream objects and re-pins the
plan identity; no scientific or authorization field changes.

One further fail-closed retry showed the authenticated-session fast path:
after the first proof, subsequent allowlisted files redirect directly to the
same exact asset host without a second challenge page.  The same host/path
predicate is now shared by both the challenge-response and authenticated
direct-response branches.  Test 28 freezes rejection of HTTP, other S3
buckets, and non-`/v3/` paths.

## Retry rule

The failed first output is retained as engineering evidence.  The repaired
execution must use a fresh output root.  It remains metadata-only and does not
authorize PCAP, the 13.92 GB archive, HPC, model work, or FINAL access.
