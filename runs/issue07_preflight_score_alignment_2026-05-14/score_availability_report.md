# Score Availability Report

## Scope
This preflight checks whether existing dA / Transformer per-sample scores can support a future `issue07` low-OOD few-shot adapter experiment. No model was trained and no adapter was run.

## dA score cache
- Status: **ready** for `da_score_only_fewshot_lr` and `original100_plus_da_score_fewshot_lr`.
- Cache directory: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\original100_fewshot_official_control_2026-04-22\score_cache`
- Files:
  - `da_full_id_scores.npy`: 50000 rows, aligned with full ID source.
  - `da_ood_scores.npy`: 20000 rows, aligned with OOD benign source.
  - `da_attack_scores.npy`: 10000 rows, aligned with attack source.
- Existing audit source: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\collapse_sanity_audit_2026-04-25\score_cache_alignment_check.csv`.

## Transformer score cache
- Status: **partial / blocked for current primary split adapter**.
- Transformer OOD and attack score files do exist:
  - `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_tailreg_stage1_2026-03-27\transformer_seed42\iot23_ood_benign_scores.npy`: 20000 rows.
  - `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_joint_eval_stage1_2026-03-31\transformer_attack_scores.npy`: 10000 rows.
- Blocking issue:
  - `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_tailreg_stage1_2026-03-27\transformer_seed42\id_scores.npy` has only 5000 rows.
  - Current primary protocol needs scores covering the full 50000 ID source rows so it can slice ID train/calibration/eval consistently.
- Therefore existing Transformer assets are valid as historical/auxiliary low-OOD evidence, but not enough for a strict current-split Transformer-score adapter without regenerating or recovering full-ID Transformer scores.

## Key distinction
The user memory is correct: Transformer and dA both have OOD low-OOD results saved. The adapter preflight asks a stricter question: whether each detector has row-aligned scores for all split roles needed by current few-shot training and guarded threshold selection. dA passes; Transformer does not yet pass because of the 5000-row ID score cache.
