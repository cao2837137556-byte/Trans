# issue27bx4 Data Cleanliness Contract

- No model training, threshold tuning, OOD gate repair, or formal benchmark.
- ID train is fixed to issue27bx3 to preserve train-state semantics and cache validity.
- 500k base rows are exact cache-reuse candidates; 500k new rows are same-role extensions.
- No cross-role fallback is allowed.
- Sealed final OOD and sealed final attack remain report-only and forbidden for fit, threshold, support selection, and model selection.
- Attack roles use malicious PCAP members from the audited attack onset cache, not filename-only benign PCAP pairings.
