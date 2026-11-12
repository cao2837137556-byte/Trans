## 2026-11-11：完整库p4控制、TabM衔接与参考审计183551/183552

用户确定完整库p4为新版主结果。183551运行六控制、六条CIC撤警解释和历史参考来源/严格等价候选盘点；183552 afterok接原p3任务183549及183551，复用TabM预测追加p4。原库不删、不压缩；新增压缩想法只作只读可行性盘点。各1CPU8GiB1小时；客户端19112、18883接收、18806页面。[回执](collab/20261111_p4_controls_and_history_audit_launch_codex.md)。

---

## 2026-11-11：TabM原生概率域3D迁移183549

已提交固定五行比较，初始PENDING。复用权重，完整源FIT补打分，自身Q90−Q10尺度和源正常CAL阈值；完整RAW与旧指标通过后才做p3/λ.25/保护开修正，不裁剪、不套MLP尺度、不重训。RTX4090+8CPU16GiB2小时，20依赖通过；客户端44692、18882接收、18806页面。未宣称结果已完成；[回执](collab/20261111_tabm_3d_transfer_launch_codex.md)。

---

## 2026-11-11：保护及指数五臂消融正式验收

183530正常完成，两项PASS；388202查询冻结基准0误差/0判定差，156指标一致。B保护保留295攻击告警并保留28正常误报，Edge保留5 HTTP；p3→p4减少B/Edge误报80/24，但A少6攻击告警，单种子代价保留。五臂/全部头/视图/子组与SHA交付paper_reading_ablations_acceptance_v1_20261111；[论文回传](paper_writing_v1/experiment_results_guard_exponent_codex_20261111.md)。不重新挑参数，不扩大实验，六基线另验收。

---

## 2026-11-11：五配置消融已提交183530

用户恢复连接并授权提交。来源四份JSON在独立v2中按原SHA快照，67依赖通过；183529因无/usr/bin/time启动1秒失败未进科学计算，183530通过Python资源记录器重交，已实际核验Edge缓存。只做SYN保护及p=1/2/3/4，基准全通过后分项运行/回传。客户端47644、接收18881、进度18806；六基线状态全部COMPLETE待结果验收。见[回执](collab/20261111_paper_reading_ablations_submission_codex.md)。

---

## 2026-11-10：五配置补充消融本地交付

用户因超算网络故障要求先本地打包。paper_reading_ablations_v1_20261110已准备ZIP和SHA：五臂、原始support3身份门、BASE全指标与判定门、保护/指数分项回执、加权配对和HT。合成回归及67依赖核验通过，真实缓存未读、未提交。基线不操作，状态不可据旧快照推定。见[本地交付回执](collab/20261110_paper_reading_ablations_local_package_codex.md)。

---

## 2026-11-08：论文写作新对话接手入口

已整理[论文写作接手包](PAPER_WRITING_START_HERE_20261108.md)，区分当前FUSION790三维C5与旧少样本草稿，列出证据阅读顺序、六基线结果入口、写作边界和Codex/anti分工。此轮只新增写作导航，不修改模型或运行作业。TabR当前三个种子182915–182917已提交，评价182918依赖三者成功。

---

## 2026-11-08：TabR分种子预算修复182914

182807数值/整轮通过，因三种子总预算超过单作业7天被拦。独立种子作业+afterok评价替代单长链，科学worker/CONFIG字节未改，真实预检182914运行。客户端39556/18880/原页面18806；其他方法不重跑。见[修复回执](collab/20261108_tabr_seed_budget_repair_codex.md)。

---

## 2026-11-08：后三基线提交模块冲突修复182804

182796真实小切片PASS后，通用import controller被旧包截获，submit缺seconds而停止，未产生新训练作业。v2绝对路径加载+模块/worker/签名身份门，本地与计算节点启动提交包装器回归PASS；182804共享预检完成，Disent182805/TabM182806/TabR182807已提交排队。原训练worker/CONFIG字节不变；DTE旧作业继续。客户端8748、接收端18879、进度18806。见[修复回执](collab/20261108_remaining_three_dispatch_repair_codex.md)。

---

## 2026-11-08：六基线后三方法独立放行链182796

用户取消ModernNCA；共享预检182796运行，8CPU24GiB2小时，后续TabM/TabR/Disent各申请RTX4090+8CPU32GiB、7天硬上限，整轮资源门通过即三种子正式训练/CAL/A-B-Edge评价。Disent不受监督划分等待。保留全候选精确检索、作者早停和训练loss选择，本地跨进程恢复通过，GPU门尚待实测。客户端35108统一18806，接收端18878；旧包/主模型不热改。见[回执](collab/20261108_remaining_three_baseline_launch_codex.md)。

---

## 2026-11-08：固定七基线，推进剩余四方法审查

用户取消8–10数量目标，固定现有七个。四方法本地前后向检查完成；Disent-AD须沿用最低训练loss保存规则、不用控制台最佳测试AP，ModernNCA原默认周期拼接单张量float32约139.91GiB（总峰值更高），TabR参数更名历史证据仍待核实。无新作业，不动现有训练包。见[审查回执](collab/20261108_remaining_four_baseline_audit_codex.md)。

---

## 2026-11-08：SLAD独立评价导入路径修复182782

182779三种子训练100轮均完成，纯评价torch.load缺algorithms模块而失败。原续训检查因先construct注册路径而漏检；新进程直接predictor回归复现错误并验证修复预测精确一致。独立修复182782运行（1CPU8GiB2小时），复用三模型与大数组、先真实链路和加载门再CAL/A/B/Edge，无重训、不热改DTE父包。DTE182778仍运行，CatBoost182781完成待验收。客户端34636统一18806状态。见[回执](collab/20261108_slad_prediction_import_repair_codex.md)。

---

## 2026-11-08：作者参数首批自动训练链182777

已提交1CPU12GiB2小时真实预检，环境门PASS。DTE-C/SLAD/CatBoost按作者默认固定400/100轮、1000树，各自资源门后自动提交三种子训练、独立CAL、A/B/Edge评价；1CPU12GiB按实测定时长，每方法最多24小时。主模型不变，大工件留超算，客户端PID29824和18806进度页。TabM/TabR早停与资源、Disent适配资源、ModernNCA内存仍待办，未宣称七方法全部放行。见[启动回执](collab/20261108_baseline_author_defaults_launch_codex.md)。

---

## 2026-11-08：用户决定采用作者推荐参数，取消超参数搜索

取消每方法16配置计划。逐方法核实作者通用推荐/固定官方版本默认配置；不继续为超参数搜索修统一验证划分，若原方法需要验证早停或检查点选择，仍保留合法独立源验证及相应覆盖门。独立CAL阈值、评价角色与主模型冻结不变。剩余全量资源和跨进程恢复仍需补齐，本轮无新作业。见[方案修订](collab/20261108_baseline_author_defaults_decision_codex.md)。

---

## 2026-11-08：整轮资源通过，协议覆盖仍待修复

182752 COMPLETED/0:0、50:29，8阶段PASS、135项验收、保守峰值3.588GiB。新划分457120/160788行，六设备两类覆盖与capture/session/component隔离通过；DTE/SLAD/TabM完整轮次及完整验证计时通过，TabM训练42:26+验证2:40。协议细分仍有5个单侧缺失切片（ArloQ TCP仅验证、4设备UDP仅训练），另52活动切片，可能重叠；候选20%目标未约束协议，正式调参不放行。先审独立组数量区分可修与单组不可分，再定协议优先划分/交叉验证和限制。跨进程恢复、其余方法资源及逐配置门待补。主模型不改，大工件留超算，无新作业。见[验收报告](collab/20261108_baseline_split_resource_acceptance_codex.md)。

---

## 2026-11-07：源分组修复与整轮资源预检

用户授权合理调参，先修验证划分再补资源门。独立包baseline_split_resource_v1_20261107已封存/启动交付，作业182752，1CPU8GiB2小时8阶段；88材料/23依赖。逐行组隔离和6设备×两类覆盖，DTE/SLAD/TabM整轮及全验证计时；资源探针用完整FIT，验证有重叠，仅计时不选模。TabM/DTE同进程optimizer/RNG/游标回放本地通过，跨进程和其余方法资源门仍待补。正式执行版仅全部门满足后放行，主模型不改、大工件留超算。见[启动回执](collab/20261107_baseline_split_resource_launch_codex.md)。

---

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

用户要求暂不改模型，已固定FUSION790＋完整历史参考＋C5_3D_OLD的权重、阈值、尺度、半径和参考身份。生成主结果、二维/三维×尺度消融、四组前端RAW、历史覆盖对照及全种子/设备/全视图附录，共936条完整指标与112条前端指标，1253项构建核验通过。A/B开发评价与Edge未参与开发的外部评价角色和未达标边界保留；下一步先准备公平基线执行卡与真实预检，同时核验未消费外部数据资格，随后补统计与端到端开销。本轮无训练/推断/新作业。见[冻结整理回执](collab/20261107_paper_method_freeze_and_experiment_plan_codex.md)及[论文结果包](../paper_results_freeze_v1_20261107/PAPER_RESULTS.md)。

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
下一步：建议固定编码器，源侧构造因果8维，比较782/8/790维及固定误报预算；先RAW，再单独检查C5撤警。新训练未启动，Edge未参与开发，作为跨数据集外部评价。

完整证据与限制见 [诊断验收报告](collab/20261105_context_separability_acceptance_codex.md)、`runs/context_separability_v1_20261104/FINAL_ACCEPTANCE.json`。正常UDP只有497条、单设备和不同采集文件混杂仍存在。大文件继续留超算；未新增小anti复核。

---

## 2026-11-04 单包消融与跨连接可分性诊断已交付

结果：本地原包/数学/分词检查 PASS；真实 Linux 预检 182279 COMPLETED/0:0（1分10秒，MaxRSS 1,465,692 KiB）；完整诊断作业 182280 已自动提交并运行。
影响：固定 200 条 UDP 配对干预及 Edge 60k 查询的 1s/10s 八维统计；冻结模型、阈值和历史正式结果不变。此为机制诊断，不是修复后性能验收。
下一步：读取 `runs/context_separability_v1_20261104/REMOTE_STATE.json` 与最终两类 SUMMARY；核对 `ARTIFACT_ACCEPTANCE.json` 后判断修复方向。

用户要求大文件留超算、可见进度；已实现 http://127.0.0.1:18804/ 。普通程序同步，助手不守候轮询。执行 1 CPU/8 GiB，预检15分钟+完整105分钟，无自动重试。源数据/窗口/抽样固定，Edge未参与开发，作为跨数据集外部评价；完整同协议及分段对照，正常UDP 497条。用户准备下周开始论文，不为赶时间省略对照。详细设计和解释边界见 `runs/context_separability_v1_20261104/README.md` 与 `PLAN.json`。

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

# Mainline Handoff

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

## 2026-11-03 当前接手

当前唯一方法为冻结C5/p=3，A/B为开发证据。181418同运行时真实切片已验收通过；完整Edge worker/原子批次恢复/正式统计已实现，本地检查通过，尚未生成外部效果。新worker的Linux冻结encoder恢复、UDP末段资源和batch16/大库吞吐仍待一次有界工程验证，不能沿用旧小切片PASS宣布正式就绪。小anti按[新复核请求](collab/20261103_edge_formal_worker_and_budget_review_request_codex.md)核对执行卡后再申请具体资源授权；本轮未提交云作业。正常/HTTP/UDP各20k、原4,124参考及原seal保留，预算未锁，不自动重投。入口详见[五项当前状态](NEW_CHAT_START_HERE.md)；下方均按各自日期作为历史记录。

## 2026-10-28 最新接手：P1失败小诊断完成，原QP/QG不直接升级A/B

最新背景与10月25日后完成链见[接手入口](NEW_CHAT_START_HERE.md)顶部；本轮见[诊断与下一步判断](collab/20261028_p1_failure_diagnosis_and_direction_codex.md)。P1原SOURCE_SIGNAL_FAIL保持，48报告精确复现、69原文件SHA未变；G0缺跨设备近边界攻击保护，G1共享1.96%仍为单折信号。原共享QG家族同当前B分数无2%/99%联合解，不宜原样A/B。下一版先设计有折外困难攻击保护的条件修正；0新阈值选择/训练/前向/距离/A/B加载/远端任务，P2/P3未启动。当前密参考A/B仍3.993482%/100%和9.519654%/99.966594%，下方10月25日“最新”为历史快照。

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

**10月24日19:11历史启动快照：独立 V4 已按用户“可以动手运行。”授权正式启动，当时运行正常。** 19:08:45启动，root `/srv/paper04/learned_onboarding_20261024_v4`、unit `paper04-learned-onboarding-20261024-v4`、InvocationID `226cc64bb84747518f72afe05abe1969`。19:11:12验active/running、NRestarts=0、无异常；真实Python3.9下63项及adapter另4项通过；tests／prepare／validate／preflight完成，已进入fit，未观察optimizer更新数。正式preflight READY／规模证明VERIFIED，估计7.172 GiB；启动RSS峰值4.617 GiB，原16 GiB硬限／8 GiB守卫／4线程／单worker／零自动重试保持。新701件身份已核，12源与已验修复一致；V1-3保留，页面已切V4。见 [执行复核](../learned_onboarding_v1_20261023/memory_revision_v4_20261024/deployment_20261024/EXECUTION_REVIEW.md)／[执行回执](../learned_onboarding_v1_20261023/memory_revision_v4_20261024/deployment_20261024/EXECUTION_RECEIPT.json)。普通程序继续完整链，科学FAIL继续配对，技术异常停链，不持续AI轮询。下方停止／待部署是历史修复快照，三模块／CAL／A/B科学结果仍待。

**10月24日最新修复验收：进度页已修复上线，V4 源侧完整规模验证及实际 preflight 均通过；正式 V3 仍异常停止，未重启。** 页面明确显示外层终态、停止时间／原因、进程、完成与未完成阶段，worker RUNNING 标为快照；独立修复验证不覆盖正式停止状态。V4 共享任务记录和元数据；617,908 条 FIT／1,206,882 条任务实测峰值 5.839 GiB，旧／新任务 JSON、H、采样及批次对照通过。实际预检 READY／完整规模证明 VERIFIED，估计峰值7.169 GiB，保留原8 GiB守卫；真实Python3.9下63项及adapter另4项通过。生产更新／CAL评分／目标读取均0，26件原V3资产身份未变。源困难信号 READY 是训练资格，不是科学收益。正式V4部署配置／manifest尚未准备，不可复用复制来的V3部署身份启动。见 [修复说明](../learned_onboarding_v1_20261023/memory_revision_v4_20261024/MEMORY_REPAIR_REVIEW.md)／[修复回执](../learned_onboarding_v1_20261023/memory_revision_v4_20261024/REPAIR_RECEIPT.json)／[页面验收](../diagnostics_d1_d2_v1_20261022/PAGE_REPAIR_CARD_ACCEPTANCE_20261024.json)。下方均为各自当时快照；不持续AI轮询。

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

## 2026-10-24 稍早完成回执：现代头与 v3 全链完成，低误报目标仍未达到

依用户截图做了一次终态和小报告验收：14/14、failure=null，原 systemd 成功退出。MLP／TabM／LightGBM 三 seed 及各自 OLD_BANK/B0/B1/B2 配对全部完成；科学门槛均 FAIL，96 份配对报告均记录零新增攻击漏检。B2 ensemble 加权 FPR（A/B）依次为 5.74266%/15.21880%、6.14519%/19.96197%、8.32616%/20.31610%；TabM 源保护 λ=0。见 [完成复核](../modern_head_new_lineage_v1_20261022/analysis/completion_review_20261024/RESULT_REVIEW.md)。113 个约 12 MiB 小报告已回传验 SHA 和完成链，完整模型／预测备份待完成。本轮无新训练或作业修改；学习式 V1 代码交付仍有效、真实训练未运行。下一项是落实独占环境并做其资源 preflight，无需继续等换头。下方“现代链待完成”保留为历史状态。

## 2026-10-23 历史实现回执：学习式入网 V1 实现与工程验证

新实现见 [README](../learned_onboarding_v1_20261023/README.md) 和 [implementation_manifest.json](../learned_onboarding_v1_20261023/implementation_manifest.json)。已实现源专用适配、两辅助头、三修正器、FIT-only 困难任务、源 CAL 保护、v3 单列对照、40 主项及 EMPTY／WRONG 控制；合成测试覆盖完整训练与 no-op 分支、回放及身份／数值／角色负例。真实源身份和 33,147 条 CAL 正常旧阈值回放通过；具体源码身份、最终测试数及全量源资格以新回执为准。

本轮没有真实模型优化、CAL 攻击 λ、A/B 新评价、远端连接、作业变更或 AI 轮询。真实折外困难信号、资源、收益和参考归因仍待执行；生产目标 manifest 未装配。冻结规格及旧六准备文件保持不变。下方“尚未实现”是此前方案交付快照。

## 2026-10-23 历史方案交付：方案已定，待 Sol 实现

用户指定 astra 制定方案、sol 后续实现。本轮完成 [冻结执行规格](../learned_onboarding_pilot_v1_20261023/EXECUTION_SPEC_V1.md)、[协议审查](../learned_onboarding_pilot_v1_20261023/REVIEW_V1.md) 和 [实现交接](../learned_onboarding_pilot_v1_20261023/IMPLEMENTATION_HANDOFF.md)，身份与未执行项见 [方案回执](../learned_onboarding_pilot_v1_20261023/PLAN_RECEIPT_V1.json)。正式 QUERY_TAIL seed27 复用；两辅助头按六源设备三三互换产生头层未见设备任务，三个修正器比较普通／困难训练和给定资格后的参考内容贡献。最多五终点，单 seed，无新集成；这不是旧四设备主头加外层验证的五终点草稿。

FIT-only 中心/尺度、50维输入、有限残差损失、最坏合法源 bank 攻击保护、完整 A/B 四库配对与失败规则均已冻结。当前只有设计和既有结构审计，尚无新实现、辅助头、H 或模块结果；q14 身份、帧因果资格、真实困难信号和资源待执行验收。旧外层划分的7个共享捕获不套到新分组，新分组依赖交叉待统计。现有现代链、进度页和远端作业未操作；本轮不查实时状态。以下准备段是此前快照，“配方尚未冻结”以本节及新规格为准。

## 2026-10-23 学习式入网：源侧准备开始，尚无新训练

**同日后续澄清优先：** [数据用途说明](../learned_onboarding_pilot_v1_20261023/DATA_USE_CLARIFICATION.md)。主方案沿用源 FIT 拟合、CAL 校准、目标正常参考入网、A/B 查询评价；源 FIT 同时服务检测头和修正器本身合法，可复用适配的已有头。下述五终点内部留设备先导是困难样本构造/额外验证的候选，不是整条主线必经前置；不能把其捕获交叉解释成原 FIT/CAL/A/B 隔离失效。此前没有新模型拟合，因此本次纠正不需要撤销或重跑实验。

用户要求不把换头完成作为学习式入网准备的前置条件。本地已完成源LEARN/FIT/CAL及参考结构审计，12项边界测试通过，并形成最多五个新训练终点的先导设计草稿；见 [准备回执](../learned_onboarding_pilot_v1_20261023/README.md)。104条源参考、六台源设备，但拟定开发侧满足双组件条件的任务主要来自SimCam/ArloQ；外层可受修正影响的攻击主要在Philips，且外层/开发共享7个原始捕获。统计为时间条件结构上界，尚未完成帧因果装配，不称精确v3资格、独立跨环境确认或已有学习收益。当前未拟合、未排队、未读远端状态，原九头及其全部v3配对继续按原合同；具体配方、数据装配和训练资源仍待就绪。用户当前几轮不需要DS转发文字。

## 2026-10-22 最新接手导航：固定诊断完成，现代头正式链已启动

**新对话先读 [NEW_CHAT_START_HERE.md](NEW_CHAT_START_HERE.md)。** 本节整理本地验收回执，本次未查询远端实时进度。下方历史“当前／未运行”不代表最新状态；冻结协议保留，执行事实以最新回执和对应产物为准。

- 冻结前端 1,095,200 行已完成、验收、本地备份，无需重建。QUERY_TAIL 十二头及其完整 v3 入网四策略已完成并备份；误报有改善，科学门槛仍 FAIL。
- D1/D2 已结束：D1 在 B 新增 26 条集成攻击漏检，FAIL，不加入换头矩阵；D2 四材料 NOT_EVALUABLE，0 拟合，不阻塞固定换头。
- MLP_QUERY_BCE／TabM／LightGBM ×3 seed 及同一 v3 几何入网 OLD_BANK/B0/B1/B2 正式链已启动，最终结果待完成。见 [README](../modern_head_new_lineage_v1_20261022/README.md) 和 [启动回执](../modern_head_new_lineage_v1_20261022/LAUNCH_RECEIPT.json)。正式本地包 `package_v2`、远端部署 `..._20261022_v2`、输出仍 `..._20261022_v1`；旧 OPERATE 首版命令不可照抄重提。
- 用户固定要求 AI 不持续轮询，普通进度页 [18765](http://127.0.0.1:18765/) 展示。有代码／分析／集成任务继续做。自动停机未启用；现代结果待完成后核算空间、验收拉回。学校超算当前暂缓。

下方保留历史；现代头启动详见文件末尾 2026-10-22 执行回执。新状态同步本导航和接手入口，避免只写底部。

## 2026-10-21 HPC recheck blocked before Python/model execution

Login node168 remains reachable, but Slurm job178526 on compute node185 timed out without a first batch receipt. Independent startup diagnostic178527 on node186 passed shell/hostname/date, then hung on stat of shared project/Python paths; FAILED137:0, batch MaxRSS3M. Both nodes were drained with Kill task failed. The affected /public versus /share mount remains to be isolated by administrators. No further nodes were tried; user queue is empty. Cloud work was unchanged. No cross-environment E3 reuse gate passed; P-only adapter remains an unverified draft. See [diagnosis and administrator request](../hpc_e3_recheck_v1_20261021/FAILURE_178526_178527.md).







## Current Mainline Control Panel

### 2026-10-22 诊断规格复核：D1单条位置规则、D2双域分组验证已明确，未执行

已读DeepSeek追加复核并形成[首轮登记稿](diagnostics_d1_d2_spec_v1_20261022.md)与[逐项回执](collab/20261022_additional_ideas_review_response_codex.md)。D1固定组件等权中位数位置修正，min8/ESS8、源锚点排除本模拟设备、MAD只描述、原cut不变；复用源FIT尺度而不用FIT效果选规则，固定lambda候选仅按CAL攻击全额封顶压力检查逐seed/ensemble零新增标定。源≥8本设备库仅ArloQ TCP8/SimCam TCP8/Amcrest UDP63，源覆盖限制明确；无参考/证据不足回退原判。

D2纠正“只源训练、只目标验证”：域二分类训练和AUC验证都必须包含两域，先各域按组件/捕获时间块连通组划分，后合并两域对应折。固定L2逻辑回归、3折、seed27、每域≤10k组件代表，最多36次小探针拟合；不称全链路独立验证，不按AUC取消换头。后验参考代表性差不删设备、不缩分母、不把已执行FAIL改成整体NOT_EVALUABLE。此次仅文档与源参考计数核对，未实现、未运行、未访问云端；实际输入/分折清单仍须执行前封存。

### 2026-10-22 方案增量：纳入参考分数校准与正常域可分性诊断，尚未运行

按用户转来的DeepSeek文档继续方案协作，接受优先加两个低成本、有终点的诊断，再结合固定换头/同模块结果决定分支。参考校准先核正常参考代表性与稀疏统计，再评价一套源侧封存规则；不把目标查询用于拟合/调参，不直接串联几何修正。域诊断限一种线性探针、E3/q14/拼接、A/B分别、组件/捕获隔离及有界抽样；高AUC不证明换头无效，低AUC不证明无域差异，不用0.8作取消候选的门槛。无参考仅约束当前模块，不约束新头可能修正的基础误报。

当前参考头分数不能默认已保存，未来可能只需小批冻结头前向；域探针有少量训练，不能写零算力。未运行任一诊断、未改实验包、未访问云端。阶段阈值/滚动库/学习修正仍暂缓。见[文档回执](collab/20261022_additional_head_module_ideas_response_codex.md)及[更新方案](next_head_and_onboarding_plan_20261022.md)。以下“DeepSeek讨论未重启”为更早状态。

### 2026-10-22 方案讨论：不以当前FPR达标阻塞换头，先完成有限的联合比较

用户要求仔细思考下一步方案，尚未启动新实验。建议“一次已有结果复盘＋同缓存MLP_QUERY_BCE/TabM/LightGBM固定三seed比较＋预登记同模块四库配对”，保持已完成QUERY_TAIL完整方案为锚点。当前头和B2资格不变时，即便消除资格内全部误报，A/B加权FPR仍至少5.64014%/7.35325%；不能只加修正强度等到1%再允许换头。这是事后乐观范围边界，不是新头能力上限或新门槛。

原现代合同模块名单仅TabM/LightGBM；讨论稿建议补MLP_QUERY_BCE配对作为损失/架构对照，无额外训练终点，需先另立补充登记。新重建谱系适配及v3因果检查仍需接入，旧包不能原样改pin运行。所有预定候选完成配对后依据A/B联合效果、攻击保护和残余误报位置决定是否进入学习参考模块或表示/训练覆盖改动；不无限调当前头，也不同时改前端。详见[方案讨论稿](next_head_and_onboarding_plan_20261022.md)。此项不是用户已批准的执行合同；原包/实验结果不改，DeepSeek讨论未重启。

### 2026-10-22 当前：修复头＋入网全部完成并本地备份，降低误报但尚未达标

v3终态COMPLETE/failure=null，四策略OLD_BANK/B0/B1/B2的两池真实评价齐全；911,288,320字节（0.849GiB）结果已本地回传、SHA通过，普通备份监听终态退出。固定QUERY_TAIL头、原阈值和集成不变，源CAL选lambda=0.25，参数更新0、未按目标选模型。

固定集成加权FPR：头单独A/B=6.15818%/23.65666%；OLD_BANK=5.59506%/18.94770%；B0=6.14371%/18.94770%；B1=6.14371%/18.94921%；B2=6.14371%/16.59348%。B2在B修正6,933条误报，加权FPR相对下降29.86%；A新三策略均只修正1条。B2按条数FPR为A0.37985%、B30.76832%，不能混用口径宣布达标。2池×4策略×3seed及集成共32报告均零新增攻击漏检；集成A攻击召回100%，B加权99.99463%，保留原5条漏检。

四策略科学判定均FAIL：池FPR1%及部分设备FPR2%未过；三设备回归缺失，独立确认未运行。A新库仅覆盖原加权FP的8.4122%资格、0.4699%正支持；B2对应68.9168%/53.1143%。B攻击TP资格约60.0032%但正支持0，零新增漏检的验证边界须保留。只汇总官方报告和内部一致性，未宣称本轮独立重算全部分数。新重建谱系不能冒充历史父缓存逐位等价。

完整结果见[入网结果初评](../onboarding_new_lineage_v1_20261022/analysis/RESULT_REVIEW.md)及[备份回执](../onboarding_new_lineage_v1_20261022/RESULT_BACKUP_VERIFIED_v3.json)。未启动现代头或新实验，DeepSeek讨论仍暂停，学校超算未操作。自动停机未启用；结果已备份，可由用户手动节省停机，磁盘继续计费。以下运行条目均为历史状态。

### 2026-10-22 当前：入网全参考库已完成，v3修复观察期重放校验后仅接续评价

v3正式运行已越过原失败点：源校准完成，CIC/B0已生成真实报告、分数和判定，179,886条固定查询保留，三seed与集成新增漏检均0。其余策略/池继续；全系统效果待完整结果，不提前宣称通过。

v2已完成2捕获全解码及6组真实参考E3，评价在REFERENCE_QUERY_UID_OVERLAP停止。真实盘点CIC B0/B1各63、B2 64个重叠；UNSW B0/B1无、B2 19个；全为同池、同正常端点且早于库截止。原协议要求早期固定查询保持头判定，但旧实现先一概禁UID重叠，形成校验冲突。v3新增身份/时间审计，仅允许目标B0/B1/B2观察期重放并强制support0/不匹配/原判定；源角色与OLD_BANK仍互斥，固定查询/权重/参考选择/校准不变，不删样本不换UID。

97项测试通过，含无重叠时全流水线分数/决定/源校准逐字节不变。92个完成文件逐项封存后复用，新unit `paper04-onboarding-20261022-v3`仅evaluate；不重做解码或E3，旧失败现场保留。18764已切v3，备份独立pullback_v3。后续现代头应使用repo/ood新增core_v3/runner_v3。详见[v3修复与边界](../onboarding_new_lineage_v1_20261022/fix_v3/README.md)。

### 2026-10-22 当前：入网 v1 的 root 解码警告已修复，v2 独立重启

正式v2已通过原失败点：CIC全部645,951包参考准备COMPLETE、stderr0，正在raw-UNSW_DEV；回执已拉回fix_v2/CIC_raw_complete.json。不是仅提交成功。

两份正常捕获全部上传并验SHA通过。v1在raw-CIC_DEV退出，TShark返回0但stderr含唯一root身份提示，被旧严格空stderr检查拦截；此前已完成的头回放和其他缓存有效。修复部署层的raw子进程为uid/gid65534、无附加组，设置新运行内只读空WIRESHARK_CONFIG_DIR；科学解码器/字段/模型不改，不忽略错误。目标93项回归通过，A/B各64个真实包的56字段逐字节一致、stderr0；离线解码首选项一致。v2 `paper04-onboarding-20261022-v2` 已提交，8核/16GiB不变；旧现场保留，上传/查询E3/头无需重跑。18764已切v2，结果独立回传pullback_v2。见[修复及验证记录](../onboarding_new_lineage_v1_20261022/fix_v2/README.md)。无自动重试、无自动停机。

### 2026-10-22 当前：先接既定入网模块，真实回放通过，等待正常参考数据上传后自动运行

用户明确暂缓 DeepSeek 方案讨论和现代替换头，先评价完整结构；已手动启动代金券实例。新谱系适配包 `onboarding_new_lineage_v1_20261022` 已部署，原封存入网算法/协议不改。目标环境92项测试通过；CAL/CIC_DEV/UNSW_DEV的QUERY_TAIL三seed与集成分数及决定逐位复现，同缓存RECENT对照、源FIT617,908行与104源参考验证通过。历史父缓存等价仍不可核验；不冒充旧Job177891。

服务 `paper04-onboarding-20261022-v1` active，当前WAIT_RAW_UPLOAD；两份正常捕获共4,308,928,187字节上传中，文件齐全并SHA验证后自动运行原OLD_BANK/B0/B1/B2两池对照。复用完成的查询缓存和修复头，无百万查询重提取、无参数更新；8核/16GiB，应用RSS14GiB保护、串行阶段、零自动重试。92项生成测试及全量真实回放证据已回传本地。三设备回归缺失时不得完整系统PASS，零新增漏检仍为系统验收门槛。

18764页面新增完整方案进度卡，普通程序60秒同步；终态后自动拉回入网输出、验SHA并保存最终退出回执，不重复下载缓存/权重。上传与备份需本机联网，计算独立运行；自动停机仍未启用，用户手动节省停机。详见[当前运行说明](../onboarding_new_lineage_v1_20261022/README.md)。以下诊断条目为历史状态，不能把单独头结果当成完整系统最终结果。

### 2026-10-22 UNSW高误报已分层诊断，方案交DeepSeek文档复核

用户要求先分析后讨论，不启动新实验。三池16输出/96加权指标独立复算一致；B主方案TCP占FP84.01%，TCP_OTHER占加权FP74.35%，五设备TCP均变差。源FIT有47,802条正常OTHER，TAIL概率持续关注此阶段；同阶段源CAL正常分数中位-42.1121、B为-22.6013，显示正常侧迁移问题，具体表示/头机制尚未证实。精确事后ROC证明当前固定四臂单一全局阈值均不能同时达到B加权FPR≤1%/召回≥99%；R3的1%点最高召回95.2053%，不能当部署阈值。旧reference_available范围即使完美修正，R3 FPR乐观下限仍6.9893%，不是新库实测资格。B攻击全为当前SYN_NO_ACK，不能据此放行其他阶段。建议新库资格普查＋同缓存现代头/受约束模块两路线，需显式新重建谱系适配；方案未实现未运行。已在[DeepSeek讨论发起文档](collab/20261022_unsw_high_fpr_diagnosis_and_plan_codex_to_deepseek.md)留5项问题，尚未收到其回复。完整诊断在query_tail_ecs_v1_20261022/analysis，原封存结果未改。

### 2026-10-22 QUERY_TAIL运行及本地备份完成，误报目标未通过

12头/40轮/1,158,720更新全部完成，零重试，约37分钟；结果与最终state归档本地SHA校验PASS。固定集成加权FPR：同缓存RECENT基线CIC 5.76093%、UNSW 21.28324%；主QUERY_TAIL为6.15818%、23.65666%，均未达到1%且比基线上升。主方案加权攻击检出率CIC 100%、UNSW 99.99463%。保留负结果，不挑seed、不切换到按条数口径宣布通过。本轮入网模块/现代替换头未运行，历史留出仍关闭；未操作云端电源。详见[结果初评及四组对照](../query_tail_ecs_v1_20261022/analysis/RESULT_REVIEW.md)。下方启动记录为历史状态。

### 2026-10-22 QUERY_TAIL同缓存12头已正式提交，现有页面展示进度

用户授权下一步且不需AI持续轮询。复用已封存new_lineage_query_v1/service与QUERY v2r3科学代码，部署SHA通过；64条真实源FIT、四组各一隔离优化步/梯度探针通过，目标57项生成回归测试通过，原服务环境/缓存/资源预检PASS。绑定已本地完整验收缓存marker `0185757a…d9b1`，新同源R0三头＋候选九头，四臂三seed/40轮/1,158,720更新保持。正式unit `paper04-lineage-03ab64a6c75e94331e1b` 已一次启动、active/running；确认进入P_NEW_QUERY_DESCRIPTORS，114,688/1,094,929行，非重做E3。20GiB/16CPU/三worker×四线程，零重试；尚无训练完成或效果结论。原18764页增加P/T/K和12头逐头进度，普通程序每60秒同步；终态后自动拉回完整结果和最终state并验SHA，不重复下载缓存。自动停机仍未启用。学校超算不操作。见[正式实验与进度入口](../query_tail_ecs_v1_20261022/README.md)、[提交回执](../query_tail_ecs_v1_20261022/submission_receipt.json)。

### 2026-10-22 完整本地备份及全量验收 PASS，前端缓存恢复完成

最终 COMPLETE_LOCAL_CACHE_VERIFIED 为 PASS：原448个归档对象及新增626个对象全校验通过；三worker各357块，共1,095,200行，全部UID/role/slot、26维状态与P逐行一致，794维分块值与合并NPY逐字节一致且完整覆盖。P共68,518批，原批次划分通过；两套源FIT归一化器已在云端按原函数精确复算并绑定本地文件SHA。最终回执、远端验收报告、导出目录及本地完成marker的摘要绑定已复核。P和最终特征已恢复至 `ecs_cache_resume_v1_20261020/verified_cache_20261022`，worker分块保存在已核验归档中。完整本地备份确认通过，不再等待下载。后续为同缓存R0/QUERY_TAIL训练入口适配和小样验证，再按既定四臂三seed配置实验；本轮尚未启动训练或更改云端电源。旧超算父缓存逐位等价仍不可验证。见[最终验收回执](../ecs_cache_resume_v1_20261020/deployment/acceptance_20261022/COMPLETE_LOCAL_CACHE_VERIFIED.json)。

### 2026-10-22 完整缓存生成，云端验收通过，本地备份与全量恢复验收中

云端 COMPLETE 1,095,200行，主服务/三worker退出码0。只读验收五角色794维特征、封存SHA和原始划分通过；768/794维normalizer仅源FIT617,908行调用原函数复算，均值/尺度字节全同。原P与447旧块共448个备份对象已重核SHA通过。复用既有下载监听补齐本轮5.41GiB归档；本地完整验收尚待下载后自动执行，不得宣称已全部备份。磁盘核算通过，现有18764页新增独立备份进度条，后台验收核对全量P身份/状态/最终合并值及完整覆盖；最终以PASS回执为准。用户将带宽调为10Mbps，不需AI持续轮询。没有启动训练或操作超算/停机。见[验收进度与操作记录](../ecs_cache_resume_v1_20261020/deployment/acceptance_20261022/README.md)、[动态状态](../ecs_cache_resume_v1_20261020/deployment/acceptance_20261022/status.json)。

### 2026-10-21 17:40 云端已回传特征检查通过，学校超算暂缓

按用户要求暂缓学校超算，保持代金券云端任务。v3 三 worker 实测持续推进，检查结束 751,970/1,095,200 行（68.66%，含导入458,112行），无 cgroup OOM/CPU throttle。固定快照的281个本地新增块、287,794行全部重核归档与成员SHA，并调用真实恢复读取器检查794维float32有限值、UID摘要、角色/slot及去重；27行源P身份/状态抽查通过。没有重启或改实验、重算编码器。完整合并/归一化和最终训练入口仍待验收，不能声称完整缓存或检测效果已通过。见[健康检查及边界](../ecs_cache_resume_v1_20261020/deployment/RESULT_HEALTH_REVIEW_20261021.md)和[逐块证据](../ecs_cache_resume_v1_20261020/deployment/SAVED_BLOCK_AUDIT_20261021.json)。

### 2026-10-21 速度核查：E3约61.6%，接续区段单条输入更长

当前v3三worker持续运行。旧有效历史平均约12.21行/秒，新续算平均约5.58行/秒；封存SQLite核实旧保存前缀平均约227 token/行、新续算段约487，当前shape为730。条数进度不等于计算量进度，不能按前半段平均继续沿用“余下15小时”。5秒样本无CPU quota throttle/steal、OOM或明显I/O等待；不同shape并非同批机器性能对比。本轮只读诊断，未改/重启实验或备份。见[速度核查](../ecs_cache_resume_v1_20261020/deployment/THROUGHPUT_REVIEW_20261021.md)。

### 2026-10-20 当前：P/旧块导入和36批次回放通过，v3已续算E3

23:14实际 `RESUME_GATE_PASS=PASS`，三worker固定36批次float32逐字节一致；回执本地按gate验SHA通过。主服务已进入run，三个worker均 `E3_REMAINING_BATCHES`；观测458,256/1,095,200行，超过已导入458,112行，约41.84%。已正式接续缺失E3，非重做P或从零重算。新增块增量导出/回传继续，完整缓存尚未完成。见[真实回放证据](../ecs_cache_resume_v1_20261020/deployment/target_replay_v3/RESUME_GATE_PASS.json)及[启动观测](../ecs_cache_resume_v1_20261020/deployment/post_fix_snapshot.json)。

两处部署问题已定位修复：v1遗漏缓存父目录；v2完成导入后发现systemd PATH遗漏已安装TShark，尚未创建target.json即退出。原P的1,095,200行及447旧E3块/458,112行导入核验通过。补齐PATH后，原目标CPU/版本/数值环境比较通过，11项本机/目标部署测试通过。冻结恢复包、科学门槛与数据不改。

v3显式绑定既有IMPORT_COMPLETE的SHA，核实v2终态和无目标/计算声明后从validate接续，未重传/重导入或删除标记。主服务 `paper04-coupon-resume-20261020-v3.service`，InvocationID `4420fc5662234af9b5b30c827a4b6351`；run沿用v2已验证导入，state/exports及本地 `local_resume_backup_v3` 独立。18764及备份监听已切换，旧失败现场保留。固定5Mbps、20GiB/16CPU和用户手动节省停机不变。见[完整修复记录](../ecs_cache_resume_v1_20261020/deployment/README.md)。

### 2026-10-20 历史：上传全验通过，目录初始化修复后v2正在导入

916文件约6.71GiB已全部上传并远端SHA通过。首次v1报 `NEW_RESTORE_OUTPUT_REQUIRED`：部署遗漏创建 `/srv/paper04/cache` 父目录，restore尚未写输出即退出，数据无损。已补父目录初始化与已有结果保护，8项部署测试在本机/目标均通过；原冻结包和科学门槛不改。旧失败现场完整保留，新服务 `paper04-coupon-resume-20261020-v2.service`（InvocationID `d198605e921b4b618f3897ad418999df`）23:08实际active/running并进入restore。回放通过后才接续缺失E3，不能提前声称已续算。

18764页面及增量备份已切到新尝试；本地新增结果在 `ecs_cache_resume_v1_20261020/local_resume_backup_v2`，旧v1备份保留。没有重新上传原P/E3/encoder，固定5Mbps及20GiB/16CPU约束不变，本轮仍需用户手动节省停机。见[修复记录和回执](../ecs_cache_resume_v1_20261020/deployment/README.md)。

### 2026-10-20 历史：代金券机上传中，自动接续服务已提交，本轮手动停机

用户手动启动代金券实例并批准接续；已确认 `i-0jlequa076yrk9p5wjet` / `8.130.103.183`，原环境与AMD EPYC7T83保留，固定5Mbps保持。原续跑包目标26项测试、新部署层5项服务边界测试通过。完整P＋447旧E3块＋encoder约6.71GiB正在后台上传，远端SHA齐全后自动进入restore→固定批次逐位validate→缺失E3。可复用原458,112行（41.83%），仍需真实目标回放通过，不把旧页面42.78%当已保存量。

主服务 `paper04-coupon-resume-20261020-v1.service` 已一次启动、active/running，InvocationID `060f814708b34e50abebc1bb5cc8e475`，目前 `wait_upload`，尚未进行E3生产续算。20GiB/swap0/16CPU实际约束通过；52h为含4h上传等待的服务停止上限，非ETA。独立导出与本地新分块下载监听已启动，原P/旧E3不重复下载。新[进度页18764](http://127.0.0.1:18764/)自动同步，不需AI持续检查。详见[部署说明与回执](../ecs_cache_resume_v1_20261020/deployment/README.md)。

**停机口径更新：**用户批准的最小角色创建被阿里云安全验证“未知错误”阻塞，未成功绑定。用户随后明确允许先不处理自动停机，故本次按 `MANUAL_USER_ACCEPTED` 启动。**自动停机未启用，作业结束/失败仍需用户手动“节省停机”；未使用旧实例角色。** 上传仍依赖本机联网；进入服务器计算后不依赖本机。完整缓存本地备份验证后再进行同缓存R0/候选；无新完整缓存或模型结果，科学合同未改。

### 2026-10-20 历史：代金券机 P/E3 续跑入口本地验收通过，目标回放待执行

用户授权实现“导入完整 P＋验证并接续 E3 分块”的方案和入口，优先接续代金券服务器，本轮没有启动实例或实验。独立包见 [ecs_cache_resume_v1_20261020](../ecs_cache_resume_v1_20261020/README.md)。本地真实导入已通过完整 P 的 1,095,200 行 / 68,518 批次身份与分组核验；447 个封存块（三个 worker 各149块）是原批次连续前缀，458,112 行（41.8291%）的 UID/role/slot、26维状态字节及794维有限值 schema 均通过；剩637,088行。页面最后42.78%不能替代实际本地41.83%。见[真实导入回执](../ecs_cache_resume_v1_20261020/local_restore_receipt.json)与[本地验收](../ecs_cache_resume_v1_20261020/validation.json)。本轮新建临时展开副本约6.05GiB仍在tmp/ecs_cache_resume_validation_20261020；清理命令被工具策略拦截，未删除。原P/E3备份保留。

新入口 restore→validate→run 保持原3worker×4线程和完整批次组成；目标同CPU代际、Python/包/Torch构建检查后，最多36个固定抽样批次要求float32逐字节一致，未通过不得混合或自动重算。通过才续缺失批次，原合并与源FIT normalizer不改；完整marker后先做本地备份，再接同缓存R0和候选。旧分块未带回的实际tensor逐条日志不补造，回执明确旧块与新前向证据边界。科学门槛、原包和数据不变。

26项最终合成测试在本机Python3.9通过，包含续算与完整执行逐字节一致及门槛拒绝；WSL仅bash/CLI入口通过，未声称真实目标已验收。目标16vCPU/32GiB，systemd上限20GiB、树RSS guard16GiB；48h为停止上限非ETA，余下E3约15h只是旧吞吐估计。部署前仍须上传备份/encoder、目标回放，并接新进度/导出与自动节省停机；旧RAM角色仅覆盖旧实例。固定5Mbps保持。**无新云作业、无完整缓存、无新模型效果。**

### 2026-10-20 历史：学校电力维护取消178456，资产保留，未重试

恢复路线补充：用户提醒阿里云完整P已回传后，重新核验本地P_STAGE的19分片SHA（约4.57GiB）、完整P回执（1095200行/219捕获）、固定inputs/设计/checkpoint及9个工程引擎身份，全部通过。下一步优先实现独立完整P导入→E3入口，以免默认重跑P；目标恢复后的SQLite/UID/token验证仍待实现，部分云端E3跨环境混用未验证。见[P复用评估](../hpc_frontend_compat_v1_20261020/ECS_P_REUSE_20261020.md)。

上传已全部完成；环境/真实流量小样通过后完整缓存178456于15:00:46启动，16:21:16被管理员取消。sacct=`CANCELLED by 0`；node185=`DOWN+NOT_RESPONDING`、`Power_maintenance_2026-10-20`。首次程序异常是SIGTERM，没有OOM/超时终态。停在P_DECODE_active-05（720896/815421包），尚未进入E3。源资产和约497MiB部分spool仍在，P无完成封存标记；现runner不支持直接中途恢复，不能把半成品当有效缓存。未扩大资源、未改科学代码、未重提作业。维护恢复时间待学校确认。见[排查与恢复边界](../hpc_frontend_compat_v1_20261020/FAILURE_178456_20261020.md)、[原始诊断证据](../hpc_frontend_compat_v1_20261020/failure178456_diagnosis.json)。

### 2026-10-20 历史：学校新环境小样通过，原始数据上传与前端自动接续已启用

用户补充授权：本次作为后续可沿用的新环境，不再以旧kitsune环境恢复为前提；空白超算重新创建工作区，先适配和运行冻结前端缓存。已新建 `/public/home/jiangxinwei.zr/work/paper04`，复用共享torch_demo_2025（Python3.11.11、Torch2.5.1、NumPy1.26.4）和共享TShark4.6.6；项目依赖在本机组装为独立vendor_py311，无远端pip/Conda安装或公共环境修改。旧3.9封存包未改，新环境建立独立缓存谱系，不能声称旧缓存逐位恢复。

新依赖、代码、encoder上传并SHA通过。**178437（amd/node185，4CPU/12GiB）环境与冻结编码器小样PASS**：Linux恢复测试21项全部通过；33行3次真实冻结模型前向及张量/批次输出一致性通过；完整1095200条固定元数据与生成归一化工作区通过。采样子进程树峰E3约1.50GiB，metadata/merge约5.02GiB，不是完整阶段峰值。详见[新环境与接续说明](../hpc_frontend_compat_v1_20261020/README.md)、[目标小样回执](../hpc_frontend_compat_v1_20261020/remote_probe_result.json)。

**两份原始数据包仍在上传；真实流量小样和完整缓存尚未完成。** 单次接续已启用，当前WAITING_RAW_UPLOADS：归档完整回执齐全→原始CIC/UNSW各16384包小样→检查Slurm成功终态/PASS/资源覆盖→完整缓存。完整作业12CPU/20GiB/3worker；280h为最坏shape停止上限非ETA；失败停止、不自动重试、不启动检测头。进度见[学校页面18763](http://127.0.0.1:18763/)，旧ECS18761不代表学校状态。上传依赖本机联网与VS Code SSH转发，计算启动后不依赖本机。前端结束后仍须完整本地备份，再按同一新缓存重训R0及候选，科学门槛不变。

### 2026-10-20 历史：学校软件复用核查完成，项目固定 Python 包待补齐

**后续补查已收敛**：检查142个module文件及新增6个教学环境，未找到匹配基础环境；没有重复原22个Conda环境检查，也未新增作业/安装。现需学校提供等价受控基础环境或恢复入口（Python3.9、NumPy2.0.1、Torch2.5.1、pandas2.3.3、dpkt1.9.8）。前端vendor/权重本地已备份、共享TShark可用；不要求管理员重新安装所有前端包。见[补查记录及管理员请求](../hpc_restoration_check_v1_20261020/environment_checks/ADMIN_ENV_REQUEST.md)，尚未代发。取得入口后做计算节点实际导入/小样验收，再恢复输入重建缓存；暂不修改模型。

学校Python **3.9.5**（`/share/software/anaconda3/envs/r-reticulate/bin/python`）及共享TShark **4.6.6** 已在amd/node185验证。TShark计算节点缺libpcap的问题复用历史CST共享库修正，ldd、版本及生成单包解码通过，无需重编译解码器或另装解释器。三个小诊断178419/178420/178421均COMPLETED/0:0，无遗留诊断，不是完整项目环境验收或科研实验。

22个公共Conda环境元数据检查未找到完整项目组合；公共Torch_demo为Python3.11/NumPy1.26.4/Torch2.5.1，不能放宽项目Python3.9/NumPy2.0.1门槛来采用，也不能据此断言学校所有位置均无所需依赖。用户提醒后核回 `ckbe_hpc_py39_fix_20260712.md` 的历史禁止用户自管安装记录，**撤回直接新建venv补包安排**；先确认学校现行受控环境/离线源及旧kitsune_py39替代或恢复入口，按平台允许方式处理，不自行pip/建环境。本地匹配vendor_py/dpkt只是可用恢复材料，不构成上传/安装许可。本轮未修改公共软件、安装包、上传科研输入或开始正式重建/训练，云任务和计费未动。见[软件核查及修正路线](../hpc_restoration_check_v1_20261020/environment_checks/README.md)、[转录观测](../hpc_restoration_check_v1_20261020/environment_checks/observed.json)。

随后完整依赖/encoder生成前向、输入SHA、学校Slurm入口与合理资源绑定、真实小样通过后才重建完整新血缘缓存；完整缓存本地备份后跑R0三seed和九候选。云端systemd/cgroup入口不直接用于学校Slurm；已备份P/部分E3无直接续跑接口。科学版本、门槛和旧包保持封存。

### 2026-10-20 历史初查：调度可见，旧 work 尚未找回

用户随后确认旧硬盘已更换、旧资源已无，按**重建**安排，不再等待管理员找旧路径。已读用户提供的七页手册，修正环境表述：先核查并复用学校module/公共软件和项目依赖入口，不从零部署超算系统或擅自pip/重建环境；`miniconda3.2025`是手册模块示例，当前实际可用性待检查。随后恢复encoder、代码和固定输入，按新血缘重建/迁移完整缓存，备份后训练同源R0三seed和九候选。云端已备份P与部分E3保留；现有runner不支持直接恢复部分块，跨平台复用须另做适配和一致性校验。手册8CPU/32G/8h不是生产预算。见[手册阅读记录](../hpc_restoration_check_v1_20261020/HPC_MANUAL_READ_20261020.md)。本轮未执行远端环境变更或新作业。

用户已用 VS Code 登录 `school-hpc`（`jiangxinwei.zr@node168`）。实际 `/public` 已挂载 Lustre `/hpc2610`，但原 `/public/home/jiangxinwei.zr/work` 返回 ENOENT，主目录仅见基础隐藏配置；旧父 features、SQLite、encoder、环境及 raw 路径因此均不可读，没有进行或宣称通过资产 SHA 校验。迁移前目录及 `/share` 的已检查本用户常见路径也未找到旧主目录，尚不能断言永久丢失，需学校确认旧数据/快照/迁移位置。`sinfo` 可见 amd/gpu/intel 为 up 且有 idle 节点，不等于本账户提交权限或计算环境已验收。本轮未上传、安装、提交实验或操作云端任务；新旧血缘、合同 pins 和科学门槛保持。详见[只读恢复报告](../hpc_restoration_check_v1_20261020/README.md)及其中转录观测记录。

### 2026-10-19 新机增量：基础环境验收完成，已节省停机备用

用户已自行创建 `paper04-coupon-20261019`：实例 `i-0jlequa076yrk9p5wjet`，私网172.21.90.26，原公网8.130.103.183已因节省停机释放，重启后可能变化，须按实例ID识别。乌兰察布B，16vCPU/32GiB、200GiB系统盘、Ubuntu22.04。实际**固定带宽5Mbps必须保持**；此前10Mbps只是购买草稿。已通过Workbench免密root接入，未新设密码、SSH密钥或RAM角色。

环境v1已完成apt/uv，但GitHub的Python下载慢，主任务显式停止 `paper04-coupon-environment-20261019-v1`，保留v1日志；不是OOM或科学失败，没有环境成功回执。随后从旧机只读stream打包Python3.9.24与Wireshark4.6.6软件到本地，不含数据或venv；[软件归档回执](../ecs_migration_v1_20261019/coupon_environment_v1/software_runtime_from_verified_ecs_v1.tar.gz.receipt.json)记录67,940,751字节及完整SHA。

Workbench上传因浏览器扩展fileURLs未开放而未成功，未修改浏览器权限。改以旧机172.21.90.23→新机172.21.90.26内网单次软件stream：旧机仅在privateIP:18764服务，限制新机源IP及固定路径，完成即退出（exit0）；此传输未在旧机写文件或修改原作业。新机同SHA及安全解压到原 `/opt` 路径已通过。

`paper04-coupon-environment-20261019-v2` 已成功，final_exit=0，结束于07:15:39 UTC（北京时间15:15:39）；31个锁定包、Python3.9.24/CPU torch及TShark4.6.6通过。原waiter退出后，改用 `verify_and_export_resume_v1.py` 续验，07:16:57 UTC的实际AutoModel/AutoTokenizer额外导入验证成功。8份真实回执及证据bundle已保存本地，逐成员SHA通过，见[本地验收回执](../ecs_migration_v1_20261019/coupon_environment_v1/evidence/local_verification_receipt.json)。安装限8CPU/16GiB/2h只作软件安装预算；未传大数据/encoder、未加载科研资产或运行实验，旧机缓存作业及下方13:44/13:45证据不受影响。

15:20:08（北京时间）控制台明确显示目标实例“已停止+节省停机模式”，正常停止、磁盘及软件环境保留，已作为备用机；见[停机回执](../ecs_migration_v1_20261019/coupon_environment_v1/evidence/savings_stop_receipt.json)、[最终截图](../ecs_migration_v1_20261019/coupon_environment_v1/evidence/stopped_savings_mode.png)及[控制台快照](../ecs_migration_v1_20261019/coupon_environment_v1/evidence/stopped_console_snapshot.txt)。CPU、内存及固定公网带宽暂停计费，系统盘继续计费。现代检测头隔离环境仍DEFERRED；数据/encoder迁移、路径/资源binding、完整资产校验及新作业停机覆盖待做，旧机角色只授权旧实例。未启动新机科研实验；“代金券机”不表示已核实账单抵扣。

### 2026-10-19 当前增量：进度页已上线，阶段导出及缓存终态自动停机已启用

完整缓存重建继续运行。[进度页](http://127.0.0.1:18761/)每60秒通过SSH自动同步、页面每5秒读取本地快照，不调用AI，无需保持对话运行；重启入口为 `runs/ecs_migration_v1_20261019/progress_dashboard_v1/open_progress.ps1`。现有本地13:44:18（北京时间）快照为 `P_DECODE_active-04`，204,800/578,499仅指该捕获；P/E3尚未整体完成，检测头未提交。后续以页面实际观测时刻为准，不手工持续轮询。

用户已批准创建、绑定并启用最小停机角色 `Paper04EcsSelfStop20261019`。角色名和原主服务InvocationID核验通过，`paper04-cache-auto-stop-20261019-v1`一次提交后为active/running，[启用回执](../ecs_migration_v1_20261019/auto_stop_target_submission_v1.json)为 `ARMED`。仅监控当前缓存作业；成功或失败真实终态后，最多留30分钟备份窗口，再请求 `StopCharging`，不释放实例或删除磁盘。CPU/内存计算资源停止计费，ESSD等保留资源继续收费。API接受不等于已Stopped，SSH断连也不能直接判定停机。

13:45:18进度页已显示“自动停机已启用”，`WATCH_STARTED.armed=true`且守护unit active/running，[核实回执](../ecs_migration_v1_20261019/auto_stop_armed_verification_v1.json)及页面截图保留。停机守护在服务器运行，不依赖本机或对话在线；用户离开后终态仍可自动停机，回来可重新开机导出。后续12头作业提交时须将停机监控覆盖到对应最终作业，当前缓存守护不自动覆盖未来训练。

独立阶段导出及本地分片取回已启动，回执见 `stage_export_target_submission_v1.json`、`stage_fetch_local_submission_v1.json`；13:44快照仍为WATCHING、0包，尚不能声称已有真实缓存备份。远端每5分钟最多96轮（约8小时，另加打包时间）、总导出限24GiB；本地最多108轮（约9小时）、下载限8GiB，需本机在线。到期或限额退出，不无限监护。阶段包不等于完整缓存，完整缓存终态只生成容量报告，后续须按实际空间安排完整导出和SHA校验；只有完整本地校验ACK才能提前停机，否则30分钟到期保留远端磁盘后停机，未取回数据需以后开机提取。新血缘、原科学门槛、完整备份后再训练12头的顺序保持。

### 2026-10-19 13:15 历史增量：现有付费ECS已启动完整缓存重建，后续迁往代金券实例

用户明确要求先用当前已充值20元的实例推进实验，客服回复稍后提供；本轮不再等待代金券问题，也不创建或购买新实例。13:15:57（北京时间）一次性提交 `paper04-cache-rebuild-20261019-v1` 成功，systemd为 `active/running`。13:17快照仍在服务前置检查，正式cache目录尚未出现；不能把提交成功写成P/E3完成。运行证据：[提交回执](../ecs_migration_v1_20261019/cache_rebuild_target_submission_v1.json)、[单次状态快照目录](../ecs_migration_v1_20261019/validation/cache_rebuild_running_v1/)。

本次只重建固定五角色完整缓存，不训练前端、不提交检测头。沿用已过preflight的3worker×4线程、18GiB估计预算、16GiB进程树RSS guard及110GiB输出guard。新血缘仍为 `NEW_RECONSTRUCTION_LINEAGE` / `PARENT_PARITY_UNAVAILABLE`，不改旧包pins或科学门槛。顺序：缓存重建 → 完整缓存/快照/normalizer本地验SHA备份 → 同缓存3seed R0及9候选 → 入网/现代头适配。

迁移采用独立阶段封存/分片导出，不改正在运行的科学入口。当前runner没有断点恢复消费者：未完成的P必须重跑；封存P和E3块仅作为恢复材料，不能直接冒充完整缓存。完整缓存可跨主机消费，但新主机须重建外部路径binding和资源计划。当前D盘空闲约27.8GiB，完整cache含spool/blocks/证据，可能大于最终NPY的约3.24GiB；按实际字节核空间，不承诺整包一定装得下，不重复回传P/blocks/full或删除原始数据。公网出站0.800元/GB，回传也须计入费用；20元不是已验证的全程预算，余额耗尽不视作自动完成停机/释放操作。

### 2026-10-19 提交前历史：上传/解包完成，真实小样与18GiB资源计划预检通过

用户批准真实数据小规模资源确认。encoder、CIC/UNSW两归档全部上传并核SHA；原始数据安装完成，219/219捕获SHA通过。CIC `active-06`、UNSW mixed各16,384包试运行成功并回传链式校验：解码阶段约1.235/1.542秒，采样进程树峰约5.647/5.649GiB；UNSW触发current/legacy spill及legacy reload。短prefix不是完整捕获峰值/吞吐证明，UNSW前缀0目标不代表完整spool为空。

独立计划已生成：3worker×4线程、CPU容量字段16，P/E3/MERGE峰估13.5/14.5/约11.84GiB，20%一次余量后18GiB allocation、16GiB进程树guard、2.5GiB/worker guard；三个完整phase均ESTIMATED。新增输出disk guard110GiB、启动free最低120GiB；未新增磁盘或改变实例规格。280小时仅停止上限，保留原全最坏shape时间guard，不能视为ETA或实际费用。

相同计划以paper04用户正式preflight通过：1,095,200条、219捕获，`output_reserved=false`，未开始真实流量E3/完整缓存或头训练。首次预检因输出父目录未准备失败，已只补建 `/srv/paper04/cache` 并修正所属用户，失败回执保留，未重跑两prefix。计划SHA256：`bc2117446d634dc52326cb3d956d371dc8e1b000948f4e90acf0df0021f961c0`。

详见[资源确认及限制](../ecs_migration_v1_20261019/RESOURCE_CONFIRMATION_20261019.md)、[完整本地计划/证据](../ecs_migration_v1_20261019/validation/frontend_resource_plan_v1/resource_plan.json)、[最终预检](../ecs_migration_v1_20261019/validation/frontend_resource_plan_v1/observations/frontend_resource_preflight_v2.json)。本轮资源确认结束，未提交正式长作业；用户已让代金券问题等待客服，实际抵扣未明。后续完整缓存须先备份回本地，再启动同源12头，入网/现代头随后适配。下方早间状态作为历史保留。

### 2026-10-19 早间历史：ECS依赖与三个资源探针通过，待两捕获前缀和生产预算

用户补缴后原实例和专用SSH已恢复。Python3.9.24/NumPy2.0.1/Torch2.5.1+cpu及冻结前端依赖已装齐，TShark4.6.6核官方HTTPS清单SHA并独立编译成功；pandas2.3.3及导入依赖已补齐。环境v1的signature旧URL 404与v3成功续接均留回执，没有重装Python。encoder远端SHA通过，两份大输入归档仍在断点续传。100Mbps按流量峰值已获用户确认并在控制台实例表显示生效，截图/回执保留；不等于实际传输恒达100Mbps。

metadata_v1曾因loader错误要求179+92条正常参考含评价权重而失败，这不是OOM。独立工程修订recovery_payload_v1r1只纠正该角色校验，不补造原metadata字段；旧payload、输入和失败证据保留。新版已安装，目标完整依赖生成检查21/21通过，测试日志SHA及独立下载回执已核验。

成功探针已回传本地并核对marker/request/result链：完整metadata为1,095,200条、219捕获、FIT617908/CAL148819，内核进程HWM约5.33GiB；33行生成输入执行三次真实冻结E3前向，HWM约1.49GiB，真实流量前向为0；完整metadata加8192行生成工作区的merge-block通过，768/794维块约0.0312/0.0315秒，HWM约5.41GiB。**以上只是各探针实测，完整生产phase仍ESTIMATED；两捕获前缀及经审生产资源计划待完成，正式缓存重建、真实流量E3与检测头训练尚未开始。**

[迁移说明](../ecs_migration_v1_20261019/README.md)、[服务器实测](../ecs_migration_v1_20261019/server_inventory.json)、[恢复设计复核](../ecs_migration_v1_20261019/restore_design_review.md)。实测16逻辑CPU、约30.2GiB物理内存、约185GiB根盘空闲，Ubuntu22.04.5/AMD EPYC7T83/systemd249/cgroup-v2，无GPU。目标Linux服务36项生成测试、真实20GiB/16CPU cgroup smoke及三分片跨网备份演练已通过，演练只用生成数据，不代表生产缓存已备份。此前欠费停机、首次连接准备失败及5Mbps/100Mbps未提交草稿均属历史，不覆盖或删除。

父Job177891的三份主features、snapshots.sqlite和完整provenance未回传本地，不能只上传旧QUERY_TAIL包就训练。现从固定五角色metadata/完整FIT-CAL、保留的原始PCAP与冻结encoder另建 `NEW_RECONSTRUCTION_LINEAGE`，父数值等价记 `PARENT_PARITY_UNAVAILABLE`；不改旧封包或pins。新底座需重训三seed RECENT_BCE共同R0，再与原九候选同源比较，共12头、1158720次更新。参考角色保留全局批次，768/794维normalizer隔离，CAL/DEV/参考不进入优化或normalizer。

新版载荷、环境、生成校验及成功探针证据见迁移目录`validation/`，下载未修改远端或重跑测试。原QUERY_TAIL普通Linux包装只适用原完整父缓存；新缓存采用新增血缘及服务入口。入网及现代头随后显式绑定新血缘，科学门槛与开发材料边界保持，无新模型效果结论；完整新缓存和结果须回传本地。目标阶段计划仍PENDING，生产入口拒绝pending模板。

### 2026-10-18 当前：现代头 v1r1 完成 P1–P7 修订，P/T/K 可先于入网运行

[逐项回应](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261018_modern_head_v1_code_review_response_codex.md)、[新版说明](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/README.md)、[最终验证](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/validation.json)、[将来操作](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_comparison_v1r1_20261018/OPERATE_HPC.md)。后续上传采用 **v1r1**，下方原 v1 条目作为历史保留。新归档 SHA256：`ad2454fa3766d3862d98e90370fb9dc1fa8b5d67afd20123863182123f71d4d3`；旧 v1、QUERY_TAIL v2r3、入网 v1r1 归档保持。

P1 允许合法 LightGBM 自然停止，分别记录请求/回调/实际树轮数；4.6.0 常数特征实测为 500/500/1，不能声称“回调必少于预算”已复现。P2 新增 `--heads-only` 与 `--modules-only`：纯头 P/T/K 只依赖完整 QUERY_TAIL 和父资产；M 另查入网六库，复用同包封存头，不重训。生产模块提交须等待头作业最终成功退出，避免与导出重叠；状态、claim、回传归档按阶段分开，失败不自动重提。

P3 proof 改由 adapter 实际逐位比较及摘要生成，先完成全部只读采用前置条件，缺复用证据记录原因后重训；封存/哈希/非有限权重损坏仍硬停。P4 补 CAL_used=false；P5 合同说明涵盖所有 family/seed/ensemble，数字门槛不变；P6 M 显式要求 optimizer_updates=0；P7 提交与作业入口先查离线依赖，不自动安装。三族、三 seed、40 神经轮/500 请求树轮、目标数据用途和科学门槛保持。

最终安装包的 57 项受影响 Python 测试、37 项 Linux 模拟调度、3 项分阶段导出用例通过，共 97 项不同用例；导出在两平台各执行一次，总执行数 100。原完整套件未整套重跑，原 Python 21 项未重跑及上游套件均明确 `rerun:false`。8CPU/16GiB/4线程、RSS14GiB预算继承；72/70h 是每个作业上限，非拆分链总预算或耗时预测。目标环境和完整真实峰值未核验，真实实验仍 NOT_STARTED。

**当前顺序更新：恢复资产并完成 QUERY_TAIL → 现代头 P/T/K 可独立先跑；入网 v1r1 六库与配对完成后 → 同包模块阶段。** 默认 full 仍可用但须先备齐全部依赖。三设备回归、前端独立重建封包、选型后补证据与独立确认待完成；无新模型指标，完整系统不得 PASS。

### 2026-10-18 历史：现代检测头 v1 初次实现与本地验证（由上方 v1r1 接替）

用户授权推进下一步，落实10月15日已确认方案。入口见 [交付说明](../modern_head_comparison_v1_20261018/README.md)、[正式配置](../modern_head_comparison_v1_20261018/bundle/experiment_contract.json)、[资源依据](../modern_head_comparison_v1_20261018/RESOURCE_BUDGET.md)、[验证回执](../modern_head_comparison_v1_20261018/validation.json)、[将来命令](../modern_head_comparison_v1_20261018/OPERATE_HPC.md)。旧QUERY_TAIL v2r3和入网v1r1保持封存；新源码/新包不覆盖旧实验。

固定MLP_QUERY_BCE、官方TabM v0.0.3、LightGBM4.6.0，均为同一782维输入、原FIT/CAL划分及权重语义，seeds27/127/227。神经头40轮、batch256；TabM k32/3blocks/width512/dropout0.1、逐成员加权BCE；LGB固定尝试500轮、N×w，天然无法分裂时另报实际树轮数，不作为早停选型。TabM稳定平均概率转logit，外部三seed float64 mean-logit；各头只在源CAL正常样本定cut。原池/设备目标及历史Q/协议保护应用到所有候选，未自动选择赢家。

**已接同一入网模块：预先固定TabM和LightGBM，各自比较OLD_BANK/B0/B1/B2；库共享，每头独立按同一规则在源端定尺度/保护参数。** P核验原资产→逐头/seed训练或严格复用→K校准与全池报告→两候选逐位回放/入网配对。参考来自完成的入网v1r1，不重新解码或E3。头产物封存在heads子树，监控与模块另存。缺三设备回归仍不得完整系统PASS；错设备供体控制缺计划时NOT_AVAILABLE。

MLP复用必须有原运行封存的完整数值runtime指纹及逐位回放。原QUERY_TAIL未强制记录该指纹，通常会记录缺证据后重训共同MLP，故按最多九个新训练终点准备；不能把代码支持复用写成已省去三次训练。数据或封存损坏直接停止，不隐式回退掩盖。当前原缓存/真实头结果尚未获取，无真实训练、评分或新增模型指标。

**资源按增量维护：8CPU/16GiB、单重阶段进程/4线程、RSS保护14GiB；运行磁盘8GiB、导出6GiB、空闲16GiB。** P/评价旧预算复用，仅新增模型训练估计与生成输入局部量测；TabM完整结构1097184参数，256行单步Windows峰值约0.601GiB，不代表全量峰值。5步稳态均值约0.5094秒，三seed纯更新算术约41小时，未计实际I/O、生产检查、K及两次入网；72/70h只是上限，不能保证整链完成，不自动缩轮数/seed。

**最终归档全新安装后，41项模型/评价/流程合成测试与24项Linux模拟调度测试共65项通过，另有7项生成文件导出检查通过；Windows/WSL安装、159个封存文件及Bash/PowerShell语法校验通过。** 原89个项目Python模块、17个前端vendor模块及旧科学合同逐字节保持，旧179项未整套重跑。归档SHA256为 `635d617637d8dbf2de7ce46cdbceda88e24286f36b371db1d71ed5d534c0dfc4`；最终状态以 `validation.json` 为准，`build_receipt.json` 保留构建时pending历史。

新增库使用包内离线轮子安装至extra_deps，不更改旧环境；真实目标仍需Python3.9/NumPy2.0.1/Torch2.5.1，本地合成环境的NumPy/Torch版本不同，尚不能证明目标兼容。LGB轮子要求Linux x86_64/glibc≥2.28，远端未核实，不支持时须另立构建修订。真实依赖、完整父缓存、已完成QUERY_TAIL及入网参考产物仍是前提。

当前顺序：恢复超算/资产后跑QUERY_TAIL→入网v1r1→现代头联合比较；若父缓存丢失，先补前端重建的独立资源/封包并恢复身份。前端重建封包、三设备回归、选型后的独立确认和补证据仍待做。当前A/B仍为开发材料，论文不填入候选有效性结论。此条取代下方“现代替换头未实现”的当前状态。

### 2026-10-17 交付修订：入网 v1r1 修复导出失败仍报成功；预算改为增量维护

用户反馈独立复审发现：原入网 v1 的 `run.slurm` 将导出失败变成提示，作业与 `exit_code.txt`仍返回实验退出码；实验成功/导出失败时误报0。现另出 [v1r1交付](../onboarding_configured_v1r1_20261017/README.md)，保留原包；最新可用包以 v1r1 为准。实验、导出、最终作业三个退出状态分别保存；导出失败作业返回非零，两者都失败时保留实验失败码并单列导出错误。最终两份回执在归档后生成，由回传入口先单独获取，避免归档里保存过时“成功”。导出失败仅处理导出，不自动重跑实验。

本次仅交付脚本及说明变化；89个Python模块、科学协议、runtime_contract和资源计划逐字节继承。8CPU/16GiB预算直接复用，无新资源估算。**最终包全新安装后的22项模拟提交/失败检查、5项PowerShell模拟回传检查共27项通过**，另单例复现原包误报0；详见 [回执](../onboarding_configured_v1r1_20261017/validation.json)。新归档SHA256为 `d984be0105dda3d7a37e22d85d87c3ec2a209d91e9b2535760c0bda79999a883`；下方179项为原版继承证据，未整套重跑。无远端动作或真实实验；目标tokenizer、真实峰值、模块效果与三设备回归仍待验证。

长期遵循 [资源预算维护约定](resource_budget_maintenance.md)：未变任务复用已有预算，只更新规模/批量/并发/实现变化影响的阶段；首轮真实峰值用于校正估计；按变更验证，常规只读汇总和失败片段。既不每轮重建预算，也不为节约token省略必要失败场景。本条覆盖下方v1交付当前版本，其他科学路线与待办不变。

### 2026-10-17 最新：入网模块独立封包完成，已接 QUERY_TAIL v2r3，真实实验待恢复

用户授权完成入网模块交付。本轮在已验证的受约束入网 v2 科学代码及内存工程修订上，补全参考准备→六库E3→同头配对评价→归档回传的生产入口；见 [交付说明](../onboarding_configured_v1_20261017/README.md)、[资源依据](../onboarding_configured_v1_20261017/RESOURCE_BUDGET.md)、[验证回执](../onboarding_configured_v1_20261017/validation.json)、[操作命令](../onboarding_configured_v1_20261017/OPERATE_HPC.md)。归档 `onboarding_configured_v1_20261017.tar.gz` SHA256：`0e91afd2ca4e1a3d5ec85e6aa3dd323d80c243568ae4ea74f7d60fe39e925bd4`。

**接入已实现：读取 QUERY_TAIL v2r3 完整运行目录的同一 R3 头；OLD_BANK、B0、B1、B2 共用一次源端封存的几何/尺度/保护参数，输出加模块前后的配对结果。** 两份正常捕获必须完整解码核包数；每个参考编码与评价阶段使用独立进程，结束释放。没有重新训练头，也不按目标数据集效果选择开关。目标头分数在源参数封存前会被读取用于固定头复现检查，模块的目标支持/修正在源参数封存后进行，不能表述为此前完全未读目标分数。

**实际配置：8 CPU、16 GiB、单重阶段进程、4 数值线程。** RAW/E3/回放与评价峰值预算6/4/11.5 GiB，均为估计，最大阶段加一次25%余量后取整。总RSS保护14 GiB；运行磁盘保护8 GiB、开始空闲16 GiB、导出上限4 GiB；24h Slurm/22h内部时限不是耗时预测。内存预算包含完整元数据、mmap和临时工作区，不沿用旧大资源申请；真实峰值待首轮监控。完整哈希预检位于内部22h计时前，仍受24h作业上限约束。

**最终归档全新安装后的162项合成检查、Linux模拟提交17项，共179项通过；Windows/WSL安装与内外SHA、4个Bash脚本及PowerShell AST校验通过。** 本地缺transformers，真实tokenizer生成输入检查未运行；目标作业会先补此检查。原科学代码、冻结协议、QUERY_TAIL v2r3包哈希保持。草稿曾有一项测试fixture引用历史协议路径，已改为绑定包内同字节协议，最终全过；失败日志保留。未连接超算、上传、提交或运行真实解码/E3/训练/评分。

| 工作 | 当前状态 |
|---|---|
| QUERY_TAIL 检测头修复 | v2r3 配置、封包、本地验证完成；真实 P/T/K 未开始 |
| 受约束新设备入网 | 独立包及与修复头接入完成；完整父缓存、正常PCAP、checkpoint、目标环境与真实头产物就绪后运行 |
| 前端缓存重建 | 工程源码已修订；独立资源定值与封包仍待完成，不能套用入网16GiB |
| 现代替换头 | 联合方案已写，代码未实现 |

同头零新增漏检是验收门槛，不能宣称实现即可保证不漏攻击。三设备新输入回归尚未生产接入，完整系统只能PENDING或FAIL；没有事前供体计划的错设备控制明确NOT_AVAILABLE。CIC/UNSW仍为开发材料，当前无新模型指标；选型后补证据待办继续有效。本包依赖完整远端QUERY_TAIL运行目录及原父资产，精简pullback不可替代缓存，也不是超算全部资产丢失后的自动恢复包。此条更新下方“入网独立封包待做”的当前状态，下方记录保留历史。

### 2026-10-17 最新：QUERY_TAIL 资源配置与 v2r3 封包完成，本地交付检查通过

用户指定先完成检测头修复实验的资源核算与封包。本轮产物见 [交付说明](../query_tail_configured_v2r3_20261017/README.md)、[资源依据](../query_tail_configured_v2r3_20261017/RESOURCE_BUDGET.md)、[验证回执](../query_tail_configured_v2r3_20261017/validation.json)、[操作命令](../query_tail_configured_v2r3_20261017/OPERATE_HPC.md)。新归档 `query_tail_configured_v2r3_20261017.tar.gz` SHA256 为 `1678d1b2b7162d788f3058b47dd06231c7db7a21287046675fe3ecf985415317`；旧 v2r1/v2r2、科学合同及预测规则哈希不变。

**实际提交配置：amd 单节点、16 CPU、20 GiB、3 worker × 4 线程。** P/T/K 峰值预算分别 10.5/15.5/10.5 GiB，均为 `ESTIMATED`；取最大值加一次 25% 余量后上取整至20。总/worker RSS保护线18/4 GiB，新输出预计0.732 GiB、运行保护4 GiB、启动空闲8 GiB、导出included上限2 GiB。沿用72小时Slurm/70小时程序上限，仅为上限，未宣称新TAIL预计耗时；历史RECENT耗时不是新任务吞吐实测。没有预设小内存目标或沿用旧64/192G。

本地完整元数据测量：LEARN 766,727行加载/验证/紧凑构建峰值3.893 GiB，CIC/UNSW分别1.011/0.889 GiB；紧凑worker准备完整617,908行FIT权重峰值0.319 GiB，权重哈希与原实现相同。角色分进程测量不等于整链实测；训练预算计入3份共享映射RSS、Linux父进程未返还堆及目标运行库余量。

**最终归档全新安装后的57项合成检查、Windows安装7项、Linux安装7项+假调度提交13项，共84项通过；PowerShell传输脚本仅AST解析通过，未执行。** 原包38个Python文件逐字节不变，使用原v2r2 runner，新增5项正式配置测试。新包绑定预算证据、安装校验、一次性提交入口和回传SHA；原九头/三seed/40轮、BCE+TAIL与评价门槛保持。此版本完成了QUERY_TAIL的资源与交付配置，替代下方旧“资源计划pending”的当前状态，不覆盖历史记录。

| 工作 | 当前状态 |
|---|---|
| QUERY_TAIL 修复实验 | 配置/封包及本地验证完成；超算环境、父缓存身份与真实P/T/K待验证；真实实验NOT_STARTED |
| 新设备入网与前端重建 | 源码工程修订及journal补丁已验证；各自资源预算/独立封包仍待做，不能套用本包20GiB |
| 现代替换头 | 联合方案已写，代码未实现 |

本轮没有远端连接、上传、作业提交、真实训练/评分、PCAP或E3。父RECENT缓存/只读spool/基线仍是依赖；恢复缺失资产是单独工作，本包不自动重建、换输入或重试。下一步按恢复实况核验依赖，再执行此固定链；后续入网封包及现代头按既定优先级推进。10月15日选型后补证据清单继续有效。

### 2026-10-17 复审修正：主快照库 journal 误停遗漏已修复

用户转来复审指出正式 `snapshots.sqlite` 没登记临时 journal，正常 commit 与资源扫描交错可能误停；上一轮242项检查中未覆盖这处入口，问题属实。已增加仅登记该持久库三个精确 sidecar 的接口，在首次写库前调用，正式数据库本体与目录仍不豁免。新增真实SQLite事务的确定性交错回归，包括实际spool两处提交；原55项工程检查+新5项共60项通过，正式库丢失/未知文件/权限错误仍失败。见 [修复说明](../engineering_snapshot_journal_fix_20261017/README.md)、[最新验证回执](../engineering_snapshot_journal_fix_20261017/validation.json)。

本次仅改两处工程源码，前一版本回执保留，新source manifest明确承接修订；原封存包和科学合同不变。未运行真实实验或远端操作；tokenizer/目标环境验证、资源定值与交付封装仍待完成。下条为本轮整体工程范围，当前源文件身份以此补丁的新manifest为准。

### 2026-10-17 最新：入网与前端内存工程修订已验证，剩余工作收口至资源定值和封装

用户授权继续工程修复后，新增独立版本，见 [工程修订说明](../engineering_memory_followup_20261017/README.md)、[验证回执](../engineering_memory_followup_20261017/validation.json)。连接重状态与入网候选快照改为限定驻留条数、完整写入/恢复；FIT/CAL 及正常/攻击子集改为按批行索引读取；SQL shape/UID 分组和 worker batch ID 流式读取。跨连接时间可回退，因此没有按别的连接时间删状态；原输入状态、B0/B1/B2 选择、batch 16、数学与科学验收保持。小型元数据账本仍驻留，不宣称整条链内存已有硬上界。

新增 [独立前端缓存重建入口](../engineering_memory_followup_20261017/FRONTEND_REBUILD.md)，只做 P→E3→merge/normalizer，资源计划显式绑定并发、各阶段组成、证据 SHA 和 Slurm 实际分配，不启动旧 T/K。修复了临时 SQLite 删除导致资源监控误停的竞态及失败路径资源释放。旧基线资产仍是输入前置依赖，本入口不是所有远端数据丢失后的一键恢复；未来重建特征仍须符合原父缓存身份与数值复现规则。

**242 项选定合成/模拟回归通过**：原入网89、新版科学兼容61、新工程55、原输入/scope37。额外旧 ActualTokenizer 检查因本地缺 transformers 在 setup 失败，单列日志，未计入通过项，目标环境仍待复查。原 v2r1/v2r2 包、科学合同、原入网九文件及原前端关键六模块哈希核对不变。没有真实训练、PCAP 解码、E3、评分、远端动作或新的 Claude 审阅。

生成数据局部基准：6000 个嵌套状态工作集峰值284.2→32.0 MiB，耗时0.47→1.49秒，增加磁盘I/O；生成特征子集297.2→209.9 MiB，耗时0.155→0.168秒，两组内容哈希一致。这不是完整任务峰值，不能据此定生产内存或worker数。**本轮独立源码已验证，尚非可直接提交的新超算包；完整 P/T/K 与前端/入网资源计划仍 pending。** 下一步按实际资产规模收口阶段组成、并发收益及磁盘/时间预算，再封装已验证工程版本。无16/32GiB目标，无自动沿用192G/64G；无需继续扩展方法讨论或重跑旧诊断。10月15日路线和选型后补证据待办继续有效，下方保留历史。

### 2026-10-16 最新：工程修复优先；QUERY_TAIL 独立工程版已实现，整链资源定值待补依据

用户确认先解决实验包的工程与资源申请问题，再继续入网模块封装和现代检测头对照。本地首批修复见 [工程版说明](../query_tail_engineering_v2r2_20261016/README.md)、[验证回执](../query_tail_engineering_v2r2_20261016/validation.json)。新版 v2r2 使用共享只读紧凑训练元数据，避免各 worker 展开完整 LEARN Python 字典；加入正常/异常退出释放、分阶段 RSS/cgroup 观测、统一资源计划及提交/运行身份核对。固定 64G 已从新版有效配置中移除，并发可为 1–3，每 worker 仍为 4 线程；不能据此预先指定小内存目标。

固定前 10 万条 LEARN 元数据的本地读取与权重测试，进程峰值工作集由 0.495 GiB 降至 0.056 GiB，投影和原权重哈希相同；逐字段访问变慢。这是 Windows 元数据局部测量，不是完整任务峰值或整体 88.7% 降幅。新包包含原科学实现，输入、损失、batch、三 seed/40 轮及验收不变；合成检查、安装和模拟提交结果以验证回执为准。封存 v2r1、科学合同与入网 v1 的九个代码/测试文件保持不变；Claude 的旧审阅不等于审过新工程版。

**交付状态：本地工程实现/验证完成，提交资源计划未完成，真实实验 NOT_STARTED。** 新版 `resource_plan.template.json` 尚无 P/T/K 完整阶段峰值依据和最终申请值；提交入口不会猜测或回退到旧 64G。后续先补全阶段组成估计/可比测量及并发理由，再定资源配置。缺完整缓存时不声称已实测整链。旧前端重建的 16 进程、Contexts 重状态及入网候选快照/特征子矩阵仍需在相应包中处理，不能用本次结果直接为其降配。该剩余工程范围与新版资源定值排在后续方法扩展之前。

本轮只有本地合成检查、已有元数据存储测量和独立封包，无超算访问、提交、真实训练、PCAP 解码、特征提取或目标评分。下方旧条目保留历史；10 月 15 日的选型后补证据清单继续有效。

### 2026-10-16 用户澄清：实验包与资源配置须符合任务的正常工程需求

用户明确要求代码包及资源配置合理：按任务量、常规高效实现、合理并发和运行效率确定CPU/内存/时间；既不追求最小资源，也不默认大资源。撤回助手先前提出的32GiB适配目标，该目标不是用户要求。先检查各阶段本来需要保留什么数据、是否存在多余副本/状态及并发收益，再用阶段测量验证常规量级，配置有依据的余量；不能靠极低并发拖长时间来完成降配指标，也不能因缺测量而惯性上调内存。

已有只读核对：历史192G为16进程E3完整链的保守申请，非方法最低内存；Job177891 batch MaxRSS约40.94GiB，单特征worker完成样本约1.66–1.87GiB，但缺完整cgroup/整树峰值记录。当前封存QUERY_TAIL为64G/3worker，真实运行未开始；其合理性同样待验证。代码有metadata重复、状态回收滞后、候选快照常驻等优化空间，未确诊泄漏。详见 [资源合理性审查](../memory_efficiency_review_20261016/README.md)。本轮仅更正工程目标和文档，没有改源码/封存包/资源合同，没有新实验或远端操作。下方实现状态、补证据清单继续有效。

### 2026-10-15 最新：入网模块代码已实现；现有数据先验证，选型后写作与补证据

**用户确认的顺序：暂不下载新数据，先用现有开发材料落实并评价已定新设备入网方案；与修复头及有限现代头对照后确定最终系统，再并行推进论文和补充实验。** 覆盖审查中的缺口登记为后续任务，不作为当前开发实验的新增先行关卡；保留已知限制和固定评价口径，不为追求完整材料而推迟现有对照。

#### 当前状态与下一步

| 工作 | 当前状态 | 接下来 |
|---|---|---|
| QUERY_TAIL 修复头 v2r1 | 已实现、封存且审阅通过；真实实验未运行 | 数据/运行环境就绪后按原合同执行，不改封存包 |
| 新设备入网完善 | 用户授权后已实现参考准备、共用模块、QUERY_TAIL 接入及评价；89 项合成测试通过，真实实验未开始 | 完整父缓存与真实 R3 结果就绪后，先做原库同头配对，再接 B0/B1/B2；尚非独立超算提交包 |
| 现代检测头对照 | MLP/QUERY_BCE、TabM、LightGBM 同输入方案已写；未实现 | 有限候选共用同一入网规则，按完整系统表现选型 |
| 数据充分性 | 元数据审查完成；有开发价值，覆盖与独立性缺口仍在 | 如实报告分母和局限；补材料后置，见持续待办 |
| 论文 | 稳定部分已有草稿 | 可继续写有依据的部分；最终选型后与补实验并行完善结果、图表及结论 |

新模块尚无真实性能。“材料可用”不表示所需全部缓存已经就绪；超算/缓存恢复状态以后续核验为准，本次未访问远端。参考准备、共用模块和已封存头适配器已写入独立新文件；源侧定参封存后再做目标配对，完整系统缺少三设备回归时必须 PENDING。现代头新比较实现及其生产适配器仍待完成，不重复旧 G1–G4/D3/CAL 诊断。既定主分母、门槛、seed、参考时间合法性及同头零新增漏检要求保持。

入口：[代码实现与验证](../constrained_onboarding_implementation_v1_20261015/README.md)、[实现回执](../constrained_onboarding_implementation_v1_20261015/implementation_receipt.json)、[联合方案](../modern_head_comparison_design_20261015/proposal.md)、[入网方法](../modern_head_comparison_design_20261015/onboarding_refinement.md)、[材料与配置](../onboarding_materials_and_protocol_20261015/README.md)。固定 protocol 内历史 NOT_IMPLEMENTED 字样不改，当前状态以本条及新实现回执为准。

#### 持续待办：选型后推进，投稿前逐项核对

以下事项未完成，进入实现、换对话或写作后仍须跟进。当前登记，不启动新数据下载或采集。

- [ ] **薄弱正常设备与功能覆盖。** 优先补 HeimVision 等正常证据少的设备、不同功能/日期；核实可信参考先于后续功能记录。CIC 两小时后正常 96,041 条，其中 HeimVision 仅 672 条；较晚正常只承载完整正常权重约 21.62%，不能代表全部功能的入网验证。
- [ ] **外部攻击多样性与独立执行。** 当前 UNSW 72,553 条攻击主要是直接 TCP SYN、同日 15 个注释区间。优先补合法非 SYN 行为、独立执行及同设备正常/攻击配对，避免只增加重复洪泛包。
- [ ] **最终独立确认。** 当前 CIC/UNSW 已参与开发，旧三设备用于回归。确认评价前落实未参与当前选型的来源，先锁定最终模型、参考规则、参数/阈值选择流程和确认规则，再读取确认效果。新目标设备按冻结规则取得可信正常参考仍是方法的正常步骤。
- [ ] **论文对照与稳定性。** 按实际主张补齐必要同头单独/加模块、参考策略、保留基线及设备/攻击事件分层结果；区分训练 seed 和独立场景重复。三设备新输入回归沿用已有协议，不改称未触碰确认。
- [ ] **采集混杂与部署主张。** 优先可靠标注的同条件正常—攻击配对。披露可信正常前提、功能日志及混合流证据不足；论文提出相应主张时再补污染、时延、开销或连续流告警量，不默认无限扩大矩阵。
- [ ] **投稿前证据核对。** 每项主张对应真实实验和分母；完成项链接日期 run/结果，未补项明确限制或收窄主张。补充结果无论好坏都保留；若据新确认结果继续改方法，该批转为开发材料并更新确认安排。

依据与已有候选资格见 [数据充分性报告](../evidence_adequacy_20261015/README.md)。无需重做 Gosund/Luohe 身份检查，不把尚不满足入网/标签条件的候选写成已就绪确认集。

#### 维护方式

本文件顶部是当前状态、决定、阻塞和待办的主入口；[mainline_experiment_map.md](mainline_experiment_map.md) 是简短实验索引。每次方案版本/实验的脚本、配置、日志、结果及验收证据继续留在 `runs/<主题>_<日期>/`（按需附版本），完成后回写主线状态、待办及索引。冻结结果不原地改写，已有目录不因日期变化重命名。

本条记录路线与待办，本次未启动训练、原始包处理、远端提交或下载。以下 10 月 12 日及更早内容保留为历史；当前优先级以本条为准。

### 2026-10-12 latest: prospective CPU-aware parent replay rules recorded

Claude accepted the four prior increments. Response: `collab/20261012_three_device_numeric_parity_response_codex.md`; latest future planning: `runs/system_vs_module_planning_v3_20261012/`. Exact input/state/token/batch identity required in both branches; before observing replay outputs, confirmed numerical-runtime match selects BITWISE, different/UNKNOWN selects per-row float64 relativeL2<=1e-5 plus frozen RECENT3seeds+ensemble decision parity (4096pairs). No failure-driven branch switch. Future actual heads require their own paired checks before final cache acceptance; endpointsPENDING. State26/QUERY14 floating transforms are not CPU-independent and do not inherit E3 tolerance. Missing original features/spool remains UNAVAILABLE.

Local archived sacct already identifies parent177891 node188; historicalCPU/ISA/backend identity incomplete. Post-recovery scontrol is current-node evidence only. P/worker environment-capture specification written, not implemented/run. No real replay/forward/training/remote commands or repeated diagnostics. Prior reviewedv2 files, current sealedQUERY_TAILv2r1 package/contract/predictions unchanged. Full-system zero-added-miss gate, old-level report flag and<=150G/<130GiB budget condition retained. HPC/cache recovery -> existingv2r1 remains next; paper stable drafting continues without new performance claims.

### 2026-10-11 follow-up latest: Claude planning review PASS / attack TP eligibility added

Claude reviewed four planning items with no blockers and reported9 official weighted FPR values exactly equal. Incremental response: `collab/20261011_system_vs_module_planning_followup_codex.md`; latest artifacts: `runs/system_vs_module_planning_v2_20261011/`, prior reviewed directory preserved. Future full-system zero-added-miss is explicitly mandatory on3pools x4suffixes; any1 added miss FAIL. OLD_LEVEL_PRESERVED remains report-only. Added attack TP weighted eligibility share: RECENT CIC66.667807%,UNSW60.007370%; this is exposure, not module miss rate.6new boundary checks PASS,900 old normal-statistic values identical.

Future cache key includes decoder/effective prefs and numerical batch identity;1024 selected-parent-row replay requires original batch companions (actual forwards<=16384), original gold and spool. Synthetic checks cannot substitute for real parent parity. P decode workload26,220,035,883B verified from saved inventories;12604.7s timer is mixed preparation, so pure-decode coefficient/new P estimate PENDING. Prefer<=150G only with credible full-tree peak<130GiB under prior user condition; no automatic192G escalation/retry. Ordinary outside-owner log rows may be summarized only while all new/old anomalies and per-frame state/audit remain intact. These wrapper/resource changes are plans, not implemented/current v2r1 changes. HPC/cache recovery -> sealed v2r1 remains next; no real training/forward/replay/remote action.

### 2026-10-11 latest: reference eligibility addendum / A old-level comparison report-only

Current package is QUERY_TAIL v2r1 SHA af61a1b187acaf8c379f1c8b01de0b18001aaa194333cfb7cf3bf95f6adddc4c; B1 closed and Claude review accepted, real experiment NOT_STARTED. Wait for HPC/full-parent-cache recovery and target synthetic checks, then keep the fixed four-arm/three-seed/40-epoch chain. Stable paper writing is active; no new performance claim.

Claude review §5 answered in `collab/20261011_system_vs_module_framing_response_codex.md`. Current main-path valid_reference encodes full structural eligibility. New descriptive formula F=H(1-s*g_eligible); s is weighted head-FP share, NOT all-query coverage. Saved RECENT CIC/UNSW ideal floors3.354251%/6.519688% apply only to fixed current head/eligibility. Old88.55% whole-pool gain equaled eligible gain only in old DEV with s=1; transfer unvalidated. New planning and read-only per-arm/seed/ensemble addendum live in `runs/system_vs_module_planning_20261011/`, outside sealed runs.

Unfrozen future A draft now treats OLD_LEVEL_PRESERVED as report-only; original research floors and same-new-head zero-added-miss pairing retained. HistoricalQ raw recall0.1pp guard stays two-device CIC_DEV only. Three-device current-inclusive input and module remain unimplemented;341222queries+48refs need ~0.976GiB E3 payload, conditional historical pure-E3 estimate4.28h, not total-job guarantee. Future staged cache preparation may share one module job but never expands sealed v2r1. No new training/forward/remote submission; no repeat G1–G4/D3/CAL diagnosis; no automatic retry.

### 2026-10-02 latest: QUERY_TAIL local feasibility assessed / current formal package not directly runnable

Algorithm uses small CPU heads; current laptop i7-12700H/15.8GiB RAM/D19.35GiB free does not satisfy fixed3worker package or24GiB free guard. Missing parentfeatures+SQLite about7.41GiB. Original217source PCAPs and2UNSW PCAPs exist with source sizes matched, but full input hashes and exact cache rebuild not yet verified. Frozenencoder/heads/results local preserved. Local route requires versioned cache reconstruction if remote recovery fails and memory-efficient singleworker P/T/K adaptation; no real training, rawdecode or benchmark run. Read `query_tail_local_feasibility_20261002.md`.


### 2026-10-02 latest: HPC disk damage USER_REPORTED / local result exports preserved / remote parent caches UNCONFIRMED

Local audit verified26 legacy delivery archives against sidecars and5 returned manifests covering1662 files (three176411 members verified inside archive). Latest177891 export916files and12 endpoint weights intact; original scientific FAIL preserved. QUERY_TAIL local package/seal intact, real P/T/K NOT_STARTED in available records. Full177891 features and4.17GiB snapshots.sqlite were retained remotely; disk fault scope/recoverability unknown. NEXT confirm restored parent caches before any upload/submission; current reuse-only package cannot run against empty replacement storage. No automatic rebuild/retrain or cache substitution. Read `local_result_preservation_after_hpc_disk_damage_20261002.md` and `runs/local_result_preservation_audit_20261002/audit.json`.


### 2026-09-30 latest: QUERY_TAIL v1 IMPLEMENTED / LOCAL DELIVERY PASS / real P/T/K NOT_STARTED

Frozen current-query descriptors + weighted normal tail implemented with full FIT617908/CAL148819, nine new heads x40 epochs (869040 updates), and R0 RECENT reused from177891. Clean Python3.9 synthetic23, Windows installer6, Linux installer/mock submit12 tests PASS;12 returned snapshots passed parser compatibility, with no new real forward or repeated diagnosis. Archive127034bytes, SHA25672a50f76e2bb14683b285cef5fbd2e5cc38cc6112886e687fee82d219725f1c2. Resources amd16CPU/64G/72h,3workers; tree56GiB/worker14GiB/program70h guards. Exact source support and target numeric compatibility remain pending inside the formal job. Codex self-review only; Claude unavailable is not a waiting gate. Read `legacy_query_tail_learning_implementation_v1_20260930.md` and `runs/legacy_query_tail_learning_delivery_v1_20260930/{acceptance.json,OPERATE_HPC.md,RESOURCE_BUDGET.md}`. NEXT user-operated upload/single whole-chain submission/pull; final-package real execution authority not yet recorded. Reference NOT_TESTED, ID_NOT_RUN, holdoutclosed, paperPAUSED; HEAD and8 unrelated edits preserved. Earlier DESIGN READY entries below are historical.








Status: active living handoff. This top section is the authoritative current state.



If older time-log entries conflict with this section, treat the older entry as historical evidence only.







Continuity / operating workflow: read `mainline_workflow_and_hpc_continuity_20260909.md`



for the verified document-maintenance rules, collaboration preferences and HPC lessons.



This navigation note changes no scientific state or execution authorization.







### 2026-09-30 latest: QUERY_TAIL learning-repair v1 DESIGN READY FOR IMPLEMENTATION; no real P/T/K. Keep verified RECENT/E3 and source FIT weights; append14 current-packet descriptors to one782->128->1 head, combine BCE with source-FIT top1%weighted-normal-tail pair ranking refreshed each epoch. Primary QUERY_TAIL; QUERY_BCE/RECENT_TAIL ablations,3seeds each,9newheads40epochs; reuse177891 RECENT baseline and features, no raw/E3 rerun. All original core attack/FPR gates retained; add protocol/activity regression check; reference gains NOT_TESTED, ID_NOT_RUN, holdoutclosed/paperPAUSED. Source metadata weights verified: Hydra471rows=25%attackmass; TCP429350=41.6667%; ACTIVE_UNANNOTATED131823=17.9479%normalmass, counts are not training emphasis. Exact SYN phase/weight census PENDING_REMOTE_SNAPSHOT, folded into implementation P; no fabricated completeness. Read legacy_query_tail_learning_design_v1_20260930.md and runs/legacy_query_tail_learning_design_v1_20260930/ (research,contract,self-review,acceptance). Target DEV remains consumed; no automatic winning-arm promotion or retries. NEXT implement/synthetic/package; user handles later authorized whole-chain upload/submit/pull. HEAD4b28747/codex-exp-mainline and8 unrelated edits preserved.

### 2026-09-30 latest: Job177891 G1/G3/G4 COMPLETE, G2 fixed-query normal headers/ports completed locally. Saved-score per-device1%FPR retrospective: UNSW96.6038%attack,0.9730%FPR;Samsung63.08%ofweightedloss; rate1/10/100 loss42.34/38.28/19.38%;only5longattackcomponents,83.57%loss>=60safterannotationstart. RemainingnormalFP90.38%ACK/data;1603normalSYNqueries0FP atsourceandoracle. All3seeds share1169misses/2.2040ppweightedloss;Samsungworstforall. G2missingportsfilled fromexistingnormalPCAP5413239packets/75763fixedqueries;fullSHAverified,31.1s,nofeatures/forwards. CICoracleattack99.9437%;all95missesHeimVisionTCP. NEXT targetedlearningrepairdesign/current-query-context attack evidence andhardnormalconstraints; H1/H3cluesonly,H2notfullyexcluded,fullsnapshotdescriptorsstillremote;noautomaticfrontendchange ornewtraining. Read legacy_continuous_input_job177891_overlap_diagnosis_20260930.md andmatchingrun. No deployedcut/data/model/gate change,HPC/download/holdout;HEAD/8unrelatededits preserved;ID_NOT_RUN/paperPAUSED.

### 2026-09-30 latest: overlap G1-G4 INPUT AUDIT COMPLETE (not score diagnosis). Verified schema of1095200 existing role rows. UNSW72553 attacks have15annotation IDs,rate1/10/100,direction and victim targetTCPport; allinboundSYN&&!ACK,notARP/reflection. UNSW75763normal rows lackports/canonicalkey. SourceFIT/CAL unoriented endpoint-port inventory saved separately; NOTservice coverage. G1/G3/G4 existing-field diagnostics feasible; fullG2service needs targetnormal header enrichment; remotev3snapshot contains window descriptors but no rawports. ProposedH3 attack-stage supervision mismatch: sourceFIT TCPattack payload lowerbound80.54%unweighted vs targetSYNquery scope; hypothesisNOTPROVEN. Both source/target attack label rules inbound; directIP/MAC/port absent fromRECENT tokens. Smallcomponent/lowrate orseedvariation do not proveH2/H1; require actualcausalwindow evidence. Read collab/20260930_job177891_overlap_diagnosis_reply_codex.md and runs/legacy_continuous_input_job177891_overlap_metadata_audit_20260930/. NoG1-G4scoreexecution,forward,training,CAL,rawdecode,HPC orprotectedpool;99%target andD3NOT_RUN unchanged. Next agree correctedreadonlydiagnosis,notauto frontend replacement. HEAD/8unrelated edits preserved;ID_NOT_RUN/holdoutclosed/paperPAUSED.

### 2026-09-30 latest: Claude four-question response + saved-score D1 COMPLETE. UNSW RECENT ensemble retrospective attack bound at each-device weighted FPR<=1% is96.6038%; even relaxing to each-device<=2% and ignoring pool<=1% gives only97.5301% (Samsung92.1361%). Thus fixed RECENT + one scalar threshold/device cannot pass frozen99%pool/97%device gates; KEEP gates, no D3 recommended. CIC each-device1% bound99.9437%. Target reference calibration requires a future version; v3 remains source-CAL-only. DEV row logits local; reference classifier logits not computed; small new reference features retained remote (not rechecked), all7device banks3-64rows insufficient for example alpha.005. Reference/queryUIDs disjoint and time strict; UNSW same-component overlap means no iid/conformal guarantee. D2metadata complete, reference-score comparison NOT_RUN. Pause currentSTATE/LEARNED deployment candidacy, retain ablations; RECENT development baseline only. Next joint discussion on low-FPR score separation, not threshold sweep or automatic frontend replacement. Read collab/20260930_job177891_joint_discrimination_reply_codex.md and runs/legacy_continuous_input_job177891_d1_reference_audit_20260930/. No model forward/training/calibration/remote execution or changed frozen result. ID_NOT_RUN/holdoutclosed/paperPAUSED;HEAD/8unrelated edits preserved.

### 2026-09-30 latest: v3 Job177891 COMPLETE / pullback verified / SCIENTIFIC FAIL BOTH POOLS. User sacct COMPLETED0:0,18:34:26,MaxRSS42923988K(~40.9355GiB batch accounting). Archive321375653bytes SHA35f371d04763e24d6a1ee4af0f3a9eff5e463c981da538ec84006e11051bb450;916 included files/917 members verified. P1095200 rows/current token checks,12 heads40epochs,1134960updates,fullCIC179886/UNSW148316 UID decisions independently reproduced. UNSW ensemble weighted attack/normalFPR: OLD_MATCHED99.9416/23.0415%,RECENT99.9849/21.2832%,RECENT_STATE90.7491/19.3087%,LEARNED35.0251/7.4092%;RAW90.7491/17.7011%. Learned adds43028 attack misses, three devices wholly missed; CIC adds105 with weighted attack97.5694%,FPR2.7524%. RECENT has useful development signal but high FPR; OLD_MATCHED is old features with new matched head, NOT historicalQ. Retrospective DEV-label single-threshold score-order bound at1%weightedFPR: UNSW OLD59.8948%,RECENT96.1919%,STATE37.8711%; diagnostic only, no new deployed threshold or gate change. NEXT focused mechanism design/literature for joint discrimination and attack-safe reference use; no new training/evaluation authorized. Read legacy_continuous_input_job177891_result_20260930.md and runs/legacy_continuous_input_job177891_result_20260930/. No auto-promotion/retry, ID_NOT_RUN, holdoutclosed, paperPAUSED, old edits/package preserved.

### 2026-09-29 latest: v3 Job177891 observed RUNNING on node188 at21:48:04CST (user screenshot, not live remote inspection). Elapsed08:00:29; stage P_FEATURE_WORKERS;524725/1095200 rows47.9113%; current treeRSS sample34.2634GiB; retries0,optimizer_updates0,historical_holdout_opened=false. Passed earlier input preflight/spool gates to reach feature workers; no model capability result yet. Feature-stage ETA17585.7s (~4h53m), not whole-chain ETA or guarantee. Submission now observed; do not submit again. User whole-chain authority remains valid, zero automatic retry. Evidence: runs/legacy_continuous_input_repair_execution_v3_20260929/job177891_observed_progress_20260929_214804.json.

### 2026-09-29 latest: v3 REAL FIXED CHAIN AUTHORIZED; user explicitly waives Claude code review for this package. Package SHA485a95d8bb93d14c281670d80c502b1c80045e3f1665382ddb49e4c4d3bb84c1 and delivery/bundle/clean-install hashes verified unchanged. Authority covers one P/E3/T(12 endpoints)/K(source CAL,CIC DEV,consumed UNSW)/export chain; no repeated stage approval, failure STOP and zero automatic retries. User operates upload/install/submit/pull through authenticated terminal; actual submission not yet observed and job ID unknown. 64CPU/192G/72h retained. See runs/legacy_continuous_input_repair_execution_v3_20260929/authorization.json. This explicit user waiver supersedes previous review/authorization-pending notes; sealed implementation records remain historical.

### 2026-09-29 latest: Job177491 FINAL SACCT RECORDED (user terminal output); memory follow-up complete. FAILED/1:0,587s,192G requested,64 CPUs; batch MaxRSS=AveRSS7291960K on node188/task0 (~6.9542GiB assuming KiB). Job-row memory fields blank. P preflight only; task/step accounting is not guaranteed whole-tree peak or temporal average. Failure remains MISSING_NAMESPACE_HEADERS, no OUT_OF_MEMORY state reported. KEEP192G for unmeasured E3/T/K. v3 implementation/65 tests/package unchanged; Claude code review and separate real-chain submission authority remain pending. See collab/20260929_job177491_final_memory_record_codex.md and runs/legacy_continuous_input_job177491_memory_followup_20260929/.

### 2026-09-29 latest: continuous-input v3 IMPLEMENTED / 65 tests PASS / Claude focused code review pending. User authorized owner scope isolation implementation and Job177491 sacct read, NOT real-chain resubmission. Full known registry retained; capture frozen query/reference owner union drives isolation. Full legacy audit retains1/346,2/7424,14/2 receipts; required-owner per-frame identities and fixed UID checks remain; assert every receipt incomplete event is outside-required-owner. Pinned real first/last fragment fixture demonstrates outside-owner target snapshot byte identity and required-owner STOP. Only input/audit production behavior changed; v2/model/loss/data/CAL/gates/resources unchanged. 65 tests (52 inherited+13 scope), Windows/Linux6each delivery, Bash and mock submit, PowerShell Mode PASS. Archive349678bytes SHA485a95d8bb93d14c281670d80c502b1c80045e3f1665382ddb49e4c4d3bb84c1;44modules. Design SHAa10a38edd2a871ebfb70cc37c1be3b1ac9715a2e0b0024019146f834b55674d9. No real P/E3/T/K retry or successful remote command. Job177491 final sacct pending operator output after SSH authentication failed; pre-exit archived sacct blank MaxRSS is not peak evidence; KEEP192G. Read legacy_continuous_input_repair_v3_implementation_20260929.md, collab/20260929_continuous_repair_v3_response_codex.md, delivery_v3 acceptance.json and OPERATE_HPC.md. HEAD/branch/8 unrelated edits preserved; paper PAUSED, ID NOT_RUN.

### 2026-09-29 latest: Job177491 pullback VERIFIED / preflight root cause identified / v3 scope-isolation PROPOSED, not implemented. Archive8ae5a2b6...f67abd,43 included files verified. Exact failure frame1135180 is intact IPv4 UDP FIRST fragment; default tshark reassembly hides its ports. Header census SHA verified for both consumed UNSW captures:28/4 fragment frames (14/2 first fragments), all from non-target registered owner70:5a:0f:e4:9b:c0; zero frozen query/reference hits and zero target-owner overlap. active00/01 preflight complete; entire P incomplete, realE3/T/K not started. Propose retain full known-owner registry and global legacy audit, isolate demonstrably outside-required-owner failures; target-owner strict checks remain. See collab/20260929_job177491_preflight_diagnosis_codex.md and runs/legacy_continuous_input_job177491_diagnosis_20260929/. No production changes, retry, remote command or scientific result. sacct export captured pre-exit RUNNING/blankMaxRSS; no measured peak, KEEP192G.

### 2026-09-29 latest: Job177491 FAILED during P anomaly preflight (user terminal screenshot; pullback not yet local). Slurm FAILED/1:0 elapsed00:09:47; status STOPPED_NO_RETRY, P_ANOMALY_PREFLIGHT_unsw-benign-20180528, MISSING_NAMESPACE_HEADERS; optimizer_updates0, retries0, historical_holdout_opened=false. Displayed completed1105920/5413239 is the last progress sample, NOT the exact failure frame. Displayed rss_gib7.03498 is a sample, NOT total-job peak or evidence to reduce E3/T/K resources. Source check: continuous_input_v2.Contexts.append rejects absent IP/transport-port fields for an otherwise selected protocol/owner; CaptureAudit writes failure frame/time and empty_fields into capture anomalies jsonl.gz. Fragmentation, capture truncation and decoder semantics remain hypotheses pending artifacts. Exporter includes anomaly_preflight; screenshot says Pullback archive ready. NEXT user runs existing transfer_v2.ps1 -Mode Pull, then verify archive and inspect anomaly_preflight/first_failure/logs before joint semantic repair review. No automatic retry, no frozen-rule changes, no model-capability conclusion; sealed v2 package unchanged.

### 2026-09-29 latest: Job177491 queued / memory review KEEP192G / no replacement package

User reports pending(Resources), estimated start2026-10-01, node188 available allocation about155G and CPUs sufficient. Authorized a150G-only resource revision IF confidently below130G, otherwise retain192G. Static P/T/K accounting cannot establish the130GiB condition, primarily16E3-worker peak plus parent allocator/cgroup overhead; chose KEEP192G. Existing Slurm192G, treeRSSguard176GiB, train-worker32GiB,16feature/4train concurrency unchanged. Did NOT cancel/update/resubmit/upload or start any resource benchmark. User-operated job177491 is queued; scheduling date is an estimate, not a guarantee.
Read legacy_continuous_input_v2_memory_review_20260929.md and runs/legacy_continuous_input_memory_review_v2_20260929/{estimate.json,decision.json}. Header-only E3 tensor accounting0.65075GiB/worker; metadata sample extrapolation4.545GiB/copy, not hard upper bounds. Phase budgets Pdecode15-60, P16E3 sensitivity63-163, Pmerge15-40,T40-80,K15-40GiB are assumptions, not measurements. Earlier52synthetic tests do not certify target peak memory. v2 approved archive/source/delivery hashes and8 unrelated edits verified unchanged; HEAD4b28747/codex-exp-mainline preserved. If actual P input anomaly stops, pull anomaly_preflight and first failure, no autoretry. Paper PAUSED.

Completion follow-up agreed with Claude: after Job177491 finishes, retain step-level Slurm memory accounting (do not use -X): `sacct -j 177491 --format=JobID,State,ExitCode,Elapsed,ReqMem,AllocCPUS,MaxRSS,MaxRSSNode,MaxRSSTask,AveRSS -P`. Interpret MaxRSS using the cluster accounting plugin and task/step scope; it is not guaranteed to be the simultaneous whole-process-tree peak. AveRSS is not a historical time-average memory curve. Cross-check exported program RSS evidence; status.json contains the latest sample, not a guaranteed historical peak. If P stops early, measurements cover only reached stages and cannot certify later E3/T/K memory. Use these observations for future sizing only: keep current192G/job/package unchanged, no additional monitor, benchmark, remote execution or retry.

### 2026-09-28 latest: continuous-input v2 CLAUDE REVIEW PASS / no blockers / real chain NOT_STARTED

Read collab/20260928_continuous_repair_v2_review_claude.md. Claude approved the exact v2 archive; no v3 needed. Independently rechecked archive SHA7087d73186693ad4c8482027b82ce2f4b6027ed5c1c290045b44a8f0ddef2768, delivery/source pins, and8 unrelated tracked-file hashes. review_acceptance.json in delivery_v2 records the update; original sealed acceptance and package are unchanged. Claude reviewed changes/contract and archive, did not rerun tests; existing52/52 synthetic and delivery results remain engineering evidence only.
Known nonblocking risk: non-initial TCP/UDP fragments may lack namespace ports; actual14/2 UNSW anomalies are still unclassified. If P stops with MISSING_NAMESPACE_HEADERS, FIXED_TARGET_INVALID or LEGACY_*_IDENTITY, preserve first_failure.json and pull anomaly_preflight/ (included by failure export), discuss evidence before any new launch. No automatic retry, no speculative rule changes, no model-failure inference from an input stop. Four priority capture decodes consume existing budget; no completion-time guarantee.
NEXT user-operated upload/execution under explicit final-v2 real P/T/K authority. This review-notification turn contains no real execution authority; no upload/SSH/PCAP/E3/training/CAL/scoring started. Scientific gates, denominator, model and seeds unchanged. Paper PAUSED, independent ID NOT_RUN. Source selected217+external2; catalogue302 is historical inventory count. This entry supersedes pending-Claude-review status below.

### 2026-09-28 latest: continuous-input v2 IMPLEMENTED / synthetic PASS / Claude focused review pending

User explicitly authorized the four aligned amendments and v2 implementation with D1 feasibility. Implemented separate v2 sources/contract/package; parent v1 bytes unchanged and v1 remains upload-blocked. No real PCAP decode, real E3, training, CAL, evaluation, download or remote action. Real P/T/K not authorized by this implementation turn. Paper PAUSED; ID NOT_RUN; HEAD4b28747/codex-exp-mainline and8 unrelated tracked edits preserved.
B1 namespace poison persists to capture end, cross-key timestamp regressions classified. B2 complete-header payload truncation updates context but is not a query; missing-header history blocks fixed targets until provable strict>60s full idle reset; missing namespace headers STOP. Literal legacy float prefix replay checks each anomalous frame/namespace; new nanosecond regressions STOP. Four priority captures are audited before E3; main capture ordering and target denominators unchanged. Selected captures217source+2external, not302; four extra decodes consume the same70h budget. Real anomaly classification remains NOT_RUN.
D1 saved CIC DEV Q weighted attack recall99.938458%, unweighted99.986086% (79045/79056); seed27/127/227 weighted99.944053/99.942579/99.949648%. No weighted99% baseline conflict; not new v2 capability. Main attack gates weighted; historical Q regression unweighted; constants unchanged.
52synthetic tests and6Windows/6Linux installer/export tests PASS; clean Python3.9 extraction, mock submission, Bash, actual PowerShell Mode parameter, pins PASS. v2 archive342818bytes SHA7087d73186693ad4c8482027b82ce2f4b6027ed5c1c290045b44a8f0ddef2768; design SHA8396629e6e2495d98bfc1d4a5288f0570bc1a95d653596419005eb96470f55bd. No actual target E3/resource probe yet. Read legacy_continuous_input_repair_v2_implementation_20260928.md, delivery_v2 acceptance.json, and collab/20260928_continuous_repair_v2_response_codex.md. NEXT Claude focused review; operator still user upload/submit/pull after final-package real authority. Implementation completion is not scientific PASS.

### 2026-09-28 latest: continuous-input v1 UPLOAD BLOCKED after Claude review / semantic reconciliation pending

Claude review identified B1 capture-wide time regression STOP and B2 incomplete accepted context STOP against existing anomaly receipts. Codex independently verified source1/346,2/7424 and UNSW14/2 counts. v1 SHA31bdb60292a47e451b67b79a831c56bd53c5f2f8bf01fe7ff607b524f4369aff unchanged; earlier PACKAGE_READY is superseded as upload eligibility. Synthetic acceptance remains engineering evidence only. No real execution or v2 implementation in this review turn.
Read collab/20260928_continuous_repair_v1_review_claude.md and collab/20260928_continuous_repair_v1_response_codex.md. Key independent finding: legacy ScopedPrefixes appends before INCOMPLETE_TARGET check; query rejection is not context exclusion. Need distinguish complete headers with truncated payload from missing required headers; preserve every fixed UID and stop on unresolved target dependency. Prefer existing-receipt precheck plus integrated full causal audit before E3, not unbudgeted duplicate raw scans.
D1 pending decision: Codex recommends frozen original weighted attack recall for new pool/device/seed gates, unweighted historical CIC regression retained; Claude preferred unweighted attack gates. No gate/contract altered. Align semantics and version amendment before reimplementation/repack; user decides unresolved scientific tradeoffs. User-authorized collaboration uses collab files; Codex single code writer, Claude targeted reviewer, user HPC operator. Paper PAUSED; HEAD/unrelated edits preserved; no upload/submission.

### 2026-09-28 historical: continuous-input repair IMPLEMENTED / synthetic PASS / final HPC package READY

User approved implementation next. Completed current-inclusive causal input/state, exact-shape token/tensor proof, frozen E3 cache path, three matched new classifiers and learned reference verifier, fixed P/T/K runner, first-cause/zero-retry monitoring and standalone delivery. REAL CHAIN NOT STARTED; no real PCAP decode/checkpoint forward/optimizer/CAL/external scoring/download/remote action. Paper PAUSED; actualv0 unchanged; HEAD4b28747/codex-exp-mainline and8 unrelated tracked edits preserved.
Final package legacy_continuous_input_repair_v1_20260928.tar.gz is318692bytes SHA31bdb60292a47e451b67b79a831c56bd53c5f2f8bf01fe7ff607b524f4369aff. Use top-level delivery only; engineering_draft_01/02 are superseded local drafts,not uploads.36synthetic +6installer/export tests PASS; clean Python3.9 extraction,WSL Linux mocksubmission,4Bash syntax,PowerShell parse andseals PASS. Target actualE3 numerical/resource probe remains NOT_RUN and mandatory. Self-review only,no newagents.
Important implementation reconciliation:oldUNSWcache query-before-reference;external role preserved;CIC wrong-reference controls require LEARN+DEV bank.Source verifier subset follows frozen >=2-reference eligible UID census FIT567175;loss API minimum1 does not enlarge it.CALcut still all115672attacks/359875donor pairs.Source andexternal owner rosters remain separate.All1,095,200newfeature rows and12heads/3seeds/40epochs unchanged.
Resource contract:amd64CPU/192GB/72h,16featureworkers*4threads,4trainworkers;program70h/176GiB/160GiBoutputs,200GiBfree required.One integrated target generatedE3 probe beforebulkfeatures,conservative2x estimate plus12hpostfeature reserve;stoponbudget,never thin/retry.GPUunverified.CIC/UNSWconsumedDEV only,independentID NOT_RUN,no scientificsuccessclaim.
Read legacy_continuous_input_repair_implementation_20260928.md and delivery/acceptance.json / OPERATE_HPC.md in runs/legacy_continuous_input_repair_delivery_v1_20260928. NEXT explicit one whole P->T->K authority for this reviewable package; no perstage reapproval within that chain.User uploads/submits/pulls;progress via watch status.sh,no token polling needed.Goal highattacktransfer pluslowOOD falsealarms,not merelyoldexternalQ~60%;historicaldraft/sourcefailures preserved separately.

### 2026-09-28 latest: paper PAUSED / continuous-input core repair DESIGN READY

User priority is core attack transfer with low OOD false alarms before paper writing. Authorized design/self-review completed; no real raw decode, E3 forward, optimizer, CAL, download or remote action. Preserve HEAD4b28747/codex-exp-mainline and unrelated edits.
Selected: pinned E3 reuse, current-inclusive recent12burst/last6packet input plus26dim same-connection causal statistics; one new128hidden attack score plus explicit normal-reference verifier. Consistent FIT/reference/CAL/query semantics, exact-shape batching and actual frame-to-token provenance required. Old Q/R/FULL preserved separately, not stacked into new deployment. Representation repair is not a claimed learning innovation or guaranteed99% recovery.
First fixed proposal: sourceFIT617908/CAL148819, fullCICDEV179886 and consumedUNSW148316,271refs;1095200newfeature rows. OLD-MATCHED/RECENT/RECENT-STATE +RAW/learned paired outputs,3seeds,12smallheads;source-onlycalibration. No external training or repeated thresholds. OldCPU feature-only planning estimate~59h, runtime budget must be settled in implementation delivery. IndependentID NOT_RUN, freshconfirmation later; no earlyhistory expansion.
Read legacy_continuous_input_core_repair_design_v1_20260928.md and runs/legacy_continuous_input_core_repair_design_v1_20260928/implementation_and_review.md +design_contract.json/seal. NEXT implementation/synthetic acceptance/package, not another generic audit; real P/T/K requires later concrete whole-chain authority, no repetitive perstage permission within an authorized chain.
Editorial correction: actual paper remains byte-identicalv0; paper_editorial_refocus writing_brief statement thatv1 was rewritten described interrupted unexecuted work. Paper writing PAUSED; earlier paper-start notes below are historical.

### 2026-09-28 user priority: recent-only review / joint transfer capability first / paper draft started

User narrowed history checks to recent useful results,not early experiments. Review scope Job174251 DEV + Job174666 same-collection device confirmation,and their shared training-cache provenance only. Goal high transferred attack recall with low OOD false alarms remains primary;necessary independentID/baseline/ablation/confirmation after core mechanism signal. Do not reopen oldfewshot/91.91%/closedhistorical pools.
New local saved-feature review of consumed Job174666 complete:archive+featureSHA and341270UID rows verified;original134797/135877=99.20516% attack and30/205345normalFP reproduced. Exact-feature constant suffixes affect62013attackqueries acrossmanysessions (Borun13203,Netatmo36765,Ring12045),not raw-target omission proof;featurevariation also does not prove freshness. OriginalscientificFAIL remains. Job174251 originalnumericalverification retained;fullLEARN/DEVfeatureaudit PENDING remote sealedcache. Localv1/v2preallocated arrays are incomplete and explicitly rejected;do not use as training evidence. Merge needed cachehash check into next necessaryHPCpreflight,not another longoldmodel rerun.
Read recent_evidence_scope_and_repair_priority_20260928.md / SHA; scripts and sealed summaries in runs/recent_evidence_review_and_paper_start_20260928. New working paper paper_draft_commissioning_transfer_20260928.md starts problem/introduction/evidence/evaluation sections;method and performance claims deliberately pending. Olddrafts unchanged. No newPCAP/model/train/CAL/HPC. NEXT one targeted repair contract,consistenttrain/reference/CAL/query input plus attack/normal-evidence responsibilities;boundedjointcapability validation before broad supplementary experiments. User speed preference does not relax scientific gates or independent confirmation.

### 2026-09-28 current: Job177299 saved-cache audit COMPLETE / real source-feature saturation CONFIRMED

User returned authorized read-only audit. Job177299 exit0,status COMPLETE,33.185s audit;target26synthetic PASS. Archive SHA ebf8f920248013dfc4a791c5e876e6b255c5bf08c458780a9be941e9fae742e0;22returned files/export21pins/inner6seals verified. Remote receipt verifies18input pins before/after;contract byte-identical. Local independently checked148408UID metadata and148316saved score hashes. No forward/rawdecode/training/CAL/threshold changes,retries0. sacct_at_exit RUNNING is pre-exit snapshot,not final scheduler evidence;program/export complete.
All5devices:7source-field states,7savedfeatures,7jointscores each;selectedattackquery7 onward identical within each device. Starts~6.3s afterfirst,continues~63.5min across1/10/100rates;fixed12bursts/17-18packets. 72523/72553attackqueries in these tails;global31source/feature states. Duration changes but unused by E3. This closes actual source/feature identity blocker and prioritizes causal continuous-input contract design. Not proof of targetpacket retention or sole cause of misses.
Normalqueries have many distinct states;1842within-device sourcehashes map to multiplefeatures,packing/numeric cause unresolved,no automatictensorreconstruction. No exact attacksource/feature overlap with selectednormal/ref,but that does not establish learnability. Q stillmissesMotion/Samsung and FULL stillrevokes14605Q-correct attacks;prefix saturation cannot excuse both. OriginalFAIL/ID_NOT_RUN/development-corpus/foundation-uncertainty retained.
Read legacy_unsw_saved_cache_audit_job177299_result_20260928.md / SHA;reproducible verification+analysis in delivery/result_review_job177299. NEXT design/review minimal causal input/state repair,prioritize existingE3 reuse and consistenttrain/reference/CAL/query semantics;alsoaddressattacktransfer andfalseveto. Do not rerun samecacheaudit,blindlyretrain,changeonlytestwindow,orlaunchnewfront end project. No new scientific protocol/realcapabilityexperiment authorized by this returned-result review. Goal remains original-domain~99%highattackrecall+lowOOD/IDFPR,not merelyexternalQ59.94%.

### 2026-09-28 current: saved-cache audit IMPLEMENTED / user-authorized delivery READY

User authorized next bounded read-only cache audit; user continues upload/submit/pull. No new remote action performed. Ultimate objective remains approaching original-domain ~99% attack recall with low OOD/ID false alarms; restoring external Q59.94% alone is insufficient.
New standalone tool checks exact18 pinned Job176975 files (503251984bytes),148408UIDs,flow semantic-source hashes,saved768d float32 features,and13saved score values;normal/query/reference/device/component/interval summaries preserved. Before/after input verification,first-failure+zero retries,standalone stdlib export. Actual tensor reconstruction NOT_ENABLED;frame-to-token provenance UNAVAILABLE;no model/raw/optimizer/CAL/threshold changes.
Clean WindowsPython3.9 26synthetic tests PASS;Linux7stdlib tests/3shellsyntax/checksums/mocked submit+failure export PASS;PowerShell syntax/LF/10fileclosure PASS. Local WSL numpy unavailable,target26tests mandatory on output filesystem before real cache reads. Self-review only;no new independent-agent review.
Delivery runs/legacy_unsw_saved_cache_audit_delivery_v1_20260928,16,427byte archive SHA d327ca4fa59be54122a33cde32dbd6ad304096eb1266810943b2d5b0e3ca6b07. Read legacy_unsw_saved_cache_audit_implementation_v1_20260928.md / SHA and delivery/OPERATE_HPC.md. NEXT user uploads/submits once,monitors shell status,pulls compact hash summaries. Authorization covers preflight->read-only audit->export,no additional perstage approval. HPC not started;actual cache conclusions pending. OriginalFAIL,ID_NOT_RUN,consumed-dev-data and foundation-uncertainty boundaries unchanged.

### 2026-09-28 current: attack-transfer diagnosis COMPLETE / effective-input audit next

User clarified simplification means coherent responsibilities, not mandatory module deletion. Authorized bounded saved-result/input-semantic diagnosis and research completed; no new training, forward, raw decode, CAL, threshold search, data acquisition or remote action.
All five devices have seven saved joint score states each; from selected attack query 7 onward, all 13 saved score values remain identical across three rate intervals. Q misses Motion/Samsung entirely; FULL revokes 14605 Q-correct attacks and would also revoke Motion alarms if only Q decisions changed with the saved representation/verifier unchanged. Original FAIL remains.
Static source plus independent generated tokenizer/collator probe confirms early-prefix saturation can hide changed endpoint content; updated flow_duration is not passed to E3. Prior Sep25 tests already recorded truncation; new evidence closes the unused-duration path and relates it to real constant scores. This is a frozen input/task semantic limitation, not a proven recovery regression or a complete causal explanation of attack misses. Real flow/feature contents were omitted locally; equal scores do not prove equal inputs.
Actual deployment is causal input -> E3 -> P2+Q attack function plus FULL normal-reference veto. RAW/NO_CF/M/C are comparison arms, not stacked modules. Q is no longer few-shot. Do not simply repeat conditional heads, attack-protection loss, more epochs or add-device exceptions. Literature and historical negative evidence reviewed.
Read legacy_unsw_attack_transfer_diagnosis_and_repair_direction_20260928.md / SHA; reproducible diagnostics in runs/legacy_unsw_attack_transfer_diagnosis_v1_20260928. NEXT implement/review a read-only exporter of already sealed flow/feature hashes with exact UID identities; user continues HPC upload/run/pull. No model recomputation or raw decode. Spec distinguishes semantic-source, actual-tensor and feature hashes and missing target provenance. Input changes require a new coherent train/reference/CAL/evaluation contract, not a silent patch. This corpus is consumed development evidence; independent ID NOT_RUN and full foundation exposure UNRESOLVED.

### 2026-09-28 current: UNSW recovery Job176975 COMPLETE / scientific milestone FAIL

Returned archive SHA f8a211e863cc39a8335751dc6b6e11a92ac0e916563d1e2b406681c34fd51cbd;651returned files verified,159omitted content not locally verified. Program exit0,all4workers exit0,148blocks/148408UID coverage;148316queries+92refs preserved. Saved14arm decisions independently recounted overall/perdevice. Runtime28796s,no retries/training/CAL/historicalHOLDOUT. sacct at EXIT stillRUNNING is not final scheduler evidence;terminal61.23percent is stale subloop counter,not incomplete scoring.
Q attack43486/72553=59.9369%,normal sample4018/75763=5.3034%,primaryweighted2.6129%. FULL attack28881=39.8068%,48FP/0.0634%sample,0.7532%weighted;14605addedmisses=>FAIL despite71.17%weightednormal reduction. RAW preservesQattack,129FP/0.1703%sample,1.6612%weighted;limited signal,not promotion of preregistered FULL. NO_CF attack19.9964%;R100%attack but92.95%sampleFPR. Learned superiority not supported.
Q misses allMotion14553 andSamsung14506 attacks. FULL newly suppressesTPLink14602 attacks plusNetatmo3;all3seeds fail attack preservation. RAW normal gain dominatedSamsung;only1of8matchedcontrol personalization directions supported. Historical~99% does not transfer to these externaldevices.
Read `legacy_commissioning_unsw_recovery_job176975_result_20260928.md` / SHA; evidence delivery/result_review_job176975. NEXT bounded saved-result/input-semantic diagnosis of Q complete misses and FULL false veto separately;no auto thresholdsearch/training/rerun/newdata. This evaluated corpus is consumed;future result-driven design makes it development evidence. ID_NOT_RUN/fullfoundationUNRESOLVED/passiveonly/oldFAIL retained. No further real experiment initiated.

### 2026-09-27 current: UNSW recovery v2 real evaluation AUTHORIZED / awaiting user submission

User explicitly authorized the complete repaired one-attempt chain: target synthetic+output-filesystem preflight, sealed input verification/copy, full feature recomputation, frozen merge/scoring and export. No perstage reapproval;failure stops,no automatic retry,no training/CAL/scientific changes. User continues to operate upload/submit/pull. Assistant has not uploaded/submitted;new job ID unknown.
Authorization sealed in runs/legacy_commissioning_unsw_recovery_delivery_v2_20260927/execution_authorization_20260927.json / SHA. Exact package SHA7737ea7690f87294a236f5ec1b7e5d372373de7a13b507de66ec5645881bcb28 unchanged and full release reverified. Historical acceptance/build authorized:false records describe the previous preparation stage and do not revoke this later authorization. NEXT user follows OPERATE_HPC.md once;no additional confirmation needed for the authorized chain.

### 2026-09-27 current: UNSW recovery v2 IMPLEMENTED / local validation PASS / real execution NOT_STARTED

User authorized repair. Versioned runtime/runner v2 fixes transient JSON stat race, persists firstcause+traceback before kill, preserves child exitcodes and truthful terminal states. Durable1024row blocks retain UID/model/input/package identity and fsync/seals;frozen model batch16 and arithmetic unchanged. OldJob176411 firstcause remains unresolved;oldFAIL and original package retained.
Recovery verifies/copies old sealed manifests/flows and exact148408UIDs,skips raw decode/selection. Old92.5% partialfeatures NOT_REUSED;all features will be recomputed. New blocks support future explicitly reviewed recovery,not automatic retry. No genuine E3 forward/rawdecode/optimizer/CAL/remoteaction during repair. Existing resource/runtime contract byte-identical.
Clean92file bundle:26old+21new synthetic tests,6installer tests,43generatedpacket/56field parity PASS;4shellsyntax/4mocksubmit/PowerShell parser/Linuxchecksums+fsync PASS. Local actual-output-filesystem synthetic commit PASS;target preflight and output-FS probe mandatory before real reads. Self-review only.
Package runs/legacy_commissioning_unsw_recovery_delivery_v2_20260927/unsw_archival_recovery_v2_20260927.tar.gz SHA7737ea7690f87294a236f5ec1b7e5d372373de7a13b507de66ec5645881bcb28,1930325bytes. Read `legacy_commissioning_unsw_recovery_implementation_v2_20260927.md` / SHA and delivery/OPERATE_HPC.md. NEXT one explicit repaired real-execution authorization,user upload/submit/pull;no perstage reapproval or auto-retry. Roughly8h feature estimate at old throughput,not just remaining7.5%. Oldscience/ID_NOT_RUN/archival bounds unchanged.

### 2026-09-27 scheduler addendum: no recorded timeout/OOM / engineering repair next

User-provided sacct:Job176411/batch FAILED1:0,08:18:01 vs3days,batchMaxRSS9204120K(~8.78GiB),ReqMem96G,node188,ReasonNone. No timeout/OOM state or batch termination signal;not individual Python worker exit evidence. DerivedExitCode0:0 does not mean workers succeeded. No basis to increase resources. Actual first watchdog trigger remains NOT_PERSISTED/UNRESOLVED;do not claim atomic-rename candidate proven.
Read `legacy_commissioning_unsw_job176411_scheduler_addendum_20260927.md` / SHA. NEXT bounded engineering repair of monitor/error persistence/terminal states/checkpoints and validated recovery plan,not more repeated status queries or scientific redesign. Oldpartialfeatures not certified for resume;sealed manifests/flows are conditional reuse candidates. No repair delivery or real retry yet;preserve oldjob and frozen science/zero-auto-retry boundaries.

### 2026-09-27 current: UNSW Job176411 FAILED at E3_FEATURES / returned evidence verified

User returned evaluation_pullback.tar.gz SHA cd2a8b98161196f7c41f9e7c3a4d7a1fb8339d69a142e392629c22e6162d3c62; all31 included files and inner manifests/preflight seals verified. Ten omitted files have export pins, not local content verification. Job exit1, screenshot FAILED08:18:01; no evaluation scores. Target26synthetic PASS;148316queries+92refs sealed. Last worker progress137280/148408(~92.50%) is not a recovery checkpoint. Allfour logs only deprecation warning;no worker UID/completion seal.
Confirmed engineering defects by two local synthetic injections: transient atomic-status rename may break disk scan; watchdog kill-all can lose first exception and retain only FEATURE_WORKER_FAILED. Actual HPC first cause NOT_PERSISTED/UNRESOLVED;do not call candidate trigger proven or blame data/model/OOM. Read `legacy_commissioning_unsw_job176411_failure_review_20260927.md` / SHA; evidence in delivery/result_review_job176411.
NEXT obtain sacct step/exit-signal/MaxRSS evidence, then bounded monitor/checkpoint repair and recovery review. Preserve failedrun and oldpackage; no auto-retry, no skipping samples, no thresholds/model/denominator changes. Sealed manifests/flows are reuse candidates subject to full verification;partial features not yet certified. No remote actions or real rerun in this diagnosis. OldFAIL/ID_NOT_RUN/archival-only boundaries unchanged.

### 2026-09-27 delivery correction: checksum CRLF / submission not started

User screenshot: sha256sum interpreted trailing CR as filename, so set-e stopped before install/submission. Both sidecars corrected to literal LF; payload/archive SHA unchanged. Generator and upload guard fixed; local Linux checksum and PowerShell syntax PASS. See delivery/checksum_lf_fix_v1/correction.md under runs/legacy_commissioning_unsw_evaluation_delivery_v1_20260927. Original release seal retained; current release seal refreshed with provenance. NEXT user runs corrected OPERATE_HPC.md install/submit block; no reupload required, no assistant remote action or real evaluation performed. Prior scientific boundaries unchanged.

### 2026-09-27 current: UNSW archival evaluator IMPLEMENTED / small HPC package READY

User authorized implementation, synthetic validation and delivery. New run `runs/legacy_commissioning_unsw_evaluation_delivery_v1_20260927`; no real raw/model/optimizer/CAL/remote action. Recipe1476a79d unchanged:5devices,75763normal+72553attack+92refs,three seeds,frozen cuts. ActualUID manifests and model result NOT_RUN.
New versioned EXTERNAL_ARCHIVAL_EVALUATION entry preserves original causal prefix/translator/FrozenR/Q/metric arithmetic; sourceSHA/MAC identities and truthful2026declaration vs2018archive, no LEARN/name bypass. Full population/15interval counts and UID seal required before any feature forward. Shared feature cache;Q/RAW/FULL/NO_CF/R;8matched controls;singleton fallback retained.
Local final validation:26synthetic+6installer tests PASS,43generated packets/56fields exact TShark parity,87file clean package/preflight verified,4shell scripts and PowerShell syntax PASS,4mock submission checks PASS. Self-review only. TargetLinuxPy3.9.25/torch2.5.1/tokenizer preflight mandatory before real reads; Windows localPASS is not targetPASS.
Package unsw_archival_evaluation_v1_20260927.tar.gz SHA f40aeaab3c626070830a46d6c69906337417c5a4242768aaa49477bbbad1d12d;1912096bytes. Reuse remote twoPCAP and pinned E3 checkpoint;no7GB retransfer. amd16CPU/96GiB/72h scheduler,80GiB/70h/64GiB program guards,4CPUworkers*4threads,zero retry;limits not ETA. Visible progress/percent/current-stage ETA,terminal guards and bounded export.
Read `legacy_commissioning_unsw_evaluation_implementation_v1_20260927.md` / SHA d1a8278776dfc82102e0cfca27421d97a42299f05ff5adb8d3f832e994db8e55. NEXT user follows delivery/OPERATE_HPC.md to upload and explicitly submit --authorize-frozen-evaluation (one preflight/materialize/score/export chain),then pull back. Assistant must not auto-submit or request repeated per-stage approval. Export_manifest distinguishes returned files from omitted large intermediates. OldFAIL/ID_NOT_RUN/passive-only/foundation-uncertainty boundaries unchanged;no scientific success claimed.

### Historical 2026-09-26: UNSW fixed evaluation input rules FROZEN / implementation next

User accepted next fixed-five-device input preparation. New run `runs/legacy_commissioning_unsw_evaluation_preparation_v1_20260926`; recipe SHA 1476a79dcd13f814dcf57dfe26d195d41191205adc79dcc8db40cd8351fb9b97. Rules/roster/label evidence/lineage/control plans and self-review sealed. NO new raw decode/model/optimizer/CAL/HPC or protected historical query access; actual query/ref UID manifests NOT YET materialized.
Verified766,727 Q LEARN metadata rows/169source captures: six training devices, no targetMAC or two-sourceSHA overlap; verifier FIT617908/CAL148819 subsets and all11 CIC identity/source catalog disjoint. OldR27FITprefix names audited narrowly; foundation/checkpoint/all-old-threshold exposure still UNRESOLVED. All5 oldUNSW metadata appearances retained, not training proof. NetatmoCIC70:ee:50:68:0e:32 differs UNSW70:ee:50:18:34:43; no rename trick.
15narrow SYN derived label rules verified against official annotations/workbook and saved source/service census;72,553 positives all kept. Normal population983,788; cap20k/device,all components represented,deterministic quotas/hash sampling gives75,763 normal queries. Total148,316queries+92refs expected;UID seal pending. TCP singleton Switch/Samsung stayQ fallback/denominators;no policy/model/cut/seed changes.
Primary Q/RAW/FULL plus NO_CF/R and8matched same-time/protocol/count donor controls shareonefeaturecache. New archival milestone: zero additional attack misses ensemble+everyseed;>=30%primary weightednormalFPR reduction with gains>=2of3bothprotocol devices; oldFAIL unchanged and absolute capability still reported. Claims external passive archival transfer only, not all-foundation unseen/ACTIVE/novel mechanisms;ID NOT_RUN.
Read `legacy_commissioning_unsw_evaluation_preparation_v1_20260926.md` / SHA 5dc8a99f49fb118cdc065b2ff0695b847bf36530c7dfdd548c4a232e5c78b8aa. NEXT implement versioned archival evaluator+synthetic checks/package: old validator LEARN/DEV/name-only consumed guard/declared_at<t0 incompatible; preserve old code, enforce real source/MAC identity, truthful2026declaration vs2018capture. Materialization must reconcile original full counts before any feature/score. Reuse remote twoPCAP;user upload/submit/pull. Current metadata preparation does not authorize real model execution.

### Historical 2026-09-26: HPC Job176183 COMPLETE / returned qualification verified

User reports run finished and pulled back. Outer SHA + target preflight12/qualification169 sealed files PASS; exact delivered contract/package/source identities and authorization preserved. Script exit0/COMPLETE, both decoders exit0/empty stderr/no dropped rows/no retries; sacct not in returned archive, not independently queried. Target Py3.9.25/TShark4.6.6 full generated parity PASS. 10,140,230 packets fully reconciled;770.907s. Sampled RSS maxima6.559/5.722GiB; former5GiB local blocker resolved without semantic changes.
Five source pairs all have same MAC/officialIP and normal-before-attack evidence. First-hour22,784 legal positions; later normal983,788; narrow SYN candidates72,553 across15 preset intervals. TCP/UDP components: Motion603/20,Switch1/2,Samsung1/2,TPLink2/3,Netatmo7/10. Three both-protocol minimums; twoTCP singleton devices remain Q fallback and in denominator. Counts are candidate positions, not final UID/sample denominators or independent trials.
Read `legacy_commissioning_unsw_hpc_real_result_v1_20260926.md` / SHA a8a57ea759811b2979c568381c623df1b5f2b4458cc69307a5c03b32251e50b2. Evidence in delivery/result_review_job176183 and pullback/verified_job176183. Original decoded evidence and failed attempts unchanged. Final status display lags207 packets because8192-frame tick; final decoder count exact, no rerun needed. Normal file2capture gaps retained,0truncation/time regressions.
Scientific boundary: PASSIVE_ONLY/no six-phase operations; final attack labels and bank/roles not materialized; all5MACs present in older UNSW metadata, not proof of training but full-history/E3 independence unresolved. No model outcome; old FAIL and ID NOT_RUN unchanged. This turn0raw decode/model/remote actions.
NEXT recommend fixed five-device passive/archival evaluation preparation: resolve candidate label evidence and lineage claim, then freeze refs/queries/per-device denominators for frozen Q vs commissioning comparison. Keep deficient-device fallback, do not extend observation/delete devices/retrain. Model evaluation needs concrete scope and explicit authorization; full ACTIVE/new-device claims remain unproved.

### Historical 2026-09-26: HPC qualification package READY / target execution not started

User accepted higher-memory package preparation. Delivery `runs/legacy_commissioning_unsw_hpc_delivery_v1_20260926/OPERATE_HPC.md` contains user upload/explicit submission/status/pull commands. No assistant SSH, upload, sbatch, raw decode or model action. Code/data separate, visible resumable rsync. User submit flag --authorize-qualification-only grants one qualification attempt; no model authority.
Resource contract: amd 4 CPU / 64 GiB / 06:30 scheduler; 48 GiB combined guard / 21600 s raw limit / zero retries. Same two 7.02GB PCAPs, all five devices, exact original fields/Census/causal semantics and annotations. Original frozen local scope and failures preserved.
Local acceptance PASS: both source+archive member SHA and clean installation; Windows Py3.9/TShark4.6.6 23 passed+Linux skip; Linux 23 passed+TShark skip; combined all24 new cases covered. Installer6 each platform, mock lifecycle5, shell syntax pass. Generated43 packets/56 fields/full Census/scientific summary parity exact; clean extracted local preflight PASS. Target compute-node preflight STILL PENDING and mandatory before real reads.
Read `legacy_commissioning_unsw_hpc_delivery_v1_20260926.md` / SHA e40babc70915350ba185b6b9a3daa1f820b86346c0393e7b2ef2f04c42c7e0d7. Original27/diagnostic13/oldfailure70 pins and8unrelated edits unchanged. HEAD4b28747, branchcodex/exp-mainline. Raw qualification incomplete; full ACTIVE/packet labels/E3 independence unproved, old scientific FAIL and independent ID NOT_RUN unchanged.
NEXT user uploads and explicitly submits the prepared qualification-only job, then pulls back for evidence interpretation. Do not re-download/repackage inputs, auto-submit, reset streams or bypass target parity if it fails.

### Historical 2026-09-26: DIAGNOSIS COMPLETE / configured 5GiB guard confirmed, full qualification incomplete

Authorizedone-pass firstfilediagnosis stopped after289.5s at11:27:28UTC with directlymeasured COMBINED_MEMORY_LIMIT. RSS5,449,461,760bytes=5.075207GiB vs5GiB;TShark4.928482GiB,Python0.146725GiB. Watchdogrecordedcause beforekill;bufferendedwithhalfrow4077119 after4,077,118acceptedframes. CSVcolumnerror secondary;noevidenceofOSOOM/naturalTSharkcrash/badpacket. Original405万-framefailure stronglymatched but itsmissingRSS notretroactivelyproved.
Read `legacy_commissioning_unsw_decoder_diagnostic_real_result_v1_20260926.md` / SHA `637cacd45696a15bf1e40d3ffb4502b5157fd34ad0ae25d9b2fca9e833f8195a`. RuntimeSTOPPED_NO_RETRYpreserved,diagnosisgoalcomplete.57samples,5/5resultseals,independentagentread-onlyreviewPASS;27originalpins/13diagnosticpins/70oldfailurepins/8unrelatededits intact. BenignfullSHA rechecked;0newmixedrawreads/model/CAL/HPC. Session41243ended;no active experiment.
Rootdashboard/status nowexplain confirmedcause;rawdiagnosticsealedin decoder_diagnostic_execution_v1 andinterpretationin decoder_diagnostic_result_review_v1. Originalexecutionuntouched. Fullnormalcausalresult andmixedqualification unfinished;notdataqualificationPASS. No rows/fields/context/bounds changed.
NEXT recommendprepare higher-memory qualification environment/HPCpackage,sameTSharkversion/fields andcontinuousperfileparse;userupload/submit/pull workflow. Localphysical15.797GiB/available6.905GiB afterstop;firstfilelinearplanningestimate6.745GiB notguaranteedpeak,mixedRAMunknown. Do notblindlyraise localcap/retry5GiB orresetstreams via-M/chunks. Newresourcecontract/fullqualification/HPCnotauthorized by completeddiagnostic;noautolaunch. OldscientificFAIL/ID NOT_RUN,ACTIVE/labels/E3independence boundariesunchanged.

### Historical 2026-09-26: first-file diagnostic authorized and launched

User explicitly replied“允许”to onefirstfile/15min/5GiB diagnostic. Newauthority decoder_diagnostic_authorization_v1.json binds sealedplan f2410cac941dd6418a1f0bf234ee7928db96b6c93e5db4ddd5d7b8ef96c6be84. Originalplanfalse/originalfailure stayhistorical;this distinct authorizeddiagnosis hasonepass/zeroautoretry. No repeated stageapproval within accepted diagnosis/result interpretation.
Read `legacy_commissioning_unsw_decoder_diagnostic_authorized_v1_20260926.md` / SHA `0e9aa7d8c9613665e3d882591838613371f84c429cf5fec16b0590cb347f4af1`.13diagnosticpins/27originalpins/70failedartifactpins/8unrelatededits verified. Independentread-onlycode review confirms unchangedfields/command/Census/guards. Session41243;rootstatus/dashboard + decoder_diagnostic_execution_v1/status current. Resource/exit/rowshape evidence writeslocally.
Onlybenign5,413,239frames maximum,900s/5GiB;secondPCAPclosed,no model/CAL/HPC/roles/banks. Oncompletionorstop inspectseal andexplaincause;noautomaticfullqualification. Fullqualification/ACTIVE/labels/unseenproof pending;oldscientificFAIL/independentID NOT_RUN unchanged.

### Historical 2026-09-26: raw qualification stopped, diagnostic implementation prepared

Actualrawattempt1 stopped07:35:58UTC with DECODER_COLUMNS after lastprogress4,055,040/5,413,239benignframes. Completebenignstructuralcheck has0truncation/0timeregression/all5MACs,but no completedcausal summary andmixednotdecoded. Download7.02GBremains complete. Session11152ended. Originalexecution/logs immutable andsealed bydecoder_failure_review_v1/failed_execution_pins.json.
Read `legacy_commissioning_unsw_decoder_failure_diagnosis_v1_20260926.md` / SHA `040883e6d4d985cc90f3da3a154789efc633bd82f8d4e1de3d6224712d95edcf`. Syntheticfailure injection confirms originalreader can mask watchdog stop aspartial-rowcolumns;actualrootcause UNDETERMINED because memory/exitcause notsaved. Do not assert memory failure from timing alone.
Newdecoder_diagnostic_v1.py + run_decoder_diagnostic_once_v1.py retainexact originalfields/TShark/Census/prefix/bounds,addresource/exit/rowshape evidence.5/5syntheticchecks PASS incl exactgeneratedCensusparity,maskingreproduction andno-authority-before-raw gate.27originalpins/8unrelatededits preserved.0newrealPCAPdecode/model/CAL/HPC thisturn.
Concreteplan decoder_diagnostic_plan_v1.json is user_authorized=false:one first-benign-only diagnosticpass,max5,413,239frames/15min/5GiB,noauto-retry,mixedclosed. Originalretries0 retained;needs explicit newdiagnosticread authority afteractualrawfailure. RootUI explains blocker;do not restart originalexecution orchangefrozenrules. Fullqualification/ACTIVE/labels/unseenproof pending;oldscientificFAIL andindependentID NOT_RUN unchanged.

### Historical 2026-09-26: download complete, original raw qualification launched in pinnedPython3.9

TwoofficialPCAP7,020,234,000bytes completed06:45UTC;full localsize/SHA verified for both. V4handled one transient interruption automatically. Download sessions10434/85979ended;do not relaunch acquisition.
Original automatic qualification launch failed before rawread:bundledPython inherited via sys.executable lackeddpkt. Originalqualification.log preserved andexecution didnotexist. This was assistant runtime wiring error,not scientific/input failure. Read `legacy_commissioning_unsw_download_complete_and_runtime_repair_v1_20260926.md` / SHA `b69f17aac7a612fe717200e7e153c726802558ec67a87619617022c59bca69d2`.
Repair explicitly selects original pinnedPython3.9.13;dpkt1.9.8available,8/8original synthetic tests (including actual TShark on generatedPCAP)PASS. FullsourceSHA,original27pins,8unrelatededits preserved. New11repairpins/acceptance;unchangedqualify_once.py. Exclusivenewcontroller/log plus noexecution guard;actualrawattempt1,retries0. No installation/model/CAL/HPC/protocol change.
07:30UTC realcensus RUNNING,SOURCE_SHA_AND_STRUCTURE ofbenign. Session11152/controller44380. Rootstatus/dashboard andexecution/status current;V4download100% only historicaldownload completion. Original6h/5GiB limits remain;no rawretry. Finalexecution/result.md,summary.json,SHA256SUMS pending. Existingauthorizedchain continues,no repeated stageapproval. Scientificlimits unchanged:passive-only,allfive retained,candidate-labelsonly,ACTIVE/E3independence unproved,oldFAIL andindependentID NOT_RUN.

### Historical 2026-09-26 transport: V4 resumed and subsequently completed acquisition

V3 stopped73.06% at05:27UTC:three consecutive HTTPS handshake timeouts. This differs from earlierV2 connection-refused error;no data/model failure. Current06:16UTC proxy and diagnostic-direct HEAD both200 with unchanged official size/ETag;actual download keeps existing proxy,VPN/settings unchanged.
Read `legacy_commissioning_unsw_transport_continuation_v4_20260926.md` / SHA `2c5e6ac890dc8dfc1564101956250ea25127ac217a4059dd1cdfbe0eb848b1ab`. Completedbenign SHA and983,296,673-byte mixed prefix/124segment records verified;27original pins and8unrelated edits unchanged. V4 uses bounded automatic transient waiting,15s-to5min backoff with UIcountdown,30min no-byte limit,original24h deadline and400additional-transport-error cap. Identity/ETag/range/certificate failures still fatal;scientific raw retries0.8/8offline integration checks PASS,145newtransport pins sealed;no subagent this turn.
Download resumed beyond old offset. Rootstatus/dashboard now follow acquisition/resume-v4/status.json;last_byte_utc records actual bytes,utc status time,monitor_updated_utc display only. V4 sessions10434/85979;V3sessions83384/32267ended. Rawcensus NOT_STARTED at repair;unchanged once-only original qualify_once.py automatically follows completed acquisition. Read freshstatus;do not restart historical downloaders. Existing two-source chain remains authorized,no model/CAL/HPC/newdata authority. ScientificFAIL,passive-only qualification scope and independentID NOT_RUN unchanged.

### Historical 2026-09-26 transport repair: V3 resumed, subsequently stopped on TLS timeouts

V2 actually stopped at59.55%,2026-09-26 03:48:33UTC:three consecutive zero-byte ConnectionRefusedError(10061),not scientific failure. First4,145,381,196-byte benign complete/SHA verified;35,383,969-byte mixed prefix/eight prior segment receipts verified. Existing8unrelated edits and27original pins unchanged. Current proxy endpoint and original official HEAD now respond;historical exact network cause unproven,no VPN/proxy change.
Read `legacy_commissioning_unsw_transport_continuation_v3_20260926.md` / SHA `fb2960cd7d152047dc7cce0de96381cf246e29a4f8ecee9ce280821eec167090`. New23transport pins and20/20 independent synthetic checks PASS. V3 reuses complete first file and resumes second,identity checked8MiB ranges;max20additional transport interruptions/3consecutive stalls,30/60s backoff,original24h deadline retained. No raw retry or change to scientific scope.
Current real download RUNNING;rootstatus/dashboard point to acquisition/resume-v3/status.json. Controller started only after V3 status exists;unchanged qualify_once.py automatically runs once after complete acquisition. Sessions83384/32267;V2sessions14886/1428ended. Raw census NOT_STARTED at repair;read freshstatus. Original/V1/V2 failures retained historical;do not relaunch them. Original accepted chain remains authorized,no model/CAL/HPC/newsource authority.

### Historical 2026-09-26: UNSW two-PCAP authorization / initial launch

User objective clarification (2026-09-26): primary attack-generalization claim is detection on devices or collection environments excluded from attack training, with attack patterns that may be similar to training. Completely novel attack mechanisms are not a required mainline objective. Preserve exact historical metrics and frozen experiments; do not relabel old91.9089% unseen-name-family recall as the same test as new99.20516% device-confirmation recall. The latter is positive cross-device evidence within CIC2022 (three held-out devices at evaluation time),not yet external-collection validation. FULL preserved Q recall rather than improving it. New normal history is allowed only under the declared causal commissioning rules; this is not unconditional zero-shot detection. Current priorities remain joint attack preservation + OOD false-alarm reduction,external-device/source confirmation and independent ID;this clarification grants no additional model-run or protected-data authority.

User replied `核验` after the concrete two-file proposal; this authorizes acquisition and bounded raw qualification,not a model experiment. Read `legacy_commissioning_unsw_raw_authorization_and_launch_v1_20260926.md` / SHA `6096ae41f41aee19bc0a6871c2d31edf6187cc23140f4cd75ab2ebb66898834f`.
Run `runs/legacy_commissioning_unsw_raw_v1_20260926/`: scope,27code/metadata/runtime pins,8/8synthetic PASS plus range guards sealed. Actual TShark only used on generated packet so far. No new packet labels/roles/banks/features/models/CAL/HPC. Branch/HEAD and8unrelated tracked edits preserved.
Exactly benign/18-05-28.pcap + AttackAndBenign/18-06-01.pcap,total7,020,234,000bytes;all5fixed candidate devices.56same-day annotation intervals,15narrow directTCPSYN candidate rules;source/workbook attacker192.168.1.205,notCIC attacker.28knownMAC guard;firstnormalcapture's fixed1h is passive feasibility only,notACTIVE certification/policy revision.
Transport update:read `legacy_commissioning_unsw_transport_continuation_v2_20260926.md` / SHA `d230984b95ac5dc4ea4ddf8f9a6cd68a568fc03377c217acadf8f18f8150de18`. Original download ended at116,529,418bytes;32MiB range continuation ended at377,541,943bytes. Both retained. Same-client HEAD confirms size/ETag/ranges. V2 preserves exact prefixSHA and uses8MiB ranges/If-Match,per-range identity/SHA;short responses advance only received bytes. Max20additional transport interruptions/3consecutive stalls/24h;no raw decoder retry,URL/proxy change or scientific rule change.
At updated handoff,V2range transfer RUNNING,first5segments complete,total419,484,983bytes(5.98% snapshot);actual raw census NOT_STARTED. continue_v2.py is already running and will execute unchanged sealed qualify_once.py exactly once after complete verified acquisition. Source SHA/structure then causal legal-input+time/owner/annotation census,independent count reconciliation,report/seal. 5GiB parent+tshark,6h decode limit;failure stops. Do not relaunch acquisition or continuation.
Root status.json/dashboard.html/show_status.ps1 expose progress without model polling;current internal transfer status=acquisition/resume-v2/status.json. Initial/v1 STOPPED statuses and original README'sv1path are historical,superseded by CURRENT_STATUS.md. Final data result will be execution/result.md + summary.json + SHA256SUMS;check fresh status before claiming completion. Active unified sessions:transfer14886,continuation1428;old19177/35664/79729ended. No scheduler automation created.
Retain allfive devices and fallback;no score-informed filtering. Fullactive six-phase logs and all-history/E3 unseen proof remain unresolved. Frozenpolicy/model/cuts/seeds,oldJob174666FAIL,consumedconfirmation and independentID NOT_RUN unchanged. NEXT let authorized chain finish,then interpret source qualification;no reauthorization for already accepted chain, no automatic modelrun.

### Historical 2026-09-25: External paired-data research COMPLETE / UNSW selected for prospective raw qualification

Read `legacy_commissioning_external_source_research_v1_20260925.md` / SHA; 17 sealed evidence files in `runs/legacy_commissioning_external_source_research_v1_20260925/`. Report SHA `47487103fc300dd0f20e44418fba353161913da5bf27d0a6aa68144179dac0c9`.
User authorized targeted external data research. Official sources and two public annotation files inspected;30,776metadata bytes downloaded,4PCAP HEAD requests,0rawPCAPdownload/decode/forward/train/CAL/HPC/newroles. Four historical metadata/policy seals and8unrelated edits verified;branch/HEAD unchanged.
Primary UNSW Attack Traces:27benign/17mixed daily files;10MACs,234annotation intervals,174TCP/UDP-family candidates across9devices,78directTCP/UDP intervals. iHome onlyARP remains unsupported. Interval counts are not independent trials or legal packet counts;111Excel date anomalies,3five-column rows and capture-gap notes retained. No blanket time-window packet labels.
CurrentCIC11 MAC overlap0;priorUNSW-IoTraffic metadata overlap9/10,not proof of training exposure. OldCKDE23lineage groups resolved to iotsim/ToN,not this roster;all-history downstream/E3pretraining exclusion still unproved. One testbed/two cohorts,not9independent environments.
NEXT recommend raw qualification only of official benign/18-05-28.pcap + AttackAndBenign/18-06-01.pcap,7,020,234,000bytes HEAD total;5candidate devices/15directTCPSYN annotated intervals. No raw acquisition/decoding is authorized by this research receipt. Qualify identity/time/labels/complete fixed-hour counts before scaling,retain insufficient-reference devices and fallback;no outcome-based selection.
Passive normal-history transfer may be testable;fullsix-phase active-policy evidence still lacks operation logs. UNSW has no CIC Active directory contract;do not silently call it ACTIVE or rewrite t0. Active-effect claim requires logged prospective evidence or equivalent genuine source. CICIoT2023 is backup;do not resume same-local-CIC2022 rediscovery.
Frozen1h/min2/cap64/model/cuts/seeds,oldJob174666FAIL,consumedconfirmation and independentID NOT_RUN unchanged. No new scientific result.

### Historical 2026-09-25: Unused local RAW QUALIFICATION COMPLETE / full-policy new confirmation NOT_READY

Read `legacy_commissioning_unused_raw_v1_20260925.md` / SHA; full evidence and seal in `runs/legacy_commissioning_unused_raw_v1_20260925/`. Report SHA `8adad64a59fb6d282028203103abbc0035bfe60463711bbba6f1ae68f4f93398`.
Authorized single run COMPLETE in3346.078s,51candidate+7conditionalActive captures;zero retries/forwards/train/CAL/download/HPC. Independent structure/decoder counts,source/code pins,8unrelated edits and branch/HEAD verified. No query roles/labels/banks assigned.
Gosund identity=c4:dd:57:0c:39:94,official ESP_0C3994 Plug;normal/attack MAC and chronology PASS.30normal files241legal candidates;attack TCP2015SYN+UDP2827826payload,HTTP0. One new downstream-unused device pair,not millions of independent trials;E3 pretraining overlap unresolved.
SevenActive days52840legal positions,allbeforeattack;fixedActive00hour910positions(TCP190/UDP720) but1TCP+1UDPcomponent,neither meets frozenmin2. Cannot activate verifier;no longer-window/duplicate-reference substitution. Operations UNKNOWN_PASSIVE,not active commissioning evidence.
Luohe identity=7c:a7:b0:cd:18:32 confirmed;8/9normalfiles18574candidates,3Nmap mixedcaptures lack existing labelcontract. ActualDESCRIBE/SETUP/PLAY/200observed;no blanket/Hydra labels. Null attack-label time is unknown chronology qualification,not proven inversion;noLuoheActivecensus.
0newdevices qualify fullpolicy jointconfirmation;oldJob174666FAIL,policy/model/cuts/seeds/roles/denominators,consumed3confirmation and ID NOT_RUN unchanged. NEXT targeted independent paired-data/operation-evidence sourcing with complete sample qualification before scaling;end same-local-corpus rediscovery. No automatic scoring/train/download/HPC or protocol change.

### Historical 2026-09-25: Unused local candidate RAW QUALIFICATION AUTHORIZED / launched once and completed


User accepted actual-flow checks of the51pinned local files:device identity,normal/attack chronology,existing label applicability and legal input quantities. Includes conditional same-owner availability census in the existing7Active sources only if candidate identity/label/chronology succeeds.0newdownload/model/optimizer/CAL/HPC;zero raw retry.
Scope/code/runtime receipts in `runs/legacy_commissioning_unused_raw_v1_20260925/`.8/8synthetic tests PASS,including realTShark on generated packet. Inherited frontend/owner guard/label code pins verified. Gosund8possible MACs audited without picking by performance;Nmap never receives Hydra or blanket positive labels. No query role or label assignments.
NEXT execute once,then reconcile and seal real input findings. Source/model scientific conclusions pending. PriorFAIL/roles/denominators and independentID NOT_RUN unchanged.

### Historical 2026-09-25: Existing-data readiness audit COMPLETE; new joint confirmation NOT_READY

Read `legacy_commissioning_data_readiness_v1_20260925.md` / SHA; manifests, exposure ledger, member list and verification in `runs/legacy_commissioning_data_readiness_v1_20260925/`.
Report SHA256: `a9c06ef4140566f3520a605facb83df8a75ca9a39af8d88683a5a0f722d3cd95`. User authorized existing-data checks.0raw/archived-body reads,0query rows/forwards/training/downloads/HPC. Source metadata seals and directory arithmetic verified;raw existence/size checked,prior raw SHA inherited.8unrelated edits and branch/HEAD preserved.
Current11devices are6LEARN+2DEV+3consumedconfirmation:0qualified fresh joint-confirmation devices. Full CIC2022 archive864normal/96attack PCAPs;13attack labels minus11used leaveGosund Plug-Roomba andLuohe. These are directory candidates,not2verified physical devices.
Gosund:30normal+9flood files,262944093bytes;8possible official identities unresolved. Luohe:9normal+3Nmap files,34254006bytes;Nmap mixed target labels unresolved. Total51members/297198099bytes already in local archives;not in prior295qualifiedmembers. Exact paths pinned. Their packet chronology/legal target counts remainUNKNOWN;archive mtime not packet time. E3 pretraining overlap unresolved.
Another26normal-only directory labels/606PCAP candidates lack matching attack directories;could support benign-only extension,not same-device joint protection.7Active files7.22GB/58.788h/11749238packets exist,but prior device census coversonly11useddevices;other owner counts unknown. No six-phase continuous operation log;ACTIVE remainsUNKNOWN_PASSIVE. More packets do not replace new devices/independent runs.
Prior23device CKDE material has0same-device attack pairs;ToN/Gotham role/mapping gaps retained;UNSW/PNNL/CICModbus metadata not runnable paired raw replacement. No broad disk search or protected pool reopening.
NEXT one bounded raw qualification of51pinned candidates,prioritizeGosund identity;conditional same-owner Active counts only if identity/label evidence warrants. No newdownload needed for these leads;not executed by this metadata audit. If candidates cannot qualify,stop same-corpus rediscovery and specify external paired material/new collection or explicitly narrower normal-only claim. Main model experiment not ready;oldFAIL,policy/model/threshold/seeds/denominators and ID NOT_RUN unchanged.

### Historical 2026-09-25: Unified commissioning REAL INPUT PREFLIGHT COMPLETE; no model result

Read `legacy_commissioning_real_preflight_v1_20260925.md` / SHA; evidence and acceptance in `runs/legacy_commissioning_real_preflight_v1_20260925/`.
Report SHA256: `09507934f10afa4f0aa56783d0a3e0539f1ab519f9bd48510abb000b5928114a`. Authorized fixed chain completed once in207.797s,zero retries.11 source captures verified; normal85856frames plus attack3003599frames decoded with native limits.64 target UID/label/causal checks PASS;6 new synthetic adapter checks PASS;prior92 tests retained.
First-hour complete LEARN/DEV enumeration:22874owner events,21211legal endpoints,540components,295planned referenceUIDs;0encoded/registered.5/8devices both protocols,2/8UDPonly,1/8neither;previous component counts confirmed. EufyTCP0,HeimVisionTCP1 remain ineligible for verifier. Active UNKNOWN_PASSIVE;retrospective clock sentinel is not2021 preregistration.
Original11DEV Q misses:all11target packet fields survive original prefix,translator and pinned pure tokenizer methods;0cross-stream mixing/0capacity saturation;11current TCPpayload label rules apply.22matched-correct controls retain all targets too. Miss inputs1-3packets;9matched TCPpayload-correct controls4-6packets:posthoc short-context hypothesis only,not causal proof. All53correct controls include7target omissions;duration may retain current information.
Tokenizer uses pinned source methods with inert library-container stand-ins,not full transformers runtime;strip_payload=True. No inference that retained fields convey sufficient attack semantics. Original pure-bridge false source/mapping fields have layer-specific meaning;outer receipts prove decode/hash/frame trace. Shared normal capture decoder sees other owners;only8LEARN/DEV retained,no newconfirmation queries/results opened.
0model forwards/updates/CAL/downloads/HPC;model binaries not rehashed.8unrelated tracked changes preserved;branch/HEAD unchanged. Job174666 scientificFAIL,oldhardDEV pool/legalbanks,consumed3confirmationdevices and independentID NOT_RUN unchanged.
NEXT address genuine commissioning evidence/untouched paired-device readiness under frozen rules;existing Active can only support a passive DEV projection. No automatic scoring/training/newdata or confirmation. Attack enhancement,if pursued,requires justified short-context coverage/representation design;this11miss audit does not justify prefix expansion or resetting by stream,nor generalize toNetatmo1080misses.

### Historical 2026-09-25: Bounded real input preflight AUTHORIZED / prepared for one launch

User accepted the fixed LEARN/DEV real-input chain: source identity, first-hour normal reference planning, original 11 DEV Q misses plus frozen controls, report/seal. No model forwards, optimization, calibration, new confirmation, downloads or HPC; zero retries.
Inputs and execution code sealed in `runs/legacy_commissioning_real_preflight_v1_20260925/`. 64 unique attack targets / 10 DEV captures; 11 misses each have 2 matched-correct links, plus structural controls. Active-00 fixed first hour only; 8 LEARN/DEV owners. 6 new synthetic adapter tests PASS, prior 92 tests retained.
Tokenizer audit uses pinned pure source methods with inert library containers, not actual transformers runtime validation. Passive replay declaration clock is explicitly retrospective; no historical operation logs or active commissioning claim. Old scientific FAIL, query denominators, references and ID NOT_RUN remain unchanged.
NEXT launch once and seal the input findings; no repeated approval within this authorized chain.

### Historical 2026-09-25: Unified commissioning IMPLEMENTATION / SYNTHETIC PASS; real preflight subsequently authorized

Read `legacy_commissioning_implementation_v1_20260925.md` / SHA; acceptance, code pins and independent review in `runs/legacy_commissioning_implementation_v1_20260925/`.
Report SHA256: `186e61a53b77e580971bbe85d4c2f611dae994789183124d877040bb71325241`. Frozen policy remains `5e8004ddeacdef3b0b506e23795bcb7867c1fd8c6c7c10524d5307b15ed84319`.
User authorized implementation and synthetic validation only. Implemented strict episode/source/action-log validation, complete-cutoff metadata bank planner, R/Q/verifier route guard, fixed 11-miss attack selector, and bounded actual-ScopedPrefixes trace bridge. Metadata plans do not encode references or activate registration.
92/92 persisted synthetic tests PASS on local Python3.9.13 (51 policy/CLI,25 attack,16 bridge);5 complete synthetic demos sealed. Independent agent code review PASS; not external peer review. Target HPC runtime not checked. No torch/transformers loaded.
Preserved1h/cap64/same-protocol minimum2, deterministic membership and original UID metric tie order. Model/normalizer/cuts/seeds/ensemble unchanged; binaries not rehashed. Poisoned prefix cannot resurrect; rehashed singleton cannot enter verifier; action logs need predeclared/completed action identities.
Actual frozen prefix/translator synthetic check:14 prefix packets can yield12 packet representations while flow_duration still reflects14. This is not proof of total target invisibility or a real miss cause. Exact translation/tokenizer provenance remains INCONCLUSIVE without a verified adapter. No frontend change.
Real decoder factory must enforce packet limit; bridge invokes once, requests no frame after largest selected target, closes on failure. Source bytes, normality, role/cutoff truth and tokenizer identity still require real preflight. Mid-capture t0 is rejected rather than adding a new reset rule.
0real source reads/decodes/forwards/updates/CAL/new confirmation/HPC/downloads. False metadata scope template cannot start.8 unrelated tracked modifications preserved; branch and HEAD unchanged.
Scientific state unchanged: Job174666 frozen FAIL; old hard DEV denominator and original legal banks preserved;3 confirmation devices consumed;Active UNKNOWN_PASSIVE;no new untouched paired confirmation roster;independentID NOT_RUN.
NEXT prepare pinned inputs and a bounded LEARN/DEV real preflight for reference qualification and attack-input semantics; proposal in implementation folder. No automatic real decoding/scoring/training/calibration/new confirmation, no repeat stage-by-stage permission within a future explicitly authorized fixed chain.

### Historical 2026-09-24: Unified commissioning policy DESIGN COMPLETE / SEALED; real validation not ready

Read `legacy_commissioning_policy_frozen_v1_20260924.md` and its SHA256 sidecar; evidence in `runs/legacy_commissioning_policy_v1_20260924/`.
Report SHA256: `876dd81330cb9f4eacebbd8ad1be60f85d61e8325a777f8663d6f55d19c55066`. Machine policy SHA256: `5e8004ddeacdef3b0b506e23795bcb7867c1fd8c6c7c10524d5307b15ed84319`.
One fixed hour with six predeclared functional phases; trusted normal source and causal cutoff; no adaptive extension. At most 64 distinct-component references, deterministic TCP/UDP round-robin, minimum two components for the query protocol. Counts are applicability minima, not proof of behavioral coverage or safety.
No trusted legal own reference -> frozen R; registered but protocol insufficient -> frozen Q; qualified protocol -> Q plus frozen verifier. Model, normalizer, cuts, seeds 27/127/227 and ensemble stay frozen; new references still require attack non-regression verification.
LEARN/DEV metadata only: 4,621 saved endpoints / 540 components in the earliest normal Active hour; 5/8 devices meet both protocol minima, 2/8 UDP only, 1/8 neither. Availability lower bounds, not materialized banks. Existing Active has no operation logs: UNKNOWN_PASSIVE, not evidence of the proposed active routine.
Original hard DEV pool and original references remain complete. No later-only denominator shortcut. Three prior confirmation devices remain consumed; no new untouched paired confirmation roster has been established. Independent ID remains NOT_RUN.
Job174666 frozen FAIL unchanged: Q=FULL attack 134797/135877, normal FP 51->30, weighted relative gain 0.165755% below 30%. No new scientific result or attack improvement is claimed. FULL cannot rescue Q misses; separate attack-input semantic audit is specified with matched controls, but not executed.
Twelve design consistency checks PASS; same-agent review, not independent peer review. Policy fixed before metadata counts. Detector identity metadata inherited; model binaries not rehashed this turn. Zero real decodes/forwards/updates/CAL/new confirmation reads/HPC/downloads; production executor not implemented.
NEXT: implementation and synthetic acceptance of the bounded policy/causal preflight, then assess lawful data readiness. This design authorization does not authorize real decoding, scoring, training, recalibration or a new confirmation run.

### Historical 2026-09-24: Qref post-confirmation diagnosis / direction review COMPLETE; no new experiment

Read legacy_qref_post_confirmation_diagnosis_and_direction_20260924.md / SHA; sealed evidence in legacy_qref_post_confirmation_diagnosis_v1_20260924.
User authorized saved-output/metadata diagnosis and research/design review.307 source pins verified;4 existing-cut probability/logit checks;8 unrelated tracked edits preserved.0forwards/updates/PCAPdecode/HPC/download/tuning.
Job174666 result unchanged:Q=FULL attack134797/135877,FP51->30;weightedgain0.165755%,frozenFAIL;HOLDOUT consumed,independentID NOT_RUN.
Coverage cause:Netatmo original6refs UDPonly;Ring3capture endpoints collapse1TCPcomponent,4.51seconds recorded.99.773391%weightedFP in fallback;Netatmo5FP allTCP;Ring15UDP+1TCP. No earlier omitted normal sessions in existing catalogue.
Attack1080misses allNetatmo/allQfallback;811missed by all3seeds. TCP551/84canonicalgroups,5groups have all61sampledqueries missed. HTTP529 are second of2candidate queries, BUT329groups contain2transportstreams and200contain3;prior same-key alarm is NOT proof sameconnection detected.
Static frontend:owner/capture/5tuple state,not transportstream reset;retains first12bursts/direction x6packets,up to144. Current target retention/stream mixing is a hypothesis for audit,NOT proven cause or future leakage.
Rejected shortcut:first8hActive as newreference with later-only query removes357oldDEV Eufy hardFP. Cannot claim improvement via denominator/time shift. Original hard regression pool must remain.
NEXT implement bounded lawful commissioning-coverage and attack-input semantic preflight. No automatic realdecode/forward/train;only LEARN/DEV for mechanism choices,consumedconfirmation diagnosis only. FULL veto cannot rescue Q misses;attack repair is separate.
Research rechecked currentNIDS survey,DIDS-MFL,ICLAD,GroupDRO,CRC,DIoT;no new-method performance promise. New executable protocol/window not yet frozen;no blind adjacent tuning.

### Historical 2026-09-23: Qref device confirmation REAL COMPLETE / VERIFIED; frozen scientific gate FAIL

Read legacy_qref_device_confirmation_real_result_v1_20260923.md / SHA; sealed verification/metrics/diagnosis in legacy_qref_device_confirmation_verified_v1_20260923.
Job174666 COMPLETED0:0,09:55:57,zero retries. ArchiveSHA+17internal seals+saved decisions/groups verified;local0forwards/updates.
Q=FULL attack134797/135877=99.20516%,weighted99.72965%,0newmisses. NormalFP51->30/205345,raw0.024836%->0.014610%,41.176%count reduction.
Weightednormal0.128443%->0.128230%,relativegain0.165755%,belowfrozen30%:FAIL retained.3/3seeds preserve ownQ and normalgain.
BorunFP30->9,attack100%;NetatmoFP5unchanged,attack98.91621%/1080oldmissesTCP551HTTP529;RingFP16unchanged,attack100%/allQfallback.
99.773391%baselineweightedFP mass is in mandatoryfallback. Even perfect eligible repair capped0.226609%weightedgain:posthoc scope bound,not new gate or modelrun.
OnlyBorun informativegain;NetatmoeligibleUDPnormal0baselineFP. Two-device replication/personalization unsupported;correct30vswrong32,strict seed direction1/3.
RAW39FP,NO_CF33,FULL30,all0newmisses this pool. Mechanismfalse flags depend on maingate;not evidence FULL numericallyworse.
HOLDOUT consumed. No independentID or historicalattackOOD reopen. Samecollection/cleanreference limits remain. OldM/CFAIL and DEV174251 preserved.
NEXT recommend design/coverage review of legitimate commissioning references and separate Q Netatmo attackmiss mechanism;no automatictraining,tuning,newdata or experiment.

### Historical 2026-09-23: Qref device confirmation AUTHORIZED / INPUT DELIVERY READY; subsequently completed

Read legacy_qref_device_confirmation_authorization_delivery_v1_20260923.md / SHA; commands delivery/OPERATE_CONFIRMATION.md / SHA.
User authorized complete fixed chain: inputidentity+packaging,targetchecks,E3features,frozen-scoring,report. User uploads/submits/pulls;no stage-by-stage reauthorization.
Code/input SHA and all66 input archive members verified;query341222=205345normal+135877attack,48ownrefs;UID/weights/causality/roles and fixed controls PASS.
Query metadata read for identity/denominators;PCAPbytes packaged,notdecoded.0real forwards/updates/CAL. Scoring NOT_STARTED;do not claim no query bytes were accessed.
Delivery has true scope,code42.9MB plus real input archive;65newraw files packaged,7shared captures and donorcache reused remotely,remoteavailability PENDINGpreflight.
State READY_FOR_USER_UPLOAD;0HPCsubmissions. amd32CPU/128GiB/8x4threads/72h upperbound;zero retry,no training/newCAL/download;old local remains stopped.
Frozen design/gates/model/cuts unchanged;DEV174251 result retained;RingQfallback,NetatmoTCPQfallback,only2potentially adaptive devices,samecollection.
NEXT user upload/install/submit once;target numerical check thenfeatures/scoring/report in samejob. Scientific outcome pending. IndependentID/historicalattackOOD not reopened.

### Historical 2026-09-23: Qref device confirmation IMPLEMENTATION PASS; real authorization subsequently granted

Read legacy_qref_device_confirmation_implementation_v1_20260923.md / SHA and sealed implementation acceptance.json.
User authorized implementation only. Dedicated whole-capture E3/frozen scoring/report entry and once-only HPC delivery implemented.
31/31 clean WindowsPython3.9 synthetic tests;26Linux shell/stdlib mock checks;3PowerShell checks PASS. Complete generated report and code-only archive verified.
Target LinuxPython3.9/E3 numerical parity remains pending, built into same future authorized job. Local mocks are not actual HPC/encoder execution.
Receipt correction: local Python3.9.13, not3.9.25; see delivery/environment_metadata_correction.json / SHA. Sealed original retained;code/tests unchanged.
0real query/PCAPreads,0real forwards,0updates,0CAL,0HPC. Code/model/normal-metadata bundle sealed;protected input package NOT_PREPARED;authorization template false.
Frozen design unchanged:341222queries/3devices,48refs;Borun adaptive,NetatmoUDP adaptive/TCPQfallback,Ring allQfallback. Same collection,only2potentially adaptive devices.
NEXT one explicit real-confirmation authorization covers input packaging+target checks+features+frozen scoring+report,zero retry,no training/CAL/download;user uploads/submits/pulls.
Transfer/status commands are prepared;do not run before true scope/input package. Remote shared inputs availability not yet rechecked.
DEV174251 positive result preserved;oldM/CFAIL unchanged;new scientific results NOT_RUN;HOLDOUT CLOSED.

### Historical 2026-09-23: Qref device-held-out confirmation DESIGN FROZEN / REVIEWED; implementation subsequently completed

Read legacy_qref_device_confirmation_design_v1_20260923.md / SHA and runs/legacy_qref_device_confirmation_design_v1_20260923/confirmation_recipe.json.
User authorized design/review only.0HOLDOUTquery reads,0PCAPreads,0model forwards,0updates,0CAL,0HPC. Normal-reference metadata only inspected.
Existing3reserved devices341222queries=205345normal+135877attack;48own references. No new data download needed.
Borun refsTCP20/UDP21;NetatmoUDP6(TCP/HTTPQfallback);RingTCP1(allQfallback). Only2devices potentially support adaptation;do not claim3adaptive successes.
Same seven Active captures/dates across roles;device-held-out within collection,not independent campaign;external pretrain overlap unproved.
Freeze job174251 FULL/NO_CF/Q/R/cuts. Prospective single inference chain,0training/0recalibration. R/Q/FULL/NO_CF/RAW plus fixed3earlyLEARNdonor controls.
New E3 required341270vectors;65candidate new raw files1.1046GB local size-present plus7shared prior-uploaded captures;remote current existence not verified.
OldM/CgateFAIL not overridden. New versioned HOLDOUT authorization/role-aware evaluator required;old local pipeline stays stopped,sole futureHPC ownership needs explicit execution authorization.
NEXT implement+synthetic/cleanLinux acceptance,then separately authorized once-onlyfeature/scoring/report. No repeated permission within an authorized fixed chain.
Job174251 DEV success remains:0new misses,normalFP374->30;this prospective design is not new scientific evidence. HOLDOUT CLOSED.

### Historical 2026-09-22: Q verifier REAL DEV COMPLETE / VERIFIED SYSTEM+MECHANISM PASS

Read legacy_qref_training_real_result_v1_20260922.md / SHA and sealed runs/legacy_qref_training_verified_v1_20260922/verification.json.
Job174251 exit0,14911.45s,1158840updates,15endpoints,zero retries,HOLDOUT CLOSED. Archive and20internal seals verified.
Saved decisions all21arms/counts/device-activity-protocol groups,CAL359875contexts rechecked;0verification forwards/updates.
FULL preserves Q attack79045/79056=99.9861%,0new misses;normalFP374->30/100830,0.3709%->0.02975%;weighted2.7696%->0.31717%(-88.55%).
EufyWAN357->30/738(48.37%->4.07%);Heimactive17->0/696;FULL3/3seeds no new misses vs ownQ.
RAW normalFP358;NO_CF FP36 but105new attackmisses. Learned metric and worst-reference attack constraint supported on inspectedDEV.
Matchedcorrect39FP vswrong45FP,0new misses both: modest Eufy personalization support,none Heim;do not attribute whole gain to personalization.
IndependentID NOT_RUN,historical91.91%family-unseen/oldOOD NOT_REOPENED;2DEVdevices and service/source bias remain. Original11attackmisses persist.
NEXT recommendation freeze model/cuts,design/review independent device commissioning validation;no adjacent DEV tuning,no automatic HOLDOUT access or further experiment.
Original172780FAILED/M/CgateFAIL retained;this is development success,not independent deployment/paper certification.

### Historical 2026-09-22: Q verifier frozen TRAIN/CAL/DEV AUTHORIZED; delivery READY, NOT SUBMITTED

Read legacy_qref_training_authorization_delivery_v1_20260922.md / SHA; commands runs/legacy_qref_training_delivery_v1_20260922/OPERATE_TRAINING.md.
User accepted real frozen chain after verified preflight174233. CACHE_PARITY,9helpers/H gate,6verifiers,CAL,DEV once authorized together;zero retry,HOLDOUT CLOSED.
Tiny3038byte overlay reuses original remote code/data/cache,new run directory;unchanged implementation/code/recipe pins verified.
Linux mock success/failure/once-submit/duplicate refusal/status/export and5Bash syntax,2PowerShell parse PASS;0real training submissions so far.
Serial4threads,amd4CPU/64GiB/24h ceiling,1158840updates ceiling;no ETA or capability improvement promised.
NEXT user upload/submit via guide,view immutable progress,pullback; no repeated stage authorization within normal fixed chain.
Original174233preflightPASS,172780FAILED,M/CgateFAIL preserved;no automatic HOLDOUT or retry.

### Historical 2026-09-22: Q verifier TARGET PREFLIGHT VERIFIED PASS; real training NOT STARTED

Read legacy_qref_preflight_verified_v1_20260922.md / SHA; sealed receipt runs/legacy_qref_preflight_verified_v1_20260922/verification.json.
Job174233 COMPLETED/0:0,4m27s (user sacct); returned archive/internal seals verified,stderr empty.
Target64tests PASS; full synthetic192updates COMPLETE. LEARN766727/DEV179886 frozen Q replay EXACT_FLOAT32_EQUAL.
0realupdates,0newverifierforwards,0CAL,0E3recompute,0PCAPdecode,zero retries,HOLDOUT CLOSED.
NEXT: separately authorized frozen helper/verifier training,CAL,DEV once; no repeat preflight experiment needed.
No scientific improvement claim; originalQ/R,job172780FAILED,M/CgateFAIL unchanged. Pullback v2 path/checksum fix documented.

### Historical 2026-09-22: Q verifier PREFLIGHT ONLY authorized; delivery ready, NOT SUBMITTED

Read legacy_qref_preflight_delivery_v1_20260922.md / SHA; commands: runs/legacy_qref_preflight_delivery_v1_20260922/OPERATE_PREFLIGHT.md.
User authorized TARGET_SYNTHETIC + CACHE_Q_REPLAY only; independent overlay exits before real training/calibration/new-method DEV evaluation.
7/7 boundary tests,2/2 PowerShell parse,5/5 Linux Bash syntax,kit hashes,mock once-submit/duplicate refusal/early-failure export PASS.
Existing232MiB code/input bundle reused; no raw-data upload,E3 recompute,download or HOLDOUT. Original sealed implementation unchanged.
Remote target numerical checks/cache identity/exact saved-Q parity remain PENDING. User performs upload/submit/pullback;0actual remote submissions.
amd4CPU/64GiB/2h,zero retries; upload progress and immutable replay batch progress provided.
NEXT: user submit preflight only,return results for verification. Real helpers/verifiers/CAL/new DEV execution NOT AUTHORIZED.
OriginalQ/R,job172780FAILED,M/CgateFAIL,HOLDOUT CLOSED unchanged; engineering PASS is not scientific PASS.

### Historical 2026-09-22: Q normal-reference verifier IMPLEMENTED; synthetic acceptance PASS

Read legacy_q_reference_implementation_result_v1_20260922.md / SHA and runs/legacy_q_reference_implementation_v1_20260922/README.md.
Frozen recipe unchanged; implementation/code/input pins sealed.64/64 Windows Python3.9 tests PASS; full clean-source synthetic chain192/192updates COMPLETE.
12/12 clean WSL Linux stdlib delivery/report/status checks PASS; Linux numerical stack unavailable locally,NOT claimed verified.
Real entrypoint requires target synthetic numerical check + exact savedQ replay before training; these checks remain pending.
Implemented9helper+6verifier endpoints,H gate,FULL/NO_CF/RAW,CAL protection,all DEV controls/gates,paired/session/component reports.
FIT/CAL/DEV and causal-bank isolation enforced; empty inner->Q,unregistered outer->exactR including ensemble-rounding edge case.
Failure injection stops with completed endpoint preserved;repeat output rejected. Missing historical report files now fail at preflight.
Immutable numbered progress receipts and Python/PowerShell status tools;no polling task created.
Cache-only bundle prepared: runs/legacy_q_reference_delivery_v1_20260922/,243018992bytes,406members hash-verified;not uploaded/submitted. Feature cache remains external;user handles transfer/run/pullback.
Executor currently serial endpoints x4Torch threads,within maximum resource budget;parallel speedup not claimed.
THIS IMPLEMENTATION:0real forwards,0realupdates,0realcalibration,0HPCsubmission,0newdatasetdownload,HOLDOUT CLOSED.
NEXT: cached-feature delivery and separately authorized real chain:runtime/cache/Q parity,helpers/H gate,verifiers,CAL,DEV once.
OriginalQ/R/threshold,job172780FAILED,M/CgateFAIL and all historical capability limitations unchanged;synthetic PASS is not scientific PASS.

### Historical 2026-09-22: Q normal-reference verifier DESIGN FROZEN; implementation pending

Read legacy_q_reference_correction_design_v1_20260922.md and matching recipe JSON / SHA256 sidecars.
Evidence: runs/legacy_q_reference_correction_design_v1_20260922/ sealed;55design checks PASS,not scientific PASS.
One candidate: frozen completeQ + learned normal-reference veto; same-protocol >=2components or exact innerQ fallback.
Learned shared64x768metric; normal own-reference loss,attack worst time-valid LEARN-reference loss; NO_CF ablation and RAW cosine baseline.
LEARN whole-component FIT617908/CAL148819;FITnormal134493/attack483415;CALnormal33147/attack115672.
Three device-held-out helper folds x3seeds produce hard-normal training weights;9helpers+6verifiers,1158840updates future ceiling.
All115672CALattacks have eligible earlier donor banks,359875contexts; deterministic max protection cutoff computed only after future training.
DEV179886denominator unchanged;HeimTCP48014queries retainQ due singleton reference. Matched wrong donors/counts/UIDs fixed by metadata.
Development target:0new attackmisses vsQ,>=30%weighted normalFPR reduction,EufyWAN357/738FP to<=178/738;seed/mechanism checks also required.
Zero-population-miss guarantee NOT claimed;old91.91%family-unseen/independentID/historicalOOD not newly tested.Only2inspectedDEVdevices.
Targeted ICLAD/Tip-Adapter/CRC/groupDRO reading incorporated; self-review only,no independent reviewer claimed.
NEXT: implement + synthetic/clean-Linux/report-dependency acceptance;then separately authorized cached-feature execution.
Large E3arrays remain remote,pins fixed;reuse2.71GiB payload,0newdecode/E3forward planned,no60hwhole-pipeline rerun.
THIS TURN:0real forwards,0updates,0threshold computations,0HPC,0newdataset download,0HOLDOUTqueries.
Design authorization only;no real execution started. OriginalQ/R/threshold,job172780FAILED,M/CgateFAIL,HOLDOUT CLOSED unchanged.

### Historical 2026-09-22: Q/M/C mechanism diagnosis COMPLETE; next method direction selected

Read legacy_reference_qmc_mechanism_diagnosis_and_next_decision_20260922.md / SHA.
Existing scores/LEARN-DEV metadata only:0forwards,0updates,0threshold-search,0HPC,0HOLDOUT queries.
Separate diagnosis and independent validation sealed; paired flips and62groups verified.
Q strong DEV attack signal but Eufy WAN_WATCH FP357/738=48.3740%; aggregate FP0.3709% hides this.
M vsQ:316normal errors fixed,0new FP,2830new attack misses. C:99fixed,13new FP,14859new misses.
Correct/wrong-reference intervention does not support intended mechanism; M shifts both classes.
Q/M/C independently trained fromR; C lacks full query-z direct path. Only6fixed LEARN reference contexts.
LEARN/DEV identities disjoint;7shared multi-owner normal captures. No discovered direct future/label input path.
DEV attacks all involve endpoint80,normal none;port not a direct model feature. Service/source bias unresolved.
NEXT DESIGN: preserve complete frozenQ path, learn reference correction with explicit attack protection,
using LEARN-only device-held-out tasks and causal references; freeze one candidate and meaningful controls.
Do not retrain M/C or replace frontend by default. New recipe not frozen or implemented; no new trial started.
Q not promoted, historical capability not newly verified. Original M/C gateFAIL,jobFAILED,HOLDOUT CLOSED unchanged.

### Historical 2026-09-22: HPC job 172780 FAILED at report tail; saved DEV scores audited

Read legacy_reference_hpc_saved_score_diagnosis_20260922.md / SHA.
User uploaded/submitted/pulled job172780; elapsed59h48m16s. Missing excluded_capture_modes.json
and capture_receipts.json in runtime relocation prevented final reporting. Original FAILED preserved.
All8feature shards+merge+9training endpoints COMPLETE;191exported files and endpoint seals verified.
Saved LEARN/DEV logits and DEV interventions audited locally: zero new forwards/updates/HPC/HOLDOUT.
Q: attack79045/79056=99.9861%,normalFP374/100830=0.3709%;weighted99.9385%/2.7696%.
M:96.4063%/0.0575%;C:81.1905%/0.2856% (row attackTPR/normalFPR on this DEV only).
Frozen M/C gate BOTH FAIL: EufyTCP loss exceeds1pp; C mechanism unsupported. HOLDOUT remains CLOSED.
Q is a strong query-only development signal, not proof of reference benefit or independent generalization.
LEARN PhilipsTCP80 control unavailable because exported packet annotations omitted; other saved statistics audited.
NEXT: examine Q validity/generalization and reference-arm failure using existing evidence; no automatic new trial.
No retry/retrain or HOLDOUT authorization added. Historical ID anchor is not a new independent ID test.

### Historical 2026-09-19: HPC DEV-only package DELIVERED; not uploaded/submitted

Read legacy_reference_hpc_delivery_20260919.md / SHA and
runs/legacy_reference_hpc_preparation_v1_20260918/OPERATE_HPC_20260919.md.
Code1.26MiB + data6.24GiB sealed/verified; upload,once-submit,status,pullback scripts ready.
10behavior +6Linux tests PASS; mock submit/export checks PASS; remote numerical preflight pending.
amd32CPU/128GiB/72h,8workers x4threads; whole-capture shards,9frozen endpoints,DEV-only.
No HOLDOUT execution,zero auto retries. Local v2 remains STOPPED,not an active fallback.
NEXT: user uploads and submits through delivered commands; inspect actual job/preflight status.
No scientific result yet; no experiment started by this delivery.

### Historical 2026-09-18: local v2 STOPPED on progress-file write; HPC preparation continues

Read legacy_reference_local_v2_stop_and_hpc_runtime_clarification_20260918.md / SHA.
Local v2 STOPPED_NO_RETRY at ~15:44: WinError5 replacing worker status.json, last progress98,546/946,792.
No completed feature cache/training/scientific scores. Preserve failed output; no automatic restart.
HPC runtime AVAILABLE after historical module/vendor loading; Python3.9.25/torch2.5.1 need compatibility checks.
Tshark4.6.6 and E3 dependencies import successfully. Probe tail CR caused exit127, not missing software.
221missing input assets/10.87GiB identified; no upload or HPC job yet. Build Linux DEV-only package.
Local fallback is currently stopped. HOLDOUT remains reserved, not opened; remote DEV-only scope unchanged.

### Historical 2026-09-18: reference joint v2 AUTHORIZED and STARTED; outcome pending



Parallel HPC preparation authorized: read legacy_reference_hpc_parallel_preparation_20260918.md / SHA.

Local v2 remains running and retains exclusive final HOLDOUT ownership. HPC package must stop at DEV.

Remote audit COMPLETE: Python3.9.25; E3 weights/config SHA match;221 inputs (10.87GiB) missing at expected paths.

Runtime incomplete: E3 libraries missing from active environment, tshark absent from PATH.

Read legacy_reference_hpc_input_audit_result_20260918.md / SHA; do not submit Windows executor unchanged.

No HPC submission yet. New authorization supersedes earlier local-only preparation scope only for the

separately versioned HPC branch; frozen science and local execution remain unchanged.









Read legacy_reference_joint_v2_real_launch_20260918.md / SHA.



User authorized one fresh complete chain with verified Windows launcher fix.



Run legacy_reference_joint_development_v2_20260918; supervisor8400, local11:03 start.



Startup snapshot RUNNING/PREPARE_LEARN_DEV; consult live status and process liveness.



Features -> nine Q/M/C endpoints -> DEV gate -> conditional one-time HOLDOUT.



Frozen recipe/data/threshold/models unchanged; no scientific result at startup.



One model/decoder,12GiB/16GiB/72h; stop on error,zero auto retries,no downloads/HPC.



Persisted status and standalone viewer handle monitoring without continuous LLM polling.



Previous v1 failure preserved; its no-restart panel below is historical, superseded by new authorization.







### Historical 2026-09-18: real reference chain STOPPED; startup fix v2 VERIFIED, not restarted







Read legacy_reference_joint_launch_failure_and_fix_v2_20260917.md / SHA.



The authorized v1 attempt stopped at first decoder launch with Windows1816; retries0.



E3 loaded, but real decoded packets/valid features/optimizer steps/science scores ZERO.



Root cause: two process slots do not accommodate Windows venv redirector + Python + decoder.



Versioned v2 wrapper allows the extra launcher slot only; four targeted regressions PASS.



Original32 acceptance and frozen scientific protocol unchanged. Failed run retained/sealed.



Current real status STOPPED_NO_RETRY; no valid cache and no real retry started.



NEXT: explicit fresh authorization for same feature/9train/DEV/conditional-HOLDOUT chain.



v2 execution_scope.template remains false; one model/one decoder,12GiB/16GiB/72h,zero auto retries.



No downloads/HPC/closed historical evaluations. Engineering fix is not a scientific result.







### Historical 2026-09-17: reference executor IMPLEMENTED; 32 synthetic acceptance checks PASS







Read legacy_reference_executor_implementation_result_v1_20260917.md / SHA and run



legacy_reference_executor_implementation_v1_20260917: acceptance, code_pins, logs,



two final synthetic chains, execution_scope.template and SHA256SUMS.



Frozen sample/recipe unchanged: LEARN766,727 / DEV179,886 / HOLDOUT341,222 queries;227refs.



Q/M/C fixed heads, frozen R/normalizer/E3, shared caches,9endpoints, original threshold,



DEV gate before single conditional HOLDOUT, matched reference interventions implemented.



25behavior/causal checks +5process/resource checks +2end-to-end synthetic chains PASS.



Real tokenizer/collator with stand-in model; real assets denied in synthetic workers.



Real features/model forwards/optimizer updates/raw decodes this stage: ZERO. No science PASS.







Local one-model worker, Job memory12GiB, disk16GiB, chain72h maximum, zero auto retries.



Persisted progress/results and standalone viewer; interrupted output cannot auto-restart.



8unrelated changes and historical frozen inputs preserved. Engineering test failures



retained and fixed; no real experiment retry. Sparse reference/service-view limits remain.



NEXT: separately authorized LEARN/DEV-feature +9train +DEV +conditional-HOLDOUT chain.



Template execution_authorized=false. Implementation authorization does not start real work.



No new downloads/HPC/undisclosed historical evaluations.







### Historical 2026-09-17: real sample manifests and prospective recipe COMPLETE; no model execution







Read `legacy_reference_sample_preparation_result_v1_20260917.md` / SHA and



`legacy_reference_development_recipe_v1_20260917.json` / SHA; run sample_preparation_v1 has



finalized UID manifests/denominators/reference controls/seals and independent_verification.



LEARN=766,727, DEV=179,886, DEVICE_HOLDOUT=341,222 query rows; references=227.



All legal canonical capture sessions retained with max32 systematic targets; exact duplicate



observations removed prospectively. Not full-packet rates or independent sample counts.



Guard applied before every append. Old encoder/R/threshold untouched; zero features/scores/training.



18 synthetic cases PASS plus strengthened protocol-matched reference-control suite7 PASS;



independent UID/time/label/weight/resource readback PASS. 8unrelated files unchanged.







Reference observations strictly earlier; do NOT claim capture end proves connection closure.



Same-canonical ongoing-connection queries tagged separately. Ring1actual reference, Atomi/Globe2each,



not padded. Reference interventions equal counts AND TCP/UDP composition, unavailable controls NA.



Freeze Q/M/C40epochs,3seeds each, original threshold, matched queries/weights; DEV gate precedes



one conditional heldout check. R/old ID0/2378 is disclosed unchanged fallback anchor, not a new test.



Service/view limits remain; no science PASS, no automatic downloads/HPC or undisclosed evaluation.



NEXT: integrate full executor and end-to-end synthetic acceptance from this exact recipe, then



one explicitly authorized feature/train/DEV/conditional-HOLDOUT chain. Current authorization



completed sample/recipe preparation ONLY; no further generic data expansion or automatic training.







### Historical 2026-09-17: seven-day normal supplement COMPLETE; prospective scope implemented







Read `legacy_normal_supplement_completion_result_v3_20260917.md` / SHA and



`legacy_reference_sample_scope_and_control_v1_20260917.md` / SHA. Run completion_v2 has combined_review,



prospective_sample_scope_contract, context_guard_verification, final_status/final_verification/SHA256SUMS.



7/7 acquired/audited:7,218,605,495bytes,58.79hours,11,749,238records,1,797,062target-device candidates.



Prior5raw audits reused, only2new decoded. User-authorized fresh attempt for11-23 succeeded;11-26



also succeeded. No additional automatic retry. Cumulative charge7,235,120,567bytes < original8GiB.







10devices have7dates,HeimVision6. All new times after old proposed references and before attacks.



Only cross-role canonical key remains shared DHCP;prospective exclusion removes8,452(0.470%),



leaving1,788,610candidates. Owner/capture/session context guard implemented with synthetic PASS,



including future-row rejection and old regression preservation; real UIDs/features NOT materialized.



All11old proposed reference pools remain nonempty after DHCP exclusion; counts are not independent units.







Philips local TCP80 has113candidate flows/113request markers across3dates;9other comparable devices



lack shared service evidence;Amcrest reused direction differs. Nmap remains mixed/unassigned.



Service/view gaps limit controlled-generalization claims, not all limited development comparisons.



DECISION: end generic normal-data expansion; proceed to bounded sample/label/reference/recipe preparation



for matched R/Q/M/C development comparison and query-fixed reference intervention. Not a scientific PASS,



not a frozen training recipe or training authorization. No features/scoring/training/HPC;R/old rules and



8unrelated modifications preserved. No automatic extra downloads or opening undisclosed evaluations.







### Historical 2026-09-17: five-day supplement preserved; transport then stopped, attribution corrected







Read `legacy_normal_supplement_result_v2_20260917.md` / SHA and correction run corrected_attribution,



cross_role_canonical_contexts/final_status/SHA256SUMS. Original acquisition run remains sealed.



5/7files acquired and audited:2,209,464,965bytes,40.00hours,5,170,998records,1,065,569MAC-attributed



old-input candidates. Ten devices have5dates; HeimVision4 (absent11-19). Sixth11-23 transfer failed



IncompleteRead after16,252,928saved bytes; seventh not requested. Zero retries. Budget conservative



upper2,225,980,037bytes <8GiB. No features/scoring/training/HPC;8unrelated edits unchanged.







V1 stream-wide attribution overcounted mixed-device streams; v2 uses exclusive-stream plus per-device



residual bounds, which coincide exactly here. Original packet/MAC totals remain unchanged. Only one



cross-role canonical key: DHCP UDP0.0.0.0:68/255.255.255.255:67;5,778candidates (0.542%). Direct



cross-role packet/hash count0 is not proof of safe shared prefixes. Before future materialization,



explicitly isolate/exclude this shared context in both reference and query contexts; not a frozen



rule or historical denominator change. Proposed exclusion retains1,059,791candidates; not executed.







Philips has shared normal/attack TCP device-port80 in comparable directional audits;9other devices



with attack direction evidence still lack overlap; Amcrest reused direction not comparable.



MATERIAL_GAPS remain. Keep5completed files; any future acquisition only addresses unfinished2,



with renewed retry scope if authorized. No broad normal expansion or automatic training; next



resolve concrete context/service/material rules using this evidence.







### Historical 2026-09-17: targeted supplement research COMPLETE; acquisition then proposed







Read `legacy_normal_supplement_research_v1_20260917.md` / SHA and matching run catalog,



chronology_and_scope, proposed_acquisition_scope, verification_and_sources and SHA256SUMS.



Official Active lists24PCAPs versus README30;17filename dates precede earliest disclosed attack



2021-11-29. Proposed first7 dates:2021-11-02,08,10,16,19,23,26, selected by evenly spaced



chronological ranks, not model outcomes. Packet timestamps and11device coverage remain unverified.



Only488bytes of official README downloaded; zero raw PCAP/archive body bytes read or saved.







Actual PCAP/archive sizes remain UNKNOWN: authenticated HEAD lacks Content-Length; Range requests



return200chunked without Content-Range. Proposed8GiB total raw transfer cap is an operational budget,



NOT actual size or scientific sufficiency; no guarantee all7files fit. Idle single archive deferred.



Active may repair short/skewed normal coverage but does not guarantee service/vantage controls,



independent sessions, nighttime coverage or adequate attack diversity. Previous7dates/~2000queries



per device remain planning targets only. MATERIAL_GAPS / NOT_TRAINING_READY remains in force.







Next proposed scope: bounded acquisition of named7files plus raw-only qualification, first-file



format/time/device/service check; preserve completed work and stop on failure/budget, no automatic



retry/expansion. Current authorization covered research only; raw acquisition/review not started.



No new decode/features/scoring/training/HPC. R, historical protocols and8unrelated edits preserved.







### Historical 2026-09-16: bounded material review COMPLETE; normal coverage insufficient for main experiment







User authorized the concrete next material review and requested defensible data quantities. Read



`legacy_reference_material_audit_result_v1_20260916.md` / SHA and



`runs/legacy_reference_material_audit_v1_20260916/` final_review_status, review_summary,



material_adequacy_decision, final_verification and SHA256SUMS. 277 new raw members decoded once,



18 sealed prior audits reused; all295 reviewed,55.1min raw run,exit0,zero retries. Four synthetic



integration cases PASS; independent record/byte checks PASS; original source pins and8unrelated



modified files unchanged. No features, model scoring, training, new download or HPC.







219normal captures have52,421candidate targets/1,113observed streams and only60.04summed minutes;



76attack captures have24,240,338directional/semantic screen targets, NOT final assigned positives.



Under proposed earliest3normal-reference split, LEARN/DEV/device-holdout normal queries are



19,988/12,313/12,762 across388/146/193observed streams. LEARN90.28%targets are from ArloQ.



Conservative reference-tuple exclusion leaves19,060/12,297/1,994targets; Atomi and Netatmo leave0.



Same tuple is dependency ambiguity, NOT automatic leakage; causal ongoing-connection queries may



be legitimate but are not independent new sessions. Roles/labels/reference recipe remain unfrozen.







All observed new flood inbound TCP/UDP targets use device port80. Nine devices with complete new



normal coverage have no shared normal/attack inbound protocol+device-port pair; SimCam newPHOTO



also lacks overlap, with older normals outside this particular comparison.18HTTP-folder captures:



only3contain requests (HeimVision1,Netatmo2);15have0HTTP requests, not proof of no attack.



Identity/header/time checks found no listed failures, but source/service confounding and short normal



coverage remain. Do not promote file/packet counts to independent evidence or train on directory labels.







Decision: MATERIAL_GAPS / NOT_READY_FOR_MAIN_EXPERIMENT, not a model-failure verdict. Retain R and



conditional-learning objective; preserve these materials. Next prepare an exact bounded supplement



manifest for multi-day normal coverage and necessary service controls. Official Idle/Active each



describe30days; these supplements are NOT downloaded and exact bytes/dates remain unverified



(new Active browser tab requires registration). Planning budget: >=7normal dates per device and



about2,000dispersed normal queries/device; keep useful qualified LEARN sessions. This is neither a



frozen threshold nor an independence/sufficiency guarantee. No automatic download or training.







### Historical 2026-09-16: conditional-learning design reviewed; material qualification then pending







User accepted pursuing lower OOD FPR with retained attack detection, without requiring97%attack first,



and requested comprehensive design and reasonable data volume. Read



`legacy_reference_conditioned_joint_design_v1_20260916.md` / SHA and matching run data_feasibility,



proposed_material_scope, sources, SHA256SUMS. DESIGN_REVIEWED_WITH_MATERIAL_GAPS; NOT_TRAINING_READY.



This turn read existing metadata/disclosed evidence only; zero new raw decode/features/scoring/training.







Metadata identifies12unique-name device correspondences/228normal+87attack captures. Excluding ambiguous



Gosund and mixed Nmap training use leaves11candidate devices,219normal+76attack members; reuse18sealed



audits,277new members proposed for bounded raw qualification. None of these counts are qualified targets



or independent units. No new download needed for these existing candidates. Short normal captures,



few attack runs and service/capture-view confounding remain decisive gaps. Do not launch a model on



directory counts. Next is the prepared bounded material qualification; not another broad inventory.







Design proposes frozen E3/R plus27201parameter query/reference relation residual; R,Q(query-only),



M(ordinary pooled-reference),C(relation) comparison at same threshold/labels, matched M/C reference.



Provisional6LEARN/2DEV/3device-holdout; prior-exposedAmcrest/SimCam stay LEARN. Reference uses earlier



normal capture/session information only, normal novel activities evaluated separately. Candidate



hyperparameters/roles/seed repeats are NOT a frozen executable recipe or changes to historical rules.



Data quantity judged by device/activity/session/capture diversity and uncertainty, not packet volume;



few correlated attack runs cannot certify1%risk from many packets. INCONCLUSIVE is an allowed outcome.



No new execution/download/HPC authority; original R and unrelated8modifications remain unchanged.







### Historical 2026-09-16 research decision: joint capability remains the objective







Read `legacy_joint_capability_mechanism_decision_20260916.md` / SHA / sources. User challenged route



oscillation and requested an independent mechanism recommendation. Retain immutable E3/R; propose



query-dependent scoring conditioned on the device's certified earlier normal reference, trained on



device episodes with later normal AND attack queries. Commissioning supplies reference information;



it is a means to joint low-FPR/high-recall capability, not an alternative objective. This is a research



recommendation, NOT a frozen mechanism or real-execution authorization. No training/scoring/download/HPC.







Current two-camera/Hydra supervision does not establish cross-device/attack learning readiness;



service/date/capture-view confounding exists, but is not proved the sole cause of B/C degradation.



R already detected54/54newHydra, so that endpoint did not demonstrate attack-weakness repair.



NEXT recommendation: one bounded qualification of named existing archive leads (ArloQ/Atomi/Globe/Ring,



etc.) for lawful earlier normal plus later normal/attack and informative counterexamples; design a



reference-conditioned learner with equal-information ordinary-adaptation baseline. Do not immediately



repeat a two-camera pilot or default to old-only replay. If support fails, state exact missing material



and minimum acquisition/scope decision; no endless inventory or implied training readiness.







Freezing R preserves unadapted traffic only. Adapted-device attacks still need evidence; old attacks



without eligible references retain R and are NOT thereby improved. Same-device normal/attack joint



results and held-out-device confirmation remain necessary. ICLAD2603.19497 and shift-adaptation



2508.15100v2 provide method context, not performance proof. Historical protocols/results untouched.







### Historical 2026-09-16 earlier recommendation: retain R; prioritize device-local commissioning research







User asked whether to continue enhancement or pursue new-device commissioning. Read



`legacy_enhancement_post_result_route_recommendation_20260916.md` / SHA. Read-only result/trace/history



and metadata review recommends pausing current global B/C continuation and designing normal-reference



device-local adaptation on immutable original R. Global joint enhancement need not remain a prerequisite.



This is a recommendation, NOT a new mechanism freeze, accepted route execution or experiment authority.



R remains baseline, not a claim that hard OOD is solved. Branch isolation cannot guarantee attack safety



within the adapting device; require same-device later normal AND attack evidence. CKDE-Q/R/S failures



constrain particular mechanisms/support, not all possible adaptation. New mechanism needs targeted



literature and review; no automatic threshold raising, loss search, training, download or HPC.







Existing two cameras can support a DEVELOPMENT pilot, not untouched unseen-device confirmation.



Do not merge all old TRAIN normal into commissioning reference: WATCH3 is October6 while RECORDING1/2



are October12. Candidate chronology uses WATCH1/2 reference then WATCH3/RECORDING3/Hydra3 queries;



scope/roles/budget remain unfrozen, original plans unchanged. Independent device confirmation requires



separate eligible material after a promising development result. See recommendation for source pins.







### Historical 2026-09-16: small-enhancement chain COMPLETE; joint improvement NOT_REACHED







Read `legacy_cic2022_p2_enhancement_real_result_v1_20260916.md` / SHA and



`runs/legacy_cic2022_p2_enhancement_real_v1_20260916/` finalstatus/final_verification,



train_B/C checkpoint.json and evaluation summary/low_FPR_points/SHA256SUMS.



Completed12:08:34 Asia/Shanghai in283s,exit0,zero retries,engineering PASS. Both arms actually completed



200updates/2419800row exposures; endpoint/evaluation seals rechecked. Supervisor merged status retains



some previous progress fields (e.g.190); use individual endpoint receipts for final update count/hash.







At unchanged original threshold R/B/C valid attack=96.4414/93.8440/93.8058%;future=95.3773/91.9113/91.8689%.



Exact-family-seen=99.9931/99.9634/99.9604%;absent=91.9089/86.0350/85.9517% (not novel-mechanism proof).



ID all0/2378,248sessions,UDP-only and previously declared independence limits. Four old OOD FPR:



hydraulic76.0928%unchanged;street0.0667->99.7/99.7%;predictive35.0051->39.7802/39.9697%;



stream0.3333->0.2667/0.2667%. New-camera normal CHECK improves: Amcrest35.2273->3.9773%,



SimCam66.6667->13.7255% for B/C; frozen hierarchical weighted FPR55.4461->18.9815%.



New Hydra attack54/54 for all including R, no new detection gain on this pool. Five-normal-pool



FPR<=1% native-probability attack90.9224->57.5735/57.2720%;raw-logit confirms deterioration.







R_to_B/R_to_C TRADEOFF, B_to_C REGRESSION. Keep original R; do not promote B/C or claim joint success.



Local new-normal learning is real, broad retention fails. E3 was frozen; this is not a new-frontend test.



No same-budget old-replay-only control exists here, so do not assign all degradation to added data or



declare the entire route exhausted. NEXT: reason from existing training/coverage/decline evidence to



choose a discriminating correction/control; no automatic retraining, adjacent CHECK tuning, new data,



HPC or commissioning. This one authorized run is CLOSED; retain all outputs and frozen constraints.







### Historical 2026-09-16: complete small-enhancement chain AUTHORIZED and LAUNCHED







User explicitly replied "授权执行" to the complete PREPARE -> TRAIN_B -> TRAIN_C -> CHECK scope.



Read `legacy_cic2022_p2_enhancement_real_authorization_v1_20260916.md` / SHA and



`runs/legacy_cic2022_p2_enhancement_authorization_v1_20260916/execution_scope.json` / SHA256SUMS.



Scope SHA=f69e0af75f21e5a75ddd49edcc79f7190ced9fdcd0687e7aa1b6d0caf4ad15a7.



This authorization supersedes the previous NOT_AUTHORIZED state for this one named chain only.



No per-stage reapproval is needed. Frozen recipe/code/runtime/ID pins verified, eight unrelated



modified files unchanged. No source implementation change or repeated synthetic test needed.







Launched once locally at 2026-09-16 12:03:51 Asia/Shanghai; supervisor PID52380. Initial verified



snapshot at12:03:53: RUNNING/PREPARE/EXTRACT_PINNED_CAPTURES, child PID19304, no recorded exception.



This is a launch snapshot, NOT a live or completion claim. Authoritative ongoing status:



`runs/legacy_cic2022_p2_enhancement_real_v1_20260916/status.json` / `status.md`;



terminal outcome `finalstatus.json`, final checks `final_verification.json`, results



`evaluation/summary.json`. Startup logs are in the authorization directory with prefix



`launch_639251282309693738`. Do not invoke start again while monitoring or after failure.







Local supervisor automatically advances the accepted chain and persists progress; no LLM polling



automation was created. Best-effort desktop completion/failure notification is enabled. Any exception



STOPs with zero retry. If STOP occurs, preserve artifacts and diagnose before proposing a correction;



this run authorization does not permit an automatic retry. No new download/HPC/resource trial or



unlisted FINAL/select/viewed access. Scientific improvement remains NOT_EVALUATED until CHECK completes.







### Historical 2026-09-16: small enhancement IMPLEMENTATION_PASS; ID v2 qualified; real chain then NOT_STARTED







Read `legacy_cic2022_p2_enhancement_implementation_v1_20260916.md` / SHA and



`runs/legacy_cic2022_p2_enhancement_implementation_v1_20260916/acceptance.json`,



`independent_reviews.json`, `real_execution_scope_template.json` and SHA256SUMS.



Frozen recipe unchanged. PREPARE16 + TRAIN9 + control/evaluation12 + ID qualification/review7 =44



unique synthetic cases PASS; final PREPARE progress-display change passed its affected existing test.



Independent interface/runtime reviews PASS. Actual enhancement PREPARE/TRAIN_B/TRAIN_C/CHECK have



NOT started; no new model capability result. This completed implementation/synthetic scope and the



previously authorized ID qualification. Do not treat repeated historical authorizations as a new run.







ID input qualification COMPLETE:5raw ID captures/14092packets,2009original fit/select target mappings



exact. Before model scoring,2583initial candidates minus48cross-capture exposed targets minus157duplicate



session observations leave2378targets/248canonical sessions (source1=1267,source2=1111). Use only



`runs/legacy_id_temporal_qualification_v1_20260916/id_test_extension_v2.json` and pinned v2 target plan.



All2378are UDP; source-local later/new-session holdout within original ID, not TLS/TCP coverage or



independent capture/device/campaign/global chronological FINAL. Other-old-capture raw mirror dedup,



earlier-route exposure and external E3 pretraining separation remain unestablished. Packet targets are



session-dependent. Do not replace this with familiar select or fitted ID; report actual limitations.







Ready chain: PREPARE reuses11529old feature rows and generates851new CIC +2378ID =3229E3 targets;



TRAIN_B/TRAIN_C each200updates on11529old+570new TRAIN; then one fixed-endpoint CHECK with ID2378,



newCIC281,197268valid old report rows/full262050coverage ledger,2188familiar and760fit-ID diagnostics.



TRAIN descriptor excludes CHECK/ID. Old R ledger is reused; no old R re-forward or historical training.



Keep primary ID FPR/attack recall/OOD FPR table and training-covered versus uncovered OOD distinction.



Two cameras are limited same-device extra supervision, not controlled-environment or broad-gain proof.







PREPARE uses existing D1 venv (default Python lacks transformers), TRAIN/CHECK existing C Python;



executables/package versions/code are pinned. No install/download. Real E3 checkpoint forward remains



untested in this scope; any real incompatibility will STOP, zero retries. Local supervisor/status/logs



and best-effort desktop completion/failure notification replace LLM polling. Scripts:



`scripts/start_legacy_cic2022_enhancement_v1.ps1`, `scripts/show_legacy_cic2022_enhancement_v1.ps1`.



Concrete scope template remains execution_authorized=false. NEXT: one explicit whole-chain



PREPARE -> TRAIN_B -> TRAIN_C -> CHECK authorization, then execute once; no per-stage reapproval



within that accepted chain. No new downloads/HPC/resource trial/unlisted FINAL or automatic retry.



Branch/HEAD unchanged;8unrelated modified files byte-identical. Old E3/P2 enhancement first; unified



GRU route DEFERRED; commissioning later. Engineering PASS is not scientific success.







### Historical 2026-09-15 supplement: user requires ID test in this enhancement; OOD training exposure clarified







Read `legacy_id_test_and_ood_exposure_addendum_v1_20260915.md` / SHA and



`runs/legacy_id_test_extension_scope_v1_20260915/metadata_audit.json`. User explicitly requested



independent ID testing in THIS experiment; do not defer it automatically to later paper work or ask again



whether to include it. Main result table must show ID FPR, attack recall and OOD FPR; split OOD by



training-covered/uncovered environments and each source. Familiar-select7.953% and fit-ID0/760 do not



fill the independent ID cell. Original ID anchor is combined-cycle-tls, not every newly trained normal source.







Original P2 DID train on normal OOD:building-monitor2604 core ood_val rows, plus other auxiliary normal



sources (total original normal14013). The four hydraulic/street/predictive/stream report pools were absent



from original fit/select; this does not mean all OOD was excluded from training.



Metadata/ZIP-directory-only audit found5ID benign captures, each with some original fit/select exposure:



tls1 aux-fit600,tls2 aux-select600,tls3/4/5 ID-fit270/270/269. No whole capture can be called untouched.



This does NOT establish all packets/sessions were fitted or rule out a valid same-capture temporal holdout.



NEXT: qualify exact ID targets/sessions/time/context against original fit,normalizer,selection and current



training exposure; freeze ID denominator before scoring, label actual independence level honestly. Do not



treat auxiliary emitted target ordinals as raw packet offsets. No ID metrics/new features/training occurred.



Keep small-enhancement recipe unchanged; append a versioned ID evaluation scope when qualified. This user



request authorizes the ID addition/necessary qualification, not unrelated downloads,HPC,FINAL or old retraining.







### Historical 2026-09-15: fixed old P2 capability ledger COMPLETE; systematic route knowledge indexed







User authorized the fixed-old-model capability ledger with "那就下一步" and requested systematic



history learning; the later "继续" resumes this work. Read



`legacy_p2_supported_capability_ledger_result_20260915.md` / SHA sidecar and



`runs/legacy_p2_supported_capability_ledger_v1_20260915/` (finalstatus, summary, low_FPR_points,



OOD exposure audit, SHA256SUMS and postrun_independent_review). Real scoring COMPLETE in21.563s,



exit0,zero retries;9/9synthetic checks and independent static/output reviews PASS. All262050 report



targets retained;200216 fixed-P2 forward rows,zero training/raw/E3/G0-P1 numeric access. All197268



valid report probabilities match archived probabilities exactly; hard mismatches0.







At original threshold, valid-input attack173959/180378=96.4414%,future90039/94403=95.3773%.



Exact attack-family strings present in original fit:101123/101130=99.9931%; absent:72836/79248=91.9089%.



These clarify existing ability, not training improvement. Seen-family valid coverage is only61.7218%;



ToN scan/bruteforce and C&C supervision mean absent family strings are not wholly unseen mechanisms.



Familiar-normal select FP174/2188=7.9525%;ID fit FP0/760 is fit-only, independent ID still incomplete.



Hydraulic/street/predictive/stream valid FPR76.0928/0.0667/35.0051/0.3333%. All four have zero original



fit/select intersections by UID/capture/source/exact-device-family; not used by P2/normalizer/threshold,



but repeatedly viewed in development. External E3 pretraining complete disjointness remains unknown.



Do not confuse FIT ood_val building-monitor2604 with REPORT ood_val hydraulic3000.







With every one of five normal pools (familiar + four OOD) at empirical FPR<=1%, fixed probability/raw



logit both give attack90.9224%,future88.0544%,seen99.9693%,absent79.3774%. At0.1%, native probability



NO_HARD is due to sigmoid saturation; raw logit gives attack38.2946%, not a new trained improvement.



No deployment threshold selected, no independent guarantee. Keep complete missing ledger; ICMP/GRE



have no valid-input learned-recall evidence. Do not compare these diagnostics directly to different



AB/U1 normal scopes or full missing denominators. Eight unrelated modified files remain byte-identical.







History entry: `project_route_knowledge_index_20260915.md` and



`legacy_core_attack_ood_history_review_20260915.md`, with SHA/source sidecars. They cover few-shot,



C1/CKBQ/CKBW/E3, CKDC/CKDE commissioning failures, later inheritance, current data and operating lessons;



they do not claim every past run/dialogue was independently re-audited. Consult closest prior evidence



before proposing a method; verify later corrections and use targeted literature for new mechanisms.







NEXT RECOMMENDED: implement the sealed two-camera small enhancement and synthetic acceptance, with



end-to-end causal-input/dependency checks. Its570TRAIN/281CHECK may test credential-bruteforce transfer



and same-device supervision; it does not directly cover hydraulic/predictive normal environments.



The enhancement recipe remains unchanged. No enhancement feature preparation, training or new CIC



CHECK scoring occurred or is authorized by this ledger. Old E3/P2 enhancement remains first; unified



GRU route DEFERRED, commissioning later. No new download, HPC, historical rerun or automatic expansion.







### Historical 2026-09-15 clarification: effective-input old baseline recovered; ledger then recommended







User asked about new-data size, future-context leakage and true protocol-supported old capability.



Read `legacy_supported_baseline_and_causality_clarification_20260915.md` / SHA sidecar.



Already disclosed aggregates give old P2 effective-input attack 173959/180378 = 96.4414%; effective



future 90039/94403 = 95.3773%. Four OOD false-positive rates: hydraulic 76.0928%, street 0.0667%,



predictive 35.0051%, stream 0.3333%. These are exposed development evidence at the original threshold,



not independent final, and overall attack is not a seen-attack-only rate. ID independent evidence incomplete.



Missing-state P2 outputs were all alarms but are not a hard-coded fallback; retain full coverage ledger.



570 targeted new rows supplement 11529 replay with E3 frozen; two cameras/limited activities do not



directly cover hydraulic/predictive normal training. Improvement remains a limited-transfer hypothesis.



Current prefix code is current-inclusive. Historical 19 cross-fit/select contexts are a distinct exposure



issue, not proof of old E3 future-packet leakage. Require decoder-to-forward future-mutation fixtures



with later targets/delayed batches during implementation; do not cite I1-only tests as an E3 certificate.



RECOMMENDED NEXT: complete one unified fixed-R effective-input capability ledger before new training,



reusing disclosed aggregates and only explicitly scoped saved-score summaries/fixed scoring if needed.



No historical retraining/rematerialization or opening new CIC CHECK scores first. This question turn



does not authorize new numerical select/report/FINAL access or real execution. Small enhancement design



below remains sealed; no changes to its seed/loss/weights/targets or old scientific judgments.







### Historical 2026-09-15: old E3/P2 small enhancement DESIGN_LOCKED; implementation next, real execution NOT_AUTHORIZED







User authorized the next small enhancement design. Read



`legacy_cic2022_p2_enhancement_small_design_v1_20260915.md` and



`legacy_cic2022_p2_enhancement_small_recipe_v1_20260915.json` / SHA sidecars;



exact design metadata is in `runs/legacy_cic2022_p2_enhancement_design_v1_20260915/`.



No raw reinspection, numerical cache/model access, features, training, evaluation, download or HPC.



R remains original E3/P2/normalizer/probability threshold 0.065159872174263. B/C warm-start independent



P2 copies; 11,529 old input-valid replay targets (7,347 benign + 4,182 attack), not all 18,398 original fit.



Existing 132 cross-role exclusions and 6,737 old-missing exclusions remain explicit; missing does not



always mean unsupported protocol. Old P2 historical exposure, including later GRU CHECK, is not undone.



New 18 normal/Hydra captures: repetitions 1/2 TRAIN, 3 CHECK; at most first/middle/last candidate per



source-local stream gives 570 TRAIN (462/108) and 281 CHECK (227/54). Nmap remains unassigned.



Capture/stream/device/class weights sealed. Same physical device is supported; matched service/vantage



is not. Explicitly use same-device added-supervision interpretation, not environment-controlled invariance.



B loss = 0.8 old class-balanced BCE + 0.2 new hierarchical BCE. C adds 0.05 weighted within-device



logit-ranking loss over 29,304 combinations, reusing the same logits. Seed 27, AdamW lr 3e-4/wd 1e-4,



200 full-batch updates per arm, microbatch 256, clip once at 1.0; no early selection/search/retry.



Future endpoint scope names 197,268 supported / 262,050 old exposed expanded targets (attack + four OOD



pools), 2,188 / 7,000 familiar-normal select development rows, 760 / 809 ID fit diagnostic, and 281 new



CHECK. Original denominators/roles retained. No fresh-ID, unseen-device or truly novel-attack claim.



Fixed original threshold for all arms; low-FPR curves descriptive only, no recalibration. Actual scoped



select/report access is proposed for the future authorized run, not granted by this design record.



NEXT: implement the selective feature/cache reader, matched B/C trainer, endpoint checker and persistent



status launcher; synthetic verification only under implementation scope. No more broad data search or



frontend restart. Future PREPARE -> TRAIN_B -> TRAIN_C -> CHECK is one named chain, not automatic now.



Old results/assets, Git branch/HEAD and unrelated modifications preserved; no new capability result.







### Historical 2026-09-15: 23-file raw semantic probe COMPLETE; input supported, narrow annotations found, training NOT_FROZEN







User authorized checking the23files after explanation of raw material versus training samples. Implemented,



4synthetic checks PASS, real23/23 COMPLETE in29.753s, zero retries. No features/model/train/download/HPC.



Read `legacy_cic2022_two_camera_semantic_probe_result_v1_20260915.md` / SHA and



`runs/legacy_cic2022_two_camera_semantic_probe_v1_20260915/evidence_review.json` / SHA256SUMS.



159565packets read;158995meet literal oldTCP/UDP causal-prefix gate with complete required headers,



no truncation/time regression.570outside-scope packets retained:94ARP+476ICMP. NoIPv6 in this pool.



No frontend change needed for these observed headers; model-forward success NOT tested. Single-packet



prefix legal;6packets is per-burst maximum, not minimum. MissingSYN not made a new eligibility gate.



Expected Amcrest/SimCam officialMAC present in every corresponding packet across normal/attack;



IPs vary. Name leads now have packet-level identity evidence. Normal October/gateway peers versus



attack December/attacker peer; normal0RTSP/0port554, so matched service/vantage still NOT_ESTABLISHED.



Hydra repeatedDESCRIBE/401/auth-header evidence found. Materialized11748annotation CANDIDATES:



1022normal packet targets and10726device-bound Hydra authenticatedDESCRIBE request targets.



Roles null, no frozenTRAIN table; repeated requests/prefixes not independent samples. Normal239streams,



Hydra126streams; substantial SimCam imbalance. Distinct auth strings are not distinct passwords.



FiveNmap captures mix scans/RTSP probes and successfulPLAY/video; no whole-file positive or automatic



benign video-tail labels. Keep these mixed files outside proposed first labeled increment.



NEXT: one explicit small oldE3/P2 enhancement TRAINING DESIGN based on actual normal/Hydra candidates.



Compare same-data/init/budget ordinaryBCE and ranking only with honest claim: same-device added



supervision is testable; stronger same-environment nuisance-removal claim is not supported by this pool.



This is a semantic decision to disclose, not a silently changed protocol or a new same-service hard gate.



Freeze targets/dependencies/weights/roles before real training. No more general metadata hunt/download



required now, no new frontend repair or GRU restart, no automatic real experiment/HPC.



OldE3/P2 enhancement first, commissioning later; old assets/results and8unrelated modifications preserved.



Engineering/input success and provisional annotations are not model improvement or final training readiness.







### Historical 2026-09-15: CIC2022 normal+attack archives ACQUIRED; 23-file semantic probe scoped, support NOT_QUALIFIED







User authorized corresponding normal acquisition/capture-label checks with "可以，动手". Completed



3-Interactions.tar.gz acquisition and metadata-only inspection, no PCAP decoding/features/model/HPC.



Read `legacy_cic2022_interactions_acquisition_result_v1_20260915.md` / SHA sidecar and



`runs/legacy_cic2022_interactions_acquisition_v1_20260915/metadata_assessment.json` / SHA256SUMS.



Normal archive76776437B (~73MiB), SHA256



3ae44cb001b1ffc7001c360bab31ffe7683f4ba14e86ef5d946e81296ba9a468, original retained; gzip/tar PASS.



1227members/878regular;876.pcap suffix entries include12AppleDouble-named sidecars, leaving864ordinary



PCAP-name candidates/89430447B,39device directories,291activity groups (284x3,5x2,2x1).



All13attack device labels have normal directory-name candidates; Gosund Plug - Roomba physical identity



still ambiguous, other12name matches still provisional. No verified pairing/target count or compatibility.



Amcrest/SimCam both have LAN_PHOTO/RECORDING/WATCH3each. Internal normalREADME gives explicit normal



activities but no endpoint/time/per-flow labels or per-file capture point. Official gateway/two-NIC setup



versus attacker-machine attackREADME remains unresolved. IEEE method full text subscription-only; not read.



NEXT: implement/review the pinned23-file raw semantic qualification (12normal WATCH/RECORDING +11Hydra/



Nmap across Amcrest/SimCam),82607797B total. Exact members/archive pins in



`proposed_two_camera_semantic_probe_scope.json` within this run. This is NOT a training denominator.



Check endpoint identity, capture/session completeness, oldinput causal-prefix compatibility and credible



target labels. Tiny normal files do not prove sufficient E3 prefixes; allRTSP/allattack-file positives invalid.



Probe is proposed, NOT implemented/executed; file does not grant real execution. No further archive needed



before probe; no unbounded metadata hunt, automatic Flood expansion, feature/model run or HPC.



Purpose-bounded acquisition permission persists, no repeated blanket download approval. OldE3/P2 first,



commissioning later, GRU DEFERRED; preserve old assets/results,8unrelated edits and prospective input/role



rules. If labels/vantage cannot support the intended matched-ranking claim, report that limitation honestly.



Acquisition and name correspondence are not learned capability or qualified joint-training evidence.







### Historical 2026-09-15: CIC2022 attack archive ACQUIRED / integrity PASS; training support still NOT_QUALIFIED







User accepted purpose/resource-bounded new acquisition and said "可以，动手". This supersedes the



blanket no-new-download rule for this support purpose; do not repeat registration/download permission.



Read `legacy_cic2022_attack_acquisition_result_v1_20260915.md` and its SHA sidecar, plus



`runs/legacy_cic2022_attack_acquisition_v1_20260915/metadata_assessment.json` / SHA256SUMS.



Single official6-Attacks.tar.gz acquired:440524703B (~420MiB), SHA256



9607f885a97848144768e041a1121e74e4fcfb9603ab6a0a1013cf400a08472b; original download preserved.



gzip CRC/length and complete tar iteration PASS. Stream decompressed for integrity; only member headers



and931B internalREADME interpreted, noPCAP extraction/packet decoding/features/inference/train/HPC.



165members,115regularfiles;103.pcap-suffix entries include7AppleDouble-named sidecars, leaving96ordinary



PCAP-name candidates (not header-validated captures):79Flood/17RTSP,34groups,13device labels.



Twelve labels have provisional single-roster-name matches; Gosund Plug - Roomba ambiguous. No raw



device identity/pair count/oldinput compatibility proven. Four groups have1or2 rather than3ordinary files.



InternalREADME says attacks captured on attacker machine; same device name cannot prove matched normal



capture vantage. It names2major families with protocol/tool variants, contains no endpoint/time/flow GT,



and notes live-feed testing after RTSP brute force. Do not label all attack-folder traffic positive.



NEXT: targeted3-Interactions.tar.gz acquisition/memberREADME and official annotation/capture-method



evidence; Amcrest/SimCam normal live-video/control first leads, ArloQ/HeimVision Flood candidates.



Normal archive not yet downloaded, size UNKNOWN; check resources, no full-corpus fetch. Acquisition



is part of qualification: do not require unavailable internal labels before obtaining their source.



Packet-level execution needs a concrete scoped step; no automatic new training/evaluation/HPC.



Train/evaluation share prospective oldinput scope, causal prefixes and role isolation; count in-scope



failures and disclose out-of-scope coverage. DataF0 N>=8 is not imported to this enhancementpilot.



OldE3/P2 enhancement stays first, commissioning later, GRU DEFERRED. Eight unrelated edits preserved;



old protocols/results stay frozen. Acquisition/integrity PASS is not a learned-capability result.







### Historical 2026-09-15: CIC2022 registration COMPLETE; official objects identified; support still NOT_QUALIFIED







User authorized the next support-package preparation, then explicitly authorized official registration



using supplied researcher details. Registration succeeded. The authenticated CIC2022 root has12 entries



(10files/2directories). Read `legacy_cic2022_support_acquisition_preparation_v1_20260915.md` and



`runs/legacy_cic2022_support_inventory_v1_20260915/support_inventory.json` with integrity sidecars.



Only official Readme2798B and DeviceList11616B were retrieved (14414B total); no rawPCAP/archive body.



DeviceList has40 devices/40 distinctMACs but no confirmed attack victims, capture links or paired count.



Exact raw objects are now known:6-Attacks.tar.gz first to resolve internalREADME/labels/member identities;



3-Interactions.tar.gz conditional on usable attack identity for matched interactive normal supervision.



1-Power is optional later coverage, not a substitute for interactive normal examples. No full-corpus fetch.



Directory publishes no sizes/member manifest; independentHEAD returns403 without registration session.



SmallREADME GET diagnosis says Registration required. No cookies copied or registration bypass;



browser registration works, so this403 is not a scientific/corpus failure. Byte budget/controlled transfer



and internal label scope remain unresolved; do not claim training readiness or a small download budget.



Train/evaluation must share prospectively fixed oldinput scope; in-scope extraction failures stay counted,



out-of-scope coverage disclosed, causal prefixes/role isolation preserved. Attack folder is not a blanket



positive label. OldDataF0 device-count gates are not imported into this enhancementpilot; old verdicts stand.



Prior direct history lookup found only knownToN duplicate download copies/CSV metadata, not new qualified



reservePCAPs; no repeated local qualification. MissingJuly history limits exhaustiveness; Gotham remainder



not universally ruled out. Original oldE3/P2 enhancement stays first, commissioning later, GRU DEFERRED.



NEXT: resolve resource scope/transfer for the single named attack archive, obtain its inventory/README,



then select corresponding normal material. User registration authorization persists; do not ask again.



No new raw download/training/HPC authorized or performed. Old assets/results and8 unrelated edits preserved.







### Historical 2026-09-15: local support qualification COMPLETE; no qualified joint-training increment







Read `legacy_local_support_qualification_result_v1_20260915.md` and JSON with SHA sidecars.



User authorized the scoped next material check. No training/inference/raw-record scan/download/HPC.



Seven reserve conn logs cannot supply ready E3 inputs: the inspected ToN root has only six known



PCAPs; its three ZIP central directories (928/18/31 entries) have zero PCAP or nested archive members.



password2/3 have no overlap with any of18 existingGT intervals; GT15/16 are byte duplicates per



the prior inventory, not independent evidence. Other time-overlap candidates are not exact joins.



The local44-column labeled table lacks timestamp/UID/capture lineage (header-only checked), so it



cannot uniquely label raw targets. Official full-schema documents include timestamp/normal labels,



but the local50k-normal table differs from the official300k-normal description and was already used



for evaluation. No label/role reassignment or approximate matching. UnmatchedGT still is not benign.



Gotham69492 candidates remain attack-only/inactive. chunk13/250-row MiraiC&C provenance differs:



region field is sidecar-derived mirai-dos, chunk field is planned preferred mirai-infection.



Neither is declared authoritative without actual materialization provenance; old assets untouched.



normal_1 has843 oldA/4000 targets (3157B); terminal29/3186 is not whole-source coverage.



Its optional same-source coverage census does not resolve new independent environment/normal-pair



support and is NOT the next mandatory gate. Both independent reviewers accepted this prioritization.



Decision: END repeated qualification of these same local candidates; current materials do not support



the selected joint-enhancement mechanism. This is a material limitation, not a failed training or



a universal claim that local data/old models cannot improve. OldE3/P2 enhancement remains first;



commissioning follows; unified frontend/GRU stays DEFERRED. All old verdicts/goals remain unchanged.



NEXT: prepare a minimum new support package with raw objects, explicit normal/attack labeling,



unique timestamp/identity mapping, comparable environments and independent development roles.



Existing CIC2022 metadata lead may be continued for this enhancement purpose; exact members,



compatibility, sizes and roles remain unqualified. No automatic registration/download or new training.



Preserve all historical input/protocol/access rules and eight unrelated tracked modifications.







### Historical 2026-09-14: legacy enhancement design/support review COMPLETE; training NOT_READY







User authorized the proposed design/support work with "可以。动手". Read



`legacy_joint_enhancement_design_and_support_v1_20260914.md` and its SHA sidecar;



`legacy_joint_enhancement_support_scope_v1_20260914.json` records exact candidates and18 source pins.



Old effective E3/P2 remains the baseline; enhance it first, commissioning afterward, unified frontend DEFERRED.



Conditional intervention: fixed old E3/normalizer, independent P2 copy, same-environment attack/benign



score-ranking supervision versus same-data/init/weights/row-exposure ordinary BCE. OriginalP2 is769->128->1



MLP,98689params. Pair ranking does not constrain shared environment offsets or prove causal invariance.



No executable recipe/row count/lambda/budget frozen; no training/inference/cache-numeric access/download/HPC.



Normal-label and raw-input correspondence must be established before implementation/real execution.



Concrete local leads: CKBT seven reserve conn logs (scanning3/4/5/6,password2/3/5), all7 present by stat;



historical reserved_not_used is not proof of no later use. RawPCAP identities/normal pairs remain UNKNOWN.



Existing GT schema audit has18 attack-type tables and no explicit normal label. UnmatchedGT is NOT benign;



do not repeat that census or manufacture negative examples. Original fit hash-sampled9511+5561 joins



are not a new E3 target count. Oldfit ToN normal4000/attack4000 is distinct from new15073TRAIN statistics.



Historical train_test_network.csv has explicit normal labels and still exists, but was used for earlier



second-environment evaluation; provenance lead only, no direct TRAIN/fresh-confirmation reassignment.



NEXT: bounded local annotation-provenance/raw-identity review using the named scope; not a general data



search, newdevice census, CIC registration, F4 repeat or new loss sweep. If only extra attacks qualify,



do not claim OOD supervision improved. Preserve Gotham unused-candidate roles and quarantined160.



Independent static mechanism review complete; precise ToN counts and matched baseline sampling clarified.



All historical scientific verdicts/frozen gates remain; no new capability result. HEAD/branch unchanged;



eight unrelated tracked files preserved. Detailed remaining questions and access limits are in the report.







### Historical 2026-09-14: enhance the old effective system first, then new-device commissioning







User clarified the intended order: first improve the old system's capability, then work on



new-device commissioning. The assistant had prematurely made commissioning data acquisition



the immediate main task. That ordering is superseded; registration/download is not next.



NEXT: a bounded legacy-system enhancement DESIGN based on fixed historical E3/P2 as the



reference, its actual remaining attack/OOD weaknesses, lawful training support and targeted



literature. Select one justified intervention and a matched capability comparison before



implementation or new real execution; no recipe is selected or training authorized yet.



Prioritize seen-attack improvement toward99% or better and attack generalization, while



preserving/improving old OOD strengths and ID benign acceptance. A small CHECK99.76% or



old overall97.37% must not be substituted for the broad seen-attack metric.



The baseline here is the old effective system, not U1 or the weaker new GRU. Keep the old



frontend/input scope and immutable reference assets; any future candidate is separately



versioned. Unified full-coverage frontend work remains DEFERRED. No historical reruns.



"Small improvement" is the desired outcome, not evidence that a small parameter tweak suffices.



Keep the effort bounded and evidence-led; no open-ended tuning or invented99%-before-anything



gate. Commissioning and its paired-data/compatibility requirements remain the subsequent task.



Four capability goals, no-leakage/causal-input rules, all historical failures and no-download/



no-HPC/access boundaries persist. No additional numerical data access or experiment this turn.







### Historical 2026-09-14: old effective E3/P2 + new-device commissioning is the paper priority







Latest correction after user challenged the apparent download->coverage->inheritance loop:



registration is only an access step, not the scientific next milestone. Before committing to



data acquisition, define a meaningful bounded commissioning task within the old input contract



and establish what compatibility evidence is needed for both normal reference and attack query.



The previous instruction to treat registration as the immediate research action is superseded.



Historical coverage failure was exposed in CKDE-S on existing local data (2026-08-27), then



Step-0b proved non-TCP/UDP/keyless/timestamp causes (2026-08-30). Data-F0 CIC2022 bulk download



was0; no evidence that downloading that candidate caused the historical frontend discovery.



The old challenger contract required the entire25467-target universe (no subset escape hatch).



The new paper scope is separate and prospective; it does not narrow that old denominator or



turn its failures into passes. Restricting the task must still leave a useful real-world problem.



Current candidate's benign/attack pairing and old-frontend compatibility are UNKNOWN. TCP/UDP



alone is insufficient: causal session keys, timestamps, required headers, identity and chronology



must hold. Apply fixed input eligibility before model scores, disclose per-device/family coverage,



retain in-scope parser/missing failures, and never drop hard samples based on their outcome.



Use existing metadata first; if exact compatibility needs packet evidence, specify minimal



inventory/sample acquisition and no-training checks under separate data-access authorization.



A candidate mismatch does not trigger frontend rebuilding, inheritance or automatic candidate2



access. Report the precise mismatch and reconsider data/task feasibility under the chosen scope.



Compatibility is not a performance promise: preserve CKDE-Q tied-score/cap failure and CKDE-S



fixed rank4 global-subspace failure. A future mechanism needs a stated difference in information



or learning, with same-device attacks; do not simply repeat threshold raising/subspace removal.







User accepted prioritizing the old effective system plus new-device commissioning for paper value



and asked where to begin. Read `legacy_backbone_commissioning_start_20260914.md` and SHA sidecar.



The unified-frontend capability-recovery line is DEFERRED, with all code/results retained;



its success is no longer a prerequisite for commissioning research. No new training authorized.



Use fixed historical E3/P2/normalizer/theta as the starting baseline under explicit input scope;



model identities are documented, no model/cache numerical access or historical replay this turn.



Keep attack detection/generalization, OOD strengths, ID behavior and seen-attack ~99% aspiration.



Do not mix old best numbers across models/operating points; old97.37% is not pure seen-attack recall.



Frontend causal-prefix/no-leakage requirements persist; old B-default alarms are not learned recall.



NEXT practical node: CIC IoT2022 official member inventory and same-device benign/attack pairing.



Existing23-device benign-only inventory has zero same-device attack pairs; do not repeat that audit.



Official landing and download entry rechecked2026-09-14: entry is a researcher-registration form,



not an accessible member list. User's real registration details or manual completion needed.



No form submitted, bulk download, model execution, candidate2 access or HPC. No paired count claimed.



After legitimate directory access, specify minimum objects, roles and byte budgets before requesting



data acquisition authorization. Then qualify pairing and select one attack-preserving adaptation



mechanism with a same-data baseline; no automatic threshold-calibration rerun or new experiment.



Historical CKDA_WEAK_ONLY, strictFAIL and dual-view TRADEOFF remain; commissioningNOT_EVALUATED.







### Historical 2026-09-14: dual-view real P/T/E COMPLETE / sealed / TRADEOFF







Latest user priority: the new unified-input route must recover the old system's best valid



capability level and strive to exceed it. Broader input coverage or improvement over a weak new



baseline alone does not satisfy the project objective. Keep the old effective attack detection,



attack generalization, OOD strengths and ID behavior as explicit matched comparison references;



inherit capability, not every historical decision. Preserve low false alarms alongside attack recall.



The user specifically wants seen-attack detection to reach about99% or better, beyond the old



roughly97% they recall. This is an improvement objective, not a newly frozen numerical pass gate.



Do not relabel old97.37% overall expanded recall as a pure seen-attack metric: role mix, B-default



alarms and historical data exposure must remain disclosed. A narrow CHECK99.76% does not meet



the broad seen-attack objective by itself. Compare appropriate historical checkpoints under



matched data/operating conditions rather than combining incompatible best numbers into one model.



Once core capability is recovered/improved, proceed to safe new-device commissioning and broader



independent validation. This is the research direction, not proof that frontend coverage was the



only remaining scientific obstacle or a promise of journal acceptance. No new experiment authorized.







User clarification after result review: track four capability axes separately: attack detection,



attack generalization, normal OOD false alarms, and ID benign acceptance. ID benign acceptance



is not proof of a separate ID-vs-OOD classifier; the current shared head is binary attack/benign.



Keep known-normal coverage and unseen-normal generalization distinct. Future-query is not an



unseen-attack-family experiment. CHECK same-source components are limited development evidence.



Unseen-device commissioning remains the scoped route for unseen OOD, but do not abandon old



zero-shot OOD strengths: oldP2 street-camera FP2/3000,stream10/3000 versus U1 2991/2979.



U1 improves predictive-maintenance FP3855->275/9000 and hydraulic2289->2102/3000 vs oldP2;



preserve every pool and historical failures instead of treating all OOD behavior as equivalent.



Next design targets attack detection/generalization and OOD error jointly, with ID preservation.



This clarifies priorities; it does not change frozen thresholds, denominators, verdicts or permissions.







Frontend leakage prevention is an explicit continuing user constraint for every future design:



use only the decision-time causal prefix (no future packets/full-session statistics); isolate both



old-session and new-context dependency components across training and checks; fit normalization



and other learned preprocessing on TRAIN only; never encode labels, teacher correctness, split



roles or query outcomes in features, input selection or missing-view masks. Labels may serve only



their authorized supervision/evaluation roles. Trace legitimate training additions and keep query



data out of training/adaptation references; preserve a genuinely untouched confirmation set.



Existing implementation checked causal AB equivalence, prefix identities, role/component joins,



TRAIN-only normalization and input-only masks. This is not a new full leakage audit or a blanket



guarantee: external pretraining corpus complete de-duplication is unproved, and the expanded pool



has been repeatedly exposed for development. Historical oldP2 CHECK/normalizer exposure remains



disclosed and cannot be reused as clean preprocessing or evidence of independent CHECK accuracy.







Read `unified_dual_view_capability_real_result_v1_20260914.md` and SHA sidecar.



User's “授权下一步” authorized one complete P->T->E including exact E3 cache rows;



see `unified_dual_view_capability_real_authorization_v1_20260914.md`. That run is COMPLETE.



P9.860s/T27.344s/E97.125s, total134.329s; all exit0, verified/seal_verified, zero retries.



P15073 AB states/9402 E3 rows; T two50-epoch heads,5900 total updates;



E199395 E3 rows/560632 scores. No E3 model forward/raw decode/download/HPC/history rerun.



U1-U0 and U1-AB both TRADEOFF; scientific_success=false, no model promotion.



U1 fixedattack94.1983%,future92.8823%,OODpoolmean68.0306%,pooled46.3722%,worst99.7%.



U0 fixedattack90.6396%,future88.1788%,OODpoolmean20.3944%,pooled14.2444%.



U1 vs U0 gains8685 fixedattack detections; vs AB gains12420, still7740 below oldP2.



At pooled1% FPR: U1 TPR57.0957% vs U0 32.0119% / AB36.5503% (real ranking gain).



At pooled0.1%: U1 18.4474% vs U0 29.8066% / AB33.6783% (tail regression).



These are exposed-development ranking diagnostics, not deployable calibrated thresholds.



Street-camera FP2991/3000 and stream2979/3000; U1 0.1% tail18/18 street-camera.



All4 expanded normal pools absent from TRAIN; coverage gap known, its remedy not yet proven.



U1 TRAIN3428/3428 attacks,0/11645 normalFP; CHECK823/825,0/2368,ID0/151.



CHECK Battack denominator0. Both heads vsfixedA zeroCHECKflips; vsP2 negative2/positive5.



Expanded B U1 attack62143/63672,normal0/1110; B still has no E3 representation.



45 historical reference source and8 unrelated tracked hashes preserved;42 implementation pins intact.



Pmanifest:1ea788df7f1401281d7f35a02ac78dfb4ea1daf707ade036f597a060ad817629.



Tmanifest:3fc3b249fc4ea53c64d0f3cccb19e650f664cbff91b6610c121af31746a80371.



Emanifest:d1468e4f24071f082508041b29f54969efd94c1796bb6920d271b967a4aea634.



NEXT: substantive qualified-training-coverage / useful-representation design with targeted research.



No adjacent same15073TRAIN head/lr/epoch/freeze/KD search; no automatic new execution.



Do not relabel exposed evaluation rows as TRAIN and still claim independent testing.



JointNOT_REACHED, historicalstrictFAIL, commissioningNOT_EVALUATED; development evidence only.



Status remains available through `scripts/show_unified_dual_view_v1.ps1` and stage status.html.







### Historical 2026-09-14: dual-view implementation SEALED / 33 tests PASS / real P/T/E NOT_STARTED







User authorized implementation with “可以，动手实现”. Read



`unified_dual_view_capability_implementation_v1_20260914.md` and SHA sidecar.



Implementation package: `runs/unified_dual_view_implementation_v1_20260914/`; manifest SHA:



33b69e49a1468cff91507db7f5d53ff2ad3b522a75347a55e742b0cfc46f5d83.



33/33 generated tests PASS in47.704s, including two50-epoch generated heads and Windows P->T->E,



input-only mask, selected-row NPZ decode, causal fixed encoder, exact ranking ties, failure/wall stop.



First generated-chain CAP_DRIFT was a fixture cap mismatch; fixed within implementation scope,



no real experiment retry or resource experiment. Real frozen caps/recipe unchanged.



check-implementation READY; real P/T/E NOT_STARTED, output directories absent.



Real model/feature numeric access, E3 loads/forwards, raw decode/download/HPC all0.



Original45 reference source and8 unrelated tracked hashes preserved; branch/HEAD unchanged.



NEXT: one explicit real P->T->E grant including exact E3 cache rows. P9402 TRAIN E3 rows;



T two new shared heads,5900 total updates; E199395 E3 rows,560632 total endpoint scores.



Normal stage transitions automatic; exception STOP,zero retry. No new decoding/E3 run or tuning fallback.



Status: `scripts/show_unified_dual_view_v1.ps1`; future stage status.html pages auto-refresh,



no LLM polling. Historical joint NOT_REACHED, strict FAIL, commissioning NOT_EVALUATED remain.



Implementation PASS is not evidence of real capability gain. No real execution authorization added.







### Historical 2026-09-14: dual-view capability design fixed; implementation next, no real execution







Read `unified_dual_view_capability_design_v1_20260914.md`, recipe JSON, evidence JSON,



and review with SHA sidecars. Design/static review complete; implementation and real P/T/E NOT_STARTED.



Selected intervention: fixed AB128 for every legal A+B target plus existing historical E3768



where input-valid, one fresh shared897->128->1 MLP. Two arms U0 zero E3 content and U1 real content,



same input-only availability flag, TRAIN-only normalizers, initialization and training rule.



Each arm uses all15073 TRAIN, class-balanced per-target BCE, seed2705,50epochs,batch256,



2950updates; two arms5900. This is additional representation content, not another F4-only head tweak.



Use all9402 valid TRAIN E3 rows including23 teacher-wrong normals; never the9379 teacher selector.



Existing E3 caches allow zero new raw decode/E3 model loads/forwards; cache numeric access is NOT granted.



Historical E3 adapter/session/tokenizer semantics retained; source-level IAT/ACK differences disclosed.



No ICMP extension or claim of universal pretrained E3: missing-view B retains real AB content only.



All four expanded normal OOD pools have zero TRAIN targets; known-family CHECK already near ceiling.



Preserve all expanded metrics, low-FPR tails and historical failures; no CHECK-only success claim.



P will prepare TRAIN only; T two fresh heads; E CHECK+expanded and cached TRAIN endpoint audit.



Future one explicit P->T->E grant must include exact E3 cache rows; normal transitions automatic,



exception STOP/zero retry, local status page, no LLM polling/download/HPC/resource retrial.



NEXT: implement new version plus generated acceptance, without real numeric data access.



Historical joint NOT_REACHED, strict FAIL, commissioning NOT_EVALUATED remain. No result gain claimed.



Original40 reference-code and8 unrelated tracked hashes preserved; branch/HEAD unchanged.







### Historical 2026-09-14: unified capability objective clarified; pretrained representation design next







Read `project_objective_and_representation_start_20260914.md` and SHA sidecar.



User priorities: exceed old effectiveattack/generalization; lowFP on independent flows from



training-covered normalOOD; unseen devices addressed by later commissioning with attackretention.



Inheritance is an important attackbenchmark, not an independent obligation to copy everyolddecision.



NEXT recommended design starts with usefulpretrained representation under unifiedlegalinputs:



audit fixedE3/tokenizer vsadapter semantics and qualifiedtrainingsupport, select one primaryintervention.



F1/F2/F3 did not directly falsify E3parameterreuse; TCP/UDP/nonIP coverage limits remain real.



Do not redo oldmissing census or assume protocolid extension provides learnedsemantics.



PublicnetFoundv5 relevantsections rechecked; latestpaper is not oldcheckpoint identity or successproof.



No newmodel chosen/frozen, no numeric computation/download/HPC or newrealexecution authorization.



H_AB T/E COMPLETE/TRADEOFF below; END adjacent same15073TRAIN head/lr/epoch/freeze/KD tuning.



JointNOT_REACHED,historicalstrictFAIL,commissioningNOT_EVALUATED remain; historicalartifacts unchanged.







### Historical 2026-09-13: H_AB T/E COMPLETE / sealed / TRADEOFF; adjacent same-TRAIN tuning ends







Read `frontend_ab_readout_preservation_real_result_v1_20260913.md` and SHA sidecar.



T217.578s,E100.891s,exit0,verified/seal_verified,stderr0,zero retries; no run active.



T3940updates/7880forwards,E280316targets/2207forwards; frozen82944 params unchanged.



H_AB attack89.3989%,future86.5858%,OODpoolmean22.4111%,pooled15.6667%,worst67.6%.



TPR@1%35.3542%,@0.1%33.3096%; both contrasts H_AB-AB and H_AB-C0_AB TRADEOFF.



VsAB fixedattack+707(+.2897pp),normalfalsealarms+284(all4OODpools worsen).



At equal180/18normalfalsealarms,attackdetections decline2919/900 vsAB.



TRAIN3423/3428 attacks,0/11645normalFP; CHECK823/825,0/2368normalFP; ID0/151FP.



CommonAcheck vsfixedA zeroflips; vsP2 negative2/positive5; strictFAIL remains.



H_AB retains more lowFPR recall thanC0_AB but loses8222fixedattackdetections; no joint breakthrough.



Tmanifest:e8b3482cf7f702f3d6e85ad4bd7d6081991658104a8e4daa353abedf87eebf67.



Emanifest:67445062fe0e0d986b79cba4d05e6d8a2574d25a5d1824979665dfcc88089828.



NEXT: honor frozen stopping rule; END adjacent same15073TRAIN head/lr/epoch/freeze/KD variants.



Next substantive design requires justified addedinput or qualifiedtraining coverage and targetedresearch.



Failure does not prove F4informationinsufficiency or GRU/head universal limit; no new execution grant.



No duplicate/extra run,P/download/HPC/rawdecode/LLMpolling. 40referencecode+8unrelated hashes preserved.



JointNOT_REACHED,historicalstrictFAIL,commissioningNOT_EVALUATED. All exposeddevelopment only.







### Historical 2026-09-13: H_AB real T RUNNING / automatic E AUTHORIZED







User replied “动手下一步” to explicit completeT->E scope after implementation delivery.



Read `frontend_ab_readout_preservation_real_authorization_v1_20260913.md` and SHA sidecar.



Authorization SHA:391e3bb4825b821f448e183f3a670c641f84469703c3fc92c617acdfa8639d47.



Implementation READY,branch/HEAD unchanged,eight unrelated tracked hashes protected.



Persistent local controller PID67028 launched once. Bounded startup snapshot at15.328s:



H_AB epoch1/20,146/3940updates,292studentforwards; stderr0bytes, no failure trace.



EntryINPUT_AND_ORDER_IDENTITY_VERIFIED; one sealedAB load,97808792TRAIN featurebytes decoded.



Teacher/guard/D/rawdecode/retry/network counters0. Real training is active, not a result.



E NOT_STARTED at startup and automatically authorized after verified/sealedT; no repeat permission.



Freeze82944 encoder/projection params,train8321 fullMLP; same frozen20epochs/lr1e-4/order/data.



E280316targets/2207forwards; stored historical references only. ExceptionSTOP,zero retry.



NoLLMpolling/automation/resource retrial/download/HPC/historyrerun. Local supervisor owns progress.



Status:`scripts/show_frontend_ab_readout_preservation_v1.ps1`; auto-refresh T page:



`runs/frontend_ab_readout_preservation_t_v1_20260913/status.html`; E uses corresponding `_e_` directory.



NEXT: authorized normalT->E completes automatically or stops; do not duplicate launch.



Live verified/sealed terminals supersede this startup snapshot. JointNOT_REACHED,



historicalstrictFAIL,commissioningNOT_EVALUATED remain until proper result review.



No six-metricjointgain vsAB ends adjacent same15073TRAIN tuning; next justifiedinput/coverage.







### Historical 2026-09-13: H_AB implementation SEALED / 41 tests PASS / real T/E NOT_STARTED







User authorized “动手，授权下一步” for frozen H_AB implementation and generated acceptance.



Read `frontend_ab_readout_preservation_implementation_v1_20260913.md` and SHA sidecar.



41/41 generated tests PASS; acceptance13.718s,unittest13.342s; bothPowerShell parsingPASS.



Package:`runs/frontend_ab_readout_preservation_implementation_v1_20260913/`; manifest SHA:



c13e309308cd27c64f9f1bc7268077401cdd370890bf3110f4e42dae622e7329.



44 implementation pins; previousAB-start47pins/runtime/eight unrelated tracked hashes preserved.



H_AB keeps fullAB initialization, freezes82944 encoder/projection params, trains8321 fullMLP.



Exact originalC0 multistep numerics/lr1e-4/order; headonlyAdamW, frozen gradNone/state absent.



GeneratedactualT/E plus Windows success/failure/wallcap supervision PASS; no real numeric access.



NoP/teacher/guard/D, including endpoint observations. Historical scores only in E.



check-implementation READY; realT/E bothNOT_STARTED, outputdirectories absent. No scientific gain claimed.



NEXT: one explicit realT->E grant covers entry,3940updates and fixed280316targets/2207Eforwards;



normalchain automatic, exceptionSTOP/zero retry. No normal-transition repeat ask or LLMpolling.



Status:`scripts/show_frontend_ab_readout_preservation_v1.ps1`; futureT/E status.html auto-refresh.



If no six-metricjointgain vsAB, end adjacent same15073TRAIN microtuning; next justifiedinput/coverage.



JointNOT_REACHED,historicalstrictFAIL,commissioningNOT_EVALUATED. Design/recipe/oldresults unchanged.







### Historical 2026-09-13: H_AB full-head / fixed-AB-encoder DESIGN FROZEN







User authorized evidence-led next design with “动手，我只能依靠你了”.



Read `frontend_ab_readout_preservation_research_decision_v1_20260913.md`,



`frontend_ab_readout_preservation_design_v1_20260913.md`, recipeJSON and review, all SHA sealed.



Design SHA:dc801799efe4c73b22b6cc57694d47a4f7860650316bb3651967ad5f7cf718e7.



Recipe SHA:36a6fb18a52b4ab212f3a7eff7fbb0b37a8d124d7f79cd9ed56b6f4f68d89417.



ONE new arm H_AB from sealedAB: freeze82944 event_projection/GRU params, train complete



8321-param MLP. OriginalC0_AB labels/order20epochs/3940updates/lr1e-4 unchanged.



Compare storedAB/C0_AB; no old reruns, no teacher/guard/P or D even in endpoint observations.



T7880forwards; E280316targets/2207forwards; no real execution in this design turn.



Independent scientific+mechanical static review PASS; not generated acceptance or sciencePASS.



Same directlabel lifetime904380 asC0_AB; parameterupdate exposure deliberately differs.



H_AB/C0_AB do not use teacher knowledge; historicalP2/R checkexposure is a separate limitation.



N1 was65-param finiteTRAIN LP on otherF5base, not this fullMLP+expandedoutcome question.



Freeze/clipping intervention can still break outputranking; no causal/input-sufficiency guarantee.



If stillTRADEOFF/unchanged/regression vsAB, end adjacent same15073TRAIN head/lr/freeze/KD trials;



next must justify added input information or qualified training support, not another near variant.



40 inherited sourcepins+8 unrelated hashes unchanged. No F4redo, model load, forward, rawdecode,



training, newevaluation, dataset/checkpointdownload or HPC; public paper reading only.



NEXT: implementation+generatedacceptance. Future one explicitrealT->E grant covers normalchain,



exceptionSTOP/zero retry/noLLMpolling. JointNOT_REACHED,strictFAIL,commissioningNOT_EVALUATED.







### Historical 2026-09-13: AB-start T/E COMPLETE / sealed / scientific TRADEOFF







Read `frontend_ab_start_control_real_result_v1_20260913.md` and SHA sidecar.



T1355.563s,E112.813s; both COMPLETE/verified/seal_verified,exit0,zero retries.



C0_AB/R_AB each3940 updates; E560632 target presentations. All five contrasts TRADEOFF.



C0_AB attack92.7679%,OOD poolmean21.0722%,TPR@1%33.3776%,@0.1%30.5982%.



R_AB attack91.1719%,OOD21.7556%,TPR@1%31.5677%,@0.1%12.0213%.



Both improve fixed attack vsAB89.1092% but lose AB low-FPR TPR36.5503%/33.6783%.



C0_AB has hydraulic180/18 false positives at1%/0.1%; R_AB reintroduces predictive



maintenance169/17 at those points. This implicates the fullR package's compatibility,



not a uniquely identified loss cause. R_AB trains teacher scores closer yet generalizes



worse on major metrics vsC0_AB; both have identicalTRAIN3423/3428,benign0/11645.



JointNOT_REACHED,historical strictFAIL,commissioningNOT_EVALUATED remain.



NEXT: evidence-led learning mechanism/training support review and design, with targeted



literature before new mechanism choice. No automatic more epochs/weights/checkpoint/AB->Q



or full-data run. No new execution authorized/running. Preserve sealed evidence and all



unrelated edits; no newP/download/HPC/LLM polling. Live terminals supersede prior snapshots.







### Historical 2026-09-12: AB-start real T RUNNING / automatic E AUTHORIZED







User explicitly authorized “授权继续” after the complete real T->E scope.



Read `frontend_ab_start_control_real_authorization_v1_20260912.md` and SHA sidecar.



Entry readiness PASS; branch/HEAD unchanged, all eight unrelated tracked hashes protected.



Persistent local controller PID8668 launched once. Startup snapshot at8.594s:



C0_AB epoch1/20,6/3940 optimizer updates,12 student forwards; stderr empty.



Existing9379 teacher rows reused, derived rows0. This is real training progress,



not completion or a scientific result. E NOT_STARTED and automatically authorized



after both frozen arms complete and T is verified/sealed. No repeat permission.



Each arm starts sealedAB independently,3940 updates; then fixed E560632 targets.



Exception STOP,zero retry. No newP,LLM polling,download,HPC,search or historical rerun.



Status:`scripts/show_frontend_ab_start_control_v1.ps1`.



Auto-refresh page:`runs/frontend_ab_start_control_t_v1_20260912/status.html`;



E page uses corresponding `_e_` directory once started. Read sealed stage terminals



before interpreting results. JointNOT_REACHED,strict historicalFAIL and



commissioningNOT_EVALUATED remain. NEXT: supervisor completes authorizedT->E;



do not duplicate launch. Live progress and verified terminals supersede this snapshot.







### Historical 2026-09-12: AB-start implementation SEALED / 35 tests PASS / real T/E NOT_STARTED







User authorized “动手实现”. Read `frontend_ab_start_control_implementation_v1_20260912.md`



and SHA sidecar. Implementation and generated acceptance complete:35/35 PASS,13.069s;



PowerShell parsing and check-implementation PASS. New realT/E status bothNOT_STARTED.



Package:`runs/frontend_ab_start_control_implementation_v1_20260912/`; manifest SHA:



`03f0091297052b0a4e0d8816bea424e5f3a48faff3cfecf450d0baa2635c34c2`.



47 code/doc/script pins; old frozen sources/runtime/eight unrelated tracked hashes preserved.



C0_AB/R_AB independently copy sealedAB, same original objectives. No newP; T entry



consumes pinned old margins/scale directly, no derive or new teacher. C0 train teacher/guard0;



R initialAguard nonzero is valid. Exact original C0/R multistep equivalence verified synthetically.



Generated T->E plus Windows success/failure/wallcap supervision verified; no real model load,



forward/update or teacher rows in acceptance. This is engineering PASS, not capability PASS.



NEXT: one explicit realT->E authorization may cover entry reuse check, both3940-update arms



and fixedE automatically. No normal-transition repeat ask; exceptionSTOP,zero retry.



Status:`scripts/show_frontend_ab_start_control_v1.ps1`; startup script has explicitT/E switches.



NoLLM polling/resource retrial/download/HPC/old experiment rerun. JointNOT_REACHED,



historical strictFAIL and commissioningNOT_EVALUATED remain;1%OOD is not new absoluteTPR gate.







### Historical 2026-09-12: AB-start C0_AB/R_AB DESIGN FROZEN / implementation next







Read `frontend_ab_start_control_design_v1_20260912.md`, recipe JSON and SHA sidecars;



static scientific/execution review:`frontend_ab_start_control_design_review_v1_20260912.md`.



Two new arms independently start sealedAB; C0_AB original label-only, R_AB original



four-termR with unchanged Aguard/teacher/data/20epochs. No newP: T entry verifies and



reuses sealed oldP, then two3940-update trajectories, followed by one fixedE if authorized.



Full student/head inherited, resetAdamW; AB initialAguard may be nonzero. ExactAB state



b800d9f1a3e11e557838cb9bdc22e7acc8559d198a57fa21a3da6c80bb7b9fda pinned.



Extra20epochs match, lifetimeB exposure differs by226840 target presentations per lineage.



Original six-metric directional flag unchanged;1% pooledOOD is not a new absoluteTPR gate.



0.1%/family/pool risks separately mandatory; new-arm relative gains cannot hide both losingAB.



NEXT: implementation and generated acceptance. Current user grant is DESIGN/REVIEW only;



no real model load/forward/update and no new execution. Later one explicitT->E grant can



cover normal transitions without repeat permission; exceptionSTOP,zero retry. NoLLM polling.



40 original source hashes/8 unrelated tracked hashes unchanged. JointNOT_REACHED;



old strictFAIL remains, commissioningNOT_EVALUATED. No new data/download/HPC/old experiment rerun.







### Historical 2026-09-12: Q/R analysis COMPLETE / AB-start C0/R contrast recommended







Read `frontend_qr_tail_and_next_decision_20260912.md`, JSON and SHA sidecar.



Authorized saved-score analysis only; no new model forward/training/raw decode/download.



At existing1%/0.1% FPR points,A/C0/C2/Q/R each have180/18 predictive-maintenance



benign errors; AB has zero predictive errors there. R top180 overlaps A168,C2 177.



R attack gain vsC2 +1255 is TCPScan +1578,other families net-323; joint NOT_REACHED.



All C0/C1/C2/Q/R began at A; new recommended contrast starts both C0/R at sealed AB,



keeping each original objective/TRAIN/20epoch budget/seed/Aguard unchanged. This tests



saved state/prior learning history, not equal lifetime B exposure or pure teacher content.



AB-start may have nonzero Aguard at step0; do not alter the formula to pass old assertions.



NEXT: freeze/implement this one bounded AB-start comparison; new real execution requires



corresponding authorization. No new experiment launched or implicitly authorized here.



If both lose tail or remain a tradeoff, pursue substantive learning/coverage/input support;



no checkpoint search or automatic extra arms. Historical FAIL and commissioning later remain.







### Historical 2026-09-12: Q/R real P/T/E COMPLETE / verified / scientific TRADEOFF







Read `frontend_task_aligned_transfer_real_result_v1_20260912.md` and SHA sidecar.



P/T/E all COMPLETE, verified/sealed, exit0, zero retries; total stage time1519.171s.



Q/R completed3940 updates each on frozen15073 A+B TRAIN; one authorized E complete.



R attack95.1567% vs C2 94.6425%, but OOD pool-mean23.2917% vs22.6000% (worse).



Q attack94.2799%, OOD21.7361%, but merged TPR@1%FPR17.4034% vs C1 29.6300%.



All seven saved contrasts TRADEOFF. R has highest listed new-student fixed-point



attack recall, still below old P2 97.3698%; AB low-FPR reference remains stronger.



TRAIN teacher hard agreement9377/9379(Q),9378/9379(R) is not generalization success.



Joint milestone NOT_REACHED; prior strict inheritance FAIL remains; commissioning



NOT_EVALUATED. Single-seed exposed development evidence, no pure transfer attribution.



NEXT: interpret capability tradeoffs and decide the next mechanism from evidence.



No new training/diagnostic/evaluation authorized or running; no automatic retry/tuning.



Status:`scripts/show_frontend_task_aligned_transfer_v1.ps1`. All unrelated edits preserved.







### Historical 2026-09-12: Q/R real P COMPLETE / T RUNNING / automatic E authorized







User explicitly authorized “可以。授权下一步” after the full P->T->E scope.



Read `frontend_task_aligned_transfer_real_authorization_v1_20260912.md` and



`frontend_task_aligned_transfer_p_result_and_t_start_v1_20260912.md` with sidecars.



P COMPLETE in5.500s, verified/sealed;9379 targets,2957/3329 class-context counts,



zero margin-hard conflicts. s_q64=24.467974454982155; no model/teacher forward or updates.



P SHA256SUMS SHA:`6d93ae8d74b3c2d754df63fc9224146a14424f43e4787d6b5dd1fdc92d26e76f`.



Persistent controller64452 automatically entered T. At34.625s:Q epoch1/20,



143 optimizer updates completed,286 forwards; log later reached step146,stderr empty.



This is a startup snapshot, not T completion. Actual stage progress/terminal override it.



Both Q/R run once from sealed A,3940 updates each; E automatically follows verified



T and both final candidates. Existing authorization covers all normal transitions;



do not request T-to-E permission, start duplicates or rerun P. Exception STOP,zero retry.



Status:`scripts/show_frontend_task_aligned_transfer_v1.ps1`.



T human page:`runs/frontend_task_aligned_transfer_t_v1_20260912/status.html`.



NEXT: local supervisor continues T->E; no LLM polling/heartbeat. Verify sealed terminal



results before scientific interpretation. Attack/OOD joint milestone remains NOT_REACHED;



new-device commissioning later. Frozen rules/old experiments/eight unrelated files preserved.







### Historical 2026-09-12: Q/R implementation SEALED / 42 tests PASS / real P/T/E NOT_STARTED







User authorized implementation after the explicit implementation/synthetic scope:



“授权动手下一步”. Read `frontend_task_aligned_transfer_implementation_v1_20260912.md`



and sidecar. Q/R code, derived-P, two-arm T, fixed E, Windows supervision and status



scripts implemented. Generated actual P->T->E and all42 tests PASS; real numerical



run-file access blocked during acceptance. Implementation entry check PASS.



Package:`runs/frontend_task_aligned_transfer_implementation_v1_20260912/`.



SHA256SUMS SHA256:`1b6a30f52137ca8ca6b9451d8d2facdb0778bcd1a2510df346fc8c85fdfde00e`.



44 source/document/script pins; frozen recipe/old code/eight unrelated hashes unchanged.



No new real teacher/student forward, optimizer update or evaluation. Current status



script confirms P=NOT_STARTED,T=NOT_STARTED,E=NOT_STARTED. Synthetic PASS is not



scientific success; attack/OOD joint milestone remains NOT_REACHED.



NEXT: separately authorize real derived-P -> Q/R T -> one E; a single explicit grant



may cover the entire conditional chain, no repeat permission at normal transitions.



Do not rerun synthetic/resource trials without new changes or concerns, old experiments,



or F4. No hyperparameter search/download/HPC/LLM polling. Stop on exception, zero retry.



Status:`scripts/show_frontend_task_aligned_transfer_v1.ps1`; commissioning remains later.







### Historical 2026-09-12: Q/R task-output transfer design COMPLETE / implementation next







Read `frontend_task_aligned_transfer_design_v1_20260912.md`, recipe JSON and SHA sidecars.



Literature-informed design and independent mathematical/protocol review completed;



no new teacher/student forward, training or evaluation. Q uses the unchanged C1



label+guard objective plus symmetric finite teacher-margin supervision on actual qS.



R adds projected contribution-residual Huber (sum128/127), testing incremental value.



Both start independently from sealed A; same15073 A+B TRAIN,9379 teacher rows,



seed2705,20x197 updates each. Only two new trajectories proposed; no old-arm reruns.



Future P derives margins/scale from sealed TRAIN cache; no old mixed NPZ/new teacher.



Negative endpoint gradients may reflect saturated BCE versus finite correct margins:



they do not by themselves prove harmful transfer. Coordinate orthogonality is not



parameter-gradient orthogonality; R may still harm Q. C0 low-FPR loss remains relevant.



Joint attack/OOD capability and AB low-FPR references govern; teacher fit is not success.



Q_const/R_perm are later attribution controls if warranted, not extra current arms.



NEXT: implement frozen Q/R and generated acceptance. Current authorization remains



design/review/documentation only; this recipe has no implementation or real P/T/E grant.



Later explicit joint P->T->E authorization may cover transitions without repeated asks.



Attack/OOD joint milestone NOT_REACHED; commissioning later. No LLM polling/HPC/download.







### Historical 2026-09-12: fixed-C2 TRAIN diagnostic COMPLETE / targeted design next







Read `frontend_transfer_diagnostic_real_result_v1_20260912.md` and sidecar.



One authorized diagnostic COMPLETE in80.844s, verified/sealed, zero retries/updates.



15073 TRAIN targets/9379 teacher rows;394 forwards,788 task gradients,197 hidden



sensitivities. C2/D unchanged; no new evaluation/teacher computation. Manifest SHA:



`0831d2066e62d1c7dc9bf977afd5a8401c4d6c388735596b2061062c32a77fd3`.



Teacher reaches shared encoder:mean norm0.0255944 vs label0.00209185, cosine−0.851657;



134/197 buckets teacher/label oppose. TRAIN task residual MAE4.22779 logits.



Aux/deploy correlation0.970921 pooled but−0.105339 within attacks; teacher/aux attack



correlation0.819036. These are fixed-endpoint/local training diagnostics, not historical



AdamW or generalization causality. No proof that deploy head never uses teacher.



C0 already has low-FPR degradation, so teacher conflict cannot explain all AB→C2 loss.



Do not abandon transfer from one recipe, or blindly extend/strengthen the same loss.



NEXT: literature-informed single-mechanism design focused on actual deployment



judgment and teacher/label compatibility; direct task/decision transfer is a necessary



reference, generic gradient surgery alone is not a proved solution. Retain AB/C0 controls.



No new training/evaluation is authorized or running; commissioning remains later.



Attack/OOD joint milestone NOT_REACHED. Status script now verifies COMPLETE.







### Historical 2026-09-12: fixed-C2 TRAIN diagnostic launch / implementation sealed







User approved the bounded mechanism diagnostic: “行吧，一定要考虑全面，你是主力选手。”



Read `frontend_transfer_diagnostic_scope_v1_20260912.md`, JSON and SHA sidecar.



Authorization covers implementation, generated acceptance and ONE real fixed-C2 TRAIN



diagnostic after acceptance; no further implementation/diagnostic permission needed.



Existing C2 and training-only D remain fixed:15073 TRAIN targets,9379 sealed A teacher



rows,197 original epoch20 buckets,394 student forwards,788 task-gradient calls plus



197 hidden-sensitivity calls. No optimizer construction or parameter updates/candidates.



15min/8GiB/64MiB cap; stop on exception, zero retry; no check/expanded numeric access,



threshold change, download, resource retrial, HPC or LLM polling automation.



Synthetic acceptance30/30 PASS, including generated actual-diagnose and Windows Job



with concurrent progress readers. Implementation seal SHA:



`a8cb7b7c1a69c3a2c95beff39c91b21fc00c036019c6c8e57a0afddcc515b42d`.



Read `frontend_transfer_diagnostic_implementation_v1_20260912.md` and sidecar.



Real diagnostic launched by authorized start script, controller40452. Startup is not



completion; actual terminal/seal override this snapshot. Do not start another attempt.



NEXT: let local supervisor finish, verify seal and interpret evidence before proposing



any separately authorized revision. Status:`scripts/show_frontend_transfer_diagnostic_v1.ps1`.



Current C2 joint milestone remains NOT_REACHED; one recipe does not falsify transfer.







### Historical 2026-09-11: attack priority / bounded fair-trial review before route exit







User clarified: pursue strong seen-type and unseen-traffic attack performance at



low benign-OOD FPR; 99.99%/97% are research aspirations, not modified frozen gates.



Completely unseen attack families need not be the main mandatory claim. Define



unseen samples/sessions/environments/variants/families explicitly in future designs.



User requires fair, bounded investigation before abandoning a potentially useful route.



Read `frontend_transfer_fair_trial_and_target_clarification_20260911.md` and sidecar.



Saved-log review: C2 teacher loss0.25349→0.05342, still falling in epoch20;



no convergence or extra-epoch benefit proved. C2 epochs10–20 had zero clipped steps;



chronic late gradient clipping is not supported. C1 guard active only76/3940 steps.



Current C2 joint success remains unproved; this single recipe does not falsify transfer.



NEXT: specify one fixed-endpoint TRAIN-only mechanism diagnostic of teacher readout,



task-direction residuals and separate encoder gradients before deciding whether a single



targeted revision deserves execution. New forwards/backwards/training remain unauthorized.



No blind hyperparameter search or frozen-run extension. Keep AB/C0 baselines and all



prior results. CIC2022 PENDING remains, but data acquisition does not replace attack repair



or automatically outrank this mechanism check. No repeat of old paired-data inventory.







### Historical 2026-09-11: post-result review / proposal to stop extending transfer package







Read `frontend_task_transfer_post_result_research_decision_20260911.md` and sidecar.



Independent read-only review and targeted primary literature checks completed; no



new training, inference, ROC, raw decoding, data-body download or access-form submission.



C0 explains most fixed-point improvement over historical AB; all new loss contrasts



remain tradeoffs. At the already-frozen 0.1% FPR diagnostic, C2 detects49/244050,



AB82192/244050 (both18 normal FPs). Raw-logit/tie semantics checked; no sigmoid artifact.



Preserve AB's low-FPR baseline and C0's plain fine-tuning baseline; do not promote C2.



Old P2 B predictions are all alarms (100% attack AND normal); C2 B shows real



separation but A content-recognition recall still trails old P2 by2.5746pp.



NEXT recommendation: advance the existing CIC IoT2022 PENDING member-acquisition



work package (official access, bounded objects/budgets, actual benign/victim mapping),



not another audit of known-insufficient old paired pools or more current-loss tuning.



Member identities/bytes/paired counts remain unknown; official access is a registration



form. No download/registration/new experiment authorized by this research request.



Behavioral evidence and necessary causal-prefix information guide the next learning



design; paired commissioning data are not a blanket prerequisite for all representation



research. All historical scientific rules and results remain frozen.







### Historical 2026-09-11: V2 T/E COMPLETE / partial attack recovery, joint milestone NOT_REACHED







Read `frontend_task_knowledge_transfer_v2_real_result_20260911.md` and sidecar.



T1952.25s / E131.203s COMPLETE, verified and seals checked; zero retry. Three arms



20 epochs each,11820 total updates;840948 evaluated targets. P V1 reused unchanged.



C0/C1/C2 attack recall94.0205/93.9971/94.6425%; old AB89.1092%, P2 97.3698%.



C2 OOD pool-mean FPR22.6000% versus AB20.5944%, P2 29.8833%; worst pool56.90%.



C2 pooled TPR@1%FPR29.6333% versus AB36.5503%. All mechanism contrasts TRADEOFF.



C2 teacher increment vs C1 is +0.6454pp attack with costs; no joint breakthrough.



Fixed-A common-check retention passes, old-P2 common-check zero-regression fails



(two negatives per arm). Historical FAILs unchanged; commissioning NOT_EVALUATED.



NEXT: review sealed coverage/information and objective conflicts before any new recipe;



no automatic training, tuning, repeat evaluation or new real execution authorized.



This terminal state supersedes the startup snapshot below. No LLM heartbeat.







### Historical 2026-09-11: V2 T RUNNING / automatic E authorized







User explicitly replied “下一步，我授权” after the V2 fix and new T→E request.



Read `frontend_task_knowledge_transfer_v2_real_authorization_20260911.md` and sidecar.



Reuse sealed P V1; one V2 three-arm T followed automatically by E after all final



candidates are sealed. No additional permission between T and E; exception-stop,



zero automatic retry. Numerical recipe and all scientific limits remain unchanged.



Prelaunch V2 readiness PASS; launched controller56484, worker68556. Latest startup



observation at72.859s: C0 epoch2/20,324 optimizer updates completed, no stderr;



both processes alive. This passes the V1 failure count but does not prove completion. E NOT_STARTED and



will follow successful T automatically. This is a startup snapshot, not completion.



Actual V2 progress and terminal files override this snapshot. Do not start a duplicate



process or rerun P. Status: `scripts/show_frontend_task_knowledge_transfer_v2.ps1`;



live human view: `runs/frontend_task_knowledge_transfer_t_v2_20260911/status.html`.



NEXT: persistent local supervisor completes T→E; inspect sealed completion/STOP.



No LLM heartbeat or further T-to-E permission request is needed.







### Historical 2026-09-11: P COMPLETE / T V1 ENGINEERING STOP / V2 fix sealed







The authorized T V1 attempt stopped after39.313s, C0 epoch1 with174 completed



optimizer steps; no final candidate, no E, zero retry. Controller37280 and worker41868



both exited. STOP seal verified; T SHA256SUMS SHA



`e54daa468f3bc24a8186969f6cd373e50cf20067e085d146074f3c3431606195`.



Failure: WinError5 replacing progress.json.tmp -> progress.json in Budget.check.



This is progress I/O failure, not a model-capability verdict or a numerical-loss failure.



P remains COMPLETE and its teacher cache valid. Do not rerun P or restart frozen T V1.







A generated held-reader test reproduces the exact WinError5 with standard Python



read handles. The sealed V2 fix uses an append-only progress.jsonl journal and reads



the last complete record; no I/O retry or optimization retry added. Generated tests



PASS 57/57, including concurrent readers and an isolated Windows Job supervisor.



V1 code, manifests and failed attempt remain frozen. V2 uses separate T/E paths,



the exact sealed P cache, unchanged numerical code and a NEW explicit execution token.



Current real execution authorization is consumed by STOP; no V2 real attempt authorized.



Read `frontend_task_knowledge_transfer_t_v1_stop_and_io_fix_v2_20260911.md` and sidecar.



V2 implementation SHA256SUMS SHA:



`5490d9de933ffebe2d398501f1b3d64c61c915f91beea19d7777c1fda92bd895`.



Sealed readiness and PowerShell syntax PASS; V2 T/E both NOT_STARTED.



NEXT: obtain explicit authorization for one new V2 T→E attempt, reusing P.



No further implementation permission needed. Exception-stop, zero automatic retry.



Status entry: `scripts/show_frontend_task_knowledge_transfer_v2.ps1`.







### Historical 2026-09-11: P completion and observed T V1 startup







Real P completed and sealed in6.109s, verified9379 teacher rows, zero optimizer steps,



zero student forwards, zero raw decode/retry. Teacher s_T0.4098227709378718;



normal/attack eligible contexts2957/3329, unchanged. P SHA256SUMS SHA



`80019634c8b158e901678f55b369476fc488104b4bf1177193750432b83d567d`.



Read `frontend_task_knowledge_transfer_p_result_and_t_start_20260911.md` and sidecar.







Controller37280 automatically entered T, worker41868. At about18:11:23 observed



C0 epoch1/20,75 completed optimizer updates; real training is underway, not complete.



All three fixed endpoints will be sealed before automatic E. Existing P→T→E



authorization covers continuation; do not ask again or start a duplicate process.



Actual live progress/terminal files override this startup snapshot. No LLM heartbeat.



NEXT: let the local supervisor finish T→E; read sealed results on completion/STOP.



Exception-stop, zero retry. P PASS is input readiness, not a scientific capability PASS.







### Historical 2026-09-11: real P-T-E authorization and prelaunch checks







User explicitly answered “动手下一步授权” to the concrete P→T→E execution request.



Read `frontend_task_knowledge_transfer_real_authorization_20260911.md` and sidecar.



One continuous pipeline is authorized:9379-row train-side teacher preparation;



if P verifies, three fixed C0/C1/C2 trajectories; then one fixed endpoint evaluation



per candidate after all three are sealed. No new permission needed between P/T/E.



Exception-stop, zero retry; unchanged recipe, data scope, budgets and science limits.



This authorization supersedes older NOT_AUTHORIZED statements for this recipe only.



Before launch, implementation readiness was PASS and all three stages were NOT_STARTED.



Actual state always comes from `runs/frontend_task_knowledge_transfer_{p,t,e}_v1_20260911/`.







### Historical 2026-09-11: task-knowledge transfer implementation PASS







User authorized the next IMPLEMENTATION step after the completed design.



Read `frontend_task_knowledge_transfer_implementation_v1_20260911.md` and its sidecar.



Independent new code implements the unchanged three-arm recipe;43/43 generated



tests PASS. Exact-runtime sealed implementation readiness and PowerShell syntax PASS.



New metadata code reproduces15073 supervised /9400 guard /9379 teacher targets.



No real model loads, forwards, optimizer steps, teacher numeric extraction or raw decode.



All three real stage directories are absent; status returns P/T/E NOT_STARTED.







Package: `runs/frontend_task_knowledge_transfer_implementation_v1_20260911/`.



SHA256SUMS SHA `5130c6a473cb7251cbe335b14c11d4e39b1b4c6e7251231890707020efeecfad`.



40 code/dependency/script/protocol identities plus runtime pinned. Eight unrelated



tracked hashes, branch and HEAD remain unchanged. Frozen design/recipe unchanged.







NEXT: explicit real P/T/E authorization may cover the complete sequential pipeline:



P prepares9379 teacher contributions only; if verified, T trains C0/C1/C2 once each;



after all final checkpoints are sealed, E evaluates each fixed endpoint once.



Exception-stop, zero automatic retry. No new resource trial, downloads, raw decode,



old experiment rerun or HPC. Existing real authorizations do not cover this new recipe.



Actual teacher UID/missing coverage remains P's gate; synthetic PASS is not capability PASS.







Status command: `scripts/show_frontend_task_knowledge_transfer_v1.ps1`.



Authorized launch script: `scripts/start_frontend_task_knowledge_transfer_v1.ps1`.



Each real stage has status.html/status.md/progress.json, then supervisor_terminal.json



and SHA256SUMS; E also has result.md/comparison.json. Persistent local supervision,



no periodic LLM polling. Old FAILs and development-only limits remain unchanged.







### Historical 2026-09-11: task-knowledge transfer design COMPLETE







Read `frontend_task_knowledge_transfer_design_v1_20260911.md` and its SHA sidecar,



plus `frontend_task_knowledge_transfer_recipe_v1_20260911.json` and its SHA sidecar.



This is a new independent recipe; all prior frozen recipes and scientific FAILs stand.



User authorized careful DESIGN/REVIEW. No implementation or real P/T/E is authorized.







Recommendation: initialize the unified student from sealed A, learn the same15073



lawful A+B targets, protect correct A attack/normal ranking, and transfer old P2's



128D task-contribution features into the GRU through a training-only projection.



Preserving A alone cannot explain recovery of the stronger old P2 attack capability.



Three independent A-initialized arms: C0 ordinary fine-tuning; C1 adds A protection;



C2 adds P2 features. Same labels/order/budget,20epochs x197updates each, seed2705,



lr1e-4, fixed final epoch and logit>=0. No search, report selection or extra resource trial.







Read-only training support is sealed in `runs/frontend_knowledge_transfer_design_v1_20260911/`:



9400 correct A targets,6286 contexts,s_A29.98624610900879,940042 unique guard pairs.



P2 whitelist is9379 current-train A old-correct targets (3357 attack,6022 benign).



The required128D teacher cache DOES NOT exist. Future authorized P must verify all



UID/missing identities and selectively extract only these E3 rows from the mixed



container, then materialize P2 contributions. No E3 rerun or raw packet decoding.







Teacher history includes current-check labels: equal direct student supervision



does not imply equal total exposure; all results remain exposed-development evidence.



Training pairs are cross-source, not verified matched-device behaviors; preservation



does not guarantee unknown OOD. C2-C1 includes auxiliary training/clip effects.



Joint attack/OOD gains must be shown; small loss, restored A alone, or threshold



changes are not a capability breakthrough. New-device commissioning remains later.







NEXT: implementation and synthetic acceptance of this concrete recipe. After that,



request the bounded real P preparation, T three-arm training, E fixed evaluation;



one explicit authorization may cover all three. Current work performed no model



loads/forwards, teacher extraction, optimization, raw decode, HPC or new downloads.







### Historical 2026-09-11 precursor: selective relation preservation / no new run







User asked for a capability breakthrough after the completed A/AB comparison.



Read-only analysis of their ONE sealed prediction table confirms a ranking loss,



not only zero-threshold placement: TCP Scan vs hydraulic AUROC A0.96884 -> AB0.53965;



Telnet vs hydraulic0.94226 ->0.37968. Empirical TPR at FPR<=1% falls78.04 ->2.45%



and62.41 ->0.64%, respectively. AB improves predictive/stream ranking; pooled OOD



TPR at FPR<=1% remains poor in BOTH A31.75% / AB36.55%. These are exposed-development



curve descriptions, not selected operational thresholds or independent evidence.







Read `frontend_joint_capability_breakthrough_review_20260911.md`.



Evidence: `runs/frontend_score_geometry_readonly_20260911/`; diagnostic SHA



`a71ddeb1335466f764144b49b16e70ea3bf7267818c897c7227b9677678e1a84`.



No model inference/train/decode; source identity and mathematical crosschecks PASS.



Same-input A is a witness for useful local separation, not sufficient joint capability.



Outputs do not identify encoder vs head failure, source shortcut or gradient conflict.







NEXT recommendation: specify one candidate initialized from A, learning A+B while



selectively preserving true-label-supported attack/normal relations; compare with



ordinary A-initialized fine-tuning using identical lawful data and update budget.



Do not copy A errors or move exposed report rows into training. Lawful behavioral



contrast support remains to be established. Relationship distillation is existing



literature, not an already-proven innovation. Input enhancement/effective pretraining



remain conditional alternatives, not the immediate default. This is NOT a frozen



recipe or new authorization; all old verdicts, protected data and run bounds stand.







### 2026-09-11 completed result: fixed-A expanded comparison COMPLETE / verified







One authorized A evaluation completed 2026-09-11T13:14:39.965612+08:00 in85.469s (inference28.985s).



All262050 targets /57686 contexts, model load1, unchanged state, zero decoding,



training, AB loads or retries. Supervisor independent verification and full output



SHA verification PASS; controller53528/worker45416 exited. Old source identities



and eight unrelated tracked hashes unchanged.



Read `frontend_a_expanded_eval_real_result_20260911.md` and sidecar.



Run `runs/frontend_a_expanded_eval_v1_20260911/`; SHA256SUMS SHA



`314f49dc0821f6d864f52e4ca1879ff20722a6bce805460eda093eff7eaa88b9`.







OldP2/A/AB attack recall97.3698/84.0533/89.1092%; future96.6786/80.2703/86.1954%.



A->AB improves overall attack and three OOD pools, BUT hydraulic FP7.6->66.5667%,



TCP Scan recall91.0931->80.1541%, Telnet82.1767->60.3671%.



Attack A-correct/AB-wrong13994; A-wrong/AB-correct26333. Both base learning/transfer



shortfall and local B-supervision costs are present in this fixed recipe; do not



blame B for the entire old-to-new aggregate loss or hide local harm with net gains.



Exposed development only; old retention FAIL and commissioning-unproved unchanged.



NEXT: recommend one targeted training intervention addressing lawful coverage and



measured compatibility costs; mechanism changes require targeted literature/history



review. No further real training/scoring/raw decode authorized by this completed run.







### Historical 2026-09-11 A evaluation authorization / startup







User explicitly authorized one fixed-A comparison: “行，动手吧，我授权，我睡午觉去了。希望起来能看到a模型结果好嘛。”



New evaluator9/9 generated tests PASS; sealed full readiness inside unchanged



Windows Job PASS. Started 2026-09-11T13:13:14.496612+08:00, controller53528 / worker45416.



Actual A inference observed progressing. Live state overrides this startup record:



`runs/frontend_a_expanded_eval_v1_20260911/status.md` / progress.json;



final supervisor_terminal.json plus SHA256SUMS; result.md after independent verification.



Protocol: `frontend_a_expanded_eval_execution_20260911.md` and sidecar.



Same262050 targets /57686 contexts; all prepared inputs and AB/P2 predictions reused.



Only fixed A loaded once, no optimizer or raw decoding; no AB re-inference.



Budget30min /8GiB /512MiB output, exception-stop and zero automatic retry.



Existing V1 startup failure and V2 AB result remain sealed unchanged.



NEXT: read verified A/AB joint comparison; no further training or mechanism execution authorized.







### Completed 2026-09-11 V2 expanded AB evaluation







Latest next-action review: `frontend_expanded_result_next_decision_20260911.md`.



Prefer one evaluation of the already sealed A-only candidate on the SAME prepared



262050 inputs before new training. Broad A was not evaluated; A/AB existing paired



training can distinguish base transfer shortfall from additional B-supervision cost.



No raw decoding/retraining; reuse existing AB scores. This proposed A inference is



not yet authorized or executed. Wider lawful training coverage remains a subsequent



candidate, not an already-qualified dataset; do not move report rows into training.







Fixed AB evaluated all262050 targets /40members in4560.719s (~76min), completed



2026-09-11T12:42:39.387872+08:00. Worker exit0, zero retries, unchanged model state, no training.



Supervisor independent result verification PASS;9 key artifact SHAs independently



rechecked at status query. Both controller52948 and worker17496 exited.



Immutable run: `runs/frontend_expanded_eval_v2_20260910/`; SHA256SUMS SHA



`5e35e97dc681c718d4002b9777ecee855e1c66bc402f13ce411858691b44a7bb`.



Read `frontend_expanded_eval_v2_real_result_20260911.md` and sidecar; full result in run/result.md.







Attack recall old97.3698% -> AB89.1092%; future-query96.6786% ->86.1954%.



Old-detected/new-missed20203; recovered43. OOD FP: hydraulic76.3% ->66.5667%,



predictive42.8333% ->1.0778%, street0.0667% ->7.2667%, stream0.3333% ->7.4667%.



Thus broader inheritance and joint attack/OOD goal remain unachieved despite a



strong predictive-normal gain. Historical strict retention FAIL unchanged.



Exposed development only; no new independent, broad-ID or commissioning evidence.



NEXT: first obtain the fixed-A broad comparison described above, then choose the



training intervention. Causes are not established by aggregate results. No automatic



scoring/training/retry or new mechanism execution authorized.







### Historical 2026-09-11 V2 authorization / startup







User replied “授权。” to the explicit request for one repaired V2 real attempt,



with stop-on-error and no automatic retry. Authorization text is persisted in



`runs/frontend_expanded_eval_v2_20260910/attempt.json`.



Started 2026-09-11T11:26:38.668872+08:00; controller52948, worker17496. Startup passed parent readiness;



current progress/terminal must be read for live state, not inferred from this entry.



HEAD remains4b28747b09480471e2bac1beb3a9badf27280efb on codex/exp-mainline;



all eight unrelated tracked hashes unchanged. Sealed code, runtime, input and



candidate identity checks passed. The September10 V1 failed run remains intact.







Live state: `runs/frontend_expanded_eval_v2_20260910/status.md` / `status.html`;



`progress.json` records counters. Use `scripts/show_frontend_expanded_eval_status_v2.ps1`.



Final success requires supervisor_terminal.json plus SHA256SUMS; then result.md



contains the verified comparison. STOP.md is a failure, never model success.



Same262050 targets /40members /two-pass46297382 packet visits, fixed AB candidate,



no fitting, no threshold/seed/frontend change. All inputs prepared before inference.



Eight-hour /8GiB /40GiB envelope; zero automatic retries for this new attempt.



No recurring LLM monitoring. True FINAL/select/viewed restrictions remain unchanged.



NEXT: allow the local supervisor to finish; read attack preservation AND benign-OOD



results together, then judge larger lawful training coverage. Do not launch again.







### Historical 2026-09-10 V1 startup stop and V2 correction







User explicitly confirmed historical report/legacy support_val/sealed_final_*



reuse and corresponding local raw input preparation: “是的，我要外出了，希望回来能看到测试结果。”



The one fixed AB attempt STOPPED after1.062s (worker exit1), before raw decoding or model load.



Controller62120 and worker62196 exited. No scientific predictions were produced.



Root cause confirmed: Git cmd wrapper needs a third process, forbidden by the two-process Job.



V2 directly calls pinned mingw64/bin/git.exe; wrapper failure reproduced, direct HEAD/branch



and invalid-ref checks pass. Complete SEALED V2 readiness inside the same Job PASS;



missing new authorization rejects launch. No real restart. Read



`frontend_expanded_eval_startup_stop_and_fix_v2_20260910.md` and sidecar.



Correction: `runs/frontend_expanded_eval_startup_diagnosis_v2_20260910/`;



startup verification: `runs/frontend_expanded_eval_v2_startup_verification_20260910/`.



Live authoritative state: `runs/frontend_expanded_eval_v1_20260910/progress.json`,



`status.md` / `status.html`; final `supervisor_terminal.json` plus SHA256SUMS.



Do not infer completion from this living entry: inspect persisted terminal state.



Implementation sealed after23/23 synthetic tests and two PowerShell parse checks.



Package: `runs/frontend_expanded_eval_implementation_v1_20260910/`;



SHA256SUMS SHA `9208679615bcd30dbb9f0b43542db00d7b83c7f41adf426bf586ba3d0b1eba46`.



See `frontend_expanded_eval_implementation_and_execution_20260910.md` and sidecar.







Row-level qualification completed:262050 unique targets,244050 attacks/16families,



18000 benign OOD/four pools,40 raw members,23148691 packets per pass/two passes.



Full source archive SHA PASS. AB train/check UID overlaps both0; shared-member



targets3198/63, respectively; not independent confirmation. Existing ID check151



FP0 and train658 FP0 are reused, not rerun. No new training. All40 inputs must be



prepared before one AB load/inference; fixed131D frontend, candidate and logit>=0.



Budget8h/8GiB aggregate/40GiB output, zero automatic retries. Persistent local



supervision replaces token-heavy model polling; no recurring Codex automation.



Historical retention FAIL remains; this attempt supplies no new scientific result.



True FINAL cooler-motor/seeds37/47, other select/viewed, downloads and HPC closed.



NEXT: obtain explicit authorization for one V2 real attempt, then use



`scripts/start_frontend_expanded_eval_local_v2.ps1` with that authorization text.



Same sealed inputs/runner/model/metrics and all bounds; no requalification or historical rerun.



V2 output namespace does not exist. Zero-retry rule still applies to the new attempt.







### Earlier 2026-09-10 pre-open direction (authorization question now resolved)







The user confirmed the overall sequence and asked to act on the next step.



Current task: evaluate the existing F4 + sealed AB candidate more broadly before



larger training or new learning mechanisms. This overrides the earlier order



that prioritized crossed-environment mechanism development. See



`frontend_expanded_eval_scope_and_preparation_20260910.md`.



Pre-open scope work completed in `runs/frontend_expanded_eval_scope_v1_20260910/`:



AB checkpoint SHA verified; existing ID outcomes reused (train658 FP0, check151



FP0), not new independent tests. Proposed broad population is the disclosed



CKDA report: attack244050 + benign OOD18000. Counts are contractual until a



new row census, not a claim that report data were opened this turn.



At that earlier pre-open stage, specific reuse of report/support_val/legacy sealed_final_attack and street



sealed_final_ood has not been clarified against the user's original access



restriction. No historical report payload opened; no model load, forward,



raw decoding or optimizer step. Current 131D inputs cover18266 targets;



the old768D report embeddings are incompatible with the current GRU input.



NEXT: clarify the precise disclosed-report reuse scope, then qualify the



target/member inputs and implement one fixed AB development reevaluation.



True FINAL cooler-motor/seeds37/47, downloads, HPC and retraining remain closed.



Do not demand another permission for already-authorized routine implementation.







### 2026-09-10 paper objective reaffirmed by the user







The scientific goal remains low benign-OOD false alarms WITH preserved attack



detection when ID, benign OOD and attacks coexist. Few-shot learning and OOD



supervision are method routes; commissioning with benign history is a narrower



scenario. Neither unseen-OOD generalization nor safe commissioning is solved.



Frontend coverage / inheritance are enabling subtasks, not the paper endpoint.



A/B is input availability, not ID/OOD. Read the objective/evidence section in



`frontend_post_paired_next_step_and_head_review_20260910.md` before proposing work.



This clarification changes no frozen rule, historical outcome or authorization.







2026-09-10 project synthesis: read `project_state_and_research_priority_20260910.md`



for the integrated scientific state before choosing work. Late E3/P2 improved



stream OOD to 0.3333% with attack/future-query recall 97.3698%/96.6786%; remaining



hydraulic/predictive failures, not early stream ~100%, describe that old system.



V3 supplies broader input/learning evidence on a separate small development pool.



Primary investment: transferable benign/attack representation on the unified input;



paired commissioning data preparation is a supporting lane. Existing Data-F0



already investigated CIC IoT 2022 and stopped PENDING member inventory after a



future download (that audit downloaded zero). Do not restart generic data research



or assume paired data are ready. No new mechanism is selected or execution granted.







2026-09-10 method review CORRECTED after the user's model-capability concern:



read the top correction in `openworld_method_direction_review_20260910.md`.



Priority for another normal-history/constraint branch is WITHDRAWN: CKBB already



tested E/R/H residual and attention combinations without resolving hard stream



OOD. The previous review omitted that direct overlap while emphasizing CKDE-R's



non-execution. Do not assume the current representation is sufficient. NEXT



DESIGN should distinguish observable input, representation generalization and



learning/coverage limitations through a controlled capability comparison, not



another small-pool fitting exercise. Larger model success is also unproved;



old pretrained netFound still had hard-OOD failures. Normal-history conditioning



remains a candidate, not the selected route. Verified commissioning pairs remain



missing from the current evidence. No new experiment, data collection, protected



access, model/threshold change or HPC authorized.







### 2026-09-10 V3 paired experiment CLOSED: execution PASS; retention FAIL; B normal gain PASS







One authorized real preparation and conditional paired training/check completed.



Preparation PASS: 18,266 prefixes, 12,889 contexts, 110,372,216 bytes, 10.140 s.



A/AB each completed 40 epochs and 7,880 updates from identical fresh initial state.



Both candidates sealed before one postfit and common check per arm. No retry.



Training/check finished about 12:20:05 Asia/Shanghai; elapsed 4,971.36 s, worker



exit 0, aggregate peak upper bound 1,084,973,056 bytes. Both processes exited.



Supervisor seal and independent artifact/count/gate verification PASS.







Common check: A attacks 2/825 misses in BOTH arms (same two UIDs, scanning and



password source); A normal 0/1,302 false alarms in both. Strict retention FAIL.



A-to-AB new A check errors=0. B normal false alarms 538/1,066 -> 0/1,066,



error contexts 503/910 -> 0/910, all source/device cells nonregressing: PASS.



B attack check=0: NOT_ESTABLISHED. Postfit A attack misses A=2/3357, AB=5/3357;



training-fit results do not override common check or prove unseen capability.



Single-seed EXPOSED_DEVELOPMENT only; no independent/OOD/device/deployment claim.







Read `frontend_paired_train_v3_real_result_20260910.md` and SHA sidecar.



Immutable run: `runs/frontend_paired_train_v3_20260910/`; SHA256SUMS digest:



`0f55d36928f813dcd034d44a19ce2ab3d57e5e7b8c9f6ecd7354b0cfc835869a`.



Read-only verification: `runs/frontend_paired_train_result_verification_v3_20260910/`.



Code/runtime/metadata pins, historical manifest pins, branch/HEAD and eight



unrelated tracked hashes verified unchanged. Training outputs were not modified.







NEXT: design a fixed-candidate evaluation of benign-OOD false alarms AND attack



retention, mapping exposure/isolation and runnable inputs from allowed manifests.



Bounded existing-output error diagnosis is a supporting item, not the endpoint.



Read `frontend_post_paired_next_step_and_head_review_20260910.md`. Deliver an



explicit fixed-candidate evaluation proposal; current MLP head has 8,321 parameters



within the fully trained 91,265-parameter GRU model. No demonstrated head-capacity



bottleneck yet; architecture complexity alone is not a paper contribution.



Strict retention FAIL remains; this does not unlock confirmation or protected roles.



No automatic retraining, threshold repair,



extra inference, K, HPC, raw replay or device experiment. The user's low-token



preference persists; heartbeat `paper04` DELETED at the user's request after



closure (previously paused). No active polling or scheduled follow-up remains.







2026-09-10 result interpretation / next-step advice (no new experiment): the



2/825 deficit is 0.2424 percentage points on this old-correct development pool,



not a full-system recall estimate. Existing sealed tables show one miss among



400 ToN scan targets and one among 398 ToN brute-force targets. Both misses are



at event index 1 (two-event prefixes), both arms have strongly negative logits;



this observation is a diagnostic lead, not a proven information deficit. The



remaining 27 check attacks cover three flood families; Mirai C&C residual errors



are in postfit, with no same-family common check evidence here. Avoid equating



the small pooled deficit with full attack-family inheritance.



Recommended next work is one bounded existing-output/metadata diagnosis of the



two check contexts and one residual Mirai fit context, using full relevant



family/prefix denominators rather than optimizing those UIDs. End with a route



decision: a mechanism-supported repair proposal or an independent-confirmation



proposal for this fixed candidate with explicit residual risk. Do not enter an



open-ended zero-error patch loop. Consult relevant literature before any new



scientific method design; no new training or data access is authorized by advice.







2026-09-10 dataset-scope clarification: 18,266 is the complete LAWFUL FRONTEND



DEVELOPMENT pool for this bounded comparison, NOT all paper04 data or the full



ID/OOD/attack benchmark. It combines former F5 train 8,660 + internal_val 5,206



+ F1 outer validation 4,400; the new split is 15,073 train / 3,193 check targets.



The broader historical data-contract records include the 1M cache and a separate



683,420-row certified attack subset (93 complete chunks); these totals include



multiple roles, are not test denominators, and are not additive or automatically



qualified for the new F4 model. Their current runnable scope has not been audited



here. A/B denotes incumbent input availability; it does NOT map to ID/OOD.



B-normal gain cannot establish hard-OOD performance. Next evaluation planning



must map the larger ID, hard-OOD and attack roles, coverage and input lineage



from allowed manifests before any separately authorized scoring/materialization.



This clarification used existing documentation only, no protected data access.



All entries below are historical unless explicitly reaffirmed here.







### 2026-09-10 V3 entry review accepted; real preparation + conditional training authorized (historical; launched)







User explicitly clarified authorization includes real preparation and direct frozen



A/AB training+terminal checks on success; stop on failure, zero retry. Do not ask



again between successful stages. V3 review completed: complete generated worker /



production validator / Windows supervisor / seal chain, accurate failure access



ledger, plan-bound counts and arm-specific supervision coverage. 76/76 generated



checks and 2/2 script parses PASS. No scientific rule or model/optimizer change.



Plan, bound recipe and initial weights remain byte-identical. Real preparation



readiness PASS and V3 namespaces absent before launch.







Read `frontend_paired_train_v3_entry_review_and_acceptance_20260910.md` and sidecar.



Package `runs/frontend_paired_train_implementation_v3_20260910/`, seal:



`b35fa10b99b87cf6cde277a5d29f0be432553c8c393945ec1aaa1677866cbf1b`.



Review proof `runs/frontend_paired_train_entry_verification_v3_20260910/`.



Use only V3 start/status scripts. Execute once with unchanged stage caps; verify



preparation terminal seal before launching training. No K/HPC/device/raw replay.



Earlier preparation V1 failure remains CLOSED. V2 was never run on real data.







### 2026-09-10 real preparation V1 CLOSED; F4 prefix compatibility fixed in V2







Authorized preparation stopped after 4.625 s at PREFIX_IDENTITY; training did not



start because its prerequisite did not pass. Both source feature hashes passed;



first 90,128-byte context was read, then first target hash failed; new output array



is empty. V1 hashed bare feature bytes, omitting the original F4_INPUT_V1 null



marker and two LE uint32 shape fields. This is an implementation compatibility



error, not evidence of feature damage or model failure. Failure seal:



`c6a866db132e7ec1d78eae130e9b16b3007a526576f25a8ac8cc8df32d955c00`.







Read `frontend_paired_preparation_v1_stop_and_prefix_fix_v2_20260910.md` and sidecar.



V2 restores the exact old hash envelope. Eight direct pinned-F4 oracle tests pass,



including every prefix length 1..256, plus 47 rerun model/IO/gate tests and 10



supervisor tests: 65/65, script parses 2/2, read-only preparation readiness PASS.



The former tests shared the new code's bare-byte assumption; the independent



historical-format reference now closes that test gap. No real retry occurred.







V2 implementation `runs/frontend_paired_train_implementation_v2_20260910/`, seal:



`822ff45825ef1cec26aed56b16b1b67e6c2ca1e5f9c0df175a6efdf2ac08be16`.



Proof `runs/frontend_paired_train_prefix_fix_v2_20260910/`. V1 remains immutable.



Plan, bound recipe and initial weights byte-identical; only namespace and F4



prefix hash framing changed. Training sources, model, seed, loss and gates unchanged.







NEXT: renewed explicit authorization for one V2 preparation and conditional direct



paired training/check on success. Previous preparation authorization was consumed



under zero retry; training authorization was conditional and never exercised.



Both V2 real namespaces absent. No promised finish time before real training speed



is observed. Same preparation 1800 s/8 GiB/256 MiB and training 14400 s/8 GiB/512 MiB



caps; stop on failure. V2 start/status scripts end `_v2.ps1`. No old attempt restart,



raw replay, K, HPC, device experiment or scientific rule change.







### 2026-09-10 real preparation AND conditional paired training authorized (historical; preparation stopped)







Following the explicit consolidated scope proposed in this conversation, the



user authorized real feature preparation and, on successful sealed preparation,



direct execution of the frozen A/AB training and terminal checks. No intermediate



permission request is needed on a clean pass. Stop on actual failure; no retry,



rule changes, K, HPC or new-device activity. Preparation readiness passed and its



namespace was absent before launch. Frozen stage limits remain unchanged.



Wait for verified final receipts and report actual results, not training loss alone.







### 2026-09-10 paired training implementation accepted; prepare/train NOT_STARTED







User authorized IMPLEMENTATION only. Fresh two-arm training executor, separate



feature preparation gate, terminal evaluation, resource supervisor and visible



status scripts are implemented. 57/57 generated checks and 2/2 script parses PASS;



read-only preparation readiness PASS. No real feature decoded or optimizer run.



Read `frontend_paired_train_implementation_and_synthetic_verification_20260910.md`



and sidecar. Package `runs/frontend_paired_train_implementation_v1_20260910/`, seal:



`262f0d76060f3b77c6362b6083862c76ded0b01f7d4c2ebb674f904572e632dd`.



Final proof: `runs/frontend_paired_train_implementation_final_v1_20260910/`.







Frozen recipe and qualified membership unchanged. Fresh 91,265-parameter initial



state sealed (no historical model); exact seed2705 default state SHA:



`627f1fc016f44094b0510130d6e28a46b86c72f5df4e4bb6ee4947a95a4b593b`.



Both complete models start equal; A/AB each 40 epochs/7880 updates. Both terminal



candidates sealed before one post-fit and common check pass per arm. No selection,



extra seed, threshold change or automatic retry. Detailed tables and compact



terminal receipt are separate. Single-worker Windows Job uses validated V3 IO fix.







All 18,266 lawful UIDs joined to inherited feature-prefix hashes and categorical



old reference metadata without opening real numeric arrays. Sources total



110,372,216 bytes. Exact train+postfit/check events 12,365,910; padded slots



113,159,662. Plan matches the previous sealed training schedule. B attack check



denominator remains zero; no B novel-attack or device claim.







NEXT: explicitly authorize ONE real feature preparation, separate from training:



identity hash two existing F4/outer arrays, decode qualified context ranges, verify



18,266 prefix hashes, seal 110,372,216-byte new view; 1800 s / aggregate 8 GiB /



256 MiB new outputs / one worker / zero retries. No model forwards or raw packets.



After valid preparation, separately authorize paired training+terminal checks



under original 14400 s / 8 GiB / 512 MiB envelope. Implementation authorization



does not authorize either real stage. No F4/metadata repeat, pilot, K, HPC or devices.



Start: `scripts/start_frontend_paired_train_local.ps1 -Stage prepare -AuthorizeFeaturePreparation`.



Status: `scripts/show_frontend_paired_train_status.ps1 -Stage prepare` (or train).



Both real namespaces are absent. Historical failures/results and unrelated edits



are preserved; scientific capability still NOT_TESTED for this paired experiment.







### 2026-09-10 V3 real metadata CLOSED: MEMBERSHIP_QUALIFIED; training NOT_STARTED







The one authorized V3 pass completed in 243.390 s, sealed and verified. All



6,737 B descriptors / 22 members / 8,207,642 packets obtained; 2 container hashes



cover 25,002,052,527 bytes. No feature/model/teacher/optimizer access or retries.



Worker/controller exited. Real seal:



`d9be8cfc181d25cd5ad64e8a66fd4a7491f2af31af4ae60d21c2a8e7a8e8d152`.



Read `frontend_paired_metadata_v3_real_result_20260910.md` and SHA sidecar.







18,266 targets / 12,889 contexts / 8,476 dependency components split into 15,073



train and 3,193 check targets; 6,000 recorded edges, zero cross-role dependencies.



Required coverage gaps=[]; supervisor recomputed membership/coverage/schedule.



Train/check counts: A0 6045/1302, A1 3357/825, B0 5600/1066, B1 71/0.



Important: 16/53 coverage rows remain train-only. NO B attack check examples;



do not claim B novel-attack generalization or complete source-level coverage.



This is exposed development, not independent confirmation or device independence.







Exact sealed schedule: A/B train contexts 6286/4297, 197 updates/epoch, 40 epochs,



7880 updates/arm; 12,017,520 train events and 111,883,555 padded slots across arms.



No model initialized or training executed. Metadata qualification blocker resolved.



NEXT is paired training executor implementation and generated verification using



the frozen recipe and sealed membership, with observable progress/terminal status.



Actual feature preparation and training need their explicit bounded authorization;



do not rerun packet acquisition, F4 or resource pilot. No K/HPC/new-device activity.



V1/V2 failures and all historical scientific results stay unchanged. Proof:



`runs/frontend_paired_metadata_v3_result_verification_20260910/`.







### 2026-09-10 ONE V3 real B metadata pass authorized (historical; now complete)







The user explicitly authorized the next V3 metadata acquisition and membership



seal. Readiness PASS; real namespace absent before launch. Use the frozen V3



namespace dated 20260909 without renaming the sealed implementation. One pass,



unchanged scope/caps, no automatic retry or training. Verify final supervisor seal.







### 2026-09-09 V2 CLOSED before content read; V3 IO repair accepted, NOT_STARTED







The user-authorized V2 real attempt ended INPUT_OR_EXECUTION_STOP after 1.046 s.



Worker failed to replace progress.json: PermissionError WinError 5. It had stat'ed



the first container size, but had not begun container content hashing or packet



decoding; every access counter is zero. Worker exit 0 means a failure receipt was



written, not success. Both worker/controller exited; final seal verified:



`9cf72f9ecae6701b68a1dd290b83a1c543a9659a2153f85f901ec5d4f1b84b00`.



This is a writer-side failure distinct from V1 monitor stat racing. Actual lock



holder is unknown; generated Windows reader handles reproduce the failure class.







Read `frontend_paired_metadata_v2_real_stop_and_io_fix_20260909.md` and sidecar.



New V3 writer repeats ONLY atomic rename on Windows 5/32/33, at most 21 calls and



20 x 25 ms waits; persistent denial still stops. No repeated data read, decoder,



worker or scientific experiment. Runner differs only by isolated writer injection;



all parsing, grouping, caps and recipe remain unchanged. 23/23 generated tests,



2/2 script parses and read-only readiness PASS. V1/V2 evidence preserved.



V3 package: `runs/frontend_paired_metadata_implementation_v3_20260909/`, seal:



`8b4e3acc1c67eac2b1b18bcf93f2289040727e5168b2eef0945bc22c1625f269`.



Evidence: `runs/frontend_paired_metadata_io_fix_v3_20260909/`.







NEXT: separately authorize ONE V3 real metadata acquisition and membership seal,



same 6,737 targets / 22 members / 8,207,642 packets / 3,600 s / aggregate 8 GiB /



64 MiB / zero experiment retries, including opaque container identity hashing.



V2 authorization is spent; V3 NOT_STARTED. No automatic third attempt, training,



K, HPC or new-device execution. Membership and broader inheritance remain unproved.



Start/status scripts now end `_v3.ps1`. Old frozen versions must not be relaunched.



All entries below are historical unless explicitly reaffirmed here.







### 2026-09-09 ONE V2 real B metadata pass authorized (historical; now CLOSED)







After reviewing the sealed V2 repair, the user explicitly authorized one new



real B metadata acquisition and membership seal. Readiness PASS; V2 namespace



absent before launch. Execute once under the unchanged envelope below, including



opaque container identity hashing. No automatic retry, training, K or HPC.



Wait for supervisor terminal seal and record qualification separately from



scientific capability. The V1 failure remains CLOSED and unchanged.







### 2026-09-09 B metadata attempt CLOSED; monitor V2 accepted, NOT_STARTED







The authorized V1 real pass ended INPUT_OR_EXECUTION_STOP after 217.234 seconds.



An atomic progress-file replacement raced with the monitor's is_file/stat calls;



the monitor raised FileNotFoundError and killed its Job. This is an engineering



fault, not a data/model capability result. Last saved progress: 7,165,077 packets,



6,732/6,737 targets, 21/22 members; these are last observations, not exact final



counts. Descriptors were still in memory: no membership was persisted and no



partial resume is valid. The remaining five targets are NOT five attack misses.



V1 is sealed and preserved; no real retry or training has occurred.







Read `frontend_paired_metadata_real_stop_and_monitor_fix_20260909.md` and sidecar.



The separate V2 monitor now takes one stat per entry, resamples the whole directory



at most three times on a vanished temporary, and fails closed for persistent



disappearance/instability. Final snapshot errors also produce a sealed stop.



22/22 generated regressions and 2/2 PowerShell parses PASS; read-only readiness



PASS and V2 status NOT_STARTED. Original 45-check evidence is preserved, not



claimed as a fresh 45-test V2 run. Parser, grouping, recipe and caps are unchanged.







V2 implementation: `runs/frontend_paired_metadata_implementation_v2_20260909/`.



SHA256SUMS: `eff56191dcbfec807f105b57c1275142add971170a58eb7dbfa51e3dd37cb0fe`.



Repair evidence: `runs/frontend_paired_metadata_monitor_fix_v2_20260909/`.



V1 real/implementation and recipe seals, HEAD/branch and eight unrelated tracked



file hashes were verified unchanged. NEXT: separately authorize ONE V2 real B



metadata pass from the beginning, including opaque container identity hashing,



under the same 6,737-target / 22-member / 8,207,642-packet / 3,600-second /



aggregate 8 GiB / 64 MiB / zero-retry envelope. The previous authorization is spent.



Entry: `scripts/start_frontend_paired_metadata_local_v2.ps1 -AuthorizeBMetadataRead`.



Visible status: `scripts/show_frontend_paired_metadata_status_v2.ps1` (`-Once`).



No training, feature reconstruction, K, new-device or HPC authorization.



Membership qualification and broader inheritance remain unproved.



All earlier September 9 entries below describe historical states.







### 2026-09-09 ONE real B metadata pass authorized (historical; attempt now CLOSED)







The user explicitly authorized the next real B metadata acquisition and membership



seal after implementation acceptance. Readiness passed; the real namespace was



absent. Execute once under the unchanged 6,737-target / 22-member / 8,207,642-packet



scope, including the declared opaque container identity hashing. No training,



feature reconstruction, additional pass, retry, K, new-device or HPC is authorized.



Wait for and verify the supervisor's terminal seal before recording completion.







### 2026-09-09 B metadata implementation accepted; real pass NOT_STARTED







The user explicitly authorized implementation. The B metadata extractor,



dependency-component split, coverage/schedule sealing, supervisor and visible



status scripts are implemented and generated verification has passed: 45/45



synthetic checks and 2/2 PowerShell parser checks. Read



`frontend_paired_metadata_implementation_and_synthetic_verification_20260909.md`



and its SHA sidecar. Acceptance package:



`runs/frontend_paired_metadata_implementation_v1_20260909/`.







No project packet, feature or model was decoded; no real split was generated.



Tests used generated headers/PCAP/ZIP and disposable processes only. A pure-



function AST projection reuses pinned F0/CKBU/session/decoder semantics without



importing model runners. B route groups, genuine A sessions and conservative



H1 compatibility bridges are united before the unchanged frozen split rule.



Outputs distinguish qualified membership from completed metadata with inadequate



coverage, and neither is a model capability result or training authorization.



The previous recipe and its 14-member freeze seal remain byte-identical.







Real namespace `runs/frontend_paired_metadata_v1_20260909/` remains absent.



NEXT: explicit authorization for ONE bounded B header metadata acquisition and



membership seal: 6,737 B targets / 22 members / 8,207,642 packets maximum,



3,600 seconds, aggregate 8 GiB, 64 MiB output, no retry. Raw whole-container



hashing and selected ZIP-member decoding occur only inside that authorized run.



The read-only readiness check verifies package/metadata/runtime, not raw sources.



No additional architecture/loss design or resource pilot is required for this step.







User-visible entry: `scripts/show_frontend_paired_metadata_status.ps1` (`-Once`



optional) reports packets, B targets, members, elapsed time and verified terminal



status. Startup script requires `-AuthorizeBMetadataRead`, not used in this stage.



Real training executor implementation and actual two-arm training remain separate.



F4 PASS, F5 failure, closed N1/N2/N3/outer and broader_inheritance=NOT_PROVED



remain unchanged; no K, deployment, new-device or HPC authorization.







### 2026-09-09 Paired recipe frozen; metadata join PASS; split NOT_QUALIFIED







The user authorized completion of the paired design's lawful train/check



qualification and one exact numerical recipe. This work is complete to the



metadata-only boundary: RECIPE_FROZEN / SPLIT_NOT_QUALIFIED / NOT_EXECUTABLE.



Read `frontend_paired_learning_recipe_and_metadata_qualification_20260909.md`



and its SHA256 sidecar. Evidence: `runs/frontend_paired_learning_freeze_v1_20260909/`.







All 18,266 lawful targets / 12,889 contexts join exactly across existing metadata.



A has 7,001 genuine old sessions; 35 span multiple new contexts (maximum 189).



All 6,737 B session IDs are per-target missingness placeholders, including eight



for timestamp regression; they cannot establish session independence. The 3,157



ToN B targets also have producer-filled -1 endpoint IDs. No new train/check



membership has been qualified; all new roles remain explicitly UNASSIGNED.



No raw packet, feature/signature or model decoding, forward or optimizer occurred.



Historical exclusions and sealed-role boundaries are unchanged.







The recipe is fixed: fresh common initialization, F4 131D + complete 91,265-



parameter GRU/classifier, ordinary BCE; L_A versus L_A + L_B, stable A weight,



seed 2705, AdamW lr .001 / wd .0001, fixed 40 epochs per arm, terminal candidates



only, common check after both are sealed. Metadata-based dependency-component



split algorithm, exact comparison gates and 4-hour / 8-GiB training envelope



are written. This is a partial freeze: missing memberships, input qualification



and executable acceptance prevent any real launch. No result or optimality claim.







NEXT: a bounded metadata-only implementation/acquisition package for the missing



B route/session bridge, followed by the already specified grouping and membership



seal. Exact proposed scope: 6,737 B targets, 22 members, one header-only pass



through at most 8,207,642 packets. Reuse A's genuine session bridge; no replay of



the two A-only ToN members. Use the pinned context-allocation structure to prove



prefix separation where valid; do not require whole-pool replay merely because



raw prefix-start positions are absent. Proposal and member/cutoff identities are



reviewable in the evidence directory. Raw decoding is NOT authorized by this



completed metadata/design stage; the two-arm real training also remains separate.







This supersedes the draft's unfinished-recipe action, not its scientific limits.



All data are exposed development; no independent confirmation reserve is qualified.



F4 remains PASS; F5 NO_ELIGIBLE_CHECKPOINT; N1/N2/N3 and outer remain CLOSED;



broader_inheritance=NOT_PROVED; K/deployment/new-device/HPC remain unauthorized.







### 2026-09-09 Objective-aligned paired learning recommended; draft only







The user requested an independent, concrete next-step judgment. The route review



and public literature lookup are complete. Read



`frontend_objective_aligned_paired_learning_design_20260909.md`.



Recommendation: ONE prospectively defined two-arm ordinary-supervision comparison



on the shared F4/GRU pipeline, A target supervision versus A+B target supervision,



with fresh common initialization, matched A exposure and paired evaluation against



the fixed old reference. This is a diagnostic baseline proposal, not an endorsed



final architecture or a claim that supervised learning guarantees zero regression.



No teacher-margin objective, auxiliary objective or further last-layer LP is



proposed for this baseline. Any later scientific protocol change is prospective.







NEXT: complete the new lawful train/check membership and dependency/exposure account,



then freeze one exact supervised recipe, candidate rule and resource envelope before



implementation. Reuse the completed N0/F4 work. The 18,266-row pool is exposed



development; there is no qualified independent same-behavior confirmation reserve.



If its known metadata cannot support an interpretable split, identify the exact



gap before training; do not invent session independence or open sealed roles.



A-only denotes target supervision and must disclose unavoidable B-prefix exposure.



Existing F5/N3 weights cannot initialize a no-B control.







This supersedes the open-ended route-review action below. The design is NOT_FROZEN



and NOT_EXECUTABLE; no new training, reallocation, model/data decode, HPC, locked



evaluation or new-device execution has occurred or is authorized. F5 remains



NO_ELIGIBLE_CHECKPOINT; N1/N2/N3 and outer are CLOSED with unchanged outcomes.







### 2026-09-09 Research ownership and next-decision clarification







Persistent user instruction: act as an independent research collaborator. Start



from project objectives and evidence; challenge inherited assumptions regardless



of which model proposed them, and challenge the user's technical suggestions



when warranted. Explain and own the recommendation instead of leaving technical



route selection to the user. Prior implementation effort is not evidence that



a route is sound. Literature-first review remains required for difficult design.







NEXT DECISION: reassess whether the current representation, learning coverage and



evaluation question serve old-attack retention plus useful A+B support. Compare



focused diagnosis and fuller lawful A+B training on their expected information



and cost. Neither repeatedly fitting observed misses nor scaling training is the



default accepted answer. State the evidence, competing explanations, recommended



next experiment and stopping conditions. This supersedes the narrow default of



diagnosing only the five misses; their result remains valid failure evidence.



Historical frozen outcomes stay unchanged. Future proposals may challenge old



design choices prospectively; no new training/data-role change, locked access,



HPC or other experiment is authorized by this discussion.







### 2026-09-09 Real outer comparison complete: five attack misses, all benign correct







OUTER_COMPARISON_COMPLETE; final supervisor seal verified. Scientific result:



A_retention=REGRESSION_ON_THIS_POOL;



B_utility=POSITIVE_IN_BOTH_REPRESENTED_GROUPS. This attempt is CLOSED.







Read frontend_inheritance_outer_real_result_20260909.md and its .sha256 sidecar.



All 4,400 targets / 3,582 contexts evaluated in one pass: 1,995/2,000 old-detected



A attacks retained (five misses); 1,174/1,174 protected A benign correct; both



old-wrong A benign corrected; 1,224/1,224 B benign correct. B complete-normal



context counts: 844/844 combined-cycle and 50/50 domotic-monitor (894/894 total).



All 2,400 benign targets correct. B benefit cannot offset the five attack misses.







All five failures are H1 reconnaissance targets from normal_scanning1.pcap,



in five distinct contexts. Four overlap the historical F1 five-error UID set;



one historical miss is corrected and one different target is now missed.



The two five-error sets are NOT identical. This is an identity comparison,



not an established causal mechanism or grounds for automatic refitting.







One worker, zero retries; elapsed 77.266 s; peak aggregate job memory 772,657,152



bytes. Exactly 628,903 decoded packets, 5,164 prepared/forward events, 112 batches,



4,400 targets and 18,808 padded slots. Input L0 mismatch count is zero.



N3 candidate state remained unchanged before/after the sole forward.



No training, LP, teacher forward, calibration or historical model replay.



Controller and worker exited. All 14 result/control manifest members verify.







Real namespace: runs/frontend_inheritance_outer_comparison_v1_20260909/.



SHA256SUMS SHA256:



5801d8d3bb364489f10bda363cb13919f37004aaab8cc9516593fdd904876666.



Supervisor terminal SHA256:



4cc8ce401fb3018f2530c48976d854e1b090d846c5da4fd8f05e3e3f864fe878.



Prepared features SHA256:



18c2533d2a91839cb17dbc35579fb96cb3050449d5badeeff2ac47d98158bd91.







NEXT: explain this bounded result plainly; propose targeted diagnostic/design



for the five observed attack misses before any new intervention. No automatic



fit of their labels, threshold adjustment, new training, replay, new-device



experiment or locked evaluation access is authorized. Preserve the entire



attempt and successful N3 finite-set witness. Literature-first research



preference persists. These exposed-development results do not prove causal



B-training contribution, independent generalization or deployment readiness.







broader_inheritance=NOT_PROVED; F5 remains NO_ELIGIBLE_CHECKPOINT; K/deployment/



new-device execution unauthorized. N1/N2/N3 and outer comparison are CLOSED.



26 source/script pins, eight runtime pins, seven documents and eight unrelated



modified-file starting hashes verified after execution. HEAD/branch unchanged.







### 2026-09-09 ONE real outer comparison authorized







The user explicitly authorized the next real step after implementation acceptance:



ONE bounded input preparation plus ONE fixed-N3 whole-pool comparison, including



the declared opaque container hashing, selected raw-member decoding and restricted



terminal-checkpoint container projection. The accepted contract, code, model,



threshold and resource limits remain unchanged. Readiness passes and the real



namespace was absent before dispatch. No retry or historical rerun is authorized.



Record a scientific result only after the supervisor's final seal is verified.



K, deployment, new training and new-device experiments remain unauthorized.







### 2026-09-09 Outer comparison implementation accepted; real attempt NOT_STARTED







The user explicitly authorized implementation of the next step. Implementation,



scoped metadata qualification and generated verification are complete:



OUTER_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS, 46/46 generated tests, 2/2



PowerShell parser checks. Read frontend_inheritance_outer_execution_contract_20260909.md



and frontend_inheritance_outer_implementation_and_synthetic_verification_20260909.md,



with their .sha256 sidecars. The previous design/scientific rules remain unchanged.







Accepted implementation: runs/frontend_inheritance_outer_implementation_v1_20260909/.



Synthetic acceptance SHA256:



c6eeab52f4222ca5e83720da520e76fe63da74cb3dec5d990af69fd7fc4d0050.



Implementation SHA256SUMS SHA256:



5a65002580de5969e469c07a76386740effd1cb16b1d678626759424e64a11bb.



26 source/script and eight runtime-file identities are pinned; all historical



N3 and frozen mapping dependencies checked unchanged.







Metadata: runs/frontend_inheritance_outer_metadata_v1_20260909/.



Qualified metadata SHA256:



12e0846eb4cd54093d077ea82a8fd5bafb9e9f980cb45cf460d30e3db05b53e4.



Exact 4,400 targets / 3,582 contexts / five members and categorical old-teacher



joins pass. Zero overlap with the F5 parent target/context/member/source sets.



F1 validation/frontend-design exposure and unknown old-session/pretraining/



physical-device independence remain explicit. No signatures/model tensors or



raw project packets were decoded in this implementation stage.







NEXT GATE: explicit authorization for ONE bounded real input preparation plus



ONE fixed-N3 whole-pool comparison, including the restricted terminal checkpoint



container projection. Readiness passes; the real namespace is absent and the



status viewer reports NOT_STARTED. No additional method design or resource



pilot is required. Future input hashes are sealed during preparation before



model load; no new training, optimizer, LP, teacher forward or retry is involved.







Real envelope: 628,903 decoded packets; 5,164 retained/forward events;



112 batches / 3,582 contexts / 4,400 targets / 18,808 padded slots.



Opaque identity hashes cover two local source containers totaling 24,442,596,676



bytes (including the whole ZIP); only five selected members are decoded.



Ceilings: 1,800 seconds, aggregate 8 GiB for worker plus one decoder, 100 MiB output.



Real namespace: runs/frontend_inheritance_outer_comparison_v1_20260909/.



Do not create/restart it without the separately authorized real attempt.







User-visible scripts:



scripts/show_frontend_inheritance_outer_status.ps1 (-Once optional) shows packet/



target progress, failures and final seal verification without launching work.



scripts/start_frontend_inheritance_outer_local.ps1 requires explicit authorization.



Generated small capture/ZIP and process-stop checks are synthetic correctness



tests, not repeated real experiments or resource trials.







The comparison will separately report old-attack/benign retention and B utility.



It does not prove causal B-training contribution or broad inheritance.



N1/N2/N3 remain CLOSED; N3 remains JOINT_EXACT_FLOAT32_FIT; F5 remains



NO_ELIGIBLE_CHECKPOINT; broader_inheritance=NOT_PROVED; K/deployment/new-device



experiments remain unauthorized. Preserve the user's literature-first research



preference and their priority of old attack capability followed by B benefit.



HEAD/branch unchanged; eight unrelated tracked modifications retain their hashes.







### 2026-09-08 Post-N3 design complete; no new experiment started







Current status: DESIGN_COMPLETE_INPUT_QUALIFICATION_PENDING. The user's latest



authorization covered the proposed literature/design stage, following the



discussion distinguishing design from experiment. Read these new documents



and their .sha256 sidecars:



- frontend_inheritance_post_n3_whole_pool_comparison_design_20260908.md



- frontend_inheritance_post_n3_literature_review_20260908.md



- frontend_inheritance_post_n3_design_evidence_20260908.json







Preserve the successful N3 witness below. The concrete next comparison uses



that ONE fixed candidate on the COMPLETE original F1 internal-validation pool:



4,400 targets / 3,582 contexts, including 2,000 old-detected reconnaissance



attacks, 1,176 A benign and 1,224 B benign targets. Require zero new misses among



the 2,000 attacks and zero new hard decisions among 1,174 old-correct A benign



targets; report B utility separately by target, context and represented group.



Do not compare these denominators with the old global P2 97.3698% recall.







This pool is outside the catalogued F5/N3 target fit but already exposed in



F1 validation and frontend diagnosis. Exact learned-component exclusion joins



and source/session dependencies still need qualification. Even a positive test



provides scoped exposed-development evidence, not complete inherited behavior,



independent holdout confirmation or a deployment qualification.







Full-pool L1/F4 inputs are missing: existing F4 has the parent plus only five



old kill prefixes. Reuse the passed F4 mapping; do not relabel F1 L0 signatures



as L1 or rerun F4/history. NEXT: separately authorized implementation/synthetic



acceptance and scoped metadata qualification, then seal exact five-member raw



identities/cutoffs, input lineage and resource bounds before proposing ONE real



bounded preparation plus fixed-candidate comparison. No new training is needed



for that comparison. Do not launch from this decision design.







The user's priorities remain old attack capability first, then additional B



benefit; new-device commissioning follows later. Useful B decisions are distinct



from the causal contribution of B training. N1/N2 already contain B-trained



encoder exposure and are invalid no-B controls. A later causal study would need



prospectively matched arms and explicit treatment of B prefixes; none is



authorized or automatically scheduled.







Focused literature review includes two August/September 2026 preprints, recent



netFound revision, backward-compatibility metrics and security evaluation bias.



Treat preprints as provisional and retain the user's literature-first research



preference. Only documents/source/authorized aggregate metadata and public paper



text were inspected. Twenty evidence hashes and eleven accepted N3 code hashes



match; no real numerical experiment or historical test was rerun.







N1/N2/N3 remain CLOSED; N3 remains JOINT_EXACT_FLOAT32_FIT; broader_inheritance



remains NOT_PROVED; F5 remains NO_ELIGIBLE_CHECKPOINT. K, deployment, raw replay,



new inference/training and new-device execution remain unauthorized by this



stage. HEAD is 4b28747 on codex/exp-mainline; protect all unrelated changes.







### 2026-09-08 N3 real attempt complete: conservative joint repair witness







N3_CONSERVATIVE_JOINT_REPAIR_WITNESS; JOINT_EXACT_FLOAT32_FIT.



Supervisor final seal verified, 25.203 seconds, one worker, one LP, one candidate,



zero retries. All 12,711 constraints passed exact and canonical float32 checks.



All 8,660 training judgments retained; 1,484 development protections correct



(previous 3 A attack misses and 843 protected benign errors repaired).



All 2,567 historical B normal targets and 2,238 normal-context members retained;



300 additional B targets / 263 contexts released. All original B floors passed.



The 1,155 exposed residual targets have 302 correct / 853 wrong outcomes.







Read frontend_inheritance_n3_real_result_20260908.md and its sidecar.



Real namespace: runs/frontend_inheritance_n3_conservative_joint_repair_v1_20260908/.



SHA256SUMS SHA256:



5ef2be5e6f7f93626d12fd87e38efbdac33967a0e4a14bb11a59cd55c9795e43.



N3 is CLOSED: no restart, second candidate or repeat fitting. The fixed encoder



and non-head state are unchanged. This repairs known finite observations;



4,051 original development targets were explicitly fitted, so broader inheritance



remains NOT_PROVED. F5 remains NO_ELIGIBLE_CHECKPOINT; K/deployment/new-device



experiments remain unauthorized. N1/N2 and the incumbent remain unchanged.







NEXT: explain project status and repair logic to the user in plain language,



including the remaining same-behavior, fit-exclusion and dependency evidence gap.



Do not automatically start another experiment. The research preference below



is persistent and applies to future difficult problem/design work.







### 2026-09-08 ONE real N3 attempt authorized (execution completed above)







The user explicitly authorized the next ONE real N3 conservative joint fitting



attempt after implementation acceptance. Execute the sealed controller once;



do not retry or change frozen constraints, model, solver or limits. K,



deployment and new-device experiments remain unauthorized. Final scientific



status requires the verified supervisor seal. The user requests a plain-language



explanation of project status and repair logic after this stage.







Persistent research preference added by the user: when facing a hard research



problem or considering a major architectural/method change, first search current



frontier literature and suitable existing methods, assess their fit to this



project and then design targeted innovation. Do not design such changes solely



from internal reasoning. This preference does not change the already frozen N3



attempt or authorize additional experiments/data access.







### 2026-09-08 N3 implementation accepted (state before real authorization)







The current user message authorizes N3 implementation and generated synthetic



acceptance. This supersedes only the implementation-authority field in the



frozen design; its numerical, input and scientific rules are unchanged.



N3_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS: 70/70 generated tests and 2/2



PowerShell parser checks passed. Eleven code pins and seven runtime pins are



sealed in runs/frontend_inheritance_n3_implementation_v1_20260908/.



Acceptance SHA256:



647b8f02e22b5197a7f301f093b560ef84f4e176e45366fe2a52ea5c7515639f.



Read frontend_inheritance_n3_implementation_and_synthetic_verification_20260908.md



and its sidecar for implementation, generated evidence and limitations.



No real N3 input decoding, checkpoint load, forward or fitting is authorized or



performed. The real namespace remains absent. Historical N1/N2 stay closed.







Read-only readiness is READY_FOR_SEPARATELY_AUTHORIZED_REAL_N3; real status is



NOT_STARTED. NEXT GATE: separate authorization for ONE real N3 conservative



joint fit, under the unchanged 1,800-second / 8-GiB / 100-MiB ceiling. The new



viewer scripts/show_frontend_inheritance_n3_status.ps1 verifies final seals and



labels earlier receipts provisional. Never restart an existing real namespace.



Synthetic acceptance is not evidence that the 12,711 real constraints can be



jointly satisfied. Even a real witness leaves broader_inheritance=NOT_PROVED,



F5_eligible=false, deployment=false, K=NOT_AUTHORIZED and new_device=NOT_EVALUATED.







### 2026-09-08 N3 joint-repair design frozen (historical authority at design time)







The user authorized the complete next design/review after the post-N2 proposal.



Read `frontend_inheritance_n3_conservative_joint_repair_frozen_20260908.md`,



`frontend_inheritance_n3_input_and_evidence_pins_20260908.json` and



`frontend_inheritance_n3_same_behavior_evidence_contract_20260908.md`, with



all three `.sha256` sidecars. Status:



N3_DESIGN_FROZEN_IMPLEMENTATION_AND_REAL_FIT_NOT_AUTHORIZED.







One prospective conservative fixed-64D/65-parameter head problem is frozen:



8,660 original train + 1,484 development protections + 2,567 historical N2 B



releases = 12,711 constraints. The 4,051 new development-fitting targets and



1,155 exposed report-only targets have explicit roles; neither is fresh



confirmation evidence. Preserve historical B target/context sets by inclusion,



allowing additional releases. The original F5/N1/N2 outcomes remain unchanged.







The protocol reuses N1's training target64 cache with full identity/metadata



joins, one fixed-N1 development extraction reproducing all N2 float32 logits,



one LP, one candidate cast, exact checks and canonical candidate train+dev



verification. Maximum real budget: one worker, 1,800 s, 8 GiB, 100 MiB,



428 batches / 13,630 context evaluations / 19,072 target evaluations;



205,470 events decoded once, 377,635 forward event occurrences. No baseline



train replay, optimizer, teacher, retry, HPC or K. Exact failure/unknown cannot



be upgraded to a broader impossibility claim.







Three read-only reviews found no blocking design issues. Static checks matched



57 effective pins, seven manifests / 39 selected entries, 16 historical code



files and seven runtime files. No real numeric input/model/solver or synthetic



experiment ran in this design. Neither N3 output namespace exists.







NEXT GATE: N3 implementation and synthetic acceptance, suitable for medium



implementation thinking; then separately authorize the one real fit. A future



witness would establish known finite-set joint repair, not broader inheritance.



The separate evidence contract keeps the missing matched-behavior, fit-exclusion



and dependency evidence explicit. No new-device/holdout/deployment claim follows.







### 2026-09-08 Post-N2 strategy review (full N3 design completed above)







The user requested careful breakthrough reasoning after N2. Read



`frontend_inheritance_post_n2_breakthrough_strategy_review_20260908.md`.



This authorized source/document reasoning and parallel read-only reviews only;



no new numerical input, model, fitting or experiment was executed.







Primary recommendation is to DESIGN one conservative fixed-last-layer joint



repair: preserve all 8,660 original training judgments, satisfy all 1,484



development protections and preserve all 2,567 N2 B target releases (12,711



disjoint target constraints). This is a proposed NEW stronger development



retention condition, not the original N2 gate expressed as an LP. Its use of



development labels must be explicitly declared as fitting. No launch is allowed



without a complete new reviewed scope and authority; N1/N2 stay permanently



closed and the ban on successive head searches remains in force.







A positive verified witness would show these known failures can be repaired



without changing the encoder. A negative result would concern only that fixed



head and stronger retention condition; it cannot prove original B floors



infeasible or input insufficiency. No subset relaxation/search is authorized.



The full design must expose the separate missing same-behavior inheritance



evidence contract. Teacher-history restriction remains a conditional diagnostic



with unresolved lawful old-session/cutoff bridge, not an automatic next run.



No original frozen file, denominator or scientific result changed in this review.







### 2026-09-08 Real N2 complete: DEV_ATTACK_GATE_FAILURE; attempt closed







Read `frontend_inheritance_n2_real_result_20260908.md` and its `.sha256` sidecar.



The ONE real attempt completed as N2_DEV_ATTACK_GATE_FAILURE in 9.016 seconds.



This is a complete scientific failure, not an engineering stop: all 5,206 targets



/ 4,323 contexts were evaluated in one pass / 136 batches. Worker exit is 0;



controller and worker are confirmed exited. All 15 output manifest members



verify in `runs/frontend_inheritance_n2_fixed_witness_development_v1_20260908/`.



The status viewer reports FINAL with verified seal. Never restart this attempt.







A1C attacks: 0/3 detected (Ingress Tool Transfer, one context). B1N attacks:



3/3 detected (File Download, two contexts). A0C: 843/1,478 errors, all 843



normal_1 A0C targets; other 635 A0C targets pass. A0W: 0/2 errors. B0N: 2,567/3,720



normal targets and 2,238/3,327 all-B-benign-normal contexts; all three raw per-key



floors pass. Usable joint utility is FALSE because protection failed.



The 846 protected wrong UIDs exactly match the final old F5 reference: zero



newly wrong and zero newly correct. No unprotected old per-UID baseline invented.







One restricted load/head decode/assembly; 172,165 development prefix events,



826,290 padded slots, peak 568,057,856 bytes. Assembled state unchanged before/



after the sole forward. Zero training replay, teacher, LP, optimizer, backward,



threshold fits, pilots, retries or HPC. All frozen identities and unrelated



issue27by file hashes are preserved; deployment is unchanged.







NEXT GATE: attack-side coverage/input/history diagnostic design and review,



as required by the frozen attack-failure branch. Training-set repair did not



resolve these exposed-development failures; the cause is not yet identified.



Do not infer backbone impossibility, launch a benign-only normal_1 fit or move



to new-device commissioning. No new design execution, fitting, N1/N2 retry or K



is authorized. N1's training witness remains intact; general inheritance remains



unproved and F5 remains NO_ELIGIBLE_CHECKPOINT. Changes remain local/uncommitted.







### 2026-09-08 One real N2 authorization (completed above)







After sealed N2 implementation acceptance, the user instructed proceeding with



the next step. This authorizes ONE real fixed-witness N2 development check,



including the frozen restricted checkpoint container, final old development



reference, exact N1 head bytes and selected internal_val feature prefixes.



Readiness passed; branch codex/exp-mainline and HEAD 4b28747 are unchanged.



The real output namespace was absent before launch. Preserve the exclusive



attempt after any terminal outcome; no retry, fitting, N1 replay or K is allowed.



All frozen scientific, access and resource rules remain in force.







### 2026-09-08 N2 implementation accepted (real authority superseded above)







Read `frontend_inheritance_n2_implementation_and_synthetic_verification_20260908.md`



and its `.sha256` sidecar. Status: N2_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS.



43/43 generated synthetic tests and 2/2 script parser checks passed. Acceptance



is sealed in `runs/frontend_inheritance_n2_implementation_v1_20260908/` with nine



code and seven runtime identities. Receipt SHA-256:



`6254aebb1edecc0459ec487a75fdf3caaa8b6e2033e10afd7578d37f3d6c666d`.



Read-only readiness passes; the real namespace is absent and status is NOT_STARTED.







The new N2 controller/selective reader, exact fixed-head assembly, one-forward



measurements and launcher/status scripts are implemented. The viewer verifies



the final supervisor seal and labels earlier receipts provisional. Use



`scripts/show_frontend_inheritance_n2_status.ps1` (or `-Once` for one snapshot).



No real features/head were decoded, no real checkpoint loaded and no real logits



computed in this stage. N1/F5 sources and frozen inputs remain unchanged.







NEXT GATE: separate explicit authorization for the ONE real N2 development check,



including its restricted checkpoint container/final old validation reference.



Only then evaluate the fixed N1 witness on 5,206 exposed-development targets /



4,323 contexts with zero fitting. Caps: 1,800 seconds, 8 GiB, 100 MiB, one pass /



136 batches. No retry, N1 replay, N3 fitting, K or deployment is authorized.



Inheritance remains unproved; F5 stays NO_ELIGIBLE_CHECKPOINT. Existing unrelated



modifications are preserved; implementation/report changes remain local.







### 2026-09-08 N2 implementation/synthetic authorization (completed above)







The user explicitly authorized N2 implementation on 2026-09-08. Only new N2



code and generated synthetic fixtures/checks are authorized in this stage.



Real feature/head numeric access, real checkpoint loading and the one real N2



development evaluation remain separately gated and have not started.



The frozen protocol and pin bundle below remain byte-for-byte unchanged.







### 2026-09-08 N2 design frozen (implementation authority superseded above)







The user authorized next-stage design/review after N1. Read



`frontend_inheritance_n2_fixed_witness_development_check_frozen_20260908.md`



and `frontend_inheritance_n2_input_and_evidence_pins_20260908.json`, with their



respective `.sha256` sidecars. Status:



`N2_DESIGN_FROZEN_IMPLEMENTATION_AND_REAL_CHECK_NOT_AUTHORIZED`.



Primary-agent source/contract review is complete with no blocking design



findings. No independent-agent review or numeric execution is claimed.







N2 will assemble the exact sealed N1 head with the original terminal backbone



and check ONE fixed candidate on all 5,206 original F5 exposed-development



targets / 4,323 contexts. It has zero fitting, teacher, optimizer, training



replay or K calls. Retain the 1,484 original protected development judgments



and the original per-key B benign target/context floors. Preserve all group



outcomes; attack failures take priority over benign utility. Candidate identity,



access projections, input pins, one-forward action caps and stop rules are fixed.







Evidence correction/clarification from the existing N0 aggregate tables: F5



development attacks are Ingress Tool Transfer (A: 3 targets/1 context) and File



Download (B: 3/2); neither recorded family occurs in F5 training. Old F1's



2,000 ToN-reconnaissance_scan targets are also exposed and family-unmatched.



These are useful transfer checks, not a qualifying same-behavior inheritance



reserve. No original inventory or numeric experiment was repeated to establish



this metadata fact. Literal family names do not by themselves establish behavior



equivalence or physical-device/session independence.







After N2, the next design depends on the observed pattern: attack coverage/input



question first if attacks fail; a separately authorized normal_1 coverage design



only for a confined normal-source gap; broader evidence design if gates pass.



Future retention acceptance should cover all 8,660 original training judgments



and carry development protections explicitly, without presenting reused learning



rows as validation. No N3 fitting protocol or data reallocation is authorized.







Next gate: explicit N2 implementation/synthetic acceptance, suitable for medium



implementation thinking, then separate real N2 authorization. The real check's



caps are one worker, 1,800 seconds, 8 GiB, 100 MiB, one forward/136 batches.



N1 remains JOINT_HEAD_WITNESS and permanently closed; inheritance remains



unproved, F5 remains NO_ELIGIBLE_CHECKPOINT and deployment is unchanged.



All changes are local documents; existing unrelated work is preserved.







### 2026-09-08 Real N1 complete: JOINT_HEAD_WITNESS (next-design status superseded above)







Read `frontend_inheritance_n1_real_result_20260908.md` and its `.sha256` sidecar.



The sole authorized attempt completed as `N1_JOINT_HEAD_WITNESS` in 11.828 s,



with one LP, two canonical forwards and zero optimizer/teacher steps. Output:



`runs/frontend_inheritance_n1_fixed_terminal_head_v1_20260908/`.



Supervisor final seal is present, exit code is 0, both processes have exited,



and the completed manifest independently verifies 23/23 artifact hashes.







Baseline reproduced the exact five terminal A-attack failures. Candidate errors



are zero for A1C 2,179, A0C 4,667, B1N 68, A0W 24 and B0N 1,722: all 6,914



protected plus all 1,746 accompanying training targets pass, with no newly wrong



UIDs. Exact original-threshold and actual float32 checks both pass. Minimum exact



signed margin is approximately 0.007725780875765587, with no zero-margin attack



ties. All 4,984 full pre-head context hashes match; non-head parameters are fixed.



The exact-negative branch was skipped because a positive witness was verified.







This establishes finite-set last-layer repair feasibility on the fixed terminal



representation. It does NOT establish holdout inheritance, retention through



later learning, ToN-normal coverage, B utility or commissioning/OOD success.



F5 remains NO_ELIGIBLE_CHECKPOINT; the diagnostic head is NOT_DEPLOYMENT and



NOT_F5_ELIGIBLE. The incumbent and original artifacts are unchanged.







Access followed the sealed scope: 33,305 train prefix events decoded; zero new



validation numeric computations. Mixed metadata parsing and incidental restricted



checkpoint optimizer/RNG/old-validation-ledger materialization are disclosed and



the incidental values were not used. No retry, extra solver, resource pilot,



download, HPC or K occurred. Current work remains local/uncommitted.







Next recommendation is scoped inheritance-verification/retention and coverage



design from this witness. Do not automatically train, replay N1, reallocate old



validation or open K. Further execution needs its own reviewed scope and authority.







### 2026-09-08 One real N1 attempt authorized (launch status superseded above)







After implementation/synthetic acceptance, the user explicitly authorized the



next stage. This authorizes the ONE frozen real N1 diagnostic fit, including



restricted full-checkpoint container access as disclosed in the protocol.



Readiness passed against V2 acceptance and the frozen design/runtime identities;



the real namespace was absent immediately before launch. Branch and HEAD remain



codex/exp-mainline / 4b28747b09480471e2bac1beb3a9badf27280efb.







Output: `runs/frontend_inheritance_n1_fixed_terminal_head_v1_20260908/`.



Use final supervisor/worker receipts and `SHA256SUMS` to establish completion;



an authorization or dispatched process is not evidence of scientific success.



Caps remain 1,800 seconds, 8 GiB, 100 MiB, one LP and at most two canonical



forwards. Do not restart the attempt, alter any frozen rule, run a teacher or



optimizer, open validation/K, or start follow-on learning automatically.







### 2026-09-08 N1 implementation/synthetic PASS (real authority superseded above)







Read `frontend_inheritance_n1_implementation_and_synthetic_verification_20260908.md`



and its `.sha256` sidecar. Current acceptance is



`runs/frontend_inheritance_n1_implementation_v2_20260908/synthetic_acceptance.json`:



`N1_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS`, 36/36 synthetic tests and 2/2



PowerShell parser checks. Package hashes, nine code/dependency identities and



seven runtime identities verify. V1's 32-test receipt is preserved but superseded;



only V2 accepts the final code after terminal-handling review corrections.







The sealed scientific protocol and input/runtime pin JSON are unchanged.



Implemented: train-only selective reader, restricted checkpoint projection,



canonical baseline/full-context replay, one LP, exact witness/certificate



verification, single-worker Windows resource enforcement, exclusive attempt



namespace, explicit launch gate and read-only status viewer. Synthetic process



checks exercised limits and failure sealing; no resource pilot was repeated.







No real checkpoint tensor, feature array, model forward, LP, teacher or optimizer



execution occurred. No validation/select/viewed/report/FINAL/K numeric access,



download or HPC occurred. Read-only readiness is



`READY_FOR_SEPARATELY_AUTHORIZED_REAL_N1`; real status is `NOT_STARTED`.







Next gate is explicit authorization for ONE real N1 attempt, including the



disclosed restricted full-checkpoint container access. Its budget remains



1,800 seconds total, 8 GiB, 100 MiB, one LP and at most two canonical forwards.



Use `scripts/start_frontend_inheritance_n1_local.ps1` only after that authority;



`scripts/show_frontend_inheritance_n1_status.ps1` is a read-only viewer.



Never automatically retry F5/N1, open K, modify the freeze or start follow-on



learning. Inheritance remains unproved and the incumbent/F5 failure unchanged.



All current work is local; no commit or push is claimed.







### 2026-09-08 N1 implementation authorized (in-progress status superseded above)







The user switched to the implementation setting and explicitly authorized the



next implementation/synthetic stage. Implement only the sealed N1 protocol.



Real checkpoint/feature access, real LP fitting, F5 retries and K remain



unauthorized. Acceptance work uses newly generated synthetic fixtures only;



Windows resource checks are bounded limit-enforcement tests, not a new resource



pilot. Code, tests, launcher and read-only status viewer are being completed.



Next gate after acceptance is separate authorization for one real N1 attempt.







### 2026-09-08 N1 design frozen (implementation status superseded above)







Read `frontend_inheritance_n1_fixed_terminal_head_feasibility_frozen_20260908.md`



and `frontend_inheritance_n1_input_and_runtime_pins_20260908.json`, with their



respective `.sha256` sidecars. Status:



`FROZEN_DESIGN_IMPLEMENTATION_AND_REAL_EXECUTION_NOT_AUTHORIZED`.



The user authorized the next design/review stage. Input/runtime, mathematics



and scientific-scope reviews are complete with no remaining blocking findings.



Only source/metadata inspection, opaque hashing and document work occurred;



no checkpoint tensor loading, feature decoding, forward, solver or test ran.







N1 fixes terminal event projection/GRU/head_hidden and fits only the existing



Linear(64,1) in a separate diagnostic copy, using one bounded maximum-margin



LP. All 6,914 original protected train judgments are constraints; the other



1,746 train rows remain outcome accounting. A positive witness needs both



exact-threshold and original full-context float32 checks. A negative result



needs an independently verified exact nonseparability certificate for the



fixed terminal 64D last-layer inputs; otherwise report numerical unknown.



An exact-affine negative result may coexist with a float32-only fit, and both



must be retained. Identity/access/resource failures give no scientific verdict.







Next gate: explicit authorization for implementation and synthetic acceptance



only, suitable for the user's medium-thinking implementation workflow. Then



seal code/test/runtime acceptance before requesting separate real N1 fitting



authorization, including its restricted full-checkpoint container access.



Zero optimizer steps does not mean zero parameter fitting. Do not execute



the design, retry F5, open validation/K or start follow-on learning automatically.







Inheritance remains unproved, F5 remains NO_ELIGIBLE_CHECKPOINT, and the



incumbent is unchanged. Even a positive N1 result covers finite-set joint



decisions only; ToN-normal coverage, holdout inheritance, B utility and



trustworthy-benign-prefix device commissioning remain separate questions.



This design and local reports are not claimed committed or pushed.







### 2026-09-07 N0 complete (next-design status superseded by N1 above)







Read `frontend_inheritance_n0_result_20260907.md`. The single metadata inventory



completed as `READY_FOR_SCOPED_DIAGNOSTIC_DESIGN`, with coverage insufficiency



and unresolved old-session/history membership; inheritance remains unproved.



Results: `runs/frontend_inheritance_n0_inventory_v1_20260907/`.



Input pins passed 25/25, synthetic checks 16/16 and result hashes 11/11.



Inventory time 1.219 s, peak process memory approximately 107 MiB; no numeric



model/data access, optimization, capture decoding or network occurred.







Legal fit remains 18,266 targets / 12,889 contexts across 22 sources and 24



artifact members. Exposure remains F5 train 8,660; F5 val 5,206; old F1 val



4,400. The only inventoried lawful ToN benign source is normal_1: 4,000 targets



(843 A, 3,157 B), all already exposed F5 val and zero F5 train. Artifact members



do not establish physical-device or old-session independence. No split changed.







Next recommendation: design one constrained feasibility check of the existing



final Linear(64,1), fixing terminal event projection/GRU/head_hidden, against all



6,914 predefined protected training targets; account for the other 1,746 rows.



This is parameter fitting, requiring its own protocol and authorization even



with zero optimizer steps. It can witness only finite-set conditional joint



decisions, not holdout inheritance or retention through later updates. Keep



coverage/generalization separate. No subsequent fitting, numeric diagnostic,



reallocation or K is authorized by N0. Old F5 failure/incumbent remain unchanged.







### 2026-09-07 N0 metadata inventory authorized (implementation status superseded above)







After reviewing the next-step explanation, the user authorized proceeding with



N0. Read `frontend_inheritance_n0_execution_scope_20260907.md`. Scope includes



the four selector columns on the mixed F1 metadata container and lawful-fit



research projections. The standalone reader and synthetic boundary checks are



being prepared before the single real metadata scan. This does not authorize



numeric diagnostics, new training, repartitioning, K, decoding, downloads or HPC.



The original F5 failure remains; no capability-inheritance PASS is established.







### 2026-09-07 Inheritance feasibility short design ready (execution status superseded by N0 above)







The user authorized the next short design and resumed it after the connection



interruption. Read `frontend_inheritance_feasibility_minimal_design_20260907.md`.



Parallel read-only review is complete with no must-fix findings. The design is



ready for user review, not a new training freeze; its .sha256 identifies only



this design. Recommended next scope



is N0 metadata-only legal-fit coverage and input-contract readiness inventory;



N0 implementation/execution and all numeric diagnostics remain unauthorized.



The document explicitly lists the mixed-table selector metadata access needed.



Joint fitting/retention, same-behavior holdout and unseen-source generalization



are separate accounts. F5 remains failed; no retry, K or deployment change.







Source review corrects one prior claim: flow_duration is constructed/collated



but not consumed by the actual E3 forward. Old early-burst/header/IAT differences



remain; their causal necessity is not proved. Prior local reports and this design



are not claimed committed or pushed. Historical status below remains evidence.







### 2026-09-07 Frontend-F5 T complete: NO_ELIGIBLE_CHECKPOINT







Latest cause investigation: `frontend_f5_failure_mechanism_review_20260907.md`;



reproducible read-only package: `runs/frontend_f5_failure_forensics_20260907/`.



Confirmed gaps: no ToN benign evidence in F5 nested-train, teacher/student fields and



history differ, and five rare training attacks were correct then lost during



optimization. Exact causal contributions remain unisolated; no implementation



repair or new run is justified yet. No new model forward/optimizer/K occurred.







Read-only failure review: `frontend_f5_t_failure_readonly_diagnosis_20260907.md`.



Final manifest passes 17/17 hashes. Final protected errors: train A attack 5;



validation A attack 3 and A normal 843. Of the validation normal errors, 839



persist through all 20 epochs. Next recommendation is mechanism diagnosis/design



review, not a retry or K. New execution remains unauthorized.







Live terminal and verdict receipts confirm `F5_NO_ELIGIBLE_CHECKPOINT` after



20 epochs / 3,120 optimizer steps, 595.812 seconds charged. No checkpoint was



eligible; this is a completed scientific failure of this realization, not an



engineering crash. B gain and K remain `NOT_EVALUATED`. Do not restart, change



the frozen rules, or open K. Earlier running status below is historical.







User-facing read-only viewer: `scripts/show_frontend_f5_status.ps1`, with desktop



shortcut `Paper04 F5 训练状态`. It refreshes every 15 seconds and prioritizes



terminal/failure records over stale heartbeats. This separate viewer does not



modify any Stage I pinned code or scientific artifact. Closing it does not



stop training. Current result does not establish inheritance or commissioning.







### 2026-09-07 Frontend-F5 T authorized and running; K not authorized (superseded)







After P PASS, the user explicitly authorized the next stage T. The existing



frozen launcher started the sole real trajectory at 10:11:04 Asia/Shanghai,



PID 62324. P manifest verification passed 9/9 before launch; no prior training



directory existed. Live startup verification observed 133 real optimizer



steps, a saved resume checkpoint/receipt and an empty stderr. This establishes



actual training progress, not an eligible candidate or scientific PASS.







Output: `runs/frontend_f5_unified_student_v1_20260906_local/`.



Logs: sibling `_local_control/train-20260907T021104007Z.{stdout,stderr}.log`.



Read status with `scripts/watch_frontend_f5_local.ps1 -Once`; inspect live



terminal/failure receipts before any action. Never launch a second trajectory



or restart from initialization. Seed/model/loss/denominators/caps are unchanged.



K remains unauthorized and must not run automatically. Earlier P-only



authorization text below is historical. Incumbent deployment remains unchanged.







### 2026-09-07 Frontend-F5 real P PASS; T/K not authorized (superseded by T above)







The user explicitly authorized the next stage P on September 7. The frozen



preflight completed as `F5_PREFLIGHT_PASS`; no optimizer training or evaluation



was authorized or started. Read `frontend_f5_real_p_result_20260907.md`.



Input/code/runtime/init identities passed. Exactly 6,870 nested-train A teacher



rows were materialized and sealed, including 24 null teacher strengths for



teacher-wrong benign. Parent counts remain 8,660 train / 5,206 internal-val.



The completed P artifact manifest independently verifies 9/9 hashes.







Current next gate: explicit T authorization for the one frozen real trajectory;



K remains separately authorized after T. P is input/teacher readiness only,



not evidence that attack inheritance or B utility succeeds. No new-device,



OOD, commissioning, CE or deployment claim follows. Incumbent is unchanged.



The September 6 P-not-authorized statement below is historical.







### 2026-09-06 Frontend-F5 Stage I complete; real P/T/K not authorized (superseded by P above)







Current result: `F5_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS`. Read



`frontend_f5_implementation_and_synthetic_verification_report_20260906.md`.



The accepted F5 is frozen; core + real-stage controller + launch/monitor are



implemented. 47/47 synthetic tests and two PowerShell parser checks pass.



The single resource pilot passed; its numerical path is unchanged and no



second timing pilot was used. Current source/runtime/test pins are in



`runs/frontend_f5_implementation_v1_20260906/stage_i_acceptance.json`.







No real F5 feature/teacher data was opened, no real optimizer step was taken,



and no real F5 run directory/background job exists. **Next gate is explicit P



authorization** for byte/census checks and 6,870-row teacher materialization;



T (one real trajectory) and K (sealed candidate/utility/kill-only evaluation)



remain separately authorized stages. Do not repeat design or redo F4. Current



Astra implementation setting is accepted; no Sol switch is required. Earlier



I1 runner-pending status below is now historical. Incumbent remains untouched.







### 2026-09-06 Frontend-F5 earlier I1 checkpoint (superseded)







The user authorized implementation/synthetic work using the current Astra



setting. The accepted numerical draft is mechanically FROZEN with SHA



`b8069e6556d6719eef3e689b1ab9a8676c24a00a82e8b5f810a401c9c42786b6`.



Read `frontend_f5_implementation_checkpoint_20260906.md` first.







Core model/loss/causality/selective-reader/checkpoint regressions pass 22/22;



the single synthetic resource pilot passes (threefold projection 27,962.99 s



below 47,494.34 s). Status is deliberately



`F5_I1_NUMERICAL_CORE_VERIFIED_I2_RUNNER_PENDING`, NOT full Stage I acceptance.



The production preflight, real controller, full accounting, one-shot seal and



launcher/monitor integration tests remain to implement under this authorization.



Do not repeat design or select another architecture. Do not rerun the bounded



pilot to obtain a better time. No real feature/teacher/score opens or real



training occurred; P/T/K remain separately unauthorized. No real-run CLI exists



yet. The historical Sol handoff is role-based, not a required model switch.







### 2026-09-06 Frontend-F5 original design milestone (superseded authorization)







F4 is complete; do not repeat its audit. The user's follow-up authorizes the



next training **design**, not implementation or a real run. Read



`frontend_f5_unified_student_one_shot_training_draft_20260906.md` and the compact



`frontend_f5_sol_implementation_handoff_20260906.md`; rationale/self-review is



`frontend_f5_design_decision_record_20260906.md`.







The proposed F5 is one shared fieldwise GRU + small student head, with old P2



only a label-aware continuous teacher on 6,870 nested-train A rows. It is not a



new 768D/frozen-P2 attempt or CE deployment change. The inherited 8,660/5,206



source split stays fixed. Numeric losses, one seed, checkpoint rules, resource



limits, A/B attack guards and per-key B utility are specified before any new



score/model access. Internal-validation A attack evidence is still one context



/ three rows; any PASS would be development-only. Training, teacher opens,



implementation, select/report/FINAL, deployment and commissioning remain



unauthorized. The next deliverable after design acceptance is Sol implementation



and synthetic verification, followed by separate bounded real-run authorization.







### 2026-09-06 Frontend-F4 fieldwise input PASS







The authorized Sol High implementation and no-model audit completed as



`F4_FIELDWISE_INPUT_PASS`. All 13,866 parent targets / 9,307 contexts / 205,470



events encode to fixed 131D float32 inputs and round-trip exactly. The 3,173



old all-UNK validation targets are now losslessly represented; canonical and



feature mixed-label buckets are zero; feature collisions are zero; all five



kill-only attack prefixes encode and none equals a nested-train benign prefix.



Synthetic tests pass 28/28 and the result manifest passes 14/14 independent



hash checks. Runtime 54.484 s, peak working set 388,538,368 bytes.







This is input feasibility only. It is not inherited attack capability, OOD



improvement, hydraulic repair, or commissioning evidence. Validation has only



one A attack context / three rows; the five exposed attacks remain kill-only.



Read `frontend_f4_fieldwise_input_result_report_20260906.md` and



`frontend_f4_to_f5_training_design_brief_20260906.md`. The only permitted next



action is a separate higher-reasoning training protocol draft. Training,



teacher/model/score opens, select/report/FINAL, CE deployment changes, external



data, and HPC remain unauthorized.







### 2026-09-05 Frontend-F3 closure and F4 implementation handoff







Historical design state, superseded by the September 6 PASS above. At this



point F4 code and the real feature audit had not run.







This entry supersedes the older control-panel experiment state below for the



current frontend work. Frontend-F1's single local GRU/frozen-P2 training ended



without an eligible checkpoint. F2 then found two deterministic contradictory



coarse-input buckets. F3's L1 refinement removed those exact conflicts, but its



full-fit audit is now closed as `F3_FULL_FIT_L1_NO_GO`: a whole-signature



dictionary maps 3,173/5,206 nested-validation target prefixes and two exposed



attack prefixes entirely to UNK. Vocabulary size 1,001 is below 4,094; capacity



and mixed-label collisions are not the blocker. Result package 12/12 and saved



member checkpoints 20/20 SHA checks pass. All 13,871 L0 prefixes reproduce.







The raw F3 verdict's broad interface-closure policy string is qualified in



`frontend_f3_full_fit_l1_result_closure_20260905.md`: this run stops; it does



not prove that all unified encoders or frozen-P2 interfaces are impossible.



Do not change or rerun the original verdict. Internal-val A attack evidence



is only one independent context / three rows; no positive inheritance claim.







Current authorized work: completed F3 closure and an implementation-ready



Frontend-F4 fieldwise-input draft, followed by Sol High implementation,



synthetic tests, and a no-model offline audit after mechanical freezing.



Read `frontend_f4_sol_high_implementation_handoff_20260905.md` and



`frontend_f4_fieldwise_input_feasibility_draft_20260905.md` before acting.



F4 preserves the same L1 fields in a fixed invertible 131D float32 input,



uses existing cached signatures, and introduces no learned component.



Implementation/execution are authorized; training is not. The user prefers



design/review at very-high reasoning, implementation with Sol High. The same



authorization carries forward on a model switch; do not request it again.







Incumbent deployment remains frozen. CE, select/report/FINAL, additional



model/score opens, external downloads, and commissioning experiments are not



authorized by F4. CKDA HPC replay waits for confirmed cluster access (user's



latest estimate is around September 8); no login or job action is requested.



New-device benign/attack pairing remains an independent unresolved evidence



requirement, not something F4 PASS can establish.







### 2026-07-29 CKBV result and r20 run-grounded recovery state







CKBV r16 AMD job `154917` completed the formal seed-27 computation and emitted



a scientific `NO_GO`, then failed only during `validate_and_pack`.  The



duplicate Intel job `154918` reached the same post-computation validator



failure.  Neither failure is a model or data-computation failure.







Two attempted validator/recovery repairs then failed closed because they



encoded planning-document constants instead of run-grounded evidence.  The



run's own immutable audits record the truth (failure-ledger Section 18):







- role-usage audit: GLOBAL fit `support_train=385, id_calib=809,



  ood_val=2604, ood_stress=0`, benign select all zero;



- sensitivity audit: `core_fit_benign=3413/3413/0` (= 809 + 2604),



  `core_ood_val_select=0/0/0`, zero masked rows in every pool;



- environment/run_spec: raw51 mask at the materialization layer,



  325,067 -> 323,714 targets, 1,353 masked, source



  `processed/iotsim-hydraulic-system-1.csv`.  The masked rows never entered



  any pool, so the planning figures 8,682/7,329/1,353 describe the target



  universe, not pool composition.







r20 is a metadata-only recovery of AMD job `154917` grounded in those



artifacts: preserve the original audit, append explicit `core_id_calib_fit`



809/809/0 and `core_ood_val_fit` 2604/2604/0 rows plus the



target-materialization mask row, prove all scientific hashes unchanged, rerun



the corrected validator, and produce the pullback.  It must not submit Slurm



work, retrain, re-decode PCAPs, change scores/gates, or recover the Intel



duplicate.  See `ckbv_r20_run_grounded_pool_recovery_20260729.md`.







The scientific result remains `NO_GO`: held OOD hard rates improve and overall



attack hard recall increases by about 7.416 pp, but at least one major attack



family violates the 2 percentage-point preservation gate.  Do not launch



seeds 37/47 from this result.







(The r17-r19 local packager history — PowerShell 5 compatibility, bytecode



contamination, and the falsified recovery constants — is recorded in



failure-ledger Sections 16-18.  r17/r18/r19 artifacts are retired; only the



run-grounded r20 artifact is uploadable.)







### July 2026 method-route supersession







The pre-July control-panel text below is retained as historical data/support



lineage, not as the current detector route. `openworld_handoff_20260711.md`



records the mature-TGN starting point; the current post-CKBO route is:







```text



mature flow frontend / C1 attack-candidate anchor



+ raw mature AfterImage115 process evidence



+ broader legal source/family-disjoint normal evidence



+ source-held-out one-sided calibration



-> suppress only under transferable normal evidence; otherwise retain hard



```







Strict fit/select/report isolation remains frozen. In particular, an unseen



device/source/family is excluded from both fit and select, raw labels never



enter the frontend, sources never share online memory, and the first TGN



comparison has `review=0`. CKBE T0 cache materialization passed on 2026-07-12;



this is not a model-performance result. See



`ckbe_t0_fullsupport_cache_20260712.md` before starting M1.







CKBI Stage A later completed the separate four-source report-only TGN cache.



The first CKBH Stage B revision at commit `195b1c26` is invalid and must not be



used as performance evidence: its CKBI boolean check was inverted, its C1 cap



and report-cache contracts were inconsistent, and its negative sampler drew



nonexistent cross-source-capacity nodes.  The corrected local implementation



is documented in `ckbj_m1_v2_protocol_fix_20260713.md`.  It preserves the base



26-source/34,622-target manifests, adds only a separately hashed report-only C1



extension, uses source-local past-seen negatives, and separates



fit/select/report replay.  Its first submission, job `151220`, reached the



validated PyTorch/PyG environment but exited before training because the



compute image lacks `/usr/bin/time`; it is not performance evidence. The



replacement launcher removed that dependency and r4 completed the first



single-seed formal M1 on AMD job `151377` at experiment commit `f2c8a075`.



The registered result is `NO_GO`: M1-SSL left stream-consumer OOD hard alarms



at 100%, reduced hydraulic-system only to 82.1%, and lowered overall attack



hard recall by 1.8996 percentage points. Seeds 37/47 must not be launched.



Data-use and leakage contracts passed, but post-result review found that



fit/select replay used sparse target-only histories while report replay used



dense raw histories in 200-event batches; the SSL targets were also highly



imbalanced. Therefore CKBJ v2 rejects this exact realization, not the entire



mature-TGN route. The metrics and diagnosis are frozen in



`ckbj_m1_v2_seed27_formal_result_20260714.md`.







CKBK seed 27 ran on AMD job `151489`.  Its TGN child failed a fail-fast



neighbour-negative assertion, so it supplies no repaired-TGN performance



claim.  The independent GraphMixer child completed but was `NO_GO`:



stream-consumer stayed at 100% hard OOD, overall attack recall fell 3.0854 pp,



the worst major attack family fell 98.2301 pp, and learned-vs-random select



AUROC improved only 0.0029.  Hydraulic fell to 20.3%, but that isolated canary



improvement cannot rescue attack preservation or the random-control failure.



The sealed cooler-motor final holdout remained unopened.  Do not repair only



the TGN assertion and rerun the same information-poor route.







CKBL full-source seed 27 completed on AMD job `151564` and passed every data,



alignment, causality, and fold contract.  It is a scientific



`OBSERVABILITY_NO_GO`, not an execution failure.  Exact TGN9, Compact69, and



C1 207D all contain strong unseen-source rank signal; C1 reaches `0.9176` mean



unseen-family AUROC.  However, ordered 69D history does not beat the genuinely



changed within-source permuted control.  More importantly, legal



attack-preserving thresholds do not transfer: mean unseen-source benign FPR is



`0.3310` for Compact69 and `0.4858` for C1, and only four of ten unseen-family



folds have complete legal inner-OOF threshold coverage.  The active blocker is



therefore cross-source/family score calibration and hard-decision transfer,



not absence of frontend information.  Do not run additional CKBL seeds or



repair the same TGN/GraphMixer route.  The next result experiment must reuse a



mature calibration/source-normalization method with label-free past-only



report adaptation and directly measure report OOD hard alarms plus attack



preservation.  See `ckbl_fullsource_seed27_formal_result_20260714.md`.







CKBM seed 27 is complete after metadata-only recovery of AMD job `151583`; the



formal validator passed with zero errors and no model retraining.  The result is



a diagnostic `NO_GO`.  M3-TabM-CSR changed stream-consumer hard OOD only from



100% to 99.6%, changed hydraulic-system to 45.33%, and lowered overall attack



hard recall by 0.4331 pp.  UDP Scan recall fell 71.68 pp, so the major-family



retention gate failed.  ExtraTrees controls suppressed attacks catastrophically,



and global TabM was worse than CSR.  Seeds 37/47 must not be launched.







Post-run audit also found that CKBM enforced exclusion of the current held



family but not the stronger mainline rule that both used development canaries



remain outside every fit/select scope.  Global fit used 4,000 stream rows and



3,078 hydraulic rows; strict-stream still used hydraulic and strict-hydraulic



still used stream.  Therefore CKBM may reject this symmetric backend route but



cannot support a paper-grade strict positive claim.  Before the next formal



route, validator logic must enforce all-canary zero use.  The next method must



keep C1 as the high-recall anchor and test one-sided, source-held-out calibrated



normal-evidence suppression rather than another larger attack-vs-benign



classifier.  See `ckbm_seed27_formal_result_20260714.md`.







CKBN full-source stream separability diagnosis completed on Intel job `151721`



and passed its alignment and zero-use contracts. It found that the current C1



207D representation does not rank stream-consumer below future attacks:



stream macro AUROC is `0.2513`, stream versus UDP Scan AUROC is `0.0`, and the



hard rate remains `100%`. This narrows the claim to the current representation,



legal fit diversity, and probe; it does not prove that raw traffic has no



transferable information. CKBN is diagnostic evidence, not a detector result.







CKBO AMD job `151772` is an execution failure, not a scientific result.  It



stopped before C1 fitting because permanent multi-family exclusion shifted the



linspace-capped row identities outside the immutable CKAT cache.  A real local



1M replay also proved that zero legal original benign-select rows remain after



all permanent canaries are removed.  No model/report metric was opened and the



sealed cooler-motor final remains unopened.







The corrected CKBO implementation retains mature vendored Kitsune/AfterImage



115D, official TabM, seed 27, and the deterministic multiscale contrast.  It



restricts fit/select to the immutable C1-target/T0-target intersection, freezes



a support-val attack-only recall-first C1 candidate threshold, and never fills



missing features.  A strengthened raw-PCAP extension uses 11 fit plus 5



source-disjoint select sources from known non-canary families, while all 15



predictive-maintenance sources become a second unseen development-held family.



The real local audit passed 385 support-train, 69 legal support-val, 3,413



original benign fit, zero permanent-canary use, zero auxiliary overlap, and a



31-source 6,600/3,000/9,000 fit/select/report materialization.  Seed 27 remains



pending; success now requires five-point improvement on both ip-camera-street



and predictive-maintenance plus the stream/hydraulic and attack-preservation



gates.  Final pre-submit review additionally aligned the formal 600-row/source



argument with validation, added a legal attack-only gate for no-aux ablations,



and structurally excluded sealed OOD from the global attack pass.  See



`ckbo_job151772_failure_and_scope_fix_20260715.md` and the amended



`ckbo_mature_afterimage_transfer_prereg_20260715.md`.







The first corrected rerun, AMD job `151774`, is also an execution failure and



not performance evidence. It reached the predictive-maintenance protocol but



the candidate assembler appended that protocol's existing `aux_report` rows a



second time; the duplicate-UID guard stopped before finalized outputs. Final



review also found that iterating the historical `HELD` tuple would be



incompatible with auxiliary families used for normal diversity. The repaired



scope includes each report once, independently removes the current held



family from auxiliary fit/select, and freezes the formal list to global,



ip-camera-street, predictive-maintenance, stream, and hydraulic. See



`ckbo_job151774_duplicate_scope_fix_20260715.md`.







The corrected CKBO seed-27 job `151780` completed on AMD with all data,



alignment, support-use, report-isolation, and sealed-holdout checks passing. It



is a valid scientific `NO_GO`. The primary multiscale-contrast plus auxiliary



TabM candidate changed stream only from `100%` to `99.733%`, IP-camera-street



from `100%` to `99.767%`, predictive-maintenance to `73.011%`, and hydraulic



from `72.367%` to `42.533%`, while overall attack hard recall fell `6.091 pp`.



Merlin TCP Flooding fell `32.573 pp`. Review remained zero and cooler-motor



remained unopened.







The ablations are decisive. Raw AfterImage115 without auxiliary normals



reduces predictive and hydraulic by about 34/33 pp but leaves stream and



IP-camera near 100% and still loses `1.375 pp` attack recall. Auxiliary normal



diversity improves predictive/hydraulic but worsens attacks. Raw115 plus Aux



strictly dominates the preregistered multiscale contrast on all four OOD rates



and overall attack recall, so the contrast route is rejected. Do not run CKBO



seeds 37/47. The next route must keep C1 as the attack anchor and test



source-held-out, one-sided normal-evidence calibration with broader legal



normal-family coverage; it must default to hard when normal evidence does not



transfer. See `ckbo_seed27_formal_result_20260715.md`.







CKBP seed 27 completed on AMD job `151835` at commit `af9366a`; the job,



checksum, data isolation, support use, alignment, sealed-holdout, and review=0



contracts pass. The registered primary is `NO_GO`, and post-pullback audit



finds a stronger protocol degeneracy. All 69 support-val attacks are inside



the 64-row-per-source fail-closed window and therefore have verifier score



`1.0`. Gate selection chooses threshold `1.0`, while every warmed finite-sample



conformal score is mathematically below `1.0`. M2 consequently retains almost



only cold-start rows: its attractive stream/IP-camera rates of `2.1333%` and



predictive rate of `10.6667%` equal the per-source burn-in fractions, while



overall attack recall collapses from `91.2997%` to `0.1451%`. These OOD rates



are not generalization evidence. The static M1 global-normal control remains



interpretable and shows real OOD rank signal, but loses `9.0498 pp` overall



attack recall. Do not run seeds 37/47 or repeat CKBP unchanged. Separate cold



fail-closed state from the evidence score, require warmed support-val attacks,



and populate online state from the same deployment-equivalent label-free full



stream for attack and OOD before another result run. See



`ckbp_seed27_result_and_gate_diagnosis_20260717.md`.







CKBQ seed 27 completed its formal program on AMD job `153037`; the final Slurm



failure was a stale post-result validator constant and recovery changed no



score or gate. The recovered result is a valid scientific `NO_GO`. Static



normality produced the first large, simultaneous four-held OOD reduction



(IP-camera `8.1%`, predictive `57.589%`, stream `29.7%`, hydraulic `45.7%`),



but overall attack recall fell from `91.300%` to `84.354%`. The current



temporal branch rescued only 37 attacks. Exact post-hoc score-space enumeration



found zero threshold pair satisfying both the multi-held signal and attack



constraints. Most suppressed attacks were future TCP Scan/Telnet, absent from



the 385-row support bank. Do not run CKBQ seeds 37/47 or retune its score pair.



See `ckbq_seed27_formal_result_20260721.md`.







CKBR/CKBS audited and exactly materialized 160 candidate TCP Scan/Telnet rows



without changing support v1, the 1M split, T0, or certified query chunks. The



features and labels align exactly, but all candidates occur later in the same



capture than the already frozen future/query rows. They are quarantined from



fit/select/standardization/thresholding/model selection. The apparent 505/167



combined bank is hypothetical and forbidden; active support remains 385/127



with validation lineage 58/69.







This work also corrects two provenance assumptions. The issue27cb 90,000-row



exact-label audit is invalid because it treated a role-local recorded ordinal



as a processed-CSV row index. The replacement uses unique timestamp matching.



The issue27cc `network-scanning` PCAP was only a scenario-name heuristic; the



selected rows and formal issue27cd chunks map by exact time to the



`mirai-infection` capture, where scan/Telnet are labeled infection stages. See



`ckbr_ckbs_support_v2_and_process_frontend_gate_20260722.md` before any next



training run.







### Maintenance Protocol







- Keep detailed evidence inside each numbered `runs/issue*/` directory.



- Keep this handoff short: current truth, frozen rules, superseded routes, active blocker, and next action.



- Do not append every table or diagnostic detail here. Link or name the source issue instead.



- When an issue changes the mainline, update `Current Mainline Architecture`, `Current Data Contract`, and `Decision Log`.



- When an issue does not change the mainline, record it only as a one-line indexed result in `mainline_experiment_map.md`.



- Every future issue summary should close with:



  - `solved`



  - `changed_mainline: yes/no`



  - `active_blocker`



  - `frozen`



  - `superseded`



  - `next_action`







### Current Mainline Architecture







Status: active, not final benchmark-ready.







Current system route:







```text



Gotham raw PCAP



-> Kitsune / AfterImage / netStat 115D online statistical frontend



-> clean role-specific materialized assets



-> versioned exact-label support memory



-> binary attack head / OOD-risk / temporal evidence / bounded controller



-> larger sanity replay



-> only later: formal benchmark



```







Frozen parts:







- The official Gotham frontend path is PCAP-derived Kitsune-style 115D.



- C1 remains the high-recall attack-candidate anchor; raw mature AfterImage115



  remains the process-evidence control for the next one-sided calibration test.



- The old 8D strict packet-header asset is an engineering smoke/provenance artifact only.



- Final/report-only roles cannot be used for fit, support selection, threshold selection, calibration, model selection, or protocol tuning.



- Data contract cleanliness gates precede model replay.



- The one formal region abstraction is `label_support_region`, bound to a



  human-confirmed exact attack label.



- Ten label-support regions are active for memory management; geometric



  S3/prototype strong/weak results are diagnostic only and cannot route unknown



  traffic or block a confirmed label.



- `support_train_view_v1` contains 385 rows and `support_val_view_v1` contains



  127 immutable validation rows.



- Current issue stage is waiting for the frozen issue27ckc capability replay,



  then certifying a production update budget through a binary-head



  non-regression ablation.







Open parts:







- Exact-label multi-type attack materialization is frozen as a complete-only certified subset; six combined-cycle-1 dev_future_query partial chunks are deferred, not deleted.



- Production online-label storage and durable service integration remain to be



  connected to the frozen archive/candidate schemas.



- Production global/per-region extension caps are intentionally unset until an



  empirical model-update ablation.



- Attack drift, benign OOD drift, conflict/review control, and temporal



  evidence remain detection/controller concerns rather than label-region



  membership gates.







Superseded parts:







- `original-frontend 100D` and earlier April/May few-shot framing remain historical evidence only for this branch.



- Old model wins or collapses from unclean/underspecified split assets are diagnostic only.



- Current 1M attack roles from before issue27cc are not valid for attack detection conclusions until exact-label rematerialization is complete.



- issue27cd partial chunk emissions are not certified query rows; the current mainline does not continue repairing the six partial combined-cycle-1 chunks.



- issue27cf `region_id` values are provenance seeds, not active geometric attack regions.



- Raw global Kitsune115D Euclidean/Mahalanobis medoid regions are not qualified for activation, radius tuning, model replay, or controller use.



- More raw-115D shell tuning or covariance swaps are superseded by the S3 bounded heavy-tail, family-balanced evidence space.



- Geometric `active_strong`, conflict-sensitive, and ambiguous statuses no



  longer define the formal region registry; they remain diagnostic annotations.



- New-capture acquisition is no longer a prerequisite for implementing



  human-label memory management. It remains necessary only for a future claim



  that geometric regions can automatically certify unknown traffic.



- CKBO's deterministic multiscale-contrast representation and symmetric TabM



  attack-versus-benign suppression are rejected for additional seeds.







### Current Data Contract







| Component | Current status | Source issue | Use now |



|---|---|---|---|



| Benign/OOD 1M roles | usable | issue27bz | ID train/calib, OOD val/stress, sealed final OOD remain usable under their role restrictions |



| Attack support/query/final from certified 1M | partially reusable only after exact-label filtering | issue27cb/issue27cc | do not use directly for model replay |



| Exact-label targeted attack plan | ready for Slurm materialization | issue27cc | source contract for issue27cd |



| Exact-label targeted attack chunks | issue27cd pullback partial: 93 complete chunks, 6 deferred partial chunks | issue27cd/issue27cg | source evidence for complete-only certification; partial emissions excluded |



| Certified attack subset v1 | frozen complete-only subset: 683,420 rows from 93 complete chunks; 33,636 planned partial rows excluded including 5,461 emitted rows | issue27ch | development-side protocol replay input under fixed role access; sealed final remains report-only |



| Support-bank protocol/interface | frozen at invariant/interface level | issue27ce | governs initial bank and later update contracts |



| Initial pre-deployment support bank | instantiated from complete exact-label support candidate pool: 512 rows, 10 labels, train/val disjoint | issue27cf | can be used as initial support-bank state for protocol refinement |



| Support-region protocol | historical layer separation between provenance, labels, geometry, and active evidence | issue27ci | retained as governance; formal membership is now the issue27ckg exact-label registry |



| Initial region geometry audit | failed qualification: 0 active-strong, 1 conflict-sensitive, 9 ambiguous; severe OOD overlap and label confusion | issue27cj | diagnostic evidence only; not a formal-region activation gate |



| Evidence-space repair | S3 and later two-medoid results provide geometry diagnostics for known labels | issue27ck/issue27ckd | optional diagnostic annotations only; not unknown-traffic routing or label-memory membership |



| Frozen-bank multi-prototype audit | static capacity gain only: two medoids raise support/OOD qualification from one to two strong candidates, but query-time label/coverage stability blocks registry freeze | issue27ckd | diagnostic candidate only; do not connect the two-medoid registry to the controller |



| Bounded support extension audit | E64 improves historical Mirai GRE attack coverage, but static support evidence is non-material and GRE OOD-stress core+near rises from 0 to about 2.21 percent | issue27cke | exploratory trade-off evidence only; original 512 remains unchanged and no extension is deployment-authorized |



| Fresh two-sided holdout feasibility | local archive has 4 unmaterialized malicious PCAPs and 51 unused benign PCAPs, but zero fresh attack+benign pairs relevant to the current ten regions; one substantial CoAP pair is outside the registry | issue27ckf | do not submit an HPC materialization job from the existing archive for current-region certification |



| Label-support region registry | one exact-label registry with ten active memory-management regions, immutable 385/127 views, append-only archive/candidate schemas, versioned promotion and rollback contracts | issue27ckg | current formal region system; production promotion disabled pending budget/model non-regression certification |



| CKBO auxiliary normal extension | 31 label-free raw-PCAP sources split 11/5/15 fit/select/predictive-report with a separate manifest; permanent canaries and cooler have zero fit/select use | issue27ckbo | reusable only under source/family-held-out one-sided calibration; does not alter the strict 1M or T0 manifests |



| Gotham support-v2 candidates | 160 exact timestamp-aligned city-power rows are quarantined because they occur after the frozen query in the same capture | issue27ckbr/issue27ckbs | diagnostic evidence only; selection false and fit/threshold/model-selection forbidden; active support stays 385/127 |



| ToN-IoT auxiliary process support | separate source-file-disjoint 4,000 fit + 1,000 select scan/password completed-connection rows; independent raw conn/GroundTruth validator PASS | issue27ckbt | static process-expert supervision only; no claim of campaign independence, no Gotham C1/threshold use, and no temporal replay without emission time |







### Active Blocker







`Transferable attack-preserving process evidence is not yet demonstrated`







C1 retains attack-anchor value and CKBQ proves transferable normal rank signal



across all four held families. The unresolved failure is attack preservation:



normal evidence suppresses future attacks that the old support bank never



represented. CKBT now supplies legal mature scan/password connection-process



supervision, but no causal Gotham connection cache or trained process expert



has yet shown that it can rescue those attacks without restoring held OOD



false alarms.







### Current Next Action







Do not rerun CKBO/CKBP/CKBQ or tune against the four report families. CKBT has



closed the independent supervision gate with source-disjoint ToN Bro/Zeek



rows. Next verify an existing Zeek executable/module without installing



anything, record explicit log-emission availability for Gotham, and implement



one small static connection-process expert. Then run one asymmetric seed-27



AMD/Intel result chain with collision-free outputs; no standalone preflight or



audit job.







### Latest Compact Close-out







```text



solved: CKBQ is registered NO_GO; 160 Gotham candidates are quarantined; CKBT independently validates a separate source-file-disjoint 4000/1000 ToN scan/password process-supervision bank.



changed_mainline: yes; attack preservation now uses mature completed-connection mechanism supervision plus causal Gotham process evidence, not another threshold repair.



active_blocker: no Gotham emission-time Zeek cache or asymmetric result yet demonstrates attack rescue plus four-held OOD suppression.



frozen: original strict 1M split, support-v1 hashes, certified query/T0 manifests, permanent report-only canaries, cooler sealed, review=0, and seed27-first policy.



superseded: issue27cb index-based exact-label counts, label-name-only PCAP pairing, CKBO/CKBP/CKBQ extra seeds, and report-family-specific tuning.



next_action: check the existing Zeek module/binary, implement the static process expert and causal Gotham adapter, then prepare one result-producing seed-27 AMD/Intel chain.



```







### Decision Log







| Date | Decision | Source | Status |



|---|---|---|---|



| 2026-06-01 | Formal frontend route moved from strict 8D packet-header to Gotham PCAP-derived Kitsune115. | issue27ab and later control discussion | active |



| 2026-06-14 | Certified 1M benign/OOD asset is usable, but attack roles require exact-label rematerialization. | issue27bz/issue27cb/issue27cc | active |



| 2026-06-14 | Multi-type attack support/query/final must be rebuilt using exact CSV labels and PCAP timestamp matching before model replay. | issue27cc/issue27cd | source contract; complete-only freeze now handled by issue27ch |



| 2026-06-16 | Support-bank protocol/interface invariants are frozen; concrete support indices, budgets, and thresholds remain pending exact-label instantiation. | issue27ce | active |



| 2026-06-16 | Initial support bank instantiated from complete exact-label support pool: 69,492 candidates -> 512 selected rows, no final/report-only access, train/val disjoint. | issue27cf | active support state; protocol definition now blocks replay |



| 2026-06-17 | Certified attack subset v1 frozen from complete chunks only: 683,420 rows; six partial combined-cycle-1 chunks are deferred_not_deleted, including their emitted rows. | issue27ch | active data contract; next protocol issue is issue27ci |



| 2026-06-17 | Support-region protocol v1 frozen: issue27cf provenance seeds are not active attack regions; region instantiation/radius/shell/OOD-overlap audit are deferred to issue27cj. | issue27ci | active protocol; next step is initial_region_registry_v1 |



| 2026-06-18 | Initial region audit failed qualification: no active-strong regions; raw global Kitsune115D geometry is dominated by few dimensions and strongly overlaps benign OOD. | issue27cj | active blocker; repair evidence space before region activation |



| 2026-06-21 | Bounded heavy-tail plus family-balanced S3 repair qualified one Mirai UDP Flooding region; all other regions remain non-strong. | issue27ck | active limited registry; integrate conservatively with unknown/review fallback |



| 2026-06-21 | Two train-only medoids on the unchanged 512 support rows improve static qualification to Mirai GRE plus Mirai UDP, but both expose temporal/query coverage caveats; controller integration is paused. | issue27ckd | diagnostic gain only; bounded support adequacy and temporal-coverage audit next |



| 2026-06-22 | Nested +64/+128 support extension audit finds E64 improves historical GRE attack coverage but offers no material support-val gain and raises GRE OOD-stress intrusion to about 2.21 percent. | issue27cke | no registry freeze; construct a fresh attack and benign-OOD temporal holdout before further comparison |



| 2026-06-22 | Complete Gotham archive audit finds no fresh two-sided pair relevant to the current ten regions; the only substantial unused pair is CoAP, outside the current registry. | issue27ckf | no existing-archive HPC job; design a new Gotham capture or semantically audited second environment |



| 2026-06-22 | One exact-label support-region registry and versioned archive/candidate/update workflow are instantiated; geometry is diagnostic only and production promotion remains disabled. | issue27ckg | active memory-management architecture; wait for issue27ckc, then certify update budgets through detector non-regression |



| 2026-07-15 | CKBO seed 27 validates family-dependent raw AfterImage115 normal evidence but rejects deterministic contrast and symmetric TabM suppression; stream/IP-camera remain near 100% and primary attack recall falls 6.091 pp. | issue27ckbo | no more CKBO seeds; next test is source-held-out one-sided normal-evidence calibration |



| 2026-07-21 | CKBQ produces a real four-held OOD suppression signal but loses 6.945 pp attack recall; exact score-space enumeration finds no compliant threshold pair. | issue27ckbq | no extra seeds; add missing transferable attack-process evidence |



| 2026-07-22 | CKBR/CKBS exactly materialize 160 non-overlapping TCP-Scan/Telnet candidates, then quarantine all because they occur after the frozen query in the same capture; legacy index, label-name PCAP, and row-embargo-only admissibility are rejected. | issue27ckbr/issue27ckbs | NO_GO for Gotham support expansion; active support stays 385/127; audit an independent training source next |



| 2026-07-22 | CKBT freezes 4,000 fit and 1,000 select ToN Bro/Zeek scan/password rows through unique time+5-tuple GroundTruth joins; fit/select source files are disjoint and seven sources remain unused. | issue27ckbt | legal auxiliary static process supervision; no campaign-independence claim; temporal replay forbidden until explicit emission time exists |







---







## Historical Archive Begins Below







The following sections are preserved from earlier mainline handoff revisions.



They do not override the `Current Mainline Control Panel`.







Updated: 2026-05-08



Workspace: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline`



Branch: `codex/exp-mainline`



Canonical path: `runs/mainline_docs/mainline_handoff.md`







Maintenance rule:



- Keep this as the single living mainline handoff.



- Append stable updates in time order inside this file.



- Do not create dated handoff copies for mainline.







## Scope







This file is the time-ordered handoff for the A-line main experiment only.







- Record only A-line mainline work.



- Record what was done, what the result was, what the current blocker is, and what should happen next.



- Exclude `frontend_f2_*` and any other branch-line exploration.



- Exclude merge and worktree management.







## Fixed Mainline Protocol







- Feature frontend: `original-frontend 100D`



- Main problem setting: stronger benign OOD under the formal frontend100 protocol



- Primary attack metric: Stage2 high-purity attack detection



- Required operating points:



  - `fixed_id_q99`



  - `naive_calibrated_budget5000_target1pct`



  - `det_floor_50pct_min_alarm`



- Rule: all scalers, thresholds, centers, covariance estimates, and calibration statistics must be fit only on ID benign data







## Current Status







- Latest framing note: see `2026-05-08 Strategy Update` below. The current candidate direction is base-detector-agnostic guarded few-shot adaptation, but this is a next-phase proposal, not a completed experiment or current paper claim.



- The project is no longer in "close the draft quickly" mode. It has been reclassified into the A-tier strengthening stage.



- Phase 1 is complete: problem definition, main pathology localization, main candidate screening, external baseline supplements, and one round of deployability diagnosis are already in place.



- The current A-line gap is no longer "find any Transformer win." The gap is to complete the evidence package that makes the mainline argument defensible at A-tier standard.







## Current Main Blockers







1. Modern tabular baseline evidence is not complete yet. `FT-Transformer` has only finished a local smoke and has not yet been promoted into a full formal comparison package.



2. Second-dataset or second-environment self-validation is still missing.



3. Adversarial robustness evaluation is still missing.



4. Deployability closure is incomplete. The ensemble candidate is useful evidence, but a clean single-model replacement has not been established.







## Current Next Step







- Continue the A-line baseline-strengthening package under the existing `original-frontend 100D` protocol.



- First priority is to convert the `FT-Transformer` smoke path into a formal A-line run with the standard tables and cost summary.



- If the FT line remains non-threatening after formalization, keep the scope tight and decide whether `RTDL-ResNet` is still necessary.







## Time Log







### 2026-05-22 (Issue26a Within-Dataset Temporal Feasibility Inventory)







What was done:



- Completed `runs/issue26a_within_dataset_temporal_validation_for_enhanced_lowguard_top64_2026-05-22/`.



- Scope was within-dataset temporal / data-scale feasibility and leakage audit only.



- No dA/Transformer training, no topK/support/adapter/threshold change, and no manuscript edit.



- Read issue25c strong baseline outputs, issue23 locked validation assets, issue22/22b discovery and non-regression summaries, and current mainline docs.







Result:



- Preflight passed for inventory.



- issue25c remains `strong_baseline_positive` for frozen Enhanced LOW-GUARD+ top64.



- Existing evidence was separated into:



  - `primary_lowood`: primary / non-regression evidence.



  - `holdout_bin_2`: hard-shift discovery evidence, not clean future proof.



  - `chrono_late_train_early_eval`: temporal-looking consistency evidence, but already involved in candidate confirmation.



  - locked bins `5/6/7/8`: valid same-dataset locked evidence from issue23 and issue25c, but not new temporal proof.



- No clean P0/P1 temporal candidate with low leakage risk was found.



- Best partial candidate is `chrono_early_train_late_eval`, but it overlaps issue23/25c locked eval bins `6/7/8` and needs purge/embargo plus metadata recovery before formal validation.



- Minimal new temporal validation was not run.







Judgment:



- issue26a strengthens evidence-chain hygiene, not the main temporal claim.



- It should be cited as feasibility / audit / planning evidence only.



- Do not write that issue26a proves temporal generalization or replaces second-environment validation.







Next:



- Unique next action: `issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22`.



- Recover raw timestamp / packet-order / attack-bin provenance, define a purged or embargoed future-window split, and only then decide whether formal issue26b validation can run.



- Keep second environment as later issue27, not this round's immediate next step.







### 2026-05-22 (Issue26b Split Metadata Recovery + Temporal Asset Build)







What was done:



- Completed `runs/issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22/`.



- Scope was metadata recovery, split provenance reconstruction, temporal asset candidate rebuild, and purge/embargo planning only.



- No formal temporal validation, no model training, no topK/support/adapter/threshold change, no second-environment reopening, and no manuscript edit.



- Scanned issue26a handoff assets, issue22/22b/23/25c provenance and locked-asset reports, issue18 row-level score persistence assets, and current mainline docs.







Result:



- Preflight passed for metadata recovery.



- Coarse attack-bin provenance was recovered for `primary_lowood`, `holdout_bin_2`, `chrono_late`, locked bins `5/6/7/8`, and the partial `chrono_early_train_late_eval` candidate.



- Support provenance remains clean at the inspected level: selected support rows are recorded as coming from attack train pools and not from attack eval / final OOD eval.



- Threshold provenance remains clean at the inspected level: thresholds use ID calibration + OOD validation, not final OOD / attack eval.



- Raw timestamp, packet-order, capture/session boundary, window_start/window_end, and bin-to-clock-time metadata were not recovered.



- No clean formal temporal candidate was found. `earlier-to-later` remains only a partial/planning candidate because eval bins `6/7/8` overlap issue23/25c locked evidence.



- A metadata-only split smoke was completed; it checked bin-definition wiring only and did not train models or select thresholds.







Judgment:



- issue26b improves evidence-chain hygiene and makes the temporal blocker explicit.



- It does not strengthen the temporal-generalization claim.



- Reusing issue23/25c locked bins must remain consistency or repeated-evidence analysis, not new temporal proof.







Next:



- Unique next action: `issue26c_temporal_metadata_recovery_followup_or_second_environment_feasibility`.



- First try to recover raw timestamp / packet-order / capture-level metadata or a genuinely unused future-window manifest.



- If that remains impossible, keep within-dataset formal temporal validation blocked and move to a carefully scoped issue27-level second-environment feasibility path rather than tuning the method.







### 2026-05-22 (Issue27a Deployment Feasibility + Guarded Training Protocol Audit)







What was done:



- Completed `runs/issue27a_deployment_feasibility_and_guarded_training_protocol_audit_2026-05-22/`.



- Scope was deployment-facing protocol audit and reviewer-defense planning only.



- No model training, no cross-dataset validation, no temporal validation, no topK/support/adapter/threshold change, no second-environment reopening, and no manuscript edit.



- Converted issue25c locked OOD alarm results into deployment workload language and audited support/benign-OOD guard assumptions.







Result:



- Primary verdict: `deployment_protocol_plausible_needs_robustness_simulation`.



- Secondary verdict: `lowguard_should_be_framed_as_guarded_adaptation_protocol`.



- LOW-GUARD should be written as a guarded few-shot adaptation protocol; the current LR head should be named/positioned as `LOW-GUARD-LR`, a minimal deployable instance.



- Main method locked OOD max `0.0045` corresponds to about 45 alarms per 10k OOD events, under the official 1% low-alert budget.



- Strong alternatives such as DevNet-like and random32 remain deployment-risky under the official budget because their locked OOD max exceeds 1%.



- Deployment assumptions are plausible but conditional: high-purity supports and benign-OOD guard samples need provenance, delayed confirmation, and contamination checks.







Judgment:



- issue27a strengthens claim framing, not performance evidence.



- It does not prove live SOC deployment, temporal generalization, or external generalization.



- Fully autonomous self-training remains outside scope.







Next:



- Unique next action: `issue27b_deployment_robustness_simulation_for_lowguard_top64_2026-05-22`.



- Prioritize shot sensitivity, support-noise stress, OOD-benign contamination stress, support-source comparison, label-delay if metadata permits, and shadow-mode workload evaluation.



- Do not prioritize adapter upgrades until deployment robustness reveals a concrete failure mode.







### 2026-05-26 (Issue27b Guarded Protocol Transfer + Adapter Recovery)







What was done:



- Completed `runs/issue27b_guarded_protocol_transfer_and_adapter_recovery_2026-05-26/`.



- Ran a frozen locked-bin protocol-transfer matrix on holdout bins `5/6/7/8` with seeds `42..51`.



- Frozen conditions were preserved: selected source-rich top64, kcenter32 supports, locked split protocol, 1% OOD alarm target, final eval report-only, no dA/Transformer training, no temporal or cross-dataset validation, and no manuscript edit.



- Evaluated LR reference, DevNet-like MLP, HistGB shallow, DeepSAD-like center, Prototype/metric LR, and optional RFF Logistic under P0/P1/P2/P3 protocol variants.







Result:



- Primary verdict: `nonlinear_detection_gain_not_low_alert_feasible`.



- LOW-GUARD-LR P3 exactly reproduces issue25c locked mean/min/OOD max: `0.949705 / 0.882629 / 0.004500`.



- Best non-LR full LOW-GUARD head is DevNet-like MLP with locked mean/min/OOD max `0.947497 / 0.895305 / 0.010100` and feasible rate `0.975000`.



- No non-LR adapter met the LOW-GUARD++ dominance rule.



- DevNet-like remains detection-competitive but just exceeds the 1% OOD budget, so it is not a low-alert replacement for LOW-GUARD-LR under the official protocol.



- HistGB, DeepSAD-like, Prototype/metric LR, and RFF Logistic do not provide a stronger feasible instance.







Interpretation:



- The protocol framing remains useful, but broad adapter-transfer should not be overclaimed.



- LOW-GUARD-LR remains the current strongest feasible minimal instance.



- For LOW-GUARD-LR, training-side OOD guard is the decisive recovery mechanism: raw LR detects attacks but badly violates OOD alarm, while threshold-only raw LR becomes feasible by collapsing attack detection.



- The threshold guard remains necessary as a deployment safety gate because it enforces ID+OOD validation alarm control.







Current claim boundary:



- Allowed: current evidence supports LOW-GUARD-LR as the strongest feasible minimal instance under the locked low-alert protocol.



- Allowed: nonlinear heads can be diagnostic and detection-competitive, but low-alert feasibility is not automatic.



- Not allowed: LOW-GUARD works for all adapters, DevNet/DeepSAD are generally defeated, temporal generalization is proven, cross-dataset generalization is proven, or deployment robustness is proven.







Next:



- Unique next action: `issue27c_deployment_robustness_simulation_for_lowguard_lr`.



- Prioritize shot sensitivity, support-noise, OOD benign contamination, support-source comparison, and shadow-mode workload simulation.



- Do not expand the adapter space unless a concrete deployment robustness failure motivates it.







### 2026-05-26 (Issue27c LOW-GUARD Mechanism Falsification + Head Specificity Audit)







What was done:



- Completed `runs/issue27c_lowguard_mechanism_falsification_and_head_specificity_audit_2026-05-26/`.



- Scope was mechanism audit and falsification planning only.



- No deployment robustness simulation, no temporal validation, no cross-dataset validation, no topK/support/threshold change, no dA/Transformer training, and no manuscript edit.



- Reused issue27b frozen artifacts and ran a bounded score-tail / threshold-curve audit for LR, DevNet-like, HistGB, and DeepSAD-like on locked bins `5/6/7/8`.







Result:



- Primary verdict: `lowguard_lr_success_mechanistically_supported`.



- Secondary verdicts:



  - `representation_linearization_explains_lr_advantage`;



  - `lowguard_effect_head_specific_lr_only_so_far`;



  - `non_lr_results_inconclusive_due_to_proxy_implementation`.



- LR has a clean P0/P1/P2/P3 mechanism pattern:



  - raw LR detects attacks but badly violates OOD alarm;



  - threshold-only LR controls OOD by collapsing attack detection;



  - OOD-guarded training preserves detection while suppressing OOD tail;



  - full LOW-GUARD adds the validation safety gate.



- No direct final-eval leakage or protocol bug was found.



- Non-LR heads did receive OOD_train guard, but their score tails / proxy objectives did not produce a stronger low-alert instance.



- DevNet-like and DeepSAD-like remain proxy implementations, so their failures must not be written as general method defeats.







Interpretation:



- Directly moving from issue27b to deployment robustness would be a premature close.



- LOW-GUARD can still be discussed as a guarded adaptation protocol, but empirical performance claims should center on LOW-GUARD-LR unless broader transfer is later validated.



- top64 may have linearized the task in a way that favors LR; representation-vs-head causality is not fully resolved.







Current claim boundary:



- Allowed: LOW-GUARD-LR is the strongest feasible demonstrated instance, and its recovery mechanism is supported by P0/P1/P2/P3 evidence.



- Allowed: LR success appears linked to source-rich top64, OOD-guarded training, and validation-only thresholding.



- Not allowed: LOW-GUARD works for all heads, nonlinear adapters are useless, DevNet/DeepSAD are defeated, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.







Next:



- Unique next action: `issue27d_bounded_representation_and_objective_falsification_for_lowguard_lr_specificity`.



- Run a small original100-vs-top64 / LR-vs-DevNet-like-vs-HistGB control matrix.



- Do not widen the adapter zoo or move to deployment robustness until representation/head specificity is bounded.







### 2026-05-26 (Issue27d LOW-GUARD Adapter Interface + Model-Specific Objective Smoke)







What was done:



- Completed `runs/issue27d_lowguard_adapter_interface_and_model_specific_objectives_smoke_2026-05-26/`.



- Implemented a common LOW-GUARD adapter interface with `fit`, `score`, `calibrate`, `evaluate`, and `metadata`.



- Ran a bounded smoke over locked bins `5/6/7/8`, seeds `42/43/44`, representations `source_rich_top64` and `original100`, and heads `LOW-GUARD-LR`, `DevNetScore`, `DeepSADLite`, `HistGB-Conservative`, and `PrototypeMargin`.



- Preserved final-eval exclusion: OOD validation and support validation were used for selection; final OOD eval and attack eval were report-only.



- No temporal validation, cross-dataset validation, deployment robustness simulation, dA/Transformer training, or manuscript edit was performed.







Result:



- Primary verdict: `lowguard_plus_plus_candidate_found_with_model_specific_objective`.



- Stage A interface preflight passed.



- LOW-GUARD-LR on top64 exactly reproduced the issue25c reference in this smoke: locked mean/min/OOD max `0.949705 / 0.882629 / 0.004500`.



- No top64 non-LR head dominated LOW-GUARD-LR. Best top64 non-LR was `LOW_GUARD_HistGB_Conservative` with `0.659751 / 0.040689 / 0.006600`.



- A representation-control LOW-GUARD++ candidate appeared on `original100`: `LOW_GUARD_HistGB_Conservative` reached `0.994261 / 0.978091 / 0.005100` with feasible rate `1.000000`.



- Model-specific-lite objectives improved transfer for some non-LR heads relative to issue27b proxies, but DevNetScore did not improve over the old DevNet-like MLP.







Interpretation:



- This is not a main-method replacement yet. The candidate uses `original100`, while the current frozen main method uses `source_rich_top64`.



- The result is scientifically important because it challenges the idea that top64 plus LR is the only viable route; top64 may favor a linear LR boundary while original100 leaves room for a conservative nonlinear head.



- The framework/protocol direction should stay alive, but only with explicit model-specific objectives and formal validation.







Current claim boundary:



- Allowed: issue27d establishes an auditable adapter interface and identifies a representation-control LOW-GUARD++ candidate for formal validation.



- Allowed: LOW-GUARD-LR remains the strongest demonstrated top64 minimal instance.



- Not allowed: LOW-GUARD++ is proven, the main method has been replaced, LOW-GUARD works for all heads, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.







Next:



- Unique next action: `issue27e_formal_validation_for_lowguard_plus_plus`.



- Formally validate `LOW_GUARD_HistGB_Conservative` on `original100` with the full locked seed budget and the same final-eval exclusion rules before considering any main-method change.







### 2026-05-27 (Issue27e LOW-GUARD++ Candidate Freeze Audit)







What was done:



- Completed `runs/issue27e_formal_validation_for_lowguard_plus_plus_original100_histgb_conservative_2026-05-26/`.



- Scope was the formal-validation gate for the `original100 + LOW_GUARD_HistGB_Conservative` LOW-GUARD++ candidate.



- Read issue27d smoke outputs, selection trace, leakage audit, issue27c/25c summaries, issue23 locked asset report, and mainline docs.



- No full locked-seed final-eval run was executed because Stage A candidate config recovery failed.







Result:



- Primary verdict: `candidate_config_not_recoverable_needs_debug`.



- issue27d original100 HistGB-Conservative did not yield one unique frozen config:



  - `histgb_d2_lr003_l2p0_ood4_sup2_t0100` selected 7/12 smoke bin-seed combinations.



  - `histgb_d2_lr005_l2p1_ood4_sup4_t0050` selected 5/12 smoke bin-seed combinations.



- issue27e stopped before full locked validation to avoid hindsight config selection.



- No issue27e final-eval leakage occurred because final OOD / attack eval were not run for the candidate.







Interpretation:



- This does not invalidate the original100 HistGB candidate. It means the candidate is not yet a single frozen method instance.



- The smoke result should be treated as a selection-policy / aggregate candidate, not a formal LOW-GUARD++ validation result.



- LOW-GUARD-LR remains the demonstrated stable minimal instance.







Current claim boundary:



- Allowed: original100 + HistGB-Conservative remains a serious LOW-GUARD++ candidate that needs config-freeze recovery.



- Not allowed: LOW-GUARD++ is formally validated, the main method has been replaced, HistGB universally dominates LR, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.







Next:



- Unique next action: `issue27f_candidate_config_freeze_and_formal_validation_for_original100_histgb_conservative`.



- Freeze exactly one HistGB-Conservative config using only support-validation / OOD-validation trace evidence and pre-registered simplicity/low-alert rules, then run the full locked seeds.







### 2026-05-27 (Issue27f Config Freeze + Formal LOW-GUARD++ Validation)







What was done:



- Completed `runs/issue27f_config_freeze_then_formal_validation_for_original100_histgb_conservative_2026-05-27/`.



- Froze one `original100 + HistGB-Conservative` config using only train/cal/validation-side evidence from issue27d.



- Frozen config: `histgb_d2_lr005_l2p1_ood4_sup4_t0050`.



- Ran full locked seed validation over seeds `42..51` and locked bins `5/6/7/8`.



- Re-ran LOW-GUARD-LR top64 reference in the same output schema.



- No deployment robustness, temporal validation, cross-dataset validation, representation search, new model search, or manuscript edit was performed.







Result:



- Primary verdict: `lowguard_plus_plus_formal_validated`.



- LOW-GUARD++ formal locked mean/min/OOD max: `1.000000 / 1.000000 / 0.000100`.



- LOW-GUARD-LR top64 reference locked mean/min/OOD max: `0.949705 / 0.882629 / 0.004500`.



- LOW-GUARD++ dominates LOW-GUARD-LR on locked mean, locked min, and OOD max under the locked protocol.



- Feasible rate is `1.000000`.



- No seed/bin collapse was observed; every locked bin had detection mean/min `1.000000` and OOD max `0.000100`.



- Threshold target robustness remained strong:



  - target `0.0050`: `1.000000 / 1.000000 / 0.000100`;



  - target `0.0075`: `1.000000 / 1.000000 / 0.000100`;



  - target `0.0100`: `1.000000 / 1.000000 / 0.008300`.



- No final-eval leakage or support/eval overlap was found.







Interpretation:



- The paper mainline can now use a dual-instance story:



  - `LOW-GUARD-LR` as the minimal stable instance under source-rich top64;



  - `LOW-GUARD++` as the performance-oriented instance: original100 + HistGB-Conservative with frozen config.



- This supports a model-specific guarded objective interpretation, not a claim that every head works.







Current claim boundary:



- Allowed: LOW-GUARD++ is formally validated for `original100 + HistGB-Conservative` under the locked low-alert protocol.



- Allowed: LOW-GUARD-LR remains the minimal stable instance.



- Not allowed: HistGB universally dominates LR, LOW-GUARD works for all models, deployment robustness is proven, temporal generalization is proven, or cross-dataset generalization is proven.







Next:



- Unique next action: `issue27g_deployment_robustness_for_lowguard_lr_and_lowguard_plus_plus`.



- Run support-count, support-noise, OOD-contamination, support-source, and shadow-mode robustness for both LOW-GUARD-LR and LOW-GUARD++ before widening claims.







### 2026-04-08







What was done:



- Completed the covariance-aware final candidate audit and the surrounding no-retrain diagnostics on the formal stronger-OOD mainline.



- Main related runs include:



  - `runs/frontend100_final_candidate_audit_2026-04-08/`



  - `runs/frontend100_diagload_gate_multiseed_2026-04-08/`



  - `runs/frontend100_conditional_gate_multiseed_2026-04-08/`



  - `runs/frontend100_external_baselines_2026-04-08/`



  - `runs/frontend100_recurrent_deep_baselines_2026-04-08/`







Result:



- The main pathology was pinned down as latent covariance tail instability rather than complete loss of attack-separation signal.



- Covariance-aware scoring and ensemble logic improved the Transformer family in the operating region that matters, but they did not close the whole paper-readiness gap by themselves.







Judgment:



- Covariance-aware logic is real signal, not a scoring artifact.



- The project had enough evidence to move from local debugging into formal evidence packaging.







Next:



- Add stronger external references, deployment/cost evidence, and paper-facing consolidation.







### 2026-04-09







What was done:



- Added stronger external and deployment-side evidence:



  - `runs/frontend100_deep_svdd_baseline_2026-04-09/`



  - `runs/frontend100_runtime_benchmark_2026-04-09/`



  - `runs/frontend100_additional_ood_setting_smoketest_2026-04-09_b/`



  - `runs/frontend100_additional_ood_setting_smoketest_2026-04-09_c/`







Result:



- `Deep SVDD` confirmed that a modern deep one-class baseline can drive detection high while still failing badly on fixed false alarms under stronger benign OOD.



- Runtime and throughput evidence became available for the main candidate relative to the existing references.







Judgment:



- This strengthened the main claim that stronger benign OOD is an operating-region problem, not just an AUC comparison problem.



- `Deep SVDD` is useful as a negative baseline, not as a new mainline method candidate.







Current blocker after this step:



- Even with the extra evidence, the project still lacked a complete A-tier package: modern tabular baselines, cross-environment self-validation, adversarial evaluation, and a cleaner deployability story.







Next:



- Keep strengthening the evidence package instead of opening another unconstrained method branch.







### 2026-04-11







What was done:



- Completed `runs/frontend100_ensemble_distillation_v1_2026-04-11/`.







Result:



- Distillation v1 learned bulk teacher-score structure but failed to preserve the teacher's fixed operating-point behavior.



- Teacher remained strong at the target operating point, while the distilled head lost too much fixed detection.







Judgment:



- Distillation v1 cannot be promoted to the A-line main candidate.



- If distillation is revisited later, it must be a tail-aware v2 rather than another generic regression-style imitation.







Next:



- Do not spend A-line time on ordinary distillation v1 variants.



- Treat deployability as an evidence gap to be closed after the baseline and robustness packages, not before.







### 2026-04-12







What was done:



- Reclassified the project into the A-tier strengthening stage and fixed the official execution order in `runs/mainline_docs/mainline_experiment_map.md`.







Result:



- The project status changed from "close the current draft" to "expand into a system paper with stronger evidence."



- The enforced execution order became:



  1. baseline strengthening



  2. second-dataset or second-environment minimal validation



  3. adversarial robustness evaluation



  4. deployability and cost closure



  5. tail-aware distillation v2







Judgment:



- The immediate priority is not another broad method search.



- The immediate priority is to reduce reviewer attack surface on baseline strength, external validity, robustness, and deployment realism.







Current blocker after this step:



- The plan was fixed, but the first item in the queue still needed a clean modern-tabular execution path.







Next:



- Start the modern tabular baseline package with `FT-Transformer` first.







### 2026-04-13







What was done:



- Completed `runs/frontend100_modern_tabular_baselines_ft_smoke_2026-04-13/`.







Result:



- The `FT-Transformer` autoencoder smoke path ran successfully on the formal A-line input protocol.



- Single-seed local smoke showed weak fixed performance:



  - `q99 ~ alarm 0.4935 / det 0.8064`



  - `q995 ~ alarm 0.2667 / det 0.6970`







Judgment:



- The modern tabular baseline script is now operational.



- The initial signal suggests that this line does not currently threaten the strongest A-line candidate.



- This is only a smoke result, not yet formal evidence. It still needs the standard A-line reporting package before the baseline-risk question is considered closed.







Current blocker after this step:



- The modern tabular baseline evidence is still not in full formal form.







Next:



- Promote `FT-Transformer` from smoke to formal A-line evaluation with the standard operating-point table and cost summary.



- Only consider `RTDL-ResNet` if the formal FT result leaves residual baseline-risk concerns.







### 2026-04-14







What was done:



- Fixed the ownership boundary for this conversation: it is now the A-line experiment execution thread plus the A-line mainline handoff maintainer.



- Added A-line artifact path resolution so generated experiment outputs default to the D-drive mainline worktree while tracked handoff and map files remain in the current worktree.



- Patched the current A-line baseline infrastructure to use that routing:



  - `repo/paths.py`



  - `repo/ood/stage1_probe.py`



  - `repo/ood/frontend100_modern_tabular_baselines.py`



  - `repo/ood/frontend100_deep_svdd_baseline.py`



  - `repo/ood/frontend100_external_baselines.py`



  - `repo/ood/frontend100_runtime_benchmark.py`



  - `repo/ood/frontend100_additional_ood_setting_eval.py`



  - `repo/ood/frontend100_recurrent_deep_baselines.py`



- Fixed the A-line HPC usage rule:



  - Use HPC for long formal training, multi-seed runs, sweeps, second-dataset validation, larger external-baseline reproduction, and other non-smoke workloads.



  - Do not use HPC for script/path fixing, local smoke checks, offline rescoring, or table/plot collation.



  - Formal HPC runs must follow the sequence: local smoke first, then freeze code/config, ensure portable paths, prepare stable output names plus bundle/return layout, then submit and monitor logs.



- Fixed the `FT-Transformer` formal baseline HPC blocker:



  - corrected `stage2` source TSV resolution for Windows-style manifest paths inside bundled Linux runs;



  - added `--stage2-indices-json` support to the modern-tabular baseline script so formal FT runs can consume precomputed high/mixed indices without reopening the raw TSV on the cluster;



  - added a reusable `prepare_frontend100_modern_tabular_hpc.py` bundle builder;



  - refreshed `runs/frontend100_modern_tabular_baselines_ft_2026-04-13/` with a new `job.slurm`, new `upload_bundle.tar.gz`, and stable watch files.



- Fixed the FT HPC logging protocol:



  - job stdout/stderr is now mirrored into both `slurm-<jobid>.out/.err` and `stdout.log/stderr.log`;



  - submit commands now create `latest_slurm.out`, `latest_slurm.err`, and `last_job_id.txt` in the run directory so status can be opened directly in the remote file tree without running `tail -f`.



- Fixed the Windows PowerShell submit command issue:



  - the generated SSH submit sequence is now PowerShell-safe and no longer uses a local double-quoted `JOB_ID=$(...)` pattern that gets expanded on Windows before reaching the remote shell;



  - bundle pull-back is explicitly separated from submission and should only be run after the remote job has finished and the package file exists.



- Reset the FT formal rerun onto a fresh date-stamped run tag:



  - `frontend100_modern_tabular_baselines_ft_2026-04-13` remains the failed earlier attempt;



  - the corrected formal rerun package is now prepared under `frontend100_modern_tabular_baselines_ft_2026-04-14`.



- Pulled back the first real `2026-04-14` FT rerun failure signal from the cluster:



  - `latest_slurm.out` showed the wrapper itself was healthy and the Python command exited immediately with status `1`;



  - `latest_slurm.err` showed the real cause was import-time failure inside `repo/paths.py`, not FT training instability:



    - bundled cluster Python is `3.9`;



    - `repo/paths.py` still used runtime-evaluated `str | None` style annotations;



    - the bundled run directory is not a git checkout, so the artifact-path resolver also needs a no-git fallback.



- Fixed the FT formal rerun compatibility blocker in mainline code:



  - backported `repo/paths.py` to Python `3.9`-safe typing (`Optional[...]`, `List[...]`, `Tuple[...]`);



  - made `repo/paths.py` skip git worktree probing when `.git` metadata is absent;



  - made the git helper suppress stderr noise and honor `REMOTE_PROJECT_ROOT` when resolving artifact roots in bundled HPC runs;



  - rebuilt `frontend100_modern_tabular_baselines_ft_2026-04-14/` so the refreshed upload bundle now contains the fixed `repo/paths.py`.







Result:



- This file is now the single handoff entry for A-line time-ordered progress.



- From the current Codex mirror workspace, A-line generated runs now resolve to `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs`.



- This reduces C-drive pressure without redirecting tracked mainline docs into another working tree.



- A-line now has an explicit rule for when a task should stay local and when it should be escalated to HPC.



- The FT formal run package is now refreshed and locally validated against the bundled `source_root` layout.



- The first `2026-04-14` FT rerun did not fail in training; it failed before execution because the bundle still contained a Python `3.9`-incompatible `repo/paths.py`.



- The refreshed `2026-04-14` upload bundle now matches the cluster Python requirement and should clear that immediate import-time exit.



- The current environment still cannot submit to `school-hpc` non-interactively, so actual re-upload and re-submission remain a user-side action.







Judgment:



- From this point onward, only stable A-line nodes should be added here.



- A-line should treat D-drive artifact routing as the default execution mode for new formal runs.



- HPC is the default for formal heavy A-line experiments, but only after local smoke and packaging stability are both confirmed.



- The mainline blocker is no longer an unknown FT crash. The immediate blocker has been narrowed to re-uploading the refreshed `2026-04-14` bundle and checking whether the cluster then reaches real training.







Next:



- Continue the baseline-strengthening package and update this handoff after each stable A-line node.



- Use the new default D-drive routing when promoting `FT-Transformer` from smoke to formal baseline evaluation.



- When `FT-Transformer` formal evaluation is ready, decide explicitly whether it is still local or should go to HPC using the rule above.



- Re-upload and re-submit `frontend100_modern_tabular_baselines_ft_2026-04-14` using the refreshed bundle and inspect `latest_slurm.out` / `latest_slurm.err` directly in the remote run directory.



- After FT formal results return, decide whether `RTDL-ResNet` still needs a formal 3-seed run or can stay at smoke status.







### 2026-04-17







What was done:



- Pulled back the completed formal HPC result for `runs/frontend100_modern_tabular_baselines_ft_2026-04-14/`.



- Verified the run finished successfully on the cluster:



  - job id: `14459`



  - node: `node185`



  - status: Python command exited `0`



  - returned artifacts include `modern_tabular_results.csv`, `modern_tabular_aggregate.csv`, `modern_tabular_costs_aggregate.csv`, `modern_tabular_summary.md`, `stdout.log`, `stderr.log`, and the packaged return bundle.



- Read the formal FT aggregate under the stronger-OOD mainline protocol and compared it against frozen A-line references.







Result:



- `FT-Transformer AE` is now formally negative as an A-line threat under the operating points that matter.



- Key aggregate result at `fixed_id_q995`:



  - `ft_transformer_ae`: `ood_alarm_ratio_eval_mean = 0.767333`, `attack_detection_high_purity_mean = 0.928201`, `roc_auc_attack_high_vs_ood_eval_mean = 0.754077`



  - `transformer_ensemble_main_candidate`: `ood_alarm_ratio_eval_mean = 0.126067`, `attack_detection_high_purity_mean = 0.844419`, `roc_auc_attack_high_vs_ood_eval_mean = 0.878093`



  - `dA fixed_id_q0p995`: `ood_alarm_ratio_eval_mean = 0.104489`, `attack_detection_high_purity_mean = 0.769029`, `roc_auc_attack_high_vs_ood_eval_mean = 0.809622`



- Interpretation of the formal FT result:



  - FT can push attack detection high, but only by letting stronger benign OOD alarms explode.



  - Under the fixed `0.5%` ID operating point, FT fires on about `76.7%` of eval OOD, which is far outside the acceptable deployment region.



  - Under `naive_calibrated_budget5000_target1pct`, FT holds eval OOD alarm near `1.49%`, but high-purity attack detection collapses to about `0.00044`, so it does not offer a credible operating-point alternative.



  - Under `det_floor_50pct_min_alarm`, FT still needs about `10.19%` eval OOD alarm to hold `~50%` high-purity detection, again not competitive with the mainline references.



- Seed behavior is stable enough for the conclusion:



  - all three FT seeds show the same qualitative failure mode rather than one bad run.



- Cost note:



  - checkpoint size is about `1.12 MB`



  - parameter count is `275,364`



  - mean training time is about `1934.47 s` on CPU



- Residual logging issue:



  - the returned `stderr.log` still contains a benign `git rev-parse HEAD` failure because the remote bundle root is not a git checkout; this did not affect training correctness but should be cleaned in the job wrapper later.







Judgment:



- The FT formal package closes the mainline question of whether this modern tabular baseline materially threatens the stronger-OOD covariance-tail story. It does not.



- FT should not receive more A-line optimization time unless a very specific paper-facing criticism requires a targeted rebuttal.



- `RTDL-ResNet` no longer looks mandatory as a full formal 3-seed run. It can remain optional unless we decide we need one extra modern-tabular reference for presentation completeness.







Next:



- Keep the A-line scope tight and do not spend another cycle tuning FT.



- Treat the modern-tabular baseline-risk item as substantially closed by this formal FT result plus the already available external/deep baseline evidence.



- Use the saved A-line budget on the next blocker in the fixed order:



  1. second-dataset or second-environment minimal validation



  2. adversarial robustness evaluation



  3. deployability and cost closure







### 2026-04-17 (Formal HPC SOP Fixed)







What was done:



- Fixed the A-line formal HPC operating book for all future official cluster runs.



- Locked the usage boundary:



  - local smoke first, formal cluster run second;



  - HPC is for formal training, multi-seed runs, sweeps, second-dataset or second-environment validation, formal baseline reproduction, and other long CPU/GPU jobs;



  - HPC is not for path fixing, script fixing, bundle fixing, offline rescoring, plotting, table collation, or ambiguous not-yet-worthy runs.



- Locked the formal naming rule:



  - every formal cluster task must use a fresh `run_tag` with format `task_name_YYYY-MM-DD`;



  - reruns must switch to a new date;



  - local run path is fixed to `runs/<run_tag>/`;



  - remote project root must also be date-stamped;



  - remote formal run path is fixed to `<remote_project_root>/runs/<run_tag>/`;



  - return bundle path is fixed to `package/<run_tag>_bundle.tar.gz`.



- Locked the pre-submit freeze set:



  - `command.txt`



  - `config.json`



  - `run_spec.json`



  - `job.slurm`



  - `upload_bundle.tar.gz`



  - explicit return-bundle path



  - if these are not frozen in the run directory, the task is not allowed onto HPC.



- Locked the formal submission order:



  1. create remote directories by `ssh`



  2. upload `upload_bundle.tar.gz` by `scp`



  3. unpack remotely



  4. run `sbatch job.slurm` inside the remote run directory



  5. auto-create `latest_slurm.out`, `latest_slurm.err`, and `last_job_id.txt`



  6. after completion, pull back `package/<run_tag>_bundle.tar.gz`



  7. unpack locally and verify completeness before any handoff update



- Locked the remote logging rule:



  - the remote run directory must always expose `latest_slurm.out`, `latest_slurm.err`, `stdout.log`, and `stderr.log` directly in the file tree;



  - status inspection should default to opening those files directly, not to ad hoc `tail -f`;



  - program stdout/stderr must be mirrored into both Slurm files and `stdout.log` / `stderr.log`;



  - submission must auto-record `last_job_id.txt`, `latest_slurm.out`, and `latest_slurm.err`;



  - a `job_info.json` or equivalent manifest is recommended to store `job_id`, `job_name`, `node_list`, `submit_dir`, `python_bin`, `stdout_log`, and `stderr_log`.



- Locked the `job.slurm` minimum wrapper metadata:



  - `[start]`



  - `[run_dir]`



  - `[python]`



  - `[command]`



  - `[command_exit]`



  - `[bundle]`



  - `[finish]`



- Locked the PowerShell rule:



  - generated `ssh` / `scp` / `sbatch` commands must be copy-run safe under Windows PowerShell;



  - do not emit commands that require manual quoting repair or accidental local variable expansion.



- Locked the return-bundle completeness rule:



  - `summary`



  - `results`



  - `diagnostics`



  - `config`



  - `stdout.log`



  - `stderr.log`



  - `job_info` or equivalent run manifest



- Locked the post-return action order:



  1. verify `summary`, `results`, `diagnostics`, and logs



  2. update mainline handoff



  3. update mainline experiment map



  4. commit and push



  - if the result is invalid, record failure reason, fix point, and whether a fresh-date rerun is required.







Result:



- A-line now has a fixed formal HPC contract rather than a case-by-case submission habit.



- Future cluster submissions should be easier to audit, easier to resume, and less likely to fail on naming, quoting, log visibility, or incomplete return packaging.







Judgment:



- HPC is now explicitly a formal execution backend, not a debugger.



- From this point onward, no A-line job should be promoted to HPC unless the local smoke, package freeze, naming, logging, and return-bundle rules are already satisfied.







Next:



- Apply this fixed SOP to the next formal A-line cluster workload.



- Before the next submission, verify the run directory satisfies the frozen-file checklist exactly.







### 2026-04-17 (Second-Environment Feasibility Started)







What was done:



- Started the A-line second-dataset or second-environment package with a local feasibility node instead of jumping directly to formal training.



- Added `repo/ood/second_environment_feasibility.py` as an A-line-only probe for the `BoT-IoT first` entry condition.



- Created `runs/second_environment_botiot_feasibility_2026-04-17/` and ran the probe locally.



- Verified the official dataset entry pages are reachable:



  - `https://research.unsw.edu.au/projects/bot-iot-dataset`



  - `https://research.unsw.edu.au/projects/toniot-datasets`



- Extracted the official SharePoint dataset links from those pages and tested direct access from the current environment.



- Scanned the local `D:\study` tree and confirmed there is no existing `BoT-IoT` or `TON-IoT` dataset copy available for immediate smoke preparation.







Result:



- The current A-line blocker for second-environment validation is data availability, not model code.



- `BoT-IoT first` is currently blocked on this machine:



  - the official `BoT-IoT` dataset link resolves into a Microsoft login flow rather than a directly usable dataset folder from the current environment;



  - no local `BoT-IoT` copy is present;



  - no local `TON-IoT` fallback copy is present either.



- The generated feasibility node is:



  - `runs/second_environment_botiot_feasibility_2026-04-17/`



- Main artifacts include:



  - `summary.md`



  - `config.json`



  - `run_spec.json`



  - `feasibility_report.json`



  - `command.txt`







Judgment:



- The mainline should not pretend this is a model-training blocker or spend HPC budget here yet.



- The correct reading is that the second-environment package is ready at the infrastructure/protocol level for a local smoke start, but the dataset itself is not locally available.



- Until a local `BoT-IoT` or `TON-IoT` copy is placed on disk, the second-environment line cannot advance into the mandated local smoke stage.







Next:



- Obtain a local `BoT-IoT` dataset copy first if possible, because the execution order is fixed as `BoT-IoT first`.



- If `BoT-IoT` remains inaccessible but `TON-IoT` becomes locally available earlier, rerun the same feasibility probe with a local `TON-IoT` root and decide explicitly whether the mainline should switch to the documented fallback.



- After a local dataset copy exists, rerun the feasibility node with `--bot-iot-root` or `--ton-iot-root`, then build the minimal second-environment smoke package before any formal HPC run.







### 2026-04-20 (BoT-IoT Local Data Arrived + Smoke Started)







What was done:



- Confirmed local `BoT-IoT 5%` data is now present at:



  - `D:\study\paper\anomaly_detection\paper04\worktrees\data\5%`



- Re-ran feasibility with the local data root:



  - `runs/second_environment_botiot_feasibility_2026-04-20/`



  - verdict is now `bot_iot_local_ready_for_smoke`.



- Started and completed the first local second-environment smoke node:



  - added `repo/ood/second_environment_botiot_smoke.py`



  - generated `runs/second_environment_botiot_smoke_2026-04-20/`



  - used BoT-IoT official 10-best training/testing split CSVs:



    - train: `UNSW_2018_IoT_Botnet_Final_10_best_Training.csv`



    - test: `UNSW_2018_IoT_Botnet_Final_10_best_Testing.csv`



  - smoke protocol:



    - label column: `attack` (`0` as benign)



    - numeric-only features for this first pass



    - split = ID benign from train, OOD benign from test, attack from test



    - models = `isolation_forest` and `oneclass_svm`



    - policies = `fixed_id_q99`, `naive_calibrated_budget500_target1pct`, `det_floor_50pct_min_alarm`







Result:



- The second-environment line is no longer blocked by missing data and now has a runnable local smoke path.



- Smoke split scale:



  - `id_benign_train = 370`



  - `ood_benign_test = 107`



  - `attack_test = 100000` (capped for smoke speed)



  - `numeric_feature_count = 11`



- Smoke outputs are available in:



  - `summary.md`



  - `split_summary.csv`



  - `smoke_results.csv`



  - `smoke_scan.csv`



  - `feature_columns.txt`



  - `data/id_benign_numeric.csv`, `data/ood_benign_numeric.csv`, `data/attack_numeric.csv`



- Key smoke signals (not formal conclusions):



  - `isolation_forest` fixed q99: `ood_alarm = 0.0000`, `attack_det = 0.7440`, `auc = 0.9832`



  - `oneclass_svm` fixed q99: `ood_alarm = 0.0374`, `attack_det = 1.0000`, `auc = 1.0000`







Judgment:



- This node successfully proves the BoT-IoT second-environment smoke pipeline works end-to-end on local data.



- These numbers are not yet paper-grade because benign support is extremely small (`370/107`) and the split is a dataset-provided train/test partition rather than a stronger benign-OOD construction.



- The current node should be treated as a readiness milestone, not as external-validity evidence closure.







Next:



- Build the formal second-environment definition on top of this runnable path:



  - lock a defensible benign ID/OOD split rule under BoT-IoT;



  - run the required mainline objects (`dA`, current strongest candidate, `FT` line) with aligned policies.



- If BoT-IoT cannot provide enough benign support for a defensible stronger-OOD operating-point study, escalate to the documented `TON-IoT` fallback for the formal package.







### 2026-04-20 (BoT-IoT Split Gate Converged)







What was done:



- Added `repo/ood/second_environment_botiot_split_gate.py` to make the BoT-IoT split decision explicit under mainline policy constraints.



- Ran `runs/second_environment_botiot_split_gate_2026-04-20/` using:



  - `UNSW_2018_IoT_Botnet_Final_10_Best.csv` (full 10-best)



  - `UNSW_2018_IoT_Botnet_Final_10_best_Training.csv`



  - `UNSW_2018_IoT_Botnet_Final_10_best_Testing.csv`



  - `UNSW_2018_IoT_Botnet_Full5pc_4.csv`



- Evaluated multiple BoT-IoT split candidates against fixed requirements:



  - fixed point feasibility (`id>=100`, `ood>=100`)



  - required mainline naive policy budget (`ood>=5000`)



  - formal benign support gate (`id>=1000`, `ood>=1000`)







Result:



- Gate verdict is:



  - `blocked_naive_budget5000_not_supported`



- Raw benign support in BoT-IoT 5% is too small for the required naive calibration policy:



  - full 10-best benign = `477`



  - train benign = `370`



  - test benign = `107`



  - all-feature full4 benign = `477`



- Candidate table confirms none can satisfy `naive_budget5000`:



  - `official_10best_train_vs_test`: `id=370`, `ood=107`



  - `full10best_max_ood_with_id100`: `id=100`, `ood=377`



  - `full10best_benign_70_30`: `id=334`, `ood=143`



  - `full4_benign_70_30`: `id=334`, `ood=143`



- All candidates pass minimal fixed-q99 count checks but all fail both `naive_budget5000` and formal benign support.







Judgment:



- BoT-IoT can still serve smoke/readiness diagnostics, but it cannot be the formal second-environment closure under the currently fixed mainline policy set.



- The split question is now converged for BoT-IoT under A-line rules; continuing BoT-IoT split tweaking is not a productive mainline path.







Next:



- Escalate to `TON-IoT` fallback for the formal second-environment package.



- Keep BoT-IoT nodes as negative/constraint evidence in the external-validity discussion rather than as final cross-environment proof.







### 2026-04-20 (TON-IoT Fallback Intake Attempted)







What was done:



- Started the documented `TON-IoT` fallback line immediately after the BoT-IoT split gate verdict.



- Added `repo/ood/second_environment_toniot_intake.py` to perform a concrete local intake gate on the declared data root.



- Ran:



  - `runs/second_environment_toniot_intake_2026-04-20/`



  - data root: `D:\study\paper\anomaly_detection\paper04\worktrees\data`







Result:



- Intake verdict:



  - `blocked_missing_toniot_files`



- Scanner summary:



  - total tabular files under root: `7`



  - TON-like candidate files: `0`



  - TON-like labeled candidates: `0`



- Current root content is BoT-IoT 5% only; no TON-IoT file pattern was detected yet.







Judgment:



- Mainline fallback direction is correct, but fallback cannot advance into smoke until TON-IoT files are actually present (or a concrete TON subdirectory path is provided).



- This is a data-availability blocker, not a script or protocol blocker.







Next:



- Provide the TON-IoT local directory under the same data root (or the exact absolute path if stored elsewhere).



- Rerun the TON intake node on that path, then immediately proceed to TON local smoke with fixed mainline policies.







### 2026-04-20 (TON-IoT Intake Ready + First Smoke)







What was done:



- Received local TON path:



  - `D:\study\paper\anomaly_detection\paper04\worktrees\data\Train_Test_Network_dataset`



- Re-ran intake with this exact subdirectory:



  - `runs/second_environment_toniot_intake_2026-04-20_b/`



  - verdict: `toniot_intake_ready_for_smoke`



- Started and completed the first TON local smoke node:



  - added `repo/ood/second_environment_toniot_smoke.py`



  - generated `runs/second_environment_toniot_smoke_2026-04-20/`



  - source file: `train_test_network.csv`



  - split rule:



    - `label=0` as benign, `label=1` as attack



    - ID benign first `30000`



    - OOD benign next `20000`



    - attack sample `100000` (seeded subsample)



  - policy family:



    - `fixed_id_q99`



    - `naive_calibrated_budget5000_target1pct`



    - `det_floor_50pct_min_alarm`



  - models:



    - `isolation_forest`



    - `oneclass_svm`



- Verified label semantics to avoid direction errors:



  - `label=0` corresponds to `type=normal` (`50000` rows)



  - `label=1` corresponds to attack types (`161043` rows)







Result:



- TON fallback line is now unblocked and runnable end-to-end locally.



- Smoke split scale:



  - `id_benign = 30000`



  - `ood_benign = 20000`



  - `attack = 100000`



  - `numeric_feature_count = 16`



- First smoke metrics show weak/no-separation behavior for the tested unsupervised baselines on this split:



  - `isolation_forest` fixed q99: `ood_alarm=0.0037`, `attack_det=0.0097`, `auc=0.2470`



  - `oneclass_svm` fixed q99: `ood_alarm=0.4969`, `attack_det=0.1252`, `auc=0.1839`



- `naive_calibrated_budget5000_target1pct` is now executable on TON (unlike BoT-IoT), so policy-compatibility blocker is cleared.







Judgment:



- This is a valid readiness milestone for the TON fallback route, not a formal second-environment conclusion.



- The immediate problem is no longer missing benign support; it is poor baseline behavior under the current fallback split and feature treatment.



- Formal second-environment package should now focus on running the required mainline objects and checking whether the weak signal is method-specific or split/feature-specific.







Next:



- Keep this TON node as fallback-start evidence and proceed to the required mainline object set (`dA`, current strongest candidate, FT line) under the same policy family.



- Before formal HPC, run one tighter local smoke that controls for obvious confounders (feature subset/normalization and split construction) to avoid wasting a formal run on a degenerate setting.







### 2026-04-20 (TON Formal Precheck + Polarity Gate Fixed)







What was done:



- Added `repo/ood/second_environment_toniot_precheck.py` and ran:



  - `runs/second_environment_toniot_precheck_2026-04-20/`



- Precheck scope:



  - freeze deterministic split manifest for TON fallback formal runs;



  - run score-polarity gate on baseline probes;



  - re-evaluate fixed/naive/det50 policies under the chosen score orientation.



- Fixed split used by precheck:



  - source: `train_test_network.csv`



  - ID benign: `30000`



  - OOD benign: `20000`



  - attack: `100000`



  - numeric features: `16`



  - saved as `split_manifest.json`.







Result:



- Precheck verdict:



  - `polarity_checked_ready_for_formal_object_runs`



- Polarity gate outcome:



  - `isolation_forest`: choose `raw_decision` (`auc=0.752998`, other orientation `0.247002`)



  - `oneclass_svm`: choose `raw_decision` (`auc=0.816051`, other orientation `0.183949`)



- This explains the earlier smoke anomaly (`AUC < 0.5`): prior score orientation in the smoke script was inverted for TON fallback semantics.



- Policy metrics after polarity correction are now recorded in:



  - `precheck_policy_results.csv`



  - `score_distribution_stats.csv`



  - `polarity_check.csv`







Judgment:



- TON fallback now has both a fixed split manifest and a validated score orientation.



- The pipeline is ready to enter formal object runs (`dA`, current strongest candidate, FT line) without the previous directionality ambiguity.



- We should not launch formal HPC until formal object scripts consume this exact split manifest and chosen score orientation.







Next:



- Implement/patch the formal TON object-run entry so `dA`, strongest candidate, and FT line all read `split_manifest.json`.



- Keep policy family fixed (`fixed_id_q99`, `naive_calibrated_budget5000_target1pct`, `det_floor_50pct_min_alarm`) and proceed with local smoke checks before formal HPC submission.







### 2026-04-20 (TON Mainline Object Pre-Run Completed)







What was done:



- Added `repo/ood/second_environment_toniot_object_prerun.py` to run the required second-environment object pack on a fixed TON split manifest with unified policy family.



- Ran:



  - `runs/second_environment_toniot_object_prerun_2026-04-20_b/`



- This node consumed `runs/second_environment_toniot_precheck_2026-04-20/split_manifest.json` and executed:



  - `dA`



  - `strongest_candidate_transformer_covreg_v2_seed101` (migratable single-seed strongest-candidate proxy)



  - `ft_transformer_ae`



- Local pre-run scale for this node:



  - `ID train = 8000`



  - `ID eval = 4000`



  - `OOD eval = 8000`



  - `attack eval = 12000`



  - `naive budget = 5000`







Result:



- Object pack is now runnable end-to-end under one script, one split source, and one policy set.



- Polarity gate selected `neg_raw_score` for all three objects:



  - `dA`: `auc=0.679894`



  - `strongest_candidate_transformer_covreg_v2_seed101`: `auc=0.668993`



  - `ft_transformer_ae`: `auc=0.511384`



- Fixed and naive operating points are currently weak on this TON pre-run split:



  - `dA` fixed: `ood_alarm=0.007625`, `attack_det=0.076667`



  - `strongest_candidate` fixed: `ood_alarm=0.014125`, `attack_det=0.000000`



  - `ft_transformer_ae` fixed: `ood_alarm=0.000000`, `attack_det=0.000000`



  - `ft_transformer_ae` naive: `ood_alarm=0.010875`, `attack_det=0.011750`



- Detection-floor reference (`det_floor_50pct_min_alarm`) required high OOD alarm for all:



  - `dA`: `0.298500`



  - `strongest_candidate`: `0.333125`



  - `ft_transformer_ae`: `0.480000`



- Runtime diagnostics captured in `object_diagnostics.csv` indicate the strongest-candidate line is much heavier than `dA/FT` under this local setup.



- During strongest-candidate scoring, one `NaN/Inf detected in execute score` message appeared (run completed, but this is a stability warning to resolve before formal promotion).







Judgment:



- This node closes the implementation gap (“required objects can now run on TON fallback with aligned policies”), but does not close the second-environment evidence gap.



- On the current pre-run scale and settings, none of the three objects provides a strong fixed/naive operating-point result.



- Formal HPC promotion is not justified yet; the correct next action remains local diagnosis and stabilization.







Next:



- Diagnose and fix the strongest-candidate `NaN/Inf` execute-path instability on TON split.



- Run one more local stabilization pass for the same object pack (same policy family, same split source) before scaling to full TON counts.



- If stabilized local results remain weak, record as negative external-validation evidence; if stabilized signal improves, then prepare the formal date-tagged HPC package by the fixed SOP.







### 2026-04-21 (TON Engineering + Protocol Gate Passed)







What was done:



- Upgraded `repo/ood/second_environment_toniot_object_prerun.py` for engineering auditability:



  - non-finite score replacement counters per object/split;



  - optional score-array persistence under `runs/<run_tag>/scores/`;



  - hard finite-value guard before policy evaluation.



- Added `repo/ood/second_environment_toniot_engineering_gate.py` as an explicit gate checker for:



  - split-manifest integrity and label semantics;



  - required output matrix completeness (`3 objects x 3 policies`);



  - fixed policy names and `naive_budget5000` presence;



  - finite-value checks on result and polarity tables.



- Ran local engineering smoke:



  - `runs/second_environment_toniot_object_prerun_2026-04-21_engineering_smoke/`



  - scale: `ID train=4000`, `ID eval=2000`, `OOD eval=5000`, `attack eval=5000`



- Ran gate checker on this node and generated:



  - `runs/second_environment_toniot_object_prerun_2026-04-21_engineering_smoke/engineering_gate/summary.md`



  - `runs/second_environment_toniot_object_prerun_2026-04-21_engineering_smoke/engineering_gate/engineering_gate_report.json`







Result:



- Gate verdict:



  - `engineering_gate_pass`



- Split checks all pass:



  - indices in bounds;



  - ID/OOD/attack disjoint;



  - ID and OOD labels are normal (`0`);



  - attack labels are non-normal.



- Output checks all pass:



  - required files present;



  - object-policy matrix complete;



  - `naive_calibrated_budget5000_target1pct` present;



  - metrics and polarity values finite.



- Non-finite counters:



  - total `0` in this engineering smoke run.







Judgment:



- Current blocker has moved from “possible engineering/口径错误” to “性能与跨环境泛化本身不足”。



- Formal HPC should still wait, but now the wait reason is method performance, not pipeline correctness.







Next:



- Keep this gate as mandatory pre-submit check for TON object runs.



- Move to method-side diagnosis under fixed gate:



  - same split source and policy family;



  - improve detection at low alarm, or record stable negative evidence if improvement fails.







### 2026-04-21 (TON Stability Re-Run Under Fixed Gate)







What was done:



- Ran one same-scale stability rerun under the fixed object-pack protocol:



  - `runs/second_environment_toniot_object_prerun_2026-04-21_stability/`



  - scale: `ID train=8000`, `ID eval=4000`, `OOD eval=8000`, `attack eval=12000`



  - objects: `dA`, `strongest_candidate_transformer_covreg_v2_seed101`, `ft_transformer_ae`



  - policy family unchanged: `fixed_id_q99`, `naive_calibrated_budget5000_target1pct`, `det_floor_50pct_min_alarm`



- Ran engineering/protocol gate on this run:



  - `runs/second_environment_toniot_object_prerun_2026-04-21_stability/engineering_gate/`



  - verdict: `engineering_gate_pass`







Result:



- Gate status:



  - split checks pass;



  - output matrix and policy checks pass;



  - finite-value checks pass;



  - non-finite replacement count remains `0`.



- Stability signal versus prior same-scale run (`..._2026-04-20_b`):



  - `dA` is exactly reproducible across all three policies (same metrics to 6 decimals).



  - `strongest_candidate` still weak at fixed point:



    - fixed: `ood_alarm=0.002125`, `attack_det=0.003333`, `auc=0.690065`



  - `ft_transformer_ae` still fails fixed point:



    - fixed: `ood_alarm=0.000000`, `attack_det=0.000000`, `auc=0.570755`



  - `ft_transformer_ae` naive point improved in detection:



    - naive: `ood_alarm=0.009250`, `attack_det=0.126000`



    - but `id_alarm=0.395250`, still not deployment-credible.



- The stdout warning string from backend (`NaN/Inf detected in execute score`) still appeared once during strongest attack scoring, but run-level diagnostic counters remained finite-clean after replacement guard (`nonfinite_total=0` in gate report).







Judgment:



- Engineering and protocol explanations are now largely ruled out for this stage.



- Under fixed `q99`, both `strongest_candidate` and `FT` remain clearly below `dA` on TON second-environment split.



- This is now a stable method-performance gap, not an unstable pipeline artifact.







Next:



- Keep TON second-environment line in local method-diagnosis mode (no formal HPC yet).



- Prioritize strongest-candidate execute-path numerical diagnosis (source of one-off backend warning) and low-alarm detection recovery.



- If next controlled method iteration still cannot beat the `dA` fixed operating point, lock this as stable negative external-validation evidence and stop expanding this branch.







### 2026-04-21 (Threshold Sensitivity + Coupling Verification)







What was done:



- Added and ran threshold-sensitivity audit:



  - script: `repo/ood/second_environment_toniot_threshold_sensitivity.py`



  - run: `runs/second_environment_toniot_threshold_sensitivity_2026-04-21/`



  - audited dimensions:



    - score orientation (`raw_score` vs `neg_raw_score`)



    - threshold operator (`>` vs `>=`)



    - policies (`fixed_id_q99`, `naive_calibrated_budget5000_target1pct`)



- Added and ran model-expression coupling probe:



  - script: `repo/ood/second_environment_toniot_coupling_probe.py`



  - run: `runs/second_environment_toniot_coupling_probe_2026-04-21/`



  - fixed split scale: `ID train=4000`, `ID eval=2000`, `OOD eval=5000`, `attack eval=5000`



  - models: `dA`, `ft_transformer_ae`



  - expression views:



    - `standard_zscore`



    - `winsor_zscore`



    - `signed_log1p_zscore`







Result:



- Threshold sensitivity on the stability source run confirms the `FT fixed=0` observation is not a simple comparator bug:



  - chosen orientation is `neg_raw_score`;



  - under chosen orientation:



    - `fixed_id_q99`: `attack_det=0.000000` for both `>` and `>=`;



    - changing `>` to `>=` does not recover attack detection.



- FT tie profile shows substantial threshold ties on ID at chosen orientation (`eq@q99 ≈ 0.19075`), which affects ID alarm accounting but does not explain attack detection being zero.



- Coupling probe shows strong expression sensitivity:



  - `FT` fixed point:



    - `standard_zscore`: `ood_alarm=0.0000`, `attack_det=0.0000`



    - `winsor_zscore`: `ood_alarm=0.0000`, `attack_det=0.0102`



    - `signed_log1p_zscore`: `ood_alarm=0.0990`, `attack_det=0.1452`



- Interpretation:



  - `FT` detection collapse is real under current chosen orientation + standard expression, not just an operator artifact;



  - expression change can recover some detection, but currently with unacceptable OOD alarm inflation at fixed point.







Judgment:



- The new evidence supports “model + front-expression coupling” as a real factor.



- This line is still not ready for formal HPC promotion because recovered detection has not yet met low-alarm operating requirements.







Next:



- Superseded by the 2026-04-22 failure-closure decision below.



- Do not continue TON/BoT second-environment tuning under the current A-line protocol.







### 2026-04-22 (A-line Second-Environment Failure Closure + Original100 Few-Shot Official Control)







#### Task 1: A-line second-environment failure closure







Updated project-level judgment:



- BoT-IoT / TON-IoT second-environment work is no longer an active strengthening or rescue line.



- This line is now formally sealed as negative evidence, limitation, and external-validity boundary for the current mainline formal protocol.



- No further second-environment expansion, rerun, or tuning should be started under the current A-line protocol unless a future project-level decision explicitly opens a new dated protocol.







Failure ruling:



- BoT-IoT does not support formal mainline use under the current split requirements because available benign support is too small for the required ID/OOD/calibration/eval protocol; it remains a split-feasibility failure, not a main-evidence run.



- TON-IoT passed engineering/protocol gates but does not support the current mainline model claims:



  - `dA` fixed reference remains weak but nonzero (`AUC=0.679894`, `attack_det=0.076667` on the same-scale stability run).



  - `strongest_candidate_transformer_covreg_v2_seed101` fixed point remains nearly non-detecting (`attack_det=0.003333`, `AUC=0.690065`).



  - `ft_transformer_ae` fixed point remains non-detecting (`attack_det=0.000000`, `AUC=0.570755`).



- Threshold-sensitivity and coupling probes ruled out a simple comparator/threshold artifact for the FT zero-detection point; expression changes can recover some detection but not a deployable low-alarm result.







How to use this in the paper:



- Use as negative evidence and limitation: the current formal protocol does not robustly externalize to the tested second environments.



- Use as external-validity boundary: second-environment results are not part of the positive main evidence.



- Do not frame BoT-IoT / TON-IoT as ongoing evidence strengthening or as a line still being optimized.







#### Task 2: Original100 few-shot official control package







What was done:



- Added mainline official control script:



  - `repo/ood/original100_fewshot_official_control.py`



- Ran local official control package:



  - `runs/original100_fewshot_official_control_2026-04-22/`







Protocol:



- Task type: few-shot / supervised target-aligned detector, not unsupervised anomaly scoring.



- Model: L2 `LogisticRegression`, `class_weight=balanced`, `C=1.0`, `solver=liblinear`.



- Input representation: original frontend flat 100D.



- Labels:



  - negatives = ID benign train rows + OOD benign train rows;



  - positives = seeded few-shot samples from stage2 high-purity attack train split.



- Budgets and seeds:



  - budgets: `16`, `32`;



  - positive sample seeds: `42,43,44,45,46`.



- Fairness:



  - final OOD eval is never used for threshold selection;



  - positive sampling is multi-seed;



  - summary reports mean/min/max.



- Operating points:



  - `fixed_id_calib_q99`;



  - `guarded_id_calib_and_ood_val_target1pct`.



- Boundary:



  - `original100_fewshot_logistic` is the official control group;



  - `da_unsupervised_score_seed42` is only a reference baseline and is not in the same label-information setting;



  - no source-rich win/loss conclusion is made in this mainline control package.







Integrity check:



- Required package files present:



  - `command.txt`



  - `config.json`



  - `run_spec.json`



  - `official_control_manifest.json`



  - `diagnostics.json`



  - `results.csv`



  - `original100_fewshot_official_control_summary.csv`



  - `original100_fewshot_official_control_focus.csv`



  - `summary.md`



  - `stdout.log`



  - `stderr.log`



- `results.csv`: 22 rows.



- `summary`: 6 aggregate rows.







Key control results:



- `original100_fewshot_logistic`, 16-shot, fixed ID q99:



  - `AUC mean/min/max = 0.990672 / 0.958007 / 0.999974`



  - `OOD alarm mean/min/max = 0.004500 / 0.001200 / 0.009500`



  - `attack det mean/min/max = 0.967564 / 0.914182 / 0.999273`



  - `feasible_rate = 1.000000`



- `original100_fewshot_logistic`, 16-shot, guarded:



  - `AUC mean/min/max = 0.990672 / 0.958007 / 0.999974`



  - `OOD alarm mean/min/max = 0.004440 / 0.001200 / 0.009200`



  - `attack det mean/min/max = 0.967564 / 0.914182 / 0.999273`



  - `feasible_rate = 1.000000`



- `original100_fewshot_logistic`, 32-shot, fixed ID q99:



  - `AUC mean/min/max = 0.984615 / 0.967632 / 0.999910`



  - `OOD alarm mean/min/max = 0.006520 / 0.003600 / 0.009800`



  - `attack det mean/min/max = 0.940655 / 0.920727 / 0.999273`



  - `feasible_rate = 1.000000`



- `original100_fewshot_logistic`, 32-shot, guarded:



  - `AUC mean/min/max = 0.984615 / 0.967632 / 0.999910`



  - `OOD alarm mean/min/max = 0.006520 / 0.003600 / 0.009800`



  - `attack det mean/min/max = 0.940655 / 0.920727 / 0.999273`



  - `feasible_rate = 1.000000`



- `dA` unsupervised reference:



  - fixed ID q99: `AUC=0.806365`, `OOD alarm=0.128600`, `attack det=0.686545`, `feasible_rate=0.000000`



  - guarded: `AUC=0.806365`, `OOD alarm=0.010800`, `attack det=0.002909`, `feasible_rate=0.000000`







Current next:



- Treat second-environment as closed negative evidence unless the project opens a new protocol.



- Treat the original100 few-shot package as the mainline official control group for the v7 target-aligned methodology port.



- Commit/push the script plus mainline doc updates; keep generated run artifacts local unless explicitly requested otherwise because `/runs/*` is ignored except the two mainline docs.







### 2026-05-08 (Strategy Update: From LR Replacement to Base-Detector-Agnostic Guarded Few-Shot Adaptation)







What was done:



- Recorded a strategy update only. No experiment was started, no model was trained, and the manuscript was not modified.



- Added the interpretation of `runs/issue02_original_da_normal_attack_sanity_run_2026-05-08/` into the mainline handoff.



- Reframed the next candidate direction as base-detector-agnostic guarded few-shot adaptation rather than "replace dA with few-shot LR".







Key evidence added:



- `issue02_original_da_normal_attack_sanity_run_2026-05-08/` uses clean115 original normal-vs-attack data:



  - rows: `200000`



  - feature_dim: `115`



  - benign rows: `121621`



  - attack rows: `78379`



- dA in the original normal-vs-attack setting is strong:



  - ROC-AUC `0.9340`



  - PR-AUC `0.9487`



  - benign-calibration q99 attack detection `0.8642`



  - benign eval false alarm `0.0107`



- few-shot LR on the same original setting is seed-sensitive:



  - 16-shot q99 AUC mean/min/max `0.6944 / 0.0777 / 0.9292`



  - 16-shot q99 detection mean/min/max `0.6249 / 0.0112 / 0.8648`



  - 32-shot q99 AUC mean/min/max `0.6085 / 0.1113 / 0.9312`



  - 32-shot q99 detection mean/min/max `0.5320 / 0.0316 / 0.8655`







Judgment:



- dA is not invalidated as a detector. It remains a classic lightweight cold-start unsupervised detector.



- The low-OOD collapse evidence should be interpreted as a deployment working-point problem under benign OOD and strict low-OOD-alarm constraints, not as proof that dA lacks normal-vs-attack detection ability.



- L2 `LogisticRegression` remains the minimal target-alignment baseline. It should not be written as a universal replacement for dA or as the final adapter architecture.



- The next method framing should be candidate-level only:



  - base detectors may include dA as a classic lightweight detector and Transformer as a modern contextual detector;



  - few-shot adapters use high-purity attack positives plus ID/OOD benign negatives to learn an attack-oriented score;



  - the guarded low-OOD-alarm threshold remains the deployment operating point.







Candidate next-phase names:



- `Guarded Few-shot Adapter (GFA)`



- `Base-Detector-Agnostic Guarded Few-shot Adapter`



- `Guarded Deviation Adapter (GDA)`







Candidate adapter inputs:



- base representation, such as `original100` or a future Transformer hidden representation;



- base detector score, such as dA RMSE or Transformer anomaly score;



- few-shot high-purity attack positives;



- ID benign + OOD benign negatives.







Candidate adapter output:



- an attack-oriented score evaluated under `guarded_id_calib_and_ood_val_target1pct`;



- final OOD eval and attack eval remain held out from threshold/model selection.







Transformer evidence status:



- A repository search did not find a formal ordinary normal-vs-attack result proving that Transformer is stronger than dA.



- Found assets are weaker or different in scope:



  - clean115 `trans115_min` / `da115_min` are ID-only minimal checks, not normal-vs-attack evidence;



  - stronger-OOD Transformer/FT/ensemble results are operating-point evidence, not ordinary closed-set normal-vs-attack proof.



- Therefore the Transformer role is currently `needs evidence retrieval`, not a completed claim.







Boundary:



- Do not write "few-shot LR replaces dA".



- Do not write "GFA/GDA is proven".



- Do not write "Transformer-assisted adapter is effective" until a same-protocol experiment exists.



- Do not move this strategy update into the manuscript as a claim without a future evidence package.







Next:



- First retrieve or construct a clean Transformer ordinary-setting evidence inventory.



- Then run a base-detector adapter feasibility inventory.



- Only after those gates decide whether to start a formal GFA/GDA experiment.







### 2026-05-17 Strategy Update: Problem-Driven Reframing after 2022–2026 Frontier Survey







Source report received and accepted:







- `D:\study\paper\anomaly_detection\paper04\worktrees\gpt deep\22年-26年问题定义报告.md`



- SHA-256: `d7d8649029a2bae5a5cdc6f4ca9ea07a3ea4256391d21d8cabc1345e8940c4f9`







Main framing is now changed from **few-shot LR repair** to **low-alert IDS under benign-OOD drift**. The recommended paper route is **Problem B / balanced hybrid paper**: problem definition + deployment-stage guarded adaptation + bounded coexistence with base detectors.







Current method naming:







- Preferred paper name: `LOW-GUARD` / `LOW-GUARD-minimal`.



- Internal shorthand `GDA` may remain for later guarded/deviation adapter ideas, but the current paper should not imply full neural GDA has been completed.



- Current stable implementation: `original100 representation + fixed OOD-benign guard + few-shot LR adapter`.







Current strongest evidence:







- Ordinary sanity checks show dA / Transformer are not useless cold-start detectors.



- Low-OOD collapse shows deployment mismatch: ordinary ranking quality does not guarantee low-alert attack detection under benign-OOD drift.



- Scalar score fusion is negative / not a main route.



- Fixed OOD guard is positive and currently the strongest mechanism.



- LOW-GUARD-minimal high-priority channel is positive on the current primary split.



- Mode-gated arbitration and bounded review define system coexistence with base detectors.



- Review queue is a safety net only, not a confirmed attack pool.







Current missing evidence:







- Formal harder holdout.



- Second environment / external dataset.



- Few-shot anomaly baselines such as DevNet-like / Deep SAD-like / RoSAS-like comparisons.



- OOD budget sensitivity.



- LOW-GUARD shot sensitivity.



- Modern unsupervised baselines.



- Efficiency / runtime.



- Calibration / threshold transfer.







Immediate next decision should use issue16 results to choose among:







- issue16b formal harder holdout,



- baseline recovery,



- second environment plan,



- or stop/pivot.







## issue27g suspicious perfect score audit (2026-05-27)







- primary_verdict: `lowguard_plus_plus_formal_result_passes_anomaly_audit`



- audited result: issue27f LOW-GUARD++ `original100 + HistGB-Conservative` reported `1.000000 / 1.000000 / 0.000100`.



- scope: final-eval usage, split/sample identity, original100 leakage screening, score distribution, negative controls, scratch recompute, and artifact/cache audit.



- claim boundary: do not use 27f as a broad LOW-GUARD claim; keep it bounded to tested representation/head/protocol and keep temporal/cross-dataset/deployment robustness unclaimed. Because original100 has high-cardinality near-perfect separator features, add feature-provenance evidence before strong main-text upgrading.



- next action: `issue27h_original100_feature_provenance_and_independent_verification_before_claim_upgrade`.







## issue27h feature provenance claim gate (2026-05-27)







- primary_verdict: `lowguard_plus_plus_depends_on_high_risk_separators`



- scope: maps the three original100 high-cardinality near-perfect separators, audits split distributions, runs frozen-config feature ablations, performs report-only non-locked consistency checks, and explains HistGB feature reliance.



- claim boundary: LOW-GUARD++ can remain an audited locked result, but broad/main-text performance-instance upgrading still needs clean independent validation or stronger original100 provenance.



- next action: `issue27i_separator_dependency_deeper_audit_or_demote_lowguard_plus_plus`.







## issue27i separator validation feasibility (2026-05-27)







- primary_verdict: `lowguard_plus_plus_promising_needs_clean_independent_validation`



- scope: inventories clean independent assets, checks HH separator stability on non-locked consistency objects, reports frozen LOW-GUARD++ outside locked bins, evaluates safer feature variants without tuning, and plans data expansion.



- claim boundary: LOW-GUARD++ is not abandoned, but cannot be upgraded to main-text performance instance until clean independent validation or raw provenance resolves separator dependency.



- next action: `issue27j_raw_provenance_recovery_and_clean_independent_split_construction`.







## issue27j raw provenance and clean split audit (2026-05-27)







- primary_verdict: `clean_independent_validation_blocked_but_recoverable`



- scope: recovers raw pcap/TSV/source-code provenance for original100, audits HH separator lineage, checks clean split feasibility, and blocks formal clean validation until a row-level clean split is built.



- claim boundary: LOW-GUARD++ remains a high-potential candidate; current evidence does not justify main-text performance-instance upgrade without clean independent validation.



- next action: `issue27k_row_level_original100_rebuild_and_purged_split_construction`.







## issue27k row-level original100 rebuild and purged split construction (2026-05-27)







- primary_verdict: `row_manifest_recovered_but_clean_split_blocked`



- scope: builds row-level sidecar provenance for ID/OOD/attack original100 assets, verifies source-vs-extracted feature alignment, and designs purged split candidates.



- claim boundary: row provenance is recovered, but clean/purged LOW-GUARD++ validation remains blocked until split-aware feature rebuild and sufficient independent eval assets exist.



- next action: `issue27l_split_aware_original100_rebuild_with_sufficient_clean_eval_asset`.







## issue27l clean eval asset and split-aware rebuild gate (2026-05-27)







- primary_verdict: `clean_eval_asset_found_rebuild_eval_next`



- scope: searches sufficient clean eval assets, identifies full Mirai/Botnet labeled datasets plus the extended unused-segment candidate, and blocks evaluation until feature compatibility, prior-use audit, and split-aware rebuild are resolved.



- claim boundary: LOW-GUARD++ remains high-potential, but still cannot be upgraded to a main-text performance instance.



- next action: `issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild`.







## issue27m full Mirai compatibility audit (2026-05-27)







- primary_verdict: `full_mirai_incompatible_needs_new_frontend_path`



- scope: audited full Mirai/Botnet asset identity, feature schema compatibility, prior-use risk, split feasibility, and split-aware rebuild feasibility before any LOW-GUARD++ score run.



- key result: full Mirai is a large labeled asset (`764137` rows; benign `121621`, attack `642516`), but it is `dirty116`/`clean115-restored115` style rather than the current frozen `original100` LOW-GUARD++ input.



- claim boundary: no full Mirai LOW-GUARD++ validation was run; clean115/restored115 must not be mixed with the frozen original100 claim.



- next action: `issue27n_full_mirai_restored115_feature_mapping_and_lowguardpp_interface_smoke` or, if original100 must be preserved, full Mirai original100 frontend re-extraction.







## issue27n full Mirai restored115 mapping gate (2026-05-27)







- primary_verdict: `restored115_feature_mapping_blocked`



- scope: audits dirty116-to-clean115 construction, restored115 feature mapping, historical prior-use isolation, clean115 split proposal, and LOW-GUARD interface-smoke gates.



- key result: clean115 can be defined by dropping the index-like col0, but restored115 feature names/order remain unverified and historical `my_gold` overlap contains all benign rows.



- claim boundary: no restored115 LOW-GUARD++ smoke or formal full Mirai validation was run; clean115/restored115 remains a separate candidate input track, not the frozen original100 claim.



- next action: `issue27o_restored115_mapping_recovery_or_original100_reextraction_for_full_mirai`.







## issue27o full Mirai protocol reset spec (2026-05-27)







- primary_verdict: `full_mirai_protocol_reset_ready_with_anonymous_clean115`



- scope: redefines issue20-27n as exploration, adopts full Mirai as a protocol-reset within-dataset benchmark, writes split/fairness/feature-study contracts, and runs a small anonymous-clean115 interface smoke.



- key boundary: full Mirai is not a completely unseen external test; restored115/common100 mapping remains low confidence; all baselines must be rerun under the reset protocol.



- next action: `issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution`.







## issue27p full Mirai anonymous clean115 formal benchmark execution (2026-05-27)







- primary_verdict: `baseline_dominates_needs_method_rethink`



- scope: executes the full Mirai protocol-reset benchmark on `anonymous_clean115_all` with fixed split, train/validation-only selection, and report-only final eval.



- baseline rerun status: complete for planned local reset methods; old issue20-27n numbers remain exploratory.



- current benchmark leader by feasibility-first ranking: `DeepSADStyle_Lite`.



- claim boundary: this is within-dataset protocol-reset evidence, not external generalization and not restored115/original100 evidence.



- next action: `issue27q_protocol_reset_result_audit_and_seed_expansion`.







## issue27q plan for protocol reset audit (2026-05-27)







- primary_verdict: `issue27q_execution_plan_ready`



- scope: plan-only audit package for DeepSADStyle_Lite, LOW-GUARD++ reset-protocol failure, and paired LOW-GUARD protocol universality.



- key boundary: issue27p changes the mainline question but does not yet make DeepSADStyle_Lite claim-safe or permanently demote LOW-GUARD++.



- next action: execute P0/P1 DeepSAD audit, then LOW-GUARD++ failure diagnosis and paired universality matrix.







## issue27q P0P1 DeepSAD-lite audit and seed expansion (2026-05-27)







- primary_verdict: `deepsad_lite_result_suspicious_needs_artifact_debug`



- scope: audits DeepSADStyle_Lite replay, score direction, split separation, negative controls, feature artifacts, seed expansion, and stratified behavior.



- claim boundary: DeepSADStyle_Lite remains a weighted-center lite candidate under anonymous clean115, not exact Deep SAD and not external generalization.



- next action: `issue27r_deepsad_lite_artifact_debug_and_feature_provenance`.







<!-- issue27r_semantic_validity_audit -->







## issue27r Benchmark Semantic Validity Gate







- primary_verdict: `attack_benign_artifact_risk`.



- ID/OOD drift is distinguishable but row-order/distributional, not temporal/capture/deployment drift.



- OOD benign labels are pure by sidecar, but deployment semantics are weak without timestamp/capture/session metadata.



- attack/benign semantics are blocked by high artifact risk: benign prefix, attack suffix, anonymous features, no source/capture provenance.



- anonymous_clean115 remains diagnostic only for protocol reset; it is not restored115/original100/common100.



- issue27p model rankings are diagnostic only and should not drive mainline claims until raw provenance or second-dataset semantic validation passes.



- next: `issue27s_raw_provenance_or_second_dataset_semantic_reconstruction_for_low_ood_alert_benchmark`.







<!-- issue27s_raw_provenance_or_second_dataset -->







## issue27s Raw Provenance Or Second Dataset Decision







- primary_verdict: `dual_track_raw_rebuild_and_second_dataset_intake`.



- issue27r data semantics gate did not pass for full Mirai anonymous_clean115.



- full Mirai paired raw pcap/input stream was not found; local pcaps are unrelated IoT23/public_data assets.



- full 764k timestamp/capture/session provenance is missing; `mirai3_ts.csv` is only a smaller related path.



- current full Mirai anonymous_clean115 is diagnostic only, not main low-OOD-alert benchmark.



- model experiments remain blocked by Data validity gate.



- next: dual-track full Mirai raw provenance search plus second-dataset semantic intake.







<!-- issue27t_second_dataset_intake -->







## issue27t Second Dataset Intake







- primary_verdict: `second_dataset_candidates_need_manual_access_or_download_confirmation`.



- full Mirai paired raw missing is confirmed; full Mirai anonymous_clean115 remains diagnostic only.



- current model experiments remain blocked by Data validity gate.



- recommended candidates: Gotham Dataset 2025 first, ToN-IoT network second; local IoT-23 is auxiliary for semantic-gate rehearsal.



- all future downloads must use `D:\study\paper\anomaly_detection\paper04\datasets\<dataset_name>\...`; do not stage raw/large data.



- next: `issue27u_gotham_metadata_intake_and_data_gate_precheck`.







<!-- issue27u_gotham_metadata_intake -->







## issue27u Gotham Metadata Intake







- primary_verdict: `gotham_ready_for_full_download_with_user_confirmation`.



- Gotham metadata reports raw PCAP, processed CSV, metadata with timestamps/attacker IPs/attack types, device-level traces from 78 heterogeneous IoT devices, and deterministic labels.



- Zenodo exposes a single `23.825GB decimal / 22.189GiB` zip; no large download was performed.



- model experiments remain blocked by Data validity gate.



- next: user-confirmed Gotham download and file-level Data Gate, or ToN-IoT metadata intake if Gotham is blocked.







<!-- issue27v_gotham_file_level_data_gate -->







## issue27v Gotham Download And File-Level Data Gate







- primary_verdict: `gotham_file_level_gate_passed_ready_for_sample_data_gate`.



- storage_preflight_verdict: `pass_user_approved_download_only`; user approved download-only mode below the original 80GB safety recommendation.



- planned data path: `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025`; raw zip target `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\raw\GothamDataset2025.zip`.



- Gotham zip was downloaded/resumed to the approved D: dataset path and verified with expected md5 `7ca78c0517ccb3d2854e823678e0f206`; local sha256 is recorded in issue27v outputs.



- Archive listing passed with no unsafe paths; it contains `110` PCAP files and `78` processed CSV files. CSV previews show a `label` column and `frame.time` timestamp, while device/source/capture information is partial via README, filenames, packet fields, and directory structure rather than a separate metadata JSON sidecar.



- model experiments remain blocked; this issue is not evidence for or against Gotham's semantic suitability.



- next: `issue27w_gotham_sample_data_gate`; do small sample-level validation only, with no full PCAP extraction or model execution.







<!-- issue27w_gotham_sample_data_gate -->







## issue27w Gotham Sample Data Gate







- primary_verdict: `gotham_sample_gate_promising_needs_more_space_and_larger_sample`.



- sample gate read selected processed CSVs from the zip stream and wrote only first-1000-row previews under the external dataset directory; no PCAP or full large CSV extraction was performed.



- labels, `frame.time`, packet fields, device/file names, and matching PCAP paths are usable at sample level.



- most promising split is device-disjoint benign drift, with protocol-disjoint as a secondary route.



- largest artifact risk is label/source/time coupling, especially benign-prefix then attack-label structure in mixed attack files.



- model experiments remain blocked; next is a larger sample manifest and split gate.







<!-- issue27x_gotham_larger_sample_gate -->







## issue27x Gotham Larger Sample Manifest And Split Gate







- primary_verdict: `gotham_larger_sample_promising_needs_full_manifest`.



- allowed mode was `limited_csv_extract`, but execution used streaming sampled manifest construction and did not extract PCAP or full large CSV files.



- sampled row-level manifest was built across representative benign and mixed attack processed CSVs; PCAP/CSV pairing is medium-confidence by filename/path matching.



- most promising split remains device-disjoint benign drift; protocol-disjoint is a secondary route.



- largest blocker is file/device/time shortcut risk; Gotham is not yet ready for Feature/interface gate or model experiments.



- next: fuller manifest and pre-registered split contract.







<!-- issue27y_gotham_preregistered_data_contract -->







## issue27y Gotham Fuller Manifest And Preregistered Data Contract







- primary_verdict: `gotham_data_contract_promising_needs_feature_pairing_or_full_manifest`.



- all 78 processed CSVs were summarized from the zip stream; sampled row manifest has `13,372` rows.



- best split-contract candidate is `gotham_device_disjoint_v1`; it can construct ID benign train, OOD benign validation, final OOD benign eval, and file-level disjoint attack support/eval.



- size adequacy is promising for the primary contract, but PCAP/CSV pairing remains medium-confidence filename/path matching and source-identifier feature policy is not yet defined.



- artifact risk remains material, especially label/file/device/protocol coupling; model experiments remain blocked.



- next: issue27z should strengthen PCAP/CSV pairing and define IP/MAC/port/timestamp/source handling before Feature/interface gate.











<!-- issue27z_gotham_pairing_source_policy_gate -->







## issue27z Gotham Pairing And Source Policy Gate







- primary_verdict: `gotham_ready_for_feature_interface_diagnostic_only`.



- readiness_verdict: `ready_for_feature_interface_diagnostic_only`.



- PCAP/CSV pairing status: {'medium_filename_path_match': 74, 'high_packet_count_timestamp_match': 1, 'medium_plus_frame_timestamp_hint': 3} after streaming PCAP metadata from the zip; no PCAP extraction or feature extraction was performed.



- source policy status: `gotham_feature_source_policy_v1` defined; labels, file/device/source/path, IP/MAC, and absolute timestamps are forbidden from main model inputs.



- ports/protocol fields are diagnostic-only until a later shortcut audit.



- current model experiments remain blocked; next action is Feature/interface gate work only.











<!-- issue27aa_gotham_strict_packet_dataset -->







## issue27aa Gotham Strict Packet Dataset Materialization







- primary_verdict: `gotham_strict_feature_dataset_ready_for_model_interface_smoke`.



- Materialized `gotham_strict_packet_header_v1` with 26736743 rows outside the git worktree under `datasets/gotham2025/derived/strict_packet_feature_dataset_v1/`.



- Feature matrix excludes labels, file/source/device/path, timestamps, IP/MAC, ports, and protocol fields.



- Split roles are frozen from `gotham_device_disjoint_v1`; final eval remains report-only.



- Model experiments remain blocked; next is interface smoke only.







## issue27ab Gotham Kitsune115 frontend feasibility (2026-06-01)







- primary_verdict: `kitsune115_blocked_by_pcap_label_alignment`



- scope: restores the commented Kitsune Host BW H-stat block as an explicit 115D frontend smoke, reads selected Gotham raw PCAPs from the zip, and audits split-aware frontend state behavior.



- key result: the formal route is now Gotham raw PCAP -> Kitsune/AfterImage/netStat 115D, while the strict 8D packet-header asset is downgraded to engineering smoke/provenance proof.



- state policy: compares reset-at-boundary with branch-based train-state-then-eval-online; final OOD eval is report-only and discarded.



- current model experiments allowed: no formal benchmark yet; next is issue27ac attack-onset alignment before broader 115D materialization.







<!-- issue27ac_gotham_attack_onset_alignment -->







## issue27ac Gotham Kitsune115 Attack-Onset Alignment







- primary_verdict: `attack_onset_alignment_partial_ready_for_kitsune115_smoke_expansion`.



- role: attack-side data/feature gate for Gotham Kitsune115.



- result: first-attack timestamps from processed CSVs can select causal malicious PCAP windows for support/eval smoke; support must start after confirmed attack onset.



- caveat: 6/8 attack contract CSVs aligned within the current scan budget; two ip-camera attack files still need deeper onset scan before full-contract materialization.



- model experiments remain blocked; next is a larger onset-aligned Kitsune115 smoke dataset plus unresolved attack-file deep scan.







<!-- issue27ad_gotham_kitsune115_smoke_expansion -->







## issue27ad Gotham Kitsune115 Split-Aware Smoke Expansion







- primary_verdict: `kitsune115_split_aware_smoke_dataset_ready_heavy_attack_deferred`.



- ID/OOD/final OOD use only preregistered benign split files; attack files are used only after confirmed attack onset.



- both reset-at-boundary and train-state-then-eval-online strategies output 115D finite features; no model metrics were computed.



- all 8 attack files have onset alignment, but 2 ip-camera files are deferred from local materialization because their pre-onset fast-forward is heavy.



- model experiments remain blocked unless explicitly limited to interface shape smoke.







<!-- issue27ae_gotham_kitsune115_interface_shape_smoke -->







## issue27ae Gotham Kitsune115 Model Interface Shape Smoke







- primary_verdict: `kitsune115_model_interface_smoke_passed`.



- fixed issue27ad artifacts only; no resplit, support change, thresholding, ranking, or performance metric.



- LR, HistGB, DeepSAD-style Lite, and LOW-GUARD shell adapters passed shape/finite interface checks.



- next: larger 115D materialization or fast frontend before formal benchmark.







<!-- issue27af_gotham_kitsune115_medium_materialization -->







## issue27af Gotham Kitsune115 Medium Materialization







- primary_verdict: `kitsune115_medium_materialization_ready_full_needs_slurm`.



- medium materialization executed for scalability/stability/hash/sidecar/state checks; it is not formal benchmark data.



- full_contract still needs Slurm/fast frontend for heavy ip-camera attack files.



- no model performance metrics were computed.







<!-- issue27ag_gotham_kitsune115_larger_asset_sanity -->







## issue27ag Gotham Kitsune115 Larger Asset Interface Sanity







- primary_verdict: `kitsune115_larger_asset_ready_with_full_contract_pending`.



- immutable loader verifies issue27af medium certificate hashes and role access policy.



- final OOD eval and attack eval remain report-only and selection-forbidden.



- full_contract remains pending for heavy ip-camera files; no model performance metrics were computed.







<!-- issue27ah_gotham_kitsune115_guarded_protocol_dry_run -->







## issue27ah Gotham Kitsune115 Guarded Protocol Dry Run







- primary_verdict: `guarded_protocol_medium_dry_run_completed_diagnostic_only`.



- medium 115D asset was used only for diagnostic guarded-protocol behavior checks.



- final OOD benign eval and attack eval remained report-only and were not used for thresholding or selection.



- full_contract remains pending; issue27ah results are not formal model rankings.







<!-- issue27ai_medium_protocol_audit_then_diagnostic -->







## issue27ai Medium Protocol Audit Then Diagnostic







- primary_verdict: `medium_protocol_audit_passed_diagnostic_completed`.



- A protocol correctness audit gates B diagnostic execution.



- support size fixed to `32` from preregistered attack_support role; no final eval or attack eval selection.



- output is medium diagnostic only; formal benchmark still requires full_contract or an exclusion policy and protocol freeze.







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







<!-- issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic -->







## issue27ak Recovered Kcenter32 Gotham115 Medium Diagnostic







- primary_verdict: `recovered_kcenter32_medium_diagnostic_completed`.



- Migrates recovered historical `kcenter32` support selector to the fixed Gotham Kitsune115 medium asset.



- support size fixed to `32` from preregistered attack_support role; no final eval or attack eval selection.



- output is medium diagnostic only; formal benchmark still requires full_contract or an exclusion policy and protocol freeze.







<!-- issue27am -->



## issue27am_medium_bounded_protocol_repair_validation_2026-06-03







- primary_verdict: `medium_repair_insufficient_pause_feature_state_onset_audit`



- Medium Gotham Kitsune115 bounded protocol repair validation only; not formal benchmark.



- Tested fixed split/support pool with kcenter32, stratified_kcenter64, and stratified_kcenter128 plus support_val/NP threshold rules.



- Final OOD and attack eval remain report-only; no model ranking or full benchmark claim is made.



- next action: `issue27an_feature_state_onset_or_protocol_repair_reassessment`







<!-- issue27an -->



## issue27an_gotham_kitsune115_feature_state_onset_label_alignment_audit_2026-06-03







- primary_verdict: `support_eval_distribution_mismatch_blocker_found`



- Failure attribution audit after issue27am; no new model training or protocol repair.



- Audited feature separability, onset/label density, state/warmup/carryover, support/eval coverage, and label semantics.



- next action: `issue27ao_repair_support_eval_contract_before_head_repair`







<!-- issue27ao -->



## issue27ao_repair_support_eval_contract_v2_before_head_repair_2026-06-03







- primary_verdict: `contract_v2_ready_for_medium_detection_retest`



- Support/eval contract v2 validation only; no model training.



- Benign split and Kitsune115 frontend unchanged.



- Previous medium attack_eval is consumed for diagnostic contract design, so follow-up retest remains diagnostic only.



- next action: `issue27ap_medium_detection_retest_on_contract_v2_diagnostic_only`







<!-- issue27ap -->



## issue27ap_new_heldout_attack_probe_and_v2_diagnostic_retest_2026-06-03







- primary_verdict: `new_heldout_v2_diagnostic_signal_weak_support_shift_persists`



- Newly materialized held-out heavy ip-camera attack probe; support fixed from issue27ao v2.



- Diagnostic only; not formal benchmark.







<!-- issue27aq -->



## issue27aq - Model learning and domain gap audit after new heldout zero detection







- primary_verdict: `zero_detection_due_to_ood_tail_threshold_overconservative_despite_raw_support_signal`



- Scope: diagnosis only; no support rebuild, no protocol repair, no formal benchmark.



- support_val detection at issue27ap threshold max: `0.000000`; new heldout detection max: `0.000000`.



- raw support score signal exists, but the OOD-tail threshold is above support and heldout scores.



- next action: `issue27ar_balanced_fit_and_threshold_debug_without_final_eval`.







<!-- issue27ar -->



## issue27ar - Old LOW-GUARD++ protocol fidelity on Gotham115 medium







- primary_verdict: `old_protocol_fidelity_mixed_needs_bounded_calibration_repair`



- Migrated issue27f HistGB frozen B protocol skeleton to Gotham Kitsune115 medium.



- Uses old kcenter32, old HistGB config, OOD train guard, sample weights, and guarded ID/OOD threshold.



- Diagnostic only; final OOD, attack_eval, and new heldout remain report-only.







<!-- issue27as -->



## issue27as - Bounded old-protocol calibration and coverage repair







- primary_verdict: `bounded_repair_suggests_feature_or_task_boundary`



- Medium diagnostic only; no formal benchmark.



- Keeps Gotham Kitsune115 medium frontend/split fixed and varies only bounded old HistGB weights, k-center budgets, and train-side threshold rules.



- Candidate selection uses id_calib, ood_val, and support_val only; final OOD, attack_eval, and new heldout remain report-only.







<!-- issue27at -->



## issue27at - Coverage hypothesis validation before protocol redesign







- primary_verdict: `coverage_hypothesis_partially_supported_needs_more_attack_pool`



- Diagnostic only; deterministic replay of issue27as selected candidate to compute per-sample coverage vs detection.



- New heldout remains report-only; final OOD tail risk is not resolved.







<!-- issue27au -->



## issue27au - Coverage-aware active labeling viability diagnostic







- primary_verdict: `active_labeling_viability_supported_but_ood_tail_blocked`



- Diagnostic only; previous new heldout probe is consumed as a development stream.



- Active selection is feature-only and prospective; final OOD remains report-only and not solved.







<!-- issue27av -->



## issue27av - Prototype-aware triage and OOD tail attribution







- primary_verdict: `ood_tail_needs_benign_prototype_veto`



- Diagnostic only; final OOD report-only attribution.



- Adds ID/OOD/attack prototype distance and score-margin analysis before OOD gate repair.







<!-- issue27aw -->



## issue27aw - OOD-safe gate repair diagnostic







- primary_verdict: `benign_veto_tradeoff_unresolved_ood_safe_but_attack_damaged`



- Diagnostic only; dev-selected margin gate preserves attack but does not fix final-OOD tail; fixed benign veto fixes OOD but damages attack.



- Current final OOD remains diagnostic-only; clean sealed-final replay is required before formal claims.







<!-- issue27ax -->



## issue27ax - Attack support bank detection recovery diagnostic







- primary_verdict: `support_bank_overfits_heavy_underrepresents_medium`



- Diagnostic only; tests retained-medium plus active-heavy support bank before OOD gate repair.



- No formal benchmark; final OOD not optimized.







<!-- issue27ay -->



## issue27ay - Region-aware attack bank and score gate diagnostic







- primary_verdict: `region_aware_attack_recovery_supported_ready_for_ood_gate`



- Diagnostic only; tests region weighting, per-region heads, and low-score attack-covered review routing.



- Final/report-only roles were not used for support, threshold, or model selection.



- Formal benchmark remains blocked until OOD-safe calibration and larger/full replay are ready.







<!-- issue27az -->



## issue27az - Region-aware attack-preserving OOD gate diagnostic







- primary_verdict: `needs_disjoint_ood_stress_pool_final_tail_uncovered`



- Diagnostic only; evaluates OOD-safe gates after region-aware heads.



- Final/report-only roles were not used for gate/radius/threshold selection.



- next action: `issue27ba_disjoint_ood_stress_pool_before_mixed_stream`.







<!-- issue27ba -->



## issue27ba - Disjoint OOD stress pool before mixed stream







- primary_verdict: `stress_gate_kills_attack_repair_needed`



- Diagnostic only; materializes a dev-side OOD stress pool from unused OOD-val benign files.



- Final OOD, attack eval, and dev-heavy query were not used for gate selection.



- next action: `issue27bb_attack_preserving_ood_gate_repair_on_disjoint_stress_pool`.







<!-- issue27bb -->



## issue27bb - Three prototype bank attack-preserving OOD gate







- primary_verdict: `three_bank_gate_still_kills_attack`



- Diagnostic only; adds ID/OOD/Attack prototype banks after raw attack score alarms.



- Final OOD, attack eval, and dev-heavy query were not used for prototype or gate selection.



- next action: `issue27bc_attack_core_and_review_cost_repair`.







<!-- model_protocol_open_problems_2026_06_05 -->



## Model / Protocol Open Problems Before Formal Benchmark







These are the current unresolved system problems. Do not treat any medium diagnostic result as a formal benchmark until these are resolved or explicitly bounded.







1. **Attack-preserving OOD gate remains unresolved.**



   - Solved so far: dev-side OOD stress can be materialized legally, and prototype gates can reduce OOD/stress hard alarms.



   - Still open: once OOD is suppressed, report-only attack hard detection still drops too much.



   - Next work must preserve strong attack-core alarms while suppressing only weak attack-score benign/OOD-like alarms.







2. **Attack region expansion is not scalable yet.**



   - Current diagnostics use separate medium/heavy heads as a proof of mechanism.



   - This cannot become `one new attack region -> one new model head` in the final system.



   - Needed: bounded region registry, top-k region routing, shared/global attack head or limited expert set, region prototypes, merge/split policy, and region-balanced weights.







3. **Support bank / attack-core generalization is insufficient.**



   - issue27bb shows support validation is strong, but report-only medium/heavy attack can still drop.



   - This means the support bank and attack-core definition are too close to support validation and not robust enough for broader attack evaluation.



   - Fix support-query gap before full/larger benchmark.







4. **Active labeling is still a dev-side oracle simulation.**



   - Current active labeling assumes a development stream where selected labels are available after query.



   - Real incoming traffic may be ID, OOD benign, attack, or noise.



   - Before system claims, run mixed-stream triage where feature-only routing decides hard/review/suppress/unknown before labels are revealed.







5. **Review / unknown cost must be bounded.**



   - Review cannot become a dumping ground for every difficult sample.



   - Every gate must report hard alarm, review, suppress, and unknown rates by role.



   - Review/unknown are safety states, not detection success.







6. **ID/OOD/Attack prototype banks need stable online policy.**



   - Prototype compression is required for real-time use; online detection cannot compare every sample to all ID/OOD/support rows.



   - Still open: prototype budget, radius source, top-k region routing, update cadence, and whether banks are rebuilt or incrementally updated.







7. **OOD stress coverage of final OOD tail is not fully settled.**



   - issue27ba created a legal OOD stress pool from unused OOD-val benign files.



   - Final OOD remains report-only and must not be used to tune gates.



   - If legal stress pools miss final OOD tails, broaden only from development-side benign/OOD sources.







8. **Training/sample-weight policy still needs freezing.**



   - ID/OOD data are much larger than attack support; support can be drowned out, but ID/OOD cannot be underlearned.



   - Freeze ID/OOD/support sampling, sample weights, region weights, and per-region balancing before formal benchmark.







9. **Online update policy is not frozen.**



   - The final system should not retrain for every new packet.



   - Define when support bank expands, when prototypes update, when region registry changes, and when detector/head retraining is allowed.







10. **Formal benchmark remains blocked.**



    - Required before formal benchmark: OOD hard <= 1%, high and stable attack hard detection, bounded review cost, scalable region handling, mixed-stream realism, and larger/full 115D data contract.







<!-- issue27bc -->



## issue27bc - Attack-core purity, unknown band, and review budget







- primary_verdict: `pseudo_query_reveals_support_core_overfit`



- Added file-held-out pseudo-query on dev attack support to reduce support-val overfitting.



- Added prototype purity states: hard_alarm, suppress, review_conflict, review_unknown, review_overflow_no_alarm.



- Key result: raw attack alarms remain high, but strict pure-attack-core hard alarms collapse to 0 because attack rows are also near benign/OOD prototypes and become conflict/overflow.



- Final OOD, medium attack eval, and dev-heavy query remained report-only.



- next action: `issue27bd_attack_region_generalization_before_temporal_gate`.







<!-- issue27bd -->



## issue27bd - Conflict-aware attack shell and gate subspace diagnostic







- primary_verdict: `subspace_conflict_gate_promising_attack_recovered_ood_relaxed`



- selected prototype gate subspace: `HH`; raw detector remains full Kitsune115.



- Added pseudo-query-calibrated outer attack shell and conflict-aware hard override.



- Final OOD, medium attack eval, and dev-heavy query remained report-only.



- next action: `issue27be_past_only_temporal_consistency_on_conflict_gate`.







<!-- issue27be -->



## issue27be - Past-only replay audit on conflict gate







- primary_verdict: `past_only_replay_passed_with_dev_pseudo_caveat_ready_for_attack_region_bank`



- purpose: replay the frozen issue27bd conflict-aware shell gate under role-access and past-only visibility audit.



- replay matches issue27bd metrics: `True`; forbidden role access: `False`.



- caveat: dev-side pseudo-query rows remain part of gate calibration, so this is diagnostic rather than formal.



- next action: `issue27bf_bounded_attack_region_bank`.







<!-- issue27bf -->



## issue27bf - Bounded attack region bank







- primary_verdict: `bounded_attack_bank_heavy_gain_medium_retention_failure`



- purpose: test a bank-only bounded attack region memory with top-k routing while preserving the issue27bd full-115D raw score.



- dev attack hard min: `0.6428571428571429`; report-only attack hard min: `0.6415`.



- OOD stress hard max: `0.002456140350877193`; final OOD hard max report-only: `0.154`.



- attack >=0.93 gate passed: `False`; bottleneck is medium/pseudo-medium retention, not OOD stress or review budget.



- formal benchmark remains disallowed.



- next action: `issue27bg_shared_scorer_region_refinement_before_ood_gate`; do not enter OOD repair until attack hard min reaches at least `0.93`.







<!-- issue27bg -->



## issue27bg - Shared scorer region refinement before OOD gate







- primary_verdict: `shared_scorer_no_sufficient_attack_recovery`



- purpose: replace the issue27bd/issue27bf two-head raw scorer with one shared 115D HistGB attack scorer plus bounded region evidence.



- dev attack hard min: `0.6428571428571429`; report-only attack hard min: `0.4062222222222222`.



- OOD stress hard max: `0.0`; final OOD hard max report-only: `0.0006666666666666666`.



- formal benchmark remains disallowed.



- next action: `issue27bh_attack_scorer_region_design_rethink_before_ood_gate`.







<!-- issue27bh -->



## issue27bh - Attack scorer/region failure anatomy before new head







- primary_verdict: `support_query_gap_primary_blocker_before_new_head`



- purpose: decompose attack-side failure across raw scorer, support-query gap, region/gate, and feature-family evidence.



- dominant two-head failure layer: `raw_score_layer`; dominant shared failure layer: `raw_score_layer`.



- no 115D frontend/split changes; no OOD-gate repair; no formal benchmark.



- next action: `issue27bi_region_aware_metric_or_calibrated_two_head_design`.







## issue27bi - region-aware metric/calibrated two-head diagnostic







<!-- issue27bi_region_aware_metric_or_calibrated_two_head_design -->



- Verdict: `metric_or_calibrated_two_head_no_sufficient_attack_recovery`.



- Best candidate: `logistic_twohead_fusion_uniform_rows__ood_val_only` with dev attack hard-min `0.6428571428571429` and report-only attack hard-min `0.9373333333333334`.



- 115D frontend, split, and support pool were not changed.



- Final/report-only roles were score-only replay and not used for selection.



- Next action: `issue27bj_metric_head_refinement_or_task_boundary_audit_before_ood_gate`.







## issue27bj research design - Kitsune115 evidence decomposition







<!-- issue27bj_deep_research_kitsune115_system_design -->



- Status: research/design report only; no model run and no benchmark result.



- Recommendation: next technical experiment should be a small `metric evidence + prototype shell + bounded controller` smoke, not another threshold/shared-HistGB/OOD-gate tuning pass.



- Rationale: issue27bh/issue27bi point to support-query gap and raw attack evidence instability, so OOD gate repair remains blocked until legal dev attack hard-min reaches `0.93`.



- Output directory: `runs/issue27bj_deep_research_kitsune115_system_design_2026-06-08/`.







## issue27bk - task boundary then metric shell smoke







<!-- issue27bk_task_boundary_then_metric_shell_smoke -->



- Verdict: `metric_shell_no_attack_recovery_task_boundary_audit_next`.



- Boundary verdict: `task_boundary_high_distribution_shift_no_role_leakage`.



- dev attack hard-min: `0.5606060606060606`; report-only attack hard-min: `0.10355555555555555`; review max: `0.03`.



- 115D frontend, split, and support pool were not changed.



- Final/report-only roles were attribution/replay only and not used for selection.



- Next action: `issue27bl_task_boundary_or_attack_label_phase_audit_before_more_heads`.







## issue27bl - attack phase/onset/pseudo-query contract audit







<!-- issue27bl_attack_phase_onset_pseudo_contract_audit -->



- Verdict: `attack_phase_contract_mismatch_needs_rebuild_before_more_heads`.



- high-risk overlap flags: `15`; phase contract needs rebuild: `True`.



- No 115D frontend/split/support pool changes; no model training.



- Report-only roles were attribution-only and not used for selection.



- Next action: `issue27bm_phase_balanced_attack_contract_design_without_report_only_leakage`.







## issue27bm - phase-balanced attack contract design







<!-- issue27bm_phase_balanced_attack_contract_design -->



- Verdict: `phase_balanced_contract_ready_for_attack_only_diagnostic_with_tail_gap_caveat`.



- Rebuilt a legal development-side attack support/val/pseudo-query contract without using `attack_eval` labels or final/report-only roles.



- Primary contract: `phase_balanced_dev_v2`; support/val/pseudo rows: `128` / `64` / `1024`.



- Tail/late phase gap remains: `True`; this is for attack-only diagnostic, not formal benchmark.



- OOD-gate repair remains blocked.



- Next action: `issue27bn_attack_only_diagnostic_on_phase_balanced_contract_without_ood_gate`.







## issue27bn - attack-only diagnostic on phase-balanced contract







<!-- issue27bn_attack_only_diagnostic -->



- Verdict: `phase_balanced_attack_diagnostic_recovers_dev_and_report_only_attack`.



- Best dev candidate: `old_weighted_id_ood_support_w4` + `id_calib_alarm_0.01` with dev attack min `0.984375`.



- Report-only attack min under best dev candidate: `0.992`.



- No OOD-gate repair, no 115D/split changes, and no final/report-only selection.



- Next action: `issue27bo_ood_gate_repair_after_attack_contract_recovery`.







## issue27bo - fixed-support attack future-shift validation







<!-- issue27bo_attack_future_shift_validation -->



- Verdict: `attack_future_shift_validation_passed_with_report_only_late_replay_caveat`.



- Legal dev future attack min: `0.9970501474926253`; sealed attack replay min: `0.992`.



- No new support was selected from future/query/report-only roles.



- No OOD-gate repair was run.



- Next action: `issue27bp_attack_preserving_ood_gate_repair_after_future_shift_validation`.







## issue27bp - attack-preserving OOD gate repair after future-shift validation







<!-- issue27bp_attack_preserving_ood_gate -->



- Verdict: `attack_preserved_but_dev_ood_overbudget`.



- Selected attack subspace: `HH`; selected benign/OOD subspace: `MI_H_HHjit`.



- Dev attack min: `0.96875`; dev OOD hard max: `0.36133333333333334`; dev review max: `0.05`.



- Report-only attack min: `0.975975975975976`; final OOD hard max report-only: `0.16866666666666666`.



- 115D frontend, split, support, and raw attack scorer remained frozen.



- Formal benchmark remains blocked.



- Next action: `issue27bq_ood_risk_scorer_or_task_boundary_repair_before_larger`.







## issue27bq - decoupled OOD-risk scorer after attack recovery







<!-- issue27bq_decoupled_ood_risk -->



- Verdict: `decoupled_ood_risk_partial_pareto_improvement_but_ood_overbudget`.



- Dev attack min: `0.984375`; dev OOD hard max: `0.25933333333333336`; dev review max: `0.0`.



- Report-only attack min: `0.6501501501501501`; final OOD hard max report-only: `0.0`.



- Raw full-115D attack scorer, split, and support contract remained frozen.



- Final/report-only roles were replay-only.



- Next action: `issue27br_strengthen_ood_risk_or_task_boundary_before_larger`.







## issue27br - past-only temporal/interaction evidence feasibility







<!-- issue27br_past_only_temporal_interaction -->



- Verdict: `past_only_temporal_signal_present_needs_mini_interaction_graph`.



- Scope: medium diagnostic; no full/formal benchmark; no 115D frontend or split/support change.



- Temporal features use past-only role/source windows with `shift(1)`; final/report-only replay is not used for selection.



- Current sidecar supports timestamp/source/state ordering but not full IP/port flow graph construction.



- BQ base report-only attack min: `0.6501501501501501`; temporal report-only attack min: `0.6561561561561562`.



- BQ base dev OOD max: `0.25933333333333336`; temporal dev OOD max: `0.25933333333333336`.



- Next action: `issue27bs_mini_interaction_graph_or_temporal_controller_repair_without_final_leakage`.







## issue27bs - lightweight temporal evidence head







<!-- issue27bs_lightweight_temporal_head -->



- Verdict: `temporal_evidence_head_dev_passed_ready_for_controller_stability`.



- Scope: medium diagnostic; no full/formal benchmark; no 115D frontend or split/support change.



- Non-report roles were split into fit/select halves by past-only order; final/report-only replay stayed sealed.



- Selected feature set: `current_plus_temporal`; model: `histgb_shallow`.



- Dev attack min: `1.0`; dev OOD max: `0.0`.



- Report-only attack min: `0.972972972972973`; final OOD max report-only: `0.004333333333333333`.



- Caveat: this is a time-half medium diagnostic, not group/file-disjoint formal evidence.



- Next action: `issue27bt_temporal_head_stability_ablation_and_group_disjoint_replay`.







## issue27bt - temporal head stability and ablation







<!-- issue27bt_temporal_head_stability -->



- Verdict: `temporal_head_group_stable_with_parent_evidence_no_parent_ood_overbudget`.



- Scope: medium diagnostic; no full/formal benchmark; no 115D frontend or split/support change.



- Group-disjoint no-parent report attack min: `0.9831111111111112`.



- Group-disjoint no-parent dev attack min: `0.9375`; dev OOD max: `0.025333333333333333`.



- Group-disjoint current-plus-temporal dev OOD max: `0.0`; report attack min: `0.9707207207207207`.



- Caveat: id_calib is single-source in the medium asset, so broader validation is still needed.



- Next action: `issue27bu_no_parent_temporal_ood_risk_repair_or_mini_flow_graph`.







## issue27bu - unified temporal attack/OOD heads certification







<!-- issue27bu_unified_temporal_attack_ood_heads_certification -->



- Verdict: `parent_oodrisk_certified_current_system_hard_pass_unified_no_parent_needs_ood_margin_repair`.



- Scope: medium diagnostic; no full/formal benchmark; no 115D frontend or split/support change.



- Parent OOD-risk certified for medium diagnostic use: `True`.



- Group parent current+temporal report attack/final OOD: `0.9707207207207207` / `0.0006666666666666666`.



- Group unified no-parent current+temporal report attack/dev OOD: `0.9831111111111112` / `0.025333333333333333`.



- Next action: `issue27bv_freeze_certified_parent_oodrisk_channel_and_repair_unified_ood`.







## issue27bv - problem definition and frozen protocol before larger







<!-- issue27bv_problem_definition_and_frozen_protocol_before_larger -->



- Verdict: `protocol_frozen_for_larger_sanity_not_formal_benchmark`.



- Scope: documentation/protocol freeze only; no model run, no full benchmark, no 115D frontend or split/support change.



- Current candidate system: `Kitsune115D -> attack scorer -> certified parent OOD-risk channel -> past-only temporal evidence -> controller`.



- Current strongest evidence remains medium diagnostic only; do not call the temporal layer true causality or formal deployment proof.



- Larger/full is blocked until support update rules, newly sealed final roles, mixed-stream replay, temporal leakage checklist, and online cost model are satisfied.



- Next action: `issue27bw_larger_sanity_contract_construction_or_unified_ood_margin_repair`.







## issue27bw Larger Sanity Contract Construction







marker: `issue27bw_larger_sanity_contract_construction_2026-06-11`







- status: completed, contract-only



- primary_verdict: `larger_sanity_contract_ready_for_materialization_not_formal_benchmark`



- model run: no



- 115D frontend change: no



- larger size plan: first materialization target 3M-8M model-ready rows; do not exceed 10M emitted rows without explicit confirmation



- fixed support mode and active update mode are explicitly separated



- sealed final OOD / sealed final attack are forbidden for selection and are report-only from issue27bw forward



- key caveat: Gotham has only 8 mixed attack CSV files, so sealed final attack diversity is limited and this is larger sanity, not formal benchmark



- next action: `issue27bx_larger_sanity_materialization_dry_run_from_contract_v1`







## issue27bx Larger Sanity Materialization Dry Run







marker: `issue27bx_larger_sanity_materialization_dry_run_from_contract_v1_2026-06-11`







- primary_verdict: `larger_sanity_materialization_partial_needs_quota_or_frontend_fix`



- emitted rows: `226355` with 115D Kitsune features



- strategy: `train_state_then_eval_online`



- no model run, no formal benchmark, no final-role selection



- next action: `issue27by_larger_sanity_replay_current_frozen_system`







## issue27bx2 Materialization Quota/Cache Repair







marker: `issue27bx2_materialization_quota_cache_repair_2026-06-12`







- primary_verdict: `quota_cache_repair_partial_needs_contract_or_quota_revision`



- issue27bx shortfalls were traced to quota/materialization planning, not model failure.



- Next materialization should use same-role fallback and per-file cache keys.



- Sealed final roles remain forbidden for fallback, fit, threshold, and selection.



- Current stage remains data/interface preparation; no formal benchmark is authorized.







## issue27bx3 500k Cache-aware Materialization Retry







marker: `issue27bx3_500k_cache_aware_materialization_retry_2026-06-12`







- primary_verdict: `cache_aware_500k_materialization_ready_for_1m_runtime_profile`



- materialized rows: `500000`



- final/report-only roles remained sealed from fit/threshold/selection.



- No model training or formal benchmark was run.



- Next: 1M materialization/runtime profile before mixed-stream protocol work.











## issue27bx4 - 1M Kitsune115 runtime profile attempt



- verdict: cache_aware_1m_runtime_profile_blocked_by_local_runtime_bottleneck



- result: completed 845,000/1,000,000 rows; no certified 1M asset was produced.



- blocker: local runtime bottleneck on `processed/iotsim-building-monitor-1.csv` in `dev_future_attack_query` after >70 minutes active CPU with empty stderr.



- cleanliness: preserved; no cross-role fallback, no final/report-only reuse, no model training, partial canonical files quarantined with `INCOMPLETE_INTERRUPTED_`.



- next: issue27by_runtime_optimized_1m_or_slurm_materialization.







## issue27by Runtime-optimized 1M/Slurm Materialization Pipeline







marker: `issue27by_runtime_optimized_1m_or_slurm_materialization_2026-06-12`







- primary_verdict: `slurm_ready_per_file_pipeline_smoke_passed`



- Created a state-snapshot-dependent per-file cache pipeline and Slurm array plan.



- No certified 1M asset yet; merge remains blocked until all non-ID caches are complete and quarantine-free.



- No model training or formal benchmark was run.







## issue27bz Slurm 1M Cache Execution and Certified Merge







marker: `issue27bz_slurm_1m_cache_execution_and_certified_merge_2026-06-14`







- primary_verdict: `slurm_1m_certified_asset_ready_for_larger_sanity_replay`



- materialized rows: `1000000`



- final/report-only roles remained sealed from fit/threshold/selection.



- No model training or formal benchmark was run.



- Next: issue27ca_larger_sanity_replay_on_certified_1m_asset before mixed-stream protocol work.







## issue27ca Initial Support Bank Contract on Certified 1M







marker: `issue27ca_initial_support_bank_contract_on_certified_1m_2026-06-14`







- primary_verdict: `initial_support_bank_contract_ready_with_attack_taxonomy_limit_caveat`



- legal support candidate rows: `89900`.



- support budget grid: `[32, 64, 128, 256]`; default B=128 is global, not per attack type.



- `attack_support_candidate_pool` is explicitly separated from the initial support bank.



- Caveat: current 1M support candidate pool contains only Telnet Brute Force attack labels.



- No model training or formal benchmark was run.







## issue27cb Broader Attack Support Candidate Contract







marker: `issue27cb_broader_attack_support_candidate_contract_2026-06-14`







- primary_verdict: `broader_support_contract_partial_needs_targeted_multitype_materialization_and_onset_realign`



- Read-only audit; no extracted 1M asset files were modified.



- Current legal support exact attack labels: `{'Ingress Tool Transfer': 214, 'TCP Scan': 46685, 'Telnet Brute Force': 39437}`.



- Support benign contamination rows that must be filtered before support selection: `3564`.



- Missing preregistered support-file attack types: `['C&C Communication', 'File Download', 'Merlin C&C Communication', 'Merlin ICMP Flooding', 'Merlin TCP Flooding', 'Merlin UDP Flooding', 'Mirai C&C Communication', 'Mirai GRE Flooding', 'Mirai TCP Flooding', 'Mirai UDP Flooding', 'Reporting']`.



- Next: targeted multi-type attack materialization and onset realignment before model replay.







<!-- issue27cc_targeted_multitype_attack_materialization_and_onset_realign -->



## issue27cc Targeted Multitype Attack Materialization and Onset Realign







- Verdict: `targeted_multitype_attack_contract_ready_for_slurm_exact_label_materialization`.



- Current 1M attack roles are not sufficient for model replay because support/query/final attack rows must be exact-label filtered.



- Reusable current exact support rows: `86336`.



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







## issue27ckbq causal MiniRocket consensus formal result







- canonical result: AMD job `153037`, experiment commit `7bb51cb087b54c99ffd1df248b3692336ce9637b`, recovered validator commit `aecb2ca65f3c8536587efb7b0df385becb54b9b7`;



- scientific verdict: valid seed-27 `NO_GO`; execution recovery did not retrain or change scores/gates;



- OOD signal: IP-camera `100 -> 8.1%`, predictive `100 -> 57.589%`, stream `100 -> 29.7%`, hydraulic `72.367 -> 45.7%`;



- attack failure: overall `-6.945 pp`, future `-12.639 pp`; 16,606 of 16,950 suppressed C1 attacks are future-query rows;



- mechanism: temporal-only branch rescues 37 attacks and adds 68 hydraulic false alarms, so the useful normality effect is almost entirely static;



- capability audit: zero feasible threshold pair in the current score space satisfies the overall/family attack constraints plus all four weak OOD-signal constraints; closest report-oracle point still loses `2.418 pp` attack recall;



- integrity: 385/385 support once, 69 gate-only support-val, zero report fit/select, zero future/forbidden event use, zero alignment gaps, review zero;



- frozen: strict 1M/T0 and auxiliary manifests, report canaries, cooler sealed, past-only report, C1 anchor semantics;



- superseded: CKBQ seeds 37/47, raw9 MiniRocket consensus repeats, and threshold-only repair on the current scores;



- next_action: source a mature flow/connection-process representation that can protect unseen scan/brute-force and shifted future attacks before another result job.


## 2026-10-22 诊断与现代头执行接续

用户已授权按已定规格执行。当前新目录：`runs/diagnostics_d1_d2_v1_20261022`与`runs/modern_head_new_lineage_v1_20261022`。代金券实例停机再启动后公网IP变为8.145.62.163，本地SSH别名已更新并沿用原主机密钥验证。旧数据及结果仍在。

执行偏好（用户再次明确）：长任务不持续调用AI轮询；用普通后台脚本与可见进度展示。代理只在启动验收、异常诊断、阶段完成验收时读取必要状态。有实际编码、集成、分析任务时继续完成，不以避免轮询为由提前退出。进度页为http://127.0.0.1:18765/ 。

已完成：原环境477021条CAL/A/B查询的3个seed及集成分数逐bit回放一致；9份参考资产评分完成。保存的几何模块误报路径复盘完成，旧A的344条修正UID全部物理身份匹配。D1/D2正式集成与现代头入口实现进行中，不能宣称现代头已训练。


### 同日固定诊断已完成

见 `runs/diagnostics_d1_d2_v1_20261022/RESULT_REVIEW.md`。D1选择源封顶λ=0.10，但B2集成新增26条攻击漏检，科学FAIL，不接入主比较；D2四材料均不满足预登记分组条件，NOT_EVALUABLE，0次拟合。继续固定三家头+原v3几何入网配对。旧A344条UID全部匹配；不把当前失败抹去旧正向结果。现代包v2已离线部署并通过三家真实源FIT小样训练、保存和逐bit回放；正式训练是否启动见后续执行回执。


### 同日现代头正式链已启动

`runs/modern_head_new_lineage_v1_20261022/package_v2`已在代金券服务器部署，13项本地测试及3家真实源FIT小样保存/逐bit回放通过；正式systemd服务`paper04-modern-head-20261022-v1`已进入MLP_QUERY_BCE seed27训练。完整矩阵为9新头及3家×4参考策略配对，沿用已验收缓存和v3几何模块。输出`/srv/paper04/runs/modern_head_new_lineage_20261022_v1`；启动回执`LAUNCH_RECEIPT.json`，结果尚待完成。TabM纯训练量级约21小时/三seed，非总任务ETA。资源8CPU/16GiB，4数值线程、14GiB保护，单重worker。自动停机未启用，大结果不自动重复拉取；完成后验收并拉回重要结果。用户明确不持续AI轮询，进度http://127.0.0.1:18765/ 。
