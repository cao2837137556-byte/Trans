# Global Candidate Status

Status: `unified_candidate`.

Reason: V2_top64 beats or matches V1 on primary low-OOD while keeping OOD <=1%, and hard settings remain >=0.90 detection.

Key primary deltas:

- V2_top64 - V1 detection: `0.018182`.
- V2_top64 - V1 OOD alarm max: `0.000100`.
- V2_top64 - V2_top32 detection: `0.023273`.
- V2_top64 - V2_top32 OOD alarm max: `-0.011900`.

This status is still pre-locked-validation. It only says whether top64 deserves locked validation as a unified candidate.
