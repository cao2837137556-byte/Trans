param([switch]$AuthorizeFixedTrainDiagnostic)
$ErrorActionPreference='Stop'
if (-not $AuthorizeFixedTrainDiagnostic) { throw 'The fixed C2 TRAIN-only diagnostic requires its authorized scope switch.' }
$diagnosticRoot=Split-Path -Parent $PSScriptRoot
$diagnosticPython='C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$diagnosticController=Join-Path $diagnosticRoot 'repo/ood/issue27frontend_transfer_diagnostic_v1.py'
$diagnosticOutput=Join-Path $diagnosticRoot 'runs/frontend_transfer_diagnostic_v1_20260912'
if (Test-Path -LiteralPath $diagnosticOutput) { throw 'Diagnostic attempt already exists. Inspect status; do not retry.' }
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONHASHSEED='2705'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='4'
$env:MKL_NUM_THREADS='4'
& $diagnosticPython -B $diagnosticController check
if ($LASTEXITCODE -ne 0) { throw 'Diagnostic implementation or input identity check failed. No real worker started.' }
$diagnosticProcess=Start-Process -FilePath $diagnosticPython -ArgumentList @('-B',('"'+$diagnosticController+'"'),'run','--authorization','I_AUTHORIZE_ONE_FIXED_C2_TRAIN_ONLY_DIAGNOSTIC_V1') -WorkingDirectory $diagnosticRoot -WindowStyle Hidden -PassThru
Write-Output ('Diagnostic controller PID: '+$diagnosticProcess.Id+'. Startup is not completion.')
Write-Output 'Status: scripts/show_frontend_transfer_diagnostic_v1.ps1'
Write-Output ('Live view: '+(Join-Path $diagnosticOutput 'status.html'))
