param([switch]$AuthorizeRealN2)
$ErrorActionPreference = 'Stop'
if (-not $AuthorizeRealN2) { throw 'Explicit authorization for one real N2 development check and final-reference container access is required.' }
$n2Root = Split-Path -Parent $PSScriptRoot
$n2Output = Join-Path $n2Root 'runs/frontend_inheritance_n2_fixed_witness_development_v1_20260908'
if (Test-Path -LiteralPath $n2Output) { throw 'N2 attempt exists. Do not restart.' }
$n2Python = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$n2Controller = Join-Path $n2Root 'repo/ood/issue27frontend_inheritance_n2_control_v1.py'
$env:PYTHONHASHSEED = '2705'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $n2Python -B $n2Controller check-readiness
if ($LASTEXITCODE -ne 0) { throw 'N2 readiness check failed. No worker was launched.' }
$n2Process = Start-Process -FilePath $n2Python -ArgumentList @('-B', ('"' + $n2Controller + '"'), 'run-real', '--authorization', 'I_AUTHORIZE_ONE_REAL_N2_DEV_CHECK_AND_FINAL_REFERENCE_CONTAINER_ACCESS') -WorkingDirectory $n2Root -WindowStyle Hidden -PassThru
Write-Output ('N2 controller dispatched. PID: ' + $n2Process.Id)
Write-Output 'Use show_frontend_inheritance_n2_status.ps1 to inspect startup and completion.'
