# issue27ck Validation Report

Status: `PASS_LIMITED_GO`

- Four preregistered spaces executed: S0, S1, S2, S3.
- Support bank remained fixed at 385 train and 127 validation rows.
- No support reselection, region split, model training, controller tuning, or sealed-final access occurred.
- Evidence-space selection used only support-val and OOD-val.
- OOD-stress and certified dev query were read only after the selection artifact was written.
- A complete deterministic rerun reproduced the qualification, registry, OOD, query, and result hashes.

Selected space: `S3_bounded_heavytail_family_balanced`.

Qualified region: `Mirai UDP Flooding`.

- support-val nearest-label consistency: `1.0`;
- support-val uncertain-shell coverage: `0.95`;
- OOD-val direct core intrusion: `0.0`;
- OOD-val direct core+near intrusion: `0.00025`;
- OOD-stress direct core intrusion: `0.0008217391`;
- OOD-stress direct core+near intrusion: `0.0086217391`;
- dev-future-query nearest-label match: `1.0`;
- same-file time-forward nearest-label match: `1.0`.

This is a limited registry result. It does not authorize strong evidence for the other nine labels or broad deployment claims.
