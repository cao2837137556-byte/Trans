# Reviewer Defense: Model-Specific Objectives

## Q1: Did you just rerun a model zoo?

No. issue27d first defines a common LOW-GUARD adapter interface, then runs a bounded 3-seed smoke over five pre-specified heads and two representations. The goal is mechanism falsification, not broad model search.

## Q2: Did non-LR heads get model-specific objectives?

Yes, but only lite versions. DevNetScore optimizes a scalar score, DeepSADLite optimizes normal-compact / attack-far distances, HistGB is conservative and OOD-weighted, and PrototypeMargin uses explicit ID/OOD/attack margins.

## Q3: Was final eval used for target or config selection?

No. Configuration selection used support validation and OOD validation only. Final OOD eval and attack eval are report-only.

## Q4: Does this prove LOW-GUARD is head-agnostic?

No. Primary verdict is `lowguard_plus_plus_candidate_found_with_model_specific_objective`. This issue can support bounded interface/objective evidence, not a universal head-agnostic claim.

## Q5: Why include original100?

original100 is a representation-control probe for the issue27c concern that top64 may linearize the task and favor LR.

## Q6: What happens next?

`issue27e_formal_validation_for_lowguard_plus_plus`.
