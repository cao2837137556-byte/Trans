# issue27ckf Fresh Holdout Feasibility Summary

primary_verdict: `no_fresh_current_region_two_sided_pair_in_local_gotham_archive`

- archive processed CSV members: `78`
- archive malicious PCAPs: `32`
- malicious PCAPs already feature-materialized: `28`
- malicious PCAPs not feature-materialized: `4`
- unused benign PCAPs: `51`
- eligible fresh pairs for current ten regions: `0`
- fresh pairs whose labels are outside current regions: `1`
- same-capture development residual rows for current labels: `19710139`
- sealed-source residual rows that remain forbidden: `1412283`
- same-capture residual rows are independent holdout: `false`
- sealed final consumed: `false`
- HPC materialization authorized: `false`

Interpretation:

- Four malicious PCAPs were not feature-materialized.
- The substantial aligned unused pair is CoAP Amplification on combined-cycle-1, which is outside the current ten-label initial region registry.
- The unused Merlin/Mirai-DoS PCAPs do not have scenario-matching exact Merlin/Mirai flooding labels in their paired processed CSVs.
- Many benign PCAPs remain unused, but there is no relevant fresh malicious counterpart for the current regions.
- Large numbers of exact attack rows remain in already used captures; these are development residuals, not new-environment evidence.
- The sealed final attack source remains reserved and cannot be consumed to choose or repair a region candidate.

Close-out:

```text
solved: Audited the complete local Gotham archive, current role manifests, unmaterialized malicious PCAPs, matched benign counterparts, and same-capture residual rows.
changed_mainline: no
active_blocker: no_fresh_current_region_two_sided_pair_in_local_gotham_archive.
frozen: archive hash, role ledger, sealed-role prohibition, and distinction between source-fresh and same-capture residual evidence.
superseded: assuming that unselected rows from an already used capture constitute a fresh deployment holdout.
next_action: define_new_gotham_capture_or_second_environment_acquisition_contract.
```
