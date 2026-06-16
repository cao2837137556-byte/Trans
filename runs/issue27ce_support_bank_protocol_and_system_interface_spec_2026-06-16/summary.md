# issue27ce Summary

1. issue27ce completed: `true`.
2. primary_verdict: `support_bank_protocol_interface_frozen_waiting_exact_label_instantiation`.
3. task type: protocol/interface specification only.
4. model training: forbidden and not performed.
5. metric optimization: forbidden and not performed.
6. new split construction: forbidden and not performed.
7. final/report-only access: forbidden and not performed.
8. frozen in this issue:
   - candidate pool is not the support bank;
   - support train and support validation are permanently separated;
   - only exact-label, timestamp-aligned, PCAP-paired, non-Benign/non-Unknown attack rows can enter support;
   - sealed final OOD, sealed final attack, and report-only query roles cannot enter support selection, threshold selection, model selection, calibration, or tuning;
   - unselected candidates have no default reuse identity.
9. not frozen in this issue:
   - concrete support budget;
   - concrete region count;
   - concrete controller thresholds;
   - empirical hard/suppress/review formulas;
   - active-labeling sample budget.
10. unused candidate policy: `pending_forbidden_until_explicit_issue`.
11. protocol tests: synthetic invariant tests added in `protocol_invariants_test.py`.
12. current blocker: issue27cd exact-label Slurm materialization is partial and must be resolved before instantiating support indices.
13. next action: `issue27cf_instantiate_exact_label_support_bank_from_issue27cd_outputs`.

Close-out:

```text
solved: Frozen support-bank protocol/interface invariants without touching model results.
changed_mainline: yes
active_blocker: exact-label attack materialization partial; support bank cannot be instantiated until issue27cd gaps are resolved.
frozen: support-bank role boundaries, schema, controller interface, region lifecycle states, candidate reuse prohibition.
superseded: treating broad attack candidate pools or coarse old 1M attack roles as direct support assets.
next_action: issue27cf_instantiate_exact_label_support_bank_from_issue27cd_outputs after issue27cd validation/repair.
```

