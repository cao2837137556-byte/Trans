# Claude 交接：CKBV r10 及后续完整技术方案

日期：2026-07-27（Claude 主线接手期间；若 token 耗尽，Codex 或下一位 Claude
从本文件 + 仓库事实直接续上，冲突时以最新 commit / 代码 / 正式 run artifact
为准）。分支 `codex/exp-mainline`，撰写时 HEAD `5c5a1c5`。

## 0. 一句话现状

emit 性能墙已破（TShark 权威确认 29/30 源 100% 覆盖）；唯一真实数据缺口
= hydraulic-system-1 一个源 1353 个 ood_val 目标错配（0.4163%）；已按 Codex
有条件批准实现 `raw51_observable_v1` 掩码（commit 5c5a1c5，横跨三文件）；
掩码实现正在多 agent 对抗审查中。**下一步 = 审查过关 → 打 r10 → 跑出
seed-27 正式结果 → 进入能力升级阶段。**

## 1. 立即下一步：完成 r10 并提交（阻塞项）

### 1.1 审查收尾
后台工作流 `review-raw51-mask`（task wzd1efi6d）三视角逐条核对 Codex 九约束。
- 若 0 confirmed：直接进 1.2。
- 若有 confirmed：按 verdict.corrected_fix 修 → 重跑受影响单元测试 → 重新提交
  → 再打包。修复不得违反九约束。

### 1.2 r10 slurm 接线（尚未做，打包前必须完成）
掩码参数已加进三个 py 的 argparse（`--raw51-mask` / `--raw51-mask-sha256`），
但 **slurm 脚本 `scripts/issue27ckbv_checkpointed_process_formal.slurm` 还没
把它们传下去**。需要：
- 定义 `RAW51_MASK=$BASE/runs/raw51_observable_v1/raw51_observable_v1_mask.csv`
  与 `RAW51_MASK_SHA256=b16017d2755feaedbe6d3ad76fd7d1e2444cf66a14a70f6bca35f270734ad2df`。
- 在 `--mode run-gotham-members`（约 L278）与 `--mode aggregate-gotham`（约 L294）
  与 FORMAL `--mode formal`（约 L307 附近）三处调用加
  `--raw51-mask "$RAW51_MASK" --raw51-mask-sha256 "$RAW51_MASK_SHA256"`。
- installer `issue27ckbv_install_and_submit_dual.sh` 的不可变输入检查表加入
  mask 文件（大小+sha256），并把 mask 加进 EXPORTS / 传给 slurm。
- build_bundle.ps1 的 `$payloadFiles` 加入
  `runs/raw51_observable_v1/raw51_observable_v1_mask.csv`（及 README/.sha256），
  clean-extract gate 加断言：mask 文件存在且 sha256==b16017d2…。
- 预物化覆盖校验 gate（账本 §11 永久 gate 3）：在 run-gotham-members 聚合前，
  对每个非掩码源校验其目标指纹覆盖，缺失即 fail-fast，不再跑数小时后崩。
  最省实现 = 复用 `runs/.../ckbv_tshark_coverage_review` 逻辑，或在
  aggregate 前加一遍轻量断言（29 源 must 100%、air-quality 走 source 缓存、
  hydraulic-1 must 完全在 mask 内）。

### 1.3 r10 bundle 与提交
- `powershell scripts/issue27ckbv_build_bundle.ps1 -BundleName issue27ckbv_checkpointed_process_seed27_dual_20260727_r10`
- REUSE_ROOTS 已含 154620/154621 等（member/source checkpoint 全复用；
  member_plan_sha256 不因 mask 改变，这是 62 个 checkpoint 可复用的前提，
  必须在打包前用 `--mode plan-gotham-members` 本地或远端确认 plan 哈希与 r9 一致）。
- 上传 + `sha256sum -c` + 解包 + `bash payload/scripts/issue27ckbv_install_and_submit_dual.sh`
- 监控 `CKBV_RUNTIME_GATE_PASS`；**这次预期能越过聚合**（hydraulic-1 被跳过），
  进入 `aggregate_causal_features → formal_seed27_model → phase=complete`。
  全部 checkpoint 复用 + emit 已快，正式跑预计 1–2 小时。

### 1.4 拉回与分析
- validator 自动打 pullback tar（排除大缓存）。拉回后跑
  `python repo/ood/issue27ckbv_seed27_pullback_analysis_v1.py --run-root <解压目录>`
  （已写好并自测通过，commit 早于 5c5a1c5）。它输出：九条 GO 子条件独立复核、
  按机制 AUROC、救援分支在四类 OOD 触发率、家族级救援地图。
- **注意新增列**：predictions 现有 `raw51_observable` 列；分析脚本读到
  `M0-C1-raw51obs` 候选与 `ckbu_raw51_mask_sensitivity_audit.csv`，
  向用户报双分母 C1 与 ood_val 8682→7329 的阈值敏感性（Codex 约束 4/5）。

## 2. seed-27 结果三分叉（预案，不临时发明）

预演（`mechanism_signal_local_preview_20260726.md`）保守下界：
scan vs 跨环境 AUROC 0.977、bruteforce 0.9997（跨环境信号强）；同环境
0.589/0.686（同环境混淆重）。据此预判 seed-27 **最可能部分成功**。

- **GO（九条件全过，~15-25%）**：立即预注册 seeds 37/47（聚合判据须先固定：
  均值过线 vs 全 seed 过线）+ 基线对比同窗口 → sealed cooler holdout 最后开 →
  方法论文。
- **部分成功（总召回回升但差 0.5pp 门槛，~55-65%，最可能）**：读诊断决定
  升级阶梯拧哪级（见 §3）。不缝补当前 run，走新预注册 CKBW → 再跑一轮
  （一天级迭代：全 checkpoint 复用，只重训头/重选阈值，2-3 小时）。
- **救援全失败（scan/BF 都救不回，~10-15%，预演信号不支持）**：终止统一过程
  救援路线，转 §4 备胎，或收缩为“问题+机理”论文（素材已备：无解证明 +
  CKBQ 抑制 + CKBL 阈值不迁移 + 机制救援地图）。

## 3. 能力升级阶梯（按性价比排序，全部遵守“借成熟+小幅创新”与冻结协议）

诊断路标（seed-27 报告里已能算）：过程头按机制 AUROC + 救援分支 OOD 触发率。

1. **救援否决条件（最高优先，零新数据零新模型）**：当前救援 =
   `C1判攻击 OR 过程分数≥τ`，改为**双信号**——过程分数高 **且** 正常性余量弱
   （抑制是擦边做出的）才救。四类 OOD 正常性余量强 → 不会被重新放出；被误杀
   攻击多是擦边被压 → 救援力几乎不损。二维决策区域替代两个一维阈值，同在合法
   数据校准。预演的同环境弱可分性（0.589）正指向这个修复。
2. **按机制分阈值（不是按家族）**：ToN 监督本就分 scan / credential_bruteforce
   两类；训练双头各自在良性 select 上校准，比混合分布干净。**不违反**“不许每
   攻击家族一个专家”——机制类是协议认可粒度。
3. **CKBT 配方补洪水监督**：ToN 有 ddos/dos 类别，照 CKBT 已审计通过的
   “源文件不相交 + 时间+五元组唯一匹配 + 只批静态专家”配方做 `flood` 机制库，
   补 Merlin UDP Flooding（-8.8pp）。
4. **beaconing 专家 CKBW**：无监督 RITA 式周期性评分（间隔中位数/MAD 离散比/
   载荷一致性，纯历史窗口因果化）+ 纯良性分位校准，补 Merlin C&C（-9.3pp）。
   **先过可行性门**：IoT 良性遥测本身高度周期，可能顶死分位 → 若分不开，加
   “周期性 × 目的地稀有度”第二分离轴；仍不行则写 documented limitation。
5. **窗口粒度过程表示**：借已在 vendor 闭包、已因果化的 MiniRocket，反向跑在
   51D 事件流短窗口上产窗口描述子，作第三证据接进同一非对称骨架。零新依赖。
6. **（储备）预训练流量表征**：ET-BERT/YaTC 官方权重冻结做特征 + 线性探针。
   工程量大（分词/GPU），放末端。

**平行线（不占超算、不碰冻结协议）**：conformal 按来源校准形式化——把 CKBQ
的 per-source 抑制重写成分组保形（Mondrian）语言，证明 FPR ≤ α+ε+O(1/n) 引理。
**必须先复盘 CKBP gate degeneracy 的三颗雷**（见记忆 [[ckbv-protocol-facts]] /
CKBP 复盘）：①冷启动/不可靠状态必须显式掩码不得编码进分数，且阈值须过可达性
校验；②每组校准样本量须 > burn-in，不够的组回退父组分位（Mondrian fallback，
须预注册）；③组状态须来自部署等价、label-free、past-only 全流背景，不能建在
class-conditioned 目标队列上。

## 4. 备胎路线（仅当 §2 救援全失败）

- **预训练流量基础模型做过程分支**：不再手工造特征（这是用户批评的“自造轮子”
  反例）；拿 ET-BERT/YaTC/netFound 官方权重，只做因果化截断 + 无泄漏微调。
- **收缩为问题论文**：Sommer&Paxson / TESSERACT 先例证明“被严格证明的困难”
  在安全顶刊/会可发。前八节骨架（`paper_skeleton_zh_20260726.md`）刻意不依赖
  结果方向，救援失败也能成稿。

## 5. 论文（不依赖结果，现在就能推进）

骨架 `paper_skeleton_zh_20260726.md` 已落库。可现在定稿：§1 引言（含与标准
跨数据集迁移的区别 = novelty 位置）、§2 相关工作（复用 5 月资产）、§3 形式化、
§4 单决策面结构性无解证明（890 枚举，全篇最硬）、§5.4（今日机制预演直接证据）、
§7 严格性（Arp《Dos and Don'ts》十大陷阱对照表）、§8 局限（仿真测床 + ToN 标签
质量主动披露）。待 seed-27 的：§6 结果表、§9 结论定调。基线对比预注册草案
`baseline_comparison_prereg_draft_20260726.md` 待用户批准转正式。

目标刊物：**TIFS 主投（中科院一区/CCF-A 期刊）**，TDSC（二区/CCF-A）为退路，
RAID/ACSAC（CCF-B 会议）为二级退路，四大安全会为 stretch。一区门槛不是绝对
强度，是“相对（同协议下打赢官方基线的部署工作点）+ 诚实（held-out/预注册/
多seed/第三数据集/limitations）”。

## 6. 不可触碰（冻结红线，任何后续实验都不得违反）

seed 27 先行；Gotham 严格 1M 划分；support_train 385 / support_val 69；
Injection/MITM reserved 且 model usage=0；51D schema 固定有序；score-before-
update / past-only / source-local / raw-label 不进前端；held/report/sealed 不进
fit/标准化/校准/gate/负采样/模型选择；stream-consumer 与 hydraulic-system 是
已用 development canary（严格 held 协议下整族仍须隔离，raw51 mask 不替代该隔离）；
cooler-motor final holdout SEALED_NOT_OPENED；review=0；不得自动启动 seeds 37/47；
失败必先入账本 + 永久 gate 才重试；不自装环境（用 HPC module + 打包依赖）。

## 7. 关键文件索引

- 掩码：`runs/raw51_observable_v1/`（csv + sha256 + README）
- 账本（含 §10 emit / §11 对齐审计与自纠正 / 权威覆盖 / mask 处置）：
  `runs/mainline_docs/hpc_failure_ledger_and_launch_gate_20260725.md`
- mask 预注册草案：`runs/mainline_docs/raw51_observable_v1_mask_prereg_draft_20260726.md`
- 分析脚本：`repo/ood/issue27ckbv_seed27_pullback_analysis_v1.py`（--selftest 通过）
- 覆盖率复盘产物：r9 run root 下 `ckbv_tshark_coverage_review.csv`
- 三个改动的核心 py：见 §1.1；正式消费者 = `issue27ckbu_unified_process_rescue_formal_v1.py`
- 用户约束记忆：`.claude` memory `borrow-mature-and-rigor` / `hpc-workflow-discipline`
