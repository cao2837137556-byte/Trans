# Issue27aj Summary

1. issue27aj completed: yes.
2. primary_verdict: `recovered_kcenter_mainline_protocol_ready_for_gotham115_migration`.
3. Old mainline selector recovered: `kcenter32`.
4. Support size recovered: 32.
5. Selector details: selector-local StandardScaler fit on attack train pool,
   Euclidean farthest-first, centroid-nearest initialization, sorted global row
   output.
6. Old mainline head: fixed OOD guard LR / LOW-GUARD-LR.
7. Threshold rule: ID calibration + OOD validation at the official 1% OOD alarm
   target.
8. Final eval status: final OOD eval and attack eval were report-only in the
   recovered protocol.
9. issue27ai fixed_first32 status: clean diagnostic placeholder, not recovered
   mainline.
10. Migration status: selector and protocol permissions can migrate to Gotham
    Kitsune115 medium diagnostics; old performance claims and old frontend
    cannot migrate.
11. Recommended next issue: `issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic`.
12. New model performance produced: no.
13. Commit hash: pending.
