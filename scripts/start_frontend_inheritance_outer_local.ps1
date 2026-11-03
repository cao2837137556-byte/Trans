param([switch]$AuthorizeRealComparison)
$ErrorActionPreference = 'Stop'
if (-not $AuthorizeRealComparison) { throw 'Explicit authorization for one bounded input preparation and fixed N3 comparison is required.' }
$outerRoot = Split-Path -Parent $PSScriptRoot
$outerOutput = Join-Path $outerRoot 'runs/frontend_inheritance_outer_comparison_v1_20260909'
if (Test-Path -LiteralPath $outerOutput) { throw 'An attempt already exists. Do not restart.' }
$outerPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$outerController = Join-Path $outerRoot 'repo/ood/issue27frontend_inheritance_outer_control_v1.py'
$env:PYTHONHASHSEED = '2705'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $outerPython -B $outerController check-readiness
if ($LASTEXITCODE -ne 0) { throw 'Readiness failed; no worker launched.' }
$outerProcess = Start-Process -FilePath $outerPython -ArgumentList @('-B', ('"' + $outerController + '"'), 'run-real', '--authorization', 'I_AUTHORIZE_ONE_OUTER_INPUT_PREPARATION_AND_FIXED_N3_COMPARISON') -WorkingDirectory $outerRoot -WindowStyle Hidden -PassThru
Write-Output ('Comparison controller started. PID: ' + $outerProcess.Id)
Write-Output 'Run show_frontend_inheritance_outer_status.ps1 to see progress and verified completion.'
