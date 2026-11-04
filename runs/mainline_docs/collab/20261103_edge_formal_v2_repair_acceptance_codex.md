# Edge v2修复验收（实验11 Codex）

结果：实验11独立复核的R1–R4已修复，82项本地检查全部通过；60,000条选中查询元数据核验通过。
影响：原v1源码、执行卡与CHANGES_REQUESTED复核原样保留。C5/p3、阈值、20k×3查询seal、4,124参考、编码与统计口径未改；尚无新外部效果。
下一步：具体授权后执行同运行时1CPU/8GiB/2小时Linux工程验证，再依据真实资源和恢复结果决定正式预算。此次修复没有提交超算任务。

## 修复及证据

| 问题 | 修复 | 验证 |
| --- | --- | --- |
| R1 / P1：依赖身份缺失 | 原863件基包+完整repo/ood、hnr和v2源码目录清单；执行入口与spool读取前均检查；全依赖进入科学输入绑定。 | 缺失pin、改动传递依赖、新增/删除模块、基包改字节均拒绝；v1绑定及变化后的v2绑定不能打开已有spool。两张卡各960件pin，基包+113成员增量覆盖全部。 |
| R2 / P2：父子RSS未合计 | 最外层监督进程持续采样自身及全部后代，包含等待恢复时驻留的主进程；最终回执使用监督层资源数据。 | 真实子进程测试：各进程单独低于限制、合计越限时STOP；峰值时分进程RSS和最大采样间隔可追溯。 |
| R3 / P2：旧PASS/新STOP并存 | 整轮attempt_id、卡SHA和输出锁；唯一CURRENT原子指针；子进程候选成功经监督层最终检查和清理后才发布PASS。 | PASS→准备失败→PASS、缺卡/草案重入、候选后失败、最终进度写失败、并发目录、篡改候选/回执均覆盖；历史PASS不再表示当前通过。 |
| R4 / P2：主进程超时scratch遗漏 | 监督层预登记三个阶段精确目录；终止并等待所有所属进程后按所有权清理。 | 真实主进程+后代超时，所属scratch全部移除，其他目录和持久spool保留；所有权不匹配或进程退出未确认时拒绝清理并STOP。 |

[本地验收JSON](../../edge_formal_execution_v2_20261103/LOCAL_ACCEPTANCE.json) · [82项检查明细](../../edge_formal_execution_v2_20261103/LOCAL_REGRESSION_RECEIPT.json) · [新增故障回归](../../edge_formal_execution_v2_20261103/REPAIR_REGRESSION_RECEIPT.json) · [统计元数据核验](../../edge_formal_execution_v2_20261103/STATISTICS_METADATA_VERIFICATION.json)。

原63项基础检查保留并适配新接口，新增19项故障回归。最终完整回归耗时42.094秒。首轮完整回归的79项中78项通过，1项测试在内存守卫停止子进程前未拿到子进程诊断文件；这是测试观测竞态，改用监督层实际RSS观测后通过，原FAIL保留在v2/validation_history/first_full_run，不覆盖成PASS。

## 身份与交付

v1的38件sidecar对应工件全部保持原SHA；checkpoint、streaming、evaluate、reporting、budget及5件既有元数据/探针证据与v1逐字节相同。两张v2卡共享同一科学输入绑定；测试源码SHA、所有基包文件、卡pin、tar成员大小与SHA已复核。

v2工程卡SHA：`8a89aca64f6fd792059ecf7df0073de08a60cfc8b4dd0836fcce3479e9b0110b`。
v2正式草案SHA：`1f584ff657bead6c0b747cac2291421db33160199c7eef0ad972ef5743284ccf`。
增量tar：113件、34,539,520字节，SHA `84078a414ca7ddabe9379db7e2c31e69186c607bfa0cf3b7327ef12ffd2ff0ff`；[交付清单](../../edge_formal_execution_v2_20261103/DELIVERY_DELTA_MANIFEST.json)。增量补齐原基包外依赖和既有小型历史证据，不重新打包模型/原PCAP；tar、数组、census正文不进Git，保留清单及SHA。

[工程卡草案](../../edge_formal_execution_v2_20261103/ENGINEERING_GATE_CARD_DRAFT.json) · [正式卡草案](../../edge_formal_execution_v2_20261103/FORMAL_EXECUTION_CARD_DRAFT.json) · [状态读取、检查点兼容性与运行说明](../../edge_formal_execution_v2_20261103/README.md)。

## 验收范围

本次是用户指定的实验11 Codex对实验10 v1进行独立复核后修复、自验；不是小anti对v2的独立审查。下一次独立复核由小anti承担，本次不等待他。旧v1的CHANGES_REQUESTED仍是其历史结论，新v2结论为PASS_LOCAL_REPAIR_LINUX_GATE_PENDING。

本地测试在Windows/Python3.10执行，包括真实轻量子进程终止、文件恢复和真实核心的小型合成距离运算；没有加载冻结模型、没有计算外部质量、没有提交云任务。Linux进程组、冻结encoder重启、UDP末段资源及完整批吞吐仍需同运行时实测，不能把82项本地通过或旧181418当作该项PASS。卡仍是未授权草案。

v1 spool因缺少完整依赖身份不自动复用；使用新的v2输出目录。已完成v2角色只在完整代码/运行时/原数据/seal一致时复用。RSS与磁盘是采样观测而非瞬时严格峰值；若监督进程本身被SIGKILL，CURRENT保持RUNNING，不能将历史PASS当作成功。
