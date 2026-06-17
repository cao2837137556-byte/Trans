# issue27ch Certified Attack Subset Freeze

primary_verdict: `complete_only_certified_attack_subset_frozen_for_protocol_replay`

issue27ch completed: yes
model_training: no
formal_benchmark: no
threshold_tuning: no
pcap_rerun: no
controller_changed: no
sealed_final_used_for_selection: no
support_bank_replanned: no

## Certified Subset

- source issue27cd status: `PARTIAL`
- source chunks: `99`
- certified chunks: `93`
- excluded partial chunks: `6`
- issue27cd expected exact rows: `717056`
- issue27cd emitted rows including partial emissions: `688881`
- certified_attack_subset_v1 rows: `683420`
- excluded planned rows: `33636`
- excluded emitted rows: `5461`
- excluded missing rows: `28175`
- subset_contract_sha256: `56cce3e4dec704805a1e281c0ef2120b956f135341212017eb1d09539161a770`

## Close-out

```text
solved: Froze certified_attack_subset_v1 from issue27cd by selecting only COMPLETE chunks and excluding all six combined-cycle-1 PARTIAL chunks as whole chunks.
changed_mainline: yes
active_blocker: attack region activation/radius/shell and support-bank lifecycle protocol are still undefined; no model replay yet.
frozen: certified complete-only attack subset, role access inventory, partial chunk deferred_not_deleted exclusion list, source/input hashes.
superseded: treating issue27cd dev_future_attack_query_exact partial emissions as usable certified query rows; continuing to repair the six combined-cycle-1 partial chunks for the current mainline.
next_action: issue27ci_attack_region_activation_and_support_bank_protocol_refinement.
```
