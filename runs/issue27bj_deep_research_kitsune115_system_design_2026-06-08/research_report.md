# Kitsune115 / Gotham2025 Low-OOD-Alert Few-Shot Online NIDS Research Report

## Scope

This report is a problem-driven research and design note for the current Gotham2025 Kitsune115 mainline. It is not a model result, not a formal benchmark, and not a protocol change. It assumes:

- frontend fixed: Kitsune / AfterImage / netStat 115D online statistical features;
- split fixed;
- final/report-only roles are never used for model selection, threshold selection, prototype selection, region routing rules, or review-budget tuning;
- issue27bh found the dominant failure in the raw-score layer;
- issue27bi found that calibrated two-head, logistic fusion, and simple LDA/prototype metric variants do not reach the attack hard-min gate `>= 0.93`.

## 一、当前问题重新定义

当前失败不是一个普通二分类器没调好的问题，而是四个矛盾同时耦合：

1. support-query gap  
Few-shot support 是少量已标注攻击样本，但 future query attack 可以来自不同文件、不同 attack phase、不同设备、不同强度区间。Few-shot support-query shift 文献明确指出，传统 few-shot 默认 support/query 同分布，这在现实场景会明显失效。对应到我们这里：support_val 可能高，但 medium pseudo / dev-heavy query 仍掉。

2. attack/OOD overlap  
OOD benign tail 和 attack tail 在 115D 统计特征空间里部分重叠。若把 OOD 直接当强负类硬压，模型会学成“少报警”，导致 OOD 降了、attack 也一起掉。

3. region conflict  
medium 和 heavy 两类只是当前观察到的两个 attack region。救 heavy 容易伤 medium，救 medium 又可能不覆盖 heavy。未来攻击族更多时，不能用“每个攻击族一个 head”的方式无限扩展。

4. online cost / update cost  
真实在线 NIDS 不能每个 packet 与数十万训练样本逐个算距离，也不能频繁重训大模型。系统必须用 bounded memory、top-k routing、prototype compression、delayed/controlled online update。

### 分层定位

| 层级 | 当前问题 | 证据/含义 |
|---|---|---|
| scorer 层 | raw attack score 对 query attack 不稳定 | issue27bh: two-head/shared 的 dominant failure 是 `raw_score_layer` |
| metric/region 层 | support 到 pseudo/query 距离结构不可靠 | support-query q50 gap 明显；bank-only 不能保住 medium/heavy |
| OOD gate 层 | OOD veto 容易误杀 attack | issue27ba/bd 说明 naive OOD suppression 会 attack-destructive |
| online update 层 | 新攻击 region 如何加入、如何不遗忘旧 region | active-labeled heavy 能救 heavy，但会引入旧区伤害/成本问题 |

### 为什么不能继续几条直觉路线

- 不能只调阈值：阈值只能在已有 score 上移动，issue27bh/bi 说明 raw score 本身已掉。
- 不能直接上 full：medium diagnostic 还没过 attack hard-min `0.93`，full 只会更贵地复现失败。
- 不能继续堆 prototype bank：issue27bf 显示 bank-only 不够；距离 evidence 需要更好的 embedding / scorer 支持。
- 不能每个攻击族一个 head：head 数随攻击族线性增长，在线成本、校准成本、遗忘问题都会失控。
- 不能把 OOD 当普通负类硬压：会得到低 OOD alarm 但 attack collapse。

## 二、候选技术路线调研

### A. Calibrated two-head / teacher-guided fusion

核心思想：保留 medium/head 与 heavy/head 的局部 attack signal，用 calibrated margin 或 teacher-student 融合产生统一 attack evidence。

解决痛点：避免 shared scorer 把不同 attack region 压成一个保守边界；保留旧 two-head 中相对有效的 region-specific signal。

结合方式：two-head 仍只作为 dev-side teacher；student 输出统一 attack evidence，不直接变成每 region 一个永久 head。

在线实时：中等。若只保留一个 student scorer，实时成本稳定；若长期保留所有 teacher heads，不可扩展。

风险：issue27bi 的 logistic fusion 已经不足，说明简单分数融合不够；需要 teacher-guided representation 或 calibrated margin，而不是再做概率拼接。

定位：支线/过渡机制，不适合作最终系统主体。

### B. Region-aware metric embedding

核心思想：学习 115D -> 16/32D 轻量 embedding，使 attack regions 与 benign/OOD regions 在距离结构上更清楚。

解决痛点：raw score 层泛化差，prototype bank 在原始 115D 子空间里不够稳定。Metric embedding 可以把 support-query gap 显式变成距离学习目标。

结合方式：输入仍为 Kitsune115；训练只用 ID/OOD/support_train/support_val/pseudo-dev；输出 embedding、region prototypes、coverage radius。

在线实时：好。115D 到 16/32D 的线性/小 MLP 映射 + top-k prototype 查找成本低。

风险：少量 support 下容易过拟合；如果 pseudo-query 构造不严谨，会变成 dev overfit。

定位：下一步主线候选。

### C. Supervised contrastive / triplet / center loss embedding

核心思想：监督式对比学习把同类/同 region 样本拉近，把 attack 与 ID/OOD 拉开。SupCon 用标签构造正负对；triplet loss 用 anchor-positive-negative margin；center loss 使用类中心约束。

解决痛点：二分类器只学边界，不保证 support-query 距离结构。对比/三元组目标可让 medium/heavy 保持局部结构，同时远离 benign/OOD。

结合方式：用 dev-side episodes 构造 pairs/triplets：medium support vs medium pseudo、heavy support vs heavy pseudo、attack vs ID/OOD/stress。

在线实时：好，训练稍重但推理只需 embedding + distance。

风险：batch 构造、hard negative mining、温度/边距会引入额外超参；需要严格禁止 report-only 参与 mining。

定位：主线候选，但第一步应做 lightweight smoke。

### D. Prototypical / nearest-class / prototype shell

核心思想：Prototypical Networks 学习一个 metric space，在其中按 prototype 距离做分类；prototype shell 用 inner/outer radius 表示可信区域和边界区域。

解决痛点：support bank 不应只是点集合，还应有半径、shell、coverage、unknown 判定。

结合方式：每个 attack region、ID region、OOD region 各维护 bounded prototypes 与 radius。输出 `near_attack`, `near_benign`, `conflict`, `unknown` evidence。

在线实时：好。若 prototype 数受控，单样本距离计算很小。

风险：原始 115D 空间 shell 已被证明不够；需要与 metric embedding 结合。

定位：主线组件，不单独作为完整方案。

### E. Attack evidence scorer + OOD risk scorer 双通道

核心思想：attack score 负责高召回，OOD risk 负责识别“这个报警可能是 benign drift false alarm”，controller 再决策 hard/suppress/review。

解决痛点：避免一个 scorer 同时“检 attack”和“压 OOD”，造成 OOD 低但 attack 也没了。

结合方式：attack evidence 使用 metric/scorer；OOD risk 使用 ID/OOD/stress prototypes、energy-like margin、OOD calibration。

在线实时：好，两个轻量通道并行即可。

风险：controller 规则复杂，容易被 dev 过拟合；必须预注册 review budget 和 rule grid。

定位：最终系统主线架构。

### F. Selective controller with bounded review

核心思想：Selective classification / reject option 不是把不确定样本全丢给人工，而是在固定 review budget 下只保留最高价值冲突样本。

解决痛点：attack/OOD overlap 无法二值硬分时，用 bounded review 控制风险和人工成本。

结合方式：controller 输出 `hard_alarm / suppress / bounded_review / unknown_buffer`；review top-B 只按 dev-calibrated conflict score 排序。

在线实时：好。只需维护每个时间窗/批次 review quota。

风险：如果 review 率过高，系统不可部署；如果 review 阈值用 final 调，会污染。

定位：主线组件。

### G. Top-k region routing / bounded expert / MoE-style conditional routing

核心思想：MoE 用 gate 只激活少量 experts；在本项目中，expert 不一定是大模型，可以是 region-specific calibration、prototype shell、radius、score correction。

解决痛点：未来 attack region 多，不能无限 head；top-k routing 控制实时成本。

结合方式：embedding 后找 top-k attack regions，只计算这些 region 的 shell/risk/evidence；全局 scorer 提供候选分数。

在线实时：好，`O(k*d)` 或 ANN `O(log R)`。

风险：routing 错会漏掉正确 region；需要 unknown buffer 和 fallback global scorer。

定位：主线扩展机制。

### H. Exemplar memory / region registry / online update

核心思想：持续学习中用 exemplar memory 保留旧类代表样本，避免新类加入时遗忘旧类。iCaRL 是代表性方法。

解决痛点：active labeling 得到新攻击后，不能简单 append 后重训，否则救 new 伤 old。

结合方式：每个 region 有预算、utility、age、coverage、merge/retire policy。新样本先进入 pending buffer，经人工确认后才加入 registry。

在线实时：中等。查询实时，更新可异步。

风险：标签成本、memory maintenance、region merge 错误。

定位：后续在线系统组件，medium 阶段先做模拟。

### I. ANN / FAISS-style prototype retrieval for full-scale deployment

核心思想：FAISS/HNSW 用近似最近邻索引支持大规模向量检索。FAISS 支持 L2/dot-product vector search；HNSW 用分层小世界图做高效 ANN。

解决痛点：full dataset 或在线多年 memory 下，prototype/region 数可能增长。

结合方式：小规模先 exact distance；当 prototype 超过约 10k 或查询吞吐上来，再切 FAISS/HNSW。

在线实时：好。ANN 是成熟部署技术。

风险：近似误差可能影响 security decision；需要 recall audit 和 exact fallback。

定位：全量/部署扩展支线。

### J. Active labeling under mixed incoming stream

核心思想：active learning 从未标注流中选择最有价值样本请求标签。现实 incoming stream 中未知样本不一定是攻击，也可能是 ID/OOD/noise。

解决痛点：support 不覆盖未来攻击时，系统不能假装确定；需要 unknown/review/label budget。

结合方式：只能按无标签 feature/evidence 选样本：high conflict、far from all regions、high attack score but low coverage。标签在选择后才由人工/oracle 给出。

在线实时：可行，但人工链路必须有预算。

风险：如果 incoming stream 攻击比例低，labeling yield 低；必须报告 labels-per-useful-attack-region。

定位：论文创新支线/系统机制，不能先作为核心性能结果。

## 三、三套可实验系统方案

### 方案 1：Metric Evidence + Prototype Shell Controller

核心机制：轻量 115D -> 16/32D metric embedding；ID/OOD/Attack prototype shell；controller 使用 attack evidence、benign distance、OOD risk 和 shell conflict。

训练数据：ID fit/calib、OOD train/val/stress、medium support train/val/pseudo、active-heavy support train/val/pseudo。禁止 final/report-only。

在线推理流程：

1. extract Kitsune115;
2. embedding `z=f(x)`;
3. compute nearest ID/OOD/Attack prototype distances;
4. compute attack evidence score;
5. controller outputs hard/suppress/review/unknown.

如何处理 support-query gap：用 pseudo-query 和 active-heavy dev query side 的合法 dev subsets 做 metric objective，约束 support 与 harder query 接近。

如何处理 attack/OOD overlap：若 attack 和 OOD 都近，进入 bounded review；若 attack strong 且 OOD not dominant，hard alarm；若 attack weak 且 OOD strong，suppress。

如何处理多攻击族扩展：新 attack region 进入 bounded registry，不新建完整 head。

实时成本：线性 embedding + top-k prototype lookup。

review 成本：固定每窗口 top-B conflict score。

实验表：embedding_audit.csv, prototype_shell_audit.csv, controller_decision_table.csv, support_query_gap_after_metric.csv, review_budget_table.csv。

Go / No-Go：dev attack hard-min >= 0.93；review <= 5%；OOD stress not explosively worse than previous best; no final/report-only tuning.

最大风险：metric objective 仍不能跨 support-query shift 泛化。

### 方案 2：Teacher-Guided Region Metric Student

核心机制：two-head 作为 teacher，输出 medium-like/heavy-like soft evidence；student 学一个统一 metric/evidence space，但保留 region identity。

训练数据：two-head teacher 只在合法 support/dev roles 上产生 soft labels；student 用 ID/OOD/support/pseudo train。

在线推理流程：

1. `x115 -> student embedding`;
2. student attack evidence;
3. top-k region calibration;
4. OOD risk channel;
5. selective controller.

如何处理 support-query gap：teacher 不直接最终决策，只给 region-aware soft target；student 被 pseudo-query constraints 拉向 query-compatible representation。

如何处理 attack/OOD overlap：OOD risk 不并入 attack score，只进入 controller。

如何处理多攻击族扩展：teacher heads 是训练期工具，部署时不保留无限 heads；region registry 保留 prototype/calibration。

实时成本：student 一个小模型 + top-k prototypes。

review 成本：controller fixed budget。

实验表：teacher_signal_audit.csv, student_metric_audit.csv, region_retention_delta.csv, old_vs_new_region_interference.csv。

Go / No-Go：medium/heavy/pseudo dev attack hard-min >= 0.93; adding heavy does not reduce medium below 0.93.

最大风险：teacher 自身偏差被 student 继承。

### 方案 3：High-Recall Attack Candidate + OOD Risk Decoupled Selective System

核心机制：先训练 high-recall attack candidate scorer，不强压 OOD；单独训练 OOD risk scorer；controller 再做 low-OOD-alert decision。

训练数据：attack scorer 使用 ID + support + pseudo attack，OOD 只作为 limited negative 或不进入主 attack loss；OOD risk scorer 使用 ID/OOD/stress only。

在线推理流程：

1. attack scorer emits candidate score;
2. if low attack score -> no alarm;
3. if candidate -> compute OOD risk and region compatibility;
4. controller hard/suppress/review/unknown.

如何处理 support-query gap：attack scorer 用 high-recall objective + region memory；query gap 不由 OOD negative 硬压。

如何处理 attack/OOD overlap：OOD scorer 只 veto weak attack, cannot kill strong attack core.

如何处理多攻击族扩展：attack evidence scorer global, region memory local.

实时成本：两个 small scorers + few prototype distances。

review 成本：selective budget.

实验表：attack_candidate_recall_table.csv, ood_risk_table.csv, weak_veto_vs_strong_override.csv, review_cost_table.csv。

Go / No-Go：candidate recall dev attack >= 0.97 before OOD controller; final controller attack hard-min >= 0.93 in dev; review bounded.

最大风险：candidate scorer causes too many alarms, controller overloaded.

## 四、推荐 issue27bj 实验设计

推荐：`issue27bj_metric_evidence_shell_controller_smoke`

下一步最值得做的不是继续调 calibrated two-head 或 OOD gate，而是做一个小而硬的 metric evidence + prototype shell smoke。原因：issue27bh/bi 说明 raw score 层 support-query 泛化不稳；若没有更可靠的 evidence space，OOD gate 再修也会继续误杀 attack。

### issue27bj 任务边界

- 不改 115D 前端。
- 不改 split。
- 不重新构造 support pool。
- 不上 full。
- 不使用 final/report-only 选参数。
- 不做正式 benchmark。

### Stage 0：role and artifact audit

读取 issue27af/ba/bh/bi certificate 和 summary；验证 hash、role access、final/report-only 封印。

### Stage 1：metric objective smoke

候选只做轻量：

- linear supervised metric: 115D -> 16D;
- triplet/center-margin small MLP: 115D -> 16D, max 1 hidden layer;
- no large deep model.

训练 pairs/triplets 只来自 legal dev roles：

- attack positive: same region support_train/support_val/pseudo;
- attack hard positives: support_train vs pseudo-query;
- negatives: ID/OOD/stress;
- region separation: medium and heavy not forced into one centroid.

### Stage 2：prototype shell

在 embedding 上建立：

- ID prototype shell;
- OOD/stress prototype shell;
- medium attack shell;
- heavy attack shell;
- unknown radius.

### Stage 3：fixed controller replay

只用 dev roles 选 controller rule：

```text
 if attack_evidence weak -> no_alarm
 if strong_attack_core and not OOD_dominant -> hard_alarm
 if weak_attack and OOD_dominant -> suppress
 if attack/OOD conflict -> bounded_review
 if far_all -> unknown_buffer
```

### Stage 4：report-only replay

Replay medium_attack_eval_report_only, dev_heavy_query_report_only, final_ood_report_only only after rule freeze. Report, do not select.

### Required outputs

- metric_training_contract.md
- metric_embedding_audit.csv
- triplet_or_pair_sampling_audit.csv
- prototype_shell_audit.csv
- controller_rule_grid_dev_only.csv
- controller_replay_report_only.csv
- support_query_gap_after_metric.csv
- review_budget_audit.csv
- role_access_audit.csv
- issue27bj_decision.md

### Go / No-Go

- Go to OOD repair diagnostic only if legal dev attack hard-min >= 0.93 and review <= 5%.
- Partial only if 0.80-0.93; do not enter OOD gate.
- No-Go if metric fails to improve support-query gap or report-only shows task-boundary mismatch.

## 五、实时性与全量扩展分析

### Per-sample cost

Let `d=115`, embedding dim `m=16/32`, number of regions `R`, prototypes per region `P`, top-k regions `k`.

- 115D extraction: fixed Kitsune frontend cost; already accepted.
- Linear embedding: `O(d*m)`, about 1.8k-3.7k multiply-adds.
- Small MLP: roughly `O(d*h + h*m)`, still small for h=64.
- Exact prototype search: `O(R*P*m)`.
- Top-k routed exact search: first region centroids `O(R*m)`, then `O(k*P*m)`.

For `R=32`, `P=32`, `m=16`, exact is about 16k distance ops/sample, feasible. For `R=512`, `P=64`, exact is about 524k scalar ops/sample, still possible in batch but may be high for line-rate packet stream.

### When FAISS/HNSW is needed

- Not needed for current medium.
- Consider FAISS/HNSW when prototype count exceeds 10k, query throughput is high, or region registry grows continuously.
- HNSW supports fast ANN with controllable recall; FAISS supports efficient dense vector L2/dot-product indexing and compression.
- Security setting requires ANN recall audit and exact fallback for high-risk samples.

### Full dataset scaling

If full dataset expands 10x:

- materialization/storage dominates offline;
- prototype search still fine if compressed;
- training metric head may need mini-batch/streaming pair sampling.

If full dataset expands 100x:

- metric training and memory registry maintenance become bottlenecks;
- need reservoir/exemplar sampling, region merge, retire policy, ANN index.

### Memory policy

- `prototype_budget_per_region`: start 16/32, cap 64.
- `region_merge`: merge if centroid distance small and cross-region confusion low.
- `region_retire`: retire stale regions with low utility and no recent support.
- `memory_compression`: k-center or herding per region, keep boundary prototypes and high-utility exemplars.
- `audit`: every update logs region_id, source, label source, timestamp, hash.

## 六、实验纪律

Strictly forbidden:

- no final OOD for parameter selection;
- no `medium_attack_eval_report_only` for selection;
- no `dev_heavy_query_report_only` for selection;
- no threshold overfitting to current medium results;
- no full benchmark until medium diagnostic gates pass;
- no review-as-trash-can;
- no unbounded per-attack-family head design;
- no 115D frontend changes;
- no split changes;
- no report-only-driven active labeling.

## Sources

- Kitsune online NIDS frontend: [Kitsune](https://arxiv.org/abs/1802.09089)
- Support-query shift: [Bridging Few-Shot Learning and Adaptation](https://arxiv.org/abs/2105.11804), [Dual Adversarial Alignment](https://arxiv.org/abs/2309.02088)
- Metric/prototype learning: [Supervised Contrastive Learning](https://arxiv.org/abs/2004.11362), [Prototypical Networks](https://arxiv.org/abs/1703.05175), [FaceNet / triplet loss](https://huggingface.co/papers/1503.03832)
- Domain adaptation/alignment: [Deep CORAL](https://arxiv.org/abs/1607.01719), [DeepJDOT](https://arxiv.org/abs/1803.10081)
- OOD/open-set: [Outlier Exposure](https://arxiv.org/abs/1812.04606), [Energy OOD](https://arxiv.org/abs/2010.03759), [Unified anomaly/OOD/open-set survey](https://arxiv.org/abs/2110.14051)
- Selective/reject/conformal: [SelectiveNet](https://arxiv.org/abs/1901.09192), [Conformal prediction intro](https://arxiv.org/abs/2107.07511)
- Routing/memory: [Sparsely-Gated MoE](https://arxiv.org/abs/1701.06538), [iCaRL](https://arxiv.org/abs/1611.07725)
- Scalable lookup: [FAISS official GitHub](https://github.com/facebookresearch/faiss), [HNSW](https://arxiv.org/abs/1603.09320)
