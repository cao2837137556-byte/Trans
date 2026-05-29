# issue27s Raw Provenance Or Second Dataset Semantic Reconstruction Summary

1. issue27s completed: `true`.
2. primary_verdict: `dual_track_raw_rebuild_and_second_dataset_intake`.
3. full Mirai raw pcap exists: `false` for a pcap paired with `Mirai_dataset.csv`; unrelated local IoT23 pcaps exist.
4. timestamp / packet order / label recovery: labels and CSV row order are recoverable; full 764k timestamp/capture/session provenance is not recoverable from current assets. `mirai3_ts.csv` is only a smaller related timestamp sidecar.
5. feature row to raw packet alignment: `blocked`; no paired raw packet/input stream found.
6. claim-safe ID/OOD benign construction: `false` in current full Mirai anonymous_clean115; only row-order benign slices exist.
7. claim-safe attack support/eval construction: row-disjoint attack support/eval is technically possible, but not semantically claim-safe because attack rows are a contiguous suffix and source/capture provenance is missing.
8. full Mirai as main benchmark: not in current form; possible only if paired raw/extractor-level provenance is recovered and a semantic split is rebuilt.
9. if not main benchmark, role: feature/debug diagnostic, interface stress test, attack-only auxiliary with caveats, historical exploratory baseline.
10. raw reconstruction feasible: `raw_reconstruction_blocked_missing_raw`; extractor scripts exist, but full raw input is missing.
11. Slurm needed: not for issue27s; likely for full re-extraction if raw input is recovered.
12. should turn to second dataset: `yes, in parallel`; do not stall model line on anonymous_clean115.
13. second dataset hard conditions: multi-phase/environment benign, attack labels, raw or flow records, timestamp/order, source/capture auditability, report-only final eval, attack support/eval disjointness, low-OOD-alert operating point support.
14. issue27t recommendation: dual-track full Mirai raw provenance search and second-dataset semantic intake.
15. commit hash: pending.
