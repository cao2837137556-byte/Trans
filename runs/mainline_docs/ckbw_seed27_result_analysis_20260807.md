# CKBW seed-27 result analysis (Kimi, 2026-08-07)

- Job: amd 157624, wall 1,371 s, phase chain completed cleanly, pullback verified.
- Decision: **NO_GO** (preregistered gates; PRIMARY fixed, no promotion).
- Contract checks: **16/16 PASS** (data boundary, five-place config consistency, frozen hashes, review=0, cooler-motor sealed, seeds 37/47 locked all held). The NO_GO is purely scientific, not procedural.
- Winner candidate: λ_tail=0.25, λ_family=0.25, selected epoch 6, τ_normal=0.971323, τ_attack=1.0 (rescue never activated; 27 select-pool baseline-hard rows all suppressed).

## 1. Headline numbers (GLOBAL protocol; attack recalls shown in BOTH scopes after the GPT P0 audit)

Gate scope note (P0 resolution, 2026-08-07): the preregistered gate metric `attack_overall` is computed on the **all-role attack pool** (244,050 rows = support_val 69 + same_file 2,486 + sealed_final 110,104 + future_query 131,391), where the sealed pool's 110k easy rows dilute the future_query collapse. The **future_query-only** lens is stricter and is the one that matches the open-world claim. Both scopes are raw results from `ckbw_attack_preservation_summary.csv`; an earlier version of this table quoted future-only recalls next to the overall-pool gate delta, mixing scopes (caught by GPT, fixed here).

| Arm | Benign-OOD macro | Attack recall (future_query) | Δ vs C1 (future) | Attack recall (all-role pool) | Δ vs C1 (pool = gate) |
|---|---:|---:|---:|---:|---:|
| M0-C1 | 0.931 (0.724 hydraulic + 3×1.000) | 0.8683 | — | 0.9130 | — |
| M1-FrozenCKBQ | 0.3527 | 0.7420 | −12.64 pp | 0.8435 | −6.95 pp |
| **M7-PRIMARY (TailMargin-Dual)** | **0.0015** | **0.6319** | **−23.64 pp** | **0.7771** | **−13.59 pp (gate ≥ −0.5: FAIL)** |
| M5-TabM-CE-Dual | 0.0071 | 0.6783 | −19.00 pp | 0.8088 | −10.42 pp |
| A4-ExtraTrees-Dual | 0.0894 | 0.7264 | −14.20 pp | 0.8351 | −7.79 pp |
| M6-TailMargin-OR | 0.3527 (= CKBQ) | 0.7420 (= CKBQ) | −12.64 pp | 0.8435 (= CKBQ) | −6.95 pp |
| A2-ExtraTreesRescue | 0.616 | 0.7420 | −12.64 pp | 0.8435 | −6.95 pp |
| M4-TabMProcessRescue | 0.3536 | 0.7420 | −12.64 pp | 0.8435 | −6.95 pp |

M7 per-family benign-OOD: hydraulic 0.457→0.000, predictive-maintenance 0.576→0.006, stream-consumer 0.297→0.000, ip-camera-street 0.081→0.000. Worst-family OOD = 0.61%. support_val attack recall 69/69 = 1.0.

## 2. Where the attack loss concentrates (future_query, M7 vs C1)

| Family | rows | C1 | CKBQ | M7 | M7−C1 |
|---|---:|---:|---:|---:|---:|
| Merlin C&C Communication | 9,921 | 0.998 | 0.905 | 0.045 | **−95.4 pp** |
| Telnet Brute Force | 24,712 | 0.667 | 0.328 | 0.217 | −45.0 pp |
| Ingress Tool Transfer | 3,983 | 0.631 | 0.548 | 0.184 | −44.7 pp |
| Reporting | 93 | 0.742 | 0.409 | 0.409 | −33.3 pp |
| TCP Scan | 24,711 | 0.734 | 0.532 | 0.481 | −25.4 pp |
| Merlin UDP Flooding | 5,296 | 1.000 | 0.829 | 0.828 | −17.2 pp |
| Floods (Mirai TCP/GRE/UDP, Merlin TCP/ICMP) | — | ≈1.0 | ≈0.92-1.0 | ≈0.92-1.0 | 0 to −7.7 pp |
| File Download | 1,230 | 1.000 | 1.000 | 1.000 | 0 |
| CoAP Amplification / UDP Scan | 433 | 0.0 | 0.0 | 0.0 | 0 (missed by everyone) |

The losses are exactly the **low-volume, stealthy families** (C&C, brute force, ingress, reporting, scans). High-volume floods survive essentially untouched.

## 3. Diagnosis — mechanism boundary, not a tuning problem

1. **The dual control is purely suppressive in practice.** τ_attack=1.0 and rescue=0 on every dual arm; the select pool offered only 27 suppressible baseline-hard rows. Everything the mechanism does is "revoke baseline alarms when the process score looks benign". (P1 refinement from GPT, accepted: τ_attack=1.0 is at least partly a *degenerate optimum of the legal selection objective* — with no support rows needing rescue, the maximal attack cut is optimal — so the precise statement is "no 51D rescue was authorized under the legal objective", which is weaker than "the 51D score carries no attack signal". M6's byte-identity to CKBQ likewise proves only that nothing was authorized at the legal OR cut.)
2. **Record-level process normality cannot separate stealthy attacks from benign OOD.** Both look process-normal per record; τn=0.9713 suppresses both. The spectacular OOD number (0.15% macro) and the stealthy-attack collapse are the *same* mechanism acting on two populations that are indistinguishable in this feature space.
3. **Tail-margin training did not change this.** M7 ≈ M5 (plain CE) family-by-family, and M7 is even worse on Merlin C&C (0.045 vs 0.162). The margin loss protected the 69 support rows (recall 1.0) but nothing generalizes to unseen same-family attack records — the separating information is simply not in the record-level causal features.
4. **The attack evidence exists in another view.** C1 catches Merlin C&C at 0.998 while the process side scores it benign-like. Suppression currently ignores that view: it revokes whenever the process scorer is confident, even when an attack-oriented view is firing.
5. **OR direction is dead too.** M6 is byte-identical to FrozenCKBQ on every family and every OOD rate — the tail scorer adds zero standalone detections at the legal threshold.

Honesty note: the 0.15% OOD figure is NOT a publishable result by itself — it was bought with −13.6 pp attack recall and a −95 pp worst family. It only demonstrates the suppression mechanism is extremely strong, not that it is correctly aimed.

## 4. Implications for the next iteration (to be decided with Codex; nothing implemented)

- **Option A — evidence-gated suppression (recommended starting point).** Before revoking a baseline alarm, require *all* attack views to agree benign: suppress only when tail score high AND C1 score low AND CKBQ not firing. Directly targets the observed failure (Merlin C&C should recover toward C1's 0.998) without any per-family patch. One mechanism, uniformly applied.
- **Option B — episode/temporal aggregation for stealthy families.** Stealthy attacks are visible as temporal patterns (beacon periodicity, repetition), not as single records. Bigger redesign but arguably the real open-world answer.
- **Option C — role split.** Dual control may only suppress records no attack view claims; attack views (C1+CKBQ) have veto. Close to A, framed as an architecture rule.
- Explicitly rejected: per-family thresholds/experts (patch-style, against the agreed no-patch principle); more margin tuning on the same record-level features (proven uninformative by M7≈M5).

## 5. What this run bought us

1. A fully working, contract-clean CKBW pipeline (22-minute turnaround, reproducible bundle) — the week-long engineering blocker is gone.
2. A clean negative result that *locates the boundary*: record-level process scoring solves benign-OOD suppression completely and is fundamentally blind to stealthy attacks.
3. A precise, evidence-backed next hypothesis (Option A) with an expected measurable effect on Merlin C&C / brute force / ingress.
