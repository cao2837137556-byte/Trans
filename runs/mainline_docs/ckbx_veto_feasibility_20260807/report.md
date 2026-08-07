# CKBX 前置诊断：C1-margin veto 可行性裁决（只读，seed 27）

- 日期：2026-08-07
- 执行：Kimi（三方协同：GPT 方案讨论，Codex 8 月 10 日回归评审）
- 输入（全部只读，未训练、未改模型、未触碰 FINAL 数据 cooler-motor / seed 37/47）：
  - CKBW 结果表 `ckbw_record_predictions.csv.gz`（job 157624，297,326 行）
  - CKBQ 结果表 `ckbq_record_predictions.csv.gz`（job 153037，277,326 行）
- 输出目录：`runs/mainline_docs/ckbx_veto_feasibility_20260807/`（本文件 + figures/ + 5 张 CSV + 2 个 JSON）
- 复现脚本：同目录 `diagnostic_script.py`

## 1. 诊断问题

CKBW（M7 = 冻结 CKBQ + 51D tail-margin 双阈值控制）把 OOD 误报压到 macro 0.0015 的
同时，把 future 隐蔽攻击召回压掉 23.64pp（Merlin C&C 从 C1 的 0.998 掉到 0.045）。
A+C 方案（记录级证据仲裁）假设：C1 的分数里仍含有"这是攻击不是良性 OOD"的信息，
可以用一个统一 veto 规则 `V = [c1_margin >= δ]` 把被 M7 压掉的攻击救回来：

```
H(δ) = M7 OR V(δ)        （Level 1：一维 margin veto）
H2(δ) = M7 OR (被M7压掉 AND V(δ))   （Level 2：单调二维区域的最优情形）
```

其中 `c1_margin = c1_score − 0.998085199899140`（C1 阈值全局单一值，已核验）。
M7 判定公式已逐行反推验证：`M7 = frozen_ckbq_hard AND (tail_margin_score >= 0.971323)`，
即 suppress 条件是 tail 分**低于** τn（tail 分高 = 像攻击，保住；低 = 压掉）。

两层 frontier（GPT 四轮讨论锁定）：
- **Oracle 层**（VIEWED 诊断池：future 隐蔽攻击 6 族 vs 4 个已看 OOD 池）——只回答
  "信息存不存在"，产出定性假设，不允许带出数值 cut；
- **Legal 层**（合法 select 池：aux_select 3,000 + ToN normal_2 4,000；support 攻击验证 69）——
  回答"合法规则能不能选出可用的 δ"。

## 2. 核心发现（全部为 seed-27 实测）

### 2.1 veto 召回天花板直接封死 7/8 个攻击 family

veto 最激进情形（δ→−∞，命中所有 c1_hard 行）下各族召回上限 = c1_hard 比例：

| attack family | veto 上限 | 是否够 0.90 |
|---|---:|---|
| Merlin C&C Communication | 0.998 | ✅ 唯一达标 |
| Reporting | 0.742 | ❌ |
| TCP Scan | 0.734 | ❌ |
| Telnet Brute Force | 0.667 | ❌ |
| Ingress Tool Transfer | 0.631 | ❌ |
| Mirai C&C Communication | 0.054 | ❌ 几乎不可见 |
| CoAP Amplification | 0.000 | ❌ |
| UDP Scan | 0.000 | ❌ |

C1 对除 Merlin C&C 外的隐蔽攻击只有弱反应甚至无反应。**任何 δ 都无法让最差族
召回达到 0.90**——oracle 有用区间不存在，与代价侧无关。

### 2.2 margin 轴方向是反的：最"像攻击"的是合法良性

C1 分数在整源尺度上饱和：

- `aux_select`（合法 select 池，5 个源 × 600 行）：**每一行 c1_score = 1.0**（全局最大值，
  margin = 0.001915，全组仅 1 个取值）；
- `predictive-maintenance` OOD 池 9,000 行同样全部 1.0；
- `ip-camera-street` / `stream-consumer` 各有 31.1% / 23.1% 行并列在 margin = 0.001573；
- 而被 M7 压掉的 16,212 条攻击虽然 100% c1_hard，margin 主要分布在 0.0007–0.001569，
  **低于**上述良性池的顶端值。

后果：任何能救到攻击的 δ（≤ 0.0015），先把合法良性 aux_select 和 pm-OOD 100% 打成
误报（fig4）。Legal 层唯一满足良性预算（aux 命中率 ≤ 1%）的 δ_b = 0.001915，此时
veto 全域零命中、零救援——完全退化。LOFO（留一 aux 源）下 δ_b 不变，退化稳定。

### 2.3 Level 2 单调二维区域同样不行

把 veto 限制在"被 M7 压掉的行"内部（单调二维区域的最优情形），oracle 有用区间
依然不存在（`useful2 = False`）：压掉区里良性 pm/aux 的 margin 仍压在攻击之上。

### 2.4 附带审计结果

- **27 行基线硬告警良性**（选 τn 用的那 27 条）：全部来自 aux_select 的 4 个源，
  c1_score 全部 = 1.0（margin 分位数 1.0），CKBQ 分支 26 条 M1-static+M3-consensus、
  1 条 M1+M2+M3——即 CKBQ 的静态护盾对它们的判因一致，非异常杂散。
  明细：`audit_benign_select_baseline_hard.csv`。
- **support_val 69 身份确认**：是攻击验证行（10 个 family 的混合），h0/M7/C1 三臂
  召回均 100%；veto 命中它们无害（本就 hard），所以 δ 约束只能来自良性池，
  与 GPT 的防退化警告一致。
- **ToN 腿**：20,000 行（`ton:` 前缀）无 C1 覆盖，veto 对其恒不命中，final hard = M7 = 0；
  ToN 正常 4,000 行在 veto 架构下零代价，但原因是"没有分数"而非"分得开"，需如实说明。

## 3. 裁决

```
VERDICT: STATE_1_ORACLE_INSEPARABLE_GO_EPISODE_B
```

四态门（GPT round 3 锁定）：oracle 层即不可分 → **A+C 记录级 veto 路线终止，
不烧超算，转入 episode 级仲裁（方案 B）作为 CKBX 主干**。

两条独立致死原因（任一成立即否决）：
1. 收益侧：7/8 攻击 family 的 veto 召回上限 < 0.90，最差族天花板 0.054；
2. 代价侧：合法良性池压在 margin 全局最大值，任何有效 δ 都先打穿良性预算。

## 4. 对 CKBX（episode 级仲裁）的启示

记录级 C1 分数不含可用的"攻击 vs 良性 OOD"分离信息，但本诊断留下了三条对
episode B 设计有用的实测事实：

1. **C1 的源级饱和行为本身就是 episode 级信号**：c1_score=1.0 在整个源上恒定时
   对应良性 OOD/aux 源；攻击源的 c1_hard 比例高但不饱和（sealed_final_attack
   share_at_max = 29.3%，648 个取值）。"源内分数分布形态"比"单条分数"更有区分度——
   这正是 episode 级特征该吃的东西。
2. **被 M7 压掉的 16,212 条攻击 100% c1_hard**：episode 聚合时，"窗口内 c1_hard
   密度"对找回 Merlin C&C 类压制攻击可能有价值，但需按 episode 而非记录评估。
3. **Mirai C&C / CoAP / UDP Scan 对 C1 完全或几乎不可见**：episode 级仲裁不能指望
   C1 通路覆盖这三族，需要 51D 通路或上下文通路单独承载，并在预注册中明确
   这三族的评估口径（沿用"只诊断、不打补丁"纪律）。

注意：以上三条来自 VIEWED 诊断池，**只能作为定性假设进入 CKBX 预注册讨论，
所有数值阈值必须由 LEGAL 池重新选出**。

## 5. 产物清单

| 文件 | 内容 |
|---|---|
| `figures/fig1_margin_ecdf.png` | 各组 margin 经验分布（良性占最右端） |
| `figures/fig2_scatter_2d.png` | c1_margin × tail_margin 散点（压掉区重叠） |
| `figures/fig3_metrics_vs_delta.png` | 两层 frontier：OOD / 攻击召回 / 合法池 vs δ |
| `figures/fig4_rescue_vs_cost.png` | 收益-代价曲线（主图） |
| `figures/fig5_veto_ceiling_by_family.png` | 各族 veto 召回天花板 |
| `frontier_by_group.csv` | 全部组 × 1,300+ 个 δ 的 L1/L2 命中率明细 |
| `group_percentiles.csv` | 各组 margin 分位表 |
| `margin_quantization.csv` | 分数量化/饱和证据 |
| `audit_benign_select_baseline_hard.csv` | 27 行审计明细 |
| `suppressed_attack_rescue_by_family.csv` | 被压攻击按族的救援潜力 |
| `veto_cost_by_pool.csv` | 各良性池在关键 δ 的代价 |
| `lofo_aux_sources.csv` | LOFO 稳定性门结果 |
| `eval_points.json` / `verdict.json` | 关键工作点指标 / 机器可读裁决 |
| `diagnostic_script.py` | 复现脚本 |
