# Model Update Contract v1

## Inputs

- positive attack rows: one frozen `support_train_view_vN`;
- validation attack rows: frozen `support_val_view_v1` until a separately certified replacement exists;
- ID and OOD benign development roles under their existing access restrictions;
- one frozen training and weighting configuration.

## Required Sequence

1. Freeze archive cutoff and candidate pool hash.
2. Freeze a certified production budget profile.
3. Materialize a candidate support-train view without changing its parent.
4. Freeze positive/ID/OOD sampling and label weighting.
5. Train a candidate binary attack head.
6. Evaluate low-FPR attack recall, AUROC/AUPRC, per-label recall, benign-OOD alarms, future-query behavior, unknown/review rate, and old-label forgetting.
7. Publish only after explicit non-regression and release approval.

## Prohibitions

- support-val rows cannot silently migrate into training;
- archive size does not define training-view size;
- label regions cannot force unknown traffic into known labels;
- no sealed-final tuning;
- a failed candidate view remains auditable but does not replace the active view.
