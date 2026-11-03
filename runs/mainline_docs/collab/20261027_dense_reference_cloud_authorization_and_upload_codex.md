# 密参考r2云端运行授权与手动上传交接

2026-10-27。最新用户原话：“可以运行，但是给我指令我上传会不会比你控制电脑快点？”

用户已经授权按已提供执行卡运行一次`runtime → encode → source_cal`，amd单节点4CPU/16GiB/12小时、单worker/CPU-only，0自动重试。补编码21,660个冻结参考位置，前置原104逐字节门禁；不训练、不做目标A/B评价、不运行被第三池资产阻断的完整矩阵。不再重复请求此范围授权。

实际授权已落`runs/dense_reference_matrix_v1_20261027/deployment/APPROVED.json`，由Codex后续在核验归档与新目录解包后部署到超算包目录`.private/APPROVED.json`。r2封存包和历史执行卡不修改；其中“待授权”为生成时的历史状态。本文件与根`IMPLEMENTATION_STATE.json`是更新后的状态。

当前状态：**AUTHORIZED_AWAITING_USER_UPLOAD**。本次尚未访问远端、上传或提交作业，新进度服务尚未启动。用户手工上传归档后，Codex继续远端SHA核验、全新目录解包、输入预检、单次提交及普通隐藏程序进度同步，不需再次授权。不重复运行旧BASE/CTX，不改其18769终态页。

上传件仅r2归档115,876,260字节，既有源大件及checkpoint复用。用户在**本机PowerShell**执行：

```powershell
scp "D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\dense_reference_matrix_v1_20261027\distribution\r2\dense_reference_matrix_v1_20261027.tar.gz" school-hpc:/public/home/jiangxinwei.zr/work/paper04/
```

现有SSH别名`school-hpc`来自用户本机SSH配置。用户如需登录，直接在本机终端完成交互认证，不在聊天中提供密码。归档远端目标为`/public/home/jiangxinwei.zr/work/paper04/dense_reference_matrix_v1_20261027.tar.gz`。只上传归档，不手工重复解包或sbatch；上传完成告知Codex，后续步骤由Codex继续。

预期归档SHA256：`43c31bd5ba3dc169aa95fae0079f2b856801043c46fd7862736110cb603b0140`。包`PACKAGE_SHA256SUMS`身份：`ddb94bb9836c9ace0b2a704e875d969c1d3c40c94198212ac795a9d0731db120`。本轮授权和手工上传偏好不构成数值/资源异常的自动重跑许可；遇异常保留现场停止。连接状态由普通程序显示，不持续调用AI轮询。
