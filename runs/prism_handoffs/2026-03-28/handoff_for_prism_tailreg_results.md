# Prism 论文交接：TailReg 最优配置稳定结果（frontend100_tailreg_bestcfg_stability_2026-03-28）

## 1. 所属主线
本轮结果属于 **original-frontend 100维 cross-capture 主线**。

明确边界：
- 不是 dirty116 / clean115 历史 CSV 链结果；
- 不是 adapter 映射链的预备性证据；
- 是当前“更干净输入链路 + stronger OOD 协议”下的模型层修正稳定性证据。

## 2. 数据与协议
- ID benign capture：**CTU-Honeypot-Capture-7-6**
- OOD benign capture：**CTU-Honeypot-Capture-4-1**
- 输入：**original-frontend 100维特征**
- 固定协议：
  - `train_samples=8000`
  - `id_eval_samples=5000`
  - `fm=2000`
  - `ad=6000`
- 多 seed：`101 / 202 / 303`
- detector：
  - `transformer`
  - `transformer_tailreg`（best cfg）
  - `da`（dA / KitNET backend）

## 3. TailReg 方法说明（论文写法）
TailReg 的动机是：在 stronger OOD 下，baseline Transformer 在 fixed-threshold（ID q99 固定阈值）设置中对上尾分数过敏，导致误报偏高。

当前采用形式：在 Transformer 训练目标中引入面向正常分数上尾的轻量正则（tail regularization），目标是压制正常分数尾部过高样本带来的阈值敏感性。

本轮固定最优配置：
- `lambda=0.2`
- `k=1.0`
- `warmup=256`
- `ema_alpha=0.01`

其针对问题：**stronger OOD 下 fixed-threshold 敏感性 / 正常分数上尾过高**。

## 4. 关键稳定结果（多 seed 聚合）
### 4.1 Fixed OOD alarm ratio
- transformer: **0.4548 +/- 0.2769**
- transformer_tailreg: **0.1393 +/- 0.0911**
- da: **0.1378 +/- 0.0050**

### 4.2 Calibrated OOD alarm ratio（budget=5000, target=1%）
- transformer: **0.01549 +/- 0.00068**
- transformer_tailreg: **0.01549 +/- 0.00068**
- da: **0.01516 +/- 0.00003**

### 4.3 TailReg 相对 baseline Transformer（fixed）的平均收益
- 绝对下降：**0.31545**
- 相对下降：**69.36%**

## 5. 本轮结果支持的主张与不支持的主张
### 可支持（建议写入正文）
TailReg 的稳定贡献是：**主要缓解 fixed-threshold 下 stronger OOD 的误报敏感性**。

### 不可过度主张（建议避免）
- 不能写成“TailReg 全面提升 Transformer”；
- 不能写成“TailReg 在 calibrated 条件下显著优于 baseline Transformer”。

## 6. 结果边界与证据等级
- 本轮为多 seed 稳定结果，可作为**阶段性稳定结论**；
- 但局限于当前 benign cross-capture 组合（7-6 -> 4-1）；
- 这是**模型层修正证据**，不替代阈值层校准结论；
- 当前最准确的综合表述：
  - **阈值层是主要杠杆，TailReg 进一步稳定改善 fixed-threshold 脆弱性。**

## 7. 给 Prism 的写法建议
- 位置建议：优先放在 **Results / Analysis**，并在 Method 里给 TailReg 一个简洁定义；属于 **Method+Results 联动** 的“小改动有效性验证”。
- 角色定位：更适合作为 **阶段性方法贡献**（不是最终统一方案）。
- 推荐强调：
  1) stronger OOD + fixed-threshold 下的稳定降误报；
  2) calibrated 后差距仍小，说明 TailReg 不是替代校准，而是补足 fixed-threshold 脆弱性。
- 建议避免写过头：
  - 避免“全面优于 dA / 全场景最优”；
  - 避免“校准后显著领先 baseline Transformer”。

## 8. 论文可引用产物清单（文件 -> 支撑结论）
- `summary.md`
  - 用途：给出一段可直接引用的阶段性结论与协议摘要。
  - 适合支撑："TailReg 主要改善 fixed-threshold 敏感性" 的总括句。

- `aggregate_mean_var.csv`
  - 用途：提供 mean +/- std 的核心数值。
  - 适合支撑：多 seed 稳定结论、主表中的聚合对比。

- `per_seed_results.csv`
  - 用途：提供每个 seed 的原始结果。
  - 适合支撑："改进不是单 seed 偶然"、附录透明性。

- `fixed_alarm_ratio_by_seed.png`
  - 用途：直观展示 fixed-threshold 下三 detector 的 seed 级差异。
  - 适合支撑：TailReg 对 baseline Transformer 的稳定降误报。

- `calibrated_alarm_ratio_by_seed.png`
  - 用途：直观展示 calibrated 后三 detector 基本接近。
  - 适合支撑：TailReg 在 calibrated 条件下无显著额外收益。

- `fixed_vs_calibrated_mean.png`
  - 用途：一图对比 fixed 与 calibrated 两协议的均值变化。
  - 适合支撑："阈值层是主要杠杆，TailReg 是 fixed-threshold 补充改进" 的综合表述。
