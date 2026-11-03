# H_AB 固定编码器、完整检测头适配：实现与合成验收

2026-09-13。IMPLEMENTATION_SEALED / GENERATED_ACCEPTANCE_PASS / REAL_T_E_NOT_STARTED。
用户授权“动手，授权下一步”，承接已冻结设计的实现与生成验收；本次不启动真实T/E。
本记录更新工程状态；联合能力NOT_REACHED、历史严格继承FAIL、新设备入网NOT_EVALUATED保持。

## 本次完成

H_AB完整继承封存AB，固定事件投影和GRU的82944个参数，只训练完整MLP的8321个参数。
不重置检测头。优化器为空状态的AdamW，只接收检测头参数，lr=1e-4；复用原C0数值更新。
冻结部分梯度始终None、不产生优化器状态，每轮末和终点逐张量核对身份。
这可以检验：保留AB已经学到的表示，再适配判断攻击的检测头，能否同时改善攻击和OOD。
冻结表示本身不保证最终检测能力或分数排序保持。

T入口核对原生AB文件/receipt/terminal及C0_AB训练生产身份和原始20轮顺序。
混合特征文件只作完整不透明hash；T仅解码TRAIN前缀。没有教师准备阶段、教师/保护缓存、投影D，
也没有终点教师拟合观察。T唯一终点为H_AB；通过核验封存后才可进入E。

E一次评估TRAIN15073+CHECK3193+expanded262050=280316个目标，2207次forward。
原ID151从CHECK结果中单独报告，不增加forward，不加入18000条正常OOD分母。
历史A/AB/C0/C1/C2/Q/R/C0_AB/R_AB/P2只复用保存分数；主要对比H_AB−AB和H_AB−C0_AB。
原六项指标按整数分子/分母及Fraction比较；1%/0.1%整组ties、逐族/逐池风险、翻转和尾部组成保持。

新增10个`repo/ood/issue27frontend_readout_*_v1.py`模块，包括support/model/entry/train/evaluate/
verify/control/fixture/tests/build；旧执行器原字节保留。
启动：`scripts/start_frontend_ab_readout_preservation_v1.ps1`。
状态：`scripts/show_frontend_ab_readout_preservation_v1.ps1`。
本地持久监督、隐藏数值worker、自动刷新页面和终态封存继续使用已验证的机制，不需要LLM轮询。

## 验收证据

最终 **41/41 PASS**。验收报告计时13.718秒（unittest主体13.342秒），一次合成套件运行通过。
两份PowerShell脚本解析PASS。验收没有真实模型加载、真实特征数值读取、真实forward、
真实optimizer更新或真实教师读取；进程审计钩子禁止访问runs中非文档真实文件，包括JSON和checkpoint。
临时生成资产位于`tmp/readout_synthetic_v1/`，不写入真实T/E目录。

关键覆盖：

1. 连续三步与直接冻结原Student后的原C0更新逐参数、AdamW状态、loss、梯度范数和裁剪完全一致；
   全部解冻时适配器同样与原C0一致。另用独立BCE计算核对上下文/owner归一化。
2. 检测头两层所有参数更新，六个冻结张量身份不变；冻结梯度、优化器成员/状态或张量被改动时拒绝。
   原完整Student输出一致，早期目标的因果前缀不受未来事件改变影响，33上下文的microbatch计数正确。
3. 实际train/evaluate/verify函数在生成资产上完成T→E；仅加载生成AB和新H_AB各一次。
   教师、guard和投影函数替换为报错后仍完成；所有禁用访问计数为0。
   11个模型条目、两个主对比、ID子集、精确目标/更新/forward计数和参数身份核验通过。
4. 入口不调用模型加载/forward/optimizer；错误AB身份、C0生产SHA/计数/顺序、前缀或角色泄漏被拒绝。
   缺失/错误候选屏障在模型加载前停止；落盘指标或冻结receipt篡改由无新forward的复核识别。
5. 关键指标函数与原AB-start源码AST相同；整组ties不拆分、不强填误报额度，AUROC和Fraction对照通过。
   修改显示舍入值不改变科学标志；0.1%风险独立于原六项联合标志。
6. 缺失/旧授权和重复启动被拒绝；正常T→E无需第二次授权，STOP不启动E或重试。
   Windows实际生成进程的成功、故障和墙钟限额终止通过；打开状态文件时写入兼容，终态保留完成量。

完整测试日志与所测试的源码hash位于实现包`acceptance.json`。这些是工程验收，不是攻击继承通过。

## 封存及保护

实现包：`runs/frontend_ab_readout_preservation_implementation_v1_20260913/`。
SHA256SUMS SHA256：`c13e309308cd27c64f9f1bc7268077401cdd370890bf3110f4e42dae622e7329`。
config SHA256：`b1b788fcf0a3e2ca7ef28a7cffa7455033b07eecb41f6e2c0135804eb5c694e2`。
包内config/acceptance/README均纳入manifest，锁定44项源码/设计/配方/脚本依赖。
生成验收前后、构建封存时的源码hash一致；旧AB-start实现包47项pin、原运行时及8项无关tracked文件核验通过。
分支仍为codex/exp-mainline，HEAD仍为4b28747b09480471e2bac1beb3a9badf27280efb。
没有切分支、新建worktree、重置、提交、修改冻结方案或重跑历史实验。

只读`check-implementation`返回`IMPLEMENTATION_READY_NO_REAL_EXECUTION`；
状态脚本返回T=NOT_STARTED、E=NOT_STARTED。这是实现身份就绪，不冒充真实输入预检或真实训练完成。

## 下一步与执行边界

实现已完成。下一步为一次明确授权的真实T→E：先入口核验，再H_AB固定20轮/3940更新，
完成核验封存后自动执行固定280316目标的E。正常转移不再询问；异常STOP、零重试。
T上限4小时/8GiB/512MiB，E上限30分钟/8GiB/512MiB，均包括各自入口与封存。
没有新增P、资源试验、数据下载、HPC、超参搜索或LLM定时任务。

以后获完整真实T→E授权时的执行命令（本次未执行）：

```powershell
./scripts/start_frontend_ab_readout_preservation_v1.ps1 -Stage TE -AuthorizeTraining -AuthorizeEvaluation
```

只读查看状态：

```powershell
./scripts/show_frontend_ab_readout_preservation_v1.ps1
```

未来启动后，T/E对应输出目录的`status.html`每5秒自动刷新，最终以封存终态和E的`result.md`为准。
若H_AB相对AB仍权衡/无变化/退化，按冻结决定结束当前15073条TRAIN上的相邻微调，
下一干预须有新增输入信息或合格训练覆盖依据。结果好也仅是需审查风险的开发候选。

solved: H_AB实现、41项生成验收、封存及只读实现检查完成。
changed_mainline: yes（工程就绪，无新科学结果）。
active_blocker: 核心联合能力仍未解决；新真实T/E尚未授权或启动。
frozen: 既有设计/recipe、新实现包及全部历史产物。
superseded: “实现下一步”已更新为“实现完成，真实T/E下一步”。
next_action: 获一次明确真实T→E授权后执行完整固定链，异常停止零重试。
