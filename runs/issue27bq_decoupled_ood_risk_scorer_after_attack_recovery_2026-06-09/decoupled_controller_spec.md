# Decoupled OOD-Risk Controller

- The full-115D attack scorer and attack threshold stay frozen.
- OOD-risk scoring is conditioned on raw attack alarms and uses only dev-side alarm examples for fit/selection.
- Positive OOD-risk class: dev-side benign/OOD false alarms from id_calib, ood_val, and ood_stress_val.
- Negative OOD-risk class: dev-side attack alarms from support_val and dev_future buckets.
- Final OOD and report-only attack replay are not used to fit or select the risk scorer.

Decision:

```text
if raw_attack_alarm is false: no_alarm
elif ood_risk is high and attack evidence is weak: suppress
elif ood_risk is high and attack evidence is strong: bounded review
else: hard_alarm
```
