# CKDA D1 local emergency L2 result — Codex independent review

Date: 2026-08-17 (Asia/Shanghai)  
Scope: local Windows CPU emergency execution only  
Protocol: `ckda_d1_frozen_representation_probe_preregistered_20260812.md`  
Candidate opened by frozen progression: E3 / netFound  
FINAL access: zero

## 1. Outcome

The local L2 chain completed successfully and passed its engineering validator.
The frozen scientific verdict is:

```text
CKDA_D1_WEAK_ONLY
GO_D2=false
```

This does not authorize D2, threshold reselection, candidate adaptation, or a
family/pool-specific repair. Formal paper claims remain conditional on the
pre-registered HPC replay after the school cluster becomes available.

## 2. Independent artifact validation

- L2 phase: `l2_complete`; 40/40 member checkpoints, 229,914,893 bytes.
- Pullback archive: 56,515 bytes; SHA-256
  `20988f87e6bca5af467bc8c6104d1dd6ef9378ec3e013d7065d99ff973ab929b`;
  sidecar matches.
- Stage `SHA256SUMS`: 30/30 entries independently recomputed, zero missing and
  zero mismatch.
- Report scores: 786,150 rows = 262,050 frozen report rows x three probes;
  within each probe, 262,050 unique UIDs.
- Report embeddings: 262,050 x 768; 64,782 protocol-declared missing rows remain
  in the denominator.
- Fit/select embeddings: 25,467 x 768; 11,640 protocol-declared missing rows.
- Review flags: zero for G0, P1, and P2.
- FINAL files opened: zero. No engineering failure marker remains.
- Bootstrap: 2,000 requested replicates; reported session/source intervals pass
  schema and availability checks.

## 3. Frozen metrics, independently recomputed

| Probe | Overall attack recall | Future-query recall | Four-pool OOD macro | Result |
|---|---:|---:|---:|---|
| G0 geometry | 92.6851% | 92.2263% | 60.3167% | not actionable |
| P1 linear | 96.9392% | 96.2730% | 57.8889% | weak only |
| P2 small MLP | **97.3698%** | **96.6786%** | **29.8833%** | weak only |

P2 passed all of the following frozen requirements:

- overall attack recall is not below C1 by more than 0.5 percentage point;
- future-query recall is at least 84.83%;
- all 16 attack-family deltas versus C1 are at least -2 percentage points;
- four-pool OOD macro is at most 30.2722%;
- every OOD pool is at most 90%;
- support is 69/69, review count is zero, and all contracts pass.

P2 failed exactly one conjunct: `each_ood_delta_le_2pp` versus FrozenCKBQ.

| OOD pool | P2 hard rate | FrozenCKBQ | Delta |
|---|---:|---:|---:|
| iotsim-hydraulic-system | **76.3000%** | 45.7000% | **+30.6000 pp** |
| iotsim-ip-camera-street | 0.0667% | 8.1000% | -8.0333 pp |
| iotsim-predictive-maintenance | 42.8333% | 57.5889% | -14.7556 pp |
| iotsim-stream-consumer | 0.3333% | 29.7000% | -29.3667 pp |

P2 therefore nearly reaches the aggregate target while failing uniform OOD
robustness on one whole held-out device pool. The frozen conjunction correctly
prevents the favorable macro average from hiding that regression.

## 4. Signal strength and claim boundary

This is not a `NO_INFORMATION` result. P2 has ROC-AUC 0.8822 and PR-AUC 0.9824;
its source-bootstrap 95% ROC-AUC lower bound is 0.8111 (>0.5). P1 also clears
the weak-signal bootstrap condition. The E3 representation therefore contains
substantial attack/OOD discrimination information.

It is also not an actionable result under the frozen protocol. The information
does not transfer uniformly across OOD device pools, and the hydraulic-system
regression is too large to dismiss as threshold noise. No post-hoc threshold or
hydraulic-specific patch is permitted.

The primary I1 route was not trained because its benign-only precondition failed;
E3 was opened as the frozen backup. Consequently this run evaluates externally
pretrained E3, not the proposed domain-trained I1 encoder.

## 5. Decision

**PASS for engineering integrity and verdict reproducibility.**  
**Scientific state: `CKDA_D1_WEAK_ONLY`; `GO_D2=false`.**

Next authorized activity is discussion/design only: decide whether to acquire a
larger legally disjoint benign corpus for a newly named I1 route, or close CKDA
after formal HPC replay. Do not enter D2, tune on report results, open FINAL, or
add a device/family patch under the current protocol.

