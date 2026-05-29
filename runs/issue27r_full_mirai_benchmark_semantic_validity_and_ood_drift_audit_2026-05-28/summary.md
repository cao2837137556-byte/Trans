# issue27r Full Mirai Benchmark Semantic Validity Audit Summary

1. issue27r completed: `true`.
2. primary_verdict: `attack_benign_artifact_risk`.
3. ID benign vs OOD benign drift: `ood_shift_too_artificial_or_row_order_bound`; best diagnostic AUC=0.998820, rank-normalized AUC=0.881677.
4. Drift strength/artifact status: distinguishable but row-order/distributional; no timestamp/capture/session metadata, so deployment drift is weak.
5. OOD benign purity: `supported_by_label_sidecar`; OOD train/val/final OOD rows are labeled benign.
6. OOD benign deployment claim: `weak`; current evidence supports only anonymous clean115 within-dataset row-order/distributional split, not temporal/capture drift.
7. attack vs benign semantics: `attack_benign_artifact_risk`; best diagnostic AUC=0.999972, attack label row-order correlation=0.633630.
8. row-order / scale / source artifact risk: `high`; benign rows are prefix, attack rows are suffix, source/capture metadata absent, and feature semantics anonymous.
9. anonymous_clean115 as main feature space: `anonymous_clean115_feature_semantics_too_weak_for_main_claim`.
10. rank/robust/standard effects: rank-normalization reduces DeepSADStyle_Lite in issue27q_P0P1; diagnostic classifiers remain reported in CSVs, but anonymous feature semantics make scale signals claim-unsafe.
11. low-OOD-alert detection collapse problem: `low_ood_alert_problem_artifact_risk`; present as an operating-point diagnostic, not yet claim-safe.
12. issue27p model ranking usability: diagnostic only; not main-paper evidence until benchmark semantics are fixed.
13. Continue DeepSAD artifact debug: `not before semantic/provenance gate`.
14. Enter LOW-GUARD++ failure diagnosis: `not before semantic/provenance gate`.
15. raw pcap / extractor-level reconstruction needed: `yes, unless a second validated dataset is used`.
16. direct second dataset: `recommended if full Mirai raw provenance cannot be recovered`.
17. issue27s recommendation: raw provenance or second-dataset semantic reconstruction before model-line continuation.
18. Slurm needed: `not for issue27r`; likely for full raw reconstruction or second-dataset feature extraction.
19. commit hash: pending.
