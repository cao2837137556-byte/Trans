# Final OOD Tail Attribution Report

primary_verdict = `ood_tail_needs_benign_prototype_veto`

Final OOD is report-only. It is used here only to attribute the already-observed OOD tail alarms under the frozen replay, not to tune prototypes, radii, thresholds, or model configuration.

## Budget 16 False-Alarm Triage Shares

- benign_covered: `0.9911357340720222`
- both_covered_conflict: `0.00110803324099723`
- unknown_uncovered: `0.00775623268698061`

Interpretation guide:
- benign_covered false alarms suggest an OOD/benign prototype veto may help.
- unknown_uncovered false alarms suggest the OOD stress pool is incomplete.
- attack_covered or both_covered_conflict false alarms suggest attack/benign feature overlap or a conflict gate is needed.
