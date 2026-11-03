# Q reference verifier: target preflight verified

Job174233: user-provided sacct COMPLETED/0:0, elapsed00:04:27. Returned archive SHA and all internal seals verified; stderr empty. Target Python3.9.25/NumPy2.0.1/Torch2.5.1. All64 tests PASS; full synthetic chain192updates COMPLETE (synthetic only, no scientific conclusion).

Real cached LEARN766727/DEV179886 passed frozen input checks and exact saved float32 Q replay. Real optimizer updates0, new verifier forwards0, no calibration, no E3 recomputation/PCAP decoding, zero retries, HOLDOUT CLOSED. Evidence: runs/legacy_qref_preflight_verified_v1_20260922/verification.json.

Preflight complete. Next is separately authorized frozen helper/verifier training, CAL and one DEV evaluation; no extra preflight experiment required. No capability improvement demonstrated yet. Original job172780 FAILED and M/C gateFAIL preserved.

Transfer correction: original pull script failed before rsync because Windows backslashes were lost at WSL argument boundary. New pull_preflight_v2.ps1 normalizes slashes and fixes checksum whitespace parsing; actual local WSL path conversion verified. Original sealed delivery preserved; new script is an additive correction. User successfully returned results.
