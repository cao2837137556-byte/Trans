# 最终3D配置：五配置补充消融交付包

状态：LOCAL_PREPARED_NOT_SUBMITTED。网络故障期间只准备本地材料。真实缓存尚未在超算读取，未执行消融、未生成实验成绩，也未改变现有基线作业。

## 固定范围

BASE(p=3,保护开)、GUARD_OFF(p=3,保护关)、P1/P2/P4(保护开)，共五配置。两个问题共享BASE；禁止自动增加饱和上界、λ、组件数/距离聚合、特征或分类头消融。λ=.25、旧源尺度、分类器、参考库及半径、阈值、UID顺序、视图和权重全部冻结。

`METHOD_FREEZE.json` 是当前本地冻结文件的逐字节快照；`BASE_EXPECTED_METRICS.json`含156条最终配置全指标。`INPUT_PINS.json`包含67个已在本地核验的生产者/依赖摘要。不得随意更新摘要来绕过不一致。

完整数据只在超算读取：same_bank_context_v6_20261106中的三个*_SAME_BANK.npz，共约392MB，及既有q14、行元数据、权重与模型身份文件。压缩包不含这些数组、模型、原PCAP或凭据。仅使用原始几何`support3`；不以历史support、置零support、g(s)或二维matched_reference_uid代替。读取后检查字段、范围、UID及SHA。

## 执行门与输出

1. 校验本包、67个源依赖、分类头身份/阈值、参考身份及支持缓存。缺资产停止，并保留具体缺失路径；本包不自动重算距离、训练或修改数据。
2. 三池先全部复现BASE：使用生产算术逐位对照，并核对缓存三头/集成分数（≤2e-10）及逐UID判定（必须0差异）；全156条指标计数一致、率误差≤2e-10。全部通过才计算消融。
3. 先保护开关，在全部池/视图/头生成`results/guard/`及COMPLETE回执，写作方可立即取回本项结果。
4. 再指数四档，生成`results/exponent/`；两项各自包含RESULT_READOUT.md、METRICS.json/csv、PAIRED_CHANGES.json/csv、CHANGED_UID_MANIFEST.json、VERIFICATION.json、COMPLETE.json。
5. 原始改变UID gzip留超算。回传以上小回执/表及顶层BASELINE_ACCEPTANCE、ASSET_IDENTITY、RUN_COMPLETE、RESOURCE_USAGE；如失败，回传STOP和Slurm日志。不要把输出中大量相关查询当独立事件或把各头相加。

所有记录中rate为[0,1]比率，Markdown显示百分数。配对n10为左臂有告警右臂无告警，n01反向；同时报告层级加权交叉质量。Edge保持原角色人口分母和HT率；保护/设备等子组没有封存人口分母时只报告HT总量贡献及抽样扩展总量，不能冒造子组HT率。所有视图与子组允许交叠，不将其求和当总体。

## 网络恢复后的提交（本轮不执行）

将压缩包解压至超算项目`/public/home/jiangxinwei.zr/work/paper04/runs/`，形成与本地同名目录；包内顶层就是该目录。不得覆盖已有同名运行结果。由原实验对话复用用户已建立的连接交付，不自动SSH登录。

在该包目录执行：

```bash
cd /public/home/jiangxinwei.zr/work/paper04/runs/paper_reading_ablations_v1_20261110
sbatch --parsable run.slurm
```

预设1CPU、8GiB、1小时是工程上限，不是已测耗时。此任务仅对保存数组作后处理，不重新编原包、不做前向或距离计算；不把其耗时当端到端实时性能。Python会记录实际用时，Slurm和/usr/bin/time记录资源。若内存达到7GiB或基准/单调性失败，停止而非放宽断言。

`results/PROGRESS.json`提供阶段和RSS；`guard/COMPLETE.json`与`exponent/COMPLETE.json`分别表示分项完成。联网后交付时将它接到原进度页；当前未启动接收服务或本地常驻程序，也未修改原进度写入器。

输出为NEW_OUTPUT_ONLY；重试另立版本或由实验对话明确安排，程序不会覆盖既有results。作业号/调度状态由实际提交回执记录；sbatch成功不能替代基准与实验验收。

## 数据角色表述冲突

11月10日写作交接及当前冻结材料将Edge标作未参与开发；本实验对话此前曾根据Edge诊断推进8维上下文与3D修正，并明确记录已消费诊断。该来源表述存在冲突，本执行包不静默改写任一上游文件或据此主张盲测。这里只做预先固定的五配置敏感性，不根据Edge成绩重新选择主方法；最终论文角色须根据实际设计时间线另行核对。

## 本地验证的意义

test_local.py用合成样本对照原生产函数、测试原始支持与SYN保护陷阱、p=1直接支持、零/一边界、严格阈值、指标/配对权重、HT及错误基准拒绝。LOCAL_VALIDATION只证明本地逻辑检查，不替代真实缓存SHA/基准验收。版本库提交记录与PACKAGE_MANIFEST文件摘要共同标识代码，打包时基准commit不是新包已提交commit的冒充。
