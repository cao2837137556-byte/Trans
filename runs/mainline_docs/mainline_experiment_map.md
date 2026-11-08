## 2026-11-07：新增基线适配验收，正式训练待放行

182749 COMPLETED/0:0、6:39，310项验收通过，保守峰值6.306GiB；DTE-C/CatBoost新增工程通过，累计7方法。13阶段PASS、ModernNCA全反传NEEDS_RESOURCES（单张量下界30.89GiB）。真实全源准备完成，但旧源分组两类非空门不足：验证缺3设备正常/4设备攻击，未加权攻击99.9729%来自SimCam；追加覆盖门NEEDS_REVISION，源域整组修订候选已生成未物化。工程证据及条件方案已封存，完整执行版尚不能放行：需新分组UID/覆盖、正式硬件整轮+验证/恢复、具体16配置与权重公式。主模型冻结、大工件留超算，无新作业。见[验收报告](collab/20261107_baseline_training_readiness_acceptance_codex.md)。

---

## 2026-11-07：隔离依赖导入缓存修复

独立v6作业182749已提交，86材料/17远端依赖，1CPU8GiB2小时14阶段。182748在ENVIRONMENT约32秒失败：包已解压，但预先加入不存在目录造成Python finder负缓存；远端文件核对、本地同故障复现/修复回归、新进程全依赖真实导入全部通过。v6清缓存并检查模块实体，仍先计算节点启动门；主模型/方法/协议不变，大工件留超算。两次工程失败与有效链路分别记账；正式训练资源未验收，不虚称全部可训练。见[修复回执](collab/20261107_baseline_training_import_cache_repair_codex.md)。

---

## 2026-11-07：基线资源预检依赖闭包修复

182747 FAILED/1:0、1:47，真实PIPELINE已PASS，新DTE缺sklearn在FIDELITY停止。独立v5固定22个官方wheel，31项Linux3.11依赖约束通过；各子进程统一runtime，ENVIRONMENT原生导入/标准化/CatBoost小拟合前移，14阶段。修正版作业182748已运行，进入ENVIRONMENT启动验证；1CPU8GiB2小时，主模型/方法/协议不变，无正式训练。保留有效原链路和失败分账，不改运行包。见[修复回执](collab/20261107_baseline_training_dependency_repair_codex.md)。

---

## 2026-11-07：强基线适配与全量训练资源预检

用户取消作者原数据集成绩复现要求；实现语义与适配正确性仍必须核验。修正版v4作业182747已提交，85材料/17依赖，1CPU8GiB2小时。补DTE-C与CatBoost、全部源FIT准备和七方法训练资源探针，结束自动封存带资源门的正式协议；主模型冻结、大工件留超算。DIF测试批重新拟合标准化不合当前口径，暂不运行；8–10基线目标尚未全完成。v3本地专用冻结清单误作远端依赖被提交前拦截，0作业，v4改随包携带。本段明确覆盖旧记录中“L4作者任务成绩复现必须先做”的要求；不下载作者数据集。见[启动回执](collab/20261107_baseline_training_readiness_launch_codex.md)。

---

## 2026-11-07：第二批基线复现与全池推断预检验收

182719已COMPLETED/0:0，11:04，峰值保守取6.180GiB；六阶段全部通过。TabM作者口径修正版、TabR原生FAISS、SLAD真实训练/CAL/重载通过；ModernNCA617908源FIT候选全部预编码，真实分块误差2.53e-7，源CAL8推断通过。累计5方法工程资格，L4作者任务成绩复现/L5充分正式训练仍待办；12候选不是全完成，主模型冻结、大工件留超算、本轮无新作业。下一步先封存作者任务复现清单并核验，继续补近期方法/全量训练资源与公平预算。见[验收回执](collab/20261107_baseline_fidelity_second_batch_acceptance_codex.md)。

---

## 2026-11-07：基线复现一致性与第二批预检

作业182719运行，71材料/17依赖通过。发现首批TabM平均logit与作者概率集成不等价，独立v2改两类CE/概率平均；新增TabR原Model AST+真实FAISS、SLAD原实现，检查ModernNCA全617908源FIT池分块推断。1CPU/8GiB/2小时，先真实链路，阶段/资源门失败停；主模型冻结、大工件留超算，18806六阶段进度。明确L1来源/L2语义/L3工程/L4作者任务/L5本任务充分训练：本轮不宣称论文性能复现，L4/L5待办。见[启动回执](collab/20261107_baseline_fidelity_second_batch_launch_codex.md)。

---

## 2026-11-07：近期强基线首批真实预检验收

182677已COMPLETED/0:0，3:36，1CPU/8GiB内，采样峰值3.55GiB。真实322679包、112行重编码及距离误差0；TabM/ModernNCA/Disent-AD三种2025方法真实训练、源CAL、保存回读全部通过。只取得小切片工程资格，12候选并非全完成，正式检出胜负/全量资源尚无结论；主模型冻结，大文件留超算。下一步补其他候选、检索扩展门和公平正式调参预算，不自动全量。见[验收回执](collab/20261107_recent_baseline_qualification_acceptance_codex.md)。

---

## 2026-11-07：近期强基线真实预检启动

盘点38份历史小工件，登记12个外部候选（8项2024–2026）；首批TabM/ModernNCA/Disent-AD官方实现本地检查通过，作业182677执行真实原包/编码/距离及小切片训练、CAL、重载、资源检查。17依赖SHA通过，已进入真实编码；1CPU/8GiB/2小时，仅工程预检，不自动全量。主模型冻结，大工件留超算，18806进度页已切换。候选不等于完成基线；按信息权限和源域校准公平比较，不按是否输给我们筛选。见[启动回执](collab/20261107_recent_baseline_qualification_launch_codex.md)与[执行卡](../baseline_qualification_v1_20261107/EXECUTION_CARD.md)。

---

## 2026-11-07：论文方法冻结与结果包

用户要求暂不改模型，已固定FUSION790＋完整历史参考＋C5_3D_OLD的权重、阈值、尺度、半径和参考身份。生成主结果、二维/三维×尺度消融、四组前端RAW、历史覆盖对照及全种子/设备/全视图附录，共936条完整指标与112条前端指标，1253项构建核验通过。A/B/Edge消费角色和未达标边界保留；下一步先准备公平基线执行卡与真实预检，同时核验未消费外部数据资格，随后补统计与端到端开销。本轮无训练/推断/新作业。见[冻结整理回执](collab/20261107_paper_method_freeze_and_experiment_plan_codex.md)及[论文结果包](../paper_results_freeze_v1_20261107/PAPER_RESULTS.md)。

---

## 2026-11-07：同库历史参考三维C5完整验收

182658/182659均COMPLETED，成功链14:39，峰值2.729GiB；5261项验收、388202行四头一致性与56点真实窗口oracle通过，排除0。完整历史参考＋C5_3D_OLD集成A/B主视图普通/加权FPR分别0.018742/0.002235%、0.282091/0.286266%，攻击100%/99.986217%；Edge普通/加权FPR0.12/1.220180%，HTTP99.79%、UDP98.66%。同库二维复现原基线，历史覆盖保留，三维与旧源尺度组合收益成立。全A加权FPR5.412342%、Edge127加权3.610879%及HTTP97.59%、UDP未99.9%仍为限制；不得宣称全口径原目标达成。封存候选并建议整理论文，原部署与旧NO_GO保留，无新训练，大工件留超算。见[验收报告](collab/20261107_same_bank_context_acceptance_codex.md)。

---

## 2026-11-06：供体同批次oracle修复重交

打开进度页发现v5作业182657于3:06停在供体UID比较，B960行存储schema已全部PASS。原版自身960 vs120子集可复现1条供体差异（支持差4.44e-16）。v6统一原核心批容量、legal tuple合并及全部预检查询同序oracle，保持身份严格一致；本地真实960行数值误差0/供体差0、56项回归通过。新预检182658运行，33材料/27依赖通过；1CPU8GiB30+90分钟，原方法/阈值/参考/预算不变。见[修复回执](collab/20261106_same_bank_context_batch_parity_repair_codex.md)。

---

## 2026-11-06：同库C5支持度存储语义修复重交

v4预检182656于3:03因B支持度定义混比停止，完整作业0。真实960行中11差异全为WEMO Motion SYN守卫；原/优化几何差≤1.11e-15、供体UID差0。C2存effective-zero、C4仅重算四设备，未改动设备保留旧零值。v5显式复现存储schema，全部行比较、排除0，并另存原始几何支持；B全部未改动设备34553行和A全部守卫14432行通过，54项回归通过。新预检182657已提交并进入B处理；真实门后自动完整对照，1CPU8GiB总2小时，原方法/阈值/参考/预算不变。见[修复回执](collab/20261106_same_bank_context_support_schema_repair_codex.md)。

---

## 2026-11-06：同库三维C5预算门修复重交

v3预检182655在4:05预算预测门停止，完整作业0；独立v4优化重复参考扫描/距离及稳定组件归约，按组外推并单列建库，失败前保存计时。36项本地回归及合成同值比较通过（3.49倍，最大差1.11e-16）；33项历史材料/27项运行依赖通过。新预检182656运行，真实冻结算法等价及90分钟预算通过后才完整对照；模型/阈值/半径/参考/因果口径及1CPU8GiB总2小时不变，无训练，大工件留超算。见[修复回执](collab/20261106_same_bank_context_runtime_repair_codex.md)。

---

## 2026-11-06：同库历史参考三维C5对照启动

作业182655，PREFLIGHT_RUNNING。独立v3，33项历史材料SHA通过；A289、B52835历史参考，时间索引因果重放并保留原窗口。四道门：同库二维严格复现、56点真实窗口oracle、历史供体支持留存分账、A/B主/全视图逐设备与Edge全口径四头。冻结原模型/阈值/源半径，1CPU/8GiB总预算2小时，无新训练；真实预检后自动完整对照。v1仅材料盘点、v2依赖清单被提交门拒绝，均0作业，8项约83MB补齐新目录，大工件留超算。见[执行卡](collab/20261106_same_bank_context_design_codex.md)及[启动回执](collab/20261106_same_bank_context_launch_codex.md)。

---

## 2026-11-06：三维C5归因验收，Edge改善但全目标未达

182645/182646成功链31:56，3253项本地摘要/SHA/旧成绩复现通过。3D+旧源尺度Edge普通/加权FPR0.12%/1.22018%，HTTP99.79%、UDP98.66%；恢复原967HTTP撤警中的960条。UDP漏检253/268为成熟高包率，10s独立源数负向抵消明确；不能归因冷启动或宣称768未用。只保留两小时库使B二维本已30.41%FPR，3D30.59%，A加权4.67%；须保留历史参考再同库对照。自动报告误把FIN/RST各1写成SYN2，已据封存证据修复，远端结果未变。原模型/阈值/NO_GO保留，无新训练。见[验收报告](collab/20261106_context_geometry_attribution_acceptance_codex.md)。

---

## 2026-11-06：四项归因及三维C5离线验证启动

v1预检182644因A/B两小时参考与历史扩充参考混比主动失败，90秒，无完整诊断。独立v2保留现行C5对照、同库二维/三维严格复现；182645真实预检PASS（1:20），182646完整诊断运行中，保守估算80.61分钟。固定原FUSION790/阈值/全部种子，源正常rho_c，二维/三维×当前/旧源尺度；同时解剖RAW漏检、STATS8贡献、正常FP和HTTP撤警。无新训练，大数组留超算；最终结果待验收。见[执行卡](collab/20261106_context_geometry_attribution_design_codex.md)和[启动回执](collab/20261106_context_geometry_attribution_launch_codex.md)。

---

## 2026-11-06：共同阈值诊断验收，无共同可行区间

182635/182636累计1分37秒，真实预检与544项旧成绩复现PASS，34266项摘要/SHA断言PASS。32组模型/流程/头、256个共同阈值问题全部无解；原C5集成Edge普通FPR<2%时HTTP93.99%、UDP98.12%，保住两类99.9%则最低FPR70.005%。四组C5集成A/B在原阈值及误报受限端点仍达标；RAW也无解。保留原融合，阈值与旧NO_GO不变。下一步建议冲突样本归因、检查源覆盖及上下文区分信息，未提交新训练。见[验收报告](collab/20261106_common_threshold_audit_acceptance_codex.md)。

---

## 2026-11-06：共同阈值可达性诊断启动

作业182635, 182636，快照COMMON_THRESHOLD_COMPLETE。固定四组/全部头/RAW+C5已有分数，一个阈值共同作用于Edge正常与HTTP/UDP及A/B；求2%/99.9%经验可行区间、召回约束下最低误报及误报约束下最高召回，普通/加权/HT分列并检查共同口径。38项远端依赖、29项本地检查PASS，真实预检后自动扫描，1CPU/8GiB总预算2小时。无训练、部署阈值不变，大文件留超算，最终结论待验收。见[回执](collab/20261106_common_threshold_audit_launch_codex.md)。

---

## 2026-11-06：四组跨数据集验收，误报改善但Edge检出受损

182628/182630/182632累计7:06、峰值1.703GiB，23907项摘要/SHA断言通过。四组集成及三新组全部种子A/B C5普通/加权2%/99.9%均达标；Edge无任何头同时达标。原/均匀/分层/受限Edge普通FPR 5.79/3.115/0.45/1.79%，HTTP94.995/93.155/91.325/93.405%，UDP98.66/97.18/51.8/96.02%；分层/受限加权FPR仍2.071/4.554%。UDP RAW已损失、无C5撤警；HTTP同样扣分下撤警增加。保留原融合，源NO_GO和旧科学FAIL不变。下一步建议固定分数的共同阈值可达性诊断，不部署Edge拟合阈值，未提交新作业。见[验收报告](collab/20261106_pilot_transfer_evaluation_acceptance_codex.md)。

---

## 2026-11-06：四组模型A/B/Edge统一评价启动

用户授权原FUSION790＋最近三轮固定端点统一评价。作业182628、启动快照PREFLIGHT_RUNNING；27项远端依赖和15项本地回归PASS，真实预检后自动AB→EDGE。1CPU/8GiB总上限2小时，无训练/调阈值/挑种子。直接展示误报<2%与检出≥99.9%，普通/加权/Edge HT分列，HTTP/UDP分别验收；RAW与C5及原门保留。源侧NO_GO不阻止本次诊断，也不改写为GO。大数组留超算，尚无新最终成绩。见[执行卡](collab/20261106_pilot_transfer_evaluation_design_codex.md)及[启动回执](collab/20261106_pilot_transfer_evaluation_launch_codex.md)。

---

## 2026-11-06：受限更新验收，工程PASS、科学NO_GO

182592/182593/182598累计11:53，峰值约3.37GiB，809项摘要与SHA/提案审计通过。集成CAL误报137→177，加权0.9466%→0.9570%，相对原头仅降4.28%未达10%；攻击召回100%，分数下降超限1133→735，8维总体贡献101.67%。种子27 CAL p01仍失败，全部源FIT保护端点通过但属优化条件。28次拒绝均为攻击尾部门；实际2432步、保留640步，227模型与上轮SHA完全一致。原3条SimCam录制TCP误报仍保留，约占剩余加权误报86%。保留原FUSION790，本轮无新作业/外部成绩；下一步针对持续正常误报与约束攻击尾部的源内支持及降分方向作只读诊断。见[验收报告](collab/20261106_source_guarded_pilot_acceptance_codex.md)。

---

## 2026-11-06：源域受限更新小试启动

作业182592，启动快照DECODE_PREFLIGHT_RUNNING。固定分层样本和原损失，每轮全FIT核验原保护门及正常尾部风险不增；四档lr倍率重放，完整恢复模型/Adam/RNG，五轮保留端点全报。全部FIT参与优化反馈，未抽中梯度FIT非验证集；CAL不参与接受。每头名义320、实际≤1280、保留≤320步分别记账。61项远端依赖和本地29项回归PASS，真实工程/源提案/强制恢复/预算门后自动小试，1CPU/8GiB总上限2小时。原分层NO_GO保留，无新外部成绩。见[执行卡](collab/20261106_source_guarded_pilot_design_codex.md)和[启动回执](collab/20261106_source_guarded_pilot_launch_codex.md)。

---

## 2026-11-06：分层小试验收，收益存在但科学NO_GO

182589/182590/182591累计5:22，工程PASS，三种子各320更新；403项分组计数/质量检查及回执SHA通过。集成CAL普通误报161→137、加权0.9507%→0.9466%（相对原头降5.32%，未达10%）；攻击召回100%，集成CAL p01转PASS但27源FIT和127仍FAIL。8维总体贡献103.38%，个别保留不足7→13。全部语义组已覆盖，SimCam录制TCP不同训练行3→59/66，原3条CAL误报仍保留，占剩余加权误报86.95%。41个有定义探针均有正常/保护梯度方向冲突。下一步固定采样，设计源域尾部约束更新小对照；不继续盲目扩量，不筛种子/改门或按CAL挑样本。原FUSION790保留，无新作业/外部成绩。见[验收报告](collab/20261106_source_stratified_pilot_acceptance_codex.md)。

---

## 2026-11-06：源域分层抽样与权重校正小试启动

用户授权后启动独立v1，作业182589, 182590、快照TRAIN_PREFLIGHT_RUNNING。修订源FIT语义分层配额及组内有放回PPS抽样，使用Wg/ng损失权重；每类8192样本位、三种子各320更新，原损失/优化器/起点/阈值/科学门保持，历史均匀小试锁定对照。52项远端依赖及本地22项回归通过；1CPU/8GiB三阶段预算2小时，真实工程和训练预算门通过才自动小试。大文件留超算，无新外部候选评价；当前尚无新效果结论。见[执行卡](collab/20261106_source_stratified_pilot_design_codex.md)及[启动回执](collab/20261106_source_stratified_pilot_launch_codex.md)。

---

## 2026-11-06：源FIT覆盖诊断验收，优先修订抽样与权重估计

182585/182586累计6:36，工程及诊断PASS，6648项摘要一致性断言通过。现有源FIT有相关场景，原小试遗漏35/94正常组、1/11攻击组；等量层级抽样覆盖集成正常/攻击残余风险73.99%/65.83%，原样本9.67%/0.34%，均匀加倍12.75%/1.27%。这是训练后描述性覆盖，不能因果预测改采样的收益。CAL误报组全有FIT及实际成员支持，SimCam录制TCP的3条占剩余加权误报86.57%，仍需核验组内泛化。下一步设计仅FIT的分层/重要性抽样及正确权重估计，固定预算对照，禁止直接按权重抽样后照搬旧权重。原小试NO_GO和原FUSION790保留，无新训练或外部成绩。详见[验收报告](collab/20261106_source_coverage_audit_acceptance_codex.md)。

---

## 2026-11-06：源FIT覆盖与攻击尾部只读诊断启动

源小试科学NO_GO后，用户授权先查覆盖。v1作业182585、启动快照PREFLIGHT_RUNNING；52项远端依赖提交前PASS，1CPU/8GiB总预算90分钟，真实工程/源结果预检通过才自动完整诊断。三种子及集成、实际抽样/等量层级抽样/两倍均匀抽样；成员仅由FIT构造，CAL描述性关联，模型更新0、阈值重拟合0、新外部候选评价0。完整分组明细留超算，当前无最终诊断结论。见[设计卡](collab/20261106_source_coverage_audit_design_codex.md)和[启动回执](collab/20261106_source_coverage_audit_launch_codex.md)。

---

## 2026-11-06：源域风险保护小试验收，改善但科学NO_GO

182579完成2:32，三种子共960更新；成功链5:35，工程PASS。CAL集成普通FPR 0.8870%→0.4857%，加权0.9998%→0.9507%（相对降4.91%，未达10%）；所有源攻击召回100%、撤警0，正向8维贡献约101.8%保留。全部种子攻击分数p01下降仍略超0.01原尺度门，不能放宽门或用召回替代；LC几乎未激活，不能宣称其因果作用。下一步只建议源FIT高权重正常覆盖与攻击尾部约束排查，不自动新训练/外部评价。无新作业，大文件留超算。见[验收报告](collab/20261106_source_risk_preservation_pilot_acceptance_codex.md)。

---

## 2026-11-06：源域真实训练门PASS，小试182579启动

182577/182578通过；原融合头全FIT/CAL精确复现，三种子24次真实更新与保存重读/评价/预算门PASS。小试保守预测8.1分钟，1CPU/8GiB，进程采样峰值3.336GiB。182579已启动，固定三种子各320更新，不自动全量或外部评价；科学效果待验收。见[回执](collab/20261106_source_risk_preservation_pilot_launch_codex.md)。

---

## 2026-11-06：源域正常风险与攻击能力保护小试启动

原融合790起步；固定正常尾部单侧风险＋攻击分数/正向8维贡献保护，源FIT每类8192行、三种子各5轮320更新。原阈值/编码器/归一化冻结，无外部候选评价。v1作业182576误列本地审计依赖，3秒失败、训练0；v2方法字节不变，45项远端依赖提交前PASS，当前作业182577, 182578、TRAIN_PREFLIGHT_RUNNING。自动真实工程→真实训练预算门→源小试，1CPU/8GiB总上限2小时；不自动全量训练，尚无科学结论。见[设计卡](collab/20261106_source_risk_preservation_pilot_design_codex.md)及[启动回执](collab/20261106_source_risk_preservation_pilot_launch_codex.md)。

---

## 2026-11-06：8维贡献与锚定冲突诊断已验收

三作业累计3:14，进程采样峰值1.684GiB；固定输入分数完全复现、21个源FIT快照、1408项干预计数检查通过。Edge UDP8维贡献中位数原融合+5.91→锚定+0.64；置零基底裕量−1.45→−18.13。第1轮三个种子全参数及8列平均梯度冲突；末轮8列锚定梯度大12.3万—346.7万倍，分类饱和；非全程反向、未重建Adam。诊断验收PASS不等于模型修复，原科学FAIL保留。下一步保留原融合能力，撤销全分数弱教师锚定，设计正常风险与攻击裕量保护的源域小试，须检查硬负例覆盖；尚未封存新目标、无新作业。见[验收报告](collab/20261106_context_anchor_diagnosis_acceptance_codex.md)。

---

## 2026-11-05：8维贡献与锚定冲突诊断启动

用户授权只读机制排查。真实Linux预检182560运行，之后条件自动CONTRIBUTION→GRADIENT，1CPU/8GiB总上限2小时。固定三数据集/三种子/第40轮端点做真实8维、置零、同设备协议内两次置换；源FIT拆分BCE_NORMAL/BCE_ATTACK/TAIL/ANCHOR_NORMAL/ANCHOR_ATTACK，21个预定快照、固定64批，保留范数和近零不可解释门。无训练、调阈值或外部选轮次；大数组/逐批明细留超算。当前仅启动，尚无机制结论。见[执行卡](collab/20261105_context_anchor_diagnosis_launch_codex.md)。

---

## 2026-11-05：锚定790统一评价结束，工程PASS、科学FAIL

182554/182555/182556累计5:01，峰值1.691GiB；真实编码距离门及五组全量复现通过，868项旧指标一致。新Edge集成C5正常误报5.79%→0.58%，127误报5047→116，但UDP98.66%→0%、HTTP94.995%→46.51%；UDP RAW已失败，HTTP撤警967→6467。A/B原RAW门、Edge安全门仍FAIL。不替换主候选，无新作业；建议固定头8维干预和源FIT梯度冲突诊断后再定目标，不按Edge选种子/轮次。大数组留超算。见[验收报告](collab/20261105_fusion_anchor_evaluation_acceptance_codex.md)。

---

## 2026-11-05：固定锚定790模型评价启动

用户授权后，真实Linux预检182554已运行，通过后自动AB→EDGE。五组模型、全三种子和集成，固定阈值/尺度/C5；新候选门显式映射，旧对照数值与判定复核。工程失败停止，科学FAIL照报；新效果未知，大工件留超算。见[执行卡](collab/20261105_fusion_anchor_evaluation_launch_codex.md)。

---

## 2026-11-05：锚定790三头与源CAL训练验收

三种子各40轮、共289,680更新、120份逐轮头，六阶段全部完成；正式训练44:48，成功链51:52，峰值3.307GiB。三个FIT尺度回到旧头±0.5%；源CAL集成加权误报0.9788%。仅训练/校准验收，本轮A/B/Edge效果未知，尚无评价作业。下一步固定端点统一评价全种子，必须检查UDP收益和HTTP撤警。见[验收报告](collab/20261105_fusion_score_anchor_training_acceptance_codex.md)。

---

## 2026-11-05：锚定修复真实全链路通过

182507 COMPLETED/0:0，5分04秒，1564412KiB；112行/7原始批次重新编码、距离复算误差0，评价回执通过。线程归属修复已在真实Linux验证。182509进入三种子真实训练/校准/预算门，通过后自动三个40轮头和源CAL；不等于正式训练或效果验收。证据：`runs/fusion_score_anchor_v2_20261105/REAL_DECODE_GATE_ACCEPTANCE.json`。

---

## 2026-11-05：分数锚定预检运行时修复v2

v1作业182502在真实编码器构造时因interop重复初始化失败（3:07、858544KiB）；未启动正式训练。独立v2修复线程初始化归属，正/负回归通过，真实预检182507运行；方法/源数据/三种子40轮不变。当前仍未通过真实门。见[修复回执](collab/20261105_fusion_score_anchor_runtime_v2_codex.md)。后续按条件自动链执行，大工件留超算。

---

## 2026-11-05：接受既有A/B取舍，启动源分数锚定修复

用户接受此前已观察A/B退化；不改写旧FAIL，不放宽Edge误报/撤警门。九头日志完整性通过，源损失饱和非127独有且旧日志无逐轮分数。封存单一790维源FIT教师分数锚定候选（系数1、三种子40轮），真实Linux预检182502运行，门通过自动训练/源CAL；效果未知。见[执行卡](collab/20261105_fusion_score_anchor_launch_codex.md)。大工件留超算。

---

## 2026-11-05：768维使用与误报诊断验收

768维正确使用且A/B判别重要；Edge UDP表示恒定。127失稳的近端机制是分数/阈值/C5尺度交互，固定新分数新阈值只换旧尺度可使误报5047→67，但集成HTTP检出会降低，未批准作为修复。训练根因尚未严格归因，无新训练。见 [诊断报告](collab/20261105_representation_usage_diagnosis_acceptance_codex.md)。

---

## 2026-11-05：隐式特征使用与误报归因诊断

用户追问768维隐式表示是否被利用。v2预检182478，通过后自动诊断四组全种子；不训练、不拟合阈值、不挑种子。v1工程故障182469已封存并修正回执交付路径。见 [执行回执](collab/20261105_representation_usage_diagnosis_launch_codex.md)。

---

## 2026-11-05：四组评价工程完成，科学验收未通过

四阶段累计10分35秒、峰值1.662GiB。融合C5 Edge样本UDP98.66%、HTTP94.995%，正常FPR5.79%；A/B RAW误报退化和Edge C5安全门失败。保留全部种子，先诊断误报/种子稳定性，不自动重训。见 [验收报告](collab/20261105_device_context_evaluation_acceptance_codex.md)。

---

## 2026-11-05：四组固定模型评价启动

真实预检作业 182427 已运行；通过后自动 CONTEXT→AB→EDGE。真实门、A/B 防退化与 Edge 科学效果尚未验收。全部固定种子和组报告，工程失败停止、科学失败照实汇报；大工件留超算。见 [执行回执](collab/20261105_device_context_evaluation_launch_codex.md)。

---

## 2026-11-05 九头与源CAL校准最终验收

结果：九头各40轮共869,040更新全部完成，集成校准182392通过；累计训练94分54秒，峰值约3.22GiB。
影响：三组固定端点可供评价，集成源CAL加权FPR均≤1%；REFIT782三种子阈值/尺度及集成阈值与旧记录精确一致，不等于外部检测修复。
下一步：沿已有授权做A/B防退化、C5安全性/裕量与Edge诊断，所有组/种子全部报告；当前评价尚未提交。
证据：`runs/device_context_head_training_v2_20261105/COMPLETION_AUDIT.json`；报告 `collab/20261105_device_context_training_acceptance_codex.md`。大工件留超算。

## 2026-11-05 真实训练门通过并进入正式训练

结果：182344 COMPLETED/0:0，2分45秒；九个128批真实训练、种子及集成校准和预算门通过。
影响：REFIT782种子27正式作业182345已运行；后续自动串行，其余条件与资源v2不变。未产生最终模型成绩。
下一步：普通程序继续九头及集成CAL验收，之后A/B和Edge评价。证据 `runs/device_context_head_training_v2_20261105/REAL_GATE_ACCEPTANCE.json`。

## 2026-11-05 真实预算修订v2

结果：182342完成真实小训练/校准后因最大预测2395.91s>1800s在资源门STOP；独立v2预检182344已启动，尚未宣称通过。
影响：按用户先前不足可增时的授权封存RESOURCE_REVISION，正式单头改1CPU/8GiB/60分钟，40轮/损失/种子/阈值不变。九头仍串行，预检30分钟；不热改旧任务、不挑低耗时观测。
下一步：v2通过全部门后自动正式训练和集成校准；大工件留超算，评价待后续。无需重复请求已有授权。
证据：`runs/device_context_head_training_v2_20261105/RESOURCE_REVISION.json`；报告 `collab/20261105_device_context_training_resource_v2_codex.md`。旧失败有效计算与STOP已封存。

## 2026-11-05 真实训练预检与条件自动对照链

结果：真实预检182342运行中，1CPU/8GiB/30分钟；尚未声称预检通过。
影响：通过校准及每头1800秒预测门后自动串行九头（40轮/头），最后集成CAL校准；不重训OLD782，不读取外部评价分数。
下一步：普通程序继续，完成后取小回执验收；A/B、C5与Edge评价待后续，已有授权无需重复问。
证据：`runs/device_context_head_training_v1_20261105/STARTUP_RECEIPT.json`；报告 `collab/20261105_device_context_training_dispatch_codex.md`。大工件留超算。

## 2026-11-05 完整源特征验收通过

结果：182332 COMPLETED/0:0，12分07秒、216724 KiB；200捕获/1,094,929行/581,590恢复查询通过。
影响：源域新增8维数组可供训练；仅工程验收，新训练作业0，检测效果未知。
下一步：已有授权下真实训练/校准/预算门，再四组对照与A/B、Edge评价。大工件继续留超算。
证据：`runs/device_context_training_v2_20261105/FINAL_ACCEPTANCE.json`；报告 `collab/20261105_device_context_source_features_acceptance_codex.md`。

## 2026-11-05 源域准入/真实特征门通过，完整特征构建启动

结果：182330/182331 COMPLETED/0:0，54秒/24秒；231项超算资产SHA及全部1,094,929元数据身份核对通过，57个真实窗口/42个恢复查询一致。182332已运行，完整门尚待回执。
影响：修复182321共享ACTIVE目录owner为空的准入假设，独立v2加原设备名册绑定和PCAPNG容器适配；旧失败回执保存，未改变流式统计核心、旧模型或阈值。未提交训练，不能宣称检出改善。
下一步：用户已授权后续全量特征、真实训练门和四组对照/评价，无需重新询问。自动程序当前止于SOURCE_FEATURES_READY，须接续真实头训练/校准门后再训练9个新头。大文件留超算。[报告](collab/20261105_device_context_source_admission_codex.md) · [阶段回执](../device_context_training_v2_20261105/PREPARATION_GATE_RECEIPT.json) · [进度](http://127.0.0.1:18806/)。

---

## 2026-11-05 D1 流式与资源验收，训练方案封存

结果：182314/182315 均 COMPLETED/0:0（20秒/2分7秒）；112个真实端点及83个恢复查询零差异，150万事件压力门通过，最终验收 PASS。
影响：训练规格已封存，SHA 501aea9c9dd62b84a80e0cb4931935aeb766afb3d5c24e9fb39d2866800fb065；没有训练或新检测性能结果。UDP解码+统计8.44万帧/秒，压力峰值267.7MiB。NORMAL最大逻辑时钟超前854.643ms，需保留该限制。
下一步：源原包/MAC/UID/权重与完整特征准入，真实训练运行时小切片，再按四组对照推进；预算每新头1CPU/8GiB/30分钟，特征构建另计。[验收](../device_context_stream_gate_v1_20261105/FINAL_ACCEPTANCE.json) · [报告](collab/20261105_device_context_stream_gate_codex.md) · [封存规格](../device_context_stream_gate_v1_20261105/TRAINING_SPEC_FROZEN.json)。全部大工件留超算。

---

## 2026-11-05 设备级 D1 流式小切片与资源门启动

结果：本地边界、真实原包前缀/恢复核对 PASS；Linux 预检 182314 COMPLETED/0:0、20秒，完整资源门 182315 已运行。
影响：锁定当前包纳入的 D1 前缀逻辑单调时钟、112个真实端点、硬状态上限与门槛；未改变原模型或 C5、未训练。通过后普通程序自动封存训练规格，任一门失败 STOP。
下一步：在[进度页](http://127.0.0.1:18805/)看最终状态，以新目录 TRAINING_FREEZE_RECEIPT / ARTIFACT_ACCEPTANCE 为准；之后仍须源域全量特征/UID/原包和真实训练运行时准入。详见[执行说明](collab/20261105_device_context_stream_gate_codex.md)。大工件全部留超算。

---

## 2026-11-05 小anti文档评审核对与设备统计设计草案

结果：收到用户转述的小anti评审，接受设备级8维主方向，修正当前包泄漏、捷径已证明、HTTP子层/全体、A/B基线和绝对裕量预测等表述。
影响：182280诊断不变；新增OLD782历史锚点与REFIT782同配方训练对照。D0事件时间与候选D1前缀逻辑单调时间必须分开命名核验，8维不等于状态维护已满足边缘预算。
下一步：[设计草案](collab/20261105_device_context_repair_design_draft_codex.md)的流式小切片、资源与门槛映射完成后再冻结。当前未训练、未提交、未向小anti发消息；这是其文档审阅和Codex核对，不是独立代码/原包复现。详见[回复](collab/20261105_anti_context_review_reply_codex.md)。

---

## 2026-11-05 单包消融与跨连接统计验收，确定优先修复候选

结果：182280 COMPLETED/0:0、21分09秒；200条配对消融、Edge60k统计验收PASS，原E3误差0、头误差≤0.00001145，72个真实窗口核对通过。
影响：A UDP64条截成单包仍全检出，原“更长历史”解释不成立于该切片；Edge跨连接1s包速率AUROC UDP0.999986/HTTP0.999214，提示缺失设备级密度视野，但非修复后性能。
下一步：建议固定编码器，源侧构造因果8维，比较782/8/790维及固定误报预算；先RAW，再单独检查C5撤警。新训练未启动，Edge不再视为未消费独立确认。

完整证据与限制见 [诊断验收报告](collab/20261105_context_separability_acceptance_codex.md)、`runs/context_separability_v1_20261104/FINAL_ACCEPTANCE.json`。正常UDP只有497条、单设备和不同采集文件混杂仍存在。大文件继续留超算；未新增小anti复核。

---

## 2026-11-04 单包消融与跨连接可分性诊断已交付

结果：本地原包/数学/分词检查 PASS；真实 Linux 预检 182279 COMPLETED/0:0（1分10秒，MaxRSS 1,465,692 KiB）；完整诊断作业 182280 已自动提交并运行。
影响：固定 200 条 UDP 配对干预及 Edge 60k 查询的 1s/10s 八维统计；冻结模型、阈值和历史正式结果不变。此为机制诊断，不是修复后性能验收。
下一步：读取 `runs/context_separability_v1_20261104/REMOTE_STATE.json` 与最终两类 SUMMARY；核对 `ARTIFACT_ACCEPTANCE.json` 后判断修复方向。

用户要求大文件留超算、可见进度；已实现 http://127.0.0.1:18804/ 。普通程序同步，助手不守候轮询。执行 1 CPU/8 GiB，预检15分钟+完整105分钟，无自动重试。源数据/窗口/抽样固定，Edge 已消费为诊断数据；完整同协议及分段对照，正常UDP 497条。用户准备下周开始论文，不为赶时间省略对照。详细设计和解释边界见 `runs/context_separability_v1_20261104/README.md` 与 `PLAN.json`。

---

## 2026-11-04：输入提取与真实模型执行验收PASS

结果：182266预检PASS；182267完成159秒，19条A/B/Edge前向E3误差0，分数最大误差0.0000114441，三头和集成判决一致。
影响：337个权重名逐项一致，20k UDP原包首包/q14与五层HTTP独立输入匹配；未发现核验范围内换模型、漏特征或提取错误，原科学效果FAIL不变。
下一步：表示设计与分类头泛化需预登记消融区分；[验收报告](collab/20261104_input_model_execution_acceptance_codex.md) · [结果页](http://127.0.0.1:18803/)。182263审计器共享权重假设停止原证据保留，大文件留超算。

---

## 2026-11-04：A/B/Edge三层诊断完成，定位输入盲区与HTTP撤警

结果：182245 COMPLETED/0:0、3分19秒；A/B全池及Edge 60k已有产物/判决复核PASS。
影响：Edge UDP 20k已存输入同指纹、抽查单包，C5支持度全0；HTTP RAW样本AUROC 0.225，p3再撤7,027条告警。原外部安全FAIL不变。
下一步：独立小切片核对UDP原包→快照语义边界，再决定新方法；没有新训练或评价。大文件留超算，[三层诊断报告](collab/20261104_ab_edge_three_layer_diagnosis_codex.md) · [结果页](http://127.0.0.1:18801/)。

---

## 2026-11-04：Edge正式评价完成，工程PASS、召回损失检查FAIL

结果：182071预检PASS；182089 COMPLETED/0:0，完整性及封存UID复核PASS。
影响：ensemble样本误报84.03%→0.475%，HTTP关联召回66.33%→31.195%；p3/p1所有种子安全门FAIL，UDP基线及所有方法均0。42,428条旧编码成功复用，大数组留超算。
下一步：只读诊断UDP基线及HTTP撤警分层，冻结不变；[详细结果](collab/20261104_edge_182089_formal_results_codex.md)。没有自动新增实验。

---

## 2026-11-04：正式评价监控竞态修复并重交

结果：181931因磁盘扫描撞上原子改名而FAILED；修复预检182071已提交。
影响：已提交编码留超算并逐批核验复用，另修实际BatchStore身份验收格式；科学v4冻结不变。
下一步：预检PASS后自动正式续跑1CPU/8GiB/24小时；[交接](collab/20261104_edge_formal_monitor_race_resume_codex.md)，[进度](http://127.0.0.1:18799/)。本地仅重要结果，AI不持续监控。

---

## 2026-11-04：正式评价已授权并启动自动交付

结果：真实预检181930 RUNNING；正式评价等待本轮预检验收后自动提交。
影响：复用181905完整三角色快照；科学v4字节及20k/角色固定选择不变，1CPU/8GiB/24小时上限。
下一步：普通pipeline自动推进，进度 http://127.0.0.1:18798/；不持续AI监控。详见 [交付记录](collab/20261104_edge_formal_evaluation_launch_codex.md)。

---

## 2026-11-04 · 181905完整Linux工程门最终验收PASS

181902实际大检查点恢复与固定78端点预检PASS，13:31；181905 COMPLETED/0:0、44:17、整树采样峰值6.49GiB，清理成功。UDP从2877608帧仅追加338124数值帧到EOF；64124快照、73形状编码探针、15文件中断恢复字节一致、源已存CAL零误差和合成距离均通过。46件取回文件及实际归档SHA复核；修正本地归档SHA字段变量覆盖问题并以真实包回归验证，原回执保留。正式外部评价仍未授权，下一步制定正式编码/评价执行卡。[详细验收](collab/20261104_edge_181905_final_acceptance_codex.md)。以下为历史。

## 2026-11-04 · 181856超时封存，实际大检查点恢复预检181902

181856再次触发2小时时间守卫，峰值5.50GiB，持久恢复点2877608帧保留。用户授权增加时间后，新独立交付将完整门上限及内部三处上限同步改为21600秒，预检1800秒，接收器/观察窗口12小时。科学绑定保持v4不变；预检必须恢复本次实际大检查点并推进16个选中端点，另做固定78全链路和UDP中断恢复。181902已RUNNING，尚未验收，不提前启动完整门。进度18797。[详细交付](collab/20261104_edge_v4_extended_resume_codex.md)。以下为历史。

## 2026-11-04 · v4预检PASS，完整工程门181856运行中

181854真实78端点及UDP强制退出恢复预检PASS，COMPLETED/0:0、6分51秒、采样峰值约1.60GiB。条件门核验后181856已RUNNING，1CPU/8GiB/2小时，最终验收待完成。进度18795由普通程序自动更新；[远端启动证据](../edge_formal_gate_deployment_v4_20261104/STARTUP_GATE_REMOTE_READBACK.json)。以下保留启动历史。

## 2026-11-04 · v4持久上下文修复，续跑流水线启动

用户“赶紧修复，然后续跑。”授权继续；独立v4的109+15本地测试通过，持久检查点每约600秒提交，支持同绑定新作业恢复。181699的UDP上下文已丢失，本次重建；NORMAL/HTTP在完整门内逐块SHA与新旧快照一致审计后复用。真实78端点加UDP16实际退出恢复预检181854已提交；PASS后唯一完整门1CPU/8GiB/7200秒。进度18795，普通程序自动推进，无AI持续监测，无自动重投/延期。详见[v4修复续跑](collab/20261104_edge_v4_durable_resume_codex.md)。以下为历史。

## 2026-11-04 · 181699预算停止已诊断

完整门STOP（1:57:37，EDGE_REPLAY_DEADLINE）；预检181696 PASS。UDP最后STOP心跳98.59%，append累计87.6分钟。NORMAL/HTTP完整标记已见，载荷审计待做；未重投。下一步完整产物同版本绑定审计与append内部瓶颈拆查。[详细证据](collab/20261104_edge_181699_budget_stop_codex.md)。

## 2026-11-04 · v3真实预检后完整工程门

用户已免本次独立复核，USER_WAIVED；新v3r1本地98+15检查通过。真实78端点预检1CPU/8GiB/600秒，PASS后完整工程门1CPU/8GiB/7200秒；无自动重投，正式评价未授权。[交付与证据](collab/20261104_edge_v3_preflight_then_gate_codex.md)。进度18794（旧18793保留），由普通程序自动推进；当前提交/运行状态以新交付PROGRESS/SUBMIT_RECEIPT为准。

# Mainline Experiment Map

## 2026-11-04 UTC：181645预算停止，独立v3已本地封存

181645触发EDGE_REPLAY_DEADLINE，调度FAILED/1:0、117分37秒，24件回执验证、3.31GiB整树采样峰值与scratch清理成功。NORMAL 24124行、HTTP 20000行完整产物通过只读SHA/绑定/EOF审计，UDP部分角色不可复用。按用户确认分支集成独立v3，仅取消两条实时进度fsync；93项本地检查和60000查询元数据核验通过，971件卡pin由863基包+138件增量覆盖。v3默认新输出全量重放，不隐式迁移旧spool；待小anti独立复核与真实Linux验收，未提交新作业。见[停止封存与v3交付](collab/20261104_edge_181645_stop_and_v3_package_codex.md)。以下为历史。


## 2026-11-04 UTC：181645 UDP瓶颈已定位，进度I/O候选待小anti复核

真实worker的24/24短时样本阻塞于共享盘REPLAY_HEARTBEAT的fsync。仅优化两条实时进度路径的候选已通过8项测试及同作业内小文件字节同值对照；未集成、未热改，完整Linux工程验收仍PENDING。原1CPU/8GiB/2小时作业继续，无自动延期或重投。见[诊断与候选](collab/20261104_udp_progress_io_bottleneck_codex.md)。以下为历史。


## 2026-11-03 用户授权Linux工程验证：181645已启动

用户明确授权一次1CPU/8GiB/2小时，并要求进度页。181645实际提交、启动读回为RUNNING/NORMAL因果重放；普通程序更新http://127.0.0.1:18793/并取回小回执，最终工程验收PENDING。amd TmpDisk登记为0造成首次test-only拒绝，提交前仅去掉该不受支持字段，原失败与原脚本保留；实际节点空闲32GiB门及24GiB守卫仍执行，没有调度器磁盘预留保证。无正式外部评价、自动重投或AI持续监测。见[启动交付记录](collab/20261103_edge_v2_linux_gate_181645_start_codex.md)。以下为历史阶段。

## 2026-11-03 实验11修复完成：v2本地验收通过，Linux工程门待运行

R1依赖闭包、R2整树RSS、R3当前轮次终态、R4主进程超时scratch均已修复。82项本地检查和60,000条元数据核验通过；基包863件+增量113件覆盖执行卡960个pin。原v1及独立复核保留，C5/阈值/选择seal和科学核心不变。v1 spool不能自动升级复用，v2使用新输出目录。本次未调用模型、未提交超算或评价外部质量；下一步具体授权后做1CPU/8GiB/2小时同运行时Linux工程验证，再锁正式预算。此次Codex修复自验，下次独立复核交小anti。见[修复验收](collab/20261103_edge_formal_v2_repair_acceptance_codex.md)。以下均为历史阶段记录。

## 2026-11-03 实验11独立复核：工程验证前有四项待修

用户指定本次由实验11 Codex复核实验10交付，下次再交小anti。原63项测试及60,000查询统计权重、35成员增量核验通过；独立复现发现1项P1（依赖身份闭包）和3项P2（父子资源监督、重入终态、超时scratch清理）。结论CHANGES_REQUESTED，先修复并复验；没有修改原工程源码/封存卡，也没有启动超算或生成外部效果。见[独立复核](collab/20261103_edge_formal_independent_review_experiment11_codex.md)。以下为此前状态。

## 2026-11-03 当前实验线

C5/p=3与A/B开发线冻结。Edge独立外部线：181418真实小切片PASS；`runs/edge_formal_execution_v1_20261103/`完整worker、恢复、统计和增量包已准备，本地检查PASS，正式质量尚未评价。当前待小anti复核和一次1CPU/8GiB/2小时工程验证，核实新worker真实恢复/末段资源/完整批吞吐后再冻结正式预算。见[执行卡复核请求](collab/20261103_edge_formal_worker_and_budget_review_request_codex.md)。下方为历史阶段记录。

## 2026-10-28 最新：P1失败小诊断完成

见[诊断与下一步判断](collab/20261028_p1_failure_diagnosis_and_direction_codex.md)及[当前接手入口](NEW_CHAT_START_HERE.md)。原48报告精确复现、69文件SHA保持；原QP停止，P2/P3未启动。G0新增漏报说明CAL缺跨设备近边界保护；G1共享校准收益只在单折。原QG可调/回退家族对当前B分数同样无2%/99%联合解，不列为原样A/B主攻候选，下一版先设计受保护的条件修正。本轮0新选阈值/训练/前向/距离/A/B加载/远端任务，无新A/B指标。下方10月25日“最新”为历史快照。

## 2026-10-25 12:33 最新完成复核：V4-EVAL1 已完成，存在局部收益但未达科研目标

独立评价 `V4-EVAL1` 已正常完成：北京时间11:12:03启动、12:28:32结束，耗时76分28秒；`CHAIN_COMPLETE=COMPLETE`、`ACCEPTANCE=PASS`。40个主项＋12个控制全部完成，共8,533,252条预测记录；原V4已有49份摘要均与本次对应摘要全相等。原V4仍为 `EXCEPTION_STOP`，本次独立评价完成不改写原失败历史，也没有重训或从旧49格续跑。

完成依据包括journal正常成功退出、无遗留worker及完成回执；V4-EVAL1的unit现已卸载，不能只靠缺失unit的默认success判成功。本次独立复验评价seal内113件文件SHA；956件原输入的stat／目录成员保持，runner终验已做原输入全量SHA。本轮RSS峰值5.178 GiB低于8 GiB守卫，新增输出853,872,316 bytes（约0.795 GiB）低于独立2 GiB预算。93件小证据、共7,060,904 bytes已下载并逐件验SHA；完整预测尚未下载。

B2加权FPR如下；A所有臂均为7.3703%，学习三臂的λ均为0.25。全40个主格攻击检出率100%，新增FN为0。

| 方法 | B2池B加权FPR |
| --- | --- |
| BASE | 23.3533% |
| V3几何 | 16.7832% |
| L_STANDARD | 21.9392% |
| L_HARD | 20.7265% |
| L_QUERY_ONLY | 22.6389% |

`learned_benefit` 与 `hard_task_value` PASS，但仍未达到池FPR≤1%目标；`reference_attribution` FAIL：B的HARD错参考匹配子集修正2,723条，自身参考为2,167条，错库不逊于自身。因此局部收益存在，学习臂未超过几何方法，参考特异性仍未证实；这是科学结论，并非技术失败。A的440条原始FP中412条资格外，28条可用中另有4条超cap；B在当前约束下的原始FP比例条件下界为12,198／75,763＝16.10%，不能称为加权FPR下界。

见 [完整结果复核](../learned_onboarding_v1_20261023/evaluation_completion_v1_20261025/analysis/completion_review_20261025/RESULT_REVIEW.md)／[远端完成审计](../learned_onboarding_v1_20261023/evaluation_completion_v1_20261025/analysis/completion_review_20261025/REMOTE_COMPLETION_AUDIT.json)／[小证据下载验收](../learned_onboarding_v1_20261023/evaluation_completion_v1_20261025/analysis/completion_review_20261025/DOWNLOAD_VERIFIED.json)。保持现有普通进度页，不持续调用AI轮询；未启动新实验。以下启动、停止与准备记录均保留为各自当时的历史快照。

## 2026-10-25 11:15 历史启动验收：V4-EVAL1 当时正常运行，进入真实评价

用户已明确授权本次在现有云服务器完成。独立执行 `V4-EVAL1` 于北京时间 `2026-10-25T11:12:03.760+08:00` 启动，root `/srv/paper04/learned_onboarding_eval_20261025_v1`，unit `paper04-learned-onboarding-eval-20261025-v1`，InvocationID `2fb248ddc3ce43b19900483b1ba7d4ae`，PID `5174`。`SOURCE_REUSE_VERIFIED` 于11:13:25.838 PASS，runtime／source binding／target manifest／原科研代码一致；worker 于11:13:25.840进入真实 `evaluation`。11:14:40最终远端验收为 active/running、NRestarts=0，无 `EXCEPTION_STOP`／`child_exception`、stderr为空，资源 READY；新增输出11,863 bytes，RSS峰值4,215,074,816 bytes（约3.926 GiB，低于8 GiB守卫）。尚无 `CHAIN_COMPLETE`，科学结果及完整52格最终验收仍待完成。

本次复用已封存 V4 的 tests／prepare／validate／preflight／fit／calibration／target 共七阶段资产，完整重做 40 个主项＋12 个控制；不重训，也不从旧 49 格续跑。原 V4 仍为 `EXCEPTION_STOP`，原失败现场和未完成事实保留。新 results 独立采用 2 GiB 输出预算，经验上界为 `2,018,840,552 bytes`；原输入 `2,149,196,167 bytes` 单独只读记账，不并入新增输出额度。关键模型／CAL 约 50.81 MiB 已本地备份并逐成员验 SHA，这不是全量结果或全部预测备份。实际云端 Python 3.9 下 16 项工程测试通过；这不等同于科学效果通过。

现有页面任务已重启；11:13验收HTTP 200，11:15:01 `PAGE_ACCEPTANCE.json` 已写 PASS、`connected=true`，版本、启动时间、PID及InvocationID均匹配V4-EVAL1，`worker_stage=evaluation`，原V4历史异常保留。页面每 60 秒由普通程序更新；不持续调用 AI 轮询。科学 FAIL 继续完成登记矩阵，技术异常停止并保留现场、零自动重试。见 [独立评价执行复核](../learned_onboarding_v1_20261023/evaluation_completion_v1_20261025/EXECUTION_REVIEW.md)／[独立评价执行回执](../learned_onboarding_v1_20261023/evaluation_completion_v1_20261025/EXECUTION_RECEIPT.json)。以下均按各自日期阅读历史状态，不能替代本次启动验收。

**10月25日10:41历史核查（独立评价启动前）：原实验9学习型入网 V4 已异常停止，整链未完成；训练与 CAL 已完成并封存有效。** 10月24日21:20:30在A/B评价触发 `OUTER_RESOURCE_OUTPUT_LIMIT`：results 2,149,196,167 bytes超过2 GiB守卫约1.63 MiB；RSS峰值5.973 GiB低于8 GiB，物理盘有余量。当前无实验worker，原unit已卸载，缺CHAIN_COMPLETE；缺失unit的默认Result=success及旧worker RUNNING均不代表当前成功/在跑。两个辅助头、三个修正器及CAL共7套seal逐文件SHA通过；49/52份摘要已落盘，缺UNSW的B2/EMPTY/WRONG三份L_QUERY_ONLY，最终汇总/decision/评价seal均无。现有摘要尚未显示学习臂达到目标，不能当完整矩阵结论。79件约3.30 MiB小证据已回传验SHA；权重/完整预测尚未独立备份。云端SSH已恢复，10:40:58页面connected=true；充值不自动恢复链。本轮只读远端，未重启/续跑/提交HPC/改变守卫。下一步保全模型、精算输出后独立补评价；未来回超算先验真实计算节点共享路径及跨环境数值身份，不重提已备份百万行E3缓存。见 [当前状态复核](../learned_onboarding_v1_20261023/memory_revision_v4_20261024/deployment_20261024/STATUS_REVIEW_20261025.md)。下方全部按各自日期的历史启动/修复快照阅读，不持续AI轮询。

**10月24日19:11历史启动快照：V4 已启动且当时运行正常。** 用户已授权“可以动手运行。”，19:08:45启动独立root `/srv/paper04/learned_onboarding_20261024_v4`、unit `paper04-learned-onboarding-20261024-v4`，InvocationID `226cc64bb84747518f72afe05abe1969`。19:11:12验active/running、零重启、无异常；真实63项＋adapter另4项通过，tests／prepare／validate／preflight完成，已进入fit，未观察optimizer更新数。正式preflight READY／规模证明VERIFIED，估计峰值7.172 GiB，启动RSS峰值4.617 GiB；原资源／科学约束和技术异常停链／零自动重试保持。701件新包身份核验，12源与已验修复一致，V1-3保留，进度页同步V4。见 [执行复核](../learned_onboarding_v1_20261023/memory_revision_v4_20261024/deployment_20261024/EXECUTION_REVIEW.md)／[执行回执](../learned_onboarding_v1_20261023/memory_revision_v4_20261024/deployment_20261024/EXECUTION_RECEIPT.json)。不持续AI轮询；下方待部署／未启动为历史快照，三模块训练／CAL／A/B结果仍待。

**10月24日最新修复验收：进度页已修复上线，V4 源侧完整规模验证及实际 preflight 均通过；正式 V3 仍异常停止，未重启。** 页面权威总状态优先，旧worker RUNNING标为快照，源侧修复验证独立展示。V4共享记录／元数据；617,908条FIT、1,206,882条任务实测峰值5.839 GiB，完整任务JSON／H／采样／批次旧语义对照通过；实际预检READY、规模证明VERIFIED，估计峰值7.169 GiB，原8 GiB守卫未放宽。真实Python3.9下63项及adapter另4项通过；生产更新／CAL评分／目标读取均0，26件V3资产未变。源困难信号READY仅代表训练资格。正式V4部署配置／manifest尚未准备，不可复用复制来的V3部署身份直接启动；三模块真实训练、CAL及A/B仍待。见 [修复说明](../learned_onboarding_v1_20261023/memory_revision_v4_20261024/MEMORY_REPAIR_REVIEW.md)／[修复回执](../learned_onboarding_v1_20261023/memory_revision_v4_20261024/REPAIR_RECEIPT.json)／[页面验收](../diagnostics_d1_d2_v1_20261022/PAGE_REPAIR_CARD_ACCEPTANCE_20261024.json)。下方按历史快照阅读，不持续AI轮询。

**10月24日15:37最新只读核查：学习型入网 V3 已异常停止，未完成。** 北京时间13:58:40在fit触发 `OUTER_RESOURCE_RSS_LIMIT`：进程树RSS 8,610,660,352 bytes超过8 GiB守卫（8,589,934,592 bytes）。远端总状态与异常回执一致，systemd为failed／exit-code=1、MainPID=0、NRestarts=0，无对应V3/现代头训练进程；无 `CHAIN_COMPLETE.json`。tests／prepare／validate／preflight已完成，fit未完成，CAL／target／A/B评价尚未开始。fit子状态停留在13:58:27的 `source_task_records`（view=1，450560/617908），其RUNNING及页面local整体RUNNING均不可当实时运行证据；子进程returncode=0也不替代外层失败终态。属于资源异常，不是科学FAIL；现场保留，本轮未重启／续跑／修改远端。见 [只读状态回执](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/deployment_20261024/operations/STATUS_CHECK_20261024_153755.json)。下方13:28启动运行是历史快照，不代表当前仍运行。

## 2026-10-24 13:28最新：独立V3已启动并通过启动验收

**10月24日13:28最新启动验收：** 用户已授权“修复好了，就可以启动实验了。”。独立V3全链于北京时间13:26:46启动，新root `/srv/paper04/learned_onboarding_20261024_v3`、unit `paper04-learned-onboarding-20261024-v3`，原V1/V2现场和权重保留。13:28:17验收为active/running、无异常；真实Python3.9/Torch2.5.1下原49＋新增5＝54项全部通过，adapter另4项通过（真实目标读取0）。tests/prepare完成，当前validate；资源preflight、真实辅助头/模块训练、CAL和A/B仍待，科学结果暂无。已验16GiB硬限／8GiB RSS守卫／4线程／单重worker／零自动重试。普通程序按完整冻结链串行继续，科学FAIL继续配对，技术异常停链。既有18765页面已切到V3并验connected=true，不持续AI轮询。见 [执行复核](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/deployment_20261024/EXECUTION_REVIEW.md)／[执行回执](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/deployment_20261024/EXECUTION_RECEIPT.json)。下方“实验仍停止／未启动”等属于本次授权启动前的历史快照。

## 2026-10-24 13:18历史：数值修订已验收，实验未重启

**10月24日13:18历史数值修复验收（当时尚未重启）：** V2 的 G1 异常已独立复现：108,675 条源侧留出样本中 1 条超原容差；输入、前一 Linear/ReLU 均逐位相同，差异出在末 Linear，原 FIT 伪阈值下零判决翻转、零新增攻击漏检。V3 使用独立逐条 float32 推理，保留真正 256/127 两路径、各自尾批与原门，未改训练公式/权重或正式头路径。云端实际 Python 3.9/Torch 2.5.1 原49＋新增5项通过；两个既有辅助头共617,908条留出样本，新版256/127及独立重载分数全部逐位相等，输入SHA/原FIT索引/元数据/检查点训练UID补充核验通过。跨版本分数不宣称逐位保留，具体差分与资源以 [修复回执](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/REPAIR_RECEIPT.json)／[审查说明](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/NUMERIC_REPAIR_REVIEW.md) 为准。**本轮仅诊断、修订和前向验证，实验仍停止，未重训或自动续跑；完整源几何/H、源困难信号、三模块、CAL和A/B仍待正式执行，科学收益未知。**

## 2026-10-24 历史：V2数值回放异常停止，本地页面已恢复

**10月24日历史异常与页面恢复快照（后续修复见顶部）：** 用户报告页面拒绝连接后核查：本地PID62256已退出、18765无监听，现已改由当前用户的Windows任务计划服务独立托管（仅按需启动、无定时触发器、无AI任务），PID14752，HTTP200、云端连接正常，见 [页面修复回执](../learned_onboarding_v1_20261023/compatibility_revision_v2_20261024/LOCAL_PAGE_REPAIR_20261024.json)。同时发现云端V2已于北京时间12:10:36在fit异常停止：AUX_G0完成40轮/17000步并封存；AUX_G1完成40轮/79600步，但训练后的256/127分批分数回放不满足原rtol=atol=1e-6，报QUERY_BATCH_SCORE_DRIFT，未封存。原批次重新加载bitwise门已通过，G1偏差大小／判决／新增FN集合尚未知，不能豁免或放宽容差。三个修正器、CAL及目标评价均未开始，科学结果暂无。14件小证据已只读回传验SHA，见 [停止诊断](../learned_onboarding_v1_20261023/compatibility_revision_v2_20261024/operations/fit_stop_20261024/DIAGNOSIS.json)。现场、模型与两个失败版本保留，未重跑／续跑／修改远端。12:04运行中是此前真实快照，不能作为当前状态。

## 2026-10-24 12:04历史状态：当时预检完成、fit运行

**10月24日12:04用户要求的一次状态核查：** V2服务active/running，无EXCEPTION_STOP；tests、prepare、validate、preflight均完成，已进入fit阶段。进程在运行，当前cgroup内存约3.8GiB，进程树RSS峰值约6.25GiB，低于8GiB守卫。此次未观测optimizer更新数，不能凭stage名称报具体训练步数；CAL／目标评价和科学结果仍待。见 [状态回执](../learned_onboarding_v1_20261023/compatibility_revision_v2_20261024/operations/STATUS_CHECK_20261024_120437.json)。不持续AI轮询，进度页由普通程序更新。

## 2026-10-24 12:01启动验收：远端49＋4通过，源准备中

**10月24日12:01最新执行快照：** 用户已明确确认重新启动。独立兼容 V2 于北京时间12:00:51启动，实际 Python 3.9 环境中原49项全部PASS、adapter另4项PASS（真实目标读取0）；首次临时目录API错误已通过实际验收。12:01:35服务active/running、完成tests、正在源prepare；不能称真实训练已开始，资源preflight、辅助头／模块训练、CAL及A/B收益仍待。见 [V2执行复核](../learned_onboarding_v1_20261023/compatibility_revision_v2_20261024/EXECUTION_REVIEW.md)／[执行回执](../learned_onboarding_v1_20261023/compatibility_revision_v2_20261024/EXECUTION_RECEIPT.json)。原失败现场完整保留；新root为 `/srv/paper04/learned_onboarding_20261024_v2`、新unit为 `paper04-learned-onboarding-20261024-v2`，不要重用v1输出。已验16GiB硬限／4线程／8GiB RSS guard和空闲窗口，源预检通过后由程序按冻结完整链串行继续；科学FAIL继续配对、技术异常停止留现场，零自动重试。现有18765进度页显示新V2，不持续AI轮询。下方停止／待确认记录均是此次重新执行前的历史。

## 2026-10-24 11:20历史首次执行：兼容验收停止，未真实训练

**10月24日最新学习式执行回执：** 已按用户同意部署并首次启动，但远端 Python 3.9 启动验收中 49 项有 1 项因测试临时目录参数不兼容而 ERROR，链已停止；未进入源准备、资源 preflight 或真实训练，CAL／A/B 新结果均无。独占窗口与 16 GiB 硬限已验，停止现场已回传验 SHA。已备本地独立兼容修订，49 项通过、科研源码及断言未改，实际远端修订仍未验，未上传或重提。见 [执行复核](../learned_onboarding_v1_20261023/deployment_20261024/EXECUTION_REVIEW.md) 和 [修订回执](../learned_onboarding_v1_20261023/compatibility_revision_v2_20261024/REVISION_RECEIPT.json)。进度页已显示 EXCEPTION_STOP；遵守异常停链、不自动重跑，下一步由用户决定是否独立新执行。以下“窗口待落实／仍未部署”等为历史快照。

## 2026-10-24 稍早完成回执：现代三家头与 v3 四库配对全部完成

[完成复核及原始小报告](../modern_head_new_lineage_v1_20261022/analysis/completion_review_20261024/RESULT_REVIEW.md)：14/14 正常结束；三家头及四库完整系统科学 FAIL，96 配对报告零新增攻击漏检。B2 ensemble 加权 FPR（A/B）：MLP 5.74266%/15.21880%、TabM 6.14519%/19.96197%（λ=0）、LightGBM 8.32616%/20.31610%。113 个约 12 MiB 小结果已回传核对 SHA／完成链；完整模型、逐条预测备份待完成。学习式入网 V1 真实训练仍未运行，不按现代头 A/B 成绩改选其冻结主头。下方启动及待完成记录为历史快照。

## 2026-10-23 历史实现回执：学习式入网 V1 代码与验证交付，未真实训练

[新实现与运行说明](../learned_onboarding_v1_20261023/README.md)／[实现验证回执](../learned_onboarding_v1_20261023/implementation_manifest.json)。冻结规格未改；源适配、两辅助头、三学习臂、独立 CAL 保护、40 主项及控制已实现并进行合成集成验证。真实源身份及原 33,147 条 CAL 正常阈值回放已通过；全量源资格、最终测试数及未运行项以新回执为准。没有新真实训练、λ 或 A/B 学习结果，无远端操作或轮询。下方 NOT_IMPLEMENTED 等保留为历史方案状态。

## 2026-10-23 历史方案交付：方案完成，尚未实现或训练

[执行规格](../learned_onboarding_pilot_v1_20261023/EXECUTION_SPEC_V1.md)／[Astra 协议审查](../learned_onboarding_pilot_v1_20261023/REVIEW_V1.md)／[Sol 实现交接](../learned_onboarding_pilot_v1_20261023/IMPLEMENTATION_HANDOFF.md)／[方案回执](../learned_onboarding_pilot_v1_20261023/PLAN_RECEIPT_V1.json)。复用 QUERY_TAIL seed27 正式头，固定两组三设备互换的辅助头＋普通参考／困难参考／query-only 三模块，共最多五训练终点。源 FIT 训练、CAL 最终保护、A/B 四库完整评价；没有新正式头或集成。配方与对照已定，q14 绑定、精确资格、真实折外困难信号和资源仍待验收。此五终点与下方旧外层先导草稿不同；旧共享7捕获的数字不代表新分组。原准备封存文件保持不变，本轮无实现、训练、远端提交或实时检查。

## 2026-10-23 学习式入网源侧准备（历史准备快照，尚未训练）

**同日后续解释：** [数据用途与额外先导澄清](../learned_onboarding_pilot_v1_20261023/DATA_USE_CLARIFICATION.md)。主方案继续以源 FIT 训练检测头/修正器、CAL 校准、A/B 查询评价；可以复用适配的已训练头。五终点内部留设备先导仅为任务构造/额外验证候选，不是主线必须先重训基础头的前置。原结构审计及其限制保留，不外推为原评价隔离失效。

“针对性困难任务＋可学习参考修正”已开始独立本地准备：[源审计与先导设计](../learned_onboarding_pilot_v1_20261023/README.md)。766,727源查询、104源参考完成流式结构审计，12项边界测试通过；时间条件统计是结构上界，帧因果装配/精确配方未完成。源任务多样性有限且拟定外层/开发共享7捕获，不称独立跨环境验证。无新拟合、远端提交或目标评价；既有现代头及v3链未改，本次不查实时状态。

## 2026-10-22 最新入口

先读 [新对话接手说明](NEW_CHAT_START_HERE.md) 与 [主交接顶部](mainline_handoff.md)：前端、QUERY_TAIL＋入网已完成备份；D1 FAIL／D2 NOT_EVALUABLE 已结束；现代三家头×3 seed＋v3 四库配对正式链已启动，最终结果待完成。证据见 [启动回执](../modern_head_new_lineage_v1_20261022/LAUNCH_RECEIPT.json)。本次仅整理本地交接，未读远端实时状态。AI 不持续轮询，进度 [18765](http://127.0.0.1:18765/)。以下保留历史，旧“当前／未运行”不代表本轮进展。

## 2026-10-21 HPC recheck blocked before Python/model execution

Login node168 remains reachable, but Slurm job178526 on compute node185 timed out without a first batch receipt. Independent startup diagnostic178527 on node186 passed shell/hostname/date, then hung on stat of shared project/Python paths; FAILED137:0, batch MaxRSS3M. Both nodes were drained with Kill task failed. The affected /public versus /share mount remains to be isolated by administrators. No further nodes were tried; user queue is empty. Cloud work was unchanged. No cross-environment E3 reuse gate passed; P-only adapter remains an unverified draft. See [diagnosis and administrator request](../hpc_e3_recheck_v1_20261021/FAILURE_178526_178527.md).

## 2026-10-20 当前：代金券机真实回放通过，v3已接续E3

23:14三worker固定36批次float32逐字节回放PASS；本地回执按gate验SHA通过。正式进入run，三worker均 `E3_REMAINING_BATCHES`，观测458,256行（约41.84%）已超过导入458,112行。后续仅续算缺失部分，新增块增量备份继续；无完整缓存或训练结果。见[回放门槛证据](../ecs_cache_resume_v1_20261020/deployment/target_replay_v3/RESUME_GATE_PASS.json)。

v1遗漏缓存父目录已修复；v2完成导入后因服务PATH找不到已安装TShark而在target创建前退出。P的1,095,200行、447块/458,112行导入校验均通过。补齐服务PATH后环境比较通过，11项本机/目标测试通过。v3绑定导入SHA并从validate接续，不重复导入，不清理声明，旧日志保留。服务 `paper04-coupon-resume-20261020-v3.service`，InvocationID `4420fc5662234af9b5b30c827a4b6351`；run沿用v2，新增state/exports/本地备份为v3。18764已同步；固定5Mbps、20GiB/16CPU、手动停机及科学合同不变。见[修复回执](../ecs_cache_resume_v1_20261020/deployment/README.md)。

## 2026-10-20 历史：代金券机上传验SHA完成，修复目录初始化后v2导入中

916文件7,204,966,417字节远端SHA齐全；首次v1因部署未创建缓存父目录，restore在写输出前退出。已修复部署初始化，8项本机/目标测试通过，旧失败记录保留，科学包未改。23:08新 `paper04-coupon-resume-20261020-v2.service` active/running并进入restore，InvocationID `d198605e921b4b618f3897ad418999df`。新页面/下载监听指向v2，本地新增备份目录 `local_resume_backup_v2`；原P/E3备份和服务器上传无需重做。真实回放通过后才能接续E3，尚无完整新缓存；固定5Mbps、20GiB和手动节省停机不变。见[修复记录](../ecs_cache_resume_v1_20261020/deployment/README.md)。

## 2026-10-20 历史：代金券机已提交上传后自动接续，本轮手动停机

代金券实例 `i-0jlequa076yrk9p5wjet` / `8.130.103.183` 已由用户开机。固定5Mbps保留，环境复用；原恢复26项及新服务5项测试在目标通过。约6.71GiB完整P/447旧E3块/encoder后台上传中，主服务 `paper04-coupon-resume-20261020-v1.service` active/running，阶段 `wait_upload`；上传全量SHA通过后自动导入、固定抽样逐位回放，再续剩637,088行。回放失败停止，不混合、不重算原P；尚无生产回放通过或完整缓存。

新[页面18764](http://127.0.0.1:18764/)与增量导出/本地下载监听已接入。20GiB、swap0、16CPU quota已实际验证，52h包括最多4h上传等待和48h计算上限，非ETA。用户在云权限安全验证失败后允许暂不处理自动停机，本轮明确 `MANUAL_USER_ACCEPTED`：**结束后仍需手动节省停机，不能宣称自动停止计费。** 完整本地备份验证后才训练同缓存R0及候选。见[部署详情](../ecs_cache_resume_v1_20261020/deployment/README.md)与[提交回执](../ecs_cache_resume_v1_20261020/deployment/submission_receipt.json)。

## 2026-10-20 历史：代金券机完整P导入与E3续跑入口本地验收通过

用户授权准备方案及入口，优先接续昨日云端缓存，不启动服务器。新独立包 [ecs_cache_resume_v1_20261020](../ecs_cache_resume_v1_20261020/README.md) 完成restore→目标小样validate→续跑run。真实本地完整P（1,095,200行/68,518批次）全量身份/分组核验通过；447封存块的458,112行（41.8291%）在UID、slot、role、状态字节及批次边界上均可接续，剩637,088行。26项Python3.9合成测试通过，续算与完整执行逐字节一致；详见[验收](../ecs_cache_resume_v1_20261020/validation.json)。

这仅证明导入结构和续跑逻辑，实际目标最多36批次的float32字节回放仍PENDING，未过不可混合缓存。保留原P环境/血缘，旧块缺失的历史tensor日志不补造，新前向另存。原科学门槛、输入、前端和同缓存R0要求不变。目标20GiB上限/16GiB树guard，3worker×4线程；48h是停止上限非预计时长。目标上传/回放、进度导出、新实例自动停机接入未执行；保持5Mbps及原始备份。本轮新建约6.05GiB临时展开副本因工具策略拦截清理而保留，原始备份也保留。当前无完整缓存或新模型结果。

## 2026-10-20 历史：178456因学校电力维护取消，无完整缓存

恢复优先项：阿里云完整P已在本地，19分片约4.57GiB，本轮SHA重验及固定输入/设计/引擎一致性核对通过。应补独立完整P导入→E3入口，避免默认重做P；生产适配和目标读取验证尚未完成。见[P复用评估](../hpc_frontend_compat_v1_20261020/ECS_P_REUSE_20261020.md)。

资产全部上传并校验后，前端完整作业178456运行01:20:30，于16:21:16被UID0取消。node185明确登记`Power_maintenance_2026-10-20`，状态`DOWN+NOT_RESPONDING`；没有OOM或超时终态。停在P_DECODE_active-05，E3尚未开始。已上传资产与失败中间文件均保留，无P完整封存回执，现有入口不支持直接中途续跑。本轮仅诊断和修正页面说明，未重提作业；待学校确认可用节点/维护恢复后安排。见[诊断与恢复边界](../hpc_frontend_compat_v1_20261020/FAILURE_178456_20261020.md)。

## 2026-10-20 历史：学校新环境前端小样通过，原始数据上传中

按用户后续授权，不再等待旧环境恢复；空白远端新建 `/public/home/jiangxinwei.zr/work/paper04`。复用学校Python3.11.11/Torch2.5.1/NumPy1.26.4和TShark4.6.6，独立vendor_py311来自本地组装；不远端pip/Conda安装。旧封存包不改，新增Slurm适配与明确的新环境合同。

依赖、编码器与新代码上传SHA通过；178437在amd/node185完成环境/冻结编码器小样，PASS回执已回本地：21项Linux恢复测试、33行3次真实模型前向及完整固定元数据/生成归一化工作区通过。采样峰E3约1.50GiB、metadata/merge约5.02GiB。两份原始归档仍在上传，无完整生产缓存或新模型效果。

单次自动接续已启用：上传回执齐全→真实CIC/UNSW各16384包小样→成功终态/PASS与资源覆盖通过→完整缓存（12CPU/20GiB/3worker）。失败停止、无重试、无检测头训练。280h只是保守停止上限；完整新缓存须本地备份后才进行后续训练，同源R0必须重跑。详见[环境与运行说明](../hpc_frontend_compat_v1_20261020/README.md)、[目标回执](../hpc_frontend_compat_v1_20261020/remote_probe_result.json)、[学校进度页](http://127.0.0.1:18763/)；旧ECS页面不代表学校进度。

## 2026-10-20 历史：学校 Python/解码器验证通过，固定项目依赖待恢复

后续module及新增6个教学环境补查仍未找到匹配基础环境，未重复原22个环境检查、未安装或新增作业。已备[管理员请求](../hpc_restoration_check_v1_20261020/environment_checks/ADMIN_ENV_REQUEST.md)，当前推进项是取得学校受控基础环境替代/恢复入口；前端vendor和权重可用本地备份恢复，暂不修改模型，消息未代发。

共享Python3.9.5和TShark4.6.6已在amd/node185验证，解码器复用CST目录libpcap后成功解码生成单包。诊断178419/178420/178421均COMPLETED/0:0，无遗留诊断；第一条退出0仅表示检查完成，缺包仍有报告，不是项目环境PASS。22个公共Conda环境未找到完整项目匹配，公共Torch环境为Python3.11/NumPy1.26.4。用户提醒后核回历史禁止用户自管安装记录，撤回直接新建venv补包安排；先确认学校现行受控环境/离线源及旧项目环境替代入口，按学校允许方式恢复，不自行安装，不改pins。见[核查及修正报告](../hpc_restoration_check_v1_20261020/environment_checks/README.md)。本轮未安装/上传科研数据/正式重建或训练，云端未动。完整依赖及encoder、学校Slurm资源绑定、输入SHA和真实小样验收后正式重建，完整缓存本地备份后跑同源12头。已备份P/部分E3不宣称能直接续跑。

## 2026-10-20 历史初查：集群调度可见，旧资产未在已检查路径找回

用户随后确认旧硬盘已更换、旧资源已无；后续按新血缘重建或迁移完整缓存，不再等待旧路径。按用户提供的七页手册修正：先核查并复用学校现成module/软件及项目依赖入口，再恢复代码/输入，不从零部署超算环境；手册资源只是模板。已备份P与部分E3保留，现入口不支持直接续跑，跨平台部分复用另需适配/验证。见[手册阅读记录](../hpc_restoration_check_v1_20261020/HPC_MANUAL_READ_20261020.md)。本轮未变更远端环境或启动作业。

VS Code 已登录 node168；`/public` 挂载 `/hpc2610`，旧用户 `work` 不存在，原缓存/SQLite/encoder/环境/raw 路径不可读，未做资产 SHA 验收。迁移前目录与 `/share` 常见本用户路径未发现旧主目录；是否另有备份/迁移位置待学校确认，不能判定永久丢失。`sinfo` 显示 amd/gpu/intel up/idle，但未提交作业验证账户资格。本轮只读远端，不调整云作业或新旧血缘。见[恢复报告](../hpc_restoration_check_v1_20261020/README.md)。

## 2026-10-19 新机增量：基础环境验收完成，已节省停机备用

新实例 `i-0jlequa076yrk9p5wjet` / `paper04-coupon-20261019`，私网172.21.90.26，原公网8.130.103.183因节省停机已释放；启动后公网可能变化，按实例ID识别。乌兰察布B、16vCPU/32GiB/200GiB、Ubuntu22.04；实际固定带宽**5Mbps须保持**。已通过Workbench免密root，不新设密码、密钥或角色。

环境v1 apt/uv完成后卡在GitHub Python慢下载，由主任务显式停止；不是OOM或科学失败，日志保留、无成功回执。复用旧机Python3.9.24/Wireshark4.6.6软件（不含数据/venv）只读stream归档到本地，67,940,751字节，SHA见[归档回执](../ecs_migration_v1_20261019/coupon_environment_v1/software_runtime_from_verified_ecs_v1.tar.gz.receipt.json)。Workbench上传因扩展fileURLs未开放未成功，未改浏览器权限；改用172.21.90.23→172.21.90.26单次内网软件stream，仅绑定旧privateIP:18764并限制新源IP/固定路径，完成exit0。旧机未写文件或修改作业，新机同SHA和原 `/opt` 路径安全解压通过。

续接unit `paper04-coupon-environment-20261019-v2` final_exit=0，07:15:39 UTC结束；31锁定包、Python3.9.24、CPU torch、TShark4.6.6及07:16:57 UTC的实际AutoModel/AutoTokenizer导入验收通过。旧waiter退出后由 `verify_and_export_resume_v1.py` 续验留证；8份真实回执和bundle已回传本地、逐成员SHA通过，见[本地回执](../ecs_migration_v1_20261019/coupon_environment_v1/evidence/local_verification_receipt.json)。未传大数据或encoder、未运行科研实验，旧机证据保持。

15:20:08（北京时间）控制台已确认“已停止+节省停机模式”，正常停止并保留磁盘/软件环境备用；[停机回执](../ecs_migration_v1_20261019/coupon_environment_v1/evidence/savings_stop_receipt.json)、[截图](../ecs_migration_v1_20261019/coupon_environment_v1/evidence/stopped_savings_mode.png)、[控制台快照](../ecs_migration_v1_20261019/coupon_environment_v1/evidence/stopped_console_snapshot.txt)保留。CPU/内存/固定公网带宽暂停计费，系统盘续费。现代头隔离环境DEFERRED，数据/encoder及完整资产迁移、路径/资源binding、新作业停机覆盖待做，旧角色不能用于新实例。新机无科研实验，代金券实际账单抵扣尚未核实。

## 2026-10-19 当前增量：进度页、阶段导出与缓存终态自动停机已启用

[进度页](http://127.0.0.1:18761/)每60秒自动读取SSH状态，不调用AI。现有本地13:44:18快照为 `P_DECODE_active-04`，204,800/578,499仅为该捕获进度；完整P/E3未完成，检测头未提交。重启页面用迁移目录 `progress_dashboard_v1/open_progress.ps1`，无需AI持续轮询。

最小角色经用户批准创建、绑定；原InvocationID及角色名已核验。[自动停机回执](../ecs_migration_v1_20261019/auto_stop_target_submission_v1.json)为ARMED，监控unit active/running。仅当前缓存作业在成功或失败真实终态后最多等待30分钟备份，再请求StopCharging；保留ESSD及数据，磁盘等继续收费。API_ACK不表示云端已经Stopped，断连也不能作停机证明。

13:45:18页面已核实“自动停机已启用”、`WATCH_STARTED.armed=true`，见[核实回执](../ecs_migration_v1_20261019/auto_stop_armed_verification_v1.json)。停机不依赖本机在线；离开后作业终态仍自动停机，回来可开机导出。后续12头须在每次提交时将监控覆盖到对应最终作业。

独立阶段导出及本地取回已运行，13:44快照0包。远端最多约8小时/24GiB，本地最多约9小时/8GiB且需本机在线，均非无限监护。阶段包不是完整缓存备份；终态完整缓存只报容量，仍待按实际空间导出并验SHA。有完整本地校验ACK才提前停机；否则30分钟后保留磁盘停机，以后可开机取回。完整备份后才启动新同源12头，原血缘和门槛不变。

## 2026-10-19 13:15 历史增量：完整缓存作业已启动，按现有付费实例→代金券实例安排迁移

用户要求不等券问题、先用当前20元充值的实例推进。13:15:57一次提交 `paper04-cache-rebuild-20261019-v1` 成功，systemd active/running；13:17仍在前置检查，cache目录未出现，尚无P/E3完成或新模型结果。[提交回执](../ecs_migration_v1_20261019/cache_rebuild_target_submission_v1.json)、[状态证据](../ecs_migration_v1_20261019/validation/cache_rebuild_running_v1/)。

只运行完整五角色缓存重建，沿用3worker×4线程及18GiB估计计划。完整cache先本地验SHA备份，后运行新同源R0三seed及九候选；入网/现代头随后适配。保留新血缘/父数值一致性不可核实的标记和原门槛。独立迁移导出保留封存P/E3材料，但现runner无断点恢复入口；跨主机继续完整缓存训练须新binding/计划。D空闲约27.8GiB不能保证整cache容纳，按实际容量和出站0.800元/GB安排不重复回传；不创建新实例或更改计费，不视20元为已确认全程预算。

## 2026-10-19 提交前历史：数据已就位，真实资源小样及正式preflight通过

全部资产上传SHA通过，原始219捕获解包及SHA通过。CIC/UNSW各16,384包真实prefix均成功，采样进程树峰约5.65GiB，解码阶段约1.235/1.542秒；UNSW实际触发spill/reload。复用已有metadata/E3/merge及并发观察，独立计划为3worker×4线程、18GiB allocation、16GiB tree RSS guard、110GiB输出disk guard/120GiB启动free；完整phase仍ESTIMATED。

paper04用户正式preflight `PREFLIGHT_PASS`，1,095,200条、219捕获，正式输出未预留。仅补建缺失的cache父目录后修复初次预检，失败回执保留。完整缓存重建、真实流量E3、头训练尚未启动；280小时是保留旧最坏shape时间guard的停止上限，非ETA。代金券实际抵扣仍待客服。后续完整缓存先回传本地，再运行新同源R0/候选。

[资源确认](../ecs_migration_v1_20261019/RESOURCE_CONFIRMATION_20261019.md)、[计划](../ecs_migration_v1_20261019/validation/frontend_resource_plan_v1/resource_plan.json)、[预检](../ecs_migration_v1_20261019/validation/frontend_resource_plan_v1/observations/frontend_resource_preflight_v2.json)。以下当日早间记录为历史。

## 2026-10-19 早间历史：ECS依赖与三个资源探针通过，待两捕获前缀和生产预算

用户补缴后原实例及专用SSH已恢复。Python3.9.24/NumPy2.0.1/Torch2.5.1+cpu与冻结前端依赖已装齐；TShark4.6.6核官方HTTPS清单SHA并独立编译成功，pandas2.3.3及导入依赖已补齐。环境v1旧signature URL 404与v3续接记录保留，没有重装Python。encoder远端SHA通过，两份大原始归档仍断点续传；用户确认的100Mbps按流量峰值已在实例表显示生效，不保证本地实际吞吐。

metadata_v1参考schema误校验失败已由独立recovery_payload_v1r1纠正，不补造输入字段，旧payload/metadata及失败证据保持。新版已安装，目标完整依赖生成测试21/21通过。完整metadata1,095,200条、219捕获及FIT617908/CAL148819成功，内核进程HWM约5.33GiB；33行生成输入三次冻结E3前向成功，HWM约1.49GiB、真实流量前向0；8192行生成merge-block加完整metadata成功，768/794维块约0.0312/0.0315秒，HWM约5.41GiB。成功探针marker/request/result链与目标测试log SHA已回传本地核验。

**两捕获前缀、经审生产资源计划与正式重建仍待完成。** 当前实测只覆盖上述有界探针；完整phase峰值/耗时仍ESTIMATED，生产入口拒绝pending计划。尚无完整生产缓存、真实流量E3、头训练或新模型效果。目标服务36项生成检查、真实20GiB/16CPU cgroup smoke和生成三分片跨网备份演练通过，演练不代表生产缓存已备份。

[迁移说明](../ecs_migration_v1_20261019/README.md)、[服务器实测](../ecs_migration_v1_20261019/server_inventory.json)、[恢复复核](../ecs_migration_v1_20261019/restore_design_review.md)。此前欠费停机/首次连接准备失败及未提交带宽草稿属历史，相关证据保留；当前已恢复SSH与目标依赖，可继续迁移准备。

父大特征和spool未回传，本地原始PCAP、冻结encoder、输入包与历史结果保留。新恢复血缘保留固定五角色及完整FIT/CAL，标为`NEW_RECONSTRUCTION_LINEAGE`/`PARENT_PARITY_UNAVAILABLE`，不改旧pins。新RECENT缓存和normalizer上重训R0三seed及九候选，共12头1158720更新；旧基线只列历史。入网及现代头后续显式绑定新血缘，原包留存。完整新缓存、权重及结果须回传本地。

## 2026-10-18 历史：现代头 v1r1 修复 P1–P7，拆分纯头与模块作业

[逐项回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261018_modern_head_v1_code_review_response_codex.md)、[新版交付](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/README.md)、[验证](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/validation.json)、[命令](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/OPERATE_HPC.md)。待上传版本改为 v1r1，旧 v1 留存；归档 SHA256 `ad2454fa3766d3862d98e90370fb9dc1fa8b5d67afd20123863182123f71d4d3`。

P1 分报 LightGBM 请求/回调/实际树轮数并允许合法自然停止；P2 的 `--heads-only` 不要求入网完成，`--modules-only` 验证同包封存头与入网六库，不重训。P3 实际回放证据与复用前置检查；P4 CAL_used 保护；P5 所有 family 的范围文字；P6 模块零更新断言；P7 模型导入前离线依赖检查，均已实现。科学配方、seed、数字门槛不变。

57 项受影响 Python + 37 项模拟调度 + 3 项导出不同用例通过；导出跨平台重复后共 100 次执行。旧完整套件与未选取 21 项原 Python 检查未重跑，已标 `rerun:false`。8CPU/16GiB/4线程、RSS14GiB沿用；72/70h 为每作业上限。当前仅本地工程验证，目标环境/真实峰值待核实，真实实验 NOT_STARTED。

执行依赖改为：QUERY_TAIL 完整产物 → 现代头 P/T/K；入网 v1r1 完整产物 + 头作业最终成功退出 → M_TabM/M_LightGBM。两个作业分别回传，模块失败保留封存头且不自动重启。下方旧 v1 的串行依赖说明不再作为当前要求；三设备回归、前端重建封包和选型后补证据仍待做。

## 2026-10-18 历史：现代头 v1 与两候选入网初次独立交付

[说明](../modern_head_comparison_v1_20261018/README.md)、[正式合同](../modern_head_comparison_v1_20261018/bundle/experiment_contract.json)、[验证](../modern_head_comparison_v1_20261018/validation.json)、[资源](../modern_head_comparison_v1_20261018/RESOURCE_BUDGET.md)、[操作](../modern_head_comparison_v1_20261018/OPERATE_HPC.md)。固定MLP_QUERY_BCE/TabM/LightGBM，同782维/划分/权重，三seed27/127/227；神经40轮，树500轮。TabM/LightGBM事前固定接同一模块、同OLD_BANK/B0/B1/B2；按原门槛报告全部候选，不自动选型。

8CPU/16GiB，顺序独立阶段，RSS14GiB；新增T估计，旧P/K/入网预算继承。磁盘8/导出6/空闲16GiB。TabM生成输入时间纯算术三seed约41h不含真实I/O/检查/评价，72h仅上限。旧MLP缺完整runtime指纹时重训，共最多九终点；无证据不复用。科学旧包不改，当前真实实验NOT_STARTED、无远端操作。离线依赖包含LGB4.6.0/rtdl0.0.12等，目标glibc≥2.28和缓存仍需核验。

最终归档安装后41项合成测试+24项Linux模拟调度共65项通过，另7项生成文件导出检查通过；Windows/WSL安装、159个封存文件及Bash/PowerShell语法通过。归档SHA256 `635d617637d8dbf2de7ce46cdbceda88e24286f36b371db1d71ed5d534c0dfc4`，身份及日志见最终验证回执；旧179项未重跑，原89个项目Python模块与17个vendor模块保持。

此条更新“现代头未实现”状态；前端独立重建封包、三设备回归、选型后补证据及独立确认仍待完成。本地NumPy/Torch与目标版本不同，目标环境和真实资源/性能验证仍待恢复；构建时pending回执作为历史保留。

## 2026-10-17 最新交付：入网 v1r1 退出状态修订

[v1r1交付](../onboarding_configured_v1r1_20261017/README.md)、[本轮验证](../onboarding_configured_v1r1_20261017/validation.json)：修复“实验成功但导出失败仍返回0”。实验/导出/作业退出码分别保存；最终状态单独回传；导出失败不重跑实验。仅修改交付脚本与文档，89个Python模块、科学协议和8CPU/16GiB资源计划继承不变；按交付层增量验证，不宣称下方179项在本轮重跑。当前待上传版本改为v1r1，原v1保留。

本轮最终归档安装/哈希通过；22项模拟提交/失败检查+5项模拟回传共27项通过，另复现原包问题。新归档SHA256 `d984be0105dda3d7a37e22d85d87c3ec2a209d91e9b2535760c0bda79999a883`。[资源预算维护约定](resource_budget_maintenance.md)已记录：任务不变复用，按受影响阶段更新，用真实峰值校正估计，避免每轮全面重读重算。无真实实验/远端操作；其他待办沿用下方。

## 2026-10-17 最新：入网模块独立封包及修复头接入完成

[交付说明](../onboarding_configured_v1_20261017/README.md)、[资源预算](../onboarding_configured_v1_20261017/RESOURCE_BUDGET.md)、[验证回执](../onboarding_configured_v1_20261017/validation.json)、[操作命令](../onboarding_configured_v1_20261017/OPERATE_HPC.md)：已接完整 QUERY_TAIL v2r3/R3 产物，串行执行两份正常捕获准备、六库E3及OLD_BANK/B0/B1/B2同头配对。共用一次源参数封存；目标模块修正在封存后，固定头目标分数的复现检查发生在此前。没有重训或按数据集择优开关。

实际8CPU/16GiB、单重阶段进程/4线程；各阶段估计6/4/11.5GiB，最大值加25%余量取整，总RSS保护14GiB。磁盘保护8GiB、启动空闲16GiB、导出4GiB；24/22h为上限。**最终包162项合成+17项Linux模拟提交共179项通过**，Windows/WSL安装及SHA、Bash语法/PowerShell AST通过；真实tokenizer因本地缺依赖未跑，目标环境补查。归档SHA `0e91afd2ca4e1a3d5ec85e6aa3dd323d80c243568ae4ea74f7d60fe39e925bd4`；原科学代码、protocol和修复包不变。

**入网本地交付完成，真实实验NOT_STARTED，无远端动作或新性能结果。** 必须依赖完整父资产、PCAP、checkpoint和修复头真实完成产物；精简回传包不足以启动。零新增漏检为验收要求；三设备回归尚未接入，完整系统不得PASS。此条取代下方入网封包pending状态；前端重建独立资源/封包仍待做，现代替换头未实现，选型后补证据清单继续有效。

## 2026-10-17 最新：QUERY_TAIL v2r3 已完成资源核算、配置与封包

[交付说明](../query_tail_configured_v2r3_20261017/README.md)、[资源预算](../query_tail_configured_v2r3_20261017/RESOURCE_BUDGET.md)、[验证回执](../query_tail_configured_v2r3_20261017/validation.json)、[将来操作命令](../query_tail_configured_v2r3_20261017/OPERATE_HPC.md)：amd单节点16CPU/20GiB、3worker×4线程；P/T/K估计10.5/15.5/10.5GiB，最大阶段加一次25%余量。全角色元数据和完整FIT权重局部测量已完成，非整链实测；Linux堆保留及重复映射RSS已计入。总/worker保护18/4GiB，输出预计0.732GiB、保护4GiB，启动空闲8GiB；72/70h是上限而非预计耗时。

最终包安装后的57项合成检查+Windows安装7项+Linux安装/模拟提交20项共84项通过；PowerShell仅解析通过。原38个Python文件、科学合同和预测规则不变，新增配置检查。归档SHA256 `1678d1b2b7162d788f3058b47dd06231c7db7a21287046675fe3ecf985415317`。**QUERY_TAIL本地配置交付完成，环境/父缓存待核验、真实实验NOT_STARTED。** 此条取代下方QUERY_TAIL资源pending作为当前状态；入网/前端资源封包仍待完成，现代头未实现。未连接或提交超算，无新模型结果。

## 2026-10-17 复审补丁：主快照库 journal 扫描竞态关闭

[补丁说明](../engineering_snapshot_journal_fix_20261017/README.md)、[最新回执](../engineering_snapshot_journal_fix_20261017/validation.json)：确认此前漏登记正式snapshots.sqlite的临时journal，正常提交可能误停；现仅豁免该库精确sidecar消失，主库/目录丢失仍报错。真实SQLite交错及实际spool回归新增5项，连同原55项工程检查共60项通过。旧242项结果保留为前版证据，新源文件manifest记录两处工程修订。生产资源、封装与目标环境检查仍待完成，无真实实验。

## 2026-10-17 最新：入网/前端存储工程修订完成本地验证

[工程说明](../engineering_memory_followup_20261017/README.md)、[验证回执](../engineering_memory_followup_20261017/validation.json)：独立新版对连接状态/候选快照做完整写入恢复，对特征子集按批索引读取，对 SQL 分组流式处理；新增仅 P/E3/normalizer 的前端重建入口、资源计划绑定与失败释放。242项选定检查通过，额外 tokenizer 检查因缺 transformers 未运行并单列。原包、科学合同、旧入网及前端关键代码哈希保持。

生成数据基准显示局部内存降低，状态落盘有I/O与时间代价；不得外推整链RAM。**当前为验证后的独立源码，生产资源定值/新封装仍待完成，真实实验 NOT_STARTED。** 下一步按阶段组成和合理并发补预算、封装；不设小内存目标、不默认旧大资源，不扩展方法矩阵。旧基线依赖仍须恢复，前端入口不是全部资产丢失时的一键恢复。详情及持续待办以主线顶部为准。

## 2026-10-16 最新：先修工程，QUERY_TAIL v2r2 本地修订完成

[工程代码包与范围](../query_tail_engineering_v2r2_20261016/README.md)、[验证回执](../query_tail_engineering_v2r2_20261016/validation.json)：训练元数据改为共享只读紧凑映射，保留原科学数值路径；增加退出释放、分阶段内存观测和资源计划校验，提交/运行使用同一份计划。固定 10 万条元数据测量峰值 0.495→0.056 GiB，字段/权重相同，访问速度有代价；不可外推成整链实测或整体降幅。

新工程包为本地验证版本，**最终 P/T/K 申请资源待定、不可直接提交、真实实验未开始**；不自动沿用旧 64G，不设 16/32 GiB 目标。先补资源依据及剩余必要工程修正，再继续入网包封装和现代头实现。旧 v2r1 科学包与入网 v1 源码保持不变；旧前端重建和入网状态/候选缓存的开销不在本次已解决范围。下方路线和补证据待办仍有效。

## 2026-10-16 实验包与资源配置合理性

[只读审查及用户澄清](../memory_efficiency_review_20261016/README.md)：目标是按任务量、正常高效实现、合理并发和实测峰值制定资源配置；撤回助手提出的32GiB目标，不追求最低或最高资源。历史192G偏保守，当前QUERY_TAIL的64G也未实测；重复元数据、状态回收和候选快照等需优化与验证，不能只改申请数字。未改封存包或运行实验。开发状态及补证据待办沿用下方10月15日入口。

## 2026-10-15 当前索引：现有数据先验证，选型后写作与补实验并行

用户确认暂不下载新数据；先实现并评价已定入网方案，与修复头及有限现代头比较完整系统，再固定模型和规则，补充实验与论文并行。权威状态与**持续待办清单**见 [mainline_handoff.md](mainline_handoff.md) 顶部 2026-10-15 条目；当前证据缺口不作为现有开发实验的新增先行关卡。

| 项目 | 状态 | 入口/下一步 |
|---|---|---|
| 入网材料、配置与实现 | 参考准备/共用模块/QUERY_TAIL 接入及评价已实现；合成验证见回执，真实实验未开始 | [实现与验证](../constrained_onboarding_implementation_v1_20261015/README.md)、[材料与配置](../onboarding_materials_and_protocol_20261015/README.md)；完整缓存与真实 R3 就绪后配对评价 |
| 头与入网联合比较 | 方案完成；QUERY_TAIL v2r1 已封存但未真实运行，现代头尚未实现 | [联合方案](../modern_head_comparison_design_20261015/proposal.md)、[入网方法](../modern_head_comparison_design_20261015/onboarding_refinement.md)；按完整系统固定口径选型 |
| 数据充分性与补证据 | 审查完成；薄弱正常设备、功能时间覆盖、外部攻击多样性和独立确认待补 | [详细审查](../evidence_adequacy_20261015/README.md)；选型后推进，投稿前核对；当前 A/B 仍为开发材料 |

详细产物继续按主题、日期/版本保存于各 run；本索引只记录状态与入口。下方旧条目保留历史，不覆盖本条的新优先级。

2026-10-12 latest: Parent replay numerical rules recorded before real replay. Exact input/state identity in both branches; confirmed full numeric-runtime match -> BITWISE, different/UNKNOWN -> each-row relativeL2<=1e-5 + RECENT3seed/ensemble paired decisions. No post-failure branch switch; actual future heads pending separate checks. Parent node188 already in local archivedsacct; CPU/backend evidence incomplete. Read `collab/20261012_three_device_numeric_parity_response_codex.md` and `runs/system_vs_module_planning_v3_20261012/`. Environment capture/replay remain future specifications; no new experiment, old diagnosis rerun or sealedv2r1 change.

2026-10-11 follow-up latest: Claude planning review PASS/no blockers; attack-TP eligibility added in separate v2 addendum (CIC66.667807%,UNSW60.007370%; exposure, not miss rate). Future complete-system zero-added-miss mandatory in all12 pool/suffix pairs; old-level comparison report-only. Decoder/prefs/batch identity and real-parent bit-pattern replay drafted; missing original features/spool cannot PASS via synthetic replacement. Prefer<=150G subject to credible<130GiB peak; P time PENDING comparable decode measurements. Read `collab/20261011_system_vs_module_planning_followup_codex.md` and `runs/system_vs_module_planning_v2_20261011/`.6new boundary checks PASS,900 prior normal values unchanged; sealed v2r1 and real-run NOT_STARTED unchanged.

2026-10-11 latest: QUERY_TAIL v2r1 remains engineering/Claude-review PASS, real run NOT_STARTED, HPC/cache recovery pending. Accepted reference-eligibility planning: F=H(1-s*g_eligible), s is weighted head-FP eligibility share, not query coverage. Saved RECENT CIC/UNSW floors under fixed eligibility are3.354251%/6.519688%; all-arm future addendum implemented outside sealed package. Future A draft changes strict old-FULL preservation to report-only OLD_LEVEL_PRESERVED; existing research floors and frozen gates unchanged. Three-device new-input cache341222queries+48refs (~0.976GiB E3) planned for separate future preparation/module chain, not current v2r1. Read `collab/20261011_system_vs_module_framing_response_codex.md` and `runs/system_vs_module_planning_20261011/`. No training/forward/remote action; old diagnostics not repeated. Paper stable writing continues; no new performance results.

2026-10-02 latest: QUERY_TAIL algorithm can run CPU locally; current16GiB laptop/fixed package blocked by missing7.41GiB parentcaches, memory/disk and platform adaptation. Source217PCAP+2UNSW present, fullSHA/rebuild unverified; feasibility only, no run. See `query_tail_local_feasibility_20261002.md`.


2026-10-02 latest: HPC disk damage USER_REPORTED; local archives/returned results and177891 twelve endpoint weights verified intact. Full parentfeatures/4.17GiB SQLite remote-only in known export; recovery UNCONFIRMED, QUERY_TAIL execution waits cache verification. See `local_result_preservation_after_hpc_disk_damage_20261002.md`; no automatic rebuild/retrain.


2026-09-30 latest: QUERY_TAIL v1 IMPLEMENTED / LOCAL DELIVERY PASS; real P/T/K NOT_STARTED. Nine fixed heads, R0 reused; synthetic23 + Windows installer6 + Linux installer/mock12 PASS. Source support and target numeric compatibility pending same-job checks. See `legacy_query_tail_learning_implementation_v1_20260930.md` and `runs/legacy_query_tail_learning_delivery_v1_20260930/OPERATE_HPC.md`; user-operated final-package whole-chain execution next, no Claude waiting gate. Reference NOT_TESTED, ID_NOT_RUN, holdoutclosed/paperPAUSED. Earlier design-only entry superseded as current status.


2026-09-30 latest: QUERY_TAIL learning-repair v1 DESIGN READY FOR IMPLEMENTATION; no real P/T/K. Keep verified RECENT/E3 and source FIT weights; append14 current-packet descriptors to one782->128->1 head, combine BCE with source-FIT top1%weighted-normal-tail pair ranking refreshed each epoch. Primary QUERY_TAIL; QUERY_BCE/RECENT_TAIL ablations,3seeds each,9newheads40epochs; reuse177891 RECENT baseline and features, no raw/E3 rerun. All original core attack/FPR gates retained; add protocol/activity regression check; reference gains NOT_TESTED, ID_NOT_RUN, holdoutclosed/paperPAUSED. Source metadata weights verified: Hydra471rows=25%attackmass; TCP429350=41.6667%; ACTIVE_UNANNOTATED131823=17.9479%normalmass, counts are not training emphasis. Exact SYN phase/weight census PENDING_REMOTE_SNAPSHOT, folded into implementation P; no fabricated completeness. Read legacy_query_tail_learning_design_v1_20260930.md and runs/legacy_query_tail_learning_design_v1_20260930/ (research,contract,self-review,acceptance). Target DEV remains consumed; no automatic winning-arm promotion or retries. NEXT implement/synthetic/package; user handles later authorized whole-chain upload/submit/pull. HEAD4b28747/codex-exp-mainline and8 unrelated edits preserved.

2026-09-30 latest: Job177891 G1/G3/G4 COMPLETE, G2 fixed-query normal headers/ports completed locally. Saved-score per-device1%FPR retrospective: UNSW96.6038%attack,0.9730%FPR;Samsung63.08%ofweightedloss; rate1/10/100 loss42.34/38.28/19.38%;only5longattackcomponents,83.57%loss>=60safterannotationstart. RemainingnormalFP90.38%ACK/data;1603normalSYNqueries0FP atsourceandoracle. All3seeds share1169misses/2.2040ppweightedloss;Samsungworstforall. G2missingportsfilled fromexistingnormalPCAP5413239packets/75763fixedqueries;fullSHAverified,31.1s,nofeatures/forwards. CICoracleattack99.9437%;all95missesHeimVisionTCP. NEXT targetedlearningrepairdesign/current-query-context attack evidence andhardnormalconstraints; H1/H3cluesonly,H2notfullyexcluded,fullsnapshotdescriptorsstillremote;noautomaticfrontendchange ornewtraining. Read legacy_continuous_input_job177891_overlap_diagnosis_20260930.md andmatchingrun. No deployedcut/data/model/gate change,HPC/download/holdout;HEAD/8unrelatededits preserved;ID_NOT_RUN/paperPAUSED.

2026-09-30 latest: overlap G1-G4 INPUT AUDIT COMPLETE (not score diagnosis). Verified schema of1095200 existing role rows. UNSW72553 attacks have15annotation IDs,rate1/10/100,direction and victim targetTCPport; allinboundSYN&&!ACK,notARP/reflection. UNSW75763normal rows lackports/canonicalkey. SourceFIT/CAL unoriented endpoint-port inventory saved separately; NOTservice coverage. G1/G3/G4 existing-field diagnostics feasible; fullG2service needs targetnormal header enrichment; remotev3snapshot contains window descriptors but no rawports. ProposedH3 attack-stage supervision mismatch: sourceFIT TCPattack payload lowerbound80.54%unweighted vs targetSYNquery scope; hypothesisNOTPROVEN. Both source/target attack label rules inbound; directIP/MAC/port absent fromRECENT tokens. Smallcomponent/lowrate orseedvariation do not proveH2/H1; require actualcausalwindow evidence. Read collab/20260930_job177891_overlap_diagnosis_reply_codex.md and runs/legacy_continuous_input_job177891_overlap_metadata_audit_20260930/. NoG1-G4scoreexecution,forward,training,CAL,rawdecode,HPC orprotectedpool;99%target andD3NOT_RUN unchanged. Next agree correctedreadonlydiagnosis,notauto frontend replacement. HEAD/8unrelated edits preserved;ID_NOT_RUN/holdoutclosed/paperPAUSED.

2026-09-30 latest: Claude four-question response + saved-score D1 COMPLETE. UNSW RECENT ensemble retrospective attack bound at each-device weighted FPR<=1% is96.6038%; even relaxing to each-device<=2% and ignoring pool<=1% gives only97.5301% (Samsung92.1361%). Thus fixed RECENT + one scalar threshold/device cannot pass frozen99%pool/97%device gates; KEEP gates, no D3 recommended. CIC each-device1% bound99.9437%. Target reference calibration requires a future version; v3 remains source-CAL-only. DEV row logits local; reference classifier logits not computed; small new reference features retained remote (not rechecked), all7device banks3-64rows insufficient for example alpha.005. Reference/queryUIDs disjoint and time strict; UNSW same-component overlap means no iid/conformal guarantee. D2metadata complete, reference-score comparison NOT_RUN. Pause currentSTATE/LEARNED deployment candidacy, retain ablations; RECENT development baseline only. Next joint discussion on low-FPR score separation, not threshold sweep or automatic frontend replacement. Read collab/20260930_job177891_joint_discrimination_reply_codex.md and runs/legacy_continuous_input_job177891_d1_reference_audit_20260930/. No model forward/training/calibration/remote execution or changed frozen result. ID_NOT_RUN/holdoutclosed/paperPAUSED;HEAD/8unrelated edits preserved.

2026-09-30 latest: v3 Job177891 COMPLETE / pullback verified / SCIENTIFIC FAIL BOTH POOLS. User sacct COMPLETED0:0,18:34:26,MaxRSS42923988K(~40.9355GiB batch accounting). Archive321375653bytes SHA35f371d04763e24d6a1ee4af0f3a9eff5e463c981da538ec84006e11051bb450;916 included files/917 members verified. P1095200 rows/current token checks,12 heads40epochs,1134960updates,fullCIC179886/UNSW148316 UID decisions independently reproduced. UNSW ensemble weighted attack/normalFPR: OLD_MATCHED99.9416/23.0415%,RECENT99.9849/21.2832%,RECENT_STATE90.7491/19.3087%,LEARNED35.0251/7.4092%;RAW90.7491/17.7011%. Learned adds43028 attack misses, three devices wholly missed; CIC adds105 with weighted attack97.5694%,FPR2.7524%. RECENT has useful development signal but high FPR; OLD_MATCHED is old features with new matched head, NOT historicalQ. Retrospective DEV-label single-threshold score-order bound at1%weightedFPR: UNSW OLD59.8948%,RECENT96.1919%,STATE37.8711%; diagnostic only, no new deployed threshold or gate change. NEXT focused mechanism design/literature for joint discrimination and attack-safe reference use; no new training/evaluation authorized. Read legacy_continuous_input_job177891_result_20260930.md and runs/legacy_continuous_input_job177891_result_20260930/. No auto-promotion/retry, ID_NOT_RUN, holdoutclosed, paperPAUSED, old edits/package preserved.

2026-09-29 latest: v3 Job177891 observed RUNNING on node188 at21:48:04CST (user screenshot, not live remote inspection). Elapsed08:00:29; stage P_FEATURE_WORKERS;524725/1095200 rows47.9113%; current treeRSS sample34.2634GiB; retries0,optimizer_updates0,historical_holdout_opened=false. Passed earlier input preflight/spool gates to reach feature workers; no model capability result yet. Feature-stage ETA17585.7s (~4h53m), not whole-chain ETA or guarantee. Submission now observed; do not submit again. User whole-chain authority remains valid, zero automatic retry. Evidence: runs/legacy_continuous_input_repair_execution_v3_20260929/job177891_observed_progress_20260929_214804.json.

2026-09-29 latest: v3 REAL FIXED CHAIN AUTHORIZED; user explicitly waives Claude code review for this package. Package SHA485a95d8bb93d14c281670d80c502b1c80045e3f1665382ddb49e4c4d3bb84c1 and delivery/bundle/clean-install hashes verified unchanged. Authority covers one P/E3/T(12 endpoints)/K(source CAL,CIC DEV,consumed UNSW)/export chain; no repeated stage approval, failure STOP and zero automatic retries. User operates upload/install/submit/pull through authenticated terminal; actual submission not yet observed and job ID unknown. 64CPU/192G/72h retained. See runs/legacy_continuous_input_repair_execution_v3_20260929/authorization.json. This explicit user waiver supersedes previous review/authorization-pending notes; sealed implementation records remain historical.

2026-09-29 latest: Job177491 FINAL SACCT RECORDED (user terminal output); memory follow-up complete. FAILED/1:0,587s,192G requested,64 CPUs; batch MaxRSS=AveRSS7291960K on node188/task0 (~6.9542GiB assuming KiB). Job-row memory fields blank. P preflight only; task/step accounting is not guaranteed whole-tree peak or temporal average. Failure remains MISSING_NAMESPACE_HEADERS, no OUT_OF_MEMORY state reported. KEEP192G for unmeasured E3/T/K. v3 implementation/65 tests/package unchanged; Claude code review and separate real-chain submission authority remain pending. See collab/20260929_job177491_final_memory_record_codex.md and runs/legacy_continuous_input_job177491_memory_followup_20260929/.

2026-09-29 latest: continuous-input v3 IMPLEMENTED / 65 tests PASS / Claude focused code review pending. User authorized owner scope isolation implementation and Job177491 sacct read, NOT real-chain resubmission. Full known registry retained; capture frozen query/reference owner union drives isolation. Full legacy audit retains1/346,2/7424,14/2 receipts; required-owner per-frame identities and fixed UID checks remain; assert every receipt incomplete event is outside-required-owner. Pinned real first/last fragment fixture demonstrates outside-owner target snapshot byte identity and required-owner STOP. Only input/audit production behavior changed; v2/model/loss/data/CAL/gates/resources unchanged. 65 tests (52 inherited+13 scope), Windows/Linux6each delivery, Bash and mock submit, PowerShell Mode PASS. Archive349678bytes SHA485a95d8bb93d14c281670d80c502b1c80045e3f1665382ddb49e4c4d3bb84c1;44modules. Design SHAa10a38edd2a871ebfb70cc37c1be3b1ac9715a2e0b0024019146f834b55674d9. No real P/E3/T/K retry or successful remote command. Job177491 final sacct pending operator output after SSH authentication failed; pre-exit archived sacct blank MaxRSS is not peak evidence; KEEP192G. Read legacy_continuous_input_repair_v3_implementation_20260929.md, collab/20260929_continuous_repair_v3_response_codex.md, delivery_v3 acceptance.json and OPERATE_HPC.md. HEAD/branch/8 unrelated edits preserved; paper PAUSED, ID NOT_RUN.

2026-09-29 latest: Job177491 pullback VERIFIED / preflight root cause identified / v3 scope-isolation PROPOSED, not implemented. Archive8ae5a2b6...f67abd,43 included files verified. Exact failure frame1135180 is intact IPv4 UDP FIRST fragment; default tshark reassembly hides its ports. Header census SHA verified for both consumed UNSW captures:28/4 fragment frames (14/2 first fragments), all from non-target registered owner70:5a:0f:e4:9b:c0; zero frozen query/reference hits and zero target-owner overlap. active00/01 preflight complete; entire P incomplete, realE3/T/K not started. Propose retain full known-owner registry and global legacy audit, isolate demonstrably outside-required-owner failures; target-owner strict checks remain. See collab/20260929_job177491_preflight_diagnosis_codex.md and runs/legacy_continuous_input_job177491_diagnosis_20260929/. No production changes, retry, remote command or scientific result. sacct export captured pre-exit RUNNING/blankMaxRSS; no measured peak, KEEP192G.

2026-09-29 latest: Job177491 FAILED during P anomaly preflight (user terminal screenshot; pullback not yet local). Slurm FAILED/1:0 elapsed00:09:47; status STOPPED_NO_RETRY, P_ANOMALY_PREFLIGHT_unsw-benign-20180528, MISSING_NAMESPACE_HEADERS; optimizer_updates0, retries0, historical_holdout_opened=false. Displayed completed1105920/5413239 is the last progress sample, NOT the exact failure frame. Displayed rss_gib7.03498 is a sample, NOT total-job peak or evidence to reduce E3/T/K resources. Source check: continuous_input_v2.Contexts.append rejects absent IP/transport-port fields for an otherwise selected protocol/owner; CaptureAudit writes failure frame/time and empty_fields into capture anomalies jsonl.gz. Fragmentation, capture truncation and decoder semantics remain hypotheses pending artifacts. Exporter includes anomaly_preflight; screenshot says Pullback archive ready. NEXT user runs existing transfer_v2.ps1 -Mode Pull, then verify archive and inspect anomaly_preflight/first_failure/logs before joint semantic repair review. No automatic retry, no frozen-rule changes, no model-capability conclusion; sealed v2 package unchanged.

2026-09-29 latest: Job177491 queued (user report); static memory review KEEP192G, insufficient confidence below130GiB; no150G package or remote job change. See legacy_continuous_input_v2_memory_review_20260929.md.


2026-09-28 latest: continuous-input v2 Claude review PASS/no blockers; exact package unchanged. See delivery_v2/review_acceptance.json and collab/20260928_continuous_repair_v2_review_claude.md. Real P/T/K NOT_STARTED; input stop => pull anomaly_preflight/ and first failure, no automatic retry.


2026-09-28 latest: continuous-input repair v2 implemented,52synthetic+6Windows/6Linux delivery PASS; D1 historical Q weighted99.938458%. Claude focused review pending; real P/T/K NOT_RUN. Parent v1 upload-blocked, paper PAUSED. See legacy_continuous_input_repair_v2_implementation_20260928.md and collab/20260928_continuous_repair_v2_response_codex.md.


2026-09-28 current: continuous-input v1 UPLOAD BLOCKED after independently verified Claude B1/B2 review; old package unchanged. B2 query rejection differs from context exclusion; D1 weighted-vs-unweighted attack gate needs prospective agreement. See collab/20260928_continuous_repair_v1_response_codex.md and Claude review. No v2 implementation or real execution yet; prior PACKAGE_READY superseded for upload.

2026-09-28 historical: continuous-input core repair IMPLEMENTED/synthetic36+installer6 PASS; final318692byte HPCpackage ready, REAL_CHAIN_NOT_STARTED;64CPU/192GB/72h fixed P/T/K with12heads; explicit whole-chain authority next. See legacy_continuous_input_repair_implementation_20260928.md and runs/legacy_continuous_input_repair_delivery_v1_20260928/acceptance.json + OPERATE_HPC.md. PaperPAUSED/ID_NOT_RUN.


## Current Experiment Map Control Panel

Status: active index. This top section is the current navigation map.

2026-09-28 latest: paper PAUSED; core continuous-input repair DESIGN READY, not implemented/executed. Recent current-inclusive E3 +26 causal state; matched old/recent/content+state heads and RAW/learned reference comparison;source-only FIT/CAL,fullCICDEV+consumedUNSW,1095200feature rows. Read `legacy_continuous_input_core_repair_design_v1_20260928.md` and `../legacy_continuous_input_core_repair_design_v1_20260928/implementation_and_review.md`. NEXT implementation/synthetic/package. Actualpaper remainsv0; interruptedv1 rewrite was not performed.

2026-09-28 scope update: recent-only Job174251/174666 review and currenttrainingcache;no ancientexperiment audit. Job174666341270features locallyverified,99.20516%attack preservedbut62013attackqueries liein exactfeaturetails;rawprovenance unresolved. Job174251fullLEARN/DEVcache pendingremote;localpartialsrejected. Jointtransfer+lowOODFPR first,necessaryconfirmation/ID/baselineslater. Newpaperworkingdraft started;method/results pending. See `recent_evidence_scope_and_repair_priority_20260928.md` and `../../paper_draft_commissioning_transfer_20260928.md`.

2026-09-28 latest: Job177299 cache audit COMPLETE/verified. All5devices source+feature+score constant from selectedattackquery7 (~6.3s),lasting~63.5min;72523/72553queries in tails. Normalstates vary;not solecause of misses,FULL14605falseveto persists. NEXT minimalcausal continuous-input/state design + attack/reference responsibility review,no repeatedaudit or blindtraining. See `legacy_unsw_saved_cache_audit_job177299_result_20260928.md` and delivery/result_review_job177299.

2026-09-28 latest: saved-cache read-only audit IMPLEMENTED/26local synthetic PASS;Linux delivery/mocked lifecycle PASS;16KB package READY. User authorized and operates upload/submit/pull;HPC_NOT_STARTED. Check 18pins/148408UIDs/source-field-vs-feature-vs-score repeats;no forward/training/rawdecode/thresholdchanges. Target26synthetic checks mandatory. Original~99% high attack recall +lowFPR remains goal,not currentexternalQ preservation alone. See `legacy_unsw_saved_cache_audit_implementation_v1_20260928.md` and `../legacy_unsw_saved_cache_audit_delivery_v1_20260928/OPERATE_HPC.md`.

2026-09-28 latest: bounded attack-transfer diagnosis complete. Five devices each show seven saved score states; early-prefix saturation plus unused duration confirmed synthetically, actual input/feature identity pending. Q and FULL fail separately; coherent roles, no forced module deletion. Next implement/review read-only saved-cache input audit, no training/raw decode/recompute. See `legacy_unsw_attack_transfer_diagnosis_and_repair_direction_20260928.md` and `../legacy_unsw_attack_transfer_diagnosis_v1_20260928/next_cached_input_audit_spec.md`.

2026-09-28 latest: UNSW recovery Job176975 COMPLETE/verified,scientificFAIL. Q59.9369%attack,FULL39.8068% with14605addedmisses;weightednormalFPR2.6129->0.7532%. RAW preservesQattack with1.6612%weightedFPR,limited control signal. Two Q device blindspots plus FULL TPLink suppression;no new experiment. See `legacy_commissioning_unsw_recovery_job176975_result_20260928.md`.

2026-09-27 latest authorization: UNSW recovery v2 full one-attempt evaluation AUTHORIZED;user upload/submit/pull,next job ID not yet observed. Exact package unchanged. See `../legacy_commissioning_unsw_recovery_delivery_v2_20260927/execution_authorization_20260927.json`;no repeated stage approval,zero automatic retries.

2026-09-27 latest: UNSW recovery v2 implementation READY;47synthetic+6installer PASS,92file package. Sealed input reuse,all features recomputed with durable blocks;oldpartialfeatures excluded. No real execution. See `legacy_commissioning_unsw_recovery_implementation_v2_20260927.md`;user upload/explicit one-attempt submission next. Prior repair-next notes historical.

2026-09-27 scheduler supplement: Job176411 FAILED1:0,8h18m/3days,MaxRSS~8.78GiB/96G,no recorded TIMEOUT/OOM. First worker/watchdog cause still unresolved. Next monitor/checkpoint repair and validated recovery preparation;no real retry. See `legacy_commissioning_unsw_job176411_scheduler_addendum_20260927.md`.

2026-09-27 latest: UNSW Job176411 failed at E3_FEATURES;31returned files verified;last progress137280/148408,not sealed feature completion. Two monitor defects reproduced synthetically;actual first cause lost/unresolved. See `legacy_commissioning_unsw_job176411_failure_review_20260927.md`. No scores/retry;prior READY and checksum-only status are historical.

2026-09-27 delivery correction: UNSW checksum sidecar CRLF fixed; install/submission had not started in user screenshot. Payloads unchanged, no reupload needed. See `../legacy_commissioning_unsw_evaluation_delivery_v1_20260927/checksum_lf_fix_v1/correction.md` and corrected OPERATE_HPC.md.
Older sections below are historical archive unless explicitly revalidated under this control panel.

### 2026-09-09 current navigation override

The latest top panel of `mainline_handoff.md` governs. The September 6 state below
is historical: real P/T and N1/N2/N3 have occurred, and the one outer comparison
is complete and CLOSED. This index correction adds no execution authorization.

| Issue | Current evidence | Next boundary |
|---|---|---|
| UNSW archival evaluation implementation 2026-09-27 | READY:26synthetic+6installer;43generated packets/56fields parity;87file clean package;small1.91MB upload;no real scoring | `legacy_commissioning_unsw_evaluation_implementation_v1_20260927.md`; delivery/OPERATE_HPC.md:user upload/explicit once-only submission/pull. Target preflight pending;16CPU/96GiB/72h bounds,4workers;reuse raw/E3. Frozen5device148316queries+92refs;oldFAIL/ID_NOT_RUN unchanged |
| UNSW external archival evaluation inputs 2026-09-26 | FROZEN:5devices,15derived SYN rules,766727training metadata rows audited;plan75763normal+72553attack+92refs;Q/RAW/FULL/NO_CF samecache;8matched controls | `legacy_commissioning_unsw_evaluation_preparation_v1_20260926.md`; NEXT versioned archival implementation/synthetic/package. ActualUIDs pending;foundation exposure unresolved, passive-only, ID NOT_RUN;no model/raw execution this stage |
| UNSW HPC raw qualification Job176183 2026-09-26 | COMPLETE/verified: 10,140,230 packets,770.907s;5 paired-device candidates;983,788 later normal positions/72,553 narrow SYN candidates;3 both-protocol minimums,2 TCP singleton fallback;sealed preflight12+result169 PASS | `legacy_commissioning_unsw_hpc_real_result_v1_20260926.md`: next labels+lineage and fixed passive evaluation preparation; no model result, ACTIVE/independence unproved, oldFAIL/ID NOT_RUN unchanged; no re-decode |
| UNSW HPC qualification delivery 2026-09-26 | READY; two-PCAP7.02GB package verified; exact synthetic field/Census parity, local clean installation/preflight PASS; original pins and unrelated edits retained | `legacy_commissioning_unsw_hpc_delivery_v1_20260926.md`; user upload/explicit one-job submit/pull, target compute-node preflight pending. 4CPU/64GiB allocation,48GiB guard,6h raw limit. No real decode/model action; full qualification and scientific boundaries unchanged |
| Attack-generalization claim clarified 2026-09-26 | Main target: new device/collection environment,similar attack patterns allowed. Fully novel mechanisms not a required mainline task. Recent99.20516% is positive within-CIC cross-device evidence;historical91.9089% uses unseen-family-name split and another pool | Latest handoff user-objective note. Preserve both metrics/frozen experiments;external collection transfer and joint false-alarm benefit still need confirmation. No new execution authority |
| UNSW raw qualification 2026-09-26 | Download COMPLETE7.02GB;diagnosis COMPLETE:5GiB guard triggered at5.075GiB,TShark97.11%RSS;thenhalfrow error.4,077,118frames accepted,57samples,5/5sealsPASS. Fullqualification unfinished | `legacy_commissioning_unsw_decoder_diagnostic_real_result_v1_20260926.md` / SHA. NEXT higher-memory same-semantics qualification preparation;noautoHPC/newdecode. Oldfailure/seeds/denominators/FAIL/ID NOT_RUN retained |
| Commissioning external paired-data research 2026-09-25 | COMPLETE/sealed;UNSW Attack Traces primary,CIC2023 backup.10MACs/234intervals;9TCP/UDP candidates,not9independent environments.30,776metadata bytes,4HEAD,0raw/modelactions. PriorUNSW metadata overlaps9/10;E3 exposure unresolved | `legacy_commissioning_external_source_research_v1_20260925.md` / SHA. NEXT recommend fixed2PCAP/7.02GB qualification for5devices;not yet downloaded/authorized. Passive transfer potentially testable;fullactive six-phase logs absent. Frozenpolicy/oldFAIL/ID NOT_RUN retained |
| Commissioning unused local raw qualification 2026-09-25 | COMPLETE/verified/sealed;51candidate+7Active,zero retries/modelactions. Gosund pair TCP2015/UDP2827826/HTTP0;Active52840legal but fixedhour1TCP+1UDPgroup belowmin2. Luohe identityconfirmed,Nmap labelsundefined | `legacy_commissioning_unused_raw_v1_20260925.md` / SHA.0full-policy newconfirmation devices;UNKNOWN_PASSIVE,oldFAIL/ID NOT_RUN retained. NEXT targeted independent paireddata with actual commissioning evidence;no more samecorpus rediscovery or automatic modelrun |
| Commissioning existing-data readiness 2026-09-25 | Metadata audit COMPLETE;0qualified fresh joint pairs.11used devices;2unresolved attack-directory leads:Gosund identity,Luohe Nmap labels.51members/297.2MB already local.26normal-only dirs/606PCAPs;Active other-owner counts unknown | `legacy_commissioning_data_readiness_v1_20260925.md` / SHA. Historical readiness stage; subsequent authorized raw qualification completed in row above. Not main-effect ready;no new scoring/training. OldFAIL/roles/policy/ID NOT_RUN retained |
| Unified commissioning real input preflight 2026-09-25 | COMPLETE,207.797s,zero retries;11sources/64targets.295plannedrefs across8devices,540components;5both/2UDP/1neither.11misses retain target fields,0mixing/0saturation;short-context hypothesis only.0modelactions | `legacy_commissioning_real_preflight_v1_20260925.md` / SHA. NEXT genuine operation evidence and untouched paired-device readiness. Active UNKNOWN_PASSIVE,tokenizer source methods only;no independent migration or accuracy result;historicalFAIL/ID NOT_RUN preserved |
| Unified commissioning implementation 2026-09-25 | Implementation + independent agent review PASS;92/92 Python3.9 synthetic tests,5 demos. Fixed policy planner/routing, original-prefix bounded attack trace bridge;0real actions. Prefix retention and translator/tokenizer retention explicitly distinct | `legacy_commissioning_implementation_v1_20260925.md` / SHA. Historical implementation boundary; bounded real LEARN/DEV input preflight subsequently authorized and completed (row above). New independent paired roster and active logs absent; historical FAIL/denominators preserved; ID NOT_RUN |
| Unified commissioning policy 2026-09-24 | DESIGN COMPLETE/sealed; fixed 1h, six functional phases, cap64 distinct components, same-protocol minimum2, causal cutoff and frozen R/Q/verifier routing. LEARN/DEV metadata: 5/8 both protocols, 2/8 UDP only, 1/8 neither; UNKNOWN_PASSIVE. Twelve design checks PASS, no real execution | `legacy_commissioning_policy_frozen_v1_20260924.md` / SHA. NEXT implementation + synthetic acceptance. New untouched paired confirmation roster not established; original hard pool, FAIL and consumed HOLDOUT preserved; ID NOT_RUN. No real-run authority |
| Qref post-confirmation diagnosis 2026-09-24 | COMPLETE/sealed;307 source pins,0forwards/updates/decode. Missing protocol refs explain fallback;811/1080 misses shared by3seeds. HTTP canonical groups contain2–3streams;current-token retention cause NOT_PROVEN. Later-only8h shortcut would remove357hardDEV FP | legacy_qref_post_confirmation_diagnosis_and_direction_20260924.md / SHA. NEXT bounded coverage+attack-input semantic preflight implementation;no automatic real run. OriginalFAIL/consumedHOLDOUT preserved;ID NOT_RUN |
| Paper priority: Qref device confirmation 2026-09-23 | Job174666 COMPLETE/verified;attack99.20516% preserved,FP51->30;weightedgain0.165755%,frozenFAIL;99.7734%weightederrors in fallback | legacy_qref_device_confirmation_real_result_v1_20260923.md / SHA. HOLDOUT consumed;onlyBorun gain. NEXT commissioning coverage and separate Q attack-miss design review;no automatic retrain/retune. IndependentID NOT_RUN |
| Unified dual-view capability baseline 2026-09-14 | Real P/T/E COMPLETE/verified/sealed,134.329s,zero retries; both contrasts TRADEOFF. U1 attack94.1983%,future92.8823%,OODpoolmean68.0306%; TPR@1%57.0957%,@0.1%18.4474%. VsU0 +8685 fixedattack, but street/stream FP99.7%/99.3% | `unified_dual_view_capability_real_result_v1_20260914.md`: E3 content adds attack information but no joint success or promotion. Next substantive qualifiedcoverage/representation design with research; no adjacent sameTRAIN tuning or automatic new experiment. B lacks E3; jointNOT_REACHED,strictFAIL,commissioningNOT_EVALUATED |
| Unified capability / representation starting point 2026-09-14 | Recover/exceed old best valid capability on four axes; broad input coverage alone is insufficient. Seen-attack aim about99% or better; retain old unseenOOD strengths and ID behavior. Leakage prevention explicit | `mainline_handoff.md` latest user priority: matched historical comparisons, joint attack/OOD improvement, then safe commissioning and independent validation. Old97.37% is not pure seen-attack recall; CHECK99.76% is insufficient broad proof. Causal prefixes/component separation/TRAIN-only preprocessing required. No frozen gate change or new experiment |
| Q/R / AB-start / representation-preserving readout 2026-09-13 | H_AB T/E COMPLETE/verified/sealed,318.469s; bothcontrastsTRADEOFF. Attack89.3989%,OODpoolmean22.4111%,TPR@1%35.3542%,@0.1%33.3096%; vsAB+707attack/+284normalFP | `frontend_ab_readout_preservation_real_result_v1_20260913.md`: END adjacent same15073TRAIN head/lr/epochs/freeze/KD tuning. Next justifiedinput/qualifiedcoverage design with targetedresearch; no automatic newexperiment. JointNOT_REACHED,strictFAIL,commissioningNOT_EVALUATED |
| Fixed-C2 mechanism diagnostic 2026-09-12 | COMPLETE/verified/sealed80.844s;15073 TRAIN/9379 teacher, zero updates. Teacher reaches encoder but134/197 bucket gradients oppose label; aux/deploy rank correspondence differs within attacks | `frontend_transfer_diagnostic_real_result_v1_20260912.md`: diagnosis preserved; next design now Q/R above. Local TRAIN geometry does not explain all prior low-FPR degradation or prove generalization |
| Joint capability / task-knowledge transfer 2026-09-11 | V2 T/E COMPLETE/verified/sealed; C2 attack94.6425%, OOD pool-mean22.60%; all contrasts TRADEOFF. Loss/log review does not prove transfer route exhausted; late clipping absent, guard rarely active | `frontend_transfer_fair_trial_and_target_clarification_20260911.md`: attack priority,99.99%/97% aspirations; fully unseen families optional extension. Bounded mechanism diagnosis is now authorized under September12 scope; no automatic retraining/tuning/download; retain AB/C0 and prior results |
| Fixed A expanded comparison 2026-09-11 | COMPLETE/PASS,262050 targets,85.469s. A84.05% vs AB89.11% attack; B improves aggregate but worsens scan/Telnet/hydraulic. Attack negative flips13994, positive26333 | `frontend_a_expanded_eval_real_result_20260911.md`: base transfer deficit and local compatibility costs coexist; choose targeted training intervention next. No new real execution authorized |
| Fixed AB expanded evaluation V2 2026-09-11 | COMPLETE:262050 targets,76min,execution/seal PASS. Attack97.3698% ->89.1092%; predictive FP42.8333% ->1.0778%, street/stream regress; broad retention unachieved | `frontend_expanded_result_next_decision_20260911.md`: next recommend one fixed-A evaluation on prepared same inputs to separate base transfer loss and B-supervision cost; reuse AB scores, no train/decode. Proposed A evaluation not authorized/executed; V1/V2 preserved |
| Paper objective / method direction 2026-09-10 | Late P2 has attack and stream-OOD joint progress; V3 has separate coverage/learning progress; broad unified capability and safe commissioning unresolved | Read `project_state_and_research_priority_20260910.md`: representation/learning capability is primary, paired data follow existing CIC IoT 2022 PENDING research. Conditional-branch priority withdrawn; no new mechanism or execution selected |
| Frontend-F4 / F5 | F4 remains PASS; F5 T ended NO_ELIGIBLE_CHECKPOINT | No F4 repeat, F5 retry or K access |
| Inheritance N1/N2/N3 | Attempts CLOSED; N3 satisfies all 12,711 fitted constraints, a finite-set repair witness | Preserve witness; broader inheritance NOT_PROVED |
| Fixed-N3 outer comparison | `frontend_inheritance_outer_real_result_20260909.md`: 1,995/2,000 attacks retained, all 2,400 benign correct including 1,224 B; A retention REGRESSION_ON_THIS_POOL | Reassess the route from project goals; compare diagnosis and fuller lawful A+B training before intervention; no new execution authorized |
| Workflow / HPC continuity | `mainline_workflow_and_hpc_continuity_20260909.md`: maintenance, independent research judgment, collaboration preferences, selected HPC lessons and history gap | Literature-first technical recommendation; neither inherited route nor user's proposal accepted automatically; no remote action authorized |
| Objective-aligned paired learning | V3 CLOSED; real execution/seal verified, A/AB each40 epochs. A attack misses both2/825; A normal FP both0/1302; B normal FP538/1066 -> 0/1066. See `frontend_paired_train_v3_real_result_20260910.md` | Retention FAIL, B normal gain PASS, B attack check=0. Next: bounded diagnosis + larger ID/hard-OOD/attack evaluation-scope proposal; see `frontend_post_paired_next_step_and_head_review_20260910.md`. No new execution; heartbeat deleted |

### 2026-09-06 frontend navigation override

Current frontend state is governed by the September 6 entries in
`mainline_handoff.md`; older architecture/status tables below are historical.
F4 implementation/audit is complete. F5 is FROZEN and implementation/synthetic
verification passed; real P/T/K has not been authorized or started.

| Issue | Current evidence | Next authorized action |
|---|---|---|
| Frontend-F3 / F4 | F3 whole-signature OOV diagnosed; F4 fieldwise input PASS: 13,866/13,866 targets, 205,470/205,470 events exact round-trip, 3,173 all-UNK recovered, zero collisions, 28/28 tests | Closed input audit; continue via F5, do not repeat F4 |
| Frontend-F5 | FROZEN shared GRU/student head; 47/47 synthetic tests; resource screen PASS; P/T/K controller and monitor ready; zero real training | Await explicit P teacher-preflight authorization, then separately authorized T/K; all scientific capability claims remain open |

### Maintenance Protocol

- This file is an index, not the full lab notebook.
- Keep detailed evidence, tables, and diagnostics inside numbered `runs/issue*/` directories.
- Add at most one compact row per issue here unless the issue changes the mainline.
- If an issue changes the mainline, update `mainline_handoff.md` first, then update one row here.
- Preserve old experiments as historical evidence; supersede rather than delete.
- Do not use old report-only or diagnostic results as current evidence unless revalidated under the current data contract.
- Future issue summaries should close with:
  - `solved`
  - `changed_mainline: yes/no`
  - `active_blocker`
  - `frozen`
  - `superseded`
  - `next_action`

### Current Paper/System Center

Current working definition:

```text
Low-false-alarm few-shot online NIDS under dual distribution shift:
benign OOD drift causes false alarms, and attack support-query drift causes missed detections.
```

Current system object:

```text
Gotham PCAP -> Kitsune115 -> clean split assets -> versioned label support memory -> binary attack head / OOD-risk / controller
```

Current stage:

```text
C1/portable features have transferable rank signal; cross-source calibration and report hard-alarm suppression remain unresolved.
```

### Current Truth Table

| Item | Current status | Source issue | Confidence | Notes |
|---|---|---|---|---|
| Frontend | Kitsune / AfterImage / netStat 115D from raw PCAP | issue27ab and follow-up audits | frozen | 8D strict packet-header is engineering smoke only |
| Benign/OOD 1M roles | usable under sealed role rules | issue27bz | active | ID train/calib, OOD val/stress, sealed final OOD remain role-restricted |
| Attack support/query/final roles | certified complete-only attack subset frozen | issue27cb/issue27cc/issue27cd/issue27cg/issue27ch | active | 683,420 certified rows from 93 complete chunks; six partial combined-cycle-1 chunks deferred_not_deleted |
| Support memory | one ten-label `label_support_region_registry_v1`; immutable 385 train and 127 validation views; archive/candidate/update contracts ready | issue27cf/issue27ci/issue27ckg | active protocol, production updates blocked | wait for issue27ckc then certify one bounded update budget through detector non-regression |
| Model replay | frozen-medium issue27ckc HPC capability replay pending; geometric region experiments do not alter it | issue27ckc/issue27ckg | running/pending | inspect aggregate, low-FPR, OOD, and per-label results before designing update ablation |
| Open-world temporal verifier | CKBJ v2 seed-27 formal run completed; registered `NO_GO` | issue27ckbd/issue27ckbe/issue27ckbi/issue27ckbj | current realization rejected | stream OOD remained 100%; attack recall fell 1.8996 pp; fix sparse-train/dense-report mismatch before any new formal seed |
| Frontend observability/calibration gate | CKBL/CKBM/CKBO/CKBP completed; first CKBQ pair failed before training and has no metric | issue27ckbl/issue27ckbm/issue27ckbo/issue27ckbp/issue27ckbq | raw AfterImage has cross-family normality signal; corrected CKBQ target-scope isolation passed real 385/69/3,129 regression | rerun only corrected CKBQ seed 27 dual-partition result job |
| Formal benchmark | not authorized | current governance | blocked | requires clean data contract and frozen system protocol |

### Active Issue Index

| Issue | Purpose | Verdict/status | Mainline effect | Next |
|---|---|---|---|---|
| issue27bz | Execute and certify 1M Gotham Kitsune115 cache | certified merge passed for benign/OOD roles | 1M benign/OOD asset becomes usable | keep role restrictions |
| issue27ca | Initial support-bank contract on certified 1M | taxonomy caveat found | attack-side support cannot be trusted at coarse label level | exact-label attack audit |
| issue27cb | Broader attack support candidate contract | exact support labels found, query/final blockers found | multi-type support is possible but old attack query/final invalid | targeted exact-label materialization |
| issue27cc | Targeted multi-type attack materialization and onset realign plan | ready for Slurm exact-label materialization | defines legal attack rebuild contract | run issue27cd |
| issue27cd | Slurm exact-label targeted attack materialization | partial pullback: support/sealed final complete, dev_future_query missing 28,175 rows | source evidence for complete-only certification | issue27ch excludes partial chunks instead of repairing them |
| issue27ce | Support-bank protocol and system interface spec | support-bank protocol/interface frozen; thresholds and indices pending | freezes support-bank boundaries without model metrics | instantiate initial bank from complete support pool |
| issue27cf | Initial support bank instantiation | 69,492 candidates -> 512 selected rows; 10 exact labels; train/val disjoint | support-bank state is clean but model replay still blocked | issue27ci protocol refinement after issue27ch freeze |
| issue27cg | Combined-cycle query alignment audit | issue27cd shortfall localized; six partial chunks not worth repairing under current contract | supersedes direct repair route for current mainline | freeze complete-only certified subset |
| issue27ch | Certified attack subset freeze for protocol replay | certified_attack_subset_v1 frozen: 683,420 rows, 93 complete chunks, six partial chunks deferred_not_deleted | changes active attack data contract from partial pullback to complete-only certified subset | issue27ci attack region activation and support-bank protocol refinement |
| issue27ci | Region/provenance layer separation | support_region_protocol_v1 separates exact labels, provenance seeds, geometric candidates, and active evidence | retained governance foundation | formal label-memory registry now issue27ckg |
| issue27cj | Raw-115D geometry diagnostic | failed qualification with severe OOD overlap and label confusion | diagnostic negative result | archived geometry evidence |
| issue27ck | S3 geometry repair | one static active-strong region under single medoid | selected S3 as diagnostic representation | archived diagnostic annotation |
| issue27ckd | Frozen-bank multi-prototype diagnostic | two static strong candidates but temporal/query instability | shows one-medoid under-expression | archived diagnostic annotation |
| issue27cke | Bounded geometric-support extension audit | no material support-val gain and GRE OOD-stress trade-off | rejects E64/E128 as deployment updates | archived negative update evidence |
| issue27ckf | Fresh geometric-certification holdout feasibility | no fresh pair for current labels; CoAP-only unused pair | relevant only if automatic geometric routing is reopened | no longer blocks label-memory implementation |
| issue27ckg | Label-support region registry and versioned update protocol | ten exact-label memory regions, immutable 385/127 views, append-only archive, candidate gates, simulation-only promotion, and rollback contract pass | changes the formal region from geometric evidence to label-memory management | wait for issue27ckc, then issue27ckh detector update-budget ablation |
| issue27ckbd | PyG TGN event contract audit | passed label/future invariance, past sensitivity, source-reset isolation, and held-family role exclusion | maintained TGN adapter is permitted; no classifier claim | materialize full-source event cache |
| issue27ckbe | Full-support TGN event cache | HPC job 150067 completed 26/26 sources, 34,622 target alignments, no raw label reads | T0 substrate is ready; no training/performance claim | M1 under fixed per-packet support and strict leave-family protocol |
| issue27ckbi | Four-source report-only TGN extension | Stage A job 150547 completed with separate manifest and zero fit/select use | report coverage completed without changing the 26-source T0 freeze | consume only in label-free past-only report replay |
| issue27ckbj | Single-seed formal M1 v2 | AMD job 151377 completed; contracts passed; decision `NO_GO` | rejects current sparse-train/dense-report M1 realization; does not establish a general TGN failure | do not run seeds 37/47; repair temporal replay/task/gate audit before another formal seed |
| issue27ckbk | TGN replay repair plus maintained GraphMixer comparison | AMD job 151489 partial: TGN fail-fast assertion; GraphMixer completed `NO_GO` | rejects GraphMixer realization and blocks same-route rerun; no repaired-TGN metric claim | run feature-information gate before another temporal backend |
| issue27ckbl | Strict fit-only frontend observability gate | bounded local real-data run `TRUNCATED_LOCAL_NO_SIGNAL`; 9D weak, 69D matched its permuted control, 207D stronger | changes immediate mainline from backend repair to full feature-observability validation | run frozen full-source protocol with all 385 support rows |
| issue27ckbm | Official TabM plus causal source-relative calibration | seed-27 AMD compute recovered without retraining; validator `PASS`, scientific `NO_GO`; stream 99.6%, overall attack -0.4331 pp, UDP Scan -71.68 pp | rejects symmetric TabM/ExtraTrees suppression; diagnostic only because both development canaries were not globally excluded from fit/select | no more seeds; harden all-canary audit and preregister one-sided normal-evidence suppression |
| issue27ckbo | Mature AfterImage115 transfer plus legal auxiliary normal diversity and TabM | AMD job 151780 completed; all contracts passed; primary `NO_GO`: stream 99.733%, predictive 73.011%, hydraulic 42.533%, attack -6.091 pp | raw115 shows family-dependent signal; raw115+Aux strictly dominates contrast+Aux; contrast and symmetric verifier rejected | no more seeds; source-held-out one-sided normal-evidence calibration with raw115 control |
| issue27ckbp | Source-held-out one-sided normal-evidence calibration | AMD 151835 completed; registered `NO_GO`; M2 result is protocol-degenerate because threshold 1.0 selects only cold-start rows | preserves valid scope audits and an interpretable M1 static-normal diagnostic, but rejects current source-local gate | no extra seeds; repair cold-state separation, warmed attack selection, and deployment-equivalent history |

### Latest Compact Close-out

```text
solved: issue27ckg instantiated and validated the single exact-label support-memory registry and versioned update workflow.
changed_mainline: yes
active_blocker: production extension budgets and detector non-regression remain uncertified while issue27ckc is pending.
frozen: ten label-support regions, 385/127 views, archive/candidate gates, production-promotion disable, model-update contract, and rollback lineage.
superseded: geometric strong/weak status as formal region membership and fresh-data acquisition as a prerequisite for label-memory implementation.
next_action: issue27ckh_support_update_budget_and_binary_head_nonregression_ablation_after_issue27ckc.
```

### Current Rule For Future Issue Docs

Every issue may keep its full local detail, but its close-out summary should include:

```text
solved:
changed_mainline: yes/no
active_blocker:
frozen:
superseded:
next_action:
```

---

## Historical Archive Begins Below

The following sections are preserved from earlier experiment map revisions.
They do not override the Current Experiment Map Control Panel.

Canonical path: `runs/mainline_docs/mainline_experiment_map.md`

> 版本：v3 convergence-first（2026-04-23）
> 用途：作为汇合后的主线总地图，优先呈现当前真实 paper center、证据分层、下一阶段最小实验包，并将旧路线下沉为历史资产/归档。

---

## 0. 文档用途与维护规则

Maintenance rule:
- Keep this as the single living mainline experiment map.
- Update this file continuously as mainline experiments advance.
- Do not create dated copies for the mainline map.
- This v3 map supersedes the old unsupervised-first v2 ordering.
- Historical runs and old planning are preserved below, but archived sections no longer define the current paper center.

What this file should answer first:
- What is the current paper center?
- Which evidence is primary, diagnostic, negative, or archived?
- Which minimal experiments remain necessary under the convergence-first storyline?
- Which old routes are preserved only as historical assets?

---

## 1. 当前项目重定性

### 1.1 Current Paper Center

当前论文中心已经从旧的“stronger OOD + calibration + TailReg / unsupervised mainline”切换为：
- `strict low-OOD-alarm operating region`
- `unsupervised detection collapse`
- `few-shot target-aligned detector`

一句话口径：严格低 OOD 误报部署区间揭示了无监督网络异常检测的目标错配；在 frozen benign representation 上，仅用极少量 high-purity attack positives 的 target-aligned linear head，就能显著恢复低误报区间的检测能力。

### 1.2 四个当前定位

- `original100 few-shot official control` 是主线官方控制组，用来固定 target alignment 这个主要杠杆。
- `source_rich` 的角色经 v7.4 paired verification 后，可狭义写成 `hard-holdout robustness + auditability`，但不是平均性能全面压过 original100 的主英雄。
- `A-line second-environment` 已封口为 `negative evidence / limitation / external-validity boundary`，不再扩跑、不再救线、不进入正向主证据。
- old mainline 的 stronger OOD、calibration、TailReg 资产仍然重要，但现在是背景机制资产与历史证据，不再单独定义当前 paper center。

### 1.3 已退场的旧叙事

当前地图不再支持以下表述：
- “无监督 frontend-f2 已经翻盘。”
- “source_rich_v1 是击败 dA 的唯一原因。”
- “第二数据集正在逐步支持旧主线。”
- “继续修 tokenizer / AE / scorer 是当前主线最优先事项。”
- “TailReg 是当前论文唯一或最高层方法中心。”

---

## 2. 当前论文中心与创新点

### 2.1 立脚点

开放世界 IoT 异常检测的难点不是一般性的 AUC 排名，而是在 stronger benign OOD 条件下，模型必须在严格 low-OOD-alarm operating region 内仍保持 attack detection。传统 unsupervised detector 在这个区间容易出现 detection collapse；few-shot target alignment 用很少的 high-purity attack labels 修正了训练目标与部署目标的不一致。

### 2.2 创新点 1：问题定义重写

把评估核心从“整体 AUC/平均分数更高”重写为：
- fixed 或 guarded low-OOD-alarm operating point 下是否可用；
- final OOD eval 不参与阈值选择；
- ID benign、OOD benign、high-purity attack 的角色必须清楚分离。

### 2.3 创新点 2：机制发现

系统实验说明：
- stronger benign OOD 会放大误报与阈值失配；
- 压低 OOD alarm 后，无监督 score 的 attack detection 可能同时塌陷；
- 这不是单个模型弱，而是 objective 与 deployment target 不一致。

### 2.4 创新点 3：方法杠杆

few-shot target-aligned detector 是当前方法中心：
- positives = stage2 high-purity attack；
- negatives = ID benign + OOD benign；
- model first = L2 `LogisticRegression` with balanced class weights；
- budgets 至少包括 16-shot 与 32-shot；
- 多 positive-sampling seed 输出 mean / min / max；
- operating points 包括 `fixed_id_calib_q99` 与 `guarded_id_calib_and_ood_val_target1pct`。

### 2.5 Source-Rich 的克制定位

`source_rich` 只能在证据支持范围内写成：
- narrow hard-holdout robustness evidence on specific paired holdouts；
- auditability / family-scale-feature explanation layer；
- 对 objective mismatch 的机制诊断资产。

不能写成：
- source-rich 平均性能全面强于 original100；
- frontend 重构本身已经无监督翻盘；
- source-rich 是 few-shot 成功的唯一原因。

---

## 3. 当前证据分层地图

### 3.1 主证据

| Evidence | Current role | Paper use | Boundary |
|---|---|---|---|
| original100 few-shot official control (`runs/original100_fewshot_official_control_2026-04-22/`) | official control | 主文或主附录核心表 | 证明 target alignment 是主要杠杆，不证明 source-rich 胜出 |
| frontend-f2 v7.2 / v7.3 few-shot | target-aligned positive evidence | 主文或主附录 | 必须和 original100 同口径比较 |
| frontend-f2 v7.4 paired holdout fairness | narrow hard-holdout robustness evidence | 主文解释段或主附录 | 只支持特定 hard holdout，更不支持平均性能全面胜出 |
| stronger benign OOD + calibration old mainline | problem/mechanism evidence | 主文背景和机制段 | 不再单独作为 paper center |
| unsupervised baselines under low-OOD-alarm | collapse evidence | 主文机制段 | 不写成“模型差”，写成目标错配 |

### 3.2 机制诊断资产

| Evidence | Use |
|---|---|
| TailReg / calibration / stronger OOD 历史结果 | 解释低误报区间、阈值选择、尾部分布失配 |
| frontend-f2 early tokenizer / AE / temporal / contrast negative lines | 说明“不是没有信号，而是无监督 objective 不对齐” |
| TON threshold-sensitivity + coupling probe | 说明 threshold/operator bug 被排除，模型-表达耦合真实存在 |
| source-rich feature/family/scale analysis | 支撑 auditability 和 hard-holdout case study |
| collapse sanity audit (`runs/collapse_sanity_audit_2026-04-25/`) | 已完成；结论为 `collapse_likely_real_operating_point_effect`，当前 dA official cache 未发现 row-order / index / threshold 泄漏问题，旧 transformer raw cache 仅作 legacy auxiliary evidence |
| Prism collapse sanity handoff (`runs/prism_handoffs/handoff_collapse_sanity_audit_2026-04-25.md`) | paper-facing 段落已生成；用于把 collapse sanity audit 写成保守正文资产 |
| issue02 original normal-vs-attack sanity (`runs/issue02_original_da_normal_attack_sanity_run_2026-05-08/`) | 已完成；clean115 原始 normal-vs-attack 下 dA 很强（AUC `0.9340`, PR-AUC `0.9487`, q99 attack detection `0.8642`, benign false alarm `0.0107`），few-shot LR 在该原始 setting 下波动大。用途是支持“low-OOD collapse 更像 deployment working-point 问题”，不是证明 LR 全面优于 dA |

### 3.3 负结果资产

| Evidence | Use |
|---|---|
| BoT-IoT split-feasibility failure | negative evidence；说明 formal split 支撑不足 |
| TON-IoT fixed operating point failure | negative evidence；说明 current formal protocol 不外推 |
| FT fixed zero-detection on TON | detection collapse / coupling evidence |
| old unsupervised frontend-f2 patches | 负结果资产；支撑 objective mismatch 解释 |

### 3.4 Limitation / Archive

| Asset | Status |
|---|---|
| A-line second-environment | closed limitation / external-validity boundary |
| “source_rich 平均性能全面优于 original100” | archived old tendency, not current claim |
| “无监督 frontend-f2 超越 dA” | archived old route, not current claim |
| old must-do second-dataset rescue line | archived planning, not active |
| broad unsupervised tokenizer / AE patch expansion | archived planning, not active |

---

## 4. 旧实验如何吸收

### 4.1 Stronger OOD / Calibration / TailReg

吸收方式：
- 作为 low-OOD-alarm operating region 的问题定义与机制背景；
- 作为 unsupervised detector 在部署阈值下失配的历史证据；
- 作为论文前半段的 motivation / mechanism，不再作为当前唯一方法主线。

保留边界：
- TailReg 可以作为模型层补充资产，但不应压过 few-shot target alignment。
- calibration 是重要机制杠杆，但当前方法中心不是“只调阈值”。

### 4.2 Original100 Few-Shot Official Control

吸收方式：
- 作为主线官方控制组；
- 必须进入主文或主附录核心表；
- 固定 few-shot target-aligned protocol 的口径和边界。

已固定结果：
- 16-shot fixed: AUC mean/min/max `0.990672 / 0.958007 / 0.999974`, OOD alarm max `0.009500`, det min `0.914182`。
- 16-shot guarded: AUC mean/min/max `0.990672 / 0.958007 / 0.999974`, OOD alarm max `0.009200`, det min `0.914182`。
- 32-shot fixed/guarded: AUC mean/min/max `0.984615 / 0.967632 / 0.999910`, OOD alarm max `0.009800`, det min `0.920727`。
- dA reference remains unsupervised and not in the same label-information setting。

### 4.3 Frontend-F2 v7.2 / v7.3 / v7.4

吸收方式：
- v7.2 / v7.3：作为 few-shot target-aligned positive evidence，并与 original100 official control 同口径比较。
- v7.4：已完成 paired verification，可狭义写为 `source_rich_hard_holdout_robustness_supported`，但边界必须保持很窄：
  - paired integrity 已确认：
    - same holdout specs
    - same label budgets
    - same seed set
    - same threshold rules
    - final OOD eval does not participate in threshold selection
  - `original100` 仍是平均性能控制组，按 `det_mean` 赢 `7/9` holdouts，不能忽略。
  - `source_rich` 的可写价值是：
    - 在特定 hard holdout 上比 original100 更稳；
    - 更适合做 family / scale / feature 级别审计；
    - 不是 universal cross-window winner。
  - 当前最强可写 case：
    - `chrono_late_train_early_eval`, 32-shot, guarded:
      - `source_rich`: `AUC_min=0.9494`, `det_min=0.8549`, `alarm_max=0.0099`, `feasible_rate=1.0`
      - `original100`: `AUC_min=0.7030`, `det_min=0.6824`, `alarm_max=0.0029`, `feasible_rate=1.0`
    - `holdout_bin_2`, 16/32-shot, guarded:
      - `original100` segment-collapse is severe;
      - `source_rich` keeps useful detection, but alarm is only near-target rather than fully stable.
  - paper-facing asset bundle 已生成于：
    - `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/branch_handoffs/frontend_f2/paper_facing_hard_holdout_cases.md`
    - `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/branch_handoffs/frontend_f2/source_rich_original100_boundary_table.csv`
    - `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/branch_handoffs/frontend_f2/source_rich_auditability_summary.md`
- early frontend-f2 tokenizer / AE / temporal / contrast lines：作为机制诊断资产和旧路线负结果，不再作为当前 paper center。

### 4.4 Second-Environment

吸收方式：
- BoT-IoT 与 TON-IoT 只写成 limitation / external-validity boundary；
- 不再作为主证据；
- 不继续扩跑、调参或救线；
- 若未来要重新打开，必须新日期、新 protocol、新 run_tag。

---

## 5. 后续最小实验包

当前只保留三类后续实验包。任何新实验必须直接服务这三类之一。

### 5.1 Few-Shot 主发现支持包

目的：证明 target-aligned few-shot 不是 lucky split / lucky seed。

最小内容：
- cross-window / alternate attack segment / hard holdout 验证；
- 16-shot、32-shot、多 seed 的 mean/min/max 表；
- fixed 与 guarded operating points；
- final OOD eval 不参与阈值选择；
- paper-facing operating-point 图和核心表。

### 5.2 Source-Rich 独特价值支持包

目的：证明 source-rich 的合理定位是 hard-holdout robustness + auditability。

最小内容：
- 基于已核验的 v7.4 做 paper-facing hard-holdout case analysis；
- 固定保留 original100 paired control，不允许删掉对照；
- 把 narrow robustness claim 与 average-performance non-win 边界同时写清；
- family / scale / feature 级别 auditability 分析；
- 与 original100 的适用边界图或案例表。
- 当前已落地的 paper-facing 资产包位于 frontend handoff 目录，可直接供论文正文 / 附录引用。

### 5.3 部署意义支持包

目的：证明 few-shot target alignment 不是不可部署的“监督作弊”。

最小内容：
- high-purity attack positives 的标签预算说明；
- 训练成本和推理成本；
- 与 dA / unsupervised baselines 的 low-OOD-alarm operating-region 对照；
- 对“监督当然赢”的审稿攻击给出 label-efficiency + fairness protocol 防御。

当前 paper-facing 写作包：
- `runs/prism_handoffs/handoff_fewshot_target_alignment_2026-04-25.md`
- `runs/prism_handoffs/fewshot_dataset_split_budget_summary_2026-04-25.csv`
- `runs/prism_handoffs/fewshot_paper_main_table_2026-04-25.csv`
- `runs/prism_handoffs/handoff_paper_restructure_from_transformer20_to_fewshot_2026-04-25.md`：已生成；用于 Prism 将旧 Transformer ensemble 稿重构为 few-shot target alignment 新主线，不改变 v3 convergence-first paper center。
- `runs/prism_handoffs/paper_restructure_section_decision_table_2026-04-25.csv`：旧稿章节处理裁决表，供 Prism 重排标题、摘要、方法、结果、讨论与结论。

用途：
- 交给 Prism 写 few-shot target alignment 正文；
- 回答 dataset / split / budget 口径问题；
- 明确 `16-shot` / `32-shot` 是训练 high-purity attack positives 的预算，不是评估集规模；
- 固定 dA 为 unsupervised reference，original100 为 official control，source_rich 为 hard-holdout robustness + auditability 资产。

### 5.4 Next Phase: Base-Detector-Agnostic Guarded Few-Shot Adapter

Status:
- This is a candidate next phase, not a completed experiment.
- It upgrades the narrative from "replace dA with few-shot LR" to "use few-shot target alignment as a guarded deployment adapter on top of base detectors".
- The current paper center remains `strict low-OOD-alarm operating region` + `detection collapse` + `few-shot target alignment`.

2026-05-08 strategy update:
- dA remains a classic lightweight cold-start unsupervised detector.
- Transformer should be treated as a possible modern contextual base detector, but the project still needs evidence retrieval before claiming ordinary-setting strength.
- L2 `LogisticRegression` remains the minimal target-alignment baseline; it is not automatically the final adapter head.
- Candidate names include `Guarded Few-shot Adapter (GFA)`, `Base-Detector-Agnostic Guarded Few-shot Adapter`, and `Guarded Deviation Adapter (GDA)`.

Candidate adapter inputs:
- base representation: `original100` or future Transformer hidden representation;
- base detector score: dA RMSE or Transformer anomaly score;
- few-shot high-purity attack positives;
- ID benign + OOD benign negatives.

Candidate adapter output:
- attack-oriented score;
- evaluated under `guarded_id_calib_and_ood_val_target1pct`;
- final OOD eval and attack eval remain excluded from threshold/model selection.

| item | current_status | evidence_status | role_in_paper | next_action | risk |
|---|---|---|---|---|---|
| dA only | completed reference baseline | strong in original normal-vs-attack issue02 sanity; collapses under guarded low-OOD main protocol | classic cold-start detector and unsupervised reference | keep as reference; do not frame as invalid detector | writing dA as "failed model" would misstate the evidence |
| Transformer only | historical exploratory line | stronger-OOD evidence exists; no formal ordinary normal-vs-attack proof stronger than dA found in this update | possible modern base detector, not current paper center | perform Transformer evidence retrieval before any claim | historical results may be non-comparable or not reproducible |
| LR original100 minimal baseline | completed mainline control | strong guarded few-shot control on primary split; original normal-vs-attack LR is seed-sensitive | minimal target-alignment baseline | keep as baseline for adapter comparisons | confusing minimal baseline with final method |
| dA-assisted adapter | proposed feasibility direction | not yet run under current guarded paired protocol | candidate lifecycle story: dA cold-start plus few-shot adaptation | first run score-alignment inventory, then paired feasibility if aligned | dA score may add no stable value beyond original100 |
| Transformer-assisted adapter | proposed feasibility direction | needs Transformer base evidence and aligned scores/representations | candidate modern-detector adapter | retrieve Transformer ordinary-setting and low-OOD score evidence first | cannot support detector-agnostic framing without clean Transformer evidence |
| detector-agnostic GFA/GDA | proposed next-phase framework | not yet completed; requires at least two base detectors | future method framing candidate, not current claim | define shared adapter protocol after dA/Transformer evidence gates | detector-agnostic claim requires multiple base detectors |
| prototype adapter | future optional head | not run | possible nonlinear target-alignment head | only compare after LR baseline and detector-score adapters are fixed | model-capacity gains may obscure target-alignment contribution |
| cost-sensitive / low-OOD-aware adapter | future optional head | not run | possible low-alarm-aware adapter variant | pre-register a small fixed weighting set; no final-eval tuning | large sweep could become uncontrolled method search |
| second-environment validation | closed limitation under current protocol | BoT-IoT/TON-IoT sealed as negative evidence / boundary | limitation and external-validity boundary | reopen only with new dated same-protocol manifest | forcing dirty external data would weaken credibility |
| modern unsupervised baseline comparison | partial historical evidence | Deep SVDD, FT, other baselines exist mainly as collapse/negative evidence | reviewer attack-surface reduction, not paper center | keep as archived support unless a targeted gap remains | turning into model zoo would dilute the main story |

Issue02 evidence routing:
- Run: `runs/issue02_original_da_normal_attack_sanity_run_2026-05-08/`.
- Data: clean115, `200000` rows, `115` dimensions; benign `121621`, attack `78379`.
- dA original normal-vs-attack: ROC-AUC `0.9340`, PR-AUC `0.9487`, q99 attack detection `0.8642`, benign false alarm `0.0107`.
- few-shot LR original normal-vs-attack is seed-sensitive and should not be written as a dA replacement.
- Recommended use: appendix sanity comparison.
- Non-use: do not put it in the main-text core result, and do not claim LR is generally stronger than dA in the original setting.

Transformer evidence retrieval note:
- Search found clean115 `trans115_min` / `da115_min`, but they are ID-only minimal checks with no attack metrics.
- Search found stronger-OOD Transformer/FT/ensemble evidence, but that is not ordinary closed-set normal-vs-attack evidence.
- Current status: `needs evidence retrieval`.

### 5.5 当前不再推进的实验包

- second-environment rescue / expansion；
- 新一轮无监督 tokenizer / AE patch；
- 大范围 baseline 家族扩张；
- 以 TailReg 或 calibration 重新抢回唯一主线中心；
- 即使 v7.4 已核验，也不能写 source-rich 的稳定平均胜出结论。

---

## 6. 历史路线归档区

以下内容为 v2 旧地图与历史追加内容的原文归档，保留 run 名、裁决、边界和操作书，供追溯与论文附录取材使用。

Archive rule:
- Archived content is evidence inventory, not the active paper-center ordering.
- If archived text conflicts with Sections 1-5, Sections 1-5 are authoritative.
- Do not delete archived evidence unless a separate cleanup task explicitly requests deduplication.

### 一、项目总目标（作者视角）

这篇论文的核心目标已经明确为：在 **original-frontend 100维** 的可信输入链上，研究 stronger OOD（更强分布外）场景下异常检测的**低误报稳健性机制**。因此它不是“换一个 detector 看分数高低”的小模型对比，而是“协议强度 + 阈值机制 + 模型补充修正”的系统问题：先坐实 stronger OOD 的误报放大现象，再证明 calibration（校准）是主要杠杆，最后用 TailReg（尾部正则）给出模型层的定向补充改进。

---

### 二、实验总框架（总表）

| 模块 | 当前状态 | 论文作用 |
|---|---|---|
| 1) 历史链 detector 比较（clean115） | 已完成基础版 | 后端比较与历史对照 |
| 2) stronger OOD 主线现象（frontend100） | 已完成并稳定 | 主结果现象证据 |
| 3) calibration 机制实验 | 已完成并稳定 | 主线机制证据（核心） |
| 4) TailReg 方法实验 | 已完成阶段稳定版 | 模型层补充贡献 |
| 5) 扩展验证（更多 capture/能力约束/效率） | 进行中（已完成 Transformer fixed-vs-dA 自检） | A区完整性与泛化增强 |

---

### 三、当前已完成实验（按“支撑什么主张”整理）

#### A. 动机证据

**1) 已完成实验**
- `runs/ood_probe_stage1_2026-03-21`
- `runs/ood_probe_stage1_stability_2026-03-21`
- `runs/ood_probe_2026-03-21`

**2) 核心结果**
- 在 adapter/映射链路下观察到非常强的 OOD benign 误报（含接近灾难级现象）。

**3) 论文作用**
- 用于说明“开放世界误报失稳值得研究”，即问题发现与研究动机。

**4) 边界说明**
- 该链路存在 schema 映射与输入一致性问题，只能做动机证据，不能当正式主结论。

---

#### B. 输入链纠错证据

**1) 已完成实验**
- `runs/csv_input_clean_stage1_2026-03-23`（dirty116 -> clean115）
- `runs/kitsune_frontend_stage1_2026-03-22`（原版前端最小接入）

**2) 核心结果**
- 证实 `Mirai_dataset.csv / my_gold_mirai.csv` 的 116 维含索引样首列污染；清洗后得到 clean115。
- 原版前端链成功产出稳定 100维特征缓存（不再依赖 adapter）。

**3) 论文作用**
- 解决“输入空间不一致/污染”这一可信度前提问题，为主线结论提供可辩护输入基础。

**4) 边界说明**
- clean115 与 original-frontend 100 是两条并行输入轨道，不能混写成同一主线结果。

---

#### C. 历史链 detector 比较证据（clean115）

**1) 已完成实验**
- `runs/csv_input_clean_stage1_2026-03-23/trans115_min`
- `runs/csv_input_clean_stage1_2026-03-23/da115_min`
- 同配置 dirty116 对照：`trans116_dirty_min` / `da116_dirty_min`

**2) 核心结果**
- clean115 与 dirty116 的分数统计显著不同，确认索引列污染会扭曲 detector 行为。
- 在 clean115 下已完成 Transformer 与 dA 的可复现实验入口。

**3) 论文作用**
- 承担“历史链输入纠错后后端比较”的对照角色，支撑方法选择的历史合理性。

**4) 边界说明**
- 不用于 stronger OOD 主结论；该链路不等价于原版前端 100维主线。

---

#### D. stronger OOD 主线证据（frontend100）

**1) 已完成实验**
- 同 capture 分段（较弱 OOD）：`runs/frontend100_ood_stage1_2026-03-23`
- cross-capture stage1（更强 OOD）：`runs/frontend100_crosscapture_stage1_2026-03-25`
- cross-capture 多 seed 稳定：`runs/frontend100_crosscapture_stability_2026-03-25`

**2) 核心结果**
- 同 capture 分段下报警率低（Transformer 0.00610，dA 0.01085）。
- cross-capture 后 fixed 报警显著升高（stage1：Transformer 0.44175，dA 0.12580；多 seed 稳定维持高误报趋势）。

**3) 论文作用**
- 直接支撑“stronger OOD 问题真实存在”，并完成从弱协议到强协议的递进证据链。

**4) 边界说明**
- 当前 strongest 组合主要是 7-6 -> 4-1；跨更多 benign capture 的泛化还需补。

---

#### E. calibration 机制证据（主线核心）

**1) 已完成实验**
- 阈值基线：`runs/frontend100_crosscapture_threshold_2026-03-25`
- 校准扫描：`runs/frontend100_crosscapture_calibration_scan_2026-03-25`
- 关键设置多 seed 稳定：`runs/frontend100_crosscapture_calib_stability_local_2026-03-30`

**2) 核心结果**
- Fixed OOD alarm ratio（mean ± std）：  
  - transformer：`0.4548 ± 0.2769`  
  - da：`0.1378 ± 0.0050`
- Calibrated（budget=5000,target=1%）：  
  - transformer：`0.01549 ± 0.00068`  
  - da：`0.01516 ± 0.00003`
- gap：`0.316983 -> 0.000333`，缩小约 `99.9%`。

**3) 论文作用**
- 形成当前最强机制结论：**threshold layer 是主要杠杆**。

**4) 边界说明**
- 该结论成立于“无监督 OOD 校准可用”的设置；预算更小、场景更换时的鲁棒性仍需补。

---

#### F. TailReg 方法证据（阶段性方法贡献）

**1) 已完成实验**
- 方法首轮：`runs/frontend100_tailreg_stage1_2026-03-27`
- 超参扫描：`runs/frontend100_tailreg_hparam_scan_2026-03-28`
- 最优配置多 seed 稳定：`runs/frontend100_tailreg_bestcfg_stability_2026-03-28`

**2) 核心结果**
- 最优配置：`lambda=0.2, k=1.0, warmup=256, ema_alpha=0.01`
- fixed OOD alarm（mean ± std）：  
  - transformer：`0.4548 ± 0.2769`  
  - transformer_tailreg：`0.1393 ± 0.0911`  
  - da：`0.1378 ± 0.0050`
- calibrated 后 transformer 与 tailreg 基本重合（约 `0.01549`）。

**3) 论文作用**
- 支撑“模型层可补 fixed-threshold 脆弱性”的阶段性方法贡献。

**4) 边界说明**
- TailReg 不是 calibration 替代方案；当前不支持“全面提升 Transformer”的表述。

---

### 四、当前论文已经“写得动”的结论

#### 可写（阶段性稳定结论）
- stronger OOD（cross-capture）下误报问题真实存在。
- fixed threshold 会显著放大 detector 间误报差距。
- calibration 是当前误报控制的主要杠杆。
- TailReg 主要改善 fixed-threshold 下 Transformer 的尾部敏感性。

#### 不可写（禁止过度主张）
- “Transformer 全面优于 dA”。
- “TailReg 在所有评估条件下都优于 baseline 和 dA”。
- “calibration 已彻底解决开放世界低误报问题”。
- 把 clean115 或 adapter 链结果写成 stronger OOD 主结论。

---

### 五、后续必须完成的实验（优先级）

#### A. 必须做

1) **扩展 benign cross-capture 组合（至少再补 2 组）**  
- 为什么：当前 strongest 结论主要基于 7-6 -> 4-1，外推范围仍窄。  
- 支撑主张：stronger OOD 误报放大是否具有场景普适性。  
- 论文位置：Main Results + Robustness subsection。

2) **补“低误报不以漏检为代价”验证（恶意检测能力约束）**  
- 为什么：只看 benign 误报不足以完成检测器评价闭环。  
- 支撑主张：calibration/TailReg 降误报后仍保持检测能力（TPR/PR-AUC 不明显掉）。  
- 论文位置：Results 主表（误报-检出联合结果）。
- 2026-04-02 进展：已完成 `runs/frontend100_transformer_self_audit_2026-04-02/` 自检，确认 fixed 下 transformer 攻击分数存在更大阈下质量，当前差距更偏向“分布-阈值交互”而非实现口径错误。
- 2026-04-02 进展：已完成 `runs/frontend100_threshold_tradeoff_constrained_2026-04-02/`（score-only 阈值扫描 + detection-constrained 规则）。结论：naive calibration（budget=5000,target=1%）会将三种 detector 检出压到近0；引入 detection-floor 规则后可在约 7%~8% OOD 报警水平恢复约 50% 高纯攻击检出，显示 decision rule 层存在可用 operating region。
- 2026-04-03 进展：已完成 `runs/frontend100_constrained_rule_multiseed_2026-04-03/` 最小必要多 seed 复验（seed=101/202/303，detector=transformer/transformer_tailreg/da，规则=fixed/naive/det50/det60，附 alarm<=5% 弱基线）。结论：naive 在多 seed 下稳定近零检出；detection-floor 可稳定恢复到目标检出层，但 transformer 系列在 constrained 点的 OOD alarm 方差仍偏高，da 在 constrained 区域更稳。
- 2026-04-03 进展：已完成 `runs/frontend100_mae_v1_2026-04-03/`（Transformer-MAE-v1 单seed最小扫描，mask_ratio=0.3/0.4/0.5，比较 transformer/transformer_mae_v1/da，含 fixed+naive+det50）。结论：MAE 在 fixed 下可显著降低 OOD alarm（约 0.446 -> 约 0.071），但 attack detection 明显下降（约 0.634 -> 0.228~0.336）；m0.3 为当前检测保留最佳，MAE 单线尚不足反超 dA，建议下一步转入 MAE+TailReg 并做最小多 seed 复验。
- 2026-04-03 进展：已完成 `runs/frontend100_mae_tailreg_v1_2026-04-03/`（single-seed MAE+TailReg-v1，mask=0.3/0.4，比较 transformer/transformer_tailreg/transformer_mae_v1/transformer_mae_tailreg_v1/da，含 fixed+naive+det50）。结论：MAE+TailReg 在 mask=0.4 下相对 MAE-v1 可小幅修回 fixed detection（+0.0309）且基本保住低 alarm，但 detection 仍明显低于 transformer 与 dA，当前可作为“继续验证候选”而非已完成修复。
- 2026-04-04 进展：已完成 `runs/frontend100_uncertainty_v1_2026-04-04/`（Transformer-Uncertainty-v1，单seed，稳定版 `log_var` + clamp + Gaussian NLL，比较 `error-only / uncertainty-only / combined_nll`，并与 `transformer/da` 同口径对照，含 fixed+naive+det50）。结论：数值稳定性正常（NaN/Inf=0），但 `log_var` 下界触碰 clamp（-8.0）；`combined_nll` 固定阈值下可将 OOD alarm 降至约 0.0747，但 high-purity detection 仅约 0.4439；分离度上 `combined_nll` 略劣于 `error-only`（AUC 约 0.573 vs 0.602），表明 uncertainty v1 当前更像“降误报方向”而非直接提升检出。
- 2026-04-04 进展：已完成 `runs/frontend100_latent_contrastive_v1_2026-04-04/`（Transformer-LatentContrastive-v1，single-seed，margin∈{1,5}、lambda∈{0.1,0.5}，比较 transformer/transformer_tailreg/transformer_latent_contrastive_v1/da，含 fixed+naive+det50，附 latent distance 分析）。结论：fixed 下可见“提检出”趋势（最佳点 detection 最高达约 0.754），但伴随明显 alarm 反弹（最高约 0.55），尚未满足“提检出且不炸误报”；较稳健点（m=5, l=0.5）可将 alarm 压至约 0.094 但 detection 仍低于原始 transformer。说明该线已体现分离塑形潜力，但负样本构造与损失权重仍需继续收敛。
- 2026-04-04 进展：已完成 `runs/frontend100_latent_contrastive_compact_v2_2026-04-04/`（Transformer-LatentContrastive-Compact-v2，single-seed，固定 `m=5, lambda_margin=0.5`，扫描 `lambda_compact∈{0.01,0.05,0.1}`，引入 Cross-window Swap + EMA-detach center compactness + warm-up，比较 transformer/transformer_tailreg/latent_v1_best/latent_compact_v2/da，含 fixed+naive+det50 与 latent spread 分析）。结论：v2 在低 `lambda_compact` 下可进一步压低 fixed alarm（约 0.0747），但 detection 下降到约 0.494；高 `lambda_compact` 可把 detection 拉到约 0.679，但 alarm 反弹至约 0.501。当前尚未实现“比 v1 更优的 detection-alarm 同时改进”，但已明确 compactness 强度与 trade-off 的方向性约束。
- 2026-04-05 进展：已完成 `runs/frontend100_negative_semantics_ablation_2026-04-05/`（latent 主线 synthetic negative semantics ablation，single-seed，固定 `m=5, lambda_margin=0.5`，对 `cross-window swap / local permutation / mild spike` 做单类型与双类型组合消融，比较 transformer/transformer_tailreg/latent_v1_best/latent_compact_v2_lc0.01/da，含 fixed+naive+det50、四类分布图与 OOD-Negative overlap 指标）。结论：negative 语义对 detection-alarm trade-off 影响显著；`swap_only` 为当前最稳 utility 点（低于原始 transformer 的 alarm 但 detection 未超过 v1_best），`swap+spike` 检出最高但 alarm 明显反弹；目前未出现对 v1_best 的严格 fixed 支配配方，说明下一步应在最佳语义配方上做最小多 seed/轻量叠加，而非继续盲扫 compactness。
- 2026-04-05 进展：已完成 `runs/frontend100_negative_recipe_rescoring_2026-04-05/`（关键 latent recipe 严格离线重评分；不训练、不改 checkpoint；比较 RMSE / Latent-L2 / Latent-Cosine / Hybrid-L2 / Hybrid-Cosine，覆盖 fixed+naive+det50，并补 attack_high vs OOD_eval ROC-AUC、分布图与相关性分析）。结论：存在显著 scoring mismatch 迹象；`latent_swap_spike_mix` 在 RMSE 下呈“高检出高报警”，换到 latent/hybrid（当前以 `hybrid_cosine` 最优）后可在保持较高检出的同时明显降低报警，支持下一步以“最佳 recipe + 最佳 score”做最小多 seed 复验。
- 2026-04-05 进展：已完成 `runs/frontend100_latent_compact_v3_smoketest_2026-04-05/` 本地最小自检与 `runs/frontend100_latent_compact_v3_2026-04-05/` 超算协议准备（`compact_v3` 代码路径、`hybrid_cosine` 锁定评估、`lambda_compact={0.01,0.05,0.1,0.5}` 运行定义、`job.slurm`/`upload_bundle.zip`/`upload_manifest.txt`）。当前阻塞点为本 shell 环境对 `school-hpc` 非交互认证未打通，待凭据可用后执行正式 HPC 训练与打包回传。
- 2026-04-05 进展：已切换为本地正式运行 `runs/frontend100_latent_compact_v3_2026-04-05_local_full/`（single-seed，全量 `lambda_compact={0.01,0.05,0.1,0.5}`，`hybrid_cosine` 评估锁定），后台进程已启动，待跑完后回填最终结果与结论。
- 2026-04-05 进展：已完成 `runs/frontend100_latent_compact_v3_2026-04-05_local_live/`（Transformer-LatentContrastive-Compact-v3，single-seed，negative=`latent_swap_spike_mix`，`m=5.0`、`lambda_margin=0.5`，扫描 `lambda_compact={0.01,0.05,0.1,0.5}`，评估锁定 `hybrid_cosine`）。结论：`lc=0.01` 为 v3 最优，但相对 no-compact（latent_swap_spike_mix）在 fixed 点仍呈 `alarm +0.0115 / detection -0.0460`，未形成“降 alarm 且保 detection”的净外移；相对 transformer_tailreg 则表现为“更高 detection 但更高 alarm”。
- 2026-04-05 进展：已完成 `runs/frontend100_score_postprocessing_2026-04-05/`（锁定 `latent_swap_spike_mix` 做强化版离线 score-postprocessing；不训练、不改 checkpoint；在 `hybrid_cosine` 基础上比较 weighted hybrid、`log-transform + z-score`、`MAD` 稳健标准化，并重点检查 pure cosine，统计量严格来自 ID benign eval）。结论：评分器确实是当前主矛盾的一部分；最佳 fixed 点为 `log_weighted_z_rmse0.5_cos1.0`，相对默认 `hybrid_cosine` 将 OOD alarm 从约 `0.3261` 压到 `0.1857`，同时 high-purity detection 从约 `0.8955` 降到 `0.8233`。说明“降 RMSE 权重 + log 化”可明显改善 trade-off，但 pure cosine 虽 alarm 极低（约 `0.0368`）却 detection 明显不足（约 `0.4095`），MAD 版本也未优于 log 版本；当前更像 score-combination 问题而非纯模型崩坏，仍不足直接进入多 seed。
- 2026-04-06 进展：已完成 `runs/frontend100_locked_candidate_multiseed_2026-04-06/`（正式 seed=`101/202/303` 的最小必要多 seed 验证；锁定 recipe=`latent_swap_spike_mix`，比较旧评分 `hybrid_cosine_default` 与候选新评分 `log_weighted_z_rmse0.5_cos1.0`，并与 `transformer / transformer_tailreg / da` 官方口径对照，统一报告 fixed+naive+det50）。结论：新评分在多 seed 下**未稳定优于**同 recipe 旧评分器，fixed 均值仅从 `alarm 0.2220 -> 0.2161` 小幅下降，同时 `detection 0.6558 -> 0.6353` 回落；但相对 `transformer_tailreg`，该 latent 主候选在 fixed 下呈“更高检出、更高报警”，在 det50 下则能以更低 alarm 达到近同等 detection。相对 `da` 仍未进入全面可竞争区间（fixed 下同时更高 alarm、更低 detection），naive calibration 也继续在多 seed 下稳定塌检出。当前证据支持其作为“Transformer 家族的强候选之一”，但**不足以直接锁定为正式最强主候选**。
- 2026-04-06 进展：已完成 `runs/frontend100_mae_latent_v1_2026-04-06/`（Transformer-MAE-LatentContrastive-v1，single-seed，固定 negative=`latent_swap_spike_mix`、`m=5.0`、`lambda_margin=0.5`，扫描 `mask_ratio={0.3,0.4}`，primary score 回退为 `hybrid_cosine_default`，比较 transformer/transformer_tailreg/latent no-compact/mae+latent/da，统一报告 fixed+naive+det50，并附 trade-off、分布与局部 attack 响应图）。结论：融合线未实现预期的“降 alarm 且不明显伤 detection”；`mask=0.4` 为本轮较优点，fixed 下将 OOD alarm 从 no-compact 的约 `0.3261` 压到 `0.1201`，但 high-purity detection 同时从约 `0.8955` 降到 `0.5174`；`mask=0.3` 则同时表现为高报警（约 `0.4475`）与低检出（约 `0.5188`）。相对 `transformer_tailreg`，`mask=0.4` 虽 fixed alarm 更低，但 detection 更差，det50 下也未形成更优 trade-off；相对 `da` 则仅在 fixed alarm 上接近持平，但 detection 仍明显落后。当前证据**不支持**将 MAE+Latent 融合线直接推进为下一轮多 seed 主候选，更像是 MAE mask 机制削弱了 latent separation 与 attack 响应。
- 2026-04-06 进展：已完成 `runs/frontend100_latent_scorer_benchmark_2026-04-06/`（latent scorer benchmark 离线总决赛；不训练、不改 checkpoint；主 checkpoint 锁定 `latent_swap_spike_mix_no_compact`，比较旧单中心 hybrid、全局 single-center latent、双中心方向 `score_dir`、`LedoitWolf/OAS` 马氏距离及轻量 hybrid，统计与阈值严格只来自 ID benign train/calibration，补相关性矩阵与 benign latent 协方差主方向分析）。结论：当前瓶颈**不只是 scorer 粗糙**。旧 best scorer `log_weighted_z_rmse0.5_cos1.0_old` 仍是最佳 fixed 点（约 `alarm 0.1857 / det 0.8233`）；双中心方向 scorer 明显失败（`score_dir_cosine` fixed 仅约 `0.2734 / 0.0963`），说明“攻击原型方向打分”在当前表示上并未成立。`mahalanobis_ledoitwolf` 虽 fixed 下报警过高（约 `0.5843`），但 AUC 最强（约 `0.8991`），并在 det50 点把 OOD alarm 压到约 `0.0516`、同时保持约 `0.5015` detection，且 naive calibration 也不再完全塌到近零检出（约 `0.1175`）。这表明 covariance-aware scorer 有真实信号，但尚不足支持“只换 scorer 就能让当前 latent 线在 fixed 下反超 dA”；若继续推进，更值得押注 covariance-aware 方向，而不是直接进入双中心 prototype 训练线。

3) **在 stronger OOD 上补一个轻量传统 baseline（非重模型）**  
- 为什么：目前主比较集中在 Transformer 与 dA，需要最低限度外部参照。  
- 支撑主张：当前机制结论不是“双模型偶然”。  
- 论文位置：Results 对比段（附表或补充表）。

4) **补效率与代价（训练/推理/校准开销）**  
- 为什么：A区评审会问“效果是否靠高成本换来”。  
- 支撑主张：方案具备工程可行性（尤其校准预算/延迟）。  
- 论文位置：Discussion 或 Deployment Consideration。

---

#### B. 强烈建议做

1) **小预算 calibration 稳定性（多 seed，多组合）**  
- 为什么：当前最佳结果依赖 budget=5000，需评估资源敏感性。  
- 支撑主张：阈值层杠杆在受限预算下是否仍有效。  
- 论文位置：Calibration Analysis 扩展小节。

2) **TailReg 方差收敛与稳定性分析（固定最优附近）**  
- 为什么：TailReg 的 fixed 误报 std 仍明显高于 dA。  
- 支撑主张：TailReg 不仅降均值，还能降波动。  
- 论文位置：TailReg Results/Analysis。

3) **统计显著性/置信区间补充**  
- 为什么：主结论基于多 seed，加入显著性可提高审稿说服力。  
- 支撑主张：gap 收缩与 fixed 改善不是随机波动。  
- 论文位置：Results footnote 或附录统计说明。

---

#### C. 可选增强

1) **更强 OOD 强度梯度（跨更多设备/时段/协议域）**  
- 为什么：进一步放大挑战，验证结论边界。  
- 支撑主张：结论的适用范围与失效边界。  
- 论文位置：Discussion / Limitations。

2) **不确定性或分数校准高级方案（轻量）**  
- 为什么：在“阈值层主导”已成立后，可探索更稳阈值机制。  
- 支撑主张：机制深化，不改变主线框架。  
- 论文位置：Future Work 或附加实验。

3) **可解释性可视化增强（尾部样本画像）**  
- 为什么：帮助解释 TailReg 为什么主要作用于 fixed 场景。  
- 支撑主张：机制可解释性提升。  
- 论文位置：Analysis 图补充。

---

### 六、后续方法改进主线（修 Transformer 路线图）

基于现有证据，后续“修 Transformer”应坚持 **阈值层优先、模型层补充**，而不是回到大模型替换：

1) **目标 1：固定阈值下更低误报均值 + 更低方差**  
- 继续围绕 normal score tail 设计轻量约束（TailReg 家族），重点降低 seed 间波动。

2) **目标 2：小预算校准友好性（calibration efficiency）**  
- 让模型分数分布更“可校准”：在 500~2000 budget 下也能稳定逼近目标报警率。

3) **目标 3：误报-检出联合优化**  
- 任何降误报改动必须同时报告检测能力不塌陷（TPR/PR-AUC 或召回约束）。

4) **目标 4：保持工程成本可控**  
- 不引入重模型；优先维持与当前流程兼容的轻量正则/后处理改动。

建议的方法线表述：  
**“先用 calibration 解决主矛盾，再用 TailReg 类模型约束降低 fixed-threshold 脆弱性与波动，并验证在低预算校准与检测能力约束下仍成立。”**

---

### 七、论文-实验映射表

| 论文部分 | 对应实验模块 | 当前状态 |
|---|---|---|
| Introduction（stronger OOD 动机） | 动机证据 + stronger OOD 递进（A+D） | 已可写 |
| Data/Input Reliability | 输入链纠错（B） | 已可写 |
| Main Results（stronger OOD） | D（同capture->cross-capture->多seed） | 已可写 |
| Calibration Analysis | E（threshold baseline + scan + local stability） | 已可写（核心） |
| TailReg 方法与结果 | F（stage1 + hparam + bestcfg stability） | 已可写（阶段性） |
| Discussion / Limitations | 边界与待补实验（A/C/D/E/F 边界 + 五） | 已可写，待增强 |

---

### 八、作者执行建议（下一步最稳推进顺序）

建议按下面顺序推进，避免再次“实验散点化”：

1) **先补“必须做”中的 1 + 2**（更多 cross-capture + 检测能力约束）。  
2) 同步补 **必须做 4**（效率/代价），确保主线结果可工程化表达。  
3) 再做 **强烈建议 1**（小预算 calibration 稳定性），强化“阈值层主杠杆”的适用范围。  
4) 最后再决定是否推进 **强烈建议 2/可选增强**，用于冲击更高说服力版本。  

以后每个新实验立项前先回答三件事：  
- 它属于本地图哪一模块？  
- 它要支撑哪一句论文主张？  
- 它完成后进入正文哪一节？  

如果这三点回答不清，就先不做，避免新增“无法入稿的实验”。

- `frontend100_covariance_regularized_v1_2026-04-07`: Transformer-CovarianceRegularized-v1 single-seed minimal experiment; two-sided variance hinge + off-diagonal decorrelation, old-best and Mahalanobis scoring. Path: `runs/frontend100_covariance_regularized_v1_2026-04-07/`.
- `frontend100_mahalanobis_rescue_2026-04-07`: Mahalanobis epsilon-floor rescue offline rescoring; no retraining. Path: `runs/frontend100_mahalanobis_rescue_2026-04-07/`.

- `frontend100_covariance_regularized_v2_2026-04-07`: Transformer-CovarianceRegularized-v2 single-seed minimal experiment; EMA covariance, Cholesky diagonal-loading score proxy, tail-aligned loss. Path: `runs/frontend100_covariance_regularized_v2_2026-04-07/`.

- `frontend100_diagload_sweep_no_compact_2026-04-08`: Offline no-compact latent Mahalanobis diagonal-loading sweep; no retraining. Path: `runs/frontend100_diagload_sweep_no_compact_2026-04-08/`.

- `frontend100_diagload_overlap_analysis_2026-04-08`: Offline lost-attack vs false-alarm overlap analysis for no-compact latent diagload; no retraining. Path: `runs/frontend100_diagload_overlap_analysis_2026-04-08/`.

- `frontend100_diagload_gate_rescue_2026-04-08`: Offline two-threshold diagload+raw-Mahalanobis gate rescue for no-compact latent; no retraining. Path: `runs/frontend100_diagload_gate_rescue_2026-04-08/`.
- `research_log/a_tier_experiment_progress_log.md`: Living paper-level experiment logic log for A-tier direction; maintained across future experiments. Path: `runs/research_log/a_tier_experiment_progress_log.md`.
- `frontend100_diagload_gate_multiseed_2026-04-08`: Multi-seed offline validation of no-compact latent covariance gate (`diag_f0.5 q99 OR raw Mahalanobis high-tail`); no retraining. Path: `runs/frontend100_diagload_gate_multiseed_2026-04-08/`.
- `frontend100_latent_tail_seed_diagnostics_2026-04-08`: Offline latent covariance-tail seed diagnostics for no-compact latent gate instability; no retraining. Path: `runs/frontend100_latent_tail_seed_diagnostics_2026-04-08/`.
- `frontend100_conditional_gate_multiseed_2026-04-08`: Conditional covariance gate multi-seed offline validation (`diag_q99 OR (raw_q AND diag_guard_q)`); no retraining. Path: `runs/frontend100_conditional_gate_multiseed_2026-04-08/`.
- `frontend100_external_baselines_2026-04-08`: Minimal external baselines on original-frontend 100D stronger OOD (`IsolationForest`, `OneClassSVM`, `LOF`, RF mixed-attack upper-bound); path: `runs/frontend100_external_baselines_2026-04-08/`.
- `frontend100_temporal_frontend_v1_2026-04-08`: Transformer TemporalFrontend-v1 single-seed minimal experiment on stacked original 100D windows; path: `runs/frontend100_temporal_frontend_v1_2026-04-08/`.
- `frontend100_latent_seed_ensemble_2026-04-08`: Offline seed-ensemble test for latent covariance tail instability; no retraining; uses formal seeds 101/202/303 cached latents. Path: `runs/frontend100_latent_seed_ensemble_2026-04-08/`.
- `frontend100_latent_seed_ensemble_idq_sweep_2026-04-08`: ID-only fixed quantile sweep for latent seed-ensemble scalar scores; no retraining. Path: `runs/frontend100_latent_seed_ensemble_idq_sweep_2026-04-08/`.
- `frontend100_recurrent_deep_baselines_2026-04-08`: Multi-seed LSTM-AE/GRU-AE deep sequence baselines on stacked original 100D windows; path: `runs/frontend100_recurrent_deep_baselines_2026-04-08/`.
- `frontend100_latent_ensemble_cost_ablation_2026-04-08`: 1/2/3-seed ensemble cost-effect ablation for covariance gate; no retraining. Path: `runs/frontend100_latent_ensemble_cost_ablation_2026-04-08/`.
- `frontend100_final_candidate_audit_2026-04-08`: Final candidate audit for covariance-aware Transformer ensemble vs dA/recurrent/external baselines; includes main table, cost table, score distributions. Path: `runs/frontend100_final_candidate_audit_2026-04-08/`.
- `paper_handoffs/2026-04-08/a_tier_paper_readiness_handoff_2026-04-08.md`: paper-readiness consolidation of main candidate, supplement-worthy results, overclaim boundaries, figure/table checklist.

- `prism_handoffs/2026-04-08/prism_paper_revision_pack_2026-04-08`: Prism paper revision pack based on current draft PDF and final experimental evidence; includes Prism prompt, copied draft PDF, main tables, figures, evidence summaries, and zip bundle. Path: `runs/prism_handoffs/2026-04-08/prism_paper_revision_pack_2026-04-08/`.

- 
rontend100_deep_svdd_baseline_2026-04-09: Multi-seed Deep SVDD baseline on original-frontend 100D stronger OOD; ID-benign-only training with AE pretrain and center-distance scoring. Path: 
uns/frontend100_deep_svdd_baseline_2026-04-09/.
- `frontend100_additional_ood_setting_smoketest_2026-04-09_b`: Additional benign OOD setting evaluation (same-capture temporal split) for current Transformer ensemble candidate vs dA and family references; no retraining. Path: `runs/frontend100_additional_ood_setting_smoketest_2026-04-09_b/`.
- `frontend100_additional_ood_setting_smoketest_2026-04-09_c`: Additional benign OOD setting evaluation (same-capture temporal split) for current Transformer ensemble candidate vs dA and family references; no retraining. Path: `runs/frontend100_additional_ood_setting_smoketest_2026-04-09_c/`.
- `frontend100_runtime_benchmark_smoketest_2026-04-09_b`: Runtime/throughput benchmark for dA, single-seed Transformer latent gate, and 3-seed Transformer ensemble on the fixed stronger-OOD workload. Path: `runs/frontend100_runtime_benchmark_smoketest_2026-04-09_b/`.
- `frontend100_runtime_benchmark_2026-04-09`: Runtime/throughput benchmark for dA, single-seed Transformer latent gate, and 3-seed Transformer ensemble on the fixed stronger-OOD workload. Path: `runs/frontend100_runtime_benchmark_2026-04-09/`.

- `paper_handoffs/2026-04-09/paper_asset_manifest_2026-04-09.md`: Frozen main/supplement paper asset manifest after runtime and Deep SVDD updates; use this file to choose paper figures/tables without re-reading raw runs.
- `paper_handoffs/2026-04-09/paper_asset_manifest_2026-04-09.csv`: Structured asset inventory for main paper and supplement.
- `paper_handoffs/2026-04-09/PRISM_UPDATE_PROMPT_2026-04-09.md`: Direct Prism instruction for updating the draft using the latest frozen evidence.

---

### 九、外部改进建议分流（Gemini 报告处理原则）

来源：
- `D:\study\paper\anomaly_detection\paper04\论文实验改进与提升建议-gemini报告.pdf`

总原则：
- 该报告可作为“长期升级蓝图”，不能直接当作“当前论文全部待办清单”。
- 当前论文已经接近收口，后续只吸收那些**能显著增强现有主线可信度、但不会改写问题定义**的建议。
- 任何新实验若会把论文从“stronger OOD + covariance-aware operating region”改写成“多数据集/多模态/对抗鲁棒/图模型大综述”，则默认不进入当前主线。

#### A. 当前论文必须吸收的部分

1) **问题驱动而非唯指标驱动**
- 继续把主线写成：stronger OOD 暴露 benign OOD false alarm 瓶颈；Transformer 的问题是 latent covariance tail instability；最终 remedy 是 covariance-aware ensemble operating region。

2) **统计防御与部署防御**
- 继续补强 paired delta、seed-level scatter / CI、runtime/cost caveat。
- 所有 threshold 与 quantile 必须继续强调：只来自 ID benign，不使用 OOD/attack。

3) **baseline 完整性**
- Gemini 报告强调 baseline 现代性，这一点方向正确。
- 当前论文已用 `IF / OCSVM / LOF / LSTM-AE / GRU-AE / Deep SVDD / RF upper-bound` 基本补到足够水平；除非出现明显缺口，不再无边界扩 baseline 家族。

#### B. 可选补强，但必须服从主线

1) **额外 OOD / cross-capture setting**
- 只有在它能增强当前主线时才进入正文。
- 若结果只会削弱主结论，则保留为内部诊断或 supplement 备选，不强行写进主文。

2) **单个现代 deep anomaly baseline**
- 仅在发现审稿风险仍集中于“baseline 太旧”时再补一个同口径、低工程风险的现代 baseline。
- 当前已有 `Deep SVDD`，因此这项暂不升级为必须做。

#### C. 明确放入 Future Work，不进入当前论文主线

1) **多公开数据集全面迁移**
- 如 `BoT-IoT / TON-IoT / UNSW-NB15 / DataSense` 等。
- 这类工作量大，且会把当前论文从“固定 stronger OOD 设定下的机制论文”改成“新 benchmark / 大型泛化论文”。

2) **多模态 / foundation model / raw packet 级输入**
- 如原始流量、多模态融合、foundation model 方向。
- 这是下一阶段课题，不属于当前 paper 的必要收口内容。

3) **Mamba / FT-Transformer / GNN / 联邦框架 / 大型现代系统对照**
- 这类对照会大幅扩张工程面和问题边界，当前论文不吸收。

4) **对抗鲁棒性评测（FGSM/PGD/投毒/黑盒注入）**
- 这是一条新的安全问题线。
- 除非论文主问题改成“adaptive adversary robustness”，否则不进入当前主线。

5) **因果解释 / SHAP / root-cause attribution**
- 有价值，但属于下一篇或扩展工作。
- 当前论文主问题仍是 stricter evaluation + covariance-tail failure analysis + remedy。

#### D. 执行规则

以后若参考外部报告新增实验，先回答三件事：
- 它是否直接增强当前主主张？
- 它是否会改变当前论文的问题定义？
- 它是否会显著拖慢收口节奏？

若答案分别不是：
- **是 / 否 / 否**  
则默认不进入当前论文主线。

---

### 十、阶段重定性（2026-04-12）

#### A. 当前项目不再按“收口稿”理解

截至 2026-04-12，这个项目应被正式重定性为：

- **Phase 1 已完成**：我们已经完成问题定义、病理定位、主候选筛选、外部基线补充与一轮部署侧诊断。
- **当前进入 A 区增强阶段**：目标不再是“尽快把现稿修到能投”，而是把这条线扩成一篇真正具备顶级安全论文说服力的系统工作。

#### B. Phase 1 已经完成的核心资产

1. **问题定义已经成立**
- stronger benign OOD 下，fixed / ID-only operating region 会暴露出真实的 benign false alarm 瓶颈。
- 这不是单纯“谁的 AUC 更高”的问题，而是“在部署阈值下谁还能稳定工作”的问题。

2. **病理定位已经成立**
- Transformer 主问题不是完全没学到攻击分离，而是 **latent covariance tail instability**。
- covariance-aware scorer / ensemble / diagload 之所以有效，是因为它抓到了这部分几何病灶。

3. **主线证据已经成形**
- original-frontend 100D stronger OOD 主线已跑通。
- dA、TailReg、latent scorer benchmark、runtime/cost、recurrent deep baseline、Deep SVDD baseline 已形成一组可写入论文的正反证据。

4. **负结果资产已经成形**
- MAE、prototype、covreg v1/v2、离线 rescoring 补救、distillation v1 都是可用的失败诊断材料，不再视作“废实验”。

#### C. 当前距离 A 区仍缺的四个硬缺口

1. **更现代、更有代表性的 baseline 还不够完整**
2. **第二数据集 / 第二设置的跨环境自证还不够**
3. **adaptive adversary / adversarial robustness 评估缺失**
4. **deployability 闭环仍未真正完成，单模型替代 ensemble 尚未成立**

---

### 十一、2026-04-09 至 2026-04-11 新证据裁决

#### A. Deep SVDD baseline：现代 deep one-class 并不能自动解决 fixed 问题

对应运行：
- `runs/frontend100_deep_svdd_baseline_2026-04-09/`

结论：
- fixed q99 下，Deep SVDD 达到 `alarm=0.7034, det=0.9459`。
- 它证明“现代深度 one-class 模型可以把 detection 顶得很高，但在 stronger benign OOD 下 fixed false alarm 会严重失控”。
- 这条结果应保留在论文与地图中，作为“现代深度模型同样会在 fixed 部署区间翻车”的强证据。

裁决：
- **保留为关键外部 baseline 证据，不发展为主线方法。**

#### B. Ensemble Distillation v1：bulk score imitation 不足以复制 teacher 的 fixed 行为

对应运行：
- `runs/frontend100_ensemble_distillation_v1_2026-04-11/`

结论：
- teacher `q99`: `alarm=0.2307, det=0.9202`
- single-seed gate `q99`: `alarm=0.1129, det=0.7731`
- distilled head `q99`: `alarm=0.1064, det=0.4510`
- teacher-student Pearson 相关性虽高，但 fixed 检出明显崩塌。

解释：
- v1 学到了 bulk score 结构，但没有学到 teacher 在 benign tail / attack tail 上的关键 operating-point 行为。

裁决：
- **Distillation v1 不能晋升主候选。**
- 若继续此线，只能进入 **tail-aware distillation v2**，不能再做普通回归式蒸馏。

---

### 十二、A 区增强阶段总原则

#### A. 研究目标

后续实验不再服务“把当前论文补到差不多”，而是服务下面这件事：

- 把当前 stronger OOD + covariance-aware operating region 工作，升级为一篇兼具
  - **系统安全问题定义**
  - **更强实验完整性**
  - **对抗与部署视角**
  - **可被顶会审稿人正面评价的主创新闭环**
  的 A 区候选论文。

#### B. 顶级论文参照方式

以后参考顶级论文，不是机械模仿模型名，而是看它们在四个维度上如何建立说服力：

1. **问题是否真是安全问题，而不是单纯刷指标**
2. **评估是否覆盖真实部署痛点**
3. **是否考虑 adaptive adversary**
4. **是否有清楚的系统代价与边界说明**

#### C. 立项前强制三问

每个新实验立项前必须先回答：

1. 它补的是哪一个 A 区硬缺口？
2. 它支持的是哪一句最终论文主张？
3. 它失败后是否也能形成可写的负结果？

三问答不清，就先不做。

---

### 十三、Stop-Doing List（立即生效）

以下方向从现在起默认停止，不再作为主线优先级：

1. **停止继续开 MAE / prototype / compactness / covreg 新支线**
- 除非未来明确作为第二篇论文，否则不再投入主线算力。

2. **停止继续扫零散 scorer 小超参**
- 纯 scorer 微调已经不再是主矛盾。

3. **停止把“单模型翻盘审美”当成主目标**
- 单模型只在一个前提下继续：它能解决 deployability 闭环。

4. **停止为了“看起来像 A 区”而无边界扩 baseline**
- baseline 必须服务审稿风险，不是越多越好。

5. **停止把论文润色动作当成实验推进**
- 后续地图优先记录“增加硬实力”的实验，不记录纯文字修订。

---

### 十四、Tier 1：必须完成的实验包

这一层不做完，不讨论 A 区 ready。

#### A. baseline 补强包

目标：
- 用少量但真正有代表性的现代 baseline，封住“只在打旧模型”的审稿攻击。

最小方案：
1. **保留 dA**
- 作为高部署性经典 reference baseline。

2. **保留 Deep SVDD**
- 作为现代 deep one-class reference baseline。

3. **补一个现代 tabular/feature transformer 类 baseline**
- 优先：FT-Transformer 路线或同类低工程风险强 baseline。
- 原因：当前输入是 100D network statistics，这类 baseline 最对口。

4. **如工程可控，再补一个现代 SSL/novelty baseline**
- 仅在它能同协议复现且不会拖死项目时进入。

成功标准：
- 形成一张“dA / Deep SVDD / modern tabular baseline / 当前主系统”的统一比较表。
- 所有模型统一使用同一 stronger OOD 协议与同一 fixed 口径。

#### B. 第二数据集 / 第二环境自证包

目标：
- 证明当前主结论不是单一 100D 前端设置的偶然产物。

优先级：
1. **首选 BoT-IoT**
- 更贴近 IoT botnet 与网络流量异常检测，适合做最小迁移验证。

2. **备选 TON-IoT**
- 异构性更强，但工程成本也更高。

执行原则：
- 第一轮不复制所有主线实验。
- 只跑最小验证包：`dA + 当前 strongest candidate + 一个现代 baseline`。

成功标准：
- 趋势一致即可，不要求所有数值与主数据集完全对齐。
- 只要再次观察到 stronger benign OOD 下 fixed false alarm 的关键矛盾，就足以成立“跨环境复现”。

#### C. 对抗鲁棒性评估包

目标：
- 把系统从“自然漂移评估”提升到“面对 adaptive adversary 的安全评估”。

最小方案：
1. **白盒 FGSM**
2. **白盒 PGD**
3. **黑盒受限扰动 / padding-style 规避**

统一要求：
- 扰动必须施加在当前可操作的 feature space 上。
- 扰动预算、特征合法性、扰动方向必须显式记录。
- 必须同时报告 detection 下降与 false alarm 变化。

成功标准：
- 至少形成一组扰动强度曲线，比较
  - dA
  - single-seed Transformer
  - covariance-aware ensemble
- 若 ensemble 明显更稳，这将是 A 区级别的重要加分项。

#### D. deployability / cost 闭环包

目标：
- 回答“你的 strongest system 真实能不能落地”。

必须比较：
1. dA
2. single-seed Transformer
3. 3-seed covariance-aware ensemble
4. 若后续成功，再加 distilled single model

指标：
- 参数量
- CPU latency
- throughput
- memory footprint
- training cost

成功标准：
- 形成一张正式 deployment table。
- 若 ensemble 是最终 strongest candidate，也要能证明它的代价是可解释、可接受的。

---

### 十五、Tier 2：主创新收口线

当前只保留一条方法主线：

#### Tail-aware Ensemble Distillation v2

为什么是它：
- 现在 strongest system 依赖 3-seed ensemble。
- deployability 的核心矛盾不是“teacher 不强”，而是“单模型学不会 teacher 的 fixed tail 行为”。
- distillation v1 已经说明普通 bulk regression 不够。

v2 的唯一正确方向：
1. **benign high-tail weighting**
2. **synthetic negative / attack high-score weighting**
3. **pairwise ranking or margin alignment**
4. **operating-point imitation，而不是只回归平均分数**

成功标准：
- 单模型 fixed 区间进入 dA 竞争区，或明显接近 teacher 的 q995 工作区间。
- 至少满足下面之一：
  - `alarm <= 0.14` 且 `det >= 0.80`
  - 或在 alarm 不恶化的前提下，显著缩小 single-seed 与 teacher 的 fixed gap

止损标准：
- 若两周内仍然只能学到 bulk correlation，而 fixed detection 继续明显塌陷，则停止这一线。
- 停止后把 v1/v2 共同写成“为什么 ensemble 不易被廉价压缩”的部署讨论与负结果资产。

---

### 十六、Tier 3：未来高风险高收益探索

这些方向有价值，但不进入当前第一优先级：

1. hyperspherical / unit-sphere representation
2. information bottleneck / input bottleneck
3. orthogonal subspace disentanglement
4. root-cause attribution / causal explanation
5. multimodal / raw packet / foundation-style modeling

执行原则：
- 只有在 Tier 1 基本完成、Tier 2 明确止损或完成后，才允许重启。

---

### 十七、后续执行顺序（2026-04-12 起生效）

建议固定按下面顺序推进：

1. **baseline 补强包**
2. **第二数据集最小自证包**
3. **对抗鲁棒性评估包**
4. **deployability / cost 闭环包**
5. **tail-aware distillation v2**

原因：
- 前四项决定论文是否具备 A 区合法性。
- distillation v2 决定论文是否具备更漂亮的部署闭环。
- 如果前四项不做完，单做一个更优雅模型也不足以扭转整体说服力。

---

### 十八、Tier 1 执行设计（2026-04-12 版）

#### A. baseline 补强包：只补“现代且低工程风险”的强参考

##### 设计原则
- 不追逐大而全的 2025-2026 模型清单。
- 只补能够直接回应“你是不是只在打旧 baseline”的模型。
- 新 baseline 必须能沿用当前 `ID benign fit -> fixed / calibrated / constrained` 评估协议。

##### 具体配置
1. **FT-Transformer（主补强 baseline）**
- 定位：现代 tabular deep baseline。
- 理由：当前输入本质是 `100D network statistics`，FT-Transformer 与当前数据形态最匹配。
- 角色：证明在更现代的 tabular deep baseline 下，stronger OOD fixed 问题仍然真实存在。

2. **RTDL-ResNet / tabular ResNet（备选或配对 baseline）**
- 定位：与 FT-Transformer 同论文体系的强 MLP-like baseline。
- 理由：如果只补 FT-Transformer，审稿人仍可能认为“你在拿一个 Transformer 打另一个 Transformer”。
- 角色：提供一个非注意力、但同样现代且强的 tabular deep 参考。

3. **保留当前已有 baseline，不再扩大家族**
- `dA`
- `Deep SVDD`
- `IF / OCSVM / LOF`
- `LSTM-AE / GRU-AE`
- `RF upper-bound`

##### 执行顺序
1. 先补 `FT-Transformer`
2. 若复现稳定，再补 `RTDL-ResNet`
3. 若 FT 已足够回应 baseline 风险，则 ResNet 可降为可选

##### 产物要求
- `frontend100_modern_tabular_baselines_<date>/`
- 统一主表：`fixed / naive calibrated / det50 constrained`
- 统一成本表：参数量、训练时长、CPU 推理时延
- 统一 summary：只回答“现代 baseline 是否真正威胁当前主线”

##### 成功判据
- 即使现代 tabular baseline 比老浅层模型更强，也不能轻易同时做到：
  - `低 fixed alarm`
  - `高 high-purity detection`
- 只要它们没有压过当前主系统，就足以显著降低 baseline 风险。

#### B. 第二数据集 / 第二环境自证包：先做最小可复现，不做大迁移

##### 设计原则
- 目标是“趋势复现”，不是“完全复制当前主线的所有细节”。
- 这一步是外部自证，不是重建另一篇论文。
- 必须明确区分：
  - **主数据集主结论**
  - **外部公开数据集趋势验证**

##### 数据集优先级
1. **首选 BoT-IoT 5% flow CSV**
- 理由：官方提供 5% 子集，工程成本相对可控。
- 适合先验证“公开 IoT 数据下也会出现 benign OOD / fixed operating-point tension”。

2. **备选 TON-IoT network subset**
- 理由：异构性更强，更接近“更广泛的 IoT/IIoT 现实”。
- 风险：工程面更大，正常流量划分与协议重建更复杂。

##### 第二数据集上的问题定义
- 不强求复刻 `original-frontend 100D`
- 明确改写为：
  - **在公开 IoT flow benchmark 上，构造 analogous ID-train / OOD-benign / attack split，检验 fixed-threshold 部署张力是否复现**

##### 最小实验对象
1. `dA`
2. `current strongest candidate`（按可迁移实现决定是 single-seed covariance gate 还是 ensemble 版本）
3. `FT-Transformer`（若已完成）

##### 成功判据
- 只要再次观察到：
  - benign OOD 会显著放大 fixed false alarm
  - 协方差感知 / operating-region 方案相比 naive deep baseline 更稳
- 就算完成“外部趋势自证”。

##### 2026-04-17 进展
- 已完成 `runs/second_environment_botiot_feasibility_2026-04-17/` 本地 feasibility 节点，新增 `repo/ood/second_environment_feasibility.py` 用于 `BoT-IoT first` 入口核查。
- 当前结论不是模型或协议阻塞，而是**数据入口阻塞**：
  - `BoT-IoT` 官方项目页可访问，但官方 SharePoint 数据链接在当前环境下会落入 Microsoft 登录流程，不能直接当作无凭据自动下载源；
  - 本机 `D:\study` 下没有现成 `BoT-IoT` 本地副本；
  - 本机也没有 `TON-IoT` 本地副本，因此 fallback 目前同样不能立即开 smoke。
- 这一步的意义是把第二环境主线的真实起点固定下来：先拿到本地数据副本，再做最小 smoke，而不是在没有数据的情况下空转训练脚本或提前占用 HPC。

##### 2026-04-20 进展
- 已确认本地 `BoT-IoT 5%` 数据落地于 `D:\study\paper\anomaly_detection\paper04\worktrees\data\5%`。
- 已完成新一轮 feasibility：`runs/second_environment_botiot_feasibility_2026-04-20/`，结论从“数据缺失”更新为 `bot_iot_local_ready_for_smoke`。
- 已完成第一轮本地 second-environment smoke：`runs/second_environment_botiot_smoke_2026-04-20/`，并新增 `repo/ood/second_environment_botiot_smoke.py`。
- 当前 smoke 采用 `BoT-IoT` 10-best 训练/测试切分，numeric-only 快速评估，固定三类策略（`fixed_id_q99` / `naive_calibrated_budget500_target1pct` / `det_floor_50pct_min_alarm`）。
- 关键烟雾测试规模：
  - `id_benign_train=370`
  - `ood_benign_test=107`
  - `attack_test=100000`（本地 smoke 上限）
  - `feature_count=11`
- 该节点定位是“可运行性里程碑”，不是正式外部自证结论；主要风险是 benign 样本规模偏小，后续必须继续收敛成可辩护的正式 split 与正式对象对比包。
- 已完成 split 收敛判定节点：`runs/second_environment_botiot_split_gate_2026-04-20/`，新增 `repo/ood/second_environment_botiot_split_gate.py`。
- split gate 结论：
  - `BoT-IoT 5%` 在当前标签定义下 benign 总量仅 `477`（10-best train/test 为 `370/107`）；
  - 所有候选 split 都无法满足主线固定要求 `naive_calibrated_budget5000`（即 OOD benign 至少 `5000`）；
  - 因此 BoT-IoT 不能作为当前主线“正式第二环境闭环”，只能作为约束/负结果证据。
- 据此，第二环境正式包应按既定规则切换到 `TON-IoT` fallback 路线。
- 2026-04-20 fallback intake 进展：
  - 已新增 `repo/ood/second_environment_toniot_intake.py` 并执行 `runs/second_environment_toniot_intake_2026-04-20/`；
  - 对 `D:\study\paper\anomaly_detection\paper04\worktrees\data` 的扫描结果显示仅有 BoT-IoT 5%相关文件，TON-like candidate 数为 `0`；
  - 当前 verdict 为 `blocked_missing_toniot_files`，因此 TON 正式路线尚未进入 smoke 阶段。
- 2026-04-20 fallback intake 更新：
  - 已定位 TON 子目录 `D:\study\paper\anomaly_detection\paper04\worktrees\data\Train_Test_Network_dataset` 并重跑 intake（`runs/second_environment_toniot_intake_2026-04-20_b/`）；
  - 新 verdict 为 `toniot_intake_ready_for_smoke`，fallback 数据入口已打通。
- 已完成首个 TON 本地 smoke 节点：`runs/second_environment_toniot_smoke_2026-04-20/`，新增 `repo/ood/second_environment_toniot_smoke.py`。
- smoke 设置（fallback readiness 口径）：
  - 文件：`train_test_network.csv`
  - 标签：`label`（`0=normal`, `1=attack`）
  - split：ID benign `30000` / OOD benign `20000` / attack `100000`
  - policy：`fixed_id_q99`、`naive_calibrated_budget5000_target1pct`、`det_floor_50pct_min_alarm`
  - baseline：`IsolationForest`、`OneClassSVM`
- 当前 smoke 结果用于“fallback 跑通”而非正式结论；该 split 上 baseline 分离度偏弱（AUC < 0.5），后续正式包需进一步收敛 split/feature 设定并跑主线必选对象（`dA + strongest candidate + FT`）。
- 已完成 TON 正式前 precheck 节点：`runs/second_environment_toniot_precheck_2026-04-20/`，新增 `repo/ood/second_environment_toniot_precheck.py`。
- precheck 固化了 `split_manifest.json`（ID=30000 / OOD=20000 / attack=100000）并执行 score polarity gate。
- polarity gate 结论：
  - `isolation_forest` 采用 `raw_decision` 时 AUC `0.752998`（另一方向 `0.247002`）；
  - `oneclass_svm` 采用 `raw_decision` 时 AUC `0.816051`（另一方向 `0.183949`）；
  - 先前 smoke 的低 AUC 主要来自方向性口径错误，而非标签定义反转。
- 当前节点结论为 `polarity_checked_ready_for_formal_object_runs`，下一步可进入主线必选对象在 TON fallback 上的同口径正式运行准备。
- 已完成 TON 主线对象包本地预跑：`runs/second_environment_toniot_object_prerun_2026-04-20_b/`，新增 `repo/ood/second_environment_toniot_object_prerun.py`。
- 该节点在统一脚本下跑通了主线必选对象：
  - `dA`
  - `strongest_candidate_transformer_covreg_v2_seed101`
  - `ft_transformer_ae`
- 口径固定：读取 precheck `split_manifest.json`，执行同一 policy family（`fixed_id_q99` / `naive_calibrated_budget5000_target1pct` / `det_floor_50pct_min_alarm`），并做统一 polarity gate。
- 本地预跑规模（用于快速可比和稳定性检查）：
  - `ID train=8000`、`ID eval=4000`、`OOD eval=8000`、`attack eval=12000`。
- 当前结果说明：
  - 对象包可运行性已打通，但 fixed/naive operating point 下总体信号偏弱；
  - `strongest_candidate` 在本地预跑中出现一次 `NaN/Inf` execute-path 提示，需先做稳定性修复再考虑正式 HPC 提交。
- 2026-04-21 工程/口径排查进展：
  - 已升级 `repo/ood/second_environment_toniot_object_prerun.py`，新增非有限值计数、分数落盘与有限值硬校验；
  - 新增显式 gate 脚本 `repo/ood/second_environment_toniot_engineering_gate.py`；
  - 已完成工程 smoke：`runs/second_environment_toniot_object_prerun_2026-04-21_engineering_smoke/`；
  - gate 结论为 `engineering_gate_pass`，并生成：
    - `runs/second_environment_toniot_object_prerun_2026-04-21_engineering_smoke/engineering_gate/summary.md`
    - `runs/second_environment_toniot_object_prerun_2026-04-21_engineering_smoke/engineering_gate/engineering_gate_report.json`
  - 本轮排查结论：当前主要矛盾已从“工程/口径不确定”收敛为“方法在 second environment 下的性能问题”。
- 2026-04-21 同规模稳定复跑进展：
  - 已完成：`runs/second_environment_toniot_object_prerun_2026-04-21_stability/`；
  - 已执行 gate：`runs/second_environment_toniot_object_prerun_2026-04-21_stability/engineering_gate/`，结论 `engineering_gate_pass`；
  - 同规模对比 `..._2026-04-20_b` 显示：
    - `dA` 三策略指标完全复现（稳定锚点成立）；
    - `strongest_candidate` fixed 点仍弱（`attack_det=0.0033`）；
    - `ft_transformer_ae` fixed 点仍为 `attack_det=0.0000`；
    - `ft_transformer_ae` naive detection 有回升（`0.1260`），但 `id_alarm=0.3953`，不可作为可部署改进。
  - 当前可判定：TON second-environment 的主要问题是方法性能而非工程口径；在 fixed low-alarm operating point 下，主线对象尚未形成可辩护外部泛化优势。
- 2026-04-21 阈值敏感性与耦合验证进展：
  - 已新增并执行阈值敏感性审计：
    - `repo/ood/second_environment_toniot_threshold_sensitivity.py`
    - `runs/second_environment_toniot_threshold_sensitivity_2026-04-21/`
  - 结论：`FT fixed=0` 在当前 chosen orientation 下对 `>` / `>=` 都成立，不是简单比较符错误；ID tie 影响 alarm 计数，但不能解释 attack detection 为零。
  - 已新增并执行耦合探针：
    - `repo/ood/second_environment_toniot_coupling_probe.py`
    - `runs/second_environment_toniot_coupling_probe_2026-04-21/`
  - 探针结论（`dA + FT`, fixed split）：
    - `FT` 对表达方式高度敏感：`signed_log1p_zscore` 可把 fixed detection 从 `0` 拉到 `0.1452`，但 fixed OOD alarm 同时升到 `0.0990`；
    - 当前证据支持“模型 + 前端表达耦合”假设成立，但尚未得到可部署低告警 operating point。

#### C. 对抗鲁棒性评估包：分成神经白盒与统一黑盒两层

##### 设计原则
- 不做“图像领域式”的形式主义攻击演示。
- 必须围绕当前论文的真实判定规则：
  - fixed threshold
  - anomaly score crossing
  - deployment operating point

##### 攻击目标
- 把高纯攻击样本的异常分数拉低到 fixed threshold 以下，形成 evasion。

##### 评估分层
1. **R1：神经模型白盒一阶攻击**
- 对象：
  - single-seed Transformer latent gate
  - 3-seed Transformer ensemble
  - FT-Transformer / modern deep baseline（若已实现）
- 方法：
  - FGSM
  - PGD
- 输出：
  - `epsilon -> detection drop`
  - `epsilon -> evasion success rate`

2. **R2：统一黑盒约束攻击**
- 对象：
  - dA
  - single-seed Transformer
  - 3-seed ensemble
- 方法：
  - 坐标扰动 / sign-free search / padding-style constrained attack
- 输出：
  - 相同预算下，不同模型的规避难度比较

##### 特征合法性约束
- 非负特征保持非负
- 比率 / bounded 特征裁剪到观测范围
- 近似离散特征可选 round/clamp
- 扰动预算同时报告 `L_inf` 与平均相对改变量

##### 成功判据
- 只要能够展示：
  - naive/single deep model 更易被规避
  - covariance-aware ensemble 在相同预算下更稳
- 这一包就足够进入论文主文或强 supplement。

#### D. deployability / cost 闭环包：不再只说“3x cost”

##### 设计原则
- 部署讨论必须和 strongest candidate 绑定，不做泛泛而谈。
- 成本不是弱点隐藏区，而是系统论文必须正面给出的事实。

##### 必测对象
1. `dA`
2. `single-seed Transformer latent gate`
3. `3-seed covariance-aware ensemble`
4. `distillation v2`（若后续成功）

##### 必测指标
- CPU `ms/sample`
- throughput
- checkpoint size
- torch / non-torch parameter count
- peak memory（若可稳定测）
- 训练总时长
- 校准/阈值额外开销

##### 成功判据
- 形成一张能直接进入论文的 deployment table
- 对 strongest candidate 给出一句能站住的系统表述：
  - “higher-cost but still deployable remedy”
  - 或 “single-model distilled variant approaching teacher”

#### E. Tier 1 预计推进顺序

1. `FT-Transformer` 补强
2. 第二数据集最小 feasibility（BoT-IoT first）
3. 对抗协议实现与小规模白盒验证
4. 统一 deployment/cost 主表

说明：
- 若第 2 步 feasibility 显示 BoT-IoT 无法构造干净的 benign OOD split，则立即切 TON-IoT network subset，不在 BoT-IoT 上硬耗。
- 若第 1 步已经证明现代 baseline 风险显著下降，则不再继续扩大 baseline 家族。

#### F. A 线正式超算任务固定操作书（2026-04-17 固化）

##### 使用原则
- 先本地 smoke，再上超算。
- 超算只跑正式任务，不拿来修路径、修脚本、修 bundle。
- 适合上超算的任务包括：正式训练、多 seed、sweep、多配置、第二数据集或第二环境验证、正式 baseline 复现、长时间 CPU/GPU 作业。
- 不适合上超算的任务包括：本地 smoke、修路径、修脚本、修打包、离线 rescoring、画图、整理表格、是否值得正式跑仍未判断清楚的任务。

##### 命名规则
- 每次正式任务都必须新建 `run_tag`。
- `run_tag` 固定格式：`任务名_YYYY-MM-DD`。
- 正式 rerun 必须更换新日期。
- 本地正式目录固定为 `runs/<run_tag>/`。
- 远端项目根目录必须带日期，例如 `/public/home/<user>/work/<project-mainline>_YYYY-MM-DD`。
- 远端标准运行目录固定为 `<remote_project_root>/runs/<run_tag>/`。
- 回传包固定路径为 `package/<run_tag>_bundle.tar.gz`。

##### 提交前冻结清单
- 正式提交前，`runs/<run_tag>/` 下必须固定：
- `command.txt`
- `config.json`
- `run_spec.json`
- `job.slurm`
- `upload_bundle.tar.gz`
- 明确写定的回传 bundle 路径
- 如果这些还没冻结，就不允许上超算。

##### 固定执行流程
1. `ssh` 创建远端目录
2. `scp` 上传 `upload_bundle.tar.gz`
3. `ssh` 到远端解包
4. 在远端 `run_dir` 下执行 `sbatch job.slurm`
5. 自动建立 `latest_slurm.out`、`latest_slurm.err`、`last_job_id.txt`
6. 作业完成后 `scp` 拉回 `package/<run_tag>_bundle.tar.gz`
7. 本地解包并先检查结果完整性

##### 日志规则
- 远端 `run_dir` 下必须能直接打开：
- `latest_slurm.out`
- `latest_slurm.err`
- `stdout.log`
- `stderr.log`
- 默认通过远端文件树直接查看 `latest_slurm.out` / `latest_slurm.err`，不依赖每次手动 `tail -f`。
- 程序输出必须同时镜像到 Slurm 输出文件与 `stdout.log` / `stderr.log`。
- 提交后必须自动记录 `last_job_id.txt`、`latest_slurm.out`、`latest_slurm.err`。
- 建议额外生成 `job_info.json` 或同类 manifest，记录 `job_id`、`job_name`、`node_list`、`submit_dir`、`python_bin`、`stdout_log`、`stderr_log`。

##### `job.slurm` 最小元信息
- `job.slurm` 至少输出：
- `[start]`
- `[run_dir]`
- `[python]`
- `[command]`
- `[command_exit]`
- `[bundle]`
- `[finish]`
- 这样失败时可以快速区分：提交失败、环境失败、导入失败、路径失败、训练中途失败。

##### PowerShell 规则
- Windows PowerShell 下生成的 `ssh` / `scp` / `sbatch` 命令必须可直接复制执行。
- 不允许要求手动再改 quoting。
- 不允许生成会在 PowerShell 本地被错误展开变量的命令。

##### 回传包要求与回传后动作
- 回传包至少必须包含：
- `summary`
- `results`
- `diagnostics`
- `config`
- `stdout.log`
- `stderr.log`
- `job_info` 或同类运行 manifest
- 回传后固定顺序是：
1. 先检查 `summary`、`results`、`diagnostics`、logs 是否完整
2. 再更新 handoff
3. 再更新主线实验表
4. 最后 `commit + push`
- 如果结果无效，则必须记录失败原因、修复点、以及是否需要新日期 rerun。

##### 总原则
- 超算不是调试器。
- 超算只负责正式训练、正式验证、正式多 seed、正式 sweep。
- 凡是路径、脚本、bundle、命名、日志规则没有固定好的任务，一律先留在本地解决。
- `frontend100_timescale_tokenizer_v1_smoke_2026-04-13`: Frontend100 TimescaleTokenizer-v1 single-seed minimal experiment with header-aware 5x20 regrouping; path: `runs/frontend100_timescale_tokenizer_v1_smoke_2026-04-13/`.
- `frontend100_timescale_tokenizer_v1_1_smoke_2026-04-13`: Frontend100 TimescaleTokenizer-v1.1 single-seed scoring refinement with header-aware 5x20 regrouping and short-scale aware aggregations; path: `runs/frontend100_timescale_tokenizer_v1_1_smoke_2026-04-13/`.
- `frontend100_timescale_tokenizer_v1_2_smoke_2026-04-13`: Frontend100 TimescaleTokenizer-v1.2 adds scale-contrast scorers on top of header-aware 5x20 regrouping; path: `runs/frontend100_timescale_tokenizer_v1_2_smoke_2026-04-13/`.
- `frontend100_timescale_tokenizer_v1_3_smoke_2026-04-13`: Frontend100 TimescaleTokenizer-v1.3 adds short-focused weighted reconstruction training plus timescale-contrast scoring; path: `runs/frontend100_timescale_tokenizer_v1_3_smoke_2026-04-13/`.
- `frontend100_structured_frontend_v1_smoke_2026-04-13`: Frontend100 StructuredFrontend-v1 with 20 semantic tokens (`4 families x 5 scales`), dual family/scale embeddings, and contrast scorers on top of the original 100D source; local smoke indicates semantic re-layout of the same 100D is **not enough** by itself: best structured Transformer fixed point is about `0.0121 / 0.2464`, still below the older 5-token line and below flat-AE+contrast control. This supports the next step being **upstream frontend redesign**, not just richer reshaping of the same compressed 100D. Path: `runs/frontend100_structured_frontend_v1_smoke_2026-04-13/`.

---

### 八、Frontend-F2 受控重构入口（2026-04-13 固化）

#### 为什么现在切到 frontend

- `timescale_tokenizer` 与 `structured_frontend_v1` 已经把“同一份 original-frontend 100D 的后端重组空间”基本试穿。
- 结论一致：
  - scorer 可以改变 fixed trade-off，但不足以形成主线翻盘；
  - token 重组能产生局部机制信号，但仍明显打不过 dA，也未超过同源 flat 控制；
  - `4 families x 5 scales` 的 semantic token 化仍然不够，说明瓶颈不只在 token 排列，而在**上游表达生成时就被压扁了**。

#### 当前判断

- 当前 100D 对 dA 很友好，但对 Transformer 并不原生。
- 若继续在同一份 100D 上做更复杂后端重排，收益大概率已经接近上限。
- 因此下一阶段最值得投入的是：**沿着 Kitsune 原始提取链上移一层，做 upstream frontend expression 的受控重构。**

#### F2 的纪律

- 不引入外部黑盒 frontend 作为第一版主实现。
- 不破坏当前 `original-frontend 100D` 主线，必须保留 flat 100D 输出，确保历史实验与论文主干完全可复现。
- 第一轮只在 `kitsune_frontend_original_extract.py` 增加“结构化缓存输出”，不修改底层增量统计公式。

#### F2 第一轮目标

- 在原始 frontend 抽取阶段同步输出：
  - 原有 `100D flat npy`
  - `family x scale x stat-slot` 的结构化缓存
  - 语义 schema 与 token 映射元数据
- 先做本地 smoke，确认结构化缓存数值可逆、与 flat 100D 严格一致，再决定是否进入新的训练线。

#### 当前结论

- 如果要真正追求超越 dA 的新突破，最值得投入的是**重新构造前端表达**，而不是继续挤压同一份 100D 的重排空间。
- `Frontend-F2` 已成为下一阶段最合理的高价值探索入口。
- `kitsune_frontend_f2_smoke_2026-04-13`: Frontend-F2 extractor smoke. `kitsune_frontend_original_extract.py` now emits both flat 100D cache and structured semantic cache (`family_scale_tokens [N,4,5,7]`, `token_matrix [N,20,7]`, schema json). Local smoke on first 2000 packets passed with exact flat reconstruction (`max_abs_diff = 0.0`). Path: `runs/kitsune_frontend_f2_smoke_2026-04-13/`.
- `frontend_f2_crosscapture_source_smoke_2026-04-13`: Frontend-F2 source-prep smoke. Added `prepare_frontend_f2_crosscapture_sources.py` to slice structured caches into reusable ID/OOD source bundles while preserving flat csv/npy compatibility and shared schema. Smoke passed on same-source cache wiring. Path: `runs/frontend_f2_crosscapture_source_smoke_2026-04-13/`.
- `frontend100_modern_tabular_baselines_ft_smoke_2026-04-13`: FT-Transformer AE local smoke on original-frontend 100D stronger OOD. Single-seed (`101`) result confirms the modern baseline script works, but fixed performance remains weak (`q99 ~ 0.4935 / 0.8064`, `q995 ~ 0.2667 / 0.6970`), so this line does not threaten the current strongest paper candidate. Path: `runs/frontend100_modern_tabular_baselines_ft_smoke_2026-04-13/`.
- `frontend_f2_extract_id_7_6_2026-04-13`: Real benign ID Frontend-F2 extraction on `7-6` using the existing TSV from crosscapture stage1. Structured cache generated successfully with exact flat reconstruction. Path: `runs/frontend_f2_extract_id_7_6_2026-04-13/`.
- `frontend_f2_extract_ood_4_1_2026-04-13`: Real benign OOD Frontend-F2 extraction on `4-1` using the existing TSV from crosscapture stage1. Structured cache generated successfully with exact flat reconstruction. Path: `runs/frontend_f2_extract_ood_4_1_2026-04-13/`.
- `frontend_f2_extract_attack_34_1_2026-04-13`: Real attack Frontend-F2 extraction on `34-1` using the existing joint-eval TSV. Structured cache generated successfully with exact flat reconstruction, enabling aligned attack-side evaluation under the new frontend. Path: `runs/frontend_f2_extract_attack_34_1_2026-04-13/`.
- `frontend_f2_crosscapture_stage1_2026-04-13`: Real Frontend-F2 cross-capture source bundle built from `7-6` ID and `4-1` OOD structured caches; outputs both structured `.npz` sources and flat compatibility csv/npy. Path: `runs/frontend_f2_crosscapture_stage1_2026-04-13/`.
- `frontend_f2_attack_source_2026-04-13`: Real Frontend-F2 attack source bundle aligned to stage2 manifest (`use_first_n=10000`), producing reusable structured attack source plus flat compatibility outputs. Path: `runs/frontend_f2_attack_source_2026-04-13/`.
- `frontend_f2_structured_tokenizer_v1_smoke_2026-04-13`: First real-data smoke of `frontend_f2_structured_tokenizer_v1.py` using `7-6` ID, `4-1` OOD, and `34-1` attack structured caches, with token family/scale embeddings and short-vs-long contrast scoring. Local smoke runs successfully, but fixed detection remains low (best structured transformer about `0.0120 / 0.2043`), so Frontend-F2 is now a real exploratory branch but not yet a mainline challenger. Path: `runs/frontend_f2_structured_tokenizer_v1_smoke_2026-04-13/`.

- `frontend_f2_structured_tokenizer_v1_smoke_2026-04-13`: Frontend-F2 structured tokenizer v1 on real structured caches (`7-6` ID, `4-1` OOD, `34-1` attack), using token family/scale embeddings and short-vs-long contrast scoring; path: `runs/frontend_f2_structured_tokenizer_v1_smoke_2026-04-13/`.

- `frontend_f2_contrast_tokenizer_v1_smoke_2026-04-14`: Frontend-F2 contrast-token v1 derives short-vs-long anomaly-increment tokens directly from structured caches and evaluates transformer/token-MLP backends on real `7-6/4-1/34-1` data; path: `runs/frontend_f2_contrast_tokenizer_v1_smoke_2026-04-14/`.

---

### 九、2026-04-22 主线状态修订：A 线失败封口与 original100 few-shot 官方控制组

#### A 线 second-environment 失败封口包

状态：
- `BoT-IoT` 与 `TON-IoT` second-environment 不再作为继续扩跑、继续优化、继续救活的主线活线。
- 该线正式沉淀为：
- negative evidence
- limitation
- external-validity boundary
- second-environment 当前不进入主证据。

裁决依据：
- `BoT-IoT`：当前本地可用 benign 支撑不足，无法满足 formal mainline split/calibration/eval 口径；因此不进入正式主证据。
- `TON-IoT`：工程门、split 门、finite 值门已基本排除，但模型结果仍不支持主线：
- `dA` fixed reference: `AUC=0.679894`, `attack_det=0.076667`
- `strongest_candidate_transformer_covreg_v2_seed101` fixed: `AUC=0.690065`, `attack_det=0.003333`
- `ft_transformer_ae` fixed: `AUC=0.570755`, `attack_det=0.000000`
- threshold-sensitivity probe 证明 `FT fixed=0` 不是简单 `>` / `>=` 或方向选择 bug。
- coupling probe 证明模型 + 表达耦合存在，但当前没有形成可部署 low-alarm operating point。

写作边界：
- 可以写成当前 protocol 的外部有效性边界与限制。
- 不应写成主线正证据。
- 不再安排 second-environment 扩跑或调参，除非未来明确开启新日期、新 protocol。

#### original100 few-shot official control package

Run:
- script: `repo/ood/original100_fewshot_official_control.py`
- run path: `runs/original100_fewshot_official_control_2026-04-22/`
- task type: few-shot / supervised target-aligned detector
- representation: original frontend flat 100D
- model: L2 `LogisticRegression`, `class_weight=balanced`, `C=1.0`

Protocol:
- negatives = ID benign + OOD benign
- positives = stage2 high-purity attack
- positive budgets = `16`, `32`
- positive sampling seeds = `42,43,44,45,46`
- final OOD eval does not participate in threshold selection
- operating points:
- `fixed_id_calib_q99`
- `guarded_id_calib_and_ood_val_target1pct`
- outputs include mean/min/max summaries

Package integrity:
- `command.txt`, `config.json`, `run_spec.json`, `official_control_manifest.json`, `diagnostics.json`, `results.csv`, summary/focus CSVs, `summary.md`, `stdout.log`, `stderr.log` all present locally.
- `results.csv` has 22 rows.
- aggregate summary has 6 rows.

Official control results:
- `original100_fewshot_logistic`, 16-shot, fixed:
- `AUC mean/min/max = 0.990672 / 0.958007 / 0.999974`
- `OOD alarm mean/min/max = 0.004500 / 0.001200 / 0.009500`
- `attack det mean/min/max = 0.967564 / 0.914182 / 0.999273`
- `feasible_rate = 1.000000`
- `original100_fewshot_logistic`, 16-shot, guarded:
- `AUC mean/min/max = 0.990672 / 0.958007 / 0.999974`
- `OOD alarm mean/min/max = 0.004440 / 0.001200 / 0.009200`
- `attack det mean/min/max = 0.967564 / 0.914182 / 0.999273`
- `feasible_rate = 1.000000`
- `original100_fewshot_logistic`, 32-shot, fixed:
- `AUC mean/min/max = 0.984615 / 0.967632 / 0.999910`
- `OOD alarm mean/min/max = 0.006520 / 0.003600 / 0.009800`
- `attack det mean/min/max = 0.940655 / 0.920727 / 0.999273`
- `feasible_rate = 1.000000`
- `original100_fewshot_logistic`, 32-shot, guarded:
- `AUC mean/min/max = 0.984615 / 0.967632 / 0.999910`
- `OOD alarm mean/min/max = 0.006520 / 0.003600 / 0.009800`
- `attack det mean/min/max = 0.940655 / 0.920727 / 0.999273`
- `feasible_rate = 1.000000`

Reference baseline boundary:
- `da_unsupervised_score_seed42` remains a reference baseline only, not the same label-information setting.
- fixed ID q99: `AUC=0.806365`, `OOD alarm=0.128600`, `attack det=0.686545`
- guarded: `AUC=0.806365`, `OOD alarm=0.010800`, `attack det=0.002909`

Interpretation boundary:
- `original100_fewshot_logistic` is now the mainline official control for the v7 target-aligned methodology port.
- This package does not claim source-rich superiority and does not replace the A-line second-environment failure closure.

---

### 十、2026-04-23 主线-frontend-f2 叙事汇合地图

#### 汇合性质

这次汇合是论文叙事、证据结构和实验资产的汇合，不是直接把 frontend-f2 旧 tokenizer / AE 代码并入主线。

主线职责保持：
- 主线仍维护 `runs/mainline_docs/mainline_handoff.md` 与 `runs/mainline_docs/mainline_experiment_map.md` 两份活文档。
- A 线 second-environment 继续保持失败封口状态，不再扩跑救线。
- original100 few-shot official control 是主线官方控制组。
- frontend-f2 的价值重新定位为 source-rich 表示的 hard-holdout robustness 与 auditability 资产，而不是“无监督前端重构已经全面翻盘”。

#### 新论文中心

推荐中心主张：
- 严格 low-OOD-alarm operating region 揭示了传统 unsupervised detector 的 detection collapse。
- 少量 high-purity attack positives 形成的 target-aligned linear head 可以显著恢复低误报区间的检测能力。
- original100 few-shot control 证明主要杠杆是 target alignment。
- source-rich 的独特价值应写成困难 holdout 下的稳健性、可审计性和机制解释，而不是平均性能全面压过 original100。

#### 证据路由表

| 证据块 | 当前角色 | 论文去向 | 边界 |
|---|---|---|---|
| stronger benign OOD + calibration 旧主线 | 问题定义与机制背景 | 主文 | 用来证明 low-OOD-alarm 区间才是真部署痛点 |
| dA / Deep SVDD / FT 等 baseline 失败模式 | unsupervised collapse 证据 | 主文或主附录 | 不写成“模型弱”，写成 objective 与 deployment target 失配 |
| A 线 BoT-IoT / TON-IoT | negative evidence / limitation / external-validity boundary | limitation 或附录 | 不进入正向主证据，不再扩跑 |
| original100 few-shot logistic | official control | 主文或主附录核心表 | 证明 target alignment 是主要杠杆 |
| frontend-f2 v7.2 / v7.3 few-shot | target-aligned positive evidence | 主文或主附录 | 需和 original100 同口径比较，不能单独宣称 source-rich 胜出 |
| frontend-f2 v7.4 paired holdout | 待核验的 hard-holdout fairness 证据 | 待确认后决定主文/附录 | 当前主线不得未核验就写成稳定结论 |
| frontend-f2 早期 tokenizer / AE / temporal / contrast 负结果 | 机制诊断资产 | 附录或方法动机 | 支持“不是没信号，而是 objective 不对齐” |
| source-rich feature/family/scale 分析 | auditability 资产 | 主文解释图或附录 | 卖点是可审计与困难窗口解释，不是平均性能英雄 |

#### 主文叙事骨架

建议主文顺序：
1. 定义问题：开放世界 stronger benign OOD 下，AUC 不足以代表部署可用性，关键是 low-OOD-alarm operating region。
2. 展示失败机制：传统 unsupervised detector 在低误报区间出现 detection collapse。
3. 引入 target alignment：few-shot supervised linear head 使用极少量 high-purity attack positives 修正目标错配。
4. 固定公平控制：original100 few-shot official control 与 dA reference baseline 给出标签信息边界。
5. 接入 frontend-f2：source-rich 不是平均性能主英雄，而是 hard-holdout robustness 与 auditability 的表示层资产。
6. 明确限制：second-environment 当前封口为 external-validity boundary，后续外部验证需要新 protocol。

#### 后续最小补强包

优先级 1：
- 核验 frontend-f2 v7.4 paired holdout fairness 是否已经稳定。
- 若稳定，把它登记为 source-rich hard-holdout robustness 证据。
- 若不稳定，只保留为边界和负结果，不强行汇入正证据。

优先级 2：
- 为 original100 few-shot official control 生成 paper-facing 表格和 operating-point 图。
- 表格必须保留 16/32-shot、multi-seed mean/min/max、fixed 与 guarded 两个 operating points。

优先级 3：
- 做 source-rich auditability 资产整理。
- 至少包括 feature/family/scale 级别解释、困难 holdout 案例、与 original100 的边界说明。

优先级 4：
- 整理标签代价和部署成本。
- 说明 high-purity attack positives 的获取预算、训练成本、推理成本。

#### 当前禁止推进项

- 不再继续 second-environment 扩跑、调参或救线。
- 不再新增无监督 tokenizer / AE patch 作为主线中心。
- 不再写 `source_rich` 平均性能全面优于 `original100`。
- 不再把 dA reference 与 few-shot supervised detector 写成同标签信息口径的公平胜负。
- 不在未核验 v7.4 前把 paired holdout 写成主线稳定结论。

#### 当前决策

主线与 frontend-f2 可以汇合，但汇合后的主张应是：
- paper center = low-OOD-alarm detection collapse + few-shot target alignment。
- official control = original100 few-shot logistic。
- source-rich role = hard-holdout robustness + auditability。
- closed limitation = A-line second-environment failure package。

## 6. Problem-Driven Reframing and Evidence Roadmap

Date: 2026-05-17

This section records the post-survey reframing from few-shot LR repair to **Low-Alert Intrusion Detection under Benign-OOD Drift**. The current recommended route is **Problem B / balanced hybrid paper**.

### 6.1 New Evidence Map

| Evidence level | Items | Paper role |
|---|---|---|
| A-level | low-OOD collapse; fixed OOD guard; original100 fixed guard / LOW-GUARD-minimal; clean support and threshold provenance | Can support main claims if harder-holdout and baseline gaps are handled. |
| B-level | source_rich useful but unstable; Transformer hidden integration feasible; mode-gated arbitration as deployment policy; bounded review as safety net | Auxiliary and system-context evidence. |
| C-level / negative | scalar score fusion; hidden-only failure; source_rich as stable main gain | Boundary evidence and appendix / negative-result record. |
| Missing | formal harder holdout; second environment; DevNet / Deep SAD / RoSAS-like baselines; OOD target sensitivity; shot sensitivity; runtime / efficiency; threshold transfer | Must be addressed before strong submission claims. |

### 6.2 Experiment Priority

| Priority | Experiments | Purpose |
|---|---|---|
| S-level | formal harder holdout validation; few-shot anomaly baseline comparison; OOD target sensitivity 0.5 / 1 / 2; shot sensitivity 8 / 16 / 32 / 64; threshold/provenance audit preserved | Defend the main problem definition and prevent reviewer collapse into "cost-sensitive LR on one split." |
| A-level | second environment pilot; modern unsupervised baselines; efficiency / runtime; calibration transfer | Strengthen external validity and deployment credibility. |
| B-level | adapter upgrade such as margin-GDA / deviation-GDA / prototype-GDA; Transformer hidden improvement; explainability / feature attribution | Only after S-level gaps are addressed. |
| C-level | further source_rich tinkering as main route; large neural model upgrade before generalization evidence; more score-level fusion | Do not prioritize as mainline. |

### 6.3 Current Stop Rule

- Do not continue source_rich as the main route.
- Do not continue Transformer hidden as the main route.
- Do not optimize review queue as an added attack-detection contribution.
- Do not perform complex adapter upgrades before harder-holdout and baseline recovery.
- Do not reopen score-level fusion unless a new, pre-registered reason exists.

### 6.4 Current Naming

Use `LOW-GUARD-minimal` for the current implementation:

`original100 representation + fixed OOD-benign guard + few-shot LR adapter`.

Avoid writing that full GDA, detector-agnostic adaptation, source_rich superiority, or Transformer-hidden improvement has already been proven.

### 6.5 Issue26a Within-Dataset Temporal Feasibility Inventory

Date: 2026-05-22

Run:
- `runs/issue26a_within_dataset_temporal_validation_for_enhanced_lowguard_top64_2026-05-22/`

Scope:
- within-dataset temporal / data-scale feasibility;
- evidence inventory;
- temporal candidate matrix;
- leakage audit;
- issue26b planning.

Not in scope:
- formal temporal validation;
- second environment;
- topK/support/adapter/threshold tuning;
- dA or Transformer training;
- routing, promotion, or frontend-f2 reopening.

Key result:
- issue25c remains `strong_baseline_positive` for frozen Enhanced LOW-GUARD+ top64.
- No clean P0/P1 temporal candidate with low leakage risk was found.
- `chrono_early_train_late_eval` is the best partial candidate, but it overlaps issue23/25c locked eval bins `6/7/8`; it cannot be written as clean new temporal proof without metadata recovery and purge/embargo design.
- Existing `primary_lowood`, `holdout_bin_2`, and `chrono_late_train_early_eval` remain consistency/discovery evidence.
- Existing locked bins `5/6/7/8` remain same-dataset locked evidence, but repeated locked-bin analysis risk must be stated.
- No optional minimal temporal validation was run.

Current claim boundary:
- Allowed: issue26a inventories within-dataset temporal/data-scale evidence and audits leakage risk.
- Not allowed: issue26a proves temporal generalization, proves external generalization, or replaces second-environment validation.

Next:
- Unique next action: `issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22`.
- Do local metadata recovery and split-manifest construction first.
- Use Slurm only after local smoke passes and the formal temporal protocol is frozen.
- Keep second-environment validation as issue27-level work.

### 6.6 Issue26b Split Metadata Recovery And Temporal Asset Build

Date: 2026-05-22

Run:
- `runs/issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22/`

Scope:
- split metadata recovery;
- known-setting provenance reconstruction;
- temporal candidate rebuild;
- purge/embargo planning;
- metadata-only split smoke.

Not in scope:
- formal temporal validation;
- second environment;
- new method development;
- topK/support/adapter/threshold tuning;
- dA or Transformer training;
- routing, promotion, or frontend-f2 reopening.

Key result:
- Bin-level provenance was recovered for primary, discovery, locked, and partial temporal settings.
- Support provenance and threshold provenance remain clean in the inspected artifacts: support selection does not use attack eval / final OOD eval, and threshold selection uses ID calibration + OOD validation.
- Raw timestamp, packet-order, capture/session boundary, window_start/window_end, and bin-to-clock-time metadata were not recovered.
- No clean formal temporal candidate is ready.
- `earlier-to-later` is still the best partial temporal direction, but it overlaps issue23/25c locked eval bins `6/7/8` and needs purge/embargo metadata before any formal claim.
- No formal validation result was produced.

Current claim boundary:
- Allowed: issue26b documents metadata/provenance recovery and identifies the concrete asset gap blocking clean temporal validation.
- Not allowed: issue26b proves temporal generalization, completes formal temporal validation, or replaces second-environment evidence.

Next:
- Unique next action: `issue26c_temporal_metadata_recovery_followup_or_second_environment_feasibility`.
- Recover raw temporal metadata or unused future-window assets before any formal issue26c validation.
- If raw metadata remains unavailable, avoid dressing locked-bin reuse as temporal proof and move toward a scoped second-environment feasibility path.

### 6.7 Issue27a Deployment Feasibility And Guarded Training Protocol Audit

Date: 2026-05-22

Run:
- `runs/issue27a_deployment_feasibility_and_guarded_training_protocol_audit_2026-05-22/`

Scope:
- deployment assumption inventory;
- guarded training pipeline design;
- alert-budget workload interpretation;
- label-budget and contamination robustness plan;
- LR-vs-framework positioning;
- deployment reviewer defense.

Not in scope:
- model training;
- temporal validation;
- cross-dataset validation;
- topK/support/adapter/threshold tuning;
- autonomous online learning;
- manuscript edit.

Key result:
- Primary verdict: `deployment_protocol_plausible_needs_robustness_simulation`.
- Secondary verdict: `lowguard_should_be_framed_as_guarded_adaptation_protocol`.
- LOW-GUARD is better framed as a guarded few-shot adaptation protocol, while the current LR head is `LOW-GUARD-LR`, a minimal deployable instance.
- Current main method locked OOD max is `0.0045`, about 45 alarms per 10k OOD events, under the official 1% low-alert budget.
- DevNet-like and random32 are detection-competitive in places but exceed 1% locked OOD alarm, making them deployment-risky under the official low-alert constraint.
- Deployment assumptions are plausible only with explicit support provenance, benign-OOD guard provenance, delayed confirmation, no self-training, and rollback controls.

Current claim boundary:
- Allowed: LOW-GUARD protocol is deployment-plausible under explicit support/guard assumptions and needs robustness simulation.
- Not allowed: live SOC deployment is proven, 32 supports are always available, OOD benign labels are always clean, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27b_deployment_robustness_simulation_for_lowguard_top64_2026-05-22`.
- Run shot sensitivity, support-noise, OOD contamination, support-source, update, and shadow-mode workload simulations before adapter upgrades.

### 6.8 Issue27b Guarded Protocol Transfer And Adapter Recovery

Date: 2026-05-26

Run:
- `runs/issue27b_guarded_protocol_transfer_and_adapter_recovery_2026-05-26/`

Scope:
- frozen locked-bin protocol-transfer matrix;
- LR / DevNet-like / HistGB / DeepSAD-like / Prototype-metric / RFF adapter-head comparison;
- P0/P1/P2/P3 training-guard and threshold-guard ablation;
- LOW-GUARD++ candidate check;
- final-eval leakage audit through selection trace.

Not in scope:
- temporal validation;
- cross-dataset validation;
- topK/support/adapter/threshold tuning beyond the pre-registered head configs;
- dA or Transformer training;
- deployment robustness simulation;
- manuscript edit.

Key result:
- Primary verdict: `nonlinear_detection_gain_not_low_alert_feasible`.
- LOW-GUARD-LR P3 reproduces issue25c exactly: locked mean/min/OOD max `0.949705 / 0.882629 / 0.004500`.
- Best non-LR full LOW-GUARD head: DevNet-like MLP with locked mean/min/OOD max `0.947497 / 0.895305 / 0.010100`, feasible rate `0.975000`.
- No LOW-GUARD++ candidate was found.
- DevNet-like is near LR on detection and stronger on locked min, but its OOD max remains just above the official 1% budget.
- HistGB, DeepSAD-like, Prototype/metric LR, and RFF Logistic do not threaten LOW-GUARD-LR as the current feasible minimal instance.

Current claim boundary:
- Allowed: LOW-GUARD-LR remains the strongest feasible minimal instance under the locked low-alert protocol.
- Allowed: nonlinear heads can be detection-competitive but are not automatically low-alert feasible.
- Not allowed: LOW-GUARD transfers cleanly to all adapters, LOW-GUARD++ is proven, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27c_deployment_robustness_simulation_for_lowguard_lr`.
- Run shot sensitivity, support-noise, OOD-benign contamination, support-source, and shadow-mode workload simulations.
- Do not widen the adapter space unless deployment robustness exposes a concrete failure mode.

### 6.9 Issue27c LOW-GUARD Mechanism Falsification And Head Specificity Audit

Date: 2026-05-26

Run:
- `runs/issue27c_lowguard_mechanism_falsification_and_head_specificity_audit_2026-05-26/`

Scope:
- LR rescue mechanism audit;
- head-specificity audit;
- score distribution and OOD-tail audit;
- stricter OOD validation target curve;
- top64 linearity / representation-bias audit;
- implementation-gap audit for proxy heads.

Not in scope:
- deployment robustness simulation;
- temporal validation;
- cross-dataset validation;
- new method development;
- topK/support/threshold tuning;
- manuscript edit.

Key result:
- Primary verdict: `lowguard_lr_success_mechanistically_supported`.
- Secondary verdicts: `representation_linearization_explains_lr_advantage`, `lowguard_effect_head_specific_lr_only_so_far`, `non_lr_results_inconclusive_due_to_proxy_implementation`.
- LR recovery is mechanistically interpretable: raw LR has high detection but severe OOD alarm; threshold-only LR collapses detection; OOD-guarded training preserves detection and suppresses OOD tail; full LOW-GUARD adds validation safety.
- Non-LR heads did receive OOD_train guard, so the near-miss/failure is not explained by missing guard exposure.
- DevNet-like remains detection-competitive but has insufficient OOD-tail safety margin.
- DeepSAD-like and DevNet-like are proxy implementations; do not write their failure as full method defeat.
- No direct implementation bug or final-eval leakage was found.

Current claim boundary:
- Allowed: LOW-GUARD-LR is the strongest feasible demonstrated instance and has a supported rescue mechanism.
- Allowed: broader head-agnostic transfer is not established.
- Not allowed: LOW-GUARD works for all heads, nonlinear adapters are useless, DevNet/DeepSAD are defeated, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27d_bounded_representation_and_objective_falsification_for_lowguard_lr_specificity`.
- Run a small original100-vs-top64 control over LR / DevNet-like / HistGB before returning to deployment robustness.
- Keep the matrix bounded and do not open a model zoo.

### 6.10 Issue27d LOW-GUARD Adapter Interface And Model-Specific Objective Smoke

Date: 2026-05-26

Run:
- `runs/issue27d_lowguard_adapter_interface_and_model_specific_objectives_smoke_2026-05-26/`

Scope:
- common LOW-GUARD adapter interface;
- Stage A interface, score-direction, data-usage, and leakage checks;
- bounded model-specific-lite objective smoke;
- representation control: `source_rich_top64` vs `original100`;
- locked bins `5/6/7/8`, seeds `42/43/44`.

Not in scope:
- formal issue27e validation;
- temporal validation;
- cross-dataset validation;
- deployment robustness simulation;
- dA or Transformer training;
- topK/support/threshold tuning;
- manuscript edit.

Key result:
- Primary verdict: `lowguard_plus_plus_candidate_found_with_model_specific_objective`.
- Stage A interface preflight passed with no final-eval selection or support/eval overlap.
- LOW-GUARD-LR top64 reproduced issue25c: locked mean/min/OOD max `0.949705 / 0.882629 / 0.004500`.
- No non-LR head dominated LOW-GUARD-LR on frozen `source_rich_top64`.
- `LOW_GUARD_HistGB_Conservative` on `original100` is a representation-control LOW-GUARD++ candidate: `0.994261 / 0.978091 / 0.005100`, feasible rate `1.000000`.
- Best non-LR on top64 was `LOW_GUARD_HistGB_Conservative`: `0.659751 / 0.040689 / 0.006600`.

Current claim boundary:
- Allowed: issue27d found a candidate worth formal issue27e validation and strengthened the adapter-interface evidence.
- Allowed: LOW-GUARD-LR remains the strongest demonstrated top64 minimal instance.
- Not allowed: the main method is replaced, LOW-GUARD++ is proven, LOW-GUARD is head-agnostic, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27e_formal_validation_for_lowguard_plus_plus`.
- Validate the `original100 + LOW_GUARD_HistGB_Conservative` candidate under full locked seeds and unchanged final-eval exclusion before changing any paper claim.

### 6.11 Issue27e Formal LOW-GUARD++ Validation Gate

Date: 2026-05-27

Run:
- `runs/issue27e_formal_validation_for_lowguard_plus_plus_original100_histgb_conservative_2026-05-26/`

Scope:
- candidate config freeze recovery for `original100 + LOW_GUARD_HistGB_Conservative`;
- audit of issue27d selection trace and leakage evidence;
- formal-validation go/no-go decision.

Not in scope:
- full locked-seed final-eval run after config ambiguity was found;
- temporal validation;
- cross-dataset validation;
- deployment robustness simulation;
- representation search;
- new model search;
- manuscript edit.

Key result:
- Primary verdict: `candidate_config_not_recoverable_needs_debug`.
- The issue27d candidate was not one unique frozen config:
  - `histgb_d2_lr003_l2p0_ood4_sup2_t0100` selected 7/12 smoke bin-seed combinations.
  - `histgb_d2_lr005_l2p1_ood4_sup4_t0050` selected 5/12 smoke bin-seed combinations.
- Full locked seed validation was not run, by design, because selecting one config after seeing the smoke aggregate could become hindsight model selection.
- No issue27e final-eval leakage occurred.

Current claim boundary:
- Allowed: issue27e identifies a candidate-freeze blocker and preserves claim hygiene.
- Allowed: original100 + HistGB-Conservative remains a serious LOW-GUARD++ candidate.
- Not allowed: LOW-GUARD++ is formally validated, the main method is replaced, HistGB universally dominates LR, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27f_candidate_config_freeze_and_formal_validation_for_original100_histgb_conservative`.
- Freeze one HistGB-Conservative config using support-validation / OOD-validation evidence only, then run full locked seeds.

### 6.12 Issue27f Config Freeze Then Formal LOW-GUARD++ Validation

Date: 2026-05-27

Run:
- `runs/issue27f_config_freeze_then_formal_validation_for_original100_histgb_conservative_2026-05-27/`

Scope:
- train/cal/validation-side config freeze for `original100 + HistGB-Conservative`;
- full locked seed validation after config freeze;
- LOW-GUARD-LR top64 reference rerun in matched schema;
- threshold target robustness report;
- leakage and artifact audit.

Not in scope:
- deployment robustness simulation;
- temporal validation;
- cross-dataset validation;
- representation search;
- new model search;
- manuscript edit.

Key result:
- Primary verdict: `lowguard_plus_plus_formal_validated`.
- Frozen config: `histgb_d2_lr005_l2p1_ood4_sup4_t0050`.
- LOW-GUARD++ formal locked mean/min/OOD max: `1.000000 / 1.000000 / 0.000100`.
- LOW-GUARD-LR top64 reference locked mean/min/OOD max: `0.949705 / 0.882629 / 0.004500`.
- LOW-GUARD++ dominates LOW-GUARD-LR on locked mean, locked min, and OOD max.
- Feasible rate: `1.000000`.
- Threshold robustness:
  - target `0.0050`: `1.000000 / 1.000000 / 0.000100`;
  - target `0.0075`: `1.000000 / 1.000000 / 0.000100`;
  - target `0.0100`: `1.000000 / 1.000000 / 0.008300`.
- No final-eval selection leakage was found.

Current claim boundary:
- Allowed: LOW-GUARD++ is formally validated as `original100 + HistGB-Conservative` under the locked low-alert protocol.
- Allowed: LOW-GUARD-LR remains the minimal stable instance under source-rich top64.
- Allowed: the method story can be framed as minimal instance + performance instance.
- Not allowed: HistGB universally dominates LR, LOW-GUARD works for all models, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.

Next:
- Unique next action: `issue27g_deployment_robustness_for_lowguard_lr_and_lowguard_plus_plus`.
- Stress-test both instances under support budget, support noise, OOD benign contamination, support source, and shadow-mode workload protocols.

| issue27g | suspicious-perfect-score audit for LOW-GUARD++ | `lowguard_plus_plus_formal_result_passes_anomaly_audit` | Audits issue27f 1.0 result for final-eval leakage, split overlap, original100 leakage, negative controls, scratch recompute, and cache artifacts. Next: `issue27h_original100_feature_provenance_and_independent_verification_before_claim_upgrade`. |

| issue27h | original100 feature provenance and LOW-GUARD++ claim gate | `lowguard_plus_plus_depends_on_high_risk_separators` | Maps separator features, runs frozen ablations, and blocks broad claim upgrade pending clean independent validation/provenance. Next: `issue27i_separator_dependency_deeper_audit_or_demote_lowguard_plus_plus`. |

| issue27i | LOW-GUARD++ separator validation and data expansion feasibility | `lowguard_plus_plus_promising_needs_clean_independent_validation` | Characterizes separator stability and safer variants; keeps LOW-GUARD++ alive while blocking claim upgrade pending clean independent validation. Next: `issue27j_raw_provenance_recovery_and_clean_independent_split_construction`. |

| issue27j | raw provenance and clean split audit for LOW-GUARD++ | `clean_independent_validation_blocked_but_recoverable` | Recovered raw pcap/TSV/source-code provenance but found clean independent validation still blocked by insufficient unused future/capture split assets. Next: `issue27k_row_level_original100_rebuild_and_purged_split_construction`. |

| issue27k | row-level original100 rebuild and purged split construction | `row_manifest_recovered_but_clean_split_blocked` | Builds row-level sidecar and verifies feature alignment; clean/purged validation remains blocked by insufficient clean independent split assets. Next: `issue27l_split_aware_original100_rebuild_with_sufficient_clean_eval_asset`. |

| issue27l | clean eval asset and split-aware original100 rebuild gate | `clean_eval_asset_found_rebuild_eval_next` | Finds full Mirai/Botnet labeled assets and a sufficiently sized extended-segment candidate; blocks formal LOW-GUARD++ clean eval pending feature compatibility, split-aware rebuild, and prior-use/provenance audit. Next: `issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild`. |

### issue27m full Mirai compatibility audit (2026-05-27)

| Run | Verdict | Role | Boundary | Next |
|---|---|---|---|---|
| `runs/issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild_2026-05-27/` | `full_mirai_incompatible_needs_new_frontend_path` | Large-data compatibility and prior-use gate for LOW-GUARD++ | Full Mirai is not yet a clean validation result for frozen original100; it is a clean115/restored115 or re-extraction path | Recover restored115 mapping or re-extract original100 before evaluation |
| issue27n | full Mirai restored115 mapping and interface-smoke gate | `restored115_feature_mapping_blocked` | Defines clean115 from dirty116 but blocks smoke because feature mapping is unverified and strict prior-use exclusion removes all benign rows. Next: `issue27o_restored115_mapping_recovery_or_original100_reextraction_for_full_mirai`. |

| issue27o | full Mirai protocol reset spec | `full_mirai_protocol_reset_ready_with_anonymous_clean115` | Adopts full Mirai as within-dataset protocol-reset benchmark; old issues are exploration; restored115/common100 remain unmapped; baselines must be rerun. Next: `issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution`. |

| issue27p | full Mirai anonymous clean115 reset benchmark | `baseline_dominates_needs_method_rethink` | Runs formal within-dataset reset benchmark with anonymous clean115; best current method `DeepSADStyle_Lite`; old results superseded for final claims. Next: `issue27q_protocol_reset_result_audit_and_seed_expansion`. |

| issue27q_plan | protocol reset result audit plan | `issue27q_execution_plan_ready` | Plan-only package: audit DeepSADStyle_Lite, diagnose LOW-GUARD++ failure, and design paired protocol-universality matrix. Next: P0/P1 audit before mainline decision. |

| issue27q_P0P1 | DeepSAD-lite replay/audit/seed expansion | `deepsad_lite_result_suspicious_needs_artifact_debug` | P0/P1 audit for the issue27p leader; checks replay, leakage, negative controls, feature artifact risk, and seed 42-51 stability. Next: `issue27r_deepsad_lite_artifact_debug_and_feature_provenance`. |

<!-- issue27r_map_entry -->

### issue27r_full_mirai_benchmark_semantic_validity_and_ood_drift_audit_2026-05-28

- status: completed.
- primary_verdict: `attack_benign_artifact_risk`.
- outputs: `runs/issue27r_full_mirai_benchmark_semantic_validity_and_ood_drift_audit_2026-05-28/`.
- role: benchmark semantic validity gate before model-line continuation.
- implication: pause DeepSAD mainline, LOW-GUARD++ repair, and universality claims until full Mirai raw provenance or second-dataset semantic validation resolves row-order/source/feature-semantics risk.

<!-- issue27s_map_entry -->

### issue27s_raw_provenance_or_second_dataset_semantic_reconstruction_for_low_ood_alert_benchmark_2026-05-28

- status: completed.
- primary_verdict: `dual_track_raw_rebuild_and_second_dataset_intake`.
- outputs: `runs/issue27s_raw_provenance_or_second_dataset_semantic_reconstruction_for_low_ood_alert_benchmark_2026-05-28/`.
- role: Data validity gate fork after issue27r semantic failure.
- implication: full Mirai anonymous_clean115 is not current main benchmark; proceed with raw provenance recovery and second-dataset intake before any model execution.

<!-- issue27t_map_entry -->

### issue27t_second_dataset_intake_with_full_mirai_raw_missing_confirmed_2026-05-28

- status: completed.
- primary_verdict: `second_dataset_candidates_need_manual_access_or_download_confirmation`.
- outputs: `runs/issue27t_second_dataset_intake_with_full_mirai_raw_missing_confirmed_2026-05-28/`.
- role: Data validity gate second-dataset candidate intake after full Mirai paired raw was confirmed missing.
- implication: no model execution; proceed to Gotham metadata intake, with ToN-IoT as fallback and local IoT-23 as auxiliary.

<!-- issue27u_map_entry -->

### issue27u_gotham_metadata_intake_and_data_gate_precheck_2026-05-28

- status: completed.
- primary_verdict: `gotham_ready_for_full_download_with_user_confirmation`.
- outputs: `runs/issue27u_gotham_metadata_intake_and_data_gate_precheck_2026-05-28/`.
- role: Gotham metadata-level Data Gate precheck.
- implication: Gotham is promising but requires user-confirmed 23.825GB decimal / 22.189GiB download and file-level split/label audit before any model execution.

<!-- issue27v_map_entry -->

### issue27v_gotham_download_and_file_level_data_gate_2026-05-28

- status: completed under user-approved download-only mode.
- primary_verdict: `gotham_file_level_gate_passed_ready_for_sample_data_gate`.
- outputs: `runs/issue27v_gotham_download_and_file_level_data_gate_2026-05-28/`.
- role: Gotham file-level Data Gate entry point after user-confirmed download permission.
- implication: Gotham passed file-level gate for raw PCAP + labelled processed CSV presence, but metadata is partial and sample-level Data Gate is still required before feature/interface work or any model execution.

<!-- issue27w_map_entry -->

### issue27w_gotham_sample_data_gate_2026-05-28

- status: completed.
- primary_verdict: `gotham_sample_gate_promising_needs_more_space_and_larger_sample`.
- outputs: `runs/issue27w_gotham_sample_data_gate_2026-05-28/`.
- role: Gotham sample-level Data validity gate before feature/interface work.
- implication: Gotham is promising but requires larger sample manifest/split validation before any model execution.

<!-- issue27x_map_entry -->

### issue27x_gotham_larger_sample_manifest_and_split_gate_2026-05-28

- status: completed.
- primary_verdict: `gotham_larger_sample_promising_needs_full_manifest`.
- outputs: `runs/issue27x_gotham_larger_sample_manifest_and_split_gate_2026-05-28/`.
- role: larger-sample Data validity gate for Gotham split construction.
- implication: Gotham remains promising, but Feature/interface gate is blocked until a fuller manifest and exact claim-safe split contract control file/device/time artifacts.

<!-- issue27y_map_entry -->

### issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28

- status: completed.
- primary_verdict: `gotham_data_contract_promising_needs_feature_pairing_or_full_manifest`.
- outputs: `runs/issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28/`.
- role: final-strengthening Data validity gate for all-CSV Gotham summaries and preregistered split-contract candidates.
- implication: Gotham has a promising device-disjoint data contract and adequate scale, but model experiments remain blocked until PCAP/CSV pairing and source-feature shortcut policy are strengthened.


<!-- issue27z_map_entry -->

### issue27z_gotham_pcap_csv_pairing_and_feature_source_policy_gate_2026-05-28

- status: completed.
- primary_verdict: `gotham_ready_for_feature_interface_diagnostic_only`.
- outputs: `runs/issue27z_gotham_pcap_csv_pairing_and_feature_source_policy_gate_2026-05-28/`.
- role: PCAP/CSV pairing strengthening and feature-source policy pre-gate.
- implication: Gotham may proceed only to Feature/interface gate work; model experiments remain disallowed.


<!-- issue27aa_map_entry -->

### issue27aa_gotham_strict_packet_feature_dataset_and_split_materialization_2026-06-01

- status: completed.
- primary_verdict: `gotham_strict_feature_dataset_ready_for_model_interface_smoke`.
- outputs: `runs/issue27aa_gotham_strict_packet_feature_dataset_and_split_materialization_2026-06-01/` plus external dataset artifacts under `datasets/gotham2025/derived/strict_packet_feature_dataset_v1/`.
- role: strict source-clean data asset construction and frozen split materialization.
- implication: proceed to interface smoke only; no formal model benchmark yet.

## issue27ab Gotham Kitsune115 frontend feasibility (2026-06-01)

- primary_verdict: `kitsune115_blocked_by_pcap_label_alignment`
- evidence role: Feature/interface pre-gate for the formal Gotham PCAP-derived 115D feature path.
- claim boundary: no model ranking, no external generalization, no deployment robustness; strict 8D is engineering-only.
- next action: issue27ac Gotham Kitsune115 attack-onset alignment and broader split-aware materialization before any model interface smoke.

<!-- issue27ac_map_entry -->

### issue27ac_gotham_kitsune115_attack_onset_alignment_then_materialization_2026-06-02

- status: completed.
- primary_verdict: `attack_onset_alignment_partial_ready_for_kitsune115_smoke_expansion`.
- outputs: `runs/issue27ac_gotham_kitsune115_attack_onset_alignment_then_materialization_2026-06-02/` plus tiny external probe artifacts under `datasets/gotham2025/derived/kitsune115_attack_onset_probe_v1/`.
- implication: attack-side alignment is tractable for a smoke expansion if PCAP scenario and onset timestamp are selected correctly; full-contract materialization still needs deeper scan for unresolved ip-camera attack files. No model benchmark yet.

<!-- issue27ad_map_entry -->

### issue27ad_gotham_kitsune115_split_aware_smoke_dataset_expansion_2026-06-02

- status: completed.
- primary_verdict: `kitsune115_split_aware_smoke_dataset_ready_heavy_attack_deferred`.
- outputs: `runs/issue27ad_gotham_kitsune115_split_aware_smoke_dataset_expansion_2026-06-02/` plus external artifacts under `datasets/gotham2025/derived/kitsune115_split_aware_smoke_expansion_v1/`.
- implication: 115D smoke dataset construction is ready for a minimal model-interface shape smoke, not formal benchmarking; heavy ip-camera attack files need fast frontend/Slurm for larger materialization.

<!-- issue27ae_map_entry -->

### issue27ae_gotham_kitsune115_model_interface_shape_smoke_2026-06-02

- status: completed.
- primary_verdict: `kitsune115_model_interface_smoke_passed`.
- outputs: `runs/issue27ae_gotham_kitsune115_model_interface_shape_smoke_2026-06-02/`.
- implication: backend adapters can consume fixed 115D smoke artifacts for shape checks only; no method claim.

<!-- issue27af_map_entry -->

### issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02

- status: completed.
- primary_verdict: `kitsune115_medium_materialization_ready_full_needs_slurm`.
- outputs: `runs/issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02/` plus external medium artifacts under `datasets/gotham2025/derived/kitsune115_medium_materialization_v1/`.
- implication: medium data asset is ready for non-performance sanity checks; formal benchmark waits for full_contract or explicit preregistration.

<!-- issue27ag_map_entry -->

### issue27ag_gotham_kitsune115_larger_asset_interface_sanity_2026-06-02

- status: completed.
- primary_verdict: `kitsune115_larger_asset_ready_with_full_contract_pending`.
- outputs: `runs/issue27ag_gotham_kitsune115_larger_asset_interface_sanity_2026-06-02/`.
- implication: medium 115D asset has a fixed loader and role-permission sanity gate; formal benchmark still waits on full_contract or explicit preregistration.

<!-- issue27ah_map_entry -->

### issue27ah_gotham_kitsune115_guarded_protocol_small_scale_dry_run_2026-06-02

- status: completed.
- primary_verdict: `guarded_protocol_medium_dry_run_completed_diagnostic_only`.
- outputs: `runs/issue27ah_gotham_kitsune115_guarded_protocol_small_scale_dry_run_2026-06-02/`.
- implication: medium 115D diagnostic behavior is available, but formal benchmark waits for full_contract or a documented exclusion policy.

<!-- issue27ai_map_entry -->

### issue27ai_medium_protocol_audit_then_diagnostic_2026-06-02

- status: completed.
- primary_verdict: `medium_protocol_audit_passed_diagnostic_completed`.
- outputs: `runs/issue27ai_medium_protocol_audit_then_diagnostic_2026-06-02/`.
- implication: protocol matrix diagnostics are available for debugging only; final claims wait for full/larger asset and frozen protocol.

## issue27aj - Protocol Lineage Recovery And Support Selector Audit

- Status: completed.
- Primary verdict: `recovered_kcenter_mainline_protocol_ready_for_gotham115_migration`.
- Key recovery: old mainline support selector is `kcenter32`, not issue27ai
  `fixed_first32`.
- Evidence: issue23 locked validation and issue25c strong baseline pack name
  the main candidate as `selected_source_rich_top64 + kcenter32 + fixed OOD
  guard LR`; executable code calls `issue19b.kcenter_support(...)` on the
  train-side attack pool only.
- Selector mechanics: selector-local `StandardScaler`, Euclidean farthest-first
  k-center, budget 32, no attack eval or final OOD eval access.
- Gotham migration: migrate selector/protocol permissions only to Gotham
  Kitsune115 medium diagnostics; do not migrate old frontend or old performance
  claims.
- Next: `issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic`.

<!-- issue27ak_map_entry -->

### issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic_2026-06-02

- status: completed.
- primary_verdict: `recovered_kcenter32_medium_diagnostic_completed`.
- outputs: `runs/issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic_2026-06-02/`.
- implication: recovered kcenter32 support can be diagnosed on medium Gotham115 only; final claims wait for full/larger asset and frozen protocol.

<!-- issue27am -->
## issue27am

- verdict: `medium_repair_insufficient_pause_feature_state_onset_audit`
- route: Gotham Kitsune115 medium bounded protocol repair validation.
- claim boundary: diagnostic only; formal full/larger benchmark remains gated.

<!-- issue27an -->
## issue27an

- verdict: `support_eval_distribution_mismatch_blocker_found`
- route: Gotham Kitsune115 medium failure attribution audit.
- claim boundary: diagnostic failure attribution only; no model ranking or formal benchmark.

<!-- issue27ao -->
## issue27ao

- verdict: `contract_v2_ready_for_medium_detection_retest`
- route: Gotham Kitsune115 medium support/eval contract v2 validation.
- claim boundary: contract-only diagnostic; no model performance claim.

<!-- issue27ap -->
## issue27ap

- verdict: `new_heldout_v2_diagnostic_signal_weak_support_shift_persists`
- route: new held-out heavy attack probe plus v2 diagnostic retest.
- claim boundary: diagnostic only.

<!-- issue27aq -->
## issue27aq - Model learning/domain-gap diagnosis

- Inputs: issue27af medium reset asset, issue27ao `file_balanced_v2`, issue27ap new heldout probe.
- Verdict: `zero_detection_due_to_ood_tail_threshold_overconservative_despite_raw_support_signal`.
- Model line remains diagnostic; full benchmark remains blocked until learning/calibration is repaired under role-safe rules.

<!-- issue27ar -->
## issue27ar - Old LOW-GUARD++ protocol fidelity migration

- verdict: `old_protocol_fidelity_mixed_needs_bounded_calibration_repair`
- purpose: determine whether current Gotham weak signal is partly due to protocol mismatch against old issue27f LOW-GUARD++.
- outputs: `runs/issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium_2026-06-03/`.

<!-- issue27as -->
## issue27as - Bounded calibration repair after old protocol fidelity

- verdict: `bounded_repair_suggests_feature_or_task_boundary`
- purpose: test whether bounded calibration/support-influence changes can rescue medium signal without using report-only roles.
- outputs: `runs/issue27as_old_protocol_bounded_calibration_and_coverage_repair_2026-06-03/`.

<!-- issue27at -->
## issue27at - Coverage hypothesis validation

- verdict: `coverage_hypothesis_partially_supported_needs_more_attack_pool`
- purpose: test whether support-query coverage explains medium/high vs heavy/low heldout behavior without tuning a new protocol.
- outputs: `runs/issue27at_coverage_hypothesis_validation_before_protocol_redesign_2026-06-03/`.

<!-- issue27au -->
## issue27au - Coverage-aware active labeling viability

- verdict: `active_labeling_viability_supported_but_ood_tail_blocked`
- purpose: test whether budgeted representative labels from uncovered incoming heavy stream can rescue dev-query detection without using final roles.
- outputs: `runs/issue27au_coverage_aware_active_labeling_viability_diagnostic_2026-06-04/`.

<!-- issue27av -->
## issue27av - Prototype-aware triage

- verdict: `ood_tail_needs_benign_prototype_veto`
- purpose: attribute final OOD tail alarms using ID/OOD/attack prototypes before OOD-safe gate repair.
- outputs: `runs/issue27av_prototype_aware_triage_and_ood_tail_attribution_2026-06-04/`.

<!-- issue27aw -->
## issue27aw - OOD-safe gate repair

- verdict: `benign_veto_tradeoff_unresolved_ood_safe_but_attack_damaged`
- purpose: test whether benign/OOD prototype veto can reduce OOD tail without using final roles for gate selection.
- outputs: `runs/issue27aw_ood_safe_gate_repair_with_benign_prototype_veto_2026-06-04/`.

<!-- issue27ax -->
## issue27ax - Attack support bank diagnostic

- verdict: `support_bank_overfits_heavy_underrepresents_medium`
- purpose: test whether a multi-region support bank can recover support_val, medium attack, and dev-heavy attack detection together.
- outputs: `runs/issue27ax_attack_support_bank_detection_recovery_diagnostic_2026-06-04/`.

<!-- issue27ay -->
## issue27ay - Region-aware attack support bank diagnostic

- verdict: `region_aware_attack_recovery_supported_ready_for_ood_gate`
- purpose: test whether attack regions should be kept as structured memory instead of one merged positive class.
- outputs: `runs/issue27ay_region_aware_attack_bank_and_score_gate_diagnostic_2026-06-05/`.

<!-- issue27az -->
## issue27az - Region-aware OOD gate diagnostic

- verdict: `needs_disjoint_ood_stress_pool_final_tail_uncovered`
- purpose: test whether region-aware attack heads can be guarded without killing attack detection or overloading review.
- outputs: `runs/issue27az_region_aware_attack_preserving_ood_safe_gate_repair_2026-06-05/`.

<!-- issue27ba -->
## issue27ba - Disjoint OOD stress pool gate diagnostic

- verdict: `stress_gate_kills_attack_repair_needed`
- purpose: give OOD gate selection a harder legal dev-side benign drift signal before mixed-stream realism.
- outputs: `runs/issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05/`.

<!-- issue27bb -->
## issue27bb - Three prototype bank gate diagnostic

- verdict: `three_bank_gate_still_kills_attack`
- purpose: test whether compressed ID/OOD/Attack prototype banks can suppress OOD drift while preserving attack core alarms.
- outputs: `runs/issue27bb_attack_preserving_ood_gate_with_three_prototype_banks_2026-06-05/`.

<!-- model_protocol_open_problems_2026_06_05 -->
## Model / Protocol Open Problems Before Formal Benchmark

- **Attack-preserving OOD gate:** OOD/stress hard alarms can be reduced, but report-only attack still drops too much.
- **Attack region expansion:** current medium/heavy two-head design is diagnostic only; final system needs bounded region registry, top-k routing, shared/limited heads, and merge/split policy.
- **Support bank generalization:** support validation is not enough; support-query gap still damages report-only attack.
- **Active labeling realism:** current active labels are dev-side oracle simulation; mixed ID/OOD/attack/noise stream triage is still required.
- **Review/unknown cost:** review and unknown must be bounded and cannot count as detection success.
- **Prototype bank online policy:** ID/OOD/Attack prototypes need fixed budgets, radii, top-k routing, and update cadence.
- **OOD stress coverage:** final OOD remains report-only; legal dev-side stress pools may need broadening if they miss tails.
- **Training weights:** ID/OOD/support/region sampling and weights must be frozen before formal benchmark.
- **Online update policy:** support expansion, prototype update, region creation/merge, and retraining cadence remain undefined.
- **Formal benchmark block:** no formal benchmark until OOD hard <= 1%, attack hard is high/stable, review cost is bounded, region expansion is scalable, mixed-stream passes, and larger/full 115D contract is frozen.

<!-- issue27bc -->
## issue27bc - Prototype purity and unknown-band gate diagnostic

- verdict: `pseudo_query_reveals_support_core_overfit`
- purpose: test whether attack-core purity, pseudo-query generalization, and bounded review can improve the three-bank gate without leaking final roles.
- result note: strict purity removes OOD hard alarms but also kills attack hard alarms; next work should repair attack-region generalization/conflict handling before temporal smoothing or full runs.
- outputs: `runs/issue27bc_attack_core_purity_unknown_band_review_budget_2026-06-07/`.

<!-- issue27bd -->
## issue27bd - Conflict-aware shell and subspace gate diagnostic

- verdict: `subspace_conflict_gate_promising_attack_recovered_ood_relaxed`
- purpose: test whether gate evidence should use a fixed Kitsune115 family subspace and pseudo-query-calibrated attack shell instead of strict full-115D purity.
- outputs: `runs/issue27bd_conflict_aware_attack_shell_and_gate_subspace_diagnostic_2026-06-07/`.

<!-- issue27be -->
## issue27be - Frozen past-only replay audit

- verdict: `past_only_replay_passed_with_dev_pseudo_caveat_ready_for_attack_region_bank`
- outputs: `runs/issue27be_past_only_replay_audit_on_conflict_gate_2026-06-07/`.
- no full/larger benchmark and no temporal smoothing; proceed to bounded attack region bank if continuing.

<!-- issue27bf -->
## issue27bf - Bounded attack region bank diagnostic

- verdict: `bounded_attack_bank_heavy_gain_medium_retention_failure`
- outputs: `runs/issue27bf_bounded_attack_region_bank_2026-06-08/`.
- no 115D frontend or split changes; no full/larger formal benchmark.
- attack hard min remained `0.6428571428571429`, below the `0.93` attack-side gate; next step is shared-scorer / region-refinement before any OOD-gate repair.

<!-- issue27bg -->
## issue27bg - Shared scorer region refinement diagnostic

- verdict: `shared_scorer_no_sufficient_attack_recovery`
- outputs: `runs/issue27bg_shared_scorer_region_refinement_before_ood_gate_2026-06-08/`.
- no 115D frontend or split changes; no full/larger formal benchmark.
- attack hard min gate 0.93 passed: `False`.

<!-- issue27bh -->
## issue27bh - Attack-side failure anatomy

- verdict: `support_query_gap_primary_blocker_before_new_head`
- outputs: `runs/issue27bh_attack_scorer_region_failure_anatomy_before_new_head_2026-06-08/`.
- no new head is selected here; this is anatomy before scorer redesign.

## issue27bi - region-aware metric/calibrated two-head diagnostic

<!-- issue27bi_region_aware_metric_or_calibrated_two_head_design -->
- Stage: medium diagnostic before OOD gate repair.
- Primary verdict: `metric_or_calibrated_two_head_no_sufficient_attack_recovery`.
- Attack gate threshold remains `0.93` before any OOD repair/full benchmark.
- Candidate families: calibrated two-head margin, logistic score fusion, LDA metric prototype.
- Current formal benchmark status: blocked.

## issue27bj research design - Kitsune115 evidence decomposition

<!-- issue27bj_deep_research_kitsune115_system_design -->
- Stage: research/design gate before the next issue27bj implementation.
- Outputs: `research_report.md`, `method_candidate_table.csv`, `issue27bj_next_action.md`, `online_cost_model.md`, `risk_and_failure_modes.md`, `paper_claim_boundary.md`.
- Recommended experiment: `issue27bj_metric_evidence_shell_controller_smoke_2026-06-08`.
- Formal benchmark status: still blocked; no OOD-gate repair until attack hard-min `>=0.93`.

## issue27bk - task boundary then metric shell smoke

<!-- issue27bk_task_boundary_then_metric_shell_smoke -->
- Stage: medium diagnostic before any OOD-gate repair.
- Primary verdict: `metric_shell_no_attack_recovery_task_boundary_audit_next`.
- Boundary verdict: `task_boundary_high_distribution_shift_no_role_leakage`.
- Formal benchmark status: blocked.
- OOD-gate repair remains blocked unless attack hard-min reaches `0.93`.

## issue27bl - attack phase/onset/pseudo-query contract audit

<!-- issue27bl_attack_phase_onset_pseudo_contract_audit -->
- Stage: data-contract audit before more head repair.
- Primary verdict: `attack_phase_contract_mismatch_needs_rebuild_before_more_heads`.
- Formal benchmark status: blocked.
- OOD-gate repair remains blocked.

## issue27bm - phase-balanced attack contract design

<!-- issue27bm_phase_balanced_attack_contract_design -->
- Stage: data-contract audit before more model/head repair.
- Primary verdict: `phase_balanced_contract_ready_for_attack_only_diagnostic_with_tail_gap_caveat`.
- Formal benchmark status: blocked.
- Attack_eval/final/report-only roles remain sealed for selection.

## issue27bn - attack-only diagnostic on phase-balanced contract

<!-- issue27bn_attack_only_diagnostic -->
- Stage: attack-side diagnostic before any OOD-gate repair.
- Primary verdict: `phase_balanced_attack_diagnostic_recovers_dev_and_report_only_attack`.
- Formal benchmark status: blocked.
- Report-only roles remained replay-only.

## issue27bo - fixed-support attack future-shift validation

<!-- issue27bo_attack_future_shift_validation -->
- Stage: attack-side validation before OOD-gate repair.
- Primary verdict: `attack_future_shift_validation_passed_with_report_only_late_replay_caveat`.
- Formal benchmark status: blocked.
- Future/query and report-only roles remained replay-only.

## issue27bp - attack-preserving OOD gate repair

<!-- issue27bp_attack_preserving_ood_gate -->
- Stage: medium diagnostic for family-aware gate evidence.
- Primary verdict: `attack_preserved_but_dev_ood_overbudget`.
- Full 115D raw attack scorer stayed fixed; prototype gate evidence used selected Kitsune family subspaces.
- Final/report-only roles remained replay-only.

## issue27bq - decoupled OOD-risk scorer diagnostic

<!-- issue27bq_decoupled_ood_risk -->
- Primary verdict: `decoupled_ood_risk_partial_pareto_improvement_but_ood_overbudget`.
- Stage: medium diagnostic; no full/formal benchmark.
- Purpose: test whether alarm-conditioned OOD-risk scoring improves the attack/OOD frontier.

## issue27br - past-only temporal/interaction diagnostic

<!-- issue27br_past_only_temporal_interaction -->
- Primary verdict: `past_only_temporal_signal_present_needs_mini_interaction_graph`.
- Purpose: test whether causal/past-only temporal-source evidence can help explain or repair BQ's suppressed attack tail without final leakage.
- Stage: medium diagnostic before any larger/full benchmark.

## issue27bs - lightweight temporal evidence head diagnostic

<!-- issue27bs_lightweight_temporal_head -->
- Primary verdict: `temporal_evidence_head_dev_passed_ready_for_controller_stability`.
- Purpose: test whether training-layer past-only temporal evidence improves the BQ/BR frontier without final leakage.
- Stage: medium diagnostic before any larger/full benchmark.

## issue27bt - temporal head stability/ablation

<!-- issue27bt_temporal_head_stability -->
- Primary verdict: `temporal_head_group_stable_with_parent_evidence_no_parent_ood_overbudget`.
- Purpose: verify issue27bs high score against parent-risk and source/time-adjacency artifacts.
- Stage: medium diagnostic before any larger/full benchmark.

## issue27bu - unified temporal attack/OOD heads certification

<!-- issue27bu_unified_temporal_attack_ood_heads_certification -->
- Primary verdict: `parent_oodrisk_certified_current_system_hard_pass_unified_no_parent_needs_ood_margin_repair`.
- Purpose: certify parent OOD-risk lineage and compare parent-stacked vs no-parent unified temporal two-head variants.
- Stage: medium diagnostic before larger/full benchmark.
- Final/report-only roles remained replay-only.

## issue27bv - problem definition and frozen protocol before larger

<!-- issue27bv_problem_definition_and_frozen_protocol_before_larger -->
- Primary verdict: `protocol_frozen_for_larger_sanity_not_formal_benchmark`.
- Purpose: freeze the current candidate protocol, define support/mixed-stream/leakage/online-cost contracts, and bound claims before larger sanity.
- Stage: documentation/protocol gate before any larger/full benchmark.
- No model was run; final/report-only independence remains mandatory.

## issue27bw - Larger Sanity Contract Construction

- output_dir: `runs/issue27bw_larger_sanity_contract_construction_2026-06-11/`
- decision: `larger_sanity_contract_ready_for_materialization_not_formal_benchmark`
- stage: larger sanity data contract before materialization
- inputs: issue27bv frozen protocol, issue27bu certified medium system, issue27y all-CSV manifest
- no model run, no feature extraction, no commit/push
- main artifacts: `larger_sanity_contract_v1.json`, `role_file_inventory.csv`, `split_disjointness_audit.csv`, `final_seal_audit.csv`, `medium_to_larger_migration_map.md`
- next: issue27bx bounded larger materialization dry run

## issue27bx - Larger Sanity Materialization Dry Run

- output_dir: `runs/issue27bx_larger_sanity_materialization_dry_run_from_contract_v1_2026-06-11/`
- decision: `larger_sanity_materialization_partial_needs_quota_or_frontend_fix`
- stage: bounded local larger sanity asset materialization
- no model run; data artifacts live under `datasets/gotham2025/derived/kitsune115_larger_sanity_v1/`
- next: issue27by frozen-system replay

## issue27bx2 Materialization Quota/Cache Repair

marker: `issue27bx2_materialization_quota_cache_repair_2026-06-12`

- Inputs: issue27bw larger contract, issue27bx role meta, archive listing.
- Outputs: available row estimates, quota-vs-actual table, fallback rules, cache key manifest, v2 quota plan.
- Next: issue27bx3 500k cache-aware materialization retry before model replay.

## issue27bx3 500k Cache-aware Materialization Retry

marker: `issue27bx3_500k_cache_aware_materialization_retry_2026-06-12`

- Inputs: issue27bx2 v2 quota plan.
- Outputs: 500k X/y/sidecar/split manifest, per-file cache, runtime/cache audit.
- Role: data production line stabilization, not model performance.


## issue27bx4 - 1M Kitsune115 runtime profile attempt
- verdict: cache_aware_1m_runtime_profile_blocked_by_local_runtime_bottleneck
- result: completed 845,000/1,000,000 rows; no certified 1M asset was produced.
- blocker: local runtime bottleneck on `processed/iotsim-building-monitor-1.csv` in `dev_future_attack_query` after >70 minutes active CPU with empty stderr.
- cleanliness: preserved; no cross-role fallback, no final/report-only reuse, no model training, partial canonical files quarantined with `INCOMPLETE_INTERRUPTED_`.
- next: issue27by_runtime_optimized_1m_or_slurm_materialization.

## issue27by Runtime-optimized 1M/Slurm Materialization Pipeline

marker: `issue27by_runtime_optimized_1m_or_slurm_materialization_2026-06-12`

- Role: data production line hardening before certified 1M/larger asset.
- Key constraint: non-ID extraction jobs depend on the frozen ID train frontend state snapshot.

## issue27bz Slurm 1M Cache Execution and Certified Merge

marker: `issue27bz_slurm_1m_cache_execution_and_certified_merge_2026-06-14`

- Inputs: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\issue27bx4_1m_materialization_runtime_profile_2026-06-12\materialization_1m_runtime_profile_plan.csv`.
- Outputs: 1m_certified X/y/sidecar/split manifest, per-file cache, runtime/cache audit.
- Role: data production line stabilization, not model performance.

## issue27ca Initial Support Bank Contract on Certified 1M

marker: `issue27ca_initial_support_bank_contract_on_certified_1m_2026-06-14`

- Role: support-bank contract and coverage audit before larger system replay.
- Main output: bounded initial support bank candidates for B=32/64/128/256 using phase-file balanced k-center.
- Boundary: data/system contract only, not performance.

## issue27cb Broader Attack Support Candidate Contract

marker: `issue27cb_broader_attack_support_candidate_contract_2026-06-14`

- Role: exact-label support taxonomy audit on certified 1M before any model replay.
- Main output: broader attack support contract v1 plus targeted materialization request.
- Boundary: data contract only; not performance.

<!-- issue27cc_targeted_multitype_attack_materialization_and_onset_realign -->
## issue27cc Targeted Multitype Attack Materialization and Onset Realign

- Verdict: `targeted_multitype_attack_contract_ready_for_slurm_exact_label_materialization`.
- Current 1M attack roles are not sufficient for model replay because support/query/final attack rows must be exact-label filtered.
- Historical `86336` reusable-current-support claim is superseded by CKBR: it
  came from treating a role-local recorded ordinal as a processed-CSV row
  index. Exact reuse now requires unique timestamp alignment.
- Newly planned targeted support rows: `69492`.
- Planned dev/query attack rows: `125679`.
- Planned sealed final exact attack rows: `110104`.
- Next: run exact-label Slurm materialization before any model replay.

<!-- issue27cd_slurm_exact_label_targeted_multitype_attack_materialization -->
### issue27cd_slurm_exact_label_targeted_multitype_attack_materialization
- Status: transfer/materialization script prepared for exact-label targeted multi-type attack Kitsune115 chunks.
- Purpose: repair attack-side materialization using issue27cc exact-label rows; no model training or benchmark.
- Key guardrail: emit only rows whose processed CSV label equals the planned attack label and whose packet timestamp matches the PCAP stream.
- Current 1M benign/OOD roles remain usable; attack query/final roles require this exact-label rematerialization before model conclusions.
- Next: run the Slurm transfer kit, validate missing_exact_rows/quarantine, then decide merge policy.

<!-- issue27cg_combined_cycle_query_alignment_repair_or_replan -->
### issue27cg combined-cycle query alignment audit
- solved: diagnosed issue27cd partial dev/query exact-label materialization gap (28175 rows).
- changed_mainline: no; support bank remains frozen and model replay remains blocked.
- active_blocker: dev_future_attack_query exact packet-label alignment for combined-cycle-1 partial chunks.
- frozen: issue27cf initial support bank, issue27bz benign/OOD 1M asset, sealed final attack/OOD non-selection rules.
- superseded: none; this audit narrows issue27cd partial status.
- next_action: query_alignment_requires_replan_for_combined_cycle_1.

<!-- issue27ckb_offline_static_capability_snapshot -->
### issue27ckb raw static scorer ablation
- scope: not a frozen-medium-mainline replay; parent OOD-risk, past-only temporal heads, and bounded controller were absent.
- verdict: `offline_static_attack_signal_present_but_benign_ood_nonseparable_score_saturated_and_seed_unstable`; seven HPC jobs completed with clean role access, but threshold-free attack-vs-OOD AUC was at or below chance and nominal q99 calibration was invalidated by score ties.
- changed_mainline: no; continue issue27ck family-aware evidence-space repair, with tie-aware calibration required before any repeat.

## issue27ckbo mature AfterImage transfer

- status: AMD jobs 151772 and 151774 failed before finalized metrics; corrected AMD job 151780 completed with valid `NO_GO`.
- failures: 151772 exposed shifted cached identities and zero legal original benign-select rows; 151774 exposed duplicate predictive report assembly and an over-broad historical held-protocol loop.
- corrected route: immutable C1/T0 target intersection, attack-only recall-first C1 candidate threshold, mature AfterImage115/TabM, 11/5 source-disjoint auxiliary fit/select sources, and 15 predictive-maintenance sources as a second unseen held family.
- local evidence: real 1M scope PASS (385/69, 3,413 original benign fit, zero canary/aux overlap) and real 31-source PCAP materialization PASS (6,600/3,000/9,000 fit/select/report).
- guardrails: missing-feature zero fill=0; unique per-protocol records; held-family auxiliary fit/select=0; exact five-protocol list; original strict 1M/T0 unchanged; stream/hydraulic/cooler fit/select=0; cooler sealed/unscored; review=0; both ip-camera-street and predictive-maintenance must individually and jointly improve.
- result: primary contrast+Aux changed stream to 99.733%, predictive to 73.011%, hydraulic to 42.533%, and overall attack by -6.091 pp; review 0 and cooler sealed.
- ablation: raw115+Aux strictly dominates contrast+Aux on four held OOD rates and overall attack recall; auxiliary normals help predictive/hydraulic but not stream/IP-camera and cost attack recall.
- next: no seeds 37/47; preregister source-held-out one-sided normal-evidence calibration with raw115/no-aux control and broader legal normal coverage.

## issue27ckbp source-local one-sided normal calibration

- status: AMD seed-27 job `151835` completed, but the registered primary is `NO_GO` and its apparent OOD improvement is protocol-degenerate.
- mature components: frozen C1 anchor, raw AfterImage115, scikit-learn QuantileTransformer, LedoitWolf shrinkage, and finite-sample split-conformal ranks.
- calibration contract: model fits legal benign-fit sources only; the deployed reference uses source-disjoint benign-select sources scored by the exact frozen model; leave-one-fit-source-out scores are diagnostic only.
- causal contract: source/phase reset, current-score-before-update, 64-row fail-closed provisional history, unreliable-state rejection, bounded shift for the primary, and unbounded non-deployable control.
- scope audit: 385 support-train, 69 support-val, 3,413 original benign fit, zero permanent-canary fit/select use, zero report-extension retention, zero raw rematerialization, and zero missing-feature fill.
- result: M2 selects verifier threshold `1.0` because all 69 support-val attacks are inside per-source burn-in; warmed scores cannot reach `1.0`. OOD hard counts therefore reduce to cold-start counts while overall attack recall collapses from `91.2997%` to `0.1451%`.
- retained evidence: M1 global normal conformal has real but insufficient OOD signal and loses `9.0498 pp` attack recall.
- next: repair the evaluation/state protocol before any new model or additional seed; see `runs/mainline_docs/ckbp_seed27_result_and_gate_diagnosis_20260717.md`.

## issue27ckbq causal MiniRocket normal-consensus verifier

- status: corrected AMD job `153037` completed the formal program; a stale post-run warm-up/hash validator was transparently repaired without retraining, and the recovered result passes `CKBQ_RESULT_VALID`.
- mature component: BSD-licensed `sktime v0.24.1` MiniRocketMultivariate algorithm with only its Numba backend ported to frozen-environment CPU PyTorch.
- primary: C1 shield plus static AfterImage normal score plus causal 32-event MiniRocket/Ridge evidence; only joint normal consensus suppresses, with no score addition and review=0.
- attack contract: all 385 global support-train rows supervise the family-balanced Ridge head once; 69 support-val rows are gate-only and are not claimed as future-attack evidence.
- leakage/cold contract: strict held exclusion from every fit/select stage; target-level windows skip later-phase frozen targets; 3,583-target real regression skipped 283 forbidden target-window occurrences and used zero forbidden/future events; report gradients and threshold updates zero; cold C1 candidates remain hard.
- result: valid single-seed `NO_GO`; M3 changes IP-camera/predictive/stream/hydraulic hard OOD from `100/100/100/72.367%` to `8.1/57.589/29.7/45.7%`, but overall attack recall drops `6.945 pp` and future attack recall drops `12.639 pp`.
- decomposition: temporal-only evidence rescues 37 attacks but adds 68 hydraulic false alarms; M3 is nearly the static branch. Exact post-hoc score-space feasibility finds zero current thresholds satisfying all attack and four-held constraints; the closest still loses `2.418 pp` attack recall.
- next: no seeds 37/47 and no report threshold tuning; retain static normality as an ablation and replace anonymous raw9 history with mature flow/connection-process evidence targeted at unseen attack preservation.

## issue27ckbr / issue27ckbs support-v2 mechanism admissibility audit

- status: exact provenance/materialization passes, but the candidate support extension is scientific `NO_GO` and fail-closed; no model training or HPC submission occurred.
- correction 1: issue27cb's 90,000-row exact-label inventory is rejected because `recorded_index_within_file` is a role-local ordinal, not a processed-CSV row index. The replacement joins packet and CSV timestamps uniquely within 2 microseconds.
- correction 2: issue27cc's `network-scanning` PCAP choice was a scenario-name heuristic. Exact target times and formal issue27cd chunk metadata select the `mirai-infection` PCAP, where scan/Telnet are labeled infection stages.
- candidate: 60 proposed train + 20 proposed validation rows per label, each from a distinct segment and 500 rows from query intervals; these proposed roles are not active.
- chronology: TCP candidates begin 322.611 seconds after the frozen TCP query ends; Telnet candidates begin 190.152 seconds after its query ends, all in the same capture. Row non-overlap therefore cannot justify fit use.
- output: 160/160 mature AfterImage115 diagnostic rows, shape `(160,115)`, zero missing/ambiguous targets and zero parse errors; all carry selection false and fit/threshold/model-selection forbidden. Active support remains 385/127 (58/69 validation lineage).
- frozen: original 385/127 support files and hashes, strict 1M/T0/query manifests, report canaries, cooler sealed, and review=0.
- next: CKBT supplies the independent-source gate; verify an already-installed Zeek binary/module and build one result-producing causal seed-27 chain.

## issue27ckbt ToN-IoT auxiliary process-support gate

- status: local data gate and independent raw-line validator PASS; no model training or HPC submission.
- mature source: dataset-provided Bro/Zeek 21-field conn logs plus ToN-IoT per-event GroundTruth; prior CKAN timestamp-sort/header policy is reused.
- exact join: direct `floor(conn.ts)` plus source/destination IP/port and protocol, unique on both conn and GroundTruth sides.
- bank: reconnaissance scan 2,000 fit + 500 select; credential brute force 2,000 fit + 500 select. Fit/select use different conn-log/GroundTruth source files (not a campaign-independence claim); seven further scan/password conn files have zero use.
- boundary: this is generic mechanism supervision, not exact Gotham label equivalence. It cannot enter Gotham C1 fit/normalization/thresholds/report roles and cannot support temporal replay because the provided logs lack explicit emission time.
- frozen Gotham: active support remains 385/127 with 58/69 validation lineage; the CKBR/CKBS 160 remain quarantined.
- next: verify an already-installed Zeek binary/module, build emission-time-aware Gotham process evidence, and train one small static process expert inside a result-producing seed-27 asymmetric chain.
