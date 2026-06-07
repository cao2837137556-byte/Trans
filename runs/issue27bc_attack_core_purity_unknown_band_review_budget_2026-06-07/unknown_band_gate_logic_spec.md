# Unknown-Band Prototype Gate Logic

This diagnostic is a medium-only mechanism test, not a formal benchmark.

The gate uses a raw attack score plus three-bank prototype evidence:

- ID prototype bank and OOD/stress prototype bank represent known benign and benign drift regions.
- Medium and active-heavy attack prototype banks represent confirmed development-side attack regions.
- Pseudo-query attack rows are held out by file from development support pools to reduce support-val overfitting.

Decision states:

- `hard_alarm`: raw attack alarm and pure attack-core evidence.
- `suppress`: weak raw attack alarm and pure benign/OOD-core evidence.
- `review_conflict`: attack and benign/OOD cores both close.
- `review_unknown`: raw alarm is outside both cores or otherwise ambiguous.
- `review_overflow_no_alarm`: review candidate beyond the frozen budget.
- `no_alarm`: raw attack alarm is absent.

Final OOD, medium attack eval, and dev-heavy query are report-only replay roles and never tune thresholds, prototype radii, purity labels, review budgets, or gate parameters.
