# 局部几何v2实现与验收回执

2026-10-29。响应用户转述的grok“可以进实现”，已完成独立实验包、运行门控与工程验收。状态：`IMPLEMENTED_AND_ACCEPTED_NOT_RUN`。不再追加原则确认稿。

冻结方案SHA保持 `797a08dc7cd540f6c1c2d498490e520cb40d6938da8c6ceec350f5b80b17fc51`；方案文件不改写，原文的 `DESIGN_FIXED_IMPLEMENTATION_PENDING` 是定稿快照。当前工程证据见[机器回执](../../local_geometry_budgeted_v2_20261029/IMPLEMENTATION_RECEIPT.json)，实际命令见[执行卡](../../local_geometry_budgeted_v2_20261029/EXECUTION_CARD.md)。

## 已交付

- 独立 `run.py check/source/target`。默认check只核源输入；source执行六头旧RAW逐值重放、own-FIT小头前向、同头D0、唯一L；target只有完整源PASS才可进入主CAL，再在CAL零撤回后评价一次A/B。
- 局部半径沿冻结5邻居/最多8时间块/联合距离≤2/2倍上限；零半径、重复、1C新资格、2C不降格和整库交付依赖均已实现。D0/L共享距离，三seed共享support。本实现采用全量支持，不启用可选的support=1裁剪。
- 源与主头分别保持原ensemble数值路径；L攻击使用自身资格及RAW回退。累计撤回、基线失败、覆盖不足、收益门分开报告。所有合同边界使用原整数分母作精确比较，显示值仍可读。
- 4CPU、8GiB、源4小时/目标另4小时、2e9/9e9实际距离对与各2GiB输出守卫。含输入加载、科学计算、存盘与输出SHA；失败现场保留，无自动重试。后继同时验证代码/输出SHA、源PASS、最终完成状态及预算，未完成或异常快照不可推进。

## 验收证据

[61项合成测试](../../local_geometry_budgeted_v2_20261029/validation/synthetic_tests_final.log)全部通过，0失败/0错误/0跳过。包含真实源runner的人工数据衔接、主CAL真实函数的小型模拟输入、D0锚失败阻断、新1C foreign donor撤回阻断A/B、完整两池调用与资源异常。测试没有对真实数据运行新前向或距离。

[最终只读输入验收](../../local_geometry_budgeted_v2_20261029/outputs/implementation_check_final_20261029/RESULT.json)为CHECK_PASS：[阶段回执](../../local_geometry_budgeted_v2_20261029/outputs/implementation_check_final_20261029/STAGE_RECEIPT.json)耗时48.140秒，峰值进程树RSS 4,751,290,368字节（约4.42GiB），766,727条源数据与4,728条密参考身份通过；新前向、距离、support、训练、新编码、A/B输入和新目标评价均0。前一份实现中期check保留，最终证据以本段链接为准。

实际RAW逐值重放和D0数值锚尚未执行，属于正式阶段预算。当前本地NumPy2.2.6/Torch2.8.0与历史环境不同，已实现严格不一致即停；不能用导入或合成测试替代真实数值复现。这是待运行核验项，不是已观察到的失败。

## 下一步

工程实现完成后，下一项是按执行卡运行一次源阶段。源不过即止；源PASS才进入一次主CAL＋A/B。现阶段没有新的误报或召回结论，更不能声称已达到2%。旧B1结项、独立源Atomi1C延期及正式A/B结果均保留：A FPR3.993482%、召回100%；B FPR9.519654%、召回99.966594%。

本轮完成实现与验收，没有提交远端作业或启动正式source/target。所有调用均为合成测试、环境信息读取、输入身份验收与文档/代码封存。
