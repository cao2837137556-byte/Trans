# issue27m Full Mirai Compatibility / Prior-Use / Split-Aware Rebuild Audit

## Verdict

- primary_verdict = `full_mirai_incompatible_needs_new_frontend_path`
- Full Mirai/Botnet is a large, useful asset, but it is **not directly compatible with the frozen `original100 + HistGB-Conservative` LOW-GUARD++ input**.
- The largest file is a 116-column CSV with an index-like first column; the clean historical path is `clean115/restored115`, which the mainline docs already warn must not be mixed with original frontend 100D.
- No evidence was found that full Mirai was used for issue27f LOW-GUARD++ config freeze, kcenter32 support, thresholding, or locked final eval. Historical clean115 use exists and must be separated from any future clean-eval claim.

## Answers

1. full Mirai/Botnet asset format: feature CSV plus label sidecar. `Mirai_dataset.csv` has 116 columns; `mirai_labels.csv` has 764,137 labels.
2. It is not current `original100`. It is best treated as `dirty116` unless col0 is dropped, after which it becomes a `clean115/restored115`-style input. `mirai3.csv` is 115D with timestamp sidecar.
3. Compatibility with current LOW-GUARD++: blocked for frozen `original100`; feasible only through a new `restored115/clean115` path or by re-extracting original100 from raw/packet-level input.
4. original100 recovery/rebuild: not from the current feature CSV alone. It requires raw packet or extracted packet fields compatible with `netStat.py` / `AfterImage.py`.
5. restored115 recovery/rebuild: feature matrices already exist or are recoverable by dropping the index column, but the feature-name/order mapping must be recovered before formal LOW-GUARD++ evaluation.
6. Prior-use/contamination: no current LOW-GUARD++ selection contamination detected; historical clean115 experiments exist, so future clean eval should exclude or explicitly account for those rows.
7. ID/OOD/support/eval construction: row counts are sufficient for full Mirai and official 100k candidates, but evidence is pending frontend compatibility.
8. Split proposal: constructed as proposal-only, not a clean validation split.
9. Split-aware rebuild: blocked from feature CSV alone because state-reset / train-state-then-eval-online needs packet-level frontend input, not only 115D/116D features.
10. Micro-smoke: not executed. Running it now would test a different representation and risk mixing claims.
11. LOW-GUARD++ can enter full Mirai clean eval only after either (a) restored115 is declared as a new bounded LOW-GUARD++ input path with mapping, or (b) full Mirai is re-extracted to current original100.
12. Minimal blocker: feature schema/front-end path incompatibility with frozen original100.
13. Next: `issue27n_full_mirai_restored115_feature_mapping_and_lowguardpp_interface_smoke` or an equivalent re-extraction issue if we choose original100 reconstruction instead.
14. Slurm: not needed for this audit; likely needed for full raw/front-end re-extraction over 764k rows.

## Claim Boundary

Allowed: full Mirai is a large labeled candidate asset; it strengthens the data-expansion route and can support future split-aware LOW-GUARD++ evaluation after feature compatibility is resolved.

Not allowed: LOW-GUARD++ is validated on full Mirai; full Mirai proves temporal/cross-dataset generalization; clean115/restored115 results are interchangeable with frozen original100 results; deployment robustness is proven.
