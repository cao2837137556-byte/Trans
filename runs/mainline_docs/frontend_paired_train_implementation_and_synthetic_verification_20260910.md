# 双臂训练实现与合成验收

2026-09-10。范围：用户授权实现，不授权真实特征准备或真实训练。
状态：实现完成，57/57 生成检查与 2/2 PowerShell 解析通过；真实准备/训练均未启动。

## 已实现内容

新增 `repo/ood/issue27frontend_paired_train_*_v1.py` 模块：标准库元数据/计数支持、
模型与优化、结果判定、阶段 worker、监测控制、验收工具、数值测试、独立监测器测试。
新增启动/查看脚本 `scripts/start_frontend_paired_train_local.ps1` 与
`scripts/show_frontend_paired_train_status.ps1`。

实现严格使用冻结配方及 V3 合格名单：131→64 GELU→GRU128→64 GELU→1，
全部 91,265 参数训练，无辅助头、无旧 checkpoint 初始化、无教师前向。
共同 seed2705 新初始化已封存为 initial.pt/initial.receipt.json；该初始化不依赖
任何真实特征，也不是训练产物。实际训练重新按指定顺序构造并核对同一 state hash，
再在任何更新前 deepcopy 为 A/AB 两臂。

训练各 40 轮、197 步/轮、7,880 更新/臂；AdamW 全参数、BCE 上下文均值、
全 owner 分母及 B 权重 1 不变。A 顺序、次数、梯度权重两臂一致；B 按最多 32
上下文的微批累积，整步只裁剪/更新一次。没有检查选轮次、早停、阈值调整或续训。

两臂末轮权重及候选屏障先封存验证，随后每臂一次训练内拟合检查和一次共同
check 检查。按 owner/标签、攻击族、设备族、source/member、context、component
与训练覆盖报告分母、目标/上下文错误、旧正确变错、旧错误变对及 A→AB 翻转。
训练内结果单独保存；共同检查由标准库监督器重算判定，零分母为 NOT_ESTABLISHED。
详细结果单独封存；worker_terminal 只放小摘要，避免超过 64 KiB 接收限制。

## 输入身份与精确计数

仅通过已授权合法元数据 join 18,266 目标/12,889 上下文；没有读取真实特征数值。
F4 目标审计和 outer 逐 UID 前缀 receipt 均固定 SHA，A 的 attack_hard/benign
分类参考逐 UID 与冻结合法账核对，旧模型不运行。不得读取旧 select/viewed/report/FINAL。

真实准备只复用两个已有 float32 小端数组：F4 parent 107,666,280 字节、outer
2,705,936 字节，共 110,372,216 字节；先分别做完整身份 SHA，再读取合法上下文
范围，每目标前缀 SHA 与已存审计一致后写入新顺序数组。校验 finite、宽度131、
前缀范围、角色和依赖分量一致。所有源内容身份值来自旧封存记录，本轮没有新读取它们。

| 精确动作 | 训练 | 终点拟合/检查 | 合计 |
|---|---:|---:|---:|
| 上下文事件 | 12,017,520 | 348,390 | 12,365,910 |
| padding 槽位 | 111,883,555 | 1,276,107 | 113,159,662 |
| 监督/检查目标呈现 | 979,000 | 30,861 | 1,009,861 |
| 上下文呈现 | 674,760 | 21,481 | 696,241 |

精确数组偏移、目标前缀、类别参考、轮次顺序哈希和计数已封存于 plan.json，
训练部分逐项与 V3 schedule.json 一致。事件量未超冻结 13,664,708 上限。
所有已选目标按新用途属于暴露过的开发数据，不是独立确认集；B 攻击检查为 0。
后续可检验旧攻击继承与 B 正常误报增量，不能声称证明 B 新攻击泛化或设备入网能力。

## 生成验证及工程纠正

数值/输入/结果测试 47/47，独立标准库监测器测试 10/10，共 57/57。
覆盖完整微型 40 轮双臂实验、精确行动计数、共同初始化、因果前缀、排序还原、
隐藏状态重置、全部模块梯度、全 owner 归一、B 大桶微批、A 监督隔离、
模型检查屏障、old-reference 漂移、跨角色依赖、缺失目标、SHA/前缀漂移、
零分母、旧正确回退、B 攻击退化对正常收益的保护、结果摘要大小和篡改拒绝。
监测器测试覆盖缺失授权、已有目录禁止重启、失败/成功封存、超时、输出超限、
篡改 seal 与 Windows Job 拒绝额外进程。两个 PowerShell 脚本解析通过。

初始综合测试 42/45 时有 3 项监测器 fixture 失败：测试进程已加载 PyTorch，
超过原监测 fixture 的 192 MiB 保留量。改为独立标准库进程运行监测测试，
与真实控制器一致，未抬高那些 fixture 的内存门槛；初始日志原样保留。
元数据初读还发现 F4 布尔值为小写 true，修正解析后完整 join 通过。
审查发现详细 verdict 可能过大，改为详细表+短终态并加回归测试。
这些都是验收前工程纠正，不是科学结果，也未重跑历史实验或资源试验。

## 可见状态与两个后续授权入口

真实目录分别为 `runs/frontend_paired_train_preparation_v1_20260910/` 和
`runs/frontend_paired_train_v1_20260910/`，本轮均不存在。状态脚本显示阶段、arm、
epoch、updates、耗时和验证后的最终结论；正在 SEALING 不当作已完成。

下一步推荐明确授权**一次真实特征准备**：两个数组身份校验与合法范围读取、
110,372,216 字节新特征视图及全部前缀核验；不做优化器更新、模型推理或原始包读取。
该准备阶段独立工程上限为 1,800 秒、聚合 8 GiB、新输出 256 MiB、一个 worker、
零重试，不计入训练时间。这是具体待授权范围，不是已获授权的执行。

准备完成封存后，另行授权一次 A/AB 训练和固定终点检查：原冻结 14,400 秒、
聚合 8 GiB、新输出 512 MiB、一个 worker、零重试。两个阶段都采用 Windows Job，
控制器保留 512 MiB 用于标准库逐 UID 结果重算，其余内存属于 worker；聚合上限不变。
沿用已验证 V3 有界原子文件替换和目录采样修复；持续异常保留终态停止。

命令入口（当前未执行）：

```powershell
.\scripts\start_frontend_paired_train_local.ps1 -Stage prepare -AuthorizeFeaturePreparation
.\scripts\show_frontend_paired_train_status.ps1 -Stage prepare
```

训练入口使用 `-Stage train -AuthorizePairedTraining`，准备授权不会开启训练。
没有 HPC、K、新设备、下载、超参搜索或改变冻结规则的授权。

实现包：`runs/frontend_paired_train_implementation_v1_20260910/`，见其 SHA256SUMS、
execution_config.json、synthetic_acceptance.json、final_verification.json。
封存后只读就绪与最终工作区校验见
`runs/frontend_paired_train_implementation_final_v1_20260910/`。
