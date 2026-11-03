param([ValidateSet('T','E','TE')][string]$Stage='TE',
      [switch]$AuthorizeTraining,[switch]$AuthorizeEvaluation)
$ErrorActionPreference='Stop'
if ($Stage.Contains('T') -and -not $AuthorizeTraining) { throw 'Explicit H_AB readout training authorization required.' }
if ($Stage.Contains('E') -and -not $AuthorizeEvaluation) { throw 'Explicit H_AB readout endpoint authorization required.' }
$readoutRoot=Split-Path -Parent $PSScriptRoot
$readoutPython='C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$readoutController=Join-Path $readoutRoot 'repo/ood/issue27frontend_readout_control_v1.py'
$readoutToken='I_AUTHORIZE_ONE_AB_READOUT_PRESERVATION_V1_'+$Stage
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONHASHSEED='2705'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='4'
$env:MKL_NUM_THREADS='4'
$readoutProcess=Start-Process -FilePath $readoutPython -ArgumentList @('-B',('"'+$readoutController+'"'),'run','--stage',$Stage,'--authorization',$readoutToken) -WorkingDirectory $readoutRoot -WindowStyle Hidden -PassThru
Write-Output ('H_AB readout controller PID: '+$readoutProcess.Id+'. Startup is not completion.')
Write-Output 'Status: scripts/show_frontend_ab_readout_preservation_v1.ps1'
