# CKDA D0 FROZEN 预注册：Flow/Session 表征候选兼容性与污染审计

日期：2026-08-11

状态：**FROZEN PREREGISTRATION — 只冻结 D0；未授权执行、下载、解码、训练、生成性能 embedding 或提交 HPC**

约束性上游：

- `ckcz_seed27_formal_result_20260810.md` 与 Kimi 终审 `5ba030c`；
- `ckda_d0_d1_design_draft_20260811.md`，审查基线 `ce11e76`；
- Kimi 草案审查 `ckda_d0_d1_draft_kimi_review_20260811.md`，commit `27c391b`；
- attack-family 唯一口径 `ckcz_attack_family_scope_clarification_20260809.md`，commit `97adfe0`。

本文件的 SHA-256 由同目录侧车
`ckda_d0_representation_compatibility_audit_preregistered_20260811.md.sha256` 固定。
执行前必须核验侧车；任何正文变化都使本次 FROZEN 失效，必须重新评审并生成新侧车。

---

## 1. D0 唯一目标与禁止越界

D0 只回答：四个候选中是否存在能够在现有数据、因果、污染、覆盖、复现和资源合同下进入
D1 的 flow/session representation；若存在，按预声明的非性能词典序冻结 primary 与至多一个
backup/control。

D0 不回答攻击检测效果，不生成 attack/OOD frontier，不训练分类器，不选择阈值，不进入导师
损失函数消融。D0 的任何 PASS 只授权起草 D1 FROZEN，不等于系统能力提高。

禁止：

- 使用任何 attack/OOD label、family 指标、C1/M7 分数或 CKCZ frontier 选择候选；
- 在 51D 序列上新增主候选；
- 下载或打开 cooler-motor FINAL 数据；
- 使用 seed 37/47；
- 对 select/report/FINAL 拟合 tokenizer、bucket、normalization、encoder 或资源参数；
- 在 D0 测量后修改覆盖、污染、语料、成熟度或成本口径；
- 把兼容性 forward 的输出用于几何、分类或排名分析。

---

## 2. 冻结候选集合与身份

| candidate_id | 候选 | 类型 | D0 定位 |
|---|---|---|---|
| E1 | ET-BERT 官方代码与官方 checkpoint | 外部成熟组件 | primary 候选 |
| E2 | YaTC 官方代码与官方 checkpoint | 外部成熟组件 | primary 候选 |
| E3 | netFound 官方代码与官方 checkpoint | 外部成熟组件 | primary 候选 |
| I1 | 域内小型自监督 session encoder | 本项目受控实现 | 候选兼受控基线 |

D0 执行时只接受作者/机构官方论文、官方仓库、官方 release 与官方 checkpoint。第三方复刻、
模型聚合站镜像或无法回溯官方身份的权重不替代本表候选。

候选集合不得扩展。若某官方名称对应多个 checkpoint，先按以下固定规则选唯一身份：

1. 官方论文主结果明确指定的 checkpoint；
2. 否则官方 release 标记为 base/default 的 checkpoint；
3. 否则官方仓库 README 第一条完整可运行推理示例使用的 checkpoint；
4. 仍不唯一则该候选为 `AMBIGUOUS_IDENTITY`，D0 淘汰，不试多个 checkpoint。

---

## 3. 数据角色与 FINAL 排除

沿用现行冻结 source/target/role 清单，不因回到 PCAP 改写角色。D0 执行包必须包含显式
allowlist 与 denylist，并在任何文件读取前断言：

- fit：允许做合法可见 packet/token/session census 与兼容性 pilot；
- select：只允许 manifest/文件存在性/静态覆盖审计，不拟合、不 forward；
- report：只允许 manifest/文件存在性/静态覆盖审计，不解码内容、不拟合、不 forward；
- FINAL：只允许验证路径和 source ID 未进入 allowlist；不得 stat 内容后继续、不得解码、
  不得散列内容、不得生成 token 或 embedding。

命中 cooler-motor、seed 37/47 或任何冻结 FINAL marker，D0 必须 fail closed，写
`CKDA_D0_ENGINEERING_FAILURE_FINAL_EXCLUSION`，且不得生成候选排序或科学结论。

“无标签”不等于“允许训练”。report-only 数据即使不读取 label，也不能进入词表、bucket、
归一化、SSL 或成本调优。

---

## 4. D0 固定审计表模板

每候选必须写一行 `ckda_d0_candidate_audit.csv`。字段顺序固定如下，不得增删、重命名或用
自由文本替代枚举：

```text
candidate_id
official_paper_url
official_repo_url
official_repo_commit
official_release
checkpoint_url
checkpoint_sha256
license_id
license_research_use_ok
license_weights_redistribution_ok
identity_status
pretraining_corpora
pretraining_collection_dates
pretraining_iot_ics_disclosed
iotsim_overlap_evidence
ton_iot_overlap_evidence
overlap_risk
native_input_unit
required_payload
required_fields
target_fitted_tokenizer_required
strict_prefix_supported
full_session_then_slice_required
uid_join_deterministic
fit_visible_unique_packets
fit_encodable_unique_packets
fit_encodable_fraction
select_static_target_fraction
report_static_target_fraction
ton_metadata_gap_status
final_files_opened
pilot_raw_packets
pilot_candidate_tokens
pilot_peak_rss_bytes
pilot_peak_vram_bytes
pilot_median_raw_packets_per_second
pilot_median_candidate_tokens_per_second
projected_nonfinal_wall_seconds
checkpoint_resume_supported
dependency_lock_reproducible
maturity_grade
custom_adapter_files
custom_adapter_loc
i1_fit_sessions
i1_fit_tokens
i1_data_gate
hard_gate_status
hard_gate_reasons
ranking_tuple
evidence_manifest_path
```

缺失数字写空字段并在 `hard_gate_reasons` 解释；不得以 0 代替未知。所有布尔字段只允许
`true/false`；枚举只使用本文件定义值。

每行必须配套 `evidence_manifest_path`，逐条给出本地证据文件、官方 URL、访问 UTC、内容
SHA-256 或命令输出 hash。平局裁决必须引用这些证据，不接受“综合判断”。

---

## 5. 固定污染审计

只使用官方论文、官方数据说明、官方仓库与可归档的语料清单。检索不到重叠证据不等于已证明
互斥。

`overlap_risk` 只允许：

1. `KNOWN_DISJOINT`：有可核验证据排除 IoTSIM 与 ToN-IoT 及其直接派生物；
2. `NO_KNOWN_OVERLAP`：未发现重叠，但公开组成不足以证明互斥；
3. `POSSIBLE_OVERLAP`：来源、时间或组成无法排除直接/派生重叠；
4. `CONFIRMED_OVERLAP`：确认包含评测数据或直接派生物。

固定裁决：

- `CONFIRMED_OVERLAP`：硬淘汰；
- `POSSIBLE_OVERLAP`：候选选择硬淘汰，只可记录为污染敏感性对照，D0 不 forward；
- `NO_KNOWN_OVERLAP` 优先级低于 `KNOWN_DISJOINT`；
- 不允许通过“模型很通用”“预训练很早”推断无重叠。

---

## 6. 固定覆盖与 census 口径

### 6.1 Fit-visible packet universe

fit census 只统计冻结 fit target 的合法 past-and-current 可见前缀并集。packet 以
`source_id + pcap_member + event_position` 唯一化；同一 packet 被多个 fit prefix 看见时只计一次。
不得读取任一 select/report target 之后才出现的 packet 来扩大 fit 语料。

`fit_visible_unique_packets` 是上述并集大小。

`fit_encodable_unique_packets` 是候选原生 tokenizer 在不做目标数据拟合、且不补看未来的条件下
可编码的并集大小。覆盖率固定为：

```text
fit_encodable_fraction = fit_encodable_unique_packets / fit_visible_unique_packets
```

select/report 的 `static_target_fraction` 只基于冻结 manifest、候选所需字段是否存在和文件格式
兼容性推导；D0 不解码其内容、不 forward。

### 6.2 I1 session 与 token 下限

I1 的 census 在任何实测数字打开前冻结如下：

- packet universe：§6.1 的 fit-visible unique packets；
- session key：`source_id + pcap_member + canonical_bidirectional_5tuple`；
- canonical bidirectional 端点按 `(IP bytes, port)` 字节序排序；protocol 纳入 key；
- 非 TCP/UDP 若无端口，以端口 0 表示但 protocol 仍区分；
- pcap member 边界强制 reset；不跨 source/member 合并；
- 本次 census 不以 inactivity timeout 拆分，避免通过 timeout 调节 session 数；
- I1 token 数等于在固定最小解析合同下可编码的 unique packet 数，不因多个 prefix 重复计数。

I1 的先验资格门固定为：

```text
i1_fit_sessions >= 500000
AND i1_fit_tokens >= 10000000
```

任一不足，`i1_data_gate=FAIL`，I1 在 D0 直接淘汰且不训练。达到下限只表示允许继续参与
兼容性排序，不证明语料充分或模型有效。该门是本项目的保守运营门，不宣称普适样本复杂度定理。

---

## 7. 固定因果与输入合同审计

候选只有同时满足以下静态条件才可继续：

1. 可直接编码 prefix，或官方接口允许在 target cut 处截断后独立编码；
2. 不需要完整 session 的最终长度、完成标记、未来反向包或未来统计；
3. tokenizer/normalization 不需要目标 report/FINAL 拟合；
4. current-inclusive 与 prefix 截断语义可精确定义；
5. UID 可通过冻结 source/member/event_position 确定性 join；
6. 相同 timestamp 可用冻结稳定键排序；
7. source/member state 可显式 reset；
8. D1 可实现 future mutation、future label、source reset、exact cut、equal-time、
   prefix-vs-full、join、deterministic replay、FINAL exclusion 九项合同测试。

`full_session_then_slice_required=true` 或 `strict_prefix_supported=false` 为硬淘汰。D0 不以经验上
“影响很小”放宽因果合同。

---

## 8. 固定成熟度与复现等级

`maturity_grade` 只允许：

- `A`：官方代码、官方 checkpoint、固定 release/commit、文档化推理入口、依赖可锁定；
- `B`：官方代码与 checkpoint 齐全，但需要本项目输入 adapter；不得改 encoder 主体；
- `C`：无唯一官方 checkpoint/推理入口，或必须重写核心模型路径；
- `I`：I1 本项目受控实现。

`C` 硬淘汰。`A` 排在 `B` 前。`I` 不自动等同 A/B；在其他排名维度完全相同的情况下，
固定排在 E1–E3 之后。

`custom_adapter_files` 和 `custom_adapter_loc` 通过最终 D0 patch 机械计数；只计 CKDA 新增 adapter，
不得把 vendor 代码行数藏入“不计”。适配量仅作成熟度之后的固定平局证据，不按主观代码质量评分。

---

## 9. 固定资源 pilot 与成本口径

D0 资源 pilot 只使用按 `(source_id, pcap_member, event_position)` 排序后的 fit-visible 前缀：

- 每候选取前 100 个非空 session；
- raw packet 上限 100,000；达到任一上限停止；
- tokenizer warm-up 一次，不计时；
- 同一环境连续运行 3 次，报告中位吞吐；
- forward 只为接口与资源测量，禁止持久化 embedding 内容；只记录 shape、finite、RSS/VRAM、
  输入/配置 hash 和退出状态；
- 峰值 RSS/VRAM 使用同一测量工具与同一采样周期；
- projected wall time 以 `nonfinal eligible raw packets / median raw packets per second` 计算，
  不使用作者论文中的硬件吞吐替代本地测量。

若候选不能在现有合法队列资源内完成，只有同时具备 source/session 分块、不可变输入 hash、
validated checkpoint 与 resume 才可保留。无 resume 的长单体任务硬淘汰。

两个成本相差不超过 10% 视为平局，进入下一排名键；不得用小于等于 10% 的噪声调整顺序。

---

## 10. D0 硬门

以下任一成立，候选 `hard_gate_status=FAIL`：

- 身份歧义、权重/代码不可固定或许可证不允许研究使用；
- `CONFIRMED_OVERLAP` 或 `POSSIBLE_OVERLAP`；
- 必须拟合目标 report/FINAL tokenizer、词表或归一化；
- 无严格 prefix、需要完整 session 后切片或无法实现九项 D1 因果测试；
- UID join 不确定；
- 合法关键角色系统性不可编码且无统一缺失状态；
- maturity `C`；
- 依赖不可锁定、输出身份不可复核；
- 资源超出现有队列且无分块/checkpoint/resume；
- I1 未同时达到 500,000 session 与 10,000,000 token；
- 任一 FINAL 文件被打开；
- D0 表字段、证据 manifest 或 hash 不完整。

工程失败不得转写为候选科学失败。

---

## 11. 固定词典序与平局证据

只有 `hard_gate_status=PASS` 的候选参与排序。`ranking_tuple` 固定为：

```text
(
  overlap_rank,                 # KNOWN_DISJOINT < NO_KNOWN_OVERLAP
  -fit_encodable_fraction,      # 越高越优
  -select_static_target_fraction,
  -report_static_target_fraction,
  prefix_native_rank,           # 原生 prefix < adapter prefix
  maturity_rank,                # A < B < I
  custom_adapter_loc,
  projected_nonfinal_wall_seconds,
  candidate_order               # E1 < E2 < E3 < I1
)
```

浮点覆盖差异小于 `1e-6` 视为相等；成本差异不超过较小者的 10% 视为相等。每个非平局键必须
在 `evidence_manifest_path` 附原始计数/测量证据；不能提供证据时该键记为未知，候选不得凭该键
获胜。

排序第一为 primary。排序第二只有在全部硬门 PASS 且污染等级不差于
`NO_KNOWN_OVERLAP` 时才冻结为 backup/control；否则不设 backup。不得生成性能 embedding 后
改序。

---

## 12. D0 执行阶段与产出

经用户授权后，D0 仍分为一个逻辑审计链：

1. 官方身份、许可证、语料与污染证据归档；
2. FINAL denylist 与合法 fit-visible universe 固定；
3. 静态字段/覆盖审计；
4. fit-only census 与固定资源 pilot；
5. 表格、证据 manifest、hash 与机器裁决生成；
6. validator 复核表结构、硬门与排序；
7. 独立审查后才允许解释结果。

必须产出：

- `ckda_d0_candidate_audit.csv`；
- `ckda_d0_evidence_manifest.csv`；
- `ckda_d0_data_census.json`；
- `ckda_d0_resource_pilot.csv`；
- `ckda_d0_final_exclusion_audit.json`；
- `ckda_d0_verdict.json`；
- `SHA256SUMS`；
- 结果报告与 validator 报告。

D0 正式 verdict 只允许：

- `CKDA_D0_PRIMARY_AND_OPTIONAL_BACKUP_FROZEN`；
- `CKDA_D0_NO_COMPATIBLE_REPRESENTATION`；
- `CKDA_D0_ENGINEERING_FAILURE`；
- `CKDA_D0_ENGINEERING_FAILURE_FINAL_EXCLUSION`。

后两者无科学/路线裁决。所有输出必须在独立目录原子完成；失败不得留下看似正式的 partial
verdict。

---

## 13. D1 与 D2 的冻结边界

D0 PASS 只授权另起 D1 FROZEN。D1 仍须冻结 embedding 层、pooling、G0/P1/P2、阈值、
bootstrap 与一次性 report opening 后才能执行。

D1 沿用 attack-family 唯一字典 `ckcz_attack_family_scope_clarification_20260809.md`：

- 16 个报告 family 使用 `GLOBAL_ATTACK_PRESERVATION` 244,050 全角色分母；
- rows ≥ 15 的每 family 相对 C1 不低于 −2 pp；
- support 69/69 是独立硬门；
- future-only 使用 131,391 分母；
- CKBW 的 12 族只属训练历史，不参与 CKDA 报告或映射。

D1 五态保留，机器别名固定为：

```text
GO_D2 == CKDA_D1_ACTIONABLE_PROBE_SIGNAL
```

只有该状态能授权起草 D2。几何、线性、小 MLP 全失败时只能写
`CKDA_D1_NO_ACTIONABLE_SIGNAL_UNDER_FROZEN_PROBES`，不得写信息论 `NO_INFORMATION`。

导师损失函数不属于 D0；未经 D1 唯一 GO 状态，不得实现或实验。

---

## 14. 授权与审查门

本 FROZEN 文件生成后：

1. Kimi 必须核验正文 SHA、表格字段、I1 先验门、词典序、family 字典引用和 FINAL 排除；
2. Kimi PASS 只解除用户授权前的技术审查门；
3. 用户明确授权后，Codex 才可编写 D0 审计/validator、归档官方资料或执行 fit-only census；
4. 任何下载、PCAP 解码或计算作业必须在执行前再次说明范围；
5. D0 不自动授权 D1、D2、seed 27 正式实验或任何 FINAL。

截至本文件冻结时：**未执行 D0，未下载候选，未打开/解码任何 CKDA PCAP，未训练模型，
未提交 HPC，FINAL 继续封存。**
