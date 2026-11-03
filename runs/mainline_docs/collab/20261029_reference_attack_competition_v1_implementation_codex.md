# 正常／攻击参考竞争v1：实现交付

2026-10-29。状态：`IMPLEMENTED_LOCAL_ACCEPTANCE_PASS_REMOTE_PREFLIGHT_PENDING`。

用户“开始实现”的工作已完成：两方向Q/N/C六模块、依赖隔离攻击原型、正常／攻击关系、同初始化抽样、最坏donor训练、独立与共同λ、RAW累计保护／分支收益／对照门，以及条件主头与一次A/B流程均已实现。新候选不继承D0的强制减分，也不要求旧D0先PASS；自身保护及推进门完整保留。

最终合成验收通过，最新测试数见包内`validation/SYNTHETIC_ACCEPTANCE.json`，含六模块及目标阶段的合成流水线、数值重放失败、前置门、空保护、1C、原2C零support、原分母严格阈值与资源停止。真实源只读验收63个输入SHA通过，766,727源行／4,728参考身份绑定、六原型库TCP/UDP与活动覆盖通过，CAL/S与FIT完整依赖闭包交叉为0。只读验收158.089秒、峰值约4.625GiB。

资源shape上界为源1,425,303,553距离对（含缺旧cache的回退），小于2e9；最大单role低维关系缓存约566MiB，逐role释放。合成本地24,000更新约406.33秒，仅估计训练计算，不含关系/I/O/基础头评分，不保证HPC四小时完成。运行时仍守4CPU/8GiB/源4h、条件目标另4h等硬限，超限停、不改配方救场。

环境说明已按用户纠正并回查实验9：超算已有Python3.11.11，主阶段同样沿用它，复用179602／179700的NumPy2.0.1私有overlay；源BASE仍用NumPy1.26.4。先前把主头ECS历史Py3.9当超算必需条件、主入口硬锁3.9的处理过强，现已撤销。已有缓存评价不能证明新主头前向相容，故保留真实主CAL逐字节门；兼容性由该门判断，不由历史Python版本推断。没有新建环境、修改共享环境或启动真实前向。

交付见[README](../../reference_attack_competition_v1_20261029/README.md)、[执行卡](../../reference_attack_competition_v1_20261029/EXECUTION_CARD.md)、[机器回执](../../reference_attack_competition_v1_20261029/IMPLEMENTATION_RECEIPT.json)及[分发回执](../../reference_attack_competition_v1_20261029/distribution/DISTRIBUTION.json)。冻结设计SHA`47847119e5cae15ca41cf7433b615cf5741dac9d1ef59f70077090f88444c5c7`未改。

本轮只做实现、合成验收、只读真实输入核验和封包；真实新训练／前向／距离／E3／A/B均0，无超算提交。Codex右侧进度页已实现，未启动本轮服务。下一项是本轮部署与一次源运行，主阶段仍须源PASS及真实主CAL一致性核验。本轮未自动沿用旧轮次运行授权。

180007科学失败结论、179700正式开发成绩、旧B1及独立源1C延期均保留。不能把实现完成写成性能提升已经成立。
