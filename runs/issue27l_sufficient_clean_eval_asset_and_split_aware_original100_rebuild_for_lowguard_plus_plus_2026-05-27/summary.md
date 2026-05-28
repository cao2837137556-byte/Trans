# Issue27l Sufficient Clean Eval Asset And Split-Aware Original100 Rebuild Summary

## Verdict

- primary_verdict: `clean_eval_asset_found_rebuild_eval_next`
- issue27m_next_action: `issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild`
- commit_hash: `pending_before_git_commit`

## 1. Sufficient clean eval asset

Sufficient-sized eval candidate found in current extracted assets: `True`.

Large labeled full Mirai/Botnet eval asset found: `True`.

The best candidate is `extended_attack_10k_30k_plus_future_benign_90k_110k`: 20,000 future attack rows plus 20,000 future benign rows.

After the user-requested full-dataset search, the higher-priority candidate is `full_mirai_labeled_restored115_chrono_split`: 764,137 labeled rows with 121,621 benign and 642,516 attack rows.

## 2. Main gap

The blocker is not row count anymore. The blocker is feature/protocol compatibility: full Mirai appears restored115-style while frozen LOW-GUARD++ is original100 + HistGB-Conservative.

## 3. Best available split

Best available split manifest constructed: `True`.

Split evidence_level: `large_labeled_dataset_candidate_pending_frontend_compatibility`.

## 4. Split-aware original100 rebuild

Executed: `False`.

Executable state strategies: `continuous_state_baseline`, `reset_at_split_boundary`, and `train_state_then_eval_online`.

## 5. Frozen LOW-GUARD++ clean/purged evaluation

Executed: `False`.

No clean/purged LOW-GUARD++ metric is claimed from issue27l.

## 6. Safer variants

Not evaluated because clean eval and split-aware rebuilt features were not admitted.

## 7. Continuous-state carryover

No new evidence proves old continuous-state carryover invalid, but it remains a claim-safety risk until split-aware rebuild is run.

## 8. Main-text upgrade

LOW-GUARD++ cannot yet be upgraded to main-text performance instance.

## 9. Slurm

Not required for this audit/search. Slurm may be needed for full feature reconstruction or second-environment feature construction.
