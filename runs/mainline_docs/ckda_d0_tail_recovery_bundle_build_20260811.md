# CKDA D0 job 158210 tail-recovery bundle build

Date: 2026-08-11

Review authorization: Kimi PASS commit `76e530c4161ba2f91dd0a470e53c637b9c490b45`

## Bundle identity

- bundle directory: `issue27ckda_d0_tail_recovery_158210_20260811`
- archive: `issue27ckda_d0_tail_recovery_158210_20260811_upload_bundle.tar.gz`
- bytes: `6,952`
- SHA-256: `7766d7c71444a1339a60197098f8e218fc749742e4e9c95fbfa8e90fe4c8f89d`
- archive members: `10`
- internally hashed payload members: `4`
- source commit: `76e530c4161ba2f91dd0a470e53c637b9c490b45`

Identity assertions:

- original job: `158210`, required original state `FAILED`;
- recovery class: `POST_RESULT_VALIDATION_PACKAGING`;
- scientific recomputation: `false`;
- Slurm submission: `false`;
- FINAL included: `false`;
- seed 37/47 included: `false`.

## Independent build verification

The archive was independently reopened without trusting the builder output.
The outer SHA matched its sidecar; every `SHA256SUMS` member was read directly
from the compressed archive and rehashed; bundle identity matched the reviewed
commit; Bash syntax and the validator atomic-write contract both passed.

Terminal marker:

```text
CKDA_D0_TAIL_RECOVERY_INDEPENDENT_VERIFY_PASS
CKDA_D0_VALIDATOR_CONTRACT_PASS
```

## Authorization boundary

This build does not authorize or perform remote recovery.  Execution requires
the user's explicit authorization.  The recovery command runs on the HPC login
node, submits no Slurm job, preserves the failed stage, performs no scientific
recomputation, and creates a separately marked recovered result package.
