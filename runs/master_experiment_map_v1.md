# master_experiment_map_v1

> 版本：v2（2026-04-12）  
> 用途：作为后续实验补充、论文写作与 A 区增强路线的固定“总地图”，避免实验散点化推进。

---

## 一、项目总目标（作者视角）

这篇论文的核心目标已经明确为：在 **original-frontend 100维** 的可信输入链上，研究 stronger OOD（更强分布外）场景下异常检测的**低误报稳健性机制**。因此它不是“换一个 detector 看分数高低”的小模型对比，而是“协议强度 + 阈值机制 + 模型补充修正”的系统问题：先坐实 stronger OOD 的误报放大现象，再证明 calibration（校准）是主要杠杆，最后用 TailReg（尾部正则）给出模型层的定向补充改进。

---

## 二、实验总框架（总表）

| 模块 | 当前状态 | 论文作用 |
|---|---|---|
| 1) 历史链 detector 比较（clean115） | 已完成基础版 | 后端比较与历史对照 |
| 2) stronger OOD 主线现象（frontend100） | 已完成并稳定 | 主结果现象证据 |
| 3) calibration 机制实验 | 已完成并稳定 | 主线机制证据（核心） |
| 4) TailReg 方法实验 | 已完成阶段稳定版 | 模型层补充贡献 |
| 5) 扩展验证（更多 capture/能力约束/效率） | 进行中（已完成 Transformer fixed-vs-dA 自检） | A区完整性与泛化增强 |

---

## 三、当前已完成实验（按“支撑什么主张”整理）

### A. 动机证据

**1) 已完成实验**
- `runs/ood_probe_stage1_2026-03-21`
- `runs/ood_probe_stage1_stability_2026-03-21`
- `runs/ood_probe_2026-03-21`

**2) 核心结果**
- 在 adapter/映射链路下观察到非常强的 OOD benign 误报（含接近灾难级现象）。

**3) 论文作用**
- 用于说明“开放世界误报失稳值得研究”，即问题发现与研究动机。

**4) 边界说明**
- 该链路存在 schema 映射与输入一致性问题，只能做动机证据，不能当正式主结论。

---

### B. 输入链纠错证据

**1) 已完成实验**
- `runs/csv_input_clean_stage1_2026-03-23`（dirty116 -> clean115）
- `runs/kitsune_frontend_stage1_2026-03-22`（原版前端最小接入）

**2) 核心结果**
- 证实 `Mirai_dataset.csv / my_gold_mirai.csv` 的 116 维含索引样首列污染；清洗后得到 clean115。
- 原版前端链成功产出稳定 100维特征缓存（不再依赖 adapter）。

**3) 论文作用**
- 解决“输入空间不一致/污染”这一可信度前提问题，为主线结论提供可辩护输入基础。

**4) 边界说明**
- clean115 与 original-frontend 100 是两条并行输入轨道，不能混写成同一主线结果。

---

### C. 历史链 detector 比较证据（clean115）

**1) 已完成实验**
- `runs/csv_input_clean_stage1_2026-03-23/trans115_min`
- `runs/csv_input_clean_stage1_2026-03-23/da115_min`
- 同配置 dirty116 对照：`trans116_dirty_min` / `da116_dirty_min`

**2) 核心结果**
- clean115 与 dirty116 的分数统计显著不同，确认索引列污染会扭曲 detector 行为。
- 在 clean115 下已完成 Transformer 与 dA 的可复现实验入口。

**3) 论文作用**
- 承担“历史链输入纠错后后端比较”的对照角色，支撑方法选择的历史合理性。

**4) 边界说明**
- 不用于 stronger OOD 主结论；该链路不等价于原版前端 100维主线。

---

### D. stronger OOD 主线证据（frontend100）

**1) 已完成实验**
- 同 capture 分段（较弱 OOD）：`runs/frontend100_ood_stage1_2026-03-23`
- cross-capture stage1（更强 OOD）：`runs/frontend100_crosscapture_stage1_2026-03-25`
- cross-capture 多 seed 稳定：`runs/frontend100_crosscapture_stability_2026-03-25`

**2) 核心结果**
- 同 capture 分段下报警率低（Transformer 0.00610，dA 0.01085）。
- cross-capture 后 fixed 报警显著升高（stage1：Transformer 0.44175，dA 0.12580；多 seed 稳定维持高误报趋势）。

**3) 论文作用**
- 直接支撑“stronger OOD 问题真实存在”，并完成从弱协议到强协议的递进证据链。

**4) 边界说明**
- 当前 strongest 组合主要是 7-6 -> 4-1；跨更多 benign capture 的泛化还需补。

---

### E. calibration 机制证据（主线核心）

**1) 已完成实验**
- 阈值基线：`runs/frontend100_crosscapture_threshold_2026-03-25`
- 校准扫描：`runs/frontend100_crosscapture_calibration_scan_2026-03-25`
- 关键设置多 seed 稳定：`runs/frontend100_crosscapture_calib_stability_local_2026-03-30`

**2) 核心结果**
- Fixed OOD alarm ratio（mean ± std）：  
  - transformer：`0.4548 ± 0.2769`  
  - da：`0.1378 ± 0.0050`
- Calibrated（budget=5000,target=1%）：  
  - transformer：`0.01549 ± 0.00068`  
  - da：`0.01516 ± 0.00003`
- gap：`0.316983 -> 0.000333`，缩小约 `99.9%`。

**3) 论文作用**
- 形成当前最强机制结论：**threshold layer 是主要杠杆**。

**4) 边界说明**
- 该结论成立于“无监督 OOD 校准可用”的设置；预算更小、场景更换时的鲁棒性仍需补。

---

### F. TailReg 方法证据（阶段性方法贡献）

**1) 已完成实验**
- 方法首轮：`runs/frontend100_tailreg_stage1_2026-03-27`
- 超参扫描：`runs/frontend100_tailreg_hparam_scan_2026-03-28`
- 最优配置多 seed 稳定：`runs/frontend100_tailreg_bestcfg_stability_2026-03-28`

**2) 核心结果**
- 最优配置：`lambda=0.2, k=1.0, warmup=256, ema_alpha=0.01`
- fixed OOD alarm（mean ± std）：  
  - transformer：`0.4548 ± 0.2769`  
  - transformer_tailreg：`0.1393 ± 0.0911`  
  - da：`0.1378 ± 0.0050`
- calibrated 后 transformer 与 tailreg 基本重合（约 `0.01549`）。

**3) 论文作用**
- 支撑“模型层可补 fixed-threshold 脆弱性”的阶段性方法贡献。

**4) 边界说明**
- TailReg 不是 calibration 替代方案；当前不支持“全面提升 Transformer”的表述。

---

## 四、当前论文已经“写得动”的结论

### 可写（阶段性稳定结论）
- stronger OOD（cross-capture）下误报问题真实存在。
- fixed threshold 会显著放大 detector 间误报差距。
- calibration 是当前误报控制的主要杠杆。
- TailReg 主要改善 fixed-threshold 下 Transformer 的尾部敏感性。

### 不可写（禁止过度主张）
- “Transformer 全面优于 dA”。
- “TailReg 在所有评估条件下都优于 baseline 和 dA”。
- “calibration 已彻底解决开放世界低误报问题”。
- 把 clean115 或 adapter 链结果写成 stronger OOD 主结论。

---

## 五、后续必须完成的实验（优先级）

### A. 必须做

1) **扩展 benign cross-capture 组合（至少再补 2 组）**  
- 为什么：当前 strongest 结论主要基于 7-6 -> 4-1，外推范围仍窄。  
- 支撑主张：stronger OOD 误报放大是否具有场景普适性。  
- 论文位置：Main Results + Robustness subsection。

2) **补“低误报不以漏检为代价”验证（恶意检测能力约束）**  
- 为什么：只看 benign 误报不足以完成检测器评价闭环。  
- 支撑主张：calibration/TailReg 降误报后仍保持检测能力（TPR/PR-AUC 不明显掉）。  
- 论文位置：Results 主表（误报-检出联合结果）。
- 2026-04-02 进展：已完成 `runs/frontend100_transformer_self_audit_2026-04-02/` 自检，确认 fixed 下 transformer 攻击分数存在更大阈下质量，当前差距更偏向“分布-阈值交互”而非实现口径错误。
- 2026-04-02 进展：已完成 `runs/frontend100_threshold_tradeoff_constrained_2026-04-02/`（score-only 阈值扫描 + detection-constrained 规则）。结论：naive calibration（budget=5000,target=1%）会将三种 detector 检出压到近0；引入 detection-floor 规则后可在约 7%~8% OOD 报警水平恢复约 50% 高纯攻击检出，显示 decision rule 层存在可用 operating region。
- 2026-04-03 进展：已完成 `runs/frontend100_constrained_rule_multiseed_2026-04-03/` 最小必要多 seed 复验（seed=101/202/303，detector=transformer/transformer_tailreg/da，规则=fixed/naive/det50/det60，附 alarm<=5% 弱基线）。结论：naive 在多 seed 下稳定近零检出；detection-floor 可稳定恢复到目标检出层，但 transformer 系列在 constrained 点的 OOD alarm 方差仍偏高，da 在 constrained 区域更稳。
- 2026-04-03 进展：已完成 `runs/frontend100_mae_v1_2026-04-03/`（Transformer-MAE-v1 单seed最小扫描，mask_ratio=0.3/0.4/0.5，比较 transformer/transformer_mae_v1/da，含 fixed+naive+det50）。结论：MAE 在 fixed 下可显著降低 OOD alarm（约 0.446 -> 约 0.071），但 attack detection 明显下降（约 0.634 -> 0.228~0.336）；m0.3 为当前检测保留最佳，MAE 单线尚不足反超 dA，建议下一步转入 MAE+TailReg 并做最小多 seed 复验。
- 2026-04-03 进展：已完成 `runs/frontend100_mae_tailreg_v1_2026-04-03/`（single-seed MAE+TailReg-v1，mask=0.3/0.4，比较 transformer/transformer_tailreg/transformer_mae_v1/transformer_mae_tailreg_v1/da，含 fixed+naive+det50）。结论：MAE+TailReg 在 mask=0.4 下相对 MAE-v1 可小幅修回 fixed detection（+0.0309）且基本保住低 alarm，但 detection 仍明显低于 transformer 与 dA，当前可作为“继续验证候选”而非已完成修复。
- 2026-04-04 进展：已完成 `runs/frontend100_uncertainty_v1_2026-04-04/`（Transformer-Uncertainty-v1，单seed，稳定版 `log_var` + clamp + Gaussian NLL，比较 `error-only / uncertainty-only / combined_nll`，并与 `transformer/da` 同口径对照，含 fixed+naive+det50）。结论：数值稳定性正常（NaN/Inf=0），但 `log_var` 下界触碰 clamp（-8.0）；`combined_nll` 固定阈值下可将 OOD alarm 降至约 0.0747，但 high-purity detection 仅约 0.4439；分离度上 `combined_nll` 略劣于 `error-only`（AUC 约 0.573 vs 0.602），表明 uncertainty v1 当前更像“降误报方向”而非直接提升检出。
- 2026-04-04 进展：已完成 `runs/frontend100_latent_contrastive_v1_2026-04-04/`（Transformer-LatentContrastive-v1，single-seed，margin∈{1,5}、lambda∈{0.1,0.5}，比较 transformer/transformer_tailreg/transformer_latent_contrastive_v1/da，含 fixed+naive+det50，附 latent distance 分析）。结论：fixed 下可见“提检出”趋势（最佳点 detection 最高达约 0.754），但伴随明显 alarm 反弹（最高约 0.55），尚未满足“提检出且不炸误报”；较稳健点（m=5, l=0.5）可将 alarm 压至约 0.094 但 detection 仍低于原始 transformer。说明该线已体现分离塑形潜力，但负样本构造与损失权重仍需继续收敛。
- 2026-04-04 进展：已完成 `runs/frontend100_latent_contrastive_compact_v2_2026-04-04/`（Transformer-LatentContrastive-Compact-v2，single-seed，固定 `m=5, lambda_margin=0.5`，扫描 `lambda_compact∈{0.01,0.05,0.1}`，引入 Cross-window Swap + EMA-detach center compactness + warm-up，比较 transformer/transformer_tailreg/latent_v1_best/latent_compact_v2/da，含 fixed+naive+det50 与 latent spread 分析）。结论：v2 在低 `lambda_compact` 下可进一步压低 fixed alarm（约 0.0747），但 detection 下降到约 0.494；高 `lambda_compact` 可把 detection 拉到约 0.679，但 alarm 反弹至约 0.501。当前尚未实现“比 v1 更优的 detection-alarm 同时改进”，但已明确 compactness 强度与 trade-off 的方向性约束。
- 2026-04-05 进展：已完成 `runs/frontend100_negative_semantics_ablation_2026-04-05/`（latent 主线 synthetic negative semantics ablation，single-seed，固定 `m=5, lambda_margin=0.5`，对 `cross-window swap / local permutation / mild spike` 做单类型与双类型组合消融，比较 transformer/transformer_tailreg/latent_v1_best/latent_compact_v2_lc0.01/da，含 fixed+naive+det50、四类分布图与 OOD-Negative overlap 指标）。结论：negative 语义对 detection-alarm trade-off 影响显著；`swap_only` 为当前最稳 utility 点（低于原始 transformer 的 alarm 但 detection 未超过 v1_best），`swap+spike` 检出最高但 alarm 明显反弹；目前未出现对 v1_best 的严格 fixed 支配配方，说明下一步应在最佳语义配方上做最小多 seed/轻量叠加，而非继续盲扫 compactness。
- 2026-04-05 进展：已完成 `runs/frontend100_negative_recipe_rescoring_2026-04-05/`（关键 latent recipe 严格离线重评分；不训练、不改 checkpoint；比较 RMSE / Latent-L2 / Latent-Cosine / Hybrid-L2 / Hybrid-Cosine，覆盖 fixed+naive+det50，并补 attack_high vs OOD_eval ROC-AUC、分布图与相关性分析）。结论：存在显著 scoring mismatch 迹象；`latent_swap_spike_mix` 在 RMSE 下呈“高检出高报警”，换到 latent/hybrid（当前以 `hybrid_cosine` 最优）后可在保持较高检出的同时明显降低报警，支持下一步以“最佳 recipe + 最佳 score”做最小多 seed 复验。
- 2026-04-05 进展：已完成 `runs/frontend100_latent_compact_v3_smoketest_2026-04-05/` 本地最小自检与 `runs/frontend100_latent_compact_v3_2026-04-05/` 超算协议准备（`compact_v3` 代码路径、`hybrid_cosine` 锁定评估、`lambda_compact={0.01,0.05,0.1,0.5}` 运行定义、`job.slurm`/`upload_bundle.zip`/`upload_manifest.txt`）。当前阻塞点为本 shell 环境对 `school-hpc` 非交互认证未打通，待凭据可用后执行正式 HPC 训练与打包回传。
- 2026-04-05 进展：已切换为本地正式运行 `runs/frontend100_latent_compact_v3_2026-04-05_local_full/`（single-seed，全量 `lambda_compact={0.01,0.05,0.1,0.5}`，`hybrid_cosine` 评估锁定），后台进程已启动，待跑完后回填最终结果与结论。
- 2026-04-05 进展：已完成 `runs/frontend100_latent_compact_v3_2026-04-05_local_live/`（Transformer-LatentContrastive-Compact-v3，single-seed，negative=`latent_swap_spike_mix`，`m=5.0`、`lambda_margin=0.5`，扫描 `lambda_compact={0.01,0.05,0.1,0.5}`，评估锁定 `hybrid_cosine`）。结论：`lc=0.01` 为 v3 最优，但相对 no-compact（latent_swap_spike_mix）在 fixed 点仍呈 `alarm +0.0115 / detection -0.0460`，未形成“降 alarm 且保 detection”的净外移；相对 transformer_tailreg 则表现为“更高 detection 但更高 alarm”。
- 2026-04-05 进展：已完成 `runs/frontend100_score_postprocessing_2026-04-05/`（锁定 `latent_swap_spike_mix` 做强化版离线 score-postprocessing；不训练、不改 checkpoint；在 `hybrid_cosine` 基础上比较 weighted hybrid、`log-transform + z-score`、`MAD` 稳健标准化，并重点检查 pure cosine，统计量严格来自 ID benign eval）。结论：评分器确实是当前主矛盾的一部分；最佳 fixed 点为 `log_weighted_z_rmse0.5_cos1.0`，相对默认 `hybrid_cosine` 将 OOD alarm 从约 `0.3261` 压到 `0.1857`，同时 high-purity detection 从约 `0.8955` 降到 `0.8233`。说明“降 RMSE 权重 + log 化”可明显改善 trade-off，但 pure cosine 虽 alarm 极低（约 `0.0368`）却 detection 明显不足（约 `0.4095`），MAD 版本也未优于 log 版本；当前更像 score-combination 问题而非纯模型崩坏，仍不足直接进入多 seed。
- 2026-04-06 进展：已完成 `runs/frontend100_locked_candidate_multiseed_2026-04-06/`（正式 seed=`101/202/303` 的最小必要多 seed 验证；锁定 recipe=`latent_swap_spike_mix`，比较旧评分 `hybrid_cosine_default` 与候选新评分 `log_weighted_z_rmse0.5_cos1.0`，并与 `transformer / transformer_tailreg / da` 官方口径对照，统一报告 fixed+naive+det50）。结论：新评分在多 seed 下**未稳定优于**同 recipe 旧评分器，fixed 均值仅从 `alarm 0.2220 -> 0.2161` 小幅下降，同时 `detection 0.6558 -> 0.6353` 回落；但相对 `transformer_tailreg`，该 latent 主候选在 fixed 下呈“更高检出、更高报警”，在 det50 下则能以更低 alarm 达到近同等 detection。相对 `da` 仍未进入全面可竞争区间（fixed 下同时更高 alarm、更低 detection），naive calibration 也继续在多 seed 下稳定塌检出。当前证据支持其作为“Transformer 家族的强候选之一”，但**不足以直接锁定为正式最强主候选**。
- 2026-04-06 进展：已完成 `runs/frontend100_mae_latent_v1_2026-04-06/`（Transformer-MAE-LatentContrastive-v1，single-seed，固定 negative=`latent_swap_spike_mix`、`m=5.0`、`lambda_margin=0.5`，扫描 `mask_ratio={0.3,0.4}`，primary score 回退为 `hybrid_cosine_default`，比较 transformer/transformer_tailreg/latent no-compact/mae+latent/da，统一报告 fixed+naive+det50，并附 trade-off、分布与局部 attack 响应图）。结论：融合线未实现预期的“降 alarm 且不明显伤 detection”；`mask=0.4` 为本轮较优点，fixed 下将 OOD alarm 从 no-compact 的约 `0.3261` 压到 `0.1201`，但 high-purity detection 同时从约 `0.8955` 降到 `0.5174`；`mask=0.3` 则同时表现为高报警（约 `0.4475`）与低检出（约 `0.5188`）。相对 `transformer_tailreg`，`mask=0.4` 虽 fixed alarm 更低，但 detection 更差，det50 下也未形成更优 trade-off；相对 `da` 则仅在 fixed alarm 上接近持平，但 detection 仍明显落后。当前证据**不支持**将 MAE+Latent 融合线直接推进为下一轮多 seed 主候选，更像是 MAE mask 机制削弱了 latent separation 与 attack 响应。
- 2026-04-06 进展：已完成 `runs/frontend100_latent_scorer_benchmark_2026-04-06/`（latent scorer benchmark 离线总决赛；不训练、不改 checkpoint；主 checkpoint 锁定 `latent_swap_spike_mix_no_compact`，比较旧单中心 hybrid、全局 single-center latent、双中心方向 `score_dir`、`LedoitWolf/OAS` 马氏距离及轻量 hybrid，统计与阈值严格只来自 ID benign train/calibration，补相关性矩阵与 benign latent 协方差主方向分析）。结论：当前瓶颈**不只是 scorer 粗糙**。旧 best scorer `log_weighted_z_rmse0.5_cos1.0_old` 仍是最佳 fixed 点（约 `alarm 0.1857 / det 0.8233`）；双中心方向 scorer 明显失败（`score_dir_cosine` fixed 仅约 `0.2734 / 0.0963`），说明“攻击原型方向打分”在当前表示上并未成立。`mahalanobis_ledoitwolf` 虽 fixed 下报警过高（约 `0.5843`），但 AUC 最强（约 `0.8991`），并在 det50 点把 OOD alarm 压到约 `0.0516`、同时保持约 `0.5015` detection，且 naive calibration 也不再完全塌到近零检出（约 `0.1175`）。这表明 covariance-aware scorer 有真实信号，但尚不足支持“只换 scorer 就能让当前 latent 线在 fixed 下反超 dA”；若继续推进，更值得押注 covariance-aware 方向，而不是直接进入双中心 prototype 训练线。

3) **在 stronger OOD 上补一个轻量传统 baseline（非重模型）**  
- 为什么：目前主比较集中在 Transformer 与 dA，需要最低限度外部参照。  
- 支撑主张：当前机制结论不是“双模型偶然”。  
- 论文位置：Results 对比段（附表或补充表）。

4) **补效率与代价（训练/推理/校准开销）**  
- 为什么：A区评审会问“效果是否靠高成本换来”。  
- 支撑主张：方案具备工程可行性（尤其校准预算/延迟）。  
- 论文位置：Discussion 或 Deployment Consideration。

---

### B. 强烈建议做

1) **小预算 calibration 稳定性（多 seed，多组合）**  
- 为什么：当前最佳结果依赖 budget=5000，需评估资源敏感性。  
- 支撑主张：阈值层杠杆在受限预算下是否仍有效。  
- 论文位置：Calibration Analysis 扩展小节。

2) **TailReg 方差收敛与稳定性分析（固定最优附近）**  
- 为什么：TailReg 的 fixed 误报 std 仍明显高于 dA。  
- 支撑主张：TailReg 不仅降均值，还能降波动。  
- 论文位置：TailReg Results/Analysis。

3) **统计显著性/置信区间补充**  
- 为什么：主结论基于多 seed，加入显著性可提高审稿说服力。  
- 支撑主张：gap 收缩与 fixed 改善不是随机波动。  
- 论文位置：Results footnote 或附录统计说明。

---

### C. 可选增强

1) **更强 OOD 强度梯度（跨更多设备/时段/协议域）**  
- 为什么：进一步放大挑战，验证结论边界。  
- 支撑主张：结论的适用范围与失效边界。  
- 论文位置：Discussion / Limitations。

2) **不确定性或分数校准高级方案（轻量）**  
- 为什么：在“阈值层主导”已成立后，可探索更稳阈值机制。  
- 支撑主张：机制深化，不改变主线框架。  
- 论文位置：Future Work 或附加实验。

3) **可解释性可视化增强（尾部样本画像）**  
- 为什么：帮助解释 TailReg 为什么主要作用于 fixed 场景。  
- 支撑主张：机制可解释性提升。  
- 论文位置：Analysis 图补充。

---

## 六、后续方法改进主线（修 Transformer 路线图）

基于现有证据，后续“修 Transformer”应坚持 **阈值层优先、模型层补充**，而不是回到大模型替换：

1) **目标 1：固定阈值下更低误报均值 + 更低方差**  
- 继续围绕 normal score tail 设计轻量约束（TailReg 家族），重点降低 seed 间波动。

2) **目标 2：小预算校准友好性（calibration efficiency）**  
- 让模型分数分布更“可校准”：在 500~2000 budget 下也能稳定逼近目标报警率。

3) **目标 3：误报-检出联合优化**  
- 任何降误报改动必须同时报告检测能力不塌陷（TPR/PR-AUC 或召回约束）。

4) **目标 4：保持工程成本可控**  
- 不引入重模型；优先维持与当前流程兼容的轻量正则/后处理改动。

建议的方法线表述：  
**“先用 calibration 解决主矛盾，再用 TailReg 类模型约束降低 fixed-threshold 脆弱性与波动，并验证在低预算校准与检测能力约束下仍成立。”**

---

## 七、论文-实验映射表

| 论文部分 | 对应实验模块 | 当前状态 |
|---|---|---|
| Introduction（stronger OOD 动机） | 动机证据 + stronger OOD 递进（A+D） | 已可写 |
| Data/Input Reliability | 输入链纠错（B） | 已可写 |
| Main Results（stronger OOD） | D（同capture->cross-capture->多seed） | 已可写 |
| Calibration Analysis | E（threshold baseline + scan + local stability） | 已可写（核心） |
| TailReg 方法与结果 | F（stage1 + hparam + bestcfg stability） | 已可写（阶段性） |
| Discussion / Limitations | 边界与待补实验（A/C/D/E/F 边界 + 五） | 已可写，待增强 |

---

## 八、作者执行建议（下一步最稳推进顺序）

建议按下面顺序推进，避免再次“实验散点化”：

1) **先补“必须做”中的 1 + 2**（更多 cross-capture + 检测能力约束）。  
2) 同步补 **必须做 4**（效率/代价），确保主线结果可工程化表达。  
3) 再做 **强烈建议 1**（小预算 calibration 稳定性），强化“阈值层主杠杆”的适用范围。  
4) 最后再决定是否推进 **强烈建议 2/可选增强**，用于冲击更高说服力版本。  

以后每个新实验立项前先回答三件事：  
- 它属于本地图哪一模块？  
- 它要支撑哪一句论文主张？  
- 它完成后进入正文哪一节？  

如果这三点回答不清，就先不做，避免新增“无法入稿的实验”。

- `frontend100_covariance_regularized_v1_2026-04-07`: Transformer-CovarianceRegularized-v1 single-seed minimal experiment; two-sided variance hinge + off-diagonal decorrelation, old-best and Mahalanobis scoring. Path: `runs/frontend100_covariance_regularized_v1_2026-04-07/`.
- `frontend100_mahalanobis_rescue_2026-04-07`: Mahalanobis epsilon-floor rescue offline rescoring; no retraining. Path: `runs/frontend100_mahalanobis_rescue_2026-04-07/`.

- `frontend100_covariance_regularized_v2_2026-04-07`: Transformer-CovarianceRegularized-v2 single-seed minimal experiment; EMA covariance, Cholesky diagonal-loading score proxy, tail-aligned loss. Path: `runs/frontend100_covariance_regularized_v2_2026-04-07/`.

- `frontend100_diagload_sweep_no_compact_2026-04-08`: Offline no-compact latent Mahalanobis diagonal-loading sweep; no retraining. Path: `runs/frontend100_diagload_sweep_no_compact_2026-04-08/`.

- `frontend100_diagload_overlap_analysis_2026-04-08`: Offline lost-attack vs false-alarm overlap analysis for no-compact latent diagload; no retraining. Path: `runs/frontend100_diagload_overlap_analysis_2026-04-08/`.

- `frontend100_diagload_gate_rescue_2026-04-08`: Offline two-threshold diagload+raw-Mahalanobis gate rescue for no-compact latent; no retraining. Path: `runs/frontend100_diagload_gate_rescue_2026-04-08/`.
- `research_log/a_tier_experiment_progress_log.md`: Living paper-level experiment logic log for A-tier direction; maintained across future experiments. Path: `runs/research_log/a_tier_experiment_progress_log.md`.
- `frontend100_diagload_gate_multiseed_2026-04-08`: Multi-seed offline validation of no-compact latent covariance gate (`diag_f0.5 q99 OR raw Mahalanobis high-tail`); no retraining. Path: `runs/frontend100_diagload_gate_multiseed_2026-04-08/`.
- `frontend100_latent_tail_seed_diagnostics_2026-04-08`: Offline latent covariance-tail seed diagnostics for no-compact latent gate instability; no retraining. Path: `runs/frontend100_latent_tail_seed_diagnostics_2026-04-08/`.
- `frontend100_conditional_gate_multiseed_2026-04-08`: Conditional covariance gate multi-seed offline validation (`diag_q99 OR (raw_q AND diag_guard_q)`); no retraining. Path: `runs/frontend100_conditional_gate_multiseed_2026-04-08/`.
- `frontend100_external_baselines_2026-04-08`: Minimal external baselines on original-frontend 100D stronger OOD (`IsolationForest`, `OneClassSVM`, `LOF`, RF mixed-attack upper-bound); path: `runs/frontend100_external_baselines_2026-04-08/`.
- `frontend100_temporal_frontend_v1_2026-04-08`: Transformer TemporalFrontend-v1 single-seed minimal experiment on stacked original 100D windows; path: `runs/frontend100_temporal_frontend_v1_2026-04-08/`.
- `frontend100_latent_seed_ensemble_2026-04-08`: Offline seed-ensemble test for latent covariance tail instability; no retraining; uses formal seeds 101/202/303 cached latents. Path: `runs/frontend100_latent_seed_ensemble_2026-04-08/`.
- `frontend100_latent_seed_ensemble_idq_sweep_2026-04-08`: ID-only fixed quantile sweep for latent seed-ensemble scalar scores; no retraining. Path: `runs/frontend100_latent_seed_ensemble_idq_sweep_2026-04-08/`.
- `frontend100_recurrent_deep_baselines_2026-04-08`: Multi-seed LSTM-AE/GRU-AE deep sequence baselines on stacked original 100D windows; path: `runs/frontend100_recurrent_deep_baselines_2026-04-08/`.
- `frontend100_latent_ensemble_cost_ablation_2026-04-08`: 1/2/3-seed ensemble cost-effect ablation for covariance gate; no retraining. Path: `runs/frontend100_latent_ensemble_cost_ablation_2026-04-08/`.
- `frontend100_final_candidate_audit_2026-04-08`: Final candidate audit for covariance-aware Transformer ensemble vs dA/recurrent/external baselines; includes main table, cost table, score distributions. Path: `runs/frontend100_final_candidate_audit_2026-04-08/`.
- `paper_handoffs/2026-04-08/a_tier_paper_readiness_handoff_2026-04-08.md`: paper-readiness consolidation of main candidate, supplement-worthy results, overclaim boundaries, figure/table checklist.

- `prism_handoffs/2026-04-08/prism_paper_revision_pack_2026-04-08`: Prism paper revision pack based on current draft PDF and final experimental evidence; includes Prism prompt, copied draft PDF, main tables, figures, evidence summaries, and zip bundle. Path: `runs/prism_handoffs/2026-04-08/prism_paper_revision_pack_2026-04-08/`.

- rontend100_deep_svdd_baseline_2026-04-09: Multi-seed Deep SVDD baseline on original-frontend 100D stronger OOD; ID-benign-only training with AE pretrain and center-distance scoring. Path: 
uns/frontend100_deep_svdd_baseline_2026-04-09/.
- `frontend100_additional_ood_setting_smoketest_2026-04-09_b`: Additional benign OOD setting evaluation (same-capture temporal split) for current Transformer ensemble candidate vs dA and family references; no retraining. Path: `runs/frontend100_additional_ood_setting_smoketest_2026-04-09_b/`.
- `frontend100_additional_ood_setting_smoketest_2026-04-09_c`: Additional benign OOD setting evaluation (same-capture temporal split) for current Transformer ensemble candidate vs dA and family references; no retraining. Path: `runs/frontend100_additional_ood_setting_smoketest_2026-04-09_c/`.
- `frontend100_runtime_benchmark_smoketest_2026-04-09_b`: Runtime/throughput benchmark for dA, single-seed Transformer latent gate, and 3-seed Transformer ensemble on the fixed stronger-OOD workload. Path: `runs/frontend100_runtime_benchmark_smoketest_2026-04-09_b/`.
- `frontend100_runtime_benchmark_2026-04-09`: Runtime/throughput benchmark for dA, single-seed Transformer latent gate, and 3-seed Transformer ensemble on the fixed stronger-OOD workload. Path: `runs/frontend100_runtime_benchmark_2026-04-09/`.

- `paper_handoffs/2026-04-09/paper_asset_manifest_2026-04-09.md`: Frozen main/supplement paper asset manifest after runtime and Deep SVDD updates; use this file to choose paper figures/tables without re-reading raw runs.
- `paper_handoffs/2026-04-09/paper_asset_manifest_2026-04-09.csv`: Structured asset inventory for main paper and supplement.
- `paper_handoffs/2026-04-09/PRISM_UPDATE_PROMPT_2026-04-09.md`: Direct Prism instruction for updating the draft using the latest frozen evidence.

---

## 九、外部改进建议分流（Gemini 报告处理原则）

来源：
- `D:\study\paper\anomaly_detection\paper04\论文实验改进与提升建议-gemini报告.pdf`

总原则：
- 该报告可作为“长期升级蓝图”，不能直接当作“当前论文全部待办清单”。
- 当前论文已经接近收口，后续只吸收那些**能显著增强现有主线可信度、但不会改写问题定义**的建议。
- 任何新实验若会把论文从“stronger OOD + covariance-aware operating region”改写成“多数据集/多模态/对抗鲁棒/图模型大综述”，则默认不进入当前主线。

### A. 当前论文必须吸收的部分

1) **问题驱动而非唯指标驱动**
- 继续把主线写成：stronger OOD 暴露 benign OOD false alarm 瓶颈；Transformer 的问题是 latent covariance tail instability；最终 remedy 是 covariance-aware ensemble operating region。

2) **统计防御与部署防御**
- 继续补强 paired delta、seed-level scatter / CI、runtime/cost caveat。
- 所有 threshold 与 quantile 必须继续强调：只来自 ID benign，不使用 OOD/attack。

3) **baseline 完整性**
- Gemini 报告强调 baseline 现代性，这一点方向正确。
- 当前论文已用 `IF / OCSVM / LOF / LSTM-AE / GRU-AE / Deep SVDD / RF upper-bound` 基本补到足够水平；除非出现明显缺口，不再无边界扩 baseline 家族。

### B. 可选补强，但必须服从主线

1) **额外 OOD / cross-capture setting**
- 只有在它能增强当前主线时才进入正文。
- 若结果只会削弱主结论，则保留为内部诊断或 supplement 备选，不强行写进主文。

2) **单个现代 deep anomaly baseline**
- 仅在发现审稿风险仍集中于“baseline 太旧”时再补一个同口径、低工程风险的现代 baseline。
- 当前已有 `Deep SVDD`，因此这项暂不升级为必须做。

### C. 明确放入 Future Work，不进入当前论文主线

1) **多公开数据集全面迁移**
- 如 `BoT-IoT / TON-IoT / UNSW-NB15 / DataSense` 等。
- 这类工作量大，且会把当前论文从“固定 stronger OOD 设定下的机制论文”改成“新 benchmark / 大型泛化论文”。

2) **多模态 / foundation model / raw packet 级输入**
- 如原始流量、多模态融合、foundation model 方向。
- 这是下一阶段课题，不属于当前 paper 的必要收口内容。

3) **Mamba / FT-Transformer / GNN / 联邦框架 / 大型现代系统对照**
- 这类对照会大幅扩张工程面和问题边界，当前论文不吸收。

4) **对抗鲁棒性评测（FGSM/PGD/投毒/黑盒注入）**
- 这是一条新的安全问题线。
- 除非论文主问题改成“adaptive adversary robustness”，否则不进入当前主线。

5) **因果解释 / SHAP / root-cause attribution**
- 有价值，但属于下一篇或扩展工作。
- 当前论文主问题仍是 stricter evaluation + covariance-tail failure analysis + remedy。

### D. 执行规则

以后若参考外部报告新增实验，先回答三件事：
- 它是否直接增强当前主主张？
- 它是否会改变当前论文的问题定义？
- 它是否会显著拖慢收口节奏？

若答案分别不是：
- **是 / 否 / 否**  
则默认不进入当前论文主线。

---

## 十、阶段重定性（2026-04-12）

### A. 当前项目不再按“收口稿”理解

截至 2026-04-12，这个项目应被正式重定性为：

- **Phase 1 已完成**：我们已经完成问题定义、病理定位、主候选筛选、外部基线补充与一轮部署侧诊断。
- **当前进入 A 区增强阶段**：目标不再是“尽快把现稿修到能投”，而是把这条线扩成一篇真正具备顶级安全论文说服力的系统工作。

### B. Phase 1 已经完成的核心资产

1. **问题定义已经成立**
- stronger benign OOD 下，fixed / ID-only operating region 会暴露出真实的 benign false alarm 瓶颈。
- 这不是单纯“谁的 AUC 更高”的问题，而是“在部署阈值下谁还能稳定工作”的问题。

2. **病理定位已经成立**
- Transformer 主问题不是完全没学到攻击分离，而是 **latent covariance tail instability**。
- covariance-aware scorer / ensemble / diagload 之所以有效，是因为它抓到了这部分几何病灶。

3. **主线证据已经成形**
- original-frontend 100D stronger OOD 主线已跑通。
- dA、TailReg、latent scorer benchmark、runtime/cost、recurrent deep baseline、Deep SVDD baseline 已形成一组可写入论文的正反证据。

4. **负结果资产已经成形**
- MAE、prototype、covreg v1/v2、离线 rescoring 补救、distillation v1 都是可用的失败诊断材料，不再视作“废实验”。

### C. 当前距离 A 区仍缺的四个硬缺口

1. **更现代、更有代表性的 baseline 还不够完整**
2. **第二数据集 / 第二设置的跨环境自证还不够**
3. **adaptive adversary / adversarial robustness 评估缺失**
4. **deployability 闭环仍未真正完成，单模型替代 ensemble 尚未成立**

---

## 十一、2026-04-09 至 2026-04-11 新证据裁决

### A. Deep SVDD baseline：现代 deep one-class 并不能自动解决 fixed 问题

对应运行：
- `runs/frontend100_deep_svdd_baseline_2026-04-09/`

结论：
- fixed q99 下，Deep SVDD 达到 `alarm=0.7034, det=0.9459`。
- 它证明“现代深度 one-class 模型可以把 detection 顶得很高，但在 stronger benign OOD 下 fixed false alarm 会严重失控”。
- 这条结果应保留在论文与地图中，作为“现代深度模型同样会在 fixed 部署区间翻车”的强证据。

裁决：
- **保留为关键外部 baseline 证据，不发展为主线方法。**

### B. Ensemble Distillation v1：bulk score imitation 不足以复制 teacher 的 fixed 行为

对应运行：
- `runs/frontend100_ensemble_distillation_v1_2026-04-11/`

结论：
- teacher `q99`: `alarm=0.2307, det=0.9202`
- single-seed gate `q99`: `alarm=0.1129, det=0.7731`
- distilled head `q99`: `alarm=0.1064, det=0.4510`
- teacher-student Pearson 相关性虽高，但 fixed 检出明显崩塌。

解释：
- v1 学到了 bulk score 结构，但没有学到 teacher 在 benign tail / attack tail 上的关键 operating-point 行为。

裁决：
- **Distillation v1 不能晋升主候选。**
- 若继续此线，只能进入 **tail-aware distillation v2**，不能再做普通回归式蒸馏。

---

## 十二、A 区增强阶段总原则

### A. 研究目标

后续实验不再服务“把当前论文补到差不多”，而是服务下面这件事：

- 把当前 stronger OOD + covariance-aware operating region 工作，升级为一篇兼具
  - **系统安全问题定义**
  - **更强实验完整性**
  - **对抗与部署视角**
  - **可被顶会审稿人正面评价的主创新闭环**
  的 A 区候选论文。

### B. 顶级论文参照方式

以后参考顶级论文，不是机械模仿模型名，而是看它们在四个维度上如何建立说服力：

1. **问题是否真是安全问题，而不是单纯刷指标**
2. **评估是否覆盖真实部署痛点**
3. **是否考虑 adaptive adversary**
4. **是否有清楚的系统代价与边界说明**

### C. 立项前强制三问

每个新实验立项前必须先回答：

1. 它补的是哪一个 A 区硬缺口？
2. 它支持的是哪一句最终论文主张？
3. 它失败后是否也能形成可写的负结果？

三问答不清，就先不做。

---

## 十三、Stop-Doing List（立即生效）

以下方向从现在起默认停止，不再作为主线优先级：

1. **停止继续开 MAE / prototype / compactness / covreg 新支线**
- 除非未来明确作为第二篇论文，否则不再投入主线算力。

2. **停止继续扫零散 scorer 小超参**
- 纯 scorer 微调已经不再是主矛盾。

3. **停止把“单模型翻盘审美”当成主目标**
- 单模型只在一个前提下继续：它能解决 deployability 闭环。

4. **停止为了“看起来像 A 区”而无边界扩 baseline**
- baseline 必须服务审稿风险，不是越多越好。

5. **停止把论文润色动作当成实验推进**
- 后续地图优先记录“增加硬实力”的实验，不记录纯文字修订。

---

## 十四、Tier 1：必须完成的实验包

这一层不做完，不讨论 A 区 ready。

### A. baseline 补强包

目标：
- 用少量但真正有代表性的现代 baseline，封住“只在打旧模型”的审稿攻击。

最小方案：
1. **保留 dA**
- 作为高部署性经典 reference baseline。

2. **保留 Deep SVDD**
- 作为现代 deep one-class reference baseline。

3. **补一个现代 tabular/feature transformer 类 baseline**
- 优先：FT-Transformer 路线或同类低工程风险强 baseline。
- 原因：当前输入是 100D network statistics，这类 baseline 最对口。

4. **如工程可控，再补一个现代 SSL/novelty baseline**
- 仅在它能同协议复现且不会拖死项目时进入。

成功标准：
- 形成一张“dA / Deep SVDD / modern tabular baseline / 当前主系统”的统一比较表。
- 所有模型统一使用同一 stronger OOD 协议与同一 fixed 口径。

### B. 第二数据集 / 第二环境自证包

目标：
- 证明当前主结论不是单一 100D 前端设置的偶然产物。

优先级：
1. **首选 BoT-IoT**
- 更贴近 IoT botnet 与网络流量异常检测，适合做最小迁移验证。

2. **备选 TON-IoT**
- 异构性更强，但工程成本也更高。

执行原则：
- 第一轮不复制所有主线实验。
- 只跑最小验证包：`dA + 当前 strongest candidate + 一个现代 baseline`。

成功标准：
- 趋势一致即可，不要求所有数值与主数据集完全对齐。
- 只要再次观察到 stronger benign OOD 下 fixed false alarm 的关键矛盾，就足以成立“跨环境复现”。

### C. 对抗鲁棒性评估包

目标：
- 把系统从“自然漂移评估”提升到“面对 adaptive adversary 的安全评估”。

最小方案：
1. **白盒 FGSM**
2. **白盒 PGD**
3. **黑盒受限扰动 / padding-style 规避**

统一要求：
- 扰动必须施加在当前可操作的 feature space 上。
- 扰动预算、特征合法性、扰动方向必须显式记录。
- 必须同时报告 detection 下降与 false alarm 变化。

成功标准：
- 至少形成一组扰动强度曲线，比较
  - dA
  - single-seed Transformer
  - covariance-aware ensemble
- 若 ensemble 明显更稳，这将是 A 区级别的重要加分项。

### D. deployability / cost 闭环包

目标：
- 回答“你的 strongest system 真实能不能落地”。

必须比较：
1. dA
2. single-seed Transformer
3. 3-seed covariance-aware ensemble
4. 若后续成功，再加 distilled single model

指标：
- 参数量
- CPU latency
- throughput
- memory footprint
- training cost

成功标准：
- 形成一张正式 deployment table。
- 若 ensemble 是最终 strongest candidate，也要能证明它的代价是可解释、可接受的。

---

## 十五、Tier 2：主创新收口线

当前只保留一条方法主线：

### Tail-aware Ensemble Distillation v2

为什么是它：
- 现在 strongest system 依赖 3-seed ensemble。
- deployability 的核心矛盾不是“teacher 不强”，而是“单模型学不会 teacher 的 fixed tail 行为”。
- distillation v1 已经说明普通 bulk regression 不够。

v2 的唯一正确方向：
1. **benign high-tail weighting**
2. **synthetic negative / attack high-score weighting**
3. **pairwise ranking or margin alignment**
4. **operating-point imitation，而不是只回归平均分数**

成功标准：
- 单模型 fixed 区间进入 dA 竞争区，或明显接近 teacher 的 q995 工作区间。
- 至少满足下面之一：
  - `alarm <= 0.14` 且 `det >= 0.80`
  - 或在 alarm 不恶化的前提下，显著缩小 single-seed 与 teacher 的 fixed gap

止损标准：
- 若两周内仍然只能学到 bulk correlation，而 fixed detection 继续明显塌陷，则停止这一线。
- 停止后把 v1/v2 共同写成“为什么 ensemble 不易被廉价压缩”的部署讨论与负结果资产。

---

## 十六、Tier 3：未来高风险高收益探索

这些方向有价值，但不进入当前第一优先级：

1. hyperspherical / unit-sphere representation
2. information bottleneck / input bottleneck
3. orthogonal subspace disentanglement
4. root-cause attribution / causal explanation
5. multimodal / raw packet / foundation-style modeling

执行原则：
- 只有在 Tier 1 基本完成、Tier 2 明确止损或完成后，才允许重启。

---

## 十七、后续执行顺序（2026-04-12 起生效）

建议固定按下面顺序推进：

1. **baseline 补强包**
2. **第二数据集最小自证包**
3. **对抗鲁棒性评估包**
4. **deployability / cost 闭环包**
5. **tail-aware distillation v2**

原因：
- 前四项决定论文是否具备 A 区合法性。
- distillation v2 决定论文是否具备更漂亮的部署闭环。
- 如果前四项不做完，单做一个更优雅模型也不足以扭转整体说服力。

---

## 十八、Tier 1 执行设计（2026-04-12 版）

### A. baseline 补强包：只补“现代且低工程风险”的强参考

#### 设计原则
- 不追逐大而全的 2025-2026 模型清单。
- 只补能够直接回应“你是不是只在打旧 baseline”的模型。
- 新 baseline 必须能沿用当前 `ID benign fit -> fixed / calibrated / constrained` 评估协议。

#### 具体配置
1. **FT-Transformer（主补强 baseline）**
- 定位：现代 tabular deep baseline。
- 理由：当前输入本质是 `100D network statistics`，FT-Transformer 与当前数据形态最匹配。
- 角色：证明在更现代的 tabular deep baseline 下，stronger OOD fixed 问题仍然真实存在。

2. **RTDL-ResNet / tabular ResNet（备选或配对 baseline）**
- 定位：与 FT-Transformer 同论文体系的强 MLP-like baseline。
- 理由：如果只补 FT-Transformer，审稿人仍可能认为“你在拿一个 Transformer 打另一个 Transformer”。
- 角色：提供一个非注意力、但同样现代且强的 tabular deep 参考。

3. **保留当前已有 baseline，不再扩大家族**
- `dA`
- `Deep SVDD`
- `IF / OCSVM / LOF`
- `LSTM-AE / GRU-AE`
- `RF upper-bound`

#### 执行顺序
1. 先补 `FT-Transformer`
2. 若复现稳定，再补 `RTDL-ResNet`
3. 若 FT 已足够回应 baseline 风险，则 ResNet 可降为可选

#### 产物要求
- `frontend100_modern_tabular_baselines_<date>/`
- 统一主表：`fixed / naive calibrated / det50 constrained`
- 统一成本表：参数量、训练时长、CPU 推理时延
- 统一 summary：只回答“现代 baseline 是否真正威胁当前主线”

#### 成功判据
- 即使现代 tabular baseline 比老浅层模型更强，也不能轻易同时做到：
  - `低 fixed alarm`
  - `高 high-purity detection`
- 只要它们没有压过当前主系统，就足以显著降低 baseline 风险。

### B. 第二数据集 / 第二环境自证包：先做最小可复现，不做大迁移

#### 设计原则
- 目标是“趋势复现”，不是“完全复制当前主线的所有细节”。
- 这一步是外部自证，不是重建另一篇论文。
- 必须明确区分：
  - **主数据集主结论**
  - **外部公开数据集趋势验证**

#### 数据集优先级
1. **首选 BoT-IoT 5% flow CSV**
- 理由：官方提供 5% 子集，工程成本相对可控。
- 适合先验证“公开 IoT 数据下也会出现 benign OOD / fixed operating-point tension”。

2. **备选 TON-IoT network subset**
- 理由：异构性更强，更接近“更广泛的 IoT/IIoT 现实”。
- 风险：工程面更大，正常流量划分与协议重建更复杂。

#### 第二数据集上的问题定义
- 不强求复刻 `original-frontend 100D`
- 明确改写为：
  - **在公开 IoT flow benchmark 上，构造 analogous ID-train / OOD-benign / attack split，检验 fixed-threshold 部署张力是否复现**

#### 最小实验对象
1. `dA`
2. `current strongest candidate`（按可迁移实现决定是 single-seed covariance gate 还是 ensemble 版本）
3. `FT-Transformer`（若已完成）

#### 成功判据
- 只要再次观察到：
  - benign OOD 会显著放大 fixed false alarm
  - 协方差感知 / operating-region 方案相比 naive deep baseline 更稳
- 就算完成“外部趋势自证”。

### C. 对抗鲁棒性评估包：分成神经白盒与统一黑盒两层

#### 设计原则
- 不做“图像领域式”的形式主义攻击演示。
- 必须围绕当前论文的真实判定规则：
  - fixed threshold
  - anomaly score crossing
  - deployment operating point

#### 攻击目标
- 把高纯攻击样本的异常分数拉低到 fixed threshold 以下，形成 evasion。

#### 评估分层
1. **R1：神经模型白盒一阶攻击**
- 对象：
  - single-seed Transformer latent gate
  - 3-seed Transformer ensemble
  - FT-Transformer / modern deep baseline（若已实现）
- 方法：
  - FGSM
  - PGD
- 输出：
  - `epsilon -> detection drop`
  - `epsilon -> evasion success rate`

2. **R2：统一黑盒约束攻击**
- 对象：
  - dA
  - single-seed Transformer
  - 3-seed ensemble
- 方法：
  - 坐标扰动 / sign-free search / padding-style constrained attack
- 输出：
  - 相同预算下，不同模型的规避难度比较

#### 特征合法性约束
- 非负特征保持非负
- 比率 / bounded 特征裁剪到观测范围
- 近似离散特征可选 round/clamp
- 扰动预算同时报告 `L_inf` 与平均相对改变量

#### 成功判据
- 只要能够展示：
  - naive/single deep model 更易被规避
  - covariance-aware ensemble 在相同预算下更稳
- 这一包就足够进入论文主文或强 supplement。

### D. deployability / cost 闭环包：不再只说“3x cost”

#### 设计原则
- 部署讨论必须和 strongest candidate 绑定，不做泛泛而谈。
- 成本不是弱点隐藏区，而是系统论文必须正面给出的事实。

#### 必测对象
1. `dA`
2. `single-seed Transformer latent gate`
3. `3-seed covariance-aware ensemble`
4. `distillation v2`（若后续成功）

#### 必测指标
- CPU `ms/sample`
- throughput
- checkpoint size
- torch / non-torch parameter count
- peak memory（若可稳定测）
- 训练总时长
- 校准/阈值额外开销

#### 成功判据
- 形成一张能直接进入论文的 deployment table
- 对 strongest candidate 给出一句能站住的系统表述：
  - “higher-cost but still deployable remedy”
  - 或 “single-model distilled variant approaching teacher”

### E. Tier 1 预计推进顺序

1. `FT-Transformer` 补强
2. 第二数据集最小 feasibility（BoT-IoT first）
3. 对抗协议实现与小规模白盒验证
4. 统一 deployment/cost 主表

说明：
- 若第 2 步 feasibility 显示 BoT-IoT 无法构造干净的 benign OOD split，则立即切 TON-IoT network subset，不在 BoT-IoT 上硬耗。
- 若第 1 步已经证明现代 baseline 风险显著下降，则不再继续扩大 baseline 家族。
- `frontend100_timescale_tokenizer_v1_smoke_2026-04-13`: Frontend100 TimescaleTokenizer-v1 single-seed minimal experiment with header-aware 5x20 regrouping; path: `runs/frontend100_timescale_tokenizer_v1_smoke_2026-04-13/`.
- `frontend100_timescale_tokenizer_v1_1_smoke_2026-04-13`: Frontend100 TimescaleTokenizer-v1.1 single-seed scoring refinement with header-aware 5x20 regrouping and short-scale aware aggregations; path: `runs/frontend100_timescale_tokenizer_v1_1_smoke_2026-04-13/`.
- `frontend100_timescale_tokenizer_v1_2_smoke_2026-04-13`: Frontend100 TimescaleTokenizer-v1.2 adds scale-contrast scorers on top of header-aware 5x20 regrouping; path: `runs/frontend100_timescale_tokenizer_v1_2_smoke_2026-04-13/`.
- `frontend100_timescale_tokenizer_v1_3_smoke_2026-04-13`: Frontend100 TimescaleTokenizer-v1.3 adds short-focused weighted reconstruction training plus timescale-contrast scoring; path: `runs/frontend100_timescale_tokenizer_v1_3_smoke_2026-04-13/`.
- `frontend100_structured_frontend_v1_smoke_2026-04-13`: Frontend100 StructuredFrontend-v1 with 20 semantic tokens (`4 families x 5 scales`), dual family/scale embeddings, and contrast scorers on top of the original 100D source; local smoke indicates semantic re-layout of the same 100D is **not enough** by itself: best structured Transformer fixed point is about `0.0121 / 0.2464`, still below the older 5-token line and below flat-AE+contrast control. This supports the next step being **upstream frontend redesign**, not just richer reshaping of the same compressed 100D. Path: `runs/frontend100_structured_frontend_v1_smoke_2026-04-13/`.

---

## 八、Frontend-F2 受控重构入口（2026-04-13 固化）

### 为什么现在切到 frontend

- `timescale_tokenizer` 与 `structured_frontend_v1` 已经把“同一份 original-frontend 100D 的后端重组空间”基本试穿。
- 结论一致：
  - scorer 可以改变 fixed trade-off，但不足以形成主线翻盘；
  - token 重组能产生局部机制信号，但仍明显打不过 dA，也未超过同源 flat 控制；
  - `4 families x 5 scales` 的 semantic token 化仍然不够，说明瓶颈不只在 token 排列，而在**上游表达生成时就被压扁了**。

### 当前判断

- 当前 100D 对 dA 很友好，但对 Transformer 并不原生。
- 若继续在同一份 100D 上做更复杂后端重排，收益大概率已经接近上限。
- 因此下一阶段最值得投入的是：**沿着 Kitsune 原始提取链上移一层，做 upstream frontend expression 的受控重构。**

### F2 的纪律

- 不引入外部黑盒 frontend 作为第一版主实现。
- 不破坏当前 `original-frontend 100D` 主线，必须保留 flat 100D 输出，确保历史实验与论文主干完全可复现。
- 第一轮只在 `kitsune_frontend_original_extract.py` 增加“结构化缓存输出”，不修改底层增量统计公式。

### F2 第一轮目标

- 在原始 frontend 抽取阶段同步输出：
  - 原有 `100D flat npy`
  - `family x scale x stat-slot` 的结构化缓存
  - 语义 schema 与 token 映射元数据
- 先做本地 smoke，确认结构化缓存数值可逆、与 flat 100D 严格一致，再决定是否进入新的训练线。

### 当前结论

- 如果要真正追求超越 dA 的新突破，最值得投入的是**重新构造前端表达**，而不是继续挤压同一份 100D 的重排空间。
- `Frontend-F2` 已成为下一阶段最合理的高价值探索入口。
- `kitsune_frontend_f2_smoke_2026-04-13`: Frontend-F2 extractor smoke. `kitsune_frontend_original_extract.py` now emits both flat 100D cache and structured semantic cache (`family_scale_tokens [N,4,5,7]`, `token_matrix [N,20,7]`, schema json). Local smoke on first 2000 packets passed with exact flat reconstruction (`max_abs_diff = 0.0`). Path: `runs/kitsune_frontend_f2_smoke_2026-04-13/`.
- `frontend_f2_crosscapture_source_smoke_2026-04-13`: Frontend-F2 source-prep smoke. Added `prepare_frontend_f2_crosscapture_sources.py` to slice structured caches into reusable ID/OOD source bundles while preserving flat csv/npy compatibility and shared schema. Smoke passed on same-source cache wiring. Path: `runs/frontend_f2_crosscapture_source_smoke_2026-04-13/`.
- `frontend100_modern_tabular_baselines_ft_smoke_2026-04-13`: FT-Transformer AE local smoke on original-frontend 100D stronger OOD. Single-seed (`101`) result confirms the modern baseline script works, but fixed performance remains weak (`q99 ~ 0.4935 / 0.8064`, `q995 ~ 0.2667 / 0.6970`), so this line does not threaten the current strongest paper candidate. Path: `runs/frontend100_modern_tabular_baselines_ft_smoke_2026-04-13/`.
- `frontend_f2_extract_id_7_6_2026-04-13`: Real benign ID Frontend-F2 extraction on `7-6` using the existing TSV from crosscapture stage1. Structured cache generated successfully with exact flat reconstruction. Path: `runs/frontend_f2_extract_id_7_6_2026-04-13/`.
- `frontend_f2_extract_ood_4_1_2026-04-13`: Real benign OOD Frontend-F2 extraction on `4-1` using the existing TSV from crosscapture stage1. Structured cache generated successfully with exact flat reconstruction. Path: `runs/frontend_f2_extract_ood_4_1_2026-04-13/`.
- `frontend_f2_extract_attack_34_1_2026-04-13`: Real attack Frontend-F2 extraction on `34-1` using the existing joint-eval TSV. Structured cache generated successfully with exact flat reconstruction, enabling aligned attack-side evaluation under the new frontend. Path: `runs/frontend_f2_extract_attack_34_1_2026-04-13/`.
- `frontend_f2_crosscapture_stage1_2026-04-13`: Real Frontend-F2 cross-capture source bundle built from `7-6` ID and `4-1` OOD structured caches; outputs both structured `.npz` sources and flat compatibility csv/npy. Path: `runs/frontend_f2_crosscapture_stage1_2026-04-13/`.
- `frontend_f2_attack_source_2026-04-13`: Real Frontend-F2 attack source bundle aligned to stage2 manifest (`use_first_n=10000`), producing reusable structured attack source plus flat compatibility outputs. Path: `runs/frontend_f2_attack_source_2026-04-13/`.
- `frontend_f2_structured_tokenizer_v1_smoke_2026-04-13`: First real-data smoke of `frontend_f2_structured_tokenizer_v1.py` using `7-6` ID, `4-1` OOD, and `34-1` attack structured caches, with token family/scale embeddings and short-vs-long contrast scoring. Local smoke runs successfully, but fixed detection remains low (best structured transformer about `0.0120 / 0.2043`), so Frontend-F2 is now a real exploratory branch but not yet a mainline challenger. Path: `runs/frontend_f2_structured_tokenizer_v1_smoke_2026-04-13/`.

- `frontend_f2_structured_tokenizer_v1_smoke_2026-04-13`: Frontend-F2 structured tokenizer v1 on real structured caches (`7-6` ID, `4-1` OOD, `34-1` attack), using token family/scale embeddings and short-vs-long contrast scoring; path: `runs/frontend_f2_structured_tokenizer_v1_smoke_2026-04-13/`.

- `frontend_f2_contrast_tokenizer_v1_smoke_2026-04-14`: Frontend-F2 contrast-token v1 derives short-vs-long anomaly-increment tokens directly from structured caches and evaluates transformer/token-MLP backends on real `7-6/4-1/34-1` data; path: `runs/frontend_f2_contrast_tokenizer_v1_smoke_2026-04-14/`.
