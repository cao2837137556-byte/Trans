# handoff_for_prism_strongerood_calibration_tailreg

## 1) 当前论文主线

当前正式主线是 **original-frontend 100维 cross-capture stronger OOD**。  
核心研究问题是：在开放世界（open-world）更强分布外迁移下，如何实现**低误报与稳健性**，而不是单纯比较谁的 detector（检测器）分数更好。  
`clean115` 历史链目前主要承担“同输入条件下的 detector 对照”角色；`dirty116` 与 adapter 链只用于问题发现/动机，不作为 stronger OOD 正式主证据。

---

## 2) stronger OOD 主线协议（固定）

- ID benign capture：`CTU-Honeypot-Capture-7-6`
- OOD benign capture：`CTU-Honeypot-Capture-4-1`
- 输入：original-frontend 100维特征
- 固定训练/评估协议：
  - `train_samples=8000`
  - `id_eval_samples=5000`
  - `fm=2000`
  - `ad=6000`

---

## 3) stronger OOD 现象证据

在同一输入链（original-frontend 100维）下，协议强度提升后出现了清晰分层：

- **同-capture 分段（较弱 OOD）**：OOD benign 报警率较低  
  - Transformer：`0.00610`  
  - dA：`0.01085`
- **cross-capture（stronger OOD）**：误报显著升高  
  - Transformer（seed=42 stage1）：`0.44175`  
  - dA（seed=42 stage1）：`0.12580`

这说明开放世界问题真实存在；同时也说明结论强度必须建立在更可信输入链（original-frontend）与更强协议（cross-capture）之上。

---

## 4) calibration 机制证据（重点）

多 seed 稳定结果（seed=101/202/303，固定 cross-capture 协议）：

- **Fixed OOD alarm ratio（mean +/- std）**
  - transformer: `0.4548 +/- 0.2769`
  - da: `0.1378 +/- 0.0050`

- **Calibrated OOD alarm ratio（budget=5000,target=1%）**
  - transformer: `0.01549 +/- 0.00068`
  - da: `0.01516 +/- 0.00003`

- **Gap 收缩**
  - fixed gap: `0.316983`
  - calibrated gap: `0.000333`
  - gap 缩小约 `99.9%`

论文可用结论（建议原句）：

1. stronger OOD 下，fixed threshold 会显著放大误报。  
2. calibration（无监督 OOD 阈值校准）是主要杠杆。  
3. Transformer 在 fixed threshold 下更敏感，但经无监督 OOD 校准后与 dA 的误报差距显著缩小。  
4. 因而不能把 stronger OOD 下的 detector 排名简单解释为“模型本体优劣”。

---

## 5) TailReg 方法与结果（阶段性方法贡献）

### 5.1 方法动机与设置

TailReg（Tail-Regularized Transformer）动机：缓解 stronger OOD 下**正常分数上尾过高**导致的 fixed-threshold 敏感性。  
最优配置（已固定）：

- `lambda=0.2`
- `k=1.0`
- `warmup=256`
- `ema_alpha=0.01`

### 5.2 多 seed 稳定结果

- **Fixed OOD alarm ratio**
  - transformer: `0.4548 +/- 0.2769`
  - transformer_tailreg: `0.1393 +/- 0.0911`
  - da: `0.1378 +/- 0.0050`

- **Calibrated OOD alarm ratio**
  - transformer: `0.01549 +/- 0.00068`
  - transformer_tailreg: `0.01549 +/- 0.00068`
  - da: `0.01516 +/- 0.00003`

- **TailReg 相对 baseline Transformer（fixed）平均收益**
  - 绝对下降：`0.31545`
  - 相对下降：`69.36%`

论文可用结论（建议原句）：

1. TailReg 的稳定贡献主要体现在 fixed-threshold 敏感性缓解。  
2. calibrated 条件下额外收益有限。  
3. TailReg 是模型层补充修正，不替代 calibration。

---

## 6) 当前最准确的三层叙事（总口径）

1. **现象层**：stronger OOD 下误报问题真实存在。  
2. **机制层**：threshold layer（阈值层）是主要杠杆。  
3. **方法层**：TailReg 提供模型层补充改进，主要降低 fixed-threshold 脆弱性。

---

## 7) 哪些话不能写过头（必须保留边界）

- 不能写“Transformer 全面优于 dA”。
- 不能写“TailReg 全面提升 Transformer”。
- 不能写“校准已彻底解决开放世界低误报问题”。
- 不能把 clean115 历史链结果写成 stronger OOD 主结论。
- 不能把 dirty116 / adapter 链写成正式主证据。

---

## 8) 推荐给 Prism 的写法建议

### 8.1 Introduction / Discussion

- 强调：开放世界 stronger OOD 会触发显著误报放大；阈值机制不可忽略。  
- 强调：模型比较若不控制阈值层，会把“阈值失配”误判为“模型本体差距”。

### 8.2 Results / Analysis

- 主表建议按三段组织：
  1) fixed threshold 的 cross-capture 误报对比；  
  2) calibration 后误报与 gap 收缩；  
  3) TailReg 在 fixed 与 calibrated 下的差异定位。  
- 结论语气保持“阶段性稳定证据”，避免“终局结论”。

### 8.3 Method（TailReg 补充段）

- TailReg 作为轻量模型层修正写入方法补充（不是主方法替代 calibration）。  
- 重点说明它解决的是“normal score tail”问题，并明确 calibrated 条件下收益边界。

### 8.4 Prism 写作重点与边界

- 推荐重点：**stronger OOD -> calibration 主杠杆 -> TailReg 补充收益**。  
- 必须保留边界：结果当前主要基于该 benign cross-capture 组合，外推需谨慎。

---

## 9) 可引用产物清单（含用途）

### A. `frontend100_crosscapture_stability_2026-03-25`

- `summary.md`：支撑“cross-capture stronger OOD 下误报升高且多 seed 稳定”。  
- `aggregate_mean_var.csv`：支撑 fixed 条件下 Transformer 与 dA 的稳定差距量化。  
- `plots/alarm_ratio_by_seed.png`：支撑“按 seed 看误报差异稳定存在”。  
- `plots/id_vs_ood_boxplot.png`：支撑“ID/OOD 分布分离与尾部放大”。

### B. `frontend100_crosscapture_threshold_2026-03-25`

- `summary.md`：支撑“阈值自适应可显著降误报”的首轮机制证据。  
- `threshold_comparison.csv`：支撑固定阈值 vs 自适应阈值的定量对照。  
- `plots/threshold_policy_alarm_ratio.png`：支撑“调阈值能救多少”直观展示。

### C. `frontend100_crosscapture_calibration_scan_2026-03-25`

- `summary.md`：支撑“budget × target 扫描下 calibration 机制稳定有效”。  
- `calibration_grid_results.csv`：支撑阈值、目标报警率、实际报警率映射关系。  
- `plots/achieved_alarm_vs_budget.png`：支撑“校准预算影响规律”。  
- `plots/detector_compare_by_target.png`：支撑“不同 target 下 detector 差异”。

### D. `frontend100_crosscapture_calib_stability_local_2026-03-30`

- `summary.md`：支撑“关键校准设置（budget=5000,target=1%）多 seed 稳定复验结论”。  
- `aggregate_mean_var.csv`：支撑 fixed gap 与 calibrated gap 的均值/方差比较。  
- `per_seed_results.csv`：支撑每个 seed 的一致性检查与可追溯性。  
- `plots/fixed_alarm_ratio_by_seed.png`：支撑“fixed 下误报放大稳定成立”。  
- `plots/calibrated_alarm_ratio_by_seed.png`：支撑“calibrated 后 gap 显著收缩”。  
- `plots/fixed_vs_calibrated_mean.png`：支撑“阈值层是主要杠杆”的核心图。

### E. `frontend100_tailreg_bestcfg_stability_2026-03-28`

- `summary.md`：支撑 TailReg 阶段性方法结论与边界。  
- `aggregate_mean_var.csv`：支撑 TailReg 在 fixed 下平均收益（含 mean +/- std）。  
- `per_seed_results.csv`：支撑 TailReg 改善是否跨 seed 稳定。  
- `plots/fixed_alarm_ratio_by_seed.png`：支撑“TailReg 主要改善 fixed-threshold 敏感性”。  
- `plots/calibrated_alarm_ratio_by_seed.png`：支撑“calibrated 条件下 TailReg 额外收益有限”。  
- `plots/fixed_vs_calibrated_mean.png`：支撑“TailReg 是补充修正，不替代 calibration”。

---

## 建议在正文中的一句话总述（可直接改写使用）

在 original-frontend 100维 cross-capture stronger OOD 协议下，我们观察到 fixed threshold 会显著放大误报；无监督 OOD calibration 可将 Transformer 与 dA 的误报差距压缩约 99.9%，表明阈值层是主要杠杆；在此基础上，TailReg 进一步稳定缓解了 Transformer 在 fixed-threshold 条件下的尾部敏感性，但其 calibrated 条件下的额外收益有限，因此应被定位为模型层补充修正而非替代校准的终局方案。
