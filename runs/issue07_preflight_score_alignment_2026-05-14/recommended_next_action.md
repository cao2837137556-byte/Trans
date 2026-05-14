# Recommended Next Action

## Recommended gating decision
Proceed with issue07 only after splitting the experiment into two gates:

1. **Gate A: dA-assisted adapter branch**
   - Ready now.
   - Existing dA full ID/OOD/attack score caches are aligned with the current primary split.
   - Executable branches:
     - `da_score_only_fewshot_lr`
     - `original100_plus_da_score_fewshot_lr`

2. **Gate B: Transformer-assisted adapter branch**
   - Not ready under strict current primary split.
   - Existing Transformer OOD and attack scores are present, but full 50000-row ID scores are missing.
   - Minimal unblock: score the existing Transformer checkpoint on the full 50000 ID source rows without retraining, then rerun alignment checks.

## Do not do next
- Do not train a new Transformer for issue07.
- Do not mix Transformer normal-vs-attack or issue06b scores into the current low-OOD split.
- Do not compare Transformer subset/legacy score results against current dA/full original100 metrics as if they were same-protocol.
- Do not write adapter conclusions into the manuscript before the adapter run exists.

## Suggested next task wording
`issue07a_da_assisted_adapter_lowood_repair_2026-05-14`: run only dA-score adapter and original100+dA-score adapter under current primary split.

Optional unblock task before Transformer branch:
`issue07b_transformer_full_id_score_recovery_2026-05-14`: recover/generate full-ID Transformer scores from the existing checkpoint, no retraining.
