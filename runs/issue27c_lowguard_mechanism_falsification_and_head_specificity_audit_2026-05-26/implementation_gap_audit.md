# Implementation Gap Audit

## DevNet-like MLP

The current DevNet-like head is a lightweight weighted MLP classifier. It is not equivalent to full DevNet: it does not implement the original deviation-network objective, reference-score prior, or full method-specific training recipe. It did use OOD_train in P2/P3 through the guarded training matrix, and sample weights were passed to `MLPClassifier.fit` without runtime failure.

## DeepSAD-like center

The current DeepSAD-like head is a center-distance proxy with attack-weighted feature weights. It is not equivalent to full Deep SAD because it does not learn a deep representation or optimize the full Deep SAD objective. Its failure should not be written as "Deep SAD is defeated".

## HistGB

HistGB is a shallow supervised tree baseline with OOD_train negatives in P2/P3 and a validation-only threshold. It does not directly optimize the low-alert tail objective, which likely explains why detection can remain useful while the OOD tail is not controlled.

## RFF Logistic

RFF Logistic was optional in issue27b and is sensitive to scaling/gamma. It is useful as a kernelized linearity probe, not as a strong method claim.

## Protocol-equivalence risks

- Non-LR heads do receive OOD_train guard in P2/P3.
- No final eval selection was found in issue27b traces.
- No direct implementation bug was found for LR or DevNet-like.
- DeepSAD-like shows score/objective mismatch in raw and threshold-only variants, which should be interpreted as proxy-objective weakness rather than a final conclusion about full Deep SAD.
- Proxy implementations are not method-equivalent to full DevNet / Deep SAD, so non-LR conclusions must stay bounded.
