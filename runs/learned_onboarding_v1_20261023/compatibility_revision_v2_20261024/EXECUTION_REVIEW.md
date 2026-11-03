# 2026-10-24 独立兼容 V2：用户确认后已启动，远端测试通过

> 后续最新事实：北京时间12:10:36在AUX_G1训练后分批数值回放中EXCEPTION_STOP，未进入三个修正器、CAL或目标评价。见 [诊断与证据](operations/fit_stop_20261024/DIAGNOSIS.json)。本地页面另已恢复独立托管，见 [修复回执](LOCAL_PAGE_REPAIR_20261024.json)。下文保留启动时快照；没有自动重跑。

用户明确回复“确认重新启动”后，独立兼容修订已部署并启动。北京时间 **12:00:51** 新服务进入运行；**12:01:35 有限启动验收**确认：原 49 项测试全部 PASS，0 error／0 failure／0 skip；目标适配器独立 4 项 PASS，真实目标查询读取 0。此前 Python 3.9 临时目录参数异常已通过实际环境验收。

验收快照中服务 `active/running`，完成 `tests`，正在 `prepare`（源身份核验与源输入装配）。**当时资源 preflight、真实辅助头／修正器训练、CAL 及 A/B 新评价尚未完成；不能把服务启动说成真实训练已经开始。** 后续阶段由程序自动串行继续，不持续调用 AI 轮询。

## 执行身份

- 新远端目录：`/srv/paper04/learned_onboarding_20261024_v2`。
- 新服务：`paper04-learned-onboarding-20261024-v2.service`。
- InvocationID：`8dfc9669c40a493e93d862ec768b2ca1`。
- 冻结规格 SHA256：`a07d736c7c9c756478a7d163873611132ff0b14abc855ab3a3709257433674b8`。
- ZIP：695 件，3,763,580 字节；SHA256 `6e3e13f04e7b6bcac69e2fbf278c287f000a93e773f57ef7e27348cf452c0e61`。
- 部署 manifest SHA256：`c2f40b052a2839f53f2d732096a2c2e2a8b1832fec8e2fbae5e781bfff93debc`。
- 兼容修订实现 manifest SHA256：`98f2e32dde1a16021adf533389b2b001decea5030cdf7c4615cb97599491fc7b`。原实现 manifest 按原 SHA `f304679eed5214e6f670d7a4a77037c8b00329aa2ce82abc42c6f9ac484f81c8` 随包单独保留。
- 新源专用 tar 43,458,560 字节，仍是原 16 件源资产逐件 SHA 相同；BACKUP_INDEX SHA256 `a408e4069e4a6d9a1140d943fc028193127dcbb2e5a1eb32a0419f461b13ec88`。

原、本地冻结 30 件产物全部保持原样；修订只在独立副本中按版本决定测试临时目录参数，模型源码、科学配方、断言与测试名单不变。新配置仅将输入 archive 指到独立新目录，新 manifest 如实记录该修订。`REVISION_RECEIPT.json` 的 NOT_RUN／未部署是先前修订准备快照，后续实际执行以本回执及 `operations/` 为准。

## 空闲窗口与启动验收

启动前无活动 paper04 实验服务／计算 worker；可用内存 31,549,579,264 字节，磁盘空闲 158,776,963,072 字节。复用已有实例，无购置、HPC 提交或抢占。

实际读取服务属性确认：MemoryMax=17,179,869,184 字节、MemorySwapMax=0、CPUQuota=800%、四数值线程、Restart=no、KillMode=control-group。外层进程树 RSS 守卫保持 8 GiB。12:01:35 快照中进程树 RSS 峰值 4,115,472,384 字节，cgroup MemoryCurrent=3,991,056,384 字节；这些是早期源准备阶段观测，不能当作后续训练峰值。

原 49 项远端测试于 Python 3.9.24／Torch 2.5.1+cpu 环境全部通过；其中先前失败的 `test_geometry_batch_to_module_endpoint` 也实际通过。适配器 4 项另存 `adapter_validation.json`，不混入 49 计数，范围为封存门控、篡改拒绝、固定 UID／分数接口和历史 parent_slot 回放。

部署逐件验 SHA、源输入装配、空闲窗口、完整命令、硬限及实际验收见 [operations](operations/STARTUP_ACCEPTANCE_SNAPSHOT.json)。其中 `REMOTE_LAUNCH_RECEIPT.json` 是实际提交与服务硬限回执，`USER_CONFIRMATION.json` 记录本次明确授权。没有覆盖首次失败现场，也没有对本次再设自动重试。

## 后续自动执行与未知项

完整登记链为 tests → prepare → validate → preflight → fit → calibration → target → evaluation。资源 preflight 通过后才允许真实训练；正式头固定 QUERY_TAIL seed27、两个辅助头及三个修正臂按原规格执行。源信号不足则按预登记导出 NOT_TRAINED／no-op 并继续完整配对，不另换组或加头。科学 FAIL 继续登记配对，技术异常停止并保留现场，不自动重提。

results 累计预算仍为 2 GiB，目标输入格式转换 staging 另限 2 GiB，源暂存独立列账；全部新文件、可用磁盘和进程树 RSS 均记录。10 小时训练／24 小时全链是停止预算，不是 ETA。无自动云停机。

当前未知：源准备与全量资格是否完成、资源 preflight 实测、辅助折外困难信号、模块是否可训练、最终源 CAL λ、A/B 收益和完整科学判据。现代头大结果备份仍待，不在本次擅自下载。

现有 [18765 进度页](http://127.0.0.1:18765/) 接入本次独立 V2；页面接入的实际本地回执见 `PROGRESS_PAGE_RECEIPT.json`。普通程序后台读取小状态，不消耗 AI 对话轮次。
