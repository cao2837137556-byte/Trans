# issue27s Next Action

Recommended next issue:

`issue27s_raw_provenance_or_second_dataset_semantic_reconstruction_for_low_ood_alert_benchmark`

Priority order:

1. Recover timestamp/capture/source/session metadata for full Mirai rows, or confirm it is unavailable.
2. If metadata exists, rebuild a provenance-aware split: benign ID, benign OOD, attack support, attack eval, report-only final OOD, with purge/embargo if temporal.
3. If full Mirai metadata is unavailable, move to a second dataset or raw pcap/extractor-level reconstruction before any further model mainline decision.
4. Preserve issue27p results as diagnostic baselines only; do not use them for final method claims.
5. Only after semantic validity passes should DeepSAD artifact debug and LOW-GUARD++ failure diagnosis resume.

Slurm: not needed for issue27r; may be needed for raw feature reconstruction or second-dataset extraction.
