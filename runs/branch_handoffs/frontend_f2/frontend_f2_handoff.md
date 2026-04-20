# Frontend-F2 Handoff
最后更新：2026-04-17

## 0. 维护规则

- 这是 `frontend-f2` 支线**唯一持续维护**的主 handoff。
- 以后这条支线的阶段进展、结果、失败点、当前结论、下一步计划，都只更新这一个文件。
- `runs/prism_handoffs/` 下的 dated handoff 保留为**历史归档**，不再作为主维护入口。
- 每个稳定节点完成后，应更新本文件，并在需要时再做 `commit + push`。

## 1. 支线定位

- 分支：`codex/frontend-f2`
- 目录：`worktrees/kitnet-frontend-f2`
- 目标：为 stronger-OOD 异常检测项目探索“前端表达重构”路线。
- 关注点：从原始 TSV / frontend 提取链重新生成更适合模型的 model-facing expression，而不是继续在 old `100D` 平面表示上做后端小修小补。

## 2. 和主线的关系

- 主线分支：`codex/exp-mainline`
- 主线职责：维护论文主叙事、 strongest candidate、已验证主实验代码。
- 本支线职责：高风险探索新的 frontend expression。
- 原则：本支线可以失败，但不能污染主线；只有明确有效的表达或结论才考虑回收。

## 3. 当前结论

- old `100D` 的高级重排已经基本试穿，上限明显：
  - `structured_tokenizer_v1` 最好约 `alarm 0.012 / det 0.20`
  - `contrast_tokenizer_v1` 最好约 `alarm 0.07 / det 0.30`
- `expression_v2 [20,5]` 证明 extractor-level 新表达可以落地，但通道压缩过猛，失败：
  - token-MLP 几乎“全报”
  - transformer AUC 只有 `0.18~0.21`
- `expression_v3 [20,8]` 是当前有效主线：
  - 修复了 `pcc` 和 `dispersion(CV)` 的数值爆炸
  - family-selective scoring 后，AUC 提升到 `0.810~0.838`
  - 首次出现 `alarm <= 1%` 的 feasible 点
- 当前最值得继续押的候选不是 `hphp_mean`，而是：
  - `transformer + family_short_focus + mi_dir_mean`
  - `transformer + family_short_focus + mi_hphp_short_mean`

## 4. 当前最佳结果

### 判别力最强

- `transformer + family_short_focus + mi_hphp_short_mean`
  - `fixed_alarm = 0.964`
  - `fixed_det = 0.974`
  - `calibrated_alarm = 0.065`
  - `calibrated_det = 0.460`
  - `AUC = 0.838`

- `transformer + family_short_focus + mi_dir_mean`
  - `fixed_alarm = 0.549`
  - `fixed_det = 0.853`
  - `calibrated_alarm = 0.045`
  - `calibrated_det = 0.441`
  - `AUC = 0.810`

### 首个 feasible 点

- `transformer + family_short_focus + hphp_mean`
  - `calibrated_alarm = 0.0093`
  - `calibrated_det = 0.133`
  - `AUC = 0.536`
  - `feasible = True`

解释：

- `hphp_mean` 的价值是证明这条支线**存在**满足 `alarm<=1%` 的 operating point。
- 但它的 detection 太低，不应当作为当前主攻候选。

## 5. 当前最关键的认识

### 5.1 `expression_v3` 已经证明这条路有希望

- 与 `expression_v2` 相比，`expression_v3` 不再是“方向不清的试错”。
- 它已经表现出：
  - 可解释的 AUC 提升
  - 可解释的 family-level 诊断结果
  - 可解释的 alarm/det trade-off

### 5.2 HH / HH_jit 是 OOD alarm 的主要来源

- per-token 诊断显示：
  - HH / HH_jit 的 OOD/ID RMSE 比达到 `10~39x`
  - 但 Attack/ID 只有 `10~25x`
- 含义：
  - 在这些 token 上，benign OOD 比 attack 更难重建
  - 它们显著抬高 OOD alarm
- 排除这两个 family 后，AUC 上升且 calibrated alarm 明显下降。

### 5.3 PCC 与 dispersion 必须做数值压缩

- Kitsune frontend 的 `pcc` 在真实数据中并不受限于 `[-1, 1]`
- OOD 上可出现 `6.64e7` 级别极端值
- `dispersion = std/mean` 在 `mean≈0` 时也会异常放大
- 结论：
  - `pcc` 和 `dispersion` 不能 raw 用
  - 必须 `slog()` 压缩

## 6. 当前最关键的失败点

- `structured_tokenizer_v1`
  - 失败原因：只是 100D 重排，信息上限不足
- `contrast_tokenizer_v1`
  - 失败原因：仍属 old `100D` 重排，提升有限
- `expression_v2`
  - 失败原因：通道压缩过猛，判别结构被打坏
- `expression_v3` 修复前版本
  - 失败原因：`pcc/dispersion` 数值爆炸，导致 OOD outlier 主导

## 7. 下一步计划

### 优先级 1：增训练量

- 当前 smoke 规格：`20 epochs + 8000 samples`
- 下一步优先：
  - `50 epochs + 20000 samples`
  - 主跑对象：`mi_dir_mean`、`mi_hphp_short_mean`
- 目标：
  - 看是否能把 calibrated alarm 从 `4~7%` 继续压向 `1~3%`
  - 同时尽量保住 `det > 30%`

### 优先级 2：family-selective weighted scoring

- 当前 `mi_dir_mean` / `mi_hphp_short_mean` 仍然是简单 mean
- 下一步可以尝试：
  - 给 MI_dir 更高权重
  - 给短尺度 token 更高权重
  - 按 diagnostic 中更健康的 token 分布加权

### 优先级 3：把 `hphp_mean` 当作 feasibility reference，而不是主攻方向

- 它的作用是证明 `alarm<=1%` 的 feasible operating point 存在
- 不是当前最有前景的主 scoring 候选

### 当前不做

- 不开多 seed
- 不扩超算 sweep
- 不改大模型结构
- 不 merge 主线

## 8. 时间线

### 2026-04-13

- F2 结构化缓存链打通
- 完成真实数据 `7-6 / 4-1 / 34-1` 的 structured 抽取

### 2026-04-14

- 两轮 token 重排确认 old `100D` 上限不足
- `expression_v2` 落地，但 smoke 失败

### 2026-04-16

- `expression_v3` 落地
- 修复 `pcc / dispersion` 爆炸
- 加入 calibration 逻辑
- 加入 per-token diagnostic
- 加入 family-selective scoring
- `fix3` 成为当前主参考节点

### 2026-04-17

- 把支线 handoff 体系切换为**单一滚动 handoff**
- 本文件成为之后唯一持续维护的主 handoff
- 新建 `v4a_hh_stabilized` 设计文档，专门放入支线设计目录

### 2026-04-19

- 按 hard-masking ablation 方案实现 `compute_expression_v4a_hh_stabilized(...)`
- extractor 现在可同时导出 `token_matrix_v3` 与 `token_matrix_v4a_hh_stabilized`
- 两个 source prep 脚本已支持 `--expression-version {v3,v4a_hh_stabilized}`
- 新增独立 smoke 入口：`repo/ood/frontend_f2_expression_v4a_tokenizer_v1.py`
- 代码已完成并通过语法 / `--help` 自检
- 已完成本地 smoke：
  - `runs/frontend_f2_expression_v4a_crosscapture_stage1_2026-04-17/`
  - `runs/frontend_f2_expression_v4a_attack_source_2026-04-17/`
  - `runs/frontend_f2_expression_v4a_tokenizer_v1_smoke_2026-04-17/`
- 本轮核心结论：
  - `v4a` 没有优于 `v3 fix3`
  - `transformer + family_short_focus + mi_dir_mean`
    - `AUC 0.759`
    - `calibrated_alarm 0.043`
    - `calibrated_det 0.272`
    - 相比 `v3 fix3` 的 `AUC 0.810 / alarm 0.045 / det 0.441`，det 明显下降
  - `transformer + family_short_focus + mi_hphp_short_mean`
    - `AUC 0.776`
    - `calibrated_alarm 0.065`
    - `calibrated_det 0.339`
    - 相比 `v3 fix3` 的 `AUC 0.838 / alarm 0.065 / det 0.460`，AUC 与 det 均下降
  - `hphp_mean` 不再出现 `feasible=True`
    - 最好仅到 `calibrated_alarm 0.019 / calibrated_det 0.092`
- 当前判断：
  - 仅对 HH / HH_jit 做 `ch0/ch1/ch3/ch4` hard mask 过于粗暴
  - 它确实压低了一部分 calibrated alarm，但同时破坏了整体判别力，尤其是 detection
  - 这条 hard-masking ablation 可以视为一个**负结果节点**
  - 结论不是“HH / HH_jit 不该处理”，而是“不能只靠简单硬屏蔽”

## 9. 必看代码

- `repo/ood/kitsune_frontend_original_extract.py`
- `repo/ood/prepare_frontend_f2_crosscapture_sources.py`
- `repo/ood/prepare_frontend_f2_attack_source.py`
- `repo/ood/frontend_f2_expression_v3_tokenizer_v1.py`
- `repo/ood/frontend_f2_expression_v3_token_diagnostic.py`

## 10. 必看设计

- `runs/branch_designs/frontend_f2/frontend_f2_v4a_hh_stabilized_implementation_spec.md`

## 11. 必看 runs

- `runs/frontend_f2_expression_v3_crosscapture_stage1_2026-04-16/data/`
- `runs/frontend_f2_expression_v3_attack_source_2026-04-16/data/`
- `runs/frontend_f2_expression_v3_token_diag_2026-04-16/`
- `runs/frontend_f2_expression_v3_tokenizer_v1_smoke_2026-04-16_fix3/`
- `runs/frontend_f2_expression_v4a_crosscapture_stage1_2026-04-17/`
- `runs/frontend_f2_expression_v4a_attack_source_2026-04-17/`
- `runs/frontend_f2_expression_v4a_tokenizer_v1_smoke_2026-04-17/`

## 12. 关键输出文件

### fix3 run

- `summary.md`
- `frontend_f2_expression_v3_combined.csv`
- `frontend_f2_expression_v3_results.csv`

### diagnostic run

- `token_diagnostic.md`
- `problem_tokens.csv`
- `heatmap_tail_overlap.png`
- `token_dist_4x5.png`

## 13. 接手时先看什么

1. 本文件第 3、4、5、7 节
2. `runs/branch_designs/frontend_f2/frontend_f2_v4a_hh_stabilized_implementation_spec.md`
3. `runs/frontend_f2_expression_v3_tokenizer_v1_smoke_2026-04-16_fix3/summary.md`
4. `runs/frontend_f2_expression_v3_tokenizer_v1_smoke_2026-04-16_fix3/frontend_f2_expression_v3_combined.csv`
5. `runs/frontend_f2_expression_v3_token_diag_2026-04-16/token_diagnostic.md`
6. `runs/frontend_f2_expression_v3_token_diag_2026-04-16/problem_tokens.csv`

## 14. 关键约束与陷阱

- 不改 original-frontend `flat100` 的历史兼容输出逻辑
- `pcc` 和 `dispersion` 不能 raw 使用，必须做压缩
- token 布局固定：
  - tokens `0-4` = MI_dir
  - tokens `5-9` = HH
  - tokens `10-14` = HH_jit
  - tokens `15-19` = HpHp
- scale 顺序固定：
  - `0=5s`
  - `1=3s`
  - `2=1s`
  - `3=0.1s`
  - `4=0.01s`

## 15. 2026-04-20 Update (v4b_hh_soft_stabilized)

- Locked decision: treat `v4a_hh_stabilized` as strategy-level negative result; move to `v4b_hh_soft_stabilized`.
- Implemented extractor-side `compute_expression_v4b_hh_soft_stabilized(...)` with:
  - MI_dir/HpHp unchanged from v3.
  - HH/HH_jit soft-stabilized channels (`ch0/ch1/ch3/ch4/ch5/ch6/ch7`) and keep `ch2` from v3.
  - `nan_to_num` and channel-wise clipping (`[-6,6]` for ch0/ch1/ch3/ch4/ch5, `[-4,4]` for ch6/ch7).
- Structured cache export now includes `token_matrix_v4b_hh_soft_stabilized` and related metadata.
- Added audit output: `expression_v4b_audit.json` (nan_count / inf_count / max_abs / p99_abs per channel).
- Updated source prep scripts to support `--expression-version v4b_hh_soft_stabilized` and v4b-named outputs.
- Added independent smoke entry: `repo/ood/frontend_f2_expression_v4b_tokenizer_v1.py`.
- Local status:
  - `py_compile` passed for modified scripts.
  - `--help` checks passed for both source prep scripts and v4b tokenizer script.
- Next step: run the three v4b local-smoke commands and evaluate:
  - `transformer + family_short_focus + mi_dir_mean`
  - `transformer + family_short_focus + mi_hphp_short_mean`

## 16. 2026-04-20 Smoke Results (v4b_hh_soft_stabilized)

- Executed:
  - `frontend_f2_expression_v4b_crosscapture_stage1_2026-04-20`
  - `frontend_f2_expression_v4b_attack_source_2026-04-20`
  - `frontend_f2_expression_v4b_tokenizer_v1_smoke_2026-04-20` (CPU)
- Main focus checkpoints:
  - `transformer + family_short_focus + mi_dir_mean`
    - `AUC=0.6649`
    - `calibrated_alarm=0.0377`
    - `calibrated_det=0.0793`
    - `selection_feasible=False`
  - `transformer + family_short_focus + mi_hphp_short_mean`
    - `AUC=0.7180`
    - `calibrated_alarm=0.0138`
    - `calibrated_det=0.1853`
    - `selection_feasible=False`
  - `transformer + family_short_focus + hphp_mean`
    - `calibrated_alarm=0.0089`
    - `calibrated_det=0.1303`
    - `selection_feasible=True`
- Additional observation:
  - `token_mlp + uniform + mi_hphp_mean` reached `AUC=0.8547`, `calibrated_alarm=0.0290`, `calibrated_det=0.3401`.
- Current conclusion:
  - For the two prioritized transformer objectives, v4b still underperforms target (especially detection and AUC).
  - v4b did not resolve the core transformer bottleneck yet.

## 17. 2026-04-20 Source-Rich Stage1 (frontend re-extraction line)

- Strategy update:
  - Pause `v4a/v4b` HH/HH_jit stabilization line.
  - Start frontend re-extraction Stage1 with richer source-level representation + offline audit.
- Implemented `source_rich_v1` view (`[N,20,13]`) in extractor:
  - raw channels: `logw_raw, mean_slog_raw, std_slog_raw, cv_slog_raw, cov_slog_raw, pcc_slog_raw`
  - family-relative channels: `mean_rel_family, std_rel_family, logw_centered_family, cov_rel_family, pcc_centered_family`
  - cross-scale channels: `mean_short_long_ratio, cv_short_long_ratio`
  - numeric protection: `nan_to_num`, clip raw/rel/centered to `[-6,6]`, ratio to `[-4,4]`
- Minimal source prep support added:
  - `--expression-version source_rich_v1` in both crosscapture/attack prep scripts
  - output matrices:
    - `id_source_expression_source_rich_v1_matrix.npy`
    - `ood_benign_source_expression_source_rich_v1_matrix.npy`
    - `attack_source_expression_source_rich_v1_matrix.npy`
- New offline audit script:
  - `repo/ood/frontend_f2_source_rich_audit.py`
  - outputs:
    - `source_rich_channel_audit.csv`
    - `source_rich_family_scale_summary.csv`
    - `source_rich_problem_channels.csv`
    - `source_rich_recommendation.md`
    - `source_rich_audit.json`
    - `summary.md`
- Run artifacts:
  - `runs/frontend_f2_source_rich_crosscapture_stage1_2026-04-20/`
  - `runs/frontend_f2_source_rich_attack_source_2026-04-20/`
  - `runs/frontend_f2_source_rich_audit_2026-04-20/`
- Stage1 audit highlights:
  - recommended v5 compact keep channels:
    - `mean_slog_raw, cv_slog_raw, logw_centered_family, mean_rel_family, std_slog_raw, logw_raw, std_rel_family, pcc_centered_family`
  - downweight/drop candidates:
    - `mean_short_long_ratio, cov_slog_raw`
  - family focus order (health high -> low):
    - `HpHp, HH, HH_jit, MI_dir`
  - scale focus order (health high -> low):
    - `0.1s, 0.01s, 1s, 3s, 5s`

## 18. 2026-04-20 v5_compact_v1 Smoke (audit-guided compact baseline)

- Implemented and ran:
  - `frontend_f2_expression_v5_compact_crosscapture_stage1_2026-04-20`
  - `frontend_f2_expression_v5_compact_attack_source_2026-04-20`
  - `frontend_f2_expression_v5_compact_tokenizer_v1_smoke_2026-04-20` (CPU)
- Key transformer + family_short_focus results:
  - `mi_dir_mean`: `AUC=0.8286`, `calibrated_alarm=0.0125`, `calibrated_det=0.1578`
  - `mi_hphp_short_mean`: `AUC=0.8083`, `calibrated_alarm=0.0027`, `calibrated_det=0.1691`
  - `hphp_mean`: `feasible=True`, but `calibrated_det=0.0000`
- Conclusion:
  - Better than `v4a/v4b` in overall shape.
  - Still below `v3 fix3` on low-alarm detection (`det` remains too low).

## 19. 2026-04-20 v6_input_aligned_v1 Smoke (short-scale input-alignment attempt)

- Goal:
  - Move from patch-style channel tweaks to input/model alignment.
  - Keep model/training pipeline fixed, but redesign input as short-scale compact tokens.
- Implemented:
  - New expression version `v6_input_aligned_v1` in extractor:
    - derived from `source_rich_v1`
    - short scales only `1s/0.1s/0.01s` (`scale_id=[2,3,4]`)
    - output shape `[N,12,8]` (4 families x 3 scales)
    - HH/HH_jit families use relative replacements for raw-absolute channels.
  - Source prep support in both scripts:
    - `--expression-version v6_input_aligned_v1`
    - outputs `*_expression_v6_input_aligned_v1_matrix.npy` and `*_96.npy`
  - New smoke entry:
    - `repo/ood/frontend_f2_expression_v6_input_aligned_tokenizer_v1.py`
- Executed runs:
  - `frontend_f2_expression_v6_input_aligned_crosscapture_stage1_2026-04-20`
  - `frontend_f2_expression_v6_input_aligned_attack_source_2026-04-20`
  - `frontend_f2_expression_v6_input_aligned_tokenizer_v1_smoke_2026-04-20` (CPU)
- Key transformer + family_short_focus results:
  - `mi_dir_mean`: `AUC=0.7871`, `calibrated_alarm=0.0136`, `calibrated_det=0.0413`
  - `mi_hphp_short_mean`: `AUC=0.6689`, `calibrated_alarm=0.0047`, `calibrated_det=0.0124`
  - `hphp_mean`: `feasible=True`, `calibrated_det=0.0000`
- Conclusion:
  - This v6 formulation reduced alarm but caused a severe detection collapse for the target transformer scorers.
  - As currently defined, `v6_input_aligned_v1` is a negative result relative to both `v3 fix3` and `v5_compact_v1`.
  - Next step should avoid this aggressive short-token collapse and move to a milder `v6.1` (retain `20x8` geometry while applying alignment only on channel semantics).
