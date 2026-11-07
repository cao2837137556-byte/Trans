# 同库历史参考＋三维C5：完整验收

结果：工程与全量一致性验收通过；完整历史参考＋C5_3D_OLD达到A/B主视图全部四头整体2%/99.9%门，并维持Edge改善，确认为有价值的零重训后处理候选。
影响：阶段目标成立，但全样本/逐设备/单种子与Edge双99.9%原目标尚未全部满足；不是新模型训练收益，也不是未触碰外部测试结论。
下一步：封存该候选及同库消融，先整理论文结果；将Edge RAW漏检、单种子稳定性和建档期表现作为独立剩余问题，不自动训练或部署。

## 1. 工程验收与证据

- 182658预检COMPLETED/0:0，4:02；182659完整对照COMPLETED/0:0，10:37；成功链14:39，1CPU/8GiB，采样峰值2.729GiB。完整阶段原保守预测25.28分钟，实测10.62分钟，未超预算。
- 本地验收5261项通过；源码/取回回执SHA一致。A179886、B148316、Edge60000，共388202查询，支持度按C2/C3/C4封存存储语义全行比较，排除0；最大支持差1.89e-15、最大分数差6.76e-14，四头判决差0。
- 真实预检A512/B960/Edge256行与原算法同批次全字段复核，供体UID和元数据精确一致；56条真实历史参考独立窗口核对通过。B四档均到bank_end_frame停止、HIST_DEV解码0；A三capture独立状态。真实编码112行/7批，E3误差0。
- v3/v4/v5预检失败分别245/183/186秒，合计614秒，另列工程排障；其中包含有效重放和核对，无可靠子阶段CPU拆分，不全部宣称浪费。v1/v2未分配作业。
- 原FUSION790头、所有种子、部署阈值、源半径及两组源尺度不变。OLD指封存旧782源尺度用于扣分，不表示替换为旧782分类模型。完整数组留超算，本地仅汇总/验收/SHA。

## 2. 主结果：集成头

A/B使用预先登记post_window_primary；Edge为全部所选正常/HTTP/UDP查询。普通FPR=正常告警数/正常查询数；检出率=攻击告警数/对应攻击查询数。分层加权使用原权重，不能与Edge HT混为同一分母。

|数据|方法|正常告警/正常行|普通FPR|分层加权FPR|普通攻击检出|分层加权攻击检出|
|---|---|---:|---:|---:|---|---|
|CIC_DEV|C5_FROZEN|22/96041|0.022907%|0.233716%|ATTACK: 99.993675%|ATTACK: 99.998731%|
|CIC_DEV|C5_3D_OLD|18/96041|0.018742%|0.002235%|ATTACK: 100.000000%|ATTACK: 100.000000%|
|UNSW_DEV|C5_FROZEN|1299/74444|1.744936%|0.560510%|ATTACK: 99.986217%|ATTACK: 99.991298%|
|UNSW_DEV|C5_3D_OLD|210/74444|0.282091%|0.286266%|ATTACK: 99.986217%|ATTACK: 99.991298%|
|EDGE|C5_FROZEN|1158/20000|5.790000%|9.332313%|HTTP: 94.995000%; UDP: 98.660000%|HTTP: 96.243810%; UDP: 98.660000%|
|EDGE|C5_3D_OLD|24/20000|0.120000%|1.220180%|HTTP: 99.790000%; UDP: 98.660000%|HTTP: 99.751165%; UDP: 98.660000%|

B主视图正常误报1299→210，净减少1089（83.8337%），攻击72543/72553保持。与前轮仅两小时参考的3D_OLD误报30.5894%相比，本轮完整历史库恢复至0.282091%。A主视图正常22→18，攻击79051→79056；Edge正常1158→24，HTTP18999→19958（净增959），UDP19732/20000保持。

Edge C5_3D_OLD的HT口径：正常FPR 0.017457%；HTTP检出 99.795250%；UDP 98.660000%。这些是按既定抽样扩展权重的点估计，不等于已实测线上告警率。

## 3. 2×2对照：三部分各自作用

|数据主视图|方法|普通正常FPR|加权正常FPR|普通攻击检出|
|---|---|---:|---:|---|
|CIC_DEV|C5_2D_FUSION|0.022907%|0.233716%|99.993675%|
|CIC_DEV|C5_2D_OLD|0.018742%|0.002235%|99.955728%|
|CIC_DEV|C5_3D_FUSION|0.026031%|0.401540%|100.000000%|
|CIC_DEV|C5_3D_OLD|0.018742%|0.002235%|100.000000%|
|UNSW_DEV|C5_2D_FUSION|1.744936%|0.560510%|99.986217%|
|UNSW_DEV|C5_2D_OLD|0.177314%|0.210230%|99.986217%|
|UNSW_DEV|C5_3D_FUSION|2.153296%|0.821222%|99.986217%|
|UNSW_DEV|C5_3D_OLD|0.282091%|0.286266%|99.986217%|
|EDGE|C5_2D_FUSION|5.790000%|9.332313%|94.995000%/98.660000%|
|EDGE|C5_2D_OLD|0.085000%|0.849810%|88.310000%/98.660000%|
|EDGE|C5_3D_FUSION|5.815000%|9.596863%|99.795000%/98.660000%|
|EDGE|C5_3D_OLD|0.120000%|1.220180%|99.790000%/98.660000%|

- 历史覆盖：去掉历史库时B二维本已严重退化；恢复完整历史库后，同库二维重新逐条复现旧C5，因此可把后续变化归因于三维与尺度。
- 旧源尺度：B同库二维1299→132正常误报；Edge1158→17，但Edge HTTP同时降到17662/20000（88.31%）。仅增强扣分不能兼顾检出。
- 三维保护：相同OLD尺度下，Edge HTTP17662→19958，增加2296条检出，仅增加7条正常误报；B正常132→210，攻击不变。三维交集削弱部分正常支持，但历史覆盖总体保住。
- 三维单独配当前尺度：B普通FPR2.153296%，Edge5.815%，不能单独宣称三维就解决误报。有效候选是完整历史参考、三维约束与旧源尺度的组合。
- 本轮没有重新训练；证据支持后处理机制改善，不能外推成新训练方法或编码器泛化能力提升的证明。

## 4. 历史供体支持留存（全视图正常）

分组依据原二维匹配的两个不同组件代表；3D仍遍历全部合法参考，可以改选支持者，因此原二维代表dc/rho>1不等于整条查询三维支持归零。

|池/原二维供体|正常行|二维正支持|三维正支持|归零|归零比例（原正支持）|任一原匹配dc/rho>1|该比例（有匹配）|支持比中位数|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|CIC_DEV/NO_TWO_LEGAL_MATCHES|6025|0|0|0|—|0|—|—|
|CIC_DEV/BOTH_DENSE|94491|94491|94399|92|0.097364%|665|0.703771%|1.000000|
|CIC_DEV/MIXED_DENSE_HIST|211|211|208|3|1.421801%|38|18.009479%|1.000000|
|CIC_DEV/BOTH_HIST|103|103|103|0|0.000000%|0|0.000000%|1.000000|
|UNSW_DEV/BOTH_HIST|41688|41683|41679|4|0.009596%|2849|6.834101%|0.914322|
|UNSW_DEV/BOTH_DENSE|24288|24288|24284|4|0.016469%|2029|8.353920%|0.995763|
|UNSW_DEV/NO_TWO_LEGAL_MATCHES|1319|0|0|0|—|0|—|—|
|UNSW_DEV/MIXED_DENSE_HIST|8468|8356|8355|1|0.011967%|393|4.641001%|1.000000|

B纯历史供体41683条原正支持中只有4条归零；混合供体8356条中1条归零。存在支持强度下降（纯历史支持比中位数0.914322），但没有大规模抹去历史覆盖。完整逐设备供体分账和六流程四头误报数保存在DIAGNOSE_RESULT。

## 5. 全视图与种子，必须同时披露

|数据|视图|头|普通FPR|加权FPR|普通攻击检出（Edge HTTP/UDP）|加权攻击检出|
|---|---|---|---:|---:|---|---|
|CIC_DEV|post_window_primary|27|0.015618%|0.001788%|99.996205%|99.998666%|
|CIC_DEV|post_window_primary|127|0.012495%|0.001440%|99.998735%|99.999715%|
|CIC_DEV|post_window_primary|227|0.040608%|0.005022%|100.000000%|100.000000%|
|CIC_DEV|post_window_primary|ensemble|0.018742%|0.002235%|100.000000%|100.000000%|
|CIC_DEV|full|27|0.396707%|5.033339%|99.996205%|99.998666%|
|CIC_DEV|full|127|0.478032%|5.421758%|99.998735%|99.999715%|
|CIC_DEV|full|227|0.449271%|5.059189%|100.000000%|100.000000%|
|CIC_DEV|full|ensemble|0.460181%|5.412342%|100.000000%|100.000000%|
|UNSW_DEV|post_window_primary|27|0.282091%|0.264039%|99.979325%|99.987961%|
|UNSW_DEV|post_window_primary|127|0.253882%|0.267688%|99.986217%|99.990279%|
|UNSW_DEV|post_window_primary|227|0.346569%|0.522840%|99.972434%|99.981586%|
|UNSW_DEV|post_window_primary|ensemble|0.282091%|0.286266%|99.986217%|99.991298%|
|UNSW_DEV|full|27|1.074403%|0.716546%|99.979325%|99.987961%|
|UNSW_DEV|full|127|1.114000%|0.678850%|99.986217%|99.990279%|
|UNSW_DEV|full|227|1.186595%|0.921067%|99.972434%|99.981586%|
|UNSW_DEV|full|ensemble|1.099481%|0.695814%|99.986217%|99.991298%|
|EDGE|full|27|0.115000%|1.167270%|99.820000%/97.645000%|99.782738%/97.645000%|
|EDGE|full|127|0.360000%|3.610879%|97.590000%/99.380000%|96.780567%/99.380000%|
|EDGE|full|227|0.000000%|0.000000%|99.795000%/98.350000%|99.753475%/98.350000%|
|EDGE|full|ensemble|0.120000%|1.220180%|99.790000%/98.660000%|99.751165%/98.660000%|

关键边界：

- A全视图集成普通FPR0.460181%，但加权FPR5.412342%，不满足全口径2%。464条正常误报全部来自NO_TWO_LEGAL_MATCHES组；其中446条位于主窗口之外，18条仍在主窗口内。不能把无合法参考都称为纯暖机，也不能仅展示建档后数字。
- B全视图集成普通/加权FPR1.099481%/0.695814%，整体仍达标；但WEMO Motion全视图普通FPR2.31%。主视图各设备集成达标；Seed227的Samsung攻击普通检出99.896595%略低于99.9%，不能称所有设备所有头都达标。
- Edge集成HTTP99.79%、UDP98.66%未到双99.9%；Seed127加权FPR3.610879%、HTTP普通97.59%也须披露，不能用集成掩盖。
- RAW在Edge本就只有HTTP19966/20000（99.83%）、UDP19732/20000（98.66%）；减分式C5不新增RAW告警，不能越过这两个上限。达到各19980/20000至少还需修复HTTP RAW中的14条、UDP RAW中的248条；当前C5另有8条HTTP撤警。
- A/B为开发评价；Edge已经多轮用于诊断和方案调整，定位为已消费数据上的迁移/弱泛化证据，不能包装为未触碰独立外部测试。

## 6. 候选逐设备明细（普通与原分层权重）

|池|视图|头|设备/类|告警/样本|普通率|加权率|
|---|---|---|---|---:|---:|---:|
|CIC_DEV|post_window_primary|27|Eufy Home Base / NORMAL|15/95369|0.015728%|0.003575%|
|CIC_DEV|post_window_primary|27|Eufy Home Base / ATTACK|13507/13507|100.000000%|100.000000%|
|CIC_DEV|post_window_primary|27|HeimVision Camera / NORMAL|0/672|0.000000%|0.000000%|
|CIC_DEV|post_window_primary|27|HeimVision Camera / ATTACK|65546/65549|99.995423%|99.997332%|
|CIC_DEV|post_window_primary|127|Eufy Home Base / NORMAL|12/95369|0.012583%|0.002879%|
|CIC_DEV|post_window_primary|127|Eufy Home Base / ATTACK|13507/13507|100.000000%|100.000000%|
|CIC_DEV|post_window_primary|127|HeimVision Camera / NORMAL|0/672|0.000000%|0.000000%|
|CIC_DEV|post_window_primary|127|HeimVision Camera / ATTACK|65548/65549|99.998474%|99.999430%|
|CIC_DEV|post_window_primary|227|Eufy Home Base / NORMAL|39/95369|0.040894%|0.010044%|
|CIC_DEV|post_window_primary|227|Eufy Home Base / ATTACK|13507/13507|100.000000%|100.000000%|
|CIC_DEV|post_window_primary|227|HeimVision Camera / NORMAL|0/672|0.000000%|0.000000%|
|CIC_DEV|post_window_primary|227|HeimVision Camera / ATTACK|65549/65549|100.000000%|100.000000%|
|CIC_DEV|post_window_primary|ensemble|Eufy Home Base / NORMAL|18/95369|0.018874%|0.004470%|
|CIC_DEV|post_window_primary|ensemble|Eufy Home Base / ATTACK|13507/13507|100.000000%|100.000000%|
|CIC_DEV|post_window_primary|ensemble|HeimVision Camera / NORMAL|0/672|0.000000%|0.000000%|
|CIC_DEV|post_window_primary|ensemble|HeimVision Camera / ATTACK|65549/65549|100.000000%|100.000000%|
|CIC_DEV|full|27|Eufy Home Base / NORMAL|334/99833|0.334559%|4.794862%|
|CIC_DEV|full|27|Eufy Home Base / ATTACK|13507/13507|100.000000%|100.000000%|
|CIC_DEV|full|27|HeimVision Camera / NORMAL|66/997|6.619860%|5.271815%|
|CIC_DEV|full|27|HeimVision Camera / ATTACK|65546/65549|99.995423%|99.997332%|
|CIC_DEV|full|127|Eufy Home Base / NORMAL|419/99833|0.419701%|5.852415%|
|CIC_DEV|full|127|Eufy Home Base / ATTACK|13507/13507|100.000000%|100.000000%|
|CIC_DEV|full|127|HeimVision Camera / NORMAL|63/997|6.318957%|4.991100%|
|CIC_DEV|full|127|HeimVision Camera / ATTACK|65548/65549|99.998474%|99.999430%|
|CIC_DEV|full|227|Eufy Home Base / NORMAL|393/99833|0.393657%|5.204788%|
|CIC_DEV|full|227|Eufy Home Base / ATTACK|13507/13507|100.000000%|100.000000%|
|CIC_DEV|full|227|HeimVision Camera / NORMAL|60/997|6.018054%|4.913589%|
|CIC_DEV|full|227|HeimVision Camera / ATTACK|65549/65549|100.000000%|100.000000%|
|CIC_DEV|full|ensemble|Eufy Home Base / NORMAL|398/99833|0.398666%|5.516173%|
|CIC_DEV|full|ensemble|Eufy Home Base / ATTACK|13507/13507|100.000000%|100.000000%|
|CIC_DEV|full|ensemble|HeimVision Camera / NORMAL|66/997|6.619860%|5.308510%|
|CIC_DEV|full|ensemble|HeimVision Camera / ATTACK|65549/65549|100.000000%|100.000000%|
|UNSW_DEV|post_window_primary|27|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / NORMAL|52/19711|0.263812%|0.021775%|
|UNSW_DEV|post_window_primary|27|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / ATTACK|14494/14506|99.917276%|99.949757%|
|UNSW_DEV|post_window_primary|27|unsw-attack-traces-2018:50:c7:bf:00:56:39 / NORMAL|1/2597|0.038506%|0.000528%|
|UNSW_DEV|post_window_primary|27|unsw-attack-traces-2018:50:c7:bf:00:56:39 / ATTACK|14602/14604|99.986305%|99.993380%|
|UNSW_DEV|post_window_primary|27|unsw-attack-traces-2018:70:ee:50:18:34:43 / NORMAL|20/19879|0.100609%|0.052450%|
|UNSW_DEV|post_window_primary|27|unsw-attack-traces-2018:70:ee:50:18:34:43 / ATTACK|14377/14377|100.000000%|100.000000%|
|UNSW_DEV|post_window_primary|27|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / NORMAL|105/13028|0.805956%|0.874493%|
|UNSW_DEV|post_window_primary|27|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / ATTACK|14512/14513|99.993110%|99.996669%|
|UNSW_DEV|post_window_primary|27|unsw-attack-traces-2018:ec:1a:59:83:28:11 / NORMAL|32/19229|0.166415%|0.370947%|
|UNSW_DEV|post_window_primary|27|unsw-attack-traces-2018:ec:1a:59:83:28:11 / ATTACK|14553/14553|100.000000%|100.000000%|
|UNSW_DEV|post_window_primary|127|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / NORMAL|37/19711|0.187712%|0.016360%|
|UNSW_DEV|post_window_primary|127|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / ATTACK|14497/14506|99.937957%|99.954725%|
|UNSW_DEV|post_window_primary|127|unsw-attack-traces-2018:50:c7:bf:00:56:39 / NORMAL|2/2597|0.077012%|0.001055%|
|UNSW_DEV|post_window_primary|127|unsw-attack-traces-2018:50:c7:bf:00:56:39 / ATTACK|14604/14604|100.000000%|100.000000%|
|UNSW_DEV|post_window_primary|127|unsw-attack-traces-2018:70:ee:50:18:34:43 / NORMAL|13/19879|0.065396%|0.052452%|
|UNSW_DEV|post_window_primary|127|unsw-attack-traces-2018:70:ee:50:18:34:43 / ATTACK|14377/14377|100.000000%|100.000000%|
|UNSW_DEV|post_window_primary|127|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / NORMAL|91/13028|0.698496%|0.748186%|
|UNSW_DEV|post_window_primary|127|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / ATTACK|14512/14513|99.993110%|99.996669%|
|UNSW_DEV|post_window_primary|127|unsw-attack-traces-2018:ec:1a:59:83:28:11 / NORMAL|46/19229|0.239222%|0.520385%|
|UNSW_DEV|post_window_primary|127|unsw-attack-traces-2018:ec:1a:59:83:28:11 / ATTACK|14553/14553|100.000000%|100.000000%|
|UNSW_DEV|post_window_primary|227|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / NORMAL|39/19711|0.197859%|0.469233%|
|UNSW_DEV|post_window_primary|227|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / ATTACK|14491/14506|99.896595%|99.924542%|
|UNSW_DEV|post_window_primary|227|unsw-attack-traces-2018:50:c7:bf:00:56:39 / NORMAL|4/2597|0.154024%|0.150481%|
|UNSW_DEV|post_window_primary|227|unsw-attack-traces-2018:50:c7:bf:00:56:39 / ATTACK|14602/14604|99.986305%|99.993380%|
|UNSW_DEV|post_window_primary|227|unsw-attack-traces-2018:70:ee:50:18:34:43 / NORMAL|39/19879|0.196187%|0.039703%|
|UNSW_DEV|post_window_primary|227|unsw-attack-traces-2018:70:ee:50:18:34:43 / ATTACK|14377/14377|100.000000%|100.000000%|
|UNSW_DEV|post_window_primary|227|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / NORMAL|141/13028|1.082284%|1.546309%|
|UNSW_DEV|post_window_primary|227|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / ATTACK|14510/14513|99.979329%|99.990007%|
|UNSW_DEV|post_window_primary|227|unsw-attack-traces-2018:ec:1a:59:83:28:11 / NORMAL|35/19229|0.182017%|0.408474%|
|UNSW_DEV|post_window_primary|227|unsw-attack-traces-2018:ec:1a:59:83:28:11 / ATTACK|14553/14553|100.000000%|100.000000%|
|UNSW_DEV|post_window_primary|ensemble|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / NORMAL|40/19711|0.202932%|0.017827%|
|UNSW_DEV|post_window_primary|ensemble|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / ATTACK|14498/14506|99.944850%|99.963130%|
|UNSW_DEV|post_window_primary|ensemble|unsw-attack-traces-2018:50:c7:bf:00:56:39 / NORMAL|1/2597|0.038506%|0.000528%|
|UNSW_DEV|post_window_primary|ensemble|unsw-attack-traces-2018:50:c7:bf:00:56:39 / ATTACK|14603/14604|99.993153%|99.996690%|
|UNSW_DEV|post_window_primary|ensemble|unsw-attack-traces-2018:70:ee:50:18:34:43 / NORMAL|27/19879|0.135822%|0.052623%|
|UNSW_DEV|post_window_primary|ensemble|unsw-attack-traces-2018:70:ee:50:18:34:43 / ATTACK|14377/14377|100.000000%|100.000000%|
|UNSW_DEV|post_window_primary|ensemble|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / NORMAL|104/13028|0.798281%|0.933786%|
|UNSW_DEV|post_window_primary|ensemble|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / ATTACK|14512/14513|99.993110%|99.996669%|
|UNSW_DEV|post_window_primary|ensemble|unsw-attack-traces-2018:ec:1a:59:83:28:11 / NORMAL|38/19229|0.197618%|0.426568%|
|UNSW_DEV|post_window_primary|ensemble|unsw-attack-traces-2018:ec:1a:59:83:28:11 / ATTACK|14553/14553|100.000000%|100.000000%|
|UNSW_DEV|full|27|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / NORMAL|104/20000|0.520000%|0.059784%|
|UNSW_DEV|full|27|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / ATTACK|14494/14506|99.917276%|99.949757%|
|UNSW_DEV|full|27|unsw-attack-traces-2018:50:c7:bf:00:56:39 / NORMAL|21/2680|0.783582%|0.467904%|
|UNSW_DEV|full|27|unsw-attack-traces-2018:50:c7:bf:00:56:39 / ATTACK|14602/14604|99.986305%|99.993380%|
|UNSW_DEV|full|27|unsw-attack-traces-2018:70:ee:50:18:34:43 / NORMAL|96/20000|0.480000%|0.633948%|
|UNSW_DEV|full|27|unsw-attack-traces-2018:70:ee:50:18:34:43 / ATTACK|14377/14377|100.000000%|100.000000%|
|UNSW_DEV|full|27|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / NORMAL|129/13083|0.986012%|0.894799%|
|UNSW_DEV|full|27|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / ATTACK|14512/14513|99.993110%|99.996669%|
|UNSW_DEV|full|27|unsw-attack-traces-2018:ec:1a:59:83:28:11 / NORMAL|464/20000|2.320000%|1.526293%|
|UNSW_DEV|full|27|unsw-attack-traces-2018:ec:1a:59:83:28:11 / ATTACK|14553/14553|100.000000%|100.000000%|
|UNSW_DEV|full|127|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / NORMAL|158/20000|0.790000%|0.125615%|
|UNSW_DEV|full|127|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / ATTACK|14497/14506|99.937957%|99.954725%|
|UNSW_DEV|full|127|unsw-attack-traces-2018:50:c7:bf:00:56:39 / NORMAL|21/2680|0.783582%|0.215895%|
|UNSW_DEV|full|127|unsw-attack-traces-2018:50:c7:bf:00:56:39 / ATTACK|14604/14604|100.000000%|100.000000%|
|UNSW_DEV|full|127|unsw-attack-traces-2018:70:ee:50:18:34:43 / NORMAL|85/20000|0.425000%|0.569551%|
|UNSW_DEV|full|127|unsw-attack-traces-2018:70:ee:50:18:34:43 / ATTACK|14377/14377|100.000000%|100.000000%|
|UNSW_DEV|full|127|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / NORMAL|114/13083|0.871360%|0.767645%|
|UNSW_DEV|full|127|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / ATTACK|14512/14513|99.993110%|99.996669%|
|UNSW_DEV|full|127|unsw-attack-traces-2018:ec:1a:59:83:28:11 / NORMAL|466/20000|2.330000%|1.715545%|
|UNSW_DEV|full|127|unsw-attack-traces-2018:ec:1a:59:83:28:11 / ATTACK|14553/14553|100.000000%|100.000000%|
|UNSW_DEV|full|227|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / NORMAL|154/20000|0.770000%|0.567194%|
|UNSW_DEV|full|227|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / ATTACK|14491/14506|99.896595%|99.924542%|
|UNSW_DEV|full|227|unsw-attack-traces-2018:50:c7:bf:00:56:39 / NORMAL|24/2680|0.895522%|0.375952%|
|UNSW_DEV|full|227|unsw-attack-traces-2018:50:c7:bf:00:56:39 / ATTACK|14602/14604|99.986305%|99.993380%|
|UNSW_DEV|full|227|unsw-attack-traces-2018:70:ee:50:18:34:43 / NORMAL|115/20000|0.575000%|0.600757%|
|UNSW_DEV|full|227|unsw-attack-traces-2018:70:ee:50:18:34:43 / ATTACK|14377/14377|100.000000%|100.000000%|
|UNSW_DEV|full|227|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / NORMAL|165/13083|1.261179%|1.566615%|
|UNSW_DEV|full|227|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / ATTACK|14510/14513|99.979329%|99.990007%|
|UNSW_DEV|full|227|unsw-attack-traces-2018:ec:1a:59:83:28:11 / NORMAL|441/20000|2.205000%|1.494817%|
|UNSW_DEV|full|227|unsw-attack-traces-2018:ec:1a:59:83:28:11 / ATTACK|14553/14553|100.000000%|100.000000%|
|UNSW_DEV|full|ensemble|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / NORMAL|119/20000|0.595000%|0.088419%|
|UNSW_DEV|full|ensemble|unsw-attack-traces-2018:00:16:6c:ab:6b:88 / ATTACK|14498/14506|99.944850%|99.963130%|
|UNSW_DEV|full|ensemble|unsw-attack-traces-2018:50:c7:bf:00:56:39 / NORMAL|21/2680|0.783582%|0.229028%|
|UNSW_DEV|full|ensemble|unsw-attack-traces-2018:50:c7:bf:00:56:39 / ATTACK|14603/14604|99.993153%|99.996690%|
|UNSW_DEV|full|ensemble|unsw-attack-traces-2018:70:ee:50:18:34:43 / NORMAL|103/20000|0.515000%|0.634119%|
|UNSW_DEV|full|ensemble|unsw-attack-traces-2018:70:ee:50:18:34:43 / ATTACK|14377/14377|100.000000%|100.000000%|
|UNSW_DEV|full|ensemble|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / NORMAL|128/13083|0.978369%|0.954091%|
|UNSW_DEV|full|ensemble|unsw-attack-traces-2018:ec:1a:59:79:f4:89 / ATTACK|14512/14513|99.993110%|99.996669%|
|UNSW_DEV|full|ensemble|unsw-attack-traces-2018:ec:1a:59:83:28:11 / NORMAL|462/20000|2.310000%|1.573411%|
|UNSW_DEV|full|ensemble|unsw-attack-traces-2018:ec:1a:59:83:28:11 / ATTACK|14553/14553|100.000000%|100.000000%|

## 7. 裁决和下一步

本轮阶段目标——保留完整历史参考后降低B误报，同时保持A和Edge的有价值表现——成立。C5_3D_OLD作为当前封存后处理候选；原FUSION790和原C5基线都保留，部署未变、没有新训练。原“所有数据/全样本/所有头均FPR<2%且HTTP/UDP≥99.9%”目标仍未达成。

建议先把本轮主结果、2×2对照、供体留存和明确失败口径整理入论文；固定该后处理候选，不再混合改动已成立部分。后续若继续逼近99.9%，单独设计源域约束的RAW漏检修复并保留A/B防退化，Seed127与建档期问题独立评价；新实验须另行形成具体执行卡，本次未启动。

验收依据：runs/same_bank_context_v6_20261106/FORMAL_ACCEPTANCE.json、DIAGNOSE_RESULT.json、PREFLIGHT_RESULT.json、取回SHA与调度回执。大逐行NPZ及历史context均留超算。
