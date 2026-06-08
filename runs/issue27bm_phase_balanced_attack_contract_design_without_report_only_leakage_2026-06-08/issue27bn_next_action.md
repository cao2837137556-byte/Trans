# issue27bn Next Action

recommended_next_action = `issue27bn_attack_only_diagnostic_on_phase_balanced_contract_without_ood_gate`

- Use the frozen `phase_balanced_dev_v2` indices from issue27bm.
- First test whether attack detection recovers on legal dev pseudo-query without OOD gate repair.
- Do not use report-only attack/final OOD for support, threshold, or model selection.
- If attack hard-min remains far below `0.93`, pause model/head work and revisit attack task boundary or label phase.
