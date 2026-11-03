# 密参考方案实现回传（Codex，r2封包与独立解包验收完成）

2026-10-27。执行用户“允许按照方案实现”，依据Claude第二步r1/r2、完整矩阵r3及既有ε/观察期口径确认。**代码、冻结输入准备和合成验收已完成；正式实验未运行，不能把实现通过解释为误报已降低。** 本轮真实前向、补编码、目标评价、训练和超算提交均为0。

主目录：`runs/dense_reference_matrix_v1_20261027/`。见[实现说明](../../dense_reference_matrix_v1_20261027/README.md)、[冻结协议](../../dense_reference_matrix_v1_20261027/PROTOCOL.md)、[具体执行卡](../../dense_reference_matrix_v1_20261027/EXECUTION_CARD.md)和[最终独立验收](../../dense_reference_matrix_v1_20261027/distribution/r2/VALIDATION.json)。**当前可用分发为r2，r1保留作失败证据，不部署。**

## 封包与验证结果

- 独立解包后 **86/86合成测试通过**（binding21、chain12、matrix12、metrics9、materialize5、progress5、runtime/monitor22）。包含微型临时worker的退出、超时和科学FAIL续行，以及完整合成矩阵。没有使用真实目标分数或特征做新评价。
- 原编码器723文件与原封存SHA逐项一致；25项独立审阅代码pin、680项源前缀资产闭包、新Python语法、源CAL纯导入闭包及Git Bash的Slurm语法检查均PASS。测试后包SHA复验PASS。
- 封包1492文件，归档115,876,260字节。包`PACKAGE_SHA256SUMS`的SHA：`ddb94bb9836c9ace0b2a704e875d969c1d3c40c94198212ac795a9d0731db120`。
- 归档SHA：`43c31bd5ba3dc169aa95fae0079f2b856801043c46fd7862736110cb603b0140`。文件为`distribution/r2/dense_reference_matrix_v1_20261027.tar.gz`，见[封包回执](../../dense_reference_matrix_v1_20261027/distribution/r2/PACKAGE_RECEIPT.json)。
- 本地为Windows/Python3.10/NumPy2.2.6；psutil来自已安装本机依赖的私有验证副本，未修改共享环境、未将Windows依赖带到Linux。以上验收不替代计算节点Linux3.11/NumPy2.0.1实际导入、原104字节门或生产资源实测。

r1独立解包暴露了测试引用包外源码路径，以及本地验收关闭user-site后没有显式提供psutil两项可移植性问题，见[失败留档](../../dense_reference_matrix_v1_20261027/distribution/r1/VALIDATION_FAILURE.json)。已将测试改为只读包内封存选择器，并显式建立本机psutil的验证私有副本；重新封r2、全项复验通过。未修改科研计算公式，未执行/重试任何远端实验。

## 已实现的内容

- 沿用原冻结源/A/B位置、观察窗口、UID、快照、q14与现有E3；没有扩大观察期或重选位置。
- 按r3冻结WRONG供体及UID表，报告实际密度比例和双方组件数；无供体NOT_EVALUABLE、单组件不合格保持原V3行为。
- 三臂 R-B2 / R-DENSE / R-DENSE-WRONG、四ε和四suffix的保存分数矩阵runner；WRONG直接复用同ε的R-DENSE源工作点，不在A/B选择λ。
- 编码完成后的输入物化：核对原104门禁、冻结metadata/UID/q14、编码receipt、源CAL输入seal和原固定参数；只填派生pin，不改科学字段。
- 观察期后按原层级重新赋权、全量并列，池/设备/攻击类型/annotation预算与完整配对覆盖率报告。CIC攻击类型使用activity，不能因缺annotation_id遗漏5pp门限。
- 有序执行前缀、进程树资源监督、零自动重试、退出回执和普通进度同步。连接断开不会冒充正常运行或完成，不持续调用AI轮询。

独立矩阵、链与runtime审阅分别见 `preparation/MATRIX_INDEPENDENT_REVIEW.md/json`、`CHAIN_INDEPENDENT_REVIEW.md/json`、`FINAL_RUNTIME_REVIEW.md/json`；兼容性审计见 `ENCODER_PORTABILITY_AUDIT.md/json`。已修复CIC攻击类型预算、源CAL固定参数交叉绑定、真实矩阵入口第三池早停和前缀委托授权不越权。进度区分排队/启动/运行/等待调度终态/异常/失联，前缀完成明确“未运行目标矩阵”；Slurm失败不能被child COMPLETE遮蔽。当前没有启动新进度服务，旧18769页保持。

## 第三池的真实缺口

这里需要更正r3的资产前提：没有查到可直接消费的V4-EVAL1第三池冻结BASE/B2。检查了旧onboarding v3协议、服务、runner、历史四suffix结果、V4 target adapter和V4-EVAL1全量parent inventory；它们只有A/B，第三池明确NOT_RUN或列为missing evidence。旧runner也没有可用于第三池的已登记统一t0。

因此这不是“第三池资产存在，但receipt没定义窗口”。当前第三池为 `BLOCKED_MISSING_FROZEN_BASE_B2`，不能套用R-B2-only分支，不得新设窗口或用源CAL替代；第三池新增编码量/距离预算记未知，不写0。

完整登记矩阵目前在启动前停止。允许准备并单独执行已实现的 `runtime → encode → source_cal` 前缀，但仍需用户后续针对具体包与资源的云端授权；本次实现授权不伪造云端批准回执。不得为了绕过缺口将三池矩阵自动改成A/B-only。第三池补齐或研究范围修订须明确登记、封新包并取得相应运行授权。

## 已冻结工作量与资源

| 内容 | 数量 |
|---|---:|
| 新增E3：源/A/B | 4,624 / 5,237 / 11,799 |
| 新增E3总计 | **21,660** |
| 原104字节门禁 | 额外104次重放；不计为新增位置 |
| A/B三臂支持 | **912,302,797距离对** |
| 真正密源CAL R-DENSE支持 | **462,617,386距离对** |
| 原R-B2源CAL支持 | 3,570,165距离对 |

源CAL两库合计466,187,551对。支持对数不乘四ε或seed，E3行秒不换算成距离kernel吞吐。参考密度匹配受供体不足限制，例如一个UNSW UDP组只有14/2,669位置；需如实披露，不能按结果换供体补齐。A的HeimVision TCP没有合法供体。

准备的超算合同为amd、4CPU、16GiB、总12小时、单worker、CPU-only；8GiB进程树RSS守卫、4线程、无自动延长/重试。阶段上限共享总12小时，以剩余总额度为准，不能将阶段上限加总解释成额外授权。

原封存编码器要求NumPy2.0.1，超算共享环境为1.26.4。新包准备在新作业私有目录离线安装已封SHA的NumPy2.0.1 overlay，原六项依赖版本门保持，不改共享环境。实际依赖ABI与netFound导入仍待计算节点验证；随后必须实际重放原104，逐UID、float32字节全等才可补21,660位置。导入通过或版本相同不代表数值门禁通过。

## 下一步与明确未完成项

1. 实现、执行卡、r2封包与独立验收已完成；按此前“云端运行前向用户申请授权”的约定，下一项可审批工作为执行卡列出的三阶段前缀（amd4CPU/16GiB/12小时、一次提交、0重试）。本轮没有生成生产批准回执、上传或sbatch。
2. 用户具体授权云端运行后，才可在超算运行私有runtime检查、原104门禁、正式补编码和真正密源CAL；技术异常停在原现场，不自动重跑。
3. 在第三池冻结资产缺口解决前，完整矩阵继续BLOCKED，不自动做A/B新评价。密源CAL科学FAIL本身不取消后续已登记对照，但缺失身份/数据证据属于技术阻断。

已有历史密参考代理信号仍只是开发诊断；本轮没有新的A/B FPR、召回或效果结论。旧BASE/CTX完成与旧异常记录保持原样，不能混作本轮生产状态。
