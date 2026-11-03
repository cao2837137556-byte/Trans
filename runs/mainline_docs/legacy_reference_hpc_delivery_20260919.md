# Reference HPC delivery, 2026-09-19

Implementation and handoff complete; no upload or Slurm submission performed by this task. Local v2 remains STOPPED_NO_RETRY on Windows status-file replacement, not an active fallback. Its partial cache is not reusable as a complete cache.

Entry: runs/legacy_reference_hpc_preparation_v1_20260918/OPERATE_HPC_20260919.md. Contains local upload, remote install/one-time submit, status, local pullback/verification commands. Upload uses WSL rsync --partial --append-verify and verifies local archive SHA first. Code and data remain separate.

Sealed code package:1,319,873bytes; SHA0e19fbbf7e240dce94d7f79aff83798f7f51e5b4c4de3dffde71736f72470ebf.
Sealed input package:6,699,738,683bytes; SHAebbd41d1960f1ece12892f050064a310495d25ddd4fe5d4fb86ac39417b95c4a. Contains221missing assets; raw captures217. Existing matching E3 model/source assets are reused and verified.

Execution scope: one amd node,32CPUs,128GiB,72hours,8workers with4threads each,64GiB output limit. Whole captures assigned to workers; within-capture causal scope and batches unchanged. Shared references recomputed identically and checked at merge; exact UID, metadata and weight identities required. Original scientific train/evaluate functions unchanged. Nine frozen Q/M/C seed endpoints, then LEARN/DEV evaluation only. No automatic retries/requeue, no GPU conversion, no threshold/model/loss search. HOLDOUT cannot be opened by this wrapper even if DEV gate passes; ownership remains reserved, requires resolution before any later final execution.

Local verification:10behavior tests and6Linux lifecycle/atomic-status tests PASS; mock sbatch duplicate protection and export inclusion/hash/omission checks PASS. Python3.9 compilation and shell syntax checks PASS. Final delivery PowerShell parsing and Bash syntax PASS. Read-only sandbox initially blocked PowerShell Parser reflection; unrestricted read-only validation subsequently passed. No scientific success claim.

Fixed synthetic compatibility reference:12synthetic E3 flow forwards and3small synthetic training endpoints on local runtime. Remote Python3.9.25/torch2.5.1 must satisfy recorded environment and numerical rtol1e-4/atol1e-5 checks before real data work. These are still pending on the compute node; they do not prove full-dataset bitwise equivalence. Mandatory preflight is built into the one submitted job.

Prior delivery-file write was rejected by automatic approval service HTTP503 before execution. The current scoped write succeeded after read-only checks; no remaining approval-service block. No sealed historical artifact was modified. Code bundle receipt and local_acceptance_final.json preserve concrete evidence.

Result export declares large intermediate caches omitted. Pullback verification checks every included file against EXPORT_MANIFEST; it does not falsely claim that the partial export verifies all full-run cache seals. Slurm forced termination may prevent export, in which case inspect job logs without resubmitting.
