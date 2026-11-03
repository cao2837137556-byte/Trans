$ErrorActionPreference='Stop'
$dualRoot=Split-Path -Parent $PSScriptRoot
$dualPython='C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
& $dualPython -B (Join-Path $dualRoot 'repo/ood/issue27dualview_control_v1.py') status --stage PTE
