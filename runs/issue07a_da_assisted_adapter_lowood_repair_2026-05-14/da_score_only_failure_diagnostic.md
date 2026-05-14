# dA Score-only Failure Diagnostic

This diagnostic does not rerun any model. It inspects the dA score distributions used by issue07a.

## Key numbers

- OOD train dA score median: 0.054762; q99: 1631.045971; max: 4325319.189618.
- Attack eval dA score median: 0.126407; q99: 16.306046; max: 59302.630032.
- 16-shot selected support union dA score median: 0.177631; q99: 29.052042.
- 32-shot selected support union dA score median: 0.204857; q99: 3.414994.

## Interpretation

The one-dimensional dA score is heavily affected by the OOD benign tail. Some OOD benign negatives have extremely high dA anomaly scores, while few-shot attack supports are sparse and do not by themselves define a stable attack-oriented boundary in this one-dimensional space. Therefore `da_score_only_fewshot_lr` failing is not evidence that the adapter script used the wrong split. It indicates that the raw dA score alone is not sufficient for target-aligned repair under this guarded low-OOD protocol.

The `original100_plus_da_score` adapter remains strong because original100 carries the high-dimensional target-alignment signal; the added dA score does not provide a measurable improvement over original100-only in this run.
