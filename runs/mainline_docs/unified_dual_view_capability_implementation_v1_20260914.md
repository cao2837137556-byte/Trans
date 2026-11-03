# 双视图能力基线：实现完成与合成验收

2026-09-14。用户“可以，动手实现”授权实现及生成验收。本次真实 P/T/E 均 NOT_STARTED。
结论：IMPLEMENTATION_READY_NO_REAL_EXECUTION；33/33 合成验收通过，执行器及依赖闭包已封存。
不是科学通过，没有产生任何新的真实能力结果。

## 已完成

- 新版入口 `repo/ood/issue27dualview_control_v1.py`，独立 P/T/E worker，单 Windows Job，异常停止、零自动重试。
- P 核验旧 AB 身份与既有角色/依赖分组，只提取 TRAIN 因果 GRU 状态；E3 压缩容器仅对获准行作数值解码。
  全部9402有效TRAIN包括23个教师判错正常；缺失标记不依赖label/old_hard。NPZ输入身份与目标前缀侧车严格核对。
- 标准化仅拟合TRAIN，有效E3使用全部9402行；缺失在标准化之后置零，B仍保留真实AB内容。
- T 不加载 AB 或 E3，使用封存表示训练两个897→128→1新头，真实配方各50轮/2950更新，合计5900更新。
  两臂相同初始参数与每轮顺序；类别均衡逐目标BCE，包含末批225行；只交付第50轮终点。
- E 在P/T完整核验封存后才读CHECK/expanded表示；固定AB编码器仅再加载一次，在两臂间复用状态。
  全部560632次末态评分，保留旧六指标、0.1%点、族/池、A/B、CHECK/ID、翻转与误报尾部。
  旧P2没有ROC不伪造；历史失败和入网NOT_EVALUATED保持。
- 本地追加式progress日志、自动刷新status.html、启动与查看PowerShell脚本；无需LLM持续轮询。

## 验收证据

正式生成验收33/33 PASS，耗时47.704秒。覆盖实际P/T/E函数及Windows supervisor完整衔接，
两个生成头均运行50轮；使用缩小的生成目标集合，不使用真实TRAIN或CHECK做smoke。
覆盖独立损失数值参考、原AB编码数值等价与因果性、冻结参数、零方差、非有限输入、相同mask/初始化/顺序、
教师判错正常仍有E3、禁用行NaN不被解码、跨角色拒绝、身份/前缀漂移、精确ties、无授权入口拒绝及失败/超时封存。
两份PowerShell脚本解析通过。

首轮32/33通过：生成Windows链夹具的资源门与夹具recipe不一致，按CAP_DRIFT正确停止。
修正的是生成夹具的预算配置，使门和recipe一致；真实冻结资源上限没有变化。
随后完整33/33通过。该机械修复属于本次实现授权，不是实际实验重试或资源试验。

合成进程安装文件/网络访问审计钩子，拒绝真实run数据、真实checkpoint、真实E3 NPZ及网络连接。
真实模型forward、真实教师行、真实优化器更新均为0；原始包解码、E3模型加载/forward、下载与HPC均0。
实现阶段只额外核对了已披露缓存audit的plan/contract身份和既有expanded目标清单pin，没有打开其数值缓存。

封存实现包：`runs/unified_dual_view_implementation_v1_20260914/`。
SHA256SUMS：`33b69e49a1468cff91507db7f5d53ff2ad3b522a75347a55e742b0cfc46f5d83`。
acceptance.json保存测试结果与对应源码/文档hash；config.json保存执行依赖、运行时和保护文件身份。
独立只读入口 `check-implementation` 返回 IMPLEMENTATION_READY_NO_REAL_EXECUTION；status返回P/T/E全部NOT_STARTED。
真实输出目录均不存在。原45项参考源码和8项无关tracked文件hash复核一致；分支/HEAD仍为codex/exp-mainline/4b28747。

## 下一步及用户可见状态

下一步是真实执行：一次明确P→T→E授权应包含P的9402条E3 TRAIN数值行及E的199395条有效CHECK/expanded数值行。
P只做TRAIN表示准备与封存；通过后两个新头训练，再进行一次完整终点评估。正常衔接自动完成，不重复问授权。
身份/分母/前缀/角色/资源超限或其他异常停止；没有自动补轮、重试、重新解流量、启动E3或额外候选。
真实资源上限仍为P1800s、T1800s、E3600s，进程树8GiB、新产物总量4GiB；这是停止预算，不是完成时间实测。

启动入口：`scripts/start_unified_dual_view_v1.ps1`；本轮未调用启动。
状态入口：`scripts/show_unified_dual_view_v1.ps1`，可随时查看P/T/E状态。
未来各阶段目录 `runs/unified_dual_view_{p,t,e}_v1_20260914/` 的status.html自动刷新，
展示表示准备/训练/评估、完成量、耗时、异常原因；只有最终核验封存完成才显示完成。

solved: 角色隔离缓存装配、新共享头两臂训练、完整终点及本地监测实现完成；生成验收通过。
changed_mainline: no（实现同日封存设计，未改变科学规则）。
active_blocker: 真实能力增量尚未验证；新真实P/T/E尚未授权或启动。
frozen: 设计、配方和本次实现封存；历史协议、结果及无关修改保持。
superseded: 实现尚未开始的当前效力；设计与历史证据保留。
next_action: 获得一次明确完整真实P→T→E及指定E3缓存行授权后执行，正常衔接自动、异常停止零重试。
