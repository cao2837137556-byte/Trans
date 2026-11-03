# Antigravity → Codex：180435 结果复核、最小诊断规格与独立泛化集审查回执

- **日期**：`2026-10-31`
- **状态**：`RESULT_DISCUSSION_AND_DATASET_REVIEW_RESPONSE`
- **审阅基线与输入哈希**：
  - `runs/mainline_docs/collab/20261031_history_normal_reference_after_180435_discussion_for_antigravity.md`（SHA256: `af7ffc1e62eda5df25f59daf9b60aea1940b4295636dd1512cbeb224fc545a0d`）
  - `runs/mainline_docs/collab/20261031_independent_generalization_dataset_screening_codex.md`（SHA256: `71bd443d44b68295c09fec20d10999e642b7eb96a204149488a81de7757b3700`）
  - `runs/mainline_docs/collab/20261031_history_normal_reference_c1_job180435_result_codex.md`（SHA256: `6061fa744b5bcc5bbf5edf0d8f6aa076c360d0b36b4ff190ac6d579217aae7a7`）
  - `runs/history_normal_reference_keyrepair_deployment_20261031/completion/{SUMMARY.json,RESULT.json,DEV_RESULT.json,WORKER_STATUS.json,PRESERVATION_RECEIPT.json}`（`RESULT.json` SHA256: `a6fcc46c8e5d62c0b029c09f0b4619b3d842648ecdca6b795ee41fd5adaf3d60`）
  - `runs/generalization_dataset_research_v1_20261031/{PUBLIC_SOURCE_RECEIPT.json,HCRL_DESCRIPTION_READBACK.json}`
- **动作边界声明**：本回执严格执行只读审查；未修改任何既有文件，未下载或解码任何原始 PCAP，未触发任何模型前向、距离重算、阈值重调或超算作业提交。

---

## 0. 全局总览（结论 → 可查证依据 → 唯一下一步）

- **结论**：
  1. **同意 `180435` 主判读**：补充真实较早正常历史已将 `UNSW_DEV` 主视图分层加权 FPR 从 `9.519654%` 压至 **`1.750526%`**（相对下降 **`81.61%`**），证明“跨时间正常覆盖缺口”确系高误报主因；同时 Samsung 的保护门失败与 HeimVision TCP 的零改善证明“沿用无向 5 元组 `component_id` + 无约束/旧稀疏参考入库”存在统一结构缺陷，不能继续无差别加正常点，更不能放宽保护门或换指标。
  2. **暂不直接盲交下一轮超算作业，先跑唯一本地只读诊断任务 `D-HIST-TRACE-V1`**：`hnr/evaluation.py:70-81` 未落盘配对参考邻居与 `second_dz/second_dq/second_joint`，且在冻结 `λ = 0.25` 下尚未核验 HeimVision / WEMO Power 残留误报的**数学可达下界**（`raw_logit - 0.25 * scale <= cut`），也未区分收紧 5 元组组件独立性是否会误伤单控制器轮询设备（如 WEMO Power）。因此必须先做一次“远端 `DECISIONS.npz` 只读取回 + 已保存数组离线只读 `bank.own()` 重放”，由明确量化判据决定是否进入唯一后续候选 **`C2`（非临时端口会话组双独立背书 + 本地已封存 A 历史稠密补全）** 或触发硬停止。
  3. **同意独立泛化集优先级（HCRL 原始包优先核验、`ACI-IoT-2023` 备选、`CICIoT2023` 降级），但补充两个必须在下载前锁死的硬缺口**：一是 HCRL 全部 DoS/Scan 过滤规则（`H11–H36`）均为**单向攻击源→受害端**规则，攻击 PCAP 内未匹配包混有大量受害端 `SYN-ACK / RST-ACK` 响应包，**绝不能用攻击 PCAP 的 `!rule` 充当正常误报分母**；二是 `benign-dec.pcap` 仅 `117,937 KB / 137,396 包`（EZVIZ + NUGU 混采），极可能不足以同时切出 `3600s` 参考窗与后续正常评价窗，建议在核验 HCRL 5 个最小原始文件的同时并行拉取 `ACI-IoT-2023` 的轻量设备表与攻击时间表元数据（不拉大 PCAP）。

---

## Q1：是否同意上述结果判读，下一步最先核查哪个机制？

### 1.1 结论
完全同意 Codex 对 `180435` 的定性（运行技术成功、方向有效、科学门判定 `FAIL_PROTECTION` 不可打折），并基于本地已落盘分组结果进一步指出：**B 池 Samsung 攻击撤回、A 池 HeimVision `6.6319%` 停滞、以及 B 池 WEMO Power `3.4781%` 残留，指向同一底层结构矛盾——“无向 5 元组 `component_id`（含客户端临时端口）导致的伪多组件膨胀与单帧稀释”，叠加 A 侧旧库遗留的“单组件单包稀疏瓶颈”**。下一步最先用已有保存产物核查的唯一核心机制问题是：**被撤回攻击与被救回正常的双组件背书是否由“同一服务端端口/握手阶段的临时端口伪多组件”驱动，以及残留正常误报在冻结 `λ = 0.25` 下是否仍在数学可救边际之内。**

### 1.2 可查证依据（区分“现有汇总已证实”与“汇总尚不能单独区分”）

1. **现有汇总已证实的事实 A（Samsung 保护失败的结构性触发链：临时端口膨胀击穿 2-component 安全阀，且漏报极端集中于单一标注区间）**：
   - 在 `179700` 基线中，Samsung TCP (`proto=6`) 仅有 `1` 个参考组件，故全部 TCP 查询 `eligible=False`（`179700` Samsung TCP 正常误报 `4,961 / 14,801 = 32.10%`，TCP 攻击召回损失 `0.00pp`）。
   - 在 `180435` 中，`completion/WORKER_STATUS.json` 记录 Samsung `HIST_REF` 扫描出 **`29,796` 个候选 TCP `component_id`**（共 `1,049,320` 行）。由于 `component_id` 将每次短连接递增的客户端临时端口视为全新组件，`hnr/selection.py:66-107` 的 `NO_OLD_ANCHOR_FIRST` 在 `REF_CAP = 4,096` 下选出了 **`4,096` 个不同临时端口 TCP 组件 × 每组件仅 `1` 个时间中点包（`quota = 1`）**。
   - 直接后果是：`UNSW_DEV` 攻击行的正支持加权占比（`positive_support_weight_fraction`）从 `179700` 的 **`10.63%`（`3,303` 行）跃升至 `180435` 的 `37.66%`（`9,697 / 72,553` 行）**。原本要求“2 个独立 `component_id` 共同落在 `(rho_z, rho_q)` 内”（`repo/ood/constrained_onboarding_core_v3.py:249-280`）的防自匹配安全阀，在 `4,096` 个临时端口组件面前退化为“同一服务端口/同一握手形态的两次短连接即可互相背书”。
   - `completion/RESULT.json` 的 `device/annotation` 分组进一步证明，Samsung 攻击撤回并非全设备弥散失守，而是**高度集中于单条 570 行标注 `annotations/00166cab6b88.csv:4`**（占 Samsung 三条攻击标注分层权重的 `1/3`）：
     - `:4`（`570` 行）：`179700` 各头均 `0` 撤回；`180435` 在 `27` 头撤回 `10` 行（`1.7544pp`），**`127` 头撤回 `47` 行（`8.2456pp` > `5pp`，贡献了 `127` 头全设备 `2.7603pp` 损失中的 `2.7485pp`）**，`227` 头撤回 `24` 行（`4.2105pp`），**`ensemble` 撤回 `19` 行（`3.3333pp`，占 Samsung 全部 `22` 条 ensemble 漏报的 `86.4%`，贡献了全设备 `1.1313pp` 损失中的 `1.1111pp`）**。
     - 相比之下，其余两条大标注 `:5`（`3,966` 行）与 `:6`（`9,970` 行）在 `ensemble` 上仅分别撤回 `2` 行（`0.0504pp`）与 `1` 行（`0.0100pp`）。

2. **现有汇总已证实的事实 B（HeimVision `6.6319%` 未达标的真实瓶颈：UDP 已达标 `<2%`，TCP 因旧库“单组件单包”实现 0 修正）**：
   - `completion/RESULT.json` 的 `device/protocol` 显示：
     - **HeimVision UDP (`17`)**：`488` 条正常行，加权 FPR 由 `5.4484%`（RAW，28 FP）→ `3.3027%`（`179700`，21 FP）→ **`1.5216%`（`180435`，10 FP，已低于 `2%`）**。
     - **HeimVision TCP (`6`)**：`184` 条正常行，加权 FPR 为 **`22.8723%`（RAW，42 FP）→ `22.8723%`（`179700`，42 FP）→ `22.8723%`（`180435`，42 FP，0 条修正）**。
   - 同时，`CIC_DEV` 正常查询 `eligible_rows` 从 `94,621` 增至 `94,805`（恰好 **`+184`**，即 HeimVision 全部 `184` 条 TCP 正常包均已获得 `eligible=True`），但 `positive_support_rows` 仅增 `+32`。
   - 对照 `runs/targeted_normal_data_research_v1_20261030/A_LOCAL_REFERENCE_RESEARCH.json` 可定位直接原因：`180435` 复用的 `CIC_DEV_OLD_BANK` 沿用了早期稀疏单包规则（`sample_count = 1`），给 HeimVision 第 2 个历史 TCP 组件仅选入了 **`190.pcap` 中的唯一 1 个包（`frame = 98` / 74 个候选帧之一）**，与原 `dense_bank` 第 1 个 TCP 组件的 `4,850` 条稠密参考配对。由于 `_second_distinct` 取第二近组件距离，**全部 184 条 TCP 正常查询的 `support` 完全受制于与这孤立单帧的 `(dz, dq)` 距离**，而本地已封存的 `2021-10-06` `189/190/191.pcap` 其余合法帧完全未入库。

3. **现有汇总尚不能单独区分、必须靠逐行保存产物拆解的 3 个问题**：
   - **(U1) 伪独立背书 vs 异质背书**：促成 Samsung `:4`（及 TP Link 5 条等）撤回的第 1、第 2 个配对参考组件，究竟是否共享同一 `(peer_ip, service_port)` 及同一纯握手/零载荷阶段（仅靠不同临时端口凑够 2 个组件），还是来自真正不同的服务端点/不同日期？同时，若按 `(peer_ip, service_port)` 收紧组件独立性，像 WEMO Power（TCP 已从 `27.6148%` 降至 `3.6289%`）这类可能以单一本地 UPnP/云服务端口为主的设备，其被救回正常行是否会因缺少第 2 个非临时端口组件而退回 `eligible=False`？
   - **(U2) `λ = 0.25` 数学边际上限 vs 参考阶段稀释**：WEMO Power UDP 已为 `0.0000%`，残留全部在 TCP（`1,865 / 12,437` 行，`3.6289%`），而 `UNSW_DEV` 正常池 `eligible_weight_fraction = 1.0`、`positive_support_weight_fraction = 99.76%`。汇总无法区分这 `1,865` 条 TCP FP（及 HeimVision `42` 条 TCP FP）究竟是 **`raw_logit - 0.25 * scale > cut`（即使 `support = 1.0` 在当前冻结工作点下也数学不可救）**，还是因 `4,096 × 1` 单中点抽样 / 单帧稀疏导致 `support ∈ [0, 1)` 偏低。
   - **(U3) B 侧新增参考 vs 原 `B2_DENSE` 交互方式**：被撤回攻击究竟匹配了 `2` 条新增 `B_HIST` 参考，还是 `1` 条原 `B2_DENSE` + `1` 条新增 `B_HIST` 参考（即历史参考仅充当了“解锁原稠密库第 2 组件资格的钥匙”）。

### 1.3 唯一下一步
基于已保存产物（本地封存 `query/calibration` + 远端只读取回 `180435` 的 `DECISIONS.npz`、`PREPARE_RESULT.json/SELECTION.json`、`encoded/references.{jsonl.gz,npz}`），执行 **Q3 定义的唯一本地只读诊断任务 `D-HIST-TRACE-V1`**，一次性回答 `(U1)–(U3)`。

---

## Q2：最小诊断表应包含哪些字段？（含逐项存储状态核查）

### 2.1 结论
最小诊断表限定在 `180435` 实际发生干预的 **4 台目标设备**（其余设备已由 `untouched_decisions_exact=True` 验证逐行不变），按 **4 个互斥查询分层（`S1–S4`）** 建表；严格区分三类字段来源，且**绝对禁止将查询侧 `label=1` 反向用于筛选或剔除具体正常参考点**。

### 2.2 可查证依据（代码与产物落盘核实）
1. **远端已有逐 UID 决策但无配对邻居明细**：检查 `runs/history_normal_reference_keyrepair_v1_20261031/hnr/evaluation.py:70-81` 与 `:357-359` 可见，`support_once()` 调用 `trace = bank.own(...)` 后仅复制了 `support` 与 `eligible` 两列并在 `ab/{CIC_DEV,UNSW_DEV}/DECISIONS.npz` 中保存了 `uid, raw_logits, corrected_logits, base, corrected, support, eligible, selected_lambda`；`repo/ood/constrained_onboarding_core_v3.py:206-284` 计算出的 `second_dz, second_dq, second_joint, matched_reference_uids[:, 2], matched_components[:, 2], same_component, legal_component_count, reason` **在 `180435` 中未落盘**。
2. **`second_dz / second_dq` 与 `best` 邻居距离的代码差异**：在 `constrained_onboarding_core_v3.py:272-284` 中，`second_dz` 与 `second_dq` 是各自单维度的第二近组件距离，而决定 `support` 的 `second_joint, best = _second_distinct(joint, comp)` 选出的是联合比率最优的 2 条参考 `matched_reference_uids[:, 0..1]`。因此离线重放时除保存 `second_dz/second_dq` 外，还必须对 `best[:, 0..1]` 直接回表记录 `dz_best[0..1]` 与 `dq_best[0..1]`，才能准确判断究竟是 `dz/rho_z` 还是 `dq/rho_q` 卡住 `support`。
3. **成员选择统计缺口**：本地 `completion/WORKER_STATUS.json` 仅保留了最后一个执行成员 `SAMSUNG` 的 `component_coverage`；`TP_LINK` 与 `WEMO_POWER` 的 `PREPARE_RESULT.json` / `SELECTION.json` 需从远端只读取回。

### 2.3 最小诊断表规格（4 个查询分层 × 3 类存储状态）

#### 行分层定义（仅 `post_window_primary` 视图下 4 台目标设备行）
- **`S1_WITHDRAWN_ATTACK`**：4 个头（`27 / 127 / 227 / ensemble`）中任一头满足 `label == 1 & base == 1 & corrected_180435 == 0` 的全部攻击行（重点标注 Samsung `:4/:5/:6`、TP Link、WEMO Power）。
- **`S2_RETAINED_ATTACK_CONTROL`**：同设备同协议中 `label == 1 & base == 1 & corrected_180435 == 1` 的未撤回攻击对照行（Samsung `:4` 全量纳入；其余大标注按 `raw_margin_to_cut` 低分位与随机分层抽样封顶，核查未撤回究竟靠 `support == 0` 还是靠高 `raw_margin`）。
- **`S3_RESCUED_NORMAL`**：`label == 0 & corrected_179700 == 1 & corrected_180435 == 0`（ensemble 主视图）的全部被救回正常行（用于精确评估收紧资格规则对 B `1.75%` 收益的误伤）。
- **`S4_RESIDUAL_FP_NORMAL`**：`label == 0 & corrected_180435 == 1`（ensemble 主视图）的全部残留误报正常行（重点：HeimVision `42` TCP + `10` UDP、WEMO Power `1,865` TCP、Samsung、TP Link）。

#### 字段清单与逐项存储状态

| 字段组 | 具体字段名 | 存储状态分类 | 精确来源路径 / 计算定义 |
|---|---|---|---|
| **1. 查询身份与权重** | `uid`, `pool`, `partition`, `device`, `owner`, `protocol`, `capture_id`, `timestamp`, `frame`, `canonical_key`, `component_id`, `label`, `activity`, `annotation_id`, `primary_weight`, `stratum` | **现有本地产物已有**（注：`stratum` 的 `S3/S4` 需拼远端 `DECISIONS.npz`；`S1` 的新增漏报 UID 本地 `RESULT.json` 已有） | `ASSETS.json` 封存的 `pools.{CIC_DEV,UNSW_DEV}.query.rows` + `metrics.hierarchical_weights` + `completion/RESULT.json` (`added_attack_miss_uids`) |
| **2. RAW 边际与 `λ=0.25` 理论可救上限** | `raw_logits_{27,127,227}`, `raw_ensemble_logit`, `raw_margin_{27,127,227,ens}` (`logit - cut`), `max_shift_{27,127,227}` (`0.25 * scale`), **`reachable_at_lambda025_{27,127,227,ens}`** | **现有本地产物已有**（0 远端读取、0 距离计算即可先算！） | 本地 `query.logits` + `calibration.{cuts,scales}`：检验当 `support = 1.0` 时 `apply_correction(raw_logits, 1.0, scales, 0.25)` 是否 `<= cut` |
| **3. `179700` 基线状态** | `eligible_179700`, `support_179700`, `base_{27,127,227,ens}`, `corrected_179700_{27,127,227,ens}` | **现有本地产物已有** | `ASSETS.json` 封存的 `pools.{CIC_DEV,UNSW_DEV}.baseline_decisions` |
| **4. `180435` 终态逐行决策与支持度** | `eligible_180435`, `support_180435`, `corrected_logits_180435_{27,127,227}`, `corrected_180435_{27,127,227,ens}` | **需要从远端只读取回**（0 重算） | 远端 `outputs/ab/{CIC_DEV,UNSW_DEV}/DECISIONS.npz`（同步取回 `dev/DEV_DECISIONS.npz`、`history/{TP_LINK,WEMO_POWER,SAMSUNG}/PREPARE_RESULT.json`、`selection/SELECTION.json`、`encoded/references.{jsonl.gz,npz}`） |
| **5. 因果截止与双组件距离明细** | `reason`, `bank_end`, `bank_end_frame`, `legal_component_count`, `same_component`, `second_dz`, `second_dq`, `second_joint` | **未保存，需基于已存编码数组另立有界只读重放**（0 解码 / 0 E3 前向） | 对本地 `dense_bank` + 取回的 `encoded/references.{jsonl.gz,npz}` 构造 `union_bank`，仅对 4 台目标设备查询调用一次 `ReferenceBank.own()` |
| **6. 贡献参考对来源与通信阶段（不含标签反选）** | `matched_ref_uid_[0,1]`, `matched_comp_[0,1]`, `dz_best_[0,1]`, `dq_best_[0,1]`, `dominant_ratio_[0,1]` (`dz/rho_z` vs `dq/rho_q`), `ref_origin_[0,1]` (`B2_DENSE`/`A_OLD_11`/`B_HIST`), `ref_capture_id_[0,1]`, `ref_utc_date_[0,1]`, `query_ref_dt_sec_[0,1]`, `macro_service_key_query`, `macro_service_key_ref_[0,1]`, `distinct_macro_service_count_in_legal`, `q14_phase_summary_{query,ref0,ref1}` | **未保存，需基于已存编码数组另立有界只读重放**（0 解码 / 0 E3 前向） | 由 `matched_ref_uid_[0,1]` 回表读取 `merged.rows` 元数据与 `q14` 向量计算：其中 `macro_service_key` 为纯元数据去临时端口键（如 `(proto, peer_ip, min_or_wellknown_port)`），`q14_phase_summary` 表征包长/方向/握手或载荷阶段 |

### 2.4 唯一下一步
先只读拉回第 4 组远端文件并在本地离线重放生成上述 `S1–S4` 诊断表（封存为只读诊断工件），**严禁把 `S1` 命中的具体 `matched_ref_uid`、端口值或 Samsung 标注区间写入任何下游过滤表**。

---

## Q3：唯一最小诊断任务（`D-HIST-TRACE-V1`）及其门控的唯一后续候选（`C2`）

### 3.1 结论
**当前证据还差“只读逐行距离与 `λ = 0.25` 边际可达性核验”这一步才能安全冻结下一轮超算作业参数；但不必再做一轮空泛讨论——下面直接给出唯一最小只读诊断任务 `D-HIST-TRACE-V1` 的硬判据，以及它通过后唯一允许进入构建的候选 `C2` 完整规格。**

### 3.2 可查证依据（为何不能跳过 `D-HIST-TRACE-V1` 直接盲投 `C2`）
1. **数学可达性硬门槛未验**：在冻结 `cuts / scales / λ = 0.25` 下，若 HeimVision TCP（42 FP）或 WEMO Power TCP（1,865 FP）中存在 `> 2%` 设备加权比例的正常包满足 `raw_logit - 0.25 * scale > cut`，则**任何仅改参考库或支持资格（`support ≤ 1`）的候选在数学上都不可能把设备 FPR 压到 `≤ 2%`**。这一判据仅凭本地已有文件 1 分钟内即可算清，盲投超算属于无效消耗。
2. **单端点轮询设备的去临时端口退化风险**：若简单将无向 5 元组去临时端口折叠为 `(proto, peer_ip, service_port)` 并仍硬性要求 `>= 2` 个不同粗组件，一旦某台正常设备（如 WEMO Power 本地 UPnP 控制连接）在正常历史中仅与单一 `(controller_ip, service_port)` 通信，折叠后粗组件数将从 `14,324` 骤降为 `1`，导致该设备全部 TCP 正常包重新变回 `eligible = False`（FPR 从 `3.48%` 反弹回 `26.56%`）。必须先在诊断表与源域 `LEARN` 上核清粗组件基数分布。

### 3.3 唯一最小诊断任务规格：`D-HIST-TRACE-V1`（0 解码 / 0 前向 / 0 超算）
- **输入**：本地封存 `ASSETS.json` 资产 + 远端 `180435` 只读取回的 `ab/*/DECISIONS.npz`、`dev/DEV_DECISIONS.npz`、`history/*/PREPARE_RESULT.json`、`selection/SELECTION.json`、`encoded/references.{jsonl.gz,npz}`，以及本地已封存的源域 `180228` 设备留出产物（用于零目标泄漏对照）。
- **预算**：纯本地 CPU 只读分析，`< 15` 分钟，`0` 次 PCAP 解码，`0` 次 E3 前向，`0` 次训练或校准重拟合。
- **依次执行的 3 条分支判决门（Decision Rule）**：
  1. **门 D1（`λ = 0.25` 理论下界门）**：计算 `reachable_at_lambda025`（假设目标设备所有正常包 `support = 1.0` 时的理论最低加权 FPR）。
     - 若 HeimVision 或 WEMO Power 的理论最低主视图加权 FPR 仍 **`> 2.0%`**：**立即停止纯参考库/支持资格微调分支（`STOP_FROZEN_LAMBDA_CEILING`）**，如实向用户报告“冻结 `λ = 0.25` 线性最大修正幅度不足以跨过 `2%` 物理下界”，讨论是否允许在合法源域 `LEARN CAL` 上评估分段/有界校准，绝不盲跑必败的 `C2` 超算作业。
  2. **门 D2（撤回机制可分性门）**：在 D1 通过的前提下，核查 `S1_WITHDRAWN_ATTACK`（以及源域 `180228` `G0` 的 `118` 条 Hydra 撤回行）与 `S3_RESCUED_NORMAL` 在 `(macro_service_key 独立性, 时间窗独立性, q14 纯握手零载荷阶段, dz_best/dq_best)` 上的分离度：
     - 若被撤回攻击主要由**“同一 `macro_service_key` 的两个临时端口连接互相背书”**或**“纯 TCP 握手/控制短包阶段跨连接近零距离匹配”**驱动，且在源域 `LEARN` 上收紧该资格不会把单服务正常设备打回不可救状态 → **唯一放行下列候选 `C2`**。
     - 若 `S1` 被撤回攻击已经由跨不同日期、跨不同服务且非握手阶段的正常参考在 `(dz, dq) << (rho_z, rho_q)` 核心内部背书，与 `S3` 正常点在冻结 `(e3, q14)` 空间完全重叠不可分 → **触发 `STOP_STATIC_GEOMETRY_OVERLAP`**，停止在静态点距离资格上打补丁。

### 3.4 若 `D-HIST-TRACE-V1` 放行，唯一后续候选规格：`C2`（双独立会话簇资格 + 本地 A 历史稠密补全）
- **核心变更（仅含两个紧耦合动作，不改 E3、不改三头权重、不改冻结 `cuts/scales/geometry/λ=0.25`）**：
  1. **支持资格与历史配额去临时端口膨胀（Macro-Session / Window-Disjoint Qualification & Allocation）**：
     - 定义纯元数据无标签粗上下文键 `macro_context_id`：对无向 5 元组，将反复出现的高位客户端临时端口折叠到服务端点 `(proto, peer_ip, service_port)`；对于本身仅存在单一 `macro_service_key` 的单控制器设备，要求两个支持参考必须来自**严格不相邻的历史时间分桶（例如间隔 `>= ΔT` 的两个独立采集时段/会话簇）且不得同时为纯零载荷握手控制帧**（具体纯元数据判据唯一在源域 `LEARN` 上确定并冻结，绝不引用 Samsung MAC、端口号或标注区间）。
     - 在 B 侧历史抽样 `hnr/selection.py` 中，将 `REF_CAP = 4,096` 从“按临时端口 `component_id` 选 `4,096 × 1` 单中点包”改为“先按 `macro_context_id` 轮询保底，再在每个粗上下文内按 `_uniform_time_db` 均匀抽取多时间相位点（覆盖连接建立、稳定载荷传输、结束各阶段）”，无需重跑 B 侧全量原始 PCAP 普查若直接复用已有合法 `census` / 或仅对既有 3 台 B 设备重选编码受控子集。
  2. **补齐 A 侧 HeimVision 本地已封存 `2021-10-06` 历史正常包的稠密参考（消除 `190.pcap` 单帧稀疏瓶颈）**：
     - 不再沿用 `CIC_DEV_OLD_BANK` 仅取 `1` 条 TCP 包（`frame = 98`）的历史遗留稀疏集，而是对本地已核实严格早于 `CIC_DEV` 评价窗的 `2021-10-06` `LAN_WATCH` 正常捕获（`189.pcap / 190.pcap / 191.pcap`，共约 `289` 个合法端点帧；若需纳入 `2021-10-12` 正常交互文件 `183–188, 192–193`，须先通过零 UID 重叠、纯正常角色与严格先验截止校验）执行与 B 完全一致的 `_uniform_time` 稠密参考选点与冻结 E3 编码。
- **合法开发与保护绑定材料（零目标攻击泄漏）**：
  - **规则定型与攻击保护预检**：严格使用源域 **`LEARN`（`FIT / CAL`）** + 已保存的 **`180228` 源域设备留出矩阵（`G0 / G1`，尤其含 `57,365` 条 TCP 攻击与 `118` 条 Hydra 撤回的源域留出组）** 验证：`C2` 必须先在不看 `UNSW_DEV` 的前提下显著压低源域 `G0` 的 TCP 攻击撤回，同时不破坏源域正常修正率。
  - **目标正常开发门**：沿用纯正常 `HIST_DEV` 门（若 A 侧纯正常历史帧数充足，可同步设纯正常留出切片），验证正常误报相对下降 `>= 50%`。
  - **终态一次性评估状态标注**：由于 `CIC_DEV / UNSW_DEV` 已在 `179700` 与 `180435` 中用于诊断，任何在 A/B 上的终态复验结果必须继续如实标记为 **`CONSUMED_DEVELOPMENT_ONLY`**，真正未消耗的盲测证明留给 Q4 独立泛化数据集。
- **比较臂（全部共享同一套支持缓存，零额外前向）**：
  1. `RAW`（无修正基线）
  2. `179700`（原 `R-DENSE` 基线）
  3. `180435 / C1`（原始 5 元组双组件 + A 旧 11 条稀疏历史）
  4. `C2`（完整候选：双独立会话簇资格 + 多相位配额 + A `2021-10-06` 稠密历史；可在离线无额外前向条件下顺带汇报“仅改资格不重编码”与“完整 `C2`”的消融读数，但只设 **唯一主决策臂 `C2`**）。
- **一次性资源预算与硬停止标准**：
  - **预算**：新增 E3 编码总行数 `<= 25,000` 行（若 `C2` 仅在现有已编码 36,451 条 B 参考上改资格 + 补编码 A 侧 `189–191.pcap` 的 `<= 300` 条，则新增 E3 编码甚至 `< 1,000` 行，单次 CPU 作业 `< 30` 分钟；若需重选 B 多相位子集，仍严控在 `<= 36,451` 行、`<= 3h` CPU、`< 16 GiB` RSS 内），`1` 次终态运行，`0` 重试。
  - **硬停止标准**：
    1. 若源域 `G0/G1` 预检未能减少 TCP 攻击撤回，或 `HIST_DEV` 正常门未过 → **不触碰 A/B，直接停止**。
    2. 若进入 A/B 后仍触发任一头 `protection_gate == FAIL` 或主视图池/设备 FPR 未改善 → **停止在当前冻结特征/线性修正框架内继续调参考规则**，不再做 `C3` 微调循环。

---

## Q4：独立泛化数据的选择是否合理？（含原始包级硬缺口补证）

### 4.1 结论
**完全同意 Codex 的排序与排除结论**：将 **IoTID20 的 HCRL 原始包（DOI `10.21227/q70p-q449`）列为第一核验目标、`ACI-IoT-2023` 列为第一备选、将 `CICIoT2023` 从“全新设备主确认集”降级（因 `HeimVision 44:01:BB:EC:10:4A` 与 `Eufy 8C:85:80:6C:B6:47` MAC 与 A 池完全重合且攻击为整包粗标签）、并排除 `IoT-23` 承担主同契约确认**，判断扎实、证据链清晰。

但通过对 `HCRL_DESCRIPTION_READBACK.json` 全部规则单元格（`H4–H42`、`D4/I4`）的独立交叉审查，我必须泼一盆关键冷水——**HCRL 原始包存在两个足以推翻“直接拿来当同契约主泛化集”的严重原始数据风险，必须在最小核验清单中前置锁死，并建议同步拉取 `ACI-IoT-2023` 的轻量时间表元数据以防 HCRL 因正常时长不足而降级。**

### 4.2 可查证依据（独立审查发现的 3 个原始包级硬缺口）

1. **硬缺口 G1（极其关键）：HCRL 的 DoS 与 Scan 过滤规则全部是“单向攻击源→受害端”谓词，攻击 PCAP 内的 `!rule` 混有大量受害端攻击响应包，绝不能当作正常包！**
   - 核查 `HCRL_DESCRIPTION_READBACK.json` 可见：
     - `dos-synflooding-1..3-dec.pcap`（EZVIZ，`H11–H13`）：规则为 `ip.src == 222.0.0.0/8 (或 111.0.0.0/8) and tcp.flags.syn == 1 and ip.dst == 192.168.0.13 and tcp.dstport == 554 and tcp`。注意 `I11 = 40,788` 总包中仅有 `J11 = 18,703` 包命中规则（`45.9%`）；`dos-synflooding-4-dec.pcap`（NUGU，`H14`）中 `I14 = 10,561` 总包、`J14 = 4,692` 命中（`44.4%`）。
     - `scan-hostport-1..6-dec.pcap` 与 `scan-portos-1..6-dec.pcap`（`H18–H36`）：Port Scan 与 OS Detection 规则全部限定了 **`ip.src == 192.168.0.15 and ip.dst == 192.168.0.13 (或 .24)`**。
   - **这意味着什么？** 受害设备（`EZVIZ 192.168.0.13` 或 `NUGU 192.168.0.24`）面对 SYN 洪泛或端口扫描时发出的全部反向响应帧（`ip.src == 192.168.0.13/.24 -> ip.dst == 222.0.0.0/8, 111.0.0.0/8, 192.168.0.15` 的 `SYN-ACK` / `RST-ACK` 帧）**全部不匹配 `H11–H36` 规则**！这正是文献中 IoTID20 流表 CSV 著名的“双向流单向过滤导致攻击响应被误标为 Normal”缺陷的根源。
   - 由于我们的检测器对设备 owner MAC 的双向 TCP/UDP 帧全部评分，若将攻击 PCAP 中的 `!rule` 当作 `label = 0` 正常分母，模型对受害端异常洪泛响应帧的正确报警会被大规模误计为正常误报（假阳性）！
   - **强制补证规则**：
     1. **正常误报（FPR）评价分母只能来自纯正常捕获 `benign-dec.pcap` 在参考截止窗之后的留出时间段**，严禁使用任何攻击 PCAP 内的 `!rule` 充当正常真值分母。
     2. 对攻击 PCAP 内的双向同五元组受害端响应帧（如 `ip.src == victim_ip and ip.dst == attacker_ip/spoofed_subnet`），必须在冻结模型运行前通过 `tshark` 核实包数占比，并在协议中预先注册其标签归属（按双向攻击会话归入攻击集，或单独列为 `VICTIM_ATTACK_RESPONSE` 审计层，绝不混入 `Normal`）。

2. **硬缺口 G2：`benign-dec.pcap` 体积与包数偏小（`117,937 KB` / `137,396` 包，两台设备混采），存在无法同时满足“`3600s` 参考窗 + 后续正常评价窗”的高概率风险**
   - `HCRL_DESCRIPTION_READBACK.json` 第 `D4 / E4 / I4` 格显示：整个数据集**唯一**的纯正常文件 `benign-dec.pcap` 总大小仅 `117,937 KB`（约 `115 MB`），总包数 `137,396`，且同时包含 `NUGU` 与 `EZVIZ`（及同网段路由器/手机交互）。
   - 对于包含高清摄像头（EZVIZ C2C，RTSP 554 视频流单帧偏大，平均包长约 `858 Bytes`）的捕获，`115 MB` 若为持续视频流可能仅持续十余分钟至数十分钟；即便在低码率待机下勉强跨过 `3600s`，按 G1 要求同时切出“前 `3600s` 参考窗”与“后段独立正常 FPR 评价窗”后，后段可用正常包数也可能过少，或真实 `frame.time_epoch` 与 `2019-05-31` 攻击文件发生倒置（`A1` 已警告 `Creation Date != 采集日期`）。
   - **强制补证规则**：下载 `benign-dec.pcap` 后第一时间跑 `capinfos` 与按设备 MAC（`bc:1c:81:4b:ae:ba`、`04:32:f4:45:17:b3`）拆分的 `frame.time_epoch` 首末时间戳、最大空闲间隔与连续时长审计：
     - 若每台设备连续跨度 **显著大于 `3600s`（例如 `>= 5400s`）且严格早于全部候选攻击 PCAP 的最小 `frame.time_epoch`**，则通过主同契约确认集（`P1`）资格；
     - 若真实时长 **`< 3600s` 或后段正常留出包不足**，严禁伪造时间戳或拼接攻击文件背景包凑数——应如实将 HCRL 降级为“短参考窗外部测试床补充验证”，并立即启用 `ACI-IoT-2023` 作为长时序主泛化集。

3. **硬缺口 G3：802.11 监听解密去头（`*-dec.pcap`）的链路层封装与网关 MAC 一致性核验**
   - HCRL 文件名均带 `-dec.pcap`（Wi-Fi Monitor 模式抓包经 Aircrack-ng 解密转换为以太网帧）。必须在最小核验中用 `capinfos / tshark` 实测确认：
     1. 链路层封装确为标准 `DLT_EN10MB (linktype=1)`，不存在残余 `radiotap / 802.11 LLC-SNAP` 异常帧或截断包（`caplen < pktlen`）；
     2. `benign-dec.pcap` 与 `dos-synflooding-* / scan-hostport-*` 中 `EZVIZ`（`bc:1c:81:4b:ae:ba`）和 `NUGU`（`04:32:f4:45:17:b3`）的二层 MAC、IP 分配及 IPv4 分片比例完全一致，与我们的冻结 `contexts.py / endpoint` 解析器零冲突。

### 4.3 唯一下一步（数据线并行边界）
1. **主动作（最小原始包核验）**：待用户授权下载动作后，仅拉取 Codex 清单锁定的 **HCRL 5 个原始 PCAP（`150,453 KB`）**，只运行 `capinfos + tshark` 头部/时间戳/过滤规则计数/反向响应包占比审计，出具 `HCRL_RAW_QUALIFICATION_RECEIPT.json`，**不跑 E3 编码、不跑模型评分**。
2. **低成本保险动作（元数据先行）**：在拉大体积 PCAP 之前，同步获取 **`ACI-IoT-2023` 的公开设备清单与攻击时间表元数据文件（仅 CSV/JSON/文档级，不拉数 GB 原始 PCAP）**，核清其同设备跨天正常时长与包级时间戳切分精度，防止 HCRL 卡在 `benign-dec.pcap < 3600s` 时泛化线停摆。
3. **揭示纪律**：在主线机制（`D-HIST-TRACE-V1` → `C2`）及泛化集适配契约完全冻结前，不在任何外部泛化候选上运行或查看模型性能指标。
