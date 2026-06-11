# Online Cost Model

## Per-Sample Pipeline

```text
packet
-> Kitsune115 update/extract
-> attack score
-> OOD-risk score
-> prototype / region lookup
-> temporal state update
-> controller decision
```

## Complexity

- 115D frontend: online state update, already required by Kitsune-style pipeline.
- attack head: small tree/logistic-style inference, `O(model_size)`.
- OOD-risk head: small tree/logistic-style inference, `O(model_size)`.
- prototype lookup: `O(num_prototypes * dim)` if exact.
- temporal state update: `O(num_windows)` per source/role key.
- controller: constant time.

## Current Medium Scale

Medium diagnostics are small enough for exact prototype lookup and simple in-memory temporal state.

## Larger / Full Scale Risks

If full data expands by 10x or 100x:

- prototype lookup can become expensive if memory grows unbounded.
- source-level temporal state can grow with number of active hosts/flows.
- full interaction graph features can become the bottleneck.

## Budget Rules

Pre-declare:

```text
prototype_budget_per_bank
attack_region_budget
benign_region_budget
temporal_window_sizes
state_retention_horizon
max_review_rate
max_unknown_buffer_size
```

## Scale-Up Options

- top-k region routing
- prototype compression
- region merge/retire
- HNSW/FAISS-style approximate nearest neighbor search
- mini flow-interaction graph before full GNN

Do not introduce expensive graph models until the mini interaction graph demonstrates value.

