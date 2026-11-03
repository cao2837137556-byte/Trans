# 局部几何 v2 执行卡

2026-10-29。工程实现及验收的机器记录见 [IMPLEMENTATION_RECEIPT.json](IMPLEMENTATION_RECEIPT.json)。**实际源实验、主CAL及新A/B均未运行。** 本卡给出可执行入口，不生成新的运行授权，也不改写冻结方案。

## 固定内容

方案：[EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)，SHA256 `797a08dc7cd540f6c1c2d498490e520cb40d6938da8c6ceec350f5b80b17fc51`。复用179460六个BASE头及既有E3/q14；无训练、无新E3编码。仅一个局部几何L，比较RAW/D0/L，不设新参数搜索。

G0头评价G1原FIT 509,233行；G1头评价G0原FIT 108,675行。own-FIT共617,908行，原CAL共148,819行，原CAL不混入源诊断S。RAW重放与own-FIT合计4,600,362条小头评分，全计入源预算。源D0的geometry使用own-FIT正常与原104参考的本组子集，scale沿own-FIT原权重；CAL只给D0选择一次λ，L继承并独立检查新资格攻击。

本包使用完整查询支持，不启用方案中的可选界限裁剪。所有D0/L距离共用；相同fold的三seed共用support。

## 环境与校验

在项目完整checkout中运行，不能只拷贝此小包而遗漏 `DEPENDENCIES.json` 和输入清单指定的历史资产。当前本地验收环境为Python 3.10.0、NumPy 2.2.6、psutil 7.2.2、Torch 2.8.0+cpu；历史评分环境包含NumPy 2.0.1/Torch 2.5.1。**导入成功及合成通过不证明真实数值一致。** 实验最先按原路径严格重放CAL/HELD，任何逐值差异立即技术停止，不放宽容差或自动重试；主CAL与A/B旧D0也有严格锚与逐值核验。

入口设置数值线程上限4与CPU affinity；源前向使用CPU、Torch intra-op≤4/interop=1。所有命令均在新进程中执行。以下PowerShell命令先进入实验包：

```powershell
Set-Location 'D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\local_geometry_budgeted_v2_20261029'
```

只读输入验收（默认入口同为check；如路径已存在则拒绝覆盖）：

```powershell
python -B run.py check --output outputs/operator_input_check_01
```

该入口只校验源文件身份、人口、UID、参考及保存分数绑定，不做新前向、距离、support、阈值选择或候选A/B。`check`有独立30分钟、8GiB和512MiB输出限额；它不是源科学阶段。

## 一次源阶段

```powershell
python -B run.py source --output outputs/source_01
```

正式运行前应核对实现回执所列代码SHA和冻结计划SHA。入口再次核验外部依赖；运行时封存代码、输入与结果，并在结束时检查是否漂移。不得在运行期间编辑代码。

| 硬限 | 源阶段 | 条件目标阶段 |
| --- | ---: | ---: |
| CPU / GPU | 4 / 0 | 4 / 0 |
| 进程树RSS | 8GiB | 8GiB |
| 墙钟（包含加载、重放、存盘与输出SHA） | 4小时 | 另4小时 |
| 实际距离对 | 2,000,000,000 | 9,000,000,000 |
| 小头评分行 | 4,600,362 | 0 |
| 新输出 | 2GiB | 2GiB |

资源异常和技术错误立即停，保留现场，无自动重试、无自动追加候选。`STATUS.json`提供当前步骤、计数、RSS和耗时；无需AI循环检查。命令退出0只表示工程完成，不能代替科学PASS。

源推进必须同时满足：两折D0有效、D0/L的CAL零RAW TP撤回、三seed和ensemble累计设备/phase×device撤回≤1pp且activity/phase×activity≤5pp；RAW召回≥99%则L保持≥99%，RAW低于99%则L不得降低。两折ensemble各修复≥20%的D0加权FP，至少一折降≥0.5pp、合计≥2设备改善，至少一折原2C零支持FP修复≥10%，并有真实1C FP跨cut修复。两折须有合法可跨cut攻击压力与足够正常修复空间。

科学报告区分保护失败、基线迁移失败、无修正预算、覆盖不足与收益未达门。两折held库均无2C半径扩张时可按冻结规则提前停止。科学不通过会保存已登记报告，阻断后继；不换参数或人口。

## 源通过后的唯一条件后继

只有 `outputs/source_01/RESULT.json` 为 `SOURCE_SIGNAL_PASS` 且完整回执、资源、代码与输出SHA一致时，才可启动：

```powershell
python -B run.py target --source-result outputs/source_01/RESULT.json --output outputs/target_01
```

前序门控先于A/B加载。目标阶段先重放主头源CAL的旧D0，再检查L在自身新资格下零RAW TP撤回；CAL失败不读取A/B数值做新评价。通过后按同一规则一次评价CIC_DEV（A）及UNSW_DEV（B），输出全量与观察期后主口径、三seed与ensemble及三分支账本。主目标为两池ensemble及各设备FPR≤2%、池召回≥99%；所有seed和ensemble累计设备撤回≤1pp、activity/annotation≤5pp。新目标不重加旧池ε=.1pp。

目标阶段不重选λ/cut/半径，不挑较好seed或视图。A/B属于开发评价；通过也不代表独立确认，第三池与自身参考特异性归因均不在本轮。

## 结果读取

- 每阶段：`STATUS.json`、`RESULT.json`、`STAGE_RECEIPT.json`；技术异常另有`EXCEPTION.json`。
- 源阶段：`INPUT_SEAL.json`、每折FIT logits、GEOMETRY/SCALES、局部邻居与半径、λ/CAL检查、S报告、逐UID own/donor分数与攻击风险、`SOURCE_GATE.json`。
- 条件目标：`MAIN_D0_PARITY.json`、`MAIN_CAL_CHECK.json`、主CAL新旧资格及donor账本、两池`*_REPORT.json`与`*_SCORES.npz`、`TARGET_INPUT_SEAL.json`。

用户主表应读取观察期后两池FPR和召回；不能把源折的FPR、support增量或合成测试通过当成新的A/B成绩。上轮正式A/B仍为A FPR 3.993482% / recall 100%，B FPR 9.519654% / recall 99.966594%。
