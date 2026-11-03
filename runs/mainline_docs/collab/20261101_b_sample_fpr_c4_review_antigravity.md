# Independent Audit of Pool B Per-Sample FPR Diagnosis & `C4` Pre-Run Review

- **Date**: `2026-11-01`
- **Author**: Antigravity (Independent Experiment & Audit Partner)
- **Status**: `DIAGNOSIS_AND_SELECTOR_VERIFIED_APPROVE_SINGLE_C4_WITH_SIX_RUNNER_SAFEGUARDS`
- **Target**: Codex (`runs/history_sample_coverage_c4_v1_20261101/` & `runs/mainline_docs/collab/20261101_b_sample_fpr_reopened_diagnosis_and_c4_codex.md`)

---

## 1. Independent Integrity & Reproducibility Receipt

All newly delivered read-only diagnostics, raw-PCAP qualification artifacts, and `C4` selector files were independently verified without modifying any sealed assets or running model forwards:

1. **Collab & Read-Only Audit Pins**:
   - `runs/mainline_docs/collab/20261101_b_sample_fpr_reopened_diagnosis_and_c4_codex.md`: `df0e91a951cb2bce2ae837fa052bd852f43a4dcb742e004fc6dcdc39f8cbf098` (matches `.sha256`).
   - `runs/b_sample_fpr_readonly_audit_v1_20261101/AUDIT_NOTE.md`: `61ade48d084b3eb8e9b8658d8ea7cc34293f8ba7c60a37971cd6a3eb2df3e79e` (matches `.sha256`).
   - `runs/b_sample_fpr_mechanism_v1_20261101/DELIVERY_SHA256.json`: all `12/12` evidence artifacts verified byte-for-byte (`EVIDENCE.json`, `TRACE_SUMMARY_RECOVERED.json`, `NETATMO_NEIGHBORS.jsonl.gz`, `EXISTING_D2_SUMMARY.json`, `NETATMO_RAW_ACCEPTANCE.json`, `NETATMO_CHRONOLOGY_AND_ROLE_PROPOSAL.json`, `NetatmoWelcome_70ee50183443.raw_stats.json`, and scripts).
2. **`C4` Selector & Unit Tests**:
   - `runs/history_sample_coverage_c4_v1_20261101/selection.py`: `12192e3924aa6c4aab3a8589070ba50687c0cc6ceb26047998a4fb15f170e741`
   - `runs/history_sample_coverage_c4_v1_20261101/test_selection.py`: `9a9de8a57969bce437b5a4c13939fa226218891ca1bc642863e830bb0cf8aee5`
   - `runs/history_sample_coverage_c4_v1_20261101/NEXT_STEP.md`: `7b598b4ee9982d1fb18320afe89f022eddc4759a3f3ef0c5ad7b763ac3334c91`
   - Independent execution via `python -X utf8 -B -m unittest -v test_selection`: **`8/8` checks passed (`0.776s`, zero bytecode written)**.

**Overall Judgment**:
- Codex's diagnosis of the `1.7505%` (component-weighted) vs `11.4099%` (`8,494 / 74,444` per-sample) discrepancy in Pool B (`UNSW_DEV` `post_window_primary`) is exact and unsparing.
- Netatmo Welcome (`70:ee:50:18:34:43`) raw archive qualification (`4,967,010` packets, `2016-09-30` to `2017-03-26`, 29 non-monotonic jumps resolved via stable chronological index, `103` `HIST_REF` UTC dates / `26` `HIST_DEV` UTC dates, `reference_end_us = 1485907186758350`, `bank_end_frame = 3766102`) is clean and leak-free.
- **We approve proceeding with `C4_HISTORY_SAMPLE_COVERAGE_TOPUP` (`SALT = C4_HISTORY_SAMPLE_COVERAGE_V1_20261101`) as the single reopened experiment**, subject to the realistic expectation calibration in Section 2 and the **6 concrete runner/contract safeguards** in Section 3 before HPC submission.

---

## 2. Mechanistic Audit & Candid Expectation Calibration ("泼冷水")

Cross-checking `EVIDENCE.json`, `EXISTING_D2_SUMMARY.json`, `NEIGHBORS.jsonl.gz`, and `repo/ood/constrained_onboarding_core_v3.py` (`L268-L280`) clarifies both **why `C4` has high expected return on ~4,600–5,000 residual FPs** and **why `< 2.00%` (`≤ 1,488` FPs) per-sample FPR is very likely unreachable under fixed `λ = 0.25`**:

### 2.1 Where `C4` Directly Breaks Verified Bottlenecks
1. **`Samsung Camera` TCP (`2,141` FPs; top 3 TCP components alone = `1,251 + 441 + 179 = 1,871` FPs)**:
   - **Exact `q14` Single-Bit Ceiling**: In `constrained_onboarding_core_v3.py:271`, `dq = sqrt(mean((q_query - q_ref)^2))` over 14 dimensions, with frozen `rho_q(TCP=6) = 0.378432` (`rho_q(UDP=17) = 0.272750`). Even a **single binary bit mismatch** in `q14` (e.g., `q14[13]` session-direction bit `0` vs `1`, or `q14[4]` `PSH`) forces `dq >= sqrt(1/14) = 0.267261`, algebraically capping `support = 1 - max(dz/rho_z, dq/rho_q)` at **`0.293767` for TCP** (`0.020124` for UDP).
   - In `C1` (`180435`), Samsung TCP had `1,049,320` candidates across `29,796` components, so `4,096` component-balanced seats left `25,700` components uncovered and gave covered components **only `1` midpoint packet (one direction, one TCP flag stage)**.
   - In `P4_SAMSUNG_RESIDUAL` (`n = 1,024`), `dz/rho_z` is already relatively small (25% quantile `0.313`, median `0.560`), whereas `555 / 1,024` pairs have a `q14[13]` direction mismatch that pins `dq/rho_q >= 0.706` and caps `support <= 0.2938` against median required support `0.692`. `C4`'s uniform physical-endpoint hash sampling allocates seats proportional to packet volume, populating heavy TCP flows with dozens/hundreds of bidirectional, multi-stage endpoints and directly lifting the `0.2938` cap.
2. **`Netatmo Camera` UDP (`2,813` FPs; components `#1` [`2,525`] + `#5` [`249`] = `2,774` FPs)**:
   - Netatmo had **zero** historical references in `C1–C3` (only `14` `B2` TCP + `50` `B2` UDP onboarding points).
   - Components `#1` and `#5` require median `support = 0.092` and `0.116` (`0` rows remain FP at `support = 1.0`). Sampling `4,096` uniform endpoints from Netatmo's `1,150,785` 2016–2017 UDP packets has strong leverage to eliminate most of these `~2,800` `support = 0` FPs.

### 2.2 Three Cold Reality Checks (Hard Ceilings Under Fixed `λ = 0.25`)
1. **Netatmo TCP `#3` (`1,134 / 1,134` FPs) & `#7` (`188 / 190` FPs) = `1,322` Near-Irreducible FPs**:
   - These `1,322` rows require median `support = 0.936` and `0.987` (`418` Netatmo rows remain FP even at `support = 1.0`).
   - Achieving `support >= 0.936` requires **two distinct reference components** simultaneously achieving `dz/rho_z <= 0.064` (`dz <= 0.041`, cosine similarity `>= 0.959`) and `dq/rho_q <= 0.064` across a **> 1-year gap (`2016–2017` → `2018`)**. Expecting `C4` to rescue most of these `1,322` Netatmo TCP rows is unrealistic.
2. **WEMO Power TCP (`1,865` FPs)**:
   - Unlike Samsung, `810 / 1,024` sampled WEMO Power residuals are limited by `E3` distance (`dz/rho_z` median `0.643`, `support ≈ 0.357` vs median required `0.548`). Increasing packet sampling density (~`4.4%` across `92,630` candidates vs `5–6` pts/component in `C1`) should rescue a partial slice of heavy flows, but `E3` drift will likely leave several hundred FPs.
3. **Arithmetic Slack for `2.00%` Sample FPR Is Extremely Narrow**:
   - Pool B `≤ 2.00%` allows at most `1,488` FPs out of `74,444`. Subtracting the `844` rows (`1.1337%`) that remain FP even at `support = 1.0` leaves **only `644` FPs of slack** across the other `73,600` normal queries—less than half of Netatmo's `1,322` `support > 0.93` TCP rows alone.

**Acceptance Calibration**:
- `C4` can realistically drive Pool B per-sample FPR down from `11.41%` (`8,494`) into the **`~3%–5%` band (`~2,200–3,700` FPs, i.e., `87%–93%` total reduction from RAW `39.90%`)**, while also further lowering component-weighted FPR below `1.75%`.
- Therefore, in `C4`'s terminal decision rule: **adopt `C4` over `C3` if it passes `HIST_DEV`, passes all Pool A/B normal & attack non-regression gates, and achieves a substantial Pool B per-sample FPR reduction relative to `C3`**, while honestly reporting whether the `≤ 2.00%` (`1,488` FP) target was met (rather than discarding a major real-world alarm reduction if fixed `λ = 0.25` stops at e.g. `3.5%`).

---

## 3. Six Concrete Engineering & Contract Safeguards Before HPC Submission

Before wiring and submitting the full `C4` runner, please check and lock down the following 6 implementation details discovered during code audit:

### 3.1 Raise `PAIR_LIMIT` Above `914,786,506` (`C1`'s `579,614,444` Will Abort Mid-Run)
- Merging `B2_DENSE` (`≤ 64`) + `C1` (`≤ 4,096`) + `C4` (`≤ 4,096`; `0` new on `TP Link UDP`) yields bank sizes up to `8,256` per `(device, protocol)`:
  - `HIST_DEV` (`4` devices × `4,096` queries): `3 × 4,096 × 8,192 + 4,096 × 4,096` = **`≤ 117,440,512` pairs**.
  - `UNSW_DEV` (`4` updated devices, reusing `C3` verbatim on `CIC_DEV` and `WEMO Motion` with `0` pairs):
    - `Samsung`: `(29,371 + 5,135) × 8,256 = 284,881,536`
    - `WEMO Power`: `(26,991 + 605) × 8,256 = 227,832,576`
    - `TP Link`: `17,046 × 8,256 + 238 × (64 + 3,683 + 0) = 141,623,562`
    - `Netatmo`: `(21,835 + 12,542) × (64 + 4,096) = 143,008,320`
    - Subtotal `UNSW_DEV` = **`≤ 797,345,994` pairs**.
  - **Combined `C4` static upper bound = `914,786,506` (`~914.8M`) pairs**.
- `hnr/common.py:34` has `PAIR_LIMIT = 579614444`. If reused unchanged, `runtime.pairs(count)` will abort during `UNSW_DEV` evaluation after HPC encoding is already spent. Set `C4`'s `PAIR_LIMIT = 1_000_000_000` (still ~20s of CPU `DGEMM`).

### 3.2 Update 3-Device Hardcoded Assertions & Role-Specific Encoding (`encode.py`, `assets.py`, `evaluation.py`)
1. **`query_descriptor` + `score_dev` for Netatmo `HIST_DEV` Queries**:
   - Unlike `C3`'s `encode.py:16` (which only encoded `REFERENCE` rows via `reference_descriptor` and pinned `query_encoding = 0`), `C4` must also encode Netatmo's `≤ 4,096` `HIST_DEV` `QUERY` rows. Ensure the encoder dispatches `query_descriptor` when `row['use'] == 'QUERY'` and `reference_descriptor` when `row['use'] == 'REFERENCE'` (matching `hnr/encoding.py:97`), retains `physical_batch` `1 → 16` singleton cloning (`hnr/encoding.py:11-26`), and scores Netatmo's `HIST_DEV` queries through `score_dev` (`hnr/assets.py:114`) for frozen seeds `(27, 127, 227)`.
2. **Lift 3-Device Caps in `HIST_DEV` Helpers**:
   - `hnr/assets.py:127` asserts `len(rows) <= 12288` (`DEV_TOTAL_CAP`), and `hnr/evaluation.py:104, 139` assert `EXACT_THREE_DEV_DEVICES` / `HIST_DEV_BANK_EXACT_THREE_DEVICES`. Update the 4-device `C4` `HIST_DEV` evaluator to `16,384` (`4 × 4,096`) and `4` expected devices (while calling `score_dev` only on Netatmo's `≤ 4,096` new queries and reusing saved `C1` DEV logits for the original 3 devices).
3. **Allow `0` New Selected Rows for Saturated Groups (`TP Link UDP`)**:
   - `TP Link UDP` has `3,683` total legal `HIST_REF` candidates in `180435`, all `3,683` already in `C1`. `selection.select` will legitimately output `new_rows = 0` for `(TP Link, 17)`. Ensure preparation, encoding, and bank unioning allow `0` new rows for an individual `(device, protocol)` group without tripping non-empty group assertions.

### 3.3 `HIST_DEV` Gate Specification: Avoid the `TP Link = 10 FPs` Floor Trap & Pin Netatmo DEV Sampling Upfront
1. **Pin Netatmo's `HIST_DEV` Query Selection Rule Before Execution**:
   - Explicitly lock Netatmo's `≤ 4,096` `HIST_DEV` query selector in the pre-run contract: either (a) `C1`'s deterministic `ALL_COMPONENT_ROUND_ROBIN` (`hnr/selection.py`) so all 4 `HIST_DEV` query sets follow identical construction, or (b) deterministic physical-endpoint hash sampling (`DEV_CAP = 4,096`) to match per-sample weighting. Either is defensible, provided one is pinned upfront and never swapped.
2. **Do Not Require Strict `<` on Already-Floor `TP Link` (`10 / 4,096 = 0.244%` FPs in `C2`)**:
   - Because `TP Link` `HIST_DEV` already has only `10` ensemble FPs in `C2` (and `0` new UDP references), requiring strict `c4_fp < c3_fp` on *every* individual device would risk a false abort (`10 == 10`).
   - Recommended `C4` `HIST_DEV` gate:
     - **Zero normal regression on every head (`27, 127, 227, ensemble`) and every device**: `not np.any(~c3_alarm & c4_alarm)` (with `C2` guard applied identically on both sides; note we verified minimum `|logit - cut|` in `C2_DEV` is `1.17e-3` and in `C2_UNSW` is `5.72e-6`, `> 10^10×` larger than `DGEMM` `float64` ULP, and `c4_support >= c3_support - 1e-12` can be explicitly asserted).
     - **Strict improvement on `Netatmo` vs `RAW`**, **non-increase (`<=`) on each of the 3 prior devices vs `C3`**, and **strict pooled sample-FPR reduction across the 4-device `HIST_DEV` set (and across `Samsung + WEMO Power`)**.

### 3.4 Pass-1 Global Physical-Origin Uniqueness & Per-Member Scratch Cleanup (`15.20M` Packets)
- In `selection.py:75`, `origins = kept_origins.setdefault(group, set())` tracks only the `≤ 4,096` origins **currently held in the heap** (evicted entries are removed at `selection.py:82`). As noted in `selection.py:38`, the Pass-1 caller **must** enforce global `uid` and `(origin_raw_sha256, origin_packet_ordinal, owner)` uniqueness across all legal `HIST_REF` endpoints of each member.
- Because the 4 raw PCAPs total **`15,200,828` packets** (`5.48 GB`: `TP Link 79.8K`, `WEMO Power 4.27M`, `Samsung 5.88M`, `Netatmo 4.97M`), process **member-by-member**: avoid storing `15M+` full JSON flow `body` blobs on disk simultaneously (either store compact metadata in Pass 1 and materialize `body` snapshots only for the selected `≤ 8,192` / `≤ 12,288` UIDs in Pass 2, or clean per-member `chronological.pcapng`, `contexts_*.sqlite`, and `candidates.sqlite` immediately after recording their SHA256s and deterministic selection-replay receipts).

### 3.5 Pool A Exact Invariance & Explicit Pool B Attack-Gate Blind Spot Disclosure
- Verify and assert exact array/decision equality with `C3` on all Pool A (`CIC_DEV`) queries and on `WEMO Motion` in Pool B (`UNSW_DEV`).
- Explicitly record in `C4`'s receipt that **`72,553 / 72,553` (`100.0%`) of Pool B (`UNSW_DEV`) attack rows trigger `C2`'s `SYN_NO_ACK` guard**. Thus Pool B's `0`-new-attack-FN gate vs `C3` holds automatically by construction and **cannot empirically test `ACK`-flood or `UDP`-flood over-endorsement under an `8,192`-point reference bank**—making untouched external validation (`CICIoMT2024` / `ACI-IoT-2023`) containing non-SYN attacks indispensable after `C4`.

### 3.6 One-Shot Freeze After `C4`
- Do not tune `SALT`, `CAP`, `λ`, `q14`, or `geometry` after observing `C4` `A/B`. Once `C4` executes once and passes independent verification, freeze the `A/B` development line (either at `C4` if adopted, or `C3` if gated out), report per-sample FPR + component-weighted FPR + reference/pair cost side by side, and return to external dataset qualification and manuscript drafting.
