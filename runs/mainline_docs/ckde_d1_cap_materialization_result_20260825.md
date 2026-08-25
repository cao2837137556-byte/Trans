# CKDE D1 Stage-P cap-only materialization result

**Date:** 2026-08-25

**Status:** `CKDE_D1_CAP_MATERIALIZED`

**Authorization:** user explicitly authorized cap-only materialization

**PRE-CAP FROZEN SHA-256:** `9e7a4904dc72c0a7f81a5510e26432128478f0a17101acbece433870804697c9`

## 1. Outcome first

The frozen max-admissible-threshold algorithm materialized:

```text
theta_0        = 0.065159872174263
T_cap          = 0.065159883194168905
cap_fit_attack = 1.1019905904463556e-08
```

At `T_cap`, all `4,385/4,385` legal fit attacks remain hard. Global recall loss and the
worst eligible exact-family loss are both `0.0` percentage points.

The trust region is numerically extremely narrow. This result does **not** authorize a benign-score
opening and does not yet establish whether any eligible device can obtain a non-fallback calibrated
threshold. That question belongs to separately reviewed and authorized Stage A/B.

## 2. Frozen denominator and family handling

- fit roles: `aux_process_fit=4,000`, `support_train=385`;
- exact fit attack rows: `4,385`;
- exact family/stratum labels: `12`;
- gate-eligible labels with `rows >= 15`: `11`;
- `Mirai C&C Communication` has `9` fit rows and is reported but does not enter the frozen family gate;
- the two ToN fit strata remain exact, unmapped labels; they are not projected into the CKCZ
  16-family report taxonomy.

The candidate set contained `2,475` distinct thresholds. Exactly two were admissible: `theta_0`
and `T_cap`. The next candidate was `0.15963729500984128`; it lost `139` global attacks
(`3.1698973774` pp) and violated multiple eligible-family gates, so the max-admissible rule
mechanically stopped at `T_cap`.

## 3. Isolation and engineering validation

- four frozen CKDA inputs and both governing documents passed SHA-256 identity checks;
- exact UID join selected `4,385` rows before frozen P2 scoring;
- non-fit rows scored: `0`;
- benign/support-val/report/FINAL scores opened: `0/0/0/0`;
- PCAP and FINAL files opened: `0/0`;
- optimizer steps and fitted parameters: `0/0`;
- Python 3.9 and 3.10 compilation gates passed;
- ten Stage-P contract tests passed under Python 3.9;
- result `SHA256SUMS`: `6/6` independently rechecked.

The embedding NPZ is a pinned 25,467-row container, but the implementation exact-joins and slices
the 4,385 authorized attack UIDs before invoking the frozen scorer. No benign or support score is
computed.

## 4. Result artifacts

Directory: `runs/issue27ckde_d1_cap_materialization_v1_2026-08-25_local_r2`

- `ckde_d1_cap.json` — literal cap artifact, SHA-256
  `4ff7b3397417b70f12c08ec928f283b14efc915bf597c486b6f4250fa92b99c8`;
- `ckde_d1_cap_frontier.csv` — complete 2,475-row threshold frontier;
- `ckde_d1_cap_family_recall_loss.csv` — complete 29,700-row exact-family table;
- input, boundary, and validation audits;
- `SHA256SUMS`, SHA-256
  `d22eb39bd24004bd14473a4117ba75c1542bea22ecbafffa047c0c93e4420fe2`.

## 5. Numerical FROZEN and next boundary

The literal values were inserted without changing any scientific rule into:

`runs/mainline_docs/ckde_d1_development_commissioning_calibration_preregistered_v1_20260825.md`

Its SHA-256 is:

`0ec11fdfd794312f2ff592fb0f5f582aa97c1557addcbfbfc2384ec80c488fb4`

The next legal action is independent hash/diff review of the Stage-P artifact and numerical
FROZEN. Stage A still requires a fresh explicit user authorization after that review. Until then,
no benign prefix or support-val score may be opened.
