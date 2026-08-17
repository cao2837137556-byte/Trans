# CKDB D0-P1 Dryad transport allowlist erratum

Status: FROZEN_ENGINEERING_ERRATUM

Date: 2026-08-17

## Evidence

After the explicitly authorized Dryad Anubis proof succeeded, the exact
official file-stream request redirected to:

`dryad-assetstore-merritt-west.s3.us-west-2.amazonaws.com/v3/...`

The returned `device_pcap_summary.csv` was 1,840 bytes with SHA-256
`34455dadf9aaada1110ca130082cec643430a6d456f1b7ce1303cd3da6f53e95`,
exactly matching Dryad's published file identity.  The prior plan allowed only
`datadryad.org`, so the executor correctly failed closed before using it.

## Mechanical erratum

For the four already frozen Dryad file-stream objects only, add the exact host
`dryad-assetstore-merritt-west.s3.us-west-2.amazonaws.com` to
`allowed_final_hosts`.  The implementation additionally requires HTTPS and
the `/v3/` path prefix.  Wildcard S3 hosts are forbidden.

No candidate, object ID, request URL, tier, expected kind, byte ceiling,
authorization, scientific gate, or claim boundary changes.  The retrieval
plan receives a new SHA-256 identity and all result artifacts must record that
new identity.  Signed S3 query parameters are transport-only and are never
persisted in the retrieval manifest; the manifest retains the original
allowlisted Dryad file-stream identity.

This erratum does not authorize PCAP, the 13.92 GB archive, a second industrial
corpus, HPC, training, embedding, thresholds, labels, or FINAL access.

Plan identities:

- superseded: `07eddd242b49b71b81a0421017bdf85a5682254bb794ea703aa32b964ef5d74f`
- active: `ca28462274bd0fe2256e8eefaead9bfc6e768b74f2dbc99a89479e34a3d46bfe`
