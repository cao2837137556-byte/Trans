param([switch]$AuthorizeRealN1)
$ErrorActionPreference = 'Stop'
if (-not $AuthorizeRealN1) { throw 'Explicit authorization for one real N1 fit and restricted checkpoint-container access is required.' }
$n1Root = Split-Path -Parent $PSScriptRoot
$n1Output = Join-Path $n1Root 'runs/frontend_inheritance_n1_fixed_terminal_head_v1_20260908'
if (Test-Path -LiteralPath $n1Output) { throw 'N1 attempt exists. Do not restart.' }
$n1Python = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$n1Controller = Join-Path $n1Root 'repo/ood/issue27frontend_inheritance_n1_control_v1.py'
$env:PYTHONHASHSEED = '2705'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $n1Python -B $n1Controller check-readiness
if ($LASTEXITCODE -ne 0) { throw 'N1 readiness check failed. No worker was launched.' }
$n1Process = Start-Process -FilePath $n1Python -ArgumentList @('-B', ('"' + $n1Controller + '"'), 'run-real', '--authorization', 'I_AUTHORIZE_ONE_REAL_N1_FIT_AND_RESTRICTED_CHECKPOINT_CONTAINER_ACCESS') -WorkingDirectory $n1Root -WindowStyle Hidden -PassThru
Write-Output ('N1 controller dispatched. PID: ' + $n1Process.Id)
Write-Output 'Use show_frontend_inheritance_n1_status.ps1 to inspect startup and completion.'
