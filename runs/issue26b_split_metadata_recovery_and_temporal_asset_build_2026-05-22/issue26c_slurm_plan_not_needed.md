# Issue26c Slurm Plan Not Needed Yet

No formal Slurm task is recommended from issue26b because no clean formal temporal validation candidate is ready.

If a later metadata recovery step finds raw timestamps / packet-order / unused future windows, prepare a date-stamped `sbatch` script under the future issue26c run directory, with stdout/stderr named by job id and with `squeue` / `sacct` checks recorded. Do not run formal validation on a login node.
