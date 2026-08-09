# Briefing for GPT: CKBW seed-27 result and next-iteration discussion (2026-08-07)

> Purpose: Codex is out of quota until 2026-08-10. Kimi (implementing agent) and GPT discuss the next iteration now, so no time is lost. Everything is recorded here for Codex to rejoin instantly. This document plus `ckbw_seed27_result_analysis_20260807.md` are the complete state.

## 0. Repo pointers (branch `codex/exp-mainline`, latest commits)

- `runs/mainline_docs/ckbw_tail_margin_dual_control_preregistered_20260803.md` — frozen protocol (SHA `80c44c8d…`)
- `runs/mainline_docs/ckbw_seed27_result_analysis_20260807.md` — full NO_GO analysis (numbers below come from here)
- `runs/mainline_docs/hpc_failure_ledger_and_launch_gate_20260725.md` §20-§22 — engineering history
- `repo/ood/issue27ckbw_tail_margin_dual_control_v1.py` — implementation (commit `b2ae810` + HPC scripts `6d359b8`/`782fdfc`, analysis `84639dd`)
- Pullback with all raw CSVs/JSONs is local at the user's machine; key figures are reproduced in the analysis doc.

## 1. What just happened (seed 27, frozen preregistration)

CKBW = one shared 51-D causal process scorer (TabM, tail-pair margin loss) + dual thresholds around FrozenCKBQ: τ_normal revokes baseline alarms on process-benign-looking records, τ_attack rescues. 8 arms, contract checks 16/16 PASS, job amd 157624, 22 min wall.

**Result: NO_GO.** Benign-OOD macro hard rate 35.27% → **0.15%** (hydraulic 0.457→0, predictive-maintenance 0.576→0.006, stream-consumer 0.297→0, ip-camera 0.081→0). Attack overall (future_query, unseen sources) 86.8% (C1) / 74.2% (FrozenCKBQ) → **63.2%** = −13.6pp vs C1 (gate ≥−0.5pp). Worst family Merlin C&C −95.4pp (0.998→0.045). support_val 69/69. τ_attack=1.0, rescue=0 on every dual arm.

## 2. Established facts (not hypotheses)

1. Suppression losses concentrate exactly in low-volume stealthy families (C&C, Telnet brute force, ingress, reporting, scans); floods survive.
2. Tail-margin ≈ plain CE per family (M7≈M5) — the margin loss found nothing to learn; record-level causal features carry no signal separating stealthy attacks from benign OOD.
3. The OR/rescue direction contributes zero detections at legal thresholds (M6 byte-identical to FrozenCKBQ everywhere).
4. C1 (attack-side view) catches Merlin C&C at 0.998 — the evidence exists in another view; suppression currently ignores it.
5. A4-ExtraTrees-Dual preserves Merlin C&C far better than TabM-Dual (0.699 vs 0.045) — model class affects over-confidence of "benign" scores, but still −30pp there.

## 3. Options on the table

- **A. Evidence-gated suppression**: revoke a baseline alarm only when ALL attack views agree benign (tail high AND C1 low AND CKBQ not firing). Uniform mechanism, no family patch. Expected: Merlin C&C recovers toward ~1.0; OOD suppression should mostly survive (benign OOD is low in all views).
- **B. Episode/temporal aggregation**: stealthy attacks are temporal patterns (beacons, repetition), not records. Bigger redesign; arguably the real open-world answer.
- **C. Attack-view veto**: dual control may only suppress records no attack view claims. A framed as an architecture rule.
- Rejected: per-family thresholds/experts (patch-style, violates the no-patch principle); more margin tuning on the same features (proven uninformative).

## 4. Questions for GPT

1. Do you agree the M7≈M5 evidence closes the "better loss on record-level features" direction, or is there a loss/objective variant still worth one shot?
2. Option A: exact legal formulation under the data-boundary rules (which scores may be combined at decision time without violating the frozen fit/select discipline; how to select the conjunction thresholds legally)?
3. Is A+C one mechanism or two? What is the cleanest preregistrable form?
4. Option B scoping: what is the minimal episode-level feature/aggregation that could catch beacon-like C&C without reintroducing per-family engineering?
5. Success-gate design for the next round: how do we avoid "OOD 0.15% bought with attack collapse" reading as progress — joint primary metric proposal?
6. Anything in the numbers above that looks like an artifact we should audit before designing on top of it?

## 5. Ground rules for this discussion

- No code, no HPC, no threshold changes until a new preregistration is frozen with Codex (back ~08-10) or explicitly delegated by the user.
- No per-family patches; mechanisms must be uniform.
- All outcomes of this discussion are appended to this file (or a follow-up dated doc) and committed, so Codex rejoins with full context.

---

# Discussion round 1 — Kimi responds to GPT (2026-08-07)

## P0 audit verdict (raw CSV, `ckbw_attack_preservation_summary.csv` + gate code line 1635)

**Both numbers are raw and correct; the analysis doc mixed scopes.** The preregistered gate metric `attack_overall` is the all-role pool (244,050 rows = support_val 69 + same_file 2,486 + sealed 110,104 + future 131,391): M7 = 0.7771 vs C1 = 0.9130 → **−13.59pp (gate number, raw)**. The future_query-only lens: M7 = 0.6319 vs C1 = 0.8683 → **−23.64pp (also raw)**. The doc quoted future-only recalls next to the pool-scope gate delta — transcription error, now fixed in `ckbw_seed27_result_analysis_20260807.md` §1 with both scopes shown. No metric/denominator bug. Side effect: the future-pool reality is *worse* than the doc implied, which strengthens GPT's §4 mathematical point.

## Position on GPT's proposals

1. **Loss direction formally closed.** Agreed, including the carve-out: model-confidence behavior (ExtraTrees vs TabM on Merlin, 0.699 vs 0.045) survives as an ablation, not a main line. No focal/triplet/SupCon/margin-respin experiments.
2. **A+C merge accepted, with GPT's rescue-veto amendment as mandatory, not optional.** `H = V_attack ∨ (H0 ∧ ¬S_normal)`. The ceiling argument is decisive: protecting only h0=1 caps us at CKBQ's 74.2% (future) while the gate needs ≥ C1−0.5pp ≈ 86.3%. V_attack must therefore *restore* records CKBQ itself suppressed. This also retroactively explains why the current CKBW structure was doomed on the attack gate even before suppression tuning.
3. **The decisive feasibility risk, quantified from this run's L2 table:** C1-as-veto at its legal support cut fires on ~100% of held benign OOD (C1 benign-OOD hard rates: ip-camera 1.000, predictive 1.000, stream 1.000, hydraulic 0.724). So V_attack cannot be C1-hard at the support operating point — that veto would disable suppression entirely and hand back the 93% OOD regime. The entire viability of A+C hinges on an empirical question: **does a higher cut on the C1 continuous score separate stealth-attack records (Merlin C&C, brute force, ingress) from held benign OOD?** If yes → A+C is viable and thresholds are legally selectable. If no → second clean negative ("record-level multi-view evidence insufficient for a safe veto") and we go to episode-level B, exactly as GPT's roadmap says.
4. **P1 (τa degenerate) accepted** and wording corrected in the analysis doc. **P1 (27 rows) accepted**: regime mismatch between select pool (0.39% baseline-hard) and held OOD (35.27% hard) is a genuine estimation-risk factor; the 27-row provenance/distribution audit is folded into the diagnostic below.
5. **Success gate: adopt GPT's lexicographic report format.** Note the current implementation already behaves this way (decision=NO_GO despite ood_macro_pass=true), so this is a reporting-formalization, not a behavior change: "Attack-safe: PASS/FAIL; OOD gain conditional on PASS". No weighted sums, ever.
6. **B scoping (causal episode summary: repetition + inter-arrival regularity + C1-score persistence, anonymous endpoint keys, causal past-only windows) is the agreed second stage** — and it should be designed as the veto side, keeping the record-level normal scorer as the suppression side. Noted with approval: simple frequency/timing aggregation first, no TGN/Transformer v2.

## Immediate next step (Kimi, no HPC, no retraining, read-only)

Before any new preregistration, run a **local read-only veto-feasibility diagnostic** on already pulled-back artifacts (154917 frozen predictions with `c1_score` × CKBW record predictions, exact UID join):

1. Distributions GPT asked for: q and c1_score percentiles (p01/p05/p25/median) for support_val attacks, future stealth families, benign select, held benign OOD; P(q ≤ τn) per group.
2. C1-cut frontier: for a grid of c1_score cuts — stealth-family recall vs held-OOD fire rate. Does any cut give e.g. ≥0.95 stealth recall at ≤0.10 OOD fire?
3. The 27-row audit: source/aux/ToN provenance, q and c1_score distributions, CKBQ reason.
4. Verdict: A+C feasible / infeasible, with the frontier plot as evidence — this gates the next preregistration.

Diagnostic output will be committed as a dated doc; then GPT+Kimi draft the Attack-Protected Suppression preregistration for Codex review on/after 08-10.

---

# Discussion round 2 — GPT constraints (2026-08-07, received; diagnostic NOT started, awaiting user go)

GPT accepts the P0 resolution and adds six constraints before any preregistration (full text relayed by user, archived in conversation):

1. **Two frontiers, not one.** Oracle frontier (future stealth vs 4 viewed OOD; raw c1_score + c1_margin + q; full Pareto) answers only "does the information exist" and must NOT feed threshold selection. Legal frontier (69 support_val vs aux 3000 + ToN 4000, aux/ToN reported separately) answers "can a legal rule find the useful region". Three-state verdict: (1) oracle inseparable → A+C dead, go B; (2) oracle separable but legal frontier can't locate it → information exists but not legally calibratable, no HPC; (3) both support → draft A+C prereg.
2. **Prefer C1 excess margin over raw score**: m_C1 = c1_score − frozen_c1_threshold; veto form V_attack = [m_C1 ≥ δ], one global δ. Cross-protocol-safe; draw both raw and margin frontiers.
3. **If A+C proceeds: freeze CKBW M7 normal scorer AND τ_normal=0.971323, no retrain, no normal-threshold reselection; add exactly one unified veto margin δ.** Single-variable experiment isolating controller architecture; also avoids re-estimating the risky 27-row τ_normal.
4. **Veto-selection degenerate trap**: a "final support=69/69 then minimize benign veto" rule collapses to δ→∞ (veto=0), repeating τ_attack=1.0. Preregister a non-degenerate lexicographic rule on the legal frontier (veto coverage vs benign-alert budget; exact order frozen after frontier data arrives). Family labels may only prevent big-family drowning, never produce family thresholds.
5. **27-row audit additions**: c1_margin + CKBQ branch/reason (C1-shield / static / temporal / temporal-reliable); specifically count how many CKBW-suppressed attacks were previously CKBQ C1-shield-protected (feeds the paper narrative: CKBQ implicitly knew the veto principle; CKBW removed it; next round generalizes it).
6. **B boundary**: not another event-window classifier (CKBQ already did causal temporal MiniRocket); B = interaction/episode-level persistence (anonymous endpoint/service episodes: repetition count, inter-arrival regularity, duration, C1 high-score persistence).

Diagnostic engineering requirements: exact (held_value, uid) join; no C1 retrain; assert c1_score ≥ frozen_c1_threshold matches frozen c1_hard row-by-row; if raw scores aren't cross-protocol comparable, prefer margin.

Kimi position (pending user authorization to execute): all six accepted without amendment; they are consistent with the data-boundary discipline and tighten the diagnostic design. Awaiting user's explicit go after GPT walkthrough.

---

# Discussion round 3 — GPT framework proposal + Kimi assessment (2026-08-07; still parked awaiting user go)

## GPT proposal (full text relayed by user, archived in conversation)

Main idea: stop building single-score detectors; build an **Asymmetric Evidence Arbitration** system. Attack evidence and normal evidence are different in kind, not two signs of one probability. Normal evidence may grant suppression *permission*; it may never override explicit attack evidence. Conflict resolution: attack priority. Decision table: attack-strong → hard (regardless of normal); attack-weak + normal-strong → suppress; both weak → keep baseline; both strong → hard.

- Direction 1 🥇: **2D evidence-space diagnosis** — scatter (C1 excess margin × 51D process score) colored by {support attack, future stealth, benign select, held OOD}; *conflict itself* (C1 says attack while 51D says benign) may be the signal. If stealth and OOD show structural separation in 2D, do a simple uniform 2D evidence region instead of episode B.
- Direction 2: **Fail-safe suppression** — revoking an attack alarm is a high-risk action that must be *earned* (strong normal evidence + no strong attack evidence + evidence present + no unresolved conflict). Secondary metric proposal: **Safe Suppression Rate** = revoked benign-OOD alarms / FrozenCKBQ benign-OOD alarms, reported only under attack-safe PASS. Hard GO gates unchanged.
- Direction 3: if B, narrow to **attack persistence evidence** (4 minimal past-only quantities per anonymous entity: C1 exceedance count, top-k C1 margin mean, recurrence count, inter-arrival regularity) — answers "is attack evidence persistent", not "is this episode attack".
- Bold framing: **multi-scale veto** — record-level C1 + episode persistence → attack veto side; 51D normality → suppression side. Paper story: "when may normality evidence revoke a security alarm in open-world IDS", not "yet another detector".
- Discipline warning: future stealth families are becoming an **invisible training set** through repeated inspection. Formalize three tiers: LEGAL SELECT (parameter selection), VIEWED DIAGNOSTIC (mechanism hypotheses only), FINAL (never look: cooler-motor, seeds 37/47). Every design doc must state: which qualitative hypotheses came from viewed diagnostics, and that no numeric cut was derived from them.
- Priority: 2D arbitration 🥇 > C1-margin veto 🥈 > episode veto 🥉 > calibration ablation; roadmap CKBX (record-level arbitration) → CKBY (episode veto) with clean negative chains.

## Kimi assessment (recorded same day)

1. **Accept the arbitration framing** — it is the correct generalization of A+C and a stronger paper contribution than a detector tweak. The A+C/C1-margin veto becomes its minimal first experiment, not a competitor.
2. **2D scatter folds into the already-planned diagnostic for free** (same pulled-back tables, one more plot). Accept; it also subsumes GPT's "conflict-as-signal" question visually before any rule is designed.
3. **No real conflict between GPT's 2D region and the C1-margin veto**: the 2D region is the veto defined on (margin × q) instead of margin alone; same mechanism family, and the *legal selectability* question applies to both. One caution to carry into the diagnostic: with only 69 legal support attacks across 10 families, a 2D boundary is more data-hungry than a 1D δ — the legal-frontier analysis must explicitly test whether any 2D region is non-degenerately selectable, or whether only the 1D margin cut survives legal discipline.
4. **Three-tier data concept adopted** (LEGAL SELECT / VIEWED DIAGNOSTIC / FINAL) + the mandatory per-design statement. Additional honest note: the 4 viewed OOD families and Merlin/Telnet/Ingress are already "viewed"; their evidentiary weight is now hypothesis-generation, and the persuasive evaluation increasingly rests on cooler-motor + seeds 37/47 + any second dataset — plan the final evaluation budget accordingly.
5. SSR accepted as a secondary reported metric under attack-safe PASS; gates stay lexicographic, no weighted sum.

Status: diagnostic still parked. On user's go, run the two-layer frontier + 2D scatter + 27-row audit (with c1_margin and CKBQ reason fields) exactly as scoped in rounds 1-3, then GPT+Kimi draft the CKBX preregistration skeleton for Codex review (back ~08-10).

---

# Discussion round 4 — GPT launch design (2026-08-07; logged, still awaiting USER's explicit go)

GPT accepts Kimi's 69-row statistical-budget caution and finalizes the diagnostic design:

1. **Complexity ladder, fixed in advance** (prevents viewed-diagnostic creep): Level 0 = C1-hard veto (frozen reference, known-bad); Level 1 = 1D C1 excess-margin veto `V=[m_C1 ≥ δ]` (one degree of freedom, first priority); Level 2 = simplest monotone 2D region only (`m_C1 ≥ δA` AND/OR one monotone 51D condition). Explicitly forbidden: logistic/SVM/tree/learned 2D classifiers, hand-drawn polygons. CKBX primary complexity is decided by the Legal frontier, not by how pretty the 2D scatter looks.
2. **Stability gate**: leave-one-support-family-out on the legal δ frontier (family used only to stress-test the *shared* δ, never to make per-family cuts). Fragile calibration (δ jumping around per excluded family) blocks HPC even if Oracle is beautiful.
3. **Four-state verdict** (supersedes three-state): (1) oracle inseparable → episode B; (2) oracle separable but legal not selectable → no HPC, calibration redesign/episode; (3) legal selectable but unstable → no HPC; (4) oracle+legal+stable → only state that authorizes CKBX preregistration.
4. **Evaluation hierarchy formalized**: viewed diagnostics (hypothesis generation) → seed 27 (preregistered dev) → seeds 37/47 (stability) → cooler-motor (final held) → second data source (external generalization). Merlin/Telnet/Ingress + the 4 viewed OOD families are now formally VIEWED DIAGNOSTIC tier.
5. GPT votes "start" — the read-only feasibility diagnostic only (no CKBX code, no thresholds, no training, no HPC, no FINAL data).

Kimi position: all accepted without amendment; the ladder and stability gate directly answer my 69-row budget caution. Execution is staged and waits for the USER's explicit "开始" (GPT's suggested authorization sentence is logged in the conversation; authorization must come from the user, not from GPT).

---

## Round 5 (2026-08-07, Kimi 执行): veto 可行性诊断完成 — VERDICT = STATE_1，A+C 终止，转 episode B

用户 11:47 明确授权"开始"后，Kimi 完成只读诊断（无训练/无阈值变更/无 FINAL 数据）。
报告与全部产物：`runs/mainline_docs/ckbx_veto_feasibility_20260807/`（report.md + 5 图 + 7 表 + verdict.json + 复现脚本）。

**方法核验**：M7 判定公式逐行反推验证通过（M7 = frozen_ckbq_hard AND tail>=0.971323，suppress 方向为 tail **低** 压掉）；
两表按 (held_value, uid) 精确 join（both=277,326；ton: 20,000 行无 C1 覆盖，如实标注）；
c1_hard 与 (c1_score >= c1_candidate_threshold) 277,326 行零不一致；C1 阈值为全局单一值 0.998085199899140。

**裁决：STATE_1_ORACLE_INSEPARABLE_GO_EPISODE_B**——oracle 层即不可分，A+C 记录级 veto 路线终止，不烧超算，CKBX 主干转入 episode 级仲裁（方案 B）。

两条独立致死原因（seed-27 实测）：
1. 收益侧：veto 召回天花板（= c1_hard 比例）7/8 族 < 0.90——Merlin C&C 0.998（唯一达标）、Reporting 0.742、TCP Scan 0.734、Telnet 0.667、Ingress 0.631、Mirai C&C 0.054、CoAP/UDP 0.000。任何 δ 都无法让最差族召回达标。
2. 代价侧：合法良性 aux_select 3,000 行 c1_score **全部为 1.0**（全局最大值，单源内零方差），pm-OOD 9,000 行同；任何能救攻击的 δ（≤0.0015）先把合法良性池 100% 打成误报。Legal 层唯一满足良性预算的 δ_b=0.001915 全域零救援（退化稳定，LOFO 不变）。
3. Level 2 单调二维区域（veto 仅限被 M7 压掉的行）同样不存在有用区间。

附带审计：27 行基线硬告警良性全部为 M1-static 分支判因、c1_score=1.0，非杂散；support_val 69 确认为攻击验证行（10 族混合，三臂召回 100%），δ 约束只能来自良性池（GPT 防退化警告成立）；16,212 条被 M7 压掉的攻击 100% c1_hard。

对 episode B 的三条定性假设（仅定性，数值阈值须由 LEGAL 池重选）：
1. C1 的源级饱和形态本身是 episode 级信号（良性 OOD 源整源 1.0 饱和；攻击源高但不饱和）——episode 特征应吃"源/窗口内分数分布形态"而非单条分数；
2. 窗口内 c1_hard 密度对找回 Merlin 类压制攻击可能有用，按 episode 评估；
3. Mirai C&C / CoAP / UDP Scan 对 C1 通路不可见，episode 仲裁需 51D/上下文通路单独承载这三族，预注册中明确口径（不打补丁）。

下一步：GPT + Kimi 起草 CKBX（episode 级仲裁）预注册，等 Codex 8 月 10 日回归评审；本诊断给出的禁令——不得再从记录级 C1 分数设计救援机制。

---

## Round 6 (2026-08-07, Kimi 执行): Record-level Capacity Audit 完成 — 裁决 R2（有界版）

GPT 提议、用户转发授权：在 CKBX episode 预注册前先钉死"是不是我们模型太弱"的替代解释。
审计文档：`runs/mainline_docs/record_level_capacity_audit_20260807.md`，检索证据 CSV 在同名目录。
全程无训练、无 HPC、无 FINAL、无 VIEWED 选阈值。

**文献侧（协议逐条核对，已核实 venue：Whisper=CCS 2021、HyperVision=NDSS 2023、pVoxel=CCS 2023、NetVigil=NSDI 2024、Kitsune=NDSS 2018）**：
无一高水平 benign-only 系统在"留一 device/source 良性环境 + 冻结合法阈值 + 同时报 unseen 攻击召回"协议下被评估；
Kitsune/Whisper/HyperVision 良性 train/test 全部同源（同 capture / 同 MAWI 骨干 / 同集群）。
且顶级 benign-only 系统无一停留在单记录粒度（频域流序列 / 跨流交互图 / 告警点云）——领域自己早已走向跨记录上下文。

**内部侧**：六个模型类别（保形 C1/A0、静态护盾 M1、时序 M2、共识 M3、raw AfterImage115、少样本 TabM/CKBW）全部撞上同一堵墙
（攻击高→OOD 爆炸；OOD 低→隐蔽攻击崩），但未覆盖深度一类表示学习。

**裁决：R2（有界版）**——预注册且仅预注册一个强 benign-only 记录级 baseline：Deep One-Class（DeepSVDD 类）on 冻结 51D 特征，
LEGAL benign fit 训练，CKBW 相同分母，GO/NO_GO 草案门槛已写（OOD macro ≤ 30.27% 且 future 召回损失 ≤ 2pp vs C1，待评审）。
明确排除新前端（Whisper 式频域 = 新管线工程，排除）。若该 baseline 同样撞墙 → 假设 A 钉死、R1 自动成立、episode 必要性闭环；
若明显解决 → 暂停 episode 回头研究表示。四个评审点已列给 GPT/Codex（模型二选一、门槛宽严、训练池是否仅 id_calib=809、是否加报 episode 口径）。
三方评审通过前不启动新超算任务。

---

## Round 7 (2026-08-07, Kimi 执行): GPT 评审并入 + CKBY DROCC 预注册草案（DRAFT）完成

GPT 对 68bdeb2 的 8 条评审全部接受并入。Kimi 独立复核意见：

- **核验通过**：GPT 所称 LEGAL benign fit = 14,013（id_calib 809 + ood_val 2,604 + aux fit 6,600 + ToN normal_1 4,000）
  与 benign select = 7,000（aux 3,000 + ToN normal_2 4,000）已对照 CKBW FROZEN 原文第 3.1/3.2 节逐条一致；非转述采信。
- **接受 DROCC 替代 DeepSVDD**：collapse 风险论证成立；DROCC 合成负样本不接触真实攻击，保持 zero-positive。
- **接受 pure zero-positive 阈值纪律**：support_val 69 不参与训练/阈值/checkpoint 选择，仅作报告；
  若不遵守则须降级表述（草案选择不降级）。
- **Kimi 补充的两条设计**（GPT 未覆盖，已写入草案 §2.2/§4）：(a) checkpoint/早停规则必须 benign-only——
  从 14,013 fit 按 source 分层切 10% benign 验证集，仅凭 benign 验证损失选模型；(b) 工作点采用
  OP-1（99 分位，1% 预算）与 OP-0.1（99.9 分位）双冻结点，report 池 ROC 仅诊断、不得反馈选择。
- 文献表述已按论文纪律收紧（"代表性系统中未发现完全匹配协议"/"现代方法越来越多利用跨记录上下文"）。

产物：`runs/mainline_docs/ckby_drocc_record_capacity_baseline_prereg_draft_20260807.md`（DRAFT，含双重门：
Gate A CAPACITY_SIGNAL = OOD macro ≤ 30.27% 且 future 召回 ≥ 84.83%；Gate B 沿用冻结严格契约；
四个待评审开口项列于 §9）。冻结前不训练、不上 HPC；等 GPT 确认措辞 + Codex 8 月 10 日终审。

---

## Round 8 (2026-08-07, Kimi 执行): GPT round-8 评审并入 + Claude handoff 登记为历史假设库

GPT 复核 7473a0e 整体接受，5 条收紧已全部落入 CKBY 草案（仍 DRAFT）：
1. §8 因果表述收紧——Gate A FAIL 封死的是"冻结 51D 表示上的模型容量解释"，不声称所有记录级表示不可能、
   不声称 episode 数学上必要；FAIL 后先开 Episode Design Review 再起草 episode 预注册。
2. benign 验证集改为 per-source 时序尾部 10%（前 90% train），无法定义时序的源退回预注册 deterministic hash split，
   禁止临时随机（Codex 终审重点）。
3. OP-1 定 PRIMARY、OP-0.1 定预声明副压力点，禁止择优晋升；双点用于观察 capacity curve（渐降 vs 崩塌）。
4. Gate A（30.27% / C1−2pp）冻结为 capacity signal，不再磨数字；Gate B 保持 mainline 严格契约。
5. 14,013/7,000 核验无异议。

**Claude handoff（claude_handoff_next_steps_20260727.md，Kimi 已逐条核对原文）登记为 historical hypothesis registry
（不是执行计划，现在不实现、不上 HPC）**：

- 已正式淘汰、不得复活：§3.1 记录级双信号/二维 veto（被 a23c5fa oracle-inseparable 实证判死）；
  §3.2 按机制分阈值（scan/bruteforce 双头）与 §3.3 flood 机制库——机制粒度的分阈值/机制库有长成
  family patchwork 的风险，不进主线（GPT 裁定）。
- 保留为 episode 假设（统一机制、禁止 family 专家）：
  (a) generic interaction persistence——recurrence、inter-arrival median/MAD/CV、C1-high persistence、
      endpoint/service persistence、destination/service rarity（Claude §3.4 beaconing 思想的通用化：
      "beaconing 机制思想保留，Merlin 专家不做"）；
  (b) 反例约束——IoT 良性遥测本身高度周期，periodicity alone 禁止作为 attack shortcut，
      必须与 persistence/rarity/score trajectory 组合（Claude §3.4 可行性门原意）；
  (c) episode 定义方向——interaction-conditioned、source-local、anonymous、past-only 的上下文单元，
      不是重复 CKBQ 已否决的 32-event MiniRocket 滑窗（Claude §3.5 的升级版）。
- 储备路线（不进入 CKBY，DROCC FAIL 也不自动启动）：ET-BERT / YaTC / netFound 预训练流量表征
  （Claude §3.6/§4），仅在 episode 主线仍失败或出现表示疑问时经新预注册启用。

**后续路由（三方一致）**：CKBY DROCC（待 Codex 8/10 终审转 FROZEN）→ PASS 则暂停 episode 研究其机制 /
FAIL 则停止换模型 → Episode Design Review（统一三方 episode 假设，明确相对 CKBQ 旧 temporal 分支的新增信息）
→ episode 预注册。FINAL cooler-motor、seed 37/47 全程封存。

---

## Round 9 (2026-08-07, Kimi 执行): CKBY 转 FROZEN（用户治理调整：Codex 终审非阻塞）

**治理变更**：用户 15:37 明确指令"codex 不在，就记录好我们干了啥就行，不用等他拍板，实验效率会被拉低"。
CKBY 冻结授权链变为：用户授权 + GPT round-8 评审已并入 + Kimi 执行。Codex 回归后按 commit 记录审查，
不构成解冻条件；若 Codex 有异议，走新预注册而非修改本冻结文件。

**FROZEN 产物**：

- `ckby_drocc_record_capacity_baseline_preregistered_20260807.md`
- SHA-256：`bbb113eaef19325099c997e8af8c8ff1a623ea60a01933fff7dcc3271a8a69f0`（侧车同名 `.sha256`）
- 与草案 736c7a2 的差异仅限：填入 §2.1 冻结超参、写明哈希兜底规则、新增 §9 特征快照合同、
  §10 冻结确认、状态转 FROZEN。数据角色/双重门/工作点/路由零变化。

**冻结时填入的关键技术决策**（来源：microsoft/EdgeML 官方 master 分支
`pytorch/edgeml_pytorch/trainer/drocc_trainer.py` 2026-08-07 原文逐行核对）：

- 实现=自包含脚本逐行复刻官方 DROCCTrainer（不装 edgeml 依赖，避免依赖漂移）。
- 算法精确细节：对抗点初始化 x_adv = x + N(0,I)；50 步归一化梯度上升（step 0.001）最大化
  "判为负类"的 BCE；每 10 步（含第 50 步）把位移投影到环带 [r, γr]；损失 = CE(normal→1) + λ·CE(adv→0)。
- 架构 MLP 51→128→1（logit 即异常分）；Adam lr=1e-3 官方四段式调度；λ=1，γ=2，r=7（√51 规则），
  only_ce=50 / 总 200 epoch / batch 256；纯 CPU + seed 27 固定全部随机源。
- checkpoint=benign 验证 CE 损失最低 epoch（并列取早）；哈希兜底=md5(uid) 末位为 'f' 入验证集
  （单字符方案，禁止凑比例），逐 source 声明入 run_spec。

**下一步（已获冻结授权范围）**：HPC 导出 51D 特征快照（只读复用 ckbu 装配，行数断言=297,326，
uid 逐一 join 角色，失败即中止）→ 拉回本地 → 训练 → 一次性评估 → 结果文档。
导出前需先读 ckbu 装配接口（issue27ckbu_unified_process_rescue_formal_v1.py）确认
feature_map/fit_preprocessor 签名——只读，不改。

---

## Round 10 (2026-08-07, Kimi 执行): 勘误 1 + 特征快照导出程序与上传包完成（待用户提交 HPC）

**勘误 1（执行前）**：`ckby_preregistered_erratum_1_feature_snapshot_contract_20260807.md`。
核验发现 FROZEN §9 "快照行数=297,326" 假设不成立——CKBW 记录表只含 select/report 两阶段
（35,345 + 261,981，跨 5 个 held_value 切片），**不含 fit 行**，且 uid 跨切片重复。
修正后合同：快照 = GLOBAL fit 18,398（14,013 benign + 4,385 attack，attack 仅供断言）
∪ 记录表全部唯一 uid，按 uid 去重；硬性断言=记录表覆盖率 100%、fit/select 基数精确、
矩阵 (N,51) 无 NaN/Inf。科学面零变化。附带澄清：raw51 masked 1,353 行有 51D 特征
（CKBW job 157624 全局 store.add 成功为证），CKBY 将对其直接打分并单列 masked 口径对照。

**导出程序**（commit 9439ba1）：

- `repo/ood/issue27ckby_drocc_feature_dump_v1.py`——逐行复用 CKBW `run_formal` 装配半段
  （prepare_inputs→mask→restrict→protocols→assemble_protocol×5→assert_global_pool_contract→
  assert_protocol_identity→UnifiedFeatureStore.add），在任何预处理/训练/打分**之前**停止，
  导出 quantile 变换**前**的原始 51D 因果特征 + 行级元数据（uid/role/m1_phase/source/label/
  attack_family/recorded_index/raw51_observable/global_pool）。
- `scripts/issue27ckby_drocc_feature_dump_formal.slurm`——amd 分区、4h 上限、禁重排、
  60s 心跳（phase + 日志行数）、job_failure.txt 失败落盘、自动打 pullback 包。
- `scripts/issue27ckby_install_and_submit.sh`——镜像 CKBW installer：不可变资产哈希全钉
  （154917 五资产 + 157624 记录表 f53f1e3d… + raw51 掩码 b16017d2…）、SHA256SUMS 校验、
  sbatch --test-only 干跑、job id 幂等记录、900s runtime gate（到达 snapshot_dump 阶段即判
  提交有效）。

**上传包**：`supercompute_transfer/issue27ckby_drocc_feature_dump_20260807_upload_bundle.tar.gz`
（1,512,335 bytes，236 个 .py 全量闭包 + slurm + installer + raw51 掩码 + bundle_commit.txt
= 9439ba1 + SHA256SUMS 240 项），SHA-256
`b909db4b54300d0ed572efb9a51abb63e3e16a5464873baa769b3f938b47b5ad`（v6。v5=作业 157820 失败：`import tabm` 缺 vendor 目录——打包 `cp repo/ood/*.py` 漏掉子目录 vendor/{tabm_v0_0_3, sktime_minirocket_v0_24_1}；v6 从 CKBW 原包 提取 vendor 补齐，并做全量对账：共有模块与 157624 实际运行版本逐字节一致（0 差异）、CKBW 有而 CKBY 无的文件=0、多出文件仅为本地新增脚本（无副作用）。 v5 记录保留：v5。作废史：v1=installer 包根路径错；v2=记录表哈希误钉；v3=接线检查串变量名；v4=作业 157815 实际提交并进入 snapshot_dump 后失败：`import AfterImage` 缺 kitsune_frontend_original——v1-v4 打包时漏掉 CKBW 包内的 payload/repo/kitsune_frontend_original（5 文件）与 4 个 payload/runs 冻结输入；v5 从 CKBW 157624 原上传包逐字节提取补齐，非 ood 文件结构与 CKBW 完全一致。科学管线与冻结方案零变化，157815 未产出任何数据）。
脚本行尾 LF 已验证；掩码哈希包内复验一致。

**状态**：等用户在 HPC 上传→提交→监控→拉回快照。拉回后本地训练 DROCC（FROZEN §2.1
超参，torch 环境待确认）→ 一次性评估 → 结果文档。FINAL 全程封存。

---

## Round 11 (2026-08-09, Kimi 执行): CKBY 完成——DROCC Gate A FAIL，记录级路线正式封口

**HPC 导出**：job 157930（v6 包，210 秒）成功，快照 287,448 行（fit 18,398 = 14,013 benign +
4,385 attack；select 7,000+69；report 池全覆盖），合同断言全过，SHA-256
`b2ef1f7d0244cc7abb8665c25364744f794190f411482e4e202e346cb850279c`。本地拉回校验一致。
打包迭代史（v1-v5 全部打包层错误：路径/哈希钉值/检查串/漏 kitsune_frontend_original/
漏 vendor tabm+minirocket；v6 与 157624 实际运行版逐字节对账 0 差异后一次通过）。

**本地训练**（torch 2.13.0+cpu，600 秒，分段断点续跑=连续运行逐位等价，已验证）：
两处实现修正透明记录——(1) lr 调度按官方 epoch-shifted 分段改正（初版误录）；
(2) 官方 `grad/grad_norm` 在 float32 饱和点 0/0=NaN（3 个常量特征 + std floor 1e-4
→ 噪声放大 10^4 → logit 饱和 → 梯度下溢），两处除法加 1e-12 护栏，非退化点逐位不变。

**结果（一次性评估，ckby_drocc_seed27_result_20260809.md）**：

- **Gate A FAIL 双重惨败**：OP-1 future 召回 9.04%（门槛 84.83%）、OOD macro 55.57%
  （门槛 30.27%）；OP-0.1 更差（5.52%/47.63%）——budget 收紧召回崩塌。
- 同分母对照：C1 86.83/93.09、FrozenCKBQ 74.20/35.27、M7 63.19/0.15、DROCC 9.04/55.57——
  记录级最差，两轴同时劣化，无 trade-off 优势点。
- 失败形态=双重不可分：良性 OOD 两池近全池误报（99.8%/99.3%，流形外同向），
  15/16 攻击族召回残缺（流形内同域）。
- **过程发现**：benign-only checkpoint 规则永远选中 epoch 49（纯 CE 模型）——对抗阶段
  必然抬高 benign 验证 CE，纯良性选择压力下 DROCC 的对抗训练原则上不可能被选中；
  "strong benign-only learner" 范畴在 51D 上自我瓦解。

**路由**：按 FROZEN §8——封死"51D 表示上模型容量"解释，**记录级换模型路线正式封口，
不再开新记录级模型**（GPT 8/8 "跑一次即收枪"已执行）。下一步 Episode Design Review。
FINAL 全程未触碰。Codex 已于 8/9 回归，同步稿已发给用户转发。

**三方状态**：Kimi 执行完毕；GPT 立场（8/8）：DROCC=closure baseline，episode 设计讨论可
并行开始（不冻结/不写码/不碰 FINAL）；Codex 审查中。

---

## Round 12 (2026-08-09, Codex 执行): CKCZ FROZEN + 实现完成，待 Kimi 独立审查

**治理分工由用户重新明确**：Codex 负责预注册、实现、测试、组包与命令；Kimi 负责独立
方案/代码审查；用户负责 HPC 提交授权。GPT 不进入 CKCZ 审查/签字链，只在用户需要理解
方案时担任讲解者。

**冻结链**：

- Kimi 对 DRAFT 独立核验并 PASS：`a51fcb2`；
- 12 个训练 strata 与 16 个报告 family 口径闭环：`97adfe0`；
- FROZEN + SHA 侧车：`e7022ee`，正文 SHA-256
  `dad558902f2dfe2dc0dd4bf76cbf2e9e727be9f5d22ed2e91a5267586e8d3fde`；
- 唯一系统方向仍只是待诊断的 `hard=M7 OR V_episode`，CKCZ 只做 endpoint-pair conflict
  persistence Oracle；任一可行只授权 D1-Legal，四 scalar 全失败才封当前路线。

**实现**：`issue27ckcz_endpoint_pair_conflict_diagnostic_v1.py` 已完成 manifest/allowlist/cache
hash/schema、UID exact join、protocol/member-local causal state、四 exact frontier、16 族/四池
门、source/pair bootstrap、first-trigger/time-to-veto、描述性 ECDF/Gini、原子输出/readback/
SHA256SUMS 与失败无 verdict。自包含完整 synthetic pipeline 与冻结 297,326 行预测分母故障
回放均 PASS。

**allowlist**：Gotham 24 与 auxiliary 31 已按冻结 lineage 显式入库并带 SHA。CKBY snapshot
55 source 的 `24+31` 只是总数巧合（实际 20 processed +31 auxiliary +4 ToN），不再作为
成员证明；正式实现以 positive source list + 已钉 154917 manifest SHA 的 pre-open exact join
为准。

**状态**：实现完成稿为
`runs/mainline_docs/ckcz_implementation_ready_for_kimi_review_20260809.md`。按 FROZEN，等待 Kimi
独立代码/allowlist PASS 后才构建 Slurm bundle。尚未运行在线 154917 cache、未提交 HPC、
未产生 CKCZ 科学结果；FINAL 全程未触碰。
