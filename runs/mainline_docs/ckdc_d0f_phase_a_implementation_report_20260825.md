# CKDC D0-F Phase A implementation report

**Date:** 2026-08-25  
**Scope:** implementation and pre-execution validation only  
**FROZEN contract:** `ckdc_d0f_m7_certificate_provenance_preregistered_20260825.md`  
**Contract SHA-256:** `534e0cd4a0617dacbc37ce72e0a6ccad9b138438c7c68c48386edb48b5c93fc1`

## Implementation identities

- `repo/ood/issue27ckdc_d0f_certificate_phase_a_v1.py`  
  SHA-256 `501b7b67cb71392fdac8ec5ab14d1280063ce2ed9a0069062f5c5ad91c39e990`
- `repo/ood/issue27ckdc_d0f_certificate_phase_a_contract_tests_v1.py`  
  SHA-256 `1080d66a3ca0e3638dc9bdbe76832d91e84429ea2d2e4eb98c7271a5b95624ec`

The executable exposes only Phase-A input paths. It contains no Phase-B input argument or report
score filename. Before reading rows it verifies the FROZEN contract, CKDA contract, fit/select
plan, threshold marker, CKBW predictions, and committed CKDC D0 legal-select identity.

## Input and decision guards

- exact 7,069-row denominator and role counts (`4000 + 3000 + 69`);
- exact UID one-to-one joins and role/source/family/label agreement;
- CKBW duplicate held-view invariance before UID deduplication;
- four frozen D0 quadrant sentinels reproduced;
- P2 hard decisions reproduced from the frozen P2 threshold;
- literal Option-A truth table and exact `<=` tail-normal boundary;
- ten conjunctive Phase-A clauses, including AND/M7 non-equivalence;
- fail-closed handling, atomic output directory, complete `SHA256SUMS`, and no scientific verdict
  after engineering failure;
- Python 3.9 AST parsing for executable and test suite.

The D0 CSV and source CKBW table differ on 79 tail-score rows only at CSV binary64 round-trip
precision (maximum absolute difference `3.3881317890172014e-21`, maximum relative difference
`2.0989161525869835e-16`). The implementation permits only `rtol=5e-16, atol=0`, records the
observed differences, then consumes the source CKBW values. Threshold and Boolean decisions remain
exact.

## Validation

`python repo/ood/issue27ckdc_d0f_certificate_phase_a_contract_tests_v1.py`

Result: **35/35 PASS**.

The suite includes a full real-input end-to-end run into a temporary directory followed by
complete output-hash readback. That rehearsal output is deleted and is not a scientific result.

## Authorization boundary

The user explicitly authorized Phase-A implementation and execution after Kimi freeze review
`b9895a1`. This implementation does not authorize or implement Phase B, does not open report or
FINAL material, does not open PCAP, and performs no training or fitting.
