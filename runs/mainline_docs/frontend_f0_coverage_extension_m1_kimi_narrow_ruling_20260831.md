# Kimi Narrow Ruling — CE M1 Denominator Clarification

- Date: 2026-08-31
- Reviewer: Kimi (independent review role)
- Clarification under review: `runs/mainline_docs/frontend_f0_coverage_extension_m1_denominator_clarification_20260831.md`
- Commit: `6accfd1` (verified single-file commit)
- Governing chain: CE ruling `539b313`; draft review `d76915a`; CE draft `e7a7075`

## Ruling

**ACCEPT: `denominator = 4,812`, `H_old = 4,812`, literal reduction gate = 482.**

The mechanically frozen definition

```text
phase == select AND label_metric_only == 0 AND old_missing == true
```

is the correct CE-5 select-utility denominator. Codex's correction of the
review's 5,242 figure is scientifically right: the 430 disputed rows
(`ood_val` 381 + `id_calib` 49) are frozen as `phase=fit`, and admitting
them into a select-side utility gate would let fitted rows contribute to a
selection verdict. The review's 5,242 is hereby withdrawn; 5,242 must not
enter the FROZEN contract.

## Independent verification performed by the reviewer

All counts below were recomputed by the reviewer from the pinned artifacts,
not copied from the clarification.

### 1. Pinned identity (five artifacts, SHA-256 recomputed)

| Artifact | SHA-256 | Match |
|---|---|---|
| `ckda_d1_select_scores.csv.gz` | `bc34268e…3419` | ✓ |
| `ckda_d1_threshold_freeze_marker.json` | `84576a50…4dd5b` | ✓ |
| `ckda_d1_probe_state.npz` | `50a9bcfc…0c38` | ✓ |
| `ckda_d1_fit_select_embeddings.npz` | `b1b4f2fd…6099` | ✓ |
| `ckda_d1_fit_select_plan.csv` | `eed3d431…9aeac` | ✓ |

Threshold marker contents spot-checked: `candidate_id=E3`,
`select_rows=7069`. ✓

### 2. Mechanical reconstruction (reviewer's own join)

- P2 slice of the score artifact (`candidate_id=E3`, `probe_id=P2`):
  **7,069 rows, 7,069 unique UIDs**, one-to-one joins to availability and
  plan with zero misses, zero role mismatches. ✓
- Frozen select benign rows (`phase=select`, `label_metric_only=0`):
  **7,000**. ✓
- Old-missing select benign rows: **4,812**, decomposing exactly as
  `aux_normal_select` 3,518 + `aux_select` 1,294. ✓
- `H_old` = **4,812** (all 4,812 rows `hard=1`). ✓
- Excluded roles confirmed on the full 25,467-row plan: `ood_val` 2,604
  rows (381 old-missing) and `id_calib` 809 rows (49 old-missing), both
  `phase=fit`. 4,812 + 430 = 5,242, exactly the disputed difference. ✓
- Select attacks: **69/69 incumbent-hard**; old-missing select attacks
  (`support_val`): **23/23 hard**. Condition 5 therefore subsumes condition
  4 under this pinned baseline; keeping condition 4 as an explicit redundant
  guard is correct because it makes the sparse missing-attack denominator
  impossible to hide. ✓
- Reduction gate: `max(300, ceil(0.10 × 4,812)) = 482`. ✓

### 3. Finding the FROZEN protocol must disclose (not a blocker)

Reviewer verified that all 4,812 old-missing rows carry **score exactly equal
to the P2 threshold** (`0.065159872174263`, min = max), and
`apply_threshold` (`issue27ckda_d1_representation_probe_v1.py:1082`) uses
`score >= threshold`. Therefore `H_old = 4,812` is a consequence of the
incumbent's **fail-closed score-pinning convention for missing rows**
(missing → score pinned at threshold → hard), not of learned P2 behavior on
those rows.

The FROZEN protocol must state this explicitly, because it fixes the
interpretation of CE-5 conditions 6–8: a "hard-count reduction" means the
challenger emits a finite, below-threshold score for rows the incumbent
pinned at threshold. It also explains why condition 5 subsumes condition 4
on current rows.

### 4. Q6 mapping

The clarification's §5 (CE-2 requires `F0_ENCODER_ONLY_PASS` + count-only
artifacts; CE-4 requires `F1_FRONTEND_CHALLENGE_PASS` + separate user
authorization) matches ruling `d76915a` Q6 verbatim. ✓

## Consequence

- M1 is now fully discharged: incumbent identity pinned (E3/P2 + five
  SHAs + threshold literal), denominator 4,812, `H_old` 4,812, gate 482,
  condition 4/5 overlap explained, Q6 mapping fixed.
- Codex may now emit the FROZEN CE protocol + SHA-256 sidecar, incorporating:
  M1.1–M1.3 as discharged by this ruling and the clarification, the 4,812 /
  4,812 / 482 literals with the score-pinning disclosure (§3 above), the Q6
  prerequisite mapping, and the six §13 rulings from `d76915a`.
- Freeze verification (reviewer SHA/diff) remains required before any
  implementation authorization. No implementation, retrieval, decode,
  training, or execution is authorized by this ruling.
