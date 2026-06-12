# Support Pool Contract

## Fixed Support Mode

Use this mode to test frozen few-shot generalization. The attack support selector may only read files in `attack_support_candidate_pool`:

`processed/iotsim-air-quality-1.csv`, `processed/iotsim-city-power-1.csv`

Budgets:

- support: 32 / 64 / 128 / 256
- support_val: fixed or proportional development-side split
- attack prototype budget: bounded and reported

Forbidden:

- no `sealed_final_ood`
- no `sealed_final_attack`
- no final/report-only detection, coverage, distance, or score feedback
- no future labels before review

## Active Update Mode

Use this mode only as a separate online diagnostic. Incoming samples first pass a pre-frozen controller. Only after review/oracle confirmation:

- confirmed attack may enter bounded attack region memory
- confirmed benign drift may enter OOD/benign memory
- uncertain samples remain unknown/review, not support

Label budgets to report: 32 / 64 / 128 / 256.

## Data Size Note

The first larger materialization should be bigger than medium but still bounded: target 3M-8M model-ready rows, hard ceiling 10M emitted 115D rows without another explicit confirmation. This is a sanity scale, not full Gotham.
