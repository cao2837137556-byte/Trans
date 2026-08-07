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
