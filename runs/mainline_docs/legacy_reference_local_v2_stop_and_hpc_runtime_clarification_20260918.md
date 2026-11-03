# Local v2 stop and HPC runtime clarification, 2026-09-18

## Current real execution

Local legacy_reference_joint_development_v2_20260918 is STOPPED_NO_RETRY, not running. It stopped around15:44 on2026-09-18, during progress publication at features_LEARN_DEV/status.json.tmp -> status.json. Traceback is PermissionError WinError5 from os.replace in legacy_reference_executor_common_v1.atomic_json. Last published feature progress98,546/946,792; no stage completed, no optimizer steps or scientific scores. The incomplete preallocated cache is not valid/reusable merely because some rows were computed. Failed run remains unchanged; no automatic real retry authorized or performed.

A transient Windows file-sharing conflict is a plausible explanation; the log establishes replacement denial, not which process held the file or that an antivirus/monitor caused it. The worker status file has concurrent readers in the supervisor. Record this as engineering failure, not a model result. Do not claim local fallback remains available while it is stopped.

## HPC manual and observed environment

Read all7pages of the user-supplied March2026 quick-reference PDF. Relevant guidance: use login nodes for preparation/submission, Slurm compute nodes for real work; load module/conda through a fixed environment entrypoint; separate data/code; preserve stdout/stderr and environment provenance; inspect resource usage rather than blindly increasing CPU requests. Manual examples are reference material, not new execution instructions.

The configured environment is Python3.9.25, numpy2.0.1, torch2.5.1, dpkt1.9.8. Loading apps/tshark/4.6.6 and the historical libpcap path makes tshark4.6.6 available. Adding existing D0 r2 payload/vendor_py exposes transformers4.57.3, tokenizers0.22.2, safetensors0.6.2 and huggingface-hub0.36.2; imports all succeeded. No new install is currently justified by the initial unactivated probe. E3 source exists and model/config SHA match from prior audit.

The runtime probe completed intended checks but its shell exited127 because the PowerShell pipe appended a trailing CR-only line. Preserve raw log; do not label whole-command PASS. Future scripts must use LF-safe transport. This is a probe transport defect, not missing cluster software or an experiment failure.

Remaining: CPU/Linux compatibility verification (local E3 torch2.8.0+cpu versus remote2.5.1), versioned path/process adapters, exact input transfer (221missing assets,11,668,855,112bytes), synthetic acceptance, then reviewable upload/submission/pullback commands. No HPC job submitted. Remote first scope remains DEV-only; final HOLDOUT ownership is reserved for local but currently no local execution is active. Ownership must be resolved explicitly before any final heldout evaluation.
