# 旧 E3/P2 小增强：实现验收与 ID 测试接入

日期：2026-09-16。实现与合成验收完成；真实增强 PREPARE、TRAIN_B、TRAIN_C、CHECK 均未启动。已执行的真实操作仅为此前获准的 ID 原始输入资格核验，未计算模型特征或分数。

## 这一步解决了什么

保持旧 E3 编码器、normalizer 和参考 P2 不动，已实现两份独立 P2 副本的训练及固定终点比较。B 使用原冻结的加权分类损失；C 在完全相同数据、初始权重、随机数顺序和训练预算上增加冻结的同设备排序损失。比较回答“有针对性的新增监督是否有帮助，以及排序是否有额外帮助”，不把它当作已经成功的新机制。

训练仍为旧有效输入 11,529 条（正常 7,347、攻击 4,182）加新 TRAIN 570 条（正常 462、Hydra 108）。新 CHECK 281 条（正常 227、Hydra 54）与训练按完整抓包划分。两台摄像头的数据规模及行为覆盖都有限；正常与攻击的服务、观察位置和时间并不严格匹配，不能宣称已经控制环境因素，也不能保证改善 hydraulic/predictive OOD。

冻结训练协议及 SHA 未改：seed 27、每臂 200 次 full-batch 更新、原学习率/损失/权重/梯度裁剪和概率阈值 `0.065159872174263`。不搜索、不按 CHECK 选模型或调阈值。

## 本次 ID 测试的实际范围

用户要求本次补入 ID 测试，已完成资格核验与模型打分前的跨抓包复核。入口是 `runs/legacy_id_temporal_qualification_v1_20260916/id_test_extension_v2.json`。最终为 **2,378 个目标、248 个会话**，两份原 ID 抓包分别贡献 1,267 和 1,111 条，**全部为 UDP**。

五份原 ID 抓包共解析 14,092 个包，2,009 个原 fit/select 目标的原始位置、时间和会话映射全部一致。初始 2,583 条候选排除 48 条跨抓包旧曝光会话/前缀，再按预先确定的来源字典序代表规则排除 157 次重复会话观测。最终清单不由模型分数决定，不参与本次训练、normalizer、阈值或停止条件。

它是原 ID 来源中源内较晚且与所审五源旧 fit/select 会话及前缀隔离的保留集，**不是独立新抓包、新设备或新 campaign 的终测**；也不是晚于全部旧训练数据的全局时间切分。其他旧抓包的原始镜像去重未建立，早期其他路线曝光未完全排除，E3 外部预训练重叠未知。同会话包目标不能视为独立统计样本，结果会另报来源和会话诊断。文件名含 tls 不代表这份 UDP 清单覆盖 TLS/TCP 业务。

详细资格证据见 `runs/legacy_id_temporal_qualification_v1_20260916/qualification_review.md`、`cross_capture_review_v2.json` 和 `postreview_acceptance.json`。不以原 ID fit 的 0/760 或辅助正常 select 的 174/2188 代替本次 ID 测试。

## 实现与验证证据

| 部分 | 验证 | 结论 |
|---|---|---|
| PREPARE | 16 项合成测试 | 真实 TShark 解码、旧因果前缀、实际 tokenizer/collator 与 stub forward；未来修改不影响早期目标，前缀有效，延迟批次不污染早期副本，跨抓包隔离；缓存与 TRAIN descriptor 接口通过 |
| TRAIN | 9 项合成测试 | 分块累积与独立完整目标一致；精确权重/排序目标、两臂随机数和预算、normalizer 精度与失败停止通过 |
| 控制器/终点评估 | 12 项合成测试 | 完整维度合成训练到评分、角色与路径限制、缺失分母、加权退化、ID 会话诊断、运行环境路由、中断停止通过 |
| ID 资格/跨抓包复核 | 4+3 项合成测试 | 原始身份、会话隔离、跨抓包旧前缀和重复会话处理通过；真实资格结果及封存身份另经复核 |

共 **44 项合成测试通过**，无真实模型效果结论。PowerShell 两个入口语法检查、Python 3.9 语法检查及独立接口静态审查通过。末次 PREPARE 进度显示修正仅使完成数包含 ID 目标，受影响的既有合成测试通过；不增加科学操作。

PREPARE 将读取已有旧表示的精确 11,529 行，不重建旧特征；新 CIC 851 条加 ID 2,378 条，共需物化 **3,229 个 E3 目标表示**。每个抓包完整按时间顺序解码，使用目标当时的过去及当前包，未来包禁止进入目标特征；新目标有任何数值或身份失败都停止，不删分母继续。

TRAIN 子进程只收到含旧训练、新训练及六数组参考状态的清单，清单中无 CHECK/ID 路径。B/C 终点均封存后才进入 CHECK。原 R 历史分数直接复用已封存的能力台账，B/C 在相同旧有效输入及完整缺失账本上比较；R/B/C 都评估新 CHECK 与 ID。主表分列 ID 误报、攻击检出、OOD 误报，区分训练覆盖的新增摄像头环境与未被原 fit/select 覆盖的四个旧 OOD 环境。低误报曲线仍使用原冻结五个正常池，不能据此选部署阈值。

默认 C 盘 Python 缺少旧 E3 的 transformers 依赖；已核对并复用现有 D1 本地 venv 运行 PREPARE。TRAIN/CHECK 使用现有 C 盘 Python。两者均为 Python 3.9.13、numpy 2.0.2、CPU torch 2.8.0；包元数据的 torch 版本为 2.8.0，模块版本为 2.8.0+cpu。E3 依赖、解释器 SHA 与代码均写入运行范围模板，离线加载，不安装下载。合成链使用 stub 模型，**本实现验收未加载真实 E3 checkpoint，真实 forward 的兼容性仍需在获准 PREPARE 中检验**。

## 可审阅的下一次真实运行

具体范围模板及验收保存在 `runs/legacy_cic2022_p2_enhancement_implementation_v1_20260916/`。模板 `real_execution_scope_template.json` 的 `execution_authorized=false`，不能直接启动。冻结 recipe 中原设计时的授权字段作为历史不改，由新增执行范围记录后续实际授权。

下一次只需一个明确完整链授权：**PREPARE → TRAIN_B（200 更新）→ TRAIN_C（200 更新）→ CHECK（固定终点、含 ID）**。包括已命名旧开发评估池的有界访问；不包含无关 FINAL、下载、HPC、资源复试、历史重跑或异常后的重试。发生异常立即 STOP，零自动重试；工程执行完成与科学改进分别记载。

入口为 `scripts/start_legacy_cic2022_enhancement_v1.ps1`，状态入口为 `scripts/show_legacy_cic2022_enhancement_v1.ps1`。本地后台程序更新 `status.json`、`status.md` 和日志；完成或失败写 `finalstatus.json` 并尝试桌面通知，无需模型持续轮询，不创建定时 LLM 任务。桌面通知受系统设置影响，文件状态是判断依据。

分支与 HEAD 保持 `codex/exp-mainline` / `4b28747b09480471e2bac1beb3a9badf27280efb`；八个无关已修改文件哈希未变。交接和实验地图仅更新当前导航，旧实验与冻结文档不改。历史知识仍以 `project_route_knowledge_index_20260915.md` 与 `legacy_core_attack_ood_history_review_20260915.md` 为导航。

solved: 冻结小增强的实现、合成验收、运行入口与本次 ID 保留集接入。
changed_mainline: no；旧 E3/P2 增强优先，统一 GRU 路线继续 DEFERRED。
active_blocker: 无已知实现阻断；真实 E3 物化及模型收益尚未验证，完整真实链尚未授权启动。
frozen: 原训练 recipe、目标/权重/预算/阈值、ID v2 清单和独立性限制。
superseded: 九月十五日“实现尚未开始、ID 清单未确定”的当前状态；保留其历史记录。
next_action: 获完整链授权后执行一次固定 PREPARE/TRAIN_B/TRAIN_C/CHECK，异常停止且不重试。
