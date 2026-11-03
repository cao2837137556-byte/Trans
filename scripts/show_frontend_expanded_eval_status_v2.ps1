$ErrorActionPreference = 'Stop'
$evalRoot = Split-Path -Parent $PSScriptRoot
$evalPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
& $evalPython -B (Join-Path $evalRoot 'repo/ood/issue27frontend_expanded_eval_control_v2.py') status
$evalOut = Join-Path $evalRoot 'runs/frontend_expanded_eval_v2_20260910'
Write-Output ('状态：' + (Join-Path $evalOut 'status.md'))
Write-Output ('结果：' + (Join-Path $evalOut 'result.md'))
