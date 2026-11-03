param([ValidateSet('T','E','TE')][string]$Stage='TE',
      [switch]$AuthorizeTraining,[switch]$AuthorizeEvaluation)
$ErrorActionPreference='Stop'
if ($Stage.Contains('T') -and -not $AuthorizeTraining) { throw 'Explicit AB-start training authorization required.' }
if ($Stage.Contains('E') -and -not $AuthorizeEvaluation) { throw 'Explicit AB-start endpoint authorization required.' }
$abstartRoot=Split-Path -Parent $PSScriptRoot
$abstartPython='C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$abstartController=Join-Path $abstartRoot 'repo/ood/issue27frontend_abstart_control_v1.py'
$abstartToken='I_AUTHORIZE_ONE_AB_START_CONTROL_V1_'+$Stage
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONHASHSEED='2705'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='4'
$env:MKL_NUM_THREADS='4'
$abstartProcess=Start-Process -FilePath $abstartPython -ArgumentList @('-B',('"'+$abstartController+'"'),'run','--stage',$Stage,'--authorization',$abstartToken) -WorkingDirectory $abstartRoot -WindowStyle Hidden -PassThru
Write-Output ('AB-start controller PID: '+$abstartProcess.Id+'. Startup is not completion.')
Write-Output 'Status: scripts/show_frontend_ab_start_control_v1.ps1'
