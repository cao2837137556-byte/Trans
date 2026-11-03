param([switch]$AuthorizeBMetadataRead)
$ErrorActionPreference = 'Stop'
if (-not $AuthorizeBMetadataRead) { throw 'Explicit authorization for one B header metadata pass and membership seal is required.' }
$pairedRoot = Split-Path -Parent $PSScriptRoot
$pairedOutput = Join-Path $pairedRoot 'runs/frontend_paired_metadata_v2_20260909'
if (Test-Path -LiteralPath $pairedOutput) { throw 'An attempt already exists. Do not restart.' }
$pairedPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$pairedController = Join-Path $pairedRoot 'repo/ood/issue27frontend_paired_metadata_control_v2.py'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONHASHSEED = '2705'
& $pairedPython -B $pairedController check-readiness
if ($LASTEXITCODE -ne 0) { throw 'Readiness failed; no worker launched.' }
$pairedProcess = Start-Process -FilePath $pairedPython -ArgumentList @('-B', ('"' + $pairedController + '"'), 'run-real', '--authorization', 'I_AUTHORIZE_ONE_B_ROUTE_METADATA_PASS_AND_MEMBERSHIP_SEAL') -WorkingDirectory $pairedRoot -WindowStyle Hidden -PassThru
Write-Output ('Metadata controller started. PID: ' + $pairedProcess.Id)
Write-Output 'Use show_frontend_paired_metadata_status_v2.ps1 for progress and verified completion.'
