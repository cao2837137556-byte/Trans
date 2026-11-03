param([Parameter(Mandatory=$true)][string]$ScopeFile, [switch]$AuthorizeChain)
$ErrorActionPreference = 'Stop'
if (-not $AuthorizeChain) { throw 'One explicit PREPARE/TRAIN_B/TRAIN_C/CHECK chain authorization is required.' }
$enhancementRoot = Split-Path -Parent $PSScriptRoot
$enhancementScope = (Resolve-Path -LiteralPath $ScopeFile).Path
$enhancementSpec = Get-Content -LiteralPath $enhancementScope -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $enhancementSpec.execution_authorized) { throw 'Scope is a review template, not an authorized run.' }
$enhancementPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$enhancementControl = Join-Path $enhancementRoot 'repo/ood/legacy_cic2022_enhancement_control_v1.py'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONHASHSEED = '27'
$env:PYTHONIOENCODING = 'utf-8'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'
Push-Location -LiteralPath $enhancementRoot
try {
    & $enhancementPython -B $enhancementControl validate --scope $enhancementScope --authorize-chain
    if ($LASTEXITCODE -ne 0) { throw 'Preflight failed; no experiment was started.' }
} finally { Pop-Location }
$enhancementLogBase = Join-Path (Split-Path -Parent $enhancementScope) ('launch_' + [DateTime]::UtcNow.Ticks)
$enhancementProcess = Start-Process -FilePath $enhancementPython -ArgumentList @('-B', ('"' + $enhancementControl + '"'), 'run', '--scope', ('"' + $enhancementScope + '"'), '--authorize-chain') -WorkingDirectory $enhancementRoot -WindowStyle Hidden -RedirectStandardOutput ($enhancementLogBase + '.stdout.log') -RedirectStandardError ($enhancementLogBase + '.stderr.log') -PassThru
Write-Output ('Supervisor PID: ' + $enhancementProcess.Id + '. Startup is not completion.')
Write-Output ('Startup logs: ' + $enhancementLogBase + '.*.log')
Write-Output ('Status directory: ' + (Join-Path $enhancementRoot ('runs/' + $enhancementSpec.output_run_name)))
Write-Output 'Use scripts/show_legacy_cic2022_enhancement_v1.ps1 -OutputDirectory <status directory>.'
