# CKDA D0 job 158210 tail-recovery implementation — ready for Kimi review

Date: 2026-08-11

Scope: engineering-only recovery of a completed D0 result stage

Original Slurm job: `158210` (`FAILED`)

Original failure phase: `validate_and_finalize`

## 1. Classification

The exact failure is:

```text
TypeError: write_text() got an unexpected keyword argument 'newline'
```

It occurred after census, both real resource pilots, candidate ranking, verdict,
and FINAL/label boundary audit completed.  This is therefore
`POST_RESULT_VALIDATION_PACKAGING_FAILURE`, not scientific evidence against
`I1`, `E3`, or CKDA.

The preserved stage already contains:

- I1 data gate PASS: `4,764,022` sessions and `11,705,453` tokens;
- resource-pilot rows for exactly `E3`, `I1`, both PASS;
- frozen verdict: primary `I1`, optional backup `E3`;
- FINAL opened `0`, labels read `0`, performance embeddings persisted `0`.

## 2. Root cause and complete same-class fix

Python 3.9 does not accept the later `newline` keyword on
`pathlib.Path.write_text`.  Syntax compilation cannot detect this runtime
stdlib API mismatch.

The repair removes all three CKDA-owned occurrences:

1. D0 validator atomic report writer;
2. netFound compatibility-patched source writer;
3. netFound compatibility-audit writer.

All use explicit `Path.open(..., newline="\n")`, `handle.write`, and atomic
`os.replace`.  A new AST regression rejects any future `.write_text` call with
a `newline` keyword across the four CKDA D0 owned modules.  A real atomic-file
contract test checks LF bytes, readback, replacement, and absence of temporary
files.  The validator contract now runs in both login and compute gates.

Local evidence: `36/36` contract tests PASS, validator contract PASS, Bash
syntax PASS, PowerShell parser PASS, `git diff --check` PASS.

## 3. Recovery design

`scripts/issue27ckda_d0_tail_recover_158210.sh` is deliberately pinned to the
failed job and reviewed r2 bundle.  It:

1. requires an explicit tail-recovery authorization distinct from Slurm submit;
2. verifies the recovery kit and complete r2 bundle SHA manifests;
3. requires `sacct` state `FAILED`, exact failure phase, and exact TypeError;
4. verifies preserved census/pilot/verdict/boundary values and both content
   lineage hashes before copying anything;
5. leaves the original hidden stage and `job_failure.txt` unchanged;
6. copies into a new `.tail_recovery.stage`, renames the copied engineering
   marker to prior-failure lineage, and records a recovery-lineage JSON;
7. runs only the corrected validator under the frozen project Python;
8. requires validation PASS with ranking `[I1, E3]`, pilot set `[E3, I1]`, and
   all FINAL/label/embedding counters zero;
9. hashes every recovered top-level file, atomically publishes the result root,
   creates and verifies the pullback, and writes a separate
   `tail_recovery_success.txt` marker.

It does not call `sbatch`, decode PCAP, run a model, reopen source data, touch
FINAL, read labels, or claim that job `158210` completed successfully.

## 4. Requested Kimi review

Please independently decide:

1. Is the failure classification correctly bounded as post-result packaging?
2. Does explicit-open atomic writing preserve the intended LF/atomic semantics?
3. Are the AST and runtime tests sufficient for this observed Python-3.9 API
   failure class?
4. Is copying the failed stage while retaining the original untouched a valid
   no-recompute recovery boundary?
5. Are the exact census/pilot/verdict/FINAL gates sufficient to prevent recovery
   of an incomplete or scientifically invalid stage?
6. Is it acceptable to build the tiny recovery kit after PASS, with execution
   still requiring separate user authorization?

## 5. Authorization boundary

This implementation and document do not authorize recovery execution or any
new HPC submission.  After Kimi PASS, Codex may build the small SHA-pinned kit.
The user must explicitly authorize the login-node tail recovery.  No Slurm
resubmission is planned.
