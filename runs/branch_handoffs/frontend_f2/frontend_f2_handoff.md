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

## 20. 2026-04-21 F2.5 Temporal Smoke (causal history predictor)

- Goal:
  - Test whether temporal dynamics can separate attack from benign OOD better than single-frame token reconstruction.
  - Use existing `expression_v3` matrices without re-extraction.
- Implemented independent entry:
  - `repo/ood/frontend_f2_5_temporal_tokenizer.py`
  - Input: causal history window `K=5` from `expression_v3 [20,8]`
  - Target: current frame only; target frame is not included in the model input.
  - Evaluation: same `stage2 manifest + id_budget_calibrated_target1pct` protocol as frontend-f2 tokenizer runs.
- Executed:
  - `runs/frontend_f2_5_temporal_smoke_2026-04-21/`
- Key transformer + family_short_focus results:
  - `mi_dir_mean`: `AUC=0.4216`, `calibrated_alarm=0.0095`, `calibrated_det=0.0028`, `feasible=True`
  - `mi_hphp_short_mean`: `AUC=0.5900`, `calibrated_alarm=0.0099`, `calibrated_det=0.0320`, `feasible=True`
  - `hphp_mean`: `AUC=0.5796`, `calibrated_alarm=0.0085`, `calibrated_det=0.0707`, `feasible=True`
- Best temporal point overall:
  - `uniform + hphp_mean`: `AUC=0.6944`, `calibrated_alarm=0.0098`, `calibrated_det=0.1367`, `feasible=True`
- Conclusion:
  - Temporal causal prediction did not improve the main attack-separation objective.
  - It can satisfy low alarm, but mostly by becoming conservative; detection remains too low.
  - This is not a fast path to surpass DA in its current form.
  - Next practical direction should be explicit `delta/innovation` features rather than a heavier temporal transformer.

## 21. 2026-04-21 F2.6 Innovation Smoke (explicit current-vs-history features)

- Goal:
  - Test whether explicitly encoding current-frame deviation from short history can separate attack from benign OOD.
  - Avoid relying on a temporal transformer to infer the innovation signal implicitly.
- Implemented independent entry:
  - `repo/ood/frontend_f2_6_innovation_tokenizer_v1.py`
  - Input source: existing `expression_v3 [20,8]` matrices.
  - In-memory representation:
    - for each target row `t`, compute rolling history over previous `K=5` rows
    - `innovation = (x_t - mean(x_{t-K:t-1})) / std(x_{t-K:t-1})`
    - clip to `[-8, 8]`
    - output keeps `[20,8]` geometry and uses the standard tokenizer/evaluation protocol
- Executed:
  - `runs/frontend_f2_6_innovation_smoke_2026-04-21/`
- Key transformer + family_short_focus results:
  - `mi_dir_mean`: `AUC=0.4029`, `calibrated_alarm=0.0254`, `calibrated_det=0.0167`, `feasible=False`
  - `mi_hphp_short_mean`: `AUC=0.4034`, `calibrated_alarm=0.0459`, `calibrated_det=0.0004`, `feasible=False`
  - `hphp_mean`: `AUC=0.4195`, `calibrated_alarm=0.0583`, `calibrated_det=0.0092`, `feasible=False`
- Best innovation point overall:
  - `token_mlp + uniform + mi_hphp_mean`: `AUC=0.4951`, `calibrated_alarm=0.1026`, `calibrated_det=0.0881`, `feasible=False`
- Conclusion:
  - Explicit short-history z-score innovation is a negative result.
  - It does not preserve the v3 attack-vs-OOD ranking signal and does not improve low-alarm detection.
  - The frontend-f2 branch now has three recent negative input-alignment attempts:
    - aggressive short-token v6
    - causal temporal predictor
    - explicit innovation tensor
  - Next step should stop local input reshaping and return to either:
    - a stronger supervised/contrastive objective on the existing best v3/v5 representation, or
    - a DA-facing comparison protocol to identify exactly which signal DA has that frontend-f2 is missing.

## 22. 2026-04-21 v7 Source-Rich Diagnostic Ranker (target-aligned probe)

- Motivation:
  - GPT deep diagnosis recommended stopping local frontend formula patches.
  - The next falsification target was whether `source_rich_v1` already contains enough signal if the objective is target-aligned.
- Implemented independent entry:
  - `repo/ood/frontend_f2_v7_source_rich_diagnostic_ranker.py`
  - Input: frozen `source_rich_v1 [20,13]`, flattened to 260 dimensions.
  - Model: L2 `LogisticRegression`, `class_weight=balanced`, `C=1.0`.
  - Labels:
    - negative: ID benign + OOD benign
    - positive: stage2 high-purity attack only
  - Splits:
    - ID: train `[0,8000)`, val `[8000,10000)`, calibration `[10000,15000)`
    - OOD: train `[0,8000)`, val `[8000,10000)`, eval `[10000,20000)`
    - high-purity attack: contiguous split by row index, 60% train / 20% val / 20% eval
- Executed:
  - `runs/frontend_f2_v7_source_rich_ranker_2026-04-21/`
- Main result:
  - `AUC=0.9997`
  - `calibrated_alarm=0.0088`
  - `calibrated_det=0.9942`
  - `selection_feasible=True`
  - fixed ID q99 also strong: `alarm=0.0028`, `det=0.9898`
- Top coefficient signals:
  - `HpHp@0.01s cov_slog_raw`
  - `HpHp@0.01s std_slog_raw`
  - `HpHp@0.1s std_slog_raw`
  - `HH_jit@0.1s cv_slog_raw`
  - `HH_jit@0.01s mean_rel_family`
- Interpretation:
  - This is the first frontend-f2 result that strongly exceeds the prior v3/v5 trade-off under the 1% OOD-alarm protocol.
  - It proves `source_rich_v1` contains target-relevant signal when the learning objective is aligned with “ID/OOD benign vs high-purity attack”.
  - The main bottleneck is now strongly supported as objective mismatch, not lack of frontend information.
  - This is still a supervised diagnostic probe, not the final deployable detector.
- Next recommended direction:
  - Build a v7.1 target-aligned but less directly supervised frontend objective, likely contrastive / PU / DA-aligned, using this ranker result as an oracle-style upper bound.
  - Also preserve row scores and feature importance for DA-vs-frontend comparison:
    - `frontend_f2_v7_source_rich_ranker_row_scores.csv`
    - `frontend_f2_v7_source_rich_ranker_feature_importance.csv`

## 23. 2026-04-21 v7.1 Source-Rich Label-Budget Sweep

- Goal:
  - Test whether the strong v7 diagnostic result depends on thousands of supervised attack labels.
  - Keep the same frozen `source_rich_v1 [20,13]` input, same benign negatives, same held-out OOD/attack eval splits, and vary only the number of high-purity attack positives used for training.
- Implemented independent entry:
  - `repo/ood/frontend_f2_v7_1_source_rich_label_budget_ranker.py`
  - Model: L2 `LogisticRegression`, `class_weight=balanced`, `C=1.0`.
  - Positive budgets: `16, 32, 64, 128, 256, 512, 1024, 2048, all(4122)`.
  - Positive budget sampling: deterministic seeded sampling from the v7 attack-train split only.
  - Eval remains fixed:
    - OOD benign eval: rows `[10000,20000)`
    - high-purity attack eval: held-out contiguous rows `[8417,9791]`
- Executed:
  - `runs/frontend_f2_v7_1_source_rich_label_budget_2026-04-21/`
- Main label-budget results:
  - budget `16`: `AUC=0.9757`, `calibrated_alarm=0.0097`, `calibrated_det=0.9585`, `feasible=True`
  - budget `32`: `AUC=0.9794`, `calibrated_alarm=0.0099`, `calibrated_det=0.9636`, `feasible=True`
  - budget `64`: `AUC=0.9640`, `calibrated_alarm=0.0100`, `calibrated_det=0.9164`, `feasible=True`
  - budget `128`: `AUC=0.9907`, `calibrated_alarm=0.0097`, `calibrated_det=0.9469`, `feasible=True`
  - budget `256`: `AUC=0.9984`, `calibrated_alarm=0.0100`, `calibrated_det=0.9876`, `feasible=True`
  - budget `512`: `AUC=0.9986`, `calibrated_alarm=0.0089`, `calibrated_det=0.9862`, `feasible=True`
  - budget `1024`: `AUC=0.9992`, `calibrated_alarm=0.0077`, `calibrated_det=0.9891`, `feasible=True`
  - budget `2048`: `AUC=0.9994`, `calibrated_alarm=0.0097`, `calibrated_det=0.9913`, `feasible=True`
  - budget `4122`: `AUC=0.9997`, `calibrated_alarm=0.0088`, `calibrated_det=0.9942`, `feasible=True`
- Key conclusion:
  - v7 is not merely a large-label artifact.
  - Even 16 high-purity attack positives are enough to reach `AUC>0.97` and `det>0.95` at <=1% OOD alarm under this split.
  - This strongly supports that `source_rich_v1` contains a sparse, target-relevant signal and the previous frontend-f2 failures were mainly objective/scoring mismatch, not missing frontend information.
- Important caveat:
  - This is still a supervised/target-aligned diagnostic using high-purity attack labels.
  - It should not be presented as the final unsupervised detector.
- Next recommended direction:
  - Promote the line from "diagnostic probe" to a deployable target-aligned detector:
    - keep `source_rich_v1` frozen
    - start from the 16/32/64 positive-label regime
    - add robustness checks against other attack windows/captures if available
    - compare learned top coefficients with DA signals before deciding whether to distill into a compact frontend model or keep the linear ranker as the practical detector head

## 24. 2026-04-22 v7.2 Fairness Validation (no final-OOD threshold leakage)

- Goal:
  - Validate whether the v7/v7.1 signal still holds when final OOD eval is not used for threshold selection.
  - Check whether the 16-shot result was a lucky positive-sample draw by repeating positive sampling across 5 seeds.
- Implemented independent entry:
  - `repo/ood/frontend_f2_v7_2_fairness_validation.py`
  - Input: frozen `source_rich_v1 [20,13]`, flattened to 260 dimensions.
  - Model: L2 `LogisticRegression`, `class_weight=balanced`, `C=1.0`.
  - Negative labels: ID benign train + OOD benign train.
  - Positive labels: high-purity attack train split only.
  - Positive budgets: `16, 32, 64`.
  - Positive sample seeds: `42, 43, 44, 45, 46`.
- Strict split / leakage control:
  - ID:
    - train `[0,8000)`
    - val `[8000,10000)`
    - calibration `[10000,15000)`
    - extra eval unused by threshold `[15000,50000)`
  - OOD:
    - train `[0,8000)`
    - validation/threshold guard `[8000,10000)`
    - final eval only `[10000,20000)`
  - high-purity attack:
    - train pool rows `[2921,7042]` (`4122` rows)
    - val rows `[7043,8416]`
    - final eval rows `[8417,9791]`
  - Final OOD eval is never used for threshold selection.
- Threshold policies:
  - `fixed_id_calib_q99`: threshold from ID calibration q99 only.
  - `guarded_id_calib_and_ood_val_target1pct`: threshold selected using ID calibration + OOD validation only.
- Executed:
  - `runs/frontend_f2_v7_2_fairness_validation_2026-04-22/`
- Aggregate results:
  - `16-shot`, fixed ID q99:
    - `AUC_mean=0.9776`, `AUC_min=0.9646`
    - `OOD_alarm_mean=0.0058`, `OOD_alarm_max=0.0096`
    - `det_mean=0.9488`, `det_min=0.9273`
    - `feasible_rate=1.0`, `all_runs_strong=True`
  - `16-shot`, guarded ID+OOD-val:
    - `AUC_mean=0.9776`, `AUC_min=0.9646`
    - `OOD_alarm_mean=0.0056`, `OOD_alarm_max=0.0088`
    - `det_mean=0.9487`, `det_min=0.9273`
    - `feasible_rate=1.0`, `all_runs_strong=True`
  - `32-shot`, fixed ID q99:
    - `AUC_mean=0.9776`, `AUC_min=0.9682`
    - `OOD_alarm_mean=0.0075`, `OOD_alarm_max=0.0109`
    - `det_mean=0.9587`, `det_min=0.9476`
    - `feasible_rate=0.8`
  - `64-shot`, fixed ID q99:
    - `AUC_mean=0.9837`, `AUC_min=0.9640`
    - `OOD_alarm_mean=0.0104`, `OOD_alarm_max=0.0218`
    - `det_mean=0.9533`, `det_min=0.9251`
    - `feasible_rate=0.6`
- Key conclusion:
  - Under the stricter no-final-OOD-leakage protocol, `16-shot` is still robust across all 5 positive-sample seeds.
  - Minimum all-seed strong budget is `16`.
  - The result is not just threshold leakage and not just one lucky 16-positive draw.
  - More positive samples did not monotonically improve final OOD alarm under the current fixed `C=1.0` linear model; `32/64` keep high det but sometimes exceed the strict 1% final OOD alarm target.
- Current interpretation:
  - This is now a credible few-shot target-aligned detector result, not merely the v7 oracle-style diagnostic.
  - It is still not directly comparable to an unsupervised DA baseline unless DA is evaluated under the same information setting.
- Next recommended direction:
  - Build a formal DA fairness comparison:
    - same train/val/calib/eval splits
    - same positive-label budgets if DA is allowed labels
    - same fixed-ID-q99 and/or guarded validation threshold policies
    - report OOD final alarm and high-purity attack final det
  - In parallel, test one cross-window/cross-capture holdout if another attack/capture source is available; this is the main remaining risk before using v7.2 as a paper-grade result.

## 25. 2026-04-22 v7.3 DA Fairness Comparison + original100 few-shot control

- Goal:
  - Compare the v7.2 source-rich few-shot ranker against DA under the same final OOD/attack split.
  - Add an `original100` few-shot logistic control with the same positive-label budgets/seeds to test whether the gain is source-rich specific or mainly objective/label alignment.
- Implemented independent entry:
  - `repo/ood/frontend_f2_v7_3_da_fairness_comparison.py`
  - Objects compared:
    - `source_rich_v7_2_fewshot_logistic`
    - `original100_fewshot_logistic`
    - `da_unsupervised_score_seed42`
  - Threshold policies:
    - `fixed_id_calib_q99`
    - `guarded_id_calib_and_ood_val_target1pct`
  - Final OOD eval is not used for threshold selection.
- DA handling:
  - DA checkpoint:
    - `KitNET-py-master/runs/frontend100_tailreg_stage1_2026-03-27/da_seed42/kitnet_da_seed42.ckpt`
  - Full ID scores were recomputed from the checkpoint to match the v7.2 ID split:
    - train `[0,8000)`
    - val `[8000,10000)`
    - calibration `[10000,15000)`
    - eval unused by threshold `[15000,50000)`
  - Existing stage1 DA attack scores were reused for attack eval.
- Executed:
  - `runs/frontend_f2_v7_3_da_fairness_comparison_2026-04-22/`
- Focus comparison (`16-shot` vs DA):
  - `DA unsupervised`, fixed ID q99:
    - `AUC=0.8064`
    - `OOD_alarm=0.1286`
    - `det=0.6865`
    - not feasible under <=1% OOD alarm
  - `DA unsupervised`, guarded ID+OOD-val:
    - `AUC=0.8064`
    - `OOD_alarm=0.0108`
    - `det=0.0029`
    - not feasible (`OOD_alarm` slightly >1%, detection collapsed)
  - `source_rich_v7.2 few-shot`, 16 positives, fixed ID q99:
    - `AUC_mean=0.9776`, `AUC_min=0.9646`
    - `OOD_alarm_mean=0.0058`, `OOD_alarm_max=0.0096`
    - `det_mean=0.9488`, `det_min=0.9273`
    - `feasible_rate=1.0`
  - `source_rich_v7.2 few-shot`, 16 positives, guarded:
    - `AUC_mean=0.9776`, `AUC_min=0.9646`
    - `OOD_alarm_mean=0.0056`, `OOD_alarm_max=0.0088`
    - `det_mean=0.9487`, `det_min=0.9273`
    - `feasible_rate=1.0`
  - `original100 few-shot`, 16 positives, fixed ID q99:
    - `AUC_mean=0.9907`, `AUC_min=0.9580`
    - `OOD_alarm_mean=0.0045`, `OOD_alarm_max=0.0095`
    - `det_mean=0.9676`, `det_min=0.9142`
    - `feasible_rate=1.0`
  - `original100 few-shot`, 16 positives, guarded:
    - `AUC_mean=0.9907`, `AUC_min=0.9580`
    - `OOD_alarm_mean=0.0044`, `OOD_alarm_max=0.0092`
    - `det_mean=0.9676`, `det_min=0.9142`
    - `feasible_rate=1.0`
- Full original100 few-shot control:
  - `16-shot`: strongest clean point; all seeds feasible.
  - `32-shot`: still all seeds feasible, `det_mean=0.9407`, `OOD_alarm_max=0.0098`.
  - `64-shot`: higher `AUC/det`, but some seeds exceed 1% final OOD alarm (`feasible_rate=0.8`).
- Key conclusion:
  - Against unsupervised DA at the same final split, both few-shot logistic detectors are dramatically better in the low-OOD-alarm operating region.
  - However, the original 100D few-shot control is at least as strong as source-rich v7.2 in this protocol.
  - Therefore the current breakthrough should be attributed primarily to target-aligned few-shot supervision/objective alignment, not uniquely to `source_rich_v1`.
- Updated interpretation boundary:
  - It is fair to say: "few-shot target-aligned linear detectors beat unsupervised DA under the same final split and low-OOD-alarm protocol."
  - It is not yet fair to say: "`source_rich_v1` alone is the reason for beating DA."
  - If the paper claims frontend re-extraction value, it must either:
    - show cross-capture/cross-window robustness where source-rich wins, or
    - position source-rich as an interpretable/auditable representation rather than the sole source of performance.
- Next recommended direction:
  - Run a cross-window holdout / alternate attack segment validation for both `source_rich_v7.2` and `original100_fewshot_logistic`.
  - If original100 remains stronger, the most pragmatic path is to promote the method as "few-shot target-aligned frontend detector" and keep source-rich as the diagnostic/explainability layer.

## 26. 2026-04-22 v7.4 Paired Holdout Fairness Package

- Goal:
  - Decide whether the v7 few-shot strength survives stricter attack-window holdouts.
  - Decide whether `source_rich_v1` has a performance advantage over `original100`, under paired fairness controls.
  - Keep the branch scope fixed on few-shot / target-aligned detector validation; do not resume v4/v5/v6 frontend patching.
- Implemented independent entry:
  - `repo/ood/frontend_f2_v7_4_paired_holdout_fairness.py`
  - Compared objects:
    - `source_rich_fewshot_logistic` using `source_rich_v1_flat260`
    - `original100_fewshot_logistic` using original frontend flat100
  - Positive budgets:
    - `16`
    - `32`
  - Positive sample seeds:
    - `42,43,44,45,46`
  - Threshold policies:
    - `fixed_id_calib_q99`
    - `guarded_id_calib_and_ood_val_target1pct`
  - Final OOD eval is never used for threshold selection.
- Paired fairness protocol:
  - Same negative train split for both representations.
  - Same positive holdout train/eval attack windows.
  - Same label budgets and seed set.
  - Same threshold policy and final OOD eval.
  - Same low-OOD-alarm operating-region feasibility check.
- Holdout design:
  - Leave-one-attack-window-out:
    - held-out attack bins `2,3,4,5,6,7,8`
  - Chronological cross-window:
    - `chrono_early_train_late_eval`: train bins `2,3,4`, eval bins `6,7,8`
    - `chrono_late_train_early_eval`: train bins `6,7,8`, eval bins `2,3,4`
  - Attack eval counts:
    - bin2: `1348`
    - bin3: `958`
    - bin4: `1120`
    - bin5: `877`
    - bin6: `1001`
    - bin7: `1141`
    - bin8: `426`
    - early-to-late eval: `2568`
    - late-to-early eval: `3426`
- Executed:
  - `runs/frontend_f2_v7_4_paired_holdout_fairness_2026-04-22/`
  - Key outputs:
    - `summary.md`
    - `frontend_f2_v7_4_paired_holdout_results.csv`
    - `frontend_f2_v7_4_paired_holdout_summary.csv`
    - `frontend_f2_v7_4_paired_holdout_deltas.csv`
    - `frontend_f2_v7_4_decision_per_model.csv`
    - `frontend_f2_v7_4_decision_win_counts.csv`
- Aggregate decision table:
  - `source_rich`, 16-shot, fixed ID q99:
    - strong holdouts `2/9`
    - `feasible_rate_mean=0.8000`
    - `det_min_global=0.7144`
    - `alarm_max_global=0.0291`
    - `auc_min_global=0.8490`
  - `source_rich`, 16-shot, guarded:
    - strong holdouts `4/9`
    - `feasible_rate_mean=0.8889`
    - `det_min_global=0.7129`
    - `alarm_max_global=0.0111`
    - `auc_min_global=0.8490`
  - `source_rich`, 32-shot, fixed ID q99:
    - strong holdouts `4/9`
    - `feasible_rate_mean=0.8000`
    - `det_min_global=0.7611`
    - `alarm_max_global=0.0258`
    - `auc_min_global=0.9079`
  - `source_rich`, 32-shot, guarded:
    - strong holdouts `4/9`
    - `feasible_rate_mean=0.8444`
    - `det_min_global=0.7530`
    - `alarm_max_global=0.0123`
    - `auc_min_global=0.9079`
  - `original100`, 16-shot, fixed ID q99:
    - strong holdouts `3/9`
    - `feasible_rate_mean=0.8889`
    - `det_min_global=0.1736`
    - `alarm_max_global=0.0188`
    - `auc_min_global=0.2404`
  - `original100`, 16-shot, guarded:
    - strong holdouts `3/9`
    - `feasible_rate_mean=0.8889`
    - `det_min_global=0.1736`
    - `alarm_max_global=0.0188`
    - `auc_min_global=0.2404`
  - `original100`, 32-shot, fixed ID q99:
    - strong holdouts `1/9`
    - `feasible_rate_mean=0.7556`
    - `det_min_global=0.2329`
    - `alarm_max_global=0.0258`
    - `auc_min_global=0.3158`
  - `original100`, 32-shot, guarded:
    - strong holdouts `1/9`
    - `feasible_rate_mean=0.7556`
    - `det_min_global=0.2329`
    - `alarm_max_global=0.0257`
    - `auc_min_global=0.3158`
- Paired winner counts by `det_mean`:
  - For every budget/policy pair, `original100` wins `7/9` holdouts and `source_rich` wins `2/9` holdouts.
  - This means `source_rich` is not an average-performance winner in v7.4.
- Critical hard-holdout findings:
  - `holdout_bin_2`, 16-shot fixed q99:
    - `original100`: `AUC_min=0.2404`, `det_min=0.1736`, `det_mean=0.2838`, `alarm_max=0.0029`
    - `source_rich`: `AUC_min=0.8490`, `det_min=0.7144`, `det_mean=0.8598`, `alarm_max=0.0166`
    - Interpretation: original100 collapses on this alternate attack segment; source_rich preserves useful detection but sometimes exceeds the 1% alarm target.
  - `chrono_late_train_early_eval`, 16-shot fixed q99:
    - `original100`: `AUC_min=0.7007`, `det_min=0.6754`, `det_mean=0.7112`, `alarm_max=0.0058`
    - `source_rich`: `AUC_min=0.9436`, `det_min=0.8678`, `det_mean=0.9167`, `alarm_max=0.0202`
    - Interpretation: source_rich is materially more robust under late-window positive training and early-window attack eval, but alarm calibration still needs tightening.
  - `chrono_early_train_late_eval`, 16-shot fixed q99:
    - `original100`: `AUC_min=0.9742`, `det_min=0.9178`, `det_mean=0.9678`, `alarm_max=0.0188`
    - `source_rich`: `AUC_min=0.9705`, `det_min=0.9034`, `det_mean=0.9533`, `alarm_max=0.0158`
    - Interpretation: both remain high-detection, but neither is strictly all-seed strong because some seeds exceed the 1% final OOD alarm target.
- Main conclusions:
  - The v7 few-shot / target-aligned detector discovery remains real, but the v7.2/v7.3 current-split result was optimistic.
  - Under stricter paired attack-window holdout, few-shot is not uniformly stable across all windows and seeds.
  - `original100` is a mandatory control: it wins most holdouts by mean detection and cannot be ignored.
  - `source_rich_v1` does not currently justify a broad "source-rich beats original100" performance claim.
  - The defensible `source_rich` value boundary is:
    - better robustness on specific hard holdouts where original100 collapses,
    - more auditable/diagnosable representation,
    - not universal average-performance superiority.
- Updated branch-level interpretation:
  - `v7` must be called a few-shot / supervised target-aligned detector, not an unsupervised detector.
  - It is fair to say: "few-shot target-aligned detectors beat unsupervised DA on the current final split under low-OOD-alarm protocol."
  - It is not fair to say: "`source_rich_v1` alone caused the DA win."
  - It is not yet paper-safe to claim cross-window stable dominance without additional threshold/alarm robustness work.
- Current answer to the branch裁决:
  - Q1: few-shot under stricter holdout remains useful but not uniformly stable.
  - Q2: source_rich value is mainly robustness/auditability, with targeted gains on hard windows, not average performance dominance.
  - Q3: frontend-f2 should be repositioned as the few-shot target-aligned detector line; source_rich should remain the diagnostic/robust representation component, not the sole performance source.
- Next recommended direction:
  - Do not return to v4/v5/v6 expression patching.
  - If continuing v7, focus on robust operating-region calibration:
    - tighten source_rich OOD alarm on hard holdouts,
    - report paired original100/source_rich under the same cross-window protocol,
    - define the paper claim around few-shot target alignment first and source-rich robustness second.

## 27. 2026-04-24 v7.4 Verification + Hard-Holdout Case Analysis

- Goal:
  - Re-verify whether v7.4 is truly paired/fair at the protocol level.
  - Decide whether `source_rich` can now be formally used as hard-holdout robustness evidence, or only as auditability evidence.
  - Keep scope fixed on verification and case analysis only; no new model, no new frontend patching, no new experiment line.
- Paired integrity re-check:
  - Re-checked script:
    - `repo/ood/frontend_f2_v7_4_paired_holdout_fairness.py`
  - Re-checked run package:
    - `runs/frontend_f2_v7_4_paired_holdout_fairness_2026-04-22/`
  - Verified paired conditions:
    - same holdout spec set: `9` holdouts
    - same label budgets: `16`, `32`
    - same positive sample seed set: `42,43,44,45,46`
    - same threshold policies:
      - `fixed_id_calib_q99`
      - `guarded_id_calib_and_ood_val_target1pct`
    - same negative train split:
      - ID benign train `[0,8000)`
      - OOD benign train `[0,8000)`
      - ID calibration `[10000,15000)`
      - OOD validation `[8000,10000)`
      - final OOD eval `[10000,20000)`
    - same positive holdout train/eval windows per holdout spec
    - final OOD eval is not used for threshold selection
  - Integrity verdict:
    - v7.4 is a valid paired fairness package.
- Holdout-level comparison output:
  - Full fixed + guarded holdout table remains in:
    - `runs/frontend_f2_v7_4_paired_holdout_fairness_2026-04-22/frontend_f2_v7_4_paired_holdout_summary.csv`
  - Deployment-focus guarded table:

| holdout_name | model_label | positive_budget | auc_mean | auc_min | eval_alarm_mean | eval_alarm_max | det_mean | det_min | feasible_rate |
|---|---|---|---|---|---|---|---|---|---|
| chrono_early_train_late_eval | original100 | 16 | 0.9933 | 0.9742 | 0.0056 | 0.0188 | 0.9678 | 0.9178 | 0.8000 |
| chrono_early_train_late_eval | source_rich | 16 | 0.9826 | 0.9705 | 0.0055 | 0.0078 | 0.9516 | 0.9034 | 1.0000 |
| chrono_early_train_late_eval | original100 | 32 | 0.9866 | 0.9656 | 0.0124 | 0.0257 | 0.9613 | 0.9361 | 0.4000 |
| chrono_early_train_late_eval | source_rich | 32 | 0.9806 | 0.9756 | 0.0070 | 0.0109 | 0.9589 | 0.9525 | 0.8000 |
| chrono_late_train_early_eval | original100 | 16 | 0.7376 | 0.7007 | 0.0028 | 0.0058 | 0.7112 | 0.6754 | 1.0000 |
| chrono_late_train_early_eval | source_rich | 16 | 0.9616 | 0.9436 | 0.0097 | 0.0111 | 0.9132 | 0.8514 | 0.6000 |
| chrono_late_train_early_eval | original100 | 32 | 0.7178 | 0.7030 | 0.0023 | 0.0029 | 0.6913 | 0.6824 | 1.0000 |
| chrono_late_train_early_eval | source_rich | 32 | 0.9644 | 0.9494 | 0.0071 | 0.0099 | 0.8966 | 0.8549 | 1.0000 |
| holdout_bin_2 | original100 | 16 | 0.3450 | 0.2404 | 0.0022 | 0.0029 | 0.2838 | 0.1736 | 1.0000 |
| holdout_bin_2 | source_rich | 16 | 0.9342 | 0.8490 | 0.0071 | 0.0109 | 0.8586 | 0.7129 | 0.8000 |
| holdout_bin_2 | original100 | 32 | 0.3971 | 0.3158 | 0.0022 | 0.0035 | 0.3231 | 0.2329 | 1.0000 |
| holdout_bin_2 | source_rich | 32 | 0.9631 | 0.9079 | 0.0090 | 0.0123 | 0.8680 | 0.7530 | 0.6000 |
| holdout_bin_3 | original100 | 16 | 0.9969 | 0.9856 | 0.0056 | 0.0114 | 0.9923 | 0.9676 | 0.6000 |
| holdout_bin_3 | source_rich | 16 | 0.9586 | 0.9369 | 0.0063 | 0.0083 | 0.9232 | 0.8539 | 1.0000 |
| holdout_bin_3 | original100 | 32 | 0.9917 | 0.9727 | 0.0092 | 0.0189 | 0.9745 | 0.9478 | 0.4000 |
| holdout_bin_3 | source_rich | 32 | 0.9815 | 0.9711 | 0.0060 | 0.0091 | 0.9363 | 0.9175 | 1.0000 |
| holdout_bin_4 | original100 | 16 | 0.9993 | 0.9981 | 0.0028 | 0.0034 | 0.9936 | 0.9759 | 1.0000 |
| holdout_bin_4 | source_rich | 16 | 0.9873 | 0.9812 | 0.0074 | 0.0111 | 0.9718 | 0.9616 | 0.8000 |
| holdout_bin_4 | original100 | 32 | 0.9999 | 0.9997 | 0.0069 | 0.0132 | 0.9998 | 0.9991 | 0.8000 |
| holdout_bin_4 | source_rich | 32 | 0.9903 | 0.9893 | 0.0060 | 0.0106 | 0.9738 | 0.9696 | 0.6000 |
| holdout_bin_5 | original100 | 16 | 0.9970 | 0.9905 | 0.0042 | 0.0102 | 0.9906 | 0.9761 | 0.8000 |
| holdout_bin_5 | source_rich | 16 | 0.9747 | 0.9682 | 0.0072 | 0.0096 | 0.9293 | 0.8985 | 1.0000 |
| holdout_bin_5 | original100 | 32 | 0.9961 | 0.9876 | 0.0039 | 0.0095 | 0.9893 | 0.9692 | 1.0000 |
| holdout_bin_5 | source_rich | 32 | 0.9901 | 0.9869 | 0.0067 | 0.0120 | 0.9555 | 0.9316 | 0.6000 |
| holdout_bin_6 | original100 | 16 | 0.9989 | 0.9976 | 0.0050 | 0.0114 | 0.9954 | 0.9810 | 0.8000 |
| holdout_bin_6 | source_rich | 16 | 0.9880 | 0.9778 | 0.0069 | 0.0110 | 0.9594 | 0.9111 | 0.8000 |
| holdout_bin_6 | original100 | 32 | 0.9970 | 0.9926 | 0.0071 | 0.0118 | 0.9854 | 0.9650 | 0.8000 |
| holdout_bin_6 | source_rich | 32 | 0.9913 | 0.9812 | 0.0062 | 0.0096 | 0.9786 | 0.9650 | 1.0000 |
| holdout_bin_7 | original100 | 16 | 0.9989 | 0.9977 | 0.0033 | 0.0049 | 0.9958 | 0.9930 | 1.0000 |
| holdout_bin_7 | source_rich | 16 | 0.9881 | 0.9810 | 0.0060 | 0.0067 | 0.9741 | 0.9641 | 1.0000 |
| holdout_bin_7 | original100 | 32 | 0.9958 | 0.9851 | 0.0103 | 0.0191 | 0.9911 | 0.9728 | 0.6000 |
| holdout_bin_7 | source_rich | 32 | 0.9915 | 0.9783 | 0.0038 | 0.0062 | 0.9756 | 0.9667 | 1.0000 |
| holdout_bin_8 | original100 | 16 | 0.9892 | 0.9541 | 0.0041 | 0.0074 | 0.9357 | 0.8146 | 1.0000 |
| holdout_bin_8 | source_rich | 16 | 0.9637 | 0.9505 | 0.0057 | 0.0081 | 0.9141 | 0.8850 | 1.0000 |
| holdout_bin_8 | original100 | 32 | 0.9724 | 0.8938 | 0.0073 | 0.0127 | 0.9160 | 0.7676 | 0.8000 |
| holdout_bin_8 | source_rich | 32 | 0.9618 | 0.9560 | 0.0058 | 0.0091 | 0.8995 | 0.8404 | 1.0000 |

- Hard-holdout cases retained for paper-facing interpretation:
  - Case 1: `holdout_bin_2`, 16-shot, guarded
    - `original100` collapse:
      - `AUC_mean/min = 0.3450 / 0.2404`
      - `det_mean/min = 0.2838 / 0.1736`
      - `alarm_max = 0.0029`
      - mean attack-vs-OOD score gap is strongly negative across seeds (`mean gap ~ -21.09`)
      - attack median is far below the selected threshold (`median - threshold ~ -24.35`)
      - interpretation: original100 keeps alarm low by pushing this held-out attack window into the benign side; this is a true held-out segment collapse, not a threshold leak.
    - `source_rich` stronger signal:
      - `AUC_mean/min = 0.9342 / 0.8490`
      - `det_mean/min = 0.8586 / 0.7129`
      - `alarm_max = 0.0109`, `feasible_rate = 0.8`
      - top family contributions:
        - `HH_jit`
        - `MI_dir`
        - `HH`
      - top scale contributions:
        - `0.01s`
        - `3s`
        - `5s`
      - top feature channels:
        - `logw_centered_family`
        - `logw_raw`
        - `mean_slog_raw`
        - `std_slog_raw`
        - `cv_short_long_ratio`
      - top family-scale tokens:
        - `HH_jit@0.01s`
        - `MI_dir@0.01s`
        - `HH_jit@1s`
        - `HH_jit@3s`
      - alarm judgment:
        - close to the `<=1%` target, but not fully all-seed stable.
  - Case 2: `holdout_bin_2`, 32-shot, guarded
    - `original100` collapse:
      - `AUC_mean/min = 0.3971 / 0.3158`
      - `det_mean/min = 0.3231 / 0.2329`
      - `alarm_max = 0.0035`
      - mean attack-vs-OOD score gap stays negative (`mean gap ~ -14.40`)
      - attack median still remains below threshold (`median - threshold ~ -15.01`)
      - interpretation: more positives do not rescue the segment mismatch for original100 on bin 2.
    - `source_rich` stronger signal:
      - `AUC_mean/min = 0.9631 / 0.9079`
      - `det_mean/min = 0.8680 / 0.7530`
      - `alarm_max = 0.0123`, `feasible_rate = 0.6`
      - top family contributions:
        - `HH_jit`
        - `MI_dir`
        - `HH`
      - top scale contributions:
        - `0.01s`
        - `3s`
        - `5s`
      - top feature channels:
        - `logw_centered_family`
        - `logw_raw`
        - `std_slog_raw`
        - `cv_short_long_ratio`
        - `mean_rel_family`
      - alarm judgment:
        - still only near-target, not stable enough to claim full low-OOD-alarm closure.
  - Case 3: `chrono_late_train_early_eval`, 32-shot, guarded
    - `original100` degradation:
      - `AUC_mean/min = 0.7178 / 0.7030`
      - `det_mean/min = 0.6913 / 0.6824`
      - `alarm_max = 0.0029`
      - attack median is above threshold, but attack lower tail is still far below threshold (`q10 - threshold ~ -53.13`)
      - interpretation: original100 does not fully collapse to zero here, but it leaves a large miss-prone attack tail under reverse chronology.
    - `source_rich` stronger signal:
      - `AUC_mean/min = 0.9644 / 0.9494`
      - `det_mean/min = 0.8966 / 0.8549`
      - `alarm_max = 0.0099`, `feasible_rate = 1.0`
      - top family contributions:
        - `MI_dir`
        - `HH`
        - `HH_jit`
      - top scale contributions:
        - `0.01s`
        - `3s`
        - `1s`
      - top feature channels:
        - `logw_centered_family`
        - `cv_short_long_ratio`
        - `logw_raw`
        - `mean_rel_family`
        - `cv_slog_raw`
      - top family-scale tokens:
        - `MI_dir@0.01s`
        - `HH@0.01s`
        - `HH_jit@0.1s`
        - `HH@1s`
      - alarm judgment:
        - satisfies the guarded low-OOD-alarm target at the aggregate holdout level (`alarm_max = 0.0099`).
- Formal verdict:
  - `source_rich_hard_holdout_robustness_supported`
- Boundary of that verdict:
  - The support is narrow and case-based, not an average-performance win.
  - `source_rich` is still not a broad mean-detection winner in v7.4; `original100` wins `7/9` holdouts by `det_mean`.
  - The defensible claim is:
    - source_rich has real value on specific hard holdouts where original100 collapses or develops a large miss-prone tail,
    - and source_rich is also the more auditable representation.
  - The non-defensible claim remains:
    - `source_rich` average performance is全面优于 `original100`.
- Updated branch-level interpretation:
  - `v7` remains a few-shot / supervised target-aligned detector line.
  - `original100` remains the mandatory performance control.
  - `source_rich` can now be written as:
    - hard-holdout robustness support on specific paired holdouts
    - auditability / family-scale-feature diagnosis layer
  - `source_rich` cannot be written as universal cross-window performance winner.
