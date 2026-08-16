# CKDA D1 local L2 hash-runtime repair (2026-08-16)

## Classification

The first L2 launcher exited during immutable-input preflight because its hidden
Windows PowerShell process did not resolve the `Get-FileHash` cmdlet. No report
plan, report metadata, report embedding, score, metric, or verdict was created.
The engineering-failure record correctly contains a null scientific verdict
and `final_files_opened=0`.

## Repair

The report runner now computes SHA-256 with the .NET
`System.Security.Cryptography.SHA256` API over an explicitly opened read-only
stream. This removes dependence on PowerShell module autoloading while
preserving byte-for-byte SHA-256 semantics. The stream and hasher are disposed
in a `finally` block.

The status script also restricts process detection to `powershell.exe`, avoiding
false positives from parent `pwsh.exe` command lines that merely mention the
report runner.

## Verification boundary

The repaired script must parse under Windows PowerShell 5.1 and complete the
no-authorization preflight with zero report outputs before the authorized L2
retry. Resume identity was not created by the failed attempt, so the repaired
run remains the first report-opening attempt.
