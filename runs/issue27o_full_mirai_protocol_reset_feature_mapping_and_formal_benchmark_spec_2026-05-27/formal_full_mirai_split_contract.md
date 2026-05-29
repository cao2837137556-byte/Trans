# Formal Full Mirai Split Contract

Split: `full_mirai_protocol_reset_row_order_v1`

This is not temporal, not capture-disjoint, and not external. It is a declared within-dataset protocol-reset split.

Rules:

- final OOD eval and attack eval are report-only.
- OOD validation is used only for threshold/validation feasibility.
- attack support is selected only from the attack support pool.
- all models and baselines must be retrained under this exact split.
- `my_gold` overlap is handled by declaring issue20-27n exploratory and rerunning all methods from scratch. It does not make full Mirai external or unseen.
