$ErrorActionPreference = 'Stop'
$evalRoot = Split-Path -Parent $PSScriptRoot
$evalPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$evalController = Join-Path $evalRoot 'repo/ood/issue27frontend_a_expanded_eval_v1.py'
& $evalPython -B $evalController readiness
if ($LASTEXITCODE -ne 0) { throw 'Readiness failed; no A evaluation launched.' }
$evalProcess = Start-Process -FilePath $evalPython -ArgumentList @('-B', ('"' + $evalController + '"'), 'run') -WorkingDirectory $evalRoot -WindowStyle Hidden -PassThru
Write-Output ('A评估已启动，controller PID：' + $evalProcess.Id)
