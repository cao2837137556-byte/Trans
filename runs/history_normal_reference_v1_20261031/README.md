# 历史正常参考 C1 实现

本包实现 `20261031_well_history_normal_reference_execution_plan_r2_for_codex.md` 加最终 Codex 复核绑定。固定单候选 `C1 / P-DEVONLY`，先历史 DEV 门，再一次 A/B。它复用冻结六头、E3、q14、几何、λ、scale 和 cut；不训练、不重校准，不实现 P-ATTN。

实现和生成数据测试不代表真实效果。当前实现授权不包含真实包解码、特征提取、补库、实验评价或远程提交。

运行入口与具体资产合同由 `run.py` 和 `config/` 提供；默认检查不启动模型或科学运行。真实执行要求显式选择执行入口，并使用新的输出目录。失败不自动重试、不恢复旧作业，不覆盖既有结项。

进度文件是输出目录的 `STATUS.json`；只读查看器 `progress.py --status-file <STATUS.json>` 监听 `127.0.0.1:18785`。在 Codex 右侧面板打开这个地址即可沿用原工作模式。网页只读取本地状态，不提交或控制作业；远端状态应由既有同步流程拉回。工作心跳和看门服务心跳分别记录；工作心跳超过 90 秒时显示进度未知，不把网页刷新当作实验仍在推进。

硬预算为整次作业 CPU 4、内存 16 GiB、中间产物 20 GiB、墙钟 8 小时、新增编码最多 36,864 行、实际距离对最多 579,614,444。Runtime 用 CPU affinity、预扣计数和独立每秒资源守卫约束，Slurm 另设 CPU/内存/时间上限。资源守卫终止时保存错误状态与现有产物，不自动重投。包中 Slurm 文件仅为后续执行准备，当前没有提交。

阶段进度包括输入核验、整成员连续流候选枚举、确定性选点、选中位置快照、E3 编码、DEV 门、一次 A/B 和结项。记录每次遍历的原包数，不能把两次遍历伪称为只读一次。没有试跑时不提供 ETA。

生成数据工程验证：`python -m unittest discover -s tests -v`。这些测试不读取真实原始包、不构造真实新参考、不运行真实模型或真实数据距离实验。

默认只读验收命令是 `python run.py check`；读取已有索引验证 UTC 日期边界，核对路径、大小及索引 SHA，不生成角色文件。加 `--verify-raw-hash` 只增加完整性读盘，不解码。`validation/READ_ONLY_ACCEPTANCE.json` 登记本机验收；其中 READY 仅表示已登记本地文件齐备，不代表超算环境已验收或真实效果达标。

执行入口为 `python run.py execute --runtime-config <已映射配置> --output <本包outputs内新目录> --execute-real-data`，Slurm 模板见 `hpc/run_history.slurm`。执行前应在交付阶段映射本机路径、核验远端输入和 Python3.11.11 / Torch2.5.1 / NumPy2.0.1，并封存远端交付代码。路径迁移允许，数据/normalizer/几何/heads的科学 SHA 不可替换。本轮没有执行这些步骤。

每个历史成员的科学准备顺序为：核 raw SHA → 逐包原样重排为 PCAPNG → 完整解码及端点 census → 确定性选点 → 第二次完整解码并只保存选中快照 → 独立历史选点/描述符回放及 E3。单成员通过后只释放本次输出中的四个已登记大中间文件，保留选点、快照、编码和 SHA 回执。一次 frozen encoder 跨三成员复用；其后释放，再按原 QUERY_TAIL 三头评分 DEV。默认不会从 A/B 获取开发分数。

沿用已验收的 singleton 修复：单逻辑行用16份相同物理张量前向，逐字节检查输出相等后只保留1个UID；不把克隆加入参考库。36,864 是唯一新增向量上限，实际物理位置另记在批次 ledger 和回执，最多另加6,480个克隆位置；总墙钟、内存预算涵盖它们，不把逻辑行数当物理计算量。

DEV 门及 A/B 均保存逐 UID logits、support、eligibility、四头决策和来源/输入封印。PASS/IMPROVED 用原 `post_window_primary`，full及其保护报告并列保存；全部原评价设备保留。最终状态有全局 `EXECUTION_ATTEMPT.json` 一次尝试标记，不靠另换输出目录获得第二次科学评价。
