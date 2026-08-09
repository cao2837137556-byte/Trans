# CKBY 结果：DROCC 记录级能力基线（seed 27）——Gate A FAIL，双重惨败

- 日期：2026-08-09
- 预注册：`ckby_drocc_record_capacity_baseline_preregistered_20260807.md`（FROZEN，
  SHA-256 `bbb113eaef19325099c997e8af8c8ff1a623ea60a01933fff7dcc3271a8a69f0`）
  + 勘误 1 `ckby_preregistered_erratum_1_feature_snapshot_contract_20260807.md`
- 执行：特征快照 HPC job 157930（287,448 行，SHA-256
  `b2ef1f7d0244cc7abb8665c25364744f794190f411482e4e202e346cb850279c`，
  全部冻结合同断言通过）；本地 CPU 训练（torch 2.13.0+cpu，600 秒）；
  评估一次性完成。
- 训练 run_spec：`runs/issue27ckby_drocc_local_seed27_2026-08-09/ckby_drocc_run_spec_seed27.json`
  （模型权重 SHA-256 `5aa9d88a5a27d473f9f1952c5a1863555918a2cd4fddc8b8d05284e6b2e593c2`）。

## 1. 裁决（PRIMARY 工作点 OP-1，良性预算 1%）

| Gate A 条款 | 门槛 | DROCC 实测 | 判定 |
|---|---:|---:|---|
| 4 池良性 OOD macro hard rate | ≤ 30.27% | **55.57%** | FAIL |
| future 攻击召回 | ≥ 84.83% | **9.04%** | FAIL |

**Gate A = FAIL（两条腿同时失败，且幅度巨大）。** OP-0.1（预算 0.1%）同样失败
（OOD 47.63% / 召回 5.52%）——收紧预算时攻击召回进一步崩塌，符合 capacity
curve 的"崩塌"形态而非渐降。

## 2. 同分母对照（冻结口径，future_query 131,391 行 / 4 池 18,000 行）

| 臂 | future 攻击召回 | 4 池 OOD macro |
|---|---:|---:|
| M0-C1 | 86.83% | 93.09% |
| M1-FrozenCKBQ | 74.20% | 35.27% |
| M7-TabM-TailMargin-DualControl（CKBW PRIMARY） | 63.19% | 0.15% |
| **CKBY-DROCC-OP-1** | **9.04%** | **55.57%** |
| CKBY-DROCC-OP-0.1 | 5.52% | 47.63% |

DROCC 是迄今所有记录级方法中**最差**的：既远不如 FrozenCKBQ 的 OOD 抑制，
也把攻击召回打到个位数。它不存在"trade-off 上更好的一点"——它在两个轴上同时劣化。

## 3. 分池与分族细节（OP-1）

良性 OOD 4 池：ip-camera-street 99.83%、stream-consumer 99.27%、
hydraulic 23.17%、predictive-maintenance 0.01%（macro 55.57%）。
前两个池几乎全池误报——**未见过的良性环境被整体当作异常**。

攻击 16 族（future+same_file+sealed_final，GLOBAL 切片）：
Merlin UDP Flooding 100% 外，其余 15 族全部残缺——TCP Scan 0.99%、
Mirai TCP Flooding 0.004%、Ingress Tool Transfer 0.22%、Mirai GRE Flooding 0%、
Merlin TCP Flooding 0.03%、UDP Scan 0%。support_val 69（仅报告）23.19%。
**攻击不是被"抑制"，而是被整体吸收进正常区。**

诊断 AUC（仅诊断，未参与任何选择）见
`ckby_drocc_diagnostic_auc_seed27.csv`。

## 4. 关键过程发现：benign-only 选择永远选不中对抗训练模型

按冻结 §2.2 的 benign-only checkpoint 规则（最低 benign 验证 CE），
最优 checkpoint = **epoch 49（纯 CE 阶段结束）**，val CE 1.92e-5。
对抗阶段（epoch 50-199）一开始，benign 验证 CE 即升至 ~2-3e-3 并保持——
**对抗训练迫使模型在法向流形附近开凿边界，必然牺牲对 normal 点的极端置信**。
在不允许看任何攻击/OOD 数据的纯 benign 选择规则下，DROCC 的对抗阶段
在原则上不可能被选中。这意味着被评估的模型实为"饱和置信 MLP"。

这一发现本身就是结果的一部分：**"strong benign-only learner" 这个范畴在
51D 上自我瓦解**——选择压力只奖励对 benign 的置信，而对抗鲁棒性恰恰要
降低这种置信。

## 5. 科学解释（为什么双重惨败恰是强证据）

DROCC 的失败模式同时暴露了两种不可分：

1. **良性 OOD ≈ 攻击（在离流形方向上）**：未见过的良性环境（ip-camera、
   stream-consumer）在 51D 上离合法 benign 流形很远，one-class 边界把它们
   全部判为异常——良性 OOD 与"真正异常"在表示中同向。
2. **攻击 ≈ 良性（在流形内部）**：绝大多攻击族（scan、flood、ingress）落在
   已见良性流形之内，被边界判为正常——攻击与良性在表示中同域。

一个只见过 benign 的学习器没有任何信息区分"流形外的良性"与"流形外的恶意"、
"流形内的良性"与"流形内的恶意"。这与 veto 诊断（a23c5fa，oracle 不可分）、
容量审计（68bdeb2，六模型类同撞一堵墙）互为印证，三方证据链闭合。

## 6. 实现偏差声明（透明记录，均无科学面影响）

1. **lr 调度**：初版实现把官方 epoch-shifted 分段误录为按总 epoch 比例；
   发现后按官方 `main_tabular.py` 原文改正（对抗段内 30%/60%/90% 分段），
   CE 预热段（0-49）两版一致，NaN 段作废重跑，最终轨迹=官方算法轨迹。
2. **数值护栏**：官方 `grad/grad_norm` 在 float32 饱和点产生 0/0=NaN
   （本数据有 3 个常量特征，std floor 1e-4 使对抗噪声在这些坐标放大 10^4 倍
   → logit 饱和 → 梯度下溢为 0）。两处除法加 1e-12（梯度归一化、环带投影），
   非退化点逐位不变，零梯度点保持不动。无此护栏官方代码在本数据上无法运行。
3. 分段断点续跑经 RNG/优化器状态持久化，与单次连续运行逐位等价
   （0-49 段重跑复现 val CE 完全一致，已验证）。

## 7. 一次性评估声明

阈值与 checkpoint 在打开任何 report 池之前冻结；全部 report 池恰好评分一次；
无任何指标反馈进任何选择；support_val 69 仅报告未参与训练/阈值；
FINAL（cooler-motor、seed 37/47）全程未触碰。

## 8. 路由（按 FROZEN §8 执行）

Gate A FAIL → **封死"现有冻结 51D 表示上模型容量不够"这一剩余替代解释**。
连同 conformal / reconstruction / tree / TabM / C1+51D 仲裁 / DROCC 在同一
trade-off 上的重复失败，继续更换记录级学习器的科学边际价值已耗尽——
**不再开新的记录级模型**（GPT 8/8 裁定"跑一次即收枪"，本条已执行）。
下一步：Episode Design Review（统一 GPT/Kimi/Claude 的 episode 假设，
明确相对 CKBQ 旧时序分支的新增信息），通过后才起草 episode 预注册。
本结果不构成"所有记录级表示均不可能"的声称（预训练流量表征等储备路线保留，
见简报 round 8 假设库）。
