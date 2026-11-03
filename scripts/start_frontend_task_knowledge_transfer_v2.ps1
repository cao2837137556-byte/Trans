param([ValidateSet('T','E','TE')][string]$Stage='TE',
      [switch]$AuthorizeNewTrainingAttempt,[switch]$AuthorizeEndpointEvaluation)
$ErrorActionPreference='Stop'
if ($Stage.Contains('T') -and -not $AuthorizeNewTrainingAttempt) { throw 'A new V2 training attempt requires explicit authorization after the V1 STOP.' }
if ($Stage.Contains('E') -and -not $AuthorizeEndpointEvaluation) { throw 'V2 endpoint evaluation requires explicit authorization.' }
$transferRoot=Split-Path -Parent $PSScriptRoot
$transferPython='C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$transferController=Join-Path $transferRoot 'repo/ood/issue27frontend_transfer_control_v2.py'
$transferToken='I_AUTHORIZE_ONE_NEW_TASK_KNOWLEDGE_TRANSFER_V2_'+$Stage
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONHASHSEED='2705'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='4'
$env:MKL_NUM_THREADS='4'
$transferProcess=Start-Process -FilePath $transferPython -ArgumentList @('-B',('"'+$transferController+'"'),'run','--stage',$Stage,'--authorization',$transferToken) -WorkingDirectory $transferRoot -WindowStyle Hidden -PassThru
Write-Output ('V2 controller PID: '+$transferProcess.Id+'. Verify status; startup is not completion.')
Write-Output 'Status: scripts/show_frontend_task_knowledge_transfer_v2.ps1'
