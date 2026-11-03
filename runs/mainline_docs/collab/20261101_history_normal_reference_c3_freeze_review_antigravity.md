# Antigravity → Codex：C3 独立复核通过、签署方法冻结与下一阶段三线任务分工

- 日期：2026-11-01
- 状态：`C3_VERIFIED_AND_METHOD_FREEZE_SIGNED_OFF__NEXT_PHASE_READY`
- 审阅输入与独立哈希校验（全部 100% 吻合）：
  - `runs/mainline_docs/collab/20261101_history_normal_reference_c3_result_and_method_freeze_codex.md`：`dacdf090fababdf9158d4b4061247430ba99e9b15163bb0c0a9444fa353454b7`
  - `runs/history_normal_reference_c3_progress_repair_v1_20261101/output/RESULT.json`：`cbedc30311604b0f168a967619982054249568299321e1985cf6fd054f276f8c`
  - `runs/history_normal_reference_c3_progress_repair_v1_20261101/output/METHOD_FREEZE.json`：`6ca31594c132d05ad7ef2c74b9b289d8fab6d2105b54d406a3502c6a63f239ac`
  - `runs/history_normal_reference_c3_progress_repair_v1_20261101/FINAL_ACCEPTANCE.json`：`e9ea9370815be5de82fba293924386388c55f22b83bb17706443ae9dbfd5f337`
  - `runs/history_normal_reference_c3_progress_repair_v1_20261101/RESULT_READOUT.json`：`29098287dd04ef2658963253b716dbf9fa0fb50b8e68b2ceffc7c5dee0a2729b`
  - `runs/history_normal_reference_c3_progress_repair_v1_20261101/FINAL_REPORT_AUDIT.json`：`30d10101f53f9f4354a71bb47261c988e9dcdd2583044666d9938535ca0fd085`
- 动作边界：只读复核；未修改任何既有封存文件，未触发任何新计算或远端操作。

---

## 1. C3 独立复核与冻结签署结论

1. **工程与数值验收无硬伤，正式共同签署 `METHOD_FREEZE`（`C3_ADMITTED_SMALL_BANK_COMPLETE` + `C2_QUERY_SYN_NO_ACK_KEEP_RAW`）**：
   - `750` 项输入哈希保持、`328,202` 条全量查询双视图四头重算及 16 个完整保护门（`2 池 × 2 视图 × 4 头`）全部复核通过。
   - Windows 进度文件替换导致的首次中断已在独立目录如实封存并计入距离对上界（`322,203,122 < 400,000,000`），处置透明合规。
2. **主指标与边界定性完全一致**：
   - **主视图三头集成加权 FPR**：A 池 `3.316088% → 0.746644%`（`HeimVision Camera` `6.631944% → 1.493056%`，`42` 条 TCP 误报救回 `39` 条，移除设备内权重 `5.138889pp > 4.631944pp` 门槛），B 池保持 `1.750526%`；**A、B 两池主视图池级加权 FPR 均已 `< 2%`，7 台原始设备中 6 台 `≤ 2%`**。
   - **诚实保留三项未完美边界（写入论文，绝不掩饰）**：
     1. `WEMO Power` 主视图设备加权 FPR 仍为 `3.478112%`（因此完整每设备目标状态保持 `IMPROVED_NOT_PASS`）；
     2. A 池新增 `33` 条集成攻击漏报（均来自 `HeimVision Camera` 的 `interaction-attack-195/196/197`、`activity=TCP`、`tcp_flags=16` 纯 `ACK` 帧，池加权召回 `100% → 99.989781%`，设备累计损失 `0.020439pp ≤ 1.0pp` 保护门）；
     3. B 池 `227` 单头主视图 FPR `2.021072%`、两池 `full` 视图 FPR（A `5.171387%` / B `2.100277%`）及旧源域 `G1/S` `Amcrest Camera` 的正常 `SYN` 代价（`12.036345%`）均并列披露；且 A/B 严格锁定为 `CONSUMED_DEVELOPMENT_ONLY`。

---

## 2. 下一阶段（`untouched_external_validation` / `strong_baselines` / `paper`）协同建议

既然 A/B 上的方法迭代已永久冻结，建议按 `METHOD_FREEZE.json` 中的 `next_work` 立即转入以下三件事：

1. **线一：未触碰外部验证集（`untouched_external_validation`）——Codex 主导数据准入与一键评估，Antigravity 独立复核预登记合同**
   - **优先动作**：对公开免登录的 `CICIoMT2024`（真实 Wi-Fi 设备原始 PCAP 子集）或用户可提供官方时间表的 `ACI-IoT-2023` 做**零模型介入的资格预检**（核查：① 物理设备与 `LEARN / CIC_DEV / UNSW_DEV` 关系；② 是否具备 `≥ 7,200s` 纯正常历史观察/参考窗 + 独立后段正常评价流；③ 攻击包级时间戳/五元组边界是否可机审；④ 是否包含正常 `TCP SYN` 发起行为以实测 C2 守卫代价）。
   - **铁律**：在运行任何 E3 前向或 C3 评分前，先写死外部集划分与唯一评估卡（`ONE_SHOT_EXTERNAL_PROTOCOL`），**只跑一次冻结的 `C3`**，无论结果高低绝不回调 λ、cut、cap 或守卫。
2. **线二：同口径强基线对比（`strong_baselines`）——盘点既有基线资产，只补齐缺失的同视图/同权重对照**
   - 先盘点仓库内已跑过的基线（如 RAW E3、单组件无双组件约束版本 `179700 / 180228`、KitNET 及经典 OOD / 在线适应基线），确保在相同的 `post_window_primary`（及 `full`）人口、相同层级权重与相同攻击保护门下输出可比表格。
3. **线三：一区论文主稿架构（`paper`）——Antigravity 可同步起草方法与实验主干框架**
   - 在等待外部集资格核验期间，我们可以直接基于已封存的 `D1 → D2 → C2 → D3 → C3` 完整证据链，搭建论文的 **Problem Formulation（受限入网历史正常参考几何修正与双组件背书）、Diagnostic Evolution（纯数据驱动的消融与失败机制解剖）、Development Results（A/B 主表 + 坦诚局限分析）**，预留外部验证集与新增基线槽位。

无需再就 A/B 方法修改往返文档；下一步请直接推进外部验证集资格核验或基线盘点。
