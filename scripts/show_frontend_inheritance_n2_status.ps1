param([switch]$Once)
$ErrorActionPreference = 'Stop'
$n2Root = Split-Path -Parent $PSScriptRoot
$n2Python = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$n2Controller = Join-Path $n2Root 'repo/ood/issue27frontend_inheritance_n2_control_v1.py'
do {
    if (-not $Once) { Clear-Host }
    Write-Output 'Paper04 N2 development check status'
    $n2Raw = & $n2Python -B $n2Controller status
    if ($LASTEXITCODE -ne 0) { throw 'Status read failed. Do not restart the attempt.' }
    $n2State = $n2Raw | ConvertFrom-Json
    if ($n2State.status -eq 'NOT_STARTED') {
        Write-Output 'NOT_STARTED: no real N2 attempt.'
    } elseif ($n2State.final) {
        Write-Output ('FINAL (seal verified): ' + $n2State.verdict.status)
    } else {
        Write-Output 'PROVISIONAL: final verified supervisor seal is pending. Do not restart.'
    }
    $n2State | ConvertTo-Json -Depth 8 | Write-Output
    if ($Once -or $n2State.final) { break }
    Start-Sleep -Seconds 2
} while ($true)
