# clean115 Construction Report

clean115 can be defined mechanically by dropping the index-like first column from `Mirai_dataset.csv`.

- raw rows: `764137`
- raw columns: `116`
- clean columns after dropping col0: `115`
- label rows: `764137`
- NaN count in full scan: `0`
- Inf count in full scan: `0`
- constant column count: `0`
- materialized cache: `False`

The cache was not materialized because the mapping gate has not passed. Creating another >1GB derived matrix before verifying column semantics would add storage churn without improving claim safety.
