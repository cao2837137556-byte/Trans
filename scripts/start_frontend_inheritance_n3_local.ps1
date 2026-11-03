param([switch]$AuthorizeRealN3)
$ErrorActionPreference = 'Stop'
if (-not $AuthorizeRealN3) { throw 'Explicit authorization for one real N3 conservative joint repair and final-reference container access is required.' }
$n3Root = Split-Path -Parent $PSScriptRoot
$n3Output = Join-Path $n3Root 'runs/frontend_inheritance_n3_conservative_joint_repair_v1_20260908'
if (Test-Path -LiteralPath $n3Output) { throw 'N3 attempt exists. Do not restart.' }
$n3Python = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$n3Controller = Join-Path $n3Root 'repo/ood/issue27frontend_inheritance_n3_control_v1.py'
$env:PYTHONHASHSEED = '2705'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $n3Python -B $n3Controller check-readiness
if ($LASTEXITCODE -ne 0) { throw 'N3 readiness check failed. No worker was launched.' }
$n3Process = Start-Process -FilePath $n3Python -ArgumentList @('-B', ('"' + $n3Controller + '"'), 'run-real', '--authorization', 'I_AUTHORIZE_ONE_REAL_N3_CONSERVATIVE_FIT_AND_RESTRICTED_INPUT_ACCESS') -WorkingDirectory $n3Root -WindowStyle Hidden -PassThru
Write-Output ('N3 controller dispatched. PID: ' + $n3Process.Id)
Write-Output 'Use show_frontend_inheritance_n3_status.ps1 to inspect startup and completion.'
