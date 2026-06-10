# issue27bs Decision

primary_verdict = `temporal_evidence_head_dev_passed_ready_for_controller_stability`

- selected feature set: `current_plus_temporal`
- selected model kind: `histgb_shallow`
- selected attack_q: `0.99`
- selected risk_threshold: `0.7`
- selected strong_attack_q: `0.75`
- selected d_attack_thr: `1.0`
- dev attack min: `1.0`
- dev OOD max: `0.0`
- report-only attack min: `0.972972972972973`
- final OOD max report-only: `0.004333333333333333`
- bq base dev OOD max: `0.25933333333333336`
- bq base report-only attack min: `0.6501501501501501`
- caveat: this is a fit/select time-half diagnostic, not a group/file-disjoint formal evaluation.
- caveat: the selected feature set includes parent BQ evidence, so the next step must run ablations without parent `ood_risk` and with group-disjoint replay.
