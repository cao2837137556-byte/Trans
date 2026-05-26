# LOW-GUARD Adapter Interface

All issue27d heads are audited through a common interface:

```python
fit(X_id_train, X_ood_train, X_support_attack, metadata)
score(X)
calibrate(scores_id_calib, scores_ood_val, target)
evaluate(scores_final_ood, scores_attack_eval)
metadata()
```

Contract:

- `score(X)` is normalized so larger scores mean more anomalous / more attack-like.
- OOD train is available only as a benign guard during fitting.
- OOD validation is used only for validation-side thresholding and configuration selection.
- Final OOD eval and attack eval are report-only.
- Every row records `final_eval_used_for_selection=false`.
- `implementation_equivalence_level` distinguishes reference-equivalent, model-specific-lite, proxy-only, and incomplete implementations.
