param(
  [ValidateSet('P','T','E','PTE')][string]$Stage = 'PTE',
  [switch]$AuthorizeTeacherPreparation,
  [switch]$AuthorizeThreeArmTraining,
  [switch]$AuthorizeEndpointEvaluation
)
$ErrorActionPreference = 'Stop'
if ($Stage.Contains('P') -and -not $AuthorizeTeacherPreparation) { throw 'P teacher preparation requires explicit authorization.' }
if ($Stage.Contains('T') -and -not $AuthorizeThreeArmTraining) { throw 'T three-arm training requires explicit authorization.' }
if ($Stage.Contains('E') -and -not $AuthorizeEndpointEvaluation) { throw 'E endpoint evaluation requires explicit authorization.' }
$transferRoot = Split-Path -Parent $PSScriptRoot
$transferPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$transferController = Join-Path $transferRoot 'repo/ood/issue27frontend_transfer_control_v1.py'
$transferToken = 'I_AUTHORIZE_ONE_TASK_KNOWLEDGE_TRANSFER_' + $Stage
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONHASHSEED = '2705'
$env:PYTHONIOENCODING = 'utf-8'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'
$transferProcess = Start-Process -FilePath $transferPython -ArgumentList @('-B', ('"' + $transferController + '"'), 'run', '--stage', $Stage, '--authorization', $transferToken) -WorkingDirectory $transferRoot -WindowStyle Hidden -PassThru
Write-Output ('Controller PID: ' + $transferProcess.Id + '. This is startup, not proof that input checks passed.')
Write-Output 'View status: scripts/show_frontend_task_knowledge_transfer_v1.ps1'
