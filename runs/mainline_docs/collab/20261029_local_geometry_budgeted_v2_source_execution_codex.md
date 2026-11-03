# 局部几何v2首次源执行：RAW复现技术停止

2026-10-29。用户明确“允许下一步”后，已实际启动一次 `python -B run.py source --output outputs/source_01`。本次在最先的G0_BASE_27 CAL重放门触发 `SOURCE_RAW_REPLAY_MISMATCH:G027CAL`，exit1；**属于技术停止，局部几何收益与攻击保护尚未评价，没有新A/B结果。**

## 实际完成与停止现场

[运行状态](../../local_geometry_budgeted_v2_20261029/outputs/source_01/STATUS.json)／[异常](../../local_geometry_budgeted_v2_20261029/outputs/source_01/EXCEPTION.json)／[独立执行审计](../../local_geometry_budgeted_v2_20261029/execution/ATTEMPT_RESULT_SOURCE_01.json)。最后状态记录约49.953秒、峰值4.40GiB，未见资源超限。源头CAL前向已做26,349行，距离对0；HELD重放、own-FIT前向、D0、L、λ选择、主CAL、新A/B及训练/编码均未进行。进程及子进程已退出。

11项执行代码SHA与启动封存/实现回执一致；启动时62项输入SHA与先前最终只读验收一致。因为未走正常finish，不能声称完成了运行后的全输入复核。原目录只有INPUT_SEAL/STATUS/EXCEPTION，没有RESULT或COMPLETED阶段回执，因此不可能合法进入target。

原错误门合并检查dtype、shape和逐字节分数。此次未保存重放向量或差异统计，故不能断言只是微小浮点误差、是否影响判定，或已确定是版本问题；也不能靠静态审阅补出这些数值。没有新前向去补取证，没有自动重试。

## 已定位的环境差异与准备的修复

历史179460源环境为 **Python3.11.11／NumPy1.26.4／Torch2.5.1／Linux**；本次为Python3.10.0／NumPy2.2.6／Torch2.8.0／Windows。证据在原179460 `environment.json`及BASE6复用审计/历史bootstrap。此前v2执行卡将NumPy2.0.1与源历史环境并列，混淆了主头/密参考链路；应更正，原封存文件仍保留作快照，本回执与修复卡记录准确版本。

静态核查未发现错换头、normalizer、特征、索引或评分batch。当前调用原 `training.scores` 的1024批、float64标准化后float32输入/输出。版本和平台差异是有依据的待检假说，尚未被实际修复运行证实。

独立[隔离修复包](../../local_geometry_budgeted_v2_replay_repair_r1_20261029/README.md)已准备：

- 历史环境专用入口，在任何真实前向前核Python/NumPy/Torch/Linux；保留历史兼容环境脚本的SHA绑定。
- 严格门前保存dtype/shape、字节SHA、差异数量/幅度、固定seed cut翻转和首16项差异；失败时保存完整期望/重放分数、原索引与UID。
- 原科学实现和原严格门不改，不增加前向，不加容差；记录/存盘/哈希仍计入原源阶段资源限额。独立源码审阅通过，去掉新增metadata/helper/唯一审计调用后，source AST与原版一致。
- **65项合成测试全部通过**；本地环境入口按预期被拒绝，0新增真实评分/距离。78项远端必需资产的布局/SHA清单已准备；当前远端可用性尚未核验。代码小包不包含数据。

见[修复执行卡](../../local_geometry_budgeted_v2_replay_repair_r1_20261029/EXECUTION_CARD.md)及[修复机器回执](../../local_geometry_budgeted_v2_replay_repair_r1_20261029/IMPLEMENTATION_RECEIPT.json)。本轮没有远端部署、提交或真实重跑。

## 后续边界

冻结方案第6节约定“一次，无自动重试”。本次源尝试已实际发生，修复后的再次源执行应作为新的单次尝试获得明确同意，建议仍4CPU/8GiB/4小时/2e9对/2GiB，0训练/新E3。远端资产与环境先只读验收，之后仅提交一次；再失败即保留停止。

条件后继仍为源PASS→主CAL严格复现/零撤回→一次A/B。未产生新A/B读数；正式成绩仍为A FPR3.993482%/recall100%、B FPR9.519654%/recall99.966594%。当前技术停止不代表局部几何无效，也不代表保护或收益门失败。旧B1结项和独立源1C延期保持。
