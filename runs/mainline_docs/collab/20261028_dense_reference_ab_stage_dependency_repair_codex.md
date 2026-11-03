# A/B密参考评价：179680停止、依赖修复与新单次运行申请

2026-10-28。**后续最新：用户已明确授权修复后重启，新179700/node185正常RUNNING，详见[单次提交与启动验收](20261028_dense_reference_ab_stage_dependency_repair_execution_codex.md)。** 原179680失败保持，尚无完整A/B指标。下文是工程修复及提交前授权申请的历史回执，不能再用“待授权”阻塞已经批准的179700范围。本文接续[原执行回执](20261028_dense_reference_ab_stage_execution_codex.md)，不改写原候选、原归档、源CAL或失败现场。

## 1. 真实失败与根因

179680/node185，FAILED、exit70:0、48秒。原包、环境、全部静态和179602派生输入身份通过；目标metadata/features/head scores读取已开始，但第一臂初始化在真实query/reference UID重叠路径触发 `ModuleNotFoundError: No module named 'causal_reference_overlap_v1'`。完成支持计算和池结果均0。worker峰值约0.955 GiB，清理确认通过，无遗留worker。

原封包只带五个模块，遗漏函数内lazy import；原19项合成测试的query/reference UID互不相交，因此没覆盖这个真实分支。这是工程依赖闭包错误，不能记为方法科学FAIL。约1.24GB缺失静态输入已补传且全部核SHA，修复后原地复用，不重传、不编码、不训练、不重跑源CAL。

## 2. 修复与本地验收

新层为 `runs/dense_reference_ab_stage_dependency_repair_v1_20261028/`。六模块全部直接取原冻结编码包，字节和SHA保持；父/子进程使用严格模块finder，原matrix即使插入旧vendor路径也不能覆盖。子进程bootstrap身份失败即exit78，避免Python忽略sitecustomize错误。原算法、阈值、尺度、λ、观察窗口和供体均未改。

11项隔离测试和独立复验通过：五模块合法重叠精确复现缺模块、六模块合法重叠通过；非法身份/角色/标签/时间/frame/q14/UID join被拒绝；真实原matrix子进程导入和严格六模块来源通过，旧授权无法启动新修复层。全部Python源码与Slurm语法通过。

本地真实metadata预检通过：328,202条query、19件源seal、A原/密参考重叠64/3,334，B原/密参考重叠19/1,319，全部冻结历史资格核查通过。真实E3数组读取、E3算术、距离、支持、分数评价、模型前向、编码、CAL、训练和新科学作业均0。合成测试会用合成数组触发原 `_queries()` 路径，不能把合成验证与真实计算混称。

冻结包身份：

- PACKAGE_SHA256SUMS：`85637f3ae213ef08bf3cb70976a3188246eb03554d4b7fe7393f4cfe4414d9e8`。
- archive：`034a576d8c04bb1f06f3330f79a7ca1333e27e2ac4f77d1ac27c68373541ff5f`，618,516字节，含固定顶层目录。
- 分发目录：`runs/dense_reference_ab_stage_dependency_repair_distribution_20261028/r1/`。
- 独审：包内 `validation/INDEPENDENT_REVIEW.json`，`PASS_LOCAL_REPAIR_ONLY`；外部分发receipt记录最终封包身份。

## 3. 超算工程预检

**真实超算工程预检已完成，PASS_ENGINEERING_ONLY，耗时51.50秒。** 经既有 `school-hpc` 会话部署618,516字节修复归档，27件SHA与成员集合全部通过；固定工程入口先运行合成检查，再跑真实metadata预检，两阶段均exit0。328,202条query、53个pin、19件源seal，以及A原/密库64/3,334、B原/密库19/1,319个重叠UID均通过。远端加载的六模块路径与SHA均绑定新修复层。

传输桥无submit或通用执行端点；真实E3/分数数组读取、E3算术、距离、支持、前向、编码、CAL、训练和新科学提交均0。原179680现场保持。结果在 `runs/dense_reference_ab_stage_dependency_repair_deployment_20261028/PREFLIGHT.json`；最终工程回执为同目录 `ENGINEERING_ACCEPTANCE.json`。**工程PASS不等于A/B科学结果；新A/B指标仍无。**

## 4. 具体后续运行卡与授权边界

按[修复版执行卡](../../dense_reference_ab_stage_dependency_repair_v1_20261028/EXECUTION_CARD.md)，申请一次独立新提交：A/B两池、原参考/密参考/错设备密参考三臂；四ε、三seed及集成，主ε=.1个百分点，观察期后为主、全量并列。复用179602全部编码与源CAL，固定原工作点；第三池延期且未评价，原三池完整性保持false。

资源仍为amd、4CPU、16GiB、最多2小时；进程树RSS8GiB、输出2GiB、启动空闲12GiB；**只提交一次、0自动重试、0训练/编码/新CAL/前向**。新作业独立runtime，不续用179680目录。

原执行卡限定单次提交、0自动重试，179680已消费该授权。因此修复验收并不自动产生第二次提交授权；需要用户对本卡及上述新包身份明确确认。新模板仍为false，新授权必须绑定repair SHA和新的用户证据，旧179680授权不能触发。

[18771进度页](http://127.0.0.1:18771/)分别显示原失败终态和后续修复准备，不持续AI轮询。
