# certified_attack_subset_v1 Limitations

This is a development-side certified subset freeze, not a model experiment and not a formal benchmark.

1. The subset is complete-only: chunks with status `partial_or_unstable` are excluded as whole chunks.
2. The six excluded chunks remain deferred_not_deleted; they are not erased and may be revisited in a future data alignment track.
3. The `5461` emitted rows from partial chunks are intentionally excluded because the chunk-level exact alignment contract is incomplete.
4. The certified dev_future query is therefore smaller than the issue27cd emitted total: `683420` certified rows versus `688881` emitted rows in the partial pullback.
5. Sealed final attack rows remain sealed/report-only and cannot be used for selection, training, threshold tuning, support selection, or protocol tuning.
6. This freeze does not define attack region activation, radius/shell, merge/split/retire, online update, OOD-risk/evidence-head training, controller rules, review-cost control, or mixed-stream simulation.
