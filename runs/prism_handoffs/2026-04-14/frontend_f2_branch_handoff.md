# Frontend-F2 Branch Handoff

## 1. 这条分支是干什么的

- 分支名：`codex/frontend-f2`
- 目录：`worktrees/kitnet-frontend-f2`
- 目标：为 stronger-OOD 异常检测项目探索“前端表达重构”路线，而不是继续只在旧 `100D` 平面表示上做后端修补。

## 2. 它和主线什么关系

- 主线分支：`codex/exp-mainline`
- 主线职责：维护论文主叙事、稳定 strongest candidate、保留已验证主实验代码。
- `frontend-f2` 职责：高风险前端重构支线。
- 原则：本支线可以失败，但不能污染主线；只有明确有效的前端表达与结论才考虑回收。

## 3. 按时间顺序的稳定节点

### 2026-04-13：F2 结构化缓存链打通

- 已完成真实数据的 Frontend-F2 结构化缓存抽取：
  - ID：`7-6`
  - OOD benign：`4-1`
  - attack：`34-1`
- 结构化缓存保持对 old `100D` 的严格可逆展开：
  - `family_scale_tokens [N,4,5,7]`
  - `token_matrix [N,20,7]`
  - schema / token 映射元数据
- 这一步证明 F2 可以从真实 TSV source 重新提取，而不只是消费历史 cache。

### 2026-04-13 到 2026-04-14：下游 token 重排线已跑过两轮

- `repo/ood/frontend_f2_structured_tokenizer_v1.py`
  - 最佳 fixed 点大约为 `alarm 0.012 / det 0.20`
  - 结论：真实结构化前端链路可运行，但“同一 100D 的结构重排”不够。
- `repo/ood/frontend_f2_contrast_tokenizer_v1.py`
  - 最佳 token-MLP 点约 `alarm 0.0719 / det 0.2995`
  - 最佳 transformer 点约 `alarm 0.1328 / det 0.2858`
  - 结论：短时相对长时的异常增量确实带来真实信号，但提升仍不足以挑战主线或 dA。

### 2026-04-14：放弃先做 `contrast_tokenizer_v1_1`，转向 extractor-level expression_v2

- 当前判断：`v1.1` 仍然只是“更高级的 old 100D 重排”，大概率不会根本改变上限。
- 因此支线方向正式改为：**从原始 TSV source 重新提取新的 model-facing frontend expression，而不是继续在现有 structured cache 上小修小补。**

### 2026-04-14：expression_v2 提取协议已实现并落地到真实数据

- 修改了 `repo/ood/kitsune_frontend_original_extract.py`
- 在保留 old `flat100` 和 old structured cache 的同时，新增 extractor-level `expression_v2`：
  - `expression_v2_matrix [N,20,5]`
  - `expression_v2_flat [N,100]`
  - `expression_v2_channel_mask [20,5]`
  - `expression_v2_channel_names`
- 当前 `expression_v2` 的 5 个通道是：
  - `level_mean_slog`
  - `level_rms_slog`
  - `delta_short_mean_slog`
  - `delta_mid_mean_slog`
  - `delta_global_mean_slog`
- 其中 `slog = sign(x) * log1p(abs(x))`，目的是在 extractor 端先做幅值压缩，避免原始槽位动态范围过大。

### 2026-04-14：expression_v2 的真实 source bundle 已打通

- 新提取完成：
  - `runs/frontend_f2_expression_v2_extract_id_7_6_2026-04-14/`
  - `runs/frontend_f2_expression_v2_extract_ood_4_1_2026-04-14/`
  - `runs/frontend_f2_expression_v2_extract_attack_34_1_2026-04-14/`
- 新 source-prep 完成：
  - `runs/frontend_f2_expression_v2_crosscapture_stage1_2026-04-14/`
  - `runs/frontend_f2_expression_v2_attack_source_2026-04-14/`
- 这说明本支线已经具备了“从真实 source 重提取 -> 生成新表达 -> 生成新 source bundle”的完整闭环。

### 2026-04-14：expression_v2 第一轮 tokenizer smoke 已完成

- 新脚本：
  - `repo/ood/frontend_f2_expression_v2_tokenizer_v1.py`
- run：
  - `runs/frontend_f2_expression_v2_tokenizer_v1_smoke_2026-04-14/`
- 结果很差，尚未形成可用 detector：
  - token-MLP 看起来几乎“全报”：
    - 最好 detection 接近 `1.0`
    - 但 OOD alarm 也接近 `0.96 ~ 0.99`
    - AUC 约 `0.49 ~ 0.54`
  - transformer 看起来则是“信息塌掉”：
    - `alarm 0.306 ~ 0.394`
    - `det 0.089 ~ 0.123`
    - AUC 约 `0.18 ~ 0.21`
- 当前结论：**expression_v2-v1 作为 extractor-level 新表达是机械可行的，但当前 `20x5` 通道设计并不是有效的检测表达。**

## 4. 当前最关键的失败点

- 失败点 1：只做 old `100D` 的更复杂重排，收益已经接近上限。
- 失败点 2：第一版 extractor-level `expression_v2` 压缩得过猛，当前 5 通道设计把本该保留的判别结构压坏了。
- 失败点 3：`expression_v2_tokenizer_v1` 的 fixed 结果显示：
  - token-MLP 学到的是“把 benign OOD 和 attack 一起推高”，不是有效分离；
  - transformer 学到的则像是“整体过平”，连攻击响应都被削弱了。

## 5. 当前结论

- 本支线现在已经不再只是做“高级 100D 重排”。
- 我们已经把分支推进到了真正的 extractor-level 新表达实验：
  - 输入来自真实 TSV source
  - 新表达在提取阶段直接生成
  - 新 source bundle 与新 tokenizer smoke 都已跑通
- 但第一个真实新表达 `expression_v2-v1` 已经证明：**“改前端提取表达”这个方向是对的，但当前这套 20x5 通道定义还不对。**

## 6. 下一步最合理的计划

- 暂时不要上超算，不做多 seed，不做 sweep。
- 先在本地做 `expression_v2` 的失败归因，而不是盲开 `v2.1`。
- 下一步最合理的是：
  - 检查 `expression_v2` 5 个通道在 ID / OOD / attack 上的分布和可分性；
  - 检查是哪些 family / scale / channel 在把 benign OOD 和 attack 一起推高；
  - 基于分布再决定 `expression_v2.1` 是否要：
    - 减少均值型压缩，保留更多 raw-slot 结构；
    - 拆分 level 与 contrast 分支，而不是都压成 5 个标量；
    - 对 `HH/HpHp` 与短尺度保留更高分辨率，而不是对 20 个 token 一刀切压缩。

## 7. 当前最重要的文件

- 设计与 handoff：
  - `runs/prism_handoffs/2026-04-13/frontend_f2_controlled_redesign_spec_2026-04-13.md`
  - `runs/prism_handoffs/2026-04-14/frontend_f2_branch_handoff.md`
- extractor / source prep：
  - `repo/ood/kitsune_frontend_original_extract.py`
  - `repo/ood/prepare_frontend_f2_crosscapture_sources.py`
  - `repo/ood/prepare_frontend_f2_attack_source.py`
- 下游实验代码：
  - `repo/ood/frontend_f2_structured_tokenizer_v1.py`
  - `repo/ood/frontend_f2_contrast_tokenizer_v1.py`
  - `repo/ood/frontend_f2_expression_v2_tokenizer_v1.py`
- 当前关键 run：
  - `runs/frontend_f2_expression_v2_crosscapture_stage1_2026-04-14/`
  - `runs/frontend_f2_expression_v2_attack_source_2026-04-14/`
  - `runs/frontend_f2_expression_v2_tokenizer_v1_smoke_2026-04-14/`
