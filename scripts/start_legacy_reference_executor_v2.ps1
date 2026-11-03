param([Parameter(Mandatory=$true)][string]$ScopeFile, [switch]$AuthorizeChain)
$ErrorActionPreference = 'Stop'
if (-not $AuthorizeChain) { throw 'Explicit authorization for the complete feature/train/DEV/conditional-HOLDOUT chain is required.' }
$referenceRoot = Split-Path -Parent $PSScriptRoot
$referenceScope = (Resolve-Path -LiteralPath $ScopeFile).Path
$referenceSpec = Get-Content -LiteralPath $referenceScope -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $referenceSpec.execution_authorized) { throw 'This is a review template, not an authorized execution scope.' }
$referencePython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$referenceControl = Join-Path $referenceRoot 'repo/ood/legacy_reference_executor_control_v2.py'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONHASHSEED='27'
$env:PYTHONIOENCODING='utf-8'
Push-Location -LiteralPath $referenceRoot
try {
    & $referencePython -B -X utf8 $referenceControl validate --scope $referenceScope --authorize-chain
    if ($LASTEXITCODE -ne 0) { throw 'Preflight failed; no experiment was started.' }
} finally { Pop-Location }
$referenceLog = Join-Path (Split-Path -Parent $referenceScope) ('launch_' + [DateTime]::UtcNow.Ticks)
$referenceProcess = Start-Process -FilePath $referencePython -ArgumentList @('-B','-X','utf8',('"' + $referenceControl + '"'),'run','--scope',('"' + $referenceScope + '"'),'--authorize-chain') -WorkingDirectory $referenceRoot -WindowStyle Hidden -RedirectStandardOutput ($referenceLog+'.stdout.log') -RedirectStandardError ($referenceLog+'.stderr.log') -PassThru
Write-Output ('Supervisor PID: '+$referenceProcess.Id+'. Startup is not completion.')
Write-Output ('Status: '+(Join-Path $referenceRoot ('runs/'+$referenceSpec.output_run_name+'/status.json')))
Write-Output 'Use show_legacy_reference_executor_v1.ps1 -OutputDirectory <run> [-Watch]. No LLM polling is required.'

