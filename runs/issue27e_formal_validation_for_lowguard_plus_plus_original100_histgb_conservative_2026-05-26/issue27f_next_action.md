# Issue27f Next Action

## Recommendation

`issue27f_candidate_config_freeze_and_formal_validation_for_original100_histgb_conservative`

## Goal

Recover a formal candidate by freezing exactly one original100 HistGB-Conservative config before any full final-eval reporting.

## Recommended freeze rule

Use only issue27d selection trace fields:

1. OOD validation feasibility under the candidate target.
2. support validation detection / margin.
3. simplicity and lower target alarm as tie breakers.
4. no final OOD eval or attack eval.

Then run the full seeds locked validation for the frozen config.

## Not recommended

- Do not choose by issue27d final locked detection.
- Do not run both configs and pick the better final result.
- Do not change representation, add new models, or tune topK/support.
