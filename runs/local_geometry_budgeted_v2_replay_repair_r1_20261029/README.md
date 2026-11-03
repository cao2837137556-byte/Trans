# 局部几何v2：RAW重放取证修复r1

原v2的首次源运行在历史RAW逐值重放检查处技术停止，局部几何和A/B尚未评价。本包隔离准备历史源环境入口和失败分数取证；原包、失败输出及科学方案均保留。

[执行卡](EXECUTION_CARD.md)给出历史环境、输入SHA验收、单次4CPU/8GiB/4小时源重跑命令及后继门。65项合成测试通过；本地错误环境在任何模型前向前被拒绝。远端部署及真实重跑尚未发生，真实数值复现仍未知。

`run.py`保留原check/source/target入口；正式源重跑应使用`historical_source.py`或`hpc/source_once.slurm`以强制历史环境。`verify_source_inputs.py`只哈希核验78个依赖文件，不加载模型或数值数组。`SOURCE_TRANSFER_MANIFEST.json`是数据布局和身份清单，代码归档不包含约2.44GiB历史数据。

RAW诊断仅报告本fold/seed/role：严格门通过时存JSON摘要，失败另存完整期望/重放分数与索引UID。shape不同情况下的展开值不是逐UID对齐对比；单seed的cut翻转也不是ensemble或A/B指标。未修改算法、人口、阈值或严格失败条件。
