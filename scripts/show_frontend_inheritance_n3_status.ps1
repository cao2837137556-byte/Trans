param([switch]$Once)
$ErrorActionPreference = 'Stop'
$n3Root = Split-Path -Parent $PSScriptRoot
$n3Python = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$n3Controller = Join-Path $n3Root 'repo/ood/issue27frontend_inheritance_n3_control_v1.py'
do {
    if (-not $Once) { Clear-Host }
    Write-Output 'Paper04 N3 conservative joint repair status'
    $n3Raw = & $n3Python -B $n3Controller status
    if ($LASTEXITCODE -ne 0) { throw 'Status read failed. Do not restart the attempt.' }
    $n3State = $n3Raw | ConvertFrom-Json
    if ($n3State.status -eq 'NOT_STARTED') {
        Write-Output 'NOT_STARTED: no real N3 attempt.'
    } elseif ($n3State.final) {
        Write-Output ('FINAL (seal verified): ' + $n3State.verdict.status)
    } else {
        Write-Output 'PROVISIONAL: final verified supervisor seal is pending. Do not restart.'
    }
    $n3State | ConvertTo-Json -Depth 8 | Write-Output
    if ($Once -or $n3State.final) { break }
    Start-Sleep -Seconds 2
} while ($true)
