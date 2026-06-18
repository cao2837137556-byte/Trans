# issue27ck Next Action

Recommended next issue:

`issue27ck_kitsune115_region_geometry_failure_anatomy_and_evidence_space_repair`

## Purpose

Repair the evidence space before attempting region activation again.

## Scope

1. Audit feature-family contributions and heavy-tail behavior for:
   - `MI_dir`;
   - `H`;
   - `HH`;
   - `HH_jit`;
   - `HpHp`.
2. Test a small preregistered set of non-learned, provenance-safe transformations:
   - ID-fit signed `log1p` for heavy-tailed magnitude/covariance features;
   - ID-fit winsorization or bounded quantile scaling;
   - family-balanced distance aggregation;
   - optional removal/downweighting of numerically degenerate dimensions.
3. Keep the issue27cf support selection fixed.
4. Keep issue27ch dev query and OOD stress read-only.
5. Re-run only geometry qualification gates, not detector performance.

## Forbidden

- learned embedding or attack-head training;
- support reselection;
- region split/merge execution;
- radius tuning against dev query;
- controller work;
- sealed final access.

If no small non-learned repair yields stable support-val structure with low OOD overlap, the next route should explicitly consider a learned attack-evidence representation in a separate issue.
