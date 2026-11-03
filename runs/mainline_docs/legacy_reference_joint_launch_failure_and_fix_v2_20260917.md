# Reference joint execution: startup failure and verified v2 fix

Recorded 2026-09-18; attempt and fix artifacts dated 2026-09-17.

## Outcome

The user-authorized v1 complete chain was started once and stopped with STOPPED_NO_RETRY during PREPARE_LEARN_DEV. Completed stages: none; retries: zero. The frozen E3 checkpoint was loaded, but the first tshark launch failed before decoding any real packets. Valid feature vectors, optimizer steps and scientific scores: zero. Preallocated arrays/SQLite are incomplete artifacts, not a reusable cache; cache.json was not produced. No claim about model quality follows from this engineering failure.

Source: runs/legacy_reference_joint_development_v1_20260917/status.json and requests/PREPARE_LEARN_DEV.log. Peak job committed memory was 2,553,434,112 bytes (about 2.38 GiB), below the frozen 12 GiB limit.

## Cause and coverage gap

Windows returned WinError 1816 while subprocess.Popen attempted to start tshark. The original supervisor limited the job to two active processes. The pinned Windows virtual-environment interpreter retains a redirector process plus the actual Python process; this left no slot for the decoder. The isolated decoder-version probe reproduced the failure with venv/two slots and passed with base/two slots or venv/three slots. Source: runs/legacy_reference_decoder_launch_diagnostic_v1_20260917.

The original synthetic end-to-end checks used in-memory packet rows; supervisor tests used base Python. They did not cover the actual virtual-environment launcher plus decoder combination. This was an executor verification gap.

## Concrete fix and verification

Versioned wrapper repo/ood/legacy_reference_executor_control_v2.py provides three process slots only for the pinned encoder virtual environment; the base interpreter retains two. The original scientific worker is unchanged. One actual model worker, one decoder, 12 GiB job/process memory, 16 GiB disk, 72-hour chain cap and zero automatic retries remain unchanged. The per-request job limits are recorded.

Four targeted regressions PASS: base/two-slot decoding of one synthetic packet; venv/three-slot decoding through the actual decoded_rows path; reproduction of the original venv/two-slot error; and fixed-job child-tree termination. Memory and kill flags were checked. These tests read no real dataset or model weights and performed no optimizer work. The original 32-check acceptance is preserved. Source: runs/legacy_reference_executor_launch_fix_v2_20260917/acceptance.json, regression_tests.json, code_pins.json and SHA256SUMS. Fix package and failed-run seals were reverified when writing this note.

## State and next boundary

No real retry has started. The v2 scope template remains execution_authorized=false. A fresh explicit authorization is required for one new complete-chain start because the previously authorized real attempt stopped under the explicit zero-retry condition. The proposed scope is unchanged: shared LEARN/DEV feature preparation, Q/M/C x seeds27/127/227 (nine endpoints), DEV gate, then one conditional DEVICE_HOLDOUT preparation/evaluation. Use a fresh versioned output directory and preserve v1 evidence.

No changes to frozen samples, denominators, threshold, models, losses, seeds, or scientific gate. No downloads, HPC, or historical closed evaluations. LEARN766,727 / DEV179,886 / HOLDOUT341,222 queries and 227 references remain frozen. Synthetic PASS is not scientific PASS.
