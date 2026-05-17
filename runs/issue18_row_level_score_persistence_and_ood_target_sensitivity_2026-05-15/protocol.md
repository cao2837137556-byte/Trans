# Issue18 Protocol

This is a diagnostic row-level score persistence pass. It replays the issue17 random and kcenter 32-shot LOW-GUARD-minimal configuration to persist scores. It does not introduce a new model family, does not tune OOD weight, and does not select a new OOD target.

Thresholds for 0.5%, 1%, and 2% are computed from ID calibration + OOD validation only. Final OOD eval and attack eval are used only for reporting diagnostic curves.
