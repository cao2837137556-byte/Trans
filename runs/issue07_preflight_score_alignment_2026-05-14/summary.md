# Issue07 Preflight Score Alignment Summary

## 1. Task scope
This run performs only the first-step asset check for future base-detector few-shot adapter experiments. It did not train models, did not run adapters, did not modify the manuscript, and did not change any existing experimental numbers.

## 2. Main finding
The existing assets support a **dA-assisted few-shot adapter branch now**, but they do **not yet support a strict current-split Transformer-assisted adapter branch**.

## 3. dA availability
- dA full score cache exists in `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\original100_fewshot_official_control_2026-04-22\score_cache`.
- ID score length: 50000.
- OOD benign score length: 20000.
- Attack score length: 10000.
- Prior collapse sanity audit marks these caches as aligned.
- Current dA guarded baseline is reusable from `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\original100_fewshot_official_control_2026-04-22\original100_fewshot_official_control_focus.csv`:
  - ROC-AUC: 0.806365
  - final OOD alarm: 0.010800
  - attack detection: 0.002909

## 4. Transformer availability
Transformer OOD and attack scores do exist, so the OOD runs were indeed saved:
- OOD benign score: `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_tailreg_stage1_2026-03-27\transformer_seed42\iot23_ood_benign_scores.npy` with 20000 rows.
- Attack score: `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_joint_eval_stage1_2026-03-31\transformer_attack_scores.npy` with 10000 rows.

However, the base Transformer ID score cache is only 5000 rows:
- `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_tailreg_stage1_2026-03-27\transformer_seed42\id_scores.npy`

Current primary protocol needs 50000 ID scores to slice ID train, ID calibration, and ID final eval. Therefore Transformer assets are currently **historical/auxiliary low-OOD evidence**, not a ready current-split adapter input.

## 5. Baseline reuse status
- `fixed_baseline_da_only`: exact current protocol, reusable.
- `fixed_baseline_original100_lr`: exact current protocol, reusable for 16-shot and 32-shot.
- `fixed_baseline_transformer_only`: auxiliary only; existing result uses legacy partial-ID cache.

## 6. Go / no-go
- dA adapter branch: **go**.
- Transformer adapter branch: **no-go until full-ID Transformer scores are recovered or generated without retraining**.
- Full issue07 with both dA and Transformer: **not ready**.

## 7. Output files
- `score_alignment_check.csv`
- `score_availability_report.md`
- `baseline_reuse_report.csv`
- `missing_baseline_report.md`
- `risk_register.csv`
- `recommended_next_action.md`

## 8. Claim boundary
This preflight does not prove adapter effectiveness. It only verifies which cached scores and baselines can be safely reused for the next experiment.
