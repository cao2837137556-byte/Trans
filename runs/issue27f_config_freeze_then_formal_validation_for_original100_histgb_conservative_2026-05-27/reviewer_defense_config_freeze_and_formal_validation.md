# Reviewer Defense: Config Freeze And Formal Validation

## Q1: Was the HistGB config picked using final eval?

No. The config was frozen before full final-eval reporting using only issue27d support-validation and OOD-validation traces.

## Q2: Why choose `histgb_d2_lr005_l2p1_ood4_sup4_t0050`?

Both candidate configs passed the primary 0.0075 validation feasibility count. `histgb_d2_lr005_l2p1_ood4_sup4_t0050` then had strictly safer OOD validation alarm/tail, better support validation detection, and the more conservative 0.005 threshold target.

## Q3: Was the full validation run after freezing?

Yes. The full locked seeds `42..51` and locked bins `5/6/7/8` were evaluated after the freeze.

## Q4: Does this prove external or temporal generalization?

No. This is locked within-dataset formal validation only.

## Q5: What is the decision?

`lowguard_plus_plus_formal_validated`.
