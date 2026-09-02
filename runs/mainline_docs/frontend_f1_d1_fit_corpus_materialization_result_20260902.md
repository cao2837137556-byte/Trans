# Frontend-F1 D1 fit-corpus materialization result (2026-09-02)

## Result

```text
status = F1_D1_FIT_CORPUS_MATERIALIZED
scientific verdict = not opened at this stage
training started = 0
select/viewed/report/FINAL opened = 0
```

Output namespace:

`runs/frontend_f1_d1_fit_corpus_v1_20260902_local`

## Independent post-run verification

All values below were recomputed from the durable output rather than copied
from the runner terminal message.

| Check | Recomputed result |
|---|---:|
| SHA256SUMS members | 4/4 PASS |
| semantic contexts | 12,889 |
| target rows | 18,266 |
| unique target UIDs | 18,266 |
| train contexts / rows | 9,307 / 13,866 |
| internal-val contexts / rows | 3,582 / 4,400 |
| exact reused member checkpoints | 24/24 |
| select targets materialized | 0 |
| viewed/report/FINAL opened | 0/0/0 |

Key durable identities:

```text
fit corpus SHA-256
623d4e0bbec6ddfad4e98c08a9fc90df137e51e7692ff3453ac7f38c5e84097e

manifest SHA-256
748cd9aa98a15d491b6b4b5f7b84d2679c566ca417084fb17e6236227a4e162b

member audit SHA-256
b6ae09363f74f0e970c842b9e54921a154ef36a3f5d7ef640b486ae4bb0e3494

result SHA256SUMS SHA-256
9844053f605b066876a080d01d3fb37af67f78d8df39c18afce4592d7bb82776
```

Materialization cumulative wall time was `829.6873433` seconds. Peak process
working set was `412,626,944` bytes and durable output before final publication
was `3,056,391` bytes, both below the frozen limits.

## Engineering-failure lineage

The first finalization attempt stopped only after 24/24 fresh member replays
because the target plan contains 12,000 legitimate literal `nan` timestamps.
No corpus or scientific verdict was emitted. The failure record is preserved at:

`runs/frontend_f1_d1_fit_corpus_v1_20260902_local_engineering_failure_r1`

The narrow timestamp repair is documented in:

`runs/mainline_docs/frontend_f1_d1_materialization_timestamp_repair_20260902.md`

The successful finalization reused only checkpoints whose marker identities
and content hashes matched exactly. The repair did not reclassify or change any
semantic target.

## Authorization boundary

This result closes fit-corpus materialization only. The one-shot local GRU
training remains a separate user authorization. Select evaluation remains
physically locked until a frozen checkpoint and fit-derived gates exist.
