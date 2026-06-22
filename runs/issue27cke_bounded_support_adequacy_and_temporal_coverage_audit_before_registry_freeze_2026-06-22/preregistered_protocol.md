# issue27cke Preregistered Protocol

## Objective

Test whether a bounded, versioned extension of the legal support candidate pool
improves initial S3 attack-region adequacy without rewriting
`initial_support_bank_v1`, relaxing activation gates, or tuning the controller.

## Scientific Status Of Existing Query Roles

`same_file_time_forward_dev_query_exact` and `dev_future_attack_query_exact`
were already inspected in issue27ck and issue27ckd. They are therefore reused
development diagnostics in this issue, not fresh validation and not evidence
that can certify a registry for deployment.

The extension variant is selected only with:

- support candidates and support-train;
- the frozen issue27cf support-val rows;
- OOD-benign validation.

Existing query roles and OOD stress are evaluated only after the selected
variant is frozen. Sealed final roles remain forbidden.

## Frozen Components

- original issue27cf 512 rows and train/validation membership;
- `S3_bounded_heavytail_family_balanced`;
- two train-only medoids where the minimum eight-row cluster rule permits;
- issue27ck activation gates and medium shell definition;
- ID-benign transformation fitting and role order.

## Extension Variants

1. `B0_frozen512_two_medoid`: issue27ckd V1 baseline.
2. `E64_nested_source_time_balanced`: B0 plus 64 unused legal candidates.
3. `E128_nested_source_time_balanced`: B0 plus 128 unused legal candidates,
   containing every E64 row.

All extension rows are support-train-only development candidates. They do not
replace, re-partition, or mutate any original support row.

## Allocation And Selection

- E64 allocates at least four and at most eight rows per exact label.
- Remaining E64 rows are allocated deterministically by candidate-pool size
  relative to existing support-train count.
- E128 doubles each E64 per-label allocation, guaranteeing nestedness.
- Within each label, unused candidates are divided by provenance source and
  timestamp quartile within that source.
- Selection cycles across source-time strata before taking additional rows
  from a stratum.
- Inside each stratum, deterministic S3 k-center ordering begins at the
  within-stratum centroid medoid.
- No OOD, query, stress, or final row participates in support selection.

## Static Admissibility And Ranking

A challenger is admissible only if:

- Mirai UDP remains static `active_strong`;
- active-strong count does not decrease from B0;
- mean support-val consistency is no more than 0.02 below B0;
- global OOD-val nearest core+near rate increases by no more than 0.02.

Admissible variants are ranked by:

1. active-strong region count;
2. active-strong semantic-group count;
3. mean support-val label consistency;
4. lower OOD-val overlap;
5. smaller extension budget.

## Interpretation

- Existing query diagnostics cannot authorize registry freeze.
- A static gain plus historical-query improvement is `promising`, not
  deployment certification.
- No static gain stops this bounded extension recipe.
- Any future registry freeze requires a newly reserved or newly materialized
  temporal holdout that has not influenced protocol development.

## Explicit Non-Actions

- no controller integration or tuning;
- no learned evidence space or model training;
- no activation-gate relaxation;
- no sealed-final access;
- no online insertion, merge, split, retirement, or promotion;
- no claim that the extension is part of the deployed initial bank.
