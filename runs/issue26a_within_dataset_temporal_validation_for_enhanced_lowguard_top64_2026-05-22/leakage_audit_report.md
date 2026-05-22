# Leakage Audit Report

Scope: issue26a audits candidates only. It does not change topK, support budget, adapter, or threshold protocol.

## chrono_early_train_late_eval
- candidate_type: chronological_cross_window
- top64 feature selection participation: no new feature selection allowed; frozen top64 only
- threshold selection participation: no if ID/OOD val only
- support selection participation: no if rebuilt from train bins only
- adapter/model choice participation: no direct issue22 discovery, but late eval bins overlap locked bins
- issue22/22b/23/25c overlap: yes
- train/cal/val/final time overlap risk: medium
- needs purging: yes
- needs embargo/gap: yes
- usable for issue26b formal temporal validation: no under current metadata
- consistency-check only: yes
- conclusion: usable_with_purge_embargo
- reason: Natural temporal direction, but not clean new proof because eval bins 6/7/8 were already used as locked evidence in issue23/25c.

## purged_future_window_holdout
- candidate_type: purged_temporal_split
- top64 feature selection participation: unknown
- threshold selection participation: no if constructed before eval
- support selection participation: unknown
- adapter/model choice participation: unknown
- issue22/22b/23/25c overlap: unknown
- train/cal/val/final time overlap risk: unknown
- needs purging: yes
- needs embargo/gap: yes
- usable for issue26b formal temporal validation: no under current metadata
- consistency-check only: no/unknown
- conclusion: insufficient_metadata
- reason: Scientifically preferable if raw temporal metadata can recover a future window not consumed by issue22/23/25c. Current metadata is insufficient.

## holdout_bin_3
- candidate_type: leave_one_bin_out
- top64 feature selection participation: yes via issue22 chrono discovery overlap
- threshold selection participation: no
- support selection participation: unknown
- adapter/model choice participation: yes
- issue22/22b/23/25c overlap: yes
- train/cal/val/final time overlap risk: high
- needs purging: unknown
- needs embargo/gap: unknown
- usable for issue26b formal temporal validation: no under current metadata
- consistency-check only: yes
- conclusion: not_recommended
- reason: Eval bin overlaps issue22 chrono_late discovery bins.

## holdout_bin_4
- candidate_type: leave_one_bin_out
- top64 feature selection participation: yes via issue22 chrono discovery overlap
- threshold selection participation: no
- support selection participation: unknown
- adapter/model choice participation: yes
- issue22/22b/23/25c overlap: yes
- train/cal/val/final time overlap risk: high
- needs purging: unknown
- needs embargo/gap: unknown
- usable for issue26b formal temporal validation: no under current metadata
- consistency-check only: yes
- conclusion: not_recommended
- reason: Eval bin overlaps issue22 chrono_late discovery bins.

## locked_bins_5_6_7_8_reanalysis
- candidate_type: leave_one_bin_out_locked_reuse
- top64 feature selection participation: no new selection allowed
- threshold selection participation: no new threshold selection allowed
- support selection participation: no new selection allowed
- adapter/model choice participation: no for issue22 discovery
- issue22/22b/23/25c overlap: yes
- train/cal/val/final time overlap risk: medium
- needs purging: unknown
- needs embargo/gap: unknown
- usable for issue26b formal temporal validation: no under current metadata
- consistency-check only: yes
- conclusion: consistency_only
- reason: Evidence inventory only; repeated locked-bin analysis is not new temporal proof.

## adjacent_bin_holdout
- candidate_type: adjacent_window_holdout
- top64 feature selection participation: unknown
- threshold selection participation: unknown
- support selection participation: unknown
- adapter/model choice participation: unknown
- issue22/22b/23/25c overlap: unknown
- train/cal/val/final time overlap risk: medium
- needs purging: yes
- needs embargo/gap: yes
- usable for issue26b formal temporal validation: no under current metadata
- consistency-check only: no/unknown
- conclusion: insufficient_metadata
- reason: Potentially useful, but adjacent-window contamination and prior bin use make cleanliness unclear.

## rolling_origin_validation
- candidate_type: rolling_origin
- top64 feature selection participation: unknown
- threshold selection participation: unknown
- support selection participation: unknown
- adapter/model choice participation: unknown
- issue22/22b/23/25c overlap: unknown
- train/cal/val/final time overlap risk: medium
- needs purging: yes
- needs embargo/gap: yes
- usable for issue26b formal temporal validation: no under current metadata
- consistency-check only: no/unknown
- conclusion: insufficient_metadata
- reason: Good design, but current artifacts do not persist enough clean temporal metadata.

## larger_attack_eval_window
- candidate_type: data_scale_stress
- top64 feature selection participation: yes/unknown
- threshold selection participation: no
- support selection participation: unknown
- adapter/model choice participation: yes
- issue22/22b/23/25c overlap: yes
- train/cal/val/final time overlap risk: high
- needs purging: yes
- needs embargo/gap: yes
- usable for issue26b formal temporal validation: no under current metadata
- consistency-check only: yes
- conclusion: not_recommended
- reason: Mostly reuses previously inspected bins/windows; suitable only as appendix after clean split recovery.

## later_to_earlier_chrono_repeat
- candidate_type: reverse_chronological_consistency
- top64 feature selection participation: yes
- threshold selection participation: no
- support selection participation: unknown
- adapter/model choice participation: yes
- issue22/22b/23/25c overlap: yes
- train/cal/val/final time overlap risk: high
- needs purging: unknown
- needs embargo/gap: unknown
- usable for issue26b formal temporal validation: no under current metadata
- consistency-check only: yes
- conclusion: not_recommended
- reason: Already used in method discovery/confirmation; consistency evidence only.
