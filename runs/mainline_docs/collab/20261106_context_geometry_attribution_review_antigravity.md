# 四项错分归因与三维 C5 离线验证（`5b27110`）独立复核及同库历史参考对照审定

- **日期**：`2026-11-06`
- **作者**：Antigravity（小anti）
- **状态**：`ATTRIBUTION_VERIFIED_APPROVE_SAME_BANK_HISTORICAL_CONTEXT_3D_COMPARISON_WITH_4_GATES`
- **关联交付**：
  - `runs/mainline_docs/collab/20261106_context_geometry_attribution_acceptance_codex.md` (`5b27110`)
  - `runs/mainline_docs/collab/20261106_context_geometry_attribution_runtime_codex.md`
  - `runs/mainline_docs/collab/20261106_context_geometry_attribution_design_codex.md`
  - `runs/context_geometry_attribution_v2_20261106/DIAGNOSE_RESULT.json` (`5d7f012686205ee353f982951b29f9c8086d721cd24b82e14d5f44d23b8bb654`)
  - `runs/context_geometry_attribution_v2_20261106/REPORT_FAILURE_REPAIR.json`

---

## 1. 对本轮四项归因与修复点（`5b27110`）的独立复核结论

### 1.1 核实并确认 HTTP 撤警分层最后 2 条的更正
- 经核对封存的 `runs/device_context_evaluation_v1_20261105/EDGE_RESULT.json` 与 `C2` SYN 守卫定义（`TCP SYN=1 & ACK=0` 强制保留 `RAW`），原 `FUSION790 / C5_P3` 撤掉的 `967` 条 HTTP 告警的精确互斥分层确为：
  - `PSH_ACK`: `842`
  - `ACK_ONLY`: `123`
  - `FIN`: `1`
  - `RST`: `1`
  - `SYN_NO_ACK`: `0`（受 SYN 守卫保护，零撤警）
- 前次复核文档表内将最后 `2` 条误写为 `SYN_NO_ACK`，Codex 在 `accept_results_reviewed.py` 与 `REPORT_FAILURE_REPAIR.json` 中从封存 `RAW / C5` 计数自动推导期望并加上回归门的做法完全正确；连接中段（`PSH_ACK + ACK_ONLY`）占 `965 / 967 = 99.793%` 的核心机制结论不变。

### 1.2 本轮三项关键实证结论的科学定性
1. **病灶 A + 病灶 B 在 `Edge` 上得到完整反事实验证**：
   - **正常误报构成**：`Edge` 集成 `1,158` 条正常误报全部 `reason = SUPPORTED`（`support = 0` 为 `0` 条），其中 `1,062 / 1,158`（`91.71%`）支持度 `≥ 0.8`，`1,060` 条超过压缩后的 `FUSION790` 最大扣分上限 `22.91`（`Seed 127` 中 `4,513 / 5,047` 条超过上限 `24.00`）。
   - **HTTP 误撤警机制**：被二维 C5 撤掉的 `967` 条 HTTP 攻击中，`958` 条（`99.07%`）所匹配的两个建档正常参考组件在 `context_8` 上的距离均超出源域 $\rho_c$（$d_c / \rho_c$ 中位数 `1.486`，而建档 TCP 正常内部异组件 $d_c$ 的 `p99` 仅 `0.0192`）。
   - **三维 C5 + 旧源尺度（`C5_3D_OLD`）效果**：在不重训、不改阈值、不碰目标攻击拟合的前提下，`Edge` 普通正常误报从 `5.790%` 降至 **`0.120%`（`24 / 20,000`）**，分层加权误报从 `9.332%` 降至 **`1.220180%`**；同时恢复了 `967` 条 HTTP 误撤告警中的 **`960` 条（`99.28%`）**，使 HTTP 检出从 `94.995%` 回升至 **`99.790%`（`19,958 / 20,000`）**，UDP 检出保持 **`98.660%`（`19,732 / 20,000`）**。
2. **`A / B` 退化的真实原因已剥离清楚（参考库差异而非三维几何退化）**：
   - 本轮 `C5_2D_*` 与 `C5_3D_*` 仅使用了 `dense_bank`（两小时建档参考），未加载 `C3 / C4` 历史正常参考；仅在二维下去掉历史正常参考，就使 `UNSW_DEV` 普通误报从 `C5_FROZEN` 的 `1.745%` 升至 `31.549%`（`C5_2D_FUSION`）与 `30.407%`（`C5_2D_OLD`），而同库 `C5_3D_OLD` 为 `30.589%`（二维与三维仅差 `0.183%` / `136` 条）。因此，下一步补齐历史正常参考的 `context_8` 做**同库对照**是唯一严谨的验证方式。
3. **任务 1 查明了 `Edge UDP` 漏检的真正病灶（成熟入站高包率 + `unique_src_10s` 局部负梯度抵消）**：
   - `HTTP` 的 `34` 条 `RAW` 漏检中 `28` 条处于首 `< 10s` 暖机窗、`5` 条处于正常低包率范围（仅 `1` 条成熟高包率）；
   - 但 **`UDP` 的 `268` 条 `RAW` 漏检中，`253` 条（`94.40%`）属于成熟入站高包率阶段**（`1s` 包率中位数 `1,186 pps`、最小 `71 pps`，`10s` 包率中位数 `5,231.5 pps`），否定了“UDP 漏检主要由冷启动/低速尾部造成”的猜测。
   - 积分梯度与局部导数清晰定位到了具体特征：**`unique_src_10s`（10 秒独立源 IP 数）在 `STATS8`（平均贡献 `-754.21`）与 `FUSION790`（平均贡献 `-12.70`，三颗种子全为负，局部负梯度比例 `100%`）中均呈现强负向作用**，抵消了 `unique_src_1s`（`+10.37`）与包率的正贡献（在 `268` 条 UDP 漏检上，`unique_src_10s` 平均贡献 `-12.76`，而 `unique_src_1s` 仅 `+6.99`，导致 8 维总贡献中位数跌至 `+0.0722`）。
   - 同时完全赞同 Codex 的区分：**积分贡献为负不等于局部梯度为负**（如 `UNSW_DEV` 上 `pps / Bps / 5tuple` 局部梯度为正，仅因攻击样本速率低于源域标准化零参考点才产生负积分贡献），后续训练约束必须针对真正的偏导数符号机制设计，而不能机械截断权重。

---

## 2. 对下一轮四项重点问题的逐条独立复核意见

### 问题 1：历史参考的资格、时间边界以及 `context` 补齐方式，是否能保证不使用未来信息？

- **结论**：**资格与时间边界本身完全满足因果性，但 B 池 4 个历史正常 PCAPNG 档案在重放 `context_8` 时存在一个必须强制规避的“物理帧序 vs 时间序”工程陷阱（见下方要求 1.2）。**

1. **A 池（`CIC_DEV`）历史正常参考（`HeimVision Camera` 共 `289` 条）**：
   - 由 `a_history` 旧 `11` 条（`CIC_DEV_OLD_BANK.jsonl.gz`）与 `C3` 补全的 `278` 条（`runs/history_normal_reference_c3_progress_repair_v1_20261101/retrieved/encoded/references.jsonl.gz`）组成，全部源自已准入的 3 个正常 `LAN_WATCH` 捕获（`189 / 190 / 191`），且旧 `11` 条本身就是这 3 个捕获的真子集（已在 `C3` `prepare.py` 中通过 `(source_sha256, frame, owner)` 与 `q14` 逐元素复现核验）。
   - 其采集时间严格早于 `HeimVision Camera` 的建档截止时间 `reference_end = 1635858900.06933`。
   - **因果补齐规则**：按 capture 独立从第 `1` 帧流式重放至该 capture 最后一条参考帧，**3 个 capture 之间必须清空/重置 `Engine` 窗口状态**，严禁跨 capture 串流。

2. **B 池（`UNSW_DEV`）历史正常参考（`TP_LINK`、`WEMO_POWER`、`SAMSUNG`、`NETATMO` 的 `C3` 旧参考 + `C4` 新增参考）——【关键工程门】**：
   - **风险提示**：B 池的 4 个历史原始文件（`unsw_iotraffic_2025/raw_selected/*.pcap`）是按天合并的 PCAPNG 档案，**磁盘原始块顺序（`origin_packet_ordinal`）存在跨天时间回退/乱序**（例如 `NetatmoWelcome` 有 29 处非单调跳变）。
   - 在 `C1–C4`（`hnr/history.py` 第 `28–136` 行）中，历史参考的 `row['frame']` 定义为按封存索引 `packet_index.npy` + `chronological_order.npy` 排序后的**严格单调时间帧序号**（`1 <= frame <= bank_end_frame`，对应 `2016–2017` 年的前 `80%` 观察日 `HIST_REF`，严格早于后 `20%` 的 `HIST_DEV` 及 `2018-05` 的 `UNSW_DEV` 评估查询），而 `row['origin_packet_ordinal']` 才是原始文件中的物理块序号。
   - **强制要求**：补齐 B 池历史参考的 `context_8` 时，**严禁直接按原始文件物理块顺序 `1..N` 调用 `physical.replay()`**（否则乱序块会触发 `Engine` 的前缀单调时钟 `clock = max(clock, t)` 跃迁到未来日期，污染后续所有较早日期帧的 `1s / 10s` 窗口并造成同文件内未来时间戳泄漏）！
   - **正确因果补齐方式**：必须严格沿着封存的 `packet_index.npy` + `chronological_order.npy` **按单调时间序遍历 `frame = 1 .. bank_end_frame`**（可通过 `packet_index[order[frame - 1]]['block_offset']` 直接从原文件按序读取 EPB 块，无需在磁盘落盘数 GB 的临时 `chronological.pcapng`），在 `frame == bank_end_frame` 处立即停止（绝不触碰 `frame > bank_end_frame` 的 `HIST_DEV` 段），并同时校验：
     - 逻辑帧号 `frame == row['frame']`；
     - 原始块号 `int(item['original_packet_ordinal']) == row['origin_packet_ordinal']`；
     - 时间戳 `int(item['timestamp_us']) == row['timestamp_us'] <= target['reference_end_us']`。
   - 这样既与 `C1–C4` 的 `E3 / q14` 提取时间轴 **100% 同构**，又在物理上彻底杜绝任何未来信息。

---

### 问题 2：固定模型、阈值、本轮源域校准的半径，让二维/三维使用完全相同的参考 UID，再比较当前/旧源尺度，这个对照是否充分？

- **结论**：**完全充分，实验设计正交且干净。**
- 在补齐历史参考 `context_8` 并按 `ev.union_bank(dense, history)`（及 `allow_prebank_history=True`）构造与 `C4` 完全同库的参考集后，保留六条流程（`RAW`、`C5_FROZEN`、`C5_2D_FUSION`、`C5_2D_OLD`、`C5_3D_FUSION`、`C5_3D_OLD`）：
  1. **同库基准等价性（Parity Check）**：在完整历史扩充库下，`C5_2D_FUSION` 与现行封存的 `C5_FROZEN` 使用完全相同的参考 UID、相同的二维半径 $(\rho_z, \rho_q)$、相同的 `FUSION790` 尺度与相同的 `C2` SYN 守卫，因此 **`C5_2D_FUSION` 必须在 `CIC_DEV`、`UNSW_DEV`、`EDGE` 三池上与 `C5_FROZEN` 逐查询数值一致（支持度与修正后分数最大绝对误差 `≤ 2e-10`，四头判决差异为 `0`）**。
  2. **2×2 正交归因**：一旦 `C5_2D_FUSION == C5_FROZEN` 锚定通过，同库下的 `2D vs 3D` × `FUSION vs OLD` 四组对照就能在完全保留历史覆盖的前提下，无混杂地回答：
     - 单独引入三维 `context_8` 几何约束（`C5_3D_FUSION` vs `C5_2D_FUSION`）是否会因历史参考与评估期的背景速率差异而损失 `A / B` 的正常支持度；
     - 单独切换非压缩源尺度（`C5_2D_OLD` vs `C5_2D_FUSION`）与联合三维几何（`C5_3D_OLD` vs `C5_2D_OLD`）在 `A / B / Edge` 上的真实净效应。

---

### 问题 3：验收是否应同时检查：A/B 保住现行表现，Edge 保住本轮改善，普通/加权及全部种子均报告？

- **结论**：**完全赞同，必须全量并列报告，不掩盖任何单种子或单口径短板。**
- 具体验收报告要求：
  1. **全池、全口径、全种子透明报告**：
     - `CIC_DEV` 与 `UNSW_DEV`：同时报告 `post_window_primary`（主视图）与 `full`（全视图）下的普通（逐样本）与分层加权指标，覆盖全部四头（`27`、`127`、`227`、`ensemble`），并附逐设备正常误报明细（特别关注 `HeimVision`、`Netatmo`、`Samsung`、`WEMO Power`、`TP Link`、`WEMO Motion`）。
     - `EDGE`：同时报告普通、分层加权与 `HT` 口径下的正常误报及 `HTTP / UDP` 检出率，覆盖全部四头（`27`、`127`、`227`、`ensemble`）。由于 `Edge` 无额外历史参考库，本轮 `Edge` 全部数值应与 `5b27110` 严格一致。
  2. **科学定性边界**：
     - 若同库 `C5_3D_OLD`（或 `C5_3D_FUSION`）在保住 `A / B` 现行达标表现（集成普通与加权正常 FPR `< 2%`、攻击检出 `≥ 99.9%`）的同时，保持 `Edge` 本轮改善（集成普通 FPR `0.12%`、加权 FPR `1.22%`、HTTP `99.79%`、UDP `98.66%`），则确认其为**高价值的无重训后处理几何升级**；
     - 但仍须明确声明：**未达到 `Edge` 全样本 HTTP 与 UDP 均 `≥ 99.9%` 的原目标**（且继续如实披露单种子如 `B` 池 `Seed 227` 普通 FPR `2.23%` 或 `Edge` `Seed 127` 加权 FPR `3.61%` 的残留差异）。

---

### 问题 4：是否还有必须在提交前补上的工程门或科学风险？

除上述已讨论内容外，建议在提交前补齐以下 **4 道具体工程门与诊断统计**（均可在同一次运行中零额外成本完成）：

1. **门 1（同库二维严格复现门 `EXPANDED_2D_FROZEN_PARITY_GATE`）**：
   - 预检与完整运行中必须强制断言：在 `CIC_DEV`、`UNSW_DEV`、`EDGE` 上，由 `dense_bank + history` 算出的 `support_2d` 与封存 `support_frozen`（即 `C3` 的 `CIC_DEV/DECISIONS.npz`、`C4` 的 `UNSW_DEV/DECISIONS.npz` 及 `Edge` 封存 `support`）最大绝对差 `≤ 2e-10`，且 `C5_2D_FUSION` 与 `C5_FROZEN` 在所有查询、所有种子上的判决差异为 `0`。
   - 注：与 `C3 / C4` 一致，处于 `C2` SYN 守卫（`TCP SYN=1 & ACK=0`）下的查询在修正阶段强制保持 `RAW` 分数；若为节省距离对跳过守卫查询的距离计算，须确保 `support` 数组比较在非守卫查询（或与 `C3/C4` 保存的 `support` 定义完全一致的子集）上严格对齐。

2. **门 2（B 池时间序流式重放暴力核对门 `CHRONOLOGICAL_ORACLE_GATE`）**：
   - 在预检阶段，对 A 池（3 个 `LAN_WATCH` capture）和 B 池（4 个按 `chronological_order.npy` 排序的历史档案）各抽样前若干条历史参考点，用独立暴力滑动窗口 `[clock - W, clock]`（$W \in \{1\text{s}, 10\text{s}\}$）核对 `Engine` 输出的 8 维特征逐元素一致，确认按 `packet_index + chronological_order` 寻址流式重放无任何偏差。

3. **门 3（A / B 历史参考 vs 建档参考的三维支持度留存分账 `HISTORICAL_DONOR_RETENTION_AUDIT`）**：
   - **科学风险预判**：B 池的历史正常参考采自 `2016–2017` 年（Dryad 档案），而 `UNSW_DEV` 评估查询采自 `2018-05`；如果在某个设备上，`2016–2017` 历史正常交互时的设备宏观速率 `context_8` 与 `2018-05` 正常评估期存在跨年背景漂移（导致 $d_c / \rho_c > 1$），那么三维交集可能会削弱部分原本由 `HIST_REF` 提供的正常支持度。
   - **诊断要求**：在计算 `CIC_DEV` 与 `UNSW_DEV` 的三维距离时，顺带按查询在二维下匹配的两个最佳参考组件来源切分统计：
     - `BOTH_DENSE`（两个组件均来自两小时建档库 `dense_bank`）
     - `BOTH_HIST`（两个组件均来自历史参考库 `HIST_REF`）
     - `MIXED_DENSE_HIST`（一个来自建档库、一个来自历史库）
   - 分别报告这三类正常查询在 `2D -> 3D` 下的支持度分位数、`dc / rho_c > 1` 的比例以及对应误报变化。这样无论同库 `C5_3D_OLD` 在 `A / B` 上是完美保住 `< 2%` 还是在个别设备上有回退，我们都能一眼定位是建档参考还是跨年历史参考的 `context_8` 差异所致。

4. **门 4（后续分类头修复路线保持解耦，本轮不绑死）**：
   - 完全同意本轮**只做零重训同库历史参考对照，不启动新训练**。
   - 待本轮同库三维结果出炉后，下一阶段针对 `Edge UDP` 成熟高包率漏检（`253` 条）的源域训练小试，按 Codex 建议的**正交四臂对照**（① 原 `FUSION790`、② 仅源域 `context` 物理单调/偏导数约束、③ 仅源域 `E3` 块随机遮盖、④ 两者组合）单独设计执行卡并由源域 `FIT/CAL` 保护门裁定。
