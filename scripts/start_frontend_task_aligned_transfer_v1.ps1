param([ValidateSet('P','T','E','TE','PTE')][string]$Stage='PTE',
      [switch]$AuthorizePreparation,[switch]$AuthorizeTraining,[switch]$AuthorizeEvaluation)
$ErrorActionPreference='Stop'
if ($Stage.Contains('P') -and -not $AuthorizePreparation) { throw 'Explicit Q/R preparation authorization required.' }
if ($Stage.Contains('T') -and -not $AuthorizeTraining) { throw 'Explicit Q/R training authorization required.' }
if ($Stage.Contains('E') -and -not $AuthorizeEvaluation) { throw 'Explicit Q/R endpoint authorization required.' }
$alignedRoot=Split-Path -Parent $PSScriptRoot
$alignedPython='C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$alignedController=Join-Path $alignedRoot 'repo/ood/issue27frontend_aligned_control_v1.py'
$alignedToken='I_AUTHORIZE_ONE_TASK_ALIGNED_TRANSFER_V1_'+$Stage
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONHASHSEED='2705'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='4'
$env:MKL_NUM_THREADS='4'
$alignedProcess=Start-Process -FilePath $alignedPython -ArgumentList @('-B',('"'+$alignedController+'"'),'run','--stage',$Stage,'--authorization',$alignedToken) -WorkingDirectory $alignedRoot -WindowStyle Hidden -PassThru
Write-Output ('Q/R controller PID: '+$alignedProcess.Id+'. Startup is not completion.')
Write-Output 'Status: scripts/show_frontend_task_aligned_transfer_v1.ps1'
