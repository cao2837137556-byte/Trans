# 源8 B1/B16 克隆技术诊断：一次运行执行回执

当前状态：**COMPLETE_TECHNICAL_DIAGNOSTIC_POSITIVE**。179591/node185，Slurm COMPLETED、exit 0:0，用时36秒。

用户明确授权原话：**允许执行这一次小诊断**。本回执由此前179536数值停止后的新范围授权产生，不能引用原生产作业授权替代。

固定范围：8条正常源参考、8个B1控制与8组B16克隆，共136前向位置；amd 4 CPU / 16 GiB，Slurm最长600秒，进程树RSS<8 GiB、输出<256 MiB、磁盘空闲>1 GiB，no-requeue、0自动重试。B1必须全部逐字节复现179536后才运行B16。B16先验证16克隆彼此一致，再比较旧向量字节；任何结果仅作技术诊断，禁止生产复用，不自动继续补编码/CAL/A/B。

封条SHA256：`0d6d59c904b6a6e0a29725c99fc628c760e2489fdb2bbbbcf90027bb79c1f1d5`；manifest SHA256：`ae3e5008e91abdb40ea132ef648d95533d546285518d825146366d176bbea746`。封存包不改，真实批准存于封条外私密目录。

提交前超算只读核查：包存在、APPROVED不存在、新部署目录不存在、独立runtime无job_*，没有重复提交。17项科学合成测试及包独审沿用已通过回执，不重复运行。

新提交器固定路径、O_EXCL提交锁、sbatch超时/未知结果禁止重提；进度页保持18770并区分当前技术诊断与179536/179523历史失败。普通隐藏程序同步，无AI持续轮询。原104数值门未放宽，正式21660新增位置、源CAL、新目标评价与训练仍为0。

## 实际执行与回传

用户授权后仅提交一次。新部署提交器18/18离线行为测试、AST与独立静审通过，固定封条验证通过后安装封条外私密批准，O_EXCL提交锁在sbatch前落盘。提交回执见[EXECUTION.json](../../dense_reference_source8_diagnostic_deployment_20261027/EXECUTION.json)，实际时间18:58:06北京时间。状态桥仅固定179591与源8独立runtime，18782仅远端loopback；18770隐藏页已切换源侧技术诊断，并保留179536、179523历史。

已拉回7份原始小文件（RESULT、OBSERVATIONS、ENVIRONMENT、status、launch、DRY_RUN、Slurm log），每份原始字节长度与SHA均核对通过。16份诊断f32原始观察保留超算独立目录，文件长度及SHA索引已回传；未把这些观察作为生产特征或参考库。见[原始结果](../../dense_reference_source8_diagnostic_deployment_20261027/results/job_179591/science/RESULT.json)、[观察回执](../../dense_reference_source8_diagnostic_deployment_20261027/results/job_179591/science/OBSERVATIONS.json)、[字节回传与SHA索引](../../dense_reference_source8_diagnostic_deployment_20261027/results/job_179591/READBACK.json)。Slurm日志只有Transformers device参数弃用提醒，无异常traceback。

## 读数与结论边界

| 核查 | 实际结果 |
| --- | --- |
| B1输入tensor身份 | 8/8等于179536对应hash |
| B1输出控制 | 8/8逐字节复现179536，仍与旧向量不同 |
| B16克隆输入 | 每UID16份均等于同一对应tensor hash |
| B16克隆内部输出 | 8组均16份逐字节相等 |
| B16对旧向量 | 8/8逐字节完全恢复，零容差 |
| 前向总预算 | 恰好8 + 8×16 = 136位置 |
| 外层与调度器 | launch COMPLETE/return0；sacct COMPLETED/0:0/36秒 |
| 新生产补编码/CAL/目标评价/优化器更新 | 全部0 |

这是一次控制变量的正向技术结果：保持179536同一运行时与每条输入tensor，B1复现失败特征，B16恢复旧特征。它将这8条失配指向批次大小影响的浮点计算路径，给出可操作的修复方向；不再需要先假定是数据变化或必需重建旧Python/MKL环境。但本次没有恢复历史真实batch cohort（其中含目标query），不能称历史全队列重放，更不能宣称原104已经通过、所有后续shape都有同样性质或密参考科研效果已改善。

下一步应准备封条外的单样本批次处理修复：对B1形状组采用同一合法样本克隆成B16的候选兼容路径，明确去除重复输出、保留唯一UID与原顺序并增加防重复入库验证；随后仍须对原104独立执行零容差门。修复准备本身可本地完成，任何新增远端前向/补编码/CAL不由此次小诊断授权自动产生。本次授权已用完，0自动重试；没有续跑正式链。

进度普通同步已收到终态并自行退出，隐藏本地页面保留；无AI持续轮询，无新自动化。封存原r2、修复层、诊断包及两次失败现场均保持。

## 独立结果审计

本地独审PASS，见[独立审计](../../dense_reference_source8_diagnostic_deployment_20261027/results/job_179591/analysis/SOURCE8_RESULT_INDEPENDENT_AUDIT_179591.md)。独审直接使用密封EXPECTED8.f32中每条旧3072字节重复16次，重算8个整组文件SHA，全部等于远端B16_CLONE原始f32的文件SHA；不只相信程序输出的8/8标签。136个输入tensor hash、8个B1失败控制、B1/B16顺序、16组观察、预算与7份原始回传以及外层/调度器终态均一致。审计仅本地读取，零额外前向或远端操作。

最终进度验收：179591 COMPLETE、scope仅源8技术诊断；sync进程已自然退出，dashboard隐藏进程正常，历史页保留。见[最终进度验收](../../dense_reference_source8_diagnostic_deployment_20261027/FINAL_PROGRESS_ACCEPTANCE.json)。
