# Support Selection Method Report

- `random_32shot_baseline`: reused issue16b random support and metrics.
- `kcenter_32shot`: farthest-first k-center in standardized attack train-pool original100 space, initialized at the point nearest the train-pool centroid.
- `diversity_32shot`: seeded farthest-first max-min selection in attack train-pool original100 space.
- `density_aware_32shot`: k-center after excluding the most extreme sparse/dense 10% by local kNN radius, using train-pool features only.
- `stratified_bin_32shot`: uses available stage2 attack bin metadata and allocates support quota across train bins, with k-center selection inside each bin.

All methods are train-pool-only support acquisition rules. Attack eval and final OOD eval are not used for selection.

64-shot sensitivity was not run in this pass to avoid turning the repair test into a budget sweep.
