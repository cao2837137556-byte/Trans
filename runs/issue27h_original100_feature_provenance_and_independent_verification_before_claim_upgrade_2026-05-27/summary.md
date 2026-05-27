# Issue27h Original100 Feature Provenance And Claim Gate Summary

## Verdict

- primary_verdict: `lowguard_plus_plus_depends_on_high_risk_separators`
- frozen_config_id: `histgb_d2_lr005_l2p1_ood4_sup4_t0050`

## 1. Separator provenance

The three separator features map to legal KitNET/Kitsune traffic statistics: `HH_radius_lambda_0.01; HH_magnitude_lambda_0.01; HH_radius_lambda_0.1`.

## 2. Label/split/bin/capture artifact risk

No direct label/split/bin feature was found. Risk remains `medium-low` because these time-updated flow statistics may indirectly encode temporal/capture conditions, and raw packet-level provenance is still incomplete.

## 3. Support/eval similarity

Support-vs-attack-eval distributions are not identical duplicates; kcenter supports are often more extreme than attack_eval on the separator dimensions. This reduces direct duplication concern but raises a support-representativeness caution.

## 4. Feature ablation

| ablation_variant | feature_count | locked_detection_mean | locked_detection_min | locked_ood_alarm_max | feasible_rate | dominates_lowguard_lr_three_axis |
|---|---|---|---|---|---|---|
| full_original100_reference | 100 | 1.000000 | 1.000000 | 0.000100 | 1.000000 | True |
| remove_top1_separator | 99 | 0.999648 | 0.985915 | 0.000000 | 1.000000 | True |
| remove_top2_separators | 98 | 0.980914 | 0.847418 | 0.010500 | 0.950000 | False |
| keep_only_non_separator_features | 97 | 0.671552 | 0.004695 | 0.006500 | 1.000000 | False |
| remove_all_high_risk_separator_candidates | 97 | 0.671552 | 0.004695 | 0.006500 | 1.000000 | False |
| remove_top3_separators | 97 | 0.671552 | 0.004695 | 0.006500 | 1.000000 | False |
| train_using_only_top3_separators | 3 | 1.000000 | 1.000000 | 0.001100 | 1.000000 | True |


## 5. Top3-only diagnostic

Top3-only near-perfect: `True`.

## 6. Model overdependence

Top3 final AUC drop share by permutation explanation: `0.047384`. Judge this with ablation rather than importance alone.

## 7. Independent verification

Clean independent verification completed: `False`. Available non-locked settings are consistency-only and cannot be used as formal independent proof.

## 8. Main-text performance instance upgrade

`Not yet; LOW-GUARD++ remains audited but needs clean independent validation or stronger provenance before major claim upgrade.`

## 9. Missing evidence

- raw packet/timestamp/row provenance for original100 row generation;
- clean locked-independent or second-environment verification;
- bounded wording that avoids universal HistGB/LOW-GUARD claims.

## 10. Issue27i

`issue27i_separator_dependency_deeper_audit_or_demote_lowguard_plus_plus`

## 11. Slurm

Not needed.
