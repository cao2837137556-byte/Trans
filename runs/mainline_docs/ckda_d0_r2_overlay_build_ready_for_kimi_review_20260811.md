# CKDA D0 r2 overlay build ready for Kimi review (2026-08-11)

## Review scope

This report records the local r2 build authorized by Kimi commit `c4276bd`.
It requests artifact review only.  Overlay upload and HPC resubmission remain
separately user-authorized actions.

## Full r2 identity

- bundle root:
  `issue27ckda_d0_representation_compatibility_20260811_r2`;
- source commit: `c4276bd3074dccb900c361d09772ae4bc97eb656`;
- full archive bytes: `665,819,348`;
- full archive SHA-256:
  `91e19a446ffd76300c909a458c47bee74a2efde12b67e3dc02b29e05fef89e95`;
- payload files: `2,834`;
- clean full-archive extraction and all-entry SHA check: `PASS`;
- LF-only gate: `PASS`.

The unchanged model checkpoint remains 698,780,900 bytes with SHA-256
`e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105`.

## Repair overlay identity

- archive:
  `issue27ckda_d0_representation_compatibility_20260811_r2_repair_overlay.tar.gz`;
- bytes: `145,185`;
- SHA-256:
  `6dc832e59b4fc6e716f85dd7810e275c9c9b261dcd3fda4c086cac607e57e140`;
- files: `7`.

Exact members:

1. `bundle_commit.txt`;
2. `bundle_identity.json`;
3. `payload/repo/ood/issue27ckda_netfound_py39_compat_v1.py`;
4. `payload/scripts/issue27ckda_d0_install_and_submit.sh`;
5. `payload/vendor/netFound/PY39_COMPAT_AUDIT.json`;
6. `payload/vendor/netFound/src/modules/netFoundModels.py`;
7. `SHA256SUMS`.

The sidecar was independently reread and matches the recomputed overlay hash.

## Overlay equivalence test

The builder performed this clean-room sequence:

1. reject any file present in r1 but absent from r2;
2. derive overlay membership only from per-file SHA differences;
3. copy the verified r1 directory to an isolated r2 verification root;
4. extract the 7-file overlay over that copy;
5. recompute every entry in the resulting r2 `SHA256SUMS`.

Result: `clean_overlay_sha_check=PASS`.  Thus the 145,185-byte overlay plus the
verified r1 directory is byte-equivalent to the locally verified full r2
bundle for every hashed file.

## Compatibility audit in the artifact

- upstream source SHA-256:
  `a70366ea775f2eeaabd2e6a00a44c2dfae1a199249a3688d5183866b8a4ed0ed`;
- patched source SHA-256:
  `a66834ea194a291ebbf563027df5e995f57ce8033699b8bc8e78f071de931526`;
- replacements: `1`;
- Python-3.9 AST files: `17`;
- semantic-change marker: `NONE_SYNTAX_EQUIVALENT_IF_ELIF`.

## Proposed remote boundary after PASS

The remote procedure must preserve the r1 directory, copy it to the exact r2
name, apply the hash-pinned overlay, run the full r2 `SHA256SUMS`, and only then
invoke the r2 installer.  Job `158187` remains failure evidence.  The new job
may reuse only the content-addressed census checkpoint and must regenerate its
summary before entering the resource pilot.
