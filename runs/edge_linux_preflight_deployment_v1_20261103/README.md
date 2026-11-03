# Edge Linux 预检交付

结果：交付程序及接收端命令已准备，25项合成工程检查通过，用户已明确授权仅本次10分钟预检。工具拒绝自动启动及本地启动脚本生成，目前尚未上传或提交。
影响：实际环境沿用180772成功入口；在包外source既有environment.sh并带入固定NumPy/Transformers vendor路径。预检仍为1CPU、6GiB、600秒和91逻辑端点，不启动正式外部评价。
下一步：先在已连接的Linux终端执行 `RUN_IN_HPC_TERMINAL.txt` 的整行命令；接收端就绪后，在本机PowerShell手动运行下述已有程序。无需再次授权。

## 手动启动顺序

1. **超算Linux终端**：复制执行本目录 `RUN_IN_HPC_TERMINAL.txt` 的整行内容，看到 `EDGE_PREFLIGHT_DELIVERY_READY`。保持VS Code连接。
2. **本机Windows PowerShell**：执行下面命令，保持该窗口打开。程序会续传已有4个文件、核验、提交一次并在有界窗口内取回小结果。

```powershell
& 'C:/Users/28371/AppData/Local/Programs/Python/Python310/python.exe' -X utf8 -B 'D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/edge_linux_preflight_deployment_v1_20261103/pipeline.py' --wait-for-receiver-seconds 1800 --observe-seconds 1800 --interval-seconds 20
```

3. **另一个本机PowerShell窗口，可选的网页进度**：执行下面命令后访问 <http://127.0.0.1:18793/>。进度来源是本目录 `PROGRESS.json`；网页只读，不启动远端动作。

```powershell
& 'C:/Users/28371/AppData/Local/Programs/Python/Python310/python.exe' -X utf8 -B 'D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/edge_linux_preflight_deployment_v1_20261103/progress_server.py' --port 18793
```

不要将本机PowerShell命令粘到超算Linux终端。本地启动脚本因工具策略拒绝未能生成；以上直接调用已完成且通过检查的Python入口，供用户手动执行，助手未代为启动。

连接由用户手动完成。启动命令只在远端个人项目目录创建本次专用loopback接收服务，不重新SSH登录，不改VPN、依赖或冻结包。命令及 `.private/` 含临时通道凭据，不进Git。

`DELIVERY.json`登记四个输入的大小和SHA：已封存归档及NORMAL/HTTP/UDP原包。本地和远端均核对SHA；上传中断只续传文件，不重提交实验。远端独立解包，不覆盖原项目。提交意图先持久化；若sbatch结果不确定，停止并报告，不自动再投。

仅 `SUBMIT_RECEIPT.json` 中有已确认作业号才可称已提交；只有完整Linux运行时、端到端回执和严格形状探针均通过，才可称预检通过。调度器COMPLETED本身不代表科学或数值门通过。

普通程序可在有界时间内更新进度、取回小日志/回执，不需要AI持续监测。预检通过也不自动启动60,000查询的正式评价；完整续跑恢复门、实测预算和最终评价卡另行闭合。
