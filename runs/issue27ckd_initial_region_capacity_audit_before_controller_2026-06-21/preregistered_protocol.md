# issue27ckd Preregistered Protocol

## Question

Can the frozen 512-row initial support bank produce stronger initial attack
regions under the already-selected S3 evidence space when one-medoid
under-expression is removed?

## Frozen Inputs

- issue27cf initial support bank: 385 support-train and 127 support-val rows;
- issue27ck selected evidence space: `S3_bounded_heavytail_family_balanced`;
- issue27ck medium shell scheme and activation gates;
- ID benign train fits the S3 transformation only;
- OOD benign validation participates in qualification;
- OOD stress and certified dev query remain read-only after variant selection;
- sealed final roles are forbidden.

## Preregistered Variants

1. `V0_frozen512_single_medoid`: exact reproduction of issue27ck.
2. `V1_frozen512_two_medoid`: request two train-only medoids per label when
   at least 16 support-train rows exist.
3. `V2_frozen512_adaptive_three_medoid`: request up to three train-only
   medoids, requiring at least eight train rows per fitted cluster.

Medoids are initialized deterministically by farthest-first traversal and
refined using train-only pairwise distances. A requested prototype count is
reduced when any resulting train cluster has fewer than eight rows.

For multi-prototype regions, distance to a label region is the minimum distance
to any prototype assigned to that exact label. Shell radii are fitted to these
minimum train/validation distances.

## Unchanged Activation Gates

An `active_strong` region still requires:

- support train at least 12;
- support validation at least 3;
- true-region uncertain coverage at least 0.80;
- nearest-label consistency at least 0.80;
- at least two provenance sources;
- OOD-val direct core intrusion at most 0.001;
- OOD-val direct core+near intrusion at most 0.01.

## Selection And Stop Rules

A challenger is admissible only if:

- the existing Mirai UDP strong region remains `active_strong`;
- active-strong count does not decrease;
- mean support-val consistency is no more than 0.02 below V0;
- global OOD-val nearest core+near rate increases by no more than 0.02.

The best admissible variant is ranked by active-strong region count, semantic
group count, mean support-val consistency, and lower OOD overlap.

- `GO`: at least one additional region becomes active-strong.
- `DIAGNOSTIC_ONLY`: consistency improves but no additional region qualifies.
- `STOP`: no admissible improvement; next issue may audit bounded candidate
  extension without rewriting the frozen 512 bank.

## Explicit Non-Actions

- no candidate-pool reuse or support-row reselection;
- no controller integration or tuning;
- no learned metric or model training;
- no activation-gate relaxation;
- no sealed-final access;
- no online update, merge, retirement, or promotion logic.
