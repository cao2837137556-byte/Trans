param([ValidateSet('P','T','E','TE','PTE')][string]$Stage='PTE')
$ErrorActionPreference='Stop'
$alignedRoot=Split-Path -Parent $PSScriptRoot
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe' -B (Join-Path $alignedRoot 'repo/ood/issue27frontend_aligned_control_v1.py') status --stage $Stage
if ($LASTEXITCODE -ne 0) { throw 'Q/R status verification failed; do not restart.' }
