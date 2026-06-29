# issue27cko mechanism frontend v1

## Scope

Fixed detector: C4 four-class HistGB.
Changed input: raw115 vs processed-CSV mechanism features vs raw115+mechanism.
Mechanism features use packet fields and past-only rolling source/file state; processed CSV label is audit-only and not a feature.
Mode: `smoke`.

## Main matrix

| feature set | future hard | same-file hard | sealed attack hard/review | sealed OOD hard/review | sealed OOD group hard max | OOD-stress hard/review |
|---|---:|---:|---:|---:|---:|---:|
| M0_raw115 | 0.9993 | 1.0000 | 0.9910/0.0007 | 0.0027/0.0083 | 0.0027 | 0.0020/0.0053 |
| M1_mechanism_only | 0.9993 | 1.0000 | 0.8723/0.0723 | 0.0000/0.0097 | 0.0000 | 0.0000/0.0007 |
| M2_raw115_plus_mechanism | 0.9900 | 1.0000 | 0.9457/0.0000 | 0.1963/0.0000 | 0.1963 | 0.0100/0.0000 |

## Mechanism extraction audit

| files read | requested rows | computed rows | out-of-bounds rows | seconds |
|---:|---:|---:|---:|---:|
| 10 | 21512 | 21512 | 0 | 220.1 |

## Guardrail

- A useful mechanism frontend must reduce sealed OOD review/hard without hurting future/sealed attack hard detection.
- Lower review alone is not success if it becomes hard OOD false alarm or loses attack retention.
- This run does not use report-only rows for fitting, thresholding, or model selection.
- Full flow/fanout extraction may need HPC because it reads many large processed CSV members from the 23GB Gotham zip.

Runtime seconds: `240.7`.
