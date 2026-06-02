# Split Source Policy Report

- ID/OOD/final OOD rows use only preregistered benign split files.
- Attack files are never used for ID/OOD/final OOD, even if they contain benign prefix rows.
- Attack support/eval rows start at confirmed first attack timestamps; pre-onset packets only update frontend state.
- No model metrics were computed.
