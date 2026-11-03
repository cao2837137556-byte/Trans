# Reference HPC parallel preparation, 2026-09-18

User authorized preparation of an HPC duplicate for faster execution while keeping the local v2 run as fallback, with reasonably increased resources. No HPC experiment has been submitted. Existing local frozen artifacts and running processes are unchanged.

The HPC branch must stop after LEARN/DEV preparation, nine endpoints and DEV evaluation. Final DEVICE_HOLDOUT ownership remains with the already running local v2 chain. The remote branch must not materialize heldout query features or score heldout data. Any later transfer of this ownership requires verified local/remote state and an explicit exclusive handoff before execution. Duplicate outputs are not independent evidence and must not be selected by better scores.

Current local inventory: 217 raw captures used by LEARN/DEV and their references, 11,513,805,987 bytes (10.72 GiB); including frozen manifests, E3 weights/config and R state, about 11.52 GiB. Immutable full reference manifest may be carried for identity checking, but only LEARN/DEV references may be materialized by the HPC branch. No heldout query manifest or heldout-exclusive raw payload is included in the proposed input list. Presence of shared raw captures does not authorize heldout feature selection.

See runs/legacy_reference_hpc_preparation_v1_20260918/required_inputs.json for exact local paths, expected SHA and explicit remote candidate paths. New downloads have not been transferred by this task. Remote existence and byte identity remain UNVERIFIED; matching names do not establish reuse eligibility.

Screenshot confirms node168, school-hpc connection, active amd/intel/gpu partitions. Login node lacks nvidia-smi in PATH, which does not establish absence of GPUs on compute nodes. Historical workflow used Python3.9; current Python and package compatibility is not yet verified. Current local E3 code enforces Python3.9.13 and specific package versions and uses Windows process APIs. A checked Linux runtime adapter is required; do not directly submit the Windows supervisor or assume more CPU allocations accelerate four-thread code.

Independent BatchMode SSH authentication was rejected. VS Code's existing connection is not directly controllable by this tool environment. A user-visible SSH read-only audit window was opened; the user enters credentials there, never into chat. check_remote_inputs.ps1 streams remote_readonly_audit.sh over SSH stdin, records explicit-file SHA checks and Python dependency versions locally. It submits no jobs and executes no models. The previous partial probe lacked dependency/data evidence; do not interpret it as PASS.

Next: collect authenticated audit, select compatible resources/runtime, build and test a versioned DEV-only Linux execution package, pack missing inputs and provide upload/verification/submit/pullback commands. This document records preparation, not delivery of a runnable validated HPC package.
