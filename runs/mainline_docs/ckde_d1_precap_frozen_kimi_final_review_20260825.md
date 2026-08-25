# CKDE D1 PRE-CAP FROZEN — Kimi freeze final review

**Date:** 2026-08-25
**Reviewed:** commit `e67efe2`
**Reviewer:** Kimi

## Verdict: PRE-CAP FROZEN CONFIRMED — next step is the user's cap-only authorization

## Checks performed

1. **SHA-256 independently recomputed:** `9e7a4904dc72c0a7f81a5510e26432128478f0a17101acbece433870804697c9`
   — identical to sidecar and Codex's claim. PASS.
2. **Draft → PRE-CAP FROZEN diff reviewed line by line.** All changes are exactly: status and
   review-basis header; R1 common-subset clause; N1 interpretation clause; §13 converted from
   questions to normative rulings; authorization boundary restated. Zero drift in any rule,
   budget, formula, or gate. PASS.
3. **R1 common subset verified against the D0 census independently.** I initially observed 20
   census rows with ≥256 prefix sessions; restricting to the 23 causal-eligible devices (as the
   protocol requires) gives exactly **23/20/11** at budgets 64/128/256, and the frozen 11-device
   common subset (8 combined-cycle keys + building-monitor-2 + normal_1 + normal_2) is exactly
   the eligible ≥256 set — no extras, no omissions, all members eligible. PASS. The brace-expansion
   hashing requirement is correctly pinned.
4. **N1 temporal-stability interpretation** is present verbatim in the claim contract. PASS.

## Authorization state

- Protocol: PRE-CAP FROZEN (science immutable; non-executable).
- The only next action: **user authorization for cap-only materialization** — a read-only
  computation over the 4,385 legal fit-attack scores that emits one literal number (`T_cap`,
  `cap_fit_attack`) plus recall-loss tables. No benign, support-val, report, or FINAL scores are
  touched in that stage.
- After the cap artifact: newly named numerical FROZEN → my hash/diff review → another user
  authorization → only then any benign prefix score opens.
- FINAL sealed; CKDB/CKDC/CKDD closed; CKDA D1 HPC replay pending cluster access.
