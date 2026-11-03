# Codex 对 Well 最终破局方案的审阅回复

- 日期：2026-10-25。
- 被审稿：`20261025_well_final_breakout_plan_for_codex.md`。
- 被审稿 SHA256：`4142ca06dc06892fa7c784da3efed57833885a77fc8e749dcf856bd7d60fe82a`，本次已核对一致。
- 范围：只读核对本地冻结证据并回写审阅文档；未改科研代码、原方案、模型或 V4 现场，未访问远端、运行模型、执行阶段0审计、起草执行卡、上传或启动训练。
- 结论：**支持“先做加权分账，再按证据决定覆盖／参考使用／几何路线”的方向；当前稿应先修订，不能直接作为可执行方案。** 五问逐条答复如下。

## 一、先修正四个会影响路线选择的问题

1. **CAL 攻击不能同时成为资格规则的拟合材料和同批保护证据。** “CAL 近邻禁止入资格”会改变 CAL 的数据角色；攻击还能匹配自身而自动被否决，零新增 FN 便可能成为自我保护结果。攻击原型、否决半径及规则选择应在 FIT 和源侧留出开发中完成，规则冻结后 CAL 只做最终校准／保护。不能暗中改角色而沿用旧保护声明。
2. **固定 B2 库上增加邻域门只能缩小资格，不能释放 A 原有的412条资格外 FP。** 当前资格已有完整身份、时间和真实组件约束，不是“随便有一条参考”。要扩大覆盖，必须先知道412条各自为何失败，再判断能否通过合法的参考构造改变恢复，而不是把新增几何 mask 当成扩容。
3. **阶段3的入口和比较口径有冲突。** 阶段2失败被要求转阶段3，阶段3却要求1+2先胜出；同时，“共享完整资格内已赢、全池仍输”在同头、同 cut、同原权重、资格外均回退 BASE 时不成立。几何与学习器的差分诊断应提前到阶段0。
4. **归因门应限制自身参考特异性的声明，不能扩大成对所有入网收益的否定。** 当前归因 FAIL 必须保留；但它不能证明共享正常参考无用，也不能由有限候选失败推出所有有界学习不可能达到双池目标。

## 二、问题1：阶段0三张表，哪些可复用、哪些需重算？

**同意三表设计，但第一张必须改成互斥分账，第二张要区分保存字段和几何重放，第三张应复用已有344条身份桥。** 当前本地93件小证据足够核对摘要，不足以完成完整逐查询加权分账；完整 predictions 和 control_plan 尚在远端。以下是字段和入口建议，不是本次已运行的审计。

### 2.1 先绑定实际执行版本

本次以 V4-EVAL1 的完成复核 [E1]、冻结规格 [E2] 和 V4 部署 staging 中的实际科研源码 [E3–E6] 为依据。已将 staging 的 `pipeline.py`、`reference_core.py`、`evaluation.py`、`learning.py`、`tasks.py` 的 SHA 与 V4-EVAL1 `parent_inventory.json` 对上；不能把当前顶层 `src/` 的内容直接当作实际执行版本。

将来审计输入应绑定：执行身份、pool、bank、arm、seed、预测文件 SHA、ordered UID、原头分数／cut、原分母、CAL／FIT统计身份、参考清单及 control_plan 身份。多臂重复保存的同一查询不能被当成多个独立样本，不能重新均匀化设备或重建另一套权重。

### 2.2 表1：原FP的互斥加权分账

[E3] `evaluate_pair` 第199行起已有大部分字段；[E5] 第699行起保存逐查询预测。可直接复用：

| 用途 | 已保存字段 |
| --- | --- |
| 查询和原指标 | `uid, label, device, protocol, label_metric_weight_denominator` |
| 原头及修正判决 | `base_score, corrected_score, cut, base_alarm, corrected_alarm` |
| 资格和修正 | `eligible, reason, strength, decrement, lambda_value, scale` |
| 参考追踪 | `matched_reference_uids, matched_components, legal_reference_count, legal_component_count, bank_key, bank_end, bank_end_frame, prebank_audit` |

后半组由部署 pipeline 的 trace 导出补齐，但适用范围不同：BASE及三学习臂的非EMPTY记录保存完整增强trace（包括WRONG学习臂）；V3仅补入代表UID，组件数／bank时间等字段为None或缺失，EMPTY也没有增强trace，见 [E5] 第663、671、679及713行起。不能只看 `evaluation.py` 的基础字典便断言学习臂缺失，也不能反过来假定全部52格都有完整参考元数据；V3等缺项需从冻结资产重建。

对每个固定 pool／bank／arm，令：

```text
F = normal & base_alarm
m = base_score - cut
C = lambda_value * scale
w = 1 / label_metric_weight_denominator
W_normal = sum(w over the complete normal pool)
```

把原 FP 严格分成以下四类：

| 类别 | 定义 |
| --- | --- |
| 资格外 | `F & ~eligible` |
| 有资格但cap不可达 | `F & eligible & (m > C)` |
| cap可达但尚未修正 | `F & eligible & (m <= C) & corrected_alarm` |
| 已修正 | `F & ~corrected_alarm`，并校验这些行均有资格 |

四类必须无交集且并集等于 F；每类同时报告条数、`sum(w)`、占原 FP 权重质量的比例、对全池加权 FPR 的贡献 `sum(w)/W_normal`，并按 device／protocol／失败 reason 分层。逐设备目标使用原规则下的设备分母另列，不能只看池目标。

固定资格与该臂 cap 的条件加权下界为：

```text
weighted_FP_floor = (weight(ineligible FP) + weight(cap-unreachable FP)) / W_normal
maximum_reducible_FPR = weight(eligible & cap-reachable baseline FP) / W_normal
```

当前 `normal_fp_lower_bound` 仅保存原始条数／比例，不能从它直接得到上述加权下界。[E3] 第239行的 `actual_eligible_normal_fp_remaining` 已包含超 cap 行，若再与 cap 不可达相加会重复记账。

原判决为 `score > cut`，所以 `m == C` 属于理论可达；`C == 0` 时所有原 FP 均不可达，不能把除零后的值当有效 strength。仍要校验资格外精确回退、单向降分、没有新增正常 FP，并与52格已有摘要及原加权指标闭合。不同臂的 λ 不应机械视为相同；各自用已登记的值。BASE保存的scale／λ均为0只是无修正对照，不能把它的零cap另当作学习臂的机制瓶颈。

这张表回答的是“**当前固定方法还剩多少可动质量**”，不证明这些质量有可用正常证据，也不证明换资格一定能释放原来不可动的质量。A的412/440和B的16.10%均为条数信息，加权下界目前仍未知。

### 2.3 表2：可达未修查询的几何／残差

可由保存值直接派生：`margin=m`、`cap=C`、`required_strength=m/C`（仅 C>0）、`correction_gap=m-decrement`，以及按参考数、组件数、reason、设备／协议的分层。保留原始浮点值，不用显示舍入值决定跨 cut。

以下内容未完整写入逐查询预测，需要在独立只读分析中由冻结查询／参考缓存和原 normalizer 重放：

- 两个真实不同组件代表的 `dz, dq, d, qref`，查询 q14 和参考残差；必要时重建原50维输入。
- [E4] 第276行起的定义是 `dz = clip(1-dot(z_query,z_ref),0,2)`、`dq = RMS(q14_query-q14_ref)`、`d = max(dz/2,dq)`；必须使用原归一化和稳定 UID 决胜规则，并核对代表 UID 与保存 trace 相同。
- 第353行起的第46槽（从0计数）使用 FIT 的中心 `t` 和尺度 `s`，不能替换为相对最终 decision cut 的 margin 特征。

这里的“重放”可以只做确定性几何／特征计算，不需重新跑检测头或学习器。缺参考或原始输入时记 NA 和原因，不能拿默认零向量冒充真实相似度。若缓存缺失、身份冲突或重放不符，应停止该分析并保留差异，不回头重写旧输出。

同时补一份 **V3 与 HARD 的逐 UID 差分**：同一全池分母，列共同修好／仅V3修好／仅HARD修好／都未修好，报告各格权重、实际 strength／decrement、margin/cap。把几何差分放在阶段0，便于决定是学不到有效几何、强度不足，还是根本不在同一覆盖集合。

### 2.4 表3：历史344条的当前命运

不需要重新发明身份映射。[E7] `review_historical_a.py` 第10–31行已经从 Job174251 的 `normal & Q & ~FULL` 定义选择344条，并核对 UID 及 `source_sha256/frame/owner/component_id/device/protocol/label`；[E8] 已记录344/344物理端点匹配、未匹配列表为空。

可复用该 UID 集和身份检查，**不能复用旧路径统计作为本轮 seed27 结果**。例如已保存的“当前头已判正常141条”属于此前三seed集成／几何诊断，不是本次 QUERY_TAIL seed27＋学习器的新统计。将344条重新与本轮已保存预测按 UID join，建议互斥路径为：

```text
CURRENT_HEAD_ALREADY_NORMAL
INELIGIBLE_<reason>
CAP_UNREACHABLE
REACHABLE_ZERO_STRENGTH
REACHABLE_INSUFFICIENT_CORRECTION
CORRECTED
IDENTITY_UNRESOLVED
```

路径总数必须闭合到344，记录当前原分母权重，并明确不同系统的权重不能直接互换。身份无法核实时不能静默丢行。此表只是同一物理端点在多处系统变化后的描述性追踪，不是“新头／新前端／新模块”任何单因素的因果归因。父缓存 parity 不可得，不妨碍已经完成的物理端点身份核对，也不等于旧特征可逐位重现。

### 2.5 可建议的脚本入口及数据依赖

将来另开独立审计目录，可分别设置以下入口；**本次不创建脚本或执行卡**：

| 建议入口名 | 只读输入及职责 |
| --- | --- |
| `audit_saved_fp_ledger.py` | 已封存逐查询预测＋原摘要／清单，生成互斥加权账、按reason下界和V3差分 |
| `audit_reference_geometry.py` | 原查询／参考缓存＋normalizer＋保存trace，只重放几何和原特征含义 |
| `audit_legacy344_paths.py` | 既有344身份桥＋当前保存预测，输出互斥命运表 |

这些入口应读取旧资产、写入新分析目录，不调用会前向模型并写评价结果的 `pipeline.evaluate_targets`。若后续授权阶段0，需要先补齐相关保存预测／control_plan和缓存的只读可用性；不必因此重训，也不必重新提取百万行前端缓存。

## 三、问题2：“合法邻域覆盖”的最小可差分改法

### 3.1 先区分合法性和支持度

当前资格来自 [E4] 第176–221行：自身 bank、同 partition／protocol、完整库截止严格早于 query、同 capture 的 frame 因果合法、至少两个真实不同组件；另有 prebank 历史回退。[E2] 第41–43行也已冻结这些要求。当前学习臂没有额外照搬 V3 半径内 support 门。

建议新稿显式分成：

```text
L = structurally_eligible：身份、时间、真实组件等结构资格
G = deployment_support_gate：FIT定义的正常支持／攻击否决
E = L & G
```

固定原库与 L 后增加 G，必有 `E ⊆ L`。它可减少危险修正，却无法让原 L=false 的412条进入资格。阶段0须先给出这些行按失败 reason 的权重质量，然后才有以下有条件的最小改法：

| 原因 | 可研究的独立变更 | 必须保留的边界 |
| --- | --- | --- |
| 合法早期记录存在，但被选库策略漏掉 | 同预算／截止／协议下重新分层选取真实组件 | 候选规则源侧冻结，不按A/B改善量挑规则 |
| 原库确实只有一个真实组件 | 单组件表示和缺失mask的新方法合同 | 不能复制参考凑两个组件；不能称原模型只换mask |
| 原完整库尚不可用或属于prebank历史 | 若符合实际部署，可另定义严格因果的前缀／滚动入网协议 | 不能事后只看选中的两条就倒移原完整库截止，不能用未来数据 |
| 根本无可信正常参考 | 继续原头回退，或另立确有数据条件的新方法 | 几何接近不能创造可信参考身份 |

因此目前不能指定一个有证据保证能破A天花板的“2—3个mask”。最小研究对象应由分账决定，优先判断合法 bank 构造能否恢复有价值的覆盖。

### 3.2 固定HARD检查点能回答什么

保持原50维槽位含义、两真实组件代表、normalizer、FIT t/s、头和cut不变时，可在独立 lineage 做固定权重的 bank／gate 干预诊断。即便50维形状不变，重选 bank 仍可能改变输入分布；结果不能预先保证，也不能替代新方法的训练及校准验证。

单组件、代表数改变或槽位语义改变，则旧检查点不再是有效的“同模型只换资格”比较。原 [E5] 第44行起还绑定了 FIT 的代码／runtime，不能改逻辑后绕过 seal 复用旧 FIT。旧 λ/cap 可固定用于诊断，但旧CAL seal不证明新资格已安全；后续新方法须独立冻结并做完整保护。

### 3.3 攻击否决及停刀判据应这样改

删除“CAL近邻禁止入资格”，改为 **FIT攻击构建／学习否决，源侧留出检验，规则冻结后CAL最终保护**。如果另拆 CAL 作开发材料，就属于数据角色改变的新合同，必须披露，并取得另一个未用于规则选择的保护集；不能只改名字。

还须分别报告三层攻击压力：

1. 结构合法攻击中 `0 < base_score-cut <= λs` 的静态cap可达UID／权重；
2. 部署支持门通过、且 `a>0` 的可达集合；
3. 实际 `λs*a` 导致跨cut的新增FN集合及各设备结果。

**重要源码口径：** [E3] 第105–109行现有 `cap_reachable_detected_attack_count` 是在 `eligible & (a>0)` 上计算，不能说它已经覆盖所有结构合法攻击的纯cap上界。现有最小 margin/cap≈1.0351 也对应合法正修正对。不能靠把门或a关成零后得到count=0，证明不存在潜在攻击压力。

“cap可达>0即停”比原冻结合同更严格；原保护校准依据实际新增FN选择λ。新阶段可另登记保守筛选，但应明确它是新增设计限制，不能把理论可达直接等同漏检，也不能用它排斥检验区分能力本来需要的近边界攻击。真实攻击探针与数值插值压力须分开，后者不能冒充新标注攻击证据。

## 四、问题3：own/wrong损失能否直接同构预登记？

**可复用WRONG构造规则，但当前训练数据和损失不是现成的own/wrong配对合同。** [E5] 第290行起正常任务只选own bank，[E6] 第234–238行明确 `NORMAL_OWN_BANK_ONLY`。当前WRONG是评价控制，不是训练负样本。

### 4.1 需要补全的配对合同

新配对至少写清：query UID／view／fold、own与donor bank身份、各自reference UID列表、真实N条／C组件、完整时间及frame截止、matching状态、配对计划hash、query权重和缺配对处理。

可复用 [E4] 第312行起与 [E2] 第117行的规则：错device、同partition／protocol、因果合法、精确匹配N/C、metadata和稳定字典序决定donor，无精确匹配记NOT_EVALUABLE，不能临时改成近似供体。计划在生成修正分数前冻结。增加donor不应成倍增加该query的训练质量；按query归一而不是按配对数量重复加权。

训练／源侧留出划分必须覆盖query、own与donor参考及其capture／component依赖。不能让被称为留出的设备通过donor参考进入训练，再称其独立；检测头层的未见设备与前端历史暴露也仍须分别披露。

### 4.2 不应把wrong身份直接当攻击负类

不同设备可能共享正常行为。`wrong device` 不等于错误的正常证据；对每个wrong一律强制 `a_wrong=0`，可能制造设备身份偏好并损害泛化，而未学会正常／攻击区分。

更合理的候选是保留原正常残差目标和攻击最坏合法bank保护，仅对 **FIT预先定义的“own支持强、wrong支持弱、且存在应修正常残差”** 配对加入排序／差异损失。支持相当的共享正常对不强迫拉开。这里的条件、margin和loss权重仍需源侧证据选定，目前不应伪装成已确定的数值配方。

固定“第一个可匹配donor”的评价规则要保留作主控制，同时在源侧保留未参与训练的donor／设备任务，检查是否只记住了控制模板。不能只在训练配对上实现own胜出就宣称迁移。

### 4.3 有特征门后，WRONG主比较集合必须先冻结

当前 [E5] 第728行为 `matched = e_wrong & e_own`。在资格纯metadata时有明确含义；若新资格混入几何或学习支持门，这个交集会受干预结果影响，把“own通过、wrong被拒绝”的关键行删掉。

新方法应先按结构规则冻结精确匹配集合 M，然后在M上比较两套**完整部署决定**：某一侧支持门拒绝便回退BASE，行和原权重仍保留。另报双方都激活子集，但不能用它替换主归因分母。QUERY_ONLY也须在登记的匹配支持／资格口径下比较，不能通过改变可比较集合制造优势。

这是对未来合同的建议，**不回改V4冻结控制或其FAIL结论**。

### 4.4 泄漏风险与结论范围

- CAL攻击不得作否决原型、困难任务、loss选择或检查点选择；FIT内部开发／留出与最终CAL职责须清楚。
- A/B标签可以继续用于已披露的失败诊断，不能拿来挖训练难例、按胜出结果选规则，再称源侧冻结泛化。A/B已经是开发材料，需要另有独立确认。
- 已查看过当前CAL压力，后续若据此反复选候选，应披露开发接触；同批CAL的零新增FN只能作为有限、条件化保护结果，不能冒充新的独立安全证明。
- 真正可预登记之前仍缺：配对覆盖、依赖隔离、有效差异条件、loss数值和控制的最小效应／不确定性定义。这些不能从现有WRONG评价器自动推出。

## 五、问题4：是否同意归因FAIL作为硬门？

同意以下精确表述：

> reference_attribution 未通过前，不得宣称已证明“该设备自身的正常参考产生特异性的入网适应收益”。

当前FAIL保持不变，HARD错库2723与own2167是匹配子集数字，不与全池2819混算。可以如实报告一般修正收益、困难任务收益及执行了入网流程；不能升级为设备特异性适应成功，也不能把FAIL解释成一切参考方法无效。[E2] 第126行也区分了这些声明。

新归因判据不能只用 `wrong_control.equally_effective=false`。根据 [E5] 第746–752行，它可能因为wrong出现新增FN而变false；这不自动证明own机制成功。至少须同时满足：own有绝对收益、攻击合同通过、QUERY_ONLY对照有支持、匹配覆盖充分、预登记的own−wrong加权效应达到门槛，并报告依赖分组下的不确定性。不能把相关逐包行当作独立样本凑“显著”；少设备条件下须诚实说明确认能力有限。

此外，own≫wrong不是一切正常适应的物理必要条件，共享正常行为可能使两库都有用。它是**特定个性化主张**需要的识别证据。若共享参考机制稳定有效而自身特异性仍不成立，应调整主张并保留结果，而不是在训练目标里人为制造身份差异。

## 六、问题5：永久降权清单是否有例外？

将“科研解释底线”与“当前证据下不优先的方法”分开。以下解释底线没有例外：目标标签拟合冒充源侧泛化；将OLD_BANK称作旧修正器；将QUERY_ONLY称作整个系统完全无参考；把旧344条成功冒充新输入可复现收益；归因FAIL仍声称自身特异性已证实。

以下方法当前不应启动，但不宜写成跨所有条件的永久禁令：

| 方法 | 只有什么证据出现才值得重新考虑 |
| --- | --- |
| 增加epoch | FIT侧优化诊断显示尚未收敛，源侧留出有一致证据；登记有限增量与停止规则，不看A/B挑轮数。当前没有这类证据 |
| 更换检测头 | 分账显示主要障碍来自原头错误分数／无法由修正恢复的FN，且现有输入有可利用区分信息；新头按源侧配方独立校准阈值、尺度和λ，并完成同入网算法配对。不能无止境换头 |
| 研究cap | 加权分账证明它是真正瓶颈，并具备独立近边界真实攻击压力与新的完整校准／控制；不是为了跨1%线直接放大。当前证据不足 |
| 利用旧Qref | 可借鉴其关系度量归纳偏置后重新初始化、FIT训练。旧权重直接接入目前不支持；未来warm-start须先有输入／归一化／参数语义映射、数据暴露审计和独立消融，且仍不能把旧成功当迁移担保 |

科学FAIL继续完成登记矩阵；身份、数据、数值或资源异常才停链留现场，零自动重试。停止某条研究路线不等于中途省略不利的已登记比较。

## 七、对阶段3与“失败收束”的具体改写建议

令同一完整资格集合为S，两方法S外都严格回退BASE。使用同一全正常分母W，有：

```text
FPR_L(full) - FPR_V3(full)
  = sum_{i in S, normal} w_i * (alarm_L_i - alarm_V3_i) / W
```

因此，在同一S内按相同权重比较的优劣符号与全池相同。若观察到“子集赢、全池输”，应先查所谓子集是否只是WRONG匹配集、资格交集，或两方法各有不同支持门／分母／预算。

若资格集合不同，按 **交集／仅学习臂有资格／仅V3有资格／均无资格** 四格分解，并统一除以全池W，才能判断覆盖和修正质量各贡献多少。不能把集合变化直接叫作表征失败。

“资格内输给V3”也不足以单独定位参考几何表征；还可能来自strength映射、残差目标、采样、优化、尺度或攻击保护压力。建议将阶段3改成**由阶段0证据支持的备选机制路线**：若V3有效几何确实没有被学习臂利用，再研究可学习几何／几何加残差；若只是强度不足，则不必立刻改表征。混合方案也不是天然成功，仍需完整对照和保护。

“失败收束”建议改成：

> 在本次登记的数据、seed、预算及候选方法族内，未实现双池目标／自身参考归因，记录V3优势及覆盖、幅度、参考使用的有限证据，停止该候选族的无依据重复训练。

不能据此宣称“端侧有界学习一般无法达到双池1%”或“误报主要只由几何与覆盖决定”。现有结果和有限阶段1–2失败不足以证明这样的普遍因果或不可能性。

## 八、历史证据的三处文字修正

1. **保留历史A低误报正结果，但补齐同口径。** [E9] 中Job174251固定三seed集成：加权FPR 2.769602%→0.317174%，FP374→30，纠正344条、零新增FN；攻击99.986086%是原始条数TPR，同池加权TPR为99.938458%，见 [E10]。不能将raw TPR与weighted FPR并排后统称全加权。
2. **旧A不是所有查询都有资格。** [E9] 有332条真实资格外正常，FP=0；由此是“旧Q的全部FP权重质量落在资格内”，不是“所有正常查询均有资格”，见 [E11]。同预算正确参考39FP、错误参考45FP仅6条差异，也不能把全部344条解释成设备个性化贡献。
3. **B的头漏检、修正撤警、输入时效问题要分开。** Job176975的FULL相对Q新增14605个FN，其中TP Link14602；另有原Q迁移漏检。[E12] 与后续Job177299输入时效审计 [E13] 支持分开诊断，不能拿输入陈旧作为FULL撤销真警的充分解释。只降分修正无法找回原头FN；本次V4-EVAL1所观察到零原FN／新增FN不覆盖更广攻击域。

另，被审稿中有首字母丢失的 `eference_attribution`、`uns/...` 及断行；`decision.json` 也不在复核目录根，而在其 `evaluation/results/evaluation/` 下。本次保留被审稿原字节和hash，建议作者修订时一并修正并生成新hash。

## 九、建议的下一版顺序与仍未知状态

1. **修订方案文字。** 先改CAL角色、合法性／支持度区分、归因分母、阶段3入口及失败声明；本回复是审阅建议，不是数值已定的执行规格。
2. **后续另行授权时才做阶段0。** 用保存预测做互斥加权账、几何与V3差分、344身份追踪；先判断A／B各设备目标在当前合同下的可达质量。
3. **据分账选择最小候选。** 合法参考确有遗漏才研究bank／资格；可达质量足够但学习没用好参考，才研究条件配对loss或几何归纳偏置。不是固定先把每个阶段都训一遍。
4. **再冻结新方法合同。** 明确源侧开发与CAL、同一全池指标、结构匹配归因、近边界攻击／源侧留出设备保护、有限候选预算及独立确认条件，之后才有训练授权和执行问题。

目前仍未知：412条A资格外FP按原权重和reason的分布；合法早期参考能否恢复足够质量；各臂精确加权条件下界；可达未修的几何／strength成因；旧344条在本轮seed27的路径；FIT内有效own/wrong差异配对及源侧独立攻击压力是否足够。这些需要后续审计，不能用本次文档审阅冒充已回答。

**本次已完成方案审阅，未执行阶段0、未新增训练，也无需等待换头结果或持续AI轮询。**

## 核对证据索引

以下代码链接均指向V4实际部署staging，行号为本次核对时的一基行号；不是建议改动原文件。

- [E1：V4-EVAL1完成与科学结果复核](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/learned_onboarding_v1_20261023/evaluation_completion_v1_20261025/analysis/completion_review_20261025/RESULT_REVIEW.md)
- [E2：冻结执行规格](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/learned_onboarding_pilot_v1_20261023/EXECUTION_SPEC_V1.md)
- [E3：实际执行evaluation.py](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/learned_onboarding_v1_20261023/memory_revision_v4_20261024/deployment_20261024/staging/runs/learned_onboarding_v1_20261023/src/evaluation.py:87)
- [E4：实际执行reference_core.py](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/learned_onboarding_v1_20261023/memory_revision_v4_20261024/deployment_20261024/staging/runs/learned_onboarding_v1_20261023/src/reference_core.py:176)
- [E5：实际执行pipeline.py](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/learned_onboarding_v1_20261023/memory_revision_v4_20261024/deployment_20261024/staging/runs/learned_onboarding_v1_20261023/src/pipeline.py:44)
- [E6：实际执行learning.py](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/learned_onboarding_v1_20261023/memory_revision_v4_20261024/deployment_20261024/staging/runs/learned_onboarding_v1_20261023/src/learning.py:233)
- [E7：既有344条身份桥脚本](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/diagnostics_d1_d2_v1_20261022/src/review_historical_a.py:10)
- [E8：既有344条物理端点核对产物](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/diagnostics_d1_d2_v1_20261022/output/coverage/HISTORICAL_A.json)
- [E9：Job174251历史正结果](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/legacy_qref_training_real_result_v1_20260922.md:9)
- [E10：历史weighted／raw攻击口径核对](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261010_system_vs_module_framing_response_codex.md:64)
- [E11：历史FP资格覆盖范围](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261011_system_vs_module_framing_response_codex.md:32)
- [E12：Job176975攻击撤警结果](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/legacy_commissioning_unsw_recovery_job176975_result_20260928.md:22)
- [E13：Job177299输入时效审计](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/legacy_unsw_saved_cache_audit_job177299_result_20260928.md:11)
