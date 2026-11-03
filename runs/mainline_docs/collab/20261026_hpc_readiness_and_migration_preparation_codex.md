# 超算恢复连接后的实验准备（Codex，2026-10-26）

用户已在 VS Code 中连接 `school-hpc`，截图显示远端终端与 `work/paper04`；旧 `_upload_issue27cd/README_run_on_hpc.md` 无法打开。截图仅证明该 VS Code 会话已连接，不能证明旧路径、缓存或环境完整。

本轮已核对本地最新执行卡和补编码包，并尝试一次只读、非交互 `ssh ... school-hpc hostname`，返回认证失败 `Permission denied (publickey,gssapi-keyex,gssapi-with-mic,password)`。没有密码尝试、修改 SSH 配置或安装密钥。**VS Code 会话和 Codex 命令行会话认证独立；远端数据与调度状态尚未实查。** 本轮未提交计算作业、安装依赖、上传资产、运行模型或更改远端。

## 1. 当前优先事项

先做就绪核查，确认共享项目目录、容量/配额、现有缓存、Python/依赖与 Slurm 分区；根据实际缺项生成最小上传清单。之后用获准的小型 Slurm 预检，在真实计算节点检查共享路径、依赖及资源，不能把入口节点检查当成计算节点已验收。正式实验提交独立作业，保留日志、终态、失败原因与输出 seal，禁止自动重试。

现有云端启动与监督使用 systemd，迁往超算需要重新包装为 Slurm：绑定实际 partition/account/QoS、输入与日志路径、资源限制、退出码和终态回执，明确不自动 requeue。不能把旧服务启动命令或旧 issue27cd 的 sbatch 参数原样套用。

截图中的旧 issue27cd 标签属于历史任务，不能作为本轮提交入口。README 缺失也不能作为磁盘恢复失败或全部数据丢失的证据。

## 2. 两条实验链的准备不同

|链|已备|启动前还缺什么|
|---|---|---|
|第四步源侧 BASE/CTX/覆盖对照|源数据与候选索引、逐格行数/权重、执行卡、单 capture AfterImage 计时|Claude 收敛删样对照、seed 聚合、更新步数与速率报告；独立 trainer/runner、生产 MI15、测试和资源证明、HPC 作业包装、用户训练授权|
|补编码→密源 CAL→完整矩阵|v2 补编码包、冻结 21,660 新位置、原 104 数值门禁、密源 CAL 代码与准备资产；Claude r3 已给 WRONG/第三池最小规格|HPC 环境与包适配、原 104 实际逐 UID 字节门禁、输入验收；r3 对应完整矩阵 runner 与第三池检查仍待实现；用户执行授权|

第四步在超算可登记新环境、同机同环境配对训练，不要求新训练权重逐字节等同旧云端。若要回放旧 BASE，则单独检查数值/决策身份，不把新训练冒充旧终点复现。

补编码会把新 E3 与旧库拼接，**原 104 逐字节门禁必须在任何新增位置前向前通过**。当前生产包要求 torch 2.5.1、numpy 2.0.1、transformers 4.57.3、tokenizers 0.22.2、safetensors 0.6.2、huggingface_hub 0.36.2。截图中的 `py311-torch2-cpu` 名称不足以证明满足这些要求；安装相同版本也不替代实际门禁。若门禁失败，停在新编码前保存现场，再决定修复环境或登记独立谱系，不擅自放宽容差。

## 3. 数据上传预算与复用

以下为本地资产测得大小，**不是已核实的超算现存资产**：

- 第四步基础源 E3、q14、metadata、FIT/CAL 共约 2.40 GiB；通过 SHA 校验的现存副本可复用，不重新生成百万行 E3。
- 生产 MI15 尚未生成。若在超算流式提取，需要 169 个源 capture，原始数据约 10.34 GiB；也可在已验本地输入上按冻结规则先提取，再上传 92,007,240 bytes 的 float64 MI15 与定位/验收回执。后者需单独准备生产提取器并验证，不能复用计时输出（此次保存特征向量为 0）。
- 补编码 v2 tar 为 31,186,330 bytes；外部 checkpoint 为 698,780,900 bytes；密源 CAL 输入 seal 内资产约 2.41 GiB。当前可见组合约 3.09 GiB，尚不含依赖安装、额外校验文件、运行余量和后续完整 A/B 矩阵资产。
- 两条链共享的 E3/q14/metadata 只传一份，以只读 SHA 绑定；输入和新增输出分别记账。远端已有目录名相同不能当作身份一致。

容量按实际部署清单与站点配额核算，不仅看 `df`。源侧 CPU 即可；单 worker/4 线程、16 GiB 申请、8 GiB RSS 守卫、6 小时 wall 和 2 GiB 增量输出仅为现执行卡候选，须由实际计算节点 preflight 验证。此前源侧整轮 3–5 小时估计不含排队、传输、环境配置；补编码的耗时不能沿用云端速度直接承诺超算完成时间。

## 4. 可以先在已登录的 VS Code 远端 Bash 运行的只读命令

```bash
hostname
pwd
ls -ld "$HOME/work" "$HOME/work/paper04"
readlink -f "$HOME/work/paper04"
df -h "$HOME" "$HOME/work/paper04"
ls -la "$HOME/work/paper04"
command -v python python3 tshark sbatch sinfo squeue
sinfo -h -o '%P|%a|%l|%c|%m'
squeue -u "$USER"
```

命令不安装软件、不写文件、不启动训练、不提交 Slurm。若目录不存在保留原错误，不创建同名空目录掩盖路径问题。若命令或 Slurm 查询被站点禁用，记录实际错误；无需 sudo 或改变站点配置。此轮只取得目录/调度元数据，不读取封闭评价标签。

取得输出后再绑定真实项目路径、识别现有缓存与 Python 入口，并进行有针对性的文件字节数/SHA 核查；不扫描全 home、不先上传全部历史 run。若仍只有 VS Code 会话可用，可以由用户在该终端执行后续准确命令，不需要把密码发到聊天中。

## 5. 相关依据

- [第四步执行卡](20261026_step4_source_controls_execution_card_codex.md)
- [当前只读诊断回传](20261026_p1_p2_source_controls_preparation_response_codex.md)
- [补编码与密源 CAL 准备申请](20261025_c5_and_supplement_cloud_request_codex.md)
- [Claude r3 完整矩阵规格](20261026_c5_readout_matrix_spec_r3_claude.md)：其中旧“先补编码再原104门禁”的次序及可达性表述已被 [第四步 r1](20261026_step4_source_controls_r1_claude.md) 更正，不照旧顺序执行。

本文件是恢复连接后的准备记录，不授权正式实验，也不声称完整作业包已经可提交。

## 6. 用户回传后的更新：入口检查已完成，计算节点共享路径未验

用户于 2026-10-26 回传远端终端文本：入口为 node168，实际 home 为 `/public/home/jiangxinwei.zr`，项目目录存在；`assets/environment/frontend_compat_v1/frontend_followup_v1/hpc_e3_recheck_20261021_v1/incoming_20261020/runs/validation` 仍在。amd、gpu、intel 为 up，amd 最大 wall 14 天；用户 squeue 为空。`/public` 文件系统总余量约 506T，**不是用户/项目配额**；`command -v` 找到 `/bin/python`、`/bin/python3` 和 sbatch，未找到当前 PATH 下的 tshark。以上来自用户文本，不能标为本轮 Codex SSH 实测。

重新核对 [10月21日历史对照](../../hpc_e3_recheck_v1_20261021/YESTERDAY_COMPARISON_20261021.md) 后，优先级需更具体：原故障已在模型前复现于计算节点读取 `/public` 文件；原共享 Python 环境此前成功。因此先验证真实计算节点共享路径，随后再核对依赖/缓存，避免先重装环境或重传全量资产。旧 tshark 使用 `module load apps/tshark/4.6.6`，当前 PATH 不含它不证明软件消失。

已准备 [单次路径预检脚本](../../hpc_readiness_preparation_v1_20261026/probe_compute_shared_paths.sh) 与 [可复制命令](../../hpc_readiness_preparation_v1_20261026/RUN_ON_HPC.md)。它仅申请 amd 的 1 CPU / 1 GiB / 3 分钟，在 `/tmp` 启动干净 Bash；逐项 stat 共享路径、读取旧环境脚本 SHA 和共享 Python 版本，输出直回终端，不读取数据集、不 source 旧环境、不导入模型。没有提交该预检；由已登录 VS Code 终端执行一次后回传结果。

历史上阻塞 I/O 曾不能被 timeout/SIGKILL 正常清理，故这些时间限制不是内核 D 态的绝对终止保证。若再次卡住或失败，保存 job id/最后 marker 和错误，不自动重试或轮换节点扩散故障。此预检 PASS 仅表示所分配节点上的这些路径与 Python 可读，不代表整个集群、依赖、配额、缓存 SHA 或数值门禁通过。
