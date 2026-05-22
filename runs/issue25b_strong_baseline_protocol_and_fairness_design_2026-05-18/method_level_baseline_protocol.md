# Method-Level Strong Baseline Protocol

## Purpose

Method-level strong baseline comparison tests whether Enhanced LOW-GUARD+ remains competitive against reasonable anomaly detection and few-shot semi-supervised baselines under the same low-alert deployment constraint.

## Baseline Groups

### A. Unsupervised Anomaly Baselines

Methods:

- Isolation Forest.
- OC-SVM.
- LOF optional.

Input:

- Main: source_rich_top64.
- Optional appendix: full_source_rich or original100 if method-native stability requires it.

Supervision:

- No attack supports.
- Fit only on allowed benign training data according to each method's standard use.

Threshold:

- ID calibration + OOD validation at 1% OOD alarm target.

### B. Semi-Supervised / Few-Shot Anomaly Baselines

Methods:

- DevNet-like lightweight.
- DeepSAD-like lightweight.
- RoSAS-like design-only unless implementation is clean and affordable.

Input:

- source_rich_top64 main.

Supervision:

- Same 32 confirmed attack supports.
- Same benign/OOD train-cal-val access as Enhanced LOW-GUARD+.

Threshold:

- ID calibration + OOD validation at 1%.

### C. Nonlinear Tabular Baselines

Methods:

- HistGB shallow.
- Shallow XGBoost-like if available.

Input:

- source_rich_top64.

Supervision:

- Same 32 confirmed attack supports and same benign/OOD data access.

Threshold:

- ID calibration + OOD validation at 1%.

### D. Existing Detector / Internal Baselines

Methods:

- V1 original100 fixed guard LR.
- V2_top32 source_rich fixed guard LR.
- Enhanced LOW-GUARD+ top64 fixed guard LR.
- top64 no guard.
- top64 random32.

Purpose:

- Preserve continuity with the existing evidence chain.
- Quantify representation, support, and guard contributions.

## Main Reporting Principle

Method-level fairness does not require identical input for every method. It requires supervision-consistent input, identical final-eval isolation, and identical low-alert thresholding.
