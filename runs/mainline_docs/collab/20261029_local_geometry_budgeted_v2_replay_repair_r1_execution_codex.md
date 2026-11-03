# 局部几何v2修复r1：一次源执行与科学门终态

**最新终态：180007 / node185于2026-10-29北京时间14:30:05正常完成，调度COMPLETED、exit0:0；科学判定SOURCE_SIGNAL_FAIL，源门BASELINE_TRANSFER_GUARD_FAIL。** 本次是D0跨设备模拟基线的攻击保护未通过，属于按登记规则完成后不推进目标的科学停止；不是作业崩溃、资源超限或RAW复现再次失败。主CAL和CIC_DEV / UNSW_DEV A/B均未执行，`A_B_inputs=0`，无新正式目标成绩、无自动重试。

## 终态证据与实际资源

[终端确认的最终快照](../../local_geometry_budgeted_v2_progress_20261029/runtime/TERMINAL_CONFIRMED_FINAL_SNAPSHOT.json)／[精确解析的STATUS及STAGE_RECEIPT](../../local_geometry_budgeted_v2_progress_20261029/runtime/TERMINAL_PARSED_FINAL_ARTIFACTS.json)／[固定远端Linux路径只读捕获](../../local_geometry_budgeted_v2_progress_20261029/runtime/FINAL_STATUS_TERMINAL_CAPTURE.txt)。最终快照明确标注来源为`verified_remote_linux_terminal`，保留调度、源门及代码/输出SHA。表内源阶段资源以STAGE_RECEIPT为准，调度耗时与阶段计时各自记录。

| 项目 | 最终记录 |
| --- | --- |
| 调度终态 | 180007 / node185，COMPLETED，0:0，18分33秒 |
| 源阶段计时 | 1,103.205968秒（约18分23秒） |
| 小头前向 | 4,600,362条，达到登记总量 |
| 实际距离对 | 355,060,239，低于2e9上限 |
| 峰值进程树RSS | 7,783,469,056 bytes（约7.249 GiB），低于8 GiB |
| 最终输出 | 262,972,027 bytes，低于2 GiB |
| 训练 / 新E3 / A_B输入 | 均0 |
| 自动重试 | false；仅此次提交 |

`RESULT.json`为5,866,809 bytes，SHA为`f5ddc8882b6945535913de64daf2250347bc0b6340d123e5eadb953f9e9c97fe`；阶段回执绑定该SHA及全部输出。原始结果仍在远端，本地持有终端证据和只读RESULT摘要，14:55恢复后的artifact_refs也独立记录相同SHA；尚未完整拉回全部科学产物。

## D0保护门失败的含义

六头的12组CAL/HELD RAW摘要均严格重放PASS。两折源CAL均选λ=0.25，D0及L在27/127/227/ensemble四suffix的RAW CAL TP撤回均0。源侧后续D0、L、局部scale与报告已经计算；这与主头目标链的主CAL是不同阶段，不能混称主CAL已通过。

失败发生在源跨设备模拟人口的D0基线累计攻击保护。以G0的own ensemble为例：

- SimCam设备原RAW TP累计撤回 **12.0220592823个百分点**，超过设备1个百分点上限。
- Hydra活动原RAW TP累计撤回 **26.5625个百分点**，超过活动5个百分点上限；对应phase×device/phase×activity也有越界。
- 原RAW召回已低于99%时，进一步撤回原TP也违反登记保护规则；单seed与safety视角另有失败项，完整原因保留在SOURCE_GATE。

这些是原攻击分母下的累计RAW→D0撤回，不能用原FN或别处收益抵消。`source_gate`按登记顺序先检查D0，再检查L的安全、压力和收益；因此准确结论是**D0迁移保护门未通过，L虽已计算，本次门禁未继续裁决L的安全或收益**。不能将其写成L已PASS、L的SAFETY_FAIL，或已经证明局部几何完全无效。

源`source_pass=false`，完整源PASS前提不成立，主CAL及一次A/B均被阻断。既有179700正式A/B成绩仍为A FPR3.993482% / recall100%，B FPR9.519654% / recall99.966594%；本次源模拟结果不追改它们。

## 源S固定人口的已保存指标

下表直接读取[恢复后的RESULT摘要](../../local_geometry_budgeted_v2_progress_20261029/runtime/RECOVERED_FINAL_SNAPSHOT.json)中`folds.G0/G1.metrics.*.ensemble`，使用固定源S population及继承的原加权规则，属于own ensemble指标，**不是A/B目标结果，也不是三seed指标的简单均值**。表内百分比保留12位小数，完整精度保存在摘要。

| 源折 | 分数臂 | FPR（%） | 攻击召回（%） |
| --- | --- | ---: | ---: |
| G0 | RAW | 11.132877341814 | 90.291979340069 |
| G0 | D0 | 5.101403882878 | 86.517604655296 |
| G0 | L | 5.100862976325 | 86.517604655296 |
| G1 | RAW | 18.453431512738 | 100.000000000000 |
| G1 | D0 | 7.451243673101 | 100.000000000000 |
| G1 | L | 7.450576591272 | 100.000000000000 |

L相对D0仅额外降低G0 FPR约**0.00054090655个百分点**、G1约**0.00066708183个百分点**，两折召回均未进一步改变。这一量级不构成实用收益，不能据此声称有显著改善；这里没有进行统计显著性检验。该描述是保存结果的读数，不取代登记门顺序：正式源门仍停在D0保护失败，未继续裁决L的安全/收益。本次读取与监控恢复均不补跑科学实验。

## 进度页为何曾停在RUNNING

旧只读bridge对单份JSON设4 MiB上限，最终5,866,809-byte RESULT触发`JSON_TOO_LARGE`，使自动快照停留在14:30附近的旧RUNNING记录；这是监控读取故障，不是科学作业仍运行或科学程序异常。原卡住快照保存在[监控故障证据](../../local_geometry_budgeted_v2_progress_20261029/runtime/STALE_MONITOR_JSON_TOO_LARGE_SNAPSHOT.json)。

截至14:51:10的结构化终态由固定远端Linux路径只读核验后恢复到本地，已停止旧collector，18775页面可保存已确认终态。该快照`connection.state=unknown`，明确说明自动只读同步仍在修复；不把终端人工确认伪称为自动连接已恢复。后续sidecar恢复只读监控不提交、重启或重算科学任务。

**14:55只读自动同步已实际恢复。** [恢复验收快照](../../local_geometry_budgeted_v2_progress_20261029/runtime/RECOVERED_FINAL_SNAPSHOT.json)于14:55:06记录`connection.state=connected`、scheduler COMPLETED0:0、`recovery.artifact_errors=[]`；STATUS、STAGE_RECEIPT、SOURCE_GATE、RESULT及RAW摘要已读成功。sidecar读取约5.6MiB RESULT后仅输出保存指标摘要，`artifact_refs`的RESULT字节数和SHA与阶段回执一致。[新collector记录](../../local_geometry_budgeted_v2_progress_20261029/runtime/RECOVERY_COLLECTOR_PROCESS.json)为PID4200、5秒一次GET18782、固定job180007；本地cache和18775页面已切到此已恢复终态。此修复只读监控，科学作业没有被重新提交、重启或重算。

原source_01失败、两个封存包及以下提交/启动快照均保留；下方RUNNING及“尚无源结果”是14:12时的历史记录。

## 14:12提交与启动历史快照

2026-10-29。用户已明确允许历史HPC修复版新一次源尝试；实际仅提交一次，**180007 / node185 / amd 已启动源阶段，技术状态RUNNING，科学结论仍未知**。提交时间为北京时间14:11:33（UTC 06:11:33）。本回执记录截至14:12:55的已保存工作进程证据，不把部署、调度运行或局部RAW重放通过写成源科学门PASS。

## 提交前核验与作业身份

- [提交回执](../../local_geometry_budgeted_v2_progress_20261029/runtime/SOURCE_SUBMISSION_RECEIPT.json)：`job_id=180007`，调度提交返回码0，`automatic_retry=false`。
- [HPC预检](../../local_geometry_budgeted_v2_progress_20261029/runtime/HPC_PREFLIGHT_VERIFY.json)：78项源必需输入SHA全部通过；历史源环境Python3.11.11 / NumPy1.26.4 / Torch2.5.1 / Linux精确匹配；65项合成测试通过。预检本身新增真实前向及距离均0。
- [首次工作进程快照](../../local_geometry_budgeted_v2_progress_20261029/runtime/FIRST_JOB_SNAPSHOT.json)：调度RUNNING，工作节点node185、分区amd，源工作进程PID1263436；14:11:53处于`SOURCE_INPUT_IDENTITY`。部署终端node168及bootstrap PID不作为该作业的工作节点或作业ID。
- 部署小包SHA：`abea951e099f531d385f081c60d3291f147f987cd5e921298c7a3a9a98460fb5`。原v2及隔离修复r1的封存文件、原失败现场均保留；执行状态在本回执和进度目录记录，封存卡中的“尚未部署”是封包时快照。

## 已跨过旧失败点，尚未完成源门

[已保存运行快照](../../local_geometry_budgeted_v2_progress_20261029/runtime/RUNNING_CONFIRMED_SNAPSHOT.json)含14:12:55工作心跳：

- G0/27/CAL（原source_01失败点）的26,349条分数严格dtype、shape、逐值和逐字节均PASS；字节差、数值差、阈值判定翻转均0。
- G0/27/HELD及G0/127/CAL也已严格重放PASS。
- 累计小头前向883,188条，实际距离对0；技术状态仍为`SOURCE_RAW_REPLAY / RUNNING`，峰值进程树RSS 6,837,526,528 bytes（约6.37 GiB）。这是一项有时间戳的运行快照，不是完整阶段回执或最终资源统计。

历史HPC环境下已恢复旧失败点的严格重放，是新的直接证据；由于同时更换了平台及多个软件版本，不能据此宣称NumPy是唯一根因。原source_01未保存的差异向量依旧未知，不追写为“仅微小浮点误差”。

当前尚无`SOURCE_GATE`、源`RESULT`或完整源完成回执。own-FIT、D0/L及收益/保护评价尚未在此快照中完成，**局部几何科学效果未评价，主CAL和A/B目标阶段尚未执行，没有新A/B指标**。

## 范围、停止条件与进度

本次脚本只启动源阶段：4CPU、0GPU、RSS≤8GiB、≤4小时、≤2e9实际距离对、≤4,600,362条小头评分、≤2GiB新输出；不训练、不新E3编码。仅此一次提交，`--no-requeue`、无自动重试；技术/资源异常即停并保留证据。

完整源PASS及绑定代码/输入/输出SHA、资源回执验收后，才可能进入既定条件主CAL：原D0锚严格复现和全部合格donor（包括新L/1C）的RAW TP零撤回。主CAL也PASS后，才能进行一次CIC_DEV / UNSW_DEV A/B；目标预算仍为4CPU/8GiB、另4小时、≤9e9距离对、≤2GiB输出。不得把当前源环境核验直接当作主头环境或D0锚已通过。

[本地18775进度页](http://127.0.0.1:18775/)由普通collector每5秒只读抓取快照，区分调度状态、工作心跳和科学门。桥接抓取时间更新本身不证明实验仍运行；工作心跳超过90秒时，实验状态应记未知。距离预算占比不作整体完成百分比。运行终态由独立历史记录保留。

原[source_01技术停止回执](20261029_local_geometry_budgeted_v2_source_execution_codex.md)不改判；旧B1仍为NOT_RUN / PROTECTION_EVIDENCE_INSUFFICIENT，独立源Atomi 1C仍延期。正式179700成绩保持：A FPR3.993482% / recall100%，B FPR9.519654% / recall99.966594%。
