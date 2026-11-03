# Edge preflight I/O repair

结果：本地工程门通过；本次唯一 Linux 预检的作业号与最终状态见 SUBMIT_RECEIPT.json / FINAL_ACCEPTANCE.json。缺少最终回执不能宣称 Linux 通过。
影响：C5 p=3、选点、原始上下文更新、resident=256、78 个切片端点和 13 个严格探针不变。只改变临时存储位置、可诊断性与完成角色的保存。
下一步：一次 1 CPU / 6 GiB / 600 秒预检；结果由普通交付程序自动取回，无 AI 持续监测、自动重投或正式外部评价。

181403 在上下文重放期间超时，尚未进入编码。484,214 个前缀物理包必须全部更新上下文，不能按 91 个逻辑端点估算解码工作量。共享 SQLite 是主要性能嫌疑，不能称为已证明的唯一根因。

## Repair boundaries

- `replay_io.py`：原 NumericalContexts/SpillMap 临时库转移到已核验节点本地 scratch；逐帧期限检查，昂贵资源检查每秒至多一次。每 4096 帧或 5 秒保存心跳。
- 每个选中快照立即保存。只有原生成器完全结束且最终输入校验通过才标记完整角色缓存；部分角色只保留证据，不从任意帧续跑。缓存绑定原包、代码、帧集、参考角色、运行时和命名空间，受限反序列化前校验大小与 SHA。
- `worker.py`：验证实际 mount/device/free space，拒绝 NFS/Lustre 和与持久存储同设备的 scratch，无共享回退；只清理带所有权标记的唯一临时目录。
- `launch_preflight.py`：逐字节校验原 863 文件；沿用原严格探针入口和所有接受门。统一 560 秒父截止；子进程提前 15 秒停止以写 STOP/最终回执。
- `remote_receiver.py`：新命名空间、18819 端口与单次提交意图；复用旧原包/checkout，不清除或重置 181403 的意图和失败证据。Slurm 仅替换两条路径赋值，资源和调用参数不变。
- `delivery_pipeline.py`：复用用户手动建立的 SOCKS 通道，普通程序自动核验、单次提交和有界取回；将当前展示状态镜像到原进度页 18793。旧封存失败回执不变。

## Evidence

新测试 30 项：28 通过，2 项 Linux 专属检查在 Windows 跳过。原交付回归 39/39 通过。最终源码的真实 HTTP 14 端点递归值/类型与原实现、完整缓存重载完全一致。

完整前缀无模型验证：NORMAL 255,220 包 28.109 秒；HTTP 228,978 包 81.438 秒；UDP 16 包 1.359 秒。脚本共 119.594 秒，临时峰值 196,879,426 字节，已清理自有临时目录。这是 Windows/Python 3.10 的重放证据，不等于 Linux 端到端数值验收或吞吐承诺。

详见 `REAL_REPLAY_VALIDATION.json`、`REAL_ENDPOINT_FINAL_VALIDATION.json`、`RUNNER_TEST_RESULTS.json`、`UNIT_TEST_RESULT.json`、`INDEPENDENT_REVIEW.json` 和 `REPAIR_CONTRACT.json`。

只允许本轮有界工程预检。正式外部测试、模型训练、加预算和自动重新提交均未被该程序授权。
