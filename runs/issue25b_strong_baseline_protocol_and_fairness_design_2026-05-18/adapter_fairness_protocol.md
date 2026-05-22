# Adapter-Level Fairness Protocol

## Purpose

Adapter-level fairness answers a narrow question: under the same representation and the same few-shot evidence, does any adapter outperform the fixed OOD guard LR used by Enhanced LOW-GUARD+?

This layer protects against the reviewer claim that the result is only due to using a weak adapter comparison.

## Fixed Inputs

- Feature input: selected_source_rich_top64.
- Attack support budget: the same kcenter32 confirmed attack supports as Enhanced LOW-GUARD+.
- Benign data: same ID benign train/calibration and OOD benign train/validation splits.
- Threshold protocol: ID calibration + OOD validation at 1% OOD alarm target.
- Final evaluation: final OOD eval and attack eval are report-only.

## Required Adapter Baselines

- Guarded LR: main Enhanced LOW-GUARD+ adapter.
- HistGB / shallow tree: shallow nonlinear tabular adapter.
- DevNet-like lightweight adapter: few-shot anomaly supervision with same 32 attack supports.
- DeepSAD-like lightweight adapter: semi-supervised anomaly objective with same 32 attack supports.

## Reference-Only Adapter Results

The following have already been explored and should be cited as reference or appendix rather than rerun as new search unless reproducibility requires it:

- Weighted LR from issue24.
- Linear SVM from issue24.
- V1/V2 residual fusion from issue24c.

## Hyperparameter Rules

- Hyperparameters are selected only from train/cal/val.
- No final OOD eval or final attack eval may be used to choose model class, tree depth, learning rate, epochs, early stopping point, SVM margin setting, or regularization.
- Every candidate must be thresholded by the same 1% OOD validation protocol after training.
- If an adapter cannot expose a scalar anomaly/attack score usable for OOD validation thresholding, it is not eligible for main comparison.

## Interpretation

- If a stronger adapter wins under this protocol, it indicates adapter capacity matters beyond representation.
- If no adapter wins, fixed guard LR remains justified as a lightweight, stable, low-alert adapter.
- A win must improve locked mean or min detection without exceeding 1% final OOD alarm and without relying on final-eval selection.
