# Online Cost Model

## Baseline symbols

- `d = 115`: Kitsune feature dimension.
- `m = 16 or 32`: proposed embedding dimension.
- `R`: number of regions.
- `P`: prototypes per region.
- `k`: top-k routed regions.
- `N = R * P`: total prototypes.

## Single-sample inference

### Feature frontend

Kitsune / AfterImage / netStat frontend is fixed and online-stateful. It is outside this report's optimization scope.

### Embedding

Linear projection:

```text
cost = O(d*m)
```

For `d=115`, `m=16`, this is about 1,840 multiply-adds.

Small MLP with one hidden layer h:

```text
cost = O(d*h + h*m)
```

For `h=64`, `m=16`, this is about 8,384 multiply-adds.

### Prototype lookup

Exact all-prototype lookup:

```text
cost = O(N*m) = O(R*P*m)
```

Examples:

| R | P | m | rough scalar distance ops |
|---:|---:|---:|---:|
| 16 | 32 | 16 | 8,192 |
| 32 | 32 | 16 | 16,384 |
| 128 | 64 | 16 | 131,072 |
| 512 | 64 | 16 | 524,288 |

Top-k routing:

```text
centroid search = O(R*m)
prototype search = O(k*P*m)
```

For `R=512`, `P=64`, `k=3`, `m=16`:

```text
centroid search ~= 8,192
prototype search ~= 3,072
total ~= 11,264 scalar ops
```

This is much cheaper than all-prototype exact search.

## Full dataset scaling

### 10x data

Likely bottlenecks:

- offline materialization / storage;
- metric training pair/triplet sampling;
- prototype update audit.

Online cost remains manageable if prototype budget is fixed per region.

### 100x data

Likely bottlenecks:

- region registry growth;
- pair/triplet mining;
- exact prototype search if `N` grows beyond 10k;
- active-labeling queue management.

Need:

- bounded exemplar memory;
- region merge/retire;
- approximate nearest neighbor index;
- periodic compression.

## When to use FAISS / HNSW

Use exact distance first for medium diagnostic. Switch to ANN only when:

- total prototypes > around 10k;
- query throughput requires sub-millisecond lookup;
- exact top-k region routing becomes a measurable bottleneck.

FAISS is designed for efficient dense vector similarity search and supports L2/dot-product indexing. HNSW is a graph-based ANN method with strong empirical scalability.

Security caveat:

- ANN recall must be audited.
- High-risk conflict samples should have exact-distance fallback.
- ANN index version/hash must be logged.

## Prototype budget policy

Initial:

- ID prototypes: 32-64;
- OOD/stress prototypes: 32-64;
- attack prototypes per region: 16-32;
- max regions in medium diagnostic: <= 8;
- max review budget: <= 5%.

Deployment:

- cap prototypes per region at 64;
- if region grows, compress by k-center/herding;
- preserve boundary exemplars and high-utility support samples;
- retire stale low-utility prototypes;
- merge regions only if cross-region confusion and centroid distance both support merge.

## Online update policy

Online packet processing should not synchronously retrain the metric model.

Recommended:

1. Query-time only:
   - extract 115D;
   - embed;
   - lookup top-k regions;
   - controller decision.
2. Async update:
   - unknown/review samples enter buffer;
   - human/oracle labels selected samples;
   - region registry updates off-path;
   - metric retraining only in scheduled maintenance.

## Main bottleneck forecast

Before full scale:

- metric objective design and role-pure sampling are the bottlenecks, not lookup cost.

At full scale:

- active labeling yield, region memory maintenance, and pair/triplet mining become bottlenecks.

At deployment scale:

- bounded review budget and safe online update become the real bottlenecks.
