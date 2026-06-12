# Larger Sanity Size Plan

## Why Not Full Yet

The current strongest system passed a medium diagnostic, but full Gotham contains 35,134,281 processed rows and raw PCAP extraction is materially larger. Jumping straight to full would hide data-contract mistakes behind expensive runtime.

## Recommended First Larger Scale

- target: 3M-8M model-ready Kitsune115 rows
- hard ceiling without another explicit confirmation: 10M emitted rows
- include multiple ID devices and ID calibration files
- include development OOD val and OOD stress
- include sealed final OOD as capped report-only replay
- include fixed support budgets 32/64/128/256
- include active update budgets 32/64/128/256 only in a separate diagnostic
- include dev future attack query and sealed final attack

## Full Corpus Context

- processed CSV files: 78
- all-benign files: 70
- mixed attack files: 8
- total rows: 35,134,281
- benign rows: 12,256,883
- attack rows: 22,869,728

## Go / No-Go Before Larger Replay

Go only if `split_disjointness_audit.csv` is accepted and issue27bx materialization writes sidecar/hash/state logs. No formal benchmark claim is allowed from this contract alone.
