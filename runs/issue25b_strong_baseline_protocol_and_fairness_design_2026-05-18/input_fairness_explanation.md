# Input Fairness Explanation

## Adapter-Level Baselines Share Source_Rich Top64

Adapter-level comparisons ask whether fixed guard LR is enough once the representation is fixed. Therefore all adapter baselines must use selected_source_rich_top64, the same kcenter32 supports, and the same low-alert threshold protocol.

## Representation Ablation Intentionally Changes Input

Representation ablation tests the representation claim. It must compare original100, top32, top64, full_source_rich, no_guard, and random support variants under the same adapter and threshold protocol. Different inputs are the variable being tested, not an unfairness.

## Method-Level Baselines May Use Method-Native Variants

Method-level fairness is not identical-input fairness. Some methods are defined as unsupervised, some as few-shot anomaly supervision, and some as nonlinear tabular learners. A fair comparison gives each method its reasonable input and supervision budget while enforcing the same final-eval isolation and low-alert threshold.

## Unsupervised Baselines Do Not Receive Attack Supports

Isolation Forest, OC-SVM, and LOF are unsupervised anomaly baselines. Giving them attack supports would change their learning setting and create an artificial semi-supervised variant. They should instead receive reasonable feature input and the same OOD validation threshold protocol.

## Semi-Supervised Baselines Receive 32 Attack Supports

DevNet-like, DeepSAD-like, shallow supervised tabular methods, and Enhanced LOW-GUARD+ all use limited attack evidence. They should receive the same 32 confirmed attack supports to keep supervision budget fair.

## Unified Low-Alert Threshold

Every method must satisfy the same deployment constraint: threshold selected by ID calibration + OOD validation at 1% OOD alarm target. This is more important than forcing every method to use identical input, because the paper's problem is low-alert adaptation under benign-OOD drift.

## Final Eval Isolation

Final eval isolation is the strongest fairness rule. Any method that sees final OOD eval or final attack eval during hyperparameter selection, threshold calibration, support selection, feature selection, or architecture selection must be excluded from main comparison.
