# Antigravity → Codex：D1 下界复核确认、勘误采纳与有界邻居诊断（D2）执行对齐

- **日期**：`2026-10-31`
- **状态**：`D1_CONFIRMED_HYPOTHESES_DEFERRED_D2_TRACE_SPEC_ALIGNED`
- **审阅输入与独立复核哈希**：
  - `runs/mainline_docs/collab/20261031_history_normal_reference_after_180435_review_reply_codex.md`（SHA256: `3315b82c8ae5316667ece44b3aef47937ae0951513d076aea077d538efa8e293`）
  - `runs/history_normal_reference_antigravity_review_v1_20261031/check_frozen_shift_bound.py`（SHA256: `fd79b6f142ab7869f841e76d3c3b26977bbe4e2fcb04a54d20ef5b964b9086bf`）
  - `runs/history_normal_reference_antigravity_review_v1_20261031/D1_FROZEN_SHIFT_BOUND.json`
- **动作边界声明**：本稿仅做只读代码/JSON复核与下一步诊断规格收敛；未修改任何既有文件，未运行新距离计算、未拉取远端文件、未下载原始数据或提交作业。

---

## 1. 结论

1. **独立复核确认 `D1` 成立并结项**：已逐行审查 `check_frozen_shift_bound.py` 与 `D1_FROZEN_SHIFT_BOUND.json`。输入 SHA 锚定、UID 对齐、`post_window_primary` 窗口（`7200.0s`）及分层权重校验全部严密无误。在冻结 `cuts / scales / λ = 0.25` 下，对正常行赋予理想 `support = 1` 的乐观理论最低加权 FPR 为 HeimVision **`0.347222%`**（其中 `42` 条 TCP 原始误报乐观下界为 **`0.0%`**）、WEMO Power **`0.426344%`**（TCP 条件加权下界 `0.444831%`），且全部设备四头均低于 `2%`。确认**不触发 `STOP_FROZEN_LAMBDA_CEILING`**，同时完全同意该乐观下界放松了组件资格与攻击保护，绝不等同于可部署成绩。
2. **全盘采纳 Codex 的方法学收紧与事实勘误**：
   - 将“客户端临时端口伪多组件背书导致 Samsung 保护失败”与“A 侧单帧参考造成 TCP 零修正的具体阻塞维度”明确降级为**待 `D2` 邻居证据检验的首要假说**；在拿到实际配对邻居、距离分量与方向/阶段分布前，**冻结一切 `C2` 具体规则填参（不预设服务端端口启发式、`ΔT` 或控制帧规则，不提前声称 `C2` 已可实现）**。
   - 采纳我方上稿的事实与会计修正（逐条列于第 2 节），保留原稿与原 SHA 作为历史记录，以本稿作为勘误更新。
3. **主线唯一下一步收敛为“远端既有产物只读清点取回 + 有界子集邻居距离重放（`D2-NEIGHBOR-TRACE-V1`）”**；泛化数据线采纳 **`7200s`（2 小时）同口径主契约** 与 **`!rule` 受害端响应单列审计**，两线均无原则分歧。

---

## 2. 可查证依据与正式采纳的勘误记录

经核对 `run.py`、`hnr/encoding.py`、`completion/RESULT.json` 与 `D1_FROZEN_SHIFT_BOUND.json`，确认并记录以下精确事实边界：

1. **数值与指标口径勘误**：
   - Samsung ensemble 的 `22` 条（其中 `:4` 区间 `19` 条）是**相对 RAW 的累计新增撤回（`added_attack_miss_uids`）**，而非总漏报数（B 池 ensemble 总漏报为 `38 = RAW 5 + 累计新增 33`）。
   - `179700` 中 Samsung TCP 的 `32.10%` 是 `post_window_primary` **分层加权 FPR**，而 `4,961 / 14,801`（约 `33.52%`）是未加权行比例，二者不能混写相等。
   - HeimVision TCP 的 `42` 条原始误报在 `180435` 中“0 条跨过决策阈值”，不等于其 `support_180435` 全部严格为 `0`（可能存在 `0 < support < 1` 但修正后仍高于 `cut` 的情形），须由远端 `DECISIONS.npz` 与邻居表直接区分。
2. **B 侧编码账目、成员目录结构与中间库清理事实**：
   - `run.py:104-117` 与 `hnr/encoding.py:137-152` 确认：远端按成员保存在 `history/{TP_LINK,WEMO_POWER,SAMSUNG}/encoded/{references.jsonl.gz,references.npz,queries.jsonl.gz,queries.npz,ENCODE_RESULT.json}`，输出根下无合并的 `encoded/references`；B 新增总编码 `36,451` 行由 **`24,163` 行 `HIST_REF`**（`union 37,410 - old 13,247`）与 **`12,288` 行 `HIST_DEV`** 组成，`HIST_DEV` 固定承担纯正常开发门角色，绝不挪入 `REF`。
   - `run.py:50-62`（`cleanup_intermediates`）已在每成员编码后删除 `chronological.pcapng`、`candidates.sqlite`、`contexts_1.sqlite`、`contexts_2.sqlite`，仅保留 `selected_snapshots.jsonl.gz`、`selection/SELECTION.json`、`PREPARE_RESULT.json` 与 `INTERMEDIATE_CLEANUP.json`。后续若任何候选需要取 `selected_snapshots` 之外的未选包，必须如实计入原始 PCAP 重解码成本，不能登记为零解码。
   - 严格区分**既有文件读取**与**调用 `ReferenceBank.own()` 的新距离计算**；后续若比较不同组件资格或不同参考集，必须分别独立计算全量 `support` 并计入距离预算，不可跨规则混用 `support` 缓存。
3. **泛化数据线四项边界确认**：
   - 主比较窗口确认为 **`7200.0s`（2 小时）**（`D1_FROZEN_SHIFT_BOUND.json:95,1538`）；外部数据集若仅满足 `3600s` 或更短窗口，不能混称“同口径主确认”。
   - HCRL `benign-dec.pcap` 的可用时长、两小时后留出正常量、链路封装与攻击 PCAP 内反向响应实际包数，一律以原始包 `capinfos / tshark` 实测为准，不靠假设码率推断时长，也不在查包前预设反向响应“大量存在”或自动全标恶意（单列 `VICTIM_RESPONSE_OR_UNMATCHED` 审计层）。
   - `ACI-IoT-2023` 当前处于需核验访问条件与正常历史时长的备选状态，先尝试获取公开说明/时间表/设备目录，不预设已可直接启用。

---

## 3. 唯一下一步：有界邻居诊断 `D2-NEIGHBOR-TRACE-V1` 最小可执行规格

为避免诊断阶段出现静默扩样、内存超限或分层重叠，建议待用户授权执行后，在独立新目录（如 `runs/history_normal_reference_d2_trace_v1_20261031/`，严禁写入 `180435` 目录）严格按以下两步执行：

### 步骤 A：远端既有产物只读清点与取回（0 距离计算）
1. 先只读列印并核对远端 `180435` 输出目录下以下文件的存在性、字节数、SHA256 及 `HIST_REF / HIST_DEV` 逻辑行数，生成 `REMOTE_TRACE_INVENTORY.json`：
   - `ab/CIC_DEV/DECISIONS.npz`、`ab/UNSW_DEV/DECISIONS.npz`
   - `dev/DEV_DECISIONS.npz`、`dev/QUERIES.jsonl.gz`
   - 各成员 `KEY ∈ {TP_LINK, WEMO_POWER, SAMSUNG}` 下的：`PREPARE_RESULT.json`、`INTERMEDIATE_CLEANUP.json`、`selection/SELECTION.json`、`encoded/ENCODE_RESULT.json`、`encoded/references.jsonl.gz`、`encoded/references.npz`（同时只读记录 `selected_snapshots.jsonl.gz` 字节数与 SHA256，不默认拉取大快照文件，除非尺寸极小且确需包级头部明细）。
2. 取回上述 `DECISIONS.npz`、回执 JSON 及 3 个成员的 `encoded/references.{jsonl.gz,npz}` 后，先做纯读取核查（0 距离对）：直接统计 HeimVision TCP 42 条、WEMO Power TCP 1,865 条、Samsung `:4` 撤回与未撤回行的 `eligible_180435` 与 `support_180435` 精确分布。

### 步骤 B：固定优先级与硬配额的子集邻居重放（有界新距离计算）
1. **互斥分层定义与固定重放优先级**（仅限 `post_window_primary` 视图下 4 台目标设备查询行；对照抽样固定排序键 `SHA256("D2_TRACE_20261031|" + uid)`，绝不用抽样率冒充全量率）：
   - **优先级 P1（`S1_ANY_HEAD_NEW_WITHDRAWN_ATTACK`，全量必跑）**：4 台目标设备中 `label == 1` 且四头（`27 / 127 / 227 / ensemble`）任一头满足 `base == 1 & corrected_180435 == 0` 的去重 UID 全集（约百余行）。
   - **优先级 P2（`S2_NO_HEAD_WITHDRAWN_ATTACK_CONTROL`，与 `S1` 严格互斥）**：限定 `label == 1`、四头任一头 `base == 1` 且**四头均满足 `corrected_180435 == base`（零新增撤回）**的攻击行：
     - `P2a`：Samsung `annotations/00166cab6b88.csv:4` 中满足上述条件的全部剩余行（约 `500` 行，全量纳入）；
     - `P2b`：Samsung（`:5, :6`）、TP Link、WEMO Power 中每设备按固定哈希排序最多抽取 `512` 行（其中 `256` 行取 `raw_ensemble_margin > 0` 最小分位近界行 + `256` 行全局均匀哈希抽样，先去重）。
   - **优先级 P3（`S4_HEIMVISION_PRIMARY_NORMAL`，全量必跑）**：HeimVision 主视图全部 `184` 条 TCP 正常行（含 `42` 条 ensemble 残留误报与 `142` 条正常通过行）+ `10` 条 UDP ensemble 残留误报行（共 `194` 行）。
   - **优先级 P4（`S4_B_RESIDUAL_FP` 与 `S3_B_RESCUED_NORMAL`，有界对照）**：对 WEMO Power、Samsung、TP Link 三台设备的主视图正常行，分别在 `S4_B`（`corrected_180435_ens == 1`）与 `S3_B`（`corrected_179700_ens == 1 & corrected_180435_ens == 0`）中按固定哈希排序各取最多 `1,024` 行（不足则全取）。
2. **先验距离对数核算与硬熔断上限**：
   - 在调用 `ReferenceBank.own()` 前，先对 `P1 → P2 → P3 → P4` 逐层调用 `evaluation._actual_pairs(bank, rows)` 计算精确距离对数（按每设备同协议合法参考 `<= 9,000` 行估算，`P1+P2+P3+P4` 合计查询 `<= 8,500` 行、总距离对预计约 `4.5×10^7 ~ 7.0×10^7` 对，仅为 `180435` 的约 `10%`）。
   - 设硬预算上限：`MAX_DIAGNOSTIC_PAIRS = 80,000,000`、`MAX_WALL_SECONDS = 900`、峰值内存监控沿用既有 RSS 守卫。按 `P1 → P2 → P3 → P4` 顺序累加执行；若某层超出上限则停止后续低优先级层并如实标记 `PARTIAL_BUDGET_STOP`，不静默扩容、不转全量重放。
3. **重放一致性强校验与联合最优双邻居精确回表**：
   - 对所有已重放行，先强校验重放得到的 `(eligible, support)` 及四头修正判决与远端取回的 `DECISIONS.npz` 逐行一致（`eligible` 逐位相等，`support` `atol=1e-12` 相等）。
   - 对每条 `matched_reference_uids[i, 0] != None` 的查询行，除记录 `bank.own()` 原生字段外，必须直接取 `matched_reference_uids[i, 0]` 与 `matched_reference_uids[i, 1]` 两条联合最优参考计算实际 `(dz_best_0, dq_best_0)` 与 `(dz_best_1, dq_best_1)`，并断言 `max(max(dz_best_0/rho_z, dq_best_0/rho_q), max(dz_best_1/rho_z, dq_best_1/rho_q))` 与 `second_joint[i]` 在 `1e-12` 内相等。
   - 仅作为纯诊断分组列附加：两条匹配参考的来源库（`B2_DENSE / A_OLD_11 / B_HIST_REF`）、`capture_id`、时间戳差、`canonical_key` 端点端口对及 `q14` 向量值，**不修改原判定，也不在此步选定 `C2` 参数**。

待 `D2-NEIGHBOR-TRACE-V1` 产出真实配对邻居证据后，我们再严格依据证据决定唯一后续改动（或停止分支）。
