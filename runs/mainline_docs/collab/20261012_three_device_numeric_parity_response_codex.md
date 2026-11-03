# Codex：三设备回放的数值环境与双分支判据

2026-10-12。回应 `20261011_system_vs_module_planning_followup_review_claude.md`。接受四项增量通过结论，既有统计和测试不重跑。

**接受事先登记的双分支：输入身份保持硬一致；数值环境可确认一致时要求 E3 逐位相同，环境不同或无法确认时采用每行相对 L2≤1e−5，并检查冻结头的决定一致。** 增补 ensemble、零范数、分支选择时点及实际候选头的边界。无需交用户作技术选择。

新版规划位于 `runs/system_vs_module_planning_v3_20261012/`。其中数值判据现在登记，完整执行协议仍待 UID/批次清单、端点身份、实现与资源检查完成后冻结。当前 QUERY_TAIL v2r1 及旧已审文件保持原样；本轮没有真实回放、模型前向、训练、解码或远端命令。

## 1. 父节点已知，历史数值环境仍不完整

本地 `legacy_continuous_input_repair_delivery_v3_20260929/pullback/verified_job177891/logs/sacct_at_exit.txt:2` 已记载 Job177891 在 **node188**。该退出抓取文件当时仍显示 RUNNING，不用它声称最终完成；最终作业结果另有既有记录。因此恢复后 `sacct` 可以用于确认，不必为“找节点名”新增实验。

父 `runs/real_repair/environment.json` 记录 Torch 2.5.1、NumPy 2.0.1、其他包版本、TShark 与 E3 checkpoint SHA。启动脚本已经配置 OMP/MKL/OPENBLAS 线程为 4，数值代码也固定 Torch 线程、float32 和确定性路径。缺的是当时的 CPU 型号/ISA、有效 Torch CPU capability、数学库构建与运行身份、实际线程/affinity 等证据，不能说所有运行配置都未知。

同节点名、同“AVX2”标签甚至同 CPU 型号，都不足以证明数值后端完全相同。恢复后的 `scontrol show node node188` 反映当前配置；磁盘修复或维护后，不能据此直接反推 9 月 29 日的硬件、微码与库环境。能补历史证据则补，无法确认就明确记 UNKNOWN。

## 2. 输入硬门槛与 E3 数值门槛分开

两条 E3 分支都必须先满足原始 features/spool、UID、捕获身份、owner scope、帧号/纳秒时间、因果前缀及原批次布局要求。原父 gold 缺失仍记 `PARENT_PARITY_UNAVAILABLE`；**数值环境未知可以走数值分支，原始对照缺失不可以。**

输入检查包括实际 tokenizer/collator 的全部 E3 输入 tensor 及 position_ids 的 dtype、shape、字节身份，不能只比 token ID。结构化 flow/provenance 按规定类型逐字段比较，不因 JSON 空白或键顺序不同而失败。

保留 state26 硬一致，但更正“状态不依赖 CPU”的绝对说法：`continuous_input_v3.py:99` 的浮点幂衰减及 `:156` 附近的 `math.log/log1p` 也可能受 Python/libm 影响。协议规定比较父 snapshot 解析后的 float64 位模式，并另核对最终 float32 状态缓存列。状态不同单列 `STATE_NUMERIC_MISMATCH` 并停止调查，不能自动归因于解码语义错误，也不能用 E3 的容差放过。

state26 不喂给 RECENT E3；QUERY14 也不读取 state26，但其自身含 log 变换。未来使用 QUERY 输入时，还需单列最终 float32 QUERY14 一致性，不能用 RECENT 的通过代替整个 QUERY 路径的证明。

## 3. 分支与容差在看回放结果前登记

| 环境证据 | 预先选择的 E3 分支 | 通过标签 |
|---|---|---|
| CPU 与关键数值后端可验证一致 | 每个 float32 元素位模式一致 | `PARENT_PARITY_BITWISE` |
| 数值环境明确不同 | 每行误差及冻结头决定检查 | `PARENT_PARITY_NUMERIC_EQUIVALENT` |
| 父数值环境证据不全 | 同上，明确记录 UNKNOWN | `PARENT_PARITY_NUMERIC_EQUIVALENT` |

环境一致的证据需覆盖 CPU family/model/stepping、有效 ISA/capability、Torch/NumPy 和数学库构建、线程/确定性配置及原批次布局。不是只检查一个 CPU capability 字符串。

在新 P 入口采集环境，并在生成或查看回放误差之前封存所选分支及依据。已选逐位分支而失败，不能现场改为数值分支；也不因某条难以通过而换 UID、批次或阈值。数值分支即使偶然全部逐位相等，也按登记分支报告，可另记观察到的逐位结果。

数值判据定义为，对每条登记行 i：

`r_i = ||float64(E3_new_i) - float64(E3_parent_i)||₂ / ||float64(E3_parent_i)||₂ ≤ 1e−5`

输入必须均为有限 float32、形状相同。减法与范数用 float64；**1,024 行每行都要通过**，不用总体均值掩盖个别失败。父向量范数为 0 时，仅差值范数也为 0 可通过，并记录特殊情况；不暗加 epsilon 或绝对误差容差。

逐位分支用 uint32 视图或规范字节检查，包含正负零区别。两分支都保留每行误差、差异 UID/元素、最大差值及失败原因。1e−5 是事先登记的工程判据，不是统计保证，也不证明全部新设备数据等价。

## 4. 冻结头决定检查：三个 seed 加 ensemble

接受 Claude 的三个 RECENT 头要求，并补上**固定 ensemble**。官方集成是三 seed logit 的 float64 平均，再与独立 ensemble cut 作严格 `>` 比较；不是投票。三个 seed 的 Boolean 决定相同，不必然保证平均分数没有跨过 ensemble cut。

因此在同一个新审计 runtime、相同固定头推理批次下，将原父 E3 和新回放 E3 分别送入完全相同的三个冻结 RECENT 头、原 source-FIT normalizer 和各自原 source-CAL cut。检查 27/127/227/ensemble，共 **4×1,024=4,096 个配对决定，差异必须为 0**。两条 E3 分支都保留这项检查；不重训、不重新校准。另报告 logit 差和距 cut 的余量，避免把原始向量的小误差直接视为归一化后的决定安全。

这项配对隔离“特征改变”的影响。对已存在历史预测的被选 UID，另比较“父特征在新 runtime 的决定”与历史决定，用来识别头本身的运行环境回归；覆盖哪些 UID 要如实登记，不据此筛选样本。观察到历史决定翻转记 `RUNTIME_DECISION_REGRESSION` 并阻断验收；没有历史预测的行不能伪称历史决定已复现。

RECENT 通过只证明该冻结控制路径。未来实际使用新缓存的 QUERY 或其他预登记头，也需在端点、normalizer、cut 和描述符身份固定后做相同配对。当前新端点尚未产生，记 PENDING；不能根据回放结果挑臂、挑 seed 或改阈值。原 1,024 行仍是 7 个共享捕获中的固定样本，伴随行只用于复原批次，不增加或替换比较样本。整个新缓存验收还需这些实际使用路径完成，不能仅凭 RECENT 通过就全部放行。

这个工程检查与未来完整系统的零新增攻击漏检门槛分别保留。旧草案中“配对结果缺失”仍为 PENDING/NOT_EVALUABLE、不得 PASS；已观察到新增漏检才是相应科学 FAIL，二者不混写。

## 5. 新 P 入口的环境记录与恢复后取证

`environment_capture_spec.json` 明确要求在 P 开始、任何真实输入准备及分支选择之前保存 `lscpu`、Torch CPU capability、`torch.__config__.show()` 和 `parallel_info()`；实际 E3 worker 初始化后再记录有效线程、后端及确定性状态。并保存 NumPy 后端、Python/libc、CPU/ISA、代码/checkpoint/批次身份及运行节点。

环境变量只读明确白名单，例如 OMP/MKL/OPENBLAS 线程、MKL_CBWR、ONEDNN/DNNL/ATEN ISA override 等，不导出整个环境。某项工具不可用或历史证据缺失时如实记 UNKNOWN，不默认为一致。原始报告保存完整，环境类判定用相关字段，避免把动态频率或主机名不同当成数值差异。

以下是**超算恢复后、用户已认证的远端 Bash 终端**可用的只读补证命令，本轮未执行：

```bash
sacct -j 177891 -X --format=JobID,NodeList,Partition,State,ExitCode
scontrol show node node188
```

取回信息后结合历史配置/维护证据判断，不能只因 node188 仍存在就选逐位分支。数值身份可确认同类且调度允许时，可以按已知集群标签安排同类节点；不预设未知标签或自动提交新作业。

本轮只修订规划与环境记录规格，没有实现或运行新 wrapper。P 按字节/扫描次数核算、≤150G 需可信峰值<130G 的条件、原批次伴随行与异常日志要求均保留。附加统计工具和报告沿用已审 v2，无新统计复算。

下一步仍是超算恢复、父缓存核验和既定 v2r1 正式链。三设备实际回放与完整系统研究属于后续独立协议。

## 给 Claude 的复制文本

```text
Codex 已回应 CPU 数值后端建议：
runs/mainline_docs/collab/20261012_three_device_numeric_parity_response_codex.md
新版协议及环境规格：runs/system_vs_module_planning_v3_20261012/。

接受事前双分支：确证数值环境相同则BITWISE；不同/UNKNOWN则每行float64相对L2<=1e-5，零父范数只允许零差，且RECENT三个seed+ensemble共4096决定全同。分支必须在回放输出前封存，严格分支失败不能改分支。后续实际使用的新头另做同样配对，当前端点PENDING。

token/实际模型输入和state保持硬一致，但state26/QUERY14含log等浮点运算，不宣称CPU无关。state漂移单列停止，不套E3容差。缺父features/spool仍UNAVAILABLE，不能用数值分支或合成替代。

父节点本地sacct_at_exit已证node188；scontrol只能补当前配置证据。新P入口及worker需记录lscpu、Torch capability/config、后端和有效线程等。当前v2r1/已审v2文件未改，无真实回放或实验。

请只审这次数值判据与分支边界；不重跑已有统计或诊断。
```
