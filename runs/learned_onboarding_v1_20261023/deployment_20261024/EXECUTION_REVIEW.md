# 2026-10-24 学习式入网首次执行回执：测试兼容异常，已停止

> 后续状态：用户已确认，新独立V2启动并通过远端49＋4测试；见 [12:01执行复核](../compatibility_revision_v2_20261024/EXECUTION_REVIEW.md)。本文保留首次失败事实，不是当前服务状态。

用户已同意推进冻结的学习式入网 V1。首次新部署和 systemd 启动已经完成，但远端启动验收在 tests 阶段停止，**没有进入源准备、资源 preflight 或真实辅助头／修正器训练，也没有 CAL 或 A/B 新结果**。这是工程兼容异常，不是科学 FAIL。

## 首次部署与现场

- 原冻结规格 SHA256：`a07d736c7c9c756478a7d163873611132ff0b14abc855ab3a3709257433674b8`。
- 原实现 manifest SHA256：`f304679eed5214e6f670d7a4a77037c8b00329aa2ce82abc42c6f9ac484f81c8`；原 30 件产物逐件验字节／SHA，均未改。
- 部署包 694 件、ZIP 3,761,014 字节，SHA256 `e959b076b3a2a9855a92b7b312bc0b4037d725f69dedd4e04d47daac84db638d`。
- 部署 manifest SHA256：`b3f61b777d92c9ca814428bec7cacf0ce3572cca336010f8771cd9fb4aafcdc2`。
- 远端目录：`/srv/paper04/learned_onboarding_20261024`。
- 服务：`paper04-learned-onboarding-20261024-v1.service`；InvocationID `db91ff9a9cbe4a88836839180d73ffa1`。
- 北京时间 11:20:08 启动，11:20:15 退出；`ActiveState=failed`、`Result=exit-code`、`ExecMainStatus=1`，无自动重启。
- 启动紧邻检查：无活动 paper04 服务／计算 worker，MemAvailable 31,530,291,200 字节、磁盘空闲 158,847,717,376 字节。使用已有实例，无购置、HPC 提交或抢占。
- 已验外部硬限：MemoryMax=17,179,869,184 字节、MemorySwapMax=0、CPUQuota=800%、四数值线程、Restart=no、KillMode=control-group。运行器另有进程树 RSS 8 GiB 守卫。
- 原源资产 16 件按原 SHA 重新封成源专用输入 tar，43,458,560 字节；BACKUP_INDEX SHA256 `6bf1363d5825f97ebdcfe3071d4f6231c9014f2474d40bc62a4801d6cf86e0c3`。没有读取真实 A/B 查询。

完整 tests 日志和失败现场已只读回传，15 件、103,044 字节，见 [现场清单](local_ops/stopped_attempt_v1/EVIDENCE_RECEIPT.json)。未清除、覆盖或续跑原现场。

## 实际错误和证据边界

原 49 项测试中 48 项通过、1 项 ERROR，0 failure、0 skip。`tests/test_learning.py:158` 调用 `tempfile.TemporaryDirectory(ignore_cleanup_errors=True)`；该参数自 Python 3.10 才可用，实例为 Python 3.9.24，因此在进入该项测试体前报 `TypeError`。先前 Python 3.9 AST 语法验证不能替代此运行时 API 验收；本次实际验收捕获了差异。

tests 非零后执行链立即停下：prepare/validate/preflight/fit/calibration/target/evaluation 均未进入；adapter 独立四项因前序失败也未在该实例运行。没有真实优化更新、目标装配或新的科学结果。全 tests API 只读审计仅识别这一处 3.10 专属调用，但不能据此保证后续所有阶段必然通过。

首次安装辅助脚本还曾在解包前遇到占位符替换造成的 Python 语法错误，解析阶段未写远端目录。该本地安装器已纠正，使用同一已验 ZIP 完成部署，原错误回执保留于 `local_ops/REMOTE_DEPLOYMENT_VERIFIED.json`，成功回执另存 `REMOTE_DEPLOYMENT_VERIFIED_AFTER_INSTALLER_FIX.json`。这发生在服务提交之前，不是模型／实验重跑。

## 已备好的独立兼容修订，尚未重提

修订位于 [compatibility_revision_v2_20261024](../compatibility_revision_v2_20261024/REVISION_RECEIPT.json)，只在新测试副本中按 Python 版本决定是否传入该临时目录参数。没有删断言、跳测试、修改模型／损失／数据划分／训练步数；独立审查比较了 29 个断言／skip 调用及测试名单，全部一致。原冻结 30 件原样保留。

本地修订全 49 项 PASS；Python 3.9 分支参数构造及 AST 已验证，**实际远端 Python 3.9 仍 NOT_RUN**。新包 695 件，3,763,580 字节；ZIP SHA256 `6e3e13f04e7b6bcac69e2fbf278c287f000a93e773f57ef7e27348cf452c0e61`，部署 manifest SHA256 `c2f40b052a2839f53f2d732096a2c2e2a8b1832fec8e2fbae5e781bfff93debc`。原 manifest 作为 `implementation_manifest.original.json` 随包保留，新 manifest 明确是兼容修订、未远端验收。

拟新目录 `/srv/paper04/learned_onboarding_20261024_v2`、新服务 `paper04-learned-onboarding-20261024-v2`，不恢复或覆盖首次现场。当前修订只在本地，**未上传、未启动、未自动重提**。依据用户的异常停链／不自动重跑要求及冻结规格第 9 节，重新执行须由用户决定；决定前不继续尝试真实链。

results 累计上限仍为 2 GiB；目标格式转换输入 staging 另限 2 GiB，源输入暂存独立列账，所有新文件和可用空间一起报告，不把输入副本说成零占用。时间上限是停止预算，不是 ETA。

## 进度页

现有 [18765 进度页](http://127.0.0.1:18765/) 已加载学习式栏目并显示本次 `EXCEPTION_STOP`。只重启了经路径核验的本地页面服务器（PID 26300→36092），原日志保留，新日志带 20261024；没有重启远端实验。页面后台每 60 秒读小状态，不调用 AI，不安排持续模型轮询。

下一步候选是对上述独立兼容包进行远端验收；若用户同意，先保留首次现场并重新核查执行窗口，再以新版本执行同一完整冻结链。尚未知：远端兼容修订是否全测通过、资源实测、真实折外残差信号、三修正器能否训练、CAL λ 和 A/B 收益。现代头完整模型／逐条预测备份仍待，未在本轮擅自下载。
