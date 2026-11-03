param([Parameter(Mandatory=$true)][ValidateSet('prepare','train')][string]$Stage,
      [switch]$AuthorizeFeaturePreparation,[switch]$AuthorizePairedTraining)
$ErrorActionPreference = 'Stop'
if ($Stage -eq 'prepare' -and -not $AuthorizeFeaturePreparation) { throw 'Explicit authorization for one feature preparation is required.' }
if ($Stage -eq 'train' -and -not $AuthorizePairedTraining) { throw 'Explicit authorization for one paired training and terminal check is required.' }
$pairedRoot = Split-Path -Parent $PSScriptRoot
$pairedPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$pairedController = Join-Path $pairedRoot 'repo/ood/issue27frontend_paired_train_control_v2.py'
$pairedToken = if ($Stage -eq 'prepare') { 'I_AUTHORIZE_ONE_PAIRED_FEATURE_PREPARATION' } else { 'I_AUTHORIZE_ONE_PAIRED_A_AB_TRAINING_AND_TERMINAL_CHECK' }
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONHASHSEED = '2705'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'
& $pairedPython -B $pairedController check-readiness --stage $Stage
if ($LASTEXITCODE -ne 0) { throw 'Readiness failed. No worker launched.' }
$pairedProcess = Start-Process -FilePath $pairedPython -ArgumentList @('-B', ('"' + $pairedController + '"'), 'run-real', '--stage', $Stage, '--authorization', $pairedToken) -WorkingDirectory $pairedRoot -WindowStyle Hidden -PassThru
Write-Output ('Started ' + $Stage + ' controller PID ' + $pairedProcess.Id)
Write-Output ('View progress: scripts/show_frontend_paired_train_status_v2.ps1 -Stage ' + $Stage)
