# 冻结表示上的检测头留一设备验证：阶段 A 协议

日期：2026-10-10。回应 Claude 的 `20261010_query_tail_assessment_followup_claude.md` 第 3 节及 `20261010_query_tail_objective_decision_ack_claude.md`。本协议独立于 QUERY_TAIL 新版包，状态为 **设计已登记、实现与执行未开始**。审阅重点是折内隔离与下文事先冻结的复现判据。

## 1. 问题、范围与阶段顺序

阶段 A 检验：只用其余五台源设备训练并做源侧校准时，留出设备的正常误报是否膨胀。固定六折、RECENT/BCE、seed 27、40 轮，不选折、seed 或中间 checkpoint；不加入 QUERY、TAIL、REFERENCE 或入网正常模块，不访问 CIC_DEV、UNSW_DEV 或历史保护池。

这是**冻结 E3 表示上的检测头源内开发检验**。六台设备已参与全源训练和方法开发；E3 的预训练暴露排重尚未完成，不能称为整套模型的未见设备验证或未消耗独立确认。单 seed 六折不能替代三 seed 稳定性证据，3% 判据也不替代主实验的 1%/2% 科学验收门槛。

执行顺序：先完成 QUERY_TAIL 目标函数与日志联合修订及审查；父缓存恢复并通过完整性核验后，运行其主实验，再运行本阶段。当前只起草协议，不运行真实头训练或前向。

## 2. 折内隔离：审阅清单

**集合与身份。** 每折留出一台设备；训练仅为另五台的原 FIT，校准仅为另五台原 CAL 的正常查询。留出评估为该台全部非 REFERENCE 查询，即原 FIT∪CAL；不因稀疏或成绩改用旧 CAL。沿用父 run 的 row/UID 顺序和既定 component FIT/CAL 角色，不随机切包、重分割或跨设备借样本。component 仍依据物理 owner 与规范双向五元组、跨 capture 保持身份；session 层级仍包括 capture。留出设备的所有行不得进入 normalizer、优化器或阈值。

**归一化。** 复用 Job177891 的未归一化 current-inclusive RECENT 父特征，仅读前 768 维。每折在五台 FIT 上重拟合普通逐行均值和总体标准差，完全不使用层级权重；匹配 `continuous_model_v3.fit_normalizer` 的 float64、4096 行方差合并、`sqrt(m2/N)` 和最低 scale `1e−6`。输出归一化后 float32。不能复用全六台 normalizer，不能用已归一化值冒充原始值。CAL、留出查询只应用本折参数。

**三套权重。** 各集合独立按 `device→activity→capture_id→session_id→row`、仅非空分支重算：

- 五台 FIT：每类条件权重和为 1，再分别乘 0.5；总训练质量为 1，与原 BCE 口径一致。
- 五台 CAL 正常：条件权重和为 1，仅用于本折源阈值及 CAL 正常指标。
- 单台留出评估：正常、攻击各自条件权重和为 1；类内指标分别计算。报告活动/协议切片时在该切片内重算条件权重，同时给整数 TP/FP 与分母。

不沿用全源 `label_metric_weight_denominator` 作为折内权重；不对当前 batch 再归一化。保存各集合 UID、行数、权重摘要/SHA 与分支 census。空活动或协议切片记 `N/A_NO_SUPPORT`，不记 100% 召回或零误报。

**初始化与训练。** 每折从相同 seed 27 的**未训练** `Linear(768,128)→ReLU→Linear(128,1)` 初始化，98,561 个参数；不从已见过留出设备的全源 R0 checkpoint 起步。各折初始化参数 SHA 必须相同。BCE 为 `N/b × Σ_batch w_i BCEWithLogits(s_i,y_i)`，每行每轮访问一次，batch 256、40 轮、最后不足一批照常更新。CPU torch 独立 shuffle generator seed 27；各折原 FIT 顺序先过滤，再 `randperm(N)`。AdamW 沿用 lr `3e−4`、weight_decay `1e−4`、betas `(0.9,0.999)`、eps `1e−8`、amsgrad/foreach 均 false。只评价 epoch 40，无续跑寻优。

**阈值与评价。** 对每折 epoch 40 头，仅用其五台 CAL 正常，在本折条件权重下调用父 `continuous_model_v3.threshold`：取使严格上尾加权 FPR≤1% 的最低可行观测 logit，按 `score > cut` 判攻击，不插值。一个折只用一个源阈值，不做留出设备阈值、不用留出标签选 cut。随后固定头与阈值，评价留出全部查询；源 FIT 与源 CAL 的类指标只作训练/校准一致性诊断。留出表现不能影响 checkpoint、seed、阈值或已登记配置。

**结构性停止。** 在任何优化更新前，核验父 manifest/SHA、float32 原特征维度、LEARN UID 与数组精确逐行 join、原 FIT/CAL 身份及行数、owner/component 一致性、集合 UID 不交叠、训练与校准 component 不交叠、无 REFERENCE/目标行、训练两类及 CAL 正常非空、特征/均值/scale 有限、scale 正值、权重质量守恒。任何不符则停止该整轮验证，不能补标签、借缓存或自行删行。对原划分中与合法早期 REFERENCE 共 component 而进入 FIT 的查询，保持父规则；REFERENCE 本身不入本阶段。训练中非有限损失/梯度/参数同样停止。结构检查通过和 CAL FPR≤1% 均是有效性条件，不等于留出迁移通过。

## 3. 已有覆盖与固定预算

下表复用 20261010 Codex 回复中已核对的源元数据，不重做旧诊断。正常和各攻击列为留出设备的旧 FIT+CAL 行数；训练 FIT 为另五台行数。

| 留出设备 | 正常 | TCP 活动攻击 | UDP 活动攻击 | Hydra 活动攻击 | 本折训练 FIT | 本折 CAL（两类） | 每轮 batch | 40 轮更新 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Amcrest Camera | 41,177 | N/A | N/A | 108 | 584,881 | 140,561 | 2,285 | 91,400 |
| ArloQ Camera | 46,756 | 3,006 | 17,324 | N/A | 564,070 | 135,571 | 2,204 | 88,160 |
| Atomi Coffee Maker | 3,930 | 6,049 | 16,674 | N/A | 596,098 | 143,976 | 2,329 | 93,160 |
| Globe Lamp | 1,107 | 6,179 | 15,591 | N/A | 599,323 | 144,527 | 2,342 | 93,680 |
| Philips Hue Bridge | 61,268 | 185,231 | 16,864 | N/A | 405,868 | 97,496 | 1,586 | 63,440 |
| SimCam | 13,402 | 331,485 | N/A | 576 | 339,300 | 81,964 | 1,326 | 53,040 |
| 合计 | 167,640 | 531,950 | 66,453 | 684 | 3,089,540 | 744,095 | 12,072 | **482,880** |

六折训练都保留 TCP/UDP/Hydra；留出 Amcrest 或 SimCam 时，训练 Hydra 只来自另一台。Globe 正常旧 FIT/CAL 仅 21/5 个 component，SimCam Hydra 仅 12/6 个 component。执行时必须输出各活动 capture/session/component 数、权重 ESS；包行或 ESS 不当作独立样本量。TCP 活动不含 Hydra，协议 6 切片则含 Hydra。

阶段 A 共六个新头、123,581,600 次 FIT 行访问；不含校准/评价前向成本。`482,880=40×Σ_f ceil(N_f/256)`，不能把全源单头的 96,560 次更新直接套给每折。无 TAIL 抽样/扫描、无 q 读出。

父全 role float32 794 列载荷约 3.24 GiB；阶段 A 只需 LEARN 查询：766,727×794×4 字节约 **2.268 GiB**，若事先合规导出仅前 768 列，载荷约 **2.194 GiB**，另加 manifest/UID/元数据。缓存载荷不等于峰值 RSS；metadata、float64 归一化块和并发还需计入。本地能否跑尚未决定，现有 trainer 固定全源 FIT 行数、角色与主实验包，须另做六折 runner 和资源适配，不能直接运行原命令。

## 4. 事前冻结的复现判据：审阅清单

定义本阶段的描述性复现事件：**全部六折有效完成后，至少 2 折的留出设备加权正常 FPR≥0.03，且该 FPR 均在该折固定的五台源 CAL 1% 阈值下计算。** 比较用未舍入数值；等于 3% 计入。不看 CIC/UNSW 来调整判据。3% 是开发路线触发界，不是显著性水平或主实验成功界。

固定输出 `reproduced_fold_count`、六折各自 cut/CAL FPR/留出正常 FPR/攻击召回及分母，另给六设备正常 FPR 的等设备均值与中位数。判据只看各折条件加权正常 FPR，不以行数合并 FPR 替代。所有攻击召回、协议/活动覆盖和 source FIT/CAL 类指标同时报告，不因正常 FPR 高而省略攻击结果。不会以攻击表现好坏改写正常偏移是否复现。

- 六折有效完成且计数≥2：`SOURCE_DEVICE_FPR_SHIFT_REPRODUCED`。
- 六折有效完成但计数<2：`NOT_REPRODUCED_BY_FIXED_STAGE_A_RULE`；只表示这六折/这个 seed 未复现，不能推出外部目标无偏移或源侧方法都无效。
- 任一折结构/数值失败或未完成：`NOT_ASSESSABLE_INCOMPLETE_OR_INVALID`；不可用剩余折宣布复现或不复现，也不默默重试、换折、换 seed。

保存全源 R0 的父 CAL 分数可作历史背景。当前本地并没有父 R0 对所有旧 FIT 的逐行终点分数，不能声称具备“全部留出查询上的全源头 vs 折头”配对基线；此类新前向若以后需要，须另登记，不能混入本阶段复现判据。

阶段 B（R1/QUERY_BCE）只在阶段 A 的上述复现事件成立时安排，六折、相同 seed/epoch/batch，另加 482,880 次更新及合规 q/snapshot 依赖，先另立实施合同与配对比较判据。阶段 B 的触发不使用目标数据或阶段 A 的逐折挑选。未触发不等于 R1 无效；复现也不能证明入网模块在实践或理论上是必要条件，任何结构仍需自己的对照。阶段 A 不自动提交阶段 B 作业。

## 5. 依赖、交付和 Claude 审阅入口

可共享只读父 E3 特征，不重跑 E3、解码或缓存替换；只恢复“current-inclusive RECENT”对应 sealed manifest 的缓存，旧 early-prefix 特征不能代替。完整性凭据引用 Job177891：LEARN UID `5ed3b2bb21970ecc29cdb288ac3a58522cef784207dcbf1164478440b515ef23`；input manifest `d8ea248436cb95686ea747a5dbe0cb71323f1dfed31579be9cfb1a3e6e6b2009`；feature manifest `259ef4eadac38a4be0a30d79bd55b4513cf01a96a90ee9577a3a51c28100b040`；原源元数据 SHA `295a714ab573baf50086464d0c5e97ddfa9ca9e065a06cf282037df75541ae91`。各折实际 UID/component/normalizer/权重摘要由未来 preflight 生成并封存，当前未声称它们已经计算。

设计合同：`runs/legacy_lodo_stage_a_design_v1_20261010/design_contract.json`。它不覆盖 QUERY_TAIL v1/v2 合同、包或原科学门槛，也不是运行包。下一步是 Claude 审阅第 2、4 节；实现时再对照冻结合同补合成隔离验证、输出格式和独立 P/T/K/导出包。

日常交付沿用普通 Work 模式：Codex 提供完整工作目录、上传包、校验 SHA、单条可复制超算命令、阶段状态和回拉命令；用户上传/提交/回拉，Claude 只审约定范围。当前没有远程作业或本地执行指令。父缓存是否可恢复及本地峰值内存仍是未决执行前提。
