# Base vs GDA Conflict Analysis

- Transformer / heldout_support_47_51: base-only review candidates average 0.4 attack rows and 108.6 OOD rows; GDA-driven highs average 1360.8 attack rows and 43.8 OOD rows.
- Transformer / main_paired_42_46: base-only review candidates average 1.6 attack rows and 95.6 OOD rows; GDA-driven highs average 1287.6 attack rows and 29.6 OOD rows.
- dA / heldout_support_47_51: base-only review candidates average 0.4 attack rows and 107.6 OOD rows; GDA-driven highs average 1360.8 attack rows and 43.8 OOD rows.
- dA / main_paired_42_46: base-only review candidates average 1.6 attack rows and 94.6 OOD rows; GDA-driven highs average 1287.6 attack rows and 29.6 OOD rows.

Interpretation boundary: base-high/GDA-low rows are review candidates, not confirmed attacks. The review queue preserves base-detector evidence rather than proving unseen-attack capture.
