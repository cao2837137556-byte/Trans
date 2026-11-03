# QUERY_TAIL v1 实现与交付

2026-09-30。补读experiment8交接后，从设计直接进入实现、合成语义验证和交付；未重做G1–G4或D3。用户临时暂停权限讨论后已要求继续。真实超算P/T/K没有启动，最终包尚无单独的真实执行授权记录。

## 结果

本地工程验收通过，版本化整链包已生成：

- 交付目录：runs/legacy_query_tail_learning_delivery_v1_20260930/。
- 包名：legacy_query_tail_learning_v1_20260930.tar.gz。
- 127034字节，SHA256 72a50f76e2bb14683b285cef5fbd2e5cc38cc6112886e687fee82d219725f1c2。
- 设计SHA仍为8fc236975039773580fef8d40705d205dc382dbc5159c43833928958c62a6ecd，设计正文未改。
- 操作入口：交付目录OPERATE_HPC.md；transfer_v1.ps1负责用户上传/拉回。无需重新上传PCAP、特征或编码器。

## 实现与自审

新增repo/ood/query_tail_{core,prepare,train,evaluate,runner,export}_v1.py及test_query_tail_v1.py。包中共有31个Python模块，旧模块只作为固定算法与工具依赖复制；旧生产文件和封存包未改。

P验证Job177891身份、全部三池当前特征、源normalizer和spool。查询按role/slot/UID逐行匹配，按query_frame定位，检查query_time、namespace、未来/过龄帧、重复帧和flow token映射。q只读取指定14字段，方向来自旧窗口首IP源语义；不从长度猜payload、不读取reference body。FIT617908/CAL148819严格使用完整索引，不使用旧reference-eligible子集。

源支持统计按FIT/CAL、标签、协议和互斥阶段保存类条件权重、实体数、ESS与实际窗口信息，并对可复现的父support计数对账。缺SYN正/负跨实体支持、缺TCP非SYN或UDP类别、身份/权重不守恒均在训练前停止。完整源阶段支持仍待远端P，不能以本地合成PASS称已满足。

T实现加权最高1%正常质量、整个并列块按权重分配边界、每epoch刷新、独立UID排序逆CDF随机流、有放回128负例和双方当前logit梯度。BCE完整FIT权重保持，pair正例使用2w与N/实际batch大小，不按batch重归一化。无攻击batch按冻结公式pair=0、总目标=BCE/2。三臂各3seed、40轮固定终点，869040更新；R0直接复用封存分数。

初始化共享参数逐字节与原随机初始头一致，q新增列全0。更宽矩阵的float32 GEMM可能产生约舍入级的输出差异，不声称浮点逐位函数一致；测试同时检查共享参数、float64数学函数一致及float32误差界。该验证口径修正不改变模型、优化器或初始化配方。

K使用原source-CAL正常阈值算法、严格>、每seed及float64集成分别校准；R0阈值与原保存决定重现。原共同攻击/FPR门槛保留，新增源CAL TCP/UDP/Hydra与CIC攻击协议组逐seed/集成保护。所有臂报告，不按结果选新主候选。参考增益/否决零新增漏检NOT_TESTED，ID NOT_RUN，历史holdout关闭。

## 验证证据

- 干净解包Windows Python3.9.13：23项生成数据语义/生命周期测试PASS，包含小型P→9头→K→成功导出、源目录字节不变、CAL标签不影响训练终点、尾部解析/梯度/末batch、缓存和角色错误拒绝、资源/人工停止、失败导出。
- Windows安装6项PASS；Linux标准库安装6项及真实Bash+模拟sbatch6项PASS，覆盖无授权、成功后重复、提交失败/响应不明确保留锁、篡改前置拒绝与脚本语法。
- PowerShell语法与Mode参数PASS，干净解包与全部归档成员一致、LF及内部/外部SHA核验PASS。
- 另外只对已返回12个早期snapshot运行确定性q解析，兼容性PASS；无模型前向、原始解码或科学分数诊断。详细摘要在saved_snapshot_compatibility.json。
- 本地NumPy2.0.2/Torch2.8.0+cpu不同于目标NumPy2.0.1/Torch2.5.1；目标计算节点实际环境检查与同一合成测试并入正式作业，尚未执行。Linux本地数值测试未声称完成。
- 分支codex/exp-mainline、HEAD4b28747b09480471e2bac1beb3a9badf27280efb及8项旧无关修改SHA保持；source_validation.json保存身份。

自审为Codex单方，无Claude/子代理独立审查。Claude token耗尽已知，不把等待其审查设置为继续障碍，也不假称他审核了本包。

## 资源与下一步

固定amd16CPU/64G/72小时，3个训练进程各4线程；总RSS56GiB/worker14GiB、程序70小时、输出12GiB、至少24GiB空闲。静态假设与局限见RESOURCE_BUDGET.md；没有以旧batch记账值替代全树峰值，也没有运行资源benchmark。

用户同意本包一次完整P→T→K→export后，按OPERATE_HPC.md上传、在已认证终端提交和拉回；无需重复逐阶段授权。没有自动SSH登录、上传、提交或实验重试。此前打开应用权限菜单的讨论不被当作本包真实训练授权。

solved: 设计已实现、合成语义/交付验证完成，整链包与操作说明就绪。
changed_mainline: engineering implementation only; no new scientific result。
active_blocker: 真实源阶段支持及目标节点兼容性等待一次明确授权后的P；联合能力待实验。
frozen: QUERY_TAIL设计、旧v3结果/包、FIT/CAL/DEV分母与核心门槛。
next_action: 用户确认最终包完整链执行，再由用户上传/单次提交/拉回。
