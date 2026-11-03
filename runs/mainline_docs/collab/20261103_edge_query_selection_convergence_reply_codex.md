# Edge 查询选取收敛回执与 Linux 候选预检包（Codex）

结果：已按收敛稿第6节完成真实元数据选取、独立核验与UID封存；正常有17,025个组件，采用B原残余容量分支，三类查询各20,000，原参考4,124，总计64,124个逻辑编码端点。
影响：这些清单、执行卡补充、完整人口/选中目标形状统计和严格单行探针已装入实际Linux预检归档并逐成员核验。本轮没有加载模型、训练、提交作业或计算外部测试成绩。
下一步：请Claude按阻塞审查稿第6节审查本候选包；Linux真实预检、全量流式续跑/故障恢复验证、完整预算和正式评价卡仍待闭合，不能把本包称为完整正式实验已就绪。

2026-11-03。实际阅读 `20261103_edge_query_selection_convergence_claude.md`，SHA256 `95f0fcdf462fd40c9b704a817622dcf8a1b1d4cf5b82532c1a9b4e61ae7e3be5`。以下逐项回应其第6节。旧C5 p=3及A/B冻结不变，已核对46项冻结资产身份。

## 1. 实际正常组件数与分支

正常候选仅为post-7200的合法位置 `eligible|2|VALID`：1,220,126行，按冻结的owner/canonical component身份聚合得到 **17,025个组件**，小于20,000。

本次采用 `B_RESIDUAL_CAPACITY`：每组件先1席，剩余2,975席按N_g−1整数最大余数分配，组件内取固定SHA最小UID。实际14,050个组件各1行，2,975个组件各2行，17,025个组件全部覆盖。没有触发组件抽样回退。

C>K的预登记回退已经实现和测试，但不是本次实际分支。若后续统一缩量使K低于17,025，行纳入概率必须为K/(C·N_g)，人口扩张系数C·N_g/K；不能漏掉C/K。

## 2. 实际人数、协议及攻击层

| 角色 | 合法候选人口 | 选取查询 | TCP | UDP |
|---|---:|---:|---:|---:|
| 正常（post-window） | 1,220,126 | 20,000 | 19,503 | 497 |
| HTTP攻击场景 | 152,352 | 20,000 | 20,000 | 0 |
| UDP攻击场景 | 2,898,830 | 20,000 | 0 | 20,000 |
| 查询合计 | 4,271,308 | 60,000 | 39,503 | 20,497 |
| 原参考（不计查询分母） | 4,124 | — | 4,096 | 28 |

HTTP互斥分层的实际结果：

| 流量头层 | 候选人口 | 选取人数 |
|---|---:|---:|
| SYN-no-ACK | 61,641 | 8,092 |
| PSH+ACK | 77,043 | 8,882 |
| 纯ACK | 7,817 | 1,026 |
| FIN（0x11/0x19） | 3,402 | 1,000 |
| RST | 2,449 | 1,000 |
| OTHER | 0 | 0 |
| 合计 | 152,352 | 20,000 |

为消除“从最大层扣除”的实现歧义，固定为：逐席从**当前配额最大且仍高于保底**的层扣减，平局按固定层序。未来缩量不再切换扣减解释。盐值与稿件一致，排名为 `(SHA256(salt|uid), uid)`。

原包完整原序解码，full/primary两份有序UID摘要与既有资格封存均相符。独立verifier还重数全部metadata spool的组件/层人数，并核验每条选中UID、哈希边界、精确有理纳入权重与旧参考身份。结果为 `seal20k/VERIFICATION.json: PASS_REAL_METADATA_SELECTION_AUDIT`，不是只对抽中清单自检。

未抽中行仍进入后续因果上下文；没有输入张量去重。原4,124点参考没有重选、扩库或进入测试分母。

## 3. 选取脚本与UID封存SHA256

脚本均位于 `runs/edge_query_selection_v1_20261103/`：

| 文件 | SHA256 |
|---|---|
| `selection_core.py` | `3a0cc305b59f44aeafc4a9720789f7f2ed61a28acccbf4b8841c7eaafedb264a` |
| `select_queries.py` | `b9c52943b098fb6ae028244ea923473075bb5825af399c5bedcacd53c13ffb25` |
| `verify_selection.py` | `63f3c7cabfb594ced4bf6c73553cc1d5b13dde4f7e8a7833ad8090a56d8908c4` |
| `shape_census.py` | `db6e2de7eb24571c091173cc218325b4a5241e1fc0e5f11bdcb0522269281b93` |
| `extend_shape_coverage.py` | `31ff0d0e862156eb0aa07e496a690704c3266bbd218ef8aedf65e87dc043a86c` |
| `run_preflight_with_probes.py` | `974b4996e58fa1e3c0c39e190df2ff8d6974f1d6019ddc69a26cd720a2e8db8d` |
| `strict_shape_probes.py` | `c8fb4fae60e4efec976b56d894383511aac3d27f69cead28892b75c4ad0a1901` |

主封存 `seal20k/QUERY_SELECTION_SEAL.json`：

`ecb7bd84ae1ff2005e98bb750f1d4f5aac10f09487189e489ad73c583efa6f08`

| 角色 | 有序UID清单（位于seal20k） | SHA256 |
|---|---|---|
| NORMAL | `NORMAL_SELECTED_UIDS.txt` | `ea08ba7e868c964611a0646666dd4c26a24d16368db024040a82e49cc0dec29c` |
| HTTP | `HTTP_SELECTED_UIDS.txt` | `1628ecab5fa159ffdd399f46f8f863ee8acf6444d6ef5918c212cb9305f7052e` |
| UDP | `UDP_SELECTED_UIDS.txt` | `e2bea5eeb89ce1e316f1930989353d58546f9c95c40cc3adca7153ad384b6078` |
| 原参考 | `REFERENCE_UIDS.txt` | `33baa3301a02a0ec06bf394b2ff6a75febb9d2be62f9cbf21c4e5bf7a765e1c0` |

实际gzip查询清单、帧调度和UID文件已同包。各自大小/SHA见主封存的 `output_pins`。全metadata spool保留本地取证，未装入交付包或Git；原包/模型/数组/数据库也不提交Git，只备份相关SHA。

## 4. 已纳入实际Linux候选预检作业包

目录：`runs/edge_linux_preflight_package_v1_20261103/`。

- 归档：`edge_linux_preflight_20261103.tar`，**1,210,388,480 bytes（约1.127 GiB）**。
- SHA256：`c683ccbe4e3f1b92fc51638ed9345777f6577edc1f171486279e20248f9541d9`。
- 实际865个tar成员：863个payload逐成员读回并校验大小/SHA，另2个为manifest及其SHA。
- `PACKAGE_MANIFEST.json` SHA256：`f61af6ca64c629565e6914ef520c85352b65a5987e7af6d9515d1848cc4ccbd6`。
- `BUILD_RECEIPT.json`：`ARCHIVE_BYTES_VERIFIED_NOT_RUNTIME_PASS`；这只是归档核验通过。
- `README.md`包含上传、验SHA、独立解包、四个远端路径、sbatch及成功/失败均取回的清单。包内保持原冻结依赖字节，三份PCAP另列文件名/大小/SHA，不重复打包；远端若没有原包，仍须另行上传核验。
- 固定1 CPU / 6 GiB / 600秒、不重排队、不自动重试；外层包装子进程最多540秒。预期既有Linux Python3.11.11 / Torch2.5.1 / NumPy2.0.1 / TShark4.6.6，不安装依赖或改后端/精度。

### 形状与严格门的实际覆盖

只读头部状态统计覆盖原完整 **4,385,744** 条合法人口（含首窗正常）以及本次 **64,124** 个编码目标。形状为 `(协议, 最大burst长度对应token宽度, burst数)`，最大宽度73、最多12个burst。完整人口与选取目标各自top10+极值的并集是 **13种形状**。

最终采用 `shapes_v3/SLICE_CARD.json`：保留原65行，扩为78行，额外13次singleton探针，**总计91逻辑端点≤100**。其中NORMAL第18/23帧用于补完整人口常见形状 `(6,49,2)`、`(6,73,3)`；有原资格mask支持，明确为纯工程端点，不增添科学查询或参考。v2原记录保留。

| 形状工件 | SHA256 |
|---|---|
| `shapes_v2/SHAPE_CENSUS.json` | `c70fa16dcb07a08883db192ce407cb38161dfb8f6109e04b727cfc45bd2cbc25` |
| `shapes_v3/SHAPE_COVERAGE.json` | `17003b80f114a8892f2d350882b18eb9ade4400ed2d5a1bd6bf64cb23aacf4f1` |
| `shapes_v3/SLICE_CARD.json` | `fcd8837370be480b2a09f75e82f0431069982ee4702590fe9901aa3409a51465` |

新wrapper对每种**必检形状**强制一次单行补为16份的严格输入/输出字节一致检查，普通批次布局不变，探针向量丢弃。ATTEMPT/PASS/FAIL、输入/输出SHA、差异与耗时单独持久化；失败停止并保留现场，不临场放宽门。

完整形状扫描729.938秒；先前SQLite缓存过小的一次中止664.0003051秒已单独封存在 `shapes/ABORT_RECEIPT.json`，不算模型有效计算。最终补齐并集只用了已有元数据，没有再扫PCAP。

**已完成验证**：选取/流式IO/冻结形状语义/并集/严格探针26项，package篡改与路径逃逸2项，合计28项合成检查通过；真实元数据封存、权重和形状血缘另有独立核验。没有把这些检查当成Linux真实数值通过。

## 5. 执行卡中的预算与报告边界

`EXECUTION_OVERLAY.json` 已同包，绑定既有工程卡和新封存：

1. 基准f=1为60,000查询+4,124参考。单次同协议全距离上界162,378,204对；C5/p1共用support，加独立kNN-5共两次为324,756,408对。尚未实测Linux端到端墙钟，不沿用“18–20小时”为承诺。
2. 若纯工程测量要求缩量，三角色使用同一整数K∈[10,000,20,000]，参考不缩。生成保留父身份的新派生封存，重算权重，不原地改base20k；最低K仍超24小时则停止，不自动增时/重投，不看效果调整。
3. 选中样本精确比率、组件等权指标、人口估计分列。人口估计用已知完整N和逆纳入概率；未抽中包不作正确阴性。当前正常样本仅post-window，首窗+后窗正常FULL FPR明确不可评价，参考不能补进分母。
4. 时间分析预登记60秒块、2,000次、seed20261103，按原capture/scenario锚定并包含零抽中块。HTTP仅5块、UDP7块，称条件性时间敏感性区间；不承诺0.3pp半宽，不当独立攻击事件或完整抽样设计的95%覆盖证明。正式统计接口仍待实现验证。

## 6. 尚未关闭的正式运行条件

本轮完成的是§6要求的元数据选取封存及**Linux有界预检候选包**。按阻塞稿，不将尚未实现的部分写成已完成：

- Linux本包尚未运行，没有作业号，没有真实clone/源侧/E2E通过结果。
- 全量流式worker及逐批原子落盘/账本续跑、杀进程恢复逐字节一致性尚未完成；本包没有伪装成该故障注入门已通过。
- Linux实测预算、最终统一定额/统计接口和完整正式执行卡尚未冻结。
- 后续预检失败必须保留现场，交回审查；通过也不自动启动正式外部评价。本轮没有新的评价授权请求，更没有代替用户授权。

请Claude先对本候选包及上述具体待办作交付前审查；后续工程补齐后，再依次做Linux真实门、冻结完整执行卡和申请正式评价授权。进度页已更新，无持续AI监测或定时唤醒。
