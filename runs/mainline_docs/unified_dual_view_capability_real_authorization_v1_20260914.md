# 双视图真实 P→T→E 执行授权

2026-09-14。用户在“实现与验收完成，下一步一次完整真实准备→训练→评估授权”的交付后回复“授权下一步”。
本次授权承接该明确范围：一个本地 P→T→E 流程及指定 E3 缓存行，正常阶段自动衔接，异常停止、零自动重试。
这是新真实执行授权记录；不改写旧设计、配方中的历史授权状态或历史实验结果。

## 固定执行身份

- 工作目录：D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline。
- 分支 codex/exp-mainline；实际 HEAD 4b28747b09480471e2bac1beb3a9badf27280efb。
- 设计 SHA256：580690aef6b2b5740bd5c56df37ba939f6e7688070f6f49351636ea08f9286b2。
- 配方 SHA256：4d8f18a890b9eae3c45f50a16c4fdf66356aa5e86f24872d83afedc0a287b481。
- 实现目录 runs/unified_dual_view_implementation_v1_20260914/；SHA256SUMS：
  33b69e49a1468cff91507db7f5d53ff2ad3b522a75347a55e742b0cfc46f5d83。
- 实现验收33/33 PASS；启动前 check-implementation 返回 READY，P/T/E 均 NOT_STARTED。
- 所有已有无关修改保护；不切换分支、重置工作区、新建 worktree、改旧执行器或重跑旧实验。

## 本次可执行范围

P：只读取现有合法15073 TRAIN的因果F4输入，加载固定AB编码器一次，提取128维状态。
从已固定 fit/select E3 NPZ 中只数值读取9402条有效TRAIN行，包含教师判错的23条正常。
按UID/前缀/缺失位/依赖角色核验，仅TRAIN拟合标准化后封存。其他表示行保持不透明字节，不进行优化器训练。

T：P核验封存后，两个新共享头 U0/U1 各训练一次，固定seed2705、50epochs、batch256、类别均衡逐目标BCE。
每臂2950更新，合计5900更新；U0零E3内容/U1真实E3内容，两臂可用mask、初始化、顺序和训练规则相同。
T仅使用P封存表示，不重新加载或更新AB/E3。仅第50轮终点，无搜索、早停选优或额外候选。

E：两个T终点核验封存后，加载固定AB编码器一次供两臂复用，准备3193 CHECK及262050 expanded目标的状态。
从fit/select缓存数值读取2127有效CHECK行，从既有report E3缓存数值读取197268有效expanded行，总199395行。
明确允许本次这组report缓存表示行；不扩展到其他report/select/viewed/真正FINAL资料或新查询集合。
每臂评分280316=15073 TRAIN末态审计+3193 CHECK+262050 expanded，总560632目标呈现；ID151已包含在CHECK中。
复用冻结历史评分，仅进行新终点评估，完整报告攻击、正常、低误报尾部、A/B、每族每池及翻转。

E3缓存身份、行范围与侧车均按固定recipe执行；缺失、hash、前缀、角色或分母不一致停止。
零E3模型加载/forward、零原始包解码、零下载/HPC、零资源重试、零历史重跑、零LLM定时轮询。
本地controller和Windows Job负责持久进度与故障退出；P1800s/T1800s/E3600s，进程树8GiB，新产物总量4GiB。
上述为资源停止上限，不是完成时间或性能承诺。

启动入口 scripts/start_unified_dual_view_v1.ps1；状态入口 scripts/show_unified_dual_view_v1.ps1。
各阶段 status.html 自动刷新；最终状态以 supervisor_terminal.json、verification.json 与SHA256SUMS一致核验为准。
单次有界启动状态核对用于确认启动，不设置持续模型轮询或定时任务。

solved: 本次完整真实流程和指定缓存行的授权明确，启动前身份/入口核对完成。
changed_mainline: no（执行固定双视图设计）。
active_blocker: 真实能力结果尚待执行；若发生异常停止，不自动重试。
frozen: 现有设计、配方、实现、数据角色、分母、预算和历史科学结论。
next_action: 启动一次本地P→T→E，正常自动衔接；不另行申请正常阶段转换授权。
