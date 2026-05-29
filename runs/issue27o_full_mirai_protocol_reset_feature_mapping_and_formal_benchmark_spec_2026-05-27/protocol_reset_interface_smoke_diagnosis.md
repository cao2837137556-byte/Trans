# Protocol Reset Interface Smoke Diagnosis

Smoke status: `ran`

The smoke uses only `anonymous_clean115_all`. It does not use restored115_common100 or extra15 because those mappings remain blocked. It is not formal validation and does not support a main claim.

The smoke verifies that:

- the anonymous clean115 matrix can feed LOW-GUARD-style heads;
- thresholding uses ID calibration + OOD validation only;
- final OOD and attack eval are report-only;
- a collapse-prone baseline can be included under the same interface.
