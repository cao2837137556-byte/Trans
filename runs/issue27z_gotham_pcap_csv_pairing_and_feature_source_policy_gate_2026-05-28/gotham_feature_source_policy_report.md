# Gotham Feature Source Policy Report

- `frame.time`: ordering, purge, split, timestamp pairing, and audit only; never raw model input.
- IP/MAC fields: source/device inference, pairing, and artifact audit only; default excluded from main model input.
- ports/protocol: diagnostic-rich only until a later shortcut audit; not default main-claim inputs.
- file/device/source/path fields: split and audit only; never model inputs.
- label/attack_type: training/evaluation targets only; never input features.
- strict_content_policy keeps only lower-risk numeric packet/header fields as candidates, and still requires a feature-interface audit before model execution.
