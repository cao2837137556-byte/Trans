# 任务知识迁移 V1：实现与合成验收

2026-09-11。状态：**IMPLEMENTATION_AND_SYNTHETIC_ACCEPTANCE_PASS**。
用户在方案完成后授权“那就动手下一步吧”，本步范围为实现及合成验收。
真实P教师物化、T三臂训练、E终点评估均为NOT_STARTED，尚无本新配方真实执行授权。

## 冻结依据与实现身份

- 方案：`frontend_task_knowledge_transfer_design_v1_20260911.md`，SHA256
  `cba8f3726c7b8318d309d59ce9afc0552941227e75e3f6700e0994d0a6598eb6`。
- 配方：`frontend_task_knowledge_transfer_recipe_v1_20260911.json`，SHA256
  `7707807c49950fbffe47d2025ce6ceb6edf7106d588b04e688afe41baacd9513`。
- 实现包：`runs/frontend_task_knowledge_transfer_implementation_v1_20260911/`。
  `SHA256SUMS` SHA：`5130c6a473cb7251cbe335b14c11d4e39b1b4c6e7251231890707020efeecfad`。
  `config.json` SHA：`c12bbc81a632e8679134c8f6d068b929663484d9199cab713682c4053cbed027`。
  `acceptance.json` SHA：`ea8499e7887f6018d0ed8d43a555aeafb51dc3963297611b6a8d2a7c854c568e`。
- 封存40个代码/依赖/脚本/协议文件身份及固定Python3.9.13、NumPy2.0.2、torch2.8.0+cpu
  运行时身份。HEAD仍为`4b28747b09480471e2bac1beb3a9badf27280efb`，分支`codex/exp-mainline`。
  八个已有无关tracked文件的SHA与原基线逐项相同；未切分支或新建worktree。

## 已实现

代码位于`repo/ood/issue27frontend_transfer_*_v1.py`，独立版本保留全部历史执行器：

| 模块 | 工作 |
|---|---|
| support | 固定配方、输入身份、train白名单、原批次顺序、A代表及配对 |
| model | 原学生前向等价的因果GRU状态读出；C0/C1/C2损失；零初始化训练专用D；统一裁剪 |
| prepare | 仅9,379条教师白名单进入表示数值数组；六个P2状态数组；原hard数值核对、贡献/RMS及隔离缓存 |
| train | 三臂各自复制A、重置优化器；20轮×197步；每步损失/梯度记录；三臂最终状态封存屏障 |
| evaluate | 每臂一次train/check/扩大池终点；固定0阈值；合并池ties一致的低FPR曲线；分族/池/输入归属和逐目标翻转 |
| control | 分阶段授权、单worker Windows Job、时间/内存/输出监督、独立产物校验、状态页及零自动重试 |
| tests / fixture / build | 生成数据测试、隔离监督夹具、源码依赖闭包和验收封存 |

教师侧不读取其他角色的标签或表示数值；物理混合容器的完整UID/missing身份数组访问
将如实记录。T只解码train的已有F4前缀；E在三臂终点全部封存后才读check/扩大池输入。
无netFound重跑、原始包解码、超算、新数据下载或运行时旧P2分流头。

## 验收证据

**43/43合成测试通过**，实际固定Python3.9.13环境完成。包括：

- 原学生逐输出完全相同；packed变长排序、短序列padding及早期目标因果性。
- D不消耗随机数；首步教师项编码器梯度为零，此后能回传；D从部署状态移除。
- 真标签上下文均值、类别/上下文教师分母、A代表轮转、配对方向和空桶行为。
- 教师规范float32 hard及float64重构；RMS按上下文/类别均衡。
- 合成混合NPZ完整白名单物化和缓存重读：未授权行含NaN仍不进入数值数组；缺失教师立即停止。
- 三臂合成微型训练：同初始化/呈现/顺序；独立普通BCE参考更新与C0相同；各终点可由原部署学生读取。
- ties整体处理、整数FPR边界、独立正负配对枚举AUROC核对、同一合并阈值的分族召回。
- 未授权入口/重复尝试拦截；轻量控制器中的单进程Job；生成模型在Job中导入及前向；
  完成封存、缺终态、输出篡改、超时停止与零重试。

首轮合成测试35/37通过，暴露的是测试夹具问题：数值测试主进程导入torch后不适合
充当512MiB预留的轻量控制器，以及RMS参考式误用了float32除法。
已改为独立轻量控制器、按冻结float64→float32语义构造参考；未改真实预算或损失。
最终43项全部通过。测试中的requires_grad标量转为float产生过PyTorch提示，不影响结果；
正式训练日志使用detach，未据此改变梯度路径。

新实现额外只读既有train plan与保存分数，核对：15,073监督目标、9,379教师目标、
9,400保护目标、`s_A=29.98624610900879`全部与封存设计相同。
这不是新教师前向或重做F4字段审计。PowerShell两个脚本语法解析通过；封存后的
`check-implementation`通过，状态脚本返回P/T/E三个NOT_STARTED。

本步实际真实模型加载/推理/优化器更新/教师数值提取/原始解码均为0。
测试仅创建生成模型和生成数据，不能当作真实训练稳定性或科学能力证据。

## 启动、可见进度与后续授权

只读状态入口：

```powershell
./scripts/show_frontend_task_knowledge_transfer_v1.ps1
```

真实运行目录分别为：

- `runs/frontend_task_knowledge_transfer_p_v1_20260911/`
- `runs/frontend_task_knowledge_transfer_t_v1_20260911/`
- `runs/frontend_task_knowledge_transfer_e_v1_20260911/`

启动后各目录提供自动刷新的`status.html`、`status.md`、`progress.json`；
以`supervisor_terminal.json`及有效`SHA256SUMS`为终态。E结果为`result.md`和`comparison.json`。
控制器独立于对话持续工作，不创建周期性LLM轮询。

后续用户可一次明确授权P→T→E：P通过才训练，三臂全部封存才评估，任何异常停止且不重试。
P上限30分钟/8GiB/128MiB，T合计4小时/8GiB/512MiB，E合计30分钟/8GiB/512MiB；
校验和封存包含在阶段预算中。这是上限，不是实测耗时承诺。

**以下命令只在取得该完整真实授权后执行，本轮未执行：**

```powershell
./scripts/start_frontend_task_knowledge_transfer_v1.ps1 -Stage PTE -AuthorizeTeacherPreparation -AuthorizeThreeArmTraining -AuthorizeEndpointEvaluation
```

真实P还须确认9,379 UID在旧容器中唯一存在且missing=False。该条件不能由合成验收替代。
旧P2历史见过当前check标签、扩大池已暴露、单seed及辅助训练混杂等科学限制继续适用。
程序不会自动宣告实用继承成功，旧FAIL保留；新设备入网尚未进入本实验。

solved: 封存配方的实现和生成数据验收完成。
changed_mainline: yes，下一步由实现转为待授权的真实P/T/E。
active_blocker: 真实教师映射/缓存、真实数值稳定性与攻击/OOD联合效果尚未检验。
frozen: 原方案、分母、seed、损失、模型、预算与历史结果均未修改；新实现独立封存。
superseded: 本新配方尚无实现的状态。
next_action: 取得真实P/T/E范围授权后，依次进行教师准备、三臂训练与一次终点评估。
