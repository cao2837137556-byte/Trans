# Remaining Technical Debt

## Data Contract

- Rebuild larger/full dev/report/final contracts.
- Create newly sealed final OOD and final attack roles before formal benchmark.
- Ensure report-only data is not repeatedly used for protocol design.
- Broaden ID calibration source groups.

## OOD Stress

- Broaden OOD stress across devices, time blocks, benign workload patterns, and background-load regimes.
- Check whether OOD stress covers final OOD tails without peeking at final.

## Support and Active Update

- Define initial support budget.
- Define active-labeling candidate selection without future-label leakage.
- Define bounded attack memory update, merge, split, and retire.
- Define label-noise handling.

## Temporal / Interaction Evidence

- Continue past-only leakage audits.
- Build mini flow-interaction metadata if no-parent OOD-risk remains overbudget.
- Avoid calling the current lightweight temporal layer a true causal layer.

## Controller

- Mature `hard / suppress / review / unknown` rules.
- Prevent review from absorbing difficult cases without budget.
- Add per-bucket and time-to-detect diagnostics.

## Online Cost

- Bound prototype and region memory.
- Define temporal state retention.
- Estimate full-scale throughput.
- Consider HNSW/FAISS only if exact lookup becomes costly.

## Method Presentation

- Stabilize method name.
- Keep claim boundary strict.
- Do not write current medium diagnostic as formal success.

