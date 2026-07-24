# CKBU missing CKBT dependency correction

Date: 2026-07-24

## Failure

CKBU seed-27 jobs `153331` (AMD) and `153332` (Intel) both failed before
scientific execution:

- AMD: `FAILED 2:0`, elapsed 2 seconds.
- Intel: `FAILED 2:0`, elapsed 1 second.
- Missing immutable input:
  `runs/issue27ckbt_toniot_aux_process_support_gate_v1_2026-07-22/aux_process_support_candidate_manifest.csv`.

No PCAP extraction, model fitting, threshold selection, report evaluation, or
scientific result occurred. These job IDs are infrastructure failures and must
not be interpreted as CKBU `NO_GO`.

## Root cause

The Slurm script correctly required the frozen CKBT support manifest, but the
r2 installer neither copied the tracked CKBT result directory nor checked that
dependency before calling `sbatch`. The six ToN pilot PCAPs were checked, so
the incomplete dependency surface incorrectly passed the login-node installer.

## Correction

The corrected installer:

1. copies the complete tracked CKBT result directory without overwriting
   divergent remote files;
2. verifies the 5,000-row support manifest and its frozen SHA-256;
3. verifies the CKBT contract SHA-256 and independent validation `PASS`;
4. checks every immutable file and directory required by the Slurm script
   before either partition is submitted;
5. reuses the six already uploaded and SHA-256-verified PCAPs;
6. keeps AMD and Intel run roots, logs, and pullback archives isolated.

Frozen CKBT hashes:

- support manifest:
  `c637e1e50d86252a590c216c286f53411b83facb60f44be3989afbab1b032fcb`
- contract:
  `9ec01f6df760cdf9bc35836dc049e03e359780bf16278daf7a2466b4904f8940`

This correction changes no split, support role, feature, score, model,
threshold, or preregistered go/no-go rule.

## Compute-node TShark runtime failure

After the immutable-input correction, CKBU jobs `153917` (AMD) and `153918`
(Intel) reached the compute nodes but failed before PCAP extraction:

- AMD: `FAILED 127:0`, elapsed 8 seconds.
- Intel: `FAILED 127:0`, elapsed 6 seconds.
- loader error:
  `libpcap.so.1: cannot open shared object file: No such file or directory`.

The `apps/tshark/4.6.6` module was validated on the login node, where TShark
silently resolved `libpcap.so.1` from `/lib64`. That host-local library is not
available on the compute nodes. The module itself does not add a shared
libpcap directory.

The correction explicitly prepends the shared ABI-compatible library at:

`/share/software/CST/installed/MCR/bin/glnxa64/libpcap.so.1`

Before submission, the installer now requires `ldd` to resolve TShark against
that exact shared path and requires TShark to read the first frame of the
frozen `normal_1.pcap`. The batch script repeats both checks on the compute
node and records the resolved library in `slurm_identity.txt`.

Jobs `153917` and `153918` are infrastructure failures, not scientific
`NO_GO` results. No feature extraction, fitting, threshold selection, or
report evaluation occurred.

## Known-predecessor installation rule

The first corrected runtime bundle stopped on the login node before submission
because the installer correctly refused to overwrite the r3 Slurm file. The
installer now permits exactly two version transitions, each guarded by the
frozen predecessor SHA-256:

- CKBU Slurm script:
  `7c99d3644d9f24b371081729cf0d46a8cc5867981ffe1161af3f5dd4b37fcc9b`
- CKBU infrastructure-failure note:
  `84edb14b76f40d148c3f21e885c119cc01bb21c1c83cfb10f38c0b725cd03050`

No other differing remote target can be overwritten. This login-node stop
submitted no job and produced no scientific result.
