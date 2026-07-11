# issue27ckaz_context_causality_contract_audit_v1_2026-07-11

overall_pass: `True`

## Contract

- label excluded from raw frontend: `True`
- future packet invariant: `True`
- raw-label invariant: `True`
- past packet affects state: `True`
- strict held-family fit/select exclusion: `True`
- cached frontend label-free: `True`

## Deliberate online policy

Past packets of any eventual truth class may affect history, but their labels cannot. This is deployment-realistic and is not ground-truth cleaning. It must be analysed separately as history-contamination robustness, never repaired with true labels.
