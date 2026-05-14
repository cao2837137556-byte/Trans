# Applicability Lifecycle Interpretation

This run tests a conservative lifecycle interpretation: dA can remain a cold-start unsupervised detector, while a lightweight few-shot adapter can be added after high-purity attack positives become available.

The experiment should not be interpreted as replacing dA. It asks whether dA scores, alone or combined with original100 features, are useful inputs for target-aligned adaptation under the guarded low-OOD protocol.
