# Gotham Size Adequacy Report

Size adequacy was evaluated with row count, file count, device count, protocol count, attack type coverage, support/eval independence, final OOD size, and subgroup-analysis feasibility.

- gotham_device_disjoint_v1: size_adequate_for_main_benchmark (ID=1716285, OOD_val=1308423, final_OOD=842307, attack_eval=15250158)
- gotham_protocol_disjoint_v1: size_adequate_for_main_benchmark (ID=2480949, OOD_val=908975, final_OOD=477091, attack_eval=15250158)
- gotham_time_aware_within_device_v1: size_blocked_by_group_dominance (ID=2245995, OOD_val=1164881, final_OOD=456139, attack_eval=0)

The primary contract appears size-adequate, but size alone does not resolve shortcut, pairing, or feature-provenance risks.
