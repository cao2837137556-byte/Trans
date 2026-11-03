# 2026-09-30 项目接续摘要

用途：本次按用户要求阅读近期文档、协作约定和超算交付流程后的导航。不是新设计、科学结果或执行授权；当前科学状态仍以 mainline_handoff.md 顶部及对应结果证据为准。

## 工作区与目标

- 活跃工作区为 kitnet-exp-mainline；本次实际核对分支 codex/exp-mainline、HEAD 4b28747b09480471e2bac1beb3a9badf27280efb。
- 工作区有大量未跟踪实现/文档、两份已修改的主索引，以及 runs/issue27by_runtime_optimized_1m_or_slurm_materialization_2026-06-12/ 下八项旧修改。不能因 HEAD 较旧判断近期工作不存在；不得清理、覆盖或混入无关变更。
- 研究目标是新设备/采集环境下高攻击检出与低正常 OOD 误报同时成立，入网适应不能以撤掉正确攻击告警换取低误报。不是无限复刻旧系统，也不默认要求完全新攻击机制。

## 最新状态与难题

- v3 Job177891 已完整执行并拉回验证，耗时18:34:26；工程完成，冻结完整方案在 CIC/UNSW 均科学 FAIL。
- UNSW 原冻结加权口径：RECENT 攻击99.9849%、正常FPR21.2832%；加26维状态攻击降至90.7491%；完整学习参考方案攻击35.0251%、FPR7.4092%，三设备攻击全漏。RECENT保留为开发基线，当前STATE/LEARNED暂停部署候选。
- 固定RECENT分数每设备FPR≤1%的事后攻击上限96.6038%；更宽松地允许每设备≤2%且忽略池级≤1%，上界仍仅97.5301%，Samsung92.1361%。因此每设备一个标量阈值不能满足原池级99%/设备97%攻击目标。此为DEV标签诊断，不是部署校准。
- 最新重叠诊断：Samsung占63.08%加权攻击损失；83.57%损失在攻击开始≥60秒后；剩余加权正常误报90.38%来自ACK/数据查询。目标攻击为入站SYN&&!ACK；源FIT TCP攻击载荷查询占比下界80.54%仅是未加权线索。
- 优先研究攻击阶段监督/困难正常约束与当前查询证据的匹配；不认定H1覆盖不足或H3监督失配已证明，也未完全排除H2实际窗口信息不足。全量窗口描述仍需远端封存snapshot支持。
- 下一步性质为有针对性的文献核对和学习修复设计；不是再次整链训练、阈值扫描或直接换前端。独立ID NOT_RUN、历史holdout关闭、论文仍暂停；已消费开发池不能恢复独立确认资格。

## Claude 与日常协作

- 用户本次明确告知：Claude 当前 token 已耗尽，暂不可用。不能声称它正在审查或已批准新方案；这也不等于对未来所有审查的永久豁免。
- 既有分工：Codex与Claude讨论新问题，Codex实现/打包/交付，Claude按需审查，用户负责目标和关键取舍及上传/提交/拉回。
- 沟通文件在 runs/mainline_docs/collab/YYYYMMDD_<主题>_<claude|codex>.md。单写者：Codex维护实现、交付与handoff；Claude通常只写讨论审查文件。涉及协作时给用户附简短可转述文本；不自动发送外部消息。
- Claude恢复前，继续已授权分析、设计和必要验证；如具体新任务确需其审查，明确待审范围与风险，不伪造审查。v3曾获用户明确豁免，后来也有20260929_continuous_repair_v3_review_claude.md通过记录；这些都不是下一包的通用许可。
- 独立判断、先证据后方案；新模块必须有单一职责、可消融且对应已证实问题。不要只靠堆模块、挑seed、改门槛或把技术选择全部推回用户。
- 已授权完整链内不反复索要逐阶段许可；新范围按当前用户授权处理。冻结文档不原地改写，详细证据留专题/run，主handoff与experiment map保留简短最新索引。

## 超算交付惯例

1. 先明确本次范围、输入角色/身份、资源、结果与停止条件；复用现有数据和编码器，不反复上传大文件。整链需要的预检并入正式作业，不另起只有预检的长作业。
2. 唯一版本化交付目录及tar.gz；提供字节数、外部SHA、内部SHA256SUMS、合同和源依赖闭包。LF字节审计、干净解包、Python3.9兼容/导入、Bash语法、合同/回归、安装拒绝覆盖/篡改、模拟提交流程均在交付前验证。
3. 每次给完整绝对路径、无占位符的命令，明确终端：本地PowerShell调用transfer脚本Upload；已登录VS Code超算终端用纯Bash验证/安装/单次提交/status；本地PowerShell调用Pull。安装与提交分开。
4. 当前参考实现使用WSL Ubuntu-24.04 rsync -t --partial --append-verify --info=progress2 --human-readable；SSH公钥历史上被拒绝，不能假设无人值守免密已恢复。不在命令/文档写密码。
5. 历史远端工作根/public/home/jiangxinwei.zr/work；v3使用kitsune/env/kitsune_py39/bin/python。环境复用受控入口scripts/00_env_issue27ckc.sh，依赖须在实际计算节点验证；不擅自pip/重建环境。
6. v3资源64CPU/192G/72h、16特征/4训练进程，仅为历史合同而非新任务默认值。batch MaxRSS约40.94GiB不等于整个进程树同步峰值，不据此机械降资源。
7. 防重复提交，持久日志、明确退出码、阶段/完成量/总量/首错；心跳和CPU忙不等于有效进展。COMPLETE与scientific_gate分开。失败零自动实验重试，先拉回诊断；传输续传不等于实验重跑。
8. 拉回先验外包SHA，再验manifest/逐文件、UID分母及决定算术。大型feature/SQLite可按export_manifest留远端；需要时只取必要证据。尾部导出失败只修尾部，不自动重训。sacct包含step、不用-X，记账与程序RSS交叉解释。

注意：v3 OPERATE_HPC.md是封存时的历史说明，其中“待审/未授权”已被后续授权、复审和Job177891完成事实覆盖；只作为命令结构参考，不再次运行。

## 首选阅读入口

- mainline_handoff.md（顶部）、mainline_experiment_map.md。
- mainline_workflow_and_hpc_continuity_20260909.md。
- claude_codex_collaboration_20260928.md（含09-29补充）。
- legacy_continuous_input_job177891_result_20260930.md。
- legacy_continuous_input_job177891_overlap_diagnosis_20260930.md。
- collab/20260930_job177891_joint_discrimination_reply_codex.md。
- hpc_failure_ledger_and_launch_gate_20260725.md（通用门槛，本次未逐条重审全部历史案例）。
- ../legacy_continuous_input_repair_delivery_v3_20260929/OPERATE_HPC.md及transfer_v3.ps1。

本次仅阅读项目文件、核对Git状态并新增本摘要；未运行真实实验、未连接超算、未修改旧代码/封存包/主控制面板。未声称独立重验本摘要引用的全部历史产物。
