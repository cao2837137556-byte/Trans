# HPC input/environment audit result, 2026-09-18

Supersedes the authentication-pending state in legacy_reference_hpc_parallel_preparation_20260918.md. Authenticated read-only audit completed with SSH exit0; no HPC experiment started.

Remote node168; historical environment activates /public/home/jiangxinwei.zr/work/kitsune/env/kitsune_py39/bin/python, Python3.9.25. numpy2.0.1, torch2.5.1, dpkt1.9.8. transformers/tokenizers/safetensors/huggingface-hub are absent from that environment's distribution metadata. tshark is absent from its PATH; this does not prove no installation exists elsewhere. Check existing offline vendor libraries and tools before planning installs. Shared filesystem free space is not the user's quota.

The two expected E3 files (model.safetensors and config.json) MATCH expected size/SHA and are reusable. At the explicit expected remote paths,217 LEARN/DEV raw captures,3 immutable manifests and1 frozen R state are missing:221 assets totaling11,668,855,112bytes (10.87GiB). This is not a claim that the whole remote filesystem was exhaustively searched. New local normal-supplement downloads have not been uploaded by this task. No alternate D1 probe-state candidates were found by the bounded known-run glob.

Evidence: remote_audit_output.txt, remote_audit.json, missing_inputs.json, required_inputs.json in runs/legacy_reference_hpc_preparation_v1_20260918. Exact data identities must be checked after transfer; no substitution of other historical state files.

Next: inspect existing offline runtime assets, prepare a tested Linux DEV-only wrapper and missing-input package. Python3.9 alone is insufficient: current local implementation pins Windows Python3.9.13, torch2.8.0+cpu and E3 dependencies. Do not disable dependency guards without an explicit versioned compatibility check. No runnable HPC package delivered yet. Local v2 continues and owns the one final HOLDOUT evaluation; no remote holdout scoring/materialization is permitted in the parallel package.
