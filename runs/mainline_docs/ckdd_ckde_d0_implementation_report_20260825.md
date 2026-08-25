# CKDD / CKDE D0 Implementation Report (2026-08-25)

Status: `IMPLEMENTED_AND_LOCALLY_VALIDATED`

## 1. Authorization and scope

The user explicitly authorized both frozen count/audit-only D0 protocols:

- CKDD: `ckdd_d0_constrained_attack_head_retraining_feasibility_preregistered_20260825.md`
  (`0c33a0eca009242238910dffa004b8cec1fedc39b5e77f0e1be05e5b7850eb7a`)
- CKDE: `ckde_d0_benign_commissioning_identifiability_preregistered_20260825.md`
  (`1f36d0dba81e676af1a2bd29436e4fdf90e85642301cf30a9ca09af751f823a1`)

The implementation does not authorize or perform CKDD training, CKDE D1 calibration,
report-score opening, FINAL access, PCAP decoding, downloads, or HPC submission.

## 2. Implemented programs

- `repo/ood/issue27ckdd_d0_feasibility_audit_v1.py`
- `repo/ood/issue27ckdd_d0_feasibility_audit_contract_tests_v1.py`
- `repo/ood/issue27ckde_d0_identifiability_audit_v1.py`
- `repo/ood/issue27ckde_d0_identifiability_audit_contract_tests_v1.py`

Both implementations pin the frozen contract and every consumed input by SHA-256,
fail closed on identity or schema drift, write into isolated result directories, and
remove scientific verdicts on engineering failure. All four files parse under the
Python 3.9 grammar.

## 3. Contract validation

- CKDD: 19/19 tests PASS.
- CKDE: 18/18 tests PASS.
- Combined: 37/37 tests PASS.
- Both result `SHA256SUMS` manifests validate completely.

The test suites cover contract hashes, Python 3.9 compatibility, exact input
identities, forbidden report/FINAL inputs, live count/verdict reproduction,
source/session split gates, output hashes, and failure-without-verdict behavior.

## 4. Boundary audit

Observed execution counters:

| Boundary | CKDD | CKDE |
|---|---:|---:|
| FINAL files opened | 0 | 0 |
| PCAP files opened | 0 | 0 |
| report score files opened | 0 | 0 |
| training / optimizer steps | 0 | 0 |
| fitted thresholds / parameters | 0 | 0 |

CKDE additionally read zero row labels and zero attack-family columns. CKDD used
only the already-frozen fit/select representation and state needed for first-order,
optimizer-free diagnostics.

## 5. Transparent schema-inspection incident

After both protocols were frozen, a manual command intended to print only the
schema of `ckda_d1_report_plan.csv` also displayed its first data row. That file
mixes identity fields and score fields. The row was not used to define, modify, or
select any D0 rule, threshold, partition, or verdict. The formal D0 programs refuse
the report plan and all report-score files, and their measured
`report_score_files_opened` counters are zero.

This is recorded as a process incident rather than silently omitted. It does not
change either frozen scientific result, but future schema inspection must use a
header-only reader that cannot emit data rows.

## 6. Output locations

- `runs/issue27ckdd_d0_feasibility_audit_v1_2026-08-25_local/`
- `runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local/`
