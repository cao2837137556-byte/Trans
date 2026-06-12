# issue27bx2 Per-file Cache Design

The cache is a production-line accelerator, not a new dataset split.

Required cache artifacts per source file:

- `X_115D.npy`: rows emitted from one PCAP under one state strategy
- `y.npy`: binary labels aligned to emitted rows
- `sidecar.csv.gz`: row id, role, report-only flags, source paths, timestamps, state id
- `numeric_audit.json`: finite rate, NaN/Inf counts, family health
- `source_manifest.json`: source PCAP path/hash, CSV path/hash, schema hash, state strategy

Cache keys are listed in `cache_key_manifest.csv`. A cache hit is valid only when every key input matches.

The next materializer should concatenate per-file caches according to `materialization_v2_quota_plan.csv`; it must not recompute files whose cache keys already match.
