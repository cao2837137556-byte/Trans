# Three Prototype Bank Attack-Preserving Gate

This diagnostic uses three evidence banks after a raw attack score alarm:

- ID prototype bank: known benign support for false-alarm attribution.
- OOD/stress prototype bank: benign drift support for OOD-tail veto.
- Attack prototype banks: medium and active-heavy attack regions that protect confirmed attack alarms.

Decision order:

```text
if raw_attack_alarm == false: no_alarm
elif strong_attack_score and near_attack_core: hard_alarm
elif near_attack_core and not near_benign_or_ood: hard_alarm
elif weak_attack_score and near_benign_or_ood and not near_attack_core: suppress
elif near_attack_core and near_benign_or_ood: review
else: unknown_review
```

Final OOD, medium attack eval, and dev-heavy query are report-only and do not tune prototypes, score floors, or gate parameters.
