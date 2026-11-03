# Edge Linux 预检交付

结果：准备阶段故障已修复，但真实预检181403在上下文重放阶段超时，未进入模型编码。最终回执未通过，已保存失败现场；39项工程回归不能替代真实Linux全链路通过。
影响：实际环境沿用180772成功入口；在包外source既有environment.sh并带入固定NumPy/Transformers vendor路径。预检仍为1CPU、6GiB、600秒和91逻辑端点，不启动正式外部评价。
下一步：先完成吞吐、临时状态存放与逐包诊断修复及等价性核验，再制定下一次有界验证。当前没有新增云作业；不要重复执行下面的历史手动启动命令。失败页保留在 <http://127.0.0.1:18793/>。

## 备用手动启动说明（当前无需执行）

1. **超算Linux终端**：复制执行本目录 `RUN_IN_HPC_TERMINAL.txt` 的整行内容，看到 `EDGE_PREFLIGHT_DELIVERY_READY`。保持VS Code连接。
2. **本机Windows PowerShell**：执行下面命令，保持该窗口打开。程序会续传已有4个文件、核验、提交一次并在有界窗口内取回小结果。

```powershell
& 'C:/Users/28371/AppData/Local/Programs/Python/Python310/python.exe' -X utf8 -B 'D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/edge_linux_preflight_deployment_v1_20261103/pipeline.py' --wait-for-receiver-seconds 1800 --observe-seconds 1800 --interval-seconds 20
```

3. **另一个本机PowerShell窗口，可选的网页进度**：执行下面命令后访问 <http://127.0.0.1:18793/>。进度来源是本目录 `PROGRESS.json`；网页只读，不启动远端动作。

```powershell
& 'C:/Users/28371/AppData/Local/Programs/Python/Python310/python.exe' -X utf8 -B 'D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/edge_linux_preflight_deployment_v1_20261103/progress_server.py' --port 18793
```

不要将本机PowerShell命令粘到超算Linux终端。隐藏后台启动及生成本地脚本曾被拒绝；本轮直接通过同一命令工具的前台会话启动已有Python入口，已获准执行。以上命令仅作恢复参考，不能据此重复启动当前流程。

连接由用户手动完成。启动命令只在远端个人项目目录创建本次专用loopback接收服务，不重新SSH登录，不改VPN、依赖或冻结包。命令及 `.private/` 含临时通道凭据，不进Git。

`DELIVERY.json`登记四个输入的大小和SHA：已封存归档及NORMAL/HTTP/UDP原包。本地和远端均核对SHA；上传中断只续传文件，不重提交实验。远端独立解包，不覆盖原项目。提交意图先持久化；若sbatch结果不确定，停止并报告，不自动再投。

仅 `SUBMIT_RECEIPT.json` 中有已确认作业号才可称已提交；只有完整Linux运行时、端到端回执和严格形状探针均通过，才可称预检通过。调度器COMPLETED本身不代表科学或数值门通过。

普通程序可在有界时间内更新进度、取回小日志/回执，不需要AI持续监测。预检通过也不自动启动60,000查询的正式评价；完整续跑恢复门、实测预算和最终评价卡另行闭合。
