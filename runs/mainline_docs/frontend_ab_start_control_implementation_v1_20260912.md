# AB 起点 C0_AB/R_AB：实现与合成验收

2026-09-12。状态：IMPLEMENTATION_SEALED / GENERATED_ACCEPTANCE_PASS / REAL_T_E_NOT_STARTED。
用户明确授权“动手实现”。本轮完成执行器、启动/状态脚本和生成数据验收，不新增真实训练或评估授权。
冻结设计和配方保持原字节；未修改旧模型、旧执行器、八项无关修改或任何历史实验结果。

## 实现结果

- 两个新臂从同一封存AB完整student独立开始，空AdamW，C0_AB复用原C0更新，R_AB复用原R更新。
- 原标签/保护/教师损失及随机顺序不变。R保留原Aguard，允许AB起点保护loss非零；C0无教师/保护调用。
- 没有新P。T入口按旧生产SHA核验并直接消费封存margin/scale/teacher/guard；不derive、不重新估计尺度、
  不重新物化教师。AB原生终态、receipt、文件及state身份逐项核对。
- 固定两个终点封存后才E；旧A/AB/C0/C1/C2/Q/R/P2只引用保存分数，独立新臂名避免覆盖。
- E完整报告固定点攻击/future/逐族/逐OOD池/A-B/ID、翻转、原六项有理数比较、1%/0.1%尾部组成。
  C0的教师/guard拟合仅为E的TRAIN终点观察，不是其训练项，也不增加forward。
- Windows持久Job监督、追加进度、终态/封存核验和状态页面复用既有可靠机制；异常停止、零重试。

新模块位于 `repo/ood/issue27frontend_abstart_{support,model,reuse,train,evaluate,verify,control,fixture,tests,build}_v1.py`。
启动脚本：`scripts/start_frontend_ab_start_control_v1.ps1`。
状态脚本：`scripts/show_frontend_ab_start_control_v1.ps1`，查询不加载模型或启动计算。

## 验收证据

最终 **35/35 PASS**，耗时 13.500 秒；两份PowerShell脚本解析PASS。
第一轮29项全部通过；静态收尾发现旧P描述残留，已修正，并补齐行/符号/生产消费身份及超时检查；
最终35项在最终代码上全部通过。没有真实实验失败或重试，没有重复真实资源试验。

覆盖包括：
1. 任意生成状态上的C0/R连续三步与原实现参数、投影、AdamW状态、clip及loss完全一致。
2. 完整新生成资产的真实T/E函数路径、结果重读核验、两臂独立起点/同预算、历史引用不覆盖。
3. 零教师C0、R非零初始guard合法、D零初始化不耗RNG、原student输出一致与早期目标因果性。
4. 缓存生产SHA/新消费SHA区分、文件篡改/UID映射/错误margin符号/尺度拒绝；禁止derive及额外forward。
5. 整组ties、不强填误报预算、AUROC对照、有理数判读、AB尾部描述独立于科学SUCCESS。
6. T→E正常转移无需二次许可，授权缺失/旧token/重复尝试拒绝，缺候选禁止E。
7. Windows实际生成进程的成功/失败/墙钟预算停止、零重试、结果封存、打开状态文件的并发读兼容。

进程级审计钩子禁止读取真实runs数值文件（包括真实JSON与checkpoint）；测试仅使用临时生成数据。
原教师派生函数仅用于制造合成生产者资产，新生产执行路径没有派生调用。
验收中真实teacher/student forward、optimizer更新及真实训练侧教师行读取均为0。
这证明实现符合冻结规则，不证明新模型科学能力已改善。

## 封存与入口

实现包：`runs/frontend_ab_start_control_implementation_v1_20260912/`。
SHA256SUMS SHA256：`03f0091297052b0a4e0d8816bea424e5f3a48faff3cfecf450d0baa2635c34c2`。
封存47项源码/文档/脚本依赖；config/acceptance/README由包manifest覆盖。
`check-implementation`返回 `IMPLEMENTATION_READY_NO_REAL_EXECUTION`。
真实状态脚本返回 T=NOT_STARTED、E=NOT_STARTED。两个真实新输出目录均未创建。
分支codex/exp-mainline、HEAD4b28747b09480471e2bac1beb3a9badf27280efb保持。
原封存代码、运行时pin和8项无关tracked文件hash核验通过。

## 下一执行边界

实现完成。下一步可明确授权一次完整T→E：复用旧P的入口核验通过后，C0_AB/R_AB各20轮、3940步，
再各一次固定终点评估，共7880更新/560632终点目标呈现；正常转移不重复询问。
科学表现差仍完成并封存全部终点；真实异常停止且不重试。无新数据、HPC、搜索或LLM轮询。
下面命令只作为未来明确授权后的执行入口，本轮未调用：

```powershell
./scripts/start_frontend_ab_start_control_v1.ps1 -Stage TE -AuthorizeTraining -AuthorizeEvaluation
```

任意时候可只读查看：

```powershell
./scripts/show_frontend_ab_start_control_v1.ps1
```

继承历史FAIL、联合NOT_REACHED、新设备入网NOT_EVALUATED保持。既有1% OOD工作点不变成新绝对门槛。

solved: AB起点两臂实现、生成验收、封存及只读入口核验完成。
changed_mainline: yes（实现就绪；没有真实新结果）。
active_blocker: 核心联合能力未解决；真实T/E尚未授权执行。
frozen: AB对照设计/配方及此实现包；全部历史产物原样保留。
superseded: 顶部“实现下一步”状态，现在实现已完成。
next_action: 明确授权一次真实T→E后执行，异常停止零重试。
