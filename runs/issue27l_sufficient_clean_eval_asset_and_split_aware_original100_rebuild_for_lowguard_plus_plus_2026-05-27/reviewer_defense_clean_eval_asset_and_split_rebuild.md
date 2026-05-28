# Reviewer Defense: Clean Eval Asset And Split Rebuild

## Why did you not run the model immediately?

Because the best candidate has enough rows but is not yet claim-clean. Running a model before prior-use and split-aware feature-state checks would create a tempting but unsafe result.

## Is future bin9 enough?

No. It has only 208 attack rows and remains disallowed as stand-alone formal validation.

## Did you find a better candidate?

Yes. The extended unused-segment candidate exists, but the higher-priority route is now the full Mirai labeled feature dataset: 764,137 rows with 121,621 benign and 642,516 attack labels. It needs feature compatibility and prior-use auditing before frozen LOW-GUARD++ evaluation.

## Does this mean LOW-GUARD++ failed?

No. This is a data/provenance gate, not a method failure.
