# Claim Gate

## Target Claim

LOW-GUARD-minimal can remain viable under a pre-registered harder same-dataset holdout when evaluated with a clean low-OOD guarded protocol.

## Reviewer Attack

"The method only works on the current primary split and is just a cost-sensitive LR artifact."

## Expected Evidence

- Harder holdout metrics for original100 fixed guard LR versus original100 plain LR.
- OOD high alarm <= 1% and feasible rate.
- Attack high detection mean/min across main and held-out seeds.
- support_id_provenance.csv and threshold_provenance.csv.

## Positive Interpretation

Only if fixed guard remains feasible and maintains strong attack detection on both pre-registered holdouts should this support Problem B as a strong harder-holdout generalization result.

## Negative Interpretation

If fixed guard keeps OOD alarm low but attack detection drops on a pre-registered holdout, the result is not a method win. It becomes boundary evidence and pushes the paper toward failure analysis, baseline comparison, or measurement/protocol framing.

## Paper Role

Main text only if the result is clearly positive and provenance is clean. Otherwise appendix or limitation/failure analysis.

## Stop Rule

If both pre-registered holdouts fail, stop adapter upgrades and analyze generalization failure before running more model variants.
