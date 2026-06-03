# Issue27ar Next Action

Recommended next task: `issue27ar_balanced_fit_and_threshold_debug_without_final_eval`.

Do not go to full benchmark yet. First test bounded fixes that do not use final OOD or new heldout for selection:

- fit balance audit: normal downsampling or sample weights using only ID train + support_train;
- score-direction and proba-column lock;
- threshold debug using ID/OOD/support_val only;
- keep new heldout report-only for one-pass diagnostic after pre-registered choices.
