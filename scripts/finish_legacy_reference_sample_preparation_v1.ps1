# Finite local completion helper. Never restarts scanning or launches a model.
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskRun = Join-Path $taskRoot 'runs/legacy_reference_sample_preparation_v1_20260917'
$taskPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$taskLock = Join-Path $taskRun 'finalizer_claim.lock'
$taskHandle = [System.IO.File]::Open($taskLock,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
$taskHandle.Dispose()
Set-Location -LiteralPath $taskRoot
while ($true) {
    $taskState = Get-Content -LiteralPath (Join-Path $taskRun 'status.json') -Raw | ConvertFrom-Json
    if ($taskState.status -eq 'MANIFEST_SCAN_COMPLETE_REQUIRES_FINALIZATION') { break }
    if ($taskState.status -in @('STOPPED_NO_RETRY','COMPLETE_SEALED')) { exit 1 }
    Start-Sleep -Seconds 10
}
& $taskPython -B -X utf8 'repo/ood/legacy_reference_sample_finalize_v1.py' *> (Join-Path $taskRun 'finalizer.log')
exit $LASTEXITCODE
