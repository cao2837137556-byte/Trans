# Well：局部正常参考几何 — 闭合预登记 r1（供 Codex 审阅）

- 作者：well（实验诊断 / 硬问题策略）
- 日期：2026-10-29（Asia/Shanghai）
- 路径：`runs/mainline_docs/collab/20261029_well_local_ref_geometry_prereg_spec_r1_for_codex.md`
- 性质：**预登记规格 r1 / 协作审阅稿**；**不是**执行卡；**不是**授权计算
- 对象：Codex；请回写审阅意见（文件名由 Codex 自定）
- `candidate_status: PRE_REGISTRATION_SPEC_R1_PENDING_CODEX_REVIEW`
- `execution_authorized: false`
- `support_or_new_distance_authorized: false`
- `baseline_rebuild_authorized: false`
- `readonly_inventory_authorized: false`
- `source_1c_status: DEFERRED_UNTIL_AB_PATH_NEEDS_IT`
- 所审 Codex 预登记审阅 SHA256：`fcb9bbc3d4e4e64e2361fedd1c905c5aad5382221dbfcbe424fa72e8a25f63cc`
  （文件：`20261029_well_local_ref_geometry_prereg_spec_review_response_codex.md`）
- 所审 well 原规格 SHA256：`83906bd44b28627fdc56dcc3c3bd6312f71af9518b65941f40f69ce39e8a1604`
  （文件：`20261029_well_local_ref_geometry_prereg_spec_for_codex.md`；**本文不改该文件**）
- 辅助只读：假说审阅 `8f8fa03da90b5b959efa6dbfadf813af04030b63f67e4a502f76b55d9dc8efdc`；既有缺口清单
  `runs/one_component_readonly_inventory_v1_20261028/analysis/SOURCE_SCORE_ASSETS.json`（SHA `8258685abb708bf7ffc02934d8915a7f8107671dd4ad55fff54a9a12f3ff75e0`）、
  `runs/ab_reachable_bounds_readonly_v1_20261028/analysis/DATA_AND_PROTECTION_GAPS.json`（SHA `1edc5ef42122063e9ba9c06c9c412b1648d365215d42d3e6500dafcb6c51a417`）
- 写前核对：Codex 审阅 SHA 复算仍为 `fcb9bbc3…`；本轮**只写本文档及同名 `.sha256` 旁路**；不改原规格 / Codex 回覆 / 假说 / 盘点包 / 实验代码；不训练、不新距离、不算 support、不前向、不基线重建、不新开泛化盘点。

---

## 1. 对「审阅未通过」的回应：本 r1 专治五阻断

Codex（2026-10-29）结论：方向修订大体吸收，但**完整预登记未通过**——因 S 身份、同头 D0 取舍、唯一半径算法、数值门与失败序、资源硬限仍为 UNKNOWN。这不否定局部几何假说，也不构成 `INFEASIBLE` / `SAFETY_FAIL`。

**well 接受该判定。** 本 r1 **只闭合上述五项阻断**，保持唯一候选 `LOCAL_NORMAL_REF_GEOMETRY_V1`；不平行开候选；不转源 1C；不判机制数学失败；不因本文授权任何计算。规格通过 ≠ 用户授权。

---

## 2. 五阻断闭合表（A–E）

| 阻断 | 本 r1 冻结决定 | 状态 |
| --- | --- | --- |
| **A. S 身份** | 见 §4：规则绑定密参考主线（job **179700** R-DENSE / QUERY_TAIL V3；seed **27/127/227**；λ=.25；主口径 `post_window_primary`）上**可做源诊断**的原 FIT / 同头切片；`UID_SET_ENUMERATION: RULE_BOUND_NOT_LISTED` + 规则 SHA；与 T（A=CIC_DEV，B=UNSW_DEV）隔离 | **已闭合（规则级）** |
| **B. 同头 D0** | **选择 B1**：不重建两折 DENSE / 不补算同头 D0；S 当前**不可运行**；结项标签预登记为 `PROTECTION_EVIDENCE_INSUFFICIENT`（材料不足）——**不是** `INFEASIBLE`，也不开源 1C。依据见 §4 | **已闭合 = B1** |
| **C. 唯一半径** | 见 §3：每参考 k=5 近邻局部半径；`J2_local` = 1C/2C **联合第二距离**（Codex 强制命名；**禁止**再平方）；线性 `clip(1−J2_local,0,1)` 唯一 | **已闭合** |
| **D. 数值门与失败序** | `G_min_pp=5.0`；源保护 `Δg_pp≤1.0`；失败序与三 seed float64 **算术平均**见 §5 | **已闭合** |
| **E. 资源硬限** | RSS≤7.5 GiB；墙钟≤4 h；距离对数 ≤ min(公式上界, **2e9**)；单机不分布式；超限即停、不自动扩预算 | **已闭合** |

---

## 3. 完整公式与集成

### 3.1 局部半径（唯一算法）

绑定正常参考集 `R_S`：与 S 同折、同协议 selected bank、整库窗口/帧交付后启用的**正常**参考 UID（查询不参与尺度拟合；禁止自匹配）。

对每个参考 `r ∈ R_S`（排除自身后）：

```
ρ_z_local(r) = z-空间中 r 到 R_S\{r} 的第 k 近邻距离（沿既定 E3 / 源 normalizer）
ρ_q_local(r) = q-空间（q14）中同上
k = 5（写死；禁止运行后改 k / 改分位）
```

零半径与除零语义沿用生产 `_ratio`：`ρ=0 ∧ d=0 → 0`；`ρ=0 ∧ d>0 → +∞`。**不**用隐式 epsilon 改写合法零半径。另设 `ε_quality = 1e-12`：**仅**当半径估计非有限 / 质量失败时触发回退，不把合法零半径替换为 ε。

### 3.2 联合距离与线性支持（唯一）

```
J_local(x, r) = max( dz(x,r) / ρ_z_local(r) , dq(x,r) / ρ_q_local(r) )   # 按 _ratio
```

按既定 1C/2C 资格与顺序统计取**联合第二距离**，记为 `J2_local(x)`（名称 = joint-second；**不是**对标量再平方的软化强度）。**实现禁止对 `J2_local` 再平方一次。** Codex 原文强制该命名语义；本 r1 **不**采用 `J_local×J_local` 作为软化曲线。

```
质量或资格不满足：a_new(x) = a0(x)          # 显式回退；禁止 0×NaN
质量与资格满足：  a_new(x) = max( a0(x), clip(1 - J2_local(x), 0, 1) )
```

- **线性支持唯一**；删除一切平方软化备选。
- 单 seed 额外降分解释：`.25 × scale × (a_new − a0)`；新分数仍按既有 RAW→修正的确定算术路径生成。
- **三 seed 集成：** 固定顺序 **27 → 127 → 227**；`score_ens = mean([s27,s127,s227], dtype=float64)`（**算术平均，非和**）；严格 `score_ens > ensemble_cut`（float64）。与 `audit_reachable_bounds.py` / 179700 离线核验一致。
- λ=.25、scale、cut、参考窗口沿用密参考主线合同；引入源折头则绑**各自同头**参数，不搬主头阈值到另一折头。

### 3.3 硬禁止（继承并收紧）

禁止：平方软化；平行候选；转源 Atomi 1C；自动/本轮重建两折 DENSE；把目标 B 余量 **0.966594323pp** 搬作源预算；目标标签逐查询关门；未授权计算；字段未齐强跑。

---

## 4. S / T 与 D0 取舍依据

### 4.1 S 身份（规则绑定）

**主线锚（T 与评分身份，只读披露）：** job **179700** 密参考 R-DENSE / QUERY_TAIL V3；seed **27/127/227**；λ=.25；主口径 `post_window_primary`；正式评价池 **A=CIC_DEV，B=UNSW_DEV**。

**S（源诊断）绑定意图：** 在上述评分身份可对齐的前提下，于**源折原 FIT / 同头**切片上检验正常修复与攻击保护——优先 G0/G1 的 BASE/CTX 头与三 seed 集成；开发若用 HELD，仅 `HELD ∩ 原 FIT` 且**排除原 CAL**。

**UID 枚举（找不到本轮可粘贴的 UID 全集时）：**

```
UID_SET_ENUMERATION: RULE_BOUND_NOT_LISTED
dataset/source_rows: SOURCE_ROW_BINDING.npz + UID_ROLE_LEDGER.jsonl.gz under runs/one_component_readonly_inventory_v1_20261028/analysis/
source_uid_sha256(full ledger)=da9e90297ce28ac97b298eb6ff37964b7abede42c4df39189c9c882ad82641f8
S_query_folds: G0 and G1
S_query_role: original_role==FIT only; if HELD used, take HELD intersect original FIT and EXCLUDE original CAL
S_normal_UID: rows with normal label in above FIT slice; denominators retain parent population weights (SOURCE_ROLE_COVERAGE weighting_note)
S_attack_UID: rows with attack label in above FIT slice; group-g attack denominators from same ledger groups
S_ref_normal: same-fold bound normal reference bank for the diagnostic head (selected bank after full-window/frame delivery); query must not enter scale fit; no self-match
heads/seeds: diagnostic heads G0_BASE / G0_CTX / G1_BASE / G1_CTX aligned to dense mainline seed order (27,127,227); ensemble float64 mean
FIT_condition: own-head FIT logits + fold DENSE geometry/scale/calibration + per-UID DENSE margin REQUIRED for runnable S; currently missing per SOURCE_SCORE_ASSETS.json
population_sha: G0_FIT uid_sha256=2d985964259af13ec22d22047420acd47b8144744c56ede822ab0417c5a2115b indices_sha256=26694a4c10284747415aeba59f8e28779d050a69a2c36423e6c8004f4e672981; G1_FIT uid_sha256=fe67b837e5342bcabd3f5a666a11c05a90613b4b37c5394703a89beb7705b7c8 indices_sha256=ae11086dab6f4b8b68a23e6a99740129cb8e9048492a560658e151c0d334cc85
T_isolation: A=CIC_DEV B=UNSW_DEV from job 179700 R-DENSE / QUERY_TAIL V3 dense formal eval; T UIDs NEVER enter S parameter choice
```

- `UID_RULE_SHA256 = 18b22659beac9b55922d29645d18d5f26258a561c595ba9fe56d7806678860ef`
- 路径锚：`runs/one_component_readonly_inventory_v1_20261028/analysis/SOURCE_ROW_BINDING.npz`、`UID_ROLE_LEDGER.jsonl.gz`、`SOURCE_ROLE_COVERAGE.json`（coverage SHA `312453e48b866104f1653bd5b8ef92b7c9be736a4a0b77781dc757925db8515a`）
- **禁止**空话「HELD∩FIT」而不写取法；上表即为可机器枚举规则。

**S ↔ T 隔离：** T 分账（含 TP Link 零 support、Samsung/WEMO、HeimVision 等）**只进未来 T**；其结果**禁止**反向选参或改 S 门。S 推进通过且另有授权后，才对 A/B 算新结果。

### 4.2 同头 D0 取舍 = **B1**

**选择 B1：不重建两折 DENSE / 不补算同头 D0。**

**依据（已有文档，非新盘点）：**

1. `SOURCE_SCORE_ASSETS.json` `missing` 明确列出：`own-head FIT logits`；`fold-specific DENSE reference/geometry/scale/calibration baseline`；`fold-specific DENSE per-UID margin`；且全部 12 个 endpoint `own_head_FIT_scores_saved=false`。
2. `DATA_AND_PROTECTION_GAPS.json`：两池均写 `fold DENSE baselines not built`。
3. 假说审阅 / 预登记审阅均指向同一缺口，并反对再泛化盘点代替取舍。

因此：S 所需 own-head FIT logits、折内 DENSE 参考/几何/scale/校准、逐 UID margin **当前不可用**且本候选**不纳入重建预算** → 本候选在 S 上 **不可运行**。预登记结项标签：`PROTECTION_EVIDENCE_INSUFFICIENT`（**材料不足**）。  
**不是** `INFEASIBLE`（非机制数学失败）；**不**开源 1C；**不**选 B2（无只读证据显示上述材料已在磁盘且可写入路径）。

可同时记录：`stop_reason`（若未来因预算停）与 `evidence_status=PROTECTION_EVIDENCE_INSUFFICIENT`（科学证据状态）；二者非强制互斥。

**B2 未选：** `D0_PATHS` = （空 / 不纳入）。

---

## 5. 数值门与失败序

### 5.1 度量（Codex 建议，百分点）

```
G_pp   = 100 × (修复正常权重) / (S 全部正常权重)
Δg_pp  = 100 × (新增撤回攻击权重) / (组 g 全部攻击权重)
```

原 FN、RAW→D0 既有撤回与新 Δg **分别入账**。

### 5.2 预登记门（设计承诺；允许后被 Codex 改数）

| 门 | 数值 | 理由 |
| --- | --- | --- |
| `G_min_pp` | **5.0** | S 上非平凡修复下限；低于则机制无选择性 / 无效 |
| 源保护 `Δg_pp` 上限 | **≤ 1.0** | S 无独立 99% 合同；取设备累计撤回合同 1pp 的同源收紧；**禁止**搬用目标 B 余量 0.966594323pp |
| 目标 T 合同（仅 T；不套 S） | 池/设备 FPR≤2%；召回≥99%；设备累计撤回≤1pp；activity/annotation≤5pp | 与 Codex/前稿一致 |
| 正式成绩锚（勿改） | A **3.993482% / 100%**；B **9.519654% / 99.966594%** | 本 r1 无新成绩 |

`a_new>a0` / support 增益 = **仅机制读数**；不足以跨 cut 不计修复。

### 5.3 失败判定序（写死）

1. **资源超限** → 停（记资源停；可并行保留 `evidence_status`）。
2. **D0 缺失（B1）** → `PROTECTION_EVIDENCE_INSUFFICIENT`（本 r1 预登记主结项路径）。
3. **G_pp < G_min_pp** 且保护门已通过 → `NO_SELECTIVITY`。
4. **保护门破**（任一必要组 `Δg_pp` 超上限等）→ `SAFETY_FAIL`。
5. **字段未齐试图跑** → **不跑**（非失败标签；保持未就绪）。

`INFEASIBLE` 保留原义：明确冻结规则族被证明无法达登记目标；**材料缺失 ≠ INFEASIBLE**。主 ensemble 有否决权；单 seed 为报告项（除非另文升级）。

---

## 6. 资源硬限（意愿预算）

结合历史 `OUTER_RESOURCE_RSS_LIMIT ~8GiB`，本候选意愿预算写死：

| 资源 | 硬限 |
| --- | --- |
| RSS | **≤ 7.5 GiB** |
| 墙钟 | **≤ 4 h** |
| 距离计算次数 | 上界公式 `≤ Σ_b Q_b × R_b`（另计参考间尺度准备时 `≤ Σ_b R_b(R_b−1)/2` 若实现需要）；**绝对帽 2×10^9**；取公式与帽的较小者；超则停 |
| CPU | 不强制核数；**单机、不另开分布式** |
| 运行次数 | **一次**；0 自动追加；超任一硬限 → 停，**不**自动扩预算 |

说明：B1 下本候选预定**不跑**距离；上表仍冻结，以免「未设预算却假称已超限」。计入任何未来另授权之 D0/参数准备时，不得突破上表除非用户另授。

---

## 7. 授权边界

- `candidate_status: PRE_REGISTRATION_SPEC_R1_PENDING_CODEX_REVIEW`
- `execution_authorized: false`
- `support_or_new_distance_authorized: false`
- `baseline_rebuild_authorized: false`
- `readonly_inventory_authorized: false`
- `source_1c_status: DEFERRED_UNTIL_AB_PATH_NEEDS_IT`
- 本文不授权：训练 / 新距离 / support / 前向 / 基线重建 / 泛化盘点 / 改实验代码 / 改原规格与 Codex 回覆
- 唯一候选；不 `INFEASIBLE`；不平行；不转 1C
- 正式成绩仍为 A **3.993482% / 100%**；B **9.519654% / 99.966594%**

---

## 8. 请 Codex 四问

1. **五阻断是否闭合？** A–E 是否已从 UNKNOWN 收束为可审的唯一决定（含规则级 S 与 B1）？
2. **B1/B2 取舍是否接受？** 在既有 `SOURCE_SCORE_ASSETS` / `DATA_AND_PROTECTION_GAPS` 证据下，接受 B1 → `PROTECTION_EVIDENCE_INSUFFICIENT`（非 INFEASIBLE、不开 1C）？
3. **数值门是否要改数？** `G_min_pp=5.0`、源 `Δg_pp≤1.0`、失败序、float64 算术平均是否需调整？
4. **是否仍不授权运行？** 请确认：即便本 r1 审阅通过，也**不**自动授权距离/support/前向/重建/盘点；任何计算须另文或用户显式授权。

---

本文件状态唯一有效句：`candidate_status: PRE_REGISTRATION_SPEC_R1_PENDING_CODEX_REVIEW`
