# 接手入口历史

## 2026-11-03 Linux工程授权前入口快照

# 当前状态

更新：2026-11-03。后续只覆盖本区块，不再向入口追加历史。

1. **唯一方法**：C5（p=3）冻结，A/B仅作开发证据。[冻结JSON](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。
2. **现有结果**：B主视图选中查询误报1.55%，全时段2.24%；A召回99.82%。独立外部效果尚未确认。
3. **已完成**：Edge三类各20,000查询+4,124参考封存；v2修复四项复核问题，82项本地检查及60,000查询元数据核验通过，完整依赖与增量包已核验。
4. **下一步与分工**：具体授权后执行1CPU/8GiB/2小时同运行时Linux工程验证；真实恢复/末段资源与正式预算仍待验。此次由实验11 Codex复核并修复，下次独立复核交小anti；不自动重投。
5. **最新证据**：[v2修复验收](collab/20261103_edge_formal_v2_repair_acceptance_codex.md) · [原v1独立复核](collab/20261103_edge_formal_independent_review_experiment11_codex.md) · [181418旧切片验收](../edge_preflight_io_repair_v1_20261103/FINAL_ACCEPTANCE.json)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-03 v2修复前入口快照

# 当前状态

更新：2026-11-03。后续只覆盖本区块，不再向入口追加历史。

1. **唯一方法**：C5（p=3）冻结，A/B仅作开发证据。[冻结JSON](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。
2. **现有结果**：B主视图选中查询误报1.55%，全时段2.24%；A召回99.82%。独立外部效果尚未确认。
3. **已完成**：Edge封存正常/HTTP/UDP各20,000查询+原4,124参考；正常17,025组件全部覆盖；Linux候选包1.127GiB已逐成员验SHA。
4. **下一步与分工**：用户指定本次由实验11 Codex复核、下次交小anti。独立复核为CHANGES_REQUESTED：先修依赖身份、父子资源监督、当前轮次终态和超时scratch清理，再复验并申请1CPU/8GiB/2小时Linux验证；正式预算未锁、不自动重投。
5. **最新证据**：[实验11独立复核](collab/20261103_edge_formal_independent_review_experiment11_codex.md)（原63项测试与元数据核验通过，1项P1/3项P2待修） · [181418验收](../edge_preflight_io_repair_v1_20261103/FINAL_ACCEPTANCE.json)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-03 实验11独立复核前入口快照

当时C5/p3与A/B开发线冻结；B主视图选中查询误报1.55%、全时段2.24%，A召回99.82%。Edge三类各20k和4,124参考已封存，181418真实小切片PASS。完整worker/恢复/统计本地检查通过；当时安排待小anti复核后申请1CPU/8GiB/2小时工程验证。20k条件估算16.77h、带裕量39.79h，均非承诺；正式评价未启动。随后用户指定实验11 Codex完成本次复核，下一次交小anti，当前状态见入口。

本页封存 2026-11-02 入口简化前的完整原文。历史沿用原入口“最新更新在前”的倒序；同日条目保持原记录次序，不推造更细时间。旧状态仅作历史取证，以 [当前入口](NEW_CHAT_START_HERE.md) 为准。

以下原文完整保留，包括当时的状态、链接、校验值与导引。

---

**2026-11-02 最新：Edge-IIoTset获准三包均已完整获取，正常资格核验已交由本地普通程序执行。** [获取与启动回执](collab/20261102_edge_iiotset_acquisition_and_qualification_start_codex.md)／[当前进度](../edge_iiotset_raw_qualification_v1_20261102/PROGRESS.md)。共621,736,430原包字节；两攻击角色门通过仅允许继续固定正常，尚不代表完整资格。最终看新目录RESULT/CAPINFOS_CROSSCHECK/CONTINUATION_FINAL及自动生成的collab最终稿；0模型/编码/距离/训练/云端/删除，不持续AI监测。下方“未授权/未下载”是本次原包授权前的历史快照。

**2026-11-02 最新：其他外部候选官方资料复筛完成，建议下一次只核 Edge-IIoTset 固定三包，尚未下载。** [综合回执与获取草案](collab/20261102_external_dataset_rescreen_and_next_acquisition_codex.md)；[本轮进度](../external_dataset_rescreen_v1_20261102/PROGRESS.md)。已取得官方目录/README及作者论文，TableVI补上edge/sensor/AP IP，采集说明是多日非连续、一次最多3小时，实际7200秒/同物理目标/直接ACK与UDP仍待原包。固定温湿度正常+HTTP flood+UDP flood共621,736,430字节；下一阶段先两攻击核目标，再决定这份固定正常，不自动换设备/扩大。ACI保留但2.5KB时间表/README需合法DataPort订阅；MedBIoT/DIAD暂无可直接用主确认材料。本轮0新PCAP/CSV/编码/距离/模型/训练/云端/删除/移动；C5 p=3与A/B冻结SHA保持，175项资料完整性检查通过。下一原包阶段未授权/未执行；无持续AI监测。下方CICIoMT暂停仅指已得组合，不是整集淘汰。

**2026-11-02 最新：Benign_train/test已实际获取并全量核验，锁定补救路径失败，暂停当前CICIoMT2024因果主确认组合。** [补救最终回执](collab/20261102_ciciomt2024_benign_rescue_result_codex.md)。新增493,060,044字节/2,313,216帧，日期Sep13–14，仍晚于Aug30/Sep1已选攻击，最近相差11.94天；两包各9项容器/时钟checks与独立复算均通过，0截断。仅暂停已得六份不同原包的角色组合，不淘汰整个数据集、不盲下其他攻击；后续转其他候选元数据门。原包保留在原下载位置，未删/移/复制/上传，0模型/编码/距离/训练/云端，C5/A/B冻结与旧审计资产不变，无持续监测。当前内置已登记目录是browser2/tab4，tab2是登记表。下方Benign未取得/待登记/资料门受阻均为历史快照。

**2026-11-02 最新补充：Benign元数据有界核查收束，暂未补齐大小/时序/设备资格；本轮无新原包或删除。** [资料门与保留建议](collab/20261102_ciciomt2024_benign_metadata_gate_and_retention_codex.md)。官网可见条目无大小日期，独立HEAD均403；当前train目录请求显示需要登记，未重新提交个人信息。PCAP指定范围6份共2.474GiB，C盘0.447GiB为重复正常下载副本，D两攻击包1.580GiB各仅一份。最终无主验证/补充用途可归档或按具体指令删除原包，保留小型来源/哈希/审计；当前先保留四份净原包。C5与A/B冻结、四包失败封存回执不变；无模型/训练/云端/持续监测。

**2026-11-02 最新：CICIoMT2024 两攻击包已得并全量核验，当前四包组合因果主测试失败，两个独立agent讨论已完成。** [汇总回执](collab/20261102_ciciomt2024_raw_qualification_result_and_next_codex.md)。攻击共21,955,914帧（8月30日/9月1日），全部早于现有11月正常，最近相差61.21天；不能用未来参考修正过去查询。仅否定当前组合，不淘汰整个数据集。下一步仅核已知Benign_train/test的更早同目标可信正常、完整7200秒及角色证据，ACK/UDP攻击向仍未通过；无法补齐则暂停本集主确认。0模型/编码/距离/训练/云端运行，不复制攻击大包，C5 p=3与A/B冻结保持。下方下载受阻/等待攻击包均为历史快照。

# Paper04 新对话接手入口

**2026-11-02 原包资格最新：Idle与Active已真实下载并完整核验，攻击原包获取受阻。** [阶段回执](collab/20261102_ciciomt2024_raw_qualification_partial_codex.md)／[当前进度](../ciciomt_raw_qualification_v1_20261102/PROGRESS.md)。共479778175字节、1369566帧，受控原件副本在paper04/data_external/ciciomt2024/qualification；TShark/dpkt守恒PASS。Idle实际2段各13h、中间11h空洞；Active为11/6—24的9段，7501—20054秒，Idle严格早于Active。13共有单播MAC含网关/控制器，不能当目标数；ACK/UDP攻击向和身份仍未通过。TCP/UDP专用下载超时，普通导航被应用屏蔽；283035192字节未完成对象保留但无完整攻击文件。已请求用户Chrome下载test内DoS-TCP/DoS-UDP两包，不重复实验授权。按用户要求待查验完整再与其他agent讨论；0模型/云端，不持续监测。下方“原包0”为旧快照。

**2026-11-02 外部获取更新：CICIoMT2024 登记后目录及三份官方PDF已实际取得。** [获取回执与原包候选](collab/20261102_ciciomt2024_registered_metadata_acquisition_codex.md)／[机器目录清单](../c5_external_test_preparation_codex_20261102/acquired_direct/REGISTERED_DIRECTORY_MANIFEST.json)。用户在内置浏览器完成登记，19页/113个相关PCAP链接、3PDF共7203702字节已保存核验；原包下载仍0，7个核心正常/TCP/UDP候选已定位，但目录不显示大小，尚非最小字节最终选择。三份说明缺MAC/IP、精确时序和攻击方向，7200秒/后段正常/直接ACK及UDP资格仍未通过；不因目录存在就启动评价。真实目录大小写WiFI_and_MQTT，合法会话已保留，无凭证导出。下一步先定大小、可恢复传输和存储，再只读原包资格；C5p3及A/B冻结保持。下方“本轮仅公开HTML／目录未取得”为旧快照。

**2026-11-02 当前唯一方法：C5 p=3 已正式冻结，A/B 开发线关闭。** [方法冻结回执](collab/20261102_c5_p3_method_freeze_receipt_codex.md)／[机器冻结](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。用户确认 Claude 第4节“首个边际收益<5%步进保留较小p”，3→4为8/347，因此固定p3；规则在A/B结果已知后制定，完整网格及局限保留。主视图B逐样本FPR1.547472%、A召回99.821645%，A新增108条ACK标签漏报；Power3.085662%、Net2.278787%、full B2.235920%，不声称全设备/全时段达标。46项方法/校准/结果身份已核，旧C3/C4审计保持。下一步为[外部获取清单](collab/20261102_ciciomt2024_acquisition_checklist_codex.md)与[执行卡草案](collab/20261102_c5_external_test_execution_card_draft_codex.md)：CICIoMT真实Wi-Fi候选7台、作者称idle两次13h，但真实叶文件、时序、同设备历史、足量后段正常及直接ACK/UDP攻击均须资格核实。ACK攻击尚未证实；反向ACK不替代。原包未到且资格未过前0推理/距离/评价，外部适配器和权重schema待评分前封存；本轮仅公开HTML100126字节，无原包/训练/云端/外部评价，不持续监测。下方“C5未选p”及“C4当前”为历史记录，已由本条取代。

**2026-11-02 C5 本地独立复算已完成，尚未写生产 p：** [Codex 回执、A 攻击代价与源 CAL 纠偏](collab/20261102_c5_kernel_independent_replay_reply_codex.md)／[完整指标附表](../c5_kernel_independent_replay_codex_20261102/METRIC_TABLES.md)／[封存核验](../c5_kernel_independent_replay_codex_20261102/VERIFICATION.json)。p=1 与 C4 两池双视图四头逐位一致；五档共80份A/B保护报告全PASS。主视图ensemble：B p2/p3/p4逐样本FPR=2.133147%/1.547472%/1.350008%；p3 A召回99.821645%、FN33→141，新增108全Heim TCP ACK；Power3.085662%、Net2.278787%仍>2%，full B p3=2.235920%。179602真实4728点/12 donor并集源CAL重建通过，p1—4四头零撤警；正支持饱和127/227各撤同一SimCam攻击一次，严格源零撤警FAIL。HIST_DEV首次边际<5%为3→4，原句未定保留起点/终点，不能自动宣称唯一选p3；规则仍须披露A/B已知后制定。22项AB相关身份后验保持，源二验21输入/19输出通过；无训练/新编码/云端/外部评价。C4采纳资产未改，A/B均CONSUMED_DEVELOPMENT_ONLY；不持续监测。

**2026-11-02 当前：C4 作业 180772 已完成取回、评价和最终独立验收，PASS / ADOPT_C4；逐样本 2% 目标未达。** [最终结果与分账](collab/20261102_b_sample_fpr_c4_result_and_readout_codex.md)。观察窗后集成：B逐样本FPR 8494/74444=11.409919%→3606/74444=4.843910%，减少4888条/57.55%；加权1.750526%→1.396094%。A仍14/96041，A/B攻击FN仍33/5，16项保护门全PASS，零新增正常误报/攻击撤警。Netatmo UDP误报2813→0；残留主要Power1478、Net1157、Samsung831，且仅1条零支持。距池2%仍差至少2118条。累计40235.79/修订46861秒、计费编码37442、988569299距离对均预算内。原合同method_frozen/no_further_AB_search保持；只读讨论用最终新数组衔接，未追加实验或持续监测。下方RUNNING/待取回为历史快照。

**2026-11-02 12:56 当前：追加预算恢复作业 180772 已实际提交并 RUNNING。** [执行回执](collab/20261102_b_sample_fpr_c4_budget_amendment_and_resume_codex.md)。远端预检33.27秒PASS、134/134工程检查通过；已复用三设备20480完整编码及Netatmo12288快照，冻结编码worker启动中，0新距离/无新科学成绩。新累计账46861秒（旧28861＋追加18000）；charged编码上限37442，唯一人口32768。实际作业与自动链在 `history_sample_coverage_c4_budget_deployment_20261102` 的SUBMIT_RECEIPT/STARTUP_VERIFICATION；新科学包batch_resume的FINAL_ACCEPTANCE为最终入口。右侧18789正常，普通程序继续取回/验收；不持续AI监测。下方“预检中/待批准”等为历史快照。

**2026-11-02 最新：用户已批准 C4 追加18000秒，恢复自动流程已启动；代码已上传安装，远端预检中。** [预算授权、持久批次恢复及执行入口](collab/20261102_b_sample_fpr_c4_budget_amendment_and_resume_codex.md)。新包 `history_sample_coverage_c4_batch_resume_v1_20261102`，卡SHA a37cc580…68614；原累计28861秒保留，新账上限46861秒，charged E3上限37442，唯一人口32768。三设备20480编码及Net完整12288快照复用，无原包重扫；Net中途4658条仅内存须重算，新批次真实落盘。科学集成103项＋部署31项通过，远端注册134项；新部署 `history_sample_coverage_c4_budget_deployment_20261102` 普通程序PID21308继续预检→唯一提交→最小取回→DEV/条件AB/独立验收，作业号看该部署SUBMIT_RECEIPT。右侧18789已更新；大文件留超算，不持续AI监测。下方“等待追加预算”是历史快照。

**2026-11-02 最新：C4 180670 已因 WALL_SECONDS_LIMIT 停止，原累计8小时预算耗尽；保留现场，未重新提交。** [完成进度、剩余时间、存储及预算请求](collab/20261102_b_sample_fpr_c4_budget_stop_storage_and_resume_codex.md)。三设备20480条完整编码可复用，Netatmo4967010帧准备和12288快照已完成，但4658条中途E3只在内存，encoded目录仅ledger，不能直接离线验收。预计补完约2.5～3.5小时，建议申请追加18000秒/累计charged E3上限37442；**等待用户追加预算授权，不自动重投**。独立副本批次持久化31项合成/原runner检查通过，尚未接线/封存/上传。D剩8.601GiB，超算个人目录继续留大中间产物，本地不再取回原包/SQLite等；本轮无删除/移动。18789已显示停止与预算请求，不持续AI监测。下方180670运行中均为历史快照。

**2026-11-02 C4 提交前600秒预检超时已修复，实际作业 180670 已运行/node185：** [分阶段预检、恢复边界与实际提交](collab/20261102_b_sample_fpr_c4_staged_preflight_repair_and_actual_submission_codex.md)。远端逐阶段预检28.36秒PASS（含246真实包头、三设备20480编码与59项工程检查）；新增控制器11项、状态持久化3项检查通过。沿用已安装header科学包和原执行卡，未重新上传原包/修改科学方案；大库完整校验由原正式流程执行，未移除。预算仍剩4266秒，右侧18789由普通程序自动取回及验收，不持续AI监测。当前无新科学成绩；下方“预检中尚无作业号”等均为历史快照。

**2026-11-02 C4 180591包头布尔格式故障已修复，修复包已上传，当前超算预检中（尚无新作业号）：** [实证修复、恢复边界和自动重提交流程](collab/20261102_b_sample_fpr_c4_header_repair_preflight_codex.md)。246/246真实包头、59项工程、8项交付检查通过；复用三设备20480编码及Netatmo完整候选/索引/选点，只补未完成步骤。普通程序预检通过后自动提交并在右侧18789显示作业号，不持续AI监测。当前原预算剩4266秒，无新科学成绩。后续正式提交回执将由有界普通程序更新；下方180591运行中为历史快照。

**2026-11-01 C4 180552 已因 Netatmo 解码日志策略检查停止，检查点续跑180591已运行：** [故障、恢复边界、剩余预算与提交回执](collab/20261101_b_sample_fpr_c4_netatmo_checkpoint_repair_codex.md)。三台设备20480条编码完成，Netatmo4967010帧第一遍扫描/3592947合法endpoint已完整提交，后续复用它们，只补第二遍连续上下文、Netatmo编码和唯一验收。492条固定MPEG SECT/PES诊断须精确匹配并独立审计246个原包头；其他诊断继续拒绝。54项工程、8项交付检查通过，709共享pin不变。累计扣费23751秒，原预算剩5049秒；预计剩约1～1.5小时，不含排队，超预算明确停止。新目录 `../history_sample_coverage_c4_checkpoint_repair_v1_20261101/`；超算54项检查通过，实际提交180591/RUNNING/node185，作业号看 `../history_sample_coverage_c4_checkpoint_deployment_20261101/SUBMIT_RECEIPT.json`，最终看新目录FINAL_ACCEPTANCE。右侧18789由普通程序更新；不持续AI监测。下方180552运行中为历史快照。

**2026-11-01 C4 内存隔离修复已提交 180552，当前 RUNNING / node185：** [内存隔离与提交回执](collab/20261101_b_sample_fpr_c4_memory_isolation_repair_and_submission_codex.md)。独立 `history_sample_coverage_c4_memory_repair_v1_20261101` 将准备和模型编码拆为串行新进程，仍 4CPU/8GiB；核验复用 TP/Power 共12288行，Samsung未完状态不复用。扣除旧失败9064秒后剩19736秒。36项本地/超算检查及8项交付检查通过；第一次修复提交被CRLF拒绝、无作业号，已改LF，远端再预检通过后实际提交180552并确认Samsung开始扫描。当前作业号以 `../history_sample_coverage_c4_memory_submission_repair_20261101/SUBMIT_RECEIPT.json` 为准，最终验收以新实现目录为准；右侧18789自动更新。下方180526运行中均是历史快照；当前无新科学成绩。

**2026-11-01 C4 提交前故障已修复，作业 180526 已运行：** [修复与提交回执](collab/20261101_b_sample_fpr_c4_config_order_repair_and_submission_codex.md)。原失败为配置字段排序触发顺序敏感哈希，尚未提交；恢复原顺序后，参数值/执行卡/科学源码不变，原材料零重传，超算 23 项检查全部通过。实际作业 180526 RUNNING / node185，右侧 18789 继续自动更新。修复部署为 `../history_sample_coverage_c4_deployment_repair_v1_20261101/`；当前没有新成绩。用户长期约定：确认启动和进度页正常就结束当前轮次，不持续 AI 监测。

**2026-11-01 C4 完整实现已锁定，上传进行中：** [实现、实际预算纠偏及执行回执入口](collab/20261101_b_sample_fpr_c4_implementation_and_execution_codex.md)。23 项工程、7 项交付检查通过；328,202 行 C3 保存结果复现。真实距离对上界 997,017,497 / 10 亿。复用旧三设备 DEV，只新增 Netatmo DEV 编码和固定历史参考补点。当前不代表已提交；作业号以 `../history_sample_coverage_c4_deployment_20261101/SUBMIT_RECEIPT.json` 为准，最终结果以 `../history_sample_coverage_c4_execution_v1_20261101/FINAL_ACCEPTANCE.json` 为准。右侧进度端口 18789。本轮一次验收，2% 单列目标；A/B 仍仅开发证据。


**2026-11-01 用户已重新开启逐样本误报开发：** [B 逐样本误报诊断、材料核验与 C4 实现进展](collab/20261101_b_sample_fpr_reopened_diagnosis_and_c4_codex.md)。B 主视图 8494/74444=11.409919%，1.750526% 是另一加权口径，不能替代。到池级 2% 至少还需修复 7006 条。Netatmo/Samsung/Power 贡献 98.28% 残留；本轮完成保存数组审计、320 条 Netatmo 邻居重放和已下载 Netatmo 历史包/稳定时序核验。C4 固定选择器已实现、8 项合成检查通过，完整 runner 尚待接通，未编码/补库/新 A/B/提交超算。用户新指令取代下方“不再开发”的当前行动限制，C3 封存结果仍保留为历史基准；A/B 仍为消费过的开发数据。

**2026-11-01 外部验证数据线已恢复调研：** [当前获取状态与下一批材料](collab/20261101_external_validation_acquisition_status_codex.md)。本对话继续负责实验，论文可并行；C3冻结保持。HCRL五包已实测正常仅301.09秒，主验证淘汰不扩大下载。当前优先核CICIoMT2024真实Wi-Fi子集：官网有晚间到次晨idle采集线索，但实际时长、时序、身份排重和标签尚未闭合；实际下载入口是个人信息登记表，不能将“公开免登录原包”当已核事实。ACI仍需登录/订阅，2.5KB时间表和README未取得。下一阶段先取设备/文件目录、时间表与必要最小原包做资格核验，通过后再定向批量获取和冻结外部评价卡。本轮仅刷新163612字节公开HTML，零新PCAP/登记提交/模型评价。



**2026-11-01 C3 最终独立验收完成，方法已冻结：** [最终结果与冻结回执](collab/20261101_history_normal_reference_c3_result_and_method_freeze_codex.md)／[独立验收](../history_normal_reference_c3_progress_repair_v1_20261101/FINAL_ACCEPTANCE.json)／[机器冻结](../history_normal_reference_c3_progress_repair_v1_20261101/output/METHOD_FREEZE.json)。PASS_C3_IMPROVEMENT，采用 C3_ADMITTED_SMALL_BANK_COMPLETE；完整目标仍 IMPROVED_NOT_PASS。原7200秒观察窗后加权主集成：A FPR 3.316088%→0.746644%、召回100%→99.989781%，新增33条Heim TCP ACK攻击漏报；B FPR1.750526%、召回99.994632%保持，新增漏报0。Heim FPR6.631944%→1.493056%，FP52→13，修复39条TCP，10条UDP不变。Power3.478112%仍未达设备2%；full A/B FPR5.171387%/2.100277%，不能冒充全时间段达标。16个full/主视图四头保护门全PASS，正常告警无增加，328202行独立核验、750输入SHA保持。超算180460编码278点已完成；首次本地进度写入失败现场保留，独立修复19项检查通过，第2次进程为首个完成的候选评价，累计计算上界322203122/4亿、评价335.172秒。A/B保留CONSUMED_DEVELOPMENT_ONLY；不再据其改方法，后续外部确认/强基线/论文。下方运行中或未实现条目均为历史快照。



**2026-11-01 C3 进度故障已修复，评价已恢复启动（启动快照）：** [修复与恢复回执](collab/20261101_history_normal_reference_c3_progress_repair_codex.md)／[当前进度](../history_normal_reference_c3_progress_repair_v1_20261101/PROGRESS.md)。超算 180460 已完成 278 点编码；首次本地评价因 Windows 进度文件替换拒绝访问中断，未生成候选 A/B 判决或指标。原现场封存，独立修复目录 19 项检查通过，复用原编码和全部科学规则，用户已明确授权“修复然后重新提交”。第 2 次评价进程已启动，累计距离对保守上界 322,203,122 / 400,000,000。后续采用 C3 或回退 C2 仍由原门决定；结果须以 FINAL_ACCEPTANCE.json 和最终回执为准。按用户要求不持续 AI 监测，程序自行运行并更新进度。下方“C3 未实现/运行”为历史快照。



**2026-10-31 C2 复核与 D3 只读诊断完成，C3 尚未实现/运行：** [Codex 回写、精确门槛与唯一 C3 建议](collab/20261031_history_normal_reference_c3_contract_review_and_d3_codex.md)／[D3 机器证据](../history_normal_reference_d3_readonly_v1_20261031/D3_EVIDENCE.json)。Antigravity 原稿 SHA 8cc5aeb3…8449 核验一致；14.69秒保存数组/邻居审计，26项输入/源码不变，零解码/前向/新距离/远端作业。Heim 672正常/52FP 的加权FPR6.631944%，未加权7.738095%；TCP单行权重不等，“救回37条”不是正确门，UDP不变时需移除4.631944pp，29～39只是计数上下界，不能据此挑帧，Wilson13/672不能充当加权区间。Power全量残留1865，1024仅trace抽样；169条在support=1仍FP、1696条有幅度空间，下界0.426344%复现D1，不能宣称补点无效。粗TCP阶段/历史年代差不足以确定Power补点方案。本轮建议唯一C3_ADMITTED_SMALL_BANK_COMPLETE：已准入历史来源按设备/协议≤原4096容量则全取合法点，大库复用C1；A189/190/191最多新增278，B唯一小库TP-UDP已全取3683，其余不变。C2/λ/几何/2小时窗口冻结，不新增Power/端点豁免分支；一次C3后按预写安全/收益门采用C3或回退C2并冻结。即便Heim达标，Power3.478112%仍是局限，完整目标不能报PASS。Amcrest6097/6103正常告警反弹已核实，12.036345%为旧源C-own预检，不证明重传根因。A/B仍CONSUMED_DEVELOPMENT_ONLY；下一交付是上述单候选实现与执行卡，不再循环原则稿。



**2026-10-31 C2 已完成并独立验收 PASS：** [结果及 Antigravity 复核材料](collab/20261031_history_normal_reference_c2_syn_guard_result_codex.md)／[机器验收](../history_normal_reference_c2_syn_guard_v1_20261031/FINAL_ACCEPTANCE.json)。已获用户本轮取回、实现、运行授权；7 数组+7 回执 SHA 全通过，13项工程检查、51输入封存，单次本机149.14秒/4核/峰值1.24GiB。源域预检完成、HIST_DEV PASS（误报相对RAW降57.58%）后评价一次A/B。主视图ensemble：A FPR3.316088%/召回100%；B FPR1.750526%保持、召回99.702935%→99.994632%，33条新增漏报全部恢复、剩5条RAW原有FN；两池四头攻击保护PASS。阶段PASS_C2_PROTECTION_AND_B_POOL，完整目标仍IMPROVED_NOT_PASS：Heim6.631944%、Power3.478112%仍>2%。不得漏报副作用：B单头227 FPR1.188215%→2.021072%；源180228 C-own G1/S FPR1.755626%→5.578834%，源预检仅诊断，不是新泛化通过。328202条判决/两池双视图四头指标独立重核通过，旧输入及C1结论不改。仍CONSUMED_DEVELOPMENT_ONLY；C3/新泛化模型未运行，无新训练/编码/距离。下方“C2未实现”均为历史快照。



**2026-10-31 Antigravity 的 D2 回执已复核，C2 固定为全设备规则，尚未实现/运行：** [Codex 具体回复与依赖清单](collab/20261031_history_normal_reference_d2_review_reply_codex.md)／[只读核验证据](../history_normal_reference_d2_review_v1_20261031/REVIEW_EVIDENCE.json)。接受先保护后覆盖；统一 TCP SYN 无 ACK 查询保留 RAW，替代下条四设备建议。ACK=0 是当前包标志，不能称为整条连接未收到确认。Heim189/190/191原包SHA通过，213 TCP+76 UDP候选，与现有LEARN/CIC_DEV捕获/SHA/已有包指纹零重叠；当前编码准入和收益未验证。183–188/192–193实际已有301条A查询，禁止改作参考。Power实际803个TCP组件/4096点，49153占705点、8443占1147点、8899占117点；“14324个短组件占满单点席位”错误，825/1024统计的是配对参考端口，不能当查询端口。源180228四份SCORES及三成员HIST_DEV q14仍需取回已有文件；不重跑源分支或编码，C2先过原DEV门再一次A/B，仍为已消费开发。C2本身不会降低误报，C3不夹带；本轮仅复核/规格，无新候选评分、下载、解码或远端作业，180435 FAIL_PROTECTION保持。



**2026-10-31 D2邻居诊断完成，泛化五包资格核验已结项：** [真实邻居结果及唯一下一步建议](collab/20261031_history_normal_reference_d2_trace_result_codex.md)；[HCRL/ACI资格结论](collab/20261031_hcrl_raw_qualification_and_aci_access_codex.md)。已获用户授权，取回23个旧产物SHA通过；6645条查询、29532235距离对、138.86秒、峰值2.15GiB，P1—P4及支持度/四头判决全部复现。Heim42条TCP误报均被唯一旧TCP参考E3距离挡住；Power1865条TCP误报均已有正支持；Samsung :4被撤回49条任一头攻击均配到正常SYN，只有2/49双邻居是同IP对换端口，临时端口主因假说不足。唯一优先候选为四目标设备TCP SYN无ACK查询保留RAW，不改阈值/库/几何；这是保护修复候选，不会自行降低A误报，尚未实现或执行新候选A/B。HCRL正常包实际仅301秒，不满足7200秒+后续正常，已淘汰同合同主泛化资格；ACI仍登录/订阅门，无外部模型评价。原180435 FAIL_PROTECTION保持。



**2026-10-31 Antigravity回复已复核，D1理论下界已算：** [Codex回写与窗口勘误](collab/20261031_history_normal_reference_after_180435_review_reply_codex.md)。原回复SHA772adb05…776c2d5一致。保存分数/原权重核算：主视图ensemble理想最大修正下HeimVision设备FPR下界0.347222%、Power0.426344%，不触发固定λ=.25幅度不可达；这是忽略实际支持/攻击保护的数学下界，非新成绩。临时端口双组件根因尚未由邻居trace证实，C2规则/预算/缓存与census复用仍有缺口；下一步限定既有产物清点和有界邻居诊断。**更正此前数据筛选：入口支持1/2小时，但当前A/B B2主视图实际均为7200秒观察后；新集同合同需2小时及后续正常，1小时/5400秒不足直接宣布同口径。** 本轮0模型/距离/解码/远端/原包下载，原180435 FAIL_PROTECTION保持。



**2026-10-31 结果讨论与独立泛化筛选：** [给Antigravity的180435讨论稿](collab/20261031_history_normal_reference_after_180435_discussion_for_antigravity.md)已准备，聚焦Samsung保护失败、HeimVision/Power残留及唯一后续候选；尚未收到该稿回复。[数据筛选](collab/20261031_independent_generalization_dataset_screening_codex.md)：优先核HCRL IoTID20原始源，ACI-IoT-2023备选，尚无新集完成原包资格验收。CICIoT2023与A的HeimVision/Eufy精确同MAC且采用整攻击场景标签，不作独立设备主确认。已取官方25KB说明表，确认逐包筛选规则，同时Creation Date并非采集日期；已列5个原包最小核验清单，原包下载/新模型运行均0。当前授权为讨论与研究，180435终态仍按下条。



**2026-10-31 18:27终态：历史正常参考180435正常完成COMPLETED/0:0，已评价一次A/B，科学FAIL_PROTECTION。** [结果解释](collab/20261031_history_normal_reference_c1_job180435_result_codex.md)／[固化机器摘要](../history_normal_reference_keyrepair_deployment_20261031/completion/SUMMARY.json)。主视图ensemble：A误报3.99348%→3.31609%、召回100%；B误报9.51965%→1.75053%、召回99.70293%。B池降至2%内，但Samsung召回损失1.13126pp>设备1pp预算（127/227也失败，127单区间损失8.24561pp>5pp）；HeimVision6.63194%、WEMO Power3.47811%仍>2%。本轮补库有明显收益但未通过整套保护/目标，不能宣称全方案PASS；新漏报33样本行是相对RAW，非相对179700或独立攻击事件。64项超算测试通过，预算内，无异常/重试/重校准/训练。本轮仅核对保存终态，无新实验。下方RUNNING为历史快照。



**2026-10-31 15:59 最新：原180433因Samsung分片缺端口失败，独立修复版已提交180435/node185/amd，Slurm及真实worker均RUNNING。** [修复及提交回执](collab/20261031_history_normal_reference_c1_keyrepair_hpc_execution_codex.md)／[Codex右侧18787进度](http://127.0.0.1:18787/)。本地及超算64项测试、1435项输入/源码身份、Python3.11.11·NumPy2.0.1·Torch2.5.1验收通过。历史专用保守污染处理，不补零或过滤分片，完整重做三成员；旧包/输出/锁保持。固定4CPU/16GiB/8h/20GiB一次修复尝试，无自动重投。已观察到TP Link两遍完整79773包与11875快照；无新DEV/A/B结果，2%效果未知。按用户要求确认启动后结束AI跟踪，仅普通只读页面更新。下方180433 RUNNING为历史快照，现已失败。



**2026-10-31 14:43 最新：历史正常参考C1已提交一次180433/node185/amd，Slurm及真实worker均RUNNING。** [提交及启动回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_history_normal_reference_c1_hpc_execution_codex.md)／[Codex内18785进度](http://127.0.0.1:18785/)。1433项输入/源码身份、Python3.11.11·NumPy2.0.1·Torch2.5.1及远端56项工程测试通过；固定一次4CPU/16GiB/8h，0自动重投。首快照TP Link时间序原包复制79773/79773，尚无新DEV或A/B指标。按用户“不用一直监测”，确认启动后结束AI跟进，仅普通只读进度程序更新。下方暂停、上传0、无job ID是此前快照。



**2026-10-31 Antigravity 接手与最新交付状态：** [集中接手说明](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_antigravity_onboarding_handoff_codex.md)。C1实现56项、部署保护10项测试通过；本地1433项交付副本就绪，上传0、提交0、无job ID、无新A/B成绩。用户已授权超算交付/环境验收/一次4CPU·16GiB·8h执行，随后因需要使用电脑暂停界面操作与提交；当前仅引导新成员熟悉和独立审查，未恢复提交。此条补充下方实现回执之后的状态；历史“尚未授权”勿作为最新授权状态。



**2026-10-31 历史正常参考 C1 已实现，56项生成数据/编排测试通过，本机只读资产验收READY；尚未真实运行。** [实现验收回执](collab/20261031_history_normal_reference_c1_implementation_receipt_codex.md)／[执行卡](../history_normal_reference_v1_20261031/EXECUTION_CARD.md)。已完成整成员连续适配、全合法端点确定性有界选点、新历史双角色编码入口、HIST-DEV/AB双截止、DEV先门、一次A/B终评及Codex右侧进度。A11复用；REF每设备/协议4096，DEV每设备两协议合计4096；唯一C1/P-DEVONLY。修复normalizer路径迁移校验漏洞，代码及科学依赖封存。未真实解码/提特征/补库/新评分或距离/训练/新A/B/远端操作，无job ID；2%效果未知。下一执行阶段先做超算交付路径映射、冻结3.11.11/Torch2.5.1/NumPy2.0.1环境验收，再按另行真实执行授权提交拟定4CPU/16GiB/8h一次作业。下条“未实现”是此前复核快照。



**2026-10-31 历史补库 r2 复核完成，可按r2＋明确绑定进入后续实现；本轮未实现或运行。** [Codex回复](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_well_history_normal_reference_execution_plan_r2_review_response_codex.md)／[只读证据](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_well_history_normal_reference_execution_plan_r2_review_evidence_codex.json)。原r2 SHA dc566523…9dbf0核验一致。主体C1/P-DEVONLY已连贯；必须修正DEV为每设备两协议合计4096（总12288），REF仍每设备/协议4096；新历史编码入口须独立重放历史选点，不能伪造B2回执调用encode_selected，DEV走query_descriptor。Q1组件digest与capture无关、owner/key同则同ID；Q2从现有索引核得TP/Power/Samsung历史截止2016-12-04T12:58:53.261023Z、2017-01-10T23:59:59.863312Z、2017-03-20T23:59:56.682107Z，双视图共用编码且跨REF/DEV不重置。Q3未来P-ATTN需先冻结简短科学修订，不在实现回执里自定禁区。Q4未补Motion/Netatmo/Eufy在179700观察期后主视图FPR为1.187678421%/1.012557277%/0.000231911%，均≤2%；full的Motion2.165410491%、Eufy3.772558592%，故PASS明确沿用原主视图，full并列报告。后续无需再循环原则稿；技术复核不等于效果或执行授权。无原始包解码/补库/新特征/评分/support/实验。



**2026-10-31 历史补库 r1 复核完成，R1_REVISION_REQUIRED_BEFORE_IMPLEMENTATION。** [回复与前端更正](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_well_history_normal_reference_execution_plan_r1_review_response_codex.md)／[证据](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_well_history_normal_reference_execution_plan_r1_review_evidence_codex.json)。接受单候选/无分数选点/固定工作点的开发级设计；已明确不恢复旧源门。Q1：未找到现成已验收的额外开发攻击集，但A归档另有3份HeimVision Nmap候选（6,586,588字节、原包仍在），B三台另有06-02/06-05等官方攻击区间，不能写数据不存在。Q2：每小时重编号未解决UID、首包t0、真实完整窗闭合及跨窗状态；建议整成员连续历史适配器、A11行直复用、HIST-DEV/AB双参考截止。**更正上一轮Codex回复：v2:279实际使用continuous_input_v3 RECENT，>60秒空闲重置、最近12 burst/最多72包；旧BoundedNetfoundPrefix无idle/144包不是此入口的现行规则。三个源码与冻结vendor SHA均相同。** 新增组件锚点与4096上限分支仍需明确；静态总距离对上界579,614,444，不是耗时保证。原r1 SHA d2bd3063…44fde及上一轮文稿SHA保持；本轮无下载/解码/补库/特征/新科学运行。



**2026-10-31 历史正常补库 V1 已完成只读复核，状态 DESIGN_REVISION_REQUIRED_NOT_EXECUTION_READY。** [Codex回复](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_well_history_normal_reference_execution_plan_review_response_codex.md)／[只读证据](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_well_history_normal_reference_execution_plan_review_evidence_codex.json)。Q1确认资格依赖实际参考库；HeimVision旧TCP组件与当前密库不同，合法合库可从1C达到2C，不能按机制不变结项，但2%尚未证实。目标四台覆盖A99.9971%/B95.3775%加权残留FP；6.869728%是TP Link设备级特定范围下界，不是B池下界。已补实际几何/26,549行分库/正式前端/UTC查询边界；四目标不在源FIT/CAL/S，逐目标FIT参数及源选B设备档位无定义；HELD∩FIT正是原S，CAL/禁区/选档重用冲突。RAW cut均为负，0.1×cut不能当正上侧余量；历史时序适配、合库截止、源侧同类新增材料和资源量仍未闭合。原稿SHA ad1f9043…e899未变；本轮无补库、特征/编码、打分/距离/support、新实验或远端操作。



**2026-10-31 下一轮文档讨论请求已准备：** [Codex→Grok/well：原始材料到位后的历史正常参考方案](collab/20261031_raw_data_ready_next_reference_plan_for_grok.md)。请集中给出唯一候选的构建、源材料与角色绑定、新参考下攻击保护及具体预算/停止条件，回写20261031_well_history_normal_reference_execution_plan_for_codex.md。本稿为设计请求，未发送外部消息，不授权新科学运行；原始数据准备完成状态见下条。



**2026-10-31 最新：三台目标原始数据与按时间读取索引已准备完成，尚未补库／运行新实验。** [核查与交接报告](collab/20261031_targeted_normal_raw_data_preparation_codex.md)。官方13.92GB包SHA匹配，仅提取Power/Samsung/TP Link三份3.27GB；清理后已校验迁回D盘，释放C盘临时副本。全量10,233,818包均含预期MAC，原始时间均为2016—2017年；三文件实际PCAPNG，局部倒序4/30/9次，已建立保留全部原始包序号的稳定时间索引（约410MB）。三个首流配对显示CSV按UTC解释比原始包快5.5小时，duration也不能按声明秒直接使用；后续以原始MAC/时钟为准。包数/时间与capinfos交叉吻合、195个索引偏移独立抽验、完整源SHA及索引全排列/单调检查通过。当前状态RAW_VERIFIED_CHRONOLOGICAL_ACCESS_READY_REFERENCE_ADMISSION_PENDING，角色绑定、精确重复/上下文和新参考攻击保护仍待落实；未改模型、训练、support或A/B。



**2026-10-30 当前：用户选择手动下载，单文件清单和目录已准备。** [操作说明](../targeted_normal_data_research_v1_20261030/MANUAL_DOWNLOAD_GUIDE.md)／[机器清单](../targeted_normal_data_research_v1_20261030/MANUAL_DOWNLOAD_MANIFEST.json)。仅获取官方pcaps.zip（13,919,387,057字节），保存到D:/study/paper/anomaly_detection/paper04/data_external/unsw_iotraffic_2025/pcaps.zip；目录已创建，当前尚无该文件。D盘约17.96GB空余，单包后约4.04GB；禁止默认整包解压，先由Codex核官方SHA及ZIP目录、三台目标成员真实大小后安排定向处理。A材料／流摘要／已核CSV不重复下，UNSW-IoTraffic全数据包不选。此处只登记用户手动获取和后续校验安排，不启动下载、补库或新科学运行。



**2026-10-30 最新：用户Chrome已成功下载官方清单，SHA核验通过；代理控制Chrome仍被工具拒绝。** [核验与权限回执](../targeted_normal_data_research_v1_20261030/USER_BROWSER_DOWNLOAD_VERIFIED_20261030.json)。本机Downloads/device_pcap_summary.csv为1,840字节，SHA256完整匹配官方34455dad…e95，不能再把Dryad整体下载不可用或TUN为根因作为结论。用户已授权电脑控制，但工具返回“Computer Use was not approved to use Google Chrome”，用户未见权限弹窗；未自行改权限或绕过。仅清单成功，三台原始PCAP、ZIP目录/成员大小与Range仍未核验；未启动13.92GB整包或新科学运行。此前TUN/内置浏览器失败记录保留为历史事实。



**2026-10-30 最新定向数据调研完成，未补库或运行实验。** 见[调研结论](collab/20261030_targeted_normal_data_research_codex.md)与 `runs/targeted_normal_data_research_v1_20261030/`。A先复用已核SHA的HeimVision旧REFERENCE/当前编码；B只选Power、Samsung、TP Link的较早UNSW-IoTraffic PCAP，已清点本地883,299条流摘要并核官方整包/成员SHA。摘要有大量不同TCP五元组，但全部MAC为null、部分duration单位异常，原始身份/正常性/阶段覆盖仍待核验，状态RAW_QUALIFICATION_CANDIDATE。官网仅确认13.92GB的PCAP子包，三设备内部成员名依README推定、目录和大小待验；本轮浏览器下载小清单被审批拒绝，原始包下载0、未绕过。获取清单已落盘，排除未来日期、无关设备及重复包，不继续泛下大数据。模型、旧评价分母/攻击保护和179700成绩保持。



**2026-10-30 最新：用户希望集中补数据争取误报约2%，已找到A/B具体材料入口，尚未运行。** 见[补正常覆盖路线及事实](collab/20261030_normal_coverage_supplement_to_2pct_codex.md)。A现成HeimVision旧正常点早于评价、TCP组件不同且有当前编码；新历史合库可解除结构限制，效果未知。B同MAC的2016—2017年UNSW-IoTraffic PCAP对象已由官方API确认精确字节/SHA，尚未下载和原始资格核验，正常性/身份连续性/新增组件不由MAC自动保证。源合库角色、访问与存储尚待解决；目标为单一候选、同原评价人口及攻击保护，不通过未来数据/移除难例达标。本轮无新科学计算或远端提交，179700成绩保持；上一条当前窗口内补密度不成立并未推翻。



**2026-10-30 最新：定向补密度方案审阅完成，`DESIGN_REVISION_REQUIRED`，未实现或运行。** 见[Codex回复与三问核实](collab/20261030_well_targeted_density_reference_plan_review_response_codex.md)。主要四台目标设备原合法位置已全选，当前FIT又无这些设备；新增参考候选按现稿定义为0，且同组件补点不解除两组件资格。B前三台残留贡献95.3775%，设备选择有据，补点材料尚不成立。源S与HELD∩FIT角色重用、50条攻击保护定义亦待修改；6.869728%是TP Link设备级理想下界，不是删除该设备全部FP后的B池FPR（后者7.661903%）。下一步先由well指出真实新增合法独立参考来源；若无，结束此具体密度提案，优先原已保存Q/N/C选择性诊断建议。Grok原五问回复已收到，下方等待回复是历史记录。本次只读和文档，正式179700 A/B结果保持。



**2026-10-30 下一步已按原文档方式发起讨论稿，等待Grok/well回写。** 见[Codex给Grok的五问](collab/20261030_reference_attack_competition_after_source_fail_for_grok.md)，约定回复 `collab/20261030_reference_attack_competition_after_source_fail_review_response_grok.md`。180228候选按SAFETY_FAIL结项；源S/ensemble已补读：G0 FPR11.13%→2.61%、recall90.29%→81.58%、新增FN57,483条；G1 FPR18.45%→1.76%、recall100%、新增FN0。上述不是A/B成绩。Codex建议先审计已有Q/N/C配对、共同λ与CAL/S保护压力，再决定改学习任务还是增连接/序列信息；尚未执行新诊断/训练/远端作业，不把讨论稿或内部审阅当Grok已回复。下方“逐臂指标尚未回传”需结合已补读主ensemble摘要理解。



**2026-10-30 最新终态：参考竞争v1源作业180228正常完成，科学安全门未通过，A/B未启动。** [完成核验与监控修复](collab/20261030_reference_attack_competition_completion_and_monitor_repair_codex.md)、[18783进度](http://127.0.0.1:18783/)。Slurm COMPLETED/0:0，六模块24,000更新完成，23分28秒、峰值7.09GiB，预算内、无EXCEPTION。SOURCE_SIGNAL_FAIL / SAFETY_FAIL：G0候选撤回原RAW TP超设备/活动等保护限额；无新A/B结果。页面已固定结束时间、显示累计训练及中文停止原因；冗余squeue查询保留原始告警，不覆盖sacct和worker终态。8项监控测试通过，16项科学代码/设计SHA一致；本次仅本地监控修复和文档归档，未改科学门或重跑。逐臂完整FPR/召回尚未回传，不据安全失败推断误报未降。下方RUNNING为启动历史。



**2026-10-30 10:00最新：正常／攻击参考竞争v1源作业180228已提交，在node185／amd真实RUNNING。** 见[执行及启动回执](collab/20261030_reference_attack_competition_source_execution_codex.md)、[18783只读进度](http://127.0.0.1:18783/)。远端178文件身份、Python3.11.11／NumPy1.26.4／Torch2.5.1及99项合成测试均通过；首次工作快照PID1271488，源输入核验中，科学结果未知、主阶段未提交。一次源4CPU／8GiB／4h、六模块共24,000更新，异常或超限停、无自动重试。完整源PASS及主CAL通过前不做A/B；原179700成绩不变。下方“SSH断连等待／尚未提交”为此前快照。



**2026-10-30 投递恢复状态：新方案代码已上传，远端178文件／63源输入SHA预检PASS；尚未调用提交器。** 原运行授权保持。当前school-hpc SSH在VS Code及命令行均被服务端主动断开，原SOCKS隧道已失效；等待用户恢复既有超算连接后继续环境核验、99项HPC测试和一次源提交，不重复索取运行许可。见[恢复回执](collab/20261030_reference_attack_competition_deployment_resume_codex.md)。当前没有本轮job ID、真实训练或新A/B结果，下方“尚未上传”为更早准备快照。



**2026-10-29 环境说明更正：沿用实验9已有超算Python3.11，不要求另建3.9环境。** 3.9来自ECS历史主头记录，不是运行必要条件；已更正新包主阶段入口和环境配置，主阶段按179602／179700已有方式加载NumPy2.0.1私有overlay，源BASE保持NumPy1.26.4。真实主CAL逐字节重放仍在训练／目标前执行，不以已有缓存评价冒充新前向兼容。见[执行卡](../reference_attack_competition_v1_20261029/EXECUTION_CARD.md)；最新测试数及封包SHA以新包机器回执为准。下文关于“需要超算Python3.9”的判断已撤销。此次更正未远端运行／安装或修改共享环境。



**2026-10-29 正常／攻击参考竞争v1已实现，本地验收98/98通过；尚未提交真实运行。** 见[实现交付](collab/20261029_reference_attack_competition_v1_implementation_codex.md)、[执行卡](../reference_attack_competition_v1_20261029/EXECUTION_CARD.md)。63个真实源输入SHA、六个原型库覆盖、CAL/S依赖隔离只读核验通过；源距离对含旧cache缺失回退上界14.253亿，小于20亿。六模块源流程和条件主头／A/B门、资源硬限、Codex右侧只读进度已实现。源与主头运行时已拆分；主QUERY_TAIL历史Py3.9.24／NumPy2.0.1环境的超算路径尚待核验，不能声称目标阶段已部署就绪。真实新训练／前向／距离／A/B均0，180007与179700结论不变。下方“待实现”是此前设计快照。



**2026-10-29 下一轮设计已落盘：正常／攻击参考竞争v1，待工程实现。** 见[实验方案](../reference_attack_competition_v1_20261029/EXPERIMENT_PLAN.md)。唯一候选增加训练FIT攻击原型关系，与QUERY_ONLY／NORMAL_ONLY做两方向配对，共6个共享小模块；复用E3和检测头，允许1C与原2C零support，从RAW独立决定有限修正，不继承D0的强制减分。源CAL、累计保护、收益及对照门通过后才考虑1个主模块和一次A/B。拟定源4CPU/8GiB/4h、条件后继另4h，尚待吞吐与资产验收。当前仅设计，未实现／训练／计算距离／提交或产生新A/B成绩；180007终态与179700成绩不变。



**2026-10-29 当前终态：180007/node185技术完成、科学SOURCE_SIGNAL_FAIL；D0基线保护门失败，主CAL/A/B未启动。** [完整回执](collab/20261029_local_geometry_budgeted_v2_replay_repair_r1_execution_codex.md)。14:30:05 COMPLETED0:0、调度18:33；全部4,600,362前向、355,060,239距离对、峰值7.249GiB，预算内、无自动重试。六头12组RAW严格复现、两折源CAL均过，λ=.25；源跨设备模拟D0对G0 own ensemble的SimCam/Hydra原TP分别累计撤回12.022059pp/26.5625pp，超过设备1pp/活动5pp，门为BASELINE_TRANSFER_GUARD_FAIL。L已经算出，门优先D0失败，因此未继续判L安全/收益；保存的源S ensemble表显示L对D0额外FPR收益极小，不作实用收益。A_B_inputs=0，正式179700 A/B指标保持。旧bridge的4MiB读取上限曾使页面滞留RUNNING；14:55 sidecar自动只读同步已恢复，connection connected、artifact_errors空、RESULT SHA一致；恢复只读监控，没有补跑实验。原失败/封存包、旧B1和独立源1C延期保持，下方为历史快照。



**2026-10-29 14:12当前：修复r1已实际投递一次180007/node185/amd，源工作进程RUNNING；尚无源科学PASS或新A/B结果。** 用户新一次源尝试授权已落实，14:11:33北京时间提交、0自动重试。见[新执行回执](collab/20261029_local_geometry_budgeted_v2_replay_repair_r1_execution_codex.md)与[18775进度页](http://127.0.0.1:18775/)。78输入SHA、历史Py3.11.11/NumPy1.26.4/Torch2.5.1/Linux、65合成测试全部通过；14:12:55已保存工作快照显示G0/27/CAL旧失败点及G0/27/HELD、G0/127/CAL严格重放PASS，累计883,188小头评分/距离0。已跨过旧技术停止点，但不宣称唯一根因或几何收益；主CAL/目标尚未执行。源4CPU/8GiB/4h/2e9对/2GiB保持，完整源PASS才可能走主CAL原D0锚＋RAW TP零撤回，之后一次CIC_DEV/UNSW_DEV A/B。collector每5秒只读同步，鲜活桥接时间不替代工作心跳；心跳过期则实验状态未知。原失败/封存包、正式179700成绩、旧B1及独立源1C延期保持；下方未部署/等待新授权等均为此前快照。



**2026-10-29 局部几何v2首次源执行已技术停止，尚无几何/A/B结果。** 用户“允许下一步”后实际运行source_01，第一G0_BASE_27 CAL的26,349行前向后触发RAW逐值复现不一致，约50秒/4.40GiB、距离0、无训练/编码；无RESULT或完成回执，后继阻断，进程已退出。见[执行及根因边界回执](collab/20261029_local_geometry_budgeted_v2_source_execution_codex.md)与[机器审计](../local_geometry_budgeted_v2_20261029/execution/ATTEMPT_RESULT_SOURCE_01.json)。历史源实际为Python3.11.11/NumPy1.26.4/Torch2.5.1/Linux，不能混称主头NumPy2.0.1；环境差异是候选原因，原失败未保存逐值差异，尚未确诊。隔离[取证修复r1](../local_geometry_budgeted_v2_replay_repair_r1_20261029/EXECUTION_CARD.md)已完成65项合成验收、错误环境阻断和输入布局清单，原严格门不变；未远端部署/提交/重跑。原“一次，无自动重试”要求修复后新一次源执行得到明确同意；条件目标阶段仍仅在源PASS后。下方“正式尚未运行”是本次执行前快照。



**2026-10-29 局部几何v2已实现并验收，正式实验尚未运行。** 见[实现回执](collab/20261029_local_geometry_budgeted_v2_implementation_codex.md)、[执行卡](../local_geometry_budgeted_v2_20261029/EXECUTION_CARD.md)和[机器回执](../local_geometry_budgeted_v2_20261029/IMPLEMENTATION_RECEIPT.json)。冻结方案`797a08dc…fc51`未改；61项合成测试全部通过，最终真实源只读验收CHECK_PASS（48.140秒、峰值约4.42GiB、766,727行/4,728参考），新前向/距离/训练/编码/候选A/B均0。入口默认check；源两折六头＋D0/L通过后才准主CAL零撤回及一次A/B，4CPU/8GiB、源≤4h、条件目标再≤4h。资源及累计保护、L新1C资格和原整数分母精确门槛均已实现；真实数值重放仍在待运行的科学预算内。下一项为一次源执行，不再写原则确认；旧B1与源1C延期保持。下方“尚未实现”均为历史快照。



**2026-10-29 用户要求尽快给下一轮实验方案：已交付有限投入方案，尚未实现/运行。** 见[实验方案](../local_geometry_budgeted_v2_20261029/EXPERIMENT_PLAN.md)及[给well的回复](collab/20261029_well_no_executable_alternative_after_b1_review_response_codex.md)。推荐两折BASE×原三seed，复用六头和已有E3/q14，明确补own-FIT小头前向及同头模拟D0；一个固定局部几何候选，源通过再主CAL＋一次A/B。源距离对保守上界810,820,046；建议4CPU/8GiB/4小时，条件目标另4小时，无新训练/编码。半径、资格、累计保护、实用收益和停止规则已写定；下一工程项为实现验收，不继续原则确认。旧B1卡仍结项，此为改变必要基线投入范围的提案；正式A/B及源1C搁置状态保持，无新科学计算。



**2026-10-29 well截图回应已审阅：当前卡结项已对齐，尚无具体替代方法。** 见[Codex回复及已有路线简表](collab/20261029_well_after_b1_screenshot_review_response_codex.md)。同意B1结束局部几何卡准备；换路线可以避开当前两折DENSE重建，但仍需匹配的对照和攻击保护证据。现有结果足以初步筛选，不另起泛盘点；若well有具体替代候选，应直接说明新选择信号、合法开发/对照、必要新增成本与停止条件。没有候选则如实保留暂无可执行替代，不自动重启旧卡或源1C。论文可整理限定范围必要界限，不能宣称完整性能极限。此次仅文档审阅回写，无新科学计算，正式A/B指标不变。



**2026-10-29 最新r1审阅：Codex接受B1不推进当前局部几何卡，建议结束该卡准备。** 见[well r1](collab/20261029_well_local_ref_geometry_prereg_spec_r1_for_codex.md)、[Codex结项意见](collab/20261029_well_local_ref_geometry_prereg_spec_r1_review_response_codex.md)。r1明确不补齐必需同头D0，故源诊断S未运行、保护证据不足，科学效果未知；不是NO_SELECTIVITY/SAFETY_FAIL/INFEASIBLE，也没有测得成本超限。不能把B1取舍写成五项可执行规格都已闭合：头—人口—分母映射、局部质量门仍有歧义；5pp是绝对收益门，新增1pp不能替代累计1pp，seed仅报告不能自动解除保护。上述只作归档限制，不再推动补卡、泛盘点或runner；不自动恢复源Atomi1C。本结项意见仅限当前卡，A/B研究目标及正式成绩不变，本轮纯审阅，无新科学计算。



**2026-10-29 预登记草案已回审：框架修订大体吸收，完整预登记仍未完成。** 见[well规格稿](collab/20261029_well_local_ref_geometry_prereg_spec_for_codex.md)、[Codex四问回复](collab/20261029_well_local_ref_geometry_prereg_spec_review_response_codex.md)。S/头/UID/D0依赖、局部半径唯一程序、G_min/源保护/seed推进门、预算硬限仍未确定；保持PRE_REGISTRATION_SPEC_DRAFT_NOT_EXECUTION_READY，不判机制失败。稿件将J_local^2明确定义为第二距离，并非重新引入平方，但需统一为J2_local；集成须写原float64算术平均。拒绝把重复泛盘点已知D0缺口列为默认下一步，仅新增具体资产或S的明确依赖差异值得定向查验。下一交付应直接作S与补齐成本取舍、固定算法和数值门；预算停止与保护证据不足可分别记录。本轮仅稿件/既有摘要/代码语义审阅，无新盘点、科学计算、实验代码修改或授权升级，旧包及正式A/B成绩保持。



**2026-10-29 局部参考几何假说已审阅：方向接受，精确诊断仍未就绪。** 见[well设计骨架](collab/20261029_well_local_ref_geometry_design_hypothesis_for_codex.md)、[Codex审阅与最小修订](collab/20261029_well_local_ref_geometry_design_hypothesis_review_response_codex.md)。三项原则已对齐；当前须修四处：固定线性support、删除平方备选（否则混入强度变化且破坏部分空操作推论）；源诊断S与未来目标评价T分开；HELD∩FIT缺同头DENSE基线，不能一边禁止所有必要构建一边声称可做D0增量检验；成功主量改为固定cut下实际加权FP修复及攻击撤回，support增加仅作解释。局部半径/质量/零值/组件聚合/原因果/UID与成本仍须一次完整预登记；若必要基线依赖超预算则停止，不新增候选或恢复源Atomi小审计。状态DESIGN_HYPOTHESIS_NOT_EXECUTION_READY；本轮仅文档/代码语义复核，无新距离/support/参数选择/前向/训练/评价或实验代码修改，旧封存包及正式A/B成绩不变。



**2026-10-28 上界后机制讨论已回写，尚未成为执行方案。** 见[well讨论稿](collab/20261028_well_after_ab_bounds_discussion_for_codex.md)、[Codex五问回复与唯一机制原型](collab/20261028_well_after_ab_bounds_discussion_review_response_codex.md)。同意先设计后计算；Codex不同意将最宽6.004pp攻击暴露上界≤预算作为一切小诊断的必要条件，建议候选专属紧界限优先，必要时仅预登记一次限额诊断。旧统计无选择性不能推广成完整表示不可行。提出冻结正常参考内部局部尺度的双空间几何原型，显式改变几何、保持λ/score-scale/cut/参考/窗口，旧q14保护不自动继承；状态DESIGN_HYPOTHESIS_NOT_EXECUTION_READY。待well集中回应准入逻辑/不可行标签/原型因果缺陷，不重复上界盘点。当前仅文档与代码语义审阅，未重算目标/新距离/support/选参/训练/前向/远端；旧封存包与源1C卡不改，正式A/B成绩不变。



**2026-10-28 A/B可触达上界盘点已完成：单独1C不足，组合尚未排除，尚无新性能结果。** 见[中文结果](../ab_reachable_bounds_readonly_v1_20261028/RESULT_REVIEW.md)、[well回传](collab/20261028_ab_reachable_bounds_readonly_result_codex.md)、[总验收](../ab_reachable_bounds_readonly_v1_20261028/ACCEPTANCE.json)。固定λ=.25/原cut/scale/参考窗口，五范围×四suffix×两池；仅目标1C扩展的ensemble幅度下界A池1.256213%但HeimVision设备2.512194%，B池2.643104%，不足完整目标。“1C＋仅原正support”虽B池1.715144%但TP Link仍7.230553%；必须覆盖现有2C零支持。最大“1C＋全部原合格2C”幅度下界A0.173727%/B0.421761%，所有设备界限≤2%，但只是乐观必要条件，未计算实际新support；其潜在额外攻击暴露A0.366159pp/B6.004144pp，不能兑现成保99%召回的新成绩。下一重点是有限组合规则的选择性、合法FIT开发与近边界保护，不再单跑源Atomi1C。40格及520攻击组交叉核验通过；无新距离/support/前向/训练/参数搜索/候选A/B评价/远端，P2/P3未启动。正式成绩仍A3.993482%/100%、B9.519654%/99.966594%；旧源1C包/卡保持。下方“逐UID盘点尚未执行”为历史快照。



**2026-10-28 最新研究优先级：搁置独立源 1C，先看 A/B 可触达上界。** 见[well 立场稿](collab/20261028_well_skip_1c_focus_ab_fpr_for_codex.md)及[Codex 五问回复](collab/20261028_well_skip_1c_focus_ab_fpr_review_response_codex.md)。源1C旧卡保持DRAFT_NOT_AUTHORIZED，研究标签建议为DEFERRED_UNTIL_AB_PATH_NEEDS_IT。仅消B两个组件不足块、其他冻结，池FPR乐观下界仍2.512517%；A仅消组件不足块，HeimVision设备仍2.512194%；TP Link零支持块不变时设备下界6.869728%。均为已有汇总的限定算术界限，不是新效果。下一步建议目标UID范围/幅度上界及攻击缺口盘点，组合按UID并集；不将单模块不足扩大为所有方法不可能，也不以own归因失败阻断性能研究。旧准备包与卡不改，本轮仅审阅回写，无新距离/support/前向/训练/阈值/A/B重评/远端；该逐UID盘点尚未执行。



**2026-10-28 固定 1C 下一步只读盘点已完成，独立卡草案已准备：** 见[回传](collab/20261028_1c_readonly_asset_inventory_and_execution_card_codex.md)、[盘点结果](../one_component_readonly_inventory_v1_20261028/RESULT_REVIEW.md)、[独立执行卡草案](../one_component_readonly_inventory_v1_20261028/CARD_DRAFT_NOT_AUTHORIZED.md)。766727源行角色/分母逐条对齐，12端点32旧报告复现通过；73源输入SHA前后不变，主头58文件输入身份已核。合法开发的HELD∩FIT确有近原阈攻击，但缺对应DENSE基线。主头1C仅影响Atomi TCP12位置，原2C该分支support=0，可做最小精确差分，无需先重建两折/训练。卡预计最多1785828距离对、2CPU/2GiB/30分钟停止预算，runner尚未实现/执行；本轮无新前向/距离/support/阈值选择/训练/A/B/远端，P2/P3未启动。下方“下一步盘点尚未执行”为历史快照。



**2026-10-28 well r1 方向复核通过，执行条件未齐备：** 见[well r1](collab/20261028_well_next_direction_after_p1_r1_after_codex.md)及[Codex r1 复核](collab/20261028_well_next_direction_after_p1_r1_review_response_codex.md)。五问核心修订已吸收，不需再大改方向稿。须区分固定 CAL 上已证零撤回、迁移保护压力不足和实际支持未知；证据不足不自动将 support 置零，也不能用 CAL 标签新增逐查询否决。后续机制核查可完成并以“迁移证据不足、不推进 A/B”结项。建议下一步只读资产/角色/分母清单，明确两折 D0 与新计算缺口；原稿、r1及上一回复 SHA 均保持，本轮仅文档审阅，无新科学计算/训练/远端任务，P2/P3 未启动。下方“待 well 修订”为历史快照。



**2026-10-28 Codex 已回复 well 的 P1 后方向五问：** 见[审阅回复](collab/20261028_well_next_direction_after_p1_review_response_codex.md)。有条件同意转向条件修正；P1 只否定原登记 QP，固定分数界限只排除全局/原 QG 家族；73.61% 是残留分账，不是可恢复收益。两个 B 主残留组在完整合法窗口中都仅有一个真实组件；先区分新增真实覆盖与固定 1C 机制核查。HELD 包含原 FIT＋CAL，规则开发需按原角色隔离，已有 HELD 不能再当独立确认。保留 DENSE 主基线及 RAW 对照，两折 DENSE 与近边界保护资产仍待补齐；本轮仅文档审阅，无新前向/距离/校准/训练/A/B/远端任务，P2/P3 未启动。待 well 修订，不代表方案已一致或获准执行；下方“待 Codex 回复”为历史快照。



## 2026-10-28 18:49 状态快照：well 已写入 P1 后方向讨论稿，待 Codex 回复



见 [collab/20261028_well_next_direction_after_p1_for_codex.md](collab/20261028_well_next_direction_after_p1_for_codex.md)。主张停 cut 搜索、改近边界保护的排序/覆盖条件修正；不授权训练/不升 P2。



**2026-10-28 P1失败小诊断已完成：** 见[诊断与下一步判断](collab/20261028_p1_failure_diagnosis_and_direction_codex.md)。48份原判定/指标精确复现、69原文件SHA保持；G0 QP的170条Hydra新增FN贡献92.74%的加权召回损失，新增FN均低于同阶段CAL攻击最小分数，缺跨设备近边界保护。G1集成CAL两规则逐条相同、HELD共享QG多修12,998个FP，不能把其1.96%当A/B。结合既有B分数边界，原QG可调/回退家族同样无B2%/99%联合解，不建议原样升级A/B；下一版应先设计有折外困难攻击保护的条件修正。35.734秒、0新选阈值/前向/训练/距离/A/B加载/远端任务，P2/P3未启动；原QP停止和旧A/B结论不变。



**2026-10-28 P1已完成，技术正常、科研SOURCE_SIGNAL_FAIL：** 见[本次执行与结果回执](collab/20261028_phase_conditioned_p1_execution_codex.md)。90.094秒、24格/48报告、67产物SHA及代码封存通过；源侧集成HELD：G0原FPR10.397%→QP5.426%，召回88.624%→83.320%（保护失败）；G1原20.489%→QP7.821%，共享QG1.960%，均召回100%。两折QP都劣于QG，预登记推进门失败，P2/P3未启动。G1共享校准为单折信号，不是新A/B指标。[进度页](http://127.0.0.1:18774/)保留完成终态，无AI轮询。下方“P1尚未运行”是授权前快照。



**2026-10-28阶段条件校准v1代码已实现并验收，正式P1尚未运行：** 见[最新实现回执](collab/20261028_phase_conditioned_calibration_implementation_codex.md)、[执行卡](../phase_conditioned_calibration_v1_20261028/EXECUTION_CARD.md)及[机器回执](../phase_conditioned_calibration_v1_20261028/IMPLEMENTATION_RECEIPT.json)。63/63测试通过，真实源Q0的16报告复现、P2的26输入/6依赖只读核验、旧D0两池双视图16指标精确复现通过。默认check，P1/P2/P3分别显式执行，前序PASS及SHA门控；无新阈值校准/距离/前向/训练/云端作业，也无新A/B效果。下一步单独P1验证阶段QP相对共享QG的迁移收益。下方“尚未实现”是原方案快照。



**2026-10-28阶段条件校准v1方案已定稿（尚未实现／运行）：** 见[可交实现规格](collab/20261028_phase_conditioned_calibration_plan_v1_codex.md)及[PLAN.json](../phase_conditioned_calibration_v1_20261028/PLAN.json)。固定Q0／同回退共享QG／分阶段QP；无攻击阶段原cut冻结，低支持CAL零撤回，HELD／目标按加权护栏。新主目标固定ensemble池FPR≤2%、召回≥99%，旧池ε=.1pp不用于本新版本，设备／攻击组保护保留。先P1已有BASE两折分数probe（24格／48报告），按预登记20%／10%额外收益及安全门决定是否P2密源own＋12donor/rawfallback分数重建与组合CAL，再准备P3五臂A/B（80报告）。独立方案与资产审阅问题已处理；本轮只有文档及参数规格，无新校准／距离／前向／训练／云端作业。



**2026-10-28阶段条件校准的数据核查完成：** 当前B密参考99%描述性边界的残留FP全部位于FIN／OTHER，新增FN全部位于SYN_NO_ACK，存在跨阶段混排信号。源FIT/CAL与12个BASE/CTX端点阶段绑定通过；源非SYN/UDP攻击存在，但G0 CAL OTHER仅21条，RST/SYN_ACK/FIN源攻击为0。179602缺完整逐UID密源修正后分数，组合校准前需由已有特征／参考重建并复现旧汇总，不能以原头CAL代替。见[数据回传与实现前最小方案](collab/20261028_phase_feasibility_data_readout_codex.md)。下一步定稿源侧小验证规格再实现，本轮0新前向/训练/距离/CAL/远端作业。



**2026-10-28下一步讨论更新：用户可接受下一版池FPR≤2%、攻击召回≥99%。** 现有密参考分数的观察期后只读oracle显示：B即使事后挑单一阈值，保99%召回最低FPR仍3.676680%；压FPR到约2%时召回最高97.865187%，保原组损失护栏则99%约束下最低FPR5.866191%。这是开发诊断，不是部署工作点；A描述性可分性可满足新目标。下一步建议先核查阶段混排与源侧攻击保护信息，再决定条件校准；1C完整密源核查为次优收尾。见[新目标判断与下一步](collab/20261028_next_direction_2fpr_99recall_codex.md)。本轮仅本地保存分数分析，未训练/运行新CAL/提交作业，179700原结论不变。



**2026-10-28最新正式结果：179700完整下载、SHA和192份逐条离线指标核验PASS。** 主口径（观察期后、主ε=.1个百分点、固定三seed集成）：A原参考FPR4.751675%→密参考3.993482%，攻击召回100%；B16.482115%→9.519654%，召回99.966594%，新增FN6条、损失.028038个百分点，主攻击护栏通过。两池误报目标仍未达标，科研FAIL不是运行故障。B有明显收益；A同资格WRONG优于own，不能声称自身参考特异性。四ε均选λ=.25、预测相同，未评价“召回99%”的新阈值。见[正式结果及残留瓶颈](collab/20261028_dense_reference_ab_final_result_readout_codex.md)。第三池仍未评价；本轮仅本地分析，0新作业/前向/训练/编码/CAL/重选。下方待下载、RUNNING等为历史快照。



**2026-10-28最新完成：179700/node185已COMPLETED、exit0:0、19分01秒，A/B两池24个臂×ε单元全部完成，worker清理通过。** 本阶段科研判定FAIL，属于指标未达登记门槛，并非运行异常；具体FPR/召回仍待完整结果拉回核验，第三池继续未评价。见 `runs/dense_reference_ab_stage_dependency_repair_execution_20261028/FINAL_PROGRESS_ACCEPTANCE.json`。[18771](http://127.0.0.1:18771/)已保存完成终态，用户将自行下载job_179700（排除复用输入readonly_view）及Slurm日志，本轮未重跑或自动下载；下方RUNNING为历史快照。



**2026-10-28最新正式执行：用户已明确批准修复后重新运行，新179700/node185已RUNNING，真实worker存活，已进入CIC_DEV/R-DENSE-WRONG支持计算。** 修复包SHA85637f3a…、新授权及原NumPy2.0.1/输入门已过；新提交1次、0自动重试，复用179602编码/CAL、0新前向/训练/编码/CAL。见[提交与启动验收](collab/20261028_dense_reference_ab_stage_dependency_repair_execution_codex.md)。[18771进度页](http://127.0.0.1:18771/)继续作主入口，原179680失败移至[18773历史页](http://127.0.0.1:18773/)。尚无完整池结果和新A/B指标，第三池仍延期；下方“修复待授权/尚未重提交”等均为此前快照。



**2026-10-28 11:18最新修复：179680的依赖漏封已修复；新27件小包完成超算部署及真实工程预检，PASS、51.50秒。** 冻结六模块/子进程路径、328,202查询metadata/UID/q14、19件源seal及四库历史重叠资格均通过；真实E3算术/支持/距离/分数评价/训练/编码/CAL为0。原179680仍FAILED，尚无A/B指标，尚未再次提交；旧单次授权已消费，新修复版4CPU/16GiB/2小时、0重试待新的明确授权。见[修复回执与具体申请](collab/20261028_dense_reference_ab_stage_dependency_repair_codex.md)及[进度页](http://127.0.0.1:18771/)。下方“修复中/正在部署”是此前快照。



**2026-10-28最新真实终态：A/B先行作业179680/node185已FAILED，exit70:0、48秒，尚无A/B指标。** 原包/环境/输入门已过，真实query/reference UID重叠触发未入包的 `causal_reference_overlap_v1.py`，属于技术打包错误；支持计算及池结果完成0，worker已清理。已补传静态输入并核全部SHA，原179602编码/CAL可继续复用。新依赖修复层正在隔离验收，原科学参数、原候选与失败现场保持；本轮单次提交授权已消费，0自动重试，尚未再提交。见[真实失败与修复跟进](collab/20261028_dense_reference_ab_stage_execution_codex.md)，[18771进度页](http://127.0.0.1:18771/)已显示异常与具体原因。下方“正在部署/未提交”均为此前快照。



**2026-10-28最新授权：用户已明确“开始运行。”，批准A/B先行评价及第三池延期。** 正按固定封包部署，单次amd4CPU/16GiB/2小时、0自动重试，复用179602编码与源CAL；本段尚未宣称已提交/取得A/B结果。见[授权部署与运行回执](collab/20261028_dense_reference_ab_stage_execution_codex.md)。下方候选待授权为此前准备快照；同一已批准范围不重复申请。



**2026-10-28最新准备：A/B先行密参考评价候选已准备，尚未运行。** 第三池历史BASE/B2/receipt再次核查确实缺失；已准备独立两池阶段代码、179602派生绑定和单次4CPU/16GiB/2小时执行卡，待明确确认分阶段修订与该云端范围。见[本轮回传](collab/20261028_dense_reference_ab_stage_preparation_codex.md)及[具体执行卡](../dense_reference_ab_stage_candidate_v1_20261028/EXECUTION_CARD.md)。新A/B指标仍无；原三池完整性保持false，不复用已完成179602授权；无新远端/作业/前向/训练/CAL/目标评价。



**2026-10-27 22:33最新结果：179602完整产物已拉回，80文件／约229.9 MiB，SHA及独立离线审计PASS。** 21,660新增参考、三库26,549行及原104零字节差均核对；两臂四ε均选λ=.25，源CAL四suffix新增FN均0。源CAL集成FPR：BASE 0.974305% → 原参考0.142897%／密参考0.135608%，密参考额外仅降0.007289个百分点；修正后正常FPR由保存汇总派生，非逐行正常trace重建。见[完整结果与限制](collab/20261027_dense_reference_final_result_readout_codex.md)。本轮仅拉回与离线分析，0前向／训练／新CAL／目标评价／新作业；无新A/B指标，完整矩阵仍缺第三池冻结BASE/B2。下方“结果待读回”或RUNNING等均为历史快照。



**2026-10-27 22:01最新完成状态：179602 / node185已COMPLETED、exit0:0、耗时2小时5分钟。** 原104严格门禁、21,660新参考补编码及密源CAL全部完成，实际21,764逻辑行／22,514物理位置；[18770进度页](http://127.0.0.1:18770/)已只读刷新为四阶段完成并离线保留。见[进度刷新与完成回执](collab/20261027_dense_reference_progress_completion_codex.md)。未重启实验、无新目标评价；完整结果产物尚待读回核验分析。下方RUNNING及CAL待执行均为此前快照。



**2026-10-27 最新正式执行：179602 / node185 正常运行，原104严格门禁已真实通过（104/104逐字节一致、0差异）并开始CIC合法参考补编码。** 用户已明确“允许提交”，新修复包仅投递一次；远端26项测试及环境身份均过。见[提交与启动验收](collab/20261027_dense_reference_batch_repair_execution_codex.md)，[18770进度页](http://127.0.0.1:18770/)已绑定新job、保留三次历史。范围仍为环境→104→21,660新参考编码→密源CAL，22,514物理位置、4 CPU／16 GiB／总12小时、0自动重试；编码/CAL尚未完成、无新A/B指标。普通隐藏程序同步，无AI持续轮询。下方“未提交／原104仍待重验”是本次真实门禁之前的历史快照。



**2026-10-27 最新工程修复已本地验收，正式新作业未提交：** 单样本批兼容修复包已封存15件，本地26/26及独立解包26/26通过，零真实前向／训练／CAL／目标评价；原1492件及历史修复／诊断字节未改。拟按环境→原104零容差重验→21,660新参考编码→密源CAL，实际22,514计算位置、4 CPU／16 GiB／最多12小时、0自动重试；待新的具体云端授权。见[修复完成与执行卡回执](collab/20261027_dense_reference_singleton_batch_repair_codex.md)。原104真实修复仍待验证，完整第三池矩阵仍阻塞；[18770进度页](http://127.0.0.1:18770/)已分开显示工程准备与已完成179591小诊断。下方“准备修复／未成包”等为历史快照。



**2026-10-27 最新诊断已完成：** 用户批准的源8 B1/B16克隆小诊断 **179591/node185，COMPLETED、exit0、36秒、136位置**。B1控制8/8精确复现179536，B16克隆8/8逐字节恢复旧向量；已取得批次大小影响数值路径的强证据。原104门未改判、正式补编码/CAL/目标评价仍未开始；下一步准备单样本批次处理修复，再独立验原104，不能凭诊断直接续跑。见[源8诊断执行与结果](collab/20261027_source8_batch_diagnostic_execution_codex.md)，[进度页](http://127.0.0.1:18770/)已显示终态及两次历史失败。下方待批准、准备提交等均为历史快照。



**2026-10-27 最新：** 已运行修复版 **179536/node185**；启动修复、SHA、86测试及真实环境导入通过，但104重放 **8/104字节不同（最大差9.24e-7），FAILED70:0、2分08秒**，未新增补编码/CAL/目标评价。8条恰好全是B1，历史均B16。源8 B1/B16克隆诊断包已封存上传，17测试、独审、超算零前向dry-run均PASS；已申请一次136位置/4CPU/16GiB/10分钟小诊断，**尚未获该新范围授权、无第三次提交、数值门未放宽**。见[179536回执与具体诊断申请](collab/20261027_dense_reference_repair_restart_and_numeric_stop_codex.md)；18770清楚显示终态及179523历史。下方等待修复版确认等为历史状态。



**2026-10-27 最新执行：** 用户改由Codex上传提交，r2部署完整SHA通过；新作业 **179523/node185 已FAILED（exit1:0，3秒）**，在启动前文件SHA校验因CRLF清单兼容性退出，真实前向/补编码/密源CAL均未开始。独立修复层已解决清单解析及包外输出，已上传、独审及超算只读验收21/21 PASS，原1492件SHA保持；**未提交第二个作业，按0自动重试合同等待修复版一次新提交确认**。见[提交与启动修复回执及具体申请](collab/20261027_dense_reference_submission_and_launch_repair_codex.md)，新页<http://127.0.0.1:18770/>显示异常和修复验收，旧18769保持。下方等待手动上传等为历史快照。



**2026-10-27 最新运行授权：** 用户已允许密参考r2按执行卡运行前三阶段，并希望手动上传归档。见[授权与上传交接](collab/20261027_dense_reference_cloud_authorization_and_upload_codex.md)。当前`AUTHORIZED_AWAITING_USER_UPLOAD`，未提交作业；上传后继续核验、一次提交和进度页，不再重复询问该范围授权。完整目标矩阵仍未授权且缺第三池资产。下方“正式运行待授权”是此前封包时的状态。



## 2026-10-27 最新：密参考方案r2实现及独立验收完成，正式未运行



见[密参考实现回执](collab/20261027_dense_reference_implementation_readout_codex.md)、[具体执行卡](../dense_reference_matrix_v1_20261027/EXECUTION_CARD.md)和[r2最终验收](../dense_reference_matrix_v1_20261027/distribution/r2/VALIDATION.json)。**86/86合成测试、独立解包SHA/审阅pin/源CAL闭包/Slurm语法均通过；真实前向、补编码、训练、A/B评价与远端提交均0。** 当前可申请一次`runtime→encode→source_cal`（21,660新增位置，原104严格门、amd4CPU/16GiB/12小时）；正式运行仍按既有约定待具体云端授权。完整三池矩阵代码已实现，但第三池历史冻结BASE/B2确实缺失，为`BLOCKED_MISSING_FROZEN_BASE_B2`，不能当成“资产存在但无窗口”，不自动降为A/B-only。r1仅本地测试可移植性失败，已保留；使用r2，包身份`ddb94bb9836c9ace0b2a704e875d969c1d3c40c94198212ac795a9d0731db120`。新进度组件已实现但未启动；旧18769 BASE/CTX终态保持。实现验收通过不代表取得密参考效果，下方179460完成是另一条源侧对照的历史结果。



## 2026-10-27 179460 已完成，完整拉回与只读审计通过



**179460 / node185 已于 2026-10-26 22:08:55 北京时间正常完成，exit 0，12/12 端点完成；科学判定 FAIL 与运行故障不同。** 完整拉回 1,486 文件并通过 SHA、主结果及并列集成只读审计，见[最终结果读数](collab/20261027_base_ctx_final_result_readout_codex.md)。主指标（三 seed 各自校准后均值）G0 FPR 10.197337%→10.820529%，G1 17.612028%→12.427822%；G1 有条件性信号，G0 实质退化。简单 logit 集成的 G1 仅 20.489258%→20.344328%，单头均值收益没有保留；G0 加权召回虽升，原始 FN 仍增加。属于源侧检测头上下文对照，不是 A/B 或新入网模块结果。页面 <http://127.0.0.1:18769/> 已显示完成且离线保留终态；SSH 端口变化断联已修复，见[连接恢复回执](collab/20261027_progress_reconnect_and_completion_codex.md)。本轮未重启实验、未新训练或评价，无 AI 持续轮询；下方 RUNNING 为历史快照。



## 2026-10-26 20:03 修复后已授权续跑，179460正常运行



**用户已授权“修复完成后，自动重新运行。”新179460/node185 RUNNING，已核验复用BASE6（289800旧更新、本次BASE新增0），当前重新提取全量MI15，CTX待执行。** 见[续跑启动验收回执](collab/20261026_base_ctx_repair_restart_execution_codex.md)，进度页<http://127.0.0.1:18769/>已切新job并保留原179422异常历史。原包43件＋修复包18件SHA、授权、源输入及BASE审计再核验均通过。普通隐藏程序5秒同步，AI不持续轮询；新技术异常停链保留，科学FAIL继续登记配对。尚无CTX效果或新A/B指标。下方“待授权／正式未重启”是本轮明确授权前的历史快照。



## 2026-10-26 19:30 MI15 资源故障已修复验收，正式续跑待确认



**原179422已FAILED，BASE6完成、S0有信息性、CTX未开始。** 最大capture原命令诊断179447完整通过，实测TShark约5.59 GiB，原2 GiB保护不足。独立三阶段修复包已封存；原环境BASE6严格审计179448通过，最终包技术验收179452/node185 PASS，原v1保持。新单capture8 GiB／全树12 GiB／Slurm16 GiB；复用核验BASE6、不重训，MI15全量重做。见[修复与最终验收回执](collab/20261026_base_ctx_mi15_resource_repair_codex.md)，实时页<http://127.0.0.1:18769/>。**正式实验未重启、无新CTX/A/B指标**；遵守资源异常不自动重跑。页面显示原失败／技术诊断／待授权，无AI持续轮询。下方179422 RUNNING等均为历史快照。



## 2026-10-26 16:47 BASE/CTX 已授权并在超算正式运行



**179422 / node185 / RUNNING，当前 BASE 首端点 G0_BASE_27，训练前门与真实源输入核查已过。** 见 [正式运行回执](collab/20261026_base_ctx_hpc_execution_codex.md)，实时页 <http://127.0.0.1:18769/>。仅部署564,973字节封存代码，43/43 SHA通过，大数据复用；原合同、最多12端点及S0分支不变。普通程序每5秒同步，无AI持续轮询；异常保留现场、禁止自动重跑。无新E3或A/B评价，当前尚无新效果结论。下方“待授权、未sbatch、真实训练0”均属本次正式授权前的历史快照。



## 2026-10-26 BASE/CTX 实验包完成，正式运行待授权



见[完成回执与具体运行申请](collab/20261026_base_ctx_experiment_package_codex.md)、[实验包](../source_controls_base_ctx_v1_20261026/README.md)、[最终本地验收](../source_controls_base_ctx_v1_20261026/validation/final_r2/ACCEPTANCE.json)。独立trainer/MI15/矩阵/Slurm/普通状态同步已实现；80项测试及独立解包同80项全过，人工12端点/24更新通过，766,727行真实源只读预检正常完成。首次新预检进度写入失败已保留并修复，final_r2为最新回执。包最多12头，先BASE6的S0，再MI15/CTX6；COV/CNT暂缓。**真实源前向/训练、生产MI15、新E3、A/B和远端操作均0，未sbatch，仍待正式运行授权**。独立补E3/密源CAL/A/B链未被本包补齐。下方“尚无源trainer/MI15/需Claude收敛”属于此前快照；技术验收179404仍有效，无AI持续轮询。



## 2026-10-26 超算基础技术验收已完成



**179404/node185已正常完成（COMPLETED、exit0）**，环境/TShark/CPU验算、169/169 raw和8/8 core完整SHA全部通过。见 [修复及完成回执](collab/20261026_hpc_probe_repair_r2_codex.md)／[最终验收](../hpc_readiness_preparation_v1_20261026/repair_v2/TECHNICAL_READINESS_ACCEPTANCE.json)。原179403为预检脚本构建信息接口错误，已保留；修复后独立验收，无源数据重传、无正式训练/编码/A/B。18766页r3显示完成及历史失败，普通同步已结束、无需AI轮询。基础技术就绪不等于科学口径、trainer/MI15/矩阵runner或原104门禁已完成；个人未来输出配额仍未知。下方r2进行中等是此前快照。



## 2026-10-26 超算预检脚本修复 r2，已进入真实数据验收



见 [179403根因与179404独立修复验收](collab/20261026_hpc_probe_repair_r2_codex.md)。原失败来自预检脚本使用当前NumPy构建不存在的`get_info`，TShark/依赖版本已过；源文件5/5 SHA通过。已改公共接口并通过12项回归测试；新179404在node185环境/CPU验算已过，继续核查169 raw与8 core，当前最终状态以 [机器状态](../hpc_readiness_preparation_v1_20261026/status.json) 和r2退出回执为准。原179403失败保留、源数据零重传、未正式训练/补编码/A/B。18766页r3区分历史与当前、终态不再报心跳过期。



## 2026-10-26 超算技术准备已获授权并执行



见 [本轮超算准备执行记录](collab/20261026_hpc_preparation_execution_codex.md)；实时准备状态以 [status.json](../hpc_readiness_preparation_v1_20261026/status.json) 与各阶段最终回执为准，页面 <http://127.0.0.1:18766/>。计算节点路径预检179396/node185已PASS；源缓存传输、依赖和169原始capture身份验收由普通程序继续，未自动重试。正式训练、生产MI15/补编码及A/B评价未启动；源对照runner和科学口径仍待完成。下方“远端操作均0”等是各自历史准备回执，不替代本次技术执行状态。



## 2026-10-26 最新本地回传：P1/P2、源数据盘点及第四步执行卡完成，未训练



当前第四步以 [Claude 源侧对照 r1](collab/20261026_step4_source_controls_r1_claude.md) 为准。见 [P1/P2 与数据核查回传](collab/20261026_p1_p2_source_controls_preparation_response_codex.md) 和 [源侧执行卡](collab/20261026_step4_source_controls_execution_card_codex.md)。抽样误报均有源正常近邻，但源攻击也近，不能把“正常邻域近”直接当撤警规则；误报权重集中于少数小时、涉及较多组件。本地无未消耗合法额外正常 capture，S-COV+ 不可评。24 头候选索引已备，SimCam 逐设备精确质量匹配使数量对照退化、源缺 rate 标签、步数和 seed 聚合等口径须先收敛；runner 尚未实现。单 capture AfterImage 统计计时完成，神经前向/E3/训练/云端操作均为 0。源侧整体估计 3–5 小时属条件成本，不是已启动作业。第二步生产补编码／密 CAL／A/B 矩阵仍待独立授权，下方“最新”均按各自日期的历史快照阅读。



## 2026-10-25 最新r2回传：C5及精确补编码准备完成，待云端授权



执行以 [Claude r2](collab/20261025_c2b_c4_dryrun_readout_r2_claude.md) 为准。见 [C5回传](collab/20261025_c5_readonly_audit_response_codex.md) 与 [补编码／密源CAL云端授权申请](collab/20261025_c5_and_supplement_cloud_request_codex.md)。C5集成修FP为29/328/216，目标攻击预算四suffix通过，但源实际正支持未知、固定cap内源CAL无法撤警，暂不登记1C。精确新增E3为源4624+A5237+B11799=21660，冻结UID/快照/q14和复用向量均已核查。本地488行真实E3仅用于计时，不是正式补编码；本机104数值字节不同，生产必须先在云端原环境过104严格门禁。申请编码→密源CAL，预计5–8小时、止损总上限12小时；**尚未获本轮云端授权，未启动生产补编码、真正密CAL或新A/B评价**。完整矩阵仍缺WRONG配对与第三池规格及runner，不得将准备清单当作整链就绪。下方是此前执行快照。



## 2026-10-25 最新执行回传：C2b/C4完成，预算与密参考代码已实现，源侧dry-run完成



主方案以 [Claude r1及第6节用户确认](collab/20261025_c1_c3_readout_and_step2_r1_claude.md) 为准：主ε=0.1个百分点在源CAL执行，主指标观察期后、全量并列。最新 [Codex回传](collab/20261025_c2b_c4_and_step2_source_dryrun_response_codex.md) 已落盘：C2b服务延续不满足推进条件；C4的HeimVision后窗口69条FP=42条TCP组件不足+26条UDP零支持+1条不足修正。预算保护17项、密参考15项测试通过，完整源CAL148819行dry-run及ε=0逐位兼容通过，四ε均选λ=.25。**真正密源库尚需补编码4624个冻结位置**；源4728个完整上下文合法位置与CAL组件交集0，编码请求/快照/q14已备。现成LEARN早期额外编码为0，不能将104点稀疏库的PASS冒充密库校准通过。未运行E3、训练、远端或A/B新评价；云端仍需用户授权。以下均为此前的历史快照。



## 2026-10-25 此前主方案：Claude主导，C1–C3只读核查已完成



用户已指定 [Claude主方案](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261025_main_plan_claude.md) 为后续“下一步”的唯一主方案；well r1及此前讨论稿保留为历史。其第3节第一步C1–C3已按授权完成，见 [核查回传](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261025_c1_c3_readonly_audit_response_codex.md)。主线为 **QUERY_TAIL三seed集成＋V3＋B2**，不是下方学习式实验的seed27。C1：A的313条／4.984732个百分点参考未生效FP全部早于两小时窗起点，真正窗口内FP=0；窗口后重归一FPR为A4.751675%、B16.482115%。C2：B的10070条其他不合格TCP FP仅47条延续，权重占0.158465%。C3：指定三设备密参考代理额外修7208条集成FP，但824条攻击获正支持、3条集成新增FN，不满足直接推进分支。独立证据已落盘并带SHA；未训练、未新增E3、未改远端／原现场，未进入第二步，交Claude判读。



## 2026-10-25 13:51 状态快照：Codex 已审阅，well 落盘 r1（仍未授权训练）



Codex 支持方向但要求先修订；well 已写入 [collab/20261025_well_final_breakout_plan_r1_after_codex.md](collab/20261025_well_final_breakout_plan_r1_after_codex.md)（SHA256 d196d9a6e0b7f005b5667d091e7a157b353f9c6a2458fb0446b8075df2e41cb6）。审阅原文：[collab/20261025_well_final_breakout_plan_review_response_codex.md](collab/20261025_well_final_breakout_plan_review_response_codex.md)。下一步仅在用户授权后做阶段 0 只读加权分账。



## 2026-10-25 方案审阅回执：Codex已回复Well五问，仍未授权新实验



审阅见 [Codex对Well最终方案的回复](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261025_well_final_breakout_plan_review_response_codex.md)。结论为支持先做加权分账，但原稿须先修订：CAL攻击不能同时拟合资格规则并作同批保护；固定B2库新增支持门无法释放原有资格外FP；own/wrong需条件配对与预冻结结构匹配分母；阶段3入口及子集／全池比较逻辑须改。回复已补齐阶段0字段、互斥公式和脚本入口建议，并修正历史攻击指标口径及归因声明范围。被审稿SHA256保持原值；未改科研代码、远端或V4现场，未执行阶段0、起草执行卡或启动训练。下方“待Codex审阅”为此前送审快照。



## 2026-10-25 13:28 状态快照：well 最终破局方案已落盘，待 Codex 审阅（未授权训练）



well 将最终方案写入 [collab/20261025_well_final_breakout_plan_for_codex.md](collab/20261025_well_final_breakout_plan_for_codex.md)（SHA256 4142ca06dc06892fa7c784da3efed57833885a77fc8e749dcf856bd7d60fe82a）。请 Codex 按文末 5 问回复到同目录 *_review_response_codex.md。V4 现场冻结；不启训练，除非用户明确授权某一阶段。问题摘要仍以 [CURRENT_PROBLEM_BRIEF_20261025.md](CURRENT_PROBLEM_BRIEF_20261025.md) 为准。



仅参与科研方案讨论的AI，可先读[最小背景与当前问题](CURRENT_PROBLEM_BRIEF_20261025.md)，再按其中链接定向查证，无须通读全部历史。



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



**10月24日19:11历史启动回执：用户已授权并启动独立 V4，当时运行正常。** 北京时间19:08:45启动，root `/srv/paper04/learned_onboarding_20261024_v4`，unit `paper04-learned-onboarding-20261024-v4`，InvocationID `226cc64bb84747518f72afe05abe1969`。19:11:12启动验收为active/running、NRestarts=0、无异常，真实Python3.9下63项＋adapter另4项通过；tests／prepare／validate／preflight完成，已进入fit，尚未观察optimizer更新数。正式资源预检READY、完整规模证明VERIFIED，估计峰值约7.172 GiB；启动阶段RSS峰值4.617 GiB，不代替后续峰值。已验16 GiB硬限／8 GiB RSS守卫／4线程／8CPU quota／单worker／零自动重试。701件新包已验SHA，12个科研源与已验V4修复候选逐件一致，内存证明纳入新部署身份；原V1/V2/V3保留。进度页已切V4并验新启动时间／身份。见 [V4执行复核](../learned_onboarding_v1_20261023/memory_revision_v4_20261024/deployment_20261024/EXECUTION_REVIEW.md)／[V4执行回执](../learned_onboarding_v1_20261023/memory_revision_v4_20261024/deployment_20261024/EXECUTION_RECEIPT.json)。普通程序继续完整链，科学FAIL继续配对，技术异常停链；不持续AI轮询。下方“正式V4未部署／未重启”均为本轮授权前的历史修复快照，三模块／CAL／A/B科研结果仍待。



**10月24日最新修复验收：进度页已修复上线，V4 源侧完整规模验证及实际 preflight 均通过；正式 V3 仍异常停止，未重启。** 页面明确显示外层终态、停止时间／原因、进程、完成与未完成阶段，worker RUNNING 标为快照；独立修复验证不覆盖正式停止状态。V4 以共享任务记录和元数据减少驻留内存，完整 617,908 条 FIT／1,206,882 条任务实测峰值 5.839 GiB，旧／新任务 JSON、H、采样及批次对照通过；实际资源预检 READY、完整规模证明 VERIFIED，估计峰值 7.169 GiB，保留原 8 GiB 守卫。真实 Python3.9 下 63 项测试及 adapter 另4项通过，生产更新／CAL评分／目标读取均0，26件原V3资产前后身份一致。源困难信号门 READY 仅是后续训练资格，不是降低误报的科学结果。V4 当前是已验修复候选，正式部署配置／manifest 尚未准备，不可沿用复制来的V3部署身份直接启动。见 [修复说明](../learned_onboarding_v1_20261023/memory_revision_v4_20261024/MEMORY_REPAIR_REVIEW.md)／[修复回执](../learned_onboarding_v1_20261023/memory_revision_v4_20261024/REPAIR_RECEIPT.json)／[页面验收](../diagnostics_d1_d2_v1_20261022/PAGE_REPAIR_CARD_ACCEPTANCE_20261024.json)。下方启动／停止记录均按各自当时快照阅读；不持续AI轮询。



**10月24日15:37最新只读核查：学习型入网 V3 已异常停止，未完成。** 北京时间13:58:40在fit触发 `OUTER_RESOURCE_RSS_LIMIT`：进程树RSS 8,610,660,352 bytes超过8 GiB守卫（8,589,934,592 bytes）。远端总状态与异常回执一致，systemd为failed／exit-code=1、MainPID=0、NRestarts=0，无对应V3/现代头训练进程；无 `CHAIN_COMPLETE.json`。tests／prepare／validate／preflight已完成，fit未完成，CAL／target／A/B评价尚未开始。fit子状态停留在13:58:27的 `source_task_records`（view=1，450560/617908），其RUNNING及页面local整体RUNNING均不可当实时运行证据；子进程returncode=0也不替代外层失败终态。属于资源异常，不是科学FAIL；现场保留，本轮未重启／续跑／修改远端。见 [只读状态回执](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/deployment_20261024/operations/STATUS_CHECK_20261024_153755.json)。下方13:28启动运行是历史快照，不代表当前仍运行。



**10月24日13:28最新启动验收：** 用户已授权“修复好了，就可以启动实验了。”。独立V3全链于北京时间13:26:46启动，新root `/srv/paper04/learned_onboarding_20261024_v3`、unit `paper04-learned-onboarding-20261024-v3`，原V1/V2现场和权重保留。13:28:17验收为active/running、无异常；真实Python3.9/Torch2.5.1下原49＋新增5＝54项全部通过，adapter另4项通过（真实目标读取0）。tests/prepare完成，当前validate；资源preflight、真实辅助头/模块训练、CAL和A/B仍待，科学结果暂无。已验16GiB硬限／8GiB RSS守卫／4线程／单重worker／零自动重试。普通程序按完整冻结链串行继续，科学FAIL继续配对，技术异常停链。既有18765页面已切到V3并验connected=true，不持续AI轮询。见 [执行复核](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/deployment_20261024/EXECUTION_REVIEW.md)／[执行回执](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/deployment_20261024/EXECUTION_RECEIPT.json)。下方“实验仍停止／未启动”等属于本次授权启动前的历史快照。



**10月24日13:18历史数值修复验收（当时尚未重启）：** V2 的 G1 异常已独立复现：108,675 条源侧留出样本中 1 条超原容差；输入、前一 Linear/ReLU 均逐位相同，差异出在末 Linear，原 FIT 伪阈值下零判决翻转、零新增攻击漏检。V3 使用独立逐条 float32 推理，保留真正 256/127 两路径、各自尾批与原门，未改训练公式/权重或正式头路径。云端实际 Python 3.9/Torch 2.5.1 原49＋新增5项通过；两个既有辅助头共617,908条留出样本，新版256/127及独立重载分数全部逐位相等，输入SHA/原FIT索引/元数据/检查点训练UID补充核验通过。跨版本分数不宣称逐位保留，具体差分与资源以 [修复回执](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/REPAIR_RECEIPT.json)／[审查说明](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/NUMERIC_REPAIR_REVIEW.md) 为准。**本轮仅诊断、修订和前向验证，实验仍停止，未重训或自动续跑；完整源几何/H、源困难信号、三模块、CAL和A/B仍待正式执行，科学收益未知。**



更新：2026-10-25 12:33。本文整理回执和结果，不是新的实验合同。独立V4-EVAL1已完成40主项＋12控制，工程完成与验收PASS；学习存在局部收益但未超几何，池FPR≤1%目标未达、参考特异性未证实。原V4仍异常停止，完整预测未下载；最新事实以顶部完成复核及完整结果报告为准，未启动新实验。



**用户固定要求：AI 不持续轮询长任务。** 普通后台程序显示进度即可；启动验收、异常排查、完成验收时才读取必要状态。有代码、集成、分析任务时继续做，不因避免轮询而提前结束工作。



**10月24日历史异常与页面恢复快照（后续修复见顶部）：** 用户报告页面拒绝连接后核查：本地PID62256已退出、18765无监听，现已改由当前用户的Windows任务计划服务独立托管（仅按需启动、无定时触发器、无AI任务），PID14752，HTTP200、云端连接正常，见 [页面修复回执](../learned_onboarding_v1_20261023/compatibility_revision_v2_20261024/LOCAL_PAGE_REPAIR_20261024.json)。同时发现云端V2已于北京时间12:10:36在fit异常停止：AUX_G0完成40轮/17000步并封存；AUX_G1完成40轮/79600步，但训练后的256/127分批分数回放不满足原rtol=atol=1e-6，报QUERY_BATCH_SCORE_DRIFT，未封存。原批次重新加载bitwise门已通过，G1偏差大小／判决／新增FN集合尚未知，不能豁免或放宽容差。三个修正器、CAL及目标评价均未开始，科学结果暂无。14件小证据已只读回传验SHA，见 [停止诊断](../learned_onboarding_v1_20261023/compatibility_revision_v2_20261024/operations/fit_stop_20261024/DIAGNOSIS.json)。现场、模型与两个失败版本保留，未重跑／续跑／修改远端。12:04运行中是此前真实快照，不能作为当前状态。



**10月24日12:04历史运行快照：** V2服务active/running，无EXCEPTION_STOP；tests、prepare、validate、preflight均完成，已进入fit阶段。进程在运行，当前cgroup内存约3.8GiB，进程树RSS峰值约6.25GiB，低于8GiB守卫。此次未观测optimizer更新数，不能凭stage名称报具体训练步数；CAL／目标评价和科学结果仍待。见 [状态回执](../learned_onboarding_v1_20261023/compatibility_revision_v2_20261024/operations/STATUS_CHECK_20261024_120437.json)。不持续AI轮询，进度页由普通程序更新。



**10月24日12:01启动验收快照：** 用户已明确确认重新启动。独立兼容 V2 于北京时间12:00:51启动，实际 Python 3.9 环境中原49项全部PASS、adapter另4项PASS（真实目标读取0）；首次临时目录API错误已通过实际验收。12:01:35服务active/running、完成tests、正在源prepare；不能称真实训练已开始，资源preflight、辅助头／模块训练、CAL及A/B收益仍待。见 [V2执行复核](../learned_onboarding_v1_20261023/compatibility_revision_v2_20261024/EXECUTION_REVIEW.md)／[执行回执](../learned_onboarding_v1_20261023/compatibility_revision_v2_20261024/EXECUTION_RECEIPT.json)。原失败现场完整保留；新root为 `/srv/paper04/learned_onboarding_20261024_v2`、新unit为 `paper04-learned-onboarding-20261024-v2`，不要重用v1输出。已验16GiB硬限／4线程／8GiB RSS guard和空闲窗口，源预检通过后由程序按冻结完整链串行继续；科学FAIL继续配对、技术异常停止留现场，零自动重试。现有18765进度页显示新V2，不持续AI轮询。下方停止／待确认记录均是此次重新执行前的历史。



**10月24日11:20历史首次执行回执：** 已按用户同意部署并首次启动，但远端 Python 3.9 启动验收中 49 项有 1 项因测试临时目录参数不兼容而 ERROR，链已停止；未进入源准备、资源 preflight 或真实训练，CAL／A/B 新结果均无。独占窗口与 16 GiB 硬限已验，停止现场已回传验 SHA。已备本地独立兼容修订，49 项通过、科研源码及断言未改，实际远端修订仍未验，未上传或重提。见 [执行复核](../learned_onboarding_v1_20261023/deployment_20261024/EXECUTION_REVIEW.md) 和 [修订回执](../learned_onboarding_v1_20261023/compatibility_revision_v2_20261024/REVISION_RECEIPT.json)。进度页已显示 EXCEPTION_STOP；遵守异常停链、不自动重跑，下一步由用户决定是否独立新执行。以下“窗口待落实／仍未部署”等为历史快照。



**10月24日现代头完成回执（学习式首次执行前的快照）：** 现代三家头×三 seed＋各自 v3 四库配对已全部完成，14/14、failure=null；北京时间 10 月 23 日 20:38:52 结束，systemd 成功退出。见 [结果复核](../modern_head_new_lineage_v1_20261022/analysis/completion_review_20261024/RESULT_REVIEW.md)。B2 ensemble 加权 FPR：MLP A/B=5.74266%/15.21880%，TabM=6.14519%/19.96197%，LightGBM=8.32616%/20.31610%。96 份配对报告均记录零新增攻击漏检，但三家头和四库完整系统科学门槛均 FAIL；TabM 源保护选择 λ=0。113 个约 12 MiB 小报告已回传核对 SHA 和完成链，完整模型／逐条预测备份待完成。该回执时学习式真实训练未运行，整机窗口尚未验收；后续已实际验收窗口并首次执行，结果以上方学习式执行回执为准。下文“现代结果待完成”等均是历史快照。



**10月23日历史实现回执：** 用户已授权实现。新代码、合成全流程验证与真实源核验见 [实现说明](../learned_onboarding_v1_20261023/README.md) 和 [implementation_manifest.json](../learned_onboarding_v1_20261023/implementation_manifest.json)。源 q14／UID／spool／头／执行代码身份已验收，33,147 条 CAL 正常精确复现原 seed27 阈值；见 [源适配回执](../learned_onboarding_v1_20261023/validation/source_adapter_receipt.json)。全量 FIT 帧资格已通过，正常自身参考覆盖 4 台、攻击 3 台，新分组实测共享 7 捕获；真实困难信号仍待辅助头训练。最终测试数以新回执为准。真实辅助头／修正器训练、CAL 攻击 λ、A/B 学习收益未运行；现有作业和页面未改，无远端检查或 AI 轮询。冻结规格和旧回执保留原交付身份，NOT_IMPLEMENTED 不是最新工程状态。



**10月23日历史方案交付：学习式入网 V1 方案已形成，用户指定 astra 做方案、sol 后续实现。** 先读 [执行规格](../learned_onboarding_pilot_v1_20261023/EXECUTION_SPEC_V1.md) 和 [Sol 实现交接](../learned_onboarding_pilot_v1_20261023/IMPLEMENTATION_HANDOFF.md)，审查及文档身份见同目录 REVIEW_V1.md／PLAN_RECEIPT_V1.json。主线复用已验收 QUERY_TAIL seed27，新增两个固定三设备组互换的辅助头和三个小修正器（普通、困难、匹配 query-only），最多五个新训练终点。该方案已定数值配方，尚未实现、训练或提交；不是旧“四设备主头＋两外层设备”的五终点草稿。不按现代头 A/B 成绩选先导主头，也不声称单 seed 为三 seed 集成。原九头及其 v3 配对继续按原合同，本轮未查询实时状态。



源侧已有 [结构审计](../learned_onboarding_pilot_v1_20261023/source_task_audit.json)，但 q14／UID 绑定、精确帧因果资格、折外真实困难任务覆盖与资源尚待实现验收；没有学习式新结果。旧拟定外层/开发划分共享7捕获仅属于旧审计，新三三分组的捕获交叉待统计。完整源 FIT 可供头和修正器使用；至少两台设备具备真实折外正常修正信号是新规格的训练门槛，不能用排名样本数量冒充有效 OOD。下文现代链信息仍是既有启动/验收事实，不是本次实时检查。





## 1. 阅读顺序与历史状态陷阱



**数据用途澄清仍有效：** [主方法数据用途与额外先导的区别](../learned_onboarding_pilot_v1_20261023/DATA_USE_CLARIFICATION.md)。源 FIT 可用于检测头和入网修正器，CAL 继续校准，A/B 继续评价；可复用适配的已训练检测头。旧五终点外层验证草稿不是重训主头的硬前置；最新执行规格另行选定两辅助头来构造真实头层未见设备任务，正式主头仍复用。源侧内部共享捕获不代表原 FIT/CAL/A/B 隔离失效。原准备快照和审计回执保留。



工作根目录：`D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline`。



先读本文，再读以下小文件；其余材料按任务需要追溯，不全量扫描 runs、源码和数月日志。



| 入口 | 用途 |

| --- | --- |

| [学习式入网 V1 执行规格](../learned_onboarding_pilot_v1_20261023/EXECUTION_SPEC_V1.md)＋[实现交接](../learned_onboarding_pilot_v1_20261023/IMPLEMENTATION_HANDOFF.md) | 最新方案；精确算法、数据职责、五终点预算、对照和未验收事项。方案完成不等于实现或效果完成 |

| [现代头 README](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_new_lineage_v1_20261022/README.md)＋[启动回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/modern_head_new_lineage_v1_20261022/LAUNCH_RECEIPT.json) | 已启动任务、准确包版本、资源与启动验收事实 |

| [D1/D2 最终结论](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/diagnostics_d1_d2_v1_20261022/RESULT_REVIEW.md) | 两项诊断已经结束 |

| [完整入网结果](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/onboarding_new_lineage_v1_20261022/analysis/RESULT_REVIEW.md) | 当前完整方案锚点与剩余误报问题 |

| [换头及入网方案](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/next_head_and_onboarding_plan_20261022.md)，包括末尾执行回执 | 本轮比较的目的、结束条件与后续分支 |



[主交接](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/mainline_handoff.md)和[实验索引](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/mainline_experiment_map.md)含大量历史记录。先看最新导航，再核对日期及执行回执；首次出现的“当前／未运行”不保证是最新状态。方案中的原登记文字保留，后续事实以新回执为准，不能改写冻结合同抹掉历史。



`project_onboarding_20260930.md` 是旧接手摘要，其环境、资源和执行分工已有变化。所有旧测试数、PASS、峰值和进度都保留原观测范围；不能说成本轮重新测试或实时观测。



## 2. 研究目标与当前结构



目标是在新设备、不同采集环境中同时保持攻击检出和低正常流量误报，未见设备通过合法正常参考进行入网适应。适应不能靠撤掉正确攻击告警换取低误报。模块要职责清晰、可消融，有独立证据；不无限复制旧系统或堆模块。



当前结构：冻结 netFound/E3 前端 → 768 维近期表示＋14 维当前包描述 q14 → 检测头 → 同一 v3 几何入网修正 → 固定规则判定。头单独和完整系统都评价，不能把头单独结果当成完整方案。



- A 是当前 CIC 开发池，B 是当前 UNSW 开发池；精确样本、角色和权重以封存清单为准。

- 原缓存数组为 794 维（768 E3＋26 状态），本轮头输入为 782 维（768＋q14），不是形状矛盾。

- 前端重建是学校超算磁盘损坏后的恢复。已全部重建、验收、本地备份，不需重新提取百万行特征。

- 新谱系标记 `NEW_RECONSTRUCTION_LINEAGE / PARENT_PARITY_UNAVAILABLE` 必须保留。失去父缓存，不能宣称重建结果与旧父缓存逐位相等；当前环境内回放验证另有证据。



## 3. 已完成的阶段和结论



| 阶段 | 已确认事实 |

| --- | --- |

| 冻结前端缓存 | 1,095,200 行；本地 `runs/ecs_cache_resume_v1_20261020/verified_cache_20261022`；远端 `/srv/paper04/cache/coupon_resume_20261020_v2`。marker SHA256：`0185757a4724569359e128a6d829e6a0e524df26e5011e7b2507a08d65d4a9b1` |

| QUERY_TAIL 等同缓存十二头 | 已完成、本地验收；见 [结果](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/query_tail_ecs_v1_20261022/analysis/RESULT_REVIEW.md) |

| QUERY_TAIL＋完整入网 v3 | OLD_BANK/B0/B1/B2 全完成，约 0.849 GiB 结果已本地备份并验 SHA；见 [回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/onboarding_new_lineage_v1_20261022/RESULT_BACKUP_VERIFIED_v3.json) |

| 误报路径复盘、D1/D2 | 均完成；结论见下文，不再为它们追加诊断阻塞换头 |

| 现代三家头＋同模块配对 | 14/14 已完成，10 月 24 日终态及小结果复核通过；三家科学 FAIL。小报告已回传，完整模型／预测备份待完成 |

| 新输入三设备回归、独立确认、更广攻击覆盖 | 仍需补证据；当前 A/B 已消费为开发材料，不能冒充独立确认 |



已有固定集成的**加权 FPR**：



| 方案 | A | B |

| --- | --- | --- |

| QUERY_TAIL 头单独 | 6.15818% | 23.65666% |

| QUERY_TAIL＋B2 入网 | 6.14371% | 16.59348% |



完整入网降低 B 误报，32 份 seed/集成配对报告均零新增攻击漏检，但池级 FPR 1%／逐设备 2% 等科学门槛仍未过。B2 按条数 FPR 为 A 0.37985%、B 30.76832%，不能混用口径。B 保留原头五条攻击漏检，不是所有攻击零漏检。



历史 A 的正向结果真实存在：[旧学习参考模块结果](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/legacy_qref_training_real_result_v1_20260922.md)，加权 FPR 2.769602%→0.317174%，FP 374→30，零新增攻击漏检。当前输入、头和模块已变化；新版未达标不推翻旧结果，也不证明旧权重能直接接上。**OLD_BANK 仅指历史参考身份，不代表恢复旧学习修正器。**



诊断终态：



- D1 参考分数位置校准最终目录 `runs/diagnostics_d1_d2_v1_20261022/output/d1/r2`，由 `CURRENT.json` 指向。源 CAL 压力检查选 λ=0.10；B2 的 B 加权 FPR 降至 17.06690%，却新增 26 条集成攻击漏检，科学 **FAIL**，不进现代头矩阵。不继续看目标结果调规则或阈值。首轮失败现场保留，不当成最终状态。

- D2 源／目标正常域可分性：四材料均不满足登记分组／验证条件，**NOT_EVALUABLE，0 次拟合**。不强行随机拆分，不虚构 AUC；不能推断无域差异、前端失效或换头无效。

- 旧 A 曾修正的 344 条 UID 均匹配物理端点；当前头已判正常 141 条，剩余处理路径已记录。这是多处变化后的描述性核对，不是单因素因果结论。

- 原环境 CAL/A/B 共 477,021 条查询，三 seed 及集成已逐 bit 回放一致；804 条参考评分核验并拉回。这些是已有验证，无需接手即重跑。



## 4. 当前正式任务的准确定位



**不要因新对话接手而重新部署、重启、重复提交或重训。** 以下定位已有作业；实时状态只在具体任务需要时读取。



| 项 | 已记录值 |

| --- | --- |

| ECS | 代金券实例 `i-0jlequa076yrk9p5wjet`，物理 16 vCPU／32 GiB |

| SSH | 别名 `paper04-coupon-20261020`；最近确认 IP `8.145.62.163`。旧 `8.130.103.183` 已变化，节省停机再启动后 IP 可能再变 |

| Python | `/opt/paper04-venv/bin/python`；Python 3.9.24／NumPy 2.0.1／Torch 2.5.1+cpu |

| systemd unit | `paper04-modern-head-20261022-v1` |

| 本地正式包 | `runs/modern_head_new_lineage_v1_20261022/package_v2/` |

| 远端部署包 | `/srv/paper04/modern_head_new_lineage_20261022_v2` |

| 远端输出 | `/srv/paper04/runs/modern_head_new_lineage_20261022_v1`，注意输出仍 v1 |

| 状态／日志 | 输出目录的 `status.json`、`logs/`、`monitor/` |

| 包清单 SHA256 | `1cd3f3189d53b18fb362eb292796871ecdd08b758e05e2f0e51fd397cb6046d0` |

| 本地进度页 | [http://127.0.0.1:18765/](http://127.0.0.1:18765/)；18763/18764 是较早阶段页面 |



`package/` 为保留的首版：参考库回执模式预检失败，未正式训练。v2 验证真实生产者 manifest→receipt→四项载荷哈希及身份／形状／数值，不改训练配方。13 项本地测试、三家真实源 FIT 64 行训练／保存／逐 bit 回放已通过。



**版本陷阱：** `OPERATE.md` 保留首版路径／命令，只能参考结构，实际路径以启动回执和上表为准，不能照抄重提。启动回执中的 MLP seed27 epoch14／31,442 更新是历史启动快照，不是现在进度。



正式矩阵为 MLP_QUERY_BCE、TabM、LightGBM × seeds 27/127/227，共九新头；三家均接同一 v3 入网 OLD_BANK/B0/B1/B2。MLP 配对补充登记已完成；原 QUERY_BCE 缺完整冻结数值运行时证据，故重训公共基线，不能补写历史证明来声称复用。



神经 40 轮／LightGBM 请求 500 轮；LightGBM 合法自然停止不报 `TREE_FIXED_ROUND_BUDGET`。源 FIT/CAL、输入、查询、训练配方固定。科学 FAIL 不阻断已登记模块配对；身份、数据、非有限数值或资源错误停止，零自动实验重试。



资源：8 CPU quota、4 数值线程、16 GiB 硬上限、14 GiB RSS 保护、单重 worker。TabM 三 seed 约 21 小时仅是步时推算的纯训练量级，不是全链 ETA／当前剩余时间。不要沿用历史 100 多 GiB 申请，也不要为压低申请牺牲正确性；只重算变化阶段。



进度程序 `runs/diagnostics_d1_d2_v1_20261022/src/progress_server.py` 普通后台每 60 秒读小状态，网页每 10 秒刷新，不调用 AI。电脑关闭不影响远端 systemd 作业，页面暂不能更新。别随意新增现代头静态 `progress.json`，页面可能优先读它而不更新远端状态。



学校超算当前暂缓：此前计算节点访问共享项目／Python 路径的 stat 卡住，尚待稳定确认。不在当前任务外偷偷并行提交。以后回 HPC，要区分登录与计算节点，按学校手册复用环境并在真实计算节点验证；不能把“软件很多”等同依赖组合可用，也不擅自联网安装／重建全环境。



## 5. 科研、工程和用户偏好



1. **冻结角色／身份。** FIT 训练，CAL 按合同校准；不拿目标查询拟合、调阈值、挑 seed／中间轮次。不删困难样本、改 UID／权重／分母，或改变已消费开发材料的资格。

2. **保护比较基准。** 模块相对自己的基础头，逐 seed 与 ensemble 检验零新增攻击漏检；换头按原攻击／分组回归合同，不额外发明跨头逐 UID 硬门槛。报告加权和按条数 FPR、攻击召回、设备最差情况、资源成本，不放宽失败门槛。

3. **使用 v3 因果参考。** 只允许审计通过的目标 pre-bank 观察期重放，早期查询保留 support=0、原判回退。不能恢复 blanket UID overlap 拒绝，也不能为过检查删查询；源角色及 OLD_BANK 隔离仍按合同。

4. **比较有终点。** 固定矩阵完成后，再依据联合效果决定正常覆盖、可学习参考模块或表示／训练覆盖分支。本轮不加 D1、阶段阈值、滚动库、新编码器或大量超参搜索。低误报伴随不可接受攻击退化仍是负结果。

5. **状态分别解释。** 工程 COMPLETE 不等于科学 PASS；科学 FAIL 不等于程序坏；NOT_EVALUABLE 不等于没有问题。旧成功、新失败都保留并说清适用范围，不用局部 PASS 或测试数量替代核心效果。

6. **保护工作区。** 最近分支 `codex/exp-mainline`，HEAD `4b28747` 很旧，但大量近期实现／文档未跟踪。已有 issue27by 八项旧修改和其他协作者工作，不 reset/clean、批量覆盖、整仓暂存或混入无关提交。新实验独立版本目录，冻结产物纠错另留回执。

7. **不擅自扫盘清理。** 用户明确过“先接收信息，不是现在扫盘”。不按日期删 runs，不扩大到相邻文件。原始数据、有效缓存、模型／编码器／归一化器、正式结果、上传／代码／环境包、回传归档、SHA／清单和恢复资产都保护。清理须限定白名单、核对依赖和保留副本，保留原校验清单与清理记录。

8. **有预算地备份。** 重要结果需本地拉回并验归档／内部身份／SHA；完整现代结果尚未验收备份，也未启用新的自动大结果下载。导出预算约 9 GiB，下载前核对当时磁盘、已有文件、临时双份占用；不把历史空闲 14／32.5 GiB 当实时值。同机目录副本不是独立介质备份，不自动新增第三方存储。尾部导出失败修尾部，不自动重训。

9. **计费说清。** 自动停机未启用：此前 IAM 安全验证失败，用户接受先手动处理。不能说实验完自动不收费。节省停机释放计算资源，磁盘仍计费；系统关机不自动等同云平台节省停机。未完成作业不要停机；导出／停机按当时指令处理，不自行新购实例或改带宽计费。

10. **沟通和授权。** 中文直接解释，先结论再证据；命令分清本地 PowerShell、远端 Bash。已授权范围内的修复／集成／必要验证自主完成，不逐文件反复询问。只读接手不构成新增实验、删除、停机、云权限授权；历史命令不自动执行。密码／私钥不进聊天、文档和日志。



## 6. 协作、首次回复与维护



DeepSeek 已加入，沿用文档合作：`runs/mainline_docs/collab/YYYYMMDD_<主题>_<deepseek|codex>.md`。Claude 旧约定可作背景，不能假设目前在线或审查了本轮。不自动向其他聊天、邮箱或外部服务发消息。



协作者在 collab 写讨论／审查，代码与交付保持明确负责范围，避免多人覆盖。用户要求读某文件时实际阅读并逐条回应、写回执，不把旧讨论当新回复。旧文档里的用户上传／提交分工已被后续具体授权覆盖，不要求用户重做已完成步骤。



按任务补读 [D1/D2 规格](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/diagnostics_d1_d2_spec_v1_20261022.md)、[资源维护约定](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/resource_budget_maintenance.md)、[协作背景](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/claude_codex_collaboration_20260928.md)、[工作方式和 HPC 经验](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/mainline_workflow_and_hpc_continuity_20260909.md)。资源文档底部“前端尚未定值”为旧记录，不触发重建；历史环境、权限、审查、命令按最新证据使用。



新对话第一次回复简述：研究目标、已完成／仍在跑的事项、关键约束、下一步性质和未知状态。先只读接手，不为证明接手而再次连服务器、跑测试、重提特征；用户给下一任务后继续对应工作。



后续真实状态改变时，更新本文当前快照，同步主 handoff 顶部和实验索引；完整证据留对应 run。不要只在巨型文件底部追加与顶部矛盾的“当前”。



## 2026-11-03：查询选取封存前的入口快照

补充归档：181418在1CPU/6GiB/600秒内完成，Slurm COMPLETED、0:0、7分46秒，真实小切片与13形状严格探针通过；33导出成员SHA复验。该阶段只关闭旧小fixture门，完整worker当时尚未实现，正式预算与评价未授权。后续当前状态由NEW_CHAT_START_HERE.md顶部统一维护。

# 当前状态

更新：2026-11-03。后续只覆盖本区块，不再向入口追加历史。

1. **唯一方法及冻结位置**：C5（p=3）已冻结，A/B 仅作开发证据。[方法冻结 JSON](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。
2. **离目标多远**：B 主视图逐样本误报 1.55%，全时段 2.24%，部分设备仍高于 2%；A 召回 99.82%。独立外部效果尚未确认。
3. **正在做什么**：Edge适配、合法人口及kNN源校准完成；65行本机真实切片在编码clone严格一致性门停止，未到正式外部评价。
4. **等谁做什么**：待Linux3.11同切片预检、全量续跑和实际预算，工程卡未冻结；山西大学IEL已订，DataPort权益仍待确认。无需下载大包，无作业在跑，不持续监测。
5. **最新回执**：[学校访问核查](collab/20261103_shanxi_university_dataport_access_codex.md) · [工程进度](../edge_external_test1_engineering_v1_20261103/PROGRESS.md)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)



## 2026-11-04 UTC：UDP诊断前入口快照

# 当前状态

更新：2026-11-03。后续只覆盖本区块，不再向入口追加历史。

1. **唯一方法**：C5（p=3）冻结，A/B仅作开发证据。[冻结JSON](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。
2. **现有结果**：B主视图选中查询误报1.55%，全时段2.24%；A召回99.82%。独立外部效果尚未确认。
3. **已完成**：v2四项修复、82项检查通过；用户授权的Linux工程作业181645已提交并进入NORMAL因果重放，正式外部评价未启动。
4. **当前执行**：1CPU/8GiB/2小时；[进度页](http://127.0.0.1:18793/)由普通程序更新并取回验收，无AI持续监测、无自动重投。TmpDisk=0已作提交前适配，节点32GiB实际空闲门/24GiB守卫保留；下次独立复核交小anti。
5. **最新证据**：[181645启动](collab/20261103_edge_v2_linux_gate_181645_start_codex.md) · [v2修复验收](collab/20261103_edge_formal_v2_repair_acceptance_codex.md)。当前仅启动验证通过，最终Linux工程验收PENDING，正式预算待后续实测。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-04 UTC：181645结束后分支决策确认前入口

# 当前状态

更新：2026-11-04 UTC。后续只覆盖本区块，历史另存。

1. **唯一方法**：C5（p=3）冻结，A/B仅作开发证据。[冻结JSON](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。
2. **现有结果**：B主视图选中查询误报1.55%，全时段2.24%；A召回99.82%。独立外部效果尚未确认。
3. **当前实验**：Linux工程作业181645运行至UDP；1CPU/8GiB/2小时，最终验收PENDING，正式外部评价未启动。[进度页](http://127.0.0.1:18793/)自动更新，无AI持续监测、延期或自动重投。
4. **本次诊断**：24/24样本确认共享盘进度fsync长时间阻塞；独立候选8项测试及Linux小文件对照通过，尚未集成或热改。保留全部科学口径与权威回执持久化；下次独立复核交小anti。
5. **最新证据**：[UDP瓶颈与候选](collab/20261104_udp_progress_io_bottleneck_codex.md) · [181645启动](collab/20261103_edge_v2_linux_gate_181645_start_codex.md)。小文件加速不等于整场加速，完整Linux门仍待完成。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-04 UTC：181645停止与v3封存前入口

# 当前状态

更新：2026-11-04 UTC。后续只覆盖本区块，历史另存。

1. **唯一方法**：C5（p=3）冻结，A/B仅作开发证据。[冻结JSON](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。
2. **现有结果**：B主视图选中查询误报1.55%，全时段2.24%；A召回99.82%。独立外部效果尚未确认。
3. **当前实验**：Linux工程作业181645运行至UDP；1CPU/8GiB/2小时，最终验收PENDING，正式外部评价未启动。[进度页](http://127.0.0.1:18793/)自动更新，无AI持续监测、延期或自动重投。
4. **已确认决策**：181645不热改，结束后标准验收；若预算内未完成，直接制作独立v3封存优化。完整角色须验明后复用，未完成UDP从原包起点重放；下一次独立复核交小anti。
5. **最新证据**：[结束后分支决策](collab/20261104_edge_181645_postrun_decision_codex.md) · [UDP瓶颈与候选](collab/20261104_udp_progress_io_bottleneck_codex.md)。候选8项检查及Linux小文件对照通过，完整Linux门仍待完成。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-04 v3r1授权交付前快照

# 当前状态

更新：2026-11-04 UTC。后续只覆盖本区块，历史另存。

1. **唯一方法**：C5（p=3）冻结，A/B仅作开发证据。[冻结JSON](../c5_method_freeze_v1_20261102/METHOD_FREEZE.json)。
2. **现有结果**：B主视图选中查询误报1.55%，全时段2.24%；A召回99.82%。独立外部效果尚未确认。
3. **181645终态**：1小时57分37秒触发重放时间守卫，工程验收STOP；峰值约3.31GiB，临时目录清理成功。NORMAL/HTTP完整产物校验通过，UDP部分角色不可复用。
4. **已完成/下一步**：独立v3进度I/O优化已集成封存；93项本地检查、6万查询元数据核验通过。默认新输出全量重放，不隐式迁移v2；待小anti独立复核和真实Linux门，未提交新作业。
5. **最新证据**：[停止与v3交付](collab/20261104_edge_181645_stop_and_v3_package_codex.md) · [v3复核清单](../edge_formal_execution_v3_20261104/REVIEW_REQUEST.md) · [进度/终态页](http://127.0.0.1:18793/)。正式评价未启动，无自动延期或重投。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-04 · 181699失败诊断前状态

# 当前状态

更新：2026-11-04 UTC。后续只覆盖本区块，历史另存。

1. **唯一方法**：C5（p=3）冻结，A/B仅作开发证据；正式外部效果尚未确认。
2. **181645已封存**：时间守卫STOP，约3.31GiB峰值，清理成功；NORMAL/HTTP完整产物有效，UDP部分产物不可复用。
3. **本次授权**：用户明确免小anti独立复核，登记USER_WAIVED；先真实小切片，通过后1CPU/8GiB/2小时跑v3完整工程门，不需再次请求授权。
4. **运行状态**：真实78端点预检181696已RUNNING、进入原包重放；独立1CPU/8GiB/10分钟。v3r1的98+15本地测试和6万查询元数据核验通过；预检PASS后自动提交完整门，默认新输出全量重放。
5. **最新证据**：[v3两阶段交付](collab/20261104_edge_v3_preflight_then_gate_codex.md) · [自动流程进度](http://127.0.0.1:18794/) · [交付目录](../edge_formal_gate_deployment_v3_20261104/)。完整工程门尚未提交；正式评价未授权，不自动延期或重投。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-04 · v4修复续跑前状态

# 当前状态

更新：2026-11-04（用户时区America/Los_Angeles）。固定五项，历史另存。

1. **唯一方法**：C5（p=3）冻结；独立外部效果尚未确认，正式评价未授权。
2. **预检已通过**：真实78端点181696耗时6分53秒，终态与回执重新核验通过；本次独立复核按用户决定USER_WAIVED。
3. **完整门失败**：181699运行1:57:37触发EDGE_REPLAY_DEADLINE；峰值5.99GiB，清理成功，尚未进入完整门编码与恢复验证。
4. **已查清/下一步**：UDP最后STOP心跳3170387/3215732帧（98.59%）；NORMAL/HTTP完整标记已见、载荷SHA审计待做。UDP上下文append约87.6分钟，内部耗时需拆查；部分UDP不可续用，未重投或延期。
5. **最新证据**：[181699失败诊断](collab/20261104_edge_181699_budget_stop_codex.md) · [核验回执](../edge_gate_181699_closure_20261104/CLOSURE.json) · [终态进度页](http://127.0.0.1:18794/)。36件取回工件及归档SHA已核验；原v3/v3r1封存不修改。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-04 · v4预检运行时状态

# 当前状态

更新：2026-11-04（用户时区America/Los_Angeles）。固定五项，历史另存。

1. **唯一方法**：C5（p=3）冻结；正式外部效果尚未确认，正式评价未授权。
2. **旧轮封存**：181699在1:57:37触发EDGE_REPLAY_DEADLINE；UDP最后98.59%，上下文随scratch清理。旧结果与诊断保留。
3. **本次修复**：独立v4新增持久帧级上下文检查点及跨作业恢复；NORMAL/HTTP完整产物逐块审计后复用，本次UDP重建。109+15本地测试通过，独立复核USER_WAIVED。
4. **当前运行**：真实78端点＋UDP16强制退出恢复预检181854已提交；预检1CPU/8GiB/10分钟，PASS后完整门1CPU/8GiB/2小时各一次。最新状态见进度；无自动重投/延期。
5. **最新证据**：[v4修复续跑](collab/20261104_edge_v4_durable_resume_codex.md) · [启动回执](../edge_formal_gate_deployment_v4_20261104/STARTUP_READBACK.json) · [实时进度](http://127.0.0.1:18795/)。完整门尚待预检，不将启动计为通过。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-04 · 延长预算及实际恢复预检前状态

# 当前状态

更新：2026-11-04（用户时区America/Los_Angeles）。固定五项，历史另存。

1. **唯一方法**：C5（p=3）冻结；正式外部效果尚未确认，正式评价未授权。
2. **旧轮封存**：181699在1:57:37触发EDGE_REPLAY_DEADLINE；UDP最后98.59%，上下文随scratch清理。旧结果与诊断保留。
3. **本次修复**：独立v4新增持久帧级上下文检查点及跨作业恢复；NORMAL/HTTP完整产物逐块审计后复用，本次UDP重建。109+15本地测试通过，独立复核USER_WAIVED。
4. **当前运行**：真实78端点＋UDP中断恢复预检181854已PASS（6分51秒）；完整门181856已RUNNING，1CPU/8GiB/2小时。最新状态见进度；无自动重投/延期。
5. **最新证据**：[v4修复续跑](collab/20261104_edge_v4_durable_resume_codex.md) · [启动回执](../edge_formal_gate_deployment_v4_20261104/STARTUP_GATE_REMOTE_READBACK.json) · [实时进度](http://127.0.0.1:18796/)。完整门最终验收仍待完成，不将启动计为通过。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-04 · 181905最终验收前状态

# 当前状态

更新：2026-11-04（用户时区America/Los_Angeles）。固定五项，历史另存。

1. **唯一方法**：C5（p=3）冻结；正式外部效果尚未确认，正式评价未授权。
2. **181856已封存**：运行1:57:42再次EDGE_REPLAY_DEADLINE；峰值5.50GiB。46件终态工件SHA核验，持久检查点2877608/3215732帧（89.5%）保留。
3. **本次授权与修复**：用户同意增加时间；完整门改1CPU/8GiB/6小时，内部三处时限同步；传输观察12小时。冻结v4科学绑定不变，本地19检查通过，独立复核USER_WAIVED。
4. **当前运行**：181902实际检查点恢复＋真实78端点预检RUNNING，上限30分钟；必须恢复大检查点并计算后续16个端点，通过后唯一完整续跑。完整门尚未提交，无自动延期/重投。
5. **最新证据**：[扩大预算与真实恢复验证](collab/20261104_edge_v4_extended_resume_codex.md) · [启动回执](../edge_formal_gate_resume_v4_20261104/STARTUP_READBACK.json) · [实时进度](http://127.0.0.1:18797/)。尚不能宣称实际恢复或完整工程门已通过。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---
# 当前状态

更新：2026-11-04（用户时区America/Los_Angeles）。固定五项，历史另存。

1. **唯一方法**：C5（p=3）冻结；正式外部效果尚未确认，正式评价未授权。
2. **工程门已验收PASS**：181905调度COMPLETED/0:0，用时44分17秒；1CPU、整树内存采样峰值6.49GiB，临时目录清理成功。
3. **恢复已证实**：181902真实大检查点恢复及78端点预检PASS（13分31秒）；181905从2877608帧补算338124帧到UDP EOF，旧有效计算成功复用。
4. **验收范围**：三角色64124快照齐全、73形状编码探针、编码中断恢复15文件字节一致、源已存CAL判定一致、合成距离通过；不等于全部64124行编码或正式外部质量评价。
5. **最新证据/下一步**：[验收记录](collab/20261104_edge_181905_final_acceptance_codex.md) · [复核回执](../edge_formal_gate_resume_v4_20261104/VERIFIED_ACCEPTANCE.json) · [已结束进度页](http://127.0.0.1:18797/)。46文件及归档SHA复核；下一步按实测准备正式编码/评价执行卡，尚不提交。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---
# 当前状态

更新：2026-11-04（America/Los_Angeles）。固定五项，历史另存。

1. **唯一方法**：C5 p=3 冻结；用户已直接授权正式外部评价，尚无正式效果结论，不训练、不按分数选样。
2. **工程门已验收**：181905 PASS，44分17秒；三角色64,124完整快照、73形状探针、实际编码恢复及源CAL一致性通过，峰值6.49GiB。
3. **本轮已启动**：真实预检181930 RUNNING；通过后自动提交一次正式评价，1CPU/8GiB/24小时上限，预检30分钟。
4. **评价与进度**：完整编码64,124条、评价60,000查询；RAW/C5 p3/p1/kNN5及四head全部报告。编码基准约4.62小时，另加核验/距离/汇总。[进度页](http://127.0.0.1:18798/)。
5. **最新证据/下一步**：[正式交付记录](collab/20261104_edge_formal_evaluation_launch_codex.md) · [执行卡](../edge_formal_evaluation_v1_20261104/ENGINEERING_CARD.json)。普通pipeline自动验收/提交/取回；无已知故障时结束AI轮次，用户再问再检查。保持本机及现有SSH通道运行。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-04（America/Los_Angeles）。固定五项，历史另存。

1. **唯一方法**：C5 p=3冻结；正式评价已授权，当前尚无已验收效果结论，固定各角色20k查询不变。
2. **最新故障**：181931运行5小时41分后因磁盘扫描与编码目录原子改名竞态FAILED；非超时/内存不足，已完成编码保留超算。
3. **修复重交**：用户授权“修复后重交”；新预检182071已提交，含真实改名回归与旧编码验真，PASS后自动提交1CPU/8GiB/24小时正式续跑。
4. **存储/进度**：大产物留超算，直接核验复用；本地仅重要结果、回执、清单和必要日志。[新进度页](http://127.0.0.1:18799/)。不宣称旧有效计算全部浪费。
5. **最新证据/下一步**：[修复交接](collab/20261104_edge_formal_monitor_race_resume_codex.md) · [修复执行卡](../edge_formal_evaluation_resume_v2_20261104/ENGINEERING_CARD.json)。7项本地测试通过，实际Linux预检以回执为准；普通pipeline自动推进，AI不持续监控。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-04（America/Los_Angeles）。固定五项，历史另存。

1. **唯一方法**：C5 p=3保持冻结，外部固定NORMAL/HTTP/UDP各20k评价已完成，不据结果改参数或挑选候选。
2. **工程验收**：预检182071、正式182089均PASS；182089 COMPLETED/0:0、1小时53分、1CPU/8GiB，复用42,428条旧编码，完整64,124条编码/60,000查询。
3. **效果结论**：ensemble样本误报84.03%→0.475%，HTTP关联召回66.33%→31.195%；p3及p1全部种子/ensemble安全门FAIL，UDP所有方法均0。
4. **存储/证据**：大数组和完整快照留超算；本地重要结果已核验。[结果交接](collab/20261104_edge_182089_formal_results_codex.md) · [验收](../edge_formal_evaluation_resume_v2_20261104/VERIFIED_ACCEPTANCE.json) · [结果页](http://127.0.0.1:18799/)。
5. **下一步**：只读诊断UDP基线盲区与HTTP PSH_ACK撤警，区分工程PASS与科学安全FAIL；尚未提交新实验，未新增独立审查。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-04（America/Los_Angeles）。固定五项，历史另存。

1. **冻结/效果**：C5 p3不变；Edge正式评价182089工程PASS，p3/p1所有头安全门FAIL，UDP各方法均0。
2. **三层诊断**：182245 COMPLETED/0:0，3分19秒、1CPU/8GiB；A/B全池及Edge 60,000查询的资产、对齐、判决和汇总核验PASS。
3. **主要原因**：Edge UDP已存输入20k同指纹、单包上下文；HTTP RAW样本AUROC 0.225，C5又撤警7,027条。A的多包UDP及B全SYN攻击覆盖未暴露这些问题。
4. **证据/存储**：大快照与数组留超算；[三层报告](collab/20261104_ab_edge_three_layer_diagnosis_codex.md) · [验收与SHA](../ab_edge_diagnosis_v1_20261104/FINAL_ACCEPTANCE.json) · [结果页](http://127.0.0.1:18801/)。
5. **下一步/边界**：建议独立小切片核对UDP原包→快照，排除合法上下文漏保留后再决定新方法；本轮未重解码/编码/训练/调参，未新增小anti审查。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-04（America/Los_Angeles）。固定五项，历史另存。

1. **冻结/效果**：C5 p3不变；Edge正式评价182089工程PASS，p3/p1安全门FAIL，UDP各方法均0。
2. **实际模型验收**：182266预检PASS；182267 COMPLETED/0:0、2分39秒、1CPU/8GiB。19条A/B/Edge真实前向E3误差0，分数误差≤0.00001145，所有头/集成判决一致。
3. **原包/权重证据**：337个权重名称含11个共享别名逐项一致；UDP 20k均为连接首包且q14一致，HTTP五层独立重建输入哈希全部匹配；两路特征实际参与。
4. **证据/存储**：大快照与数组留超算；[模型验收报告](collab/20261104_input_model_execution_acceptance_codex.md) · [验收与SHA](../input_model_forensics_v2_20261104/FINAL_ACCEPTANCE.json) · [结果页](http://127.0.0.1:18803/)。182263为审计器共享权重假设停止，v1保留。
5. **下一步/边界**：核验范围未发现模型替换、漏接或提取错误；尚未因果分离表示设计与分类头泛化。建议预登记诊断消融，未启动新方法、训练或调阈值，未新增小anti审查。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-04（America/Los_Angeles）。固定五项，历史另存。

1. **冻结/效果**：C5 p3 不变；Edge 正式评价 182089 工程 PASS、科学安全门 FAIL，UDP 各方法均 0。
2. **已验收诊断**：182266/182267 模型审计 PASS；19 条实际 E3 误差 0、头误差≤0.00001145，337 个权重名称一致；UDP 20k 首包与 HTTP 五层原包重建均核对通过。
3. **当前执行**：用户已授权单包消融和跨连接统计；真实 Linux 预检 182279 PASS（1分10秒），完整作业 182280 运行中：200 条配对消融及 Edge 60k 查询，1 CPU/8 GiB，15+105 分钟预算。
4. **证据/进度**：[执行方案](../context_separability_v1_20261104/README.md) · [冻结设计](../context_separability_v1_20261104/PLAN.json) · [实时进度](http://127.0.0.1:18804/)。大数组/逐条结果留超算，仅回收摘要与 SHA。
5. **下一步/边界**：完成后验收并选择修复方向；当前不训练、不调阈值、不宣称已修好。Edge 已用于诊断；用户计划下周写论文，先把机制证据做扎实。未新增小anti审查。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **冻结/效果**：C5 p3 不变；Edge 正式评价工程 PASS、科学安全门 FAIL。尚未训练或验收修复模型。
2. **诊断验收**：182279 预检 PASS；182280 COMPLETED/0:0、21分09秒、1CPU/8GiB。200条配对消融、Edge 60k跨连接统计通过，原始E3误差0，72个真实窗口暴力核对一致。
3. **关键结论**：A UDP攻击截单包仍64/64检出，不能以更长连接历史解释该切片优势；Edge 1s包速率AUROC：UDP 0.999986、HTTP 0.999214，仅为描述性可分性。
4. **证据/存储**：[验收报告与修复建议](collab/20261105_context_separability_acceptance_codex.md) · [验收/SHA](../context_separability_v1_20261104/FINAL_ACCEPTANCE.json)。大数组与逐条结果留超算，本地仅摘要。
5. **下一步/边界**：优先验证设备×协议因果8维统计；建议782/8/790维受控比较，先RAW再检查C5撤警。Edge已消费为诊断；新训练尚未启动，未新增小anti复核。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-05 流式资源门启动前入口快照

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **冻结/效果**：C5 p3 不变；Edge 正式评价工程 PASS、科学安全门 FAIL。尚未训练或验收修复模型。
2. **诊断验收**：182279 预检 PASS；182280 COMPLETED/0:0、21分09秒、1CPU/8GiB。200条配对消融、Edge 60k跨连接统计通过，原始E3误差0，72个真实窗口暴力核对一致。
3. **关键结论**：A UDP攻击截单包仍64/64检出，不能以更长连接历史解释该切片优势；Edge 1s包速率AUROC：UDP 0.999986、HTTP 0.999214，仅为描述性可分性。
4. **证据/存储**：[验收报告与修复建议](collab/20261105_context_separability_acceptance_codex.md) · [验收/SHA](../context_separability_v1_20261104/FINAL_ACCEPTANCE.json)。大数组与逐条结果留超算，本地仅摘要。
5. **评审/下一步**：已收到小anti文档评审；[核对回复](collab/20261105_anti_context_review_reply_codex.md)及[设计草案](collab/20261105_device_context_repair_design_draft_codex.md)已写。保留当前包因果语义，增加同配方782重训对照；在线时钟/资源/验收门待封存，未训练。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-05 流式门验收前入口快照

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **冻结/效果**：原 C5 p3 不变；Edge 工程 PASS、科学安全门 FAIL，尚无修复模型训练结果。
2. **诊断结论**：A UDP 截单包仍 64/64 检出；Edge 设备跨连接速率可分，但不是修复后召回或独立泛化证明。
3. **当前执行**：设备 D1 流式门已交付；182314 预检 COMPLETED/0:0、20秒，182315 完整资源门已运行。1CPU/8GiB，5+25分钟上限，无自动重试或训练提交。
4. **证据/进度**：[执行说明](collab/20261105_device_context_stream_gate_codex.md) · [计划](../device_context_stream_gate_v1_20261105/VALIDATION_PLAN.json) · [进度](http://127.0.0.1:18805/)。大文件/检查点留超算，本地仅摘要/SHA。
5. **封存/下一步**：全部门通过后自动写 TRAINING_SPEC_FROZEN / TRAINING_FREEZE_RECEIPT，本地 ARTIFACT_ACCEPTANCE 再验；此前仅候选规格。下一步为源原包/设备映射、完整特征 UID 与真实训练运行时准入，未训练。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-05 源域特征构建启动前入口快照

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **冻结/效果**：原 C5 p3 不变；Edge 既有科学安全门 FAIL，尚无修复模型训练或检测性能结果。
2. **最新验收**：流式预检 182314/完整门 182315 均 COMPLETED/0:0，20秒/2分7秒；112个真实查询及83个恢复查询零差异，FINAL_ACCEPTANCE=PASS。
3. **资源/限制**：1CPU/8GiB；UDP解码+统计8.44万帧/秒，压力流12.77万事件/秒、267.7MiB；NORMAL逻辑时钟最大超前854.643ms，须披露，112端点D0/D1相同不等于全局等价。
4. **封存/证据**：[训练规格](../device_context_stream_gate_v1_20261105/TRAINING_SPEC_FROZEN.json) · [最终验收](../device_context_stream_gate_v1_20261105/FINAL_ACCEPTANCE.json) · [报告](collab/20261105_device_context_stream_gate_codex.md) · [进度](http://127.0.0.1:18805/)。大工件留超算。
5. **下一步**：源原包/设备映射/完整特征UID及权重准入，真实训练与校准小切片；之后按OLD782/REFIT782/STATS8/FUSION790封存对照训练。每个新头计划1CPU/8GiB/30分钟，实际训练尚未提交。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **方法/授权**：D1训练规格已封存；用户“可以”已授权源域核对→完整特征→真实训练门→四组对照及评价，无需重复询问。当前尚无新训练或检出结果。
2. **最新门**：v2准入182330/真实特征预检182331均COMPLETED/0:0，54秒/24秒；231项资产SHA通过，1,094,929查询及原FIT/CAL身份/权重一致，57个真实窗口/42个恢复查询通过。
3. **运行中**：完整特征构建182332，1CPU/8GiB/30分钟上限；普通程序显示/取回。自动链止于SOURCE_FEATURES_READY，后续真实训练/校准门尚未执行，九个新头未提交。
4. **证据/修复**：[报告](collab/20261105_device_context_source_admission_codex.md) · [阶段回执](../device_context_training_v2_20261105/PREPARATION_GATE_RECEIPT.json) · [进度](http://127.0.0.1:18806/)。v1的182321因共享抓包null owner假设失败42秒，已独立v2按设备名册修复并补验PCAPNG。
5. **接续/存储**：大原包/特征/检查点留超算v2同名目录，本地只小回执。验收全量行覆盖/UID/恢复/资源后，按原授权做真实训练门；每新头1CPU/8GiB/30分钟，仍须A/B防退化及Edge诊断评价。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **方法/授权**：D1 训练规格已封存；用户已授权源域核对→完整特征→真实训练门→四组对照及评价，无需重复询问。
2. **最新验收**：完整源特征 182332 已验收 PASS，12分07秒、峰值约212 MiB；200份捕获/39,075,313帧/1,094,929行，581,590个恢复查询一致。
3. **当前状态**：源特征自动链已完成；真实训练/校准/预算门待执行，新训练作业0。尚无新模型检出成绩。
4. **证据/进度**：[验收报告](collab/20261105_device_context_source_features_acceptance_codex.md) · [机器回执](../device_context_training_v2_20261105/FINAL_ACCEPTANCE.json) · [进度页](http://127.0.0.1:18806/)。源码及回执须备份。
5. **接续/存储**：按已有授权实现真实训练门，通过后顺序运行三个新组×三个种子，保留OLD782锚点及A/B防退化、Edge诊断。大原包/特征/检查点留超算v2目录，每新头1CPU/8GiB/30分钟，须先实测预算。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **授权/规格**：用户已授权真实训练/校准/耗时门通过后自动对照训练；规格501aea9c…不变，原编码器冻结，不需再问许可。
2. **已验收**：源特征182332通过，1,094,929行8维；本地训练适配与父实现一致性通过，不能替代Linux预检。
3. **运行中**：真实预检182342，1CPU/8GiB/30分钟；通过后九头串行，各40轮/96,560更新、30分钟上限，随后集成CAL校准。当前不得称正式头已提交。
4. **证据/进度**：[交付报告](collab/20261105_device_context_training_dispatch_codex.md) · [启动回执](../device_context_head_training_v1_20261105/STARTUP_RECEIPT.json) · [右侧进度](http://127.0.0.1:18806/)。普通程序运行，无需AI守候。
5. **接续/存储**：自动链止于训练与源校准验收；之后按已有授权接续OLD782锚点、A/B防退化、C5及Edge诊断评价。全部大工件留超算head_training_v1同名目录，本地仅小回执/SHA；失败STOP，不自动重投。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **授权/方法**：已授权真实训练/校准/耗时门后自动对照；训练规格501aea9c…方法不变。用户先前明确允许不足时增时，独立资源v2正式每头改60分钟，仍1CPU/8GiB/40轮。
2. **前置/旧STOP**：源特征182332通过；v1预检182342完成Linux一致性及9个真实小训练/校准，在30分钟预算门STOP（最大预测39.93分钟），正式头0。
3. **当前运行**：v2真实预检182344，1CPU/8GiB/30分钟；全部门及≤60分钟预测通过后自动串行九头，再集成CAL校准。尚未声明v2预检通过。
4. **证据/进度**：[资源修订](collab/20261105_device_context_training_resource_v2_codex.md) · [启动回执](../device_context_head_training_v2_20261105/STARTUP_RECEIPT.json) · [进度页](http://127.0.0.1:18806/)。普通程序运行，禁止AI守候。
5. **接续/存储**：自动链止于训练与源校准验收；随后按已有授权做OLD782锚点、A/B防退化、C5及Edge诊断。大数组/模型留超算head_training_v2同名目录，小回执取回；失败STOP无自动重投。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **授权/方法**：已授权真实训练/校准/耗时门后自动对照；训练规格501aea9c…方法不变。用户先前明确允许不足时增时，独立资源v2正式每头改60分钟，仍1CPU/8GiB/40轮。
2. **前置/旧STOP**：源特征182332通过；v1预检182342完成Linux一致性及9个真实小训练/校准，在30分钟预算门STOP（最大预测39.93分钟），正式头0。
3. **当前运行**：v2真实预检182344已通过（2分45秒、9个128批训练及种子/集成校准）；首个正式REFIT782/27作业182345运行中。后续自动串行九头及集成CAL校准。
4. **证据/进度**：[资源修订](collab/20261105_device_context_training_resource_v2_codex.md) · [真实门验收](../device_context_head_training_v2_20261105/REAL_GATE_ACCEPTANCE.json) · [进度页](http://127.0.0.1:18806/)。普通程序运行，禁止AI守候。
5. **接续/存储**：自动链止于训练与源校准验收；随后按已有授权做OLD782锚点、A/B防退化、C5及Edge诊断。大数组/模型留超算head_training_v2同名目录，小回执取回；失败STOP无自动重投。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **已验收**：head_training_v2九头与源CAL校准PASS；各40轮/96,560更新，总869,040。九头累计94分54秒，最大内存约3.22GiB，校准182392用时22秒。
2. **当前结果**：集成源CAL加权FPR：REFIT782 0.974305%、STATS8 0.977863%、FUSION790 0.999757%；这是校准成绩，A/B与Edge新检出结果尚无。
3. **方法/复现**：冻结768编码器，原FIT/CAL/权重不变；8维仅FIT归一化。REFIT782三种子阈值/尺度及集成阈值与原记录精确一致，不声称逐参数全部一致。
4. **证据/进度**：[验收报告](collab/20261105_device_context_training_acceptance_codex.md) · [复核回执](../device_context_head_training_v2_20261105/COMPLETION_AUDIT.json) · [进度页](http://127.0.0.1:18806/)。九头和校准均结束，当前无训练作业运行。
5. **接续/存储**：按已有授权做OLD782锚点与三新组A/B防退化、C5安全性/裕量及Edge诊断（STATS8只RAW）；评价尚未提交。模型/分数/数组留超算head_training_v2同名目录，仅小回执/SHA回本地。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **已验收**：head_training_v2 九头与源 CAL 校准 PASS；总 869,040 次更新。训练累计 94分54秒，最大约 3.22 GiB。
2. **当前运行**：用户“允许运行。”后，evaluation_v1 真实预检 182427 已运行；自动顺序为 PREFLIGHT → CONTEXT → AB → EDGE。当前未宣称真实门或效果通过。
3. **冻结口径**：OLD782 与 REFIT782/STATS8/FUSION790，三种子及集成；源阈值/尺度固定。STATS8 只 RAW，其余 RAW/C5。报告全部注册组，科学 FAIL 不筛选或调参。
4. **证据/进度**：[启动回执](collab/20261105_device_context_evaluation_launch_codex.md) · [进度页](http://127.0.0.1:18806/)。1 CPU/8 GiB 顺序运行；预检/统计各30分钟，A/B/Edge各60分钟上限。
5. **接续/存储**：完成后先核验执行完整性，再解读 A/B 防退化、Edge RAW/C5 与裕量。模型/数组/分数留超算同名目录，小汇总/SHA 自动回本地；Edge 是已消耗诊断集。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **工程完成**：evaluation_v1 四阶段182427/182429/182430/182431全部PASS；总10分35秒，峰值1.662GiB。112行重编码、合法参考距离误差0；旧头全量评分复现。
2. **检出改善**：Edge集成固定样本，融合C5的UDP 0→98.66%，HTTP 31.195%→94.995%；OLD与REFIT所有已报告指标一致。
3. **科学未过门**：Edge融合C5正常FPR0.475%→5.79%；三种子0.735%/25.235%/0.255%，不可择优。HTTP仍撤警967条，设备级C5安全门失败；A/B RAW正常误报退化，源CAL通过。
4. **证据/口径**：[验收报告](collab/20261105_device_context_evaluation_acceptance_codex.md) · [复核回执](../device_context_evaluation_v1_20261105/COMPLETION_AUDIT.json)。A/B融合C5仍较好，不能将RAW与C5混报；全部组/种子保留，Edge为已消耗诊断集。
5. **下一步/存储**：先用已有超算工件归因正常误报、种子127失稳及尺度/分数变化，再定源域约束修复；本轮无新训练。大模型/数组/分数留超算，小汇总/SHA/裕量图已本地封存。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **已知结果**：四组评价工程通过，融合C5 Edge样本UDP98.66%、HTTP94.995%、正常FPR5.79%；A/B RAW误报退化和Edge C5安全门失败，不能宣称修复完成。
2. **当前任务**：用户要求检查768维隐式特征是否真正使用，同时排查误报与种子127失稳。representation_usage_diagnosis_v2 预检 182478，当前 PREFLIGHT_RUNNING，通过后自动完整诊断。
3. **方法**：冻结四组/三种子/集成；输入拼接、分块零参考消融/Shapley、同协议UID置换、分数×阈值×尺度对照、正常误报分组。无训练、无阈值拟合、无择优。
4. **工程证据**：v1作业182469因远端缺少本地生成验收回执4秒失败，有效计算0秒；v2随包交付回执修复。见 [执行回执](collab/20261105_representation_usage_diagnosis_launch_codex.md)。1CPU/8GiB，预检30分钟、完整诊断2小时上限。
5. **接续/存储**：先确认真实预检与完整诊断，再区分“正确输入”“有功能依赖”“帮助分类”；零化/置换可能离分布。大数组/模型留超算，小摘要自动回本地；[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **诊断完成**：v2预检182478/完整182486均PASS，总11分22秒、峰值3.0805GiB；全模型分数复算误差0，分块数值误差未改变判定。
2. **768维结论**：正确输入且A/B判别依赖显著；旧头E3置换使A/B RAW样本攻击召回约100%降至75.18%/77.16%。Edge UDP仅1种tokenized输入，隐式表示近乎常量；融合8维归零后UDP检出98.66%→0。
3. **误报归因**：127新阈值更低、C5上限缩小，加上正常分数结构变化放大误报。固定融合分数：旧阈值/旧尺度17条，新阈值/旧尺度67条，旧阈值/新尺度1258条，新/新5047条。是诊断对照，不是可部署工作点。
4. **仍未解决**：只改旧尺度会让HTTP集成检出94.995%→88.31%；训练为何学出127边界尚未严格归因。继续保留科学失败，不挑种子、不凭外部成绩调参。见 [验收报告](collab/20261105_representation_usage_diagnosis_acceptance_codex.md)。
5. **下一步/存储**：围绕保留原正常分数结构、源域约束的上下文修正和C5尺度兼容性设计修复；可复用训练诊断追根因。本轮无新训练。大数组/模型留超算，小摘要/图表/SHA已本地封存。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **当前运行**：源域分数锚定v1真实Linux预检182502（1CPU/8GiB/30分钟）。通过全链路和真实训练/耗时门后自动串行27/127/227三头各40轮，再源CAL；目前未宣称真实门或效果通过。
2. **用户取舍**：接受此前已展示的A/B小幅退化，继续修复正常误报和种子稳定性；旧FAIL不改写，Edge误报5.79%、127误报25.235%及HTTP撤警仍待解决。
3. **训练日志**：9头869,040更新、360轮、1,080探针核验通过。源损失饱和及尾梯度弱非127独有；缺少旧逐轮模型/分数，不能确定正常漂移起点或唯一训练根因。
4. **固定修复**：保留790维/冻结编码器，原BCE＋TAIL加系数1的源FIT教师分数锚定，同种子冻结REFIT782作教师；源CAL、C5公式不变。固定40轮，新增逐轮模型与源探针；所有种子统一评价，不凭Edge调参。
5. **交接/存储**：见[执行卡](collab/20261105_fusion_score_anchor_launch_codex.md)及`runs/fusion_score_anchor_v1_20261105/CHAIN_STATE.json`。大文件留超算，小回执自动取回；[进度](http://127.0.0.1:18806/)。Edge已消费，只能作为诊断评价。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **当前运行**：源域分数锚定v2真实Linux预检182507（1CPU/8GiB/30分钟）。v1线程重复初始化失败已封存；v2通过全链路和真实训练/耗时门后自动串行27/127/227三头各40轮，再源CAL；目前未宣称真实门或效果通过。
2. **用户取舍**：接受此前已展示的A/B小幅退化，继续修复正常误报和种子稳定性；旧FAIL不改写，Edge误报5.79%、127误报25.235%及HTTP撤警仍待解决。
3. **训练日志**：9头869,040更新、360轮、1,080探针核验通过。源损失饱和及尾梯度弱非127独有；缺少旧逐轮模型/分数，不能确定正常漂移起点或唯一训练根因。
4. **固定修复**：保留790维/冻结编码器，原BCE＋TAIL加系数1的源FIT教师分数锚定，同种子冻结REFIT782作教师；源CAL、C5公式不变。固定40轮，新增逐轮模型与源探针；所有种子统一评价，不凭Edge调参。
5. **交接/存储**：见[执行卡](collab/20261105_fusion_score_anchor_runtime_v2_codex.md)及`runs/fusion_score_anchor_v2_20261105/CHAIN_STATE.json`。大文件留超算，小回执自动取回；[进度](http://127.0.0.1:18806/)。Edge已消费，只能作为诊断评价。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **当前运行**：v2真实全链路182507已PASS（5:04、112行/7批、编码和距离误差0）；182509真实训练/校准/耗时预检运行。门通过自动三种子40轮＋源CAL，当前尚无新效果结论。
2. **用户取舍**：接受此前已展示的A/B小幅退化，继续修复正常误报和种子稳定性；旧FAIL不改写，Edge误报5.79%、127误报25.235%及HTTP撤警仍待解决。
3. **训练日志**：9头869,040更新、360轮、1,080探针核验通过。源损失饱和及尾梯度弱非127独有；缺少旧逐轮模型/分数，不能确定正常漂移起点或唯一训练根因。
4. **固定修复**：保留790维/冻结编码器，原BCE＋TAIL加系数1的源FIT教师分数锚定，同种子冻结REFIT782作教师；源CAL、C5公式不变。固定40轮，新增逐轮模型与源探针；所有种子统一评价，不凭Edge调参。
5. **交接/存储**：见[执行卡](collab/20261105_fusion_score_anchor_runtime_v2_codex.md)及`runs/fusion_score_anchor_v2_20261105/CHAIN_STATE.json`。大文件留超算，小回执自动取回；[进度](http://127.0.0.1:18806/)。Edge已消费，只能作为诊断评价。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **当前完成**：源分数锚定v2三个头各40轮/96,560更新，源CAL集成182521完成；六阶段COMPLETED/0:0。正式训练44:48，成功链51:52，峰值3.307GiB。本轮无新评价作业。
2. **已验证变化**：27/127/227的FIT尺度相对旧头偏差+0.472%/+0.059%/−0.249%；127阈值从前版−23.315回到−20.400（旧−19.737）。只说明源尺度/阈值变化，不证明域外稳定。
3. **验收边界**：源CAL集成加权正常误报0.9788%，目标≤1%已满足；A/B/Edge本版成绩尚未产生，UDP收益、HTTP撤警和127误报仍待评价。源CAL达标不是泛化证据。
4. **固定下一步**：使用三个固定40轮端点、源CAL阈值、自身FIT尺度，统一评价A/B/Edge三种子和集成、RAW/C5；复用原四组对照。不凭Edge挑头/调参，保留用户接受的旧A/B取舍和旧FAIL。
5. **交接/存储**：见[训练验收](collab/20261105_fusion_score_anchor_training_acceptance_codex.md)与`runs/fusion_score_anchor_v2_20261105/FINAL_TRAINING_ACCEPTANCE.json`；120份逐轮头与所有大数组留超算，小回执和SHA本地封存。Edge已消费，仍属诊断评价。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **当前运行**：固定五组A/B/Edge评价真实预检182554运行，1CPU/8GiB；通过后自动AB→EDGE。未宣称预检或新效果通过。
2. **固定模型**：ANCHOR790三种子27/127/227第40轮端点、源CAL阈值、自身FIT尺度全部固定；编码器/归一化/因果8维/C5规则不变。无训练、无选头或调参。
3. **完整对照**：OLD782、REFIT782、STATS8、前版FUSION790、新ANCHOR790；三种子及集成，RAW/C5（STATS8仅RAW）。原四组须复算分数/判定与封存数组一致。
4. **验收重点**：正常误报、127稳定性、UDP检出、HTTP撤警/裕量；保留原A/B分母/权重与全部科学门。已接受旧A/B取舍，仍不自动放宽新结果；Edge为已消费诊断评价。
5. **交接/存储**：见[评价执行卡](collab/20261105_fusion_anchor_evaluation_launch_codex.md)及`runs/fusion_anchor_evaluation_v1_20261105/CHAIN_STATE.json`；工程失败停止，科学失败继续报告。大数组留超算、小结果自动取回，[实时进度](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **本轮结束**：182554/182555/182556全部COMPLETED/0:0；真实预检及A/B/Edge工程PASS，科学FAIL；累计5:01，峰值1.691GiB，无新作业。
2. **关键结果**：新ANCHOR790集成Edge C5正常误报5.79%→0.58%，但UDP98.66%→0%，HTTP94.995%→46.51%；127误报5047→116，收益未保住。
3. **定位边界**：UDP在RAW已全低于阈值、C5扣分0；HTTP裕量缩小并撤警6467条。旧四组全量判定复现，新头身份通过；支持锚定牺牲收益的假设，尚未证明8维贡献机制。
4. **保留与下一步**：不采用ANCHOR790替代；保留原FUSION790/OLD782。建议现有头8维贡献干预＋源FIT梯度冲突诊断，再定新目标，不直接调λ或挑种子/轮次。原A/B门和Edge安全门FAIL保留。
5. **证据与存储**：[验收报告](collab/20261105_fusion_anchor_evaluation_acceptance_codex.md)，`runs/fusion_anchor_evaluation_v1_20261105/FINAL_EVALUATION_ACCEPTANCE.json`；全五组/全部种子有据，大数组留超算，[进度/验收页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


---

# 当前状态

更新：2026-11-05（America/Los_Angeles）。固定五项，历史另存。

1. **当前运行**：8维贡献/锚定冲突诊断真实预检182560运行；通过且梯度预算门通过后自动CONTRIBUTION→GRADIENT。1CPU/8GiB，总计算上限2小时，无重试。
2. **输入干预**：A/B/Edge固定查询，FUSION790与ANCHOR790三个第40轮头及集成；真实8维、归一化置零、同设备同协议内两次固定置换，不改阈值。
3. **目标诊断**：仅源FIT，固定64×256查询与原TAIL采样；拆开正常/攻击BCE、TAIL和锚定。原融合40轮与锚定0/1/5/10/20/40轮共21点，不更新参数、不选轮次。
4. **结论边界**：本轮尚无机制结论。上轮锚定误报降低但UDP归零，科学FAIL保留；梯度近零不解释夹角，干预率不作部署成绩，源诊断不重建Adam历史。
5. **证据与存储**：[执行卡](collab/20261105_context_anchor_diagnosis_launch_codex.md)，`runs/context_anchor_diagnosis_v1_20261105/CHAIN_STATE.json`；大数组/逐批明细留超算，小汇总自动取回，[实时进度](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-06 before source risk preservation pilot

# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **诊断完成**：182560/182561/182562均COMPLETED/0:0，累计3:14；1CPU/8GiB，进程采样峰值1.684GiB。诊断验收PASS，原锚定模型科学FAIL保留，无新作业。
2. **8维确实使用**：Edge UDP原融合8维贡献中位数+5.91，置零召回98.66%→0；锚定贡献仅+0.64，置零基底裕量−1.45→−18.13，真实裕量−17.49。
3. **目标机制**：第1轮三个种子全参数/8列平均梯度均冲突；末轮8列锚定/分类梯度比1.23e5—3.47e6，完整日志锚定占loss>99.99%。非全程反向，未重放Adam，127不是唯一问题。
4. **下一方向**：保留原FUSION790，撤销全样本模仿弱782教师具体分数；先设计源域正常风险＋攻击裕量保护小试，核对硬负例覆盖。具体新目标未封存、未训练，不能直接减λ或只锚正常。
5. **证据/存储**：[验收报告](collab/20261106_context_anchor_diagnosis_acceptance_codex.md)，`runs/context_anchor_diagnosis_v1_20261105/FINAL_DIAGNOSIS_ACCEPTANCE.json`；1408项干预检查通过，大数组/逐批明细留超算，[验收页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-06 before source pilot real gate acceptance

# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **源域小试已启动**：v2；作业182577, 182578，当前TRAIN_PREFLIGHT_RUNNING。1CPU/8GiB，三阶段总预算2小时；尚未科学验收。
2. **固定方法**：原融合790起步，正常高分尾部风险＋攻击分数单侧保护＋正向8维贡献保护；冻结编码器、归一化及原阈值。每种子16,384行、5轮/320更新，27/127/227全报。
3. **自动门**：真实编码距离评价→三种子各8批训练/保存重读/源评价/预算→固定小试。45项远端依赖提交前PASS；失败停止，不自动全量训练或外部评价。
4. **失败与修复**：v1作业182576在3秒内因误列本地验收脚本失败，训练0。v2使用已交付依赖清单并提前核验；方法与worker字节不变，负例回归PASS。
5. **证据/存储**：[设计卡](collab/20261106_source_risk_preservation_pilot_design_codex.md)、[启动回执](collab/20261106_source_risk_preservation_pilot_launch_codex.md)，`runs/source_risk_preservation_pilot_v2_20261106`；大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-06 before source pilot final acceptance

# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **源域小试运行中**：v2作业182579，取回时PILOT_RUNNING。真实门182577/182578已PASS；1CPU/8GiB，小试保守估计8.1分钟；尚未科学验收。
2. **固定方法**：原融合790起步，正常高分尾部风险＋攻击分数单侧保护＋正向8维贡献保护；冻结编码器、归一化及原阈值。每种子16,384行、5轮/320更新，27/127/227全报。
3. **真实门已通过**：原头全FIT/CAL分数精确复现，三种子各8批共24次真实更新，保存重读/评价/预算门PASS，峰值3.336GiB。自动小试运行，不自动扩展全量训练或外部评价。
4. **失败与修复**：v1作业182576在3秒内因误列本地验收脚本失败，训练0。v2使用已交付依赖清单并提前核验；方法与worker字节不变，负例回归PASS。
5. **证据/存储**：[设计卡](collab/20261106_source_risk_preservation_pilot_design_codex.md)、[启动回执](collab/20261106_source_risk_preservation_pilot_launch_codex.md)，`runs/source_risk_preservation_pilot_v2_20261106`；大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-06 before source coverage audit

# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **源域小试已验收**：182579完成2:32；三种子各320更新。工程PASS、科学NO_GO，原融合790仍保留，无新作业。
2. **误报下降但加权不足**：CAL集成普通294→161条、0.8870%→0.4857%；加权0.9998%→0.9507%，相对降4.91%未达10%。剩余加权误报87.53%来自SimCam。
3. **检出/8维总体保留**：源FIT/CAL全种子及集成攻击召回100%、撤警0；CAL正向8维贡献保留101.73%—101.89%。个别样本仍下降，不能归因于几乎未激活的LC项。
4. **未通过项/下一步**：全种子攻击分数p01下降略超0.01尺度门；集成CAL有1410条超限，尚未漏报。先查源FIT高权重正常分支覆盖和攻击尾部保护，不放宽门、不自动全量或外部评价。
5. **证据/边界**：[验收报告](collab/20261106_source_risk_preservation_pilot_acceptance_codex.md)、`runs/source_risk_preservation_pilot_v2_20261106/FINAL_PILOT_ACCEPTANCE.json`；仅源域固定阈值RAW，A/B/Edge和C5新效果未知。大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-06 before source coverage acceptance

# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **覆盖诊断已提交**：v1，作业182585，启动快照PREFLIGHT_RUNNING；1CPU/8GiB，预检30＋完整60分钟。尚未完成解释验收。
2. **回答的问题**：源FIT缺语义支持、实际小试遗漏/低覆盖，还是已覆盖仍有误报与攻击分数下降；先查原因，再改训练。
3. **固定对照/边界**：原每类8192行、同样本数层级加权抽样、均匀每类16384行；只由FIT构造成员。三种子及集成全报；训练更新0，CAL仅描述，不做新外部评价。
4. **前序小试结论**：源攻击召回100%、8维总体贡献保留；CAL加权误报仅相对降4.91%，攻击p01下降略超门，科学NO_GO。原融合790仍保留。
5. **证据/执行**：[设计卡](collab/20261106_source_coverage_audit_design_codex.md)、[启动回执](collab/20261106_source_coverage_audit_launch_codex.md)；52项远端依赖PASS，真实预检通过后自动诊断、失败停止。大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-06 before source stratified pilot

# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **覆盖诊断已验收**：182585预检5:13＋182586完整1:23，工程/诊断PASS，6648项摘要一致性断言通过；无新训练作业，原小试科学NO_GO不变。
2. **已有数据，抽样不足**：原小试遗漏35/94正常语义组、1/11攻击组；SimCam/Hydra有384条仅抽4条，当前282条超限仅2条被抽中。均维持攻击检出。
3. **等量改善抽样更有依据**：集成正常/攻击残余风险覆盖9.67%/0.34%→73.99%/65.83%；均匀加倍仅12.75%/1.27%。这是覆盖诊断，受原成员拟合影响，不是效果预测。
4. **仍有未解决部分/下一步**：CAL全部剩余误报组已有FIT及实际抽样支持；SimCam录制TCP的3条占剩余加权误报86.57%。先设计源分层/重要性抽样与权重校正，固定更新小对照；不能直接双重加权或保证消除误报。
5. **证据/边界**：[验收报告](collab/20261106_source_coverage_audit_acceptance_codex.md)、`runs/source_coverage_audit_v1_20261106/FINAL_COVERAGE_ACCEPTANCE.json`；CAL不选训练成员，无A/B/Edge/C5新成绩。大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-06 before source stratified pilot acceptance

# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **分层小试已启动**：作业182589, 182590，快照TRAIN_PREFLIGHT_RUNNING；1CPU/8GiB，30＋30＋60分钟总上限2小时，尚未科学验收。
2. **固定改动**：源FIT按设备/活动/协议配额，组内原权重有放回抽样，样本位损失权重Wg/ng；每类8192位，独立UID另报。三种子各5轮320更新，原损失/阈值/优化器保持。
3. **科学对照/门**：复用封存均匀小试固定第5轮；起点/上界/阈值核验。保持正常误报不增、攻击尾部/召回/8维贡献保护及集成CAL加权误报相对降10%的全部原门，不选种子轮次。
4. **自动工程门**：52项远端依赖PASS；本地10＋8＋4项回归PASS。真实旧工程→真实训练8批/保存重读/源评价/预算→小试；失败停止，不自动全量或外部评价。
5. **证据/边界**：[执行卡](collab/20261106_source_stratified_pilot_design_codex.md)、[启动回执](collab/20261106_source_stratified_pilot_launch_codex.md)；CAL仅开发核验，不参与选样本；大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-06 before source guarded pilot

# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **分层小试已验收**：182589/182590/182591累计5:22，三种子各320更新；工程PASS、科学NO_GO，原FUSION790保留，无新作业。
2. **误报继续降，权重门未过**：集成CAL普通161→137条、0.4857%→0.4133%；加权0.9507%→0.9466%，相对原头降5.32%未达10%。原3条SimCam录制TCP误报仍在，占剩余加权误报86.95%。
3. **攻击/8维**：源FIT/CAL召回100%、撤警0；集成CAL p01−0.010729→−0.009964通过，超限1410→1133条。27在FIT/未用FIT、127三个核验集仍失败；227全过。正向8维总贡献103.38%，个别低保留行7→13。
4. **覆盖/下一步**：全部94/11语义组覆盖；SimCam录制TCP不同训练行3→59/66，Hydra 4→320/384。41个有效梯度探针均冲突。固定采样，设计源域攻击尾部约束下的正常风险更新小对照；不盲目扩量、不按CAL挑样本或放宽门。
5. **证据/边界**：[验收报告](collab/20261106_source_stratified_pilot_acceptance_codex.md)、`runs/source_stratified_pilot_v1_20261106/FINAL_PILOT_ACCEPTANCE.json`；CAL仅开发核验，无A/B/Edge/C5新成绩。大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-06 before source guarded pilot acceptance

# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **受限更新小试已提交**：作业182592，快照DECODE_PREFLIGHT_RUNNING；1CPU/8GiB，30＋30＋60分钟总上限2小时，尚无新科学结论。
2. **固定算法**：分层样本/原损失保持；每轮64批后全FIT保护验收，lr倍率1/0.5/0.25/0.125，失败恢复模型/Adam/RNG，全部拒绝则回退。三种子固定5轮保留端点。
3. **角色/成本变化**：全部FIT参与更新判断；未抽中梯度FIT不是验证集。每头名义320步、实际最多1280步、保留≤320步分别记账。CAL不决定更新，原科学门不放宽。
4. **自动门**：61项远端依赖及本地29项回归PASS；真实工程→真实源提案/全源检查/强制拒绝恢复/最坏预算→小试。失败或无可行进展停止，不自动扩量或外部评价。
5. **证据/存储**：[执行卡](collab/20261106_source_guarded_pilot_design_codex.md)、[启动回执](collab/20261106_source_guarded_pilot_launch_codex.md)；前序分层小试仍NO_GO、原FUSION790保留，大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-06 before pilot transfer evaluation

# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **受限更新已验收：工程PASS、科学NO_GO**。182592/182593/182598累计11:53、峰值约3.37GiB；809项摘要/回执/保护记账检查通过。
2. **收益与代价**：集成CAL攻击召回100%，下降超限1133→735，8维总体贡献101.67%；普通误报137→177，加权0.9466%→0.9570%，相对原头下降4.28%未达10%。种子27 CAL攻击尾部仍失败。
3. **保护真实执行**：28次提案因攻击尾部拒绝；实际2432步、保留640步。227全步长接受且模型SHA与上轮一致。全部FIT参与优化反馈，不能充当独立验证。
4. **下一步方向**：原3条高权重正常误报仍占剩余加权误报约86%。先查源内对应表达与约束攻击尾部是否共享降分方向；不盲目缩步长/加轮次或放宽门。原FUSION790保留，本次无新训练/外部评价。
5. **证据/存储**：[验收报告](collab/20261106_source_guarded_pilot_acceptance_codex.md)及source_guarded_pilot_v1_20261106验收回执；大模型/数组留超算，[进度页](http://127.0.0.1:18806/)展示验收结果。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)


## 2026-11-06 before pilot transfer acceptance

# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **四组统一评价已提交**：作业182628，启动快照PREFLIGHT_RUNNING；真实预检→A/B→Edge，当前无最终新成绩。
2. **固定模型**：原FUSION790＋均匀/分层/受限三轮小试，三种子及集成全报；保持原阈值、尺度、输入与C5，不训练、不筛种子，旧源侧NO_GO保留。
3. **最终目标直观展示**：普通/加权FPR<2%、检出≥99.9%分列；Edge HTTP/UDP分别报告，HT单列。RAW与C5分别评价，保留原科学安全门。
4. **自动门与资源**：27项远端依赖、本地15项回归PASS；真实Linux门通过才完整评价。1CPU/8GiB、30＋45＋45分钟；工程失败停止，效果失败照报，不自动重试或训练。
5. **证据与存储**：[执行卡](collab/20261106_pilot_transfer_evaluation_design_codex.md)、[启动回执](collab/20261106_pilot_transfer_evaluation_launch_codex.md)；大文件留超算，[进度页](http://127.0.0.1:18806/)随数据集完成更新成绩。A/B/Edge均为开发泛化诊断。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
