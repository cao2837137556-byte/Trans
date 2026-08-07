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
