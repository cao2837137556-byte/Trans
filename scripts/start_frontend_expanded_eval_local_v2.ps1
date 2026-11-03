param([Parameter(Mandatory=$true)][string]$NewAttemptAuthorization)
$ErrorActionPreference = 'Stop'
$evalRoot = Split-Path -Parent $PSScriptRoot
$evalPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$evalController = Join-Path $evalRoot 'repo/ood/issue27frontend_expanded_eval_control_v2.py'
if ([string]::IsNullOrWhiteSpace($NewAttemptAuthorization) -or $NewAttemptAuthorization.Contains('"')) { throw 'A new explicit authorization without double quotes is required.' }
$env:PYTHONDONTWRITEBYTECODE = '1'
& $evalPython -B $evalController readiness
if ($LASTEXITCODE -ne 0) { throw 'Readiness failed; no worker launched.' }
$evalProcess = Start-Process -FilePath $evalPython -ArgumentList @('-B', ('"' + $evalController + '"'), 'run', '--new-attempt-authorization', ('"' + $NewAttemptAuthorization + '"')) -WorkingDirectory $evalRoot -WindowStyle Hidden -PassThru
Write-Output ('已启动固定AB扩大测试V2，controller PID：' + $evalProcess.Id)
Write-Output '查看进度：scripts/show_frontend_expanded_eval_status_v2.ps1'
