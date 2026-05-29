# issue27s Decision

primary_verdict = `dual_track_raw_rebuild_and_second_dataset_intake`

Supporting stage verdicts:

- full Mirai problem support: `full_mirai_not_sufficient_for_ood_benign_problem`
- raw reconstruction feasibility: `raw_reconstruction_blocked_missing_raw`

Decision:

Current full Mirai anonymous_clean115 cannot serve as the main low-OOD-alert benchmark. It is not abandoned as data, but it is not claim-safe in current form.

Full Mirai can be revisited only if the paired raw/extractor-compatible input stream is recovered and a row-level sidecar proves timestamp/source/capture/label alignment. Because that may take time and may fail, the next issue should run a dual-track plan:

1. try to recover full Mirai raw provenance or a small extractor-level reconstruction proof;
2. start second-dataset intake using strict semantic requirements.

Model experiments remain blocked until one track passes the data validity gate.
