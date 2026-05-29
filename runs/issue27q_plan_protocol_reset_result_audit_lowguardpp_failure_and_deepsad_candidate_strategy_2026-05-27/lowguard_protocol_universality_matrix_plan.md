# LOW-GUARD Protocol Universality Matrix Plan

issue27p is a benchmark ranking, not a protocol-universality proof. Several methods used native objectives or lite objectives,
so the result cannot establish that LOW-GUARD is head-agnostic.

The next universality experiment must be paired. For each head, run:

1. raw head
2. support-only
3. OOD-training-guard-only
4. threshold-guard-only
5. full guarded version

Protocol gain must be computed within the same head:

- detection_mean gain
- detection_min gain
- final_OOD_alarm_max reduction
- feasible_under_1pct improvement

Collapse under the low-alert constraint means either detection_min collapses on at least one seed/subgroup or OOD max exceeds 1%.
The baseline set should include LR, HistGB, DeepSAD-style, DevNet-style, and one traditional anomaly detector. KitNET AE is optional
only if the implementation is already reliable; it is not required just to inflate baseline count.
