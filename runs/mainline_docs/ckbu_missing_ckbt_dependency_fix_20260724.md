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
