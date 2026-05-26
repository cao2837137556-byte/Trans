# Issue27d Next Action

## Recommendation

`issue27d_bounded_representation_and_objective_falsification_for_lowguard_lr_specificity`

## Why this, not deployment robustness yet

issue27b made deployment robustness tempting, but issue27c shows the mechanism question is not fully closed. Before stress-testing deployment assumptions, run a bounded falsification control to separate representation linearization from adapter/objective specificity.

## Minimal run matrix

- Freeze locked bins, top64, kcenter32, and final-eval exclusion.
- Compare original100 vs top64 for LR, DevNet-like, and HistGB only.
- Keep P0/P2/P3; P1 can be diagnostic if cheap.
- Add no new large model and no topK search.
- Report whether non-LR failure persists when representation bias is controlled.

## Slurm

Not needed unless the matrix is expanded beyond the bounded lightweight heads.
