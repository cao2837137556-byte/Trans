# CKBK seed-27 HPC bundle workflow

This bundle is one real result-producing experiment.  It submits the same
seed-27 workload to AMD and Intel with isolated partition/job paths.  It does
not rebuild CKBE/CKBI/C1 caches, create an environment, install a dependency,
or submit a preflight/smoke job.

## Local Windows upload

Use the login host `172.24.3.168`, not the compute-node label `node168`.
The final handoff supplies the exact local archive path, archive SHA-256, and
new remote directory.  The upload pattern is:

```powershell
ssh jiangxinwei.zr@172.24.3.168 "mkdir -p '<REMOTE_DIR>'"
scp "<LOCAL_ARCHIVE>" jiangxinwei.zr@172.24.3.168:"<REMOTE_DIR>/"
```

## Remote extraction and the only submission action

Run in the normal interactive login shell.  The final handoff substitutes the
exact archive name, directory, and SHA-256.

```bash
cd '<REMOTE_DIR>'
printf '%s  %s\n' '<ARCHIVE_SHA256>' '<ARCHIVE_NAME>' | sha256sum -c -
tar -xzf '<ARCHIVE_NAME>'
cd '<BUNDLE_DIR>'
sha256sum -c SHA256SUMS
bash payload/scripts/issue27ckbk_install_and_submit_seed27.sh
```

The last command records both IDs in:

- `ckbk_seed27_amd_job_id.txt`
- `ckbk_seed27_intel_job_id.txt`

Both copies may finish safely.  They are infrastructure duplicates of the
same seed, not two scientific seeds.

## Status

```bash
bash payload/scripts/issue27ckbk_status_seed27.sh
```

## Pullback after a completed copy

Choose one `COMPLETED 0:0` copy.  Do not combine outputs from two jobs.

```bash
CKBK_PARTITION=amd CKBK_JOB_ID='<JOB_ID>' \
bash payload/scripts/issue27ckbk_validate_and_pack_seed27.sh
```

The validator sources `scripts/00_env_issue27ckc.sh` before its Python checks,
so it does not repeat the earlier login-node `pandas` failure.  It prints the
exact pullback archive path and SHA-256 sidecar.  The final handoff supplies the
matching Windows `scp` command.
