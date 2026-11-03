# Edge 预检准备故障修复与提交回执

结果：已修复准备阶段故障，39项工程回归通过；唯一一次600秒预检已确认提交，作业号181403。2026-11-03 15:32:49 UTC即时快照为RUNNING，尚不能称Linux预检通过。
影响：复用了四份已上传并验SHA的输入及863项完整解包；没有重传、重解包、训练或正式外部评价。此前准备失败发生在sbatch之前，没有旧作业，也没有消耗旧的600秒作业预算。
下一步：普通程序在原进度页持续更新并有界取回小结果；结束当前轮次，不持续AI监测，不自动重投或放宽门。

用户本轮明确要求“修复问题，然后重新提交”。复用用户已连接的VS Code Linux终端部署修复，未重新连接VPN或SSH、未操作认证。

- 直接原因：旧receiver裸调用TSHark检查版本，缺少`frontend_compat_v1/environment.sh`提供的共享库环境。真实终端裸调用返回127，报`libimf.so`缺失；加载既有环境后返回0，确认为TSHark4.6.6。修复使检查和作业使用同一环境，新增DECODER_IDENTITY诊断，精确版本门保留。
- 恢复逻辑：先验全部输入SHA与完整manifest，允许复用此前已解包完成的checkout；partial或篡改仍停止。旧本地准备意图和错误移入repair_history保留；远端旧receiver及错误也已备份。任何本地或远端提交意图存在都不允许这条准备恢复路线继续。
- 提交前独立审查发现第二处硬伤：Slurm将脚本复制到spool目录后，BASH_SOURCE不能定位原包。包外适配仅替换EDGE_PACKAGE_DIR和EDGE_ROOT两条赋值，其余字节、资源和参数保持；原包未改。提交前校验适配SHA并重算替换范围。
- 新receiver SHA256：`e33aae00c97ab52d8ed51a9c4650c00cea845890755f26b0ba71bf8412892a80`。原Slurm SHA256：`631bded8b84233eac50bdf9beb67ee0c57a86c8bb871c05a912562dcd5e8f7a1`；包外适配SHA256：`11ad2a27f6e6d8debd883ff317e482780a04713ff8ed3e458a69f1d005e96741`。
- PREPARE_RECEIPT确认`reused_verified_extraction=true`、863项manifest通过，Python3.11.11/NumPy2.0.1/Torch2.5.1/Transformers4.57.3/TSHark4.6.6匹配；原归档SHA仍为`c683ccbe4e3f1b92fc51638ed9345777f6577edc1f171486279e20248f9541d9`。
- SUBMIT_RECEIPT确认2026-11-03 15:32:25 UTC提交181403，amd、1CPU/6GiB/600秒、no-requeue；仍为78切片端点+13探针共91逻辑端点。即时快照已通过863文件包字节门，位于RUNTIME_IDENTITY；未读取或声称最终数值验收。

证据位于`runs/edge_linux_preflight_deployment_v1_20261103/`：`PREPARE_REPAIR_PLAN.json`、`REPAIR_ENGINEERING_TESTS.json`、`REPAIR_RESUME_RECEIPT.json`、`PREPARE_RECEIPT.json`、`SUBMIT_RECEIPT.json`。实时页：<http://127.0.0.1:18793/>。源码与小回执备份，原包、私有通道配置和原始数组不进Git。
