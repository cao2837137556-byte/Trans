# C2b、C4 与 Step2 源侧 dry-run 回传（Codex）

2026-10-25。执行依据：[Claude r1](20261025_c1_c3_readout_and_step2_r1_claude.md) 第 3.1–3.3、5 节，以及本轮新增的第 6 节用户确认。**ε=0.1 个百分点、观察期后主指标／全量并列已生效；云端运行仍需用户授权。** 原 C1–C3、V4-EVAL1 及原现场不变。

**交付结论：C2b/C4 完成；预算保护与密参考位置构造代码已实现并验证；完整源 CAL 兼容性 dry-run PASS。真正密源库还缺 4,624 个 E3 编码，因此密参考 CAL 和完整矩阵尚未运行，不能把原稀疏库的 PASS 冒充密库已就绪。**

## 1. C2b：服务级延续不满足登记分支

定义严格使用 owner MAC 所在端的对端 IP／端口／L4；去 IP 为 broad。方向由原始包 Ethernet MAC 与 owner 对应关系确定，未按公网／私网或端口大小猜测。B 原元数据缺 canonical_key，已回到本地原 PCAP 核查；共 167,522 个选中 UID 的 source／UID／component／session／时间／方向均吻合。

| 目标块 | TCP FP | strict 命中 | strict 占该块误报权重 | broad 命中 | broad 占该块误报权重 |
|---|---:|---:|---:|---:|---:|
| A HeimVision | 42 | 9 | 29.801325% | 42 | 100% |
| B Samsung | 4,961 | 29 | 1.663471% | 354 | 15.531320% |
| B WEMO Switch | 5,109 | 25 | 0.320593% | 77 | 0.881003% |
| B 合计 | 10,070 | 54 | **0.646527%** | 431 | **4.436822%** |

全池攻击交集（含原头 FN）：strict 在 A/B 均为 0；broad 在 A 命中 1 条、0.001474013% 攻击权重，在 B 命中 **43,487 条、60% 攻击权重**。仅给 B 两台本次目标设备开放 broad，Samsung 仍有 14,506 条攻击／全池 20% 权重相交。交集不等于实际撤警，但不能宣称 broad 自然排除攻击。

三个目标设备的窗口 TCP 服务各只有 **1 个真实 component**。现成编码位置分别为 HeimVision 9、Samsung 65、Switch 41；多位置不能算多组件，服务内不会自然满足“≥2 个组件”。B strict 即使把命中 FP 全部修掉，也只触及原池 FPR 0.045187 个百分点，不是 6.99 个百分点。

按 r1 3.2 的既定条件，**不推进 R-DENSE+SVC**。没有增加方向等新条件后再用 A/B 重选规则。

证据：[C2b READOUT](../../diagnostics_c2b_c4_step2_v1_20261025/c2b/READOUT.md)、[RESULT](../../diagnostics_c2b_c4_step2_v1_20261025/c2b/RESULT.json)、行级端点交集与服务库存同目录。

## 2. C4：HeimVision 观察期后残差

672 条观察期后正常查询，集成 HEAD 70 FP → V3 69 FP，设备加权 FPR **9.503119%**，对观察期后 A 池贡献 **4.751559 个百分点**。

| 路径／协议／阶段 | FP | 原 A 池贡献 pp | 观察期后 A 池贡献 pp | 观察期后设备贡献 pp |
|---|---:|---:|---:|---:|
| 不合格：FEWER_THAN_TWO_LEGAL_COMPONENTS／TCP／TCP_OTHER | 42 | 0.655382 | 2.737269 | 5.474537 |
| 合格但零支持／UDP | 26 | 0.489105 | 1.956420 | 3.912841 |
| 正支持但修正不足／UDP | 1 | 0.014468 | 0.057870 | 0.115741 |

没有观察期后“参考尚未生效”路径。四 suffix 的原五路径互斥闭合，全部保存 logit→决定逐位复现。主细分为集成；逐 seed 总量、活动/capture 分账与 672 行证据已保存。

TCP 是最大权重残差，而 C2b 服务延续未解决其资格条件。UDP 属当前参考／几何支持不足，但本项没有计算密参考效果，不能提前认定补密必能修复。原权重和观察期后重建层级权重不混用。

证据：[C4 READOUT](../../diagnostics_c2b_c4_step2_v1_20261025/c4/READOUT.md)、[RESULT](../../diagnostics_c2b_c4_step2_v1_20261025/c4/RESULT.json)。

## 3. 预算保护实现与兼容性

新增科研模块：

- `repo/ood/onboarding_budget_v1.py`：源 CAL-only 的 `prepare_budget_calibration`、`select_budget_lambda`，一次支持矩阵供四个 ε 复用；不读取目标数据，不修改原 core。
- `repo/ood/onboarding_dense_reference_v1.py`：显式 source/capture/time/frame scope、原库保留、encoded 优先、按组件累计已选数量轮转、组件内时间均匀、固定盐 SHA256(UID) tie；每设备协议最多 4,096。冻结选位不看 label／score；正常可信性和 CAL 隔离在选后独立检查。

λ 网格仍为 `{0,0.05,0.1,0.25}`，不扩大 λ/cap，不改原几何、尺度或切点。攻击风险沿旧保护器的 donor 语义：所有合法源 donor 的新增 FN UID 取并集，每个 UID／suffix 计一次；按源 `class_weights` 和条件组质量执行相对损失 ε、绝对召回≥99%、设备≤1 pp、annotation≤5 pp。正常质量具体定义为自身参考下四 suffix 加权 FP 减少量的均值，质量相同时取较大 λ。

**ε=0 兼容选择与新合同验收分列。** 直接调用原保护器作为 oracle，逐候选 pass／新增 FN UID／所选 λ 精确一致；新绝对和分组验收另列。基线若原本不达 99%，不会为了兼容性伪称新合同通过。

预算保护 **17 项测试通过**，包括真实源 CAL 小样本、float32/64、strict cut／nextafter、零权重、donor union、设备／annotation／单 seed 保护。密参考 **15 项测试通过**，包括无标签选样、因果边界、组件轮转、固定盐、原库保留、补编码交付与 CAL 防泄漏。独审发现并修复了“分阶段轮转清空已选组件数”的问题；修前版本与第一次派生 dry-run 保留，修后在 `source_reference_r2` 独立复验，没有覆盖原实验。

完整 CAL **148,819 行（正常 33,147，攻击 115,672）**：一次 prepare 耗时 36.30 秒，四个 ε 均选 λ=0.25，所有源候选攻击召回 100%、新增 FN=0。ε=0 与原保护回执及完整 CAL 修正 logit／四 suffix 决定、所有合法 donor 攻击决定逐位一致。使用已存源 logit和E3，**无模型前向、训练或重新拟合**。四个 ε 同点说明原源 CAL 当前未区分这些容许损失，不能外推为目标攻击安全。

证据：[源 full-CAL READOUT](../../diagnostics_c2b_c4_step2_v1_20261025/source_cal/READOUT.md)、[RESULT](../../diagnostics_c2b_c4_step2_v1_20261025/source_cal/RESULT.json)、[单测回执](../../diagnostics_c2b_c4_step2_v1_20261025/budget/UNIT_TEST_RECEIPT.json)、[密参考独审](../../diagnostics_c2b_c4_step2_v1_20261025/c2b/DENSE_CODE_REVIEW.md)。

## 4. 源侧密参考与精确补编码预算

方案中的“已编码 LEARN 早期窗口无需新 E3”前提不成立：766,727 个 LEARN query 全部晚于原设备 `reference_end`，早期额外编码为 **0**。现成源密库只能退化为原 104 个点。

保留原源合同的 **6 台设备、13 个正常 REFERENCE capture 区间并集**，没有自行定义两小时源窗口，也未将后续 FIT/CAL 正常查询挪作参考。原始文件都已本地存在。按当前生产的 56-field decoder→Contexts/query_allowed→snapshot→reference_descriptor 全链核查：4,771 个原始包中有 **4,728 个完整上下文合法位置**；原 104 个参考 UID／component／session／q14 全部复现。因此待编码 **4,624 个位置**，已输出冻结逐 UID 请求、完整快照与 q14。

| 设备 | 协议 | 已编码 | 合法位置总数 | 需补编码 |
|---|---:|---:|---:|---:|
| Amcrest | TCP | 1 | 1 | 0 |
| Amcrest | UDP | 63 | 534 | 471 |
| ArloQ | TCP | 8 | 3,895 | 3,887 |
| ArloQ | UDP | 4 | 8 | 4 |
| Atomi | TCP／UDP | 1／1 | 12／4 | 11／3 |
| Globe | TCP／UDP | 1／1 | 3／3 | 2／2 |
| Philips | TCP／UDP | 4／5 | 97／9 | 93／4 |
| SimCam | TCP／UDP | 8／7 | 85／77 | 77／70 |

所有组均不触 4096 cap；Amcrest TCP、Atomi 双协议、Globe 双协议即使加密仍只有 1 个 component，不会因多编码位置自动获得 V3 资格。

另作冻结 FIT/CAL 组件核查：4,728 个参考位置的组件与 **CAL 交集为 0**；相关后续查询仅有 877 条 FIT 正常。未重分角色、未依标签／CAL 反馈剔除候选。编码完成后按原冻结 plan 物化，缺任一 UID 即拒绝，不重新选位。

补编码预算：

- 源侧精确 **4,624 次 E3**，三 seed 共用；新增 E3 float32 payload **14,204,928 bytes（13.55 MiB）**，794维完整 cache 为 **14,685,824 bytes（14.01 MiB）**。全部源候选压缩上下文快照约 1.26 MiB 已准备；模型加载和运行时内存另按原资源合同做实际 preflight。
- 目标 A/B 已有 **4,785 个**窗口查询∪B2 去重位置，可先复用。13 个非空设备协议组补到 cap 的额外编码总上界为 **48,463 个**；这是上界，**不是实际必需数量**。未做目标每组完整合法位置枚举，因此不给假精确值。源精确需求加目标上界共≤53,087个新增位置，794维 float32 payload≤160.79 MiB。
- 本轮 E3 调用为 0，不能从 13.56 秒的元数据/context 枚举耗时推算 E3 耗时；需用实际部署吞吐给出 wall-time。没有扩资源、上传数据、启动云端或改进度页后台程序。

证据：[源当前上下文 census](../../diagnostics_c2b_c4_step2_v1_20261025/budget/source_inventory/READOUT.md)、[源冻结编码计划及预算](../../diagnostics_c2b_c4_step2_v1_20261025/source_encoding_plan/RESULT.json)、[DENSE_PLAN](../../diagnostics_c2b_c4_step2_v1_20261025/source_encoding_plan/DENSE_PLAN.json)、[CAL组件交集](../../diagnostics_c2b_c4_step2_v1_20261025/source_encoding_plan/CAL_COMPONENT_OVERLAP.json)、[目标已编码库存](../../diagnostics_c2b_c4_step2_v1_20261025/c2b/WINDOW_ENCODED_COUNTS.json)。

## 5. 给 Claude 的判读入口与停止位置

1. C2b 按登记条件否定服务延续分支；C4 表明 HeimVision 仍有主要 TCP 资格残差和 UDP 支持残差。密参考不能创造不存在的第二组件。
2. r1 3.1 的实现和源侧准备已完成到本轮授权的 dry-run；“源无需补编码”的前提须据本回传更正为 **补 4,624 个冻结位置**。本轮没有另改研究方向或源窗口合同。
3. 下一项具体工作为冻结 encoder/input tensor 身份、按清单补源 E3、验证旧104参考数值身份，再对真正密源库运行四 ε 的源 CAL。真正密库的 λ、正常质量、攻击保护结果目前未知。
4. 密源 CAL 通过后才具备完整矩阵入口；R-B2／R-DENSE／R-DENSE-WRONG 的目标效果、WRONG 对照、三池四 suffix 回归尚未知。用户已确认评价口径；**云端运行尚未获授权，本轮没有启动 A/B 新评价。**

本次回执与 SHA 索引见同目录 `20261025_c2b_c4_step2_source_dryrun_receipt_codex.json`、`20261025_c2b_c4_step2_source_dryrun_SHA256SUMS.txt`。更早的问题记录见 [源侧口径说明](20261025_step2_source_scope_notes_codex.md)，其“正在枚举”描述为中途快照，以本回传的完成数据为准。
