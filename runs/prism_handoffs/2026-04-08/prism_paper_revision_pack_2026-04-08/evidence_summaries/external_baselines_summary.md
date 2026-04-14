# Minimal External Baseline Summary

- Data: original-frontend 100D + stronger OOD protocol.
- Seeds: `101/202/303` for stochastic baselines.
- Unsupervised baselines train only on ID benign fit split.
- RandomForest is an attack-assisted upper-bound reference: trained on ID benign plus stage2 mixed/boundary attack; high-purity attack remains evaluation. It is not a fair unsupervised deployment baseline.
- All fixed thresholds use ID benign q99.

## Fixed q99 Aggregate

| method | category | OOD alarm mean +/- std | high-purity detection mean +/- std | AUC attack-high vs OOD-eval |
|---|---|---:|---:|---:|
| dA default | existing reference | 0.1322 +/- 0.0051 | 0.8014 +/- 0.0167 | 0.8096 |
| transformer tailreg default | existing reference | 0.1414 +/- 0.1153 | 0.3740 +/- 0.2244 | 0.5932 |
| latent log-weighted | existing reference | 0.2161 +/- 0.0549 | 0.6353 +/- 0.1175 | 0.7327 |
| IsolationForest | external unsupervised | 0.4069 +/- 0.1343 | 0.5750 +/- 0.0533 | 0.6014 |
| OneClassSVM | external unsupervised | 0.8979 +/- 0.0000 | 0.9706 +/- 0.0000 | 0.7827 |
| LOF novelty | external unsupervised | 0.9741 +/- 0.0000 | 0.8759 +/- 0.0000 | 0.4488 |
| RandomForest mixed-attack upper-bound | supervised upper-bound | 0.9996 +/- 0.0006 | 1.0000 +/- 0.0000 | 0.9998 |

## det50 Aggregate

| method | OOD alarm mean +/- std | high-purity detection mean +/- std |
|---|---:|---:|
| RandomForest mixed-attack upper-bound | 0.0000 +/- 0.0000 | 0.5042 +/- 0.0028 |
| dA default | 0.0754 +/- 0.0008 | 0.5017 +/- 0.0010 |
| OneClassSVM | 0.0754 +/- 0.0000 | 0.5020 +/- 0.0000 |
| latent log-weighted | 0.1319 +/- 0.0749 | 0.5010 +/- 0.0009 |
| IsolationForest | 0.2702 +/- 0.1630 | 0.5009 +/- 0.0004 |
| LOF novelty | 0.6297 +/- 0.0000 | 0.5004 +/- 0.0000 |

## Interpretation

- The simple unsupervised baselines do **not** undermine the stronger OOD story. Under fixed q99, dA remains substantially more deployment-stable than IsolationForest, OneClassSVM, and LOF.
- OneClassSVM and LOF can raise detection, but only by alarming on most OOD benign traffic. That is not a usable operating point.
- RandomForest is a useful sanity/upper-bound reference: it has very high ranking AUC, but because it uses attack labels and still has fixed q99 alarm near 1.0, it cannot be used as a fair main baseline.
- This supports the claim that the stronger OOD fixed-threshold setting is nontrivial; common off-the-shelf baselines do not simply solve it.
- For the Transformer path, the result does not fix the current problem. It mainly reduces A-tier baseline risk and confirms that our remaining bottleneck is Transformer latent tail stability.

## Next Decision

- Do not replace the Transformer work with these baselines.
- Keep dA as the main stable deployment reference.
- If continuing model work, target latent covariance-tail stability directly rather than another decision-rule sweep.
- If strengthening paper evidence, add one deep baseline next: `LSTM-AE` or `Deep SVDD`.
