$ErrorActionPreference = 'Stop'
$evalRoot = Split-Path -Parent $PSScriptRoot
& 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe' -B (Join-Path $evalRoot 'repo/ood/issue27frontend_a_expanded_eval_v1.py') status
Write-Output ('状态与结果：' + (Join-Path $evalRoot 'runs/frontend_a_expanded_eval_v1_20260911'))
