# 同库历史正常参考＋三维C5：冻结执行卡

结果：小anti复核SHA已核对，四道门已落到独立v2实现；本地21项回归及56条真实历史参考暴力窗口核对通过，Linux预检待运行。
影响：只做零重训离线反事实；原FUSION790、阈值、源半径、两组尺度、旧NO_GO与部署均不变。
下一步：材料全部SHA通过→真实Linux预检→预算门→完整同库对照；任何门失败停止，不盲重交。

## 固定输入与权限

复核文档：20261106_context_geometry_attribution_review_antigravity.md，SHA256 64342c45ec1d0bbb3b19887d2ede007ee16c751a3ac29ea35ad3c2cc839a6fa8。用户明确授权按此封存并推进；没有新模型训练授权。

目录runs/same_bank_context_v2_20261106。v1仅完成材料盘点（25/33可用），未sbatch，实验计算0；v2增加隔离材料补齐，不改科学方法。缺失8项约82.84MB先在新目录assets中补齐SHA一致副本，不改旧封存路径。B四大原包及时间索引已在超算，不重传；本地只取回摘要。

A历史正常289条（旧HeimVision11＋C3新增278），B历史正常52835条（原三设备C3参考＋四设备C4新增），逐UID对齐原E3/q14数组。沿用原dense+history union：dense行保留，historical_reference_end保留原截止，匹配视图reference_end取该设备dense截止。不得新增参考、用目标攻击挑参考或改资格。Edge没有新增历史参考。

所有三种子27/127/227及算术集成，六流程RAW/C5_FROZEN/C5_2D_FUSION/C5_2D_OLD/C5_3D_FUSION/C5_3D_OLD。OLD为旧封存源尺度，不另拟合或挑选尺度。rho_z/rho_q和上轮源正常rho_c（TCP1.2302964232644185、UDP1.787982272961578）按上轮PREFLIGHT_RESULT SHA复用，不重新拟合。

## 门1：EXPANDED_2D_FROZEN_PARITY_GATE

预检和完整阶段均计算真实同库二维支持：可比查询support最大误差≤2e-10；全部查询、四头修正分数最大误差≤2e-10且判决差异0。C2 SYN无ACK守卫保持RAW。

唯一支持度比较例外由封存实现决定：C3曾跳过HeimVision的守卫查询距离更新，其support保存的是较旧定义，故这些行从支持度数值门剔除并明确记数；这些行的全部修正分数与判决仍必须精确复现。不是按差异大小或结果挑除。Eufy和WEMO Motion全体保留并核验。

三维按每个参考先取max(dz/rhoz,dq/rhoq,dc/rhoc)，再取不同组件二阶；dc为源标准化context8的RMS。逐行验证三维支持不高于二维、同尺度三维分数不低于二维、任何减分候选不新增RAW告警。

## 门2：CHRONOLOGICAL_ORACLE_GATE

A三capture（189/190/191）分别用新Engine，从首帧到末参考帧重放，不跨capture串流。B必须使用原packet_index.npy与chronological_order.npy；按逻辑frame=1..bank_end_frame直接寻址原PCAPNG EPB，逐包校验索引ordinal、块偏移、接口、cap/wire长度、时间戳和稳定同刻次序。最终截止为HIST_REF bank_end_frame，HIST_DEV数据包解码数强制0；只读首个HIST_DEV索引时间用于截止分离校验。

参考点校验frame、origin_packet_ordinal、timestamp_us、owner/protocol及原始输入SHA。设备内按完整未过滤历史逻辑流推进；不按参考点采样流重放，不按小时/日界重置。源统计Engine、8维字段、方向和当前包包含规则字节沿用。

复核文档用[clock-W,clock]描述窗口；封存Engine实际为**(clock-W,clock]**。本轮以原代码为准。合成边界测试显式覆盖左端淘汰、当前端包含；另设物理乱序负例，只有封存时间索引次序通过，越HIST_REF截止必须失败。

本地与Linux各核对A每capture8点、B每档案8点，共56点，采用独立deque暴力窗口，与Engine逐元素一致；完整历史重放中再次核对这些点与预检结果一致。真实Linux还执行原PCAP编码112行、距离与模型分数复现门。

## 门3：HISTORICAL_DONOR_RETENTION_AUDIT

A/B全视图正常查询按二维两个不同组件代表的来源分BOTH_DENSE、BOTH_HIST、MIXED_DENSE_HIST；无两个合法匹配单列NO_TWO_LEGAL_MATCHES，不能丢掉无支持样本。总量和逐设备分别报告：2D/3D支持分位数、原正支持数/保留数/归零数、support3/support2分布、有效匹配数、任一/两者dc/rhoc>1计数、距离分位数、六流程四头误报数及守卫数。比例可由明确分母计算；不把历史背景速率差异当攻击异常真值。

## 门4：全口径报告与训练解耦

A/B同时报告post_window_primary和full，普通/原分层加权、全部四头，逐设备正常及攻击计数。完整结果保留UID序与两视图原权重，不能重新选择分母。Edge普通/分层加权/HT、正常HTTP/UDP分列，所有指标必须与上轮同名流程在2e-10内复现且计数相同。

科学验收分别报告：A/B主视图集成普通/加权FPR<2%、攻击≥99.9%是否保持；全视图、设备、单种子失败不掩盖；Edge保持上轮结果仍不等于原双99.9%目标。若主指标保持则可确认有价值后处理候选，不能自动部署或称独立泛化。UDP训练方向（context约束/E3遮盖四臂）另行封存，此次不绑定或启动。

## 资源、进度与工件

1CPU、8GiB，PREFLIGHT最多30分钟、DIAGNOSE最多90分钟，总分配2小时，无自动重试。完整历史context在预检产生并SHA封存，完整阶段直接复用；既有dense/Edge context缓存、源半径及冻结分数复用。预检按小查询对完整库耗时外推×1.5＋600秒保守开销，须小于90分钟，否则不提交完整阶段。

启动前检查所有运行代码及父依赖SHA、33项历史材料；缺失先补齐，不以sbatch接受当预检成功。历史顺序扫描每5万帧更新进度，距离及贡献按批更新。后台普通程序自动取回结果、SHA、调度并生成runtime回执；右侧18806页面显示进度与六流程结果，不持续AI轮询。

大原包、索引、历史context、逐行支持/匹配/分数全部留超算。本地仅代码、封存执行卡、重要摘要和SHA清单。最终科学结论待结果验收。
