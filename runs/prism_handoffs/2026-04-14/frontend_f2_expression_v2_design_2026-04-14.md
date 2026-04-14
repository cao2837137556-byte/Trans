# Frontend-F2 Expression_v2 Design

日期：2026-04-14  
状态：第一版已实现并完成本地 smoke  
作用：记录 `frontend-f2` 从“高级 100D 重排”正式转向“extractor-level 新表达”的最小设计与第一轮结论。

---

## 1. 为什么切到 expression_v2

当前支线已经有两个明确负结果：

1. `frontend_f2_structured_tokenizer_v1`
- 证明真实结构化前端链路可运行；
- 但 fixed detection 只有约 `0.20`。

2. `frontend_f2_contrast_tokenizer_v1`
- 把 detection 拉到约 `0.30`；
- 但本质仍然是在 old `100D -> structured cache` 上做更高级重排；
- 仍明显打不过 `dA` 和旧的强控制线。

因此，继续做 `contrast_tokenizer_v1_1` 的意义有限。  
本支线从这里开始转向：

> **直接在 extractor 端定义新的 model-facing cache，而不是只在旧 structured cache 上继续派生 token。**

---

## 2. expression_v2 的设计目标

第一版 `expression_v2` 想解决两个问题：

1. **不再要求可逆回 old `100D`**
- 旧 `family_scale_tokens [4,5,7]` 是可逆展开；
- `expression_v2` 则明确是有损压缩后的新表达。

2. **在 extractor 端先做幅值稳定化与跨尺度语义压缩**
- 旧 `20 x 7` token 保留了原始 slot；
- `expression_v2` 直接输出 `20 x 5` 的 compact channel。

---

## 3. expression_v2-v1 的具体定义

### 输入基础

仍基于 Kitsune 原始统计过程，不修改：

- `MI_dir`
- `HH`
- `HH_jit`
- `HpHp`
- `5 / 3 / 1 / 0.1 / 0.01` 五个尺度

即：

- family 不变
- scale 不变
- 原始统计公式不变

变化只发生在 extractor 输出层。

### 幅值稳定化

对每个原始 slot 值先做：

```text
slog(x) = sign(x) * log1p(abs(x))
```

目标：

- 压缩极端动态范围
- 让后续 compact channel 不至于被少数大值主导

### 输出形状

每个 family-scale token 从原来的 `7` 维 slot，
压成 `5` 个 extractor-level channel：

1. `level_mean_slog`
2. `level_rms_slog`
3. `delta_short_mean_slog`
4. `delta_mid_mean_slog`
5. `delta_global_mean_slog`

因此新表达为：

- `expression_v2_matrix [N,20,5]`
- `expression_v2_flat [N,100]`

### 通道含义

对每个 token：

1. `level_mean_slog`
- 当前 token 在 slog 空间下的 masked mean。

2. `level_rms_slog`
- 当前 token 在 slog 空间下的 masked RMS。

3. `delta_short_mean_slog`
- 当前 token 与 family short reference 的均值差。
- short reference = `0.1` 与 `0.01` 的平均。

4. `delta_mid_mean_slog`
- 当前 token 与 family mid reference 的均值差。
- mid reference = `1` 尺度。

5. `delta_global_mean_slog`
- 当前 token 与 family long reference 的均值差。
- global reference = `5 / 3 / 1` 三个尺度的平均。

---

## 4. 代码改动范围

### 修改的文件

- `repo/ood/kitsune_frontend_original_extract.py`
- `repo/ood/prepare_frontend_f2_crosscapture_sources.py`
- `repo/ood/prepare_frontend_f2_attack_source.py`

### 新增的文件

- `repo/ood/frontend_f2_expression_v2_tokenizer_v1.py`

### 新增的 extractor 输出

在原有 structured `.npz` 中新增：

- `expression_v2_matrix`
- `expression_v2_flat`
- `expression_v2_channel_mask`
- `expression_v2_family_id`
- `expression_v2_scale_id`
- `expression_v2_channel_names`

同时 source-prep 也会同步输出：

- `id_source_expression_v2_100.npy/csv`
- `ood_benign_source_expression_v2_100.npy/csv`
- `attack_source_expression_v2_100.npy/csv`

---

## 5. 第一轮本地 smoke 结果

### 机械结果

已完成真实 source 重提取：

- `runs/frontend_f2_expression_v2_extract_id_7_6_2026-04-14/`
- `runs/frontend_f2_expression_v2_extract_ood_4_1_2026-04-14/`
- `runs/frontend_f2_expression_v2_extract_attack_34_1_2026-04-14/`

已完成 source bundle：

- `runs/frontend_f2_expression_v2_crosscapture_stage1_2026-04-14/`
- `runs/frontend_f2_expression_v2_attack_source_2026-04-14/`

extractor smoke 验证通过：

- old `flat100` 仍可严格重构
- `expression_v2_matrix` 形状正确
- `expression_v2_flat` 形状正确
- non-finite count = `0`

### detector smoke 结果

`runs/frontend_f2_expression_v2_tokenizer_v1_smoke_2026-04-14/`

#### token-MLP

表现为几乎“全报”：

- `alarm ~ 0.964 ~ 0.993`
- `det ~ 0.974 ~ 1.000`
- `AUC ~ 0.49 ~ 0.54`

这不是有效 detector，而是基本把 benign OOD 和 attack 一起推高了。

#### transformer

表现为严重信息塌缩：

- `alarm ~ 0.306 ~ 0.394`
- `det ~ 0.089 ~ 0.123`
- `AUC ~ 0.18 ~ 0.21`

说明当前 `20x5` 表达已经损坏了大部分有效分离结构。

---

## 6. 当前判断

`expression_v2-v1` 给出的最重要信息不是“数值变好了”，而是：

1. **本支线现在已经具备真实 extractor-level 新表达试验能力**
- 这不再只是 old `100D` 的重排。

2. **第一版 compact channel 设计失败了**
- 失败原因大概率不是训练脚本坏掉；
- 而是 `20x5` 的均值型压缩过猛，把 benign OOD 与 attack 的关键差异一起抹平或一起推高了。

---

## 7. 下一步不该做什么

- 不该直接上超算
- 不该直接做多 seed
- 不该直接做大 sweep
- 不该再回去做 `contrast_tokenizer_v1_1` 当主方向

---

## 8. 下一步该做什么

下一步优先级应该是失败归因，而不是盲改模型：

1. 检查 `expression_v2` 各 channel 的 ID / OOD / attack 分布
2. 检查是哪些 family / scale / channel 导致 token-MLP 接近“全报”
3. 基于分布决定 `expression_v2.1` 是否需要：
- 减少均值压缩
- 引入更高分辨率的 raw-slot 保留
- 拆分 level 与 contrast 分支
- 对 `HH / HpHp` 与短尺度保留更细粒度表达

一句话结论：

> `expression_v2` 这个“方向”成立，但 `expression_v2-v1` 这个“具体表达”不成立。
