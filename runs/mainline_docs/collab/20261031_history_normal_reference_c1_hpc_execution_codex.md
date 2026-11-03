# 历史正常参考 C1：超算提交与启动回执

2026-10-31，北京时间 14:43:26 提交，14:43:46 首次启动回读。状态：`SUBMITTED_WORKER_RUNNING`，不是科学结项。

用户已授权“允许下一步”，暂停使用电脑后又明确要求“那你先把实验继续推上去”。此次落实为一次固定 C1 / P-DEVONLY 作业；随后用户要求“不用一直监测”，因此确认启动、保存本回执后结束 AI 跟进。右侧只读页面由普通程序更新，不建立新的 AI 定时任务。

## 提交与当前状态

- 作业 **180433**，`amd` 分区，计算节点 **node185**。Slurm 与真实 worker 均为 `RUNNING`；回执中保留调度状态原文。
- 资源为 4 CPU / 16 GiB / 最多 8 小时，`--no-requeue`；中间产物≤20 GiB、新唯一 E3≤36,864、距离对≤579,614,444 仍由科学运行守卫约束。
- 输出固定为 `/public/home/jiangxinwei.zr/work/paper04/runs/history_normal_reference_v1_20261031/outputs/c1_once_20261031`。单次提交锁及全局科学尝试锁生效，实际仅提交一次。
- 首次真实快照：`CHRONOLOGICAL_COPY`，TP Link，79,773 / 79,773 原包，worker 已用约4.65秒，峰值内存约0.41 GiB；新增编码0、距离对0。该快照确认已开始真实输入准备，不能当作整个成员、DEV 或 A/B 完成。
- 当前无新的 DEV 门结果或 A/B 指标，2%目标仍未知。DEV 不通过则按合同停止；通过才进入一次 A/B，不重训或重校准。

## 交付与环境验收

1,433项清单共5,720,467,843字节已全部齐备。远端723项原有文件逐件SHA匹配复用，缺失材料上传至独立 incoming 后，经全量验证无冲突才安装。冻结权重另从已核验的 `incoming_20261020/model.safetensors` 以硬链接复用，SHA为 `e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105`；没有用符号链接绕过文件资格。

远端只读预检 **PASS**：原始输入/资产完整SHA、完整源码及vendor集合、设备与时间索引绑定、材料READY、实际依赖导入、56项生成数据测试全部通过。实际环境为 Linux / **Python3.11.11 / NumPy2.0.1 / Torch2.5.1**，沿用原私有overlay。

部署时实际发现 `tshark` 由原环境模块提供，路径为 `/share/software/tshark-4.6.6/bin/tshark`，并非先前准备副本中的 `/usr/bin/tshark`。仅修正远端交付配置的该路径，保存旧映射/清单及修正回执；科学参数、输入SHA与原科学包不变。

| 身份 | SHA256 |
|---|---|
| 原科学包代码封印 | `31ab70c41014427a49c5ce134dba269e2bbade54e911ca5e1d674ab3ad95b84e` |
| 最终远端代码封印 | `5f6156601d0d3d9223c7ca7646b3b6e21547c5d703e4ef9046e6a08e81b1a0a3` |
| 最终交付输入清单 | `95bf17e2be0a46cedff33cd2efe15f73975eaa99c111354e75a96658093242e9` |
| 远端环境验收回执 | `cbd19cf654dcaae5803482070c30769610dec652ecaf9d5e3d8943fa188014a6` |

两个代码封印的1,361个键相同，只有路径映射后的 `config/EXECUTION.json` SHA不同。未把未审查的远端源码差异重新封印。

交付期间有一次连接超时和一次本机 Windows 进度文件占用，均保留中断回执后校验续传。对 Windows 原子重命名增加了有界本地重试，并通过模拟占用回归检查；它不重发科学操作。上述中断均发生在提交前，没有因此重复运行实验。

## 证据与进度入口

- [首次启动完整回读](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_deployment_20261031/runtime/STARTUP_REMOTE_READBACK.json)
- [一次交付流程结项](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_deployment_20261031/runtime/PIPELINE_STATUS.json)
- [安装动作回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_deployment_20261031/runtime/INSTALL_ACTION_RECEIPT.json)
- [环境验收动作回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_deployment_20261031/runtime/PREFLIGHT_ACTION_RECEIPT.json)
- [提交动作回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_deployment_20261031/runtime/SUBMIT_ACTION_RECEIPT.json)
- [实际工具路径修正](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/history_normal_reference_deployment_20261031/decoder_mapping_correction/CORRECTION_RECEIPT.json)
- [Codex 内只读进度](http://127.0.0.1:18785/)，已实际打开并保留。上传、环境验收、worker工作心跳与Slurm状态分别显示；断联保留已有快照，服务刷新不冒充worker推进。

Antigravity 或新对话接手时，以本回执作为早先“交付就绪/暂停/未提交”之后的新状态；原始暂停记录保留作历史取证。不要凭旧进度条、旧授权描述或尚未运行的实现回执重复提交。
