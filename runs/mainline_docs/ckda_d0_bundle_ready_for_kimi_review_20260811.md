# CKDA D0 formal bundle — ready for Kimi review

Date: 2026-08-11

Implementation commit: `7178dccfd8d74d5b791846686e8015877099addd`

FROZEN contract SHA-256:
`ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5`

## 1. Exact bundle identity

- archive:
  `issue27ckda_d0_representation_compatibility_20260811_upload_bundle.tar.gz`
- local transfer directory:
  `D:\study\paper\anomaly_detection\paper04\supercompute_transfer`
- bytes: `665814425`
- SHA-256:
  `c979638ecf430946cdd9e2614b082c42bc5f78f6cadd4bf545ff88afd70aade9`
- archive sidecar: same archive name plus `.sha256`
- payload files hashed by bundle manifest: `2832`
- tar entries including directories: `3358`
- clean-extraction full hash check: `PASS`
- LF-only text check: `PASS`

Official netFound checkpoint inside the bundle:

- bytes: `698780900`
- SHA-256:
  `e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105`
- official repository commit:
  `b3ab5a3aa72640cc725ef207fb0145b039a57d35`
- official model commit:
  `b812e625999165376ddb47a39d0d5579d4edce89`

## 2. Independent post-build checks

The archive sidecar was independently recomputed after the builder returned.
The tar path list was independently enumerated.

- archive SHA sidecar: `PASS`
- `bundle_commit.txt` equals `bundle_identity.json.commit_sha`: `PASS`
- both identities equal implementation commit `7178dcc...`: `PASS`
- path matches for `cooler-motor`: `0`
- path matches for seed 37/47 markers: `0`
- `bundle_identity.json.final_included`: `false`
- `bundle_identity.json.seed37_47_included`: `false`

The bundle contains the P0 ruling text and executable denylist/reason-code
contracts, but no FINAL data file or FINAL model artifact.

## 3. Regression evidence carried into the bundle

- 31/31 Python contract tests PASS;
- synthetic real-shaped compile -> boundary -> validator chain PASS;
- Python byte compilation PASS;
- Bash syntax for Slurm/installer/status PASS;
- PowerShell builder parse PASS;
- genuine official netFound checkpoint load and minimal CPU forward PASS;
- exact FROZEN contract hash is checked both before and after LF
  normalization;
- result validator recomputes the I1 conjunctive gate, candidate ranking,
  verdict, boundary counters and output hashes.

## 4. Classified local build failures and permanent guards

Two local pre-archive failures occurred. Neither reached HPC and neither is
scientific evidence.

### B1 — Windows Git-root spelling mismatch

- symptom: builder rejected `D:/.../kitnet-exp-mainline` versus
  `D:\...\kitnet-exp-mainline`;
- class: local path canonicalization defect;
- root cause: Git and `Resolve-Path` emitted different separators for the same
  absolute path;
- permanent repair: normalize both through `Path.GetFullPath` and trim both
  separator forms before comparison;
- regression evidence: explicit canonical-root check PASS;
- repair commit: `7a8be7d`.

### B2 — generated bundle identity used CRLF

- symptom: the all-text LF gate rejected `bundle_identity.json`;
- class: local package serialization defect;
- root cause: `ConvertTo-Json` emitted platform-native CRLF after the earlier
  copied-file normalization pass;
- permanent repair: normalize generated JSON before UTF-8 no-BOM write;
- regression evidence: generated-JSON LF test PASS plus the unchanged all-file
  CR-byte scan and clean extraction check;
- repair commit: `7178dcc`.

Both incomplete local bundle directories were replaced by the builder's
explicit target cleanup before the successful build. No stale partial archive
was accepted.

## 5. Execution and authorization boundary

The included installer submits one complete AMD result-producing chain only
after exact bundle/input/dependency/scheduler gates pass. It requires the
literal environment variable:

```text
CKDA_D0_SUBMIT_AUTHORIZATION=YES
```

That authorization has deliberately not been set or exercised here. No CKDA
D0 HPC job has been submitted.

Requested next step: Kimi independently review the exact bundle. A Kimi bundle
PASS still does not itself submit HPC; the user must explicitly authorize the
formal D0 submission after review.
