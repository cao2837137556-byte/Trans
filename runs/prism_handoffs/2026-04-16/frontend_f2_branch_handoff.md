# Frontend-F2 Branch Handoff
更新日期：2026-04-16

---

## 1. 这条支线是干什么的

- 分支名：`codex/frontend-f2`
- 目录：`worktrees/kitnet-frontend-f2`
- 目标：为 stronger-OOD 异常检测项目探索"前端表达重构"路线——从原始 TSV 重新提取
  更具判别力的 model-facing 特征，而不是在旧 `100D` 平面表示上继续小修小补。

---

## 2. 它和主线什么关系

- 主线分支：`codex/exp-mainline`
- 主线职责：维护论文主叙事、稳定 strongest candidate、保留已验证主实验代码。
- `frontend-f2` 职责：高风险前端重构支线，探索新表达。
- 原则：本支线可以失败，但不能污染主线；只有明确有效的前端表达才考虑回收。

---

## 3. 按时间顺序的稳定节点

### 2026-04-13：F2 结构化缓存链打通

- 真实数据 ID(`7-6`) / OOD(`4-1`) / attack(`34-1`) 的结构化抽取完成：
  - `family_scale_tokens [N,4,5,7]`、`token_matrix [N,20,7]`、schema / token 映射
- 证明 F2 可以从真实 TSV source 重新提取，而不只是消费历史 cache。

### 2026-04-14：两轮 token 重排实验，确定不够

- `frontend_f2_structured_tokenizer_v1`：最佳 fixed 约 `alarm 0.012 / det 0.20`
- `frontend_f2_contrast_tokenizer_v1`：最佳约 `alarm 0.07 / det 0.30`
- 结论：同一 100D 的高级重排，上限已接近，需从 extractor 端改表达。

### 2026-04-14：expression_v2 提取协议落地

- 修改 `kitsune_frontend_original_extract.py`，保留 old flat100 + structured cache 不变，
  新增 `expression_v2_matrix [N,20,5]`（5 通道：level_mean_slog / level_rms_slog /
  delta_short / delta_mid / delta_global）。
- smoke 结果极差：token-MLP alarm 0.96~0.99，transformer AUC 0.18~0.21，
  结论：5 通道 "过压缩"，把有效判别结构打掉了。

### 2026-04-16：expression_v3 实施 + 调试 + smoke 通过

**实施内容**（对应规格书 Frontend-F2 Expression_v3 实施规格）：

1. `kitsune_frontend_original_extract.py`：
   - 新增 `compute_expression_v3()` 函数
   - 8 通道：`mean_slog / std_slog / dispersion_slog / number_log /
     cov_sign / pcc_slog / burst_ratio / dispersion_delta_slog`
   - 关键修复：`pcc` 和 `dispersion(CV)` 均用 `slog()` 压缩——
     Kitsune 内部 pcc 计算在分母接近零时会产生 max=6.6e7 的爆炸值，
     raw 保留会令 OOD 的 z-score 达到 +14175，模型全报警。
   - `save_structured_cache()` 追加 v3 字段到 npz（向后兼容）。

2. `prepare_frontend_f2_crosscapture_sources.py`：
   - 追加 v3 npy 输出（matrix `[N,20,8]` + flat `[N,160]`）
   - 支持从 npz 读取（新提取）或即时从 `family_scale_tokens` 计算（旧提取兼容）

3. `prepare_frontend_f2_attack_source.py`：同上，对称。

4. `frontend_f2_expression_v3_tokenizer_v1.py`（新）：
   - 双分支 `ExpressionV3TokenEmbedding`：
     - per-token 分支 ch0~ch5（6维）→ Linear(6, d_model)
     - cross-scale 分支 ch6~ch7（2维）→ Linear(2, d_model)
     - 两路加和 + family/scale positional embedding
   - `ExpressionV3TransformerAE` 和 `ExpressionV3TokenMLPAE`
   - channel_mask 全 1（8 通道全有效）

**调试过程**：
- 第一轮 smoke（_2026-04-16，fix 前）：pcc 和 dispersion 未压缩
  → OOD z-score 爆炸 → alarm=1.0，AUC=0.32~0.53，比 v2 更差
- 诊断发现：pcc 在 OOD 最大值 66,397,476；dispersion 在 ID 中位数 101
- 修复：ch2 改为 `slog(CV)`，ch5 改为 `slog(pcc)`，ch7 改为 `slog(disp_short)-slog(disp_long)`
- 第二轮 smoke（fix1）：数值爆炸消除

---

## 4. 当前最重要的 smoke 结果（2026-04-16 fix1）

**run**：`runs/frontend_f2_expression_v3_tokenizer_v1_smoke_2026-04-16_fix1/`

| 模型 | profile | score_mode | OOD alarm | det (high) | AUC |
|---|---|---|---|---|---|
| transformer | family_short_focus | short_scale_mean | 0.969 | 0.988 | **0.743** |
| transformer | family_short_focus | weighted_token_mean | 0.986 | 0.994 | **0.748** |
| transformer | uniform | short_scale_mean | 0.984 | 0.985 | 0.612 |
| token-MLP | family_short_focus | weighted_token_mean | 1.000 | 0.999 | **0.770** |
| token-MLP | uniform | short_scale_mean | 1.000 | 1.000 | 0.758 |

**与 v2 基线对比**：

| 指标 | v2（旧） | v3（fix1） | 目标 | 达标？ |
|---|---|---|---|---|
| transformer AUC | 0.175~0.212 | 0.587~0.748 | >0.60 | ✓ 大幅超越 |
| token-MLP AUC | 0.450~0.544 | 0.642~0.770 | — | 显著提升 |
| transformer det(fixed) | 0.089~0.123 | 0.934~0.988 | >0.25 | ✓（但 alarm 也高） |
| OOD alarm | 0.964~0.993 | 0.969~1.000 | <0.15 | ✗ 仍然偏高 |

---

## 5. 当前最重要的结论

1. **AUC 突破 0.60**：v3 表达有真实的 attack vs OOD 分离能力（最高 0.770），
   v2 完全没有（AUC 0.18~0.21）。这是本支线第一次在真正的判别性上取得进展。

2. **OOD alarm 问题的本质变了**：
   - v2 时：模型把 benign OOD 和 attack 都推高，信号完全混合，AUC≈0.5。
   - v3 时：模型能分开 attack vs OOD（AUC 0.74~0.77），但 OOD 的分数相对 ID 也被推高
     了（score order：ID < OOD_benign < attack）。
   - 意味着：`fixed_id_q99` 阈值策略不适合跨捕获场景；用 ID/OOD 对比校准阈值可能有效。

3. **PCC 的数值爆炸是关键陷阱**：Kitsune frontend 的 pcc slot 在低流量
   family/scale 下会产生数百万级别的数值，必须在 extractor 端 slog 压缩。
   规格书的 "pcc 已在 [-1,1]" 假设在真实数据中不成立。

---

## 6. 已失败的路线

- **old 100D 重排系列**：`structured_tokenizer_v1`、`contrast_tokenizer_v1` —— 上限不够
- **expression_v2（5 通道）**：过度压缩，AUC≈0.18~0.21，已放弃
- **expression_v3 未压缩 pcc/dispersion**：数值爆炸，alarm=1.0，AUC≈0.32~0.53

---

## 7. 下一步计划

**当前 AUC 已突破，但 OOD alarm 依然偏高，需要分析原因。**

### 优先级 1：分析 OOD alarm 的分布结构

- 检查 ID / OOD / attack 的 per-token score 分布（哪些 token 推高了 OOD？）
- 检查是否 benign OOD（cross-capture）的某些 family/scale token 重构误差天然偏高，
  而非 attack 独有。
- 如果 OOD alarm 主要来自 1~2 个特定 family-scale token，可以做 token mask 消除。

### 优先级 2：尝试 OOD 校准阈值（替代 fixed_id_q99）

- 当前 fixed_id_q99 是把 ID 的 q99 当阈值，但 OOD 场景天然有 distribution shift。
- 可以尝试：用 ID 和 OOD 的混合 q95 当阈值，观察 alarm vs det 的 tradeoff。

### 优先级 3（可选）：加 epochs 或调 d_model

- 当前 smoke 只跑 20 epochs + 8000 samples，扩展到 50 epochs / 20000 samples 看 AUC 是否更高。

### 不做的事

- 不开多 seed（AUC 还需进一步优化）
- 不改模型架构（先分析诊断）
- 不 merge 主线

---

## 8. 必看文件和目录

### 代码（`repo/ood/`）

| 文件 | 说明 |
|---|---|
| `kitsune_frontend_original_extract.py` | extractor，含 `compute_expression_v3()` |
| `prepare_frontend_f2_crosscapture_sources.py` | 生成 ID/OOD v3 npy |
| `prepare_frontend_f2_attack_source.py` | 生成 attack v3 npy |
| `frontend_f2_expression_v3_tokenizer_v1.py` | 双分支 embedding + AE（新） |

### 关键 runs（`runs/`）

| 目录 | 内容 |
|---|---|
| `frontend_f2_expression_v3_crosscapture_stage1_2026-04-16/data/` | v3 ID/OOD npy（修复后） |
| `frontend_f2_expression_v3_attack_source_2026-04-16/data/` | v3 attack npy（修复后） |
| `frontend_f2_expression_v3_tokenizer_v1_smoke_2026-04-16_fix1/` | **当前最新 smoke 结果** |

### 历史参考

- `runs/frontend_f2_expression_v2_tokenizer_v1_smoke_2026-04-14/` — v2 基线结果（AUC 0.18~0.21）
- `runs/prism_handoffs/2026-04-14/frontend_f2_branch_handoff.md` — 上一版 handoff

---

## 9. 新对话如何快速接入

1. 确认目录：`worktrees/kitnet-frontend-f2/`，分支 `codex/frontend-f2`
2. 读本 handoff 了解 v3 定义和当前结论
3. 看 `runs/frontend_f2_expression_v3_tokenizer_v1_smoke_2026-04-16_fix1/summary.md` 了解数字
4. 当前最需要做的事：分析 OOD alarm 偏高的 per-token 来源（见第 7 节）
5. 关键约束：**不改 original-frontend flat100 的任何输出逻辑**
