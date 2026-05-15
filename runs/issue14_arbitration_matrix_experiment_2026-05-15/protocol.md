# Issue14 Arbitration Preflight Protocol

This run is a score/provenance preflight for the base-detector + GDA-minimal arbitration experiment. It does not train any detector or adapter, does not modify prior experimental results, and does not tune thresholds or policies on final evaluation sets.

Required arbitration variables:

- `base_score(x)`: dA or Transformer anomaly score from the current low-OOD protocol.
- `base_threshold`: threshold from the corresponding base detector low-OOD protocol.
- `gda_score(x)`: original100 fixed-guard LR 32-shot GDA-minimal score from issue11.
- `gda_threshold`: issue11 guarded threshold selected from ID calibration + OOD validation only.

Decision policies to evaluate after score recovery:

| strategy | rule |
|---|---|
| base_only | high-priority alert if `base_high` |
| gda_only | high-priority alert if `gda_high` |
| OR_policy | high-priority alert if `base_high OR gda_high` |
| AND_policy | high-priority alert if `base_high AND gda_high` |
| mode_gated_arbitration | both-low -> background; both-high -> high-priority; base-low/GDA-high -> GDA-driven high-priority; base-high/GDA-low -> needs-review |

Preflight outcome:

- dA and Transformer base score caches are available and aligned at asset-shape level.
- issue11 GDA-minimal per-sample scores are not persisted.
- Therefore row-level strategy metrics are intentionally not computed in this pack.
