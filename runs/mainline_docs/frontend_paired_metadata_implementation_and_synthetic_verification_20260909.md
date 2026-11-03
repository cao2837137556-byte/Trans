# B 分组元数据工具：实现与合成验证

日期：2026-09-09。授权：用户明确“授权实现”；不包含真实包头读取或训练。
状态：**PAIRED_METADATA_IMPLEMENTATION_ACCEPTANCE_PASS**，真实尝试 **NOT_STARTED**。

## 已实现的交付

| 文件 | 用途 |
|---|---|
| `repo/ood/issue27frontend_paired_metadata_v1.py` | 固定输入校验、无模型解析投影、B 分组描述符、依赖连通分量、冻结划分与覆盖/训练调度账 |
| `repo/ood/issue27frontend_paired_metadata_runner_v1.py` | 一次受限包头读取、仅 B 目标投影、结果写入、独立结果复算 |
| `repo/ood/issue27frontend_paired_metadata_control_v1.py` | 显式执行入口、进程/资源控制、失败封存、只读状态 |
| `repo/ood/issue27frontend_paired_metadata_tests_v1.py` | 生成头部、PCAP、ZIP 和临时进程的合成验证 |
| `repo/ood/issue27frontend_paired_metadata_verify_v1.py` | 验收日志、代码/文档/运行时/冻结输入身份封存 |
| `scripts/start_frontend_paired_metadata_local.ps1` | 需要明确真实读取授权的单次启动脚本，后台隐藏窗口 |
| `scripts/show_frontend_paired_metadata_status.ps1` | 显示成员、包、B 目标进度、耗时、失败原因及最终 seal；`-Once` 单次查看 |

验收目录：`runs/frontend_paired_metadata_implementation_v1_20260909/`。
真实输出目录：`runs/frontend_paired_metadata_v1_20260909/`；本轮未创建它。
原训练配方、划分方法与 SHA 侧车保持不变。

## 解析与分组语义

实际读取时只为已封存的 **6,737 个 B 目标 / 22 个成员** 生成分组元数据，
最多单遍读取 **8,207,642 包**，每个成员在其最后一个 B 目标处截断。
不重放两个全 A 的 ToN 成员。此前 A 的 7,001 个真实旧会话直接复用。
本轮复核保存的目标元数据，确认 11,529 个 A 目标均为 H1。

解析代码通过 AST 精确取出已固定源文件中的所需函数/常量，先验证整个源文件 SHA；
不 import 历史训练/推理 runner，也不导入 torch、NumPy、pandas 或模型文件。
复用 F0 `raw_to_event`、旧 CKBU `event_from_tshark` 和旧 `canonical_session`，
以及已验证的 TShark 命令、缺失值与每 100,000 包序号重置处理。
H4 仍使用原字段集合的 presence mask；没有通过缩减字段改变其分组语义。

B 无 epoch 路由键使用同一成员内原始端点的稳定相等关系，双向规范化后只保存哈希。
原始端点值不落入描述符。单目标解析不需要为所有先前流量保存 first-seen 端点表。
上下文仍是不可拆原子，同一已存 B 上下文若产生不同路由键，立即停止并报告。
时间回退型 B 必须得到真实 canonical bridge；不得用原占位 ID 代替。

额外实现了一个保守 H1 连接：旧 CKBU 忽略 `ipv6.nxt` 的情况可能使 F0 H1 的 B
没有旧 canonical key，因此同时用 F0 H1 的规范五元组按旧 hash 命名空间查找 A 会话。
原旧 canonical key 与这项兼容 key 都保留；若它们不同，则保守地连接两者，
不重写旧系统当时的判断。零端口及旧 UDP fallback 的差别有专门合成用例。
这属于冻结协议要求的跨 A/B 依赖桥实现，不改变标签、损失、seed、划分盐或成功门槛。

原始读取过程中只向目标解析器传入 UID、source/member、位置、tier、时间等身份字段，
不传入标签/教师结果/新旧错误。生成依赖分量后才按冻结规则使用行为标签分层。
不同上下文前缀不共享原始事件的结构前提沿用固定 F0/F1 分配逻辑及 F4/outer 身份账，
不重新构造特征或执行历史审计。来源相关性与重复内容仍不能被解释成统计独立。

## 输出与判定

真实执行完成后输出：B 描述符、完整 18,266 目标的 membership、依赖分量与连接边、
来源/行为覆盖表、训练调度身份和资源计数、访问记录、工作进程终态、监督进程终态与 SHA 清单。
每个目标保留原历史用途字段，新 train/check 用独立字段记录。

划分完全使用已冻结的分量 ID、stratum、seed 2705 和哈希排序规则；单例整个 train-only。
同一检查/训练上下文内不拆目标，不按当前五条错误挑样本。
表中分别给出目标、上下文、分量计数及目标时间区间交叠；不声称时间外推或设备独立性。

工具区分三类终态：

- `MEMBERSHIP_QUALIFIED`：身份、完整性和约定覆盖条件满足，只代表名单合格。
- `METADATA_COMPLETE_COVERAGE_INSUFFICIENT`：取证与固定划分完成，但必要行为缺少训练/检查覆盖。
  具体缺口保存，不能因其他来源有覆盖而放行；B 攻击的不足也必须单列。
- `INPUT_OR_EXECUTION_STOP`：身份、语义、资源或执行异常。没有该次完整名单资格结论。

前两者都不产生模型效果，也不授权训练。监督器重新计算分量/名单/覆盖/调度并核对落盘内容，
不会只相信 worker 的 PASS 字符串。只有最终 seal 校验完成，状态入口才显示 final=true。
未封存、孤立的 worker 终态、控制进程消失、额外文件或字节漂移都不能被当成完成。

## 合成验证与运行边界

**45/45 合成检查通过；2/2 PowerShell 语法检查通过。**
其中主套件 44 项，随后针对解码子进程清理增加并单独运行 1 项；日志分别保存，
没有为了增加通过数重复统计同一检查。验收脚本核对最终测试源码声明的完整 45 项名称集合。

验证涵盖 H1/H2/H3/H4、反向流、IPv6/旧端口语义、作用域隔离、缺失/多余/重复目标、
同上下文键冲突、跨 epoch 旧会话、跨 A/B 传递合并、单例与 ToN 覆盖不足、
划分对输入顺序/旧错误字段不敏感、A/B 调度守恒和尾桶/大 B 微批、
生成 PCAP 精确截断与短读、ZIP 单成员与 CRC、显式入口拒绝、超时与输出超限、
子进程清理、未封存状态和 seal 篡改。

初次合成执行发现 AST 常量投影漏带 `TSHARK_RESOURCE_PROFILE` 依赖，已补齐后通过。
这是实现阶段的合成 setup 问题，初始记录保留；没有读取真实包或产生科学失败。
监督器的“成功路径”用模拟 validator 检查控制状态；实际分组/写入路径另由生成头部和
生成 PCAP 用例执行。所有这些测试都不代表真实数据的覆盖或继承性能通过。

真实执行上限沿用已定范围：**3,600 秒 / 聚合 8 GiB / 输出 64 MiB / 零重试**。
一个 worker 加至多一个解码子进程进入 Windows Job，关闭/超时会一起终止；
从 8 GiB 中为控制进程预留 256 MiB，并监测控制进程占用与总量。
输出与墙钟由外部控制器监测，worker 也记录进度和次数，异常超限保留失败证据。
未做真实资源试验；这些是上限，不是耗时承诺。

执行前检查只校验实现包、现有合法元数据、固定来源代码及本地运行时身份，
不 stat/hash/decode 真实 PCAP/ZIP。原始容器的完整 SHA 和选中 ZIP 成员身份在授权后、
任何真实解码前核验；只解析选中成员，但整个 ZIP 的不透明字节身份哈希会发生。
本次的 Python、解码器和关键库身份记录在 execution_config.json。

## 使用及下一步

现在可以只读查看状态（不会启动工作）：

```powershell
.\scripts\show_frontend_paired_metadata_status.ps1 -Once
```

当前应显示 `NOT_STARTED`。下一步需要明确授权 **一次 B 包头元数据读取与名单封存**。
获授权后才使用启动脚本的 `-AuthorizeBMetadataRead` 参数；本轮未使用该参数。
包头取证后的训练/检查分母现在仍未知，不能提前宣布名单合格。
新模型训练执行器及真实双臂训练不属于本轮实现范围。

交接顶部与实验索引已更新。HEAD/分支保持 codex/exp-mainline @ 4b28747，
八个已有无关 tracked 修改与前一封存配方的全部字节保持不变；见验收目录校验记录。

solved: B 分组元数据工具、固定划分与状态/封存实现完成，45/45 合成检查通过。
changed_mainline: yes（达到元数据取证实现验收；非科学结果）。
active_blocker: 真实 B 分组信息尚未取得，真实名单/覆盖仍未合格封存。
frozen: 前一训练配方与全部历史科学结论；本实现包及源代码/运行时身份。
superseded: B 元数据工具尚未实现的状态；不覆盖旧实验结果。
next_action: 明确授权一次受限 B 包头读取并封存名单；本轮未执行，训练另需授权。
