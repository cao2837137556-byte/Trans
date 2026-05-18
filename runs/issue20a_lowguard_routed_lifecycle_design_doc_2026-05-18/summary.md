# Issue20a LOW-GUARD-Routed Lifecycle Design Summary

## Purpose

This design pack freezes the current deployment interpretation after issue19b. It does not run experiments, train models, modify the manuscript, or modify historical numbers. Its role is to prepare issue20 mode-specific routing validation and future Method/System writing.

## Evidence Snapshot

| dataset | holdout | seed_group | v1_detection_mean | v1_ood_alarm_max | v2_detection_mean | v2_ood_alarm_max | delta_detection_v2_minus_v1 |
|---|---|---|---|---|---|---|---|
| harder_holdout | chrono_late_train_early_eval | heldout_47_51 | 0.6798 | 0.0018 | 0.7315 | 0.0097 | 0.0517 |
| harder_holdout | chrono_late_train_early_eval | main_42_46 | 0.6798 | 0.0018 | 0.7315 | 0.0097 | 0.0517 |
| harder_holdout | holdout_bin_2 | heldout_47_51 | 0.3264 | 0.0011 | 0.8093 | 0.0068 | 0.4829 |
| harder_holdout | holdout_bin_2 | main_42_46 | 0.3264 | 0.0011 | 0.8093 | 0.0068 | 0.4829 |
| primary_lowood | primary_lowood | heldout_47_51 | 0.9295 | 0.0036 | 0.9244 | 0.0156 | -0.0051 |
| primary_lowood | primary_lowood | main_42_46 | 0.9295 | 0.0036 | 0.9244 | 0.0156 | -0.0051 |


## System Positioning

`LOW-GUARD-Routed` is a mode-specific routed adaptation system:

- V1 / LOW-GUARD-minimal: `original100 + kcenter32 + fixed guard LR`.
- V2 / LOW-GUARD+: `selected_source_rich_top32 + kcenter32 + fixed guard LR`.
- V1 remains the primary low-OOD stable module because primary low-OOD has V1 detection 0.9295 with OOD max 0.0036, while V2 has detection 0.9244 but OOD max 0.0156.
- V2 is a harder attack-side shift repair module because holdout_bin_2 improves from V1 detection 0.3264 to V2 detection 0.8093, with V2 OOD max 0.0068.
- V2 also improves chrono_late from 0.6798 to 0.7315, with OOD max 0.0097.

## Core Conclusion

Single-adapter deployment is unsafe: always-V1 misses harder attack-side shift, while always-V2 exceeds the primary low-OOD alert budget. The correct next step is not another ad hoc V3, but a bounded routed lifecycle with a Low-Alert Promotion Gate.

## Next Step

Unique first choice: `issue20_mode_specific_routing_validation_2026-05-18`.
