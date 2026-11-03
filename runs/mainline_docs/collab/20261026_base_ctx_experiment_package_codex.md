# BASE/CTX 实验包完成回执与运行申请（Codex，2026-10-26）

状态：**LOCAL_PACKAGE_ACCEPTANCE_PASS / BUILT_NOT_SUBMITTED**。用户已接受按既有Claude/Codex方向先完成BASE/CTX子矩阵。本轮完成本地实现、绑定、测试、只读预检与人工数据dry-run，未上传、未sbatch，未运行真实源训练/前向、生产MI15、新E3或A/B评价。

入口：[实验包README](../../source_controls_base_ctx_v1_20261026/README.md)、[完整数值合同](../../source_controls_base_ctx_v1_20261026/PROTOCOL.md)、[contract.json](../../source_controls_base_ctx_v1_20261026/config/contract.json)。本回执取代旧执行卡中“尚无runner/需Claude收敛”的下一步；旧数据绑定与历史现场保留。具体口径由Codex按本次获准范围收敛，不冒称Claude已逐项确认。

## 1. 科学范围与冻结口径

沿[Claude第四步r1](20261026_step4_source_controls_r1_claude.md)检验：同数据、同QUERY_TAIL配方下，主机上下文是否改善陌生设备正常/攻击区分。BASE为E3+q14共782维；CTX增加原版AfterImage MI15共797维。**源新效果仍未知，合成数值不是科学信号。** COV−/CNT−因数量/权重匹配退化暂缓，COV+无合法本地额外capture；独立“补E3→密源CAL→A/B矩阵”没有被本包实现或启动。

- 两折G0/G1沿原三设备组，seed27/127/227，共最多12头；训练只用本组原FIT，切点只用本组原CAL正常；held必须是另一组全部LEARN查询，含原FIT与CAL。
- 每折40epoch：G0每seed17,000更新，G1每seed79,600；BASE6共289,800，全12共579,600。未套历史全源96,560更新。
- BASE先完成六头；S0为两个折的三seed平均加权FPR均≥3%。任一不达记NOT_INFORMATIVE，跳过MI15/CTX，不宣称CTX无效。
- S0通过后完成六CTX。每折均值FPR相对下降≥30%、至少2/3同seed严格改善、配对均值攻击召回损失≤0.1个百分点、原始pAUC均值不降；两个折均须通过。一般科学FAIL继续登记配对。
- 初始化、BCE+TAIL、层级权重和UID有序tail采样沿历史算法。E3/MI15只在本折FIT拟合normalizer；CTX从同seed未训练BASE零扩展MI列。旧trainer的生产行数/维数门禁未删除。
- 每seed切点独立，严格`>`、源CAL正常1%预算；另报float64均值logit集成并独立校准。pAUC按整块并列分数、0.05边界插值及梯形原积分，另报原积分/0.05。
- 源缺rate1/10/100标签仍标NOT_AVAILABLE，不伪造；报告设备/设备活动/capture/协议与整数FP/TP/FN。本源held召回判据和入网λ的源CAL ε=0.1pp是不同环节，原λ合同不改。

冻结E3历史接触及七个共享Active capture继续披露。这是同实验室、检测头层设备留出，不是端到端/场地完全未见。MI完整capture全部包因果更新，标签不进入统计状态；MAC+IP仅作原统计键，不作为神经输入。旧header把第三项叫std，但实际实现返回variance，本包保持原值。

## 2. 工程交付与验收

独立src包含：数据SHA/白名单、训练、MI15全帧提取、校准/指标、BASE先行矩阵、资源supervisor与终态回执。MI每物理capture重置，按原frame顺序更新后取查询，严格source SHA/frame/time加入UID；不接受仅存在mmap但没有完成SHA回执。

权威验收：[final_r2/ACCEPTANCE.json](../../source_controls_base_ctx_v1_20261026/validation/final_r2/ACCEPTANCE.json)。

|检查|结果|
|---|---|
|本地测试|80/80 PASS，0 skipped|
|归档独立解压再测|同80/80 PASS，不依赖外围repo|
|人工数据全矩阵|12端点、24更新、COMPLETE，标SYNTHETIC_NOT_EVIDENCE|
|真实源只读预检|766,727行、五个输入及派生索引/roster SHA、UID/角色/设备隔离、q14范围全部PASS；最终exit COMPLETE|
|Slurm脚本|Bash语法PASS，LF行尾；未实际提交|
|真实源训练/前向、生产MI15、新E3、A/B、远端操作|全部0|

首次新预检`validation/source_preflight_v1`的数据/预算检查已过，但末尾写进度遇Windows `os.replace` WinError5，整体FAILED现场保留。修订只对本地JSON文件替换的WinError5/32/33做总310ms退避；永久失败保留旧内容并停止，绝不重启worker/科研阶段。修订后独立final_r2正常完成。这不是重做已有科学实验。

最终只读worker采样RSS峰值4,464,463,872 bytes≈4.16GiB、约39秒；它不是生产内存上界。提取时的MI metadata、JSON临时对象和子进程仍增加内存，8GiB采样停止与16GiB Slurm硬限必须保留。

## 3. 发布身份与运行门禁

[发布归档](../../source_controls_base_ctx_v1_20261026/distribution/source_controls_base_ctx_v1_20261026.tar.gz)：564,973 bytes、43个封存文件；[发布回执](../../source_controls_base_ctx_v1_20261026/distribution/PACKAGE_RECEIPT.json)。五个大源输入2.40GiB和169 raw约11.10GB复用已验收只读位置，无重传。

- archive SHA256：`4f5e298a9b5a98d2b7e1590db636ac725a07046801076db8318600631d2a68f3`
- manifest SHA256：`71f03266a506c1068b2ede45f6dd978960d01f66e0037c35ea01e95ef5d6500c`
- contract SHA256：`8a31761254a7839ba73c0f45993bae8f4d1f9b39029fe1228cf1be3d78565a4b`

本地验收环境Python3.10/NumPy2.2.6/Torch2.8 CPU；生产各臂统一使用已验收HPC的Python3.11.11/NumPy1.26.4/Torch2.5.1。Slurm内在真实科学前向前必须通过包SHA（60s）、单测（180s）、同HPC环境人工数据流程（supervisor180s/外层200s），任一失败即停，不自动重提。未宣称历史云端NumPy2.0.1数值身份；原104新编码门禁仍是独立E3链前置，本包不替代它。

普通进度组件及固定job只读bridge/同步已封包，见[传输说明](../../source_controls_base_ctx_v1_20261026/hpc/STATUS_TRANSPORT.md)。门禁launch、训练阶段、完成/异常/NOT_INFORMATIVE、同步未知分别显示；终态不依赖继续心跳。尚未部署新服务，原18765/18766保持。正式部署后普通程序同步，不持续调用AI轮询。

## 4. 正式运行申请（尚未授权/执行）

具体范围：上传小包并验SHA→同作业技术门禁→源preflight→六BASE/S0→若S0通过则169 capture生产MI15、六CTX及配对报告。最多12头/579,600更新，不追加搜索，不做A/B或新E3。

资源：单worker、4CPU、Slurm16GiB/6小时/0requeue；源supervisor5小时50分，采样树RSS8GiB、增量输出2GiB、文件系统free-space下限4GiB。计划输出含两份MI文件、两份绑定metadata、日志/分数/loss/参数及10%预留，共1,379,451,390 bytes≈1.28GiB。个人/项目quota仍未知，共享free-space不等于quota；空间/I/O/身份/数值/资源异常停止留现场，不盲重跑或轮换节点。

旧云端耗时外推12头约52分钟；新超算全量未实测，整体规划2–4小时、不含排队，6小时硬限；S0未达则只完成六BASE。不能预告A/B达到1%。

下一步由用户决定是否授权此具体包运行；获准后Codex完成部署/提交及普通进度接入，不等待Claude。正式指标须等真实源端点产生后判读。
