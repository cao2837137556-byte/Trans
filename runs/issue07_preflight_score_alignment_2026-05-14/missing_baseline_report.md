# Missing Baseline / Score Report

## Missing or incomplete for issue07

### Transformer current primary split score coverage
- Missing item: full 50000-row ID score cache for base Transformer.
- Found instead: 5000-row `id_scores.npy` from `id_eval_samples=5000` in `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_tailreg_stage1_2026-03-27\transformer_seed42`.
- Why this matters: future adapter training requires ID benign train negatives and guarded threshold requires ID calibration rows. With only 5000 ID scores, the cache cannot cover current split slices `[0,8000)`, `[10000,15000)`, and `[15000,50000)`.

### Transformer-only exact current baseline
- Existing Transformer-only low-OOD result exists in `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_joint_eval_stage1_2026-03-31\joint_eval_results.csv`.
- Its context is `legacy_partial_id_cache`: 5000 ID rows, OOD calibration/eval split from 20000 OOD rows, and attack source rows.
- This can be cited internally as auxiliary evidence, but should not be used as the fixed exact current primary baseline for issue07.

## Not missing
- dA current score cache is complete and aligned.
- dA current guarded baseline is reusable.
- original100 few-shot LR current guarded baseline is reusable.

## Minimal unblock options
1. Run issue07 only for the dA-score branches first.
2. Before Transformer-score branches, generate full-ID Transformer scores from the existing checkpoint without retraining, if the scorer can safely evaluate all 50000 ID rows.
3. If full-ID Transformer scoring is too costly or unreliable, keep Transformer as auxiliary historical evidence and do not run Transformer adapter under issue07.
