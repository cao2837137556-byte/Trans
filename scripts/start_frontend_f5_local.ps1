[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('preflight','train','evaluate')][string]$Stage,
    [Parameter(Mandatory=$true)][string]$Authorization
)
$ErrorActionPreference = 'Stop'
$f5Root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$f5Python = 'C:\Users\28371\AppData\Local\Programs\Python\Python39\python.exe'
$f5Runner = Join-Path $f5Root 'repo\ood\issue27frontend_f5_unified_student_runner_v1.py'
$f5Receipt = Join-Path $f5Root 'runs\frontend_f5_implementation_v1_20260906\stage_i_acceptance.json'
$f5Output = Join-Path $f5Root 'runs\frontend_f5_unified_student_v1_20260906_local'
$f5Tokens = @{
    preflight = 'I_AUTHORIZE_F5_REAL_P_TEACHER_ONLY'
    train = 'I_AUTHORIZE_F5_REAL_T_ONE_TRAJECTORY'
    evaluate = 'I_AUTHORIZE_F5_REAL_K_ONCE'
}
if ($Authorization -cne $f5Tokens[$Stage]) { throw 'Explicit matching stage authorization is required.' }
if (-not (Test-Path -LiteralPath $f5Receipt)) { throw 'Stage I acceptance is not complete.' }
if (-not (Test-Path -LiteralPath $f5Python)) { throw 'Frozen Python runtime is absent; do not install a fallback.' }
foreach ($f5StopName in @('verdict.json','engineering_failure.json','resource_stop.json','run.lock')) {
    if (Test-Path -LiteralPath (Join-Path $f5Output $f5StopName)) {
        throw "Existing ${f5StopName}: inspect first. Never delete checkpoints or start a second trajectory."
    }
}
# Logs live outside the sealed scientific result tree because stdout closes last.
$f5Control = Join-Path $f5Root 'runs\frontend_f5_unified_student_v1_20260906_local_control'
New-Item -ItemType Directory -Path $f5Control -Force | Out-Null
$f5Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$f5Stdout = Join-Path $f5Control "$Stage-$f5Stamp.stdout.log"
$f5Stderr = Join-Path $f5Control "$Stage-$f5Stamp.stderr.log"
$env:PYTHONHASHSEED = '2705'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'
$f5Arguments = @('-u', ('"' + $f5Runner + '"'), '--stage', $Stage, '--authorization', $Authorization)
$f5Process = Start-Process -FilePath $f5Python -ArgumentList $f5Arguments `
    -WorkingDirectory $f5Root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $f5Stdout -RedirectStandardError $f5Stderr
Write-Output "Started F5 $Stage PID=$($f5Process.Id). This launch is not a scientific PASS."
Write-Output "stdout=$f5Stdout"
Write-Output "stderr=$f5Stderr"
Write-Output 'The Python process is independent of this chat and network connectivity.'
