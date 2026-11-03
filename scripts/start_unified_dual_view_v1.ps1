param([ValidateSet('P','T','E','PTE')][string]$Stage='PTE',
      [switch]$AuthorizePreparation,[switch]$AuthorizeTraining,[switch]$AuthorizeEvaluation,
      [switch]$AuthorizeExactE3CacheRows)
$ErrorActionPreference='Stop'
if ($Stage.Contains('P') -and -not $AuthorizePreparation) { throw 'Explicit TRAIN preparation authorization required.' }
if ($Stage.Contains('T') -and -not $AuthorizeTraining) { throw 'Explicit two-arm training authorization required.' }
if ($Stage.Contains('E') -and -not $AuthorizeEvaluation) { throw 'Explicit endpoint evaluation authorization required.' }
if (($Stage.Contains('P') -or $Stage.Contains('E')) -and -not $AuthorizeExactE3CacheRows) { throw 'Explicit access to the recipe-scoped E3 cache rows required.' }
$dualRoot=Split-Path -Parent $PSScriptRoot
$dualPython='C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$dualController=Join-Path $dualRoot 'repo/ood/issue27dualview_control_v1.py'
$dualToken='I_AUTHORIZE_ONE_DUAL_VIEW_V1_'+$Stage+'_INCLUDING_EXACT_E3_CACHE_ROWS'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONHASHSEED='2705'
$env:PYTHONIOENCODING='utf-8'
$env:OMP_NUM_THREADS='4'
$env:MKL_NUM_THREADS='4'
$dualProcess=Start-Process -FilePath $dualPython -ArgumentList @('-B',('"'+$dualController+'"'),'run','--stage',$Stage,'--authorization',$dualToken) -WorkingDirectory $dualRoot -WindowStyle Hidden -PassThru
Write-Output ('Dual-view controller PID: '+$dualProcess.Id+'. Startup is not completion.')
Write-Output 'Status: scripts/show_unified_dual_view_v1.ps1'
