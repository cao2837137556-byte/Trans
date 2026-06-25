# issue27ckf hard-OOD calibrated worst-group veto

## Scope

This is a stop-bleeding diagnostic, not the final paper method. It tests whether legal hard-OOD calibration can make the current Kitsune115D/evidence space separate hard benign OOD from attack without using sealed final roles for fitting or selection.

## Candidate summary

| candidate | weighting | ood_stress select | ood_stress group max | sealed_final_ood | sealed group max | support_val | same_file | future | sealed_attack |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| C0_baseline_issue27ckc | medium_mass_ratio_recalibrated | 0.9969 | 0.9969 | 0.9969 | 0.9977 | 0.8841 | 0.9406 | 0.5703 | 0.7907 |
| C0_baseline_issue27ckc | strict_frozen_weight4 | 0.6835 | 0.6835 | 0.9966 | 0.9977 | 0.9420 | 0.9659 | 0.4846 | 0.6993 |
| V1_hard_ood_risk_existing_controller | medium_mass_ratio_recalibrated | 0.0011 | 0.0011 | 0.0032 | 0.0034 | 0.7101 | 0.4106 | 0.4485 | 0.4411 |
| V1_hard_ood_risk_existing_controller | strict_frozen_weight4 | 0.0013 | 0.0013 | 0.0053 | 0.0060 | 0.7101 | 0.8079 | 0.4339 | 0.5627 |
| V2_hard_ood_conservative_veto | medium_mass_ratio_recalibrated | 0.0009 | 0.0009 | 0.0029 | 0.0030 | 0.6232 | 0.3796 | 0.4152 | 0.4121 |
| V2_hard_ood_conservative_veto | strict_frozen_weight4 | 0.0006 | 0.0006 | 0.0034 | 0.0037 | 0.5797 | 0.2740 | 0.2778 | 0.2834 |
| V3_hard_ood_attack_preserving_veto | medium_mass_ratio_recalibrated | 0.0011 | 0.0011 | 0.0032 | 0.0034 | 0.6812 | 0.4068 | 0.4319 | 0.4273 |
| V3_hard_ood_attack_preserving_veto | strict_frozen_weight4 | 0.0012 | 0.0012 | 0.0052 | 0.0058 | 0.5942 | 0.7444 | 0.3347 | 0.5169 |
| V4_baseline_attack_hard_ood_risk_veto | medium_mass_ratio_recalibrated | 0.9837 | 0.9837 | 0.9832 | 0.9855 | 0.7681 | 0.9105 | 0.5241 | 0.7466 |
| V4_baseline_attack_hard_ood_risk_veto | strict_frozen_weight4 | 0.6706 | 0.6706 | 0.9832 | 0.9855 | 0.7246 | 0.8842 | 0.3575 | 0.6314 |
| V5_baseline_attack_strict_hard_ood_veto | medium_mass_ratio_recalibrated | 0.9708 | 0.9708 | 0.9752 | 0.9790 | 0.6812 | 0.9028 | 0.4946 | 0.6777 |
| V5_baseline_attack_strict_hard_ood_veto | strict_frozen_weight4 | 0.6632 | 0.6632 | 0.9752 | 0.9790 | 0.6377 | 0.8541 | 0.3454 | 0.5822 |

## Codex readout

No candidate is acceptable as a mainline fix.

What worked:

- `V1/V2/V3` prove that hard-OOD calibration is not useless: `ood_stress_select` falls from near `1.0` to about `0.001`, and `sealed_final_ood` falls to about `0.003-0.006`.
- This means the current evidence space contains some signal that can recognize the current hard OOD once hard-OOD calibration is added.

What failed:

- The OOD-safe candidates damage attack retention too much. Medium `same_file_query` falls from `0.9406` to about `0.38-0.41`, and `sealed_final_attack` falls from `0.7907` to about `0.41-0.44`.
- The hybrid candidates `V4/V5`, which preserve the original baseline attack signal and only add hard-OOD risk as veto, retain attack better but fail to suppress hard OOD: `sealed_final_ood` remains around `0.975-0.983`.

Interpretation:

- Simple hard-OOD sample calibration can stop false alarms only by moving the decision boundary in a way that also suppresses many attacks.
- If the original baseline attack signal is preserved, current hard-OOD risk alone is not enough to veto hard OOD, because hard OOD still satisfies the same strong-attack evidence pattern.
- Therefore this is a useful diagnostic result, but not a valid repair. It supports moving next to a stronger multi-head / conflict-aware / invariant-evidence model instead of continuing threshold tuning.

## Interpretation guardrail

- If only `ood_stress_select` improves but `sealed_final_ood` does not, this is just a local OOD patch.
- If OOD improves but support-covered attack collapses, the veto is not attack-preserving.
- If both hard OOD and attack retention improve, the line is worth a full 10-seed replay and later group-robust/invariant-evidence upgrade.
- Even a successful stop-bleeding result is not enough for the final paper claim; smarter heads and causal-inspired invariant evidence remain required follow-up work.

## Hard-OOD fit audit

| job | stack | role | risk label | rows used | source |
|---:|---|---|---:|---:|---|
| 1 | baseline | id_calib | 1 | 3285 | fit_raw_alarm_rows |
| 1 | baseline | ood_val | 1 | 1647 | fit_raw_alarm_rows |
| 1 | baseline | support_val | 0 | 58 | fit_raw_alarm_rows |
| 1 | hard_ood_calibrated | id_calib | 1 | 3285 | fit_raw_alarm_rows |
| 1 | hard_ood_calibrated | ood_val | 1 | 1647 | fit_raw_alarm_rows |
| 1 | hard_ood_calibrated | ood_stress | 1 | 12000 | fit_raw_alarm_rows_even_margin_cap12000 |
| 1 | hard_ood_calibrated | support_val | 0 | 58 | fit_raw_alarm_rows |
| 6 | baseline | id_calib | 1 | 3341 | fit_raw_alarm_rows |
| 6 | baseline | ood_val | 1 | 1082 | fit_raw_alarm_rows |
| 6 | baseline | support_val | 0 | 58 | fit_raw_alarm_rows |
| 6 | hard_ood_calibrated | id_calib | 1 | 3341 | fit_raw_alarm_rows |
| 6 | hard_ood_calibrated | ood_val | 1 | 1082 | fit_raw_alarm_rows |
| 6 | hard_ood_calibrated | ood_stress | 1 | 12000 | fit_raw_alarm_rows_even_margin_cap12000 |
| 6 | hard_ood_calibrated | support_val | 0 | 58 | fit_raw_alarm_rows |

Runtime seconds: `279.6`.
