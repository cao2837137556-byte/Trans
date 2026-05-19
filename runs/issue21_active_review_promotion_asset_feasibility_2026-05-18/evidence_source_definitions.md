# Evidence Source Definitions

- R0 random confirmed attack validation: randomly draw confirmed attack evidence from local attack train pool after selected supports are removed.
- R1 kcenter confirmed attack validation: choose representative confirmed attack evidence from the same non-final local attack train pool.
- R2 V2_high_V1_low disagreement review: review candidates where V2 is high and V1 is low, then use only confirmed attacks from reviewed samples for promotion evidence.
- R3 near-threshold / uncertainty review: review samples closest to V1/V2 thresholds, then use confirmed attacks only.
- R4 representation-shift-high review: review samples far from OOD validation centroid in selected_source_rich_top32 space.
- R5 hybrid active review: combine disagreement, threshold uncertainty, and selected representation shift.

Review candidates are not assumed to be attacks. Review labels are simulated only for non-final candidate pools.
