# Fairness Audit Report

## Attack Support Budget

All semi-supervised and few-shot baselines use the same kcenter32 confirmed attack support budget as Enhanced LOW-GUARD+.

## Unsupervised Baselines

Isolation Forest and OC-SVM do not use attack supports for model fitting or hyperparameter selection. They use the frozen top64 input protocol and the same OOD validation threshold.

## Final Eval Isolation

No baseline uses final OOD eval or final attack eval for hyperparameter selection, threshold calibration, support selection, feature selection, or model selection.

## Threshold Consistency

Every method uses ID calibration + OOD validation at the official 1% OOD alarm target.

## Caveat

Unsupervised baselines receive the same frozen top64 representation protocol, which is generous to them relative to a fully native unsupervised setting. This should be disclosed rather than hidden.
