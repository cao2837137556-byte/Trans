# Edge 正式 worker 与工程验证：实验11独立复核

结果：CHANGES_REQUESTED。原63项测试重跑通过，但确认1项P1、3项P2工程问题，当前版本不直接提交两小时工程验证。
影响：未发现需要重开C5或A/B开发线的证据；须修正依赖身份、资源监督和失败状态。没有产生外部效果，也没有启动超算。
下一步：按下列四项修订并增加针对性回归，重新生成版本绑定的执行卡和增量包，再核定本次工程验证；正式评价仍另行等待真实Linux结果与预算。

## 本轮审查身份与边界

用户在实验11明确要求：本次由新聊天的Codex独立复核实验10交付，下次再交小anti。故本次不以等待Antigravity为阻塞，也不伪称小anti已审查。此前子代理审查仅作历史参考，没有作为本轮结论代用品；本轮未委派子代理。

审查基线：`07ba65e`，工程目录 `runs/edge_formal_execution_v1_20261103/`。工程卡草案SHA `8201968bbc0496d67f2c9f1421107cc53764e455563dcb077677d9e29225c1a7`；正式卡草案SHA `d66edfb94607e8d13bc18fac61b0608ceea9fa2a61905ded0d4433631aa9d527`。本轮未改这些源文件、草案、旧测试回执或原封存结果。

本轮是跨聊天代码及本地工程复核，不能替代同运行时Linux模型恢复验证；未做原包重放、模型载入/训练/前向、外部预测或远端操作。

## 必须修正的具体问题

### R1 / P1：执行身份没有覆盖实际科学依赖

定位：`build_cards.py:19–51`、`engineering_gate.py:55–63`、`worker.py:143–153`。

卡内132件现有pin均与当前本地文件一致，但实际调用的以下文件不在 `artifact_pins`，也不在科学快照绑定中：

- `repo/ood/continuous_input_engineering_v1.py`（adapter实际使用的NumericalContexts）；
- `repo/ood/continuous_features_v3.py`（tokenize/verify_batch/tensor_hash）；
- `repo/ood/query_tail_core_v2.py`（分类器及scores）；
- `repo/ood/legacy_reference_sample_prepare_v1.py`；
- `repo/ood/legacy_unsw_archival_runtime_v1.py`。

这不是说这些文件当前已经错误或被改动。问题是：以后部署或恢复时其中一个文件发生变化，新入口仍可能通过相同执行卡，甚至沿用相同快照绑定。旧863成员包有完整manifest，但新工程入口并未绑定并强制核验该完整基包；`new_encoder`验证的vendor模型树不能覆盖上述`repo/ood`源码。`replay_io`计算当前源码摘要也不等于将其与预期摘要比对，且新`PackedRoleSpool`未使用旧缓存binding。

复现：只在隔离临时目录复制实际卡的pin键集合，使用合成文件及模拟授权；改变未列入的NumericalContexts依赖后，真实 `require_engineering_authorization` 仍接受，`input_binding`前后相等。没有修改真实依赖或创建真实运行授权。

修复要求：将完整本地源码依赖闭包显式封存，或绑定可信基包manifest并在入口与恢复前核验其全部成员，再叠加经核验的增量。科学快照绑定必须包含决定上下文/descriptor/UID/形状的依赖；编码与评价绑定必须覆盖其实际依赖。增加遗漏依赖及其传递依赖变更的拒绝测试。不要仅补这五个名字就宣称完整闭包。

### R2 / P2：父子进程并存期间的内存守卫与回执漏计

定位：`engineering_gate.py:123–136,324–325,347–350`；`worker.py:86–130`。

主工程进程在恢复子进程期间阻塞于 `process.wait(timeout=remaining)`，没有继续调用自身Guard。子进程建立的Guard只统计自身及后代，不统计仍保留完整索引和运行时内存的父进程。最终 `max_tree_rss_bytes` 又只取主Guard的峰值，未合并子进程期间的进程树采样。于是父、子各自都低于上限，而合计超过上限时，应用层可能不拦截，回执仍低报。Slurm硬限制是最后防线，不能代替这项测量，也不能据此认为超算实际已发生OOM。

复现：真实本地子进程只申请64MiB；子进程自身低于合成上限，父子合计超过上限，生产`bounded_process`正常返回，主Guard只报告父进程约35MiB。具体字节见 `REPRO_RESULTS.json/resource_wait`。这证明等待路径有盲区，不是8GiB正式作业的资源预测。

修复要求：最外层监督进程在等待、模型前向和子进程恢复期间持续采样整个作业树或作业cgroup，执行同一累计RSS/墙钟守卫；失败时结束自有进程树。回执明确进程树范围、采样间隔与采样峰值；对子进程短峰值的限制如实披露。增加父子单独合格、合计超限的回归。

### R3 / P2：失败重入后旧PASS回执和进度仍保留

定位：`engineering_gate.py:285–297,356–363,369–388`。

当前实现明确允许重用完整角色spool并使用新recovery attempt。然而新一轮开始时没有更新统一的执行attempt状态；若同输出目录已有上轮`ENGINEERING_GATE_RECEIPT.json=PASS`，新一轮在准备阶段失败，旧PASS与旧`PROGRESS.json=ENGINEERING_GATE_PASS`仍保留，同时新增STOP。STOP也不绑定当前attempt/card。消费者仅核同卡SHA与PASS不能判断这是旧成功还是本轮成功。反向的旧STOP也可能在后续成功时继续残留。

复现：隔离目录放置旧PASS，在真实`execute`编排中的prepare阶段注入故障；得到旧PASS回执、旧PASS进度和新STOP并存。没有运行真实prepare或模型。成功回执写出后再调用可能失败的`guard.progress`也存在同轮PASS/STOP双终态窗口。

修复要求：为整个工程执行而不只是恢复子测试建立attempt身份；历史结果保留在各自attempt目录，稳定入口指向唯一当前attempt。RUNNING/PASS/STOP均绑定attempt、卡SHA和输出身份；最终成功只能在所有检查完成后发布。增加PASS→失败、失败→PASS及成功发布边界故障测试；页面和取回验收以当前attempt为准。

### R4 / P2：外层超时杀主进程后无主scratch清理

定位：`engineering_gate.py:294–296,364–367,381–383`。

`crash/resume`子阶段有精确scratch marker及on_exit清理，但主阶段没有。外层超时调用kill_tree，主进程的finally不会执行；其包含数值数据库的节点本地scratch因此可以残留。最需要处理的就是UDP长重放达到时限的分支，不能依赖Python finally或假设站点一定清理所有/tmp。这里不涉及删除科学spool或已提交编码块。

复现：真实子进程创建64KiB自有临时数据库后等待，调用生产顶层监督路径并把测试deadline缩为6秒。超时STOP成功写出，但没有注册主阶段on_exit，主scratch和数据库仍在，finally标记不存在；测试结束后仅由隔离临时目录清理。该测试不模拟Slurm清理策略。

修复要求：主阶段也记录PID/attempt/output/卡身份和精确scratch路径；监督者确认自有进程树退出后，只清理这些明确拥有的路径，保留进程外持久检查点。若选择保留诊断数据库，应显式登记位置、字节及后续清理职责，不以已清理结束。增加主阶段超时/强杀回归。

## 已通过的独立核验

- 用`python -B -m unittest test_checkpoint test_streaming test_reporting test_budget test_engineering_gate`重跑原63项测试，28.070秒，全部通过；没有执行会覆盖旧回执的各脚本`__main__`入口。
- 132件执行卡pin重新校验一致；35成员工程增量包逐件核对尺寸、SHA以及当前源文件一致。
- 独立读取60,000条已封存查询和4,124参考，重算所有查询的逆纳入权重，而非仅检查两个保存权重互为倒数。正常按跨捕获段同组件累计人口/实际选中数计算；HTTP按互斥层、UDP按场景计算，均精确一致。
- 三角色扩张人口为1,220,126 / 152,352 / 2,898,830；正常17,025组件完整覆盖、组件等权总质量1；64,124逻辑UID互异，参考未进入查询分母。
- 代码核对：C5 p3及p1共用同一support，冻结阈值和seed顺序保持；SYN与零支持回退保持；样本比率、组件权重、已知N的HT估计分列；未选中不作正确阴性；kNN不套抑警子集断言；时间区间明确仅条件敏感性，不能冒充独立事件置信区间。
- 20k版本的计算入口仍硬绑定60,000查询/4,124参考。若未来实测需要按已登记规则缩量，必须另建选择seal并同步修订入口、计数和执行卡，不能仅编辑资源参数。

## 判定与下一步

当前判定是 **CHANGES_REQUESTED_BEFORE_ENGINEERING_GATE**，不是C5科学FAIL，也不是Linux运行失败。先闭合R1–R4再提交短工程验证，避免用超算反复试出这类生命周期问题。本次由实验11 Codex复核已获用户指定，后续状态应写“待修复及本次复验”，不继续写“等小anti批准”；下一次独立复核再交小anti。

修订后原草案/旧审查保留，新版本需绑定本次审查、各修复回归以及真实Linux回执。不得手填Linux PASS或把本次审查变成运行授权。正式外部评价仍未启动，原数据不需要重新下载。

独立证据目录：`runs/edge_formal_review_experiment11_20261103/`，含复现脚本、`REPRO_RESULTS.json`、`METADATA_AND_DELTA_VERIFICATION.json`及本轮审查JSON；全部为小材料。
