# CKDA D0 授权后实现与本地门

日期：2026-08-11

状态：`IMPLEMENTED_LOCAL_GATE_PASS — FORMAL RAW CENSUS NOT SUBMITTED`

用户授权：本轮对话明确“授权 D0 执行”

约束协议：`ckda_d0_representation_compatibility_audit_preregistered_20260811.md`
协议 SHA-256：`ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5`

## 1. 本步实际完成

1. 固定 E1/E2/E3 三个外部候选的官方仓库 commit、官方论文、checkpoint 入口、许可与公开预训练语料证据；
2. 完整下载并固定 E3 `netFound-base` 官方权重：
   - bytes：`698,780,900`；
   - SHA-256：`e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105`；
   - 与 Hugging Face 官方响应的 `X-Linked-ETag` 一致；
3. 两次尝试从 E1 官方 Google Drive 下载并断点续传；最终只得到 `356,515,840 / 715,540,022` bytes 的残片。残片 hash 只作工程证据，**不得**作为 checkpoint hash；
4. 因 E2 官方仓库 tree `06dbc5d8fb68949de8ea055ee03053feb5d726bb` 无 `LICENSE/COPYING` 路径，按 FROZEN 研究使用许可硬门阻断，未下载其权重；
5. 实现 D0 cutoff/census/compile 审计器与 25 项合同测试；
6. 用真实冻结 target、CKCZ allowlist、154917 source plans 与真实 lineage cache 生成本地 cutoff 清单，不解码原始 PCAP。

本步没有训练模型、没有生成 embedding、没有读取攻击/OOD label 或 C1/M7/CKCZ 分数、没有打开 FINAL、没有提交 HPC。

## 2. 当前候选身份结论（不是 D0 最终排序）

| 候选 | 当前身份/许可门 | 当前结论 |
|---|---|---|
| E1 ET-BERT | MIT；官方 checkpoint 唯一，但完整权重 hash 尚不可得 | 当前不能通过 checkpoint 身份硬门；是工程可得性事实，不是科学失败 |
| E2 YaTC | 官方仓库无许可授权 | 按 FROZEN 硬淘汰；不以“学术开源惯例”补许可 |
| E3 netFound-base | MIT；repo/HF commit/完整权重均已固定 | 保留，等待真实 fit-only census 与资源 pilot |
| I1 域内小编码器 | 项目受控身份 | 保留，先过 `sessions >= 500,000 AND tokens >= 10,000,000` 数据门 |

污染审计暂按官方公开材料记录：E1/E2/E3 均为 `NO_KNOWN_OVERLAP`，不宣称已证明互斥；I1 只有在精确 fit-only manifest、select/report/FINAL 零打开全部成立时才可写 `KNOWN_DISJOINT`。

## 3. 真实 cutoff 彩排

输出（不入 Git 的执行证据）：

- `D:\study\paper\anomaly_detection\paper04\supercompute_transfer\ckda_d0_local_lineage_inputs_20260811\ckda_d0_fit_prefix_manifest.csv`
- SHA-256：`c4c504131a04617b28c488a1f863a1f303794b76d93dbedd52cb04af09e361f5`
- `27` 个 source/member prefix，覆盖 `25` 个 source；
- `final_files_opened=0`，`label_columns_read=0`；
- 输入钉死：
  - base targets：`74a1699e29b7b1e227f4532ff81f1546a9ba239f2d2d323d390efa5b07437158`；
  - Gotham allowlist：`65b4804109914d50c3efb6b9ae40d2b7d7befc903be571a92ebee90624ab6de7`；
  - auxiliary allowlist：`be4ad12a9b0807b15b120d91ec2f9519a1743120ef0e9f04e0d8bab573252c49`；
  - Gotham source plan：`79cf8f92df2d4d3eec9ceafd8279413a75c0e323e9af0518db269ad4a45e91d3`；
  - auxiliary source plan：`28a485932ba0f7e637b79ebd77b7c397c1fabaa5107790616aa559ea1aba719b`；
  - ToN manifest：`757af9ad929a4542e0023c74d3296afb3feb8da5a74cc73fd9638b4fdbfa78c5`；
  - ToN audit：`1d4b29ef694263a8a60760685f4a7fcd0eebadf77d452b1b591116cba17e90bf`。

实现先读 allowlist，再形成 raw-open 清单；旧全量 target 表中的 cooler-motor 不进入清单。任何 allowlist 内 FINAL marker 均 fail closed。

## 4. 两个提交前必须由 Kimi 明确裁定的合同点

### P0-A：表字段计数文字与枚举不一致

FROZEN §4 文字称“47 列”，但其逐项固定字段列表实际有 **50 个名字**。实现遵循可执行的逐项列表并断言 50 个字段，未删除任何统计量。请求终审明确：将“47”认定为计数笔误、50 个逐项字段为规范；若不接受，则协议本身需重新冻结，不能由实现猜删三列。

### P0-B：`hydraulic-system-1` 是否属于本次可解码 fit universe

现行 CKCZ Gotham allowlist 会排除两个 frozen-fit source：

| source | 原因 |
|---|---|
| `processed/iotsim-cooler-motor-5.csv` | FINAL denylist，必须排除 |
| `processed/iotsim-hydraulic-system-1.csv` | 上游 `raw51_observable_v1` 明确的 1,353-row 不可观测 mask，且没有 CKBU causal lineage cache |

实现当前按“沿用现行显式 allowlist”记录两者，但将第二项作为必须审查的分母边界，不能静默等同 FINAL。请 Kimi 裁定：

- 接受现行 allowlist：D0 对该 source 统一记 missing/unobservable state，census 不打开；或
- 要求回到原始 PCAP 重新建立它的 target lineage：则须先为这个 source 另冻 raw-session observation-unit 合同，不能借 51D 的失败映射猜位置。

在该点关闭前，不提交正式 raw census。

## 5. 实现与回归门

- 实现：`repo/ood/issue27ckda_d0_representation_compatibility_audit_v1.py`
  - `prepare-cutoffs`：从冻结 target + allowlist + lineage 机械生成 fit-prefix 清单；
  - `census`：复用 CKBU TShark decoder，只扫 prefix，按 source/member 原子 checkpoint/resume；
  - `compile`：严格写固定字段、硬门和词典序；缺 resource pilot 不得 PASS；
  - FINAL marker 在任何 raw open 前 fail closed。
- 测试：`repo/ood/test_issue27ckda_d0_representation_compatibility_audit_v1.py`
  - 25/25 PASS；
  - 覆盖 FINAL/seed denylist、50 字段字面 schema、双向五元组 canonicalization、protocol 隔离、IPv4/IPv6 encodability、许可/checkpoint/污染/I1/resource 硬门、allowlist-before-open、原子写和精确排除集合。

## 6. 下一步边界

Kimi 对 P0-A/P0-B 与实现给出 PASS 后，Codex 才构建正式 D0 bundle：

1. 在 HPC 上运行真实 fit-only census，得到 I1 session/token 门；
2. 只对仍通过静态门的候选做固定 100-session/100,000-packet 资源 pilot；
3. validator 生成正式 D0 verdict 与 pullback；
4. 用户拉回后由 Kimi 独立复核。

D0 verdict 即便 PASS，也只允许起草 D1 FROZEN，不授权 D1、导师损失函数、seed 37/47 或 FINAL。
