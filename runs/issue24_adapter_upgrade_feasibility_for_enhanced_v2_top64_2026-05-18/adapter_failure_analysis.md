# Adapter Failure Analysis

- `A1_low_fpr_weighted_lr` does not improve locked mean detection over LR.
- `A2_linear_svm_margin` exceeds the 1% OOD budget and cannot replace LR.

Complex adapters are not promoted unless they improve locked mean and worst-case detection while keeping OOD <=1%.
