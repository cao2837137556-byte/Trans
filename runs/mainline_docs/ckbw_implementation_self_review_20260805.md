# CKBW implementation self-review (Kimi, 2026-08-05)

- Implementation under review: `repo/ood/issue27ckbw_tail_margin_dual_control_v1.py` (2,744 lines)
- Commit: `b2ae810` (`Continue CKBW formal pipeline from token breakpoint`), branch `codex/exp-mainline`
- Frozen protocol: `ckbw_tail_margin_dual_control_preregistered_20260803.md`, SHA-256 `80c44c8db9335c2e90a7d0f6a42649ec50ae9e88418a43165696474b0d9aec5b`
- Reviewer: Kimi (the implementing agent). This is a **self-review**; independent Codex re-review is still pending and this document is its entry point.
- Scope: implementation only. No science change, no threshold change, no data change versus the frozen preregistration.

## 1. Preregistration §14.1 hard gate — TabM config five-place consistency

Frozen values: `width=192 / blocks=3 / k=16 / batch_size=512 / epochs=24 / numerical_embeddings=false`.

Evidence:

1. **Single source of truth.** The values exist exactly once as module constants (`issue27ckbw_tail_margin_dual_control_v1.py:76-84`: `INPUT_DIM=51, WIDTH=192, BLOCKS=3, ENSEMBLE_K=16, BATCH_SIZE=512, EPOCHS=24, MARGIN=0.10, TAIL_K=16, LAMBDA_GRID=(0.25,0.50)`). `TABM_CONFIG` (line 1097-1112, including `"numerical_embeddings": False`) is built only from these constants.
2. **No CLI override.** `parse_args` (lines 926-997) exposes no width/blocks/k/epochs/batch-size knob; the only free knobs are `--train-cap/--eval-cap/--bootstrap-reps/--threads`, none of which touches model shape.
3. **Runtime assertion.** `run_formal` builds the five places — `model_construction`, `cli_defaults`, `run_spec`, `model_audit`, `result` — and asserts all five equal `TABM_CONFIG` before writing results (lines 2195-2206; failure raises and aborts the run, recorded as `config_five_place_consistency` in `ckbw_single_seed_go_no_go.json` and `run_spec.json`).
4. **Audit propagation.** The same `TABM_CONFIG` lands in `ckbw_model_audit.csv` (line 2053), `ckbw_environment.json`/run_spec (lines 2196-2254) and the printed completion record, so post-run audit can re-verify consistency from artifacts alone.

Self-check: PASS.

## 2. Preregistration §9.3 contract gates — code mapping

| Gate | Code position |
|---|---|
| Single shared 51D process scorer, protocol identity across GLOBAL + 4 held runs | `assert_global_pool_contract` (line 1202), `assert_protocol_identity` (line 1225), invoked at lines 1773-1775 |
| support_train 385 seen every epoch, 12-family attack balance | `family_balanced_row_weights` (line 350), `support_usage` audit rows (lines 2084-2096), contract flags at 2181-2182 |
| Fresh C1 must equal frozen C1 | `fresh_c1_vs_frozen_audit`, `c1_mismatch_rows == 0` required (lines 1797-1800, 2183) |
| raw51 masked rows fail closed to frozen CKBQ | `_observable_predicate` (line 1115), `masked_rows_fail_closed_to_frozen_ckbq` (lines 2184-2186) |
| Frozen 154917 score bundle hash-locked | `FrozenScoreBundle.load` (line 155), pins `FROZEN_PREDICTIONS_SHA256` / model SHA-256 constants (lines 57-65); flag at 2187 |
| review_rate = 0 everywhere | `review_rate: 0.0` written in model rows, scope audit, environment (lines 2065-2115, 2227); flag at 2188 |
| No score addition, no per-family experts, UDP Scan diagnostic only, cooler-motor untouched, seeds 37/47 locked | flags at lines 2189-2193; cooler-motor asserted via `cooler_rows == 0` |
| Data boundary: fit/select/report separation, report+held rows never in fit/preprocess/tail-mining/selection | assembly via validated CKBU functions (`ckbq.prepare_inputs` line 1730, `ckbo.permanently_mask_frames`/`restrict_model_scope_to_frozen_targets` lines 1731-1733, `ckbu.UnifiedFeatureStore`/`auxiliary_records`/`ton_records`/`fit_preprocessor` lines 1748-1792); pool cardinalities pinned (lines 1082-1088); `report_rows_used: 0` / `held_rows_used: 0` asserted in selection and scope audits (lines 2044-2045, 2113-2114) |
| τ_normal/τ_attack selected only on legal select pool (support_val 69 + benign select 7,000 + aux 3,000 + ToN normal 4,000) | `choose_dual_gate` (line 476), invoked at 1812-1817; `selection_scope` recorded at line 2043 |
| PRIMARY fixed, no post-hoc promotion | `PRIMARY = "M7-TabM-TailMargin-DualControl"` (line 92); outcome decided by `scientific_outcome` against frozen gates (lines 1090-1095: attack overall −0.5pp / family −2.0pp (min 15 rows) / OOD macro ≤ 0.302722 / family worsen ≤ +0.02 / family abs ≤ 0.90) |
| Dependency closure fail-fast | `ckbu.validate_frozen_formal_dependency_closure()` first thing in `run_formal` (line 1714) |

Self-check: PASS (static mapping + smoke execution evidence below).

## 3. Local validation evidence (all on the local interpreter, cwd `repo/ood`)

| # | Check | Result |
|---|---|---|
| 1 | `python -m py_compile` | PASS |
| 2 | `--contract-unit` | PASS |
| 3 | `--validate-frozen` against local 154917 pullback copies | PASS (`CKBW_FROZEN_SCORE_CONTRACT_PASS`, no frozen-score regression) |
| 4 | `--frozen-arm-preview` on the real frozen prediction table | PASS. Diagnostic only: CE-Dual τn=0.853938/τa=1.0 (rescue=0), OOD macro ≈0.72% with attack −10.42pp; A4-Dual τn=0.489414/τa=1.0, OOD ≈8.95% with attack −7.79pp. Confirms dual control strongly suppresses benign-OOD; the preregistered decider is the tail-margin trained PRIMARY, which preview cannot exercise. |
| 5 | `--smoke-store` | PASS (`CKBW_SMOKE_STORE_PASS`) |
| 6 | `--smoke-formal` (external harness `_kimi_review/ckbw_smoke_harness.py`, monkey-patches EPOCHS=2 and a single λ; repo code untouched) | PASS (`CKBW_SMOKE_FORMAL_PASS`) |

## 4. Known limitations of this self-review

1. The full formal pipeline (24 epochs × 4 λ-candidates, 18,398 fit rows, full select/report scoring) has never executed end-to-end on real caches; the complete gotham/aux/ton feature caches exist only on the HPC. First real execution is the HPC job. Local estimate: roughly 2-6 h at 8 threads (unmeasured).
2. The rescue branch (τ_attack < 1) was not exercised with real data: the frozen-arm preview selected τa=1.0 for both frozen arms. Tail-margin rescue paths are exercised only in smoke. This is expected — preview shows the frozen arms are pure-suppression — but the HPC run is the first real test of PRIMARY.
3. Reviewer = implementing agent. Independent Codex re-review is explicitly pending; treat this document as the map for that review, not as a substitute.

## 5. Declaration

`CKBW_IMPLEMENTATION_SELF_REVIEW_PASS` within the scope above. Proceed to bundle build and HPC submission (already user-approved). Codex independent re-review remains open and can gate any *subsequent* science iteration, but does not block this already-authorized run.
