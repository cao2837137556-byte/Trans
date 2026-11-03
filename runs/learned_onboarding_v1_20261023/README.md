# 学习式入网 V1：实现与验证

2026-10-23。以 `../learned_onboarding_pilot_v1_20261023/EXECUTION_SPEC_V1.md` 为冻结科研规格，SHA256 `a07d736c7c9c756478a7d163873611132ff0b14abc855ab3a3709257433674b8`。规格正文和旧方案回执保留其交付时的状态；本目录记录后续实现事实。

本轮完成代码与合成工程验证、真实源身份验收和既有阈值回放。**真实辅助头／修正器训练、CAL 攻击保护和 A/B 评价均未启动**。现有现代九头及 v3 作业、进度页、队列均未操作，没有新增远端连接或 AI 轮询。

最新验证数、源码身份、依赖版本及未运行项见 [implementation_manifest.json](implementation_manifest.json)；真实源核验见 [source_adapter_receipt.json](validation/source_adapter_receipt.json)。工程测试通过不代表入网收益或攻击保护已通过。

## 实现内容

| 文件 | 职责 |
| --- | --- |
| `src/source_inputs.py` | 源专用适配；校验缓存、分片连续 tar、完成谱系、q14、UID、spool、QUERY_TAIL seed27、正常阈值及执行代码；保持原头 1024 行回放路径 |
| `src/reference_core.py` | 完整库时间／帧资格、两真实组件代表、50 维关系输入、精确回退、元数据 WRONG 计划 |
| `src/tasks.py` | 依赖闭包分折、FIT-only t/s、一次性困难挖掘、层级权重、配对抽样流、覆盖与残差信号门槛 |
| `src/learning.py` | 两组三设备辅助头、三个 2177 参数模块、有限正常目标、全合法 bank 最坏攻击损失、固定终点和检查点回放 |
| `src/evaluation.py` | 三臂独立源 CAL λ、真实单列 v3 对照、完整分母与加权指标、新增 FN、原攻击门槛及科学判据 |
| `src/pipeline.py` | 源拟合→封存→CAL→封存→目标加载；40 主项及 EMPTY／WRONG；源码／运行环境跨阶段绑定 |
| `src/bundle_io.py` | 显式目标 manifest 及真实参考生产者载荷链校验；不提前读取目标 |
| `src/service.py`、`src/common.py` | 分阶段 CLI、资源估计、合成计时、进程树 RSS／累计输出守卫、原子回执及异常现场 |

辅助头只用本组三设备 FIT 拟合及估计 normalizer，留组 UID 与预处理 UID 单独核验。正式头不重训；CAL 不进入修正器训练、H 或输入。科学 FAIL 继续登记矩阵；身份／数值／资源异常停止，不自动重跑。

大 E3 数组采用 mmap；多 bank 输入按 batch 动态生成，源几何压缩保存为代表槽位和距离，任务 bank 使用惰性视图，JSONL 流式导出。新模块生产路径 query256／reference64；另核验 127／31 路径的代表、H、分数容差、严格判决与新增 FN 集合。固定路径重新加载检查点必须逐 bit 复现。

## 已验收与仍未知

- 实际源装配：766,727 LEARN、617,908 FIT、148,819 CAL、104 LEARN 参考；只定向提取 16 个源／头／回执成员，未打开 A/B 查询。
- 实际源侧回放：33,147 条 CAL 正常按原权重和原算法精确复现 cut `-23.066728591918945`；额外两行验证 `score_main` 与任意查询回放接口逐 bit 相同。optimizer 更新为 0。
- 全部 617,908 FIT 的数值与精确帧资格已验收：自身参考合格正常 120,026 行／4 台设备，攻击 447,149 行／3 台设备，覆盖门槛 READY；其余 14,467 正常、36,266 攻击仍保留为自身参考回退。这里的攻击计数是自身 bank，训练时还将枚举合法 donor。见 [源资格回执](validation/source_readiness_v1/source_task_receipt.json)。新 G0/G1 独立统计也共享 7 个捕获，只声称新头及拟合预处理留设备，不能称独立采集验证。
- 合成测试包含两辅助头及三模块的短训练、保存加载、完整训练分支和 no-op 分支、CAL、40 主项、12 控制输出，以及泄漏、身份、因果、数值及输出隔离负例。完整分支测试显式模拟残差信号门槛已通过；它不证明真实源具备信号。
- 尚未知：两辅助头的真实折外困难信号、运行峰值与吞吐、非零安全 λ、误报收益、困难训练增益及参考归因。资格覆盖通过不能代替真实残差信号。
- 生产目标 manifest 本轮未装配；[目标输入合同](config/TARGET_MANIFEST_SCHEMA.md) 定义四库来源与映射要求。缺少真实来源或原始映射必须停止，不以自签成功状态替代。

## 运行入口

下面是后续执行命令，不是本轮已执行记录。工作目录为本仓库根；默认源路径指向本地已验收缓存及备份。可在 `config/local.json` 的 `source` 中显式指定 `cache`、`archive`、`binding` 的绝对路径；不能改科学配方。现有 tar 分片是一个连续流，不逐片解包。

```powershell
$pilotPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python310/python.exe'
$pilotBase = 'D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/learned_onboarding_v1_20261023'
& $pilotPython -m unittest discover -s "$pilotBase/tests" -v
& $pilotPython "$pilotBase/src/service.py" prepare --config "$pilotBase/config/local.json" --source-assets "$pilotBase/results/source_assets" --output "$pilotBase/results/source_prepare"
& $pilotPython "$pilotBase/src/service.py" validate-source --config "$pilotBase/config/local.json" --source-assets "$pilotBase/results/source_assets" --output "$pilotBase/results/source_validation"
```

`prepare` 只装配源身份，不执行模型前向；`validate-source` 做全量源因果资格，不拟合。源资产目录可重复验 SHA，阶段输出必须全新；旧输出存在即拒绝，绝不在其内补写异常文件。CLI 输出限定本目录 `results/` 或 `validation/`，禁止输入／输出嵌套或别名。

真实重计算前必须已有独占执行窗口及原有环境资源封顶。`--execution-slot` 是操作者对执行位置的明确声明，**不会查询远端，也不证明远端已空闲**。本实现不部署、不排队、不抢占既有 worker。资源 preflight 仅使用合成前反向计时，READY 仍是估计；8 GiB 进程树采样守卫和所有 `results/` 累计 2 GiB 输出守卫会在实际阶段继续检查。环境 16 GiB 硬限需由执行环境提供，CLI 不把本机未限制环境冒充已有封顶环境。本轮验收环境为本地 Python 3.10／NumPy 2.2.6／Torch 2.8 CPU；Python 3.9 语法检查不能代替远端 Python 3.9／Torch 2.5 的运行验收。

```powershell
& $pilotPython "$pilotBase/src/service.py" preflight --config "$pilotBase/config/local.json" --source-assets "$pilotBase/results/source_assets" --output "$pilotBase/results/preflight" --execution-slot exclusive-local
& $pilotPython "$pilotBase/src/service.py" fit --config "$pilotBase/config/local.json" --source-assets "$pilotBase/results/source_assets" --output "$pilotBase/results/fit" --preflight-receipt "$pilotBase/results/preflight/resource_plan.json" --execution-slot exclusive-local
& $pilotPython "$pilotBase/src/service.py" calibrate --config "$pilotBase/config/local.json" --source-assets "$pilotBase/results/source_assets" --fit-dir "$pilotBase/results/fit" --output "$pilotBase/results/calibration" --preflight-receipt "$pilotBase/results/preflight/resource_plan.json" --execution-slot exclusive-local
```

preflight 未 READY 时不进入 fit。两辅助头各最多 4 小时，三模块合计最多 2 小时，fit 阶段总守卫最多 10 小时；这些是停止上限，不是预计完成时间。参考不足或残差信号不足时导出 NOT_TRAINED/no-op，继续 CAL 和完整配对，不能自动追加头或换分组。源 FIT、CAL 与新实现代码及数值依赖在后续阶段必须保持绑定。

训练和 CAL 均封存后，才可使用已准备且精确 SHA256 绑定的目标 manifest：

```powershell
# $pilotTargetManifest / $pilotTargetSha 为实际已封存输入，不填占位值运行。
& $pilotPython "$pilotBase/src/service.py" evaluate --config "$pilotBase/config/local.json" --source-assets "$pilotBase/results/source_assets" --fit-dir "$pilotBase/results/fit" --calibration-dir "$pilotBase/results/calibration" --target-manifest $pilotTargetManifest --target-manifest-sha256 $pilotTargetSha --output "$pilotBase/results/evaluation" --preflight-receipt "$pilotBase/results/preflight/resource_plan.json" --execution-slot exclusive-local
```

evaluate 加载目标后，先通过已绑定主头回放确认原分数；WRONG 供体依据元数据固定，学习修正前写 control_plan。EMPTY、无资格和 λ0 精确回退。逐项预测保留完整 UID、原分数／修正分数、决定、原因、代表组件与完整截止，结果包含完整分母、逐设备加权指标和不可达误报下界。

原头仍输出原生产路径的 float32 分数；评价传输基线使用精确提升的 float64，再完成减分与 strict 判决。原分数文件 SHA 保留，回放需与该精确提升逐字节相等；精确回退的比较对象是统一 float64 基线。

以 `FIT_COMPLETE.json`、`calibration.json`、`EVALUATION_COMPLETE.json` 和各目录 `SEAL.json` 判断阶段完成，`status.json` 是限频的运行快照。`EXCEPTION_STOP.json` 保留异常、最后进度、输入身份和已完成项；无自动 resume、覆盖、续跑或第二 seed。源程序更新普通状态文件，不添加 AI 定时调用。
