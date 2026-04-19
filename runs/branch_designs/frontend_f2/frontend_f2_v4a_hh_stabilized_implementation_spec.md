# Frontend-F2 v4a HH Stabilized Implementation Spec

日期：2026-04-17
适用支线：`codex/frontend-f2`
状态：待实现

## 0. 2026-04-19 实现备注

- 当前代码实现已按 `runs/gemini_designs/expression_v4a_design_2026-04-17.md` 的 **Hard Masking** 方案落地。
- 也就是说，实际采用的 `compute_expression_v4a_hh_stabilized(...)` 不是 family-relative normalization。
- 当前工程执行、run-tag、文件命名与 PowerShell 命令规范仍以本文件第 10 节为准。

## 1. 目标

`v4a_hh_stabilized` 的目标是只修改 `HH / HH_jit` 两个 family 的 extractor-side expression，
把它们从容易受 capture-level 绝对值漂移影响的表达，改成更强调跨尺度相对形状的表达。

这版实验不追求大改模型，而是要回答一个更具体的问题：

- 在保持 `20 x 8` token 几何不变的前提下，
- 如果仅把 `HH / HH_jit` 的 8 个 channel 改成更稳健的相对特征，
- 是否可以明显压低 benign OOD alarm，
- 同时保住 `MI_dir / HpHp` 的 attack 区分能力。

## 2. 控制变量

- 不改 token 数量：仍为 `20 = 4 families x 5 scales`
- 不改 token 顺序：仍为 row-major，family 外层，scale 内层
- 不改 tokenizer 主体结构
- 不改 score mode 定义
- 不改 `MI_dir / HpHp` 的 extractor 公式
- 不开多 seed
- 不上超算

## 3. v4a 的核心策略

`v3` 当前主要问题不是完全没有 attack 信号，而是：

- `HH / HH_jit` 对 benign OOD 过敏
- 这两类 family 在 cross-capture 场景中更容易被绝对 level、count、cov/pcc 偏移抬高
- 导致 calibrated alarm 很难进一步压低

因此，`v4a_hh_stabilized` 采用如下策略：

- 对 `HH / HH_jit`：
  - 淡化绝对 level
  - 强化 family 内部相对强弱
  - 强化 dispersion / shape
  - 强化短长尺度比值
  - 对 covariance / pcc 做 family 内中心化或归一化
- 对 `MI_dir / HpHp`：
  - 100% 保持 `v3` 公式不动

## 4. family 范围

- family `0 = MI_dir`：完全保持 `v3`
- family `1 = HH`：使用 `v4a_hh_stabilized`
- family `2 = HH_jit`：使用 `v4a_hh_stabilized`
- family `3 = HpHp`：完全保持 `v3`

这意味着本次实验的结论会非常干净：

- 如果结果变好，基本可以归因于 `HH / HH_jit` 的表达被稳健化
- 如果结果没有改善，则说明仅靠 HH 系列稳健化还不够

## 5. 当前 v3 的 8 个 channel

当前 `expression_v3` 在 [kitsune_frontend_original_extract.py](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/repo/ood/kitsune_frontend_original_extract.py) 中的 8 个 channel 为：

- `ch0 = mean_slog`
- `ch1 = std_slog`
- `ch2 = dispersion_slog`
- `ch3 = number_log`
- `ch4 = cov_sign`
- `ch5 = pcc_slog`
- `ch6 = burst_ratio`
- `ch7 = dispersion_delta_slog`

其中 `ch6 / ch7` 为 family 级别跨尺度特征，再广播到该 family 的 5 个 scale token。

## 6. v4a 对 HH / HH_jit 的具体 channel 改法

记号约定：

- `w_s`: weight / count
- `m_s`: mean
- `sd_s`: std
- `cov_s`: covariance
- `p_s`: pcc
- `cv_s = sd_s / (|m_s| + eps)`
- `eps = 1e-6`
- `slog(x) = sign(x) * log1p(|x|)`

对每个 family 再定义 family 内跨尺度参考量：

- `mean_abs_ref = mean_s(|m_s|)`
- `std_ref = mean_s(sd_s)`
- `logw_ref = mean_s(log1p(max(w_s, 0)))`
- `pcc_ref = mean_s(slog(p_s))`

说明：

- `s` 在 5 个时间尺度上取值：`5s / 3s / 1s / 0.1s / 0.01s`
- 下表中的“新定义”只对 `HH / HH_jit` 生效
- `MI_dir / HpHp` 继续沿用原 `v3` 定义

| Channel | v3 定义 | v4a 在 HH / HH_jit 上的新定义 | 设计意图 |
|---|---|---|---|
| `ch0` | `slog(m_s)` | `slog(m_s / (mean_abs_ref + eps))` | 去掉绝对 mean 量级，保留 family 内相对强弱 |
| `ch1` | `slog(sd_s)` | `slog(sd_s / (std_ref + eps))` | 去掉绝对波动量级，改看相对 spread |
| `ch2` | `slog(cv_s)` | 保持不变 | 这是相对特征，本身就是我们想保留的 shape 信号 |
| `ch3` | `log1p(max(w_s,0))` | `log1p(max(w_s,0)) - logw_ref` | count 改为 family 内中心化的尺度活跃度 |
| `ch4` | `slog(cov_s)` | `slog(cov_s / (sd_s * sd_s + eps))` | covariance 改成无量纲相对强度，降低 capture 规模偏移 |
| `ch5` | `slog(p_s)` | `slog(p_s) - pcc_ref` | pcc 改为 family 内中心化相关性偏离 |
| `ch6` | `slog(m_0.01) / (|slog(m_5)| + eps)` | `log((|m_0.01| + eps) / (|m_5| + eps))` 后 broadcast | 直接编码短时与长时 level 对比，强调跨尺度形状 |
| `ch7` | `slog(cv_0.01) - slog(cv_5)` | `log((cv_0.01 + eps) / (cv_5 + eps))` 后 broadcast | 直接编码短长尺度 dispersion 比值 |

## 7. 为什么这样改

这次设计的核心判断是：

- `HH / HH_jit` 的问题主要不是“没有信息”
- 而是这些 family 更容易把 benign cross-capture shift 映射成大 reconstruction error

因此，最合理的第一步不是直接删掉 `HH / HH_jit`，而是把它们从绝对值表达改成：

- family 内相对强度
- family 内中心化偏离
- 短长尺度比值
- dispersion 主导的 shape 特征

这样做的预期效果是：

- benign OOD 在 `HH / HH_jit` 上的过大尾部应被压缩
- per-token diagnostic 中的 tail overlap 应下降
- `mi_dir_mean / mi_hphp_short_mean` 的 calibrated alarm 应低于当前 `v3`

## 8. MI_dir / HpHp 是否保持不动

是，`MI_dir / HpHp` 在本次 `v4a_hh_stabilized` 中保持 100% 不动。

具体含义：

- family `0` 和 family `3` 继续使用现有 `compute_expression_v3()` 的原公式
- 只对 family `1 / 2` 做条件分支替换
- tokenizer 输入 shape、token 布局、训练流程不变

## 9. 实现方式

建议实现方式如下：

1. 在 [kitsune_frontend_original_extract.py](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/repo/ood/kitsune_frontend_original_extract.py) 中新增：
   - `compute_expression_v4a_hh_stabilized(family_scale_tokens)`
   - `EXPRESSION_V4A_HH_STABILIZED_CHANNEL_NAMES`

2. 实现逻辑：
   - 先按 `v3` 方式取出 `num / mean / std / cov / pcc`
   - 先生成一份完整 `v3` 矩阵作为默认值
   - 再只覆盖 family `1 / 2` 的 8 个 channel

3. 在 source prep 脚本中增加：
   - `--expression-version`
   - 支持 `v3`
   - 支持 `v4a_hh_stabilized`

4. 输出文件命名：
   - `id_source_expression_v4a_hh_stabilized_matrix.npy`
   - `ood_benign_source_expression_v4a_hh_stabilized_matrix.npy`
   - `attack_source_expression_v4a_hh_stabilized_matrix.npy`
   - 以及对应 `*_160.npy`

5. 新建独立 smoke 脚本：
   - `repo/ood/frontend_f2_expression_v4a_tokenizer_v1.py`

理由：

- 避免把 `v3` 实验脚本先改成复杂的多版本框架
- 让这条支线的 `v4a` 实验边界更清晰
- 失败时更容易回滚和归档

## 10. 本地 Smoke 命令

以下命令基于当前这条支线已有的真实 structured source：

- ID: `7-6`
- OOD benign: `4-1`
- attack: `34-1`

### 10.1 生成 cross-capture v4a source

```powershell
python repo/ood/prepare_frontend_f2_crosscapture_sources.py `
  --run-tag frontend_f2_expression_v4a_crosscapture_stage1_2026-04-17 `
  --expression-version v4a_hh_stabilized `
  --id-structured-npz runs/frontend_f2_expression_v2_extract_id_7_6_2026-04-14/iot23_7_6_first50000_features_first50000_structured.npz `
  --ood-structured-npz runs/frontend_f2_expression_v2_extract_ood_4_1_2026-04-14/iot23_4_1_first20000_features_first20000_structured.npz `
  --schema-json runs/frontend_f2_expression_v2_extract_id_7_6_2026-04-14/iot23_7_6_first50000_features_first50000_structured_schema.json `
  --id-max-rows 50000 `
  --ood-max-rows 20000
```

### 10.2 生成 attack v4a source

```powershell
python repo/ood/prepare_frontend_f2_attack_source.py `
  --run-tag frontend_f2_expression_v4a_attack_source_2026-04-17 `
  --expression-version v4a_hh_stabilized `
  --attack-structured-npz runs/frontend_f2_expression_v2_extract_attack_34_1_2026-04-14/iot23_34_1_malicious_first30000_features_first10000_structured.npz `
  --attack-manifest-stage2 D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_joint_eval_stage2_2026-04-01\attack_manifest_stage2.json
```

### 10.3 跑 v4a tokenizer smoke

建议新建独立脚本：

- `repo/ood/frontend_f2_expression_v4a_tokenizer_v1.py`

命令如下：

```powershell
python repo/ood/frontend_f2_expression_v4a_tokenizer_v1.py `
  --run-tag frontend_f2_expression_v4a_tokenizer_v1_smoke_2026-04-17 `
  --benign-data-dir runs/frontend_f2_expression_v4a_crosscapture_stage1_2026-04-17/data `
  --attack-data-dir runs/frontend_f2_expression_v4a_attack_source_2026-04-17/data `
  --stage2-manifest D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_joint_eval_stage2_2026-04-01\attack_manifest_stage2.json `
  --epochs 20 `
  --batch-size 256 `
  --lr 1e-3 `
  --train-samples 8000 `
  --id-eval-samples 5000 `
  --calibration-budget 5000 `
  --calibration-target 0.01 `
  --d-model 64 `
  --nhead 4 `
  --num-layers 2 `
  --token-mlp-bottleneck 192 `
  --seed 42 `
  --device cuda
```

如果本机没有 CUDA，则改为：

```powershell
--device cpu
```

## 11. 这轮 Smoke 只看什么

主看两项：

- `transformer + family_short_focus + mi_dir_mean`
- `transformer + family_short_focus + mi_hphp_short_mean`

辅助看两项：

- `HH / HH_jit` 相关 token 的 tail overlap 是否下降
- `hphp_mean` 的 `alarm<=1%` feasible 点是否还存在

## 12. 成功判据

这轮本地 smoke 的目标不是超过全局最好模型，而是满足下面任一条件：

- `AUC >= 0.80`，同时 `calibrated_alarm <= 0.03`，同时 `calibrated_det >= 0.30`
- 或者相比当前 `v3`：
  - `calibrated_alarm` 至少再下降 30%
  - `AUC` 不明显跌穿 `0.80`
  - `calibrated_det` 不出现灾难性塌陷
  - per-token diagnostic 明确显示 `HH / HH_jit` 变健康

## 13. 失败判据

以下情况视为本方案不值得继续放大：

- `AUC` 明显跌破 `0.75`
- alarm 没明显下降，但 det 明显塌掉
- `HH / HH_jit` diagnostic 几乎没改善
- 所有 family 一起被“钝化”，attack 信号也一起被冲掉

## 14. 结论

`v4a_hh_stabilized` 是当前这条支线最合理的第一步，因为它满足：

- 直接命中当前瓶颈：`HH / HH_jit` 的 benign OOD 过敏
- 变量控制干净：`MI_dir / HpHp` 完全不动
- 实验成本低：不需要先动模型，不需要先上超算

如果这版 smoke 有正向信号，再考虑：

- 增训练量到 `50 epochs + 20000 samples`
- 或进入下一个对照版本，例如更激进的 `HH` 简化控制实验
