# Fixed context-model evaluation

See EXECUTION_AUTHORIZATION.json and DELIVERY.json. Current user authorization starts PREFLIGHT, then CONTEXT, AB and EDGE sequentially. Engineering failures stop; scientific failures never select models or trigger tuning. Large artifacts stay on HPC.

Local regression: 1,312,808 frozen A/B C5 decisions verified. This does not replace the same-runtime real preflight.
