# Active Update Boundary v1

Active update is not executed in issue27ce.

## Current Status

`active_update_status = pending_forbidden_until_explicit_issue`

## Frozen Boundary

Active update may only be opened by a later issue that defines:

- source of unlabeled or analyst-labeled samples;
- whether labels are simulated or real;
- label budget;
- region insertion rule;
- region merge/split rule;
- impact on support train/validation separation;
- whether prior final/report-only roles remain sealed.

## Current Prohibitions

- Do not use sealed final attack as an active-labeling pool.
- Do not use sealed final OOD as an active-labeling pool.
- Do not use report-only attack outcomes to update regions.
- Do not reuse unselected candidates for active update without a new issue and new manifest.
- Do not update the support bank online during formal replay unless the protocol explicitly permits it before final evaluation.

