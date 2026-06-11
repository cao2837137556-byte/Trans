# Temporal Leakage Checklist

## Past-Only Feature Rules

- All temporal features must use `shift(1)` or equivalent past-only construction.
- No current-row label, future row, future score, or future OOD-risk may be included.
- Window state must reset or carry only according to the declared state strategy.
- State transition logs must be materialized for larger sanity.

## Split Rules

Check:

- time-forward split
- source-group disjoint split
- file-disjoint split
- device-disjoint split
- purge/embargo if adjacent windows can leak future information

## Known Medium Limitation

The current medium asset has a single-source limitation for `id_calib`, which restricts full group-disjoint threshold calibration. Larger sanity must include broader ID calibration source groups.

## Red Flags

Block or downgrade claim if:

- fit/select/replay share the same file with adjacent temporal windows and no embargo.
- report-only roles affect threshold, model, support, prototype, or controller choice.
- source/file/device acts as a shortcut.
- past-only features are computed after sorting by a label-derived field.
- temporal gains disappear under source/file disjoint replay.

## Required Output For Future Runs

- `temporal_state_transition_log.csv`
- `temporal_split_audit.csv`
- `past_only_feature_audit.csv`
- `role_access_audit.csv`
- `group_disjoint_replay_summary.csv`

