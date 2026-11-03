# H_AB 一次真实 T→E 授权记录

2026-09-13。REAL_T_E_AUTHORIZED，尚不代表运行完成或科学能力通过。

用户在上一条明确说明“下一步就是一次真实T→E（训练→评估），完整授权后自动衔接，异常停止、零重试”之后，
回复“动手下一步”。本次授权覆盖完整正常链，不在T完成后重复询问E权限。
它不扩大冻结配方、不授权额外尝试，不延续到其他候选或后继机制。

## 已完成的启动前只读核验

工作目录：D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline。
实际分支codex/exp-mainline；HEAD4b28747b09480471e2bac1beb3a9badf27280efb。
git status中的8项既有无关tracked修改及两份living文档保持；不切分支或重置。
实现检查返回IMPLEMENTATION_READY_NO_REAL_EXECUTION，原运行时、源码与无关修改hash均通过。
启动前真实T/E均为NOT_STARTED，未创建对应输出目录。

冻结设计SHA：dc801799efe4c73b22b6cc57694d47a4f7860650316bb3651967ad5f7cf718e7。
冻结recipe SHA：36a6fb18a52b4ab212f3a7eff7fbb0b37a8d124d7f79cd9ed56b6f4f68d89417。
实现包manifest SHA：c13e309308cd27c64f9f1bc7268077401cdd370890bf3110f4e42dae622e7329。
合成验收41/41 PASS；这不等于真实输入预检或科学结果通过。

## 本次执行范围

T：核验完整AB起点原生身份、固定TRAIN输入及旧C0_AB顺序；仅训练H_AB一个候选。
冻结82944个事件投影/GRU参数，保持完整AB检测头初始化，只更新8321个MLP参数。
同15073条TRAIN，seed2705、20轮、197步/轮、lr1e-4，共3940更新及7880forward。
T只解码97808792字节TRAIN前缀，混合文件全hash不等于解码CHECK。
无P、教师、guard、投影D及额外拟合观察；不做额外初始评估或checkpoint选择。

E：仅在T核验并封存成功后自动进入，一次加载新H_AB，固定TRAIN15073+CHECK3193+
expanded262050=280316目标、2207forward。普通ID151是CHECK子集，无额外forward。
旧模型只引用已有分数，不重跑；原六项Fraction判读、1%/0.1%、逐族/逐池与翻转报告不变。
相对AB和C0_AB比较；历史严格FAIL、联合NOT_REACHED、新设备入网NOT_EVALUATED不预先改变。

T上限4小时/8GiB/512MiB，E上限30分钟/8GiB/512MiB，包含各自入口和封存。
本地持久隐藏监督进程执行，正常转换自动继续；程序异常STOP、零重试，不启动后继阶段。
科学效果差仍完成固定评估并封存，不能因此重训、改阈值或改门槛。
无历史重跑、F4重做、下载、新数据、HPC、资源复试、超参搜索或LLM轮询/定时任务。

执行入口（本记录封存后调用一次）：

```powershell
./scripts/start_frontend_ab_readout_preservation_v1.ps1 -Stage TE -AuthorizeTraining -AuthorizeEvaluation
```

只读状态：`scripts/show_frontend_ab_readout_preservation_v1.ps1`。
输出：`runs/frontend_ab_readout_preservation_t_v1_20260913/`及对应`_e_`目录。
各阶段`status.html`自动刷新；`supervisor_terminal.json`及manifest确定最终执行状态，E的`result.md`提供结果。
启动快照将写入living交接；运行终态优先于任何先前快照。

solved: 一次真实T→E授权范围及启动前工程身份确认。
changed_mainline: yes（真实执行获授权，尚无新科学结果）。
active_blocker: 核心联合能力待本次固定终点检验。
frozen: H_AB设计/recipe/实现与历史产物；零重试。
superseded: 本候选“真实T/E尚未授权”的当前效力。
next_action: 启动一次冻结T→E，由本地监督完成正常链或异常停止。
