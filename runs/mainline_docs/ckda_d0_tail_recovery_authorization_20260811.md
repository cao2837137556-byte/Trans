# CKDA D0 job 158210 tail-recovery authorization

Date: 2026-08-11

The user explicitly authorized execution of the Kimi-reviewed CKDA D0
login-node tail recovery after bundle construction, without waiting for a
second authorization prompt.

Authorized scope:

- upload and verify the 6,952-byte SHA-pinned recovery bundle;
- execute `issue27ckda_d0_tail_recover_158210.sh` on the HPC login node;
- validate and package only the preserved scientific outputs from job 158210;
- create a separately marked post-result recovery pullback.

Not authorized and not required:

- any `sbatch` or new compute job;
- census or resource-pilot recomputation;
- raw PCAP or source-data reopening;
- FINAL access, label reads, threshold selection, or family-specific changes;
- rewriting job 158210 from FAILED to COMPLETED.

Authorized bundle SHA-256:
`7766d7c71444a1339a60197098f8e218fc749742e4e9c95fbfa8e90fe4c8f89d`.
