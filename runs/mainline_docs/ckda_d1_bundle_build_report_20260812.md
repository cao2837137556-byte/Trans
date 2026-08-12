# CKDA D1 bundle build and local validation report

Status: `BUNDLE_BUILD_PASS_AWAITING_KIMI_PACKAGE_REVIEW`

Date: 2026-08-12

Bundle commit: `fc55c598aca2a2428796696024b4c34020736233`

FROZEN contract SHA-256: `ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9`

Authorization boundary: this report authorizes neither upload nor HPC submission. The bundle is awaiting independent Kimi package review. Formal submission additionally requires the user-only `CKDA_D1_SUBMIT_AUTHORIZATION=YES` gate.

## 1. Bundle identity

- directory: `issue27ckda_d1_representation_probe_20260812`
- archive: `issue27ckda_d1_representation_probe_20260812_upload_bundle.tar.gz`
- archive bytes: `97,442`
- archive SHA-256: `1035652502f2ceb1f080bce88d878670a4a2a526932004d5773f65c325ddf2a2`
- SHA sidecar: present and independently matched;
- `SHA256SUMS` members: `25`;
- total extracted files including bundle identities: `26`;
- clean-extraction member hash validation: `25/25 PASS`;
- CR bytes in executable/text payload: `0`;
- embedded PCAP/NPZ/GZ data artifacts: `0`;
- cooler-motor / seed 37 / seed 47 members: `0`.

The small archive is intentional. It reuses the already reviewed D0 r2 netFound runtime and checkpoint on HPC instead of duplicating approximately 699 MB of immutable model data.

## 2. Reused D0 identity

- D0 bundle: `issue27ckda_d0_representation_compatibility_20260811_r2`;
- netFound checkpoint bytes: `698,780,900`;
- netFound checkpoint SHA-256: `e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105`;
- netFound Python 3.9 audit status: `CKDA_NETFOUND_PY39_COMPAT_PASS`;
- D0 fit-prefix manifest SHA-256: `9184cd018efcc6547832bf04ce6d3046c687b8e48cac73234482d9fb3ba89689`.

These values are pinned in the bundle identity and rechecked by the formal job before computation.

## 3. Clean-extracted payload execution

Tests below ran from the bundle payload, with only the pinned D0 runtime placed on `PYTHONPATH`; they did not import CKDA D1 code from the working tree.

- Python 3.9 grammar/runtime-API gate: `14/14 files PASS`;
- CKDA D1 contract suite: `46/46 PASS`;
- validator atomic-write contract: `PASS`;
- FROZEN contract hash after archive extraction: exact match;
- package member SHA verification after clean extraction: `PASS`.

The 14-file Python gate covers the nine D1 files, bundled CKBU/CKCZ dependencies, D0 audit/pilot dependencies, and the patched netFound model source actually executed on HPC.

## 4. Submission and failure boundaries

- invoking the bundled installer without user authorization exits with code `3` and prints `CKDA D1 submission is not authorized`;
- no Slurm submission occurred during this build/validation step;
- installer runs exact bundle hashes, Python 3.9 gates, all 46 tests, validator contract test, Bash parsing, scheduler dry validation, and duplicate-job rejection before `sbatch`;
- the formal job produces no scientific verdict after a nonzero engineering exit;
- E3 member-level persistent checkpoints make a retry resume completed members;
- FINAL remains hard-denied.

## 5. Independent review request

Kimi is requested to independently verify archive/sidecar identity, clean extraction, member difference/scope, contract and implementation-review inclusion, D0 runtime reuse, Python 3.9 and contract tests, FINAL exclusion, and the unauthorised-submission gate. Only a package-review PASS should advance to an explicit user upload/submission authorization.
