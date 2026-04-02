# handoff_for_prism_mainline_figures

## 1) 最终推荐放正文的图（2 张）

### 图 1（主图，机制主张）
- 文件：`D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\prism_handoffs\2026-03-31_mainline_figures\mainline_fixed_vs_calibrated_alarm_ratio.png`
- 图意：在 stronger OOD（cross-capture）下，fixed threshold 导致 Transformer 与 dA 报警率差距很大；calibration 后差距显著收缩。
- 对应主张：**threshold layer（阈值层）是主要杠杆**。

### 图 2（方法补充图）
- 文件：`D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\prism_handoffs\2026-03-31_mainline_figures\mainline_tailreg_vs_baselines.png`
- 图意：TailReg 在 fixed-threshold 下显著降低 Transformer 误报；calibrated 条件下与 baseline Transformer 几乎重合。
- 对应主张：**TailReg 是 fixed-threshold 脆弱性的模型层补充修正，不替代 calibration**。

---

## 2) 每张图的数据来源（严格限定主线稳定产物）

### 图 1 数据来源
- 主要来源（多 seed 聚合）：  
  `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_calib_stability_local_2026-03-30\aggregate_mean_var.csv`
- 协议背景来源（stronger OOD 固定协议稳定性）：  
  `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_crosscapture_stability_2026-03-25\summary.md`
- 是否多 seed：是（seed=101/202/303）。

### 图 2 数据来源
- 主要来源（多 seed 聚合）：  
  `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_tailreg_bestcfg_stability_2026-03-28\aggregate_mean_var.csv`
- 是否多 seed：是（seed=101/202/303）。

---

## 3) 正文解释建议（逐图）

### 图 1 正文解释建议
建议用 2–3 句直接给机制：
1. 在 stronger OOD 下，fixed ID-q99 阈值将 Transformer 误报抬高至 `0.4548±0.2769`，dA 为 `0.1378±0.0050`。  
2. 使用无监督 OOD calibration（budget=5000, target=1%）后，二者降至 `0.01549±0.00068` 与 `0.01516±0.00003`。  
3. detector gap 从 `0.316983` 缩至 `0.000333`（约 99.9%），说明阈值层是主要杠杆。

### 图 2 正文解释建议
建议用 2–3 句明确边界：
1. TailReg 将 Transformer 的 fixed 报警率从 `0.4548±0.2769` 降到 `0.1393±0.0911`，接近 dA 的 `0.1378±0.0050`。  
2. 在 calibrated 条件下，Transformer 与 Transformer+TailReg 基本重合（均约 `0.01549`）。  
3. 因此 TailReg 的稳定贡献主要发生在 fixed-threshold 场景。

---

## 4) 哪些结论可以写、哪些不能写过头

### 可以写
- stronger OOD 问题真实存在（cross-capture 下 fixed 报警显著上升）。  
- calibration 是当前主线中的主要误报控制杠杆。  
- TailReg 能稳定缓解 Transformer 在 fixed-threshold 下的上尾敏感性。

### 不能写
- “Transformer 全面优于 dA”。  
- “TailReg 全面提升 Transformer（含 calibrated）”。  
- “calibration 已彻底解决开放世界低误报问题”。

---

## 5) 是否需要配一个 very compact 小表

建议：**需要 1 个极小表**，放在图 1 和图 2 之间或图 2 后，作为读者快速对数值锚定。

- 建议文件（已生成）：  
  `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\prism_handoffs\2026-03-31_mainline_figures\mainline_compact_table.md`  
  `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\prism_handoffs\2026-03-31_mainline_figures\mainline_compact_table.csv`
- 表格定位：Results/Analysis 小节内，作为“主图数字摘要”，不单独扩展方法讨论。

---

## 6) 推荐给 Prism 的插图位置

- 图 1：放在 Results 中 stronger OOD 主结果段落开头或中段（先现象再机制）。  
- 图 2：紧跟图 1 后，放在“模型层补充修正（TailReg）”段落。  
- 图注重点：
  1) stronger OOD 下 fixed 阈值放大误报；  
  2) calibration 显著压缩 detector gap；  
  3) TailReg 主要改善 fixed-threshold，不改变 calibrated 上限格局。

---

## 7) 本次产物清单

- `mainline_fixed_vs_calibrated_alarm_ratio.png`（正文主图候选 1）  
- `mainline_tailreg_vs_baselines.png`（正文主图候选 2）  
- `mainline_compact_table.md`（正文紧凑小表）  
- `mainline_compact_table.csv`（可复用原始表）
