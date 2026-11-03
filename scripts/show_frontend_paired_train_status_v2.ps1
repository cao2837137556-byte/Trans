param([ValidateSet('prepare','train')][string]$Stage='train',[switch]$Once)
$ErrorActionPreference = 'Stop'
$pairedRoot = Split-Path -Parent $PSScriptRoot
$pairedPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$pairedController = Join-Path $pairedRoot 'repo/ood/issue27frontend_paired_train_control_v2.py'
do {
    $pairedText = & $pairedPython -B $pairedController status --stage $Stage
    if ($LASTEXITCODE -ne 0) { throw 'Status verification failed. Do not restart.' }
    $pairedState = $pairedText | ConvertFrom-Json
    Write-Output ('[' + (Get-Date -Format 'HH:mm:ss') + '] ' + $Stage + ': ' + $pairedState.status)
    if ($null -ne $pairedState.arm) { Write-Output ('Arm: ' + $pairedState.arm) }
    if ($null -ne $pairedState.epoch) { Write-Output ('Epoch: ' + $pairedState.epoch + '/' + $pairedState.epochs) }
    if ($null -ne $pairedState.updates) { Write-Output ('Updates: ' + $pairedState.updates + '/' + $pairedState.updates_total) }
    if ($null -ne $pairedState.contexts_complete) { Write-Output ('Prepared contexts: ' + $pairedState.contexts_complete + '/' + $pairedState.contexts_total) }
    if ($null -ne $pairedState.elapsed_seconds) { Write-Output ('Elapsed seconds: ' + [math]::Round($pairedState.elapsed_seconds,1)) }
    if ($pairedState.final) {
        Write-Output 'Finished. Supervisor seal verified; see verdict below.'
        $pairedState.verdict | Format-List
        break
    }
    if ($Once -or $pairedState.status -eq 'NOT_STARTED' -or $pairedState.status -like '*DO_NOT_RESTART*') { break }
    Start-Sleep -Seconds 2
} while ($true)
