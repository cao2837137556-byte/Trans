# master_experiment_map_v1

> 版本：v1（2026-03-31）  
> 用途：作为后续实验补充与论文写作的固定“总地图”，避免实验散点化推进。

---

## 一、项目总目标（作者视角）

这篇论文的核心目标已经明确为：在 **original-frontend 100维** 的可信输入链上，研究 stronger OOD（更强分布外）场景下异常检测的**低误报稳健性机制**。因此它不是“换一个 detector 看分数高低”的小模型对比，而是“协议强度 + 阈值机制 + 模型补充修正”的系统问题：先坐实 stronger OOD 的误报放大现象，再证明 calibration（校准）是主要杠杆，最后用 TailReg（尾部正则）给出模型层的定向补充改进。

---

## 二、实验总框架（总表）

| 模块 | 当前状态 | 论文作用 |
|---|---|---|
| 1) 历史链 detector 比较（clean115） | 已完成基础版 | 后端比较与历史对照 |
| 2) stronger OOD 主线现象（frontend100） | 已完成并稳定 | 主结果现象证据 |
| 3) calibration 机制实验 | 已完成并稳定 | 主线机制证据（核心） |
| 4) TailReg 方法实验 | 已完成阶段稳定版 | 模型层补充贡献 |
| 5) 扩展验证（更多 capture/能力约束/效率） | 待补 | A区完整性与泛化增强 |

---

## 三、当前已完成实验（按“支撑什么主张”整理）

### A. 动机证据

**1) 已完成实验**
- `runs/ood_probe_stage1_2026-03-21`
- `runs/ood_probe_stage1_stability_2026-03-21`
- `runs/ood_probe_2026-03-21`

**2) 核心结果**
- 在 adapter/映射链路下观察到非常强的 OOD benign 误报（含接近灾难级现象）。

**3) 论文作用**
- 用于说明“开放世界误报失稳值得研究”，即问题发现与研究动机。

**4) 边界说明**
- 该链路存在 schema 映射与输入一致性问题，只能做动机证据，不能当正式主结论。

---

### B. 输入链纠错证据

**1) 已完成实验**
- `runs/csv_input_clean_stage1_2026-03-23`（dirty116 -> clean115）
- `runs/kitsune_frontend_stage1_2026-03-22`（原版前端最小接入）

**2) 核心结果**
- 证实 `Mirai_dataset.csv / my_gold_mirai.csv` 的 116 维含索引样首列污染；清洗后得到 clean115。
- 原版前端链成功产出稳定 100维特征缓存（不再依赖 adapter）。

**3) 论文作用**
- 解决“输入空间不一致/污染”这一可信度前提问题，为主线结论提供可辩护输入基础。

**4) 边界说明**
- clean115 与 original-frontend 100 是两条并行输入轨道，不能混写成同一主线结果。

---

### C. 历史链 detector 比较证据（clean115）

**1) 已完成实验**
- `runs/csv_input_clean_stage1_2026-03-23/trans115_min`
- `runs/csv_input_clean_stage1_2026-03-23/da115_min`
- 同配置 dirty116 对照：`trans116_dirty_min` / `da116_dirty_min`

**2) 核心结果**
- clean115 与 dirty116 的分数统计显著不同，确认索引列污染会扭曲 detector 行为。
- 在 clean115 下已完成 Transformer 与 dA 的可复现实验入口。

**3) 论文作用**
- 承担“历史链输入纠错后后端比较”的对照角色，支撑方法选择的历史合理性。

**4) 边界说明**
- 不用于 stronger OOD 主结论；该链路不等价于原版前端 100维主线。

---

### D. stronger OOD 主线证据（frontend100）

**1) 已完成实验**
- 同 capture 分段（较弱 OOD）：`runs/frontend100_ood_stage1_2026-03-23`
- cross-capture stage1（更强 OOD）：`runs/frontend100_crosscapture_stage1_2026-03-25`
- cross-capture 多 seed 稳定：`runs/frontend100_crosscapture_stability_2026-03-25`

**2) 核心结果**
- 同 capture 分段下报警率低（Transformer 0.00610，dA 0.01085）。
- cross-capture 后 fixed 报警显著升高（stage1：Transformer 0.44175，dA 0.12580；多 seed 稳定维持高误报趋势）。

**3) 论文作用**
- 直接支撑“stronger OOD 问题真实存在”，并完成从弱协议到强协议的递进证据链。

**4) 边界说明**
- 当前 strongest 组合主要是 7-6 -> 4-1；跨更多 benign capture 的泛化还需补。

---

### E. calibration 机制证据（主线核心）

**1) 已完成实验**
- 阈值基线：`runs/frontend100_crosscapture_threshold_2026-03-25`
- 校准扫描：`runs/frontend100_crosscapture_calibration_scan_2026-03-25`
- 关键设置多 seed 稳定：`runs/frontend100_crosscapture_calib_stability_local_2026-03-30`

**2) 核心结果**
- Fixed OOD alarm ratio（mean ± std）：  
  - transformer：`0.4548 ± 0.2769`  
  - da：`0.1378 ± 0.0050`
- Calibrated（budget=5000,target=1%）：  
  - transformer：`0.01549 ± 0.00068`  
  - da：`0.01516 ± 0.00003`
- gap：`0.316983 -> 0.000333`，缩小约 `99.9%`。

**3) 论文作用**
- 形成当前最强机制结论：**threshold layer 是主要杠杆**。

**4) 边界说明**
- 该结论成立于“无监督 OOD 校准可用”的设置；预算更小、场景更换时的鲁棒性仍需补。

---

### F. TailReg 方法证据（阶段性方法贡献）

**1) 已完成实验**
- 方法首轮：`runs/frontend100_tailreg_stage1_2026-03-27`
- 超参扫描：`runs/frontend100_tailreg_hparam_scan_2026-03-28`
- 最优配置多 seed 稳定：`runs/frontend100_tailreg_bestcfg_stability_2026-03-28`

**2) 核心结果**
- 最优配置：`lambda=0.2, k=1.0, warmup=256, ema_alpha=0.01`
- fixed OOD alarm（mean ± std）：  
  - transformer：`0.4548 ± 0.2769`  
  - transformer_tailreg：`0.1393 ± 0.0911`  
  - da：`0.1378 ± 0.0050`
- calibrated 后 transformer 与 tailreg 基本重合（约 `0.01549`）。

**3) 论文作用**
- 支撑“模型层可补 fixed-threshold 脆弱性”的阶段性方法贡献。

**4) 边界说明**
- TailReg 不是 calibration 替代方案；当前不支持“全面提升 Transformer”的表述。

---

## 四、当前论文已经“写得动”的结论

### 可写（阶段性稳定结论）
- stronger OOD（cross-capture）下误报问题真实存在。
- fixed threshold 会显著放大 detector 间误报差距。
- calibration 是当前误报控制的主要杠杆。
- TailReg 主要改善 fixed-threshold 下 Transformer 的尾部敏感性。

### 不可写（禁止过度主张）
- “Transformer 全面优于 dA”。
- “TailReg 在所有评估条件下都优于 baseline 和 dA”。
- “calibration 已彻底解决开放世界低误报问题”。
- 把 clean115 或 adapter 链结果写成 stronger OOD 主结论。

---

## 五、后续必须完成的实验（优先级）

### A. 必须做

1) **扩展 benign cross-capture 组合（至少再补 2 组）**  
- 为什么：当前 strongest 结论主要基于 7-6 -> 4-1，外推范围仍窄。  
- 支撑主张：stronger OOD 误报放大是否具有场景普适性。  
- 论文位置：Main Results + Robustness subsection。

2) **补“低误报不以漏检为代价”验证（恶意检测能力约束）**  
- 为什么：只看 benign 误报不足以完成检测器评价闭环。  
- 支撑主张：calibration/TailReg 降误报后仍保持检测能力（TPR/PR-AUC 不明显掉）。  
- 论文位置：Results 主表（误报-检出联合结果）。

3) **在 stronger OOD 上补一个轻量传统 baseline（非重模型）**  
- 为什么：目前主比较集中在 Transformer 与 dA，需要最低限度外部参照。  
- 支撑主张：当前机制结论不是“双模型偶然”。  
- 论文位置：Results 对比段（附表或补充表）。

4) **补效率与代价（训练/推理/校准开销）**  
- 为什么：A区评审会问“效果是否靠高成本换来”。  
- 支撑主张：方案具备工程可行性（尤其校准预算/延迟）。  
- 论文位置：Discussion 或 Deployment Consideration。

---

### B. 强烈建议做

1) **小预算 calibration 稳定性（多 seed，多组合）**  
- 为什么：当前最佳结果依赖 budget=5000，需评估资源敏感性。  
- 支撑主张：阈值层杠杆在受限预算下是否仍有效。  
- 论文位置：Calibration Analysis 扩展小节。

2) **TailReg 方差收敛与稳定性分析（固定最优附近）**  
- 为什么：TailReg 的 fixed 误报 std 仍明显高于 dA。  
- 支撑主张：TailReg 不仅降均值，还能降波动。  
- 论文位置：TailReg Results/Analysis。

3) **统计显著性/置信区间补充**  
- 为什么：主结论基于多 seed，加入显著性可提高审稿说服力。  
- 支撑主张：gap 收缩与 fixed 改善不是随机波动。  
- 论文位置：Results footnote 或附录统计说明。

---

### C. 可选增强

1) **更强 OOD 强度梯度（跨更多设备/时段/协议域）**  
- 为什么：进一步放大挑战，验证结论边界。  
- 支撑主张：结论的适用范围与失效边界。  
- 论文位置：Discussion / Limitations。

2) **不确定性或分数校准高级方案（轻量）**  
- 为什么：在“阈值层主导”已成立后，可探索更稳阈值机制。  
- 支撑主张：机制深化，不改变主线框架。  
- 论文位置：Future Work 或附加实验。

3) **可解释性可视化增强（尾部样本画像）**  
- 为什么：帮助解释 TailReg 为什么主要作用于 fixed 场景。  
- 支撑主张：机制可解释性提升。  
- 论文位置：Analysis 图补充。

---

## 六、后续方法改进主线（修 Transformer 路线图）

基于现有证据，后续“修 Transformer”应坚持 **阈值层优先、模型层补充**，而不是回到大模型替换：

1) **目标 1：固定阈值下更低误报均值 + 更低方差**  
- 继续围绕 normal score tail 设计轻量约束（TailReg 家族），重点降低 seed 间波动。

2) **目标 2：小预算校准友好性（calibration efficiency）**  
- 让模型分数分布更“可校准”：在 500~2000 budget 下也能稳定逼近目标报警率。

3) **目标 3：误报-检出联合优化**  
- 任何降误报改动必须同时报告检测能力不塌陷（TPR/PR-AUC 或召回约束）。

4) **目标 4：保持工程成本可控**  
- 不引入重模型；优先维持与当前流程兼容的轻量正则/后处理改动。

建议的方法线表述：  
**“先用 calibration 解决主矛盾，再用 TailReg 类模型约束降低 fixed-threshold 脆弱性与波动，并验证在低预算校准与检测能力约束下仍成立。”**

---

## 七、论文-实验映射表

| 论文部分 | 对应实验模块 | 当前状态 |
|---|---|---|
| Introduction（stronger OOD 动机） | 动机证据 + stronger OOD 递进（A+D） | 已可写 |
| Data/Input Reliability | 输入链纠错（B） | 已可写 |
| Main Results（stronger OOD） | D（同capture->cross-capture->多seed） | 已可写 |
| Calibration Analysis | E（threshold baseline + scan + local stability） | 已可写（核心） |
| TailReg 方法与结果 | F（stage1 + hparam + bestcfg stability） | 已可写（阶段性） |
| Discussion / Limitations | 边界与待补实验（A/C/D/E/F 边界 + 五） | 已可写，待增强 |

---

## 八、作者执行建议（下一步最稳推进顺序）

建议按下面顺序推进，避免再次“实验散点化”：

1) **先补“必须做”中的 1 + 2**（更多 cross-capture + 检测能力约束）。  
2) 同步补 **必须做 4**（效率/代价），确保主线结果可工程化表达。  
3) 再做 **强烈建议 1**（小预算 calibration 稳定性），强化“阈值层主杠杆”的适用范围。  
4) 最后再决定是否推进 **强烈建议 2/可选增强**，用于冲击更高说服力版本。  

以后每个新实验立项前先回答三件事：  
- 它属于本地图哪一模块？  
- 它要支撑哪一句论文主张？  
- 它完成后进入正文哪一节？  

如果这三点回答不清，就先不做，避免新增“无法入稿的实验”。
